#!/usr/bin/env python3
"""MOS Sensor Fusion — Phase 5: Simulated EO/IR, SIGINT, RADAR, LIDAR, SONAR detections"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, math, random, time

SENSOR_CONFIG = {
    'AIR':      {'sensors': ['EO_IR', 'SIGINT', 'RADAR'], 'range': 0.008},
    'GROUND':   {'sensors': ['EO_IR', 'RADAR', 'LIDAR'],  'range': 0.004},
    'MARITIME': {'sensors': ['RADAR', 'SONAR', 'SIGINT'],  'range': 0.006},
}

CLASSIFICATIONS = {
    'EO_IR':  ['VEHICLE', 'PERSONNEL', 'STRUCTURE', 'UNKNOWN'],
    'SIGINT': ['EMITTER', 'COMM_NODE', 'JAMMER', 'UNKNOWN'],
    'RADAR':  ['VEHICLE', 'AIRCRAFT', 'WATERCRAFT', 'UNKNOWN'],
    'LIDAR':  ['VEHICLE', 'OBSTACLE', 'STRUCTURE', 'UNKNOWN'],
    'SONAR':  ['SUBMARINE', 'WATERCRAFT', 'MARINE_LIFE', 'UNKNOWN'],
}

class SensorFusion(Node):
    def __init__(self):
        super().__init__('mos_sensor_fusion')
        self.create_subscription(String, '/mos/heartbeat', self.on_heartbeat, 10)
        self.detection_pub = self.create_publisher(String, '/mos/sensor/detections', 10)

        self.assets = {}
        self.detections = {}
        self.det_counter = 0

        self.timer = self.create_timer(3.0, self.simulate_detections)
        self.get_logger().info('[MOS SENSOR] Sensor Fusion Hub online — Phase 5')

    def on_heartbeat(self, msg):
        try:
            d = json.loads(msg.data)
            aid = d.get('asset_id', '')
            if aid:
                self.assets[aid] = d
        except Exception:
            pass

    def simulate_detections(self):
        now = time.time()
        expired = [k for k, v in self.detections.items() if now - v['timestamp'] > 15]
        for k in expired:
            del self.detections[k]

        for aid, asset in self.assets.items():
            if asset.get('mission_status', 0) == 0:
                continue
            config = SENSOR_CONFIG.get(asset.get('asset_type', 'GROUND'))
            if not config:
                continue
            if random.random() > 0.15:
                continue

            sensor = random.choice(config['sensors'])
            det_range = config['range'] * random.uniform(0.3, 1.0)
            angle = random.uniform(0, 2 * math.pi)
            det_lat = asset['lat'] + det_range * math.cos(angle)
            det_lon = asset['lon'] + det_range * math.sin(angle)
            cls_type = random.choice(CLASSIFICATIONS.get(sensor, ['UNKNOWN']))
            confidence = random.uniform(0.4, 0.95)

            fused = False
            for did, existing in self.detections.items():
                dlat = existing['lat'] - det_lat
                dlon = existing['lon'] - det_lon
                if math.sqrt(dlat**2 + dlon**2) < 0.001:
                    existing['confidence'] = min(0.99, existing['confidence'] + 0.1)
                    existing['sources'] = existing.get('sources', 1) + 1
                    existing['timestamp'] = now
                    existing['fused'] = True
                    fused = True
                    break

            if not fused:
                self.det_counter += 1
                det_id = f'DET-{self.det_counter:04d}'
                self.detections[det_id] = {
                    'detection_id': det_id, 'sensor_type': sensor,
                    'source_asset': aid, 'source_callsign': asset.get('callsign', '?'),
                    'classification': cls_type, 'confidence': round(confidence, 2),
                    'lat': round(det_lat, 6), 'lon': round(det_lon, 6),
                    'timestamp': now, 'sources': 1, 'fused': False,
                }

        all_dets = list(self.detections.values())
        if all_dets:
            m = String()
            m.data = json.dumps(all_dets)
            self.detection_pub.publish(m)

def main():
    rclpy.init()
    node = SensorFusion()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
