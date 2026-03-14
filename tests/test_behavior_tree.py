"""Tests for the AMOS Behavior Tree engine and Mission Pipeline."""
import time
import pytest
from services.behavior_tree import (
    Status, Node, Condition, Action, Sequence, Selector, Parallel,
    Inverter, Repeater, Guard, RetryUntilSuccess, BehaviorTree, BTRegistry,
)
from services.mission_pipeline import (
    TriggerRule, MissionPipeline, TEMPLATE_CATALOG,
    build_recon_to_strike, build_cqb_assault, build_border_interdiction,
    build_sensor_sweep, build_relay_support,
)


# ═══════════════════════════════════════════════════════════
#  LEAF NODES
# ═══════════════════════════════════════════════════════════

class TestCondition:
    def test_true(self):
        c = Condition("check", lambda bb: bb.get("x") > 0)
        assert c.tick({"x": 5}) == Status.SUCCESS

    def test_false(self):
        c = Condition("check", lambda bb: bb.get("x") > 0)
        assert c.tick({"x": -1}) == Status.FAILURE

    def test_exception_returns_failure(self):
        c = Condition("bad", lambda bb: bb["missing_key"])
        assert c.tick({}) == Status.FAILURE

    def test_tick_count(self):
        c = Condition("c", lambda bb: True)
        c.tick({})
        c.tick({})
        assert c.tick_count == 2


class TestAction:
    def test_returns_true(self):
        a = Action("act", lambda bb: True)
        assert a.tick({}) == Status.SUCCESS

    def test_returns_false(self):
        a = Action("act", lambda bb: False)
        assert a.tick({}) == Status.FAILURE

    def test_returns_running(self):
        a = Action("act", lambda bb: "running")
        assert a.tick({}) == Status.RUNNING

    def test_returns_status_enum(self):
        a = Action("act", lambda bb: Status.RUNNING)
        assert a.tick({}) == Status.RUNNING

    def test_modifies_blackboard(self):
        bb = {}
        a = Action("set", lambda b: b.update({"flag": True}) or True)
        a.tick(bb)
        assert bb["flag"] is True

    def test_exception_returns_failure(self):
        a = Action("bad", lambda bb: 1 / 0)
        assert a.tick({}) == Status.FAILURE


# ═══════════════════════════════════════════════════════════
#  COMPOSITES
# ═══════════════════════════════════════════════════════════

class TestSequence:
    def test_all_succeed(self):
        s = Sequence([
            Condition("a", lambda bb: True),
            Condition("b", lambda bb: True),
        ])
        assert s.tick({}) == Status.SUCCESS

    def test_first_fails(self):
        s = Sequence([
            Condition("a", lambda bb: False),
            Action("b", lambda bb: True),
        ])
        assert s.tick({}) == Status.FAILURE

    def test_running_resumes(self):
        call_count = [0]
        def maybe_running(bb):
            call_count[0] += 1
            return "running" if call_count[0] < 2 else True
        s = Sequence([
            Action("a", lambda bb: True),
            Action("b", maybe_running),
        ])
        assert s.tick({}) == Status.RUNNING
        assert s.tick({}) == Status.SUCCESS

    def test_to_dict_has_children(self):
        s = Sequence([Condition("x", lambda bb: True)])
        d = s.to_dict()
        assert "children" in d
        assert len(d["children"]) == 1


class TestSelector:
    def test_first_succeeds(self):
        s = Selector([
            Condition("a", lambda bb: True),
            Condition("b", lambda bb: False),
        ])
        assert s.tick({}) == Status.SUCCESS

    def test_all_fail(self):
        s = Selector([
            Condition("a", lambda bb: False),
            Condition("b", lambda bb: False),
        ])
        assert s.tick({}) == Status.FAILURE

    def test_fallback(self):
        s = Selector([
            Condition("a", lambda bb: False),
            Action("b", lambda bb: True),
        ])
        assert s.tick({}) == Status.SUCCESS


class TestParallel:
    def test_all_succeed(self):
        p = Parallel([
            Condition("a", lambda bb: True),
            Condition("b", lambda bb: True),
        ])
        assert p.tick({}) == Status.SUCCESS

    def test_threshold(self):
        p = Parallel([
            Condition("a", lambda bb: True),
            Condition("b", lambda bb: False),
            Condition("c", lambda bb: True),
        ], success_threshold=2)
        assert p.tick({}) == Status.SUCCESS

    def test_below_threshold_fails(self):
        p = Parallel([
            Condition("a", lambda bb: False),
            Condition("b", lambda bb: False),
            Condition("c", lambda bb: True),
        ], success_threshold=2)
        assert p.tick({}) == Status.FAILURE


# ═══════════════════════════════════════════════════════════
#  DECORATORS
# ═══════════════════════════════════════════════════════════

