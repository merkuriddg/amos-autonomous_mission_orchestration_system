import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, math, random, time

# MacDill AFB, Tampa FL — 27.8497° N, 82.5212° W
BASE_LAT = 27.8497
BASE_LON = -82.5212

ASSETS = [
    # AIR — 10
    {'id': 'MVRX-A01', 'type': 'AIR', 'callsign': 'HAWK-1',      'lat': BASE_LAT + 0.002, 'lon': BASE_LON + 0.001, 'alt': 120.0},
    {'id': 'MVRX-A02', 'type': 'AIR', 'callsign': 'HAWK-2',      'lat': BASE_LAT + 0.003, 'lon': BASE_LON - 0.001, 'alt': 130.0},
    {'id': 'MVRX-A03', 'type': 'AIR', 'callsign': 'HAWK-3',      'lat': BASE_LAT + 0.004, 'lon': BASE_LON + 0.002, 'alt': 110.0},
    {'id': 'MVRX-A04', 'type': 'AIR', 'callsign': 'RAVEN-1',     'lat': BASE_LAT - 0.001, 'lon': BASE_LON - 0.002, 'alt': 90.0},
    {'id': 'MVRX-A05', 'type': 'AIR', 'callsign': 'RAVEN-2',     'lat': BASE_LAT - 0.002, 'lon': BASE_LON + 0.003, 'alt': 95.0},
    {'id': 'MVRX-A06', 'type': 'AIR', 'callsign': 'RAVEN-3',     'lat': BASE_LAT + 0.001, 'lon': BASE_LON - 0.003, 'alt': 85.0},
    {'id': 'MVRX-A07', 'type': 'AIR', 'callsign': 'TALON-1',     'lat': BASE_LAT + 0.005, 'lon': BASE_LON + 0.000, 'alt': 150.0},
    {'id': 'MVRX-A08', 'type': 'AIR', 'callsign': 'TALON-2',     'lat': BASE_LAT + 0.006, 'lon': BASE_LON - 0.002, 'alt': 145.0},
    {'id': 'MVRX-A09', 'type': 'AIR', 'callsign': 'OVERWATCH-1', 'lat': BASE_LAT + 0.007, 'lon': BASE_LON + 0.001, 'alt': 200.0},
    {'id': 'MVRX-A10', 'type': 'AIR', 'callsign': 'OVERWATCH-2', 'lat': BASE_LAT + 0.008, 'lon': BASE_LON - 0.001, 'alt': 210.0},
    # GROUND — 12
    {'id': 'MVRX-G01', 'type': 'GROUND', 'callsign': 'WARHOUND-1',  'lat': BASE_LAT - 0.003, 'lon': BASE_LON + 0.001, 'alt': 0.0},
    {'id': 'MVRX-G02', 'type': 'GROUND', 'callsign': 'WARHOUND-2',  'lat': BASE_LAT - 0.004, 'lon': BASE_LON - 0.001, 'alt': 0.0},
    {'id': 'MVRX-G03', 'type': 'GROUND', 'callsign': 'WARHOUND-3',  'lat': BASE_LAT - 0.005, 'lon': BASE_LON + 0.002, 'alt': 0.0},
    {'id': 'MVRX-G04', 'type': 'GROUND', 'callsign': 'WARHOUND-4',  'lat': BASE_LAT - 0.002, 'lon': BASE_LON - 0.003, 'alt': 0.0},
    {'id': 'MVRX-G05', 'type': 'GROUND', 'callsign': 'MULE-1',      'lat': BASE_LAT - 0.006, 'lon': BASE_LON + 0.000, 'alt': 0.0},
    {'id': 'MVRX-G06', 'type': 'GROUND', 'callsign': 'MULE-2',      'lat': BASE_LAT - 0.007, 'lon': BASE_LON - 0.002, 'alt': 0.0},
    {'id': 'MVRX-G07', 'type': 'GROUND', 'callsign': 'MULE-3',      'lat': BASE_LAT - 0.008, 'lon': BASE_LON + 0.001, 'alt': 0.0},
    {'id': 'MVRX-G08', 'type': 'GROUND', 'callsign': 'SENTRY-1',    'lat': BASE_LAT + 0.000, 'lon': BASE_LON + 0.004, 'alt': 0.0},
    {'id': 'MVRX-G09', 'type': 'GROUND', 'callsign': 'SENTRY-2',    'lat': BASE_LAT + 0.001, 'lon': BASE_LON + 0.005, 'alt': 0.0},
    {'id': 'MVRX-G10', 'type': 'GROUND', 'callsign': 'SENTRY-3',    'lat': BASE_LAT - 0.001, 'lon': BASE_LON + 0.006, 'alt': 0.0},
    {'id': 'MVRX-G11', 'type': 'GROUND', 'callsign': 'SENTRY-4',    'lat': BASE_LAT - 0.003, 'lon': BASE_LON + 0.005, 'alt': 0.0},
    {'id': 'MVRX-G12', 'type': 'GROUND', 'callsign': 'PATHFINDER-1','lat': BASE_LAT - 0.004, 'lon': BASE_LON + 0.003, 'alt': 0.0},
    # MARITIME — 3 (in Tampa Bay waters)
    {'id': 'MVRX-M01', 'type': 'MARITIME', 'callsign': 'TRITON-1', 'lat': BASE_LAT - 0.010, 'lon': BASE_LON - 0.005, 'alt': 0.0},
    {'id': 'MVRX-M02', 'type': 'MARITIME', 'callsign': 'TRITON-2', 'lat': BASE_LAT - 0.012, 'lon': BASE_LON + 0.004, 'alt': 0.0},
    {'id': 'MVRX-M03', 'type': 'MARITIME', 'callsign': 'TRITON-3', 'lat': BASE_LAT - 0.014, 'lon': BASE_LON - 0.003, 'alt': 0.0},
    # AWACS — 2 (Autonomous Airborne C2 Nodes)
    {'id': 'MVRX-W01', 'type': 'AIR', 'callsign': 'AWACS-1', 'lat': BASE_LAT + 0.000, 'lon': BASE_LON + 0.000, 'alt': 300.0},
    {'id': 'MVRX-W02', 'type': 'AIR', 'callsign': 'AWACS-2', 'lat': BASE_LAT + 0.010, 'lon': BASE_LON - 0.008, 'alt': 280.0},
]

