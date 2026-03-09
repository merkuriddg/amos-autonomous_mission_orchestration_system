"""AMOS Plugin — ROS 2 Adapter.

Bridges the ROS 2 middleware into AMOS, publishing asset telemetry on
standard ROS topics and subscribing to external robot state.
See ``services/ros2_bridge.py`` for the core bridge implementation.

Usage::

    from plugins.ros2_adapter import ROS2AdapterPlugin
    plugin = ROS2AdapterPlugin()
    plugin.activate(event_bus)
"""


class ROS2AdapterPlugin:
    """ROS 2 transport plugin scaffold.

    Implements the AMOS plugin lifecycle:
    load → register → activate → operate → shutdown
    """

    NAME = "ros2_adapter"
    VERSION = "1.0"
    TYPE = "transport"

    def __init__(self):
        self.active = False

    def register(self, registry: dict) -> None:
        """Register plugin capabilities with the platform."""
        registry[self.NAME] = {
            "type": self.TYPE,
            "version": self.VERSION,
            "capabilities": ["publish_telemetry", "subscribe_state"],
        }

    def activate(self, event_bus=None) -> None:
        """Begin interacting with the AMOS event bus."""
        self.active = True

    def shutdown(self) -> None:
        """Cleanly disconnect."""
        self.active = False
