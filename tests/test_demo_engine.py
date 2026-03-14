"""Tests for AMOS Investor Demo Engine — Sprint 4."""
import time
import pytest
from services.sensor_fusion_engine import SensorFusionEngine
from services.mission_pipeline import MissionPipeline
from services.task_allocator import TaskAllocator
from services.swarm_behaviors import SwarmBehaviorManager
from services.closed_loop import ClosedLoopOrchestrator
from services.demo_engine import DemoRunner, DEMO_SCENARIOS


# ─── Fixtures ──────────────────────────────────────────

def make_runner():
    """Create a fresh DemoRunner with real subsystems."""
    sf = SensorFusionEngine()
    mp = MissionPipeline()
    ta = TaskAllocator()
    sbm = SwarmBehaviorManager()
    cl = ClosedLoopOrchestrator(sf, mp, ta, sbm)
    return DemoRunner(cl, sbm, ta)


# ═══════════════════════════════════════════════════════════
#  SCENARIO CATALOG
# ═══════════════════════════════════════════════════════════

class TestScenarioCatalog:
    def test_catalog_has_three_scenarios(self):
        assert len(DEMO_SCENARIOS) == 3

    def test_catalog_keys(self):
        assert "RECON_TO_STRIKE" in DEMO_SCENARIOS
        assert "BORDER_INTERDICTION" in DEMO_SCENARIOS
        assert "SWARM_SHOWCASE" in DEMO_SCENARIOS

    def test_list_scenarios_returns_all(self):
        catalog = DemoRunner.list_scenarios()
        assert len(catalog) == 3
        ids = {s["id"] for s in catalog}
        assert ids == {"RECON_TO_STRIKE", "BORDER_INTERDICTION", "SWARM_SHOWCASE"}

    def test_list_scenarios_has_required_fields(self):
        for s in DemoRunner.list_scenarios():
            assert "id" in s
            assert "name" in s
            assert "description" in s
            assert "duration_sec" in s
            assert "phase_count" in s
            assert s["duration_sec"] > 0
            assert s["phase_count"] > 0

    def test_recon_to_strike_scenario(self):
        fn = DEMO_SCENARIOS["RECON_TO_STRIKE"]
        sc = fn()
        assert sc["id"] == "RECON_TO_STRIKE"
        assert sc["duration_sec"] == 120
        assert len(sc["phases"]) == 7

    def test_border_interdiction_scenario(self):
        fn = DEMO_SCENARIOS["BORDER_INTERDICTION"]
        sc = fn()
        assert sc["id"] == "BORDER_INTERDICTION"
        assert sc["duration_sec"] == 100
        assert len(sc["phases"]) == 4

    def test_swarm_showcase_scenario(self):
        fn = DEMO_SCENARIOS["SWARM_SHOWCASE"]
        sc = fn()
        assert sc["id"] == "SWARM_SHOWCASE"
        assert sc["duration_sec"] == 100
        assert len(sc["phases"]) == 6

    def test_each_scenario_phases_have_required_keys(self):
        for sid, fn in DEMO_SCENARIOS.items():
            sc = fn()
            for phase in sc["phases"]:
                assert "name" in phase, f"{sid} phase missing 'name'"
                assert "start_sec" in phase, f"{sid} phase missing 'start_sec'"
                assert "narration" in phase, f"{sid} phase missing 'narration'"
                assert "actions" in phase, f"{sid} phase missing 'actions'"

    def test_phases_are_sorted_by_start_sec(self):
        for sid, fn in DEMO_SCENARIOS.items():
            sc = fn()
            starts = [p["start_sec"] for p in sc["phases"]]
            assert starts == sorted(starts), f"{sid} phases not sorted"


# ═══════════════════════════════════════════════════════════
#  LIFECYCLE — START / STOP
# ═══════════════════════════════════════════════════════════

