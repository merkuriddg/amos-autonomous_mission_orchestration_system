"""AMOS Plugin — ADS-B Adapter.

Bridges ADS-B aircraft surveillance into AMOS via the adsb_receiver integration.
See ``integrations/adsb_receiver.py`` for connection details.
"""

from core.plugin_base import PluginBase


class AdsbAdapterPlugin(PluginBase):
    """ADS-B sensor-adapter plugin."""

    PLUGIN_NAME = "adsb_adapter"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "sensor_adapter"

    def __init__(self):
        super().__init__()
        self.receiver = None

    def on_activate(self, event_bus) -> None:
        self.emit("sensor.registered", {"sensor": self.PLUGIN_NAME, "type": "adsb"})
        try:
            from integrations.adsb_receiver import ADSBReceiver
            self.receiver = ADSBReceiver(host="localhost", port=8080, mode="json")
            if self.receiver.connect():
                self.receiver.start_tracking()
        except ImportError:
            pass

    def on_shutdown(self) -> None:
        if self.receiver:
            self.receiver.disconnect()

    def get_capabilities(self) -> list[str]:
        return ["observations", "alerts", "health"]

    def get_observations(self) -> list[dict]:
        return self.receiver.get_aircraft() if self.receiver else []

    def health_check(self) -> dict:
        base = super().health_check()
        base["receiver_status"] = self.receiver.get_status() if self.receiver else {}
        return base
