"""Tests for AMOS Swarm Behaviors — Sprint 2."""
import time
import pytest
from services.swarm_behaviors import (
    SwarmBehavior, PerimeterScan, AreaSweep, DynamicTrack,
    RelayMesh, SearchSpiral, SwarmBehaviorManager, BEHAVIOR_CATALOG,
    _dist_deg, _polygon_centroid, _polygon_perimeter_points,
)


# ─── Test helpers ──────────────────────────────────────

SQUARE_VERTICES = [
    {"lat": 27.85, "lng": -82.52},
    {"lat": 27.85, "lng": -82.51},
    {"lat": 27.84, "lng": -82.51},
    {"lat": 27.84, "lng": -82.52},
]

SWEEP_BOUNDS = {"north": 27.86, "south": 27.84, "east": -82.50, "west": -82.54}


def make_assets(ids, lat=27.85, lng=-82.52):
    """Create minimal asset dicts."""
    return {
        aid: {"id": aid, "position": {"lat": lat, "lng": lng}, "status": "operational"}
        for aid in ids
    }


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

class TestHelpers:
    def test_dist_deg(self):
        d = _dist_deg(0, 0, 3, 4)
        assert abs(d - 5.0) < 1e-9

    def test_polygon_centroid(self):
        clat, clng = _polygon_centroid(SQUARE_VERTICES)
        assert abs(clat - 27.845) < 0.001
        assert abs(clng - (-82.515)) < 0.001

    def test_polygon_perimeter_points(self):
        pts = _polygon_perimeter_points(SQUARE_VERTICES, 8)
        assert len(pts) == 8
        for p in pts:
            assert "lat" in p and "lng" in p


# ═══════════════════════════════════════════════════════════
#  BASE BEHAVIOR
# ═══════════════════════════════════════════════════════════

class TestSwarmBehavior:
    def test_cancel(self):
        b = SwarmBehavior("SB-1", "ALPHA", ["A1", "A2"])
        result = b.cancel()
        assert result["status"] == "cancelled"
        assert b.status == "cancelled"

    def test_to_dict(self):
        b = SwarmBehavior("SB-1", "ALPHA", ["A1", "A2"])
        d = b.to_dict()
        assert d["id"] == "SB-1"
        assert d["type"] == "BASE"
        assert len(d["asset_ids"]) == 2

    def test_progress(self):
        b = SwarmBehavior("SB-1", "ALPHA", ["A1"])
        p = b.progress()
        assert p["coverage_pct"] == 0.0
        assert p["status"] == "active"


# ═══════════════════════════════════════════════════════════
#  PERIMETER SCAN
# ═══════════════════════════════════════════════════════════

class TestPerimeterScan:
    def test_tick_moves_assets(self):
        assets = make_assets(["A1", "A2", "A3"])
        b = PerimeterScan("SB-1", "ALPHA", ["A1", "A2", "A3"],
                          {"vertices": SQUARE_VERTICES, "speed_factor": 0.5})
        events = b.tick(assets, {}, dt=1.0)
        assert b.tick_count == 1
        assert b.phase == "SCANNING"
        # Assets should have moved
        assert assets["A1"]["position"]["lat"] != 27.85 or assets["A1"]["position"]["lng"] != -82.52

    def test_coverage_increases(self):
        assets = make_assets(["A1", "A2"])
        b = PerimeterScan("SB-1", "ALPHA", ["A1", "A2"],
                          {"vertices": SQUARE_VERTICES, "speed_factor": 0.8})
        for _ in range(50):
            b.tick(assets, {}, dt=1.0)
        assert b.coverage_pct > 0

    def test_empty_vertices(self):
        assets = make_assets(["A1"])
        b = PerimeterScan("SB-1", "ALPHA", ["A1"], {"vertices": []})
        events = b.tick(assets, {}, dt=1.0)
        assert events == []

    def test_cancelled_no_tick(self):
        assets = make_assets(["A1"])
        b = PerimeterScan("SB-1", "ALPHA", ["A1"], {"vertices": SQUARE_VERTICES})
        b.cancel()
        events = b.tick(assets, {}, dt=1.0)
        assert events == []
        assert b.tick_count == 0


