#!/usr/bin/env python3
"""AMOS Phase 26 — STANAG 4586 CUCS Adapter

NATO standard for UAV/UCS interoperability.
Implements Data Link Interface (DLI) messages for Levels of
Interoperability (LOI) 2-4.

DLI Messages:
  Msg 200 — Vehicle Configuration
  Msg 300 — Mission Upload (waypoints)
  Msg 301 — Vehicle Command (mode, speed, altitude)
  Msg 302 — Payload Command (sensor mode, gimbal)
  Msg 400 — Vehicle Telemetry (status response)
  Msg 500 — Payload Telemetry (sensor response)

LOI Levels:
  LOI 2 — Receive UAV telemetry only
  LOI 3 — Send commands + receive telemetry
  LOI 4 — Full mission planning + upload
"""

import struct
import uuid
import time
import logging
import threading
from datetime import datetime, timezone

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.adapter_base import ProtocolAdapter
from core.data_model import Track, Command

log = logging.getLogger("amos.stanag4586")

# DLI Message types
DLI_MESSAGES = {
    200: "VEHICLE_CONFIG",
    300: "MISSION_UPLOAD",
    301: "VEHICLE_COMMAND",
    302: "PAYLOAD_COMMAND",
    400: "VEHICLE_TELEMETRY",
    500: "PAYLOAD_TELEMETRY",
}


class DLIMessage:
    """STANAG 4586 Data Link Interface message."""

    def __init__(self, msg_id: int = 301, vehicle_id: str = ""):
        self.id = f"DLI-{uuid.uuid4().hex[:8]}"
        self.msg_id = msg_id
        self.msg_name = DLI_MESSAGES.get(msg_id, "UNKNOWN")
        self.vehicle_id = vehicle_id
        self.cucs_id = "AMOS"
        self.loi = 3
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.fields = {}

    def to_dict(self) -> dict:
        return {
            "id": self.id, "msg_id": self.msg_id,
            "msg_name": self.msg_name,
            "vehicle_id": self.vehicle_id, "cucs_id": self.cucs_id,
            "loi": self.loi, "timestamp": self.timestamp,
            "fields": self.fields,
        }

    def to_bytes(self) -> bytes:
        """Pack DLI message to binary (simplified header + JSON body)."""
        import json
        body = json.dumps(self.fields, default=str).encode("utf-8")
        vid_bytes = self.vehicle_id.encode("utf-8")[:16].ljust(16, b"\x00")
        header = struct.pack(">HH16sI",
                             self.msg_id, self.loi, vid_bytes, len(body))
        return header + body

    @classmethod
    def from_bytes(cls, data: bytes) -> "DLIMessage":
        """Unpack DLI message from binary."""
        if len(data) < 24:
            raise ValueError("DLI message too short")
        msg_id, loi, vid_bytes, body_len = struct.unpack(">HH16sI", data[:24])
        msg = cls(msg_id=msg_id, vehicle_id=vid_bytes.decode("utf-8").strip("\x00"))
        msg.loi = loi
        body_data = data[24:24 + body_len]
        try:
            import json
            msg.fields = json.loads(body_data.decode("utf-8"))
        except Exception:
            msg.fields = {"raw": body_data.hex()}
        return msg


