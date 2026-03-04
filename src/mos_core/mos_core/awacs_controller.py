#!/usr/bin/env python3
"""MOS AWACS Controller — Phase 7: Airborne C2 node, sensor aggregation, mesh relay, auto-tasking"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, math, time

class AWACSController(Node):
    def __init__(self):
        super().__init__('mos_awacs_controller')
        self.create_subscription(String, '/mos/heartbeat', self._hb, 10)
        self.create_subscription(String, '/mos/sensor/detections', self._sensor, 10)
        self.create_subscription(String, '/mos/threats/alerts', self._threat, 10)
        self.create_subscription(String, '/mos/sustainment/status', self._sust, 10)

        self.awacs_pub = self.create_publisher(String, '/mos/awacs/status', 10)
        self.cop_pub = self.create_publisher(String, '/mos/awacs/cop', 10)
        self.wp_pub = self.create_publisher(String, '/mos/waypoints/assign', 10)

        self.assets = {}
        self.detections = []
        self.threats = {}
        self.sustainment = {}
        self.awacs_assets = {}
        self.correlation_db = {}
        self.corr_counter = 0

        self.create_timer(3.0, self.update)
        self.get_logger().info('[MOS AWACS] Airborne C2 Controller online — Phase 7')

    def _hb(self, msg):
        try:
            d = json.loads(msg.data)
            aid = d.get('asset_id', '')
            if aid:
                self.assets[aid] = d
                if 'AWACS' in d.get('callsign', ''):
                    self.awacs_assets[aid] = d
        except: pass

    def _sensor(self, msg):
        try: self.detections = json.loads(msg.data)
        except: pass

    def _threat(self, msg):
        try:
            d = json.loads(msg.data)
            tid = d.get('contact_id', d.get('id', ''))
            if tid: self.threats[tid] = d
        except: pass

    def _sust(self, msg):
        try:
            for s in json.loads(msg.data):
                self.sustainment[s['asset_id']] = s
        except: pass

    def update(self):
        now = time.time()
        for awacs_id, awacs in self.awacs_assets.items():
            awacs_lat, awacs_lon = awacs['lat'], awacs['lon']
            awacs_alt = awacs.get('alt', 300)

            # Coverage radius (meters) = altitude * 6
            coverage_deg = (awacs_alt * 12) / 111000

            # Assets in coverage
            covered = []
            for aid, a in self.assets.items():
                if aid == awacs_id: continue
                dist = math.sqrt((a['lat'] - awacs_lat)**2 + (a['lon'] - awacs_lon)**2)
                if dist < coverage_deg:
                    covered.append({
                        'asset_id': aid,
                        'callsign': a.get('callsign', '?'),
                        'type': a.get('asset_type', '?'),
                        'distance': round(dist * 111000),
                        'link_quality': round(max(0, 100 - (dist / coverage_deg * 100)), 1),
                    })

            # Sensor aggregation — correlate detections from covered assets
            fused = self._correlate_detections(awacs_lat, awacs_lon, coverage_deg)

            # Threat assessment in coverage area
            active_threats = []
            for tid, t in self.threats.items():
                tdist = math.sqrt((t.get('lat', 0) - awacs_lat)**2 +
                                  (t.get('lon', 0) - awacs_lon)**2)
                if tdist < coverage_deg:
                    active_threats.append({
                        'contact_id': tid,
                        'threat_level': t.get('threat_level', 'UNK'),
                        'distance': round(tdist * 111000),
                    })

            # Sustainment warnings in coverage
            sust_alerts = []
            for aid in [c['asset_id'] for c in covered]:
                s = self.sustainment.get(aid, {})
                if s.get('level') in ('WARNING', 'CRITICAL'):
                    sust_alerts.append({
                        'asset_id': aid,
                        'callsign': s.get('callsign', '?'),
                        'battery': s.get('battery', 0),
                        'level': s.get('level', 'OK'),
                    })

            status = {
                'awacs_id': awacs_id,
                'callsign': awacs.get('callsign', 'AWACS'),
                'lat': awacs_lat, 'lon': awacs_lon,
                'alt': awacs_alt,
                'coverage_radius_m': round(awacs_alt * 12),
                'coverage_radius_deg': round(coverage_deg, 6),
                'assets_covered': len(covered),
                'covered_assets': covered,
                'sensor_tracks': len(fused),
                'active_threats': len(active_threats),
                'threats': active_threats,
                'sust_alerts': len(sust_alerts),
                'sustainment_warnings': sust_alerts,
                'mesh_relay_active': len(covered) > 0,
                'timestamp': now,
            }

            m = String()
            m.data = json.dumps(status)
            self.awacs_pub.publish(m)

            # Publish fused COP
            if fused:
                cm = String()
                cm.data = json.dumps(fused)
                self.cop_pub.publish(cm)

    def _correlate_detections(self, alat, alon, cov):
        correlated = []
        used = set()
        for i, d in enumerate(self.detections):
            if i in used: continue
            dist = math.sqrt((d['lat'] - alat)**2 + (d['lon'] - alon)**2)
            if dist > cov: continue
            cluster = [d]; used.add(i)
            for j, d2 in enumerate(self.detections):
                if j in used: continue
                if math.sqrt((d['lat'] - d2['lat'])**2 + (d['lon'] - d2['lon'])**2) < 0.0015:
                    cluster.append(d2); used.add(j)
            self.corr_counter += 1
            correlated.append({
                'track_id': f'TRK-{self.corr_counter:04d}',
                'lat': sum(c['lat'] for c in cluster) / len(cluster),
                'lon': sum(c['lon'] for c in cluster) / len(cluster),
                'classification': cluster[0].get('classification', 'UNK'),
                'confidence': min(0.99, max(c.get('confidence', 0.5) for c in cluster) + 0.05 * len(cluster)),
                'sources': len(cluster),
                'sensor_types': list(set(c.get('sensor_type', '') for c in cluster)),
                'fused': len(cluster) > 1,
            })
        return correlated

def main():
    rclpy.init(); node = AWACSController(); rclpy.spin(node)
    node.destroy_node(); rclpy.shutdown()
