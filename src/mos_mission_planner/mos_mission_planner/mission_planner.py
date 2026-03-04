#!/usr/bin/env python3
"""
MOS Mission Planner — Phase 4b
Decomposes 6 mission types into waypoint patterns and assigns to available assets.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, math, random, time

MISSION_TEMPLATES = {
    'ISR': {
        'domains': ['AIR'],
        'count': 3,
        'pattern': 'RACETRACK',
        'loop': True,
        'desc': 'Aerial reconnaissance racetrack',
    },
    'SECURITY': {
        'domains': ['GROUND'],
        'count': 4,
        'pattern': 'PERIMETER',
        'loop': True,
        'desc': 'Perimeter security patrol',
    },
    'PRECISION_EFFECTS': {
        'domains': ['AIR', 'GROUND'],
        'count': 4,
        'pattern': 'CONVERGE',
        'loop': False,
        'desc': 'Multi-domain precision strike',
    },
    'LOGISTICS': {
        'domains': ['GROUND'],
        'count': 2,
        'pattern': 'ROUTE',
        'loop': False,
        'desc': 'Supply route logistics run',
    },
    'SAR': {
        'domains': ['AIR', 'GROUND'],
        'count': 4,
        'pattern': 'SEARCH_GRID',
        'loop': True,
        'desc': 'Search and rescue grid',
    },
    'EW_SIGINT': {
        'domains': ['AIR', 'MARITIME'],
        'count': 3,
        'pattern': 'ORBIT',
        'loop': True,
        'desc': 'EW/SIGINT collection orbit',
    },
}


class MissionPlanner(Node):
    def __init__(self):
        super().__init__('mos_mission_planner')

        self.create_subscription(String, '/mos/mission_command', self.on_mission, 10)
        self.create_subscription(String, '/mos/heartbeat', self.on_heartbeat, 10)

        self.waypoint_pub = self.create_publisher(String, '/mos/waypoints/assign', 10)
        self.status_pub = self.create_publisher(String, '/mos/mission/status', 10)

        self.assets = {}
        self.get_logger().info('[MOS PLANNER] Mission Planner online — Phase 4b')

    def on_heartbeat(self, msg):
        try:
            d = json.loads(msg.data)
            aid = d.get('asset_id', '')
            if aid:
                self.assets[aid] = d
        except Exception:
            pass

    def get_available(self, domains, count):
        avail = []
        for a in self.assets.values():
            if a.get('asset_type') in domains and a.get('mission_status', 0) == 0:
                avail.append(a)
        avail.sort(key=lambda x: x.get('battery', 0), reverse=True)
        return avail[:count]

    def make_waypoints(self, pattern, clat, clon, idx, total):
        r = 0.003

        if pattern == 'RACETRACK':
            off = idx * 0.001
            return [
                {'lat': clat + r + off, 'lon': clon - r},
                {'lat': clat + r + off, 'lon': clon + r},
                {'lat': clat - r + off, 'lon': clon + r},
                {'lat': clat - r + off, 'lon': clon - r},
            ]

        elif pattern == 'PERIMETER':
            a0 = (idx / total) * 2 * math.pi
            pts = []
            for j in range(4):
                a = a0 + j * (math.pi / 2)
                pts.append({'lat': clat + r * math.cos(a), 'lon': clon + r * math.sin(a)})
            return pts

        elif pattern == 'CONVERGE':
            a = (idx / total) * 2 * math.pi
            return [
                {'lat': clat + r * 2 * math.cos(a), 'lon': clon + r * 2 * math.sin(a)},
                {'lat': clat + r * 0.3 * math.cos(a), 'lon': clon + r * 0.3 * math.sin(a)},
            ]

        elif pattern == 'ROUTE':
            off = idx * 0.0005
            return [
                {'lat': clat - r + off, 'lon': clon},
                {'lat': clat + off, 'lon': clon + r * 0.5},
                {'lat': clat + r + off, 'lon': clon},
            ]

        elif pattern == 'SEARCH_GRID':
            gs = r / 2
            row = idx // 2
            col = idx % 2
            bl = clat - r + row * gs
            bo = clon - r + col * gs * 2
            d = 1 if col == 0 else -1
            return [
                {'lat': bl, 'lon': bo},
                {'lat': bl, 'lon': bo + d * gs},
                {'lat': bl + gs * 0.5, 'lon': bo + d * gs},
                {'lat': bl + gs * 0.5, 'lon': bo},
            ]

        elif pattern == 'ORBIT':
            rad = r * (1 + idx * 0.3)
            pts = []
            for j in range(6):
                a = (j / 6) * 2 * math.pi + idx * (math.pi / 3)
                pts.append({'lat': clat + rad * math.cos(a), 'lon': clon + rad * math.sin(a)})
            return pts

        return [{'lat': clat, 'lon': clon}]

    def on_mission(self, msg):
        try:
            data = json.loads(msg.data)
            mtype = data.get('mission_type', 'ISR')
            mid = data.get('mission_id', 'UNK')

            tmpl = MISSION_TEMPLATES.get(mtype)
            if not tmpl:
                self.get_logger().warn(f'[MOS PLANNER] Unknown type: {mtype}')
                return

            self.get_logger().info(f'[MOS PLANNER] *** MISSION {mid}: {mtype} ***')
            self.get_logger().info(f'  {tmpl["desc"]} | Pattern: {tmpl["pattern"]}')

            available = self.get_available(tmpl['domains'], tmpl['count'])

            if not available:
                self.get_logger().warn(f'[MOS PLANNER] No available assets for {mtype}!')
                self.pub_status(mid, 'NO_ASSETS', 0)
                return

            clat = sum(a['lat'] for a in available) / len(available)
            clon = sum(a['lon'] for a in available) / len(available)
            clat += random.uniform(-0.002, 0.002)
            clon += random.uniform(-0.002, 0.002)

            count = 0
            for i, asset in enumerate(available):
                wps = self.make_waypoints(tmpl['pattern'], clat, clon, i, len(available))
                wp_msg = String()
                wp_msg.data = json.dumps({
                    'asset_id': asset['asset_id'],
                    'waypoints': wps,
                    'loop': tmpl['loop'],
                })
                self.waypoint_pub.publish(wp_msg)
                count += 1
                self.get_logger().info(
                    f'  -> {asset["callsign"]} tasked {len(wps)} waypoints (loop={tmpl["loop"]})')

            self.pub_status(mid, 'ACTIVE', count)
            self.get_logger().info(f'[MOS PLANNER] *** {count} assets tasked ***')

        except Exception as e:
            self.get_logger().error(f'[MOS PLANNER] Error: {e}')

    def pub_status(self, mid, status, count):
        m = String()
        m.data = json.dumps({
            'mission_id': mid,
            'status': status,
            'task_count': count,
            'timestamp': time.time(),
        })
        self.status_pub.publish(m)


def main():
    rclpy.init()
    node = MissionPlanner()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
