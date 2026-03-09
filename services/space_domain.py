#!/usr/bin/env python3
"""AMOS Phase 20 — Space Domain + JADC2 Mesh
Orbital asset tracking with Keplerian propagation, SATCOM link budget,
GPS constellation health, space weather, JADC2 mesh topology."""

import math, random, time, uuid, threading
from datetime import datetime, timezone


class SpaceDomain:
    """Space domain awareness and JADC2 mesh management."""

    # Simulated orbital assets
    DEFAULT_CONSTELLATION = [
        {"id": "SAT-GPS-01", "name": "GPS IIF-01", "orbit": "MEO", "alt_km": 20200,
         "inclination": 55, "type": "navigation", "status": "operational", "health": 98},
        {"id": "SAT-GPS-02", "name": "GPS IIF-02", "orbit": "MEO", "alt_km": 20200,
         "inclination": 55, "type": "navigation", "status": "operational", "health": 95},
        {"id": "SAT-GPS-03", "name": "GPS III-01", "orbit": "MEO", "alt_km": 20200,
         "inclination": 55, "type": "navigation", "status": "operational", "health": 99},
        {"id": "SAT-COM-01", "name": "MUOS-1", "orbit": "GEO", "alt_km": 35786,
         "inclination": 0, "type": "satcom", "status": "operational", "health": 92},
        {"id": "SAT-COM-02", "name": "AEHF-4", "orbit": "GEO", "alt_km": 35786,
         "inclination": 0, "type": "satcom", "status": "operational", "health": 88},
        {"id": "SAT-ISR-01", "name": "KH-12", "orbit": "LEO", "alt_km": 400,
         "inclination": 97, "type": "isr", "status": "operational", "health": 96},
        {"id": "SAT-ISR-02", "name": "SBIRS-GEO-1", "orbit": "GEO", "alt_km": 35786,
         "inclination": 0, "type": "early_warning", "status": "operational", "health": 94},
        {"id": "SAT-EW-01", "name": "NEMESIS-1", "orbit": "LEO", "alt_km": 550,
         "inclination": 63, "type": "sigint", "status": "operational", "health": 91},
        {"id": "SAT-RELAY-01", "name": "TDRS-M", "orbit": "GEO", "alt_km": 35786,
         "inclination": 0, "type": "relay", "status": "operational", "health": 97},
    ]

    def __init__(self):
        self._lock = threading.Lock()
        self.satellites = {}
        self.satcom_links = {}     # {link_id: {from, to, bandwidth, quality, ...}}
        self.gps_denial_zones = []  # [{center, radius_km, severity}]
        self.space_weather = {
            "kp_index": 2, "solar_flux": 110, "proton_flux": 1.5,
            "geomagnetic_storm": False, "radio_blackout": "none",
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
        self.jadc2_mesh = {}       # {node_id: {type, domain, connections, status}}
        self._init_constellation()
        self._last_propagate = 0

    def _init_constellation(self):
        """Initialize orbital assets with ephemeris data."""
        for sat in self.DEFAULT_CONSTELLATION:
            sid = sat["id"]
            self.satellites[sid] = {
                **sat,
                "epoch_angle": random.uniform(0, 360),  # starting orbital angle
                "raan": random.uniform(0, 360),          # right ascension
                "eccentricity": random.uniform(0.0001, 0.01),
                "period_min": self._orbital_period(sat["alt_km"]),
                "lat": 0, "lng": 0,  # ground track position
                "footprint_km": self._footprint(sat["alt_km"]),
                "visible_from_ao": True,
                "signal_strength": random.uniform(0.7, 1.0),
                "data_rate_mbps": {"navigation": 0.05, "satcom": 50, "isr": 800,
                                   "early_warning": 10, "sigint": 200, "relay": 300
                                   }.get(sat["type"], 1),
            }

    def _orbital_period(self, alt_km):
        """Kepler's 3rd law — period in minutes."""
        R = 6371 + alt_km  # Earth radius + altitude
        return 2 * math.pi * math.sqrt(R**3 / 398600.4) / 60

    def _footprint(self, alt_km):
        """Approximate sensor footprint radius in km."""
        return math.sqrt(alt_km * 2 * 6371) * 0.5

    def tick(self, base_lat, base_lng, assets, dt):
        """Propagate orbits, update SATCOM links, space weather drift."""
        now = time.time()
        if now - self._last_propagate < 2:
            return
        self._last_propagate = now

        with self._lock:
            # 1. Keplerian propagation (simplified ground track)
            for sid, sat in self.satellites.items():
                period = sat["period_min"]
                if period <= 0:
                    continue
                # Angular velocity (degrees per second)
                omega = 360.0 / (period * 60)
                sat["epoch_angle"] = (sat["epoch_angle"] + omega * 2) % 360

                # Ground track computation
                angle_rad = math.radians(sat["epoch_angle"])
                inc_rad = math.radians(sat["inclination"])
                sat["lat"] = round(math.degrees(math.asin(
                    math.sin(inc_rad) * math.sin(angle_rad))), 4)
                # Longitude drifts with Earth rotation (simplified)
                sat["lng"] = round((sat["raan"] + math.degrees(angle_rad) -
                                   (now % 86400) / 86400 * 360) % 360 - 180, 4)

                # Visibility from AO
                dist_deg = math.sqrt((sat["lat"]-base_lat)**2 + (sat["lng"]-base_lng)**2)
                max_vis = sat["footprint_km"] / 111  # rough degree conversion
                sat["visible_from_ao"] = dist_deg < max_vis

                # Health drift
                sat["health"] = max(50, min(100, sat["health"] + random.uniform(-0.1, 0.05)))
                if self.space_weather["geomagnetic_storm"]:
                    sat["health"] = max(50, sat["health"] - random.uniform(0, 0.5))
                sat["signal_strength"] = round(
                    min(1.0, sat["health"] / 100 * (0.9 + random.uniform(0, 0.1))), 3)

            # 2. SATCOM link updates
            self._update_satcom_links(assets)

            # 3. GPS denial zone drift
            for zone in self.gps_denial_zones:
                zone["center"]["lat"] += random.uniform(-0.001, 0.001)
                zone["center"]["lng"] += random.uniform(-0.001, 0.001)
                zone["radius_km"] += random.uniform(-0.5, 0.5)
                zone["radius_km"] = max(5, min(100, zone["radius_km"]))

            # 4. Space weather drift
            if random.random() < 0.05:
                sw = self.space_weather
                sw["kp_index"] = max(0, min(9, sw["kp_index"] + random.choice([-1, 0, 0, 0, 1])))
                sw["solar_flux"] = max(60, min(300, sw["solar_flux"] + random.uniform(-5, 5)))
                sw["proton_flux"] = max(0.1, min(1000, sw["proton_flux"] * random.uniform(0.9, 1.1)))
                sw["geomagnetic_storm"] = sw["kp_index"] >= 5
                if sw["kp_index"] >= 7:
                    sw["radio_blackout"] = random.choice(["minor", "moderate", "severe"])
                elif sw["kp_index"] >= 5:
                    sw["radio_blackout"] = random.choice(["none", "minor"])
                else:
                    sw["radio_blackout"] = "none"
                sw["last_update"] = datetime.now(timezone.utc).isoformat()

            # 5. JADC2 mesh update
            self._update_jadc2_mesh(assets)

    def _update_satcom_links(self, assets):
        """Compute SATCOM link budgets between assets and satellites."""
        self.satcom_links = {}
        com_sats = [s for s in self.satellites.values()
                    if s["type"] in ("satcom", "relay") and s["status"] == "operational"]
        for aid, a in assets.items():
            best_sat = None
            best_quality = 0
            for sat in com_sats:
                if not sat["visible_from_ao"]:
                    continue
                # Simple link budget: distance + satellite health + signal
                dist = math.sqrt((sat["lat"]-a["position"]["lat"])**2 +
                                (sat["lng"]-a["position"]["lng"])**2)
                quality = sat["signal_strength"] * max(0, 1 - dist / (sat["footprint_km"]/111))
                # GPS denial penalty
                for zone in self.gps_denial_zones:
                    zdist = math.sqrt((a["position"]["lat"]-zone["center"]["lat"])**2 +
                                     (a["position"]["lng"]-zone["center"]["lng"])**2)
                    if zdist < zone["radius_km"] / 111:
                        quality *= 0.3
                if quality > best_quality:
                    best_quality = quality
                    best_sat = sat["id"]
            if best_sat:
                self.satcom_links[aid] = {
                    "asset_id": aid, "satellite": best_sat,
                    "quality": round(best_quality, 3),
                    "bandwidth_mbps": round(
                        self.satellites[best_sat]["data_rate_mbps"] * best_quality, 1),
                    "latency_ms": round(
                        self.satellites[best_sat]["alt_km"] / 300 * 2 + random.uniform(5, 50), 1),
                }

    def _update_jadc2_mesh(self, assets):
        """Build JADC2 mesh topology — all domain nodes and connections."""
        self.jadc2_mesh = {}
        # Add satellite nodes
        for sid, sat in self.satellites.items():
            if sat["status"] != "operational":
                continue
            self.jadc2_mesh[sid] = {
                "id": sid, "name": sat["name"], "type": "satellite",
                "domain": "space", "status": sat["status"],
                "connections": [], "data_rate": sat["data_rate_mbps"],
            }
        # Add asset nodes
        for aid, a in assets.items():
            self.jadc2_mesh[aid] = {
                "id": aid, "type": a["type"], "domain": a["domain"],
                "name": aid, "status": a["status"], "connections": [],
                "data_rate": 10 if a["domain"] == "air" else 5,
            }
            # Connect to best satellite
            link = self.satcom_links.get(aid)
            if link:
                self.jadc2_mesh[aid]["connections"].append({
                    "to": link["satellite"], "type": "satcom",
                    "quality": link["quality"]})
                if link["satellite"] in self.jadc2_mesh:
                    self.jadc2_mesh[link["satellite"]]["connections"].append({
                        "to": aid, "type": "satcom", "quality": link["quality"]})

    def add_gps_denial_zone(self, lat, lng, radius_km, severity="moderate"):
        """Add a GPS denial/jamming zone."""
        zone = {
            "id": f"GPS-DZ-{uuid.uuid4().hex[:6]}",
            "center": {"lat": lat, "lng": lng},
            "radius_km": radius_km, "severity": severity,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.gps_denial_zones.append(zone)
        return zone

    def remove_gps_denial_zone(self, zone_id):
        self.gps_denial_zones = [z for z in self.gps_denial_zones if z["id"] != zone_id]
        return {"status": "ok"}

    def get_orbital_status(self):
        return {sid: {
            "id": s["id"], "name": s["name"], "orbit": s["orbit"],
            "type": s["type"], "status": s["status"],
            "health": round(s["health"], 1), "lat": s["lat"], "lng": s["lng"],
            "alt_km": s["alt_km"], "visible": s["visible_from_ao"],
            "signal": s["signal_strength"], "footprint_km": round(s["footprint_km"]),
        } for sid, s in self.satellites.items()}

    def get_satcom_links(self):
        return dict(self.satcom_links)

    def get_gps_status(self):
        gps_sats = [s for s in self.satellites.values() if s["type"] == "navigation"]
        visible = sum(1 for s in gps_sats if s["visible_from_ao"])
        avg_health = sum(s["health"] for s in gps_sats) / max(1, len(gps_sats))
        return {
            "total_gps": len(gps_sats), "visible": visible,
            "avg_health": round(avg_health, 1),
            "denial_zones": self.gps_denial_zones,
            "accuracy_status": "DEGRADED" if visible < 3 or self.gps_denial_zones else "NOMINAL",
        }

    def get_space_weather(self):
        return dict(self.space_weather)

    def get_mesh(self):
        return dict(self.jadc2_mesh)

    def get_stats(self):
        total = len(self.satellites)
        operational = sum(1 for s in self.satellites.values() if s["status"] == "operational")
        visible = sum(1 for s in self.satellites.values() if s["visible_from_ao"])
        links = len(self.satcom_links)
        mesh_nodes = len(self.jadc2_mesh)
        return {"total_satellites": total, "operational": operational,
                "visible": visible, "satcom_links": links,
                "mesh_nodes": mesh_nodes, "gps_denial_zones": len(self.gps_denial_zones),
                "space_weather_kp": self.space_weather["kp_index"]}
