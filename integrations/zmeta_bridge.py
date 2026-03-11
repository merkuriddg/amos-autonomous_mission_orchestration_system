"""AMOS ↔ ZMeta ISR Metadata Integration Bridge

Connects AMOS to the ZMeta event-based metadata standard for resilient ISR.
ZMeta defines a transport-agnostic semantic contract for observation, inference,
fusion, state, and command events across degraded/denied environments.

Data Flow:
  Ingest  — UDP listener receives ZMeta v1.0 JSON events from edge nodes,
            gateways, or the reference ZMeta gateway.  Events are parsed,
            validated, and buffered for AMOS consumption.
  Egress  — AMOS fused picture and waypoint commands are emitted as ZMeta
            STATE_EVENT and COMMAND_EVENT via UDP to a configurable forward
            address.

ZMeta Spec: https://github.com/JTC-byte/zmeta-spec

Requires: No external dependencies (stdlib only — socket, json, threading, uuid).
"""

import json
import socket
import time
import uuid
import logging
import threading
from datetime import datetime, timezone

log = logging.getLogger("amos.zmeta")

# ── ZMeta v1.0 event types ─────────────────────────────────
ZMETA_EVENT_TYPES = {
    "OBSERVATION_EVENT", "INFERENCE_EVENT", "FUSION_EVENT",
    "STATE_EVENT", "COMMAND_EVENT", "SYSTEM_EVENT",
}

ZMETA_PROFILES = {"L", "M", "H"}

ZMETA_SYSTEM_SUBTYPES = {"TASK_ACK", "LINK_STATUS", "TIME_STATUS", "SCHEMA_VIOLATION"}

ZMETA_COMMAND_TASK_TYPES = {"GOTO", "ORBIT", "HOLD", "SEARCH_BOX"}

# ── Unit conversions (ZMeta → AMOS) ────────────────────────
MPS_TO_KTS = 1.94384
M_TO_FT = 3.28084


def _uuid7_hex() -> str:
    """Generate a UUIDv7-style string (time-ordered) for ZMeta event IDs."""
    now_ms = int(time.time() * 1000)
    rand = uuid.uuid4().hex[12:]
    hex_ts = f"{now_ms:012x}"
    return f"{hex_ts[:8]}-{hex_ts[8:12]}-7{rand[:3]}-{rand[3:7]}-{rand[7:19]}"


