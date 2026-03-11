"""AMOS ↔ SDR++ Bridge

Connects to SDR++ via its built-in HTTP server API to retrieve:
  - Current VFO frequency, mode, bandwidth
  - Signal detections and spectrum data
  - Receiver status (gain, sample rate, source)

SDR++ HTTP API (default localhost:8080):
  GET /api/getFrequency
  GET /api/getMode
  GET /api/getBandwidth
  GET /api/getSampleRate
  POST /api/setFrequency?freq=<hz>

Requires SDR++ running with --server or server mode enabled.
"""

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone

log = logging.getLogger("amos.sdrpp")

try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError
except ImportError:
    urlopen = None


class SDRppBridge:
    """SDR++ HTTP API bridge for AMOS."""

    def __init__(self, host="localhost", port=8080):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.connected = False
        self._lock = threading.Lock()

        # State
        self.frequency_hz = 0
        self.mode = ""
        self.bandwidth_hz = 0
        self.sample_rate = 0
        self.gain = 0
        self.source = ""
        self.signals = []     # detected signal peaks
        self._poll_count = 0
        self._error_count = 0
        self._last_poll = 0

    def connect(self):
        """Verify SDR++ is reachable."""
        try:
            resp = self._get("/api/getFrequency")
            if resp is not None:
                self.connected = True
                self.frequency_hz = resp if isinstance(resp, (int, float)) else 0
                log.info(f"SDR++ connected: {self.base_url}")
                return True
        except Exception as e:
            log.error(f"SDR++ connect failed: {e}")
        self.connected = False
        return False

    def disconnect(self):
        self.connected = False

    def poll(self):
        """Poll SDR++ for current state."""
        if not self.connected:
            return
        now = time.time()
        if now - self._last_poll < 2:
            return
        self._last_poll = now

        try:
            freq = self._get("/api/getFrequency")
            if freq is not None:
                self.frequency_hz = freq
            mode = self._get("/api/getMode")
            if mode is not None:
                self.mode = mode if isinstance(mode, str) else str(mode)
            bw = self._get("/api/getBandwidth")
            if bw is not None:
                self.bandwidth_hz = bw
            sr = self._get("/api/getSampleRate")
            if sr is not None:
                self.sample_rate = sr
            self._poll_count += 1
        except Exception as e:
            self._error_count += 1
            log.debug(f"SDR++ poll error: {e}")

    def set_frequency(self, freq_hz):
        """Tune SDR++ to a specific frequency."""
        try:
            self._get(f"/api/setFrequency?freq={int(freq_hz)}")
            self.frequency_hz = freq_hz
            return True
        except Exception:
            return False

    def _get(self, path):
        """HTTP GET to SDR++ API."""
        if not urlopen:
            return None
        url = f"{self.base_url}{path}"
        try:
            req = Request(url)
            with urlopen(req, timeout=3) as resp:
                data = resp.read().decode("utf-8", errors="ignore").strip()
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    # Some endpoints return plain values
                    try:
                        return int(data)
                    except ValueError:
                        return data
        except (URLError, OSError):
            return None

    def get_status(self):
        with self._lock:
            return {
                "available": True,
                "connected": self.connected,
                "host": self.host,
                "port": self.port,
                "frequency_hz": self.frequency_hz,
                "frequency_mhz": round(self.frequency_hz / 1e6, 6) if self.frequency_hz else 0,
                "mode": self.mode,
                "bandwidth_hz": self.bandwidth_hz,
                "sample_rate": self.sample_rate,
                "polls": self._poll_count,
                "errors": self._error_count,
            }
