#!/usr/bin/env python3
"""AMOS Mission Pipeline — Sensor→Decide→Act→Assess Closed Loop

Connects sensor fusion outputs to autonomous mission execution via behavior trees.

Components:
  TriggerRule   — "if fused track confidence > 0.7 AND hostile → spawn ISR task"
  MissionPipeline — evaluates rules against fused tracks, spawns/manages BTs
  Template BTs  — pre-built behavior trees for common mission patterns

Template BTs:
  RECON_TO_STRIKE    — detect → classify → track → decide → engage → assess
  CQB_ASSAULT        — approach → breach → clear → secure → extract
  BORDER_INTERDICTION — detect → investigate → track → intercept → report
  SENSOR_SWEEP       — deploy → scan → correlate → report
  RELAY_SUPPORT      — detect_gap → assign_relay → verify_connectivity
"""

import time
import uuid
import threading
from datetime import datetime, timezone
from services.behavior_tree import (
    BehaviorTree, BTRegistry, Status,
    Sequence, Selector, Parallel,
    Condition, Action, Guard, Inverter, RetryUntilSuccess,
)


# ─── Trigger Rules ────────────────────────────────────────

class TriggerRule:
    """A rule that fires when conditions on fused tracks / blackboard are met.

    condition_fn: callable(track_dict, blackboard) -> bool
    action_fn:    callable(track_dict, blackboard) -> dict (event description)
    """

    def __init__(self, name: str, condition_fn, action_fn,
                 cooldown_sec: float = 30, priority: int = 5, enabled: bool = True):
        self.id = f"RULE-{uuid.uuid4().hex[:6]}"
        self.name = name
        self.condition_fn = condition_fn
        self.action_fn = action_fn
        self.cooldown_sec = cooldown_sec
        self.priority = priority
        self.enabled = enabled
        self.fire_count = 0
        self.last_fired = 0

    def evaluate(self, track: dict, bb: dict) -> dict:
        """Check if rule should fire for this track. Returns event dict or None."""
        if not self.enabled:
            return None
        if time.time() - self.last_fired < self.cooldown_sec:
            return None
        try:
            if self.condition_fn(track, bb):
                self.fire_count += 1
                self.last_fired = time.time()
                return self.action_fn(track, bb)
        except Exception:
            pass
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "priority": self.priority,
            "enabled": self.enabled, "fire_count": self.fire_count,
            "cooldown_sec": self.cooldown_sec,
            "last_fired": self.last_fired,
        }


# ─── Default Trigger Rules ────────────────────────────────