class TestInverter:
    def test_inverts_success(self):
        i = Inverter(Condition("ok", lambda bb: True))
        assert i.tick({}) == Status.FAILURE

    def test_inverts_failure(self):
        i = Inverter(Condition("no", lambda bb: False))
        assert i.tick({}) == Status.SUCCESS

    def test_running_passes_through(self):
        i = Inverter(Action("run", lambda bb: "running"))
        assert i.tick({}) == Status.RUNNING


class TestRepeater:
    def test_repeats_and_completes(self):
        count = [0]
        def inc(bb):
            count[0] += 1
            return True
        r = Repeater(Action("inc", inc), max_repeats=3)
        assert r.tick({}) == Status.RUNNING
        assert r.tick({}) == Status.RUNNING
        assert r.tick({}) == Status.SUCCESS
        assert count[0] == 3

    def test_stops_on_failure(self):
        r = Repeater(Condition("no", lambda bb: False), max_repeats=5)
        assert r.tick({}) == Status.FAILURE


class TestGuard:
    def test_passes_when_condition_met(self):
        g = Guard(
            Condition("ok", lambda bb: True),
            Action("act", lambda bb: True),
        )
        assert g.tick({}) == Status.SUCCESS

    def test_blocks_when_condition_not_met(self):
        g = Guard(
            Condition("no", lambda bb: False),
            Action("act", lambda bb: True),
        )
        assert g.tick({}) == Status.FAILURE


class TestRetryUntilSuccess:
    def test_succeeds_on_retry(self):
        attempts = [0]
        def flaky(bb):
            attempts[0] += 1
            return attempts[0] >= 2
        r = RetryUntilSuccess(Action("flaky", flaky), max_attempts=3)
        assert r.tick({}) == Status.RUNNING
        assert r.tick({}) == Status.SUCCESS

    def test_fails_after_max_attempts(self):
        r = RetryUntilSuccess(Condition("no", lambda bb: False), max_attempts=2)
        r.tick({})
        assert r.tick({}) == Status.FAILURE


# ═══════════════════════════════════════════════════════════
#  BEHAVIOR TREE + REGISTRY
# ═══════════════════════════════════════════════════════════

class TestBehaviorTree:
    def test_create_and_tick(self):
        bt = BehaviorTree("test", Condition("ok", lambda bb: True))
        assert bt.tick({}) == Status.SUCCESS
        assert bt.tick_count == 1
        assert bt.id.startswith("BT-")

    def test_to_dict(self):
        bt = BehaviorTree("test", Condition("ok", lambda bb: True))
        bt.tick({})
        d = bt.to_dict()
        assert d["name"] == "test"
        assert d["status"] == "SUCCESS"
        assert "tree" in d

    def test_reset(self):
        bt = BehaviorTree("test", Condition("ok", lambda bb: True))
        bt.tick({})
        bt.reset()
        assert bt.status == Status.FAILURE


class TestBTRegistry:
    def test_register_and_list(self):
        reg = BTRegistry()
        bt = BehaviorTree("test", Condition("ok", lambda bb: True))
        reg.register(bt)
        assert len(reg.list_all()) == 1

    def test_unregister(self):
        reg = BTRegistry()
        bt = BehaviorTree("test", Condition("ok", lambda bb: True))
        reg.register(bt)
        assert reg.unregister(bt.id) is True
        assert len(reg.list_all()) == 0

    def test_tick_all(self):
        reg = BTRegistry()
        reg.register(BehaviorTree("a", Condition("ok", lambda bb: True)))
        reg.register(BehaviorTree("b", Condition("no", lambda bb: False)))
        results = reg.tick_all({})
        statuses = {r["name"]: r["status"] for r in results}
        assert statuses["a"] == "SUCCESS"
        assert statuses["b"] == "FAILURE"


# ═══════════════════════════════════════════════════════════
#  TRIGGER RULES
# ═══════════════════════════════════════════════════════════

class TestTriggerRule:
    def test_fires_when_condition_met(self):
        r = TriggerRule("test",
            condition_fn=lambda t, bb: t.get("hostile"),
            action_fn=lambda t, bb: {"action": "ALERT"},
            cooldown_sec=0,
        )
        result = r.evaluate({"hostile": True}, {})
        assert result is not None
        assert result["action"] == "ALERT"
        assert r.fire_count == 1

    def test_does_not_fire_when_condition_not_met(self):
        r = TriggerRule("test",
            condition_fn=lambda t, bb: t.get("hostile"),
            action_fn=lambda t, bb: {"action": "ALERT"},
            cooldown_sec=0,
        )
        result = r.evaluate({"hostile": False}, {})
        assert result is None

    def test_cooldown(self):
        r = TriggerRule("test",
            condition_fn=lambda t, bb: True,
            action_fn=lambda t, bb: {"action": "X"},
            cooldown_sec=999,
        )
        assert r.evaluate({}, {}) is not None
        assert r.evaluate({}, {}) is None  # cooldown active

    def test_disabled(self):
        r = TriggerRule("test",
            condition_fn=lambda t, bb: True,
            action_fn=lambda t, bb: {"action": "X"},
            cooldown_sec=0, enabled=False,
        )
        assert r.evaluate({}, {}) is None


