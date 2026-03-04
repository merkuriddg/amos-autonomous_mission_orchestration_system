#!/usr/bin/env python3
"""
MOS Swarm Orchestrator — Phase 4b
Formations: LINE, COLUMN, WEDGE, DIAMOND, ORBIT
Passthrough: RTB, HOLD, SCATTER
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, math

class SwarmOrchestrator(Node):
    def __init__(self):
        super().__init__('mos_swarm_orchestrator')

        self.create_subscription(String, '/mos/swarm_command', self.on_command, 10)
        self.create_subscription(String, '/mos/heartbeat', self.on_heartbeat, 10)

        self.swarm_pub = self.create_publisher(String, '/mos/swarm/command', 10)
        self.waypoint_pub = self.create_publisher(String, '/mos/waypoints/assign', 10)

        self.assets = {}
        self.get_logger().info('[MOS SWARM] Orchestrator online — Phase 4b (formations)')

    def on_heartbeat(self, msg):
        try:
            d = json.loads(msg.data)
            aid = d.get('asset_id', '')
            if aid:
                self.assets[aid] = d
        except Exception:
            pass

    def on_command(self, msg):
        try:
            data = json.loads(msg.data)
            behavior = data.get('behavior', 'HOLD')
            domain = data.get('domain', 'ALL')
            self.get_logger().info(f'[MOS SWARM] Received: {behavior} domain={domain}')

            if behavior.startswith('FORM_'):
                self.execute_formation(behavior, domain)
            else:
                out = String()
                out.data = json.dumps(data)
                self.swarm_pub.publish(out)
                self.get_logger().info(f'[MOS SWARM] Passthrough → {behavior}')
        except Exception as e:
            self.get_logger().error(f'[MOS SWARM] Error: {e}')

    def get_filtered(self, domain):
        result = []
        for a in self.assets.values():
            if domain == 'ALL' or a.get('asset_type') == domain:
                result.append(a)
        return result

    def get_center(self, assets):
        if not assets:
            return 34.0, -118.0
        lat = sum(a['lat'] for a in assets) / len(assets)
        lon = sum(a['lon'] for a in assets) / len(assets)
        return lat, lon

    def execute_formation(self, formation, domain):
        assets = self.get_filtered(domain)
        if not assets:
            self.get_logger().warn(f'[MOS SWARM] No assets for domain={domain}')
            return

        clat, clon = self.get_center(assets)
        n = len(assets)
        sp = 0.0008

        positions = []

        if formation == 'FORM_LINE':
            for i in range(n):
                offset = (i - (n - 1) / 2) * sp
                positions.append((clat, clon + offset))

        elif formation == 'FORM_COLUMN':
            for i in range(n):
                offset = (i - (n - 1) / 2) * sp
                positions.append((clat + offset, clon))

        elif formation == 'FORM_WEDGE':
            for i in range(n):
                if i == 0:
                    positions.append((clat + sp, clon))
                else:
                    side = 1 if i % 2 == 1 else -1
                    row = (i + 1) // 2
                    positions.append((
                        clat - row * sp * 0.7,
                        clon + side * row * sp * 0.5))

        elif formation == 'FORM_DIAMOND':
            positions.append((clat, clon))
            ring = 1
            idx = 1
            while idx < n:
                pts_in_ring = ring * 4
                for p in range(pts_in_ring):
                    if idx >= n:
                        break
                    angle = (p / pts_in_ring) * 2 * math.pi + math.pi / 4
                    r = ring * sp
                    positions.append((
                        clat + r * math.cos(angle),
                        clon + r * math.sin(angle)))
                    idx += 1
                ring += 1

        elif formation == 'FORM_ORBIT':
            r = sp * max(1, n / 6)
            for i in range(n):
                angle = (i / n) * 2 * math.pi
                positions.append((
                    clat + r * math.cos(angle),
                    clon + r * math.sin(angle)))

        loop = (formation == 'FORM_ORBIT')

        for i, asset in enumerate(assets):
            if i < len(positions):
                wp = {
                    'asset_id': asset['asset_id'],
                    'waypoints': [{'lat': positions[i][0], 'lon': positions[i][1]}],
                    'loop': loop,
                }
                m = String()
                m.data = json.dumps(wp)
                self.waypoint_pub.publish(m)

        self.get_logger().info(
            f'[MOS SWARM] {formation}: {len(assets)} assets repositioned')


def main():
    rclpy.init()
    node = SwarmOrchestrator()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
