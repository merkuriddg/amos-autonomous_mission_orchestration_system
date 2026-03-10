"""AMOS Plugin — PX4 Autopilot Adapter.

Bridges PX4-powered drones into AMOS via MAVLink.  Subscribes to
asset command events and forwards them to the PX4 bridge.  Emits
position/telemetry updates from real drone telemetry back into the
AMOS event bus.
"""

import threading
import time

from core.plugin_base import PluginBase


class PX4AdapterPlugin(PluginBase):
    """PX4 MAVLink asset-adapter plugin."""

    PLUGIN_NAME = "px4_adapter"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "asset_adapter"

    def __init__(self):
        super().__init__()
        self.bridge = None
        self._sync_thread = None
        self._running = False

    def on_activate(self, event_bus) -> None:
        self.subscribe("asset.command", self._on_command)
        self.subscribe("asset.register_vehicle", self._on_register)
        self.emit("asset.registered", {
            "plugin": self.PLUGIN_NAME,
            "protocol": "mavlink",
            "domains": ["air", "ground"],
        })
        try:
            from integrations.px4_bridge import PX4Bridge
            conn = self.manifest.get("config", {}).get(
                "connection_string", "udp:127.0.0.1:14540"
            )
            self.bridge = PX4Bridge(conn)
            ok = self.bridge.connect()
            if ok:
                self._start_sync()
        except ImportError:
            pass

    def on_shutdown(self) -> None:
        self._running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=3)

    def get_capabilities(self) -> list[str]:
        return ["mavlink", "telemetry", "waypoint", "arm", "mode", "health"]

    # ── Event handlers ─────────────────────────────────────────

    def _on_command(self, event):
        """Handle asset.command events — forward to PX4."""
        if not self.bridge or not self.bridge.connected:
            return
        p = event.payload or {}
        aid = p.get("asset_id", "")
        cmd = p.get("command", "").upper()

        if cmd == "WAYPOINT":
            self.bridge.send_waypoint(
                aid, p.get("lat", 0), p.get("lng", 0),
                p.get("alt_m", 50), p.get("speed_ms", 15),
            )
        elif cmd == "ARM":
            self.bridge.arm(aid)
        elif cmd in ("RTL", "LAND", "HOLD", "OFFBOARD", "AUTO"):
            self.bridge.set_mode(aid, cmd)

    def _on_register(self, event):
        """Handle vehicle registration events."""
        if not self.bridge:
            return
        p = event.payload or {}
        aid = p.get("asset_id", "")
        sysid = p.get("system_id", 1)
        if aid:
            self.bridge.register_vehicle(aid, system_id=sysid)

    # ── Telemetry sync loop ──────────────────────────────────

    def _start_sync(self):
        self._running = True
        self._sync_thread = threading.Thread(
            target=self._sync_loop, daemon=True,
        )
        self._sync_thread.start()

    def _sync_loop(self):
        while self._running:
            if self.bridge and self.bridge.connected:
                for aid, telem in self.bridge.telemetry_cache.items():
                    if "lat" in telem:
                        self.emit("asset.position_updated", {
                            "asset_id": aid,
                            "lat": telem["lat"],
                            "lng": telem.get("lng"),
                            "alt_m": telem.get("alt_m"),
                            "heading_deg": telem.get("heading_deg"),
                            "battery_pct": telem.get("battery_pct"),
                            "armed": telem.get("armed", False),
                            "source": "px4",
                        })
            time.sleep(1.0)

    def health_check(self) -> dict:
        base = super().health_check()
        base["px4_connected"] = bool(self.bridge and self.bridge.connected)
        base["vehicles"] = list(self.bridge.vehicles.keys()) if self.bridge else []
        base["syncing"] = self._running
        return base
