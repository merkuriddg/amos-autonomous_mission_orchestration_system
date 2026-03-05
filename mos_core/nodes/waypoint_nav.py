"""Waypoint Navigation System"""
import math, time

class WaypointNav:
    def __init__(self):
        self.routes = {}

    def set_waypoint(self, asset_id, lat, lng, alt_ft=None, label=""):
        self.routes[asset_id] = [{"lat": lat, "lng": lng, "alt_ft": alt_ft,
                                   "label": label or "WP-1"}]

    def add_waypoint(self, asset_id, lat, lng, alt_ft=None, label=""):
        if asset_id not in self.routes:
            self.routes[asset_id] = []
        n = len(self.routes[asset_id]) + 1
        self.routes[asset_id].append({"lat": lat, "lng": lng, "alt_ft": alt_ft,
                                       "label": label or f"WP-{n}"})

    def clear_waypoints(self, asset_id):
        self.routes.pop(asset_id, None)

    def clear_all(self):
        self.routes.clear()

    def get_waypoints(self, asset_id):
        return list(self.routes.get(asset_id, []))

    def get_all(self):
        return {k: list(v) for k, v in self.routes.items()}

    @staticmethod
    def _haversine(lat1, lng1, lat2, lng2):
        R = 3440.065
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlng / 2) ** 2)
        return 2 * R * math.asin(min(1, math.sqrt(a)))

    def tick(self, assets, dt):
        events = []
        for asset_id, wps in list(self.routes.items()):
            if not wps or asset_id not in assets:
                continue
            asset = assets[asset_id]
            target = wps[0]
            pos = asset.get("position", {})
            lat1, lng1 = pos.get("lat", 0), pos.get("lng", 0)
            lat2, lng2 = target["lat"], target["lng"]
            dist = self._haversine(lat1, lng1, lat2, lng2)
            if dist < 0.05:
                wps.pop(0)
                events.append({"asset_id": asset_id, "waypoint": target,
                                "time": time.time(), "type": "waypoint_reached"})
                if not wps:
                    self.routes.pop(asset_id, None)
                continue
            speed_kts = asset.get("speed_kts", 30)
            move = speed_kts * (dt / 3600.0)
            frac = min(1.0, move / dist) if dist > 0 else 1.0
            pos["lat"] = round(lat1 + (lat2 - lat1) * frac, 6)
            pos["lng"] = round(lng1 + (lng2 - lng1) * frac, 6)
            if target.get("alt_ft") is not None and "alt_ft" in pos:
                diff = target["alt_ft"] - pos["alt_ft"]
                climb = 500 * dt
                pos["alt_ft"] = target["alt_ft"] if abs(diff) < climb else pos["alt_ft"] + (climb if diff > 0 else -climb)
        return events
