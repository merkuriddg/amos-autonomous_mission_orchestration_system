"""AMOS Plugin -- OpenDroneID / FAA RemoteID Adapter.

Wraps the existing ``integrations/remoteid_bridge.py`` as an EventBus-connected
plugin.  When a RemoteID beacon is received the adapter emits AMOS events so
other subsystems (threat tracker, map, SIGINT) can react in real time.

Events emitted:
  - sensor.remoteid_beacon      (per-drone position + metadata)
  - threat.drone_detected       (unknown / unclassified drone sighting)
  - sensor.remoteid_operator    (operator location when available)
  - sensor.remoteid_status      (bridge health heartbeat)

See ``integrations/remoteid_bridge.py`` for the full bridge.
"""

import threading
import time

from core.plugin_base import PluginBase


class RemoteIDAdapterPlugin(PluginBase):
    """OpenDroneID / FAA RemoteID sensor-adapter plugin."""

    PLUGIN_NAME = "remoteid_adapter"
    PLUGIN_VERSION = "1.1"
    PLUGIN_TYPE = "sensor_adapter"

    def __init__(self):
        super().__init__()
        self.bridge = None
        self.drone_ref_db = None
        self._poll_thread = None
        self._running = False
        self._last_drone_ids = set()
        # Load drone reference DB for enrichment
        try:
            from services.drone_reference import DroneReferenceDB
            self.drone_ref_db = DroneReferenceDB()
        except Exception:
            pass

    # ── Lifecycle ─────────────────────────────────────────

    def on_activate(self, event_bus) -> None:
        self.subscribe("remoteid.configure", self._on_configure)
        self.emit("sensor.registered", {
            "plugin": self.PLUGIN_NAME,
            "protocol": "remoteid",
            "capabilities": self.get_capabilities(),
            "domains": ["air"],
        })
        cfg = self.manifest.get("config", {})
        if cfg.get("host"):
            self._init_bridge(cfg)

    def on_shutdown(self) -> None:
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=3)
        if self.bridge:
            self.bridge.disconnect()

    def get_capabilities(self) -> list[str]:
        return [
            "remoteid_receive", "drone_identification",
            "operator_location", "airspace_awareness", "health",
        ]

    # ── Configuration ─────────────────────────────────────

    def _on_configure(self, data):
        """Handle runtime reconfiguration via EventBus."""
        self._init_bridge(data)

    def _init_bridge(self, cfg: dict):
        try:
            from integrations.remoteid_bridge import RemoteIDBridge
            self.bridge = RemoteIDBridge(
                host=cfg.get("host", "localhost"),
                port=int(cfg.get("port", 7070)),
                mode=cfg.get("mode", "network"),
            )
            ok = self.bridge.connect()
            if ok:
                self.bridge.start_scanning()
                self._start_poll()
                self.emit("remoteid.connected", {
                    "host": self.bridge.host,
                    "port": self.bridge.port,
                    "mode": self.bridge.mode,
                })
        except ImportError:
            pass

    # ── Poll Loop ─────────────────────────────────────────

    def _start_poll(self):
        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True,
            name="remoteid-adapter-poll",
        )
        self._poll_thread.start()

    def _poll_loop(self):
        """Poll bridge for new RemoteID drones and emit AMOS events."""
        while self._running:
            if not self.bridge or not self.bridge.connected:
                time.sleep(2)
                continue

            try:
                drones = self.bridge.get_drones()
                current_ids = set()

                for d in drones:
                    tid = d.get("track_id", "")
                    current_ids.add(tid)

                    # Per-drone beacon event
                    self.emit("sensor.remoteid_beacon", {
                        "source": "remoteid",
                        "track_id": tid,
                        "serial_number": d.get("serial_number", ""),
                        "ua_type": d.get("ua_type", "unknown"),
                        "position": d.get("position", {}),
                        "speed_kts": d.get("speed_kts", 0),
                        "heading_deg": d.get("heading_deg", 0),
                        "last_update": d.get("last_update", ""),
                    })

                    # Operator position if available
                    op_pos = d.get("operator_position")
                    if op_pos and op_pos.get("lat") is not None:
                        self.emit("sensor.remoteid_operator", {
                            "track_id": tid,
                            "operator_lat": op_pos["lat"],
                            "operator_lng": op_pos["lng"],
                        })

                    # New drone sighting — enrich with reference DB
                    if tid not in self._last_drone_ids:
                        det = {
                            "source": "remoteid",
                            "track_id": tid,
                            "serial_number": d.get("serial_number", ""),
                            "ua_type": d.get("ua_type", "unknown"),
                            "lat": d.get("position", {}).get("lat"),
                            "lng": d.get("position", {}).get("lng"),
                            "alt_ft": d.get("position", {}).get("alt_ft"),
                            "threat_level": "unknown",
                        }
                        if self.drone_ref_db and self.drone_ref_db.loaded:
                            self.drone_ref_db.enrich_track(det)
                            if det.get("ref_threat_classification") == "hostile":
                                det["threat_level"] = "high"
                            elif det.get("ref_threat_classification") == "friendly":
                                det["threat_level"] = "low"
                            elif det.get("ref_matched"):
                                det["threat_level"] = "medium"
                        self.emit("threat.drone_detected", det)

                self._last_drone_ids = current_ids

                # Health heartbeat
                self.emit("sensor.remoteid_status", {
                    "connected": self.bridge.connected,
                    "scanning": self.bridge._running,
                    "drone_count": len(drones),
                    "mode": self.bridge.mode,
                })

            except Exception:
                pass

            time.sleep(2)

    # ── Status ────────────────────────────────────────────

    def get_status(self) -> dict:
        if not self.bridge:
            return {"connected": False}
        s = self.bridge.get_status()
        s["plugin"] = self.PLUGIN_NAME
        return s

    def tick(self):
        """Called by plugin loader on each sim cycle (if applicable)."""
        pass
