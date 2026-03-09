"""AMOS Plugin Base — the contract all plugins must implement.

Every AMOS plugin extends ``PluginBase`` and implements its lifecycle
hooks.  The loader calls these methods in order::

    on_load  →  on_register  →  on_activate  →  (operate)  →  on_shutdown

Plugins that fail any lifecycle step are marked ERRORED and skipped.
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum

log = logging.getLogger("amos.plugins")


# ── Enums ──────────────────────────────────────────────────

class PluginType(str, Enum):
    """Recognized plugin types (matches Plugin SDK docs)."""
    ASSET_ADAPTER = "asset_adapter"
    SENSOR_ADAPTER = "sensor_adapter"
    MISSION_PACK = "mission_pack"
    PLANNER = "planner"
    ANALYTICS = "analytics"
    TRANSPORT = "transport"


class PluginState(str, Enum):
    """Plugin lifecycle state."""
    DISCOVERED = "discovered"
    LOADED = "loaded"
    REGISTERED = "registered"
    ACTIVE = "active"
    SHUTDOWN = "shutdown"
    ERRORED = "errored"
    DISABLED = "disabled"


# ── Base Class ─────────────────────────────────────────────

class PluginBase(ABC):
    """Abstract base class for all AMOS plugins.

    Subclasses must set the class-level ``PLUGIN_NAME`` attribute
    (or it will be read from plugin.yaml at load time).
    """

    # Override in subclass or loaded from plugin.yaml
    PLUGIN_NAME: str = ""
    PLUGIN_VERSION: str = "0.0"
    PLUGIN_TYPE: str = ""

    def __init__(self):
        self.state: PluginState = PluginState.DISCOVERED
        self.manifest: dict = {}     # populated by PluginLoader from plugin.yaml
        self.event_bus = None        # set during activation
        self.error: str = ""         # last error message

    # ── Lifecycle hooks (override these) ───────────────────

    def on_load(self) -> None:
        """Called after the plugin module is imported.

        Use for lightweight initialization — validate config,
        check optional dependencies, set defaults.
        """
        pass

    def on_register(self, registry: dict) -> None:
        """Called to register capabilities with the platform.

        Parameters
        ----------
        registry : dict
            The shared plugin capability registry.  Add your
            plugin's capabilities here.
        """
        registry[self.PLUGIN_NAME] = {
            "type": self.PLUGIN_TYPE,
            "version": self.PLUGIN_VERSION,
            "capabilities": self.get_capabilities(),
        }

    @abstractmethod
    def on_activate(self, event_bus) -> None:
        """Called when the plugin should start operating.

        Parameters
        ----------
        event_bus : EventBus
            The AMOS event bus — subscribe to topics and publish events.
        """
        ...

    def on_shutdown(self) -> None:
        """Called for clean disconnection.  Release resources here."""
        pass

    # ── Health / introspection ─────────────────────────────

    def health_check(self) -> dict:
        """Return plugin health status.

        Override to add domain-specific health data.
        """
        return {
            "name": self.PLUGIN_NAME,
            "version": self.PLUGIN_VERSION,
            "type": self.PLUGIN_TYPE,
            "state": self.state.value,
            "healthy": self.state == PluginState.ACTIVE,
            "error": self.error,
        }

    def get_capabilities(self) -> list[str]:
        """Return list of capabilities this plugin provides.

        Override to advertise specific capabilities.
        """
        return []

    # ── Convenience ────────────────────────────────────────

    def emit(self, topic: str, payload=None) -> None:
        """Publish an event on the bus (convenience wrapper)."""
        if self.event_bus:
            self.event_bus.publish(topic, payload, source=self.PLUGIN_NAME)

    def subscribe(self, topic: str, handler) -> None:
        """Subscribe to a bus topic (convenience wrapper)."""
        if self.event_bus:
            self.event_bus.subscribe(topic, handler)

    def to_dict(self) -> dict:
        """Serialise plugin metadata for API responses."""
        return {
            "name": self.PLUGIN_NAME,
            "version": self.PLUGIN_VERSION,
            "type": self.PLUGIN_TYPE,
            "state": self.state.value,
            "domain": self.manifest.get("domain", ""),
            "description": self.manifest.get("description", ""),
            "author": self.manifest.get("author", ""),
            "error": self.error,
        }
