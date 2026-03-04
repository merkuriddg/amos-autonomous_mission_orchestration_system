#!/usr/bin/env python3
"""
MOS Phase 6 — Course of Action (COA) Generator
AI decision engine that generates tactical options for the commander.
"""

import math
import random
from datetime import datetime, timezone

BASE_LAT = 27.8491
BASE_LNG = -82.5212


class COAEngine:
    """Generates and ranks courses of action based on threat picture."""

    def __init__(self):
        self.coa_log = []

    def generate(self, threats: list, assets: list, constraints: dict = None) -> list:
        """Generate ranked COAs for current tactical situation."""
        constraints = constraints or {}
        coas = []

        # Group threats by type
        drones = [t for t in threats if t.get("type") == "drone" and not t.get("neutralized")]
        jammers = [t for t in threats if t.get("type") == "gps_jammer" and not t.get("neutralized")]
        vessels = [t for t in threats if t.get("type") == "vessel" and not t.get("neutralized")]

        # Available assets by capability
        air_int = [a for a in assets if a.get("domain") == "air"
                   and a.get("role") in ("recon", "ew", "air_superiority")
                   and a.get("status") == "active"]
        ew_assets = [a for a in assets if "EW_JAMMER" in a.get("sensors", [])
                     or a.get("role") == "ew"]
        maritime = [a for a in assets if a.get("domain") == "maritime"
                    and a.get("status") == "active"]
        ground = [a for a in assets if a.get("domain") == "ground"
                  and a.get("status") == "active"]

        # COA 1: Aggressive — intercept all
        if drones or vessels:
            coa1 = {
                "id": f"COA-{random.randint(1000,9999)}",
                "name": "AGGRESSIVE INTERCEPT",
                "description": "Immediately intercept all hostile contacts with closest available assets.",
                "risk": "MODERATE",
                "actions": [],
                "score": 0,
            }
            for drone in drones[:len(air_int)]:
                interceptor = self._nearest_asset(air_int, drone.get("lat",0), drone.get("lng",0))
                if interceptor:
                    coa1["actions"].append({
                        "type": "INTERCEPT", "asset": interceptor["id"],
                        "target": drone["id"],
                    })
                    air_int = [a for a in air_int if a["id"] != interceptor["id"]]
            for vessel in vessels[:len(maritime)]:
                intercept = self._nearest_asset(maritime, vessel.get("lat",0), vessel.get("lng",0))
                if intercept:
                    coa1["actions"].append({
                        "type": "INTERCEPT", "asset": intercept["id"],
                        "target": vessel["id"],
                    })
            coa1["score"] = self._score_coa(coa1, threats, assets)
            coas.append(coa1)

        # COA 2: EW-first — jam then intercept
        if jammers or drones:
            coa2 = {
                "id": f"COA-{random.randint(1000,9999)}",
                "name": "EW SUPPRESSION FIRST",
                "description": "Counter-jam GPS threats first, then intercept hostile drones under EW cover.",
                "risk": "LOW",
                "actions": [],
                "score": 0,
            }
            for jammer in jammers[:len(ew_assets)]:
                ew = self._nearest_asset(ew_assets, jammer.get("lat",0), jammer.get("lng",0))
                if ew:
                    coa2["actions"].append({
                        "type": "COUNTER_JAM", "asset": ew["id"],
                        "target": jammer["id"],
                    })
                    ew_assets = [a for a in ew_assets if a["id"] != ew["id"]]
            for drone in drones[:3]:
                coa2["actions"].append({
                    "type": "INTERCEPT_AFTER_EW", "target": drone["id"],
                    "delay_sec": 30,
                })
            coa2["score"] = self._score_coa(coa2, threats, assets)
            coas.append(coa2)

        # COA 3: Defensive — harden perimeter
        coa3 = {
            "id": f"COA-{random.randint(1000,9999)}",
            "name": "DEFENSIVE POSTURE",
            "description": "Recall assets to inner perimeter, activate all EW, maximize sensor coverage.",
            "risk": "LOW",
            "actions": [
                {"type": "RECALL_TO_PERIMETER", "radius_nm": 5},
                {"type": "ACTIVATE_ALL_EW"},
                {"type": "MAXIMIZE_ISR_COVERAGE"},
            ],
            "score": 0,
        }
        coa3["score"] = self._score_coa(coa3, threats, assets)
        coas.append(coa3)

        # Sort by score
        coas.sort(key=lambda c: c["score"], reverse=True)
        for i, coa in enumerate(coas):
            coa["rank"] = i + 1

        self.coa_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "threat_count": len(threats),
            "coas_generated": len(coas),
        })
        return coas

    def _nearest_asset(self, assets, lat, lng):
        best, best_dist = None, float("inf")
        for a in assets:
            d = math.sqrt((a.get("lat",0) - lat)**2 + (a.get("lng",0) - lng)**2)
            if d < best_dist:
                best_dist, best = d, a
        return best

    def _score_coa(self, coa, threats, assets):
        score = 50.0
        score += len(coa.get("actions", [])) * 10
        risk_mod = {"LOW": 10, "MODERATE": 0, "HIGH": -15}
        score += risk_mod.get(coa.get("risk", "MODERATE"), 0)
        score += random.uniform(-5, 5)
        return round(min(100, max(0, score)), 1)


if __name__ == "__main__":
    import json
    engine = COAEngine()
    threats = [
        {"id": "T1", "type": "drone", "lat": 27.79, "lng": -82.55, "neutralized": False},
        {"id": "T2", "type": "gps_jammer", "lat": 27.82, "lng": -82.51, "neutralized": False},
        {"id": "T3", "type": "vessel", "lat": 27.72, "lng": -82.60, "neutralized": False},
    ]
    assets = [
        {"id": "GHOST-01", "domain": "air", "role": "recon", "status": "active",
         "sensors": ["EO", "SIGINT"], "lat": 27.848, "lng": -82.510},
        {"id": "GHOST-02", "domain": "air", "role": "ew", "status": "active",
         "sensors": ["EO", "EW_JAMMER"], "lat": 27.846, "lng": -82.508},
        {"id": "TRITON-01", "domain": "maritime", "role": "coastal_patrol", "status": "active",
         "sensors": ["RADAR"], "lat": 27.82, "lng": -82.54},
    ]
    coas = engine.generate(threats, assets)
    for coa in coas:
        print(f"\n#{coa['rank']} {coa['name']} (Score: {coa['score']})")
        print(f"   {coa['description']}")
        for action in coa["actions"]:
            print(f"   → {action}")
