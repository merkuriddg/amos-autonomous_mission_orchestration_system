"""
MOS Swarm Orchestrator
Manages multi-asset coordination behaviors:
  - Formation control
  - Area search patterns
  - Overwatch positioning
  - Dynamic reallocation on asset loss

Maps to MVRX-C3 swarm coordination engine from the Mavrix1 RP.
"""

import rclpy
from rclpy.node import Node
from mos_interfaces.msg import AssetState, TaskOrder
from std_msgs.msg import String
import json
import math


class SwarmBehavior:
    """Base class for swarm behaviors."""

    def __init__(self, name: str):
        self.name = name
        self.active_assets: list[str] = []

    def compute_waypoints(
        self, assets: dict[str, AssetState], params: dict
    ) -> dict[str, tuple[float, float, float]]:
        """Return asset_id -> (lat, lon, alt) waypoints."""
        raise NotImplementedError


class LineFormation(SwarmBehavior):
    """Assets arranged in a line perpendicular to direction of travel."""

    def __init__(self):
        super().__init__("LINE_FORMATION")

    def compute_waypoints(self, assets, params):
        center_lat = params.get("center_lat", 0.0)
        center_lon = params.get("center_lon", 0.0)
        heading = params.get("heading_deg", 0.0)
        spacing_m = params.get("spacing_m", 50.0)
        alt = params.get("altitude_m", 100.0)

        waypoints = {}
        asset_list = list(assets.keys())
        n = len(asset_list)

        for i, asset_id in enumerate(asset_list):
            offset = (i - n / 2) * spacing_m
            # Simplified offset calc (production would use proper geodesic math)
            perp_heading = math.radians(heading + 90)
            dlat = offset * math.cos(perp_heading) / 111320.0
            dlon = offset * math.sin(perp_heading) / (
                111320.0 * math.cos(math.radians(center_lat))
            )
            waypoints[asset_id] = (
                center_lat + dlat,
                center_lon + dlon,
                alt,
            )

        return waypoints


class AreaSearch(SwarmBehavior):
    """Divide an area into sectors and assign one per asset."""

    def __init__(self):
        super().__init__("AREA_SEARCH")

    def compute_waypoints(self, assets, params):
        # Simplified: divide bounding box into equal sectors
        min_lat = params.get("min_lat", 0.0)
        max_lat = params.get("max_lat", 0.001)
        min_lon = params.get("min_lon", 0.0)
        max_lon = params.get("max_lon", 0.001)
        alt = params.get("altitude_m", 100.0)

        waypoints = {}
        asset_list = list(assets.keys())
        n = len(asset_list)

        if n == 0:
            return waypoints

        # Simple grid subdivision
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        dlat = (max_lat - min_lat) / rows
        dlon = (max_lon - min_lon) / cols

        for i, asset_id in enumerate(asset_list):
            row = i // cols
            col = i % cols
            waypoints[asset_id] = (
                min_lat + dlat * (row + 0.5),
                min_lon + dlon * (col + 0.5),
                alt,
            )

        return waypoints


class SwarmOrchestrator(Node):
    """
    Coordinates multi-asset swarm behaviors for the Mavrix1 RP.
    """

    BEHAVIORS = {
        "LINE_FORMATION": LineFormation(),
        "AREA_SEARCH": AreaSearch(),
    }

    def __init__(self):
        super().__init__("mos_swarm_orchestrator")
        self.get_logger().info("=== MOS Swarm Orchestrator Initializing ===")

        self._asset_states: dict[str, AssetState] = {}

        # Listen for asset states
        self.create_subscription(
            AssetState, "/mos/cop/assets", self._on_asset_state, 10
        )

        # Listen for swarm commands
        self.create_subscription(
            String, "/mos/swarm/command", self._on_swarm_command, 10
        )

        # Publish individual waypoint commands
        self._wp_pub = self.create_publisher(
            String, "/mos/swarm/waypoints", 10
        )

        self.get_logger().info("Swarm Orchestrator online.")

    def _on_asset_state(self, msg: AssetState):
        self._asset_states[msg.asset_id] = msg

    def _on_swarm_command(self, msg: String):
        """
        Expected JSON:
        {
            "behavior": "LINE_FORMATION" | "AREA_SEARCH",
            "asset_ids": ["id1", "id2", ...],  // empty = all assets
            "params": { ... behavior-specific parameters ... }
        }
        """
        try:
            cmd = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().error("Invalid swarm command JSON")
            return

        behavior_name = cmd.get("behavior", "")
        behavior = self.BEHAVIORS.get(behavior_name)
        if not behavior:
            self.get_logger().error(f"Unknown behavior: {behavior_name}")
            return

        # Filter assets
        asset_ids = cmd.get("asset_ids", [])
        if not asset_ids:
            target_assets = dict(self._asset_states)
        else:
            target_assets = {
                k: v for k, v in self._asset_states.items() if k in asset_ids
            }

        # Compute waypoints
        waypoints = behavior.compute_waypoints(target_assets, cmd.get("params", {}))

        self.get_logger().info(
            f"[SWARM] Executing {behavior_name} with {len(waypoints)} assets"
        )

        # Publish waypoints
        wp_msg = String()
        wp_msg.data = json.dumps({
            "behavior": behavior_name,
            "waypoints": {
                k: {"lat": v[0], "lon": v[1], "alt": v[2]}
                for k, v in waypoints.items()
            },
        })
        self._wp_pub.publish(wp_msg)


def main(args=None):
    rclpy.init(args=args)
    node = SwarmOrchestrator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