# ═══════════════════════════════════════════════════════════
#  AREA SWEEP
# ═══════════════════════════════════════════════════════════

class TestAreaSweep:
    def test_generates_tracks(self):
        b = AreaSweep("SB-1", "ALPHA", ["A1", "A2"],
                      {"bounds": SWEEP_BOUNDS, "track_spacing_m": 300})
        assert b.total_tracks > 0
        assert len(b.tracks) > 0

    def test_tick_advances_progress(self):
        assets = make_assets(["A1", "A2"])
        b = AreaSweep("SB-1", "ALPHA", ["A1", "A2"],
                      {"bounds": SWEEP_BOUNDS, "speed_factor": 0.5})
        b.tick(assets, {}, dt=1.0)
        assert b.tick_count == 1
        assert b.phase == "SWEEPING"
        assert b.coverage_pct > 0

    def test_completes_with_fast_speed(self):
        assets = make_assets(["A1", "A2", "A3"])
        b = AreaSweep("SB-1", "ALPHA", ["A1", "A2", "A3"],
                      {"bounds": SWEEP_BOUNDS, "speed_factor": 2.0})
        for _ in range(200):
            b.tick(assets, {}, dt=1.0)
        assert b.status == "completed"
        assert b.coverage_pct == 100.0

    def test_zero_width_bounds(self):
        assets = make_assets(["A1"])
        b = AreaSweep("SB-1", "ALPHA", ["A1"],
                      {"bounds": {"north": 28, "south": 27, "east": -82, "west": -82}})
        # Should still create at least 1 track
        assert b.total_tracks >= 1


# ═══════════════════════════════════════════════════════════
#  DYNAMIC TRACK
# ═══════════════════════════════════════════════════════════

class TestDynamicTrack:
    def test_converges_on_target(self):
        assets = make_assets(["A1", "A2", "A3"], lat=27.80, lng=-82.50)
        b = DynamicTrack("SB-1", "ALPHA", ["A1", "A2", "A3"],
                         {"track_id": "TRK-001", "initial_lat": 27.85, "initial_lng": -82.52})
        for _ in range(10):
            b.tick(assets, {}, dt=1.0)
        # Assets should have moved toward target
        for aid in ["A1", "A2", "A3"]:
            assert assets[aid]["position"]["lat"] > 27.80  # moved north toward target

    def test_updates_from_blackboard(self):
        assets = make_assets(["A1", "A2"])
        b = DynamicTrack("SB-1", "ALPHA", ["A1", "A2"],
                         {"track_id": "TRK-001", "initial_lat": 27.85, "initial_lng": -82.52})
        bb = {"fused_tracks": {"TRK-001": {"lat": 28.0, "lng": -82.0}}}
        b.tick(assets, bb, dt=1.0)
        assert b.target_lat == 28.0
        assert b.target_lng == -82.0

    def test_coverage_with_multiple_assets(self):
        # Spread assets around target for good coverage
        assets = {
            "A1": {"id": "A1", "position": {"lat": 27.855, "lng": -82.52}},
            "A2": {"id": "A2", "position": {"lat": 27.845, "lng": -82.52}},
            "A3": {"id": "A3", "position": {"lat": 27.85, "lng": -82.525}},
            "A4": {"id": "A4", "position": {"lat": 27.85, "lng": -82.515}},
        }
        b = DynamicTrack("SB-1", "ALPHA", ["A1", "A2", "A3", "A4"],
                         {"track_id": "TRK-001", "initial_lat": 27.85, "initial_lng": -82.52})
        b.tick(assets, {}, dt=1.0)
        assert b.coverage_pct > 0

    def test_phase_tracking(self):
        assets = make_assets(["A1", "A2"])
        b = DynamicTrack("SB-1", "ALPHA", ["A1", "A2"],
                         {"track_id": "TRK-001", "initial_lat": 27.85, "initial_lng": -82.52})
        b.tick(assets, {}, dt=1.0)
        assert b.phase == "TRACKING"


