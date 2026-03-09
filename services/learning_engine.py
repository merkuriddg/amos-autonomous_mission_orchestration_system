"""AMOS Learning Engine — After-Action Review & Adaptive Behavior

Implements:
  - After-Action Review (AAR) pattern extraction from mission events
  - Anomaly detection (statistical deviation from baseline behavior)
  - Engagement outcome tracking with kill/miss/abort statistics
  - Swarm behavior tuning via feedback-weighted parameter adjustment
"""

import math, random, time, uuid, statistics
from collections import deque
from datetime import datetime, timezone


# ─── Event Recorder ──────────────────────────────────────

class EventRecorder:
    """Records and indexes mission events for AAR analysis."""

    def __init__(self, max_events=5000):
        self.events = deque(maxlen=max_events)
        self.engagement_log = []
        self.contingency_log = []
        self.fault_log = []

    def record(self, event_type, data):
        """Record a timestamped event."""
        entry = {
            "id": f"EVT-{uuid.uuid4().hex[:8]}",
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
            "iso": datetime.now(timezone.utc).isoformat(),
        }
        self.events.append(entry)

        if event_type in ("ENGAGEMENT", "FIRE", "STRIKE"):
            self.engagement_log.append(entry)
        elif event_type in ("CONTINGENCY_TRIGGERED", "PLAN_EXECUTED"):
            self.contingency_log.append(entry)
        elif event_type in ("ASSET_FAULT", "COMMS_LOST", "GPS_DENIED"):
            self.fault_log.append(entry)

        return entry

    def get_events(self, event_type=None, since=None, limit=100):
        """Query events with optional type and time filters."""
        results = list(self.events)
        if event_type:
            results = [e for e in results if e["type"] == event_type]
        if since:
            results = [e for e in results if e["timestamp"] >= since]
        return results[-limit:]


# ─── Anomaly Detector ────────────────────────────────────

