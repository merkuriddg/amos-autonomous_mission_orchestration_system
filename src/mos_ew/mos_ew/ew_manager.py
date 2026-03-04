#!/usr/bin/env python3
"""
MOS EW Manager — Electronic Warfare Operations Center
Orchestrates all EW/SIGINT/Cyber operations across the platoon.
Manages jamming zones, EW missions, RF environment status, and coordinates
EW-capable assets for maximum electromagnetic spectrum dominance.
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, time, random, math

class EWManager(Node):
    def __init__(self):
        super().__init__('ew_manager')
        # Publishers
        self.status_pub = self.create_publisher(String, '/mos/ew/status', 10)
        self.jamming_pub = self.create_publisher(String, '/mos/ew/jamming', 10)
        self.ew_cop_pub = self.create_publisher(String, '/mos/ew/cop', 10)
        self.ew_alert_pub = self.create_publisher(String, '/mos/ew/alerts', 10)
        # Subscribers
        self.create_subscription(String, '/mos/ew/emitters', self._on_emitter, 10)
        self.create_subscription(String, '/mos/ew/command', self._on_command, 10)
        self.create_subscription(String, '/mos/heartbeat', self._on_heartbeat, 10)
        self.create_subscription(String, '/mos/ew/spectrum', self._on_spectrum, 10)
        self.create_subscription(String, '/mos/cyber/alerts', self._on_cyber_alert, 10)
        self.create_subscription(String, '/mos/sdr/status', self._on_sdr_status, 10)
        # State
        self.emitters = {}
        self.jamming_zones = []
        self.active_ops = []
        self.ew_assets = {}
        self.sdr_hardware = {}
        self.cyber_alerts = []
        self.spectrum_snapshot = None
        self.stats = {'emitters_total': 0, 'emitters_hostile': 0,
                      'signals_classified': 0, 'jam_activations': 0}
        # EW-capable assets defined in config
        self.ew_asset_ids = ['MVRX-A03','MVRX-A04','MVRX-A05',
                             'MVRX-G03','MVRX-G04','AWACS-1','AWACS-2']
        # Timers
        self.create_timer(2.0, self._publish_status)
        self.create_timer(5.0, self._publish_cop)
        self.create_timer(10.0, self._assess_rf_threats)
        self.get_logger().info('='*60)
        self.get_logger().info('  ⚡ EW MANAGER ONLINE — ELECTROMAGNETIC DOMINANCE ⚡')
        self.get_logger().info('='*60)

    def _on_heartbeat(self, msg):
        d = json.loads(msg.data)
        aid = d.get('asset_id','')
        if aid in self.ew_asset_ids:
            self.ew_assets[aid] = {
                'asset_id': aid, 'lat': d.get('lat',0), 'lon': d.get('lon',0),
                'alt': d.get('alt',0), 'battery': d.get('battery',0),
                'status': d.get('status','UNKNOWN'), 'last_seen': time.time()
            }

    def _on_emitter(self, msg):
        d = json.loads(msg.data)
        eid = d.get('emitter_id','')
        self.emitters[eid] = d
        self.stats['emitters_total'] = len(self.emitters)
        if d.get('classification') in ['HOSTILE','JAMMER']:
            self.stats['emitters_hostile'] = sum(
                1 for e in self.emitters.values()
                if e.get('classification') in ['HOSTILE','JAMMER'])
            self._publish_alert('THREAT_EMITTER', d)
        if d.get('classification') == 'JAMMER':
            self._publish_alert('JAMMING_DETECTED', d)

    def _on_command(self, msg):
        d = json.loads(msg.data)
        action = d.get('action','')
        if action == 'START_JAM':
            zone = {
                'id': f"JAM-{len(self.jamming_zones)+1:03d}",
                'profile': d.get('profile','NOISE'),
                'center_freq_mhz': d.get('freq_mhz', 462.0),
                'bandwidth_mhz': d.get('bandwidth_mhz', 5.0),
                'lat': d.get('lat', 27.85), 'lon': d.get('lon', -82.52),
                'radius_m': d.get('radius_m', 500),
                'power_dbm': d.get('power_dbm', 30),
                'assigned_asset': d.get('asset_id','MVRX-A04'),
                'active': True, 'start_time': time.time()
            }
            self.jamming_zones.append(zone)
            self.stats['jam_activations'] += 1
            out = String(); out.data = json.dumps({'type':'JAM_ACTIVATE','zone':zone})
            self.jamming_pub.publish(out)
            self.get_logger().warn(f'⚡ JAMMING ACTIVE: {zone["id"]} | '
                                   f'{zone["center_freq_mhz"]} MHz | '
                                   f'{zone["profile"]} | Asset: {zone["assigned_asset"]}')
        elif action == 'STOP_JAM':
            jid = d.get('jam_id','')
            for z in self.jamming_zones:
                if z['id'] == jid:
                    z['active'] = False
                    self.get_logger().info(f'Jamming zone {jid} deactivated')
        elif action == 'START_SCAN':
            op = {'id': f"OP-{len(self.active_ops)+1:03d}", 'type': 'SPECTRUM_SCAN',
                  'asset': d.get('asset_id','MVRX-A03'),
                  'freq_start': d.get('freq_start', 400),
                  'freq_end': d.get('freq_end', 500),
                  'start_time': time.time(), 'status': 'ACTIVE'}
            self.active_ops.append(op)
        elif action == 'DF_LOCATE':
            target_eid = d.get('emitter_id','')
            if target_eid in self.emitters:
                op = {'id': f"OP-{len(self.active_ops)+1:03d}", 'type': 'DF_LOCATE',
                      'target': target_eid, 'status': 'ACTIVE',
                      'assigned_assets': d.get('assets', list(self.ew_assets.keys())[:3]),
                      'start_time': time.time()}
                self.active_ops.append(op)

    def _on_spectrum(self, msg):
        self.spectrum_snapshot = json.loads(msg.data)

    def _on_cyber_alert(self, msg):
        d = json.loads(msg.data)
        self.cyber_alerts.append(d)
        if len(self.cyber_alerts) > 100:
            self.cyber_alerts = self.cyber_alerts[-100:]

    def _on_sdr_status(self, msg):
        d = json.loads(msg.data)
        self.sdr_hardware = d

    def _assess_rf_threats(self):
        hostile = [e for e in self.emitters.values()
                   if e.get('classification') in ['HOSTILE','JAMMER','SUSPECT']]
        if len(hostile) > 3:
            self._publish_alert('HIGH_RF_THREAT_DENSITY',
                {'count': len(hostile), 'message': f'{len(hostile)} threat/suspect emitters active'})
        jammers = [e for e in self.emitters.values() if e.get('classification') == 'JAMMER']
        for j in jammers:
            if j.get('signal_type') == 'GPS_INTERFERENCE':
                self._publish_alert('GPS_THREAT',
                    {'emitter': j, 'message': 'GPS interference detected — check navigation'})

    def _publish_alert(self, alert_type, data):
        alert = {'timestamp': time.time(), 'type': alert_type, 'data': data,
                 'severity': 'CRITICAL' if 'JAMMER' in alert_type or 'GPS' in alert_type else 'WARNING'}
        msg = String(); msg.data = json.dumps(alert)
        self.ew_alert_pub.publish(msg)
        self.get_logger().warn(f'⚠ EW ALERT: {alert_type}')

    def _publish_status(self):
        status = {
            'timestamp': time.time(),
            'ew_assets_online': len([a for a in self.ew_assets.values()
                                     if time.time()-a.get('last_seen',0)<10]),
            'ew_assets': list(self.ew_assets.values()),
            'total_emitters': len(self.emitters),
            'hostile_emitters': self.stats['emitters_hostile'],
            'active_jamming': [z for z in self.jamming_zones if z.get('active')],
            'active_operations': [o for o in self.active_ops if o.get('status')=='ACTIVE'],
            'sdr_hardware': self.sdr_hardware,
            'readiness': 'GREEN' if len(self.ew_assets) >= 3 else
                         'AMBER' if len(self.ew_assets) >= 1 else 'RED',
            'stats': self.stats
        }
        msg = String(); msg.data = json.dumps(status)
        self.status_pub.publish(msg)

    def _publish_cop(self):
        cop = {
            'timestamp': time.time(),
            'emitters': list(self.emitters.values()),
            'jamming_zones': [z for z in self.jamming_zones if z.get('active')],
            'ew_assets': list(self.ew_assets.values()),
            'rf_environment': 'CONTESTED' if self.stats['emitters_hostile']>2 else
                              'DEGRADED' if self.stats['emitters_hostile']>0 else 'PERMISSIVE',
            'spectrum': self.spectrum_snapshot
        }
        msg = String(); msg.data = json.dumps(cop)
        self.ew_cop_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = EWManager()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node()
