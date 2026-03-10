"""AMOS ↔ AIS Receiver Bridge

Integrates AIS (Automatic Identification System) vessel tracking
into AMOS for maritime domain awareness.

Supports:
  - NMEA serial AIS receiver (dAISy, RTL-SDR + rtl_ais)
  - Network AIS feed (TCP/UDP NMEA stream)

Capabilities:
  - Vessel position, course, speed, heading tracking
  - MMSI identification and vessel type classification
  - Maritime threat/contact correlation
  - Proximity alerting for AMOS maritime assets
"""

import logging
import re
import serial
import socket
import threading
import time
from datetime import datetime, timezone

log = logging.getLogger("amos.ais")

# AIS vessel type codes (simplified)
VESSEL_TYPES = {
    30: "fishing", 31: "towing", 32: "towing_large", 33: "dredging",
    34: "diving", 35: "military", 36: "sailing", 37: "pleasure",
    40: "high_speed", 50: "pilot", 51: "sar", 52: "tug",
    55: "law_enforcement", 60: "passenger", 70: "cargo",
    80: "tanker", 90: "other",
}

# AIS navigation status
NAV_STATUS = {
    0: "underway_engine", 1: "at_anchor", 2: "not_under_command",
    3: "restricted_maneuverability", 4: "constrained_draft",
    5: "moored", 6: "aground", 7: "fishing", 8: "underway_sailing",
}