# ═══════════════════════════════════════════════════════════
#  RELAY MESH
# ═══════════════════════════════════════════════════════════

class TestRelayMesh:
    def test_positions_between_endpoints(self):
        endpoints = [
            {"lat": 27.80, "lng": -82.52, "id": "BASE"},
            {"lat": 27.90, "lng": -82.52, "id": "FOB"},
        ]
        assets = make_assets(["R1", "R2"], lat=27.85, lng=-82.52)
        b = RelayMesh("SB-1", "RELAY", ["R1", "R2"],
                      {"endpoints": endpoints, "max_link_range_m": 50000})
        for _ in range(20):
            b.tick(assets, {}, dt=1.0)
        # Assets should be between the endpoints
        for aid in ["R1", "R2"]:
            lat = assets[aid]["position"]["lat"]
            assert 27.80 <= lat <= 27.90

    def test_connectivity_measurement(self):
        endpoints = [
            {"lat": 27.80, "lng": -82.52, "id": "A"},
            {"lat": 27.81, "lng": -82.52, "id": "B"},
        ]
        # Assets close to endpoints → connected
        assets = make_assets(["R1"], lat=27.805, lng=-82.52)
        b = RelayMesh("SB-1", "RELAY", ["R1"],
                      {"endpoints": endpoints, "max_link_range_m": 50000})
        b.tick(assets, {}, dt=1.0)
        assert b.connectivity > 0

    def test_insufficient_endpoints(self):
        assets = make_assets(["R1"])
        b = RelayMesh("SB-1", "RELAY", ["R1"],
                      {"endpoints": [{"lat": 27.85, "lng": -82.52, "id": "ONLY"}]})
        events = b.tick(assets, {}, dt=1.0)
        assert b.phase == "INSUFFICIENT_ENDPOINTS"


# ═══════════════════════════════════════════════════════════
#  SEARCH SPIRAL
# ═══════════════════════════════════════════════════════════

class TestSearchSpiral:
    def test_expands_radius(self):
        assets = make_assets(["S1", "S2"])
        b = SearchSpiral("SB-1", "SEARCH", ["S1", "S2"],
                         {"center": {"lat": 27.85, "lng": -82.52}})
        initial_radius = b.radius
        b.tick(assets, {}, dt=1.0)
        assert b.radius > initial_radius
        assert b.phase == "SEARCHING"

    def test_completes_at_max_radius(self):
        assets = make_assets(["S1"])
        b = SearchSpiral("SB-1", "SEARCH", ["S1"],
                         {"center": {"lat": 27.85, "lng": -82.52},
                          "max_radius_m": 200, "expansion_rate": 500})
        b.tick(assets, {}, dt=1.0)
        assert b.status == "completed"
        assert b.phase == "MAX_RADIUS_REACHED"

    def test_target_reacquired(self):
        assets = make_assets(["S1"])
        b = SearchSpiral("SB-1", "SEARCH", ["S1"],
                         {"center": {"lat": 27.85, "lng": -82.52}})
        events = b.tick(assets, {"target_reacquired": True}, dt=1.0)
        assert b.status == "completed"
        assert b.phase == "TARGET_FOUND"
        assert any(e["type"] == "SEARCH_TARGET_FOUND" for e in events)

    def test_coverage_increases_over_time(self):
        assets = make_assets(["S1", "S2"])
        b = SearchSpiral("SB-1", "SEARCH", ["S1", "S2"],
                         {"center": {"lat": 27.85, "lng": -82.52}})
        coverages = []
        for _ in range(5):
            b.tick(assets, {}, dt=1.0)
            coverages.append(b.coverage_pct)
        assert coverages[-1] > coverages[0]


# ═══════════════════════════════════════════════════════════
#  BEHAVIOR CATALOG
# ═══════════════════════════════════════════════════════════

