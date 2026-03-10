"""AMOS Plugin — ATAK/TAK Adapter.

Bridges ATAK (Android Team Awareness Kit) / WinTAK into AMOS via
Cursor-on-Target (CoT) XML.  Pushes AMOS assets as blue force and
threats as hostile CoT markers.
See ``integrations/tak_bridge.py`` for connection details.
"""

from core.plugin_base import PluginBase


class AtakAdapterPlugin(PluginBase):
    """ATAK/TAK asset-adapter plugin."""

    PLUGIN_NAME = "atak_adapter"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "asset_adapter"

    def __init__(self):
        super().__init__()
        self.bridge = None

    def on_activate(self, event_bus) -> None:
        self.subscribe("asset.position_updated", self._on_asset_update)
        self.subscribe("threat.detected", self._on_threat_update)
        self.emit("asset.registered", {
            "plugin": self.PLUGIN_NAME,
            "protocol": "cot",
        })
        try:
            from integrations.tak_bridge import TAKBridge
            self.bridge = TAKBridge()
            self.bridge.connect()
        except ImportError:
            pass

    def on_shutdown(self) -> None:
        if self.bridge:
            self.bridge.disconnect()

    def get_capabilities(self) -> list[str]:
        return ["telemetry", "cot_publish", "health"]

    def push_assets(self, sim_assets):
        """Push AMOS assets to TAK as blue force CoT."""
        if self.bridge:
            self.bridge.send_assets(sim_assets)

    def push_threats(self, sim_threats):
        """Push AMOS threats to TAK as hostile CoT."""
        if self.bridge:
            self.bridge.send_threats(sim_threats)

    def _on_asset_update(self, event):
        """Forward asset position updates to TAK."""
        if self.bridge and event.payload:
            self.bridge.send_assets([event.payload])

    def _on_threat_update(self, event):
        """Forward threat detections to TAK."""
        if self.bridge and event.payload:
            self.bridge.send_threats([event.payload])

    def health_check(self) -> dict:
        base = super().health_check()
        base["tak_connected"] = bool(self.bridge and self.bridge.connected)
        return base
