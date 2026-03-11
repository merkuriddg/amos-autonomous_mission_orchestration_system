"""AMOS ← CoT (Cursor-on-Target) Ingest Bridge

Receives Cursor-on-Target XML events from TAK/ATAK clients, CoT gateways,
and other MIL-STD sources.  Ingested events are parsed, classified, and
buffered for the cot_adapter plugin to push onto the AMOS EventBus.

Listener modes:
  - UDP unicast / multicast (default 239.2.3.1:6969 — SA multicast group)
  - TCP server (accepts incoming connections from TAK clients)

CoT XML → AMOS mapping:
  a-f-*  →  friendly (blue force)
  a-h-*  →  hostile  (threat)
  a-n-*  →  neutral
  a-u-*  →  unknown
  b-*    →  event / alert (e.g. casevac, IED, SOS)
  t-*    →  tasking

Spec reference: MIL-STD-2525 / CoT Event Schema 2.0
"""

import json
import logging
import select
import socket
import struct
import threading
import time
import uuid
from datetime import datetime, timezone
from xml.etree.ElementTree import fromstring, ParseError

log = logging.getLogger("amos.cot_receiver")

# ── CoT type → AMOS affiliation mapping ─────────────────
_AFFIL_MAP = {
    "a-f": "friendly",
    "a-h": "hostile",
    "a-n": "neutral",
    "a-u": "unknown",
}

_DOMAIN_MAP = {
    "A": "air",
    "G": "ground",
    "S": "maritime",
    "P": "ground",    # installation
    "U": "ground",    # sub-surface → treated as ground for now
    "F": "ground",    # SOF
}

# Standard SA multicast group used by ATAK
_DEFAULT_MCAST_GROUP = "239.2.3.1"
_DEFAULT_PORT = 6969


