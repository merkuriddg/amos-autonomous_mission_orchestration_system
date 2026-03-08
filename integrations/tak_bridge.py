"""AMOS ↔ TAK (Team Awareness Kit) Bridge

Sends AMOS asset and threat positions to TAK servers via Cursor-on-Target (CoT) XML.
Supports ATAK (Android) and WinTAK.

Requires: Network access to TAK server (TCP/UDP port 8087/8089)
"""

import socket, time, logging, threading, uuid
from datetime import datetime, timezone, timedelta
from xml.etree.ElementTree import Element, SubElement, tostring

log = logging.getLogger("amos.tak")

# CoT type mappings
COT_TYPES = {
    "air": "a-f-A",         # friendly air
    "ground": "a-f-G",      # friendly ground
    "maritime": "a-f-S",    # friendly surface
    "threat_air": "a-h-A",  # hostile air
    "threat_ground": "a-h-G",
    "threat_maritime": "a-h-S",
}


def build_cot_event(uid, lat, lng, cot_type="a-f-G", callsign="AMOS",
                    alt_m=0, speed_kts=0, heading=0, stale_sec=60):
    """Build a Cursor-on-Target XML event."""
    now = datetime.now(timezone.utc)
    event = Element("event", {
        "version": "2.0", "uid": uid, "type": cot_type,
        "how": "m-g",  # machine-generated
        "time": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "start": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "stale": (now + timedelta(seconds=stale_sec)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    })
    point = SubElement(event, "point", {
        "lat": str(lat), "lon": str(lng),
        "hae": str(alt_m), "ce": "10", "le": "10",
    })
    detail = SubElement(event, "detail")
    contact = SubElement(detail, "contact", {"callsign": callsign})
    track_el = SubElement(detail, "track", {
        "course": str(heading), "speed": str(speed_kts * 0.5144),
    })
    return tostring(event, encoding="unicode")


class TAKBridge:
    """CoT bridge for TAK ecosystem."""

    def __init__(self, host="239.2.3.1", port=6969, protocol="udp"):
        self.host = host
        self.port = port
        self.protocol = protocol
        self.sock = None
        self.connected = False
        self.sent_count = 0

    def connect(self):
        try:
            if self.protocol == "udp":
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                if self.host.startswith("239."):
                    self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
            else:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.host, self.port))
            self.connected = True
            log.info(f"TAK connected: {self.protocol}://{self.host}:{self.port}")
            return True
        except Exception as e:
            log.error(f"TAK connect failed: {e}")
            return False

    def send_assets(self, sim_assets):
        """Push all AMOS assets as CoT events."""
        if not self.connected:
            return 0
        count = 0
        for aid, a in sim_assets.items():
            domain = a.get("domain", "ground")
            cot_type = COT_TYPES.get(domain, "a-f-G")
            cot_xml = build_cot_event(
                uid=f"AMOS-{aid}", lat=a["position"]["lat"], lng=a["position"]["lng"],
                cot_type=cot_type, callsign=aid,
                alt_m=a["position"].get("alt_ft", 0) * 0.3048,
                speed_kts=a.get("speed_kts", 0), heading=a.get("heading_deg", 0))
            self._send(cot_xml)
            count += 1
        return count

    def send_threats(self, sim_threats):
        if not self.connected:
            return 0
        count = 0
        for tid, t in sim_threats.items():
            if t.get("neutralized") or "lat" not in t:
                continue
            cot_xml = build_cot_event(
                uid=f"THREAT-{tid}", lat=t["lat"], lng=t.get("lng", 0),
                cot_type="a-h-G", callsign=f"HOSTILE-{tid}",
                speed_kts=t.get("speed_kts", 0))
            self._send(cot_xml)
            count += 1
        return count

    def _send(self, xml_str):
        try:
            data = xml_str.encode("utf-8")
            if self.protocol == "udp":
                self.sock.sendto(data, (self.host, self.port))
            else:
                self.sock.sendall(data)
            self.sent_count += 1
        except Exception as e:
            log.error(f"TAK send failed: {e}")

    def get_status(self):
        return {"connected": self.connected, "protocol": self.protocol,
                "host": self.host, "port": self.port, "sent": self.sent_count}
