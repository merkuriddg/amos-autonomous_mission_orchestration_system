"""AMOS Plugin — Example Sensor (ADS-B).

Reference implementation of an AMOS sensor-adapter plugin.  Copy this
directory and customize it to integrate your own sensor feed.

This example connects to a dump1090/readsb ADS-B receiver and publishes
aircraft observations into AMOS for airspace awareness.

Plugin lifecycle:
    on_load → on_register → on_activate → (operate) → on_shutdown
"""

from datetime import datetime, timezone

from core.plugin_base import PluginBase


class ExampleSensorPlugin(PluginBase):
    """ADS-B sensor adapter — reference implementation."""

    PLUGIN_NAME = "example_sensor"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "sensor_adapter"

    def __init__(self):
        super().__init__()
        self.receiver = None
        self.observations = []

    # ── Lifecycle ──────────────────────────────────────────
    def on_load(self) -> None:
        """Validate that the ADS-B bridge is available."""
        try:
            from integrations.adsb_receiver import ADSBReceiver
            self._receiver_class = ADSBReceiver
        except ImportError:
            self._receiver_class = None

    def on_activate(self, event_bus) -> None:
        """Connect to ADS-B receiver and start tracking."""
        self.emit("sensor.registered", {
            "sensor": self.PLUGIN_NAME,
            "type": "adsb",
        })

        # Connect to local dump1090 (default settings)
        if self._receiver_class:
            self.receiver = self._receiver_class(
                host="localhost", port=8080, mode="json"
            )
            if self.receiver.connect():
                self.receiver.start_tracking(poll_interval=2.0)
                self.receiver.on_alert(self._on_adsb_alert)
                self.emit("sensor.online", {"sensor": self.PLUGIN_NAME})

    def on_shutdown(self) -> None:
        """Disconnect from ADS-B receiver."""
        if self.receiver:
            self.receiver.disconnect()
        self.emit("sensor.offline", {"sensor": self.PLUGIN_NAME})

    def get_capabilities(self) -> list[str]:
        return ["observations", "alerts", "health"]

    # ── Sensor contract ───────────────────────────────────
    def get_observations(self) -> list[dict]:
        """Return latest aircraft observations.

        Each observation follows the AMOS sensor observation contract:
        - source: sensor identifier
        - timestamp: ISO 8601
        - type: observation type
        - position: {lat, lng, alt_ft}
        - confidence: 0.0 - 1.0
        - raw: original data from the sensor
        """
        if not self.receiver:
            return []

        aircraft = self.receiver.get_aircraft()
        observations = []
        now = datetime.now(timezone.utc).isoformat()

        for ac in aircraft:
            observations.append({
                "source": self.PLUGIN_NAME,
                "timestamp": now,
                "type": "aircraft_track",
                "track_id": ac["track_id"],
                "callsign": ac.get("callsign", ""),
                "position": ac["position"],
                "speed_kts": ac.get("speed_kts", 0),
                "heading_deg": ac.get("heading_deg", 0),
                "confidence": 0.95,  # ADS-B is high-confidence
                "raw": ac,
            })

        self.observations = observations
        return observations

    # ── Event handlers ────────────────────────────────────
    def _on_adsb_alert(self, alert):
        """Handle ADS-B emergency alerts (squawk 7700/7500/7600)."""
        self.emit("sensor.alert", {
            "sensor": self.PLUGIN_NAME,
            "alert_type": "adsb_emergency",
            "squawk": alert.get("squawk"),
            "callsign": alert.get("callsign"),
            "position": alert.get("position"),
        })

    # ── Health ────────────────────────────────────────────
    def health_check(self) -> dict:
        base = super().health_check()
        if self.receiver:
            status = self.receiver.get_status()
            base["receiver_connected"] = status["connected"]
            base["aircraft_count"] = status["aircraft_count"]
            base["tracking"] = status["tracking"]
        else:
            base["receiver_connected"] = False
            base["aircraft_count"] = 0
        return base
