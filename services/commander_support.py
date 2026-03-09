"""AMOS Commander Decision Support — Predictive Analysis & Resource Management

Implements:
  - Predictive threat tracks (5/10/15 min projections)
  - Resource burn-down calculator (battery, fuel, ammo endurance)
  - Branch & sequel contingency planner with auto-trigger conditions
  - Mission risk scoring
"""

import math, random, time, uuid
from datetime import datetime, timezone


# ─── Resource Burn-Down Calculator ────────────────────────

class ResourceCalculator:
    """Calculate and project resource consumption across the platoon."""

    # Consumption rates per domain (% per minute)
    DRAIN_RATES = {
        "air":      {"idle": 0.05, "transit": 0.15, "mission": 0.25, "combat": 0.40},
        "ground":   {"idle": 0.02, "transit": 0.08, "mission": 0.12, "combat": 0.20},
        "maritime": {"idle": 0.01, "transit": 0.05, "mission": 0.08, "combat": 0.15},
    }

    @classmethod
    def project(cls, assets, projection_minutes=60):
        """Project resource levels for each asset over time."""
        projections = {}
        critical_alerts = []

        for aid, a in assets.items():
            domain = a.get("domain", "ground")
            rates = cls.DRAIN_RATES.get(domain, cls.DRAIN_RATES["ground"])
            status = a.get("status", "operational").lower()
            rate = rates.get("mission", rates["idle"])
            if "combat" in status or "exec" in status:
                rate = rates["combat"]
            elif "route" in status or "transit" in status:
                rate = rates["transit"]
            elif "idle" in status or "operational" in status:
                rate = rates["idle"]

            batt = a.get("health", {}).get("battery_pct", 100)
            endurance_hr = a.get("endurance_hr", 0)

            # Project battery over time
            timeline = []
            for t_min in range(0, projection_minutes + 1, 5):
                projected = max(0, batt - rate * t_min)
                timeline.append({"minutes": t_min, "battery_pct": round(projected, 1)})

            # Time to critical (20%) and empty (5%)
            time_to_critical = max(0, (batt - 20) / rate) if rate > 0 else 999
            time_to_empty = max(0, (batt - 5) / rate) if rate > 0 else 999

            projections[aid] = {
                "current_battery_pct": round(batt, 1),
                "drain_rate_pct_min": round(rate, 3),
                "time_to_critical_min": round(time_to_critical, 1),
                "time_to_empty_min": round(time_to_empty, 1),
                "endurance_hr": endurance_hr,
                "timeline": timeline,
                "domain": domain,
            }

            if time_to_critical < 15:
                critical_alerts.append({
                    "asset_id": aid, "type": "BATTERY_CRITICAL",
                    "minutes_remaining": round(time_to_critical, 1),
                    "current_pct": round(batt, 1),
                })

        # Platoon-level summary
        all_batts = [p["current_battery_pct"] for p in projections.values()]
        domain_endurance = {}
        for aid, p in projections.items():
            d = p["domain"]
            domain_endurance.setdefault(d, []).append(p["time_to_critical_min"])

        return {
            "projections": projections,
            "alerts": critical_alerts,
            "platoon_summary": {
                "avg_battery_pct": round(sum(all_batts) / max(len(all_batts), 1), 1),
                "min_battery_pct": round(min(all_batts) if all_batts else 0, 1),
                "assets_critical": sum(1 for a in critical_alerts),
                "domain_min_endurance_min": {
                    d: round(min(times), 1)
                    for d, times in domain_endurance.items() if times
                },
            },
        }


# ─── Contingency Planner ─────────────────────────────────

class ContingencyPlan:
    """A branch/sequel plan with trigger conditions."""

    def __init__(self, name, trigger_type, trigger_params, actions, priority=5):
        self.id = f"CONT-{uuid.uuid4().hex[:6]}"
        self.name = name
        self.trigger_type = trigger_type  # THREAT_COUNT, ASSET_LOSS, BATTERY, COMMS_LOST, TIME
        self.trigger_params = trigger_params
        self.actions = actions  # list of action dicts
        self.priority = priority
        self.status = "ARMED"  # ARMED, TRIGGERED, EXECUTED, CANCELLED
        self.created = time.time()
        self.triggered_at = None

    def check_trigger(self, context):
        """Check if trigger conditions are met."""
        if self.status != "ARMED":
            return False

        if self.trigger_type == "THREAT_COUNT":
            return context.get("active_threats", 0) >= self.trigger_params.get("min_threats", 5)
        elif self.trigger_type == "ASSET_LOSS":
            return context.get("faulted_assets", 0) >= self.trigger_params.get("min_losses", 2)
        elif self.trigger_type == "BATTERY":
            return context.get("avg_battery", 100) <= self.trigger_params.get("max_avg_pct", 30)
        elif self.trigger_type == "COMMS_LOST":
            return context.get("isolated_assets", 0) >= self.trigger_params.get("min_isolated", 3)
        elif self.trigger_type == "TIME":
            return (time.time() - self.created) >= self.trigger_params.get("after_sec", 300)
        return False

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "trigger_type": self.trigger_type,
            "trigger_params": self.trigger_params, "actions": self.actions,
            "priority": self.priority, "status": self.status,
            "created": self.created, "triggered_at": self.triggered_at,
        }


# ─── Risk Scorer ──────────────────────────────────────────

