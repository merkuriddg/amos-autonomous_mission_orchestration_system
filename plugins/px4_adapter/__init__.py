"""AMOS Plugin — PX4 Adapter.

Bridges PX4 autopilot systems (SITL or hardware) into AMOS via MAVLink.
See ``integrations/px4_bridge.py`` for the low-level connection logic.

Usage::

    from plugins.px4_adapter import PX4AdapterPlugin
    plugin = PX4AdapterPlugin()
    plugin.activate(event_bus)
"""


class PX4AdapterPlugin:
    """PX4 asset-adapter plugin scaffold.

    Implements the AMOS plugin lifecycle:
    load → register → activate → operate → shutdown
    """

    NAME = "px4_adapter"
    VERSION = "1.0"
    TYPE = "asset_adapter"

    def __init__(self):
        self.active = False

    def register(self, registry: dict) -> None:
        """Register plugin capabilities with the platform."""
        registry[self.NAME] = {
            "type": self.TYPE,
            "version": self.VERSION,
            "capabilities": ["telemetry", "command", "health"],
        }

    def activate(self, event_bus=None) -> None:
        """Begin interacting with the AMOS event bus."""
        self.active = True

    def shutdown(self) -> None:
        """Cleanly disconnect."""
        self.active = False