class TestBehaviorCatalog:
    def test_all_types_present(self):
        assert "PERIMETER_SCAN" in BEHAVIOR_CATALOG
        assert "AREA_SWEEP" in BEHAVIOR_CATALOG
        assert "DYNAMIC_TRACK" in BEHAVIOR_CATALOG
        assert "RELAY_MESH" in BEHAVIOR_CATALOG
        assert "SEARCH_SPIRAL" in BEHAVIOR_CATALOG

    def test_each_has_class_and_params(self):
        for name, spec in BEHAVIOR_CATALOG.items():
            assert "class" in spec
            assert "min_assets" in spec
            assert "required_params" in spec
            assert spec["min_assets"] >= 1


# ═══════════════════════════════════════════════════════════
#  SWARM BEHAVIOR MANAGER
# ═══════════════════════════════════════════════════════════

class TestSwarmBehaviorManager:
    def test_summary(self):
        mgr = SwarmBehaviorManager()
        s = mgr.summary()
        assert s["active_count"] == 0
        assert s["catalog_count"] == 5

    def test_list_catalog(self):
        mgr = SwarmBehaviorManager()
        catalog = mgr.list_catalog()
        names = [c["type"] for c in catalog]
        assert "PERIMETER_SCAN" in names
        assert len(catalog) == 5

    def test_assign_behavior(self):
        mgr = SwarmBehaviorManager()
        result = mgr.assign_behavior(
            "AREA_SWEEP", "ALPHA", ["A1", "A2"],
            {"bounds": SWEEP_BOUNDS})
        assert "error" not in result
        assert result["type"] == "AREA_SWEEP"
        assert mgr.stats["behaviors_created"] == 1

    def test_assign_unknown_type(self):
        mgr = SwarmBehaviorManager()
        result = mgr.assign_behavior("NONEXISTENT", "ALPHA", ["A1"])
        assert "error" in result

    def test_assign_insufficient_assets(self):
        mgr = SwarmBehaviorManager()
        result = mgr.assign_behavior(
            "PERIMETER_SCAN", "ALPHA", ["A1"],  # needs 2
            {"vertices": SQUARE_VERTICES})
        assert "error" in result

    def test_assign_missing_params(self):
        mgr = SwarmBehaviorManager()
        result = mgr.assign_behavior("AREA_SWEEP", "ALPHA", ["A1"], {})
        assert "error" in result

    def test_tick_all(self):
        mgr = SwarmBehaviorManager()
        mgr.assign_behavior("SEARCH_SPIRAL", "ALPHA", ["S1"],
                            {"center": {"lat": 27.85, "lng": -82.52}})
        assets = make_assets(["S1"])
        events = mgr.tick(assets, {}, dt=1.0)
        assert mgr.stats["ticks"] == 1

    def test_cancel_behavior(self):
        mgr = SwarmBehaviorManager()
        result = mgr.assign_behavior("SEARCH_SPIRAL", "ALPHA", ["S1"],
                                     {"center": {"lat": 27.85, "lng": -82.52}})
        bid = result["id"]
        cancel = mgr.cancel_behavior(bid)
        assert cancel["status"] == "cancelled"
        assert len(mgr.list_active()) == 0
        assert mgr.stats["behaviors_cancelled"] == 1

    def test_cancel_nonexistent(self):
        mgr = SwarmBehaviorManager()
        result = mgr.cancel_behavior("SB-FAKE")
        assert "error" in result

    def test_get_behavior(self):
        mgr = SwarmBehaviorManager()
        result = mgr.assign_behavior("SEARCH_SPIRAL", "ALPHA", ["S1"],
                                     {"center": {"lat": 27.85, "lng": -82.52}})
        bid = result["id"]
        b = mgr.get_behavior(bid)
        assert b is not None
        assert b["id"] == bid

    def test_completed_moves_to_history(self):
        mgr = SwarmBehaviorManager()
        mgr.assign_behavior("SEARCH_SPIRAL", "ALPHA", ["S1"],
                            {"center": {"lat": 27.85, "lng": -82.52},
                             "max_radius_m": 100, "expansion_rate": 500})
        assets = make_assets(["S1"])
        mgr.tick(assets, {}, dt=1.0)
        # Should have completed and moved to history
        assert len(mgr.list_active()) == 0
        assert mgr.stats["behaviors_completed"] == 1


