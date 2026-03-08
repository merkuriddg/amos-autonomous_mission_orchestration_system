"""AMOS Cognitive Decision Engine — OODA Loop + Monte Carlo COA + Explainable AI

Replaces random HAL recommendations with a structured decision pipeline:
  1. OBSERVE  — ingest threat/asset state
  2. ORIENT   — classify situation, assess threat intent
  3. DECIDE   — generate and score COAs via Monte Carlo simulation
  4. ACT      — emit ranked recommendations with reasoning chains
"""

import math, random, time, uuid, copy
from datetime import datetime, timezone


# ─── OODA Loop Pipeline ──────────────────────────────────

class OODALoop:
    """Per-threat OODA cycle with time-pressure scoring."""

    PHASES = ["OBSERVE", "ORIENT", "DECIDE", "ACT"]
    MAX_DWELL_SEC = {"OBSERVE": 15, "ORIENT": 20, "DECIDE": 30, "ACT": 10}

    def __init__(self, threat_id):
        self.threat_id = threat_id
        self.phase = "OBSERVE"
        self.phase_start = time.time()
        self.observations = []
        self.orientation = {}
        self.coas = []
        self.selected_coa = None
        self.completed = False
        self.loop_count = 0

    def elapsed(self):
        return time.time() - self.phase_start

    def pressure(self):
        """0.0 = no pressure, 1.0 = critical delay."""
        max_t = self.MAX_DWELL_SEC.get(self.phase, 20)
        return min(1.0, self.elapsed() / max_t)

    def advance(self):
        idx = self.PHASES.index(self.phase)
        if idx < len(self.PHASES) - 1:
            self.phase = self.PHASES[idx + 1]
            self.phase_start = time.time()
        else:
            self.completed = True
            self.loop_count += 1
            self.phase = "OBSERVE"
            self.phase_start = time.time()

    def to_dict(self):
        return {
            "threat_id": self.threat_id,
            "phase": self.phase,
            "elapsed_sec": round(self.elapsed(), 1),
            "pressure": round(self.pressure(), 2),
            "loop_count": self.loop_count,
            "observations": len(self.observations),
            "coas": len(self.coas),
            "selected_coa": self.selected_coa,
            "completed": self.completed,
        }


# ─── Monte Carlo COA Simulator ───────────────────────────