def _default_rules():
    """Built-in trigger rules for common mission patterns."""
    rules = []

    # Rule 1: New hostile detected → spawn ISR task
    rules.append(TriggerRule(
        "hostile_detected_isr",
        condition_fn=lambda t, bb: (
            t.get("classification") in ("HOSTILE", "SUSPECTED_HOSTILE") and
            t.get("confidence", 0) >= 0.4 and
            t.get("kill_chain", {}).get("phase") == "DETECT"
        ),
        action_fn=lambda t, bb: {
            "action": "SPAWN_TASK", "task_type": "ISR",
            "description": f"ISR on track {t.get('id', '?')} — {t.get('classification')}",
            "location": {"lat": t.get("lat", 0), "lng": t.get("lng", 0)},
            "priority": 3, "required_sensors": ["EO/IR", "SAR"],
            "track_id": t.get("id"),
        },
        cooldown_sec=20, priority=3,
    ))

    # Rule 2: High-confidence hostile → spawn TRACK mission
    rules.append(TriggerRule(
        "high_confidence_track",
        condition_fn=lambda t, bb: (
            t.get("classification") in ("HOSTILE", "SUSPECTED_HOSTILE") and
            t.get("confidence", 0) >= 0.7 and
            t.get("kill_chain", {}).get("phase") in ("IDENTIFY", "DECIDE")
        ),
        action_fn=lambda t, bb: {
            "action": "SPAWN_TASK", "task_type": "TRACK",
            "description": f"Persistent track on {t.get('id', '?')} (conf {t.get('confidence', 0):.0%})",
            "location": {"lat": t.get("lat", 0), "lng": t.get("lng", 0)},
            "priority": 2, "min_assets": 2,
            "track_id": t.get("id"),
        },
        cooldown_sec=30, priority=2,
    ))

    # Rule 3: Confirmed target + weapons_free → spawn STRIKE request
    rules.append(TriggerRule(
        "confirmed_strike_request",
        condition_fn=lambda t, bb: (
            t.get("classification") == "HOSTILE" and
            t.get("confidence", 0) >= 0.85 and
            bb.get("roe_posture") in ("weapons_free", "weapons_tight") and
            t.get("kill_chain", {}).get("phase") == "DECIDE"
        ),
        action_fn=lambda t, bb: {
            "action": "SPAWN_TASK", "task_type": "STRIKE",
            "description": f"Strike request: {t.get('id', '?')} CONFIRMED HOSTILE",
            "location": {"lat": t.get("lat", 0), "lng": t.get("lng", 0)},
            "priority": 1, "required_weapons": True,
            "requires_human_approval": True,
            "track_id": t.get("id"),
        },
        cooldown_sec=60, priority=1,
    ))

    # Rule 4: Comms degraded → spawn relay task
    rules.append(TriggerRule(
        "comms_degraded_relay",
        condition_fn=lambda t, bb: (
            bb.get("comms_health", 1.0) < 0.5 and
            not bb.get("relay_assigned")
        ),
        action_fn=lambda t, bb: {
            "action": "SPAWN_TASK", "task_type": "RELAY",
            "description": "Mesh connectivity degraded — assign relay drone",
            "priority": 2,
        },
        cooldown_sec=120, priority=2,
    ))

    # Rule 5: Track lost → spawn search spiral
    rules.append(TriggerRule(
        "track_lost_search",
        condition_fn=lambda t, bb: (
            t.get("age_sec", 0) > 120 and
            t.get("confidence", 0) < 0.3 and
            t.get("classification") not in (None, "UNKNOWN", "FRIENDLY")
        ),
        action_fn=lambda t, bb: {
            "action": "SPAWN_TASK", "task_type": "SEARCH",
            "description": f"Lost track {t.get('id', '?')} — search spiral at last known",
            "location": {"lat": t.get("lat", 0), "lng": t.get("lng", 0)},
            "priority": 4,
            "track_id": t.get("id"),
        },
        cooldown_sec=60, priority=4,
    ))

    return rules


# ─── Template Behavior Trees ─────────────────────────────

TEMPLATE_CATALOG = {}


def _register_template(name, builder_fn, description):
    TEMPLATE_CATALOG[name] = {"builder": builder_fn, "description": description}


def build_recon_to_strike(params: dict = None) -> BehaviorTree:
    """Recon swarm launches → detect → classify → track → decide → engage → assess.
    This is the core AMOS_Next pipeline.
    """
    p = params or {}

    return BehaviorTree("RECON_TO_STRIKE", Sequence([
        # Phase 1: Detect
        Action("deploy_recon", lambda bb: _bb_set(bb, "phase", "DETECT")),
        RetryUntilSuccess(
            Condition("hostile_detected", lambda bb: bb.get("hostile_count", 0) > 0),
            max_attempts=50, name="wait_for_detection",
        ),
        # Phase 2: Classify
        Action("advance_classify", lambda bb: _bb_set(bb, "phase", "CLASSIFY")),
        Selector([
            Sequence([
                Condition("multi_sensor_confirm", lambda bb: bb.get("confirming_sensors", 0) >= 2),
                Action("classify_hostile", lambda bb: _bb_set(bb, "classification", "CONFIRMED_HOSTILE")),
            ]),
            Sequence([
                Condition("single_sensor", lambda bb: bb.get("confirming_sensors", 0) >= 1),
                Action("classify_suspected", lambda bb: _bb_set(bb, "classification", "SUSPECTED")),
            ]),
        ], name="classification_logic"),
        # Phase 3: Track
        Action("begin_tracking", lambda bb: _bb_set(bb, "phase", "TRACK")),
        Action("assign_tracker", lambda bb: _bb_append(bb, "events", "Tracker asset assigned")),
        # Phase 4: Decide (ROE gate)
        Action("enter_decide", lambda bb: _bb_set(bb, "phase", "DECIDE")),
        Selector([
            Sequence([
                Condition("weapons_free", lambda bb: bb.get("roe_posture") == "weapons_free"),
                Condition("confirmed_hostile", lambda bb: bb.get("classification") == "CONFIRMED_HOSTILE"),
                Action("auto_authorize", lambda bb: _bb_set(bb, "strike_authorized", True)),
            ]),
            Sequence([
                Condition("weapons_tight", lambda bb: bb.get("roe_posture") in ("weapons_tight", "weapons_hold")),
                Action("request_human_approval", lambda bb: _bb_set(bb, "awaiting_approval", True)),
                Condition("human_approved", lambda bb: bb.get("human_approved", False)),
                Action("mark_authorized", lambda bb: _bb_set(bb, "strike_authorized", True)),
            ]),
        ], name="roe_gate"),
        # Phase 5: Engage
        Guard(
            Condition("strike_auth_check", lambda bb: bb.get("strike_authorized", False)),
            Sequence([
                Action("enter_engage", lambda bb: _bb_set(bb, "phase", "ENGAGE")),
                Action("assign_strike_asset", lambda bb: _bb_append(bb, "events", "Strike asset assigned")),
                Action("execute_strike", lambda bb: _bb_append(bb, "events", "Strike executed")),
            ]),
            name="engage_guard",
        ),
        # Phase 6: Assess
        Action("enter_assess", lambda bb: _bb_set(bb, "phase", "ASSESS")),
        Action("conduct_bda", lambda bb: _bb_append(bb, "events", "BDA conducted")),
        Action("mission_complete", lambda bb: _bb_set(bb, "phase", "COMPLETE")),
    ]))


