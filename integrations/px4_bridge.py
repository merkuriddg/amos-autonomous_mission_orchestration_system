"""AMOS ↔ PX4 Autopilot Bridge

Connects AMOS air assets to PX4-powered drones via MAVLink.
Requires: pymavlink (pip install pymavlink)

Usage:
    bridge = PX4Bridge("udp:127.0.0.1:14540")
    bridge.connect()
    bridge.send_waypoint("GHOST-1", lat, lng, alt_m)
    state = bridge.get_telemetry("GHOST-1")
"""

import time, threading, logging
from datetime import datetime, timezone

log = logging.getLogger("amos.px4")


class PX4Bridge:
    """MAVLink bridge to PX4 autopilot instances."""

    def __init__(self, connection_string="udp:127.0.0.1:14540"):
        self.connection_string = connection_string
        self.mavconn = None
        self.connected = False
        self.vehicles = {}  # amos_id -> {sysid, compid, telemetry}
        self.telemetry_cache = {}
        self._lock = threading.Lock()

    def connect(self):
        """Establish MAVLink connection."""
        try:
            from pymavlink import mavutil
            self.mavconn = mavutil.mavlink_connection(self.connection_string)
            self.mavconn.wait_heartbeat(timeout=10)
            self.connected = True
            log.info(f"PX4 connected: {self.connection_string}")
            threading.Thread(target=self._telemetry_loop, daemon=True).start()
            return True
        except ImportError:
            log.warning("pymavlink not installed — run: pip install pymavlink")
            return False
        except Exception as e:
            log.error(f"PX4 connection failed: {e}")
            return False

    def register_vehicle(self, amos_id, system_id=1, component_id=1):
        """Map an AMOS asset ID to a MAVLink system/component."""
        self.vehicles[amos_id] = {
            "sysid": system_id, "compid": component_id,
            "registered": datetime.now(timezone.utc).isoformat(),
        }

    def send_waypoint(self, amos_id, lat, lng, alt_m=50, speed_ms=15):
        """Command vehicle to fly to a GPS waypoint."""
        if not self.connected or amos_id not in self.vehicles:
            return False
        v = self.vehicles[amos_id]
        try:
            self.mavconn.mav.set_position_target_global_int_send(
                0, v["sysid"], v["compid"], 6,  # MAV_FRAME_GLOBAL_RELATIVE_ALT_INT
                0b0000111111111000,
                int(lat * 1e7), int(lng * 1e7), alt_m,
                0, 0, 0, 0, 0, 0, 0, 0)
            log.info(f"WP sent: {amos_id} -> {lat},{lng} alt={alt_m}m")
            return True
        except Exception as e:
            log.error(f"WP send failed: {e}")
            return False

    def arm(self, amos_id):
        """Arm the vehicle."""
        if not self.connected or amos_id not in self.vehicles:
            return False
        v = self.vehicles[amos_id]
        self.mavconn.mav.command_long_send(
            v["sysid"], v["compid"], 400, 0, 1, 0, 0, 0, 0, 0, 0)
        return True

    def set_mode(self, amos_id, mode="OFFBOARD"):
        """Set flight mode."""
        if not self.connected:
            return False
        mode_map = {"OFFBOARD": 6, "LAND": 9, "RTL": 5, "HOLD": 3, "AUTO": 4}
        mode_id = mode_map.get(mode.upper(), 6)
        v = self.vehicles[amos_id]
        self.mavconn.mav.command_long_send(
            v["sysid"], v["compid"], 176, 0, mode_id, 0, 0, 0, 0, 0, 0)
        return True

    def get_telemetry(self, amos_id):
        """Get cached telemetry for a vehicle."""
        return self.telemetry_cache.get(amos_id, {})

    def get_status(self):
        return {
            "connected": self.connected,
            "connection": self.connection_string,
            "vehicles": list(self.vehicles.keys()),
            "vehicle_count": len(self.vehicles),
        }

    def _telemetry_loop(self):
        """Background thread reading MAVLink telemetry."""
        while self.connected:
            try:
                msg = self.mavconn.recv_match(blocking=True, timeout=1)
                if msg is None:
                    continue
                mtype = msg.get_type()
                sysid = msg.get_srcSystem()
                # Find AMOS ID for this sysid
                amos_id = None
                for aid, v in self.vehicles.items():
                    if v["sysid"] == sysid:
                        amos_id = aid
                        break
                if not amos_id:
                    continue

                with self._lock:
                    telem = self.telemetry_cache.setdefault(amos_id, {})
                    if mtype == "GLOBAL_POSITION_INT":
                        telem["lat"] = msg.lat / 1e7
                        telem["lng"] = msg.lon / 1e7
                        telem["alt_m"] = msg.alt / 1000
                        telem["heading_deg"] = msg.hdg / 100
                    elif mtype == "BATTERY_STATUS":
                        telem["battery_pct"] = msg.battery_remaining
                    elif mtype == "HEARTBEAT":
                        telem["armed"] = bool(msg.base_mode & 128)
                        telem["mode"] = msg.custom_mode
                    telem["last_update"] = time.time()
            except Exception:
                time.sleep(0.1)

    def sync_to_amos(self, sim_assets):
        """Push real telemetry into AMOS sim_assets dict."""
        for amos_id, telem in self.telemetry_cache.items():
            if amos_id in sim_assets and "lat" in telem:
                a = sim_assets[amos_id]
                a["position"]["lat"] = telem["lat"]
                a["position"]["lng"] = telem["lng"]
                a["position"]["alt_ft"] = telem.get("alt_m", 0) * 3.281
                a["heading_deg"] = telem.get("heading_deg", 0)
                if "battery_pct" in telem:
                    a["health"]["battery_pct"] = telem["battery_pct"]