class COATemplate:
    """A Course of Action template with stochastic parameters."""

    TEMPLATES = [
        {"name": "DIRECT ENGAGE", "risk": "HIGH", "time_min": 2, "time_max": 8,
         "p_success_base": 0.75, "friendly_loss_p": 0.15, "collateral_p": 0.10,
         "requires": ["weapons"], "description": "Kinetic engagement — direct fire or guided munition."},
        {"name": "EW SUPPRESS", "risk": "LOW", "time_min": 1, "time_max": 5,
         "p_success_base": 0.60, "friendly_loss_p": 0.02, "collateral_p": 0.01,
         "requires": ["EW_JAMMER"], "description": "Electronic warfare — jam C2 link, deny GPS."},
        {"name": "SWARM OVERWHELM", "risk": "MEDIUM", "time_min": 5, "time_max": 15,
         "p_success_base": 0.85, "friendly_loss_p": 0.08, "collateral_p": 0.05,
         "requires": ["swarm_3+"], "description": "Multi-asset convergence — saturate defenses."},
        {"name": "ISR THEN STRIKE", "risk": "MEDIUM", "time_min": 8, "time_max": 20,
         "p_success_base": 0.80, "friendly_loss_p": 0.05, "collateral_p": 0.03,
         "requires": ["EO/IR", "weapons"], "description": "Positive ID via ISR, then precision strike."},
        {"name": "CYBER DISRUPT", "risk": "LOW", "time_min": 3, "time_max": 12,
         "p_success_base": 0.50, "friendly_loss_p": 0.01, "collateral_p": 0.0,
         "requires": ["cyber"], "description": "Network exploitation — inject false data or deny C2."},
        {"name": "CONTAIN & MONITOR", "risk": "LOW", "time_min": 1, "time_max": 60,
         "p_success_base": 0.40, "friendly_loss_p": 0.01, "collateral_p": 0.0,
         "requires": [], "description": "Establish sensor perimeter — track and report, no engagement."},
        {"name": "DECEPTION OP", "risk": "MEDIUM", "time_min": 5, "time_max": 15,
         "p_success_base": 0.55, "friendly_loss_p": 0.03, "collateral_p": 0.02,
         "requires": ["decoy"], "description": "Deploy decoys to divert threat attention."},
    ]

    @classmethod
    def get_applicable(cls, assets, threat):
        """Return COA templates that the current force can execute."""
        has_weapons = any(a.get("weapons") for a in assets)
        has_ew = any("EW_JAMMER" in (a.get("sensors") or []) for a in assets)
        has_isr = any(s in (a.get("sensors") or [])
                      for a in assets for s in ["EO/IR", "SAR", "AESA_RADAR"])
        has_swarm = len(assets) >= 3
        has_decoy = any(a.get("role") == "decoy" for a in assets)

        caps = set()
        if has_weapons: caps.add("weapons")
        if has_ew: caps.add("EW_JAMMER")
        if has_isr: caps.update(["EO/IR", "SAR"])
        if has_swarm: caps.add("swarm_3+")
        if has_decoy: caps.add("decoy")
        caps.add("cyber")  # always available in sim

        applicable = []
        for t in cls.TEMPLATES:
            if all(r in caps for r in t["requires"]):
                applicable.append(dict(t))
        return applicable


def monte_carlo_coa(coa_template, threat, assets, n_runs=200):
    """Run N simulated engagements for a COA, return statistics."""
    successes, friendly_losses, collateral_events = 0, 0, 0
    times = []

    # Modifiers based on threat characteristics
    threat_level = threat.get("threat_level", threat.get("severity", "MEDIUM"))
    threat_mod = {"LOW": 0.10, "MEDIUM": 0.0, "HIGH": -0.10, "CRITICAL": -0.20}.get(
        str(threat_level).upper(), 0.0)

    # Proximity modifier — closer assets = faster response
    distances = []
    for a in assets:
        ap = a.get("position", a)
        if "lat" in ap and "lat" in threat:
            d = math.sqrt((ap["lat"] - threat["lat"])**2 + (ap.get("lng", ap.get("lon", 0)) - threat.get("lng", threat.get("lon", 0)))**2)
            distances.append(d)
    avg_dist = sum(distances) / len(distances) if distances else 0.05
    proximity_mod = max(-0.1, 0.1 - avg_dist * 2)

    p_base = coa_template["p_success_base"] + threat_mod + proximity_mod
    p_base = max(0.05, min(0.98, p_base))

    for _ in range(n_runs):
        # Stochastic engagement
        roll = random.random()
        success = roll < p_base
        if success:
            successes += 1
        if random.random() < coa_template["friendly_loss_p"]:
            friendly_losses += 1
        if random.random() < coa_template["collateral_p"]:
            collateral_events += 1
        t = random.uniform(coa_template["time_min"], coa_template["time_max"])
        times.append(t)

    return {
        "coa_name": coa_template["name"],
        "description": coa_template["description"],
        "risk": coa_template["risk"],
        "n_runs": n_runs,
        "p_success": round(successes / n_runs, 3),
        "p_friendly_loss": round(friendly_losses / n_runs, 3),
        "p_collateral": round(collateral_events / n_runs, 3),
        "avg_time_min": round(sum(times) / len(times), 1),
        "min_time_min": round(min(times), 1),
        "max_time_min": round(max(times), 1),
        "composite_score": 0.0,  # filled in below
    }


