#!/usr/bin/env python3
"""MOS TAK Bridge — Phase 6: Cursor on Target (CoT) XML export over UDP"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, socket, time
from datetime import datetime, timezone, timedelta

COT_TYPES = {'AIR': 'a-f-A-M-H-Q', 'GROUND': 'a-f-G-U-C', 'MARITIME': 'a-f-S-X-L'}

class TAKBridge(Node):
    def __init__(self):
        super().__init__('mos_tak_bridge')
        self.create_subscription(String, '/mos/heartbeat', self._hb, 10)
        self.create_subscription(String, '/mos/threats/alerts', self._threat, 10)
        self.assets = {}
        self.threats = {}
        self.cot_cache = {}
        self.udp_host = self.declare_parameter('tak_host', '239.2.3.1').value
        self.udp_port = self.declare_parameter('tak_port', 6969).value
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
        self.create_timer(2.0, self.broadcast)
        self.get_logger().info(f'[MOS TAK] Bridge online — UDP {self.udp_host}:{self.udp_port}')

    def _hb(self, msg):
        try:
            d = json.loads(msg.data)
            if d.get('asset_id'): self.assets[d['asset_id']] = d
        except: pass
    def _threat(self, msg):
        try:
            d = json.loads(msg.data)
            tid = d.get('contact_id', d.get('id', ''))
            if tid: self.threats[tid] = d
        except: pass

    def _iso(self, dt): return dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')

    def asset_to_cot(self, a):
        now = datetime.now(timezone.utc)
        stale = now + timedelta(seconds=30)
        uid = f'MOS-{a.get("callsign","UNK")}'
        cot_type = COT_TYPES.get(a.get('asset_type','GROUND'), 'a-f-G-U-C')
        alt = a.get('alt', 0) * 0.3048
        return (f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<event version="2.0" uid="{uid}" type="{cot_type}" '
            f'time="{self._iso(now)}" start="{self._iso(now)}" stale="{self._iso(stale)}" '
            f'how="m-g"><point lat="{a["lat"]:.6f}" lon="{a["lon"]:.6f}" '
            f'hae="{alt:.1f}" ce="10" le="10"/>'
            f'<detail><contact callsign="{a.get("callsign","UNK")}"/>'
            f'<__group name="Blue" role="Team Member"/>'
            f'<status battery="{a.get("battery",0):.0f}"/>'
            f'<track course="{a.get("heading",0):.1f}" speed="{a.get("speed",0):.2f}"/>'
            f'<remarks>MOS {a.get("asset_type","UNK")} | Mission: {a.get("mission_status",0)}</remarks>'
            f'</detail></event>')

    def threat_to_cot(self, t):
        now = datetime.now(timezone.utc)
        stale = now + timedelta(seconds=20)
        uid = f'MOS-THREAT-{t.get("contact_id","UNK")}'
        return (f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<event version="2.0" uid="{uid}" type="a-h-G" '
            f'time="{self._iso(now)}" start="{self._iso(now)}" stale="{self._iso(stale)}" '
            f'how="m-g"><point lat="{t.get("lat",0):.6f}" lon="{t.get("lon",0):.6f}" '
            f'hae="0" ce="50" le="50"/>'
            f'<detail><contact callsign="{uid}"/>'
            f'<__group name="Red" role="Team Member"/>'
            f'<remarks>{t.get("threat_type","UNK")} | {t.get("threat_level","UNK")}</remarks>'
            f'</detail></event>')

    def broadcast(self):
        for aid, a in self.assets.items():
            try:
                xml = self.asset_to_cot(a)
                self.cot_cache[aid] = xml
                self.sock.sendto(xml.encode(), (self.udp_host, self.udp_port))
            except: pass
        for tid, t in list(self.threats.items()):
            try:
                xml = self.threat_to_cot(t)
                self.cot_cache[f'T-{tid}'] = xml
                self.sock.sendto(xml.encode(), (self.udp_host, self.udp_port))
            except: pass

def main():
    rclpy.init(); node = TAKBridge(); rclpy.spin(node)
    node.destroy_node(); rclpy.shutdown()
