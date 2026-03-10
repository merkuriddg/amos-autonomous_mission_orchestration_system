"""AMOS SDK Contracts — canonical types and base classes.

These dataclasses define the wire format for events exchanged between
plugins and the AMOS core.  Plugin authors should use these types to
ensure compatibility with the event bus and analytics pipeline.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── Re-export core base class ──────────────────────────────
# When the SDK is installed standalone (pip install amos-sdk),
# PluginBase lives here.  Inside the AMOS tree we proxy to
# core.plugin_base so there is a single source of truth.

try:
    from core.plugin_base import PluginBase, PluginType, PluginState  # noqa: F401
except ImportError:
    # Standalone SDK — provide lightweight stubs
    class PluginType(str, Enum):
        ASSET_ADAPTER = "asset_adapter"
        SENSOR_ADAPTER = "sensor_adapter"
        MISSION_PACK = "mission_pack"
        PLANNER = "planner"
        ANALYTICS = "analytics"
        TRANSPORT = "transport"

    class PluginState(str, Enum):
        DISCOVERED = "discovered"
        LOADED = "loaded"
        REGISTERED = "registered"
        ACTIVE = "active"
        SHUTDOWN = "shutdown"
        ERRORED = "errored"
        DISABLED = "disabled"

    class PluginBase:
        """Minimal PluginBase stub for SDK-only environments."""

        PLUGIN_NAME: str = ""
        PLUGIN_VERSION: str = "0.0"
        PLUGIN_TYPE: str = ""

        def __init__(self):
            self.state = PluginState.DISCOVERED
            self.manifest: dict = {}
            self.event_bus = None
            self.error: str = ""

        def on_load(self) -> None:
            pass

        def on_register(self, registry: dict) -> None:
            registry[self.PLUGIN_NAME] = {
                "type": self.PLUGIN_TYPE,
                "version": self.PLUGIN_VERSION,
                "capabilities": self.get_capabilities(),
            }

        def on_activate(self, event_bus) -> None:
            raise NotImplementedError

        def on_shutdown(self) -> None:
            pass

        def health_check(self) -> dict:
            return {
                "name": self.PLUGIN_NAME,
                "version": self.PLUGIN_VERSION,
                "type": self.PLUGIN_TYPE,
                "state": self.state.value if hasattr(self.state, "value") else self.state,
                "healthy": self.state == PluginState.ACTIVE,
                "error": self.error,
            }

        def get_capabilities(self) -> list[str]:
            return []

        def emit(self, topic: str, payload=None) -> None:
            if self.event_bus:
                self.event_bus.publish(topic, payload, source=self.PLUGIN_NAME)

        def subscribe(self, topic: str, handler) -> None:
            if self.event_bus:
                self.event_bus.subscribe(topic, handler)


# ── Data Contracts ─────────────────────────────────────────

@dataclass
class AssetPosition:
    """Position report for a friendly asset (drone, UGV, etc.)."""
    asset_id: str
    lat: float
    lon: float
    alt: float = 0.0
    heading: float = 0.0
    speed: float = 0.0
    asset_type: str = "unknown"
    callsign: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SensorReading:
    """Normalised sensor reading from any adapter."""
    sensor_id: str
    sensor_type: str          # e.g. "adsb", "ais", "aprs", "meshtastic"
    lat: float | None = None
    lon: float | None = None
    alt: float | None = None
    raw: str = ""
    values: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ThreatReport:
    """Threat or hostile track report."""
    threat_id: str
    threat_type: str          # e.g. "hostile_uav", "vessel", "unknown"
    lat: float
    lon: float
    alt: float = 0.0
    heading: float = 0.0
    speed: float = 0.0
    confidence: float = 0.0   # 0.0–1.0
    source: str = ""          # originating sensor/plugin
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionWaypoint:
    """Single waypoint in a mission plan."""
    waypoint_id: str
    lat: float
    lon: float
    alt: float = 0.0
    speed: float | None = None
    action: str = "navigate"  # navigate | loiter | land | rtl
    loiter_seconds: int = 0
    radius_m: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginManifest:
    """Parsed representation of a plugin.yaml manifest."""
    name: str
    version: str
    plugin_type: str
    description: str = ""
    author: str = ""
    license: str = "MIT"
    entry_point: str = ""
    requires: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
