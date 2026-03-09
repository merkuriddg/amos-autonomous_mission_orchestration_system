"""AMOS Plugin — PX4 Adapter.

Bridges PX4 autopilot systems (SITL or hardware) into AMOS via MAVLink.
See ``integrations/px4_bridge.py`` for the low-level connection logic.
"""

from core.plugin_base import PluginBase


class PX4AdapterPlugin(PluginBase):
    """PX4 asset-adapter plugin."""

    PLUGIN_NAME = "px4_adapter"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "asset_adapter"

    def on_activate(self, event_bus) -> None:
        self.subscribe("asset.*", self._on_asset_event)
        self.emit("plugin.ready", {"name": self.PLUGIN_NAME})

    def get_capabilities(self) -> list[str]:
        return ["telemetry", "command", "health"]

    def _on_asset_event(self, event) -> None:
        """Handle asset events for PX4-connected platforms."""
        pass  # wire to integrations/px4_bridge.py when hardware is present
