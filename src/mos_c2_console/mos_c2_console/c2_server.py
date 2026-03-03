#!/usr/bin/env python3
"""
MOS C2 Server — Flask REST + ROS 2 bridge
Uses REST polling for browser, direct ROS pub/sub for comms.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from flask import Flask, render_template, request, jsonify
import threading
import json
import time
import os

# ── Flask App ─────────────────────────────────────────────────────
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=template_dir)

# Shared state
asset_data = {}
threat_data = {}
data_lock = threading.Lock()


# ── ROS 2 Node ───────────────────────────────────────────────────
class C2Bridge(Node):
    def __init__(self):
        super().__init__('mos_c2_bridge')

        # Subscribers
        self.create_subscription(String, '/mos/heartbeat', self._on_heartbeat, 10)
        self.create_subscription(String, '/mos/threats/alerts', self._on_threat, 10)

        # Publishers
        self.mission_pub = self.create_publisher(String, '/mos/mission_command', 10)
        self.swarm_pub = self.create_publisher(String, '/mos/swarm_command', 10)
        self.autonomy_pub = self.create_publisher(String, '/mos/autonomy_command', 10)

        self.get_logger().info('[MOS C2] Bridge node started')

    def _on_heartbeat(self, msg):
        try:
            d = json.loads(msg.data)
            aid = d.get('asset_id', '')
            if aid:
                with data_lock:
                    asset_data[aid] = d
        except Exception:
            pass

    def _on_threat(self, msg):
        try:
            d = json.loads(msg.data)
            tid = d.get('contact_id', d.get('id', ''))
            if tid:
                with data_lock:
                    threat_data[tid] = d
                    threat_data[tid]['_time'] = time.time()
        except Exception:
            pass

    def publish_mission(self, data):
        msg = String()
        msg.data = json.dumps(data)
        self.mission_pub.publish(msg)
        self.get_logger().info(f'[MOS C2] Mission published: {data.get("mission_id")} {data.get("mission_type")}')

    def publish_swarm(self, data):
        msg = String()
        msg.data = json.dumps(data)
        self.swarm_pub.publish(msg)
        self.get_logger().info(f'[MOS C2] Swarm command: {data.get("behavior")}')

    def publish_autonomy(self, data):
        msg = String()
        msg.data = json.dumps(data)
        self.autonomy_pub.publish(msg)
        self.get_logger().info(f'[MOS C2] Autonomy set: {data.get("target_level")}')


# Global reference
ros_node = None


# ── Flask Routes ─────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/assets')
def get_assets():
    with data_lock:
        return jsonify(list(asset_data.values()))


@app.route('/api/threats')
def get_threats():
    now = time.time()
    with data_lock:
        # Only return threats from last 30 seconds
        active = [t for t in threat_data.values() if now - t.get('_time', 0) < 30]
        return jsonify(active)


@app.route('/api/send_mission', methods=['POST'])
def send_mission():
    data = request.get_json()
    if ros_node:
        try:
            ros_node.publish_mission(data)
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"status": "error", "msg": str(e)}), 500
    return jsonify({"status": "error", "msg": "ROS not ready"}), 503


@app.route('/api/send_swarm', methods=['POST'])
def send_swarm():
    data = request.get_json()
    if ros_node:
        try:
            ros_node.publish_swarm(data)
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"status": "error", "msg": str(e)}), 500
    return jsonify({"status": "error", "msg": "ROS not ready"}), 503


@app.route('/api/set_autonomy', methods=['POST'])
def set_autonomy():
    data = request.get_json()
    if ros_node:
        try:
            ros_node.publish_autonomy(data)
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"status": "error", "msg": str(e)}), 500
    return jsonify({"status": "error", "msg": "ROS not ready"}), 503


# ── ROS Spin Thread ──────────────────────────────────────────────
def ros_thread():
    global ros_node
    rclpy.init()
    ros_node = C2Bridge()
    try:
        rclpy.spin(ros_node)
    except Exception:
        pass
    finally:
        try:
            ros_node.destroy_node()
            rclpy.shutdown()
        except Exception:
            pass


# ── Main ─────────────────────────────────────────────────────────
def main():
    # Start ROS in background thread
    t = threading.Thread(target=ros_thread, daemon=True)
    t.start()

    # Wait for ROS node to be ready
    time.sleep(1.0)

    # Start Flask (no SocketIO needed)
    print('[MOS C2] Starting C2 Console on http://0.0.0.0:5000')
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
