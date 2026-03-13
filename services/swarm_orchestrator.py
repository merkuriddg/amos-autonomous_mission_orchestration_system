#!/usr/bin/env python3
"""
MOS Phase 3 — Swarm Orchestrator
Manages multi-asset formations and coordinated behaviors:
  - Line, Wedge, Column, Diamond, Echelon, Orbit formations
  - Dynamic re-tasking and gap-filling
  - Domain-specific swarm patterns (air/ground/maritime)
"""

import math
import threading
from datetime import datetime, timezone
from services.cqb_formations import CQBFormation


class Formation:
    """Generates waypoints for common tactical formations."""

    @staticmethod
    def line(center_lat, center_lng, count, heading_deg=0, spacing_m=50):
        """Assets in a line perpendicular to heading."""
        points = []
        spacing_deg = spacing_m / 111000
        heading_rad = math.radians(heading_deg)
        perp_rad = heading_rad + math.pi / 2
        start_offset = -(count - 1) / 2
        for i in range(count):
            offset = (start_offset + i) * spacing_deg
            lat = center_lat + math.cos(perp_rad) * offset
            lng = center_lng + math.sin(perp_rad) * offset
            points.append({"lat": round(lat, 6), "lng": round(lng, 6)})
        return points

    @staticmethod
    def wedge(center_lat, center_lng, count, heading_deg=0, spacing_m=50):
        """V-shaped formation, leader at point."""
        points = [{"lat": center_lat, "lng": center_lng}]
        spacing_deg = spacing_m / 111000
        heading_rad = math.radians(heading_deg)
        for i in range(1, count):
            side = 1 if i % 2 else -1
            rank = (i + 1) // 2
            lat = center_lat - math.cos(heading_rad) * rank * spacing_deg
            lng_offset = side * rank * spacing_deg * math.sin(heading_rad + math.pi / 2)
            lng = center_lng + lng_offset - math.sin(heading_rad) * rank * spacing_deg
            points.append({"lat": round(lat, 6), "lng": round(lng, 6)})
        return points

    @staticmethod
    def column(center_lat, center_lng, count, heading_deg=0, spacing_m=50):
        """Single file along heading."""
        points = []
        spacing_deg = spacing_m / 111000
        heading_rad = math.radians(heading_deg)
        for i in range(count):
            lat = center_lat - math.cos(heading_rad) * i * spacing_deg
            lng = center_lng - math.sin(heading_rad) * i * spacing_deg
            points.append({"lat": round(lat, 6), "lng": round(lng, 6)})
        return points

    @staticmethod
    def diamond(center_lat, center_lng, heading_deg=0, spacing_m=50):
        """4-asset diamond."""
        s = spacing_m / 111000
        h = math.radians(heading_deg)
        return [
            {"lat": round(center_lat + math.cos(h) * s, 6),
             "lng": round(center_lng + math.sin(h) * s, 6)},
            {"lat": round(center_lat + math.cos(h + math.pi/2) * s, 6),
             "lng": round(center_lng + math.sin(h + math.pi/2) * s, 6)},
            {"lat": round(center_lat - math.cos(h) * s, 6),
             "lng": round(center_lng - math.sin(h) * s, 6)},
            {"lat": round(center_lat + math.cos(h - math.pi/2) * s, 6),
             "lng": round(center_lng + math.sin(h - math.pi/2) * s, 6)},
        ]

    @staticmethod
    def orbit(center_lat, center_lng, count, radius_m=500):
        """Assets evenly spaced in a circle."""
        points = []
        radius_deg = radius_m / 111000
        for i in range(count):
            angle = (2 * math.pi * i) / count
            lat = center_lat + math.cos(angle) * radius_deg
            lng = center_lng + math.sin(angle) * radius_deg
            points.append({"lat": round(lat, 6), "lng": round(lng, 6)})
        return points