def _utc_now() -> str:
    """ISO-8601 UTC timestamp (ZMeta canonical format)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ZMetaBridge:
    """Bridge to ZMeta ISR metadata network — ingest + egress."""

    def __init__(self, listen_host="0.0.0.0", listen_port=5555,
                 forward_host="127.0.0.1", forward_port=5556,
                 profile="H", platform_id="amos-gateway"):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.forward_host = forward_host
        self.forward_port = forward_port
        self.profile = profile.upper() if profile else "H"
        self.platform_id = platform_id

        self.connected = False
        self._running = False
        self._listener_thread = None
        self._sock_in = None
        self._sock_out = None
        self._lock = threading.Lock()

        # Ingest buffers (last N per category)
        self.observations: list[dict] = []
        self.inferences: list[dict] = []
        self.fusions: list[dict] = []
        self.track_states: list[dict] = []
        self.commands_in: list[dict] = []
        self.link_status: list[dict] = []
        self.task_acks: list[dict] = []
        self.system_events: list[dict] = []

        # Egress tracking
        self.commands_out: list[dict] = []
        self.states_out: list[dict] = []

        # Metrics
        self.stats = {
            "received": 0,
            "forwarded": 0,
            "emitted": 0,
            "parse_errors": 0,
            "validation_errors": 0,
            "observations": 0,
            "inferences": 0,
            "fusions": 0,
            "track_states": 0,
            "commands_in": 0,
            "commands_out": 0,
            "states_out": 0,
            "link_status": 0,
            "task_acks": 0,
            "connected_at": None,
            "last_event_at": None,
        }

    # ── Connection ─────────────────────────────────────────

    def connect(self) -> bool:
        """Start the UDP ingest listener and egress socket."""
        try:
            self._sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock_in.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock_in.bind((self.listen_host, self.listen_port))
            self._sock_in.settimeout(1.0)

            self._sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            self._running = True
            self._listener_thread = threading.Thread(
                target=self._listen_loop, daemon=True,
                name="zmeta-ingest",
            )
            self._listener_thread.start()

            self.connected = True
            self.stats["connected_at"] = time.time()
            log.info(f"ZMeta bridge listening on "
                     f"{self.listen_host}:{self.listen_port} "
                     f"(profile={self.profile}, "
                     f"forward={self.forward_host}:{self.forward_port})")
            return True
        except Exception as e:
            log.error(f"ZMeta bridge connect failed: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Stop the listener and close sockets."""
        self._running = False
        if self._listener_thread:
            self._listener_thread.join(timeout=3)
        if self._sock_in:
            try:
                self._sock_in.close()
            except Exception:
                pass
        if self._sock_out:
            try:
                self._sock_out.close()
            except Exception:
                pass
        self.connected = False
        log.info("ZMeta bridge disconnected")

    # ── UDP Ingest Loop ────────────────────────────────────

    def _listen_loop(self):
        """Receive UDP datagrams and parse ZMeta events."""
        while self._running:
            try:
                data, addr = self._sock_in.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    log.debug("ZMeta socket closed")
                break

            self.stats["received"] += 1
            try:
                event = json.loads(data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                self.stats["parse_errors"] += 1
                log.debug(f"ZMeta parse error: {e}")
                continue

            self._route_event(event)

    def _route_event(self, event: dict):
        """Validate envelope and route to the appropriate buffer."""
        # Basic envelope validation
        if not isinstance(event, dict):
            self.stats["validation_errors"] += 1
            return
        if event.get("zmeta_version") != "1.0":
            self.stats["validation_errors"] += 1
            return

        ev = event.get("event", {})
        event_type = ev.get("event_type", "")
        if event_type not in ZMETA_EVENT_TYPES:
            self.stats["validation_errors"] += 1
            return

        now = _utc_now()
        self.stats["last_event_at"] = now

        # Normalize the event with AMOS-relevant fields extracted
        entry = self._normalize(event)

        with self._lock:
            if event_type == "OBSERVATION_EVENT":
                self.observations.append(entry)
                self.stats["observations"] += 1
                self._trim(self.observations)

            elif event_type == "INFERENCE_EVENT":
                self.inferences.append(entry)
                self.stats["inferences"] += 1
                self._trim(self.inferences)

            elif event_type == "FUSION_EVENT":
                self.fusions.append(entry)
                self.stats["fusions"] += 1
                self._trim(self.fusions)

            elif event_type == "STATE_EVENT":
                self.track_states.append(entry)
                self.stats["track_states"] += 1
                self._trim(self.track_states)

            elif event_type == "COMMAND_EVENT":
                self.commands_in.append(entry)
                self.stats["commands_in"] += 1
                self._trim(self.commands_in)

            elif event_type == "SYSTEM_EVENT":
                sys_type = event.get("payload", {}).get("system_type", "")
                if sys_type == "LINK_STATUS":
                    self.link_status.append(entry)
                    self.stats["link_status"] += 1
                    self._trim(self.link_status)
                elif sys_type == "TASK_ACK":
                    self.task_acks.append(entry)
                    self.stats["task_acks"] += 1
                    self._trim(self.task_acks)
                else:
                    self.system_events.append(entry)
                    self._trim(self.system_events)

            self.stats["forwarded"] += 1

    def _normalize(self, event: dict) -> dict:
        """Extract AMOS-relevant fields from a ZMeta event."""
        ev = event.get("event", {})
        src = event.get("source", {})
        payload = event.get("payload", {})
        geo = payload.get("geo") or payload.get("estimated_state", {}).get("geo") or {}
        target_geo = payload.get("target_geo", {})

        entry = {
            "raw": event,
            "event_id": ev.get("event_id", ""),
            "event_type": ev.get("event_type", ""),
            "event_subtype": ev.get("event_subtype", ""),
            "ts": ev.get("ts", ""),
            "platform_id": src.get("platform_id", ""),
            "producer": src.get("producer", ""),
            "node_role": src.get("node_role", ""),
            "profile": event.get("profile", ""),
            "confidence": event.get("confidence"),
        }

        # Geospatial (convert ZMeta WGS-84 → AMOS)
        if geo.get("lat") is not None:
            entry["lat"] = geo["lat"]
            entry["lng"] = geo.get("lon", geo.get("lng", 0))
            if geo.get("alt_m") is not None:
                entry["alt_ft"] = round(geo["alt_m"] * M_TO_FT, 1)

        # Target geo (for COMMAND_EVENTs)
        if target_geo.get("lat") is not None:
            entry["target_lat"] = target_geo["lat"]
            entry["target_lng"] = target_geo.get("lon", target_geo.get("lng", 0))

        # Kinematics
        est = payload.get("estimated_state", {})
        speed_mps = est.get("speed_mps") or payload.get("speed_mps")
        heading = est.get("heading_deg") or payload.get("heading_deg")
        if speed_mps is not None:
            entry["speed_kts"] = round(speed_mps * MPS_TO_KTS, 1)
        if heading is not None:
            entry["heading_deg"] = heading

        # Track identity
        track_id = payload.get("track_id")
        if track_id:
            entry["track_id"] = track_id

        # RF observation specifics
        features = payload.get("features", {})
        if features.get("center_freq_hz") is not None:
            entry["freq_hz"] = features["center_freq_hz"]
            entry["bandwidth_hz"] = features.get("bandwidth_hz")
            entry["power_dbm"] = features.get("power_dbm")
            entry["signature_hash"] = features.get("signature_hash")

        # Observation modality
        modality = payload.get("modality")
        if modality:
            entry["modality"] = modality

        # Inference claim
        claim = payload.get("claim")
        if claim:
            entry["claim"] = claim
            entry["inference_type"] = payload.get("inference_type", "")
            model = payload.get("model", {})
            entry["model_name"] = model.get("name", "")
            entry["model_version"] = model.get("version", "")

        # Command fields
        task_id = payload.get("task_id")
        if task_id:
            entry["task_id"] = task_id
            entry["task_type"] = payload.get("task_type", "")
            entry["valid_for_ms"] = payload.get("valid_for_ms", 60000)
            entry["priority"] = payload.get("priority", "MED")

        # System event fields
        sys_type = payload.get("system_type")
        if sys_type:
            entry["system_type"] = sys_type
            entry["state"] = payload.get("state", "")
            entry["metrics"] = payload.get("metrics", {})

        # Lineage
        lineage = event.get("lineage", {})
        if lineage.get("based_on"):
            entry["lineage"] = lineage["based_on"]

        # Fusion stability
        stability = payload.get("stability")
        if stability is not None:
            entry["stability"] = stability

        # Valid-for (TTL)
        valid_for = payload.get("valid_for_ms")
        if valid_for is not None:
            entry["valid_for_ms"] = valid_for

        return entry

    # ── Egress: Emit ZMeta Events ──────────────────────────

    def emit_track_state(self, track_id: str, lat: float, lng: float,
                         alt_m: float = 0, heading_deg: float = None,
                         speed_mps: float = None, confidence: float = 0.8,
                         entity_class: str = None, valid_for_ms: int = 5000,
                         lineage: list = None) -> dict:
        """Emit a ZMeta STATE_EVENT (TRACK_STATE) from AMOS fused picture."""
        event = {
            "zmeta_version": "1.0",
            "event": {
                "event_id": _uuid7_hex(),
                "event_type": "STATE_EVENT",
                "event_subtype": "TRACK_STATE",
                "ts": _utc_now(),
                "t_publish": _utc_now(),
            },
            "source": {
                "platform_id": self.platform_id,
                "node_role": "GATEWAY",
                "producer": "amos",
            },
            "profile": self.profile,
            "confidence": confidence,
            "payload": {
                "track_id": track_id,
                "geo": {"lat": lat, "lon": lng, "alt_m": alt_m},
                "valid_for_ms": valid_for_ms,
            },
        }
        if heading_deg is not None:
            event["payload"]["heading_deg"] = heading_deg
        if speed_mps is not None:
            event["payload"]["speed_mps"] = speed_mps
        if entity_class:
            event["payload"]["class"] = entity_class
        if lineage:
            event["lineage"] = {"based_on": lineage}
        event["payload"]["source_summary"] = ["amos-fusion"]

        self._send_udp(event)
        with self._lock:
            self.states_out.append({"event": event, "ts": _utc_now()})
            self.stats["states_out"] += 1
            self._trim(self.states_out)
        return event

    def emit_command(self, task_type: str, lat: float, lng: float,
                     valid_for_ms: int = 600000, priority: str = "MED",
                     geometry: dict = None) -> dict:
        """Emit a ZMeta COMMAND_EVENT (MISSION_TASK) for waypoint tasking."""
        task_id = f"amos-{uuid.uuid4().hex[:12]}"
        event = {
            "zmeta_version": "1.0",
            "event": {
                "event_id": _uuid7_hex(),
                "event_type": "COMMAND_EVENT",
                "event_subtype": "MISSION_TASK",
                "ts": _utc_now(),
            },
            "source": {
                "platform_id": self.platform_id,
                "node_role": "GATEWAY",
                "producer": "amos",
            },
            "profile": self.profile,
            "payload": {
                "task_id": task_id,
                "task_type": task_type.upper(),
                "target_geo": {"lat": lat, "lon": lng},
                "valid_for_ms": valid_for_ms,
                "priority": priority.upper(),
                "requires_deconfliction": True,
            },
        }
        if geometry:
            event["payload"]["geometry"] = geometry

        self._send_udp(event)
        with self._lock:
            self.commands_out.append({"event": event, "ts": _utc_now(), "task_id": task_id})
            self.stats["commands_out"] += 1
            self._trim(self.commands_out)
        return event

    def _send_udp(self, event: dict):
        """Send a ZMeta event via UDP to the forward address."""
        if not self._sock_out:
            return
        try:
            payload = json.dumps(event, separators=(",", ":"),
                                 ensure_ascii=True).encode("utf-8")
            self._sock_out.sendto(payload, (self.forward_host, self.forward_port))
            self.stats["emitted"] += 1
        except Exception as e:
            log.debug(f"ZMeta egress send error: {e}")

    # ── Public API ─────────────────────────────────────────

    def get_observations(self, limit: int = 50) -> list[dict]:
        """Return recent OBSERVATION events (RF, EO/IR, acoustic)."""
        with self._lock:
            return list(self.observations[-limit:])

    def get_inferences(self, limit: int = 50) -> list[dict]:
        """Return recent INFERENCE events (classifications, anomalies)."""
        with self._lock:
            return list(self.inferences[-limit:])

    def get_fusions(self, limit: int = 50) -> list[dict]:
        """Return recent FUSION events (cross-sensor tracks)."""
        with self._lock:
            return list(self.fusions[-limit:])

    def get_track_states(self, limit: int = 50) -> list[dict]:
        """Return recent STATE events (operator-grade track belief)."""
        with self._lock:
            return list(self.track_states[-limit:])

    def get_commands_in(self, limit: int = 50) -> list[dict]:
        """Return inbound COMMAND events received from external sources."""
        with self._lock:
            return list(self.commands_in[-limit:])

    def get_commands_out(self, limit: int = 50) -> list[dict]:
        """Return COMMAND events emitted by AMOS."""
        with self._lock:
            return list(self.commands_out[-limit:])

    def get_states_out(self, limit: int = 50) -> list[dict]:
        """Return STATE events emitted by AMOS."""
        with self._lock:
            return list(self.states_out[-limit:])

    def get_link_status(self, limit: int = 50) -> list[dict]:
        """Return recent LINK_STATUS system events."""
        with self._lock:
            return list(self.link_status[-limit:])

    def get_task_acks(self, limit: int = 50) -> list[dict]:
        """Return recent TASK_ACK system events."""
        with self._lock:
            return list(self.task_acks[-limit:])

    def get_all_events(self, limit: int = 100) -> list[dict]:
        """Return most recent events across all types, sorted by timestamp."""
        with self._lock:
            all_events = (
                self.observations[-limit:] +
                self.inferences[-limit:] +
                self.fusions[-limit:] +
                self.track_states[-limit:] +
                self.commands_in[-limit:] +
                self.link_status[-limit:] +
                self.task_acks[-limit:] +
                self.system_events[-limit:]
            )
        all_events.sort(key=lambda e: e.get("ts", ""), reverse=True)
        return all_events[:limit]

    def get_status(self) -> dict:
        """Return bridge status and metrics."""
        return {
            "node_id": self.platform_id,
            "connected": self.connected,
            "listen_addr": f"{self.listen_host}:{self.listen_port}",
            "forward_addr": f"{self.forward_host}:{self.forward_port}",
            "profile": self.profile,
            "stats": dict(self.stats),
            "buffers": {
                "observations": len(self.observations),
                "inferences": len(self.inferences),
                "fusions": len(self.fusions),
                "track_states": len(self.track_states),
                "commands_in": len(self.commands_in),
                "commands_out": len(self.commands_out),
                "states_out": len(self.states_out),
                "link_status": len(self.link_status),
                "task_acks": len(self.task_acks),
            },
        }

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _trim(buf: list, max_size: int = 500):
        if len(buf) > max_size:
            del buf[:-max_size]
