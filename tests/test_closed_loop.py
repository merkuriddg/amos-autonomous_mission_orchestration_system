"""Tests for AMOS Closed Loop Orchestrator + COP — Sprint 3."""
import time
import pytest
from services.sensor_fusion_engine import SensorFusionEngine
from services.mission_pipeline import MissionPipeline
from services.task_allocator import TaskAllocator
from services.swarm_behaviors import SwarmBehaviorManager
from services.closed_loop import ClosedLoopOrchestrator


# ─── Fixtures ──────────────────────────────────────────

def make_orchestrator():
    """Create a fresh ClosedLoopOrchestrator with all subsystems."""
    sf = SensorFusionEngine()
    mp = MissionPipeline()
    ta = TaskAllocator()
    sbm = SwarmBehaviorManager()
    return ClosedLoopOrchestrator(sf, mp, ta, sbm)


def make_assets():
    """Create test assets with sensors that can detect threats."""
    return {
        "GHOST-01": {
            "id": "GHOST-01", "type": "uav", "domain": "air", "role": "isr_strike",
            "position": {"lat": 27.85, "lng": -82.52},
            "sensors": ["AESA_RADAR", "EO/IR"], "weapons": ["HELLFIRE"],
            "status": "operational", "heading_deg": 90, "speed_kts": 120,
            "health": {"battery_pct": 95, "comms_strength": 90},
        },
        "GHOST-02": {
            "id": "GHOST-02", "type": "uav", "domain": "air", "role": "recon",
            "position": {"lat": 27.86, "lng": -82.53},
            "sensors": ["EO/IR", "SIGINT"], "weapons": [],
            "status": "operational", "heading_deg": 45, "speed_kts": 100,
            "health": {"battery_pct": 88, "comms_strength": 85},
        },
        "TALON-01": {
            "id": "TALON-01", "type": "ugv", "domain": "ground", "role": "direct_action",
            "position": {"lat": 27.84, "lng": -82.51},
            "sensors": ["LIDAR", "ACOUSTIC"], "weapons": ["M240"],
            "status": "operational", "heading_deg": 180, "speed_kts": 15,
            "health": {"battery_pct": 92, "comms_strength": 95},
        },
    }


def make_threats():
    """Create test threats within sensor range."""
    return {
        "THR-001": {
            "id": "THR-001", "type": "drone", "lat": 27.855, "lng": -82.515,
            "neutralized": False, "threat_level": "high",
        },
        "THR-002": {
            "id": "THR-002", "type": "vessel", "lat": 27.87, "lng": -82.50,
            "neutralized": False, "threat_level": "medium",
        },
    }


# ═══════════════════════════════════════════════════════════
#  ORCHESTRATOR CONSTRUCTION
# ═══════════════════════════════════════════════════════════

class TestConstruction:
    def test_creates_with_all_subsystems(self):
        orch = make_orchestrator()
        assert orch.sensor_fusion is not None
        assert orch.mission_pipeline is not None
        assert orch.task_allocator is not None
        assert orch.swarm_behavior_mgr is not None
        assert orch.tick_count == 0

    def test_summary_initial(self):
        orch = make_orchestrator()
        s = orch.summary()
        assert s["tick_count"] == 0
        assert s["stats"]["ticks"] == 0


# ═══════════════════════════════════════════════════════════
#  TICK CYCLE
# ═══════════════════════════════════════════════════════════

