"""AMOS ↔ MOOS-IvP Bridge

Integrates AMOS maritime assets with MOOS-IvP autonomous marine vehicle middleware.
Requires: pymoos (pip install pymoos) or MOOS-IvP C++ libraries.

MOOS Variables:
  Published: AMOS_WAYPOINT, AMOS_SPEED, AMOS_HEADING, AMOS_DEPLOY
  Subscribed: NAV_X, NAV_Y, NAV_HEADING, NAV_SPEED, BATTERY_PCT
"""

import time, logging, threading, math
from datetime import datetime, timezone

log = logging.getLogger("amos.moos")


class MOOSBridge:
    """Bridge to MOOS-IvP for maritime autonomous vehicles."""

    def __init__(self, moos_host="localhost", moos_port=9000, moos_name="amos_bridge"):
        self.host = moos_host
        self.port = moos_port
        self.name = moos_name
        self.comms = None
        self.connected = False
        self.vehicles = {}  # amos_id -> {moos_community, lat_origin, lng_origin}
        self.telemetry = {}
        self._lock = threading.Lock()

    def connect(self):
        try:
            import pymoos
            self.comms = pymoos.comms()
            self.comms.set_on_connect_callback(self._on_connect)
            self.comms.set_on_mail_callback(self._on_mail)
            self.comms.run(self.host, self.port, self.name)
            time.sleep(2)
            self.connected = self.comms.is_connected()
            if self.connected:
                log.info(f"MOOS connected: {self.host}:{self.port}")
            return self.connected
        except ImportError:
            log.info("pymoos not installed — maritime integration disabled")
            return False
        except Exception as e:
            log.error(f"MOOS connect failed: {e}")
            return False

    def register_vehicle(self, amos_id, moos_community="shoreside",
                         lat_origin=27.849, lng_origin=-82.521):
        self.vehicles[amos_id] = {
            "community": moos_community,
            "lat_origin": lat_origin, "lng_origin": lng_origin,
        }

    def send_waypoint(self, amos_id, lat, lng, speed_kts=10):
        """Send waypoint in MOOS local coordinates."""
        if not self.connected or amos_id not in self.vehicles:
            return False
        v = self.vehicles[amos_id]
        x = (lng - v["lng_origin"]) * 111320 * math.cos(math.radians(v["lat_origin"]))
        y = (lat - v["lat_origin"]) * 110540
        self.comms.notify("AMOS_WAYPOINT", f"x={x},y={y}", -1)
        self.comms.notify("AMOS_SPEED", str(speed_kts * 0.5144), -1)
        self.comms.notify("AMOS_DEPLOY", "true", -1)
        return True

    def send_loiter(self, amos_id, lat, lng, radius_m=50):
        if not self.connected or amos_id not in self.vehicles:
            return False
        v = self.vehicles[amos_id]
        x = (lng - v["lng_origin"]) * 111320 * math.cos(math.radians(v["lat_origin"]))
        y = (lat - v["lat_origin"]) * 110540
        self.comms.notify("AMOS_LOITER", f"x={x},y={y},radius={radius_m}", -1)
        return True

    def _on_connect(self):
        self.comms.register("NAV_X", 0)
        self.comms.register("NAV_Y", 0)
        self.comms.register("NAV_HEADING", 0)
        self.comms.register("NAV_SPEED", 0)
        self.comms.register("BATTERY_PCT", 0)
        return True

    def _on_mail(self):
        messages = self.comms.fetch()
        with self._lock:
            for msg in messages:
                key = msg.key()
                val = msg.double() if msg.is_double() else msg.string()
                # Map to first registered vehicle (multi-vehicle needs community prefix)
                for amos_id in self.vehicles:
                    t = self.telemetry.setdefault(amos_id, {})
                    if key == "NAV_X":
                        t["local_x"] = val
                    elif key == "NAV_Y":
                        t["local_y"] = val
                    elif key == "NAV_HEADING":
                        t["heading_deg"] = val
                    elif key == "NAV_SPEED":
                        t["speed_ms"] = val
                    elif key == "BATTERY_PCT":
                        t["battery_pct"] = val
                    t["last_update"] = time.time()
                    break
        return True

    def sync_to_amos(self, sim_assets):
        with self._lock:
            for amos_id, t in self.telemetry.items():
                if amos_id in sim_assets and "local_x" in t:
                    a = sim_assets[amos_id]
                    v = self.vehicles[amos_id]
                    lat = v["lat_origin"] + t["local_y"] / 110540
                    lng = v["lng_origin"] + t["local_x"] / (111320 * math.cos(
                        math.radians(v["lat_origin"])))
                    a["position"]["lat"] = lat
                    a["position"]["lng"] = lng
                    a["heading_deg"] = t.get("heading_deg", 0)
                    if "battery_pct" in t:
                        a["health"]["battery_pct"] = t["battery_pct"]

    def get_status(self):
        return {"connected": self.connected, "host": self.host, "port": self.port,
                "vehicles": list(self.vehicles.keys())}
