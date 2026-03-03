"""
MOS Asset Registry
Tracks all robotic assets in the Mavrix1 Robotic Platoon.
Maintains state, health, and availability for task allocation.
"""

import rclpy
from rclpy.node import Node
from mos_interfaces.msg import AssetState
from collections import OrderedDict
import json
import time


class AssetRegistry(Node):
    """
    Central registry for all MVRX assets (AIR, GROUND, MARITIME).
    Subscribes to heartbeats from every asset, maintains a live roster,
    and publishes the Common Operating Picture (COP).
    """

    AUTONOMY_MODES = {
        0: "MANUAL",
        1: "ASSISTED",
        2: "COLLABORATIVE",
        3: "SWARM",
        4: "COGNITIVE",
    }

    STATUS_MAP = {
        0: "IDLE",
        1: "TASKED",
        2: "EXECUTING",
        3: "RTB",
        4: "FAULT",
    }

    # Asset considered stale after this many seconds without heartbeat
    HEARTBEAT_TIMEOUT_SEC = 10.0

    def __init__(self):
        super().__init__("mos_asset_registry")
        self.get_logger().info("=== MOS Asset Registry Initializing ===")

        # Dict of asset_id -> latest AssetState
        self._roster: OrderedDict[str, AssetState] = OrderedDict()
        self._last_seen: dict[str, float] = {}

        # Subscribe to all asset heartbeats on a common topic
        self.create_subscription(
            AssetState,
            "/mos/asset_heartbeat",
            self._on_heartbeat,
            qos_profile=10,
        )

        # Publish consolidated COP at 2 Hz
        self._cop_pub = self.create_publisher(AssetState, "/mos/cop/assets", 10)
        self.create_timer(0.5, self._publish_cop)

        # Health audit at 1 Hz
        self.create_timer(1.0, self._audit_health)

        self.get_logger().info(
            f"MOS Asset Registry online. Listening on /mos/asset_heartbeat"
        )

    def _on_heartbeat(self, msg: AssetState):
        asset_id = msg.asset_id
        self._roster[asset_id] = msg
        self._last_seen[asset_id] = time.time()

        if asset_id not in self._roster:
            self.get_logger().info(
                f"[REGISTRY] New asset registered: {msg.callsign} "
                f"({msg.asset_type}) [{asset_id}]"
            )

    def _publish_cop(self):
        """Republish all known asset states for COP consumers."""
        for asset_id, state in self._roster.items():
            self._cop_pub.publish(state)

    def _audit_health(self):
        """Flag assets that have gone silent."""
        now = time.time()
        stale = []
        for asset_id, last in self._last_seen.items():
            if now - last > self.HEARTBEAT_TIMEOUT_SEC:
                stale.append(asset_id)
                state = self._roster.get(asset_id)
                if state and state.mission_status != 4:
                    self.get_logger().warn(
                        f"[REGISTRY] Asset {asset_id} heartbeat STALE "
                        f"({now - last:.1f}s)"
                    )

    def get_available_assets(self, asset_type: str = None) -> list[AssetState]:
        """Return assets that are IDLE or TASKED and not in FAULT."""
        results = []
        for state in self._roster.values():
            if state.mission_status in (0, 1) and state.battery_pct > 15.0:
                if asset_type is None or state.asset_type == asset_type:
                    results.append(state)
        return results

    def get_platoon_strength(self) -> dict:
        """Return count of assets by type and status."""
        strength = {"AIR": 0, "GROUND": 0, "MARITIME": 0, "TOTAL": 0, "FAULT": 0}
        for state in self._roster.values():
            strength["TOTAL"] += 1
            if state.asset_type in strength:
                strength[state.asset_type] += 1
            if state.mission_status == 4:
                strength["FAULT"] += 1
        return strength


def main(args=None):
    rclpy.init(args=args)
    node = AssetRegistry()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
