#!/usr/bin/env python3
"""
MOS SIGINT Collector — Signals Intelligence Collection & Classification
Detects, classifies, and geolocates RF emitters across the spectrum.
Simulates realistic RF environment with known and unknown signals.
Supports direction finding via multi-asset angle-of-arrival.
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, time, random, math, hashlib

SIGNAL_TYPES = [
    {'type':'COMMS_VHF','freq':(136,174),'bw':(0.012,0.025),'power':(-60,-30),'threat':0.6},
    {'type':'COMMS_UHF','freq':(400,512),'bw':(0.025,0.1),'power':(-70,-35),'threat':0.8},
    {'type':'WIFI','freq':(2412,2462),'bw':(20,40),'power':(-80,-40),'threat':0.4},
    {'type':'WIFI_5G','freq':(5180,5825),'bw':(40,80),'power':(-85,-50),'threat':0.4},
    {'type':'BLUETOOTH','freq':(2402,2480),'bw':(1,2),'power':(-90,-60),'threat':0.2},
    {'type':'CELLULAR','freq':(700,900),'bw':(10,20),'power':(-65,-30),'threat':0.5},
    {'type':'CELLULAR_AWS','freq':(1700,2100),'bw':(10,20),'power':(-65,-30),'threat':0.5},
    {'type':'RADAR','freq':(2700,3500),'bw':(1,5),'power':(-50,-10),'threat':0.9},
    {'type':'DRONE_C2','freq':(900,930),'bw':(0.5,2),'power':(-75,-45),'threat':1.0},
    {'type':'DRONE_C2_5G','freq':(5725,5850),'bw':(10,20),'power':(-70,-40),'threat':1.0},
    {'type':'DRONE_VIDEO','freq':(5800,5900),'bw':(20,40),'power':(-65,-35),'threat':0.9},
    {'type':'GPS_INTERFERENCE','freq':(1575.42,1575.42),'bw':(1,10),'power':(-50,-20),'threat':1.0},
    {'type':'ISM_LORA','freq':(902,928),'bw':(0.125,0.5),'power':(-100,-70),'threat':0.1},
    {'type':'P25','freq':(764,870),'bw':(0.0125,0.0125),'power':(-70,-40),'threat':0.3},
    {'type':'DMR','freq':(400,470),'bw':(0.0125,0.0125),'power':(-70,-35),'threat':0.3},
    {'type':'ADS_B','freq':(1090,1090),'bw':(0.05,0.05),'power':(-60,-20),'threat':0.1},
    {'type':'AIS','freq':(161.975,162.025),'bw':(0.025,0.025),'power':(-70,-30),'threat':0.1},
    {'type':'SATCOM_DL','freq':(1525,1559),'bw':(0.025,0.2),'power':(-120,-90),'threat':0.5},
    {'type':'REMOTE_ID','freq':(2400,2484),'bw':(1,5),'power':(-80,-55),'threat':0.3},
    {'type':'UNKNOWN','freq':(100,5900),'bw':(0.1,5),'power':(-90,-50),'threat':0.7},
]

CLASSIFICATIONS = ['FRIENDLY','NEUTRAL','SUSPECT','HOSTILE','JAMMER']
CLASS_WEIGHTS = [0.20, 0.35, 0.25, 0.15, 0.05]

MODULATIONS = ['FM','AM','SSB','OFDM','FHSS','DSSS','FSK','GFSK','QAM','PSK','CHIRP','PULSE','UNKNOWN']

BASE_LAT, BASE_LON = 27.8506, -82.5214

class SIGINTCollector(Node):
    def __init__(self):
        super().__init__('sigint_collector')
        self.emitter_pub = self.create_publisher(String, '/mos/ew/emitters', 10)
        self.signal_pub = self.create_publisher(String, '/mos/ew/signals', 10)
        self.bearing_pub = self.create_publisher(String, '/mos/ew/bearings', 10)
        self.create_subscription(String, '/mos/heartbeat', self._on_heartbeat, 10)
        self.emitters = {}
        self.signal_db = []
        self.asset_positions = {}
        self.emitter_counter = 0
        self.create_timer(8.0, self._spawn_emitter)
        self.create_timer(3.0, self._update_emitters)
        self.create_timer(5.0, self._compute_bearings)
        self.create_timer(2.0, self._classify_signals)
        self.get_logger().info('📡 SIGINT Collector online — Listening across the spectrum...')

    def _on_heartbeat(self, msg):
        d = json.loads(msg.data)
        self.asset_positions[d.get('asset_id','')] = {
            'lat': d.get('lat',0), 'lon': d.get('lon',0), 'alt': d.get('alt',0)}

    def _spawn_emitter(self):
        if len(self.emitters) >= 50:
            oldest = min(self.emitters, key=lambda k: self.emitters[k].get('first_seen',0))
            del self.emitters[oldest]
        sig = random.choice(SIGNAL_TYPES)
        self.emitter_counter += 1
        freq = random.uniform(sig['freq'][0], sig['freq'][1])
        eid = f"EMT-{self.emitter_counter:04d}"
        classification = random.choices(CLASSIFICATIONS, CLASS_WEIGHTS)[0]
        # Hostile emitters spawn closer; neutral farther
        dist_km = random.uniform(0.1, 1.0) if classification in ['HOSTILE','JAMMER'] \
                  else random.uniform(0.5, 5.0)
        angle = random.uniform(0, 2*math.pi)
        lat = BASE_LAT + (dist_km/111.0)*math.cos(angle)
        lon = BASE_LON + (dist_km/(111.0*math.cos(math.radians(BASE_LAT))))*math.sin(angle)
        emitter = {
            'emitter_id': eid,
            'signal_type': sig['type'],
            'classification': classification,
            'freq_mhz': round(freq, 4),
            'bandwidth_mhz': round(random.uniform(sig['bw'][0], sig['bw'][1]), 4),
            'power_dbm': round(random.uniform(sig['power'][0], sig['power'][1]), 1),
            'modulation': random.choice(MODULATIONS),
            'lat': round(lat, 6), 'lon': round(lon, 6),
            'alt_m': random.uniform(0, 100) if 'DRONE' in sig['type'] else 0,
            'heading': round(random.uniform(0, 360), 1),
            'speed_mps': round(random.uniform(0, 15), 1) if classification in ['HOSTILE','SUSPECT'] else 0,
            'threat_score': round(sig['threat'] * (1.5 if classification == 'HOSTILE' else
                                  2.0 if classification == 'JAMMER' else 1.0), 2),
            'first_seen': time.time(),
            'last_seen': time.time(),
            'confidence': round(random.uniform(0.5, 0.99), 2),
            'geolocation_fix': random.choice(['NONE','ROUGH','GOOD','PRECISE']),
            'detected_by': random.choice(list(self.asset_positions.keys())) if self.asset_positions else 'MVRX-A03',
            'notes': self._generate_notes(sig['type'], classification)
        }
        self.emitters[eid] = emitter
        msg = String(); msg.data = json.dumps(emitter)
        self.emitter_pub.publish(msg)
        icon = '🔴' if classification in ['HOSTILE','JAMMER'] else '🟡' if classification == 'SUSPECT' else '🟢'
        self.get_logger().info(f'{icon} EMITTER {eid}: {sig["type"]} | {freq:.3f} MHz | '
                               f'{emitter["power_dbm"]} dBm | {classification}')

    def _generate_notes(self, sig_type, classification):
        notes = {
            'DRONE_C2': 'Possible hostile UAS command link detected',
            'DRONE_VIDEO': 'FPV video downlink — likely surveillance drone',
            'GPS_INTERFERENCE': 'GPS L1 interference — check navigation integrity',
            'RADAR': 'Search radar emission — possible air defense',
            'COMMS_UHF': 'UHF tactical comms — monitoring for COMSEC violations',
            'WIFI': 'WiFi AP detected — potential network entry point',
            'CELLULAR': 'Cellular emission — may indicate personnel with phones',
            'P25': 'P25 trunked radio — law enforcement or security',
            'UNKNOWN': 'Unclassified emission — requires analysis',
        }
        base = notes.get(sig_type, f'{sig_type} emission detected')
        if classification == 'HOSTILE': base += ' [CONFIRMED HOSTILE]'
        if classification == 'JAMMER': base += ' [ACTIVE JAMMING SOURCE]'
        return base

    def _update_emitters(self):
        now = time.time()
        to_remove = []
        for eid, e in self.emitters.items():
            age = now - e['first_seen']
            if age > 120 and random.random() < 0.1:
                to_remove.append(eid)
                continue
            # Mobile emitters move
            if e.get('speed_mps', 0) > 0:
                hdg_rad = math.radians(e['heading'])
                dt = 3.0
                dlat = (e['speed_mps'] * dt / 111000.0) * math.cos(hdg_rad)
                dlon = (e['speed_mps'] * dt / (111000.0 * math.cos(math.radians(e['lat'])))) * math.sin(hdg_rad)
                e['lat'] += dlat
                e['lon'] += dlon
                e['heading'] = (e['heading'] + random.uniform(-10, 10)) % 360
            # Power fluctuation
            e['power_dbm'] += random.uniform(-2, 2)
            e['last_seen'] = now
            msg = String(); msg.data = json.dumps(e)
            self.emitter_pub.publish(msg)
        for eid in to_remove:
            del self.emitters[eid]

    def _compute_bearings(self):
        ew_assets = {k:v for k,v in self.asset_positions.items()
                     if k in ['MVRX-A03','MVRX-G03','AWACS-1','AWACS-2']}
        if not ew_assets: return
        hostile = [e for e in self.emitters.values()
                   if e.get('classification') in ['HOSTILE','JAMMER','SUSPECT']]
        bearings = []
        for e in hostile[:10]:
            for aid, apos in ew_assets.items():
                dlat = e['lat'] - apos['lat']
                dlon = e['lon'] - apos['lon']
                true_bearing = math.degrees(math.atan2(dlon, dlat)) % 360
                measured = (true_bearing + random.uniform(-5, 5)) % 360
                bearings.append({
                    'emitter_id': e['emitter_id'], 'asset_id': aid,
                    'bearing_deg': round(measured, 1),
                    'from_lat': apos['lat'], 'from_lon': apos['lon'],
                    'timestamp': time.time()
                })
        if bearings:
            msg = String(); msg.data = json.dumps({'bearings': bearings})
            self.bearing_pub.publish(msg)

    def _classify_signals(self):
        for eid, e in list(self.emitters.items()):
            signal = {
                'signal_id': f"SIG-{hashlib.md5(eid.encode()).hexdigest()[:8]}",
                'emitter_id': eid,
                'freq_mhz': e['freq_mhz'],
                'bandwidth_mhz': e['bandwidth_mhz'],
                'power_dbm': e['power_dbm'],
                'modulation': e['modulation'],
                'signal_type': e['signal_type'],
                'classification': e['classification'],
                'threat_score': e['threat_score'],
                'timestamp': time.time()
            }
            self.signal_db.append(signal)
            if len(self.signal_db) > 500:
                self.signal_db = self.signal_db[-500:]
            msg = String(); msg.data = json.dumps(signal)
            self.signal_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = SIGINTCollector()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node()
