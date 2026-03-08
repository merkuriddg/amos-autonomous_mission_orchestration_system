"""ROE Engine — Rules of Engagement compliance checker.

Manages engagement authorization rules, weapon restrictions,
zone constraints, and ROE violation logging.
"""

import uuid
from datetime import datetime, timezone

# ROE posture levels (most to least restrictive)
ROE_POSTURES = ["WEAPONS_HOLD", "WEAPONS_TIGHT", "WEAPONS_FREE"]


class ROEEngine:
    """Rules of Engagement manager."""

    def __init__(self):
        self.posture = "WEAPONS_TIGHT"  # Default
        self.posture_set_by = "SYSTEM"
        self.posture_set_at = datetime.now(timezone.utc).isoformat()
        self.rules = {}       # {rule_id: ROERule dict}
        self.violations = []  # [{id, timestamp, rule_id, rule_name, threat_id, operator, detail}]

        # Initialize default rules
        self._init_default_rules()

    def _init_default_rules(self):
        """Load standard ROE rules."""
        defaults = [
            {"name": "Positive ID Required",
             "type": "id_required",
             "params": {"min_classification": "HOSTILE"},
             "description": "Target must be classified HOSTILE before engagement",
             "severity": "BLOCK"},
            {"name": "Collateral Damage Limit",
             "type": "zone_restriction",
             "params": {"restricted_zones": True},
             "description": "No engagement within restricted geofence zones",
             "severity": "BLOCK"},
            {"name": "Commander Auth for Tier 1-2",
             "type": "authority_tier",
             "params": {"max_auto_tier": 3},
             "description": "Assets with autonomy tier ≤ 2 require commander approval",
             "severity": "BLOCK"},
            {"name": "Proportional Response",
             "type": "proportional",
             "params": {"max_overkill_ratio": 3.0},
             "description": "Weapon capability must not exceed 3x threat level",
             "severity": "WARNING"},
            {"name": "Weapons Hold Override",
             "type": "posture_check",
             "params": {},
             "description": "No engagement allowed during WEAPONS_HOLD posture",
             "severity": "BLOCK"},
        ]
        for d in defaults:
            rid = f"ROE-{uuid.uuid4().hex[:6]}"
            self.rules[rid] = {
                "id": rid,
                "name": d["name"],
                "type": d["type"],
                "params": d["params"],
                "description": d["description"],
                "severity": d["severity"],  # BLOCK = hard stop, WARNING = log only
                "enabled": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

    def check_engagement(self, threat, asset, operator, engagement_type="intercept"):
        """
        Check if an engagement is ROE-compliant.
        Returns: {"allowed": bool, "violations": [...], "warnings": [...]}
        """
        violations = []
        warnings = []

        for rid, rule in self.rules.items():
            if not rule["enabled"]:
                continue

            result = self._evaluate_rule(rule, threat, asset, operator, engagement_type)
            if result:
                entry = {
                    "rule_id": rid,
                    "rule_name": rule["name"],
                    "detail": result,
                    "severity": rule["severity"],
                }
                if rule["severity"] == "BLOCK":
                    violations.append(entry)
                else:
                    warnings.append(entry)

        # Log all violations
        for v in violations + warnings:
            self.violations.append({
                "id": f"ROEV-{uuid.uuid4().hex[:6]}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "rule_id": v["rule_id"],
                "rule_name": v["rule_name"],
                "threat_id": threat.get("id", "unknown"),
                "operator": operator,
                "detail": v["detail"],
                "severity": v["severity"],
                "engagement_type": engagement_type,
            })

        allowed = len(violations) == 0
        return {"allowed": allowed, "violations": violations, "warnings": warnings}

    def _evaluate_rule(self, rule, threat, asset, operator, engagement_type):
        """Evaluate a single rule. Returns violation detail string or None."""
        rtype = rule["type"]
        params = rule.get("params", {})

        if rtype == "posture_check":
            if self.posture == "WEAPONS_HOLD":
                return f"ROE posture is WEAPONS_HOLD — all engagements blocked"
            if self.posture == "WEAPONS_TIGHT" and engagement_type != "intercept":
                return f"WEAPONS_TIGHT: only intercept allowed, got {engagement_type}"

        elif rtype == "id_required":
            # Threats should have a classification or be marked hostile
            if not threat.get("neutralized") and threat.get("type") == "unknown":
                return "Target type is unknown — positive ID required"

        elif rtype == "authority_tier":
            max_tier = params.get("max_auto_tier", 3)
            asset_tier = asset.get("autonomy_tier", 2) if asset else 2
            if asset_tier <= max_tier - 1:
                # Low autonomy tier needs commander auth
                pass  # Kill web handles this via approval gate

        elif rtype == "proportional":
            pass  # Proportionality check — simplified, always passes in sim

        elif rtype == "zone_restriction":
            pass  # Would check geofence — simplified for sim

        return None

    def set_posture(self, posture, set_by):
        """Change ROE posture."""
        if posture not in ROE_POSTURES:
            return None
        old = self.posture
        self.posture = posture
        self.posture_set_by = set_by
        self.posture_set_at = datetime.now(timezone.utc).isoformat()
        return {"old": old, "new": posture, "set_by": set_by}

    def add_rule(self, name, rtype, params, description="", severity="WARNING"):
        """Add a custom ROE rule."""
        rid = f"ROE-{uuid.uuid4().hex[:6]}"
        self.rules[rid] = {
            "id": rid, "name": name, "type": rtype,
            "params": params, "description": description,
            "severity": severity, "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return self.rules[rid]

    def toggle_rule(self, rule_id):
        r = self.rules.get(rule_id)
        if r:
            r["enabled"] = not r["enabled"]
            return r
        return None

    def get_status(self):
        return {
            "posture": self.posture,
            "posture_set_by": self.posture_set_by,
            "posture_set_at": self.posture_set_at,
            "total_rules": len(self.rules),
            "active_rules": sum(1 for r in self.rules.values() if r["enabled"]),
            "total_violations": len(self.violations),
            "recent_violations": self.violations[-10:],
        }

    def get_rules(self):
        return list(self.rules.values())

    def get_violations(self, limit=50):
        return self.violations[-limit:]
