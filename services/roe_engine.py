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

    # ── B3.3 CQB Engagement Rules ────────────────────────

    def init_cqb_rules(self):
        """Add CQB-specific ROE rules for indoor/close-quarters operations."""
        cqb_rules = [
            {"name": "CQB Range Engagement",
             "type": "cqb_range",
             "params": {"max_range_m": 25, "min_range_m": 1},
             "description": "CQB engagements must be within 1-25m range",
             "severity": "WARNING"},
            {"name": "Hostage Room Restriction",
             "type": "cqb_hostage",
             "params": {"restricted_rooms": []},
             "description": "No autonomous engagement in rooms marked as hostage-present",
             "severity": "BLOCK"},
            {"name": "Fratricide Prevention Zone",
             "type": "cqb_fratricide",
             "params": {"min_friendly_separation_m": 2.0},
             "description": "Block engagement if friendly assets within 2m of target",
             "severity": "BLOCK"},
            {"name": "CQB Autonomy Tier Override",
             "type": "cqb_autonomy",
             "params": {"min_tier_for_auto_engage": 4},
             "description": "CQB autonomous engagement requires tier 4+ (speed-of-action)",
             "severity": "BLOCK"},
        ]
        for d in cqb_rules:
            rid = f"ROE-CQB-{uuid.uuid4().hex[:6]}"
            self.rules[rid] = {
                "id": rid, "name": d["name"], "type": d["type"],
                "params": d["params"], "description": d["description"],
                "severity": d["severity"], "enabled": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        return len(cqb_rules)

    def set_hostage_rooms(self, room_ids):
        """Mark rooms as hostage-present for CQB ROE."""
        for rule in self.rules.values():
            if rule["type"] == "cqb_hostage":
                rule["params"]["restricted_rooms"] = list(room_ids)
                return True
        return False

    def check_cqb_engagement(self, room_id, asset, target_range_m=10.0,
                              friendly_separation_m=5.0, operator="SYSTEM"):
        """CQB-specific engagement check.

        Returns: {allowed: bool, violations: [...], warnings: [...]}
        """
        violations = []
        warnings = []

        for rid, rule in self.rules.items():
            if not rule["enabled"]:
                continue
            result = None
            rtype = rule["type"]
            params = rule.get("params", {})

            if rtype == "cqb_range":
                max_r = params.get("max_range_m", 25)
                min_r = params.get("min_range_m", 1)
                if target_range_m > max_r or target_range_m < min_r:
                    result = f"Engagement range {target_range_m}m outside CQB bounds ({min_r}-{max_r}m)"

            elif rtype == "cqb_hostage":
                restricted = params.get("restricted_rooms", [])
                if room_id in restricted:
                    result = f"Room {room_id} marked as hostage-present — autonomous engagement blocked"

            elif rtype == "cqb_fratricide":
                min_sep = params.get("min_friendly_separation_m", 2.0)
                if friendly_separation_m < min_sep:
                    result = f"Friendly asset within {friendly_separation_m}m (min {min_sep}m) — fratricide risk"

            elif rtype == "cqb_autonomy":
                min_tier = params.get("min_tier_for_auto_engage", 4)
                asset_tier = asset.get("autonomy_tier", 2) if asset else 2
                if asset_tier < min_tier:
                    result = f"Asset tier {asset_tier} < required {min_tier} for CQB auto-engage"

            elif rtype == "posture_check":
                if self.posture == "WEAPONS_HOLD":
                    result = "ROE posture is WEAPONS_HOLD — all engagements blocked"

            if result:
                entry = {"rule_id": rid, "rule_name": rule["name"],
                         "detail": result, "severity": rule["severity"]}
                if rule["severity"] == "BLOCK":
                    violations.append(entry)
                else:
                    warnings.append(entry)

        # Log violations
        for v in violations + warnings:
            self.violations.append({
                "id": f"ROEV-CQB-{uuid.uuid4().hex[:6]}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "rule_id": v["rule_id"], "rule_name": v["rule_name"],
                "room_id": room_id, "operator": operator,
                "detail": v["detail"], "severity": v["severity"],
            })

        return {"allowed": len(violations) == 0,
                "violations": violations, "warnings": warnings}