class STANAG4586Adapter(ProtocolAdapter):
    """STANAG 4586 CUCS adapter for NATO UAV interoperability."""

    def __init__(self, loi: int = 3):
        super().__init__(
            adapter_id="stanag4586", protocol="STANAG4586",
            description=f"NATO STANAG 4586 CUCS (LOI {loi})")
        self.loi = loi
        self.vehicles = {}       # {vehicle_id: config}
        self._inbox = []
        self._outbox = []
        self._lock = threading.Lock()
        self.message_log = []

    def connect(self, **kwargs) -> bool:
        self.connected = True
        self.stats["connected_at"] = time.time()
        log.info(f"STANAG 4586 adapter ready (LOI {self.loi}, simulation mode)")
        return True

    def disconnect(self) -> bool:
        self.connected = False
        return True

    def register_vehicle(self, vehicle_id: str, uav_type: str = "",
                         capabilities: dict = None) -> dict:
        """Register a UAV for STANAG 4586 control."""
        config = {
            "vehicle_id": vehicle_id, "uav_type": uav_type,
            "loi": self.loi, "capabilities": capabilities or {},
            "status": "registered",
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        self.vehicles[vehicle_id] = config
        return config

    def send_vehicle_command(self, vehicle_id: str,
                             command: str, params: dict = None) -> dict:
        """Send Msg 301 Vehicle Command."""
        if self.loi < 3:
            return {"error": f"LOI {self.loi} does not support commands (requires LOI 3+)"}
        msg = DLIMessage(301, vehicle_id)
        msg.loi = self.loi
        msg.fields = {
            "command": command,
            "speed_mps": (params or {}).get("speed_mps", 0),
            "altitude_m": (params or {}).get("altitude_m", 0),
            "heading_deg": (params or {}).get("heading_deg", 0),
            "mode": (params or {}).get("mode", "AUTO"),
        }
        with self._lock:
            self._outbox.append(msg)
            self.message_log.append(msg.to_dict())
        self._record_out()
        return msg.to_dict()

    def send_mission_upload(self, vehicle_id: str,
                            waypoints: list) -> dict:
        """Send Msg 300 Mission Upload (LOI 4 only)."""
        if self.loi < 4:
            return {"error": f"LOI {self.loi} does not support mission upload (requires LOI 4)"}
        msg = DLIMessage(300, vehicle_id)
        msg.loi = self.loi
        msg.fields = {
            "waypoint_count": len(waypoints),
            "waypoints": waypoints,
        }
        with self._lock:
            self._outbox.append(msg)
            self.message_log.append(msg.to_dict())
        self._record_out()
        return msg.to_dict()

    def send_payload_command(self, vehicle_id: str,
                             payload_type: str = "EO/IR",
                             action: str = "STARE",
                             target: dict = None) -> dict:
        """Send Msg 302 Payload Command."""
        if self.loi < 3:
            return {"error": "LOI too low for payload commands"}
        msg = DLIMessage(302, vehicle_id)
        msg.fields = {
            "payload_type": payload_type, "action": action,
            "target": target or {},
        }
        with self._lock:
            self._outbox.append(msg)
            self.message_log.append(msg.to_dict())
        self._record_out()
        return msg.to_dict()

    def ingest(self) -> list:
        """Convert incoming DLI telemetry to AMOS objects."""
        items = []
        with self._lock:
            raw = list(self._inbox)
            self._inbox.clear()

        for dli_msg in raw:
            d = dli_msg if isinstance(dli_msg, dict) else dli_msg.to_dict()
            msg_id = d.get("msg_id", 0)
            fields = d.get("fields", {})

            if msg_id == 400:  # Vehicle Telemetry → Track
                trk = Track(
                    lat=fields.get("lat", 0), lng=fields.get("lng", 0),
                    alt_m=fields.get("altitude_m", 0),
                    heading_deg=fields.get("heading_deg", 0),
                    speed_mps=fields.get("speed_mps", 0),
                    domain="air", affiliation="FRIENDLY",
                    associated_id=d.get("vehicle_id", ""),
                    metadata={"stanag4586_msg": msg_id},
                )
                items.append(trk)
            elif msg_id == 500:  # Payload Telemetry
                trk = Track(
                    lat=fields.get("sensor_lat", 0),
                    lng=fields.get("sensor_lng", 0),
                    track_type="sensor_footprint",
                    domain="air", affiliation="FRIENDLY",
                    associated_id=d.get("vehicle_id", ""),
                    metadata={"stanag4586_msg": msg_id, "payload": fields},
                )
                items.append(trk)

        if items:
            self._record_in(len(items))
        return items

    def emit(self, data) -> bool:
        """Convert AMOS Command → DLI Vehicle/Payload Command."""
        if isinstance(data, Command):
            vid = data.target_ids[0] if data.target_ids else ""
            if data.command_type in ("MOVE", "ORBIT", "RTB", "HOLD", "LAND"):
                self.send_vehicle_command(vid, data.command_type, data.parameters)
                return True
            elif data.command_type == "PAYLOAD_CMD":
                self.send_payload_command(vid, **data.parameters)
                return True
        return False

    def inject_telemetry(self, vehicle_id: str, lat: float, lng: float,
                         alt_m: float = 0, heading: float = 0, speed: float = 0):
        """Inject simulated vehicle telemetry (Msg 400) for testing."""
        msg = DLIMessage(400, vehicle_id)
        msg.fields = {"lat": lat, "lng": lng, "altitude_m": alt_m,
                       "heading_deg": heading, "speed_mps": speed}
        with self._lock:
            self._inbox.append(msg)

    def get_vehicles(self) -> dict:
        return dict(self.vehicles)

    def get_message_log(self, limit: int = 50) -> list:
        return self.message_log[-limit:]

    def get_status(self) -> dict:
        base = super().get_status()
        base["loi"] = self.loi
        base["vehicles"] = list(self.vehicles.keys())
        base["outbox_pending"] = len(self._outbox)
        return base
