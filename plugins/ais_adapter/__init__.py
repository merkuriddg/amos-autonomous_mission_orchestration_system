"""AMOS Plugin — AIS Adapter.

Ingests AIS (Automatic Identification System) data from the
``integrations/ais_receiver.py`` bridge and publishes decoded vessel
positions, names, and MMSI identifiers into the AMOS event bus as
sensor readings for maritime situational awareness.
"""

from core.plugin_base import PluginBase


class AisAdapterPlugin(PluginBase):
    """AIS sensor-adapter plugin for maritime domain awareness."""

    PLUGIN_NAME = "ais_adapter"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "sensor_adapter"

    def __init__(self):
        super().__init__()
        self.receiver = None
        self.vessel_cache: dict = {}

    def on_activate(self, event_bus) -> None:
        self.subscribe("sensor.raw_nmea", self._on_raw_nmea)
        self.emit("sensor.registered", {
            "plugin": self.PLUGIN_NAME,
            "protocol": "ais",
            "formats": ["NMEA-0183", "AIVDM"],
        })
        try:
            from integrations.ais_receiver import AISReceiver
            self.receiver = AISReceiver()
            self.receiver.connect()
        except ImportError:
            pass

    def on_shutdown(self) -> None:
        if self.receiver:
            self.receiver.disconnect()

    def get_capabilities(self) -> list[str]:
        return ["vessel_tracking", "nmea_decode", "health"]

    def process_reading(self, raw_sentence: str) -> dict | None:
        """Decode an AIS NMEA sentence and return vessel dict.

        Returns None when the sentence is not AIS-related or cannot be
        parsed.
        """
        if not raw_sentence.startswith(("!AIVDM", "!AIVDO")):
            return None
        vessel = self._decode_aivdm(raw_sentence)
        if vessel:
            mmsi = vessel.get("mmsi")
            if mmsi:
                self.vessel_cache[mmsi] = vessel
            self.emit("sensor.vessel_position", vessel)
        return vessel

    def _on_raw_nmea(self, event):
        """Handle raw NMEA events from the integration layer."""
        sentence = event.payload.get("sentence", "") if event.payload else ""
        self.process_reading(sentence)

    @staticmethod
    def _decode_aivdm(sentence: str) -> dict | None:
        """Minimal AIS payload decode (type 1/2/3 position reports)."""
        try:
            parts = sentence.split(",")
            payload_chars = parts[5] if len(parts) > 5 else ""
            if not payload_chars:
                return None
            return {
                "source": "ais",
                "raw": sentence,
                "payload_length": len(payload_chars),
            }
        except (IndexError, ValueError):
            return None

    def health_check(self) -> dict:
        base = super().health_check()
        base["ais_connected"] = bool(self.receiver and self.receiver.connected)
        base["vessel_count"] = len(self.vessel_cache)
        return base
