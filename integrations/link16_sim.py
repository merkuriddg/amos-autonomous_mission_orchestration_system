"""AMOS Link-16 Tactical Data Link Simulator

Simulates Link-16 (TADIL J) message exchange for multi-platform interoperability.
Implements J-series message formats for tracks, commands, and network management.

Messages supported:
  J2.2  — Air Track
  J3.2  — Surface Track
  J7.0  — Command
  J13.0 — Network Time Reference
"""

import time, uuid, logging, threading, json
from datetime import datetime, timezone

log = logging.getLogger("amos.link16")

# J-series message types
J_MESSAGES = {
    "J2.2": "AIR_TRACK",
    "J3.2": "SURFACE_TRACK",
    "J3.5": "SUBSURFACE_TRACK",
    "J7.0": "COMMAND",
    "J7.1": "STATUS",
    "J12.6": "MISSION_ASSIGNMENT",
    "J13.0": "NET_TIME_REF",
}


class Link16Message:
    """A single Link-16 J-series message."""

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

    def get_status(self):
        return {
            "net_id": self.net_id,
            "participants": len(self.participants),
            "tracks": len(self.track_table),
            **self.stats,
        }
