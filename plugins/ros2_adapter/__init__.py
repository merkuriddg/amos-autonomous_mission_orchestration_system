"""AMOS Plugin — ROS 2 Adapter.

Bridges AMOS ↔ ROS 2 middleware.  Publishes asset and threat state to
ROS 2 topics and ingests telemetry from external robotic nodes back
into the AMOS event bus.
See ``integrations/ros2_integration.py`` for the full bridge.
"""

import threading
import time

from core.plugin_base import PluginBase


class ROS2AdapterPlugin(PluginBase):
    """ROS 2 transport plugin."""

    PLUGIN_NAME = "ros2_adapter"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "transport"

    def __init__(self):
        super().__init__()
        self.bridge = None
        self._sync_thread = None
        self._running = False

    def on_activate(self, event_bus) -> None:
        self.subscribe("asset.position_updated", self._on_asset_update)
        self.subscribe("threat.detected", self._on_threat_update)
        self.subscribe("mission.command", self._on_command)
        self.emit("transport.registered", {
            "plugin": self.PLUGIN_NAME,
            "protocol": "ros2",
            "topics": ["/amos/assets", "/amos/threats", "/amos/commands"],
        })
        try:
            from integrations.ros2_integration import ROS2Integration
            self.bridge = ROS2Integration()
            ok = self.bridge.init()
            if ok:
                self._start_ingest()
        except ImportError:
            pass

    def on_shutdown(self) -> None:
        self._running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=3)
        if self.bridge:
            self.bridge.shutdown()

    def get_capabilities(self) -> list[str]:
        return ["ros2_publish", "ros2_subscribe", "telemetry_ingest", "health"]

    # ── Outbound: AMOS → ROS 2 ──────────────────────────────

    def _on_asset_update(self, event):
        """Forward asset positions to ROS 2."""
        if self.bridge and self.bridge.available and event.payload:
            self.bridge.publish_command({
                "type": "asset_update",
                "data": event.payload,
            })

    def _on_threat_update(self, event):
        """Forward threat detections to ROS 2."""
        if self.bridge and self.bridge.available and event.payload:
            self.bridge.publish_command({
                "type": "threat_update",
                "data": event.payload,
            })

    def _on_command(self, event):
        """Forward mission commands to ROS 2."""
        if self.bridge and self.bridge.available and event.payload:
            self.bridge.publish_command(event.payload)

    # ── Inbound: ROS 2 → AMOS ──────────────────────────────

    def _start_ingest(self):
        self._running = True
        self._sync_thread = threading.Thread(
            target=self._ingest_loop, daemon=True,
        )
        self._sync_thread.start()

    def _ingest_loop(self):
        """Poll ROS 2 incoming telemetry and emit to AMOS bus."""
        while self._running:
            if self.bridge and self.bridge.available:
                for aid, telem in list(self.bridge.incoming_telemetry.items()):
                    self.emit("asset.position_updated", {
                        "asset_id": aid,
                        "lat": telem.get("lat"),
                        "lng": telem.get("lng"),
                        "battery_pct": telem.get("battery"),
                        "source": "ros2",
                    })
            time.sleep(1.0)

    def health_check(self) -> dict:
        base = super().health_check()
        base["ros2_available"] = bool(self.bridge and self.bridge.available)
        base["node"] = self.bridge.node_name if self.bridge else None
        base["syncing"] = self._running
        return base
