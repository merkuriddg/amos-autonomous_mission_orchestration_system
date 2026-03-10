"""AMOS Plugin — DragonOS / WarDragon SDR Adapter.

Bridges DragonOS-based SDR sensor nodes into AMOS.  Each DragonOS node
(WarDragon Pro, Raspberry Pi, etc.) can be mounted on an air, ground, or
maritime asset and acts as a mobile SIGINT/EW sensor platform.

Ingest channels:
  - MQTT: drone detections, RemoteID, spectrum alerts, RF events, status
  - Kismet REST API: WiFi / Bluetooth device observations
  - DF-Aggregator: KrakenSDR direction-finding bearing lines

Events emitted:
  - threat.detected           (hostile drone / unknown UAV)
  - sensor.contact_detected   (RemoteID, Kismet wireless device)
  - ew.spectrum_scan          (spectrum signal detections)
  - ew.emitter_detected       (strong / classified RF emitter)
  - sensor.bearing_fix        (DF-Aggregator bearing line)
  - sigint.device_observed    (Kismet WiFi/BT device)
  - dragonos.node_status      (node health / heartbeat)

See ``integrations/dragonos_bridge.py`` for the full bridge.
"""

import threading
import time

from core.plugin_base import PluginBase


class DragonOSAdapterPlugin(PluginBase):
    """DragonOS / WarDragon SDR sensor-adapter plugin."""

    PLUGIN_NAME = "dragonos_adapter"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "sensor_adapter"

    def __init__(self):
        super().__init__()
        self.bridge = None
        self._poll_thread = None
        self._running = False
        # Track what we've already emitted to avoid duplicates
        self._last_drone_count = 0
        self._last_rid_count = 0
        self._last_spectrum_count = 0
        self._last_df_count = 0

    def on_activate(self, event_bus) -> None:
        self.subscribe("dragonos.configure", self._on_configure)
        self.emit("sensor.registered", {
            "plugin": self.PLUGIN_NAME,
            "protocol": "dragonos_mqtt",
            "capabilities": self.get_capabilities(),
            "domains": ["air", "ground", "maritime"],
        })
        # Auto-connect if config provided in manifest
        cfg = self.manifest.get("config", {})
        if cfg.get("mqtt_host"):
            self._init_bridge(cfg)

    def on_shutdown(self) -> None:
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=3)
        if self.bridge:
            self.bridge.disconnect()

    def get_capabilities(self) -> list[str]:
        return [
            "drone_detection", "remoteid_decode", "spectrum_monitoring",
            "direction_finding", "kismet_wireless", "rf_events",
            "node_health", "health",
        ]

    # ── Bridge Init ────────────────────────────────────────

    def _init_bridge(self, cfg: dict):
        try:
            from integrations.dragonos_bridge import DragonOSBridge
            self.bridge = DragonOSBridge(
                node_id=cfg.get("node_id", "dragon-01"),
                mqtt_host=cfg.get("mqtt_host", "localhost"),
                mqtt_port=int(cfg.get("mqtt_port", 1883)),
                mqtt_user=cfg.get("mqtt_user", ""),
                mqtt_pass=cfg.get("mqtt_pass", ""),
                kismet_url=cfg.get("kismet_url", ""),
                kismet_api_key=cfg.get("kismet_api_key", ""),
                topic_prefix=cfg.get("topic_prefix", "wardragon"),
            )
            ok = self.bridge.connect()
            if ok:
                self._start_poll()
                self.emit("dragonos.connected", {
                    "node_id": self.bridge.node_id,
                    "mqtt_broker": f"{self.bridge.mqtt_host}:{self.bridge.mqtt_port}",
                })
        except ImportError:
            pass

    # ── Polling Loop — bridge → AMOS events ────────────────

    def _start_poll(self):
        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True,
            name="dragonos-adapter-poll",
        )
        self._poll_thread.start()

    def _poll_loop(self):
        """Continuously poll the bridge for new data and emit AMOS events."""
        while self._running:
            if not self.bridge or not self.bridge.connected:
                time.sleep(2)
                continue

            # ── Drone detections → threat.detected
            drones = self.bridge.get_drone_detections()
            new_drones = drones[self._last_drone_count:]
            self._last_drone_count = len(drones)
            for d in new_drones:
                p = d.get("payload", {})
                self.emit("threat.detected", {
                    "source": "dragonos",
                    "node_id": d.get("node_id"),
                    "type": p.get("type", "UAV"),
                    "classification": p.get("classification", "unknown"),
                    "freq_mhz": p.get("freq_mhz"),
                    "signal_dbm": p.get("signal_dbm"),
                    "lat": p.get("lat"),
                    "lng": p.get("lng"),
                    "confidence": p.get("confidence", 0),
                    "timestamp": d.get("ts"),
                })

            # ── RemoteID → sensor.contact_detected
            rids = self.bridge.get_remoteid_decodes()
            new_rids = rids[self._last_rid_count:]
            self._last_rid_count = len(rids)
            for r in new_rids:
                p = r.get("payload", {})
                self.emit("sensor.contact_detected", {
                    "source": "dragonos_remoteid",
                    "node_id": r.get("node_id"),
                    "drone_id": p.get("id") or p.get("serial_number"),
                    "operator_id": p.get("operator_id"),
                    "lat": p.get("lat"),
                    "lng": p.get("lng"),
                    "alt_m": p.get("alt_m"),
                    "speed_ms": p.get("speed_ms"),
                    "heading_deg": p.get("heading_deg"),
                    "classification": "remoteid_drone",
                    "timestamp": r.get("ts"),
                })

            # ── Spectrum → ew.emitter_detected
            spectrums = self.bridge.get_spectrum_events()
            new_spectrums = spectrums[self._last_spectrum_count:]
            self._last_spectrum_count = len(spectrums)
            for s in new_spectrums:
                p = s.get("payload", {})
                self.emit("ew.emitter_detected", {
                    "source": "dragonos_spectrum",
                    "node_id": s.get("node_id"),
                    "freq_mhz": p.get("freq_mhz"),
                    "power_dbm": p.get("power_dbm"),
                    "bandwidth_hz": p.get("bandwidth_hz"),
                    "modulation": p.get("modulation"),
                    "snr_db": p.get("snr_db"),
                    "classification": p.get("type", "unknown"),
                    "timestamp": s.get("ts"),
                })

            # ── DF bearings → sensor.bearing_fix
            dfs = self.bridge.get_df_bearings()
            new_dfs = dfs[self._last_df_count:]
            self._last_df_count = len(dfs)
            for df in new_dfs:
                p = df.get("payload", {})
                self.emit("sensor.bearing_fix", {
                    "source": "dragonos_df",
                    "node_id": df.get("node_id"),
                    "freq_mhz": p.get("freq_mhz"),
                    "bearing_deg": p.get("bearing_deg"),
                    "confidence": p.get("confidence", 0),
                    "station_lat": p.get("station_lat"),
                    "station_lng": p.get("station_lng"),
                    "timestamp": df.get("ts"),
                })

            # ── Kismet devices → sigint.device_observed (batch, every cycle)
            devices = self.bridge.get_kismet_devices()
            for mac, dev in devices.items():
                self.emit("sigint.device_observed", {
                    "source": "dragonos_kismet",
                    "node_id": self.bridge.node_id,
                    "mac": mac,
                    "name": dev.get("name"),
                    "device_type": dev.get("type"),
                    "signal_dbm": dev.get("signal_dbm"),
                    "channel": dev.get("channel"),
                    "lat": dev.get("lat"),
                    "lng": dev.get("lng"),
                    "manufacturer": dev.get("manuf"),
                })

            # ── Node health → dragonos.node_status
            status = self.bridge.node_status
            if status:
                self.emit("dragonos.node_status", {
                    "node_id": self.bridge.node_id,
                    "health": status,
                })

            time.sleep(2.0)

    # ── Event Handlers ─────────────────────────────────────

    def _on_configure(self, event):
        """Handle runtime reconfiguration."""
        cfg = event.payload or {}
        if self.bridge:
            self.bridge.disconnect()
        self._init_bridge(cfg)

    # ── Health ─────────────────────────────────────────────

    def health_check(self) -> dict:
        base = super().health_check()
        if self.bridge:
            st = self.bridge.get_status()
            base["dragonos_connected"] = st["connected"]
            base["node_id"] = st["node_id"]
            base["mqtt_broker"] = st["mqtt_broker"]
            base["stats"] = st["stats"]
            base["buffers"] = st["buffers"]
        else:
            base["dragonos_connected"] = False
        base["polling"] = self._running
        return base
