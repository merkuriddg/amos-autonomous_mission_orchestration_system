"""AMOS ↔ ArduPilot Bridge

Connects AMOS to ArduPilot-powered drones, rovers, and boats via MAVLink.
Requires: pymavlink (pip install pymavlink)

Supports: ArduCopter, ArduPlane, ArduRover, ArduSub
"""

import time, threading, logging, math
from datetime import datetime, timezone

log = logging.getLogger("amos.ardupilot")

# ArduPilot mode mappings
COPTER_MODES = {
    "STABILIZE": 0, "ACRO": 1, "ALT_HOLD": 2, "AUTO": 3, "GUIDED": 4,
    "LOITER": 5, "RTL": 6, "LAND": 9, "POSHOLD": 16, "BRAKE": 17,
}
ROVER_MODES = {
    "MANUAL": 0, "STEERING": 3, "HOLD": 4, "AUTO": 10, "RTL": 11, "GUIDED": 15,
}


class ArduPilotBridge:
    """MAVLink bridge for ArduPilot vehicles."""

    def __init__(self, connection_string="udp:127.0.0.1:14550"):
        self.connection_string = connection_string
        self.mavconn = None
        self.connected = False
        self.vehicles = {}
        self.telemetry = {}
        self._lock = threading.Lock()

    def connect(self):
        try:
            from pymavlink import mavutil
            self.mavconn = mavutil.mavlink_connection(self.connection_string)
            self.mavconn.wait_heartbeat(timeout=10)
            self.connected = True
            log.info(f"ArduPilot connected: {self.connection_string}")
            threading.Thread(target=self._recv_loop, daemon=True).start()
            return True
        except ImportError:
            log.warning("pymavlink not installed")
            return False
        except Exception as e:
            log.error(f"ArduPilot connect failed: {e}")
            return False

    def register(self, amos_id, sysid=1, vehicle_type="copter"):
        self.vehicles[amos_id] = {"sysid": sysid, "type": vehicle_type}

    def goto(self, amos_id, lat, lng, alt_m=30):
        """Send GUIDED waypoint."""
        if not self.connected or amos_id not in self.vehicles:
            return False
        v = self.vehicles[amos_id]
        self.mavconn.mav.mission_item_int_send(
            v["sysid"], 0, 0, 6, 16, 2, 0, 0, 0, 0, 0,
            int(lat * 1e7), int(lng * 1e7), alt_m)
        return True

    def set_mode(self, amos_id, mode_name):
        if not self.connected or amos_id not in self.vehicles:
            return False
        v = self.vehicles[amos_id]
        modes = COPTER_MODES if v["type"] == "copter" else ROVER_MODES
        mode_id = modes.get(mode_name.upper(), 4)
        self.mavconn.mav.set_mode_send(v["sysid"], 1, mode_id)
        return True

    def arm(self, amos_id):
        if not self.connected or amos_id not in self.vehicles:
            return False
        v = self.vehicles[amos_id]
        self.mavconn.mav.command_long_send(v["sysid"], 0, 400, 0, 1, 0, 0, 0, 0, 0, 0)
        return True

    def get_telemetry(self, amos_id):
        return self.telemetry.get(amos_id, {})

    def get_status(self):
        return {"connected": self.connected, "vehicles": len(self.vehicles),
                "connection": self.connection_string}

    def _recv_loop(self):
        while self.connected:
            try:
                msg = self.mavconn.recv_match(blocking=True, timeout=1)
                if not msg:
                    continue
                sysid = msg.get_srcSystem()
                amos_id = next((a for a, v in self.vehicles.items() if v["sysid"] == sysid), None)
                if not amos_id:
                    continue
                with self._lock:
                    t = self.telemetry.setdefault(amos_id, {})
                    mtype = msg.get_type()
                    if mtype == "GLOBAL_POSITION_INT":
                        t.update(lat=msg.lat/1e7, lng=msg.lon/1e7, alt_m=msg.relative_alt/1000,
                                 heading_deg=msg.hdg/100, vx=msg.vx/100, vy=msg.vy/100)
                    elif mtype == "SYS_STATUS":
                        t["battery_mv"] = msg.voltage_battery
                        t["battery_pct"] = msg.battery_remaining
                    elif mtype == "GPS_RAW_INT":
                        t["gps_fix"] = msg.fix_type >= 3
                        t["satellites"] = msg.satellites_visible
                    t["last_update"] = time.time()
            except Exception:
                time.sleep(0.1)

    def sync_to_amos(self, sim_assets):
        for amos_id, t in self.telemetry.items():
            if amos_id in sim_assets and "lat" in t:
                a = sim_assets[amos_id]
                a["position"]["lat"] = t["lat"]
                a["position"]["lng"] = t["lng"]
                a["position"]["alt_ft"] = t.get("alt_m", 0) * 3.281
                a["heading_deg"] = t.get("heading_deg", 0)
                if "battery_pct" in t:
                    a["health"]["battery_pct"] = t["battery_pct"]
                a["health"]["gps_fix"] = t.get("gps_fix", True)
