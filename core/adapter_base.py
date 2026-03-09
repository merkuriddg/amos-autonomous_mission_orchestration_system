#!/usr/bin/env python3
"""AMOS Phase 23 — Protocol Adapter Framework

Abstract base class for all protocol adapters (MAVLink, CoT, MQTT, Link-16, …)
and AdapterManager for lifecycle management, health monitoring, and
normalised data routing into the AMOS engine pipeline.
"""

import time
import uuid
import threading
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from core.data_model import (
    Track, Detection, Command, SensorReading, Message, DataProvenance,
)
from core.schema_validator import SchemaValidator

log = logging.getLogger("amos.adapters")


# ═══════════════════════════════════════════════════════════
#  PROTOCOL ADAPTER — ABSTRACT BASE
# ═══════════════════════════════════════════════════════════

class ProtocolAdapter(ABC):
    """Base class all AMOS protocol adapters must implement."""

    def __init__(self, adapter_id: str = "", protocol: str = "",
                 description: str = ""):
        self.adapter_id = adapter_id or f"ADP-{uuid.uuid4().hex[:6]}"
        self.protocol = protocol
        self.description = description
        self.connected = False
        self.stats = {
            "messages_in": 0, "messages_out": 0,
            "bytes_in": 0, "bytes_out": 0,
            "errors": 0, "last_error": "",
            "connected_at": None, "last_activity": None,
        }
        self._lock = threading.Lock()

    @abstractmethod
    def connect(self, **kwargs) -> bool:
        """Establish connection to the external system.
        Returns True on success."""
        ...

    @abstractmethod
    def disconnect(self) -> bool:
        """Gracefully close the connection."""
        ...

    @abstractmethod
    def ingest(self) -> list:
        """Read pending data from external system.
        Returns list of canonical data objects (Track, Detection, …)."""
        ...

    @abstractmethod
    def emit(self, data) -> bool:
        """Send a canonical data object to the external system.
        data: Track | Detection | Command | Message | dict"""
        ...

    def health_check(self) -> dict:
        """Return adapter health status."""
        now = time.time()
        last = self.stats.get("last_activity")
        idle_sec = round(now - last, 1) if last else None
        return {
            "adapter_id": self.adapter_id,
            "protocol": self.protocol,
            "connected": self.connected,
            "idle_sec": idle_sec,
            "healthy": self.connected and (idle_sec is None or idle_sec < 60),
            "stats": dict(self.stats),
        }

    def get_status(self) -> dict:
        return {
            "adapter_id": self.adapter_id,
            "protocol": self.protocol,
            "description": self.description,
            "connected": self.connected,
            "stats": dict(self.stats),
        }

    # ── Stat helpers ──────────────────────────────────────
    def _record_in(self, count: int = 1, bytes_count: int = 0):
        with self._lock:
            self.stats["messages_in"] += count
            self.stats["bytes_in"] += bytes_count
            self.stats["last_activity"] = time.time()

    def _record_out(self, count: int = 1, bytes_count: int = 0):
        with self._lock:
            self.stats["messages_out"] += count
            self.stats["bytes_out"] += bytes_count
            self.stats["last_activity"] = time.time()

    def _record_error(self, msg: str):
        with self._lock:
            self.stats["errors"] += 1
            self.stats["last_error"] = msg


# ═══════════════════════════════════════════════════════════
#  ADAPTER MANAGER
# ═══════════════════════════════════════════════════════════