# ═══════════════════════════════════════════════════════════
#  SENSOR FUSION TRIGGERS
# ═══════════════════════════════════════════════════════════

class TestSensorFusionTriggers:
    def test_hostile_track_triggers_dynamic_track(self):
        mgr = SwarmBehaviorManager()
        tracks = [{"id": "TRK-001", "lat": 27.85, "lng": -82.52,
                   "classification": "HOSTILE", "confidence": 0.8}]
        swarms = {"ALPHA": {"asset_ids": ["A1", "A2", "A3"]}}
        spawned = mgr.evaluate_sensor_triggers(tracks, swarms)
        assert len(spawned) == 1
        assert spawned[0]["type"] == "DYNAMIC_TRACK"
        assert mgr.stats["sensor_triggers"] == 1

    def test_low_confidence_no_trigger(self):
        mgr = SwarmBehaviorManager()
        tracks = [{"id": "TRK-001", "lat": 27.85, "lng": -82.52,
                   "classification": "HOSTILE", "confidence": 0.3}]
        swarms = {"ALPHA": {"asset_ids": ["A1", "A2"]}}
        spawned = mgr.evaluate_sensor_triggers(tracks, swarms)
        assert len(spawned) == 0

    def test_lost_track_triggers_search(self):
        mgr = SwarmBehaviorManager()
        tracks = [{"id": "TRK-002", "lat": 27.86, "lng": -82.53, "status": "LOST"}]
        swarms = {"BRAVO": {"asset_ids": ["B1"]}}
        spawned = mgr.evaluate_sensor_triggers(tracks, swarms)
        assert len(spawned) == 1
        assert spawned[0]["type"] == "SEARCH_SPIRAL"

    def test_cooldown_prevents_repeated_triggers(self):
        mgr = SwarmBehaviorManager()
        tracks = [{"id": "TRK-001", "lat": 27.85, "lng": -82.52,
                   "classification": "HOSTILE", "confidence": 0.8}]
        swarms = {"ALPHA": {"asset_ids": ["A1", "A2"]}}
        spawned1 = mgr.evaluate_sensor_triggers(tracks, swarms)
        spawned2 = mgr.evaluate_sensor_triggers(tracks, swarms)
        assert len(spawned1) == 1
        assert len(spawned2) == 0  # cooldown active

    def test_disabled_trigger(self):
        mgr = SwarmBehaviorManager()
        for t in mgr.auto_triggers:
            t["enabled"] = False
        tracks = [{"id": "TRK-001", "lat": 27.85, "lng": -82.52,
                   "classification": "HOSTILE", "confidence": 0.9}]
        swarms = {"ALPHA": {"asset_ids": ["A1", "A2"]}}
        spawned = mgr.evaluate_sensor_triggers(tracks, swarms)
        assert len(spawned) == 0

    def test_toggle_trigger(self):
        mgr = SwarmBehaviorManager()
        result = mgr.toggle_trigger("AUTOTRIG-TRACK-HOSTILE")
        assert result["enabled"] is False
        result = mgr.toggle_trigger("AUTOTRIG-TRACK-HOSTILE")
        assert result["enabled"] is True

    def test_toggle_nonexistent(self):
        mgr = SwarmBehaviorManager()
        result = mgr.toggle_trigger("FAKE")
        assert "error" in result

    def test_get_triggers(self):
        mgr = SwarmBehaviorManager()
        triggers = mgr.get_triggers()
        assert len(triggers) == 2
        ids = [t["id"] for t in triggers]
        assert "AUTOTRIG-TRACK-HOSTILE" in ids
        assert "AUTOTRIG-LOST-SEARCH" in ids
