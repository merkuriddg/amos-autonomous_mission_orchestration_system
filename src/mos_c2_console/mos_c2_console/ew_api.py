#!/usr/bin/env python3
"""
MOS EW/SIGINT/Cyber API Routes
Registers Flask endpoints for the EW suite and manages ROS 2 subscriptions.
"""
from flask import jsonify, request, render_template
from std_msgs.msg import String
import json, time, threading

# Data stores (populated by ROS 2 callbacks)
ew_data = {
    'status': {}, 'emitters': {}, 'spectrum': {}, 'signals': [],
    'bearings': [], 'jamming': [], 'alerts': [], 'cop': {},
    'cyber_status': {}, 'cyber_networks': {}, 'cyber_devices': {},
    'cyber_vulns': [], 'cyber_alerts': [],
    'sdr_status': {}, 'anomalies': [],
}
_lock = threading.Lock()

def register_ew_routes(app, node):
    """Register all EW/SIGINT/Cyber Flask routes and ROS 2 subscribers."""

    # ── ROS 2 Subscriptions ──────────────────────────────────────────
    def _cb(topic_key):
        def callback(msg):
            d = json.loads(msg.data)
            with _lock:
                if topic_key == 'emitters':
                    eid = d.get('emitter_id','')
                    if eid: ew_data['emitters'][eid] = d
                elif topic_key == 'signals':
                    ew_data['signals'].append(d)
                    if len(ew_data['signals']) > 500:
                        ew_data['signals'] = ew_data['signals'][-500:]
                elif topic_key == 'bearings':
                    ew_data['bearings'] = d.get('bearings', [])
                elif topic_key == 'ew_alerts':
                    ew_data['alerts'].append(d)
                    if len(ew_data['alerts']) > 200:
                        ew_data['alerts'] = ew_data['alerts'][-200:]
                elif topic_key == 'cyber_vulns':
                    ew_data['cyber_vulns'].append(d)
                    if len(ew_data['cyber_vulns']) > 100:
                        ew_data['cyber_vulns'] = ew_data['cyber_vulns'][-100:]
                elif topic_key == 'cyber_alerts':
                    ew_data['cyber_alerts'].append(d)
                    if len(ew_data['cyber_alerts']) > 200:
                        ew_data['cyber_alerts'] = ew_data['cyber_alerts'][-200:]
                elif topic_key == 'cyber_networks':
                    nets = d.get('wifi_networks', d.get('devices', []))
                    for n in (nets if isinstance(nets, list) else []):
                        key = n.get('bssid', n.get('ip', ''))
                        if key: ew_data['cyber_networks'][key] = n
                elif topic_key == 'anomalies':
                    ew_data['anomalies'].append(d)
                    if len(ew_data['anomalies']) > 100:
                        ew_data['anomalies'] = ew_data['anomalies'][-100:]
                else:
                    ew_data[topic_key] = d
        return callback

    subs = [
        ('/mos/ew/status', 'status'), ('/mos/ew/emitters', 'emitters'),
        ('/mos/ew/spectrum', 'spectrum'), ('/mos/ew/signals', 'signals'),
        ('/mos/ew/bearings', 'bearings'), ('/mos/ew/cop', 'cop'),
        ('/mos/ew/alerts', 'ew_alerts'), ('/mos/ew/anomalies', 'anomalies'),
        ('/mos/cyber/status', 'cyber_status'), ('/mos/cyber/networks', 'cyber_networks'),
        ('/mos/cyber/vulns', 'cyber_vulns'), ('/mos/cyber/alerts', 'cyber_alerts'),
        ('/mos/sdr/status', 'sdr_status'),
    ]
    for topic, key in subs:
        node.create_subscription(String, topic, _cb(key), 10)

    # Command publishers
    ew_cmd_pub = node.create_publisher(String, '/mos/ew/command', 10)
    sdr_cmd_pub = node.create_publisher(String, '/mos/sdr/command', 10)

    # ── Page Routes ──────────────────────────────────────────────────
    @app.route('/ew')
    def ew_page():
        return render_template('ew.html')

    @app.route('/sigint')
    def sigint_page():
        return render_template('sigint.html')

    @app.route('/cyber')
    def cyber_page():
        return render_template('cyber.html')

    # ── EW API ───────────────────────────────────────────────────────
    @app.route('/api/ew/status')
    def api_ew_status():
        with _lock: return jsonify(ew_data['status'])

    @app.route('/api/ew/emitters')
    def api_ew_emitters():
        with _lock: return jsonify(list(ew_data['emitters'].values()))

    @app.route('/api/ew/spectrum')
    def api_ew_spectrum():
        with _lock: return jsonify(ew_data['spectrum'])

    @app.route('/api/ew/signals')
    def api_ew_signals():
        with _lock: return jsonify(ew_data['signals'][-100:])

    @app.route('/api/ew/bearings')
    def api_ew_bearings():
        with _lock: return jsonify(ew_data['bearings'])

    @app.route('/api/ew/alerts')
    def api_ew_alerts():
        with _lock: return jsonify(ew_data['alerts'][-50:])

    @app.route('/api/ew/cop')
    def api_ew_cop():
        with _lock: return jsonify(ew_data['cop'])

    @app.route('/api/ew/anomalies')
    def api_ew_anomalies():
        with _lock: return jsonify(ew_data['anomalies'][-50:])

    @app.route('/api/ew/jam', methods=['POST'])
    def api_ew_jam():
        d = request.json or {}
        d['action'] = d.get('action', 'START_JAM')
        msg = String(); msg.data = json.dumps(d)
        ew_cmd_pub.publish(msg)
        return jsonify({'status': 'ok', 'command': d})

    @app.route('/api/ew/scan', methods=['POST'])
    def api_ew_scan():
        d = request.json or {}
        d['action'] = 'START_SCAN'
        msg = String(); msg.data = json.dumps(d)
        ew_cmd_pub.publish(msg)
        return jsonify({'status': 'ok'})

    @app.route('/api/ew/df', methods=['POST'])
    def api_ew_df():
        d = request.json or {}
        d['action'] = 'DF_LOCATE'
        msg = String(); msg.data = json.dumps(d)
        ew_cmd_pub.publish(msg)
        return jsonify({'status': 'ok'})

    # ── Cyber API ────────────────────────────────────────────────────
    @app.route('/api/cyber/status')
    def api_cyber_status():
        with _lock: return jsonify(ew_data['cyber_status'])

    @app.route('/api/cyber/networks')
    def api_cyber_networks():
        with _lock: return jsonify(list(ew_data['cyber_networks'].values()))

    @app.route('/api/cyber/vulns')
    def api_cyber_vulns():
        with _lock: return jsonify(ew_data['cyber_vulns'][-50:])

    @app.route('/api/cyber/alerts')
    def api_cyber_alerts():
        with _lock: return jsonify(ew_data['cyber_alerts'][-50:])

    # ── SDR API ──────────────────────────────────────────────────────
    @app.route('/api/sdr/status')
    def api_sdr_status():
        with _lock: return jsonify(ew_data['sdr_status'])

    @app.route('/api/sdr/tool', methods=['POST'])
    def api_sdr_tool():
        d = request.json or {}
        msg = String(); msg.data = json.dumps(d)
        sdr_cmd_pub.publish(msg)
        return jsonify({'status': 'ok', 'command': d})

    node.get_logger().info('[EW API] 18 EW/SIGINT/Cyber endpoints registered')
