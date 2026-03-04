#!/usr/bin/env python3
"""
MOS Phase 6 — Geofence Manager
Defines and enforces geographic boundaries for assets.
"""

import math
import threading
from datetime import datetime, timezone


class GeofenceManager:
    """Manages inclusion/exclusion zones with altitude limits."""

    def __init__(self):
        self.zones = {}
        self.violations = []
        self._lock = threading.Lock()

    def add_zone(self, zone_id: str, zone_type: str, points: list,
                 floor_ft: int = 0, ceiling_ft: int = 60000,
                 applies_to: list = None) -> dict:
        """
        zone_type: 'inclusion' | 'exclusion' | 'warning'
        points: [{"lat": float, "lng": float}, ...]
        """
        zone = {
            "id": zone_id,
            "type": zone_type,
            "points": points,
            "floor_ft": floor_ft,
            "ceiling_ft": ceiling_ft,
            "applies_to": applies_to or ["all"],
            "active": True,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self.zones[zone_id] = zone
        return {"success": True, "zone": zone}

    def remove_zone(self, zone_id: str) -> dict:
        if zone_id in self.zones:
            del self.zones[zone_id]
            return {"success": True}
        return {"success": False, "error": "Not found"}

    def check_asset(self, asset_id: str, lat: float, lng: float,
                    alt_ft: float = 0) -> list:
        """Check all zones for violations."""
        violations = []
        for zone in self.zones.values():
            if not zone["active"]:
                continue
            if "all" not in zone["applies_to"] and asset_id not in zone["applies_to"]:
                continue
            inside = self._point_in_polygon(lat, lng, zone["points"])
            alt_ok = zone["floor_ft"] <= alt_ft <= zone["ceiling_ft"]
            if zone["type"] == "exclusion" and inside:
                v = {"asset_id": asset_id, "zone_id": zone["id"],
                     "violation": "INSIDE_EXCLUSION", "severity": "HIGH",
                     "timestamp": datetime.now(timezone.utc).isoformat()}
                violations.append(v)
            elif zone["type"] == "inclusion" and not inside:
                v = {"asset_id": asset_id, "zone_id": zone["id"],
                     "violation": "OUTSIDE_INCLUSION", "severity": "HIGH",
                     "timestamp": datetime.now(timezone.utc).isoformat()}
                violations.append(v)
            elif zone["type"] == "warning" and inside:
                v = {"asset_id": asset_id, "zone_id": zone["id"],
                     "violation": "INSIDE_WARNING", "severity": "MEDIUM",
                     "timestamp": datetime.now(timezone.utc).isoformat()}
                violations.append(v)
            if inside and not alt_ok:
                v = {"asset_id": asset_id, "zone_id": zone["id"],
                     "violation": "ALTITUDE_VIOLATION",
                     "severity": "HIGH", "alt_ft": alt_ft,
                     "limits": f"{zone['floor_ft']}-{zone['ceiling_ft']}ft",
                     "timestamp": datetime.now(timezone.utc).isoformat()}
                violations.append(v)
        with self._lock:
            self.violations.extend(violations)
            if len(self.violations) > 2000:
                self.violations = self.violations[-2000:]
        return violations

    def _point_in_polygon(self, lat, lng, polygon):
        """Ray-casting algorithm."""
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            yi, xi = polygon[i]["lat"], polygon[i]["lng"]
            yj, xj = polygon[j]["lat"], polygon[j]["lng"]
            if ((yi > lat) != (yj > lat) and
                    lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def get_all_zones(self) -> dict:
        return dict(self.zones)

    def get_violations(self, limit=50) -> list:
        return self.violations[-limit:]


if __name__ == "__main__":
    import json
    gf = GeofenceManager()
    # MacDill AFB AO
    gf.add_zone("AO-MAIN", "inclusion", [
        {"lat": 28.10, "lng": -82.80},
        {"lat": 28.10, "lng": -82.20},
        {"lat": 27.60, "lng": -82.20},
        {"lat": 27.60, "lng": -82.80},
    ], floor_ft=0, ceiling_ft=25000)
    # No-fly zone
    gf.add_zone("TPA-AIRSPACE", "exclusion", [
        {"lat": 27.98, "lng": -82.56},
        {"lat": 27.98, "lng": -82.50},
        {"lat": 27.94, "lng": -82.50},
        {"lat": 27.94, "lng": -82.56},
    ], floor_ft=0, ceiling_ft=18000)
    # Check asset
    v = gf.check_asset("GHOST-01", 27.96, -82.53, alt_ft=400)
    print(f"Violations: {json.dumps(v, indent=2)}")
