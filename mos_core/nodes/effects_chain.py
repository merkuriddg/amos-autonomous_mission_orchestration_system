#!/usr/bin/env python3
"""AMOS Phase 19 — Cross-Domain Effects Chain
Orchestrate synchronized multi-domain strikes: Cyber→EW→SIGINT→Kinetic.
Cascade planning with auto-replan on failure."""

import uuid, time, threading, random
from datetime import datetime, timezone


class EffectsChain:
    """Multi-domain effects orchestration engine."""

    STAGE_TYPES = {
        "cyber_degrade":  {"domain": "cyber", "duration_s": 10, "success_rate": 0.75,
                          "description": "Degrade target communications/networks"},
        "ew_jam":         {"domain": "ew", "duration_s": 8, "success_rate": 0.80,
                          "description": "Electronic jamming of radar/comms"},
        "sigint_confirm": {"domain": "sigint", "duration_s": 5, "success_rate": 0.90,
                          "description": "SIGINT confirmation of target vulnerability"},
        "kinetic_strike": {"domain": "kinetic", "duration_s": 3, "success_rate": 0.85,
                          "description": "Kinetic engagement of target"},
        "isr_assess":     {"domain": "isr", "duration_s": 6, "success_rate": 0.92,
                          "description": "Post-strike ISR assessment"},
        "ew_suppress":    {"domain": "ew", "duration_s": 12, "success_rate": 0.78,
                          "description": "Suppress enemy air defense radar"},
        "cyber_exploit":  {"domain": "cyber", "duration_s": 15, "success_rate": 0.65,
                          "description": "Exploit target network for intel"},
        "space_deny":     {"domain": "space", "duration_s": 8, "success_rate": 0.70,
                          "description": "Deny target satellite communications"},
    }

    TEMPLATES = {
        "SEAD": {
            "name": "Suppression of Enemy Air Defenses",
            "stages": ["ew_suppress", "cyber_degrade", "sigint_confirm", "kinetic_strike", "isr_assess"],
            "description": "Classic SEAD sequence — suppress radar, degrade C2, confirm blind, strike, assess",
        },
        "CYBER_KINETIC": {
            "name": "Cyber-to-Kinetic Kill Chain",
            "stages": ["cyber_exploit", "cyber_degrade", "ew_jam", "kinetic_strike", "isr_assess"],
            "description": "Exploit network → degrade comms → jam → kinetic strike → assess",
        },
        "QUICK_STRIKE": {
            "name": "Rapid Engagement",
            "stages": ["sigint_confirm", "kinetic_strike", "isr_assess"],
            "description": "Minimal chain — confirm target, engage, assess",
        },
        "FULL_SPECTRUM": {
            "name": "Full Spectrum Dominance",
            "stages": ["space_deny", "cyber_exploit", "ew_suppress", "cyber_degrade",
                       "sigint_confirm", "kinetic_strike", "isr_assess"],
            "description": "All-domain cascading effects — space, cyber, EW, SIGINT, kinetic, ISR",
        },
        "EW_CORRIDOR": {
            "name": "Electronic Warfare Corridor",
            "stages": ["ew_suppress", "ew_jam", "sigint_confirm", "ew_suppress"],
            "description": "Create and maintain an EW corridor for safe transit",
        },
    }

    def __init__(self):
        self._lock = threading.Lock()
        self.chains = {}       # {chain_id: chain_state}
        self.history = []      # completed chains
        self.event_log = []

    def create_chain(self, name, target, stages=None, template=None):
        """Create a new effects chain from stages or template."""
        cid = f"FX-{uuid.uuid4().hex[:8]}"
        if template and template in self.TEMPLATES:
            tmpl = self.TEMPLATES[template]
            stage_types = tmpl["stages"]
            name = name or tmpl["name"]
        elif stages:
            stage_types = stages
        else:
            return {"error": "Provide stages or template"}

        chain_stages = []
        for i, stype in enumerate(stage_types):
            sdef = self.STAGE_TYPES.get(stype, {})
            chain_stages.append({
                "seq": i, "type": stype,
                "domain": sdef.get("domain", "unknown"),
                "description": sdef.get("description", ""),
                "duration_s": sdef.get("duration_s", 5),
                "success_rate": sdef.get("success_rate", 0.8),
                "status": "pending",  # pending, executing, success, failed, skipped
                "started_at": None, "completed_at": None,
                "result": None, "assigned_asset": None,
            })

        chain = {
            "id": cid, "name": name,
            "target": target,  # {id, lat, lng, type}
            "stages": chain_stages,
            "current_stage": 0,
            "status": "ready",  # ready, executing, complete, failed, aborted
            "created": datetime.now(timezone.utc).isoformat(),
            "started_at": None, "completed_at": None,
            "cascade_failures": 0,
            "replanned": False,
        }
        with self._lock:
            self.chains[cid] = chain
        self._log("CREATE", cid, f"{name} — {len(chain_stages)} stages")
        return chain

    def execute_chain(self, chain_id, operator):
        """Start executing an effects chain."""
        chain = self.chains.get(chain_id)
        if not chain:
            return {"error": "Chain not found"}
        if chain["status"] not in ("ready", "paused"):
            return {"error": f"Chain is {chain['status']}"}

        chain["status"] = "executing"
        chain["started_at"] = datetime.now(timezone.utc).isoformat()
        self._log("EXECUTE", chain_id, f"Started by {operator}")
        return {"status": "ok", "chain_id": chain_id}

    def tick(self, threats, assets, ew_jams, cyber_events, sigint_intercepts, dt):
        """Progress active chains — called from sim_tick."""
        events = []
        with self._lock:
            for cid, chain in list(self.chains.items()):
                if chain["status"] != "executing":
                    continue

                idx = chain["current_stage"]
                if idx >= len(chain["stages"]):
                    chain["status"] = "complete"
                    chain["completed_at"] = datetime.now(timezone.utc).isoformat()
                    self.history.append({
                        "id": cid, "name": chain["name"],
                        "stages_completed": sum(1 for s in chain["stages"] if s["status"] == "success"),
                        "total_stages": len(chain["stages"]),
                        "cascade_failures": chain["cascade_failures"],
                        "completed_at": chain["completed_at"],
                    })
                    events.append(f"Effects chain '{chain['name']}' COMPLETE")
                    continue

                stage = chain["stages"][idx]

                # Start stage execution
                if stage["status"] == "pending":
                    stage["status"] = "executing"
                    stage["started_at"] = datetime.now(timezone.utc).isoformat()
                    # Auto-assign best asset for this domain
                    stage["assigned_asset"] = self._find_asset(
                        stage["domain"], chain.get("target", {}), assets)
                    events.append(f"FX '{chain['name']}' Stage {idx}: {stage['type']} EXECUTING")

                # Check stage completion (time-based + stochastic)
                elif stage["status"] == "executing" and stage["started_at"]:
                    elapsed = time.time() - self._parse_ts(stage["started_at"])
                    if elapsed >= stage["duration_s"]:
                        # Determine success/failure
                        roll = random.random()
                        success_rate = stage["success_rate"]
                        # Bonus from domain assets
                        if stage.get("assigned_asset"):
                            success_rate = min(0.98, success_rate + 0.05)
                        # Penalty from previous failures
                        success_rate -= chain["cascade_failures"] * 0.05

                        if roll < success_rate:
                            stage["status"] = "success"
                            stage["result"] = "Target effect achieved"
                            stage["completed_at"] = datetime.now(timezone.utc).isoformat()
                            chain["current_stage"] += 1
                            events.append(f"FX '{chain['name']}' Stage {idx}: {stage['type']} SUCCESS")
                        else:
                            stage["status"] = "failed"
                            stage["result"] = "Effect not achieved — target resilient"
                            stage["completed_at"] = datetime.now(timezone.utc).isoformat()
                            chain["cascade_failures"] += 1
                            # Auto-replan: skip failed stage and continue
                            if chain["cascade_failures"] <= 2:
                                chain["current_stage"] += 1
                                chain["replanned"] = True
                                events.append(f"FX '{chain['name']}' Stage {idx}: {stage['type']} FAILED — replanning, skipping")
                            else:
                                chain["status"] = "failed"
                                chain["completed_at"] = datetime.now(timezone.utc).isoformat()
                                events.append(f"FX '{chain['name']}' CHAIN FAILED — too many cascade failures")
                                self.history.append({
                                    "id": cid, "name": chain["name"],
                                    "stages_completed": sum(1 for s in chain["stages"] if s["status"] == "success"),
                                    "total_stages": len(chain["stages"]),
                                    "cascade_failures": chain["cascade_failures"],
                                    "completed_at": chain["completed_at"],
                                })

        if len(self.history) > 100:
            self.history = self.history[-100:]
        return events

    def _find_asset(self, domain, target, assets):
        """Find best asset for a domain effect."""
        domain_sensors = {
            "cyber": [], "ew": ["EW_JAMMER", "AESA_RADAR"],
            "sigint": ["SIGINT", "ELINT", "COMINT"],
            "kinetic": [], "isr": ["CAMERA", "EO/IR", "LIDAR"],
            "space": [],
        }
        required = domain_sensors.get(domain, [])
        best = None
        best_dist = float("inf")
        for a in assets.values():
            if required and not any(s in a.get("sensors", []) for s in required):
                # For kinetic, check weapons
                if domain == "kinetic" and not a.get("weapons"):
                    continue
                elif domain != "kinetic":
                    continue
            if target.get("lat"):
                dist = ((a["position"]["lat"]-target["lat"])**2 +
                       (a["position"]["lng"]-target.get("lng", 0))**2) ** 0.5
                if dist < best_dist:
                    best_dist = dist
                    best = a["id"]
            elif not best:
                best = a["id"]
        return best

    def _parse_ts(self, ts_str):
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
        except Exception:
            return time.time()

    def abort_chain(self, chain_id, reason="Manual abort"):
        chain = self.chains.get(chain_id)
        if not chain:
            return {"error": "Not found"}
        chain["status"] = "aborted"
        chain["completed_at"] = datetime.now(timezone.utc).isoformat()
        self._log("ABORT", chain_id, reason)
        return {"status": "ok"}

    def get_chains(self):
        return {cid: {k: v for k, v in c.items()}
                for cid, c in self.chains.items()}

    def get_active(self):
        return [c for c in self.chains.values() if c["status"] == "executing"]

    def get_history(self):
        return list(self.history)

    def get_templates(self):
        return dict(self.TEMPLATES)

    def get_stats(self):
        total = len(self.chains)
        active = sum(1 for c in self.chains.values() if c["status"] == "executing")
        complete = sum(1 for c in self.chains.values() if c["status"] == "complete")
        failed = sum(1 for c in self.chains.values() if c["status"] == "failed")
        return {"total": total, "active": active, "complete": complete, "failed": failed,
                "templates": len(self.TEMPLATES)}

    def _log(self, action, cid, details=""):
        self.event_log.append({"action": action, "id": cid, "details": details,
                               "timestamp": datetime.now(timezone.utc).isoformat()})
        if len(self.event_log) > 500:
            self.event_log = self.event_log[-500:]
