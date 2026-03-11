"""AMOS Plugin — Unified SDR Adapter.

Wraps multiple SDR backends into a single sensor-adapter plugin:
  - SDR++ (HTTP API)
  - SigDigger (UDP signal detections)
  - DragonOS/WarDragon (via existing dragonos_bridge)

Publishes:
  - ew.sdr_signal        — signal detection from any SDR source
  - ew.emitter_detected  — classified RF emitter
  - sensor.sdr_status    — SDR source health/status

Allows operators to monitor spectrum from multiple tools
without needing the full DragonOS stack.
"""

import threading
import time

from core.plugin_base import PluginBase


class SDRAdapterPlugin(PluginBase):
    """Unified SDR sensor-adapter plugin."""

    PLUGIN_NAME = "sdr_adapter"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "sensor_adapter"

    def __init__(self):
        super().__init__()
        self.sdrpp = None
        self.sigdigger = None
        self._poll_thread = None
        self._running = False
        self._last_sig_count = 0

    def on_activate(self, event_bus) -> None:
        self.subscribe("sdr.configure", self._on_configure)
        self.emit("sensor.registered", {
            "plugin": self.PLUGIN_NAME,
            "protocol": "sdr_multi",
            "capabilities": self.get_capabilities(),
            "backends": ["sdrpp", "sigdigger", "dragonos"],
        })

    def on_shutdown(self) -> None:
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=3)
        if self.sdrpp:
            self.sdrpp.disconnect()
        if self.sigdigger:
            self.sigdigger.disconnect()

    def get_capabilities(self) -> list[str]:
        return [
            "spectrum_monitoring", "signal_detection",
            "frequency_control", "multi_backend", "health",
        ]

    # ── Configuration ───────────────────────────────────────

    def _on_configure(self, event):
        cfg = event.payload if hasattr(event, "payload") else event
        self._init_backends(cfg)

    def _init_backends(self, cfg: dict):
        # SDR++
        if cfg.get("sdrpp_host") or cfg.get("enable_sdrpp"):
            try:
                from integrations.sdrpp_bridge import SDRppBridge
                self.sdrpp = SDRppBridge(
                    host=cfg.get("sdrpp_host", "localhost"),
                    port=int(cfg.get("sdrpp_port", 8080)),
                )
                if self.sdrpp.connect():
                    self.emit("sdr.sdrpp_connected", {
                        "host": self.sdrpp.host,
                        "port": self.sdrpp.port,
                    })
            except ImportError:
                pass

        # SigDigger
        if cfg.get("sigdigger_port") or cfg.get("enable_sigdigger"):
            try:
                from integrations.sigdigger_bridge import SigDiggerBridge
                self.sigdigger = SigDiggerBridge(
                    listen_port=int(cfg.get("sigdigger_port", 5557)),
                )
                if self.sigdigger.connect():
                    self.emit("sdr.sigdigger_connected", {
                        "port": self.sigdigger.listen_port,
                    })
            except ImportError:
                pass

        if not self._running:
            self._start_poll()

    def _start_poll(self):
        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True,
            name="sdr-adapter-poll",
        )
        self._poll_thread.start()

    def _poll_loop(self):
        while self._running:
            # Poll SDR++
            if self.sdrpp and self.sdrpp.connected:
                self.sdrpp.poll()
                self.emit("sensor.sdr_status", {
                    "source": "sdrpp",
                    "frequency_mhz": self.sdrpp.frequency_hz / 1e6 if self.sdrpp.frequency_hz else 0,
                    "mode": self.sdrpp.mode,
                    "bandwidth_hz": self.sdrpp.bandwidth_hz,
                })

            # Poll SigDigger detections
            if self.sigdigger and self.sigdigger.connected:
                detections = self.sigdigger.get_detections(limit=500)
                new_sigs = detections[:max(0, len(detections) - self._last_sig_count)]
                self._last_sig_count = len(detections)

                for sig in new_sigs:
                    self.emit("ew.sdr_signal", {
                        "source": "sigdigger",
                        "frequency_mhz": sig.get("frequency_mhz", 0),
                        "bandwidth_hz": sig.get("bandwidth_hz", 0),
                        "snr_db": sig.get("snr_db", 0),
                        "power_dbm": sig.get("power_dbm", 0),
                        "modulation": sig.get("modulation", "unknown"),
                        "timestamp": sig.get("timestamp"),
                    })
                    # Classify strong signals as emitters
                    if sig.get("snr_db", 0) > 20:
                        self.emit("ew.emitter_detected", {
                            "source": "sigdigger",
                            "freq_mhz": sig.get("frequency_mhz", 0),
                            "power_dbm": sig.get("power_dbm", 0),
                            "modulation": sig.get("modulation", "unknown"),
                            "snr_db": sig.get("snr_db", 0),
                            "classification": "strong_emitter",
                        })

            time.sleep(2)

    def get_sources_status(self):
        """Status of all SDR backends."""
        sources = {}
        if self.sdrpp:
            sources["sdrpp"] = self.sdrpp.get_status()
        if self.sigdigger:
            sources["sigdigger"] = self.sigdigger.get_status()
        return sources

    def health_check(self) -> dict:
        base = super().health_check()
        base["sdrpp_connected"] = bool(self.sdrpp and self.sdrpp.connected)
        base["sigdigger_connected"] = bool(self.sigdigger and self.sigdigger.connected)
        return base
