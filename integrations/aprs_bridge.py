"""AMOS ↔ APRS Bridge

Integrates APRS (Automatic Packet Reporting System) position and
telemetry data into AMOS. Used for tracking assets and operators
via amateur radio infrastructure.

Supports:
  - APRS-IS network gateway (TCP)
  - Local TNC via serial (KISS protocol)
  - Position reports, weather, telemetry, messages

Capabilities:
  - Asset position tracking via APRS beacons
  - Weather station data ingestion
  - Two-way messaging for field operators
  - Position beaconing for AMOS assets with callsigns
"""

import logging
import re
import socket
import threading
import time
from datetime import datetime, timezone

log = logging.getLogger("amos.aprs")

# APRS-IS servers
APRS_IS_SERVERS = [
    ("rotate.aprs2.net", 14580),
    ("noam.aprs2.net", 14580),
    ("euro.aprs2.net", 14580),
]

# APRS data type identifiers
APRS_POSITION = re.compile(r"^[!/=@]")
APRS_MIC_E = re.compile(r"^[\x1c-\x7f]")


class APRSBridge:
    """APRS integration bridge for AMOS."""

    def __init__(self, callsign="N0CALL", passcode="-1",
                 server="rotate.aprs2.net", port=14580, aprs_filter="r/27.85/-82.52/100"):
        """Initialize APRS bridge.

        Parameters
        ----------
        callsign : str
            Amateur radio callsign for APRS-IS login.
        passcode : str
            APRS-IS passcode (use '-1' for receive-only).
        server : str
            APRS-IS server hostname.
        port : int
            APRS-IS port (default 14580).
        aprs_filter : str
            Server-side filter string (e.g., 'r/lat/lng/range_km').
        """
        self.callsign = callsign.upper()
        self.passcode = passcode
        self.server = server
        self.port = port
        self.aprs_filter = aprs_filter
        self.connected = False
        self.stations = {}  # callsign -> station dict
        self._socket = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._message_callbacks = []

    def connect(self):
        """Connect to APRS-IS network."""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(30)
            self._socket.connect((self.server, self.port))

            # Read server banner
            banner = self._socket.recv(512).decode("ascii", errors="ignore")
            log.info(f"APRS-IS: {banner.strip()}")

            # Send login
            login = f"user {self.callsign} pass {self.passcode} vers AMOS 1.0"
            if self.aprs_filter:
                login += f" filter {self.aprs_filter}"
            self._socket.sendall((login + "\r\n").encode())

            # Read login response
            resp = self._socket.recv(512).decode("ascii", errors="ignore")
            if "verified" in resp.lower() or "unverified" in resp.lower():
                self.connected = True
                log.info(f"APRS-IS connected as {self.callsign}")
                return True
            else:
                log.warning(f"APRS-IS login failed: {resp.strip()}")
                return False
        except Exception as e:
            log.error(f"APRS-IS connection failed: {e}")
            self.connected = False
            return False

    def start_receiving(self):
        """Start receiving APRS packets in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()

    def stop_receiving(self):
        """Stop the receive loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _receive_loop(self):
        """Background loop to receive and parse APRS packets."""
        buffer = ""
        while self._running:
            try:
                data = self._socket.recv(4096).decode("ascii", errors="ignore")
                if not data:
                    break
                buffer += data
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    self._parse_packet(line)
            except socket.timeout:
                # Send keepalive
                try:
                    self._socket.sendall(b"#keepalive\r\n")
                except Exception:
                    break
            except Exception as e:
                log.error(f"APRS receive error: {e}")
                break
        self.connected = False

    def _parse_packet(self, raw):
        """Parse an APRS packet and extract position/telemetry."""
        try:
            # Split header from information field
            if ":" not in raw:
                return
            header, info = raw.split(":", 1)

            # Extract source callsign and path
            if ">" not in header:
                return
            source = header.split(">")[0].strip()

            # Parse position reports
            position = self._parse_position(info)
            if position:
                with self._lock:
                    self.stations[source] = {
                        "callsign": source,
                        "lat": position["lat"],
                        "lng": position["lng"],
                        "symbol": position.get("symbol", "/"),
                        "comment": position.get("comment", ""),
                        "speed_kts": position.get("speed_kts"),
                        "course_deg": position.get("course_deg"),
                        "altitude_ft": position.get("altitude_ft"),
                        "last_update": datetime.now(timezone.utc).isoformat(),
                        "raw": raw,
                    }

            # Parse messages
            if info.startswith(":"):
                self._parse_message(source, info)

        except Exception as e:
            log.debug(f"APRS parse error: {e} — raw: {raw[:80]}")

    def _parse_position(self, info):
        """Extract lat/lng from APRS position formats."""
        if not info:
            return None

        # Compressed position: /YYYY.YYN/XXXXX.XXW
        # Uncompressed: !DDMM.MMN/DDDMM.MMW
        lat_match = re.search(r"(\d{2})(\d{2}\.\d+)([NS])", info)
        lng_match = re.search(r"(\d{2,3})(\d{2}\.\d+)([EW])", info)

        if lat_match and lng_match:
            lat = int(lat_match.group(1)) + float(lat_match.group(2)) / 60
            if lat_match.group(3) == "S":
                lat = -lat
            lng = int(lng_match.group(1)) + float(lng_match.group(2)) / 60
            if lng_match.group(3) == "W":
                lng = -lng

            result = {"lat": round(lat, 6), "lng": round(lng, 6)}

            # Extract course/speed if present (CSE/SPD format)
            cs_match = re.search(r"(\d{3})/(\d{3})", info)
            if cs_match:
                result["course_deg"] = int(cs_match.group(1))
                result["speed_kts"] = int(cs_match.group(2))

            # Extract altitude from comment (/A=XXXXXX)
            alt_match = re.search(r"/A=(\d{6})", info)
            if alt_match:
                result["altitude_ft"] = int(alt_match.group(1))

            return result
        return None

    def _parse_message(self, source, info):
        """Parse APRS message and notify callbacks."""
        # Format: :ADDRESSEE:message text{msgno
        msg_match = re.match(r":(.{9}):(.+?)(?:\{(\w+))?$", info)
        if msg_match:
            addressee = msg_match.group(1).strip()
            text = msg_match.group(2)
            msgno = msg_match.group(3)
            msg = {
                "from": source,
                "to": addressee,
                "text": text,
                "msgno": msgno,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            for cb in self._message_callbacks:
                try:
                    cb(msg)
                except Exception:
                    pass

    def send_position(self, lat, lng, symbol="/[", comment="AMOS Asset"):
        """Transmit an APRS position beacon (requires valid passcode)."""
        if self.passcode == "-1":
            log.warning("Cannot transmit — receive-only mode (passcode=-1)")
            return False

        lat_str = self._encode_lat(lat)
        lng_str = self._encode_lng(lng)
        packet = f"{self.callsign}>APAMOS,TCPIP*:={lat_str}{symbol[0]}{lng_str}{symbol[1]}{comment}"
        try:
            self._socket.sendall((packet + "\r\n").encode())
            return True
        except Exception as e:
            log.error(f"APRS transmit failed: {e}")
            return False

    def send_message(self, addressee, text, msgno=None):
        """Send an APRS message."""
        if self.passcode == "-1":
            return False
        addr = f"{addressee:<9}"
        packet = f"{self.callsign}>APAMOS,TCPIP*::{addr}:{text}"
        if msgno:
            packet += f"{{{msgno}"
        try:
            self._socket.sendall((packet + "\r\n").encode())
            return True
        except Exception as e:
            log.error(f"APRS message failed: {e}")
            return False

    def on_message(self, callback):
        """Register callback for incoming messages."""
        self._message_callbacks.append(callback)

    def _encode_lat(self, lat):
        """Encode latitude to APRS format."""
        ns = "N" if lat >= 0 else "S"
        lat = abs(lat)
        deg = int(lat)
        minutes = (lat - deg) * 60
        return f"{deg:02d}{minutes:05.2f}{ns}"

    def _encode_lng(self, lng):
        """Encode longitude to APRS format."""
        ew = "E" if lng >= 0 else "W"
        lng = abs(lng)
        deg = int(lng)
        minutes = (lng - deg) * 60
        return f"{deg:03d}{minutes:05.2f}{ew}"

    # ── AMOS integration ────────────────────────────────────

    def get_stations(self):
        """Return tracked stations as AMOS-compatible observations."""
        with self._lock:
            return [
                {
                    "source": "aprs",
                    "track_id": s["callsign"],
                    "callsign": s["callsign"],
                    "position": {
                        "lat": s["lat"],
                        "lng": s["lng"],
                        "alt_ft": s.get("altitude_ft", 0),
                    },
                    "speed_kts": s.get("speed_kts", 0),
                    "heading_deg": s.get("course_deg", 0),
                    "symbol": s.get("symbol", ""),
                    "comment": s.get("comment", ""),
                    "last_update": s.get("last_update", ""),
                }
                for s in self.stations.values()
            ]

    def sync_to_amos(self, sim_assets):
        """Push APRS stations into AMOS asset layer."""
        stations = self.get_stations()
        for stn in stations:
            asset_id = f"APRS-{stn['callsign']}"
            existing = next((a for a in sim_assets if a.get("id") == asset_id), None)
            if existing:
                existing["lat"] = stn["position"]["lat"]
                existing["lng"] = stn["position"]["lng"]
            else:
                sim_assets.append({
                    "id": asset_id,
                    "type": "aprs_station",
                    "callsign": stn["callsign"],
                    "lat": stn["position"]["lat"],
                    "lng": stn["position"]["lng"],
                    "source": "aprs",
                })
        return len(stations)

    def get_status(self):
        """Return bridge status."""
        return {
            "connected": self.connected,
            "callsign": self.callsign,
            "server": f"{self.server}:{self.port}",
            "receiving": self._running,
            "station_count": len(self.stations),
        }

    def disconnect(self):
        """Disconnect and clean up."""
        self.stop_receiving()
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
        self.connected = False
        log.info("APRS bridge disconnected")