class CoTReceiver:
    """Cursor-on-Target XML ingest bridge for AMOS."""

    def __init__(self, listen_addr="0.0.0.0", udp_port=6969,
                 mcast_group="239.2.3.1", tcp_port=4242,
                 enable_udp=True, enable_tcp=True):
        self.listen_addr = listen_addr
        self.udp_port = udp_port
        self.mcast_group = mcast_group
        self.tcp_port = tcp_port
        self.enable_udp = enable_udp
        self.enable_tcp = enable_tcp

        self.connected = False
        self._running = False
        self._lock = threading.Lock()

        # Buffers
        self._events = []           # all parsed CoT events
        self._friendlies = {}       # uid → latest friendly track
        self._hostiles = {}         # uid → latest hostile track
        self._neutrals = {}         # uid → latest neutral track
        self._alerts = []           # event-type CoT (b-*, t-*)
        self._raw_count = 0
        self._parse_errors = 0

        self._udp_sock = None
        self._tcp_sock = None
        self._threads = []

        self._max_buffer = 500

    # ── Connect / Disconnect ────────────────────────────────

    def connect(self):
        """Start listening for CoT events."""
        if self._running:
            return True
        self._running = True

        if self.enable_udp:
            try:
                self._start_udp()
            except Exception as e:
                log.error(f"CoT UDP listener failed: {e}")

        if self.enable_tcp:
            try:
                self._start_tcp()
            except Exception as e:
                log.error(f"CoT TCP server failed: {e}")

        self.connected = True
        log.info(f"CoT receiver active (UDP:{self.udp_port} TCP:{self.tcp_port})")
        return True

    def disconnect(self):
        """Stop all listeners."""
        self._running = False
        if self._udp_sock:
            try:
                self._udp_sock.close()
            except Exception:
                pass
        if self._tcp_sock:
            try:
                self._tcp_sock.close()
            except Exception:
                pass
        for t in self._threads:
            t.join(timeout=3)
        self._threads.clear()
        self.connected = False
        log.info("CoT receiver stopped")

    # ── UDP Listener ────────────────────────────────────────

    def _start_udp(self):
        self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                                       socket.IPPROTO_UDP)
        self._udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            self._udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self._udp_sock.bind((self.listen_addr, self.udp_port))

        # Join multicast group if configured
        if self.mcast_group:
            mreq = struct.pack("4sl",
                               socket.inet_aton(self.mcast_group),
                               socket.INADDR_ANY)
            self._udp_sock.setsockopt(socket.IPPROTO_IP,
                                      socket.IP_ADD_MEMBERSHIP, mreq)
            log.info(f"CoT joined multicast {self.mcast_group}:{self.udp_port}")

        self._udp_sock.settimeout(1.0)
        t = threading.Thread(target=self._udp_loop, daemon=True, name="cot-udp")
        t.start()
        self._threads.append(t)

    def _udp_loop(self):
        while self._running:
            try:
                data, addr = self._udp_sock.recvfrom(65536)
                if data:
                    self._raw_count += 1
                    self._process_raw(data, source=f"udp:{addr[0]}:{addr[1]}")
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    log.error("CoT UDP socket error")
                break

    # ── TCP Server ──────────────────────────────────────────

    def _start_tcp(self):
        self._tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._tcp_sock.bind((self.listen_addr, self.tcp_port))
        self._tcp_sock.listen(5)
        self._tcp_sock.settimeout(1.0)
        t = threading.Thread(target=self._tcp_accept_loop, daemon=True, name="cot-tcp")
        t.start()
        self._threads.append(t)
        log.info(f"CoT TCP server on port {self.tcp_port}")

    def _tcp_accept_loop(self):
        while self._running:
            try:
                client, addr = self._tcp_sock.accept()
                ct = threading.Thread(target=self._tcp_client_loop,
                                      args=(client, addr), daemon=True,
                                      name=f"cot-tcp-{addr[0]}")
                ct.start()
                self._threads.append(ct)
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    log.error("CoT TCP accept error")
                break

    def _tcp_client_loop(self, client, addr):
        buf = b""
        client.settimeout(5.0)
        source = f"tcp:{addr[0]}:{addr[1]}"
        while self._running:
            try:
                chunk = client.recv(65536)
                if not chunk:
                    break
                buf += chunk
                # CoT events end with </event>
                while b"</event>" in buf:
                    idx = buf.index(b"</event>") + len(b"</event>")
                    raw = buf[:idx]
                    buf = buf[idx:]
                    self._raw_count += 1
                    self._process_raw(raw, source=source)
            except socket.timeout:
                continue
            except Exception:
                break
        try:
            client.close()
        except Exception:
            pass

    # ── XML Parsing ─────────────────────────────────────────

    def _process_raw(self, data, source="unknown"):
        """Parse raw CoT XML bytes and store the result."""
        try:
            xml_str = data.decode("utf-8", errors="ignore").strip()
            # Find the <event ...> start tag if there's preamble
            start = xml_str.find("<event")
            if start < 0:
                self._parse_errors += 1
                return
            xml_str = xml_str[start:]
            root = fromstring(xml_str)
        except ParseError:
            self._parse_errors += 1
            return

        if root.tag != "event":
            return

        # Extract core fields
        uid = root.get("uid", "")
        cot_type = root.get("type", "")
        how = root.get("how", "")
        event_time = root.get("time", "")
        stale = root.get("stale", "")

        # Point element
        point = root.find("point")
        lat = float(point.get("lat", 0)) if point is not None else 0
        lon = float(point.get("lon", 0)) if point is not None else 0
        hae = float(point.get("hae", 0)) if point is not None else 0
        ce = float(point.get("ce", 999999)) if point is not None else 999999
        le = float(point.get("le", 999999)) if point is not None else 999999

        # Detail element
        detail = root.find("detail")
        callsign = ""
        course = 0
        speed_mps = 0
        remarks = ""

        if detail is not None:
            contact = detail.find("contact")
            if contact is not None:
                callsign = contact.get("callsign", "")

            track = detail.find("track")
            if track is not None:
                course = float(track.get("course", 0))
                speed_mps = float(track.get("speed", 0))

            rem = detail.find("remarks")
            if rem is not None and rem.text:
                remarks = rem.text.strip()

        # Classify
        affiliation = "unknown"
        domain = "ground"
        for prefix, aff in _AFFIL_MAP.items():
            if cot_type.startswith(prefix):
                affiliation = aff
                break

        # Domain from 4th char of type (e.g. a-f-G → G = ground)
        parts = cot_type.split("-")
        if len(parts) >= 3:
            domain = _DOMAIN_MAP.get(parts[2], "ground")

        # Build AMOS-compatible record
        record = {
            "id": f"COT-{uuid.uuid4().hex[:8]}",
            "uid": uid,
            "cot_type": cot_type,
            "affiliation": affiliation,
            "domain": domain,
            "callsign": callsign,
            "how": how,
            "position": {
                "lat": lat,
                "lng": lon,
                "alt_ft": round(hae * 3.281, 0),
                "alt_m": hae,
                "ce_m": ce,
                "le_m": le,
            },
            "heading_deg": course,
            "speed_kts": round(speed_mps * 1.944, 1),
            "speed_mps": speed_mps,
            "remarks": remarks,
            "event_time": event_time,
            "stale_time": stale,
            "source": source,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            # Route to appropriate buffer
            if cot_type.startswith("a-f"):
                self._friendlies[uid] = record
            elif cot_type.startswith("a-h"):
                self._hostiles[uid] = record
            elif cot_type.startswith("a-n"):
                self._neutrals[uid] = record
            elif cot_type.startswith(("b-", "t-")):
                self._alerts.append(record)
                if len(self._alerts) > self._max_buffer:
                    self._alerts = self._alerts[-self._max_buffer:]
            else:
                # Unknown affiliation — store as neutral
                self._neutrals[uid] = record

            self._events.append(record)
            if len(self._events) > self._max_buffer:
                self._events = self._events[-self._max_buffer:]

    # ── Manual injection (for testing / API) ────────────────

    def inject_cot_xml(self, xml_str):
        """Parse and ingest a CoT XML string (API / test path)."""
        self._raw_count += 1
        self._process_raw(xml_str.encode("utf-8"), source="api_inject")

    # ── Data Accessors ──────────────────────────────────────

    def get_all_events(self, limit=100):
        with self._lock:
            return list(reversed(self._events[-limit:]))

    def get_friendlies(self):
        with self._lock:
            return list(self._friendlies.values())

    def get_hostiles(self):
        with self._lock:
            return list(self._hostiles.values())

    def get_neutrals(self):
        with self._lock:
            return list(self._neutrals.values())

    def get_alerts(self, limit=50):
        with self._lock:
            return list(reversed(self._alerts[-limit:]))

    def get_all_tracks(self):
        """Combined friendly + hostile + neutral tracks."""
        with self._lock:
            tracks = []
            for uid, r in self._friendlies.items():
                tracks.append({**r, "_affil": "friendly"})
            for uid, r in self._hostiles.items():
                tracks.append({**r, "_affil": "hostile"})
            for uid, r in self._neutrals.items():
                tracks.append({**r, "_affil": "neutral"})
            return tracks

    def get_status(self):
        with self._lock:
            return {
                "available": True,
                "connected": self.connected,
                "udp_port": self.udp_port,
                "tcp_port": self.tcp_port,
                "mcast_group": self.mcast_group,
                "enable_udp": self.enable_udp,
                "enable_tcp": self.enable_tcp,
                "stats": {
                    "raw_received": self._raw_count,
                    "parse_errors": self._parse_errors,
                    "events_buffered": len(self._events),
                },
                "tracks": {
                    "friendly": len(self._friendlies),
                    "hostile": len(self._hostiles),
                    "neutral": len(self._neutrals),
                    "alerts": len(self._alerts),
                },
            }
