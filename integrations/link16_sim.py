"""AMOS Link-16 Tactical Data Link Simulator (Phase 26 Upgrade)

Simulates Link-16 (TADIL J) message exchange for multi-platform interoperability.
Implements J-series message formats with binary packing and expanded message set.

Messages supported:
  J2.2  — Air Track
  J2.5  — Electronic Warfare Track (emitter)
  J3.2  — Surface Track
  J3.5  — Subsurface Track (submarine/UUV)
  J7.0  — Command
  J7.1  — Status
  J12.6 — Mission Assignment
  J13.0 — Network Time Reference
  PPLI  — Precise Participant Location & Identification
"""

import struct
import time, uuid, logging, threading, json
from datetime import datetime, timezone

log = logging.getLogger("amos.link16")

# J-series message types
J_MESSAGES = {
    "J2.2":  "AIR_TRACK",
    "J2.5":  "EW_TRACK",
    "J3.2":  "SURFACE_TRACK",
    "J3.5":  "SUBSURFACE_TRACK",
    "J7.0":  "COMMAND",
    "J7.1":  "STATUS",
    "J12.6": "MISSION_ASSIGNMENT",
    "J13.0": "NET_TIME_REF",
    "PPLI":  "PARTICIPANT_LOCATION",
}

# IFF identity codes (3-bit)
IFF_CODES = {
    "PENDING": 0, "UNKNOWN": 1, "ASSUMED_FRIENDLY": 2,
    "FRIENDLY": 3, "NEUTRAL": 4, "SUSPECT": 5, "HOSTILE": 6,
}
IFF_DECODE = {v: k for k, v in IFF_CODES.items()}

# J-type to numeric ID for binary packing
J_TYPE_ID = {
    "J2.2": 0x0202, "J2.5": 0x0205, "J3.2": 0x0302,
    "J3.5": 0x0305, "J7.0": 0x0700, "J7.1": 0x0701,
    "J12.6": 0x0C06, "J13.0": 0x0D00, "PPLI": 0xFF01,
}
J_TYPE_DECODE = {v: k for k, v in J_TYPE_ID.items()}


class Link16Message:
    """A single Link-16 J-series message with binary packing."""

    def __init__(self, j_type, source_tn, data):
        self.id = f"L16-{uuid.uuid4().hex[:8]}"
        self.j_type = j_type
        self.source_tn = source_tn  # Track Number (TN)
        self.data = data
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.sequence = 0

    def to_dict(self):
        return {
            "id": self.id, "j_type": self.j_type,
            "description": J_MESSAGES.get(self.j_type, "UNKNOWN"),
            "source_tn": self.source_tn, "data": self.data,
            "timestamp": self.timestamp, "sequence": self.sequence,
        }

    def to_bytes(self) -> bytes:
        """Pack Link-16 message to binary (75-bit J-series word simulation).

        Header (16 bytes):
          - j_type_id  (2 bytes, unsigned short)
          - sequence    (4 bytes, unsigned int)
          - iff_code   (1 byte)
          - reserved   (1 byte)
          - source_tn  (8 bytes, zero-padded ASCII)

        Body (variable):
          - lat        (8 bytes, double)
          - lng        (8 bytes, double)
          - alt_ft     (4 bytes, float)
          - heading    (2 bytes, unsigned short, 0-360 → 0-65535)
          - speed_kts  (2 bytes, unsigned short)
        """
        j_id = J_TYPE_ID.get(self.j_type, 0x0000)
        iff_code = IFF_CODES.get(self.data.get("iff", "UNKNOWN"), 1)
        tn_bytes = self.source_tn.encode("ascii")[:8].ljust(8, b"\x00")

        header = struct.pack(">HIBx8s", j_id, self.sequence, iff_code, tn_bytes)

        lat = self.data.get("lat", 0.0)
        lng = self.data.get("lng", 0.0)
        alt_ft = self.data.get("alt_ft", 0.0)
        heading = int(self.data.get("heading_deg", 0) * 65535 / 360) & 0xFFFF
        speed = int(self.data.get("speed_kts", 0)) & 0xFFFF

        body = struct.pack(">ddfHH", lat, lng, alt_ft, heading, speed)
        return header + body

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Link16Message":
        """Unpack binary Link-16 message."""
        if len(raw) < 40:
            raise ValueError("Link-16 message too short")
        j_id, seq, iff_code = struct.unpack(">HIB", raw[:7])
        tn_bytes = raw[8:16]
        lat, lng, alt_ft, heading_raw, speed = struct.unpack(">ddfHH", raw[16:40])

        j_type = J_TYPE_DECODE.get(j_id, f"0x{j_id:04X}")
        tn = tn_bytes.decode("ascii").strip("\x00")

        data = {
            "lat": lat, "lng": lng, "alt_ft": alt_ft,
            "heading_deg": round(heading_raw * 360 / 65535, 1),
            "speed_kts": speed,
            "iff": IFF_DECODE.get(iff_code, "UNKNOWN"),
        }
        msg = cls(j_type, tn, data)
        msg.sequence = seq
        return msg


