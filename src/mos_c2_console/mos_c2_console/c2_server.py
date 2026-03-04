#!/usr/bin/env python3
"""
MOS C2 Server — Flask REST + ROS 2 bridge
Phase 4: Waypoints, Formations, Asset Detail Panel
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from flask import Flask, render_template, request, jsonify
import threading
import json
import time
import os

# ── Shared state ──────────────────────────────────────────────
asset_data = {}
threat_data = {}
log_entries = []
autonomy_state = {'current_level': 1, 'level_name': 'ASSISTED'}
data_lock = threading.Lock()


# ── Find template directory robustly ─────────────────────────
def find_template_dir():
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'),
        os.path.expanduser('~/mos_ws/src/mos_c2_console/mos_c2_console/templates'),
    ]
    ament_path = os.environ.get('AMENT_PREFIX_PATH', '')
    for prefix in ament_path.split(':'):
        if prefix:
            candidates.append(
                os.path.join(prefix, 'share', 'mos_c2_console', 'templates'))

    for c in candidates:
        if os.path.exists(c) and os.path.isfile(os.path.join(c, 'index.html')):
            return c

    # Fallback — source tree
    return os.path.expanduser(
        '~/mos_ws/src/mos_c2_console/mos_c2_console/templates')


template_dir = find_template_dir()
app = Flask(__name__, template_folder=template_dir)


# ── Helper ────────────────────────────────────────────────────
def add_log(text):
    with data_lock:
        entry = {'time': time.strftime('%H:%M:%S'), 'text': text}
        log_entries.append(entry)
        if len(log_entries) > 100:
            del log_entries[:-100]


# ── ROS 2 Node ───────────────────────────────────────────────
class C2Bridge(Node):
    def __init__(self):
        super().__init__('mos_c2_bridge')

        # Subscribers
        self.create_subscription(
            String, '/mos/heartbeat', self._on_heartbeat, 10)
        self.create_subscription(
            String, '/mos/threats/alerts', self._on_threat, 10)
        self.create_subscription(
            String, '/mos/mission/status', self._on_mission_status, 10)
        self.create_subscription(
            String, '/mos/autonomy/state', self._on_autonomy_state, 10)

        # Publishers
        self.mission_pub = self.create_publisher(
            String, '/mos/mission_command', 10)
        self.swarm_pub = self.create_publisher(
            String, '/mos/swarm_command', 10)
        self.autonomy_pub = self.create_publisher(
            String, '/mos/autonomy_command', 10)
        self.waypoint_pub = self.create_publisher(
            String, '/mos/waypoints/assign', 10)

        self.get_logger().info(
            f'[MOS C2] Bridge node started — Phase 4')
        self.get_logger().info(
            f'[MOS C2] Templates: {template_dir}')

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
                    d['_time'] = time.time()
                    threat_data[tid] = d
                add_log(
                    f"THREAT: {tid} — "
                    f"{d.get('threat_type', '?')} [{d.get('threat_level', '?')}]")
        except Exception:
            pass

    def _on_mission_status(self, msg):
        try:
            d = json.loads(msg.data)
            add_log(
                f"MISSION: {d.get('mission_id', '?')} — "
                f"{d.get('status', '?')} ({d.get('task_count', 0)} tasks)")
        except Exception:
            pass

    def _on_autonomy_state(self, msg):
        global autonomy_state
        try:
            with data_lock:
                autonomy_state = json.loads(msg.data)
        except Exception:
            pass

    def publish_mission(self, data):
        msg = String()
        msg.data = json.dumps(data)
        self.mission_pub.publish(msg)
        add_log(f"CMD: Mission {data.get('mission_type', '?')} ordered")
        self.get_logger().info(
            f'[MOS C2] Mission: {data.get("mission_id")} '
            f'{data.get("mission_type")}')

    def publish_swarm(self, data):
        msg = String()
        msg.data = json.dumps(data)
        self.swarm_pub.publish(msg)
        add_log(f"CMD: Swarm {data.get('behavior', '?')}")
        self.get_logger().info(
            f'[MOS C2] Swarm: {data.get("behavior")}')

    def publish_autonomy(self, data):
        msg = String()
        msg.data = json.dumps(data)
        self.autonomy_pub.publish(msg)
        add_log(f"CMD: Autonomy → Level {data.get('target_level', '?')}")
        self.get_logger().info(
            f'[MOS C2] Autonomy: {data.get("target_level")}')

    def publish_waypoints(self, data):
        msg = String()
        msg.data = json.dumps(data)
        self.waypoint_pub.publish(msg)
        aid = data.get('asset_id', '?')
        cancel = data.get('cancel', False)
        wpc = len(data.get('waypoints', []))
        if cancel:
            add_log(f"CMD: HOLD → {aid}")
        else:
            add_log(f"CMD: {wpc} waypoints → {aid}")
        self.get_logger().info(
            f'[MOS C2] Waypoints: {aid} ← {wpc} pts (cancel={cancel})')


# Global reference
ros_node = None


# ── Flask Routes ─────────────────────────────────────────────
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
        active = [t for t in threat_data.values()
                  if now - t.get('_time', 0) < 30]
        return jsonify(active)


@app.route('/api/logs')
def get_logs():
    with data_lock:
        return jsonify(list(log_entries))


@app.route('/api/autonomy')
def get_autonomy():
    with data_lock:
        return jsonify(autonomy_state)


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


@app.route('/api/send_waypoints', methods=['POST'])
def send_waypoints():
    data = request.get_json()
    if ros_node:
        try:
            ros_node.publish_waypoints(data)
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"status": "error", "msg": str(e)}), 500
    return jsonify({"status": "error", "msg": "ROS not ready"}), 503


# ── ROS Spin Thread ──
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


# ── Main ─────────────────────────────────────────────────────
def main():
    t = threading.Thread(target=ros_thread, daemon=True)
    t.start()
    time.sleep(1.0)

    print(f'[MOS C2] Templates: {template_dir}')
    print('[MOS C2] Starting C2 Console on http://0.0.0.0:5000')
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()

