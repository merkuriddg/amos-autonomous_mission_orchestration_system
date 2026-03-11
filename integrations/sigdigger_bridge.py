"""AMOS ↔ SigDigger Bridge

Reads signal detections from SigDigger via UDP broadcast output.
SigDigger can export detected signals as JSON lines over UDP.

Configure SigDigger: Settings → Export → UDP, host=localhost, port=5557

Each detection includes: frequency, bandwidth, SNR, modulation estimate.
"""

import json
import logging
import socket
import threading
import time
import uuid
from datetime import datetime, timezone

log = logging.getLogger("amos.sigdigger")


class SigDiggerBridge:
    """SigDigger UDP signal detection bridge for AMOS."""

    def __init__(self, listen_port=5557):
        self.listen_port = listen_port
        self.connected = False
        self._running = False
        self._lock = threading.Lock()
        self._sock = None
        self._thread = None

        # Buffers
        self.detections = []  # signal detections
        self._max_buffer = 500
        self._recv_count = 0
        self._error_count = 0

    def connect(self):
        """Start listening for SigDigger UDP output."""
        if self._running:
            return True
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            self._sock.bind(("0.0.0.0", self.listen_port))
            self._sock.settimeout(1.0)
            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True,
                                           name="sigdigger-udp")
            self._thread.start()
            self.connected = True
            log.info(f"SigDigger listening on UDP port {self.listen_port}")
            return True
        except Exception as e:
            log.error(f"SigDigger listen failed: {e}")
            return False

    def disconnect(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3)
        self.connected = False

    def _listen_loop(self):
        while self._running:
            try:
                data, addr = self._sock.recvfrom(65536)
                if data:
                    self._recv_count += 1
                    self._process(data, addr)
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    log.error("SigDigger socket error")
                break

    def _process(self, data, addr):
        try:
            text = data.decode("utf-8", errors="ignore").strip()
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    # Try CSV-style: freq,bw,snr,modulation
                    parts = line.split(",")
                    if len(parts) >= 3:
                        msg = {
                            "frequency_hz": float(parts[0]),
                            "bandwidth_hz": float(parts[1]),
                            "snr_db": float(parts[2]),
                            "modulation": parts[3] if len(parts) > 3 else "unknown",
                        }
                    else:
                        self._error_count += 1
                        continue

                detection = {
                    "id": f"SIG-{uuid.uuid4().hex[:8]}",
                    "source": "sigdigger",
                    "frequency_hz": msg.get("frequency_hz", msg.get("freq", 0)),
                    "frequency_mhz": round(msg.get("frequency_hz", msg.get("freq", 0)) / 1e6, 6),
                    "bandwidth_hz": msg.get("bandwidth_hz", msg.get("bw", 0)),
                    "snr_db": msg.get("snr_db", msg.get("snr", 0)),
                    "power_dbm": msg.get("power_dbm", msg.get("power", 0)),
                    "modulation": msg.get("modulation", "unknown"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "remote_addr": f"{addr[0]}:{addr[1]}",
                }

                with self._lock:
                    self.detections.append(detection)
                    if len(self.detections) > self._max_buffer:
                        self.detections = self.detections[-self._max_buffer:]

        except Exception as e:
            self._error_count += 1
            log.debug(f"SigDigger parse error: {e}")

    def get_detections(self, limit=100):
        with self._lock:
            return list(reversed(self.detections[-limit:]))

    def get_status(self):
        with self._lock:
            return {
                "available": True,
                "connected": self.connected,
                "listen_port": self.listen_port,
                "detections": len(self.detections),
                "received": self._recv_count,
                "errors": self._error_count,
            }
