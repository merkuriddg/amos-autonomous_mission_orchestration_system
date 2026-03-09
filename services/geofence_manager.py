"""Geofence Management System"""
import math, time, uuid

class GeofenceManager:
    def __init__(self):
        self.geofences = {}
        self.alerts = []
        self._cache = {}

    def add_geofence(self, gf_type, points, name="", gf_id=None):
        gf_id = gf_id or f"GF-{uuid.uuid4().hex[:6].upper()}"
        self.geofences[gf_id] = {"id": gf_id, "name": name or gf_id,
                                  "type": gf_type, "points": points,
                                  "created": time.time(), "active": True}
        return gf_id

    def remove_geofence(self, gf_id):
        self.geofences.pop(gf_id, None)

    def get_all(self):
        return dict(self.geofences)

    def get_alerts(self, limit=100):
        return self.alerts[-limit:]

    @staticmethod
    def _pip(lat, lng, poly):
        n = len(poly)
        inside = False
        j = n - 1
        for i in range(n):
            yi, xi = poly[i]["lat"], poly[i]["lng"]
            yj, xj = poly[j]["lat"], poly[j]["lng"]
            if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    @staticmethod
    def _dist_nm(lat1, lng1, lat2, lng2):
        R = 3440.065
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlng / 2) ** 2)
        return 2 * R * math.asin(min(1, math.sqrt(a)))

    def _inside(self, lat, lng, gf):
        pts = gf["points"]
        if isinstance(pts, dict) and "center" in pts:
            return self._dist_nm(lat, lng, pts["center"]["lat"], pts["center"]["lng"]) <= pts.get("radius_nm", 1)
        if isinstance(pts, list) and len(pts) >= 3:
            return self._pip(lat, lng, pts)
        return False

    def tick(self, assets, threats):
        new = []
        entities = []
        for aid, a in assets.items():
            p = a.get("position", {})
            if p.get("lat") is not None:
                entities.append((aid, "asset", p["lat"], p["lng"]))
        for tid, t in threats.items():
            if not t.get("neutralized") and "lat" in t:
                entities.append((tid, "threat", t["lat"], t["lng"]))

        for eid, etype, lat, lng in entities:
            for gid, gf in self.geofences.items():
                if not gf.get("active"):
                    continue
                inside = self._inside(lat, lng, gf)
                key = (eid, gid)
                was = self._cache.get(key)
                if was is not None and inside != was:
                    alert = {"id": f"ALERT-{uuid.uuid4().hex[:8]}",
                             "timestamp": time.time(), "entity_id": eid,
                             "entity_type": etype, "geofence_id": gid,
                             "geofence_name": gf["name"], "geofence_type": gf["type"],
                             "event": "entered" if inside else "exited",
                             "lat": lat, "lng": lng}
                    new.append(alert)
                    self.alerts.append(alert)
                self._cache[key] = inside
        if len(self.alerts) > 500:
            self.alerts = self.alerts[-500:]
        return new
