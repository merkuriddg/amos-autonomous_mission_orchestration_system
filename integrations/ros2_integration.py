"""AMOS ↔ ROS 2 Humble Full Integration

Complete ROS 2 pub/sub integration for AMOS.
Requires: rclpy, std_msgs, geometry_msgs, sensor_msgs, nav_msgs
Only runs on Ubuntu with ROS 2 Humble installed.

Topics published:
  /amos/assets        - AssetArray (custom)
  /amos/threats       - ThreatArray (custom)
  /amos/commands      - String (JSON commands)

Topics subscribed:
  /amos/telemetry     - sensor_msgs/NavSatFix per asset
  /amos/battery       - sensor_msgs/BatteryState per asset
  /amos/status        - std_msgs/String (JSON status)
"""

import json, time, logging, threading
from datetime import datetime, timezone

log = logging.getLogger("amos.ros2")


class ROS2Integration:
    """Full ROS 2 pub/sub bridge for AMOS."""

    def __init__(self, node_name="amos_bridge"):
        self.node_name = node_name
        self.node = None
        self.available = False
        self.publishers = {}
        self.subscribers = {}
        self.incoming_telemetry = {}
        self._lock = threading.Lock()

    def init(self):
        """Initialize ROS 2 node. Call once at startup."""
        try:
            import rclpy
            from rclpy.node import Node
            rclpy.init()
            self.node = rclpy.create_node(self.node_name)
            self._setup_publishers()
            self._setup_subscribers()
            self.available = True
            threading.Thread(target=self._spin, daemon=True).start()
            log.info("ROS 2 node initialized")
            return True
        except ImportError:
            log.info("ROS 2 not available — standalone mode")
            return False

    def _setup_publishers(self):
        from std_msgs.msg import String
        self.publishers["assets"] = self.node.create_publisher(String, "/amos/assets", 10)
        self.publishers["threats"] = self.node.create_publisher(String, "/amos/threats", 10)
        self.publishers["commands"] = self.node.create_publisher(String, "/amos/commands", 10)
        self.publishers["events"] = self.node.create_publisher(String, "/amos/events", 10)

    def _setup_subscribers(self):
        from std_msgs.msg import String
        self.subscribers["telemetry"] = self.node.create_subscription(
            String, "/amos/telemetry", self._on_telemetry, 10)
        self.subscribers["status"] = self.node.create_subscription(
            String, "/amos/status", self._on_status, 10)

    def publish_assets(self, sim_assets):
        """Publish current asset state to ROS 2."""
        if not self.available:
            return
        from std_msgs.msg import String
        msg = String()
        msg.data = json.dumps({aid: {
            "lat": a["position"]["lat"], "lng": a["position"]["lng"],
            "alt_ft": a["position"].get("alt_ft", 0),
            "heading": a.get("heading_deg", 0),
            "battery": a["health"]["battery_pct"],
            "status": a["status"], "domain": a["domain"],
        } for aid, a in sim_assets.items()})
        self.publishers["assets"].publish(msg)

    def publish_threats(self, sim_threats):
        if not self.available:
            return
        from std_msgs.msg import String
        msg = String()
        msg.data = json.dumps(sim_threats)
        self.publishers["threats"].publish(msg)

    def publish_command(self, command_dict):
        if not self.available:
            return
        from std_msgs.msg import String
        msg = String()
        msg.data = json.dumps(command_dict)
        self.publishers["commands"].publish(msg)

    def _on_telemetry(self, msg):
        try:
            data = json.loads(msg.data)
            aid = data.get("asset_id")
            if aid:
                with self._lock:
                    self.incoming_telemetry[aid] = data
        except json.JSONDecodeError:
            pass

    def _on_status(self, msg):
        log.debug(f"ROS2 status: {msg.data}")

    def sync_to_amos(self, sim_assets):
        with self._lock:
            for aid, telem in self.incoming_telemetry.items():
                if aid in sim_assets:
                    a = sim_assets[aid]
                    if "lat" in telem:
                        a["position"]["lat"] = telem["lat"]
                        a["position"]["lng"] = telem["lng"]
                    if "battery" in telem:
                        a["health"]["battery_pct"] = telem["battery"]

    def _spin(self):
        import rclpy
        while rclpy.ok():
            rclpy.spin_once(self.node, timeout_sec=0.1)

    def get_status(self):
        return {"available": self.available, "node": self.node_name,
                "publishers": list(self.publishers.keys()),
                "subscribers": list(self.subscribers.keys()),
                "incoming_assets": len(self.incoming_telemetry)}

    def shutdown(self):
        if self.node:
            self.node.destroy_node()
        try:
            import rclpy
            rclpy.shutdown()
        except Exception:
            pass
