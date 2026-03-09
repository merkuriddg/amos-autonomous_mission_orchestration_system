#!/usr/bin/env python3
"""AMOS Phase 17 — Autonomous Swarm Intelligence
Reynolds flocking, task auction protocol, consensus-based decisions,
self-healing formations, emergent cooperative behaviors."""

import math, random, uuid, threading, time
from datetime import datetime, timezone


class SwarmIntelligence:
    """Advanced swarm management with bio-inspired behaviors and task allocation."""

    # Behavioral DNA profiles
    BEHAVIOR_PROFILES = {
        "scout":    {"separation": 0.8, "alignment": 0.3, "cohesion": 0.4, "target_seek": 0.9, "evasion": 0.7},
        "assault":  {"separation": 0.5, "alignment": 0.8, "cohesion": 0.7, "target_seek": 1.0, "evasion": 0.3},
        "defense":  {"separation": 0.3, "alignment": 0.6, "cohesion": 0.9, "target_seek": 0.2, "evasion": 0.5},
        "pursuit":  {"separation": 0.6, "alignment": 0.9, "cohesion": 0.5, "target_seek": 1.0, "evasion": 0.1},
        "overwatch": {"separation": 1.0, "alignment": 0.2, "cohesion": 0.3, "target_seek": 0.4, "evasion": 0.8},
    }

    # Emergent behavior patterns
    EMERGENT_BEHAVIORS = {
        "surround":  {"description": "Encircle target from all angles", "min_assets": 3},
        "funnel":    {"description": "Drive target toward kill zone", "min_assets": 4},
        "pincer":    {"description": "Dual-axis converging attack", "min_assets": 4},
        "screen":    {"description": "Wide-area coverage sweep", "min_assets": 3},
        "relay":     {"description": "Communication relay chain", "min_assets": 2},
        "decoy":     {"description": "Distract while others maneuver", "min_assets": 3},
    }

    def __init__(self):
        self._lock = threading.Lock()
        self.swarms = {}        # {swarm_id: swarm_state}
        self.auctions = []      # active task auctions
        self.consensus_log = [] # decision records
        self.event_log = []

    def create_swarm(self, swarm_id, asset_ids, behavior="scout",
                     center_lat=0, center_lng=0, target=None):
        """Create a new intelligent swarm with behavioral DNA."""
        profile = dict(self.BEHAVIOR_PROFILES.get(behavior, self.BEHAVIOR_PROFILES["scout"]))
        with self._lock:
            self.swarms[swarm_id] = {
                "id": swarm_id,
                "assets": list(asset_ids),
                "behavior": behavior,
                "profile": profile,
                "center": {"lat": center_lat, "lng": center_lng},
                "target": target,  # {lat, lng, id} or None
                "formation": "adaptive",
                "status": "active",
                "health": 1.0,  # swarm cohesion health
                "emergent": None,  # active emergent behavior
                "velocities": {aid: {"vlat": 0.0, "vlng": 0.0} for aid in asset_ids},
                "created": datetime.now(timezone.utc).isoformat(),
                "decisions": [],
                "task_queue": [],
            }
        self._log("CREATE", swarm_id, f"{behavior} swarm with {len(asset_ids)} assets")
        return self.swarms[swarm_id]

    def tick(self, assets, threats, dt):
        """Main swarm physics tick — called every sim_tick."""
        events = []
        with self._lock:
            for sid, swarm in list(self.swarms.items()):
                if swarm["status"] != "active":
                    continue
                swarm_assets = [a for aid, a in assets.items() if aid in swarm["assets"]]
                if not swarm_assets:
                    swarm["status"] = "dissolved"
                    continue

                # 1. Self-healing: detect missing assets and reorganize
                alive_ids = [a["id"] for a in swarm_assets if a["status"] == "operational"]
                if len(alive_ids) < len(swarm["assets"]):
                    lost = set(swarm["assets"]) - set(alive_ids)
                    if lost:
                        events.append(f"Swarm {sid}: Self-healing — lost {len(lost)} assets, reorganizing")
                        swarm["assets"] = alive_ids
                        # Recalculate velocities for remaining
                        swarm["velocities"] = {aid: swarm["velocities"].get(aid, {"vlat": 0, "vlng": 0})
                                                for aid in alive_ids}

                # 2. Update swarm center
                if swarm_assets:
                    swarm["center"]["lat"] = sum(a["position"]["lat"] for a in swarm_assets) / len(swarm_assets)
                    swarm["center"]["lng"] = sum(a["position"]["lng"] for a in swarm_assets) / len(swarm_assets)

                # 3. Reynolds flocking forces
                profile = swarm["profile"]
                for a in swarm_assets:
                    aid = a["id"]
                    if aid not in swarm["velocities"]:
                        swarm["velocities"][aid] = {"vlat": 0.0, "vlng": 0.0}
                    v = swarm["velocities"][aid]
                    neighbors = [n for n in swarm_assets if n["id"] != aid]
                    if not neighbors:
                        continue

                    # Separation — steer away from nearby neighbors
                    sep_lat, sep_lng = 0.0, 0.0
                    for n in neighbors:
                        dlat = a["position"]["lat"] - n["position"]["lat"]
                        dlng = a["position"]["lng"] - n["position"]["lng"]
                        dist = max(0.00001, math.sqrt(dlat**2 + dlng**2))
                        if dist < 0.005:  # ~500m threshold
                            sep_lat += dlat / (dist * dist) * 0.0001
                            sep_lng += dlng / (dist * dist) * 0.0001

                    # Alignment — match heading of neighbors
                    avg_vlat = sum(swarm["velocities"].get(n["id"], {}).get("vlat", 0) for n in neighbors) / len(neighbors)
                    avg_vlng = sum(swarm["velocities"].get(n["id"], {}).get("vlng", 0) for n in neighbors) / len(neighbors)
                    ali_lat = (avg_vlat - v["vlat"]) * 0.1
                    ali_lng = (avg_vlng - v["vlng"]) * 0.1

                    # Cohesion — steer toward center of neighbors
                    center_lat = sum(n["position"]["lat"] for n in neighbors) / len(neighbors)
                    center_lng = sum(n["position"]["lng"] for n in neighbors) / len(neighbors)
                    coh_lat = (center_lat - a["position"]["lat"]) * 0.05
                    coh_lng = (center_lng - a["position"]["lng"]) * 0.05

                    # Target seeking
                    tgt_lat, tgt_lng = 0.0, 0.0
                    if swarm.get("target"):
                        tlat = swarm["target"].get("lat", 0)
                        tlng = swarm["target"].get("lng", 0)
                        tgt_lat = (tlat - a["position"]["lat"]) * 0.03
                        tgt_lng = (tlng - a["position"]["lng"]) * 0.03

                    # Evasion — steer away from nearest active threat
                    evd_lat, evd_lng = 0.0, 0.0
                    active_threats = [t for t in threats.values()
                                     if not t.get("neutralized") and "lat" in t]
                    if active_threats:
                        nearest = min(active_threats,
                            key=lambda t: (t["lat"]-a["position"]["lat"])**2+(t["lng"]-a["position"]["lng"])**2)
                        dist_t = math.sqrt((nearest["lat"]-a["position"]["lat"])**2 +
                                          (nearest["lng"]-a["position"]["lng"])**2)
                        if dist_t < 0.02:  # ~2km
                            evd_lat = (a["position"]["lat"] - nearest["lat"]) * 0.02 / max(dist_t, 0.001)
                            evd_lng = (a["position"]["lng"] - nearest["lng"]) * 0.02 / max(dist_t, 0.001)

                    # Combine forces with behavioral DNA weights
                    v["vlat"] += (sep_lat * profile["separation"] +
                                  ali_lat * profile["alignment"] +
                                  coh_lat * profile["cohesion"] +
                                  tgt_lat * profile["target_seek"] +
                                  evd_lat * profile["evasion"]) * dt
                    v["vlng"] += (sep_lng * profile["separation"] +
                                  ali_lng * profile["alignment"] +
                                  coh_lng * profile["cohesion"] +
                                  tgt_lng * profile["target_seek"] +
                                  evd_lng * profile["evasion"]) * dt

                    # Velocity damping + limit
                    speed_limit = 0.0005 * dt
                    mag = math.sqrt(v["vlat"]**2 + v["vlng"]**2)
                    if mag > speed_limit:
                        v["vlat"] = v["vlat"] / mag * speed_limit
                        v["vlng"] = v["vlng"] / mag * speed_limit
                    v["vlat"] *= 0.95  # friction
                    v["vlng"] *= 0.95

                    # Apply velocity to position
                    a["position"]["lat"] += v["vlat"]
                    a["position"]["lng"] += v["vlng"]

                # 4. Emergent behavior execution
                if swarm.get("emergent"):
                    eb_events = self._execute_emergent(swarm, swarm_assets, threats, dt)
                    events.extend(eb_events)

                # 5. Swarm health (cohesion metric)
                if len(swarm_assets) >= 2:
                    distances = []
                    for i, a1 in enumerate(swarm_assets):
                        for a2 in swarm_assets[i+1:]:
                            d = math.sqrt((a1["position"]["lat"]-a2["position"]["lat"])**2 +
                                         (a1["position"]["lng"]-a2["position"]["lng"])**2)
                            distances.append(d)
                    avg_dist = sum(distances) / len(distances)
                    swarm["health"] = round(max(0, min(1.0, 1.0 - avg_dist / 0.05)), 3)

                # 6. Process task auctions
                self._process_auctions(swarm, swarm_assets)

        return events

    def set_emergent_behavior(self, swarm_id, behavior_name, target=None):
        """Activate an emergent behavior for a swarm."""
        if behavior_name not in self.EMERGENT_BEHAVIORS:
            return {"error": f"Unknown behavior: {behavior_name}"}
        swarm = self.swarms.get(swarm_id)
        if not swarm:
            return {"error": "Swarm not found"}
        eb = self.EMERGENT_BEHAVIORS[behavior_name]
        if len(swarm["assets"]) < eb["min_assets"]:
            return {"error": f"Need {eb['min_assets']}+ assets, have {len(swarm['assets'])}"}
        swarm["emergent"] = {"type": behavior_name, "target": target,
                             "started": datetime.now(timezone.utc).isoformat(), "phase": 0}
        self._log("EMERGENT", swarm_id, f"Activated {behavior_name}")
        return {"status": "ok", "behavior": behavior_name, "description": eb["description"]}

    def _execute_emergent(self, swarm, assets, threats, dt):
        """Execute emergent behavior physics."""
        events = []
        eb = swarm["emergent"]
        if not eb or not eb.get("target"):
            return events
        tgt = eb["target"]
        eb_type = eb["type"]
        n = len(assets)

        if eb_type == "surround":
            # Position assets evenly around target
            for i, a in enumerate(assets):
                angle = (2 * math.pi * i) / n
                radius = 0.008  # ~800m
                desired_lat = tgt["lat"] + math.cos(angle) * radius
                desired_lng = tgt["lng"] + math.sin(angle) * radius
                a["position"]["lat"] += (desired_lat - a["position"]["lat"]) * 0.05 * dt
                a["position"]["lng"] += (desired_lng - a["position"]["lng"]) * 0.05 * dt

        elif eb_type == "pincer":
            half = n // 2
            for i, a in enumerate(assets):
                side = -1 if i < half else 1
                offset = 0.01 * side
                desired_lat = tgt["lat"] + (eb["phase"] * 0.001 * dt)
                desired_lng = tgt["lng"] + offset * (1 - min(1, eb["phase"] / 20))
                a["position"]["lat"] += (desired_lat - a["position"]["lat"]) * 0.04 * dt
                a["position"]["lng"] += (desired_lng - a["position"]["lng"]) * 0.04 * dt
            eb["phase"] += dt

        elif eb_type == "funnel":
            # Create a V-shape driving target toward a point
            for i, a in enumerate(assets):
                side = 1 if i % 2 == 0 else -1
                rank = i // 2
                offset_lng = side * (0.005 + rank * 0.003)
                offset_lat = -rank * 0.003
                desired_lat = tgt["lat"] + offset_lat
                desired_lng = tgt["lng"] + offset_lng
                a["position"]["lat"] += (desired_lat - a["position"]["lat"]) * 0.04 * dt
                a["position"]["lng"] += (desired_lng - a["position"]["lng"]) * 0.04 * dt

        elif eb_type == "screen":
            spacing = 0.01
            for i, a in enumerate(assets):
                desired_lat = tgt["lat"]
                desired_lng = tgt["lng"] + (i - n/2) * spacing
                a["position"]["lat"] += (desired_lat - a["position"]["lat"]) * 0.03 * dt
                a["position"]["lng"] += (desired_lng - a["position"]["lng"]) * 0.03 * dt

        elif eb_type == "relay":
            # Space assets evenly between swarm center and target
            for i, a in enumerate(assets):
                frac = (i + 1) / (n + 1)
                desired_lat = swarm["center"]["lat"] + frac * (tgt["lat"] - swarm["center"]["lat"])
                desired_lng = swarm["center"]["lng"] + frac * (tgt["lng"] - swarm["center"]["lng"])
                a["position"]["lat"] += (desired_lat - a["position"]["lat"]) * 0.05 * dt
                a["position"]["lng"] += (desired_lng - a["position"]["lng"]) * 0.05 * dt

        elif eb_type == "decoy":
            # First asset approaches target, others flank
            if assets:
                decoy_a = assets[0]
                decoy_a["position"]["lat"] += (tgt["lat"] - decoy_a["position"]["lat"]) * 0.06 * dt
                decoy_a["position"]["lng"] += (tgt["lng"] - decoy_a["position"]["lng"]) * 0.06 * dt
                for i, a in enumerate(assets[1:], 1):
                    angle = math.pi/2 + (i-1) * math.pi / max(1, n-2)
                    desired_lat = tgt["lat"] + math.cos(angle) * 0.01
                    desired_lng = tgt["lng"] + math.sin(angle) * 0.01
                    a["position"]["lat"] += (desired_lat - a["position"]["lat"]) * 0.03 * dt
                    a["position"]["lng"] += (desired_lng - a["position"]["lng"]) * 0.03 * dt

        return events

    def create_auction(self, task_type, target, priority=5, required_sensors=None):
        """Create a task auction for swarm assets to bid on."""
        auction = {
            "id": f"AUC-{uuid.uuid4().hex[:6]}",
            "task_type": task_type,  # 'engage', 'surveil', 'jam', 'relay'
            "target": target,
            "priority": priority,
            "required_sensors": required_sensors or [],
            "bids": [],
            "winner": None,
            "status": "open",
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.auctions.append(auction)
        self._log("AUCTION", auction["id"], f"{task_type} priority={priority}")
        return auction

    def _process_auctions(self, swarm, assets):
        """Evaluate bids and assign winners for open auctions."""
        for auction in self.auctions:
            if auction["status"] != "open":
                continue
            # Auto-generate bids from swarm members
            for a in assets:
                bid_score = self._compute_bid(a, auction)
                if bid_score > 0:
                    auction["bids"].append({"asset_id": a["id"], "score": bid_score})
            if auction["bids"]:
                best = max(auction["bids"], key=lambda b: b["score"])
                auction["winner"] = best["asset_id"]
                auction["status"] = "assigned"
                self._log("AUCTION_WON", auction["id"], f"Winner: {best['asset_id']} score={best['score']:.2f}")

    def _compute_bid(self, asset, auction):
        """Compute an asset's bid score for a task auction."""
        score = 0.0
        # Proximity to target
        if auction.get("target") and auction["target"].get("lat"):
            dist = math.sqrt((asset["position"]["lat"] - auction["target"]["lat"])**2 +
                            (asset["position"]["lng"] - auction["target"]["lng"])**2)
            score += max(0, 1.0 - dist / 0.05) * 40  # closer = higher

        # Sensor match
        req = set(auction.get("required_sensors", []))
        has = set(asset.get("sensors", []))
        if req:
            match = len(req & has) / len(req) * 30
            score += match
        else:
            score += 15  # no requirement = partial credit

        # Health
        score += asset["health"]["battery_pct"] / 100 * 20

        # Weapon availability for engage tasks
        if auction["task_type"] == "engage" and asset.get("weapons"):
            score += 10
        return round(score, 2)

    def set_behavior(self, swarm_id, behavior):
        """Change swarm behavioral DNA profile."""
        if behavior not in self.BEHAVIOR_PROFILES:
            return {"error": f"Unknown behavior: {behavior}"}
        swarm = self.swarms.get(swarm_id)
        if not swarm:
            return {"error": "Swarm not found"}
        swarm["behavior"] = behavior
        swarm["profile"] = dict(self.BEHAVIOR_PROFILES[behavior])
        self._log("BEHAVIOR", swarm_id, f"Changed to {behavior}")
        return {"status": "ok", "behavior": behavior, "profile": swarm["profile"]}

    def dissolve(self, swarm_id):
        if swarm_id in self.swarms:
            self.swarms[swarm_id]["status"] = "dissolved"
            self._log("DISSOLVE", swarm_id)
            return {"status": "ok"}
        return {"error": "Not found"}

    def get_swarms(self):
        return {sid: {k: v for k, v in s.items() if k != "velocities"}
                for sid, s in self.swarms.items()}

    def get_swarm(self, sid):
        return self.swarms.get(sid, {})

    def get_auctions(self):
        return self.auctions[-50:]

    def get_stats(self):
        active = sum(1 for s in self.swarms.values() if s["status"] == "active")
        total_assets = sum(len(s["assets"]) for s in self.swarms.values() if s["status"] == "active")
        open_auctions = sum(1 for a in self.auctions if a["status"] == "open")
        return {"active_swarms": active, "total_swarmed_assets": total_assets,
                "open_auctions": open_auctions, "total_auctions": len(self.auctions)}

    def _log(self, action, sid, details=""):
        self.event_log.append({"action": action, "id": sid, "details": details,
                               "timestamp": datetime.now(timezone.utc).isoformat()})
        if len(self.event_log) > 500:
            self.event_log = self.event_log[-500:]