class AdapterManager:
    """Central registry and lifecycle manager for all protocol adapters.

    Usage:
        mgr = AdapterManager(validator)
        mgr.register(my_mqtt_adapter)
        mgr.register(my_tak_adapter)
        mgr.connect_all()
        # In sim_tick:
        data = mgr.ingest_all()   # returns normalised canonical objects
        mgr.emit_all(tracks)      # push to all connected adapters
    """

    def __init__(self, validator: SchemaValidator = None):
        self.adapters = {}          # {adapter_id: ProtocolAdapter}
        self.validator = validator or SchemaValidator()
        self.provenance_log = []    # recent DataProvenance records
        self._lock = threading.Lock()
        self.stats = {
            "total_ingested": 0, "total_emitted": 0,
            "validation_errors": 0, "adapters_registered": 0,
        }

    def register(self, adapter: ProtocolAdapter):
        """Register an adapter with the manager."""
        with self._lock:
            self.adapters[adapter.adapter_id] = adapter
            self.stats["adapters_registered"] = len(self.adapters)
        log.info(f"Adapter registered: {adapter.adapter_id} ({adapter.protocol})")

    def unregister(self, adapter_id: str):
        """Remove an adapter."""
        with self._lock:
            adapter = self.adapters.pop(adapter_id, None)
            if adapter and adapter.connected:
                try:
                    adapter.disconnect()
                except Exception:
                    pass
            self.stats["adapters_registered"] = len(self.adapters)

    def connect_all(self) -> dict:
        """Connect all registered adapters. Returns {adapter_id: success}."""
        results = {}
        for aid, adapter in self.adapters.items():
            if not adapter.connected:
                try:
                    results[aid] = adapter.connect()
                except Exception as e:
                    results[aid] = False
                    log.error(f"Adapter {aid} connect failed: {e}")
            else:
                results[aid] = True
        return results

    def disconnect_all(self) -> dict:
        results = {}
        for aid, adapter in self.adapters.items():
            if adapter.connected:
                try:
                    results[aid] = adapter.disconnect()
                except Exception as e:
                    results[aid] = False
                    log.error(f"Adapter {aid} disconnect failed: {e}")
        return results

    def connect_adapter(self, adapter_id: str, **kwargs) -> bool:
        adapter = self.adapters.get(adapter_id)
        if not adapter:
            return False
        try:
            return adapter.connect(**kwargs)
        except Exception as e:
            log.error(f"Adapter {adapter_id} connect failed: {e}")
            return False

    def disconnect_adapter(self, adapter_id: str) -> bool:
        adapter = self.adapters.get(adapter_id)
        if not adapter:
            return False
        try:
            return adapter.disconnect()
        except Exception as e:
            log.error(f"Adapter {adapter_id} disconnect failed: {e}")
            return False

    def ingest_all(self) -> list:
        """Poll all connected adapters for new data.

        Returns list of (canonical_object, provenance) tuples.
        """
        all_data = []
        for aid, adapter in self.adapters.items():
            if not adapter.connected:
                continue
            try:
                items = adapter.ingest()
                if not items:
                    continue
                for item in items:
                    # Create provenance record
                    prov = DataProvenance(
                        data_id=getattr(item, "id", ""),
                        data_type=type(item).__name__,
                        source_adapter=aid,
                        source_protocol=adapter.protocol,
                    )

                    # Validate if it has a to_dict method
                    if hasattr(item, "to_dict"):
                        schema_name = self._type_to_schema(type(item).__name__)
                        if schema_name:
                            result = self.validator.validate(
                                item.to_dict(), schema_name)
                            prov.validated = result["valid"]
                            prov.validation_errors = result.get("errors", [])
                            if not result["valid"]:
                                self.stats["validation_errors"] += 1
                                continue  # skip invalid data

                    prov.normalised_at = datetime.now(
                        timezone.utc).isoformat()
                    all_data.append((item, prov))

                    # Store provenance
                    with self._lock:
                        self.provenance_log.append(prov)
                        if len(self.provenance_log) > 5000:
                            self.provenance_log = self.provenance_log[-5000:]
                        self.stats["total_ingested"] += 1

            except Exception as e:
                adapter._record_error(str(e))
                log.error(f"Adapter {aid} ingest error: {e}")

        return all_data

    def emit_all(self, data_list: list, adapter_ids: list = None) -> dict:
        """Push data to specified adapters (or all connected).

        Args:
            data_list: list of canonical objects
            adapter_ids: optional list of adapter IDs to target

        Returns:
            {adapter_id: count_sent}
        """
        results = {}
        targets = adapter_ids or list(self.adapters.keys())
        for aid in targets:
            adapter = self.adapters.get(aid)
            if not adapter or not adapter.connected:
                continue
            count = 0
            for data in data_list:
                try:
                    if adapter.emit(data):
                        count += 1
                except Exception as e:
                    adapter._record_error(str(e))
            results[aid] = count
            self.stats["total_emitted"] += count
        return results

    def health_check_all(self) -> dict:
        """Run health check on all adapters."""
        return {aid: adapter.health_check()
                for aid, adapter in self.adapters.items()}

    def get_all_status(self) -> list:
        """Get status of all adapters."""
        return [adapter.get_status() for adapter in self.adapters.values()]

    def get_adapter(self, adapter_id: str) -> ProtocolAdapter:
        return self.adapters.get(adapter_id)

    def get_provenance(self, data_id: str) -> list:
        """Trace provenance for a specific data item."""
        return [p.to_dict() for p in self.provenance_log
                if p.data_id == data_id]

    def get_recent_provenance(self, limit: int = 50) -> list:
        return [p.to_dict() for p in self.provenance_log[-limit:]]

    def get_stats(self) -> dict:
        return dict(self.stats)

    def _type_to_schema(self, type_name: str) -> str:
        """Map data type name to schema name."""
        mapping = {
            "Track": "track", "Detection": "detection",
            "Command": "command", "SensorReading": "sensor_reading",
            "VideoFrame": "video_meta", "Message": "message",
        }
        return mapping.get(type_name, "")


