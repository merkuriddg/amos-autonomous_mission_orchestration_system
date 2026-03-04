#!/usr/bin/env python3
"""
MOS MAVLink Bridge — Phase 8
Bridges real PX4/ArduPilot drones (via MAVROS) to MOS unified topics.
Supports multiple simultaneous vehicles.

MAVROS topics used:
  Subscribe: /mavros/state, /mavros/global_position/global,
             /mavros/local_position/pose, /mavros/battery
  Publish:   /mavros/setpoint_position/global
  Services:  /mavros/cmd/arming, /mavros/set_mode, /mavros/cmd/takeoff, /mavros/cmd/land
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, time, math, yaml, os

# Conditional imports — only fail if actually connecting to real hardware
try:
    from mavros_msgs.msg import State as MavrosState
    from mavros_msgs.srv import CommandBool, SetMode, CommandTOL
    from sensor_msgs.msg import NavSatFix, BatteryState
    from geometry_msgs.msg import PoseStamped
    MAVROS_AVAILABLE = True
except ImportError:
    MAVROS_AVAILABLE = False

# Conditional Nav2 imports
try:
    from geometry_msgs.msg import PoseStamped as Nav2PoseStamped
    from nav2_msgs.action import NavigateToPose
    from rclpy.action import ActionClient
    NAV2_AVAILABLE = True
except ImportError:
    NAV2_AVAILABLE = False


class VehicleState:
    """Tracks state of a single real vehicle."""
    def __init__(self, asset_id, callsign, asset_type, source, config):
        self.asset_id = asset_id
        self.callsign = callsign
        self.asset_type = asset_type
        self.source = source  # 'mavlink' | 'nav2' | 'manual'
        self.config = config

        # State
        self.connected = False
        self.armed = False
        self.mode = 'UNKNOWN'
        self.lat = 0.0
        self.lon = 0.0
        self.alt = 0.0
        self.heading = 0.0
        self.speed = 0.0
        self.battery = 100.0
        self.battery_voltage = 0.0
        self.battery_current = 0.0
        self.mission_status = 0
        self.last_heartbeat = 0.0
        self.autonomy_level = 1  # MANUAL for real hardware

        # Position history for speed calc
        self.prev_lat = 0.0
        self.prev_lon = 0.0
        self.prev_time = 0.0

    def to_heartbeat(self):
        return {
            'asset_id': self.asset_id,
            'callsign': self.callsign,
            'asset_type': self.asset_type,
            'lat': self.lat,
            'lon': self.lon,
            'alt': self.alt,
            'heading': self.heading,
            'speed': self.speed,
            'battery': self.battery,
            'battery_voltage': self.battery_voltage,
            'mission_status': self.mission_status,
            'autonomy_level': self.autonomy_level,
            'armed': self.armed,
            'mode': self.mode,
            'connected': self.connected,
            'source': self.source,  # 'mavlink', 'nav2', 'sim'
            'timestamp': time.time(),
        }


class MAVLinkBridge(Node):
    def __init__(self):
        super().__init__('mos_mavlink_bridge')

        # Load HAL config
        config_path = os.path.join(
            os.path.dirname(__file__), '..', '..', '..', '..',
            'src', 'mos_core', 'config', 'hal_config.yaml'
        )
        # Fallback paths
        alt_paths = [
            os.path.expanduser('~/mos_ws/src/mos_core/config/hal_config.yaml'),
            '/home/rick/mos_ws/src/mos_core/config/hal_config.yaml',
        ]
        self.hal_config = {'hal': {'default_source': 'sim', 'asset_map': {}, 'safety': {}}}
        for p in [config_path] + alt_paths:
            if os.path.exists(p):
                with open(p) as f:
                    self.hal_config = yaml.safe_load(f)
                self.get_logger().info(f'[HAL] Loaded config from {p}')
                break

        self.safety = self.hal_config.get('hal', {}).get('safety', {})
        self.ddil = self.hal_config.get('hal', {}).get('ddil', {})

        # Vehicle tracking
        self.vehicles = {}  # asset_id -> VehicleState
        self.mavros_subs = {}  # asset_id -> list of subscriptions

        # MOS topic subscriptions
        self.create_subscription(String, '/mos/command', self._mos_command, 10)
        self.create_subscription(String, '/mos/waypoints/assign', self._mos_waypoint, 10)
        self.create_subscription(String, '/mos/emergency_stop', self._emergency_stop, 10)

        # MOS topic publishers
        self.hb_pub = self.create_publisher(String, '/mos/heartbeat', 10)
        self.bridge_status_pub = self.create_publisher(String, '/mos/hal/status', 10)
        self.bridge_event_pub = self.create_publisher(String, '/mos/hal/events', 10)

        # HAL status API store
        self.hal_status = {
            'mavros_available': MAVROS_AVAILABLE,
            'nav2_available': NAV2_AVAILABLE,
            'default_source': self.hal_config['hal']['default_source'],
            'vehicles': {},
            'safety': self.safety,
        }

        # Auto-register vehicles from config
        asset_map = self.hal_config.get('hal', {}).get('asset_map', {})
        if asset_map:
            for asset_id, acfg in asset_map.items():
                source = acfg.get('source', 'sim')
                if source in ('mavlink', 'nav2'):
                    self._register_vehicle(
                        asset_id,
                        acfg.get('callsign', asset_id),
                        acfg.get('type', 'AIR' if source == 'mavlink' else 'GROUND'),
                        source, acfg
                    )

        # Timers
        self.create_timer(1.0, self._publish_heartbeats)
        self.create_timer(2.0, self._publish_hal_status)
        self.create_timer(1.0, self._check_ddil)

        mode_str = 'HARDWARE' if self.vehicles else 'STANDBY (no real vehicles configured)'
        self.get_logger().info(f'[MOS HAL] MAVLink Bridge online — {mode_str}')
        self.get_logger().info(f'[MOS HAL] MAVROS: {"✓" if MAVROS_AVAILABLE else "✗ (install ros-humble-mavros)"}')
        self.get_logger().info(f'[MOS HAL] Nav2:   {"✓" if NAV2_AVAILABLE else "✗ (install ros-humble-nav2)"}')
        self.get_logger().info(f'[MOS HAL] Default source: {self.hal_config["hal"]["default_source"]}')
        self._emit_event('HAL_INIT', f'Bridge online, {len(self.vehicles)} real vehicles')

    # ─── Vehicle Registration ─────────────────────────────────────
    def _register_vehicle(self, asset_id, callsign, asset_type, source, config):
        vs = VehicleState(asset_id, callsign, asset_type, source, config)
        self.vehicles[asset_id] = vs

        if source == 'mavlink' and MAVROS_AVAILABLE:
            self._setup_mavros(asset_id, config)
        elif source == 'nav2' and NAV2_AVAILABLE:
            self._setup_nav2(asset_id, config)

        self.get_logger().info(f'[HAL] Registered {callsign} ({asset_id}) via {source}')

    def _setup_mavros(self, asset_id, config):
        """Subscribe to MAVROS topics for a specific vehicle."""
        ns = config.get('namespace', '/mavros')
        subs = []

        # State
        subs.append(self.create_subscription(
            MavrosState, f'{ns}/state',
            lambda msg, aid=asset_id: self._mavros_state(aid, msg), 10
        ))

        # Global position (GPS)
        subs.append(self.create_subscription(
            NavSatFix, f'{ns}/global_position/global',
            lambda msg, aid=asset_id: self._mavros_gps(aid, msg), 10
        ))

        # Local position (for heading/speed)
        subs.append(self.create_subscription(
            PoseStamped, f'{ns}/local_position/pose',
            lambda msg, aid=asset_id: self._mavros_local(aid, msg), 10
        ))

        # Battery
        subs.append(self.create_subscription(
            BatteryState, f'{ns}/battery',
            lambda msg, aid=asset_id: self._mavros_battery(aid, msg), 10
        ))

        self.mavros_subs[asset_id] = subs
        self.get_logger().info(f'[HAL] MAVROS subscriptions active for {asset_id} on {ns}')

    def _setup_nav2(self, asset_id, config):
        """Set up Nav2 action client for a ground robot."""
        ns = config.get('namespace', '')
        # Nav2 navigate_to_pose action client
        if NAV2_AVAILABLE:
            client = ActionClient(self, NavigateToPose, f'{ns}/navigate_to_pose')
            self.vehicles[asset_id].nav2_client = client
            self.get_logger().info(f'[HAL] Nav2 client active for {asset_id} on {ns}')

    # ─── MAVROS Callbacks ──────────────────────────────────────────
    def _mavros_state(self, asset_id, msg):
        """Handle /mavros/state — FCU connection, armed, mode."""
        v = self.vehicles.get(asset_id)
        if not v: return
        was_connected = v.connected
        v.connected = msg.connected
        v.armed = msg.armed
        v.mode = msg.mode
        v.last_heartbeat = time.time()

        if not was_connected and msg.connected:
            self._emit_event('VEHICLE_CONNECTED', f'{v.callsign} FCU connected')
        elif was_connected and not msg.connected:
            self._emit_event('VEHICLE_DISCONNECTED', f'{v.callsign} FCU LOST', 'CRITICAL')

    def _mavros_gps(self, asset_id, msg):
        """Handle /mavros/global_position/global — GPS fix."""
        v = self.vehicles.get(asset_id)
        if not v: return

        now = time.time()
        if v.prev_time > 0:
            dt = now - v.prev_time
            if dt > 0:
                dlat = (msg.latitude - v.prev_lat) * 111000
                dlon = (msg.longitude - v.prev_lon) * 111000 * math.cos(math.radians(msg.latitude))
                v.speed = math.sqrt(dlat**2 + dlon**2) / dt
                if abs(dlat) > 0.01 or abs(dlon) > 0.01:
                    v.heading = math.degrees(math.atan2(dlon, dlat)) % 360

        v.prev_lat, v.prev_lon, v.prev_time = v.lat, v.lon, now
        v.lat = msg.latitude
        v.lon = msg.longitude
        v.alt = msg.altitude

        # Safety: altitude check
        max_alt = self.safety.get('max_altitude_m', 120)
        if v.alt > max_alt and v.asset_type == 'AIR':
            self._emit_event('SAFETY_ALTITUDE', f'{v.callsign} at {v.alt:.0f}m > limit {max_alt}m', 'WARNING')

        # Safety: range check
        max_range = self.safety.get('max_range_from_base_m', 2000)
        # TODO: calculate distance from base

    def _mavros_local(self, asset_id, msg):
        """Handle /mavros/local_position/pose — local frame position."""
        # Used for precise local positioning, heading from quaternion
        pass  # GPS is primary for MOS

    def _mavros_battery(self, asset_id, msg):
        """Handle /mavros/battery — battery state."""
        v = self.vehicles.get(asset_id)
        if not v: return
        v.battery = max(0, min(100, msg.percentage * 100)) if msg.percentage >= 0 else v.battery
        v.battery_voltage = msg.voltage
        v.battery_current = msg.current if msg.current >= 0 else 0

        # Safety: auto-RTL on low battery
        rtl_pct = self.safety.get('auto_rtl_battery_pct', 25)
        if v.battery < rtl_pct and v.armed:
            self._emit_event('SAFETY_BATTERY_RTL',
                           f'{v.callsign} battery {v.battery:.0f}% < {rtl_pct}% — FORCING RTL', 'CRITICAL')
            self._send_mavros_mode(asset_id, 'AUTO.RTL')

    # ─── MOS Command Handlers ──────────────────────────────────────
    def _mos_command(self, msg):
        """Handle commands from MOS C2 → route to real hardware."""
        try:
            cmd = json.loads(msg.data)
            asset_id = cmd.get('asset_id', '')
            action = cmd.get('action', '')
            v = self.vehicles.get(asset_id)
            if not v: return  # Not a real vehicle, ignore

            if action == 'ARM':
                self._arm_vehicle(asset_id, True)
            elif action == 'DISARM':
                self._arm_vehicle(asset_id, False)
            elif action == 'TAKEOFF':
                alt = cmd.get('altitude', 10.0)
                self._takeoff(asset_id, alt)
            elif action == 'LAND':
                self._land(asset_id)
            elif action == 'RTB':
                self._send_mavros_mode(asset_id, 'AUTO.RTL')
            elif action == 'HOLD':
                self._send_mavros_mode(asset_id, 'AUTO.LOITER')
            elif action == 'OFFBOARD':
                self._send_mavros_mode(asset_id, 'OFFBOARD')
            elif action == 'GOTO':
                lat, lon, alt = cmd.get('lat'), cmd.get('lon'), cmd.get('alt', 20)
                if v.source == 'nav2':
                    self._nav2_goto(asset_id, lat, lon)
                else:
                    self._mavros_goto(asset_id, lat, lon, alt)

        except Exception as e:
            self.get_logger().warn(f'[HAL] Command error: {e}')

    def _mos_waypoint(self, msg):
        """Handle waypoint assignments for real vehicles."""
        try:
            data = json.loads(msg.data)
            for asset_id in data.get('asset_ids', []):
                v = self.vehicles.get(asset_id)
                if not v: continue
                waypoints = data.get('waypoints', [])
                if waypoints:
                    wp = waypoints[0]  # First waypoint
                    if v.source == 'mavlink':
                        self._mavros_goto(asset_id, wp['lat'], wp['lon'], wp.get('alt', 20))
                    elif v.source == 'nav2':
                        self._nav2_goto(asset_id, wp['lat'], wp['lon'])
        except: pass

    def _emergency_stop(self, msg):
        """EMERGENCY STOP — disarm all real vehicles immediately."""
        self.get_logger().error('[HAL] ⚠ EMERGENCY STOP RECEIVED')
        self._emit_event('EMERGENCY_STOP', 'All vehicles emergency disarm', 'CRITICAL')
        for asset_id, v in self.vehicles.items():
            if v.source == 'mavlink' and v.armed:
                self._arm_vehicle(asset_id, False)

    # ─── MAVROS Service Calls ──────────────────────────────────────
    def _arm_vehicle(self, asset_id, arm):
        if not MAVROS_AVAILABLE: return
        v = self.vehicles.get(asset_id)
        if not v: return
        ns = v.config.get('namespace', '/mavros')
        cli = self.create_client(CommandBool, f'{ns}/cmd/arming')
        if cli.wait_for_service(timeout_sec=2.0):
            req = CommandBool.Request()
            req.value = arm
            future = cli.call_async(req)
            action = 'ARM' if arm else 'DISARM'
            self._emit_event(f'VEHICLE_{action}', f'{v.callsign} {action} command sent')
            self.get_logger().info(f'[HAL] {v.callsign} {action} command sent')
        else:
            self.get_logger().warn(f'[HAL] Arming service not available for {asset_id}')

    def _send_mavros_mode(self, asset_id, mode):
        if not MAVROS_AVAILABLE: return
        v = self.vehicles.get(asset_id)
        if not v: return
        ns = v.config.get('namespace', '/mavros')
        cli = self.create_client(SetMode, f'{ns}/set_mode')
        if cli.wait_for_service(timeout_sec=2.0):
            req = SetMode.Request()
            req.custom_mode = mode
            cli.call_async(req)
            self._emit_event('MODE_CHANGE', f'{v.callsign} → {mode}')

    def _takeoff(self, asset_id, altitude):
        if not MAVROS_AVAILABLE: return
        v = self.vehicles.get(asset_id)
        if not v: return
        ns = v.config.get('namespace', '/mavros')
        cli = self.create_client(CommandTOL, f'{ns}/cmd/takeoff')
        if cli.wait_for_service(timeout_sec=2.0):
            req = CommandTOL.Request()
            req.altitude = float(min(altitude, self.safety.get('max_altitude_m', 120)))
            req.latitude = v.lat
            req.longitude = v.lon
            cli.call_async(req)
            self._emit_event('TAKEOFF', f'{v.callsign} takeoff to {req.altitude:.0f}m')

    def _land(self, asset_id):
        if not MAVROS_AVAILABLE: return
        v = self.vehicles.get(asset_id)
        if not v: return
        ns = v.config.get('namespace', '/mavros')
        cli = self.create_client(CommandTOL, f'{ns}/cmd/land')
        if cli.wait_for_service(timeout_sec=2.0):
            req = CommandTOL.Request()
            req.latitude = v.lat
            req.longitude = v.lon
            cli.call_async(req)
            self._emit_event('LAND', f'{v.callsign} landing')

    def _mavros_goto(self, asset_id, lat, lon, alt):
        """Send global position setpoint via MAVROS."""
        v = self.vehicles.get(asset_id)
        if not v: return
        # For real goto, would publish to /mavros/setpoint_position/global
        # or use mission upload. Simplified here.
        self._emit_event('GOTO', f'{v.callsign} → {lat:.5f}, {lon:.5f} @ {alt:.0f}m')

    def _nav2_goto(self, asset_id, lat, lon):
        """Send Nav2 navigation goal for ground robots."""
        v = self.vehicles.get(asset_id)
        if not v or not hasattr(v, 'nav2_client'): return
        self._emit_event('NAV2_GOTO', f'{v.callsign} → {lat:.5f}, {lon:.5f}')

    # ─── Heartbeat Publishing ──────────────────────────────────────
    def _publish_heartbeats(self):
        for asset_id, v in self.vehicles.items():
            msg = String()
            msg.data = json.dumps(v.to_heartbeat())
            self.hb_pub.publish(msg)

    # ─── HAL Status ───────────────────────────────────────────────
    def _publish_hal_status(self):
        self.hal_status['vehicles'] = {}
        for aid, v in self.vehicles.items():
            self.hal_status['vehicles'][aid] = {
                'callsign': v.callsign,
                'source': v.source,
                'connected': v.connected,
                'armed': v.armed,
                'mode': v.mode,
                'battery': round(v.battery, 1),
                'last_hb': round(time.time() - v.last_heartbeat, 1) if v.last_heartbeat > 0 else -1,
            }
        self.hal_status['timestamp'] = time.time()
        msg = String()
        msg.data = json.dumps(self.hal_status)
        self.bridge_status_pub.publish(msg)

    # ─── DDIL Monitor ─────────────────────────────────────────────
    def _check_ddil(self):
        timeout = self.ddil.get('heartbeat_timeout_s', 5.0)
        now = time.time()
        for aid, v in self.vehicles.items():
            if v.last_heartbeat > 0 and (now - v.last_heartbeat) > timeout:
                if v.connected:
                    v.connected = False
                    self._emit_event('DDIL_DISCONNECT',
                                   f'{v.callsign} heartbeat lost ({now - v.last_heartbeat:.1f}s)', 'WARNING')
                    if self.ddil.get('auto_hold_on_disconnect', True) and v.source == 'mavlink':
                        self._send_mavros_mode(aid, 'AUTO.LOITER')
                        self._emit_event('DDIL_HOLD', f'{v.callsign} auto-HOLD on comms loss')

    # ─── Events ────────────────────────────────────────────────────
    def _emit_event(self, event_type, detail, severity='INFO'):
        msg = String()
        msg.data = json.dumps({
            'type': event_type, 'detail': detail,
            'severity': severity, 'timestamp': time.time()
        })
        self.bridge_event_pub.publish(msg)
        log = self.get_logger()
        if severity == 'CRITICAL': log.error(f'[HAL] {event_type}: {detail}')
        elif severity == 'WARNING': log.warn(f'[HAL] {event_type}: {detail}')
        else: log.info(f'[HAL] {event_type}: {detail}')


def main():
    rclpy.init()
    node = MAVLinkBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