class Link16Network:
    """Simulated Link-16 network for AMOS."""

    def __init__(self, net_id="AMOS-NET-1", time_slot_ms=7.8125):
        self.net_id = net_id
        self.time_slot_ms = time_slot_ms
        self.participants = {}  # amos_id -> {tn, role, jid}
        self.message_log = []
        self.track_table = {}  # tn -> track data (shared tactical picture)
        self.sequence = 0
        self.stats = {"messages_sent": 0, "messages_recv": 0,
                      "tracks_shared": 0, "commands_sent": 0}
        self._lock = threading.Lock()

    def join(self, amos_id, track_number=None, role="PARTICIPANT"):
        """Register an asset on the Link-16 network."""
        tn = track_number or f"TN-{len(self.participants) + 1:04d}"
        self.participants[amos_id] = {
            "tn": tn, "role": role,
            "joined": datetime.now(timezone.utc).isoformat(),
            "jid": f"JU-{uuid.uuid4().hex[:4]}",
        }
        log.info(f"Link-16 join: {amos_id} as {tn} [{role}]")
        return tn

    def leave(self, amos_id):
        self.participants.pop(amos_id, None)

    def send_air_track(self, amos_id, lat, lng, alt_ft, heading, speed_kts,
                       iff="FRIENDLY"):
        """Send J2.2 Air Track message."""
        if amos_id not in self.participants:
            return None
        p = self.participants[amos_id]
        msg = Link16Message("J2.2", p["tn"], {
            "lat": lat, "lng": lng, "alt_ft": alt_ft,
            "heading_deg": heading, "speed_kts": speed_kts,
            "iff": iff, "quality": "HIGH",
        })
        return self._broadcast(msg)

    def send_surface_track(self, amos_id, lat, lng, heading, speed_kts,
                           iff="FRIENDLY"):
        """Send J3.2 Surface Track message."""
        if amos_id not in self.participants:
            return None
        p = self.participants[amos_id]
        msg = Link16Message("J3.2", p["tn"], {
            "lat": lat, "lng": lng,
            "heading_deg": heading, "speed_kts": speed_kts,
            "iff": iff,
        })
        return self._broadcast(msg)

    def send_subsurface_track(self, amos_id, lat, lng, depth_m,
                              heading, speed_kts, iff="FRIENDLY"):
        """Send J3.5 Subsurface Track message."""
        if amos_id not in self.participants:
            return None
        p = self.participants[amos_id]
        msg = Link16Message("J3.5", p["tn"], {
            "lat": lat, "lng": lng, "depth_m": depth_m,
            "alt_ft": -depth_m * 3.281,  # depth as negative altitude
            "heading_deg": heading, "speed_kts": speed_kts,
            "iff": iff, "domain": "subsurface",
        })
        return self._broadcast(msg)

    def send_ew_track(self, amos_id, lat, lng, emitter_type,
                      frequency_mhz=0, power_dbm=0, iff="UNKNOWN"):
        """Send J2.5 Electronic Warfare Track (emitter location)."""
        if amos_id not in self.participants:
            return None
        p = self.participants[amos_id]
        msg = Link16Message("J2.5", p["tn"], {
            "lat": lat, "lng": lng, "alt_ft": 0,
            "heading_deg": 0, "speed_kts": 0,
            "iff": iff, "emitter_type": emitter_type,
            "frequency_mhz": frequency_mhz,
            "power_dbm": power_dbm, "domain": "ew",
        })
        return self._broadcast(msg)

    def send_ppli(self, amos_id, lat, lng, alt_ft=0,
                  heading=0, speed_kts=0):
        """Send PPLI — Precise Participant Location & Identification.

        PPLI is the heartbeat message. Every participant broadcasts
        their own position at a regular interval (typically 12s).
        """
        if amos_id not in self.participants:
            return None
        p = self.participants[amos_id]
        msg = Link16Message("PPLI", p["tn"], {
            "lat": lat, "lng": lng, "alt_ft": alt_ft,
            "heading_deg": heading, "speed_kts": speed_kts,
            "iff": "FRIENDLY", "jid": p["jid"],
            "health": "OPERATIONAL",
        })
        self.stats["ppli_sent"] = self.stats.get("ppli_sent", 0) + 1
        return self._broadcast(msg)

    def send_mission_assignment(self, from_id, target_ids,
                                mission_type, params):
        """Send J12.6 Mission Assignment message."""
        if from_id not in self.participants:
            return None
        p = self.participants[from_id]
        target_tns = [self.participants.get(tid, {}).get("tn", tid)
                      for tid in (target_ids or [])]
        msg = Link16Message("J12.6", p["tn"], {
            "mission_type": mission_type,
            "target_tns": target_tns,
            "params": params,
            "priority": params.get("priority", "ROUTINE") if isinstance(params, dict) else "ROUTINE",
        })
        self.stats["missions_assigned"] = self.stats.get("missions_assigned", 0) + 1
        return self._broadcast(msg)

    def send_command(self, from_id, to_id, command_type, params):
        """Send J7.0 Command message."""
        if from_id not in self.participants:
            return None
        p = self.participants[from_id]
        msg = Link16Message("J7.0", p["tn"], {
            "command": command_type,
            "target_tn": self.participants.get(to_id, {}).get("tn"),
            "params": params,
        })
        self.stats["commands_sent"] += 1
        return self._broadcast(msg)

    def broadcast_all_assets(self, sim_assets):
        """Push all AMOS assets as Link-16 tracks."""
        count = 0
        for aid, a in sim_assets.items():
            if aid not in self.participants:
                self.join(aid)
            domain = a.get("domain", "ground")
            p = a["position"]
            if domain == "air":
                self.send_air_track(aid, p["lat"], p["lng"],
                    p.get("alt_ft", 0), a.get("heading_deg", 0),
                    a.get("speed_kts", 0))
            else:
                self.send_surface_track(aid, p["lat"], p["lng"],
                    a.get("heading_deg", 0), a.get("speed_kts", 0))
            count += 1
        return count

    def _broadcast(self, msg):
        """Simulate broadcasting a message to all participants."""
        self.sequence += 1
        msg.sequence = self.sequence
        with self._lock:
            self.message_log.append(msg.to_dict())
            # Update shared track table
            self.track_table[msg.source_tn] = {
                **msg.data, "j_type": msg.j_type,
                "last_update": msg.timestamp,
            }
            self.stats["messages_sent"] += 1
            self.stats["tracks_shared"] = len(self.track_table)
            # Trim log
            if len(self.message_log) > 1000:
                self.message_log = self.message_log[-1000:]
        return msg.to_dict()

    def get_tactical_picture(self):
        """Get the shared tactical picture (all tracks)."""
        return dict(self.track_table)

    def get_messages(self, j_type=None, limit=50):
        if j_type:
            return [m for m in self.message_log if m["j_type"] == j_type][-limit:]
        return self.message_log[-limit:]

    def get_participants(self):
        return dict(self.participants)

    def broadcast_ppli_all(self, sim_assets):
        """Send PPLI heartbeat for every registered participant."""
        count = 0
        for aid, a in sim_assets.items():
            if aid in self.participants:
                p = a.get("position", {})
                self.send_ppli(aid, p.get("lat", 0), p.get("lng", 0),
                               p.get("alt_ft", 0),
                               a.get("heading_deg", 0),
                               a.get("speed_kts", 0))
                count += 1
        return count

    def get_status(self):
        return {
            "net_id": self.net_id,
            "participants": len(self.participants),
            "tracks": len(self.track_table),
            **self.stats,
        }