# ═══════════════════════════════════════════════════════════
#  MISSION PIPELINE
# ═══════════════════════════════════════════════════════════

class TestMissionPipeline:
    def test_summary(self):
        p = MissionPipeline()
        s = p.summary()
        assert s["ticks"] == 0
        assert s["rules_count"] == 5
        assert len(s["templates_available"]) == 5

    def test_templates_available(self):
        p = MissionPipeline()
        templates = p.get_templates()
        names = [t["name"] for t in templates]
        assert "RECON_TO_STRIKE" in names
        assert "CQB_ASSAULT" in names
        assert "BORDER_INTERDICTION" in names
        assert "SENSOR_SWEEP" in names
        assert "RELAY_SUPPORT" in names

    def test_create_bt_from_template(self):
        p = MissionPipeline()
        result = p.create_bt_from_template("RECON_TO_STRIKE")
        assert "id" in result
        assert result["name"] == "RECON_TO_STRIKE"
        assert p.stats["bts_created"] == 1

    def test_create_bt_unknown_template(self):
        p = MissionPipeline()
        result = p.create_bt_from_template("NONEXISTENT")
        assert "error" in result

    def test_tick_fires_rules(self):
        p = MissionPipeline()
        # Reset cooldowns
        for r in p.rules:
            r.cooldown_sec = 0
        tracks = [{
            "id": "TRK-001", "lat": 27.85, "lng": -82.52,
            "classification": "HOSTILE", "confidence": 0.75,
            "kill_chain": {"phase": "IDENTIFY"}, "age_sec": 30,
        }]
        bb = {"roe_posture": "weapons_tight", "comms_health": 0.9}
        events = p.tick(tracks, bb)
        assert len(events) > 0
        assert p.stats["ticks"] == 1

    def test_tick_with_active_bt(self):
        p = MissionPipeline()
        p.create_bt_from_template("SENSOR_SWEEP")
        bb = {"comms_health": 0.9}
        events = p.tick([], bb)
        bt_events = [e for e in events if e.get("type") == "BT_TICK"]
        assert len(bt_events) == 1


# ═══════════════════════════════════════════════════════════
#  TEMPLATE BT EXECUTION
# ═══════════════════════════════════════════════════════════

class TestTemplateBTs:
    def test_recon_to_strike_detects_and_classifies(self):
        bt = build_recon_to_strike()
        bb = {"hostile_count": 1, "confirming_sensors": 2,
              "roe_posture": "weapons_free"}
        status = bt.tick(bb)
        assert bb.get("phase") is not None
        assert status in (Status.SUCCESS, Status.RUNNING)

    def test_cqb_assault_runs(self):
        bt = build_cqb_assault({"building_id": "BRAVO"})
        bb = {"stack_count": 4, "min_stack": 2, "door_type": "reinforced"}
        status = bt.tick(bb)
        assert bb.get("phase") is not None

    def test_border_interdiction_waits_for_anomaly(self):
        bt = build_border_interdiction()
        bb = {"anomaly_count": 0}
        status = bt.tick(bb)
        # Should be RUNNING (waiting for anomaly)
        assert status == Status.RUNNING

    def test_border_interdiction_responds_to_intrusion(self):
        bt = build_border_interdiction()
        bb = {"anomaly_count": 1, "intrusion_confirmed": True}
        # Tick multiple times to advance past RetryUntilSuccess
        for _ in range(3):
            status = bt.tick(bb)
        assert bb.get("phase") in ("TRACK", "INTERCEPT", "REPORT", "COMPLETE")

    def test_sensor_sweep_completes(self):
        bt = build_sensor_sweep()
        bb = {}
        status = bt.tick(bb)
        assert status == Status.SUCCESS
        assert bb.get("phase") == "COMPLETE"

    def test_relay_support_with_good_comms(self):
        bt = build_relay_support()
        bb = {"comms_health": 0.9}
        status = bt.tick(bb)
        # Comms good — condition fails, tree fails
        assert status == Status.FAILURE

    def test_relay_support_with_bad_comms(self):
        bt = build_relay_support()
        bb = {"comms_health": 0.3}
        status = bt.tick(bb)
        # Comms bad, but relay not yet connected — RUNNING
        assert status == Status.RUNNING