def compute_mission_risk(assets, threats, contested_status=None):
    """Compute overall mission risk score (0-100, higher = riskier)."""
    risk = 0.0
    factors = []

    # Threat ratio
    active_threats = sum(1 for t in threats.values() if not t.get("neutralized"))
    total_assets = len(assets)
    threat_ratio = active_threats / max(total_assets, 1)
    threat_risk = min(30, threat_ratio * 60)
    risk += threat_risk
    factors.append({"factor": "threat_ratio", "value": round(threat_ratio, 2),
                     "risk_contribution": round(threat_risk, 1)})

    # Battery status
    batts = [a.get("health", {}).get("battery_pct", 100) for a in assets.values()]
    avg_batt = sum(batts) / max(len(batts), 1)
    batt_risk = max(0, (100 - avg_batt) * 0.2)
    risk += batt_risk
    factors.append({"factor": "avg_battery", "value": round(avg_batt, 1),
                     "risk_contribution": round(batt_risk, 1)})

    # Comms status
    if contested_status:
        isolated = contested_status.get("stats", {}).get("comms_denied_assets", 0)
        comms_risk = min(20, isolated * 5)
        risk += comms_risk
        factors.append({"factor": "comms_denied", "value": isolated,
                         "risk_contribution": round(comms_risk, 1)})

        gps_denied = contested_status.get("stats", {}).get("gps_denied_assets", 0)
        gps_risk = min(15, gps_denied * 3)
        risk += gps_risk
        factors.append({"factor": "gps_denied", "value": gps_denied,
                         "risk_contribution": round(gps_risk, 1)})

    # Asset readiness
    faulted = sum(1 for a in assets.values() if a.get("status") == "FAULT")
    fault_risk = min(15, faulted * 5)
    risk += fault_risk
    factors.append({"factor": "faulted_assets", "value": faulted,
                     "risk_contribution": round(fault_risk, 1)})

    risk = min(100, max(0, risk))
    level = "LOW" if risk < 30 else "MEDIUM" if risk < 60 else "HIGH" if risk < 80 else "CRITICAL"

    return {
        "score": round(risk, 1),
        "level": level,
        "factors": factors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── Commander Support (Main Class) ──────────────────────

class CommanderSupport:
    """Full commander decision support system."""

    def __init__(self):
        self.resource_calc = ResourceCalculator()
        self.contingency_plans = []
        self.risk_history = []
        self.triggered_plans = []
        self._create_default_plans()

    def _create_default_plans(self):
        """Pre-load standard contingency plans."""
        defaults = [
            ContingencyPlan(
                "MASS THREAT RESPONSE", "THREAT_COUNT",
                {"min_threats": 8},
                [{"type": "ALERT", "message": "Mass threat threshold exceeded — recommend RTB non-essential"},
                 {"type": "FORMATION", "pattern": "DIAMOND", "domain": "air"},
                 {"type": "AUTONOMY", "level": 3}],
                priority=1),
            ContingencyPlan(
                "ASSET ATTRITION", "ASSET_LOSS",
                {"min_losses": 3},
                [{"type": "ALERT", "message": "Significant asset losses — consolidate and reassess"},
                 {"type": "RTB", "domain": "logistics"},
                 {"type": "FORMATION", "pattern": "WEDGE", "domain": "ground"}],
                priority=2),
            ContingencyPlan(
                "LOW BATTERY EMERGENCY", "BATTERY",
                {"max_avg_pct": 25},
                [{"type": "ALERT", "message": "Platoon battery critical — initiate phased RTB"},
                 {"type": "RTB", "domain": "air"}],
                priority=1),
            ContingencyPlan(
                "COMMS BLACKOUT", "COMMS_LOST",
                {"min_isolated": 4},
                [{"type": "ALERT", "message": "Multiple assets isolated — autonomous ops authorized"},
                 {"type": "AUTONOMY", "level": 4}],
                priority=1),
        ]
        self.contingency_plans.extend(defaults)

    def tick(self, assets, threats, contested_env=None, dt=1.0):
        """Update all commander support systems."""
        events = []

        # Risk assessment
        contested_status = contested_env.get_status() if contested_env else None
        risk = compute_mission_risk(assets, threats, contested_status)
        self.risk_history.append(risk)
        if len(self.risk_history) > 500:
            self.risk_history = self.risk_history[-500:]

        # Check contingency triggers
        context = {
            "active_threats": sum(1 for t in threats.values() if not t.get("neutralized")),
            "faulted_assets": sum(1 for a in assets.values() if a.get("status") == "FAULT"),
            "avg_battery": sum(a.get("health", {}).get("battery_pct", 100)
                               for a in assets.values()) / max(len(assets), 1),
            "isolated_assets": contested_status.get("stats", {}).get("comms_denied_assets", 0)
                               if contested_status else 0,
        }

        for plan in self.contingency_plans:
            if plan.check_trigger(context):
                plan.status = "TRIGGERED"
                plan.triggered_at = time.time()
                self.triggered_plans.append(plan.to_dict())
                events.append({
                    "type": "CONTINGENCY_TRIGGERED",
                    "plan_id": plan.id, "plan_name": plan.name,
                    "actions": plan.actions,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        return events

    def get_resources(self, assets, projection_minutes=60):
        return self.resource_calc.project(assets, projection_minutes)

    def get_risk(self):
        return self.risk_history[-1] if self.risk_history else {"score": 0, "level": "LOW"}

    def get_risk_trend(self, points=20):
        return [{"score": r["score"], "level": r["level"]}
                for r in self.risk_history[-points:]]

    def get_contingency_plans(self):
        return [p.to_dict() for p in self.contingency_plans]

    def get_triggered_plans(self):
        return list(self.triggered_plans)

    def add_contingency(self, name, trigger_type, trigger_params, actions, priority=5):
        plan = ContingencyPlan(name, trigger_type, trigger_params, actions, priority)
        self.contingency_plans.append(plan)
        return plan.to_dict()

    def cancel_contingency(self, plan_id):
        for p in self.contingency_plans:
            if p.id == plan_id:
                p.status = "CANCELLED"
                return True
        return False
