"""AMOS Plugin — ROS 2 Adapter.

Bridges the ROS 2 middleware into AMOS, publishing asset telemetry on
standard ROS topics and subscribing to external robot state.
See ``services/ros2_bridge.py`` for the core bridge implementation.
"""

from core.plugin_base import PluginBase


class ROS2AdapterPlugin(PluginBase):
    """ROS 2 transport plugin."""

    PLUGIN_NAME = "ros2_adapter"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "transport"

    def on_activate(self, event_bus) -> None:
        self.subscribe("asset.updated", self._on_asset_update)
        self.emit("plugin.ready", {"name": self.PLUGIN_NAME})

    def get_capabilities(self) -> list[str]:
        return ["publish_telemetry", "subscribe_state"]

    def _on_asset_update(self, event) -> None:
        """Forward asset updates to ROS 2 topics."""
        pass  # wire to services/ros2_bridge.py when ROS 2 is available
