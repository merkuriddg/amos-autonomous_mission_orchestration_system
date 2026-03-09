"""AMOS Plugin — Example Drone.

Reference implementation of an AMOS asset-adapter plugin.  Copy this
directory and customize it to integrate your own drone platform.

Plugin lifecycle:
    load → register → activate → operate → shutdown

Usage::

    from plugins.example_drone import ExampleDronePlugin
    plugin = ExampleDronePlugin()
    plugin.register(registry)
    plugin.activate(event_bus)
"""

import uuid
from datetime import datetime, timezone


class ExampleDronePlugin:
    """Minimal asset-adapter that demonstrates the AMOS plugin contract."""

    NAME = "example_drone"
    VERSION = "1.0"
    TYPE = "asset_adapter"

    def __init__(self):
        self.active = False
        self.asset_id = f"EXAMPLE-{uuid.uuid4().hex[:4].upper()}"

    # ── Lifecycle ──────────────────────────────────────────────
    def register(self, registry: dict) -> None:
        """Advertise capabilities to the platform."""
        registry[self.NAME] = {
            "type": self.TYPE,
            "version": self.VERSION,
            "capabilities": ["telemetry", "command", "health"],
        }

    def activate(self, event_bus=None) -> None:
        """Start publishing telemetry to the event bus."""
        self.active = True

    def shutdown(self) -> None:
        """Clean disconnect."""
        self.active = False

    # ── Asset contract methods ─────────────────────────────────
    def get_telemetry(self) -> dict:
        """Return current telemetry snapshot (stub)."""
        return {
            "asset_id": self.asset_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "position": {"lat": 0.0, "lng": 0.0, "alt_ft": 0},
            "speed_kts": 0,
            "heading_deg": 0,
            "battery_pct": 100,
        }

    def send_command(self, command: dict) -> dict:
        """Accept a command from AMOS (stub).

        Parameters
        ----------
        command : dict
            Must contain at least ``{"type": "...", "params": {...}}``.
        """
        return {
            "status": "accepted",
            "asset_id": self.asset_id,
            "command_type": command.get("type", "unknown"),
        }

    def get_health(self) -> dict:
        """Report health status (stub)."""
        return {
            "asset_id": self.asset_id,
            "operational": self.active,
            "battery_pct": 100,
            "comms_strength": 95,
            "gps_fix": True,
        }
