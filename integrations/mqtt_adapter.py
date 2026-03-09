#!/usr/bin/env python3
"""AMOS Phase 24 — MQTT Adapter

Connects AMOS to MQTT brokers for lightweight tactical messaging.
Requires: paho-mqtt (pip install paho-mqtt)

Topic structure:
  amos/{domain}/{asset_id}/{data_type}
  amos/tracks/{track_id}
  amos/detections/{sensor_id}
  amos/commands/{target_id}
  amos/alerts/{severity}

QoS mapping:
  FLASH     → QoS 2 (exactly once)
  IMMEDIATE → QoS 2
  PRIORITY  → QoS 1 (at least once)
  ROUTINE   → QoS 0 (fire and forget)
"""

import json
import time
import logging
import threading
from datetime import datetime, timezone

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mos_core.adapter_base import ProtocolAdapter
from mos_core.data_model import Track, Detection, Command, SensorReading, Message

log = logging.getLogger("amos.mqtt")

PRIORITY_QOS = {"FLASH": 2, "IMMEDIATE": 2, "PRIORITY": 1, "ROUTINE": 0}


class MQTTAdapter(ProtocolAdapter):
    """MQTT pub/sub adapter for AMOS."""

    def __init__(self, broker_host="localhost", broker_port=1883,
                 client_id="amos-c2", username="", password="",
                 tls_enabled=False, ca_cert=None):
        super().__init__(
            adapter_id="mqtt", protocol="MQTT",
            description="MQTT broker for lightweight tactical messaging")
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        self.username = username
        self.password = password
        self.tls_enabled = tls_enabled
        self.ca_cert = ca_cert
        self.client = None
        self._inbox = []          # received messages
        self._inbox_lock = threading.Lock()
        self._subscriptions = []  # active topic subscriptions

    def connect(self, **kwargs) -> bool:
        try:
            import paho.mqtt.client as mqtt
            self.client = mqtt.Client(client_id=self.client_id,
                                      protocol=mqtt.MQTTv311)
            if self.username:
                self.client.username_pw_set(self.username, self.password)
            if self.tls_enabled:
                self.client.tls_set(ca_certs=self.ca_cert)

            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect

            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            self.connected = True
            self.stats["connected_at"] = time.time()
            log.info(f"MQTT connected: {self.broker_host}:{self.broker_port}")
            return True
        except ImportError:
            log.warning("paho-mqtt not installed — run: pip install paho-mqtt")
            return False
        except Exception as e:
            self._record_error(str(e))
            log.error(f"MQTT connect failed: {e}")
            return False

    def disconnect(self) -> bool:
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
        self.connected = False
        log.info("MQTT disconnected")
        return True

    def subscribe(self, topic: str, qos: int = 1):
        """Subscribe to an MQTT topic."""
        if self.client and self.connected:
            self.client.subscribe(topic, qos)
            self._subscriptions.append(topic)
            log.info(f"MQTT subscribed: {topic} (QoS {qos})")

    def ingest(self) -> list:
        """Return pending messages from subscriptions as canonical objects."""
        items = []
        with self._inbox_lock:
            raw_messages = list(self._inbox)
            self._inbox.clear()

        for msg in raw_messages:
            topic = msg.get("topic", "")
            payload = msg.get("payload", {})

            # Route based on topic structure
            if "/tracks/" in topic or "/track" in topic:
                try:
                    trk = Track.from_dict(payload)
                    trk.metadata["mqtt_topic"] = topic
                    items.append(trk)
                except Exception:
                    pass
            elif "/detections/" in topic or "/detection" in topic:
                try:
                    det = Detection.from_dict(payload)
                    det.adapter_id = self.adapter_id
                    det.metadata["mqtt_topic"] = topic
                    items.append(det)
                except Exception:
                    pass
            elif "/commands/" in topic or "/command" in topic:
                try:
                    cmd = Command.from_dict(payload)
                    cmd.adapter_id = self.adapter_id
                    items.append(cmd)
                except Exception:
                    pass
            elif "/readings/" in topic or "/sensor" in topic:
                try:
                    sr = SensorReading.from_dict(payload)
                    sr.adapter_id = self.adapter_id
                    items.append(sr)
                except Exception:
                    pass
            else:
                # Generic message
                items.append(Message(
                    message_type="FREE_TEXT",
                    originator=self.adapter_id,
                    body=json.dumps(payload) if isinstance(payload, dict) else str(payload),
                    protocol="MQTT",
                    adapter_id=self.adapter_id,
                    metadata={"mqtt_topic": topic},
                ))

        if items:
            self._record_in(len(items))
        return items

    def emit(self, data) -> bool:
        """Publish a canonical object to the appropriate MQTT topic."""
        if not self.client or not self.connected:
            return False
        try:
            d = data.to_dict() if hasattr(data, "to_dict") else data
            type_name = type(data).__name__ if not isinstance(data, dict) else "message"
            priority = d.get("priority", "ROUTINE")
            qos = PRIORITY_QOS.get(priority, 0)

            # Determine topic
            if isinstance(data, Track):
                topic = f"amos/tracks/{data.id}"
            elif isinstance(data, Detection):
                topic = f"amos/detections/{data.sensor_id or data.id}"
            elif isinstance(data, Command):
                targets = data.target_ids[0] if data.target_ids else "all"
                topic = f"amos/commands/{targets}"
            elif isinstance(data, SensorReading):
                topic = f"amos/readings/{data.sensor_id or data.id}"
            elif isinstance(data, Message):
                topic = f"amos/messages/{data.message_type.lower()}"
            else:
                topic = f"amos/data/{type_name.lower()}"

            payload = json.dumps(d, default=str)
            self.client.publish(topic, payload, qos=qos)
            self._record_out(1, len(payload))
            return True
        except Exception as e:
            self._record_error(str(e))
            return False

    def publish_raw(self, topic: str, payload: dict, qos: int = 0):
        """Publish arbitrary JSON to a topic."""
        if self.client and self.connected:
            self.client.publish(topic, json.dumps(payload, default=str), qos=qos)
            self._record_out()

    # ── Callbacks ─────────────────────────────────────────
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info("MQTT broker connected")
            # Re-subscribe on reconnect
            for topic in self._subscriptions:
                client.subscribe(topic, 1)
        else:
            log.error(f"MQTT connect rc={rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {"raw": msg.payload.decode("utf-8", errors="ignore")}
        with self._inbox_lock:
            self._inbox.append({
                "topic": msg.topic,
                "payload": payload,
                "qos": msg.qos,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            if len(self._inbox) > 1000:
                self._inbox = self._inbox[-1000:]
        self._record_in(1, len(msg.payload))

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            log.warning(f"MQTT unexpected disconnect (rc={rc}), reconnecting…")

    def get_status(self) -> dict:
        base = super().get_status()
        base["broker"] = f"{self.broker_host}:{self.broker_port}"
        base["subscriptions"] = list(self._subscriptions)
        base["inbox_pending"] = len(self._inbox)
        base["tls"] = self.tls_enabled
        return base
