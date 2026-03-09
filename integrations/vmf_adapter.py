#!/usr/bin/env python3
"""AMOS Phase 26 — VMF (Variable Message Format) Adapter

Parses and builds US Military Variable Message Format messages
per MIL-STD-6017 / MIL-STD-2045-47001.

Message types implemented:
  K05.1  — Position Report (asset position update)
  K05.2  — Track Report (sensor track)
  K07.1  — Free Text Message
  K01.2  — Machine Command (C2 directive)

VMF messages use a binary header + body structure. This adapter
handles both binary wire format and JSON representation for
simulation/testing.
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
from core.data_model import Track, Detection, Command, Message

log = logging.getLogger("amos.vmf")

# VMF message type codes
VMF_TYPES = {
    "K01.2": {"name": "MACHINE_COMMAND", "code": 0x0102},
    "K05.1": {"name": "POSITION_REPORT", "code": 0x0501},
    "K05.2": {"name": "TRACK_REPORT", "code": 0x0502},
    "K07.1": {"name": "FREE_TEXT", "code": 0x0701},
    "K07.2": {"name": "FORMATTED_TEXT", "code": 0x0702},
}

# VMF precedence levels → AMOS priority
VMF_PRECEDENCE = {
    0: "ROUTINE", 1: "PRIORITY", 2: "IMMEDIATE", 3: "FLASH",
    4: "FLASH", 5: "FLASH",  # FLASH OVERRIDE
}


class VMFMessage:
    """A single VMF message with header and body."""

    def __init__(self, msg_type="K05.1", originator="", body=None):
        self.id = f"VMF-{uuid.uuid4().hex[:8]}"
        self.msg_type = msg_type
        self.type_info = VMF_TYPES.get(msg_type, {})
        self.originator = originator
        self.recipient = ""
        self.precedence = 0
        self.classification = "U"  # U=Unclass, C=Confidential, S=Secret, T=TS
        self.dtg = datetime.now(timezone.utc)
        self.body = body or {}
        self.raw_bytes = b""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "msg_type": self.msg_type,
            "type_name": self.type_info.get("name", "UNKNOWN"),
            "originator": self.originator, "recipient": self.recipient,
            "precedence": self.precedence,
            "priority": VMF_PRECEDENCE.get(self.precedence, "ROUTINE"),
            "classification": self.classification,
            "dtg": self.dtg.strftime("%d%H%MZ %b %y").upper(),
            "timestamp": self.dtg.isoformat(),
            "body": self.body,
        }

    def to_bytes(self) -> bytes:
        """Encode VMF message to binary wire format (simplified)."""
        # Header: 20 bytes
        # [2B type_code] [2B precedence+class] [8B DTG epoch_ms] [4B body_len] [4B reserved]
        type_code = self.type_info.get("code", 0)
        prec_cls = (self.precedence << 4) | {"U": 0, "C": 1, "S": 2, "T": 3}.get(self.classification, 0)
        epoch_ms = int(self.dtg.timestamp() * 1000)
        body_bytes = self._encode_body()
        header = struct.pack(">HH Q I 4s",
                             type_code, prec_cls, epoch_ms,
                             len(body_bytes), b"\x00\x00\x00\x00")
        return header + body_bytes

    def _encode_body(self) -> bytes:
        """Encode body based on message type."""
        import json
        return json.dumps(self.body, default=str).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "VMFMessage":
        """Decode VMF message from binary."""
        if len(data) < 20:
            raise ValueError("VMF message too short")
        type_code, prec_cls, epoch_ms, body_len, _ = struct.unpack(">HH Q I 4s", data[:20])
        # Find message type
        msg_type = "K07.1"
        for k, v in VMF_TYPES.items():
            if v["code"] == type_code:
                msg_type = k
                break
        msg = cls(msg_type=msg_type)
        msg.precedence = (prec_cls >> 4) & 0x0F
        cls_code = prec_cls & 0x0F
        msg.classification = {0: "U", 1: "C", 2: "S", 3: "T"}.get(cls_code, "U")
        msg.dtg = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
        msg.raw_bytes = data
        # Decode body
        body_data = data[20:20 + body_len]
        try:
            import json
            msg.body = json.loads(body_data.decode("utf-8"))
        except Exception:
            msg.body = {"raw": body_data.hex()}
        return msg


class VMFAdapter(ProtocolAdapter):
    """VMF adapter for AMOS — handles Variable Message Format tactical messages."""

    def __init__(self):
        super().__init__(
            adapter_id="vmf", protocol="VMF",
            description="MIL-STD-6017 Variable Message Format")
        self._inbox = []
        self._outbox = []
        self._lock = threading.Lock()
        self.message_log = []

    def connect(self, **kwargs) -> bool:
        self.connected = True
        self.stats["connected_at"] = time.time()
        log.info("VMF adapter ready (simulation mode)")
        return True

    def disconnect(self) -> bool:
        self.connected = False
        return True

    def ingest(self) -> list:
        """Convert pending VMF messages to AMOS canonical objects."""
        items = []
        with self._lock:
            raw = list(self._inbox)
            self._inbox.clear()

        for vmf_msg in raw:
            if isinstance(vmf_msg, bytes):
                try:
                    vmf_msg = VMFMessage.from_bytes(vmf_msg)
                except Exception:
                    continue

            d = vmf_msg if isinstance(vmf_msg, dict) else vmf_msg.to_dict()
            body = d.get("body", {})
            msg_type = d.get("msg_type", "")

            if msg_type == "K05.1":  # Position Report → Track
                trk = Track(
                    lat=body.get("lat", 0), lng=body.get("lng", 0),
                    alt_m=body.get("alt_m", 0),
                    heading_deg=body.get("heading_deg", 0),
                    speed_mps=body.get("speed_mps", 0),
                    affiliation="FRIENDLY",
                    associated_id=body.get("unit_id", ""),
                    metadata={"vmf_type": msg_type, "vmf_id": d.get("id", "")},
                )
                items.append(trk)
            elif msg_type == "K05.2":  # Track Report → Detection
                det = Detection(
                    lat=body.get("lat", 0), lng=body.get("lng", 0),
                    sensor_type=body.get("sensor_type", "UNKNOWN"),
                    sensor_id=body.get("reporter", ""),
                    confidence=body.get("confidence", 0.5),
                    affiliation=body.get("affiliation", "UNKNOWN"),
                    adapter_id=self.adapter_id,
                    metadata={"vmf_type": msg_type},
                )
                items.append(det)
            elif msg_type == "K01.2":  # Machine Command → Command
                cmd = Command(
                    command_type=body.get("command", "MOVE"),
                    target_ids=body.get("target_ids", []),
                    parameters=body.get("params", {}),
                    priority=d.get("priority", "ROUTINE"),
                    issuer=d.get("originator", ""),
                    adapter_id=self.adapter_id,
                )
                items.append(cmd)
            elif msg_type == "K07.1":  # Free Text → Message
                msg = Message(
                    message_type="FREE_TEXT",
                    originator=d.get("originator", ""),
                    body=body.get("text", ""),
                    priority=d.get("priority", "ROUTINE"),
                    protocol="VMF",
                    adapter_id=self.adapter_id,
                )
                items.append(msg)

        if items:
            self._record_in(len(items))
        return items

    def emit(self, data) -> bool:
        """Convert AMOS canonical object to VMF and queue for transmission."""
        try:
            if isinstance(data, Track):
                vmf = VMFMessage("K05.1", originator="AMOS")
                vmf.body = {
                    "unit_id": data.associated_id or data.id,
                    "lat": data.lat, "lng": data.lng, "alt_m": data.alt_m,
                    "heading_deg": data.heading_deg, "speed_mps": data.speed_mps,
                    "domain": data.domain,
                }
            elif isinstance(data, Command):
                vmf = VMFMessage("K01.2", originator=data.issuer or "AMOS")
                vmf.body = {
                    "command": data.command_type,
                    "target_ids": data.target_ids,
                    "params": data.parameters,
                }
                vmf.precedence = {"FLASH": 3, "IMMEDIATE": 2,
                                  "PRIORITY": 1, "ROUTINE": 0}.get(data.priority, 0)
            elif isinstance(data, Message):
                vmf = VMFMessage("K07.1", originator=data.originator)
                vmf.body = {"text": data.body, "subject": data.subject}
            else:
                return False

            with self._lock:
                self._outbox.append(vmf)
                self.message_log.append(vmf.to_dict())
                if len(self.message_log) > 500:
                    self.message_log = self.message_log[-500:]
            self._record_out()
            return True
        except Exception as e:
            self._record_error(str(e))
            return False

    def inject_message(self, vmf_dict: dict):
        """Inject a VMF message for ingestion (testing/simulation)."""
        msg = VMFMessage(
            msg_type=vmf_dict.get("msg_type", "K07.1"),
            originator=vmf_dict.get("originator", "EXTERNAL"),
        )
        msg.body = vmf_dict.get("body", {})
        msg.precedence = vmf_dict.get("precedence", 0)
        with self._lock:
            self._inbox.append(msg)

    def get_message_log(self, limit: int = 50) -> list:
        return self.message_log[-limit:]

    def get_status(self) -> dict:
        base = super().get_status()
        base["outbox_pending"] = len(self._outbox)
        base["message_types"] = list(VMF_TYPES.keys())
        return base