class TestLifecycle:
    def test_initial_state(self):
        runner = make_runner()
        assert runner.status == "idle"
        assert runner.scenario is None
        assert runner.sim_time == 0.0
        assert runner.tick_count == 0
        assert runner.timeline == []

    def test_start_returns_status(self):
        runner = make_runner()
        result = runner.start("RECON_TO_STRIKE")
        assert result["status"] == "running"
        assert result["scenario"] == "RECON_TO_STRIKE"
        assert result["duration_sec"] == 120
        assert result["phase_count"] == 7
        assert result["speed"] == 1.0

    def test_start_sets_running(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        assert runner.status == "running"
        assert runner.scenario is not None
        assert runner.started_at is not None

    def test_start_unknown_scenario(self):
        runner = make_runner()
        result = runner.start("NONEXISTENT")
        assert "error" in result
        assert "available" in result

    def test_start_while_running(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        result = runner.start("BORDER_INTERDICTION")
        assert "error" in result
        assert "already running" in result["error"].lower()

    def test_start_with_custom_speed(self):
        runner = make_runner()
        result = runner.start("RECON_TO_STRIKE", speed=3.0)
        assert result["speed"] == 3.0
        assert runner.speed == 3.0

    def test_speed_minimum_clamp(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE", speed=0.01)
        assert runner.speed == 0.1  # clamped to min 0.1

    def test_stop_running_demo(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        result = runner.stop()
        assert result["status"] == "idle"

    def test_stop_when_idle(self):
        runner = make_runner()
        result = runner.stop()
        assert "error" in result

    def test_stop_resets_status(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=5.0)
        runner.stop()
        assert runner.status == "idle"

    def test_restart_after_stop(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.stop()
        result = runner.start("BORDER_INTERDICTION")
        assert result["status"] == "running"
        assert result["scenario"] == "BORDER_INTERDICTION"

    def test_start_clears_previous_state(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=5.0)
        runner.stop()
        runner.start("BORDER_INTERDICTION")
        assert runner.sim_time == 0.0
        assert runner.tick_count == 0
        assert runner.demo_assets == {}
        assert runner.demo_threats == {}


# ═══════════════════════════════════════════════════════════
#  TICK PROGRESSION
# ═══════════════════════════════════════════════════════════

class TestTick:
    def test_tick_when_idle(self):
        runner = make_runner()
        result = runner.tick()
        assert result["status"] == "idle"
        assert result["events"] == []

    def test_tick_returns_required_fields(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        result = runner.tick()
        assert "status" in result
        assert "tick" in result
        assert "sim_time" in result
        assert "phase" in result
        assert "progress_pct" in result
        assert "events" in result
        assert "event_count" in result

    def test_tick_advances_sim_time(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=5.0)
        assert runner.sim_time == 5.0

    def test_tick_increments_count(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick()
        runner.tick()
        runner.tick()
        assert runner.tick_count == 3

    def test_first_tick_executes_first_phase(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        result = runner.tick(dt=1.0)
        # First phase starts at sec 0, so should fire immediately
        assert runner.current_phase_idx >= 1
        events = result["events"]
        spawn_events = [e for e in events if e.get("type") == "ASSET_SPAWNED"]
        assert len(spawn_events) > 0  # SWARM_LAUNCH phase spawns assets

    def test_tick_spawns_demo_assets(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=1.0)
        # RECON_TO_STRIKE first phase spawns 4 assets
        assert len(runner.demo_assets) == 4
        assert "DEMO-RECON-01" in runner.demo_assets
        assert "DEMO-STRIKE-04" in runner.demo_assets

    def test_tick_progress_percentage(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")  # 120s duration
        runner.tick(dt=60.0)
        result = runner.tick(dt=0.0)  # no-op tick just to get status
        # ~60s / 120s = 50%
        assert result["progress_pct"] == pytest.approx(50.0, abs=1.0)

    def test_multiple_phases_fire_as_time_advances(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        # Advance past first two phases (0s and 20s)
        runner.tick(dt=25.0)
        assert runner.current_phase_idx >= 2

    def test_tick_completes_scenario(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")  # 120s duration
        # Advance past the entire duration
        runner.tick(dt=130.0)
        assert runner.status == "completed"

    def test_tick_after_completion(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=130.0)
        result = runner.tick()
        assert result["status"] == "completed"
        assert result["events"] == []


# ═══════════════════════════════════════════════════════════
#  TIME COMPRESSION
# ═══════════════════════════════════════════════════════════

class TestTimeCompression:
    def test_speed_multiplier_applied(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE", speed=2.0)
        runner.tick(dt=5.0)
        # effective_dt = 5 * 2 = 10
        assert runner.sim_time == pytest.approx(10.0)

    def test_high_speed_advances_faster(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE", speed=10.0)
        runner.tick(dt=5.0)  # effective = 50s
        # Should have passed multiple phases (0, 20, 35)
        assert runner.current_phase_idx >= 3

    def test_speed_affects_completion(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE", speed=5.0)  # 120s / 5 = 24s wall time
        runner.tick(dt=25.0)  # effective = 125s > 120s
        assert runner.status == "completed"

    def test_slow_speed(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE", speed=0.5)
        runner.tick(dt=10.0)  # effective = 5s
        assert runner.sim_time == pytest.approx(5.0)


# ═══════════════════════════════════════════════════════════
#  EVENT TIMELINE
# ═══════════════════════════════════════════════════════════

class TestTimeline:
    def test_start_creates_timeline_entry(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        assert len(runner.timeline) == 1
        assert runner.timeline[0]["type"] == "DEMO_START"

    def test_timeline_grows_with_phases(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=25.0)  # fires phases at 0s and 20s
        # DEMO_START + PHASE(SWARM_LAUNCH) + behavior events + PHASE(THREAT_DETECTED) + detection
        assert len(runner.timeline) >= 3

    def test_timeline_entries_have_required_fields(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=25.0)
        for entry in runner.timeline:
            assert "sim_time" in entry
            assert "wall_time" in entry
            assert "type" in entry
            assert "title" in entry
            assert "phase" in entry

    def test_get_timeline_reversed(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=50.0)
        timeline = runner.get_timeline()
        # Should be most-recent first
        assert len(timeline) > 1
        assert timeline[0]["sim_time"] >= timeline[-1]["sim_time"]

    def test_get_timeline_limit(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=100.0)  # fire many phases
        limited = runner.get_timeline(limit=3)
        assert len(limited) <= 3

    def test_stop_adds_timeline_entry(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=5.0)
        before = len(runner.timeline)
        runner.stop()
        assert len(runner.timeline) == before + 1
        assert runner.timeline[-1]["type"] == "DEMO_STOP"

    def test_completion_adds_timeline_entry(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=130.0)
        complete_events = [e for e in runner.timeline if e["type"] == "DEMO_COMPLETE"]
        assert len(complete_events) == 1

    def test_threat_injection_records_detection(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=25.0)  # passes THREAT_DETECTED phase at 20s
        detections = [e for e in runner.timeline if e["type"] == "DETECTION"]
        assert len(detections) >= 1

    def test_autonomous_decisions_recorded(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=40.0)  # passes AUTO_RETASK phase at 35s
        decisions = [e for e in runner.timeline if e["type"] == "AUTONOMOUS_DECISION"]
        assert len(decisions) >= 1


# ═══════════════════════════════════════════════════════════
#  PHASE TRANSITIONS
# ═══════════════════════════════════════════════════════════

class TestPhaseTransitions:
    def test_initial_phase_name(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        assert runner._current_phase_name() == "SWARM_LAUNCH"

    def test_phase_advances(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=1.0)   # fires SWARM_LAUNCH (0s)
        runner.tick(dt=24.0)  # fires THREAT_DETECTED (20s)
        assert runner.current_phase_idx >= 2

    def test_all_phases_fire_for_recon_to_strike(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=115.0)  # past all phases (last at 110s)
        assert runner.current_phase_idx == 7  # all 7 phases done

    def test_all_phases_fire_for_border_interdiction(self):
        runner = make_runner()
        runner.start("BORDER_INTERDICTION")
        runner.tick(dt=90.0)  # past all phases (last at 85s)
        assert runner.current_phase_idx == 4  # all 4 phases done

    def test_all_phases_fire_for_swarm_showcase(self):
        runner = make_runner()
        runner.start("SWARM_SHOWCASE")
        runner.tick(dt=90.0)  # past all phases (last at 85s)
        assert runner.current_phase_idx == 6  # all 6 phases done

    def test_phase_reported_in_tick_result(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        result = runner.tick(dt=1.0)
        assert "phase" in result


# ═══════════════════════════════════════════════════════════
#  PHASE ACTIONS — SPAWN / THREAT / BEHAVIOR / TASK
# ═══════════════════════════════════════════════════════════

class TestPhaseActions:
    def test_spawn_assets_populates_demo_assets(self):
        runner = make_runner()
        runner.start("BORDER_INTERDICTION")
        runner.tick(dt=1.0)
        assert len(runner.demo_assets) == 3
        for aid in ("DEMO-BDR-01", "DEMO-BDR-02", "DEMO-BDR-03"):
            assert aid in runner.demo_assets
            asset = runner.demo_assets[aid]
            assert "position" in asset
            assert "sensors" in asset
            assert asset["status"] == "operational"
            assert asset["health"]["battery_pct"] == 100

    def test_inject_threat_populates_demo_threats(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=25.0)
        assert "DEMO-THR-001" in runner.demo_threats
        thr = runner.demo_threats["DEMO-THR-001"]
        assert thr["type"] == "vehicle"
        assert thr["threat_level"] == "high"

    def test_assign_behavior_creates_swarm_behavior(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=1.0)
        # SWARM_LAUNCH assigns AREA_SWEEP
        assert len(runner.swarm_behavior_mgr.active_behaviors) >= 1

    def test_create_task_via_phase(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=95.0)  # past STRIKE_ASSIGNED at 90s
        assert runner.task_allocator.stats["tasks_created"] >= 1

    def test_cancel_all_behaviors_action(self):
        runner = make_runner()
        runner.start("SWARM_SHOWCASE")
        runner.tick(dt=10.0)  # fires SETUP + AREA_SWEEP
        active_before = len(runner.swarm_behavior_mgr.active_behaviors)
        runner.tick(dt=20.0)  # fires PERIMETER_SCAN which cancels first
        # The cancel happened and a new behavior was assigned
        assert runner.swarm_behavior_mgr.stats["behaviors_cancelled"] >= 1

    def test_events_marked_as_demo(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        result = runner.tick(dt=1.0)
        for ev in result["events"]:
            assert ev.get("demo") is True


# ═══════════════════════════════════════════════════════════
#  GET STATUS
# ═══════════════════════════════════════════════════════════

class TestGetStatus:
    def test_status_while_running(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=30.0)
        status = runner.get_status()
        assert status["status"] == "running"
        assert status["scenario"] == "RECON_TO_STRIKE"
        assert status["sim_time"] == pytest.approx(30.0)
        assert status["duration_sec"] == 120
        assert status["speed"] == 1.0
        assert status["demo_assets"] > 0
        assert status["timeline_count"] > 0

    def test_status_has_phase_info(self):
        runner = make_runner()
        runner.start("RECON_TO_STRIKE")
        runner.tick(dt=5.0)
        status = runner.get_status()
        assert "current_phase" in status
        assert "phases_completed" in status
        assert "total_phases" in status
        assert status["total_phases"] == 7

    def test_status_progress_pct(self):
        runner = make_runner()
        runner.start("BORDER_INTERDICTION")  # 100s
        runner.tick(dt=50.0)
        status = runner.get_status()
        assert status["progress_pct"] == pytest.approx(50.0, abs=1.0)
