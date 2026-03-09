#!/usr/bin/env python3
"""
MOS Phase 2 — 5-Tier Autonomy Manager
Controls autonomy levels for each asset:
  T1: Manual (human stick control)
  T2: Assisted (human decides, system executes)
  T3: Supervised (system recommends, human approves)
  T4: Autonomous (system acts, human can override)
  T5: Cognitive (full AI independence)
"""

import threading
from datetime import datetime, timezone


TIER_DESCRIPTIONS = {
    1: {"name": "MANUAL", "desc": "Human stick control", "human_role": "full_control"},
    2: {"name": "ASSISTED", "desc": "Human decides, system executes", "human_role": "decision_maker"},
    3: {"name": "SUPERVISED", "desc": "System recommends, human approves", "human_role": "approver"},
    4: {"name": "AUTONOMOUS", "desc": "System acts, human can override", "human_role": "monitor"},
    5: {"name": "COGNITIVE", "desc": "Full AI independence", "human_role": "observer"},
}


class AutonomyManager:
    """Manages autonomy tiers for all assets with safety constraints."""

    def __init__(self):
        self.asset_tiers = {}
        self.global_ceiling = 4  # Max tier allowed platoon-wide
        self.tier_locks = {}     # Assets locked at a specific tier
        self.escalation_log = []
        self._lock = threading.Lock()
        self.rules = [
            {"condition": "weapons_release", "max_tier": 2, "reason": "Lethal action requires T2 or below"},
            {"condition": "near_civilians", "max_tier": 3, "reason": "Civilian proximity caps at T3"},
            {"condition": "comms_degraded", "max_tier": 4, "reason": "DDIL allows up to T4 for survivability"},
            {"condition": "rtb", "max_tier": 4, "reason": "RTB can be autonomous"},
        ]

    def set_tier(self, asset_id: str, tier: int, reason: str = "") -> dict:
        if tier < 1 or tier > 5:
            return {"success": False, "error": "Tier must be 1-5"}
        if tier > self.global_ceiling:
            return {"success": False, "error": f"Global ceiling is T{self.global_ceiling}"}
        if asset_id in self.tier_locks:
            locked = self.tier_locks[asset_id]
            return {"success": False, "error": f"{asset_id} locked at T{locked}"}

        with self._lock:
            old_tier = self.asset_tiers.get(asset_id, 1)
            self.asset_tiers[asset_id] = tier
            entry = {
                "asset_id": asset_id,
                "old_tier": old_tier,
                "new_tier": tier,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.escalation_log.append(entry)
            if len(self.escalation_log) > 5000:
                self.escalation_log = self.escalation_log[-5000:]

        return {"success": True, "asset_id": asset_id, "tier": tier,
                "tier_info": TIER_DESCRIPTIONS[tier]}

    def get_tier(self, asset_id: str) -> dict:
        tier = self.asset_tiers.get(asset_id, 1)
        return {"asset_id": asset_id, "tier": tier, "info": TIER_DESCRIPTIONS[tier]}

    def set_global_ceiling(self, ceiling: int, reason: str = "") -> dict:
        if ceiling < 1 or ceiling > 5:
            return {"success": False, "error": "Ceiling must be 1-5"}
        self.global_ceiling = ceiling
        # Downgrade any assets above new ceiling
        downgraded = []
        for asset_id, tier in self.asset_tiers.items():
            if tier > ceiling:
                self.asset_tiers[asset_id] = ceiling
                downgraded.append(asset_id)
        return {"success": True, "ceiling": ceiling, "downgraded": downgraded}

    def lock_tier(self, asset_id: str, tier: int) -> dict:
        self.tier_locks[asset_id] = tier
        self.asset_tiers[asset_id] = tier
        return {"success": True, "asset_id": asset_id, "locked_tier": tier}

    def unlock_tier(self, asset_id: str) -> dict:
        if asset_id in self.tier_locks:
            del self.tier_locks[asset_id]
            return {"success": True, "asset_id": asset_id}
        return {"success": False, "error": "Not locked"}

    def evaluate_constraints(self, asset_id: str, conditions: list) -> dict:
        """Apply safety rules based on current conditions."""
        current_tier = self.asset_tiers.get(asset_id, 1)
        effective_max = self.global_ceiling
        applied_rules = []
        for rule in self.rules:
            if rule["condition"] in conditions:
                effective_max = min(effective_max, rule["max_tier"])
                applied_rules.append(rule)
        if current_tier > effective_max:
            self.set_tier(asset_id, effective_max, f"Auto-downgrade: {', '.join(conditions)}")
        return {
            "asset_id": asset_id,
            "current_tier": min(current_tier, effective_max),
            "effective_max": effective_max,
            "applied_rules": applied_rules,
        }

    def get_all_tiers(self) -> dict:
        return {aid: {"tier": t, "info": TIER_DESCRIPTIONS[t]}
                for aid, t in self.asset_tiers.items()}

    def summary(self) -> dict:
        tier_counts = {}
        for t in self.asset_tiers.values():
            tier_counts[t] = tier_counts.get(t, 0) + 1
        return {
            "global_ceiling": self.global_ceiling,
            "total_managed": len(self.asset_tiers),
            "by_tier": tier_counts,
            "locked_assets": list(self.tier_locks.keys()),
        }


if __name__ == "__main__":
    import json
    am = AutonomyManager()
    am.set_tier("GHOST-01", 4, "Recon patrol")
    am.set_tier("TALON-01", 2, "Armed UGV")
    am.set_tier("REAPER-01", 3, "ISR orbit")
    print(json.dumps(am.summary(), indent=2))
    result = am.evaluate_constraints("GHOST-01", ["near_civilians"])
    print(json.dumps(result, indent=2))
