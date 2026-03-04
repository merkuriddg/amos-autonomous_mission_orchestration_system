#!/usr/bin/env python3
"""MOS AI Decision Engine — Phase 6: COA generation, threat response, autonomous planning"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, math, time

class AIDecisionEngine(Node):
    def __init__(self):
        super().__init__('mos_ai_decision_engine')
        self.create_subscription(String, '/mos/heartbeat', self._hb, 10)
        self.create_subscription(String, '/mos/threats/alerts', self._threat, 10)
        self.create_subscription(String, '/mos/sensor/detections', self._sensor, 10)
        self.create_subscription(String, '/mos/sustainment/status', self._sust, 10)
        self.create_subscription(String, '/mos/autonomy/state', self._auto, 10)
        self.create_subscription(String, '/mos/geofence/zones', self._gf, 10)
        self.coa_pub = self.create_publisher(String, '/mos/ai/coa', 10)
        self.wp_pub = self.create_publisher(String, '/mos/waypoints/assign', 10)
        self.swarm_pub = self.create_publisher(String, '/mos/swarm_command', 10)
        self.assets = {}
        self.threats = {}
        self.detections = []
        self.sustainment = []
        self.autonomy_level = 1
        self.geofences = []
        self.coas = []
        self.coa_counter = 0
        self.create_timer(5.0, self.evaluate)
        self.get_logger().info('[MOS AI] Decision Engine online — Phase 6')

    def _hb(self, msg):
        try:
            d = json.loads(msg.data)
            if d.get('asset_id'): self.assets[d['asset_id']] = d
        except: pass
    def _threat(self, msg):
        try:
            d = json.loads(msg.data)
            tid = d.get('contact_id', d.get('id', ''))
            if tid: d['_time'] = time.time(); self.threats[tid] = d
        except: pass
    def _sensor(self, msg):
        try: self.detections = json.loads(msg.data)
        except: pass
    def _sust(self, msg):
        try: self.sustainment = json.loads(msg.data)
        except: pass
    def _auto(self, msg):
        try: self.autonomy_level = json.loads(msg.data).get('current_level', 1)
        except: pass
    def _gf(self, msg):
        try: self.geofences = json.loads(msg.data)
        except: pass

    def evaluate(self):
        now = time.time()
        new_coas = []
        # 1. Threat proximity — reposition assets near HIGH/CRITICAL threats
        for tid, t in list(self.threats.items()):
            if now - t.get('_time', 0) > 30: continue
            tlat, tlon = t.get('lat', 0), t.get('lon', 0)
            level = t.get('threat_level', 'LOW')
            if level not in ('HIGH', 'CRITICAL'): continue
            nearby = [(a, self.assets[a]) for a in self.assets
                      if math.sqrt((self.assets[a]['lat']-tlat)**2+(self.assets[a]['lon']-tlon)**2) < 0.005]
            if nearby:
                coa = {'type': 'REPOSITION', 'priority': 5 if level == 'CRITICAL' else 4,
                       'description': f'{len(nearby)} assets near {level} threat {tid}',
                       'target': {'lat': tlat, 'lon': tlon},
                       'affected_assets': [a[0] for a in nearby],
                       'auto_exec': self.autonomy_level >= 3}
                new_coas.append(coa)
            coa2 = {'type': 'ISR_SWEEP', 'priority': 3,
                    'description': f'ISR sweep around {level} threat {tid}',
                    'target': {'lat': tlat, 'lon': tlon}, 'auto_exec': self.autonomy_level >= 4}
            new_coas.append(coa2)

        # 2. Sensor cluster analysis
        clusters = self._cluster_detections()
        for c in clusters:
            if c['count'] >= 3:
                new_coas.append({'type': 'INVESTIGATE', 'priority': 3,
                    'description': f'{c["count"]} sensor detections clustered',
                    'target': {'lat': c['lat'], 'lon': c['lon']},
                    'auto_exec': self.autonomy_level >= 4})

        # 3. Battery rotation
        warn = [s for s in self.sustainment if s.get('level') == 'WARNING']
        if len(warn) >= 3:
            new_coas.append({'type': 'RTB_ROTATION', 'priority': 2,
                'description': f'{len(warn)} assets low battery — rotate',
                'affected_assets': [s['asset_id'] for s in warn],
                'auto_exec': self.autonomy_level >= 3})

        # 4. Coverage gap — no active air ISR
        active_air = [a for a in self.assets.values()
                      if a.get('asset_type') == 'AIR' and a.get('mission_status', 0) > 0]
        if not active_air and len(self.assets) > 5:
            new_coas.append({'type': 'COVERAGE_GAP', 'priority': 2,
                'description': 'No active air ISR — recommend deployment',
                'auto_exec': self.autonomy_level >= 4})

        # 5. EW counter — SIGINT detections of jammers/emitters
        ew_dets = [d for d in self.detections
                   if d.get('sensor_type') == 'SIGINT' and d.get('classification') in ('JAMMER', 'EMITTER')]
        if ew_dets:
            new_coas.append({'type': 'EW_COUNTER', 'priority': 4,
                'description': f'{len(ew_dets)} hostile emitters detected — recommend EW response',
                'target': {'lat': ew_dets[0]['lat'], 'lon': ew_dets[0]['lon']},
                'auto_exec': self.autonomy_level >= 4})

        for coa in new_coas:
            self.coa_counter += 1
            coa['coa_id'] = f'COA-{self.coa_counter:04d}'
            coa['timestamp'] = now
            coa['status'] = 'PENDING'
            if coa.get('auto_exec') and coa['priority'] >= 4:
                self._execute(coa)
                coa['status'] = 'AUTO_EXECUTED'
            self.coas.append(coa)

        if len(self.coas) > 50: self.coas = self.coas[-50:]
        m = String(); m.data = json.dumps(self.coas[-20:]); self.coa_pub.publish(m)

    def _execute(self, coa):
        if coa['type'] == 'REPOSITION':
            tgt = coa.get('target', {})
            for aid in coa.get('affected_assets', []):
                a = self.assets.get(aid)
                if not a: continue
                dlat = a['lat'] - tgt.get('lat', a['lat'])
                dlon = a['lon'] - tgt.get('lon', a['lon'])
                dist = max(math.sqrt(dlat**2 + dlon**2), 0.0001)
                nl = a['lat'] + (dlat/dist) * 0.005
                no = a['lon'] + (dlon/dist) * 0.005
                if not self._in_keepout(nl, no):
                    m = String()
                    m.data = json.dumps({'asset_id': aid, 'waypoints': [{'lat': nl, 'lon': no}], 'loop': False})
                    self.wp_pub.publish(m)
                    self.get_logger().warn(f'[AI] AUTO-REPOSITION: {a.get("callsign","?")}')

    def _in_keepout(self, lat, lon):
        for z in self.geofences:
            if z.get('type') == 'KEEP_OUT' and z.get('active', True):
                if self._pip(lat, lon, z.get('polygon', [])): return True
        return False

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

    def _cluster_detections(self):
        clusters = []; used = set()
        for i, d in enumerate(self.detections):
            if i in used: continue
            cl = [d]; used.add(i)
            for j, d2 in enumerate(self.detections):
                if j in used: continue
                if math.sqrt((d['lat']-d2['lat'])**2+(d['lon']-d2['lon'])**2) < 0.002:
                    cl.append(d2); used.add(j)
            if len(cl) >= 2:
                clusters.append({'lat': sum(c['lat'] for c in cl)/len(cl),
                                 'lon': sum(c['lon'] for c in cl)/len(cl), 'count': len(cl)})
        return clusters

def main():
    rclpy.init(); node = AIDecisionEngine(); rclpy.spin(node)
    node.destroy_node(); rclpy.shutdown()