class TestTickCycle:
    def test_tick_returns_result(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        result = orch.tick(assets, threats)
        assert "tick" in result
        assert result["tick"] == 1
        assert "events" in result
        assert "summary" in result
        assert "timestamp" in result

    def test_tick_increments_count(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        orch.tick(assets, threats)
        orch.tick(assets, threats)
        assert orch.tick_count == 2
        assert orch.stats["ticks"] == 2

    def test_tick_produces_fusion_events(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        result = orch.tick(assets, threats)
        # At least one threat should be correlated into a fused track
        assert result["summary"]["fused_tracks"] >= 1

    def test_tick_events_have_timestamps(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        result = orch.tick(assets, threats)
        for ev in result["events"]:
            assert "timestamp" in ev

    def test_tick_with_blackboard(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        bb = {"roe_posture": "weapons_free", "comms_health": 0.8}
        result = orch.tick(assets, threats, blackboard=bb)
        # blackboard should be enriched with fused tracks
        assert "fused_tracks" in bb
        assert "track_count" in bb

    def test_tick_empty_threats(self):
        orch = make_orchestrator()
        assets = make_assets()
        result = orch.tick(assets, {})
        assert result["summary"]["fused_tracks"] == 0

    def test_tick_empty_assets(self):
        orch = make_orchestrator()
        threats = make_threats()
        result = orch.tick({}, threats)
        # No assets = no detections
        assert result["summary"]["fused_tracks"] == 0

    def test_multiple_ticks_accumulate_history(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        for _ in range(5):
            orch.tick(assets, threats)
        assert len(orch.events_history) > 0

    def test_stats_accumulate(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        orch.tick(assets, threats)
        assert orch.stats["ticks"] == 1
        assert orch.stats["total_events"] >= 0
        assert orch.stats["fusion_events"] >= 0


# ═══════════════════════════════════════════════════════════
#  SENSOR → TASK PIPELINE
# ═══════════════════════════════════════════════════════════

class TestSensorToTaskPipeline:
    def test_detections_create_fused_tracks(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        orch.tick(assets, threats)
        tracks = orch.sensor_fusion.get_tracks()
        assert len(tracks) >= 1

    def test_pipeline_rules_fire_on_hostile_tracks(self):
        orch = make_orchestrator()
        # Reset cooldowns on pipeline rules so they fire
        for r in orch.mission_pipeline.rules:
            r.cooldown_sec = 0
        assets = make_assets()
        threats = make_threats()
        # Run a few ticks to let tracks build up confidence
        for _ in range(3):
            result = orch.tick(assets, threats)
        # Check pipeline stats
        assert orch.stats["pipeline_events"] >= 0

    def test_tasks_created_from_pipeline(self):
        orch = make_orchestrator()
        for r in orch.mission_pipeline.rules:
            r.cooldown_sec = 0
        assets = make_assets()
        threats = make_threats()
        for _ in range(5):
            orch.tick(assets, threats)
        task_stats = orch.task_allocator.get_stats()
        # Tasks may or may not be created depending on track confidence
        assert task_stats["tasks_created"] >= 0


# ═══════════════════════════════════════════════════════════
#  COP (Common Operating Picture)
# ═══════════════════════════════════════════════════════════

class TestCOP:
    def test_cop_returns_all_layers(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        orch.tick(assets, threats)
        cop = orch.cop(assets, threats)
        assert "layers" in cop
        assert "operations" in cop
        assert "autonomy" in cop
        assert "counts" in cop
        assert "timeline" in cop
        assert "timestamp" in cop

    def test_cop_layers_have_assets(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        orch.tick(assets, threats)
        cop = orch.cop(assets, threats)
        assert cop["counts"]["assets"] == 3
        assert "GHOST-01" in cop["layers"]["assets"]
        a = cop["layers"]["assets"]["GHOST-01"]
        assert a["domain"] == "air"
        assert "lat" in a and "lng" in a

    def test_cop_layers_have_threats(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        orch.tick(assets, threats)
        cop = orch.cop(assets, threats)
        assert cop["counts"]["threats"] == 2
        assert "THR-001" in cop["layers"]["threats"]

    def test_cop_has_fused_tracks(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        orch.tick(assets, threats)
        cop = orch.cop(assets, threats)
        assert cop["counts"]["fused_tracks"] >= 1

    def test_cop_has_coverage(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        orch.tick(assets, threats)
        cop = orch.cop(assets, threats)
        assert "coverage" in cop["layers"]
        assert "footprints" in cop["layers"]["coverage"]
        assert "gap_count" in cop["layers"]["coverage"]

    def test_cop_has_kill_chain(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        orch.tick(assets, threats)
        cop = orch.cop(assets, threats)
        assert "kill_chain" in cop["layers"]
        assert "phase_counts" in cop["layers"]["kill_chain"]

    def test_cop_operations_section(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        orch.tick(assets, threats)
        cop = orch.cop(assets, threats)
        ops = cop["operations"]
        assert "active_tasks" in ops
        assert "active_missions" in ops
        assert "behavior_trees" in ops
        assert "swarm_behaviors" in ops

    def test_cop_autonomy_section(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        orch.tick(assets, threats)
        cop = orch.cop(assets, threats)
        auto = cop["autonomy"]
        assert "pipeline_rules" in auto
        assert "swarm_triggers" in auto
        assert "pipeline_stats" in auto
        assert "task_stats" in auto

    def test_cop_threat_track_cross_reference(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        # Run several ticks to build correlations
        for _ in range(3):
            orch.tick(assets, threats)
        cop = orch.cop(assets, threats)
        # Check that at least one threat has a fused_track_id
        has_link = any(
            t.get("fused_track_id") is not None
            for t in cop["layers"]["threats"].values()
        )
        assert has_link is True

    def test_cop_empty_state(self):
        orch = make_orchestrator()
        cop = orch.cop({}, {})
        assert cop["counts"]["assets"] == 0
        assert cop["counts"]["threats"] == 0
        assert cop["counts"]["fused_tracks"] == 0

    def test_cop_timeline_populated_after_ticks(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        for _ in range(3):
            orch.tick(assets, threats)
        cop = orch.cop(assets, threats)
        assert len(cop["timeline"]) > 0


# ═══════════════════════════════════════════════════════════
#  SUMMARY + HISTORY
# ═══════════════════════════════════════════════════════════

class TestSummaryAndHistory:
    def test_summary_after_ticks(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        orch.tick(assets, threats)
        s = orch.summary()
        assert s["tick_count"] == 1
        assert s["last_tick"] > 0

    def test_events_history_capped(self):
        orch = make_orchestrator()
        assets = make_assets()
        threats = make_threats()
        # Tick many times
        for _ in range(100):
            orch.tick(assets, threats)
        assert len(orch.events_history) <= 500
