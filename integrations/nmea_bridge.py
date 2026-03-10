"""AMOS ↔ NMEA Bridge

Parses NMEA 0183 sentences from GPS receivers, marine electronics,
and other navigation instruments.

Supports:
  - Serial port (USB GPS, marine chartplotter)
  - TCP/UDP network feed (gpsd, OpenCPN, Signal K)

Sentences:
  - GGA — GPS fix position + quality
  - RMC — Recommended minimum (position, speed, course)
  - VTG — Course and speed over ground
  - DBT — Depth below transducer
  - MWV — Wind speed and angle
  - HDT — Heading (true)
  - XDR — Transducer measurements
"""

import logging
import socket
import threading
import time
from datetime import datetime, timezone

log = logging.getLogger("amos.nmea")


class NMEABridge:
    """NMEA 0183 sentence parser and bridge for AMOS."""

    def __init__(self, port="/dev/ttyUSB0", mode="serial", host="localhost",
                 tcp_port=10110, baudrate=4800):
        """Initialize NMEA bridge.

        Parameters
        ----------
        port : str
            Serial port path.
        mode : str
            'serial', 'tcp', or 'udp'.
        host : str
            TCP/UDP host for network mode.
        tcp_port : int
            TCP/UDP port for network mode.
        baudrate : int
            Serial baud rate (4800 standard NMEA, 38400 for high-speed).
        """
        self.port = port
        self.mode = mode
        self.host = host
        self.tcp_port = tcp_port
        self.baudrate = baudrate
        self.connected = False
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

        # Current navigation state
        self.position = {"lat": None, "lng": None, "alt_m": None}
        self.velocity = {"speed_kts": None, "course_deg": None}
        self.heading = {"true": None, "magnetic": None}
        self.depth = {"below_transducer_m": None}
        self.wind = {"speed_kts": None, "angle_deg": None, "reference": None}
        self.gps_quality = {"fix_type": 0, "satellites": 0, "hdop": None}
        self.last_update = None

    def connect(self):
        """Connect to NMEA data source."""
        try:
            if self.mode == "serial":
                import serial
                self._serial = serial.Serial(self.port, self.baudrate, timeout=2)
                self.connected = True
                log.info(f"NMEA serial connected: {self.port} @ {self.baudrate}")
            elif self.mode == "udp":
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._socket.bind((self.host, self.tcp_port))
                self._socket.settimeout(5)
                self.connected = True
                log.info(f"NMEA UDP listening: {self.host}:{self.tcp_port}")
            else:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(10)
                self._socket.connect((self.host, self.tcp_port))
                self.connected = True
                log.info(f"NMEA TCP connected: {self.host}:{self.tcp_port}")
            return True
        except ImportError:
            log.info("pyserial not available — NMEA serial mode disabled")
            return False
        except Exception as e:
            log.error(f"NMEA connection failed: {e}")
            return False

    def start_reading(self):
        """Start reading NMEA sentences in background."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop_reading(self):
        """Stop reading."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _read_loop(self):
        """Background loop to read and parse NMEA sentences."""
        buffer = ""
        while self._running:
            try:
                if self.mode == "serial":
                    line = self._serial.readline().decode("ascii", errors="ignore").strip()
                    if line:
                        self._parse_sentence(line)
                else:
                    data = self._socket.recv(4096).decode("ascii", errors="ignore")
                    if not data:
                        break
                    buffer += data
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            self._parse_sentence(line)
            except socket.timeout:
                continue
            except Exception as e:
                log.error(f"NMEA read error: {e}")
                time.sleep(1)

    def _parse_sentence(self, sentence):
        """Parse a single NMEA 0183 sentence."""
        if not sentence.startswith("$"):
            return
        # Strip checksum
        if "*" in sentence:
            sentence = sentence.split("*")[0]
        parts = sentence.split(",")
        if len(parts) < 2:
            return
        talker_sentence = parts[0][1:]  # remove $
        sentence_id = talker_sentence[-3:]  # last 3 chars = sentence type

        with self._lock:
            if sentence_id == "GGA":
                self._parse_gga(parts)
            elif sentence_id == "RMC":
                self._parse_rmc(parts)
            elif sentence_id == "VTG":
                self._parse_vtg(parts)
            elif sentence_id == "DBT":
                self._parse_dbt(parts)
            elif sentence_id == "MWV":
                self._parse_mwv(parts)
            elif sentence_id == "HDT":
                self._parse_hdt(parts)
            self.last_update = datetime.now(timezone.utc).isoformat()

    def _parse_gga(self, parts):
        """Parse GGA — GPS fix data."""
        if len(parts) < 15:
            return
        if parts[2] and parts[4]:
            self.position["lat"] = self._parse_lat(parts[2], parts[3])
            self.position["lng"] = self._parse_lng(parts[4], parts[5])
        if parts[9]:
            self.position["alt_m"] = float(parts[9])
        if parts[6]:
            self.gps_quality["fix_type"] = int(parts[6])
        if parts[7]:
            self.gps_quality["satellites"] = int(parts[7])
        if parts[8]:
            self.gps_quality["hdop"] = float(parts[8])

    def _parse_rmc(self, parts):
        """Parse RMC — Recommended minimum."""
        if len(parts) < 12:
            return
        if parts[3] and parts[5]:
            self.position["lat"] = self._parse_lat(parts[3], parts[4])
            self.position["lng"] = self._parse_lng(parts[5], parts[6])
        if parts[7]:
            self.velocity["speed_kts"] = float(parts[7])
        if parts[8]:
            self.velocity["course_deg"] = float(parts[8])

    def _parse_vtg(self, parts):
        """Parse VTG — Course and speed."""
        if len(parts) < 9:
            return
        if parts[1]:
            self.velocity["course_deg"] = float(parts[1])
        if parts[5]:
            self.velocity["speed_kts"] = float(parts[5])

    def _parse_dbt(self, parts):
        """Parse DBT — Depth below transducer."""
        if len(parts) < 7:
            return
        if parts[3]:
            self.depth["below_transducer_m"] = float(parts[3])

    def _parse_mwv(self, parts):
        """Parse MWV — Wind speed and angle."""
        if len(parts) < 6:
            return
        if parts[1]:
            self.wind["angle_deg"] = float(parts[1])
        if parts[2]:
            self.wind["reference"] = parts[2]  # R=relative, T=true
        if parts[3]:
            speed = float(parts[3])
            unit = parts[4] if len(parts) > 4 else "N"
            if unit == "K":
                speed = speed / 1.852  # km/h to knots
            elif unit == "M":
                speed = speed * 1.944  # m/s to knots
            self.wind["speed_kts"] = round(speed, 1)

    def _parse_hdt(self, parts):
        """Parse HDT — Heading true."""
        if len(parts) < 3 and parts[1]:
            return
        if parts[1]:
            self.heading["true"] = float(parts[1])

    def _parse_lat(self, value, hemisphere):
        """Parse NMEA latitude (DDMM.MMMM)."""
        deg = int(value[:2])
        minutes = float(value[2:])
        lat = deg + minutes / 60
        return round(-lat if hemisphere == "S" else lat, 6)

    def _parse_lng(self, value, hemisphere):
        """Parse NMEA longitude (DDDMM.MMMM)."""
        deg = int(value[:3])
        minutes = float(value[3:])
        lng = deg + minutes / 60
        return round(-lng if hemisphere == "W" else lng, 6)

    # ── AMOS integration ────────────────────────────────────

    def get_navigation(self):
        """Return current navigation state as AMOS-compatible dict."""
        with self._lock:
            return {
                "source": "nmea",
                "position": {
                    "lat": self.position["lat"],
                    "lng": self.position["lng"],
                    "alt_ft": round((self.position.get("alt_m") or 0) * 3.281, 0),
                },
                "speed_kts": self.velocity.get("speed_kts", 0),
                "course_deg": self.velocity.get("course_deg", 0),
                "heading_true": self.heading.get("true"),
                "depth_m": self.depth.get("below_transducer_m"),
                "wind": self.wind.copy(),
                "gps_quality": self.gps_quality.copy(),
                "last_update": self.last_update,
            }

    def sync_to_amos(self, sim_assets, asset_id="NMEA-NAV"):
        """Update an AMOS asset with NMEA navigation data."""
        nav = self.get_navigation()
        if nav["position"]["lat"] is None:
            return 0
        existing = next((a for a in sim_assets if a.get("id") == asset_id), None)
        if existing:
            existing["lat"] = nav["position"]["lat"]
            existing["lng"] = nav["position"]["lng"]
            existing["speed_kts"] = nav["speed_kts"]
            existing["heading_deg"] = nav.get("heading_true") or nav["course_deg"]
        else:
            sim_assets.append({
                "id": asset_id,
                "type": "vessel",
                "lat": nav["position"]["lat"],
                "lng": nav["position"]["lng"],
                "speed_kts": nav["speed_kts"],
                "source": "nmea",
            })
        return 1

    def get_status(self):
        return {
            "connected": self.connected,
            "mode": self.mode,
            "source": self.port if self.mode == "serial" else f"{self.host}:{self.tcp_port}",
            "reading": self._running,
            "has_fix": self.position["lat"] is not None,
            "satellites": self.gps_quality.get("satellites", 0),
        }

    def disconnect(self):
        self.stop_reading()
        for attr in ("_socket", "_serial"):
            obj = getattr(self, attr, None)
            if obj:
                try:
                    obj.close()
                except Exception:
                    pass
        self.connected = False
        log.info("NMEA bridge disconnected")