def score_coas(coa_results):
    """Composite score: weighted combination of success, risk, and time."""
    for c in coa_results:
        c["composite_score"] = round(
            c["p_success"] * 0.50
            - c["p_friendly_loss"] * 0.25
            - c["p_collateral"] * 0.15
            - (c["avg_time_min"] / 60.0) * 0.10,
            4)
    coa_results.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, c in enumerate(coa_results):
        c["rank"] = i + 1
    return coa_results


# ─── Explainable Reasoning ────────────────────────────────

def build_reasoning_chain(threat, coa, assets, ooda):
    """Generate a human-readable reasoning chain for a recommendation."""
    chain = []
    chain.append(f"OBSERVE: Threat {threat.get('id','?')} ({threat.get('type','unknown')}) "
                 f"detected at ({threat.get('lat',0):.4f}, {threat.get('lng', threat.get('lon',0)):.4f})")

    threat_level = threat.get("threat_level", threat.get("severity", "MEDIUM"))
    chain.append(f"ORIENT: Threat classified as {threat_level} severity — "
                 f"{'immediate response required' if threat_level in ('HIGH','CRITICAL') else 'standard response timeline'}")

    chain.append(f"DECIDE: Evaluated {len(ooda.coas)} COAs via {coa['n_runs']} Monte Carlo runs — "
                 f"'{coa['coa_name']}' ranked #{coa['rank']} with P(success)={coa['p_success']:.0%}")

    n_assets = len(assets)
    chain.append(f"ACT: Recommend {coa['coa_name']} using {n_assets} available asset(s) — "
                 f"est. {coa['avg_time_min']:.0f} min, {coa['risk']} risk, "
                 f"P(friendly loss)={coa['p_friendly_loss']:.1%}")

    return chain


# ─── Cognitive Engine (Main Class) ────────────────────────