class AnomalyDetector:
    """Detect anomalous behavior using rolling statistical baselines."""

    def __init__(self, window_size=60):
        self.window_size = window_size
        self.baselines = {}  # metric_name → deque of values
        self.anomalies = []
        self.threshold_sigma = 2.5  # standard deviations for anomaly

    def update(self, metric_name, value):
        """Feed a new observation; returns anomaly dict if detected."""
        if metric_name not in self.baselines:
            self.baselines[metric_name] = deque(maxlen=self.window_size)

        window = self.baselines[metric_name]

        anomaly = None
        if len(window) >= 10:
            mean = statistics.mean(window)
            stdev = statistics.stdev(window) if len(window) > 1 else 0.01
            z_score = (value - mean) / max(stdev, 0.001)
            if abs(z_score) > self.threshold_sigma:
                anomaly = {
                    "id": f"ANOM-{uuid.uuid4().hex[:6]}",
                    "metric": metric_name,
                    "value": round(value, 3),
                    "mean": round(mean, 3),
                    "stdev": round(stdev, 3),
                    "z_score": round(z_score, 2),
                    "direction": "HIGH" if z_score > 0 else "LOW",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                self.anomalies.append(anomaly)
                if len(self.anomalies) > 500:
                    self.anomalies = self.anomalies[-500:]

        window.append(value)
        return anomaly

    def get_anomalies(self, limit=50):
        return self.anomalies[-limit:]


# ─── Engagement Tracker ──────────────────────────────────

class EngagementTracker:
    """Track engagement outcomes and compute effectiveness metrics."""

    def __init__(self):
        self.engagements = []
        self.stats = {
            "total": 0, "kills": 0, "misses": 0, "aborts": 0,
            "by_domain": {},
            "by_weapon_type": {},
        }

    def record_engagement(self, attacker_id, target_id, weapon_type, domain,
                          outcome, distance_m=0, time_to_engage_s=0):
        """Record a completed engagement."""
        entry = {
            "id": f"ENG-{uuid.uuid4().hex[:6]}",
            "attacker": attacker_id, "target": target_id,
            "weapon_type": weapon_type, "domain": domain,
            "outcome": outcome,  # KILL, MISS, ABORT, DAMAGE
            "distance_m": distance_m,
            "time_to_engage_s": time_to_engage_s,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.engagements.append(entry)

        self.stats["total"] += 1
        if outcome == "KILL":
            self.stats["kills"] += 1
        elif outcome == "MISS":
            self.stats["misses"] += 1
        elif outcome == "ABORT":
            self.stats["aborts"] += 1

        # Track by domain
        d = self.stats["by_domain"].setdefault(domain, {"total": 0, "kills": 0})
        d["total"] += 1
        if outcome == "KILL":
            d["kills"] += 1

        # Track by weapon
        w = self.stats["by_weapon_type"].setdefault(weapon_type, {"total": 0, "kills": 0})
        w["total"] += 1
        if outcome == "KILL":
            w["kills"] += 1

        return entry

    def get_effectiveness(self):
        """Compute hit rates and engagement metrics."""
        s = self.stats
        total = max(s["total"], 1)
        result = {
            "total_engagements": s["total"],
            "kill_rate": round(s["kills"] / total * 100, 1),
            "miss_rate": round(s["misses"] / total * 100, 1),
            "abort_rate": round(s["aborts"] / total * 100, 1),
            "domain_effectiveness": {},
            "weapon_effectiveness": {},
        }
        for domain, d in s["by_domain"].items():
            dt = max(d["total"], 1)
            result["domain_effectiveness"][domain] = {
                "total": d["total"],
                "kill_rate": round(d["kills"] / dt * 100, 1),
            }
        for wtype, w in s["by_weapon_type"].items():
            wt = max(w["total"], 1)
            result["weapon_effectiveness"][wtype] = {
                "total": w["total"],
                "kill_rate": round(w["kills"] / wt * 100, 1),
            }
        return result

    def get_recent(self, limit=20):
        return self.engagements[-limit:]


# ─── Swarm Behavior Tuner ────────────────────────────────

class SwarmTuner:
    """Adjust swarm parameters based on mission performance feedback."""

    DEFAULT_PARAMS = {
        "separation_weight": 1.0,
        "cohesion_weight": 1.0,
        "alignment_weight": 1.0,
        "threat_avoidance_weight": 1.5,
        "objective_pull_weight": 1.2,
        "max_speed_factor": 1.0,
        "comm_relay_priority": 0.8,
        "risk_tolerance": 0.5,
    }

    def __init__(self):
        self.params = dict(self.DEFAULT_PARAMS)
        self.history = []
        self.feedback_scores = []

    def get_params(self):
        return dict(self.params)

    def apply_feedback(self, metric_name, score, weight=1.0):
        """Adjust parameters based on a performance score (0-1)."""
        self.feedback_scores.append({
            "metric": metric_name, "score": score,
            "weight": weight, "timestamp": time.time(),
        })

        delta = (score - 0.5) * 0.1 * weight  # small adjustments

        # Map feedback metrics to parameter adjustments
        adjustments = {
            "collision_avoidance": {"separation_weight": delta},
            "formation_quality": {"cohesion_weight": delta, "alignment_weight": delta * 0.5},
            "threat_response_time": {"threat_avoidance_weight": -delta},  # faster = reduce avoidance
            "objective_completion": {"objective_pull_weight": delta},
            "comm_reliability": {"comm_relay_priority": delta},
            "casualty_rate": {"risk_tolerance": -delta, "threat_avoidance_weight": delta},
        }

        if metric_name in adjustments:
            for param, adj in adjustments[metric_name].items():
                old = self.params[param]
                self.params[param] = max(0.1, min(3.0, old + adj))

        self.history.append({
            "metric": metric_name, "score": score,
            "params_after": dict(self.params),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def reset_to_defaults(self):
        self.params = dict(self.DEFAULT_PARAMS)


# ─── AAR Pattern Extractor ───────────────────────────────

def extract_aar_patterns(events, engagements, anomalies):
    """Generate an After-Action Review summary with patterns and lessons."""
    patterns = []

    # Engagement patterns
    if engagements:
        outcomes = [e["outcome"] for e in engagements]
        kill_count = outcomes.count("KILL")
        miss_count = outcomes.count("MISS")
        abort_count = outcomes.count("ABORT")
        total = len(outcomes)

        if miss_count > kill_count:
            patterns.append({
                "category": "ENGAGEMENT",
                "pattern": "HIGH_MISS_RATE",
                "description": f"Miss rate ({miss_count}/{total}) exceeds kill rate — review targeting parameters",
                "severity": "WARNING",
            })
        if abort_count > total * 0.3:
            patterns.append({
                "category": "ENGAGEMENT",
                "pattern": "EXCESSIVE_ABORTS",
                "description": f"Abort rate ({abort_count}/{total}) above 30% — review engagement criteria",
                "severity": "WARNING",
            })

    # Anomaly clusters
    if anomalies:
        metric_counts = {}
        for a in anomalies:
            metric_counts[a["metric"]] = metric_counts.get(a["metric"], 0) + 1
        for metric, count in metric_counts.items():
            if count >= 3:
                patterns.append({
                    "category": "ANOMALY",
                    "pattern": "RECURRING_ANOMALY",
                    "description": f"Metric '{metric}' anomalous {count} times — investigate root cause",
                    "severity": "CAUTION",
                })

    # Event frequency patterns
    event_types = [e["type"] for e in events]
    fault_count = sum(1 for t in event_types if "FAULT" in t)
    if fault_count >= 5:
        patterns.append({
            "category": "RELIABILITY",
            "pattern": "FREQUENT_FAULTS",
            "description": f"{fault_count} fault events recorded — reliability concern",
            "severity": "WARNING",
        })

    return {
        "total_events_analyzed": len(events),
        "total_engagements": len(engagements),
        "total_anomalies": len(anomalies),
        "patterns": patterns,
        "generated": datetime.now(timezone.utc).isoformat(),
    }


# ─── Learning Engine (Main Class) ────────────────────────

class LearningEngine:
    """Unified learning and adaptation system for AMOS."""

    def __init__(self):
        self.recorder = EventRecorder()
        self.anomaly_detector = AnomalyDetector()
        self.engagement_tracker = EngagementTracker()
        self.swarm_tuner = SwarmTuner()
        self.tick_count = 0

    def tick(self, assets, threats, dt=1.0):
        """Process one learning cycle."""
        self.tick_count += 1
        anomalies_this_tick = []

        # Monitor fleet-level metrics for anomaly detection
        if assets:
            batts = [a.get("health", {}).get("battery_pct", 100) for a in assets.values()]
            avg_batt = sum(batts) / len(batts)
            a = self.anomaly_detector.update("avg_battery_pct", avg_batt)
            if a:
                anomalies_this_tick.append(a)

            active_count = sum(1 for a in assets.values() if a.get("status") != "FAULT")
            a2 = self.anomaly_detector.update("active_asset_count", active_count)
            if a2:
                anomalies_this_tick.append(a2)

        if threats:
            threat_count = sum(1 for t in threats.values() if not t.get("neutralized"))
            a3 = self.anomaly_detector.update("active_threat_count", threat_count)
            if a3:
                anomalies_this_tick.append(a3)

        # Periodically update swarm tuner based on engagement stats
        if self.tick_count % 100 == 0:
            eff = self.engagement_tracker.get_effectiveness()
            if eff["total_engagements"] > 0:
                self.swarm_tuner.apply_feedback("casualty_rate",
                    1.0 - eff.get("abort_rate", 0) / 100)

        return anomalies_this_tick

    # ── API getters ──

    def record_event(self, event_type, data):
        return self.recorder.record(event_type, data)

    def record_engagement(self, **kwargs):
        return self.engagement_tracker.record_engagement(**kwargs)

    def get_events(self, **kwargs):
        return self.recorder.get_events(**kwargs)

    def get_anomalies(self, limit=50):
        return self.anomaly_detector.get_anomalies(limit)

    def get_engagement_stats(self):
        return self.engagement_tracker.get_effectiveness()

    def get_recent_engagements(self, limit=20):
        return self.engagement_tracker.get_recent(limit)

    def get_swarm_params(self):
        return self.swarm_tuner.get_params()

    def tune_swarm(self, metric_name, score, weight=1.0):
        self.swarm_tuner.apply_feedback(metric_name, score, weight)
        return self.swarm_tuner.get_params()

    def generate_aar(self):
        return extract_aar_patterns(
            list(self.recorder.events),
            self.engagement_tracker.engagements,
            self.anomaly_detector.anomalies,
        )
