"""AMOS Plugin — CoT (Cursor-on-Target) Adapter.

Bridges Cursor-on-Target XML ingest into the AMOS event bus.
Wraps ``integrations/cot_receiver.py`` and publishes:

  - sensor.cot_position    — any position update (all affiliations)
  - friendly.cot_update    — blue-force position from TAK/ATAK clients
  - threat.cot_detected    — hostile track from CoT source
  - sensor.cot_alert       — CoT event/tasking (b-* or t-* types)

Subscribe to ``cot.configure`` to trigger bridge init with custom params.
"""

import threading
import time

from core.plugin_base import PluginBase


class CoTAdapterPlugin(PluginBase):
    """Cursor-on-Target ingest adapter plugin."""

    PLUGIN_NAME = "cot_adapter"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "sensor_adapter"

    def __init__(self):
        super().__init__()
        self.receiver = None
        self._poll_thread = None
        self._running = False
        self._last_event_count = 0
        self._last_alert_count = 0

    def on_activate(self, event_bus) -> None:
        self.subscribe("cot.configure", self._on_configure)
        self.emit("sensor.registered", {
            "plugin": self.PLUGIN_NAME,
            "protocol": "cot_xml",
            "capabilities": self.get_capabilities(),
            "formats": ["CoT XML 2.0", "MIL-STD-2525"],
        })
        # Auto-connect if config provided in manifest
        cfg = self.manifest.get("config", {})
        if cfg.get("auto_connect"):
            self._init_receiver(cfg)

    def on_shutdown(self) -> None:
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=3)
        if self.receiver:
            self.receiver.disconnect()

    def get_capabilities(self) -> list[str]:
        return [
            "cot_ingest", "blue_force_tracking", "hostile_tracking",
            "cot_alerts", "cot_inject", "health",
        ]

    # ── Receiver Init ───────────────────────────────────────

    def _on_configure(self, event):
        cfg = event.payload if hasattr(event, "payload") else event
        self._init_receiver(cfg)

    def _init_receiver(self, cfg: dict):
        try:
            from integrations.cot_receiver import CoTReceiver
            self.receiver = CoTReceiver(
                listen_addr=cfg.get("listen_addr", "0.0.0.0"),
                udp_port=int(cfg.get("udp_port", 6969)),
                mcast_group=cfg.get("mcast_group", "239.2.3.1"),
                tcp_port=int(cfg.get("tcp_port", 4242)),
                enable_udp=cfg.get("enable_udp", True),
                enable_tcp=cfg.get("enable_tcp", True),
            )
            ok = self.receiver.connect()
            if ok:
                self._start_poll()
                self.emit("cot.connected", {
                    "udp_port": self.receiver.udp_port,
                    "tcp_port": self.receiver.tcp_port,
                    "mcast_group": self.receiver.mcast_group,
                })
        except ImportError:
            pass

    # ── Polling Loop — receiver → AMOS events ───────────────

    def _start_poll(self):
        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True,
            name="cot-adapter-poll",
        )
        self._poll_thread.start()

    def _poll_loop(self):
        """Poll receiver for new events and emit to AMOS EventBus."""
        while self._running:
            if not self.receiver or not self.receiver.connected:
                time.sleep(2)
                continue

            # ── New events → sensor.cot_position + affiliation events
            events = self.receiver.get_all_events(limit=500)
            new_events = events[:max(0, len(events) - self._last_event_count)]
            self._last_event_count = len(events)

            for ev in new_events:
                # Generic position event
                self.emit("sensor.cot_position", {
                    "source": "cot",
                    "uid": ev.get("uid"),
                    "callsign": ev.get("callsign"),
                    "cot_type": ev.get("cot_type"),
                    "affiliation": ev.get("affiliation"),
                    "domain": ev.get("domain"),
                    "lat": ev["position"]["lat"],
                    "lng": ev["position"]["lng"],
                    "alt_ft": ev["position"]["alt_ft"],
                    "heading_deg": ev.get("heading_deg", 0),
                    "speed_kts": ev.get("speed_kts", 0),
                    "timestamp": ev.get("received_at"),
                })

                # Affiliation-specific events
                affil = ev.get("affiliation", "unknown")
                if affil == "friendly":
                    self.emit("friendly.cot_update", {
                        "source": "cot",
                        "uid": ev.get("uid"),
                        "callsign": ev.get("callsign"),
                        "domain": ev.get("domain"),
                        "lat": ev["position"]["lat"],
                        "lng": ev["position"]["lng"],
                        "alt_ft": ev["position"]["alt_ft"],
                        "heading_deg": ev.get("heading_deg", 0),
                        "speed_kts": ev.get("speed_kts", 0),
                    })
                elif affil == "hostile":
                    self.emit("threat.cot_detected", {
                        "source": "cot",
                        "uid": ev.get("uid"),
                        "callsign": ev.get("callsign"),
                        "cot_type": ev.get("cot_type"),
                        "domain": ev.get("domain"),
                        "lat": ev["position"]["lat"],
                        "lng": ev["position"]["lng"],
                        "alt_ft": ev["position"]["alt_ft"],
                        "heading_deg": ev.get("heading_deg", 0),
                        "speed_kts": ev.get("speed_kts", 0),
                    })

            # ── Alerts
            alerts = self.receiver.get_alerts(limit=500)
            new_alerts = alerts[:max(0, len(alerts) - self._last_alert_count)]
            self._last_alert_count = len(alerts)

            for alert in new_alerts:
                self.emit("sensor.cot_alert", {
                    "source": "cot",
                    "uid": alert.get("uid"),
                    "cot_type": alert.get("cot_type"),
                    "remarks": alert.get("remarks"),
                    "lat": alert["position"]["lat"],
                    "lng": alert["position"]["lng"],
                    "timestamp": alert.get("received_at"),
                })

            time.sleep(2)

    def health_check(self) -> dict:
        base = super().health_check()
        if self.receiver:
            s = self.receiver.get_status()
            base["cot_connected"] = s.get("connected", False)
            base["tracks"] = s.get("tracks", {})
            base["stats"] = s.get("stats", {})
        else:
            base["cot_connected"] = False
        return base
