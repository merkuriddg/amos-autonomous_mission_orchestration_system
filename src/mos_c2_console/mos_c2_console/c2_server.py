#!/usr/bin/env python3
"""
MOS C2 Server — Phase 4b
Flask REST + ROS 2 bridge
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from flask import Flask, render_template, request, jsonify
import threading, json, time, os

asset_data = {}
threat_data = {}
log_entries = []
autonomy_state = {'current_level': 1, 'level_name': 'ASSISTED'}
data_lock = threading.Lock()


def find_template_dir():
    # Always prefer source tree — never stale
    src = os.path.expanduser(
        '~/mos_ws/src/mos_c2_console/mos_c2_console/templates')
    if os.path.isdir(src):
        return src
    # Fallback to installed package location
    pkg = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'templates')
    if os.path.isdir(pkg):
        return pkg
    return src


template_dir = find_template_dir()
app = Flask(__name__, template_folder=template_dir)


def add_log(text):
    with data_lock:
        log_entries.append({'time': time.strftime('%H:%M:%S'), 'text': text})
        if len(log_entries) > 100:
            del log_entries[:-100]


class C2Bridge(Node):
    def __init__(self):
        super().__init__('mos_c2_bridge')
        self.create_subscription(String, '/mos/heartbeat', self._hb, 10)
        self.create_subscription(String, '/mos/threats/alerts', self._threat, 10)
        self.create_subscription(String, '/mos/mission/status', self._mstat, 10)
        self.create_subscription(String, '/mos/autonomy/state', self._astat, 10)

        self.mission_pub = self.create_publisher(String, '/mos/mission_command', 10)
        self.swarm_pub = self.create_publisher(String, '/mos/swarm_command', 10)
        self.autonomy_pub = self.create_publisher(String, '/mos/autonomy_command', 10)
        self.waypoint_pub = self.create_publisher(String, '/mos/waypoints/assign', 10)

        self.get_logger().info(f'[MOS C2] Bridge online — Phase 4b | Templates: {template_dir}')

    def _hb(self, msg):
        try:
            d = json.loads(msg.data)
            aid = d.get('asset_id', '')
            if aid:
                with data_lock:
                    asset_data[aid] = d
        except Exception:
            pass

    def _threat(self, msg):
        try:
            d = json.loads(msg.data)
            tid = d.get('contact_id', d.get('id', ''))
            if tid:
                with data_lock:
                    d['_time'] = time.time()
                    threat_data[tid] = d
                add_log(f"THREAT: {tid} — {d.get('threat_type','?')} [{d.get('threat_level','?')}]")
        except Exception:
            pass

    def _mstat(self, msg):
        try:
            d = json.loads(msg.data)
            add_log(f"MISSION: {d.get('mission_id','?')} — {d.get('status','?')} ({d.get('task_count',0)} assets)")
        except Exception:
            pass

    def _astat(self, msg):
        global autonomy_state
        try:
            with data_lock:
                autonomy_state = json.loads(msg.data)
        except Exception:
            pass

    def pub_mission(self, data):
        m = String(); m.data = json.dumps(data); self.mission_pub.publish(m)
        add_log(f"CMD: Mission {data.get('mission_type','?')} ordered")

    def pub_swarm(self, data):
        m = String(); m.data = json.dumps(data); self.swarm_pub.publish(m)
        add_log(f"CMD: Swarm {data.get('behavior','?')}")

    def pub_autonomy(self, data):
        m = String(); m.data = json.dumps(data); self.autonomy_pub.publish(m)
        add_log(f"CMD: Autonomy -> Level {data.get('target_level','?')}")

    def pub_waypoints(self, data):
        m = String(); m.data = json.dumps(data); self.waypoint_pub.publish(m)
        cancel = data.get('cancel', False)
        aid = data.get('asset_id', '?')
        wpc = len(data.get('waypoints', []))
        add_log(f"CMD: {'HOLD' if cancel else f'{wpc} waypoints'} -> {aid}")


ros_node = None


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/assets')
def get_assets():
    with data_lock:
        return jsonify(list(asset_data.values()))

@app.route('/api/threats')
def get_threats():
    now = time.time()
    with data_lock:
        return jsonify([t for t in threat_data.values() if now - t.get('_time', 0) < 30])

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
        try: ros_node.pub_mission(data); return jsonify({"status":"ok"})
        except Exception as e: return jsonify({"status":"error","msg":str(e)}), 500
    return jsonify({"status":"error","msg":"ROS not ready"}), 503

@app.route('/api/send_swarm', methods=['POST'])
def send_swarm():
    data = request.get_json()
    if ros_node:
        try: ros_node.pub_swarm(data); return jsonify({"status":"ok"})
        except Exception as e: return jsonify({"status":"error","msg":str(e)}), 500
    return jsonify({"status":"error","msg":"ROS not ready"}), 503

@app.route('/api/set_autonomy', methods=['POST'])
def set_autonomy():
    data = request.get_json()
    if ros_node:
        try: ros_node.pub_autonomy(data); return jsonify({"status":"ok"})
        except Exception as e: return jsonify({"status":"error","msg":str(e)}), 500
    return jsonify({"status":"error","msg":"ROS not ready"}), 503

@app.route('/api/send_waypoints', methods=['POST'])
def send_waypoints():
    data = request.get_json()
    if ros_node:
        try: ros_node.pub_waypoints(data); return jsonify({"status":"ok"})
        except Exception as e: return jsonify({"status":"error","msg":str(e)}), 500
    return jsonify({"status":"error","msg":"ROS not ready"}), 503


def ros_thread():
    global ros_node
    rclpy.init()
    ros_node = C2Bridge()
    try: rclpy.spin(ros_node)
    except Exception: pass
    finally:
        try: ros_node.destroy_node(); rclpy.shutdown()
        except Exception: pass


def main():
    t = threading.Thread(target=ros_thread, daemon=True); t.start()
    time.sleep(1.0)
    print(f'[MOS C2] Templates: {template_dir}')
    print('[MOS C2] C2 Console: http://0.0.0.0:5000')
    print('[MOS C2] Digital Twin: http://0.0.0.0:5000/dashboard')
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    main()