# ═══════════════════════════════════════════════════════════
#  LEGACY WRAPPER — adapt existing bridges to ProtocolAdapter
# ═══════════════════════════════════════════════════════════

class LegacyBridgeAdapter(ProtocolAdapter):
    """Wraps an existing AMOS bridge (PX4Bridge, TAKBridge, etc.)
    so it can be managed by AdapterManager.

    Usage:
        from integrations.px4_bridge import PX4Bridge
        px4 = PX4Bridge()
        adapter = LegacyBridgeAdapter(px4, adapter_id="px4", protocol="MAVLink")
        mgr.register(adapter)
    """

    def __init__(self, bridge, adapter_id: str = "", protocol: str = "",
                 description: str = ""):
        super().__init__(adapter_id, protocol, description)
        self.bridge = bridge

    def connect(self, **kwargs) -> bool:
        if hasattr(self.bridge, "connect"):
            result = self.bridge.connect(**kwargs) if kwargs else self.bridge.connect()
            self.connected = bool(result)
            if self.connected:
                self.stats["connected_at"] = time.time()
            return self.connected
        return False

    def disconnect(self) -> bool:
        if hasattr(self.bridge, "stop"):
            self.bridge.stop()
        elif hasattr(self.bridge, "disconnect"):
            self.bridge.disconnect()
        elif hasattr(self.bridge, "shutdown"):
            self.bridge.shutdown()
        self.connected = False
        return True

    def ingest(self) -> list:
        """Try common method names for reading data from the bridge."""
        items = []
        # Check for incoming data methods
        if hasattr(self.bridge, "get_received"):
            raw = self.bridge.get_received()
            if raw:
                for r in raw:
                    det = Detection(
                        sensor_type=self.protocol,
                        sensor_id=self.adapter_id,
                        lat=r.get("lat", 0),
                        lng=r.get("lng", r.get("lon", 0)),
                        confidence=r.get("confidence", 0.5),
                        adapter_id=self.adapter_id,
                        raw_data=r,
                    )
                    items.append(det)
                self._record_in(len(items))

        elif hasattr(self.bridge, "get_telemetry"):
            # For MAVLink bridges — sync_to_amos is called elsewhere
            pass

        return items

    def emit(self, data) -> bool:
        """Push data through legacy bridge methods."""
        try:
            d = data.to_dict() if hasattr(data, "to_dict") else data
            if hasattr(self.bridge, "send_asset"):
                self.bridge.send_asset(d)
                self._record_out()
                return True
            elif hasattr(self.bridge, "send"):
                self.bridge.send(d)
                self._record_out()
                return True
        except Exception as e:
            self._record_error(str(e))
        return False
