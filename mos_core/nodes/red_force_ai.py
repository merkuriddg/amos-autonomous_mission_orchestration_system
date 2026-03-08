"""AMOS Red Force AI — Adversarial Decision Engine

Simulates a thinking enemy with:
  - Probe/attack/withdraw tactical behavior state machine
  - Adaptive frequency hopping when jammed
  - Coordinated multi-axis attacks targeting sensor gaps
  - Deception operations: decoys, false emissions, feints
"""

import math, random, time, uuid
from datetime import datetime, timezone


def _haversine_deg(lat1, lng1, lat2, lng2):
    return math.sqrt((lat2 - lat1)**2 + (lng2 - lng1)**2)


def _bearing(lat1, lng1, lat2, lng2):
    return math.degrees(math.atan2(lng2 - lng1, lat2 - lat1)) % 360


# ─── Red Force Unit ───────────────────────────────────────

class RedUnit:
    """A single adversary unit with behavioral state machine."""

    STATES = ("STAGING", "PROBING", "ATTACKING", "WITHDRAWING", "DECOYING", "DESTROYED")

    def __init__(self, unit_id, lat, lng, unit_type="drone", speed_kts=30,
                 rf_freq_mhz=915.0, power_dbm=20):
        self.id = unit_id
        self.lat = lat
        self.lng = lng
        self.type = unit_type
        self.speed_kts = speed_kts
        self.rf_freq_mhz = rf_freq_mhz
        self.original_freq = rf_freq_mhz
        self.power_dbm = power_dbm
        self.state = "STAGING"
        self.health = 100
        self.is_decoy = False
        self.target_lat = None
        self.target_lng = None
        self.jammed = False
        self.freq_hops = 0
        self.kills = 0
        self.detection_count = 0
        self.created = time.time()
        self.last_state_change = time.time()

    def move_toward(self, target_lat, target_lng, dt):
        speed_deg = self.speed_kts * 0.00001 * dt
        d = _haversine_deg(self.lat, self.lng, target_lat, target_lng)
        if d < 0.001:
            return True  # arrived
        ratio = min(1.0, speed_deg / d)
        self.lat += (target_lat - self.lat) * ratio
        self.lng += (target_lng - self.lng) * ratio
        return False

    def hop_frequency(self):
        """Adaptive frequency hopping when jammed."""
        hop_bands = [433.0, 868.0, 915.0, 2437.0, 5805.0]
        available = [f for f in hop_bands if abs(f - self.rf_freq_mhz) > 50]
        if available:
            self.rf_freq_mhz = random.choice(available) + random.uniform(-5, 5)
            self.freq_hops += 1
            self.jammed = False
            return True
        return False

    def to_dict(self):
        return {
            "id": self.id, "lat": round(self.lat, 6), "lng": round(self.lng, 6),
            "type": self.type, "state": self.state, "health": self.health,
            "speed_kts": self.speed_kts, "rf_freq_mhz": round(self.rf_freq_mhz, 2),
            "jammed": self.jammed, "is_decoy": self.is_decoy,
            "freq_hops": self.freq_hops, "kills": self.kills,
            "detection_count": self.detection_count,
        }


# ─── Red Force AI (Main Class) ───────────────────────────

