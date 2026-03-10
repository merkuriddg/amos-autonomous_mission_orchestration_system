"""AMOS Plugin — APRS Adapter.

Bridges APRS (Automatic Packet Reporting System) into AMOS for
position tracking and messaging via amateur radio infrastructure.
See ``integrations/aprs_bridge.py`` for connection details.
"""

from core.plugin_base import PluginBase


class AprsAdapterPlugin(PluginBase):
    """APRS transport plugin."""

    PLUGIN_NAME = "aprs_adapter"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "transport"

    def __init__(self):
        super().__init__()
        self.bridge = None

    def on_activate(self, event_bus) -> None:
        self.emit("transport.registered", {"transport": self.PLUGIN_NAME})
        try:
            from integrations.aprs_bridge import APRSBridge
            self.bridge = APRSBridge()
            if self.bridge.connect():
                self.bridge.start_receiving()
                self.bridge.on_message(self._on_aprs_message)
        except ImportError:
            pass

    def on_shutdown(self) -> None:
        if self.bridge:
            self.bridge.disconnect()

    def get_capabilities(self) -> list[str]:
        return ["send", "receive", "position_tracking", "health"]

    def send(self, message: dict) -> bool:
        if not self.bridge:
            return False
        if message.get("type") == "position":
            return self.bridge.send_position(message["lat"], message["lng"])
        elif message.get("type") == "text":
            return self.bridge.send_message(message["to"], message["text"])
        return False

    def receive(self) -> list[dict]:
        return self.bridge.get_stations() if self.bridge else []

    def _on_aprs_message(self, msg):
        self.emit("transport.message_received", {
            "transport": self.PLUGIN_NAME,
            "message": msg,
        })

    def health_check(self) -> dict:
        base = super().health_check()
        base["bridge_status"] = self.bridge.get_status() if self.bridge else {}
        return base
