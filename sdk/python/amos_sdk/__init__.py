"""AMOS Plugin SDK — build plugins for the Autonomous Mission Orchestration System.

Quick start::

    from amos_sdk import PluginBase, PluginType, SensorReading
    from amos_sdk.testing import PluginTestHarness

See https://github.com/merkuriddg/amos-autonomous_mission_orchestration_system
"""

__version__ = "0.1.0"

from .contracts import (
    PluginBase,
    PluginType,
    PluginState,
    AssetPosition,
    SensorReading,
    ThreatReport,
    MissionWaypoint,
    PluginManifest,
)
from .helpers import (
    load_manifest,
    validate_manifest,
    haversine_m,
    bearing_deg,
    format_mgrs,
)
