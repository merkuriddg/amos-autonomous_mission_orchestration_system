"""ROS 2 Bridge — graceful fallback when ROS2 unavailable"""
import time, json

class ROS2Bridge:
    def __init__(self):
        self.available = False
        self.node = None
        self.publishers = {}
        self.last_publish = 0
        self.stats = {"published": 0, "received": 0, "errors": 0}
        try:
            import rclpy
            from std_msgs.msg import String
            rclpy.init()
            self.node = rclpy.create_node("mos_bridge")
            self.String = String
            self.available = True
            print("[ROS2] Connected")
        except Exception:
            print("[ROS2] Not available — standalone mode")

    def publish_assets(self, assets):
        if not self.available:
            return
        try:
            for aid, a in assets.items():
                topic = f"/mos/assets/{aid}/state"
                if topic not in self.publishers:
                    self.publishers[topic] = self.node.create_publisher(self.String, topic, 10)
                msg = self.String()
                msg.data = json.dumps({"id": aid, "position": a.get("position"),
                                        "status": a.get("status"), "ts": time.time()})
                self.publishers[topic].publish(msg)
                self.stats["published"] += 1
            self.last_publish = time.time()
        except Exception:
            self.stats["errors"] += 1

    def get_status(self):
        return {"available": self.available,
                "node": "mos_bridge" if self.available else None,
                "topics": len(self.publishers),
                "last_publish": self.last_publish,
                "stats": dict(self.stats),
                "mode": "ROS 2" if self.available else "Standalone"}