class CognitiveEngine:
    """Full cognitive decision engine managing OODA loops across all threats."""

    def __init__(self):
        self.loops = {}          # threat_id -> OODALoop
        self.recommendations = []  # scored, explained recommendations
        self.coa_cache = {}      # threat_id -> last COA results
        self.stats = {"loops_completed": 0, "coas_generated": 0, "recommendations": 0}

    def tick(self, assets, threats, dt=1.0):
        """Advance all OODA loops. Called from sim_tick."""
        events = []
        active_threats = {tid: t for tid, t in threats.items()
                          if not t.get("neutralized") and ("lat" in t or "type" in t)}

        # Create loops for new threats
        for tid in active_threats:
            if tid not in self.loops:
                self.loops[tid] = OODALoop(tid)

        # Remove loops for neutralized threats
        for tid in list(self.loops):
            if tid not in active_threats:
                del self.loops[tid]

        # Advance each loop
        for tid, loop in self.loops.items():
            threat = active_threats[tid]

            if loop.phase == "OBSERVE":
                # Gather sensor detections
                detecting = [a for a in assets.values()
                             if self._can_detect(a, threat)]
                loop.observations = [{"asset": a["id"], "time": time.time()} for a in detecting]
                if len(detecting) >= 1 or loop.pressure() > 0.6:
                    loop.advance()

            elif loop.phase == "ORIENT":
                # Classify and assess intent
                loop.orientation = self._assess_threat(threat, assets)
                if loop.pressure() > 0.4 or loop.orientation.get("confidence", 0) > 0.5:
                    loop.advance()

            elif loop.phase == "DECIDE":
                # Generate and score COAs
                nearby = [a for a in assets.values() if self._in_range(a, threat, 0.15)]
                if not nearby:
                    nearby = list(assets.values())[:5]

                templates = COATemplate.get_applicable(nearby, threat)
                coa_results = [monte_carlo_coa(t, threat, nearby) for t in templates]
                scored = score_coas(coa_results)
                loop.coas = scored
                self.coa_cache[tid] = scored
                self.stats["coas_generated"] += len(scored)

                if scored:
                    loop.selected_coa = scored[0]
                loop.advance()

            elif loop.phase == "ACT":
                # Emit recommendation
                if loop.selected_coa:
                    nearby = [a for a in assets.values() if self._in_range(a, threat, 0.15)]
                    if not nearby:
                        nearby = list(assets.values())[:3]

                    reasoning = build_reasoning_chain(threat, loop.selected_coa, nearby, loop)
                    rec = {
                        "id": f"COG-{uuid.uuid4().hex[:8]}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "threat_id": tid,
                        "threat_type": threat.get("type", "unknown"),
                        "coa": loop.selected_coa,
                        "all_coas": loop.coas,
                        "reasoning_chain": reasoning,
                        "ooda_loops": loop.loop_count + 1,
                        "time_pressure": round(loop.pressure(), 2),
                        "recommended_assets": [a["id"] for a in nearby[:4]],
                        "status": "pending",
                        "orientation": loop.orientation,
                    }
                    self.recommendations.append(rec)
                    events.append(rec)
                    self.stats["recommendations"] += 1

                self.stats["loops_completed"] += 1
                loop.advance()  # restart cycle

        # Trim old recommendations
        if len(self.recommendations) > 500:
            self.recommendations = self.recommendations[-500:]

        return events

    def get_recommendations(self, limit=50):
        return self.recommendations[-limit:]

    def get_loops(self):
        return {tid: loop.to_dict() for tid, loop in self.loops.items()}

    def get_coas(self, threat_id=None):
        if threat_id:
            return self.coa_cache.get(threat_id, [])
        return dict(self.coa_cache)

    def action_recommendation(self, rec_id, action, operator="SYSTEM"):
        for r in self.recommendations:
            if r["id"] == rec_id:
                r["status"] = action
                r["actioned_by"] = operator
                r["actioned_at"] = datetime.now(timezone.utc).isoformat()
                return r
        return None

    def get_stats(self):
        return {**self.stats, "active_loops": len(self.loops),
                "pending_recs": sum(1 for r in self.recommendations if r["status"] == "pending")}

    # ─── Helpers ──────────────────────────

    @staticmethod
    def _can_detect(asset, threat):
        sensors = asset.get("sensors") or []
        if not sensors:
            return False
        if "lat" not in threat:
            return bool(sensors)
        ap = asset.get("position", asset)
        d = math.sqrt((ap.get("lat", 0) - threat["lat"])**2 +
                      (ap.get("lng", 0) - threat.get("lng", threat.get("lon", 0)))**2)
        max_range = 0.08 if any(s in sensors for s in ["AESA_RADAR", "AEW_RADAR"]) else 0.04
        return d < max_range

    @staticmethod
    def _in_range(asset, threat, max_deg=0.1):
        if "lat" not in threat:
            return True
        ap = asset.get("position", asset)
        d = math.sqrt((ap.get("lat", 0) - threat["lat"])**2 +
                      (ap.get("lng", 0) - threat.get("lng", threat.get("lon", 0)))**2)
        return d < max_deg

    @staticmethod
    def _assess_threat(threat, assets):
        """Simple threat intent assessment."""
        ttype = threat.get("type", "unknown").lower()
        intent_map = {
            "drone": "ISR/STRIKE", "gps_jammer": "DENY_PNT",
            "rf_emitter": "C2_RELAY", "vessel": "MARITIME_APPROACH",
            "cyber": "NETWORK_EXPLOIT", "infantry": "GROUND_ASSAULT",
            "vehicle": "MECHANIZED_ADVANCE",
        }
        intent = intent_map.get(ttype, "UNKNOWN")
        speed = threat.get("speed_kts", 0)
        closing = speed > 10
        confidence = 0.7 if ttype in intent_map else 0.3
        if closing:
            confidence = min(1.0, confidence + 0.2)

        return {
            "assessed_intent": intent,
            "confidence": round(confidence, 2),
            "closing": closing,
            "speed_kts": speed,
            "threat_type": ttype,
            "priority": "HIGH" if closing or ttype in ("drone", "gps_jammer") else "MEDIUM",
        }
