"""AMOS Plugin — Example Drone.

Reference implementation of an AMOS asset-adapter plugin.  Copy this
directory and customize it to integrate your own drone platform.

Plugin lifecycle:
    on_load → on_register → on_activate → (operate) → on_shutdown
"""

import uuid
from datetime import datetime, timezone

from core.plugin_base import PluginBase


class ExampleDronePlugin(PluginBase):
    """Minimal asset-adapter that demonstrates the AMOS plugin contract."""

    PLUGIN_NAME = "example_drone"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "asset_adapter"

    def __init__(self):
        super().__init__()
        self.asset_id = f"EXAMPLE-{uuid.uuid4().hex[:4].upper()}"

    # ── Lifecycle ──────────────────────────────────────────────
    def on_activate(self, event_bus) -> None:
        """Start operating — subscribe to events."""
        self.subscribe("command.issued", self._on_command)
        self.emit("asset.registered", {
            "asset_id": self.asset_id,
            "plugin": self.PLUGIN_NAME,
        })

    def on_shutdown(self) -> None:
        """Clean disconnect."""
        self.emit("asset.unregistered", {"asset_id": self.asset_id})

    def get_capabilities(self) -> list[str]:
        return ["telemetry", "command", "health"]

    # ── Event handlers ─────────────────────────────────────────
    def _on_command(self, event) -> None:
        """Handle incoming commands from the event bus."""
        payload = event.payload or {}
        if payload.get("target") == self.asset_id:
            self.emit("command.acknowledged", {
                "asset_id": self.asset_id,
                "command": payload.get("type", "unknown"),
            })

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
        """Accept a command from AMOS (stub)."""
        return {
            "status": "accepted",
            "asset_id": self.asset_id,
            "command_type": command.get("type", "unknown"),
        }

    def health_check(self) -> dict:
        """Report health status."""
        base = super().health_check()
        base["asset_id"] = self.asset_id
        base["battery_pct"] = 100
        base["comms_strength"] = 95
        base["gps_fix"] = True
        return base
