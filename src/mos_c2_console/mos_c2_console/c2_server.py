#!/usr/bin/env python3
"""MOS C2 Server — Phase 6: AI COA, Geofencing, TAK, 3D, Echelon"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from flask import Flask, render_template, request, jsonify
import threading, json, time, os, copy

# ── EW/SIGINT/Cyber Simulation Engine ──
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from sim_data_engine import MOSSimEngine
_sim = MOSSimEngine()
_sim.start()

asset_data = {}
threat_data = {}
log_entries = []
autonomy_state = {'current_level': 1, 'level_name': 'ASSISTED'}
sensor_data = []
sustainment_data = []
aar_snapshots = []
coa_data = []
geofence_zones = []
geofence_violations = []
tak_cot_cache = {}
awacs_status = []
awacs_cop = []
hal_status = {}
hal_events = []
data_lock = threading.Lock()

def find_template_dir():
    src = os.path.expanduser('~/mos_ws/src/mos_c2_console/mos_c2_console/templates')
    return src if os.path.isdir(src) else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

template_dir = find_template_dir()
app = Flask(__name__, template_folder=template_dir)

def add_log(text):
    with data_lock:
        log_entries.append({'time': time.strftime('%H:%M:%S'), 'text': text, 'timestamp': time.time()})
        if len(log_entries) > 200: del log_entries[:-200]

class C2Bridge(Node):
    def __init__(self):
        super().__init__('mos_c2_bridge')
        self.create_subscription(String, '/mos/heartbeat', self._hb, 10)
        self.create_subscription(String, '/mos/threats/alerts', self._threat, 10)
        self.create_subscription(String, '/mos/mission/status', self._mstat, 10)
        self.create_subscription(String, '/mos/autonomy/state', self._astat, 10)
        self.create_subscription(String, '/mos/sensor/detections', self._sensor, 10)
        self.create_subscription(String, '/mos/sustainment/status', self._sust, 10)
        self.create_subscription(String, '/mos/sustainment/alerts', self._sust_alert, 10)
        self.create_subscription(String, '/mos/ai/coa', self._coa, 10)
        self.create_subscription(String, '/mos/geofence/zones', self._gfz, 10)
        self.create_subscription(String, '/mos/geofence/violations', self._gfv, 10)
        self.mission_pub = self.create_publisher(String, '/mos/mission_command', 10)
        self.swarm_pub = self.create_publisher(String, '/mos/swarm_command', 10)
        self.autonomy_pub = self.create_publisher(String, '/mos/autonomy_command', 10)
        self.waypoint_pub = self.create_publisher(String, '/mos/waypoints/assign', 10)
        self.gf_add_pub = self.create_publisher(String, '/mos/geofence/add', 10)
        self.gf_del_pub = self.create_publisher(String, '/mos/geofence/delete', 10)
        self.create_subscription(String, '/mos/awacs/status', self._awacs_status, 10)
        self.create_subscription(String, '/mos/awacs/cop', self._awacs_cop, 10)
        self.create_subscription(String, '/mos/hal/status', self._hal_status, 10)
        self.create_subscription(String, '/mos/hal/events', self._hal_event, 10)
        self.hal_cmd_pub = self.create_publisher(String, '/mos/command', 10)
        self.hal_estop_pub = self.create_publisher(String, '/mos/emergency_stop', 10)
        self.get_logger().info(f'[MOS C2] Bridge online Phase 6 | Templates: {template_dir}')

    def _hb(self, msg):
        try:
            d = json.loads(msg.data)
            if d.get('asset_id'):
                with data_lock: asset_data[d['asset_id']] = d
        except: pass
    def _threat(self, msg):
        try:
            d = json.loads(msg.data); tid = d.get('contact_id', d.get('id', ''))
            if tid:
                with data_lock: d['_time'] = time.time(); threat_data[tid] = d
                add_log(f"THREAT: {tid} - {d.get('threat_type','?')} [{d.get('threat_level','?')}]")
        except: pass
    def _mstat(self, msg):
        try:
            d = json.loads(msg.data)
            add_log(f"MISSION: {d.get('mission_id','?')} - {d.get('status','?')}")
        except: pass
    def _astat(self, msg):
        global autonomy_state
        try:
            with data_lock: autonomy_state = json.loads(msg.data)
        except: pass
    def _sensor(self, msg):
        global sensor_data
        try:
            with data_lock: sensor_data = json.loads(msg.data)
        except: pass
    def _sust(self, msg):
        global sustainment_data
        try:
            with data_lock: sustainment_data = json.loads(msg.data)
        except: pass
    def _sust_alert(self, msg):
        try:
            d = json.loads(msg.data)
            add_log(f"SUST: {d.get('type','?')} - {d.get('callsign','?')} ({d.get('battery',0):.0f}%)")
        except: pass
    def _coa(self, msg):
        global coa_data
        try:
            with data_lock: coa_data = json.loads(msg.data)
        except: pass
    def _gfz(self, msg):
        global geofence_zones
        try:
            with data_lock: geofence_zones = json.loads(msg.data)
        except: pass
    def _gfv(self, msg):
        global geofence_violations
        try:
            with data_lock: geofence_violations = json.loads(msg.data)
            for v in geofence_violations:
                add_log(f"GEOFENCE: {v.get('callsign','?')} {v.get('type','?')} in {v.get('zone_name','?')}")
        except: pass

    def _awacs_status(self, msg):
        global awacs_status
        try:
            d = json.loads(msg.data)
            with data_lock:
                awacs_status = [d] if isinstance(d, dict) else d
        except: pass

    def _hal_status(self, msg):
        global hal_status
        try:
            with data_lock: hal_status = json.loads(msg.data)
        except: pass

    def _hal_event(self, msg):
        global hal_events
        try:
            e = json.loads(msg.data)
            with data_lock:
                hal_events.insert(0, e)
                if len(hal_events) > 500: hal_events[:] = hal_events[:500]
        except: pass

    def _awacs_cop(self, msg):
        global awacs_cop
        try:
            with data_lock: awacs_cop = json.loads(msg.data)
        except: pass

    def pub(self, publisher, data, log_msg=''):
        m = String(); m.data = json.dumps(data); publisher.publish(m)
        if log_msg: add_log(log_msg)

ros_node = None

@app.route('/')
def index(): return render_template('index.html')
@app.route('/dashboard')
def dashboard(): return render_template('dashboard.html')
@app.route('/aar')
def aar(): return render_template('aar.html')
@app.route('/tactical3d')
def tactical3d(): return render_template('tactical3d.html')
@app.route('/hal')
def hal_page(): return render_template('hal.html')

@app.route('/awacs')
def awacs(): return render_template('awacs.html')

@app.route('/echelon')
def echelon(): return render_template('echelon.html')

@app.route('/api/assets')
def api_assets():
    with data_lock: return jsonify(list(asset_data.values()))
@app.route('/api/threats')
def api_threats():
    now = time.time()
    with data_lock: return jsonify([t for t in threat_data.values() if now - t.get('_time',0) < 30])
@app.route('/api/logs')
def api_logs():
    with data_lock: return jsonify(list(log_entries))
@app.route('/api/autonomy')
def api_autonomy():
    with data_lock: return jsonify(autonomy_state)
@app.route('/api/sensors')
def api_sensors():
    with data_lock: return jsonify(sensor_data if isinstance(sensor_data, list) else [])
@app.route('/api/sustainment')
def api_sustainment():
    with data_lock: return jsonify(sustainment_data if isinstance(sustainment_data, list) else [])
@app.route('/api/aar/snapshots')
def api_aar_snaps():
    with data_lock: return jsonify(aar_snapshots)
@app.route('/api/aar/events')
def api_aar_events():
    with data_lock: return jsonify(list(log_entries))
@app.route('/api/ai/coa')
def api_coa():
    with data_lock: return jsonify(coa_data if isinstance(coa_data, list) else [])
@app.route('/api/geofences')
def api_geofences():
    with data_lock: return jsonify(geofence_zones if isinstance(geofence_zones, list) else [])
@app.route('/api/geofence/violations')
def api_gf_violations():
    with data_lock: return jsonify(geofence_violations if isinstance(geofence_violations, list) else [])
@app.route('/api/tak/cot')
def api_tak_cot():
    with data_lock: return jsonify(list(tak_cot_cache.values()) if tak_cot_cache else [])

@app.route('/api/send_mission', methods=['POST'])
def send_mission():
    if ros_node:
        ros_node.pub(ros_node.mission_pub, request.get_json(), f"CMD: Mission {request.get_json().get('mission_type','?')}")
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 503

@app.route('/api/send_swarm', methods=['POST'])
def send_swarm():
    if ros_node:
        ros_node.pub(ros_node.swarm_pub, request.get_json(), f"CMD: Swarm {request.get_json().get('behavior','?')}")
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 503

@app.route('/api/set_autonomy', methods=['POST'])
def set_autonomy():
    if ros_node:
        ros_node.pub(ros_node.autonomy_pub, request.get_json(), f"CMD: Autonomy -> {request.get_json().get('target_level','?')}")
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 503

@app.route('/api/send_waypoints', methods=['POST'])
def send_waypoints():
    if ros_node:
        d = request.get_json()
        ros_node.pub(ros_node.waypoint_pub, d, f"CMD: WP -> {d.get('asset_id','?')}")
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 503

@app.route('/api/geofence/add', methods=['POST'])
def add_geofence():
    if ros_node:
        ros_node.pub(ros_node.gf_add_pub, request.get_json(), f"CMD: Geofence added")
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 503

@app.route('/api/geofence/delete', methods=['POST'])
def del_geofence():
    if ros_node:
        ros_node.pub(ros_node.gf_del_pub, request.get_json(), f"CMD: Geofence deleted")
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 503

@app.route('/api/hal/status')
def api_hal_status():
    with data_lock: return jsonify(hal_status if hal_status else {'mavros_available': False, 'nav2_available': False, 'default_source': 'sim', 'vehicles': {}, 'safety': {}})

@app.route('/api/hal/events')
def api_hal_events():
    with data_lock: return jsonify(hal_events[:50] if hal_events else [])

@app.route('/api/hal/command', methods=['POST'])
def api_hal_command():
    d = request.get_json()
    m = String()
    m.data = json.dumps(d)
    ros_bridge.hal_cmd_pub.publish(m)
    return jsonify({'status': 'sent', 'command': d})

@app.route('/api/hal/emergency_stop', methods=['POST'])
def api_hal_estop():
    m = String()
    m.data = json.dumps({'action': 'EMERGENCY_STOP', 'timestamp': time.time()})
    ros_bridge.hal_estop_pub.publish(m)
    return jsonify({'status': 'EMERGENCY_STOP_SENT'})

@app.route('/api/hal/connect', methods=['POST'])
def api_hal_connect():
    d = request.get_json()
    return jsonify({'status': 'queued', 'note': 'Edit hal_config.yaml and restart for persistent connections', 'data': d})

@app.route('/api/awacs')
def api_awacs():
    with data_lock: return jsonify(awacs_status if isinstance(awacs_status, list) else [])

@app.route('/api/awacs/cop')
def api_awacs_cop():
    with data_lock: return jsonify(awacs_cop if isinstance(awacs_cop, list) else [])

def aar_recorder():
    while True:
        time.sleep(2)
        with data_lock:
            if asset_data:
                aar_snapshots.append({'timestamp': time.time(), 'assets': copy.deepcopy(list(asset_data.values()))})
                if len(aar_snapshots) > 600: aar_snapshots.pop(0)

def ros_thread():
    global ros_node
    rclpy.init(); ros_node = C2Bridge()
    try: rclpy.spin(ros_node)
    except: pass
    finally:
        try: ros_node.destroy_node(); rclpy.shutdown()
        except: pass

def main():
    threading.Thread(target=ros_thread, daemon=True).start()
    threading.Thread(target=aar_recorder, daemon=True).start()
    time.sleep(1.0)
    print(f'[MOS C2] Templates: {template_dir}')
    print('[MOS C2] C2 Console:    http://0.0.0.0:5000')
    print('[MOS C2] Digital Twin:  http://0.0.0.0:5000/dashboard')
    print('[MOS C2] AAR Replay:    http://0.0.0.0:5000/aar')
    print('[MOS C2] 3D Tactical:   http://0.0.0.0:5000/tactical3d')
    print('[MOS C2] Echelon View:  http://0.0.0.0:5000/echelon')
    print('[MOS C2] AWACS View:    http://0.0.0.0:5000/awacs')
    print('[MOS C2] HAL Manager:   http://0.0.0.0:5000/hal')
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)


# ══════════════════════════════════════════════════════════
#  EW / SIGINT / CYBER ROUTES (Phase 9)
# ══════════════════════════════════════════════════════════

@app.route('/ew')
def ew_dashboard():
    """EW/SIGINT spectrum analyzer and emitter tracking."""
    return render_template('ew.html')

@app.route('/sigint')
def sigint_database():
    """SIGINT database — signal classification and analysis."""
    return render_template('sigint.html')

@app.route('/cyber')
def cyber_ops():
    """Cyber operations — WiFi, devices, vulnerabilities, IDS."""
    return render_template('cyber.html')


# ══════════════════════════════════════════════════════
#  EW / SIGINT / CYBER SIMULATION API
# ══════════════════════════════════════════════════════

@app.route('/api/ew/emitters')
def api_ew_emitters():
    return jsonify({"emitters": _sim.get_emitters(), "stats": _sim.get_ew_stats(), "tick": _sim.get_tick()})

@app.route('/api/ew/spectrum')
def api_ew_spectrum():
    return jsonify(_sim.get_spectrum())

@app.route('/api/ew/alerts')
def api_ew_alerts():
    return jsonify({"alerts": _sim.get_ew_alerts()})

@app.route('/api/sigint/signals')
def api_sigint_signals():
    return jsonify({"signals": _sim.get_signals()})

@app.route('/api/cyber/status')
def api_cyber_status():
    return jsonify(_sim.get_cyber())


if __name__ == '__main__':
    main()