def build_cqb_assault(params: dict = None) -> BehaviorTree:
    """CQB building assault: approach → breach → clear → secure → extract."""
    p = params or {}
    building = p.get("building_id", "ALPHA")

    return BehaviorTree("CQB_ASSAULT", Sequence([
        # Approach
        Action("phase_approach", lambda bb: _bb_set(bb, "phase", "APPROACH")),
        Action("form_stack", lambda bb: _bb_append(bb, "events", f"Stack formed at {building}")),
        Condition("stack_ready", lambda bb: bb.get("stack_count", 0) >= bb.get("min_stack", 2)),
        # Breach
        Action("phase_breach", lambda bb: _bb_set(bb, "phase", "BREACH")),
        Selector([
            Sequence([
                Condition("door_reinforced", lambda bb: bb.get("door_type") == "reinforced"),
                Action("explosive_breach", lambda bb: _bb_append(bb, "events", "Explosive breach")),
            ]),
            Action("standard_entry", lambda bb: _bb_append(bb, "events", "Standard entry")),
        ], name="breach_method"),
        # Clear
        Action("phase_clear", lambda bb: _bb_set(bb, "phase", "CLEAR")),
        Action("clear_rooms", lambda bb: _bb_set(bb, "rooms_cleared", bb.get("rooms_cleared", 0) + 1)),
        Selector([
            Sequence([
                Condition("hostage_detected", lambda bb: bb.get("hostage_present", False)),
                Action("hostage_protocol", lambda bb: _bb_append(bb, "events", "Hostage protocol activated")),
            ]),
            Action("standard_clear", lambda bb: _bb_append(bb, "events", "Standard room clear")),
        ], name="clear_logic"),
        # Secure
        Action("phase_secure", lambda bb: _bb_set(bb, "phase", "SECURE")),
        Action("set_security", lambda bb: _bb_append(bb, "events", "Building secured")),
        # Extract
        Action("phase_extract", lambda bb: _bb_set(bb, "phase", "EXTRACT")),
        Action("exfil", lambda bb: _bb_set(bb, "phase", "COMPLETE")),
    ]))


