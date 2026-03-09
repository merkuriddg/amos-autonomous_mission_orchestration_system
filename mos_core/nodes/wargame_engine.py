#!/usr/bin/env python3
"""AMOS Phase 16 — Wargaming Engine
Monte Carlo COA analysis with Markov chain force attrition modeling.
Runs thousands of engagement simulations to statistically compare COA outcomes."""

import math, random, uuid, threading, time
from datetime import datetime, timezone


class WargameEngine:
    """Run Monte Carlo simulations comparing Courses of Action."""

    # Markov transition probabilities: state → {next_state: prob}
    FORCE_TRANSITIONS = {
        "operational": {"operational": 0.85, "degraded": 0.10, "combat_ineffective": 0.04, "destroyed": 0.01},
        "degraded":    {"operational": 0.05, "degraded": 0.70, "combat_ineffective": 0.20, "destroyed": 0.05},
        "combat_ineffective": {"operational": 0.01, "degraded": 0.10, "combat_ineffective": 0.60, "destroyed": 0.29},
        "destroyed":   {"operational": 0.0, "degraded": 0.0, "combat_ineffective": 0.0, "destroyed": 1.0},
    }

    THREAT_MODIFIERS = {
        "drone": 0.8, "fighter_jet": 1.5, "missile_launcher": 1.3,
        "submarine": 1.4, "tank": 1.2, "infantry": 0.7,
        "apc": 1.0, "helicopter": 1.1, "sam_site": 1.4,
        "patrol_boat": 0.9, "radar_site": 0.6, "artillery": 1.3,
    }

    def __init__(self):
        self._lock = threading.Lock()
        self.scenarios = {}      # {scenario_id: {config, status, results}}
        self.history = []        # completed scenario summaries
        self._auto_eval = None   # last auto-evaluation result
        self._last_auto = 0

    def run_scenario(self, name, blue_forces, red_forces, coa_params, iterations=1000):
        """Run a Monte Carlo wargame scenario.
        blue_forces: [{id, type, domain, weapons, health}]
        red_forces: [{id, type, threat_level}]
        coa_params: {approach: 'direct'|'flanking'|'attrition'|'standoff'|'swarm',
                     aggression: 0.0-1.0, tempo: 'deliberate'|'hasty'|'rapid'}
        """
        sid = f"WG-{uuid.uuid4().hex[:8]}"
        scenario = {
            "id": sid, "name": name, "status": "running",
            "blue_forces": blue_forces, "red_forces": red_forces,
            "coa_params": coa_params, "iterations": iterations,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "results": None
        }
        with self._lock:
            self.scenarios[sid] = scenario

        # Run simulation in background thread
        threading.Thread(target=self._execute, args=(sid,), daemon=True).start()
        return {"id": sid, "status": "running", "iterations": iterations}

    def _execute(self, sid):
        """Execute Monte Carlo iterations for a scenario."""
        sc = self.scenarios.get(sid)
        if not sc:
            return

        blue = sc["blue_forces"]
        red = sc["red_forces"]
        coa = sc["coa_params"]
        iters = sc["iterations"]
        approach = coa.get("approach", "direct")
        aggression = coa.get("aggression", 0.5)
        tempo = coa.get("tempo", "deliberate")

        # Tempo modifiers
        tempo_mod = {"deliberate": 1.0, "hasty": 1.3, "rapid": 1.6}.get(tempo, 1.0)
        # Approach modifiers (affect blue survival vs engagement speed)
        approach_mods = {
            "direct":    {"blue_survive": 0.85, "red_attrition": 1.2, "time_mod": 0.8},
            "flanking":  {"blue_survive": 0.95, "red_attrition": 1.1, "time_mod": 1.3},
            "attrition": {"blue_survive": 0.90, "red_attrition": 0.9, "time_mod": 1.5},
            "standoff":  {"blue_survive": 0.98, "red_attrition": 0.7, "time_mod": 2.0},
            "swarm":     {"blue_survive": 0.80, "red_attrition": 1.4, "time_mod": 0.6},
        }
        amod = approach_mods.get(approach, approach_mods["direct"])

        outcomes = []
        for _ in range(iters):
            result = self._simulate_engagement(blue, red, amod, aggression, tempo_mod)
            outcomes.append(result)

        # Statistical analysis
        wins = sum(1 for o in outcomes if o["mission_success"])
        blue_losses = [o["blue_losses"] for o in outcomes]
        red_losses = [o["red_destroyed"] for o in outcomes]
        time_steps = [o["time_steps"] for o in outcomes]

        results = {
            "iterations": iters,
            "mission_success_rate": round(wins / iters * 100, 1),
            "blue_casualty_mean": round(sum(blue_losses) / iters, 2),
            "blue_casualty_median": sorted(blue_losses)[iters // 2],
            "blue_casualty_std": round(self._std(blue_losses), 2),
            "blue_casualty_p95": sorted(blue_losses)[int(iters * 0.95)],
            "red_destroyed_mean": round(sum(red_losses) / iters, 2),
            "red_destroyed_median": sorted(red_losses)[iters // 2],
            "time_to_objective_mean": round(sum(time_steps) / iters, 1),
            "time_to_objective_p95": sorted(time_steps)[int(iters * 0.95)],
            "exchange_ratio": round(sum(red_losses) / max(1, sum(blue_losses)), 2),
            "distribution": {
                "success_by_time": self._histogram(
                    [o["time_steps"] for o in outcomes if o["mission_success"]], 10),
                "blue_loss_dist": self._histogram(blue_losses, 10),
                "red_loss_dist": self._histogram(red_losses, 10),
            },
            "risk_assessment": self._assess_risk(wins / iters, blue_losses, len(blue)),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            sc["status"] = "complete"
            sc["results"] = results
            self.history.append({
                "id": sid, "name": sc["name"],
                "approach": approach, "tempo": tempo,
                "success_rate": results["mission_success_rate"],
                "exchange_ratio": results["exchange_ratio"],
                "completed_at": results["completed_at"]
            })
            if len(self.history) > 100:
                self.history = self.history[-100:]

    def _simulate_engagement(self, blue, red, amod, aggression, tempo_mod):
        """Single Monte Carlo iteration."""
        # Initialize force states
        b_states = ["operational"] * len(blue)
        r_states = ["operational"] * len(red)
        time_step = 0
        max_steps = 50

        while time_step < max_steps:
            time_step += 1

            # Blue fires at Red
            for i, bs in enumerate(b_states):
                if bs in ("destroyed", "combat_ineffective"):
                    continue
                effectiveness = 1.0 if bs == "operational" else 0.5
                fire_prob = effectiveness * aggression * amod["red_attrition"] * tempo_mod * 0.15
                for j, rs in enumerate(r_states):
                    if rs == "destroyed":
                        continue
                    if random.random() < fire_prob:
                        r_states[j] = self._markov_step(rs, hostile=True)

            # Red fires at Blue
            for j, rs in enumerate(r_states):
                if rs in ("destroyed", "combat_ineffective"):
                    continue
                threat_type = red[j].get("type", "infantry") if j < len(red) else "infantry"
                threat_mod = self.THREAT_MODIFIERS.get(threat_type, 1.0)
                fire_prob = 0.12 * threat_mod * (1.0 / amod["blue_survive"])
                for i, bs in enumerate(b_states):
                    if bs == "destroyed":
                        continue
                    if random.random() < fire_prob:
                        b_states[i] = self._markov_step(bs, hostile=True)

            # Check termination
            red_alive = sum(1 for s in r_states if s != "destroyed")
            blue_alive = sum(1 for s in b_states if s != "destroyed")
            if red_alive == 0 or blue_alive == 0:
                break
            # Mission success threshold: 70%+ red destroyed
            if red_alive <= len(red) * 0.3:
                break

        blue_losses = sum(1 for s in b_states if s in ("destroyed", "combat_ineffective"))
        red_destroyed = sum(1 for s in r_states if s == "destroyed")
        red_ci = sum(1 for s in r_states if s == "combat_ineffective")
        mission_success = (red_destroyed + red_ci) >= len(red) * 0.6 and \
                          sum(1 for s in b_states if s != "destroyed") > 0

        return {
            "mission_success": mission_success,
            "blue_losses": blue_losses,
            "red_destroyed": red_destroyed + red_ci,
            "time_steps": time_step,
            "blue_end_states": dict(zip(["op", "deg", "ci", "des"],
                [b_states.count(s) for s in ["operational", "degraded", "combat_ineffective", "destroyed"]])),
            "red_end_states": dict(zip(["op", "deg", "ci", "des"],
                [r_states.count(s) for s in ["operational", "degraded", "combat_ineffective", "destroyed"]])),
        }

    def _markov_step(self, current_state, hostile=False):
        """Advance one Markov step. If hostile, bias toward worse states."""
        transitions = dict(self.FORCE_TRANSITIONS.get(current_state, {}))
        if hostile:
            # Shift probability toward worse states
            transitions["operational"] = transitions.get("operational", 0) * 0.5
            transitions["destroyed"] = transitions.get("destroyed", 0) * 2.0
            transitions["combat_ineffective"] = transitions.get("combat_ineffective", 0) * 1.5
        total = sum(transitions.values())
        if total == 0:
            return current_state
        r = random.random() * total
        cumulative = 0
        for state, prob in transitions.items():
            cumulative += prob
            if r <= cumulative:
                return state
        return current_state

    def _assess_risk(self, success_rate, blue_losses, total_blue):
        """Generate risk assessment from outcomes."""
        avg_loss = sum(blue_losses) / max(1, len(blue_losses))
        loss_pct = avg_loss / max(1, total_blue) * 100
        if success_rate > 0.85 and loss_pct < 15:
            level, desc = "LOW", "High probability of success with acceptable losses"
        elif success_rate > 0.65 and loss_pct < 30:
            level, desc = "MODERATE", "Favorable odds but significant casualty risk"
        elif success_rate > 0.45:
            level, desc = "HIGH", "Contested outcome — consider alternative COA"
        else:
            level, desc = "EXTREME", "Mission failure likely — recommend abort or replan"
        return {"level": level, "description": desc,
                "success_rate": round(success_rate * 100, 1),
                "avg_blue_loss_pct": round(loss_pct, 1)}

    def _std(self, values):
        """Standard deviation."""
        if len(values) < 2:
            return 0
        mean = sum(values) / len(values)
        return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))

    def _histogram(self, values, bins=10):
        """Create histogram buckets."""
        if not values:
            return []
        mn, mx = min(values), max(values)
        if mn == mx:
            return [{"min": mn, "max": mx, "count": len(values)}]
        width = (mx - mn) / bins
        buckets = []
        for i in range(bins):
            lo = mn + i * width
            hi = lo + width
            count = sum(1 for v in values if lo <= v < hi) if i < bins - 1 else \
                    sum(1 for v in values if lo <= v <= hi)
            buckets.append({"min": round(lo, 1), "max": round(hi, 1), "count": count})
        return buckets

    def compare_coas(self, scenario_ids):
        """Compare multiple completed scenario results."""
        comparisons = []
        for sid in scenario_ids:
            sc = self.scenarios.get(sid)
            if sc and sc.get("results"):
                r = sc["results"]
                comparisons.append({
                    "id": sid, "name": sc["name"],
                    "approach": sc["coa_params"].get("approach"),
                    "tempo": sc["coa_params"].get("tempo"),
                    "success_rate": r["mission_success_rate"],
                    "blue_casualty_mean": r["blue_casualty_mean"],
                    "exchange_ratio": r["exchange_ratio"],
                    "time_to_objective": r["time_to_objective_mean"],
                    "risk": r["risk_assessment"]["level"],
                })
        if not comparisons:
            return {"error": "No completed scenarios found"}
        # Rank by composite score: success_rate * 0.4 + (1/casualties) * 0.3 + exchange_ratio * 0.3
        for c in comparisons:
            c["composite_score"] = round(
                c["success_rate"] * 0.4 +
                (100 / max(1, c["blue_casualty_mean"])) * 0.3 +
                min(c["exchange_ratio"] * 10, 100) * 0.3, 1)
        comparisons.sort(key=lambda x: x["composite_score"], reverse=True)
        return {"comparisons": comparisons, "recommended": comparisons[0]["id"]}

    def auto_evaluate(self, assets, threats, dt):
        """Called from sim_tick ~every 10s. Auto-run quick scenario on current force posture."""
        if time.time() - self._last_auto < 10:
            return
        self._last_auto = time.time()
        blue = [{"id": a["id"], "type": a["type"], "domain": a["domain"],
                 "weapons": a.get("weapons", []), "health": a["health"]["battery_pct"]}
                for a in assets.values() if a["status"] == "operational"]
        red = [{"id": tid, "type": t["type"],
                "threat_level": "high" if t.get("speed_kts", 0) > 50 else "medium"}
               for tid, t in threats.items() if not t.get("neutralized") and "lat" in t]
        if not blue or not red:
            self._auto_eval = {"status": "insufficient_forces", "timestamp": datetime.now(timezone.utc).isoformat()}
            return
        # Quick 200-iteration evaluation
        results = []
        for approach in ["direct", "flanking", "standoff"]:
            sid = self.run_scenario(
                f"Auto-{approach}", blue, red,
                {"approach": approach, "aggression": 0.6, "tempo": "deliberate"},
                iterations=200)
            results.append(sid)
        self._auto_eval = {"scenario_ids": [r["id"] for r in results],
                           "timestamp": datetime.now(timezone.utc).isoformat(),
                           "status": "evaluating"}

    def get_scenario(self, sid):
        return self.scenarios.get(sid, {})

    def get_history(self):
        return list(self.history)

    def get_auto_eval(self):
        return self._auto_eval or {}

    def get_stats(self):
        total = len(self.scenarios)
        complete = sum(1 for s in self.scenarios.values() if s["status"] == "complete")
        running = sum(1 for s in self.scenarios.values() if s["status"] == "running")
        return {"total": total, "complete": complete, "running": running,
                "auto_eval": self._auto_eval}