class RedForceAI:
    """Adversarial AI managing all red force units."""

    def __init__(self, base_lat=27.849, base_lng=-82.521):
        self.blue_base_lat = base_lat
        self.blue_base_lng = base_lng
        self.units = {}  # unit_id -> RedUnit
        self.events = []
        self.strategy = "PROBE"  # PROBE, ATTACK, SATURATE, WITHDRAW
        self.aggression = 0.5  # 0-1, increases over time
        self.intel = {"detected_assets": {}, "sensor_gaps": [], "jammer_locations": []}
        self.stats = {"units_spawned": 0, "units_destroyed": 0, "freq_hops": 0,
                      "decoys_deployed": 0, "attacks_launched": 0}
        self._spawn_initial()

    def _spawn_initial(self):
        """Create initial red force units from staging areas."""
        staging = [
            ("RED-DRO-01", 27.78, -82.55, "drone", 45, 915.0),
            ("RED-DRO-02", 27.79, -82.48, "drone", 35, 2437.0),
            ("RED-DRO-03", 27.76, -82.52, "drone", 50, 5805.0),
            ("RED-JAM-01", 27.77, -82.51, "gps_jammer", 5, 1575.42),
            ("RED-VES-01", 27.72, -82.60, "vessel", 22, 156.8),
            ("RED-VES-02", 27.70, -82.58, "vessel", 18, 156.8),
            ("RED-RF-01", 27.80, -82.53, "rf_emitter", 0, 433.0),
        ]
        for uid, lat, lng, utype, speed, freq in staging:
            self.units[uid] = RedUnit(uid, lat, lng, utype, speed, freq)
            self.stats["units_spawned"] += 1

    def tick(self, blue_assets, blue_threats, active_jams, dt=1.0):
        """Advance red force AI one tick. Called from sim_tick."""
        events = []

        # Update intel on blue force
        self._gather_intel(blue_assets)

        # Adapt strategy based on situation
        self._update_strategy(blue_assets, active_jams)

        # Advance each unit
        for uid, unit in list(self.units.items()):
            if unit.state == "DESTROYED":
                continue

            # Check if unit is being jammed
            for jam in active_jams:
                if abs(jam.get("target_freq_mhz", 0) - unit.rf_freq_mhz) < 20:
                    unit.jammed = True
                    break

            # Adaptive frequency hopping
            if unit.jammed and random.random() < 0.3 * dt:
                if unit.hop_frequency():
                    self.stats["freq_hops"] += 1
                    events.append({
                        "type": "FREQ_HOP", "unit_id": uid,
                        "new_freq_mhz": round(unit.rf_freq_mhz, 2),
                        "hop_count": unit.freq_hops,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

            # State machine
            if unit.state == "STAGING":
                # Wait, then begin probing
                if time.time() - unit.created > random.uniform(10, 30):
                    unit.state = "PROBING"
                    unit.target_lat = self.blue_base_lat + random.uniform(-0.03, 0.03)
                    unit.target_lng = self.blue_base_lng + random.uniform(-0.03, 0.03)

            elif unit.state == "PROBING":
                if unit.target_lat:
                    arrived = unit.move_toward(unit.target_lat, unit.target_lng, dt)
                    if arrived:
                        unit.detection_count += 1
                        # Decide: attack or withdraw based on detection
                        if self.aggression > 0.6 and not unit.is_decoy:
                            unit.state = "ATTACKING"
                            # Target nearest blue asset
                            nearest = self._find_nearest_blue(unit, blue_assets)
                            if nearest:
                                bp = nearest.get("position", nearest)
                                unit.target_lat = bp.get("lat", 0)
                                unit.target_lng = bp.get("lng", 0)
                            events.append({
                                "type": "ATTACK_INITIATED", "unit_id": uid,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })
                            self.stats["attacks_launched"] += 1
                        else:
                            # Set new probe point
                            unit.target_lat = self.blue_base_lat + random.uniform(-0.05, 0.05)
                            unit.target_lng = self.blue_base_lng + random.uniform(-0.05, 0.05)

                # Withdraw if heavily detected
                if unit.detection_count > 3 and self.aggression < 0.7:
                    unit.state = "WITHDRAWING"

            elif unit.state == "ATTACKING":
                if unit.target_lat:
                    arrived = unit.move_toward(unit.target_lat, unit.target_lng, dt)
                    if arrived:
                        # Simulated attack effect
                        unit.state = "WITHDRAWING"
                        unit.target_lat = unit.lat + random.uniform(-0.05, 0.05)
                        unit.target_lng = unit.lng + random.uniform(-0.05, 0.05)

                # Take evasive action if under fire
                if random.random() < 0.05 * dt:
                    unit.lat += random.uniform(-0.003, 0.003)
                    unit.lng += random.uniform(-0.003, 0.003)

            elif unit.state == "WITHDRAWING":
                if unit.target_lat:
                    arrived = unit.move_toward(unit.target_lat, unit.target_lng, dt)
                    if arrived:
                        unit.state = "PROBING"  # re-engage
                        unit.target_lat = self.blue_base_lat + random.uniform(-0.04, 0.04)
                        unit.target_lng = self.blue_base_lng + random.uniform(-0.04, 0.04)

            elif unit.state == "DECOYING":
                # Decoys move erratically to draw attention
                unit.lat += random.uniform(-0.002, 0.002) * dt
                unit.lng += random.uniform(-0.002, 0.002) * dt
                # Emit false signals
                if random.random() < 0.3 * dt:
                    unit.rf_freq_mhz = random.choice([915.0, 2437.0, 5805.0])

        # Spawn reinforcements based on aggression
        if random.random() < 0.02 * self.aggression * dt and len(self.units) < 20:
            self._spawn_reinforcement(events)

        # Deploy decoys periodically
        if random.random() < 0.01 * dt and self.stats["decoys_deployed"] < 5:
            self._deploy_decoy(events)

        # Increase aggression over time
        self.aggression = min(1.0, self.aggression + 0.001 * dt)

        # Sync units back to threat dict format
        self._sync_to_threats(blue_threats)

        # Trim events
        self.events.extend(events)
        if len(self.events) > 500:
            self.events = self.events[-500:]

        return events

    def _gather_intel(self, blue_assets):
        """Observe blue force positions and identify sensor gaps."""
        for aid, a in blue_assets.items():
            ap = a.get("position", a)
            self.intel["detected_assets"][aid] = {
                "lat": ap.get("lat", 0), "lng": ap.get("lng", 0),
                "domain": a.get("domain", ""), "sensors": a.get("sensors", []),
            }

        # Identify sensor coverage gaps (simplified)
        if blue_assets:
            lats = [a.get("position", a).get("lat", 0) for a in blue_assets.values()]
            lngs = [a.get("position", a).get("lng", 0) for a in blue_assets.values()]
            center_lat, center_lng = sum(lats)/len(lats), sum(lngs)/len(lngs)
            # Gaps are areas far from any blue sensor
            gaps = []
            for angle in range(0, 360, 45):
                rad = math.radians(angle)
                check_lat = center_lat + 0.05 * math.cos(rad)
                check_lng = center_lng + 0.05 * math.sin(rad)
                min_dist = min(_haversine_deg(check_lat, check_lng,
                    a.get("position", a).get("lat", 0), a.get("position", a).get("lng", 0))
                    for a in blue_assets.values())
                if min_dist > 0.03:
                    gaps.append({"lat": check_lat, "lng": check_lng, "bearing": angle})
            self.intel["sensor_gaps"] = gaps

    def _update_strategy(self, blue_assets, active_jams):
        """Adapt overall strategy based on situation."""
        n_units = sum(1 for u in self.units.values() if u.state != "DESTROYED")
        n_jams = len(active_jams)

        if n_jams > 2:
            self.aggression = max(0.3, self.aggression - 0.05)
        if n_units < 3:
            self.strategy = "WITHDRAW"
        elif self.aggression > 0.7:
            self.strategy = "ATTACK"
        else:
            self.strategy = "PROBE"

    def _find_nearest_blue(self, red_unit, blue_assets):
        best, bd = None, float("inf")
        for aid, a in blue_assets.items():
            ap = a.get("position", a)
            d = _haversine_deg(red_unit.lat, red_unit.lng, ap.get("lat", 0), ap.get("lng", 0))
            if d < bd:
                bd, best = d, a
        return best

    def _spawn_reinforcement(self, events):
        n = self.stats["units_spawned"] + 1
        uid = f"RED-REINF-{n:02d}"
        # Spawn from a random direction
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(0.06, 0.10)
        lat = self.blue_base_lat + dist * math.cos(angle)
        lng = self.blue_base_lng + dist * math.sin(angle)
        utype = random.choice(["drone", "drone", "vessel", "rf_emitter"])
        speed = random.randint(20, 50) if utype == "drone" else random.randint(10, 25)
        freq = random.choice([433.0, 868.0, 915.0, 2437.0, 5805.0])

        unit = RedUnit(uid, lat, lng, utype, speed, freq)
        unit.state = "PROBING"
        unit.target_lat = self.blue_base_lat + random.uniform(-0.03, 0.03)
        unit.target_lng = self.blue_base_lng + random.uniform(-0.03, 0.03)
        self.units[uid] = unit
        self.stats["units_spawned"] += 1
        events.append({
            "type": "REINFORCEMENT", "unit_id": uid, "unit_type": utype,
            "lat": round(lat, 4), "lng": round(lng, 4),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _deploy_decoy(self, events):
        # Pick a random active unit to spawn decoy near
        active = [u for u in self.units.values() if u.state not in ("DESTROYED", "DECOYING")]
        if not active:
            return
        parent = random.choice(active)
        uid = f"RED-DECOY-{self.stats['decoys_deployed'] + 1:02d}"
        decoy = RedUnit(uid, parent.lat + random.uniform(-0.01, 0.01),
                        parent.lng + random.uniform(-0.01, 0.01),
                        parent.type, parent.speed_kts * 0.8, parent.rf_freq_mhz)
        decoy.is_decoy = True
        decoy.state = "DECOYING"
        decoy.health = 20
        self.units[uid] = decoy
        self.stats["decoys_deployed"] += 1
        events.append({
            "type": "DECOY_DEPLOYED", "unit_id": uid, "parent": parent.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _sync_to_threats(self, blue_threats):
        """Sync red units into the blue threat tracking dict."""
        for uid, unit in self.units.items():
            if unit.state == "DESTROYED":
                if uid in blue_threats:
                    blue_threats[uid]["neutralized"] = True
                continue
            blue_threats[uid] = {
                "id": uid, "type": unit.type,
                "lat": round(unit.lat, 6), "lng": round(unit.lng, 6),
                "rf_freq_mhz": round(unit.rf_freq_mhz, 2),
                "speed_kts": unit.speed_kts,
                "neutralized": False,
                "detected_by": [],
                "first_detected": None,
                "is_decoy": unit.is_decoy,
                "red_state": unit.state,
            }

    def neutralize(self, unit_id):
        if unit_id in self.units:
            self.units[unit_id].state = "DESTROYED"
            self.units[unit_id].health = 0
            self.stats["units_destroyed"] += 1
            return True
        return False

    def get_units(self):
        return {uid: u.to_dict() for uid, u in self.units.items()}

    def get_intel(self):
        return dict(self.intel)

    def get_events(self, limit=50):
        return self.events[-limit:]

    def get_stats(self):
        active = sum(1 for u in self.units.values() if u.state != "DESTROYED")
        return {**self.stats, "active_units": active, "strategy": self.strategy,
                "aggression": round(self.aggression, 2)}
