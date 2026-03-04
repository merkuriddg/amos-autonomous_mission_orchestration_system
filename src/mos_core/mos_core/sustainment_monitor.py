#!/usr/bin/env python3
"""MOS Sustainment Monitor — Phase 5: Auto-RTB, battery prediction, degraded asset alerts"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, math, time

class SustainmentMonitor(Node):
    def __init__(self):
        super().__init__('mos_sustainment_monitor')
        self.create_subscription(String, '/mos/heartbeat', self.on_heartbeat, 10)
        self.waypoint_pub = self.create_publisher(String, '/mos/waypoints/assign', 10)
        self.alert_pub = self.create_publisher(String, '/mos/sustainment/alerts', 10)
        self.status_pub = self.create_publisher(String, '/mos/sustainment/status', 10)

        self.assets = {}
        self.battery_history = {}
        self.rtb_triggered = set()

        self.CRITICAL_BATTERY = 15.0
        self.WARNING_BATTERY = 30.0

        self.timer = self.create_timer(2.0, self.check_sustainment)
        self.get_logger().info('[MOS SUST] Sustainment Monitor online — Phase 5')

    def on_heartbeat(self, msg):
        try:
            d = json.loads(msg.data)
            aid = d.get('asset_id', '')
            if not aid:
                return
            self.assets[aid] = d
            now = time.time()
            if aid not in self.battery_history:
                self.battery_history[aid] = []
            self.battery_history[aid].append((now, d.get('battery', 100)))
            if len(self.battery_history[aid]) > 60:
                self.battery_history[aid] = self.battery_history[aid][-60:]
        except Exception:
            pass

    def calc_drain_rate(self, aid):
        hist = self.battery_history.get(aid, [])
        if len(hist) < 4:
            return 0.0
        t0, b0 = hist[0]
        t1, b1 = hist[-1]
        dt = (t1 - t0) / 60.0
        if dt < 0.1:
            return 0.0
        return max(0.0, (b0 - b1) / dt)

    def calc_time_remaining(self, aid):
        drain = self.calc_drain_rate(aid)
        if drain <= 0.01:
            return 999.0
        batt = self.assets.get(aid, {}).get('battery', 100)
        return batt / drain

    def check_sustainment(self):
        alerts = []
        status_list = []

        for aid, asset in self.assets.items():
            batt = asset.get('battery', 100)
            drain_rate = self.calc_drain_rate(aid)
            time_remaining = self.calc_time_remaining(aid)

            dlat = asset.get('base_lat', asset['lat']) - asset['lat']
            dlon = asset.get('base_lon', asset['lon']) - asset['lon']
            dist_to_base = math.sqrt(dlat**2 + dlon**2)

            speed = asset.get('speed', 0.0001)
            time_to_base = (dist_to_base / speed) * 0.5 / 60 if speed > 0 else 999

            level = 'OK'
            if batt < self.CRITICAL_BATTERY:
                level = 'CRITICAL'
            elif batt < self.WARNING_BATTERY:
                level = 'WARNING'
            elif time_remaining < 10:
                level = 'WARNING'

            status_list.append({
                'asset_id': aid,
                'callsign': asset.get('callsign', '?'),
                'battery': round(batt, 1),
                'drain_rate': round(drain_rate, 2),
                'time_remaining': round(time_remaining, 1),
                'time_to_base': round(time_to_base, 1),
                'dist_to_base': round(dist_to_base, 6),
                'level': level,
            })

            if batt < self.CRITICAL_BATTERY and aid not in self.rtb_triggered:
                if asset.get('mission_status', 0) != 0:
                    self.rtb_triggered.add(aid)
                    rtb_msg = String()
                    rtb_msg.data = json.dumps({
                        'asset_id': aid,
                        'waypoints': [{'lat': asset.get('base_lat', asset['lat']),
                                       'lon': asset.get('base_lon', asset['lon'])}],
                        'loop': False,
                    })
                    self.waypoint_pub.publish(rtb_msg)
                    self.get_logger().warn(
                        f'[SUST] AUTO-RTB: {asset.get("callsign","?")} CRITICAL ({batt:.1f}%)')
                    alerts.append({
                        'type': 'AUTO_RTB', 'asset_id': aid,
                        'callsign': asset.get('callsign', '?'),
                        'battery': round(batt, 1), 'timestamp': time.time(),
                    })

            if batt > self.CRITICAL_BATTERY + 5:
                self.rtb_triggered.discard(aid)

        if status_list:
            m = String()
            m.data = json.dumps(status_list)
            self.status_pub.publish(m)

        for alert in alerts:
            m = String()
            m.data = json.dumps(alert)
            self.alert_pub.publish(m)

def main():
    rclpy.init()
    node = SustainmentMonitor()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