def build_border_interdiction(params: dict = None) -> BehaviorTree:
    """Border patrol: detect → investigate → track → intercept → report."""
    return BehaviorTree("BORDER_INTERDICTION", Sequence([
        Action("phase_patrol", lambda bb: _bb_set(bb, "phase", "PATROL")),
        RetryUntilSuccess(
            Condition("anomaly_detected", lambda bb: bb.get("anomaly_count", 0) > 0),
            max_attempts=100, name="wait_for_anomaly",
        ),
        Action("phase_investigate", lambda bb: _bb_set(bb, "phase", "INVESTIGATE")),
        Action("dispatch_isr", lambda bb: _bb_append(bb, "events", "ISR dispatched to anomaly")),
        Selector([
            Sequence([
                Condition("confirmed_intrusion", lambda bb: bb.get("intrusion_confirmed", False)),
                Action("phase_track", lambda bb: _bb_set(bb, "phase", "TRACK")),
                Action("assign_trackers", lambda bb: _bb_append(bb, "events", "Multi-asset tracking")),
                Action("phase_intercept", lambda bb: _bb_set(bb, "phase", "INTERCEPT")),
                Action("deploy_ground_unit", lambda bb: _bb_append(bb, "events", "Ground unit deployed")),
            ]),
            Sequence([
                Condition("false_alarm", lambda bb: not bb.get("intrusion_confirmed", False)),
                Action("log_false_alarm", lambda bb: _bb_append(bb, "events", "False alarm logged")),
            ]),
        ], name="intrusion_response"),
        Action("phase_report", lambda bb: _bb_set(bb, "phase", "REPORT")),
        Action("generate_report", lambda bb: _bb_set(bb, "phase", "COMPLETE")),
    ]))


def build_sensor_sweep(params: dict = None) -> BehaviorTree:
    """Systematic area coverage with sensor fusion."""
    return BehaviorTree("SENSOR_SWEEP", Sequence([
        Action("phase_deploy", lambda bb: _bb_set(bb, "phase", "DEPLOY")),
        Action("assign_sectors", lambda bb: _bb_append(bb, "events", "Sectors assigned")),
        Action("phase_scan", lambda bb: _bb_set(bb, "phase", "SCAN")),
        Parallel([
            Action("eo_ir_scan", lambda bb: _bb_set(bb, "eo_ir_complete", True)),
            Action("sigint_scan", lambda bb: _bb_set(bb, "sigint_complete", True)),
            Action("radar_scan", lambda bb: _bb_set(bb, "radar_complete", True)),
        ], success_threshold=2, name="multi_sensor_scan"),
        Action("phase_correlate", lambda bb: _bb_set(bb, "phase", "CORRELATE")),
        Action("fuse_detections", lambda bb: _bb_append(bb, "events", "Detections fused")),
        Action("phase_report", lambda bb: _bb_set(bb, "phase", "REPORT")),
        Action("publish_picture", lambda bb: _bb_set(bb, "phase", "COMPLETE")),
    ]))


def build_relay_support(params: dict = None) -> BehaviorTree:
    """Detect comms gap and assign relay drone."""
    return BehaviorTree("RELAY_SUPPORT", Sequence([
        Condition("comms_degraded", lambda bb: bb.get("comms_health", 1.0) < 0.6),
        Action("identify_gap", lambda bb: _bb_set(bb, "phase", "IDENTIFY_GAP")),
        Action("select_relay_asset", lambda bb: _bb_append(bb, "events", "Relay drone selected")),
        Action("position_relay", lambda bb: _bb_set(bb, "phase", "POSITIONING")),
        RetryUntilSuccess(
            Condition("relay_connected", lambda bb: bb.get("comms_health", 0) >= 0.8),
            max_attempts=10, name="wait_for_connectivity",
        ),
        Action("relay_active", lambda bb: _bb_set(bb, "phase", "COMPLETE")),
    ]))


# Register all templates
_register_template("RECON_TO_STRIKE", build_recon_to_strike,
    "Recon swarm → detect → classify → track → ROE gate → engage → BDA. The core AMOS autonomy loop.")
_register_template("CQB_ASSAULT", build_cqb_assault,
    "Close-quarters building assault: approach → breach → clear → secure → extract.")
_register_template("BORDER_INTERDICTION", build_border_interdiction,
    "Border patrol: detect anomaly → investigate → track → intercept → report.")
_register_template("SENSOR_SWEEP", build_sensor_sweep,
    "Multi-sensor area coverage with parallel scan and fusion.")
_register_template("RELAY_SUPPORT", build_relay_support,
    "Detect comms degradation and assign relay drone to restore connectivity.")


# ─── Blackboard Helpers ───────────────────────────────────

def _bb_set(bb, key, value):
    """Set a blackboard key. Returns True (action success)."""
    bb[key] = value
    return True


def _bb_append(bb, key, value):
    """Append to a blackboard list. Returns True (action success)."""
    if key not in bb:
        bb[key] = []
    bb[key].append({"value": value, "time": datetime.now(timezone.utc).isoformat()})
    return True


# ─── Mission Pipeline ─────────────────────────────────────

