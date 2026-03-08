"""AMOS ↔ ROS 2 Navigation2 Bridge

Integrates AMOS ground assets with the Nav2 autonomous navigation stack.
Requires: ROS 2 Humble + Nav2 (nav2_msgs, geometry_msgs, action_msgs)

Provides:
  - Send NavigateToPose goals for waypoint navigation
  - Monitor navigation status and feedback
  - Costmap-aware path planning integration
"""

import json, time, logging, threading
from datetime import datetime, timezone

log = logging.getLogger("amos.nav2")


class Nav2Bridge:
    """Bridge to ROS 2 Navigation2 for ground UGVs."""

    def __init__(self):
        self.node = None
        self.available = False
        self.nav_clients = {}  # amos_id -> action_client
        self.nav_status = {}   # amos_id -> {status, goal_lat, goal_lng, ...}
        self._lock = threading.Lock()

    def init(self, ros2_node=None):
        """Initialize with an existing ROS 2 node."""
        try:
            import rclpy
            from nav2_msgs.action import NavigateToPose
            self.node = ros2_node
            if not self.node:
                rclpy.init()
                self.node = rclpy.create_node("amos_nav2_bridge")
            self.available = True
            log.info("Nav2 bridge initialized")
            return True
        except ImportError:
            log.info("Nav2 not available — ground nav disabled")
            return False

    def send_goal(self, amos_id, lat, lng, heading_deg=0):
        """Send a NavigateToPose goal to Nav2."""
        if not self.available:
            return False
        try:
            from nav2_msgs.action import NavigateToPose
            from geometry_msgs.msg import PoseStamped
            from rclpy.action import ActionClient

            namespace = f"/{amos_id}"
            if amos_id not in self.nav_clients:
                self.nav_clients[amos_id] = ActionClient(
                    self.node, NavigateToPose, f"{namespace}/navigate_to_pose")

            client = self.nav_clients[amos_id]
            if not client.wait_for_server(timeout_sec=2.0):
                log.warning(f"Nav2 server not ready for {amos_id}")
                return False

            goal = NavigateToPose.Goal()
            goal.pose.header.frame_id = "map"
            goal.pose.header.stamp = self.node.get_clock().now().to_msg()
            # Convert lat/lng to local frame (requires transform, simplified here)
            goal.pose.pose.position.x = (lng + 82.521) * 111320
            goal.pose.pose.position.y = (lat - 27.849) * 110540
            import math
            goal.pose.pose.orientation.z = math.sin(math.radians(heading_deg) / 2)
            goal.pose.pose.orientation.w = math.cos(math.radians(heading_deg) / 2)

            future = client.send_goal_async(goal)
            with self._lock:
                self.nav_status[amos_id] = {
                    "status": "NAVIGATING", "goal_lat": lat, "goal_lng": lng,
                    "started": time.time(),
                }
            log.info(f"Nav2 goal sent: {amos_id} -> {lat},{lng}")
            return True
        except Exception as e:
            log.error(f"Nav2 goal failed: {e}")
            return False

    def cancel_goal(self, amos_id):
        if amos_id in self.nav_clients:
            try:
                self.nav_clients[amos_id].cancel_all_goals()
                with self._lock:
                    self.nav_status[amos_id] = {"status": "CANCELLED"}
                return True
            except Exception:
                pass
        return False

    def get_nav_status(self, amos_id=None):
        if amos_id:
            return self.nav_status.get(amos_id, {"status": "IDLE"})
        return dict(self.nav_status)

    def get_status(self):
        return {"available": self.available,
                "active_goals": sum(1 for s in self.nav_status.values()
                                    if s.get("status") == "NAVIGATING"),
                "vehicles": list(self.nav_clients.keys())}
