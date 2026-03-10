"""AMOS Plugin — Meshtastic / LoRa Adapter.

Bridges Meshtastic mesh-radio nodes into AMOS for low-bandwidth,
off-grid comms.  Publishes node positions, telemetry, and text
messages via the ``integrations/lora_bridge.py`` transport layer.
"""

from core.plugin_base import PluginBase


class MeshtasticAdapterPlugin(PluginBase):
    """Meshtastic / LoRa sensor-adapter plugin."""

    PLUGIN_NAME = "meshtastic_adapter"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "sensor_adapter"

    def __init__(self):
        super().__init__()
        self.bridge = None
        self.node_cache: dict = {}

    def on_activate(self, event_bus) -> None:
        self.subscribe("mesh.packet_received", self._on_mesh_packet)
        self.emit("sensor.registered", {
            "plugin": self.PLUGIN_NAME,
            "protocol": "meshtastic",
            "formats": ["protobuf"],
        })
        try:
            from integrations.lora_bridge import LoRaBridge
            self.bridge = LoRaBridge()
            self.bridge.connect()
        except ImportError:
            pass

    def on_shutdown(self) -> None:
        if self.bridge:
            self.bridge.disconnect()

    def get_capabilities(self) -> list[str]:
        return ["mesh_tracking", "text_relay", "telemetry", "health"]

    def process_reading(self, packet: dict) -> dict | None:
        """Process a Meshtastic packet and return normalised dict.

        Handles position, telemetry, and text message packet types.
        """
        ptype = packet.get("type")
        node_id = packet.get("from")
        if not ptype or not node_id:
            return None

        normalised = {
            "source": "meshtastic",
            "node_id": node_id,
            "type": ptype,
        }

        if ptype == "position":
            normalised.update({
                "lat": packet.get("lat"),
                "lon": packet.get("lon"),
                "alt": packet.get("alt"),
            })
            self.node_cache[node_id] = normalised
            self.emit("sensor.mesh_position", normalised)
        elif ptype == "telemetry":
            normalised["metrics"] = packet.get("metrics", {})
            self.emit("sensor.mesh_telemetry", normalised)
        elif ptype == "text":
            normalised["text"] = packet.get("text", "")
            self.emit("sensor.mesh_text", normalised)
        else:
            return None

        return normalised

    def send_text(self, text: str, destination: str = "^all") -> bool:
        """Send a text message over the mesh network."""
        if self.bridge:
            return self.bridge.send_message(text, destination)
        return False

    def _on_mesh_packet(self, event):
        """Handle incoming mesh packets from the LoRa bridge."""
        if event.payload:
            self.process_reading(event.payload)

    def health_check(self) -> dict:
        base = super().health_check()
        base["mesh_connected"] = bool(self.bridge and self.bridge.connected)
        base["node_count"] = len(self.node_cache)
        return base
