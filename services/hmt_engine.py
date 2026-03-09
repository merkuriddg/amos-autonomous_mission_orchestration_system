#!/usr/bin/env python3
"""AMOS Phase 21 — Human-Machine Teaming (HMT) Engine
Adaptive autonomy, trust calibration, cognitive load monitoring,
delegation protocols."""

import time, random, threading
from datetime import datetime, timezone


class HMTEngine:
    """Human-Machine Teaming — adaptive autonomy based on operator workload."""

    AUTONOMY_LEVELS = {
        1: {"name": "Manual", "description": "Human controls all decisions", "ai_authority": 0.0},
        2: {"name": "Advisory", "description": "AI recommends, human decides", "ai_authority": 0.2},
        3: {"name": "Consensual", "description": "AI proposes, human approves/rejects", "ai_authority": 0.4},
        4: {"name": "Monitored", "description": "AI acts, human can override", "ai_authority": 0.7},
        5: {"name": "Autonomous", "description": "AI acts independently, human informed", "ai_authority": 0.9},
    }

    FATIGUE_THRESHOLDS = {
        "low": {"click_rate_max": 30, "response_time_min": 200, "description": "Operator alert and responsive"},
        "moderate": {"click_rate_max": 15, "response_time_min": 500, "description": "Normal workload, slight delay"},
        "high": {"click_rate_max": 8, "response_time_min": 1000, "description": "Possible fatigue — recommend break"},
        "critical": {"click_rate_max": 3, "response_time_min": 2000, "description": "FATIGUE ALERT — impaired performance"},
    }

    def __init__(self):
        self._lock = threading.Lock()
        self.operators = {}        # {user: {workload, trust, autonomy_level, ...}}
        self.delegations = {}      # {domain: {delegated_to, level, delegated_by, ...}}
        self.global_autonomy = 3   # system-wide default
        self._last_workload = 0
        self._last_trust = 0
        self._last_adapt = 0
        self.event_log = []

    def register_operator(self, user, name, role):
        """Register or update an operator for HMT tracking."""
        if user not in self.operators:
            self.operators[user] = {
                "user": user, "name": name, "role": role,
                "autonomy_level": self.global_autonomy,
                "trust_scores": {
                    "air": 0.7, "ground": 0.7, "maritime": 0.7,
                    "cyber": 0.6, "ew": 0.6, "overall": 0.7,
                },
                "workload": {
                    "current": "low", "click_rate": 0, "avg_response_ms": 300,
                    "tasks_pending": 0, "tasks_completed": 0,
                    "session_start": time.time(), "last_action": time.time(),
                },
                "fatigue": "low",
                "delegation_authority": ["air", "ground", "maritime"] if role == "commander" else [],
                "interactions": [],
            }
        return self.operators[user]

    def record_interaction(self, user, action_type, response_time_ms=None):
        """Record an operator interaction for workload/trust analysis."""
        op = self.operators.get(user)
        if not op:
            return
        now = time.time()
        op["workload"]["last_action"] = now
        op["workload"]["tasks_completed"] += 1
        interaction = {
            "type": action_type, "timestamp": now,
            "response_time_ms": response_time_ms,
        }
        op["interactions"].append(interaction)
        if len(op["interactions"]) > 200:
            op["interactions"] = op["interactions"][-200:]

        # Update rolling click rate (clicks in last 60s)
        recent = [i for i in op["interactions"] if now - i["timestamp"] < 60]
        op["workload"]["click_rate"] = len(recent)

        # Update average response time
        recent_rt = [i["response_time_ms"] for i in recent if i.get("response_time_ms")]
        if recent_rt:
            op["workload"]["avg_response_ms"] = round(sum(recent_rt) / len(recent_rt))

    def tick(self, operators_online, hal_pending, threat_count, dt):
        """Main HMT tick — update workload, trust, adapt autonomy."""
        now = time.time()

        # Workload sampling every ~3s
        if now - self._last_workload > 3:
            self._last_workload = now
            self._sample_workload(operators_online, hal_pending, threat_count)

        # Trust score update every ~10s
        if now - self._last_trust > 10:
            self._last_trust = now
            self._update_trust()

        # Autonomy adaptation every ~15s
        if now - self._last_adapt > 15:
            self._last_adapt = now
            self._adapt_autonomy()

    def _sample_workload(self, operators_online, hal_pending, threat_count):
        """Sample and classify operator workload."""
        with self._lock:
            for user, op in self.operators.items():
                wl = op["workload"]
                click_rate = wl["click_rate"]
                avg_rt = wl["avg_response_ms"]
                idle_time = time.time() - wl["last_action"]

                # Task queue pressure
                wl["tasks_pending"] = hal_pending

                # Classify workload
                if click_rate > 25 or (hal_pending > 10 and threat_count > 5):
                    wl["current"] = "overloaded"
                elif click_rate > 15 or hal_pending > 5:
                    wl["current"] = "high"
                elif click_rate > 5:
                    wl["current"] = "moderate"
                elif idle_time > 120:
                    wl["current"] = "idle"
                else:
                    wl["current"] = "low"

                # Fatigue assessment
                session_hours = (time.time() - wl["session_start"]) / 3600
                if session_hours > 6 or (avg_rt > 2000 and click_rate < 3):
                    op["fatigue"] = "critical"
                elif session_hours > 4 or avg_rt > 1000:
                    op["fatigue"] = "high"
                elif session_hours > 2 or avg_rt > 500:
                    op["fatigue"] = "moderate"
                else:
                    op["fatigue"] = "low"

    def _update_trust(self):
        """Update trust scores based on operator performance."""
        with self._lock:
            for user, op in self.operators.items():
                ts = op["trust_scores"]
                # Trust improves with consistent interaction
                completed = op["workload"]["tasks_completed"]
                if completed > 10:
                    for domain in ts:
                        ts[domain] = min(1.0, ts[domain] + random.uniform(0, 0.01))
                # Trust degrades with fatigue
                if op["fatigue"] in ("high", "critical"):
                    for domain in ts:
                        ts[domain] = max(0.1, ts[domain] - random.uniform(0, 0.02))
                # Overall = weighted average
                domains = [d for d in ts if d != "overall"]
                ts["overall"] = round(sum(ts[d] for d in domains) / len(domains), 3)

    def _adapt_autonomy(self):
        """Automatically adapt autonomy levels based on workload + trust."""
        with self._lock:
            for user, op in self.operators.items():
                wl = op["workload"]["current"]
                fatigue = op["fatigue"]
                trust = op["trust_scores"]["overall"]
                current_level = op["autonomy_level"]

                # Determine ideal level
                if wl == "overloaded" or fatigue == "critical":
                    ideal = 5  # Go full autonomous
                elif wl == "high" or fatigue == "high":
                    ideal = 4  # Monitored autonomy
                elif trust > 0.8 and wl in ("moderate", "low"):
                    ideal = 3  # Consensual
                elif trust < 0.4:
                    ideal = 2  # Advisory only
                else:
                    ideal = self.global_autonomy

                # Gradual adjustment (one level at a time)
                if ideal > current_level:
                    new_level = min(5, current_level + 1)
                    op["autonomy_level"] = new_level
                    self._log(user, f"Autonomy INCREASED to {new_level} ({self.AUTONOMY_LEVELS[new_level]['name']}) — workload: {wl}, fatigue: {fatigue}")
                elif ideal < current_level and wl not in ("overloaded", "high"):
                    new_level = max(1, current_level - 1)
                    op["autonomy_level"] = new_level
                    self._log(user, f"Autonomy DECREASED to {new_level} ({self.AUTONOMY_LEVELS[new_level]['name']})")

    def delegate(self, commander, domain, level, target_user=None):
        """Commander delegates decision authority for a domain."""
        op = self.operators.get(commander)
        if not op or op["role"] != "commander":
            return {"error": "Commander access required"}
        if domain not in op.get("delegation_authority", []) and domain != "all":
            return {"error": f"No delegation authority for {domain}"}
        self.delegations[domain] = {
            "domain": domain, "level": level,
            "delegated_by": commander, "target_user": target_user or "AI",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._log(commander, f"DELEGATED {domain} authority at level {level} to {target_user or 'AI'}")
        return {"status": "ok", "delegation": self.delegations[domain]}

    def revoke_delegation(self, commander, domain):
        if domain in self.delegations:
            del self.delegations[domain]
            self._log(commander, f"REVOKED delegation for {domain}")
            return {"status": "ok"}
        return {"error": "No active delegation"}

    def set_global_autonomy(self, level, operator):
        """Set system-wide default autonomy level."""
        if level not in self.AUTONOMY_LEVELS:
            return {"error": f"Invalid level {level}"}
        self.global_autonomy = level
        self._log(operator, f"Global autonomy set to {level} ({self.AUTONOMY_LEVELS[level]['name']})")
        return {"status": "ok", "level": level, "name": self.AUTONOMY_LEVELS[level]["name"]}

    def get_status(self):
        return {user: {
            "name": op["name"], "role": op["role"],
            "autonomy_level": op["autonomy_level"],
            "autonomy_name": self.AUTONOMY_LEVELS.get(op["autonomy_level"], {}).get("name", "Unknown"),
            "workload": op["workload"]["current"],
            "fatigue": op["fatigue"],
            "trust": op["trust_scores"]["overall"],
            "click_rate": op["workload"]["click_rate"],
            "tasks_pending": op["workload"]["tasks_pending"],
            "session_hours": round((time.time() - op["workload"]["session_start"]) / 3600, 1),
        } for user, op in self.operators.items()}

    def get_trust_details(self, user=None):
        if user:
            op = self.operators.get(user)
            return op["trust_scores"] if op else {}
        return {u: op["trust_scores"] for u, op in self.operators.items()}

    def get_workload(self, user=None):
        if user:
            op = self.operators.get(user)
            return op["workload"] if op else {}
        return {u: op["workload"] for u, op in self.operators.items()}

    def get_delegations(self):
        return dict(self.delegations)

    def get_autonomy_levels(self):
        return dict(self.AUTONOMY_LEVELS)

    def get_stats(self):
        total_ops = len(self.operators)
        fatigued = sum(1 for op in self.operators.values() if op["fatigue"] in ("high", "critical"))
        overloaded = sum(1 for op in self.operators.values() if op["workload"]["current"] == "overloaded")
        avg_trust = sum(op["trust_scores"]["overall"] for op in self.operators.values()) / max(1, total_ops)
        avg_level = sum(op["autonomy_level"] for op in self.operators.values()) / max(1, total_ops)
        return {"operators": total_ops, "fatigued": fatigued, "overloaded": overloaded,
                "avg_trust": round(avg_trust, 2), "avg_autonomy_level": round(avg_level, 1),
                "global_autonomy": self.global_autonomy,
                "active_delegations": len(self.delegations)}

    def _log(self, user, details):
        self.event_log.append({"user": user, "details": details,
                               "timestamp": datetime.now(timezone.utc).isoformat()})
        if len(self.event_log) > 500:
            self.event_log = self.event_log[-500:]