class MissionPipeline:
    """Evaluates sensor fusion tracks against trigger rules and manages
    behavior trees for autonomous mission execution.

    Usage:
        pipeline = MissionPipeline()
        events = pipeline.tick(fused_tracks, blackboard)
    """

    def __init__(self):
        self.rules = _default_rules()
        self.bt_registry = BTRegistry()
        self.event_log = []
        self.spawned_tasks = []
        self.stats = {
            "ticks": 0, "rules_fired": 0, "tasks_spawned": 0,
            "bts_created": 0, "bts_completed": 0,
        }
        self._lock = threading.Lock()

    def add_rule(self, rule: TriggerRule):
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)

    def remove_rule(self, rule_id: str) -> bool:
        before = len(self.rules)
        self.rules = [r for r in self.rules if r.id != rule_id]
        return len(self.rules) < before

    def create_bt_from_template(self, template_name: str, params: dict = None) -> dict:
        """Create a behavior tree from a named template and register it."""
        tmpl = TEMPLATE_CATALOG.get(template_name)
        if not tmpl:
            return {"error": f"Unknown template: {template_name}",
                    "available": list(TEMPLATE_CATALOG.keys())}
        bt = tmpl["builder"](params)
        self.bt_registry.register(bt)
        self.stats["bts_created"] += 1
        return bt.summary()

    def tick(self, fused_tracks: list, bb: dict) -> list:
        """Evaluate trigger rules against fused tracks and tick all BTs.

        Args:
            fused_tracks: list of track dicts from sensor_fusion_engine
            bb: shared blackboard dict with mission context

        Returns:
            list of events generated this tick
        """
        with self._lock:
            self.stats["ticks"] += 1
            events = []

            # Evaluate trigger rules against each track
            for track in (fused_tracks or []):
                for rule in self.rules:
                    result = rule.evaluate(track, bb)
                    if result:
                        self.stats["rules_fired"] += 1
                        self.stats["tasks_spawned"] += 1
                        result["rule_id"] = rule.id
                        result["rule_name"] = rule.name
                        result["timestamp"] = datetime.now(timezone.utc).isoformat()
                        self.spawned_tasks.append(result)
                        events.append(result)

            # Tick all active behavior trees
            bt_results = self.bt_registry.tick_all(bb)
            for r in bt_results:
                if r["status"] == "SUCCESS":
                    self.stats["bts_completed"] += 1
                events.append({"type": "BT_TICK", **r})

            # Trim logs
            if len(self.spawned_tasks) > 500:
                self.spawned_tasks = self.spawned_tasks[-500:]
            if len(self.event_log) > 1000:
                self.event_log = self.event_log[-1000:]

            self.event_log.extend(events)
            return events

    def get_rules(self) -> list:
        return [r.to_dict() for r in self.rules]

    def get_spawned_tasks(self, limit: int = 50) -> list:
        return self.spawned_tasks[-limit:]

    def summary(self) -> dict:
        return {
            **self.stats,
            "rules_count": len(self.rules),
            "active_bts": self.bt_registry.summary(),
            "templates_available": list(TEMPLATE_CATALOG.keys()),
        }

    def get_templates(self) -> list:
        return [{"name": k, "description": v["description"]}
                for k, v in TEMPLATE_CATALOG.items()]


if __name__ == "__main__":
    import json

    pipeline = MissionPipeline()
    print("Templates:", list(TEMPLATE_CATALOG.keys()))

    # Create a recon-to-strike BT
    bt_info = pipeline.create_bt_from_template("RECON_TO_STRIKE")
    print(f"\nCreated BT: {bt_info}")

    # Simulate a tick with a hostile track
    tracks = [{
        "id": "TRK-001", "lat": 27.85, "lng": -82.52,
        "classification": "HOSTILE", "confidence": 0.75,
        "kill_chain": {"phase": "IDENTIFY"}, "age_sec": 30,
    }]
    bb = {"hostile_count": 1, "roe_posture": "weapons_tight",
          "confirming_sensors": 2, "comms_health": 0.9}

    events = pipeline.tick(tracks, bb)
    print(f"\nTick events: {len(events)}")
    for e in events:
        print(f"  {e.get('type', e.get('action', '?'))}: {e.get('description', e.get('name', ''))}")

    print(f"\nPipeline: {json.dumps(pipeline.summary(), indent=2)}")