class AISReceiver:
    """AIS vessel tracking receiver for AMOS."""

    def __init__(self, host="localhost", port=10110, mode="tcp"):
        """Initialize AIS receiver.

        Parameters
        ----------
        host : str
            Network host or serial port path (e.g., '/dev/ttyUSB0').
        port : int
            TCP/UDP port for network mode.
        mode : str
            Connection mode: 'tcp', 'udp', or 'serial'.
        """
        self.host = host
        self.port = port
        self.mode = mode
        self.connected = False
        self.vessels = {}  # MMSI -> vessel dict
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._callbacks = []

    def connect(self):
        """Connect to AIS data source."""
        try:
            if self.mode == "serial":
                self._serial = serial.Serial(self.host, 38400, timeout=2)
                self.connected = True
                log.info(f"AIS serial connected: {self.host}")
            elif self.mode == "udp":
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._socket.bind((self.host, self.port))
                self._socket.settimeout(5)
                self.connected = True
                log.info(f"AIS UDP listening: {self.host}:{self.port}")
            else:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(10)
                self._socket.connect((self.host, self.port))
                self.connected = True
                log.info(f"AIS TCP connected: {self.host}:{self.port}")
            return True
        except ImportError:
            log.info("pyserial not available — AIS serial mode disabled")
            return False
        except Exception as e:
            log.error(f"AIS connection failed: {e}")
            self.connected = False
            return False

    def start_tracking(self):
        """Start receiving AIS data in background."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()

    def stop_tracking(self):
        """Stop the receive loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _receive_loop(self):
        """Background loop to receive and decode AIS messages."""
        buffer = ""
        while self._running:
            try:
                if self.mode == "serial":
                    line = self._serial.readline().decode("ascii", errors="ignore").strip()
                    if line:
                        self._process_nmea(line)
                else:
                    data = self._socket.recv(4096).decode("ascii", errors="ignore")
                    if not data:
                        break
                    buffer += data
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            self._process_nmea(line)
            except socket.timeout:
                continue
            except Exception as e:
                log.error(f"AIS receive error: {e}")
                time.sleep(1)

    def _process_nmea(self, sentence):
        """Process an NMEA sentence containing AIS data."""
        if not sentence.startswith("!"):
            return
        # Extract AIS payload from AIVDM/AIVDO sentence
        # Format: !AIVDM,fragments,fragno,seqid,channel,payload,pad*checksum
        parts = sentence.split(",")
        if len(parts) < 7:
            return
        msg_type = parts[0]
        if msg_type not in ("!AIVDM", "!AIVDO"):
            return
        payload = parts[5]
        if not payload:
            return
        self._decode_ais(payload)

    def _decode_ais(self, payload):
        """Decode AIS binary payload (simplified for common message types)."""
        try:
            bits = self._payload_to_bits(payload)
            if len(bits) < 38:
                return
            msg_type = int(bits[:6], 2)
            mmsi = str(int(bits[8:38], 2)).zfill(9)

            if msg_type in (1, 2, 3):
                # Position report (Class A)
                self._decode_position_a(bits, mmsi)
            elif msg_type == 5:
                # Static and voyage data
                self._decode_static(bits, mmsi)
            elif msg_type == 18:
                # Position report (Class B)
                self._decode_position_b(bits, mmsi)
        except Exception as e:
            log.debug(f"AIS decode error: {e}")

    def _decode_position_a(self, bits, mmsi):
        """Decode Class A position report (msg types 1, 2, 3)."""
        if len(bits) < 168:
            return
        nav_status = int(bits[38:42], 2)
        sog = int(bits[50:60], 2) / 10.0  # speed over ground in knots
        lng = self._signed_int(bits[61:89], 28) / 600000.0
        lat = self._signed_int(bits[89:116], 27) / 600000.0
        cog = int(bits[116:128], 2) / 10.0  # course over ground
        heading = int(bits[128:137], 2)

        if lat == 0 and lng == 0:
            return  # no position

        with self._lock:
            vessel = self.vessels.get(mmsi, {"mmsi": mmsi})
            vessel.update({
                "mmsi": mmsi,
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "speed_kts": round(sog, 1),
                "course_deg": round(cog, 1),
                "heading_deg": heading if heading < 511 else None,
                "nav_status": NAV_STATUS.get(nav_status, "unknown"),
                "last_update": datetime.now(timezone.utc).isoformat(),
            })
            self.vessels[mmsi] = vessel

    def _decode_position_b(self, bits, mmsi):
        """Decode Class B position report (msg type 18)."""
        if len(bits) < 168:
            return
        sog = int(bits[46:56], 2) / 10.0
        lng = self._signed_int(bits[57:85], 28) / 600000.0
        lat = self._signed_int(bits[85:112], 27) / 600000.0
        cog = int(bits[112:124], 2) / 10.0
        heading = int(bits[124:133], 2)

        if lat == 0 and lng == 0:
            return

        with self._lock:
            vessel = self.vessels.get(mmsi, {"mmsi": mmsi})
            vessel.update({
                "mmsi": mmsi,
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "speed_kts": round(sog, 1),
                "course_deg": round(cog, 1),
                "heading_deg": heading if heading < 511 else None,
                "class": "B",
                "last_update": datetime.now(timezone.utc).isoformat(),
            })
            self.vessels[mmsi] = vessel

    def _decode_static(self, bits, mmsi):
        """Decode static/voyage data (msg type 5)."""
        if len(bits) < 424:
            return
        vessel_type = int(bits[232:240], 2)
        # Extract vessel name (bits 112-232, 6-bit ASCII)
        name_bits = bits[112:232]
        name = ""
        for i in range(0, len(name_bits), 6):
            c = int(name_bits[i:i + 6], 2)
            if c == 0:
                break
            name += chr(c + 64) if c < 32 else chr(c)

        with self._lock:
            vessel = self.vessels.get(mmsi, {"mmsi": mmsi})
            vessel["name"] = name.strip().strip("@")
            vessel["vessel_type"] = VESSEL_TYPES.get(vessel_type // 10 * 10, "unknown")
            vessel["vessel_type_code"] = vessel_type
            self.vessels[mmsi] = vessel

    def _payload_to_bits(self, payload):
        """Convert AIS armored ASCII payload to binary string."""
        bits = ""
        for c in payload:
            v = ord(c) - 48
            if v > 40:
                v -= 8
            bits += format(v, "06b")
        return bits

    def _signed_int(self, bits, length):
        """Convert two's complement binary string to signed int."""
        val = int(bits, 2)
        if val >= (1 << (length - 1)):
            val -= (1 << length)
        return val

    # ── AMOS integration ────────────────────────────────────

    def get_vessels(self):
        """Return tracked vessels as AMOS-compatible observations."""
        with self._lock:
            return [
                {
                    "source": "ais",
                    "track_id": v["mmsi"],
                    "name": v.get("name", ""),
                    "mmsi": v["mmsi"],
                    "position": {"lat": v["lat"], "lng": v["lng"]},
                    "speed_kts": v.get("speed_kts", 0),
                    "heading_deg": v.get("heading_deg") or v.get("course_deg", 0),
                    "course_deg": v.get("course_deg", 0),
                    "vessel_type": v.get("vessel_type", "unknown"),
                    "nav_status": v.get("nav_status", "unknown"),
                    "last_update": v.get("last_update", ""),
                }
                for v in self.vessels.values()
                if v.get("lat") and v.get("lng")
            ]

    def sync_to_amos(self, sim_threats):
        """Push AIS contacts into AMOS threat/observation layer."""
        vessels = self.get_vessels()
        for v in vessels:
            track_id = f"AIS-{v['mmsi']}"
            existing = next((t for t in sim_threats if t.get("id") == track_id), None)
            if existing:
                existing["lat"] = v["position"]["lat"]
                existing["lng"] = v["position"]["lng"]
            else:
                sim_threats.append({
                    "id": track_id,
                    "type": "vessel",
                    "source": "ais",
                    "name": v["name"],
                    "mmsi": v["mmsi"],
                    "lat": v["position"]["lat"],
                    "lng": v["position"]["lng"],
                    "vessel_type": v["vessel_type"],
                    "threat_level": "unknown",
                })
        return len(vessels)

    def get_status(self):
        return {
            "connected": self.connected,
            "mode": self.mode,
            "host": f"{self.host}:{self.port}" if self.mode != "serial" else self.host,
            "tracking": self._running,
            "vessel_count": len(self.vessels),
        }

    def disconnect(self):
        self.stop_tracking()
        for attr in ("_socket", "_serial"):
            obj = getattr(self, attr, None)
            if obj:
                try:
                    obj.close()
                except Exception:
                    pass
        self.connected = False
        log.info("AIS receiver disconnected")
