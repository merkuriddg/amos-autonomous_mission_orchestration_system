#!/usr/bin/env python3
"""AMOS Phase 24 — Apache Kafka Adapter

High-throughput streaming adapter for AMOS data pipelines.
Requires: kafka-python (pip install kafka-python)

Topics:
  amos.tracks      — fused track updates
  amos.detections  — raw sensor detections
  amos.commands    — command directives
  amos.events      — system events / alerts
  amos.telemetry   — asset telemetry
  amos.audit       — security audit events

Consumer group: amos-c2-{instance_id}
"""

import json
import time
import logging
import threading
import uuid
from datetime import datetime, timezone

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.adapter_base import ProtocolAdapter
from core.data_model import Track, Detection, Command, SensorReading, Message

log = logging.getLogger("amos.kafka")

TOPIC_MAP = {
    "Track": "amos.tracks",
    "Detection": "amos.detections",
    "Command": "amos.commands",
    "SensorReading": "amos.telemetry",
    "Message": "amos.events",
}


class KafkaAdapter(ProtocolAdapter):
    """Apache Kafka adapter for high-throughput AMOS data streaming."""

    def __init__(self, bootstrap_servers="localhost:9092",
                 group_id=None, auto_offset_reset="latest"):
        super().__init__(
            adapter_id="kafka", protocol="Kafka",
            description="Apache Kafka for high-throughput data pipelines")
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id or f"amos-c2-{uuid.uuid4().hex[:6]}"
        self.auto_offset_reset = auto_offset_reset
        self.producer = None
        self.consumer = None
        self._inbox = []
        self._inbox_lock = threading.Lock()
        self._consuming = False
        self._consumer_thread = None
        self._standalone = False

    def connect(self, **kwargs) -> bool:
        try:
            from kafka import KafkaProducer, KafkaConsumer

            # Producer — for emitting data
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                retries=3,
            )

            # Consumer — for ingesting data
            self.consumer = KafkaConsumer(
                *list(TOPIC_MAP.values()),
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                consumer_timeout_ms=100,
            )

            self._consuming = True
            self._consumer_thread = threading.Thread(
                target=self._consume_loop, daemon=True)
            self._consumer_thread.start()

            self.connected = True
            self.stats["connected_at"] = time.time()
            log.info(f"Kafka connected: {self.bootstrap_servers}")
            return True
        except ImportError:
            log.info("kafka-python not installed — Kafka in standalone mode")
            self._standalone = True
            self.connected = True
            self.stats["connected_at"] = time.time()
            return True
        except Exception as e:
            self._record_error(str(e))
            log.error(f"Kafka connect failed: {e}")
            # Fall back to standalone
            self._standalone = True
            self.connected = True
            self.stats["connected_at"] = time.time()
            log.info("Kafka running in standalone mode (no broker)")
            return True

    def disconnect(self) -> bool:
        self._consuming = False
        if self.producer:
            try:
                self.producer.flush(timeout=5)
                self.producer.close(timeout=5)
            except Exception:
                pass
        if self.consumer:
            try:
                self.consumer.close()
            except Exception:
                pass
        self.connected = False
        log.info("Kafka disconnected")
        return True

    def ingest(self) -> list:
        """Return pending Kafka messages as canonical objects."""
        items = []
        with self._inbox_lock:
            raw = list(self._inbox)
            self._inbox.clear()

        for record in raw:
            topic = record.get("topic", "")
            value = record.get("value", {})
            try:
                if topic == "amos.tracks":
                    items.append(Track.from_dict(value))
                elif topic == "amos.detections":
                    det = Detection.from_dict(value)
                    det.adapter_id = self.adapter_id
                    items.append(det)
                elif topic == "amos.commands":
                    items.append(Command.from_dict(value))
                elif topic == "amos.telemetry":
                    items.append(SensorReading.from_dict(value))
                elif topic == "amos.events":
                    items.append(Message.from_dict(value))
                else:
                    items.append(Message(
                        message_type="FREE_TEXT", originator=self.adapter_id,
                        body=json.dumps(value), protocol="Kafka",
                        adapter_id=self.adapter_id,
                        metadata={"kafka_topic": topic},
                    ))
            except Exception:
                pass

        if items:
            self._record_in(len(items))
        return items

    def emit(self, data) -> bool:
        """Produce a canonical object to the appropriate Kafka topic."""
        if not self.connected:
            return False
        try:
            d = data.to_dict() if hasattr(data, "to_dict") else data
            type_name = type(data).__name__ if not isinstance(data, dict) else "Message"
            topic = TOPIC_MAP.get(type_name, "amos.events")
            key = d.get("id", "")

            if self._standalone:
                self._record_out(1, len(json.dumps(d, default=str)))
                return True

            self.producer.send(topic, key=key, value=d)
            self._record_out(1, len(json.dumps(d, default=str)))
            return True
        except Exception as e:
            self._record_error(str(e))
            return False

    def produce_raw(self, topic: str, key: str, value: dict):
        """Produce arbitrary data to a Kafka topic."""
        if self.producer and not self._standalone:
            self.producer.send(topic, key=key, value=value)
            self._record_out()
        elif self._standalone:
            self._record_out()

    def replay_from_offset(self, topic: str, offset: int = 0, limit: int = 100) -> list:
        """Replay historical messages from a specific offset."""
        if self._standalone:
            return []
        try:
            from kafka import KafkaConsumer, TopicPartition
            replay_consumer = KafkaConsumer(
                bootstrap_servers=self.bootstrap_servers,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                consumer_timeout_ms=5000,
            )
            partitions = replay_consumer.partitions_for_topic(topic)
            if not partitions:
                replay_consumer.close()
                return []
            tp = TopicPartition(topic, 0)
            replay_consumer.assign([tp])
            replay_consumer.seek(tp, offset)
            messages = []
            for msg in replay_consumer:
                messages.append({"offset": msg.offset, "key": msg.key,
                                 "value": msg.value, "timestamp": msg.timestamp})
                if len(messages) >= limit:
                    break
            replay_consumer.close()
            return messages
        except Exception as e:
            log.error(f"Kafka replay failed: {e}")
            return []

    def _consume_loop(self):
        """Background consumer loop."""
        while self._consuming:
            try:
                if not self.consumer:
                    time.sleep(1)
                    continue
                records = self.consumer.poll(timeout_ms=200)
                for tp, msgs in records.items():
                    for msg in msgs:
                        with self._inbox_lock:
                            self._inbox.append({
                                "topic": msg.topic,
                                "value": msg.value,
                                "key": msg.key,
                                "offset": msg.offset,
                                "timestamp": msg.timestamp,
                            })
                            if len(self._inbox) > 5000:
                                self._inbox = self._inbox[-5000:]
            except Exception as e:
                if self._consuming:
                    log.error(f"Kafka consume error: {e}")
                    time.sleep(1)

    def get_status(self) -> dict:
        base = super().get_status()
        base["bootstrap_servers"] = self.bootstrap_servers
        base["group_id"] = self.group_id
        base["standalone"] = self._standalone
        base["topics"] = list(TOPIC_MAP.values())
        base["inbox_pending"] = len(self._inbox)
        return base