class SwarmOrchestrator:
    """Manages swarm groups and formation assignments."""

    def __init__(self):
        self.swarms = {}
        self._lock = threading.Lock()
        self.event_log = []

    def create_swarm(self, swarm_id: str, asset_ids: list, formation: str = "line",
                     center_lat: float = 27.8491, center_lng: float = -82.5212,
                     heading: float = 0, spacing_m: float = 50) -> dict:
        count = len(asset_ids)
        if formation == "line":
            positions = Formation.line(center_lat, center_lng, count, heading, spacing_m)
        elif formation == "wedge":
            positions = Formation.wedge(center_lat, center_lng, count, heading, spacing_m)
        elif formation == "column":
            positions = Formation.column(center_lat, center_lng, count, heading, spacing_m)
        elif formation == "diamond":
            positions = Formation.diamond(center_lat, center_lng, heading, spacing_m)
        elif formation == "orbit":
            positions = Formation.orbit(center_lat, center_lng, count, spacing_m)
        elif formation.upper() in CQBFormation.FORMATIONS:
            # CQB meter-scale formation (STACK, BUTTONHOOK, CORRIDOR, etc.)
            positions = CQBFormation.compute(
                formation.upper(), count,
                heading_deg=heading, spacing_m=spacing_m,
                ref_lat=center_lat, ref_lng=center_lng,
            )
        else:
            return {"success": False, "error": f"Unknown formation: {formation}"}

        assignments = {}
        for i, asset_id in enumerate(asset_ids):
            if i < len(positions):
                assignments[asset_id] = positions[i]

        with self._lock:
            self.swarms[swarm_id] = {
                "id": swarm_id,
                "assets": asset_ids,
                "formation": formation,
                "center": {"lat": center_lat, "lng": center_lng},
                "heading": heading,
                "spacing_m": spacing_m,
                "assignments": assignments,
                "status": "active",
                "created": datetime.now(timezone.utc).isoformat(),
            }
        self._log("CREATE", swarm_id, f"{formation} with {count} assets")
        return {"success": True, "swarm": self.swarms[swarm_id]}

    def update_formation(self, swarm_id: str, formation: str = None,
                         center_lat: float = None, center_lng: float = None,
                         heading: float = None) -> dict:
        if swarm_id not in self.swarms:
            return {"success": False, "error": "Swarm not found"}
        swarm = self.swarms[swarm_id]
        if formation: swarm["formation"] = formation
        if center_lat: swarm["center"]["lat"] = center_lat
        if center_lng: swarm["center"]["lng"] = center_lng
        if heading is not None: swarm["heading"] = heading
        # Recalculate positions
        return self.create_swarm(
            swarm_id, swarm["assets"], swarm["formation"],
            swarm["center"]["lat"], swarm["center"]["lng"],
            swarm["heading"], swarm["spacing_m"]
        )

    def dissolve_swarm(self, swarm_id: str) -> dict:
        if swarm_id in self.swarms:
            del self.swarms[swarm_id]
            self._log("DISSOLVE", swarm_id)
            return {"success": True}
        return {"success": False, "error": "Not found"}

    def get_swarm(self, swarm_id: str) -> dict:
        return self.swarms.get(swarm_id, {})

    def get_all(self) -> dict:
        return dict(self.swarms)

    def _log(self, action, swarm_id, details=""):
        self.event_log.append({
            "action": action, "swarm_id": swarm_id,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self.event_log) > 1000:
            self.event_log = self.event_log[-1000:]


if __name__ == "__main__":
    import json
    so = SwarmOrchestrator()
    result = so.create_swarm("ALPHA", ["GHOST-01", "GHOST-02", "GHOST-03", "GHOST-04"],
                              "wedge", 27.85, -82.52, heading=45, spacing_m=100)
    print(json.dumps(result, indent=2))
    result = so.create_swarm("BRAVO", ["TALON-01", "TALON-02", "TALON-03"],
                              "line", 27.84, -82.52, heading=90, spacing_m=75)
    print(json.dumps(result, indent=2))