SPEED = {'AIR': 0.0003, 'GROUND': 0.00012, 'MARITIME': 0.00015}


class SimulatedPlatoon(Node):
    def __init__(self):
        super().__init__('mos_simulated_platoon')
        self.pub = self.create_publisher(String, '/mos/heartbeat', 10)
        self.sub_tasks = self.create_subscription(
            String, '/mos/tasks/orders', self.on_task, 10)
        self.sub_swarm = self.create_subscription(
            String, '/mos/swarm/command', self.on_swarm, 10)
        self.sub_waypoints = self.create_subscription(
            String, '/mos/waypoints/assign', self.on_waypoints, 10)

        self.state = []
        for a in ASSETS:
            self.state.append({
                **a,
                'base_lat': a['lat'],
                'base_lon': a['lon'],
                'heading': random.uniform(0, 360),
                'speed': SPEED[a['type']],
                'battery': random.uniform(70, 100),
                'comms': random.uniform(-80, -40),
                'autonomy_mode': 'ASSISTED',
                'mission_status': 0,
                'target_lat': None,
                'target_lon': None,
                'task_timer': 0,
                'waypoints': [],
                'wp_index': 0,
                'wp_loop': False,
            })

        self.timer = self.create_timer(0.5, self.tick)
        self.get_logger().info(
            f'[MOS SIM] Platoon + AWACS online — {len(self.state)} assets at MacDill AFB')

    def on_waypoints(self, msg):
        try:
            data = json.loads(msg.data)
            asset_id = data.get('asset_id')
            waypoints = data.get('waypoints', [])
            cancel = data.get('cancel', False)
            loop = data.get('loop', False)

            for asset in self.state:
                if asset['id'] == asset_id:
                    if cancel or not waypoints:
                        asset['waypoints'] = []
                        asset['wp_index'] = 0
                        asset['wp_loop'] = False
                        asset['target_lat'] = None
                        asset['target_lon'] = None
                        asset['mission_status'] = 0
                        asset['task_timer'] = 0
                        self.get_logger().info(
                            f'  [SIM] {asset["callsign"]} -> HOLD')
                    else:
                        asset['waypoints'] = waypoints
                        asset['wp_index'] = 0
                        asset['wp_loop'] = loop
                        asset['target_lat'] = waypoints[0]['lat']
                        asset['target_lon'] = waypoints[0]['lon']
                        asset['mission_status'] = 1
                        asset['task_timer'] = 0
                        self.get_logger().info(
                            f'  [SIM] {asset["callsign"]} -> '
                            f'{len(waypoints)} waypoints (loop={loop})')
                    break
        except json.JSONDecodeError:
            pass

    def on_task(self, msg):
        try:
            data = json.loads(msg.data)
            domain = data.get('required_domain', 'GROUND')
            target_lat = data.get('target_lat', BASE_LAT)
            target_lon = data.get('target_lon', BASE_LON)

            for asset in self.state:
                if asset['type'] == domain and asset['mission_status'] == 0:
                    asset['mission_status'] = 1
                    asset['target_lat'] = target_lat
                    asset['target_lon'] = target_lon
                    asset['task_timer'] = 0
                    asset['waypoints'] = []
                    asset['wp_index'] = 0
                    self.get_logger().info(
                        f'  [SIM] {asset["callsign"]} -> EN_ROUTE to '
                        f'({target_lat:.4f}, {target_lon:.4f})')
                    break
        except json.JSONDecodeError:
            pass

    def on_swarm(self, msg):
        try:
            data = json.loads(msg.data)
            behavior = data.get('behavior', 'HOLD')
            domain = data.get('domain', 'ALL')
            self.get_logger().info(
                f'[SIM] Swarm command: {behavior} for {domain}')

            for asset in self.state:
                if domain != 'ALL' and asset['type'] != domain:
                    continue

                asset['waypoints'] = []
                asset['wp_index'] = 0
                asset['wp_loop'] = False

                if behavior == 'RTB':
                    asset['target_lat'] = asset['base_lat']
                    asset['target_lon'] = asset['base_lon']
                    asset['mission_status'] = 1
                    asset['task_timer'] = 0
                elif behavior == 'HOLD':
                    asset['target_lat'] = None
                    asset['target_lon'] = None
                    asset['mission_status'] = 0
                    asset['task_timer'] = 0
                elif behavior == 'SCATTER':
                    asset['target_lat'] = asset['lat'] + random.uniform(-0.008, 0.008)
                    asset['target_lon'] = asset['lon'] + random.uniform(-0.008, 0.008)
                    asset['mission_status'] = 1
                    asset['task_timer'] = 0
        except json.JSONDecodeError:
            pass

    def tick(self):
        for asset in self.state:
            if asset['mission_status'] == 1 and asset['target_lat'] is not None:
                dlat = asset['target_lat'] - asset['lat']
                dlon = asset['target_lon'] - asset['lon']
                dist = math.sqrt(dlat**2 + dlon**2)

                if dist < 0.0005:
                    wps = asset.get('waypoints', [])
                    wpi = asset.get('wp_index', 0)

                    if wps and wpi < len(wps) - 1:
                        asset['wp_index'] += 1
                        nxt = wps[asset['wp_index']]
                        asset['target_lat'] = nxt['lat']
                        asset['target_lon'] = nxt['lon']
                    elif asset.get('wp_loop') and wps:
                        asset['wp_index'] = 0
                        nxt = wps[0]
                        asset['target_lat'] = nxt['lat']
                        asset['target_lon'] = nxt['lon']
                    else:
                        asset['lat'] = asset['target_lat']
                        asset['lon'] = asset['target_lon']
                        asset['mission_status'] = 2
                        asset['task_timer'] = 0
                else:
                    speed = asset['speed']
                    asset['lat'] += (dlat / dist) * speed
                    asset['lon'] += (dlon / dist) * speed
                    asset['heading'] = math.degrees(
                        math.atan2(dlon, dlat)) % 360

            elif asset['mission_status'] == 2:
                asset['task_timer'] += 1
                if asset['task_timer'] > 30:
                    asset['mission_status'] = 3
                    asset['task_timer'] = 0

            elif asset['mission_status'] == 3:
                asset['task_timer'] += 1
                if asset['task_timer'] > 10:
                    asset['mission_status'] = 0
                    asset['target_lat'] = None
                    asset['target_lon'] = None
                    asset['task_timer'] = 0
                    asset['waypoints'] = []
                    asset['wp_index'] = 0

            if asset['mission_status'] in [1, 2]:
                asset['battery'] = max(5.0, asset['battery'] - 0.02)

            asset['comms'] = max(-90, min(-30,
                asset['comms'] + random.uniform(-0.5, 0.5)))

            if asset['mission_status'] == 0:
                asset['lat'] += random.uniform(-0.00002, 0.00002)
                asset['lon'] += random.uniform(-0.00002, 0.00002)

            msg = String()
            msg.data = json.dumps({
                'asset_id': asset['id'],
                'asset_type': asset['type'],
                'callsign': asset['callsign'],
                'lat': round(asset['lat'], 6),
                'lon': round(asset['lon'], 6),
                'alt': asset['alt'],
                'heading': round(asset['heading'], 1),
                'speed': asset['speed'],
                'battery': round(asset['battery'], 1),
                'comms': round(asset['comms'], 1),
                'autonomy_mode': asset['autonomy_mode'],
                'mission_status': asset['mission_status'],
                'base_lat': asset['base_lat'],
                'base_lon': asset['base_lon'],
                'wp_count': len(asset.get('waypoints', [])),
                'wp_index': asset.get('wp_index', 0),
                'wp_loop': asset.get('wp_loop', False),
                'waypoints': asset.get('waypoints', []),
            })
            self.pub.publish(msg)


def main():
    rclpy.init()
    node = SimulatedPlatoon()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
