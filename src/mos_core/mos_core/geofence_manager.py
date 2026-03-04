#!/usr/bin/env python3
"""MOS Geofence Manager — Phase 6: Keep-in/keep-out zones, ROE constraints, violation alerts"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, time

class GeofenceManager(Node):
    def __init__(self):
        super().__init__('mos_geofence_manager')
        self.create_subscription(String, '/mos/heartbeat', self._hb, 10)
        self.create_subscription(String, '/mos/geofence/add', self._add, 10)
        self.create_subscription(String, '/mos/geofence/delete', self._delete, 10)
        self.violation_pub = self.create_publisher(String, '/mos/geofence/violations', 10)
        self.zones_pub = self.create_publisher(String, '/mos/geofence/zones', 10)
        self.wp_pub = self.create_publisher(String, '/mos/waypoints/assign', 10)
        self.assets = {}
        self.zones = []
        self.zone_counter = 0
        self.violations = {}
        self.create_timer(2.0, self.check)
        self.create_timer(3.0, self.publish_zones)
        self.get_logger().info('[MOS GF] Geofence Manager online — Phase 6')

    def _hb(self, msg):
        try:
            d = json.loads(msg.data)
            if d.get('asset_id'): self.assets[d['asset_id']] = d
        except: pass

    def _add(self, msg):
        try:
            z = json.loads(msg.data)
            self.zone_counter += 1
            z['zone_id'] = z.get('zone_id', f'GF-{self.zone_counter:03d}')
            z.setdefault('name', f'Zone {self.zone_counter}')
            z.setdefault('type', 'KEEP_OUT')
            z.setdefault('active', True)
            z.setdefault('color', '#ff4444' if z['type'] == 'KEEP_OUT' else '#4488ff')
            self.zones.append(z)
            self.get_logger().info(f'[GF] Added zone {z["zone_id"]}: {z["name"]} ({z["type"]})')
        except Exception as e:
            self.get_logger().error(f'[GF] Error adding zone: {e}')

    def _delete(self, msg):
        try:
            d = json.loads(msg.data)
            zid = d.get('zone_id', '')
            self.zones = [z for z in self.zones if z.get('zone_id') != zid]
            self.get_logger().info(f'[GF] Deleted zone {zid}')
        except: pass

    def publish_zones(self):
        m = String(); m.data = json.dumps(self.zones); self.zones_pub.publish(m)

    def check(self):
        now = time.time()
        active_violations = []
        for aid, asset in self.assets.items():
            lat, lon = asset['lat'], asset['lon']
            for zone in self.zones:
                if not zone.get('active', True): continue
                inside = self._pip(lat, lon, zone.get('polygon', []))
                vkey = f'{aid}:{zone["zone_id"]}'
                if zone['type'] == 'KEEP_OUT' and inside:
                    if vkey not in self.violations:
                        self.violations[vkey] = now
                        self.get_logger().warn(f'[GF] VIOLATION: {asset.get("callsign","?")} in KEEP_OUT {zone["name"]}')
                    active_violations.append({
                        'asset_id': aid, 'callsign': asset.get('callsign', '?'),
                        'zone_id': zone['zone_id'], 'zone_name': zone['name'],
                        'type': 'KEEP_OUT_VIOLATION', 'timestamp': now})
                elif zone['type'] == 'KEEP_IN' and not inside:
                    if vkey not in self.violations:
                        self.violations[vkey] = now
                        self.get_logger().warn(f'[GF] VIOLATION: {asset.get("callsign","?")} outside KEEP_IN {zone["name"]}')
                    active_violations.append({
                        'asset_id': aid, 'callsign': asset.get('callsign', '?'),
                        'zone_id': zone['zone_id'], 'zone_name': zone['name'],
                        'type': 'KEEP_IN_VIOLATION', 'timestamp': now})
                else:
                    self.violations.pop(vkey, None)
        if active_violations:
            m = String(); m.data = json.dumps(active_violations); self.violation_pub.publish(m)

    def _pip(self, lat, lon, poly):
        n = len(poly)
        if n < 3: return False
        inside = False; j = n - 1
        for i in range(n):
            pi, pj = poly[i], poly[j]
            if ((pi['lat'] > lat) != (pj['lat'] > lat)) and \
               (lon < (pj['lon']-pi['lon'])*(lat-pi['lat'])/(pj['lat']-pi['lat'])+pi['lon']):
                inside = not inside
            j = i
        return inside

def main():
    rclpy.init(); node = GeofenceManager(); rclpy.spin(node)
    node.destroy_node(); rclpy.shutdown()
