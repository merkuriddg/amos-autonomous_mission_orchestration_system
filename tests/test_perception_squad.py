"""B4.2 Perception Fusion + B5 Squad Autonomy Supervisor Tests.

Tests:
  - PerceptionFusion: detection ingest, track correlation, SLAM grids,
    intel forwarding, neutralization, stats
  - OccupancyGrid: merge_scan, explored_pct, to_dict
  - SquadSupervisor: create mission, plan, execute, tick, reserves,
    abort, AAR generation, stats
  - API endpoints: perception + squad supervisor routes
"""

import sys, os, json, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from services.perception_fusion import (
    PerceptionFusion, CQBDetection, CQBThreatTrack, OccupancyGrid,
    CQB_CLASSIFICATIONS, CQB_CORRELATION_THRESHOLD_M,
)
from services.squad_supervisor import (
    SquadSupervisor, SquadMission, OBJECTIVE_TYPES, MISSION_STATUSES,
)
from services.cqb_planner import CQBPlanner
from services.cqb_executor import CQBExecutor
from services.building_model import BuildingModel, BuildingManager
from services.indoor_positioning import IndoorPositioningService
from core.event_bus import EventBus


# ═══════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════

SAMPLE_BUILDING = {
    "id": "BLDG-PF-01",
    "name": "Perception Test Building",
    "location": {"lat": 35.686, "lng": 51.318, "alt_m": 1200},
    "dimensions": {"length_m": 20, "width_m": 15, "floors": 2},
    "walls": {"material": "concrete", "thickness_cm": 25},
    "entry_points": [{"id": "EP-01", "type": "door", "door_id": "D-001"}],
    "threats_intel": {},
    "floors": [
        {
            "floor": 0, "name": "Ground",
            "rooms": [
                {"id": "R-001", "name": "Entry Hall", "type": "corridor",
                 "bounds": {"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 5}},
                {"id": "R-002", "name": "Office", "type": "office",
                 "bounds": {"x_min": 10, "y_min": 0, "x_max": 20, "y_max": 5}},
            ],
            "doors": [
                {"id": "D-001", "from_room": "EXTERIOR", "to_room": "R-001", "type": "standard"},
                {"id": "D-002", "from_room": "R-001", "to_room": "R-002", "type": "standard"},
            ],
            "windows": [],
            "stairs": [],
        },
    ],
}

TEAM = ["CLAW1", "CLAW2", "CLAW3", "PACK1"]


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def building():
    return BuildingModel(copy.deepcopy(SAMPLE_BUILDING))


@pytest.fixture
def building_mgr(building):
    mgr = BuildingManager()
    mgr.buildings[building.id] = building
    return mgr


@pytest.fixture
def planner():
    return CQBPlanner()


@pytest.fixture
def indoor():
    return IndoorPositioningService()


@pytest.fixture
def executor(building_mgr, indoor, event_bus):
    return CQBExecutor(building_mgr=building_mgr,
                       indoor_positioning=indoor,
                       event_bus=event_bus)


@pytest.fixture
def perception(event_bus):
    return PerceptionFusion(event_bus=event_bus)


@pytest.fixture
def supervisor(building_mgr, planner, executor, perception, event_bus):
    return SquadSupervisor(
        building_mgr=building_mgr,
        cqb_planner=planner,
        cqb_executor=executor,
        perception_fusion=perception,
        event_bus=event_bus,
    )


# ═══════════════════════════════════════════════════════════
#  PERCEPTION FUSION — DETECTIONS
# ═══════════════════════════════════════════════════════════

def test_detection_creation():
    det = CQBDetection("BLDG-01", 0, "R-001", x_m=5.0, y_m=3.0,
                       classification="hostile_armed", confidence=0.8,
                       source_asset="CLAW1")
    assert det.building_id == "BLDG-01"
    assert det.classification == "hostile_armed"
    d = det.to_dict()
    assert d["x_m"] == 5.0
    assert d["source_asset"] == "CLAW1"


def test_ingest_creates_track(perception):
    track = perception.ingest_detection(
        "BLDG-PF-01", 0, "R-001", x_m=5.0, y_m=3.0,
        classification="hostile_armed", confidence=0.8, source_asset="CLAW1")
    assert track.id.startswith("CTT-")
    assert track.building_id == "BLDG-PF-01"
    assert len(perception.tracks) == 1
    assert len(perception.detections) == 1


def test_ingest_correlates_nearby_detections(perception):
    """Two detections within 3m should merge into one track."""
    t1 = perception.ingest_detection("BLDG-PF-01", 0, "R-001",
                                     x_m=5.0, y_m=3.0,
                                     classification="hostile_armed",
                                     confidence=0.7, source_asset="CLAW1")
    t2 = perception.ingest_detection("BLDG-PF-01", 0, "R-001",
                                     x_m=6.0, y_m=3.5,
                                     classification="hostile_armed",
                                     confidence=0.8, source_asset="CLAW2")
    assert t1.id == t2.id  # same track
    assert len(perception.tracks) == 1
    assert len(t1.sources) == 2
    assert t1.confidence > 0.5  # boosted by corroboration


def test_ingest_separates_distant_detections(perception):
    """Two detections > 3m apart should be separate tracks."""
    t1 = perception.ingest_detection("BLDG-PF-01", 0, "R-001",
                                     x_m=1.0, y_m=1.0,
                                     source_asset="CLAW1")
    t2 = perception.ingest_detection("BLDG-PF-01", 0, "R-002",
                                     x_m=15.0, y_m=8.0,
                                     source_asset="CLAW2")
    assert t1.id != t2.id
    assert len(perception.tracks) == 2


def test_ingest_different_floors_separate(perception):
    """Same x/y but different floors should not correlate."""
    t1 = perception.ingest_detection("BLDG-PF-01", 0, "R-001",
                                     x_m=5.0, y_m=3.0, source_asset="CLAW1")
    t2 = perception.ingest_detection("BLDG-PF-01", 1, "R-201",
                                     x_m=5.0, y_m=3.0, source_asset="CLAW2")
    assert t1.id != t2.id
    assert len(perception.tracks) == 2


def test_mark_neutralized(perception):
    t = perception.ingest_detection("BLDG-PF-01", 0, "R-001",
                                    x_m=5.0, y_m=3.0, source_asset="CLAW1")
    assert perception.mark_neutralized(t.id) is True
    assert t.status == "neutralized"
    assert perception.mark_neutralized("FAKE-ID") is False


def test_tracks_in_room(perception):
    perception.ingest_detection("BLDG-PF-01", 0, "R-001",
                                x_m=2.0, y_m=2.0, source_asset="CLAW1")
    perception.ingest_detection("BLDG-PF-01", 0, "R-002",
                                x_m=15.0, y_m=5.0, source_asset="CLAW2")
    room1 = perception.get_tracks_in_room("BLDG-PF-01", "R-001")
    room2 = perception.get_tracks_in_room("BLDG-PF-01", "R-002")
    assert len(room1) == 1
    assert len(room2) == 1


def test_tracks_on_floor(perception):
    perception.ingest_detection("BLDG-PF-01", 0, "R-001",
                                x_m=2.0, y_m=2.0, source_asset="CLAW1")
    perception.ingest_detection("BLDG-PF-01", 0, "R-002",
                                x_m=15.0, y_m=5.0, source_asset="CLAW2")
    floor0 = perception.get_tracks_on_floor("BLDG-PF-01", 0)
    floor1 = perception.get_tracks_on_floor("BLDG-PF-01", 1)
    assert len(floor0) == 2
    assert len(floor1) == 0


# ═══════════════════════════════════════════════════════════
#  PERCEPTION FUSION — SLAM / GRID
# ═══════════════════════════════════════════════════════════

def test_occupancy_grid_creation():
    g = OccupancyGrid("BLDG-01", 0, width_m=10, height_m=10, resolution_m=1.0)
    assert g.cols == 10
    assert g.rows == 10
    assert g.get_explored_pct() == 0


def test_grid_merge_scan():
    g = OccupancyGrid("BLDG-01", 0, width_m=10, height_m=10, resolution_m=1.0)
    cells = [{"x_m": 0.5, "y_m": 0.5, "value": 1},
             {"x_m": 1.5, "y_m": 0.5, "value": 2}]
    g.merge_scan("CLAW1", cells)
    assert g.get_explored_pct() > 0
    assert "CLAW1" in g.contributors
    assert g.last_update is not None


def test_grid_to_dict():
    g = OccupancyGrid("BLDG-01", 0)
    d = g.to_dict()
    assert d["building_id"] == "BLDG-01"
    assert d["floor"] == 0
    assert "explored_pct" in d


def test_slam_ingest_creates_grid(perception):
    # Need enough cells (> 0.05% of 2400) to register after rounding
    cells = [{"x_m": float(i) * 0.5, "y_m": 0.5, "value": 1} for i in range(30)]
    perception.ingest_slam_scan("BLDG-PF-01", 0, "CLAW1", cells)
    grid = perception.get_grid("BLDG-PF-01", 0)
    assert grid is not None
    assert grid["explored_pct"] > 0


def test_get_all_grids(perception):
    perception.ingest_slam_scan("BLDG-PF-01", 0, "CLAW1",
                                [{"x_m": 1, "y_m": 1, "value": 1}])
    perception.ingest_slam_scan("BLDG-PF-01", 1, "CLAW2",
                                [{"x_m": 2, "y_m": 2, "value": 1}])
    grids = perception.get_all_grids()
    assert len(grids) == 2


# ═══════════════════════════════════════════════════════════
#  PERCEPTION FUSION — INTEL FORWARDING
# ═══════════════════════════════════════════════════════════

def test_forward_intel(perception):
    intel = perception.forward_intel("BLDG-PF-01", "R-001",
                                     intel_type="threat",
                                     details="IED reported near door")
    assert intel["type"] == "intel_forward"
    assert intel["building_id"] == "BLDG-PF-01"
    assert len(perception.intel_forwarded) == 1


def test_perception_stats(perception):
    perception.ingest_detection("BLDG-PF-01", 0, "R-001",
                                x_m=5.0, y_m=3.0, source_asset="CLAW1")
    perception.ingest_slam_scan("BLDG-PF-01", 0, "CLAW1",
                                [{"x_m": 1, "y_m": 1, "value": 1}])
    perception.forward_intel("BLDG-PF-01", "R-001")
    stats = perception.get_stats()
    assert stats["total_tracks"] == 1
    assert stats["active_tracks"] == 1
    assert stats["total_detections"] == 1
    assert stats["grids"] == 1
    assert stats["intel_forwarded"] == 1


# ═══════════════════════════════════════════════════════════
#  SQUAD SUPERVISOR — MISSION LIFECYCLE
# ═══════════════════════════════════════════════════════════

def test_create_mission(supervisor):
    m = supervisor.create_mission(
        objective="Clear Building PF-01",
        building_id="BLDG-PF-01",
        asset_ids=TEAM,
    )
    assert m.id.startswith("MISSION-")
    assert m.status == "PENDING"
    assert m.objective == "Clear Building PF-01"
    assert len(supervisor.missions) == 1


def test_plan_mission(supervisor):
    m = supervisor.create_mission("Clear BLDG-PF-01", "BLDG-PF-01",
                                  asset_ids=TEAM)
    result = supervisor.plan_mission(m.id)
    assert result.get("status") == "ok"
    assert m.plan_id is not None
    assert m.status == "READY"


def test_plan_mission_bad_building(supervisor):
    m = supervisor.create_mission("Clear fake", "BLDG-FAKE",
                                  asset_ids=TEAM)
    result = supervisor.plan_mission(m.id)
    assert "error" in result


def test_execute_mission(supervisor):
    m = supervisor.create_mission("Clear BLDG-PF-01", "BLDG-PF-01",
                                  asset_ids=TEAM)
    supervisor.plan_mission(m.id)
    result = supervisor.execute_mission(m.id)
    assert result.get("status") == "ok"
    assert m.execution_id is not None
    assert m.status == "EXECUTING"


def test_execute_without_plan_fails(supervisor):
    m = supervisor.create_mission("Clear BLDG-PF-01", "BLDG-PF-01",
                                  asset_ids=TEAM)
    result = supervisor.execute_mission(m.id)
    assert "error" in result


def test_execute_without_assets_fails(supervisor):
    m = supervisor.create_mission("Clear BLDG-PF-01", "BLDG-PF-01",
                                  asset_ids=[])
    supervisor.plan_mission(m.id)
    result = supervisor.execute_mission(m.id)
    assert "error" in result


def test_tick_mission(supervisor):
    m = supervisor.create_mission("Clear BLDG-PF-01", "BLDG-PF-01",
                                  asset_ids=TEAM)
    supervisor.plan_mission(m.id)
    supervisor.execute_mission(m.id)
    result = supervisor.tick_mission(m.id)
    assert result.get("status") == "ok"
    assert "execution" in result


def test_full_mission_lifecycle(supervisor):
    """Plan → execute → tick to completion → AAR generated."""
    m = supervisor.create_mission("Clear BLDG-PF-01", "BLDG-PF-01",
                                  asset_ids=TEAM)
    supervisor.plan_mission(m.id)
    supervisor.execute_mission(m.id)
    for _ in range(50):
        result = supervisor.tick_mission(m.id)
        if m.status == "COMPLETE":
            break
    assert m.status == "COMPLETE"
    assert m.aar is not None
    assert m.aar["mission_id"] == m.id
    assert m.aar["total_tasks"] > 0
    assert m.aar["completed_tasks"] > 0


def test_abort_mission(supervisor):
    m = supervisor.create_mission("Clear BLDG-PF-01", "BLDG-PF-01",
                                  asset_ids=TEAM)
    supervisor.plan_mission(m.id)
    supervisor.execute_mission(m.id)
    result = supervisor.abort_mission(m.id, "test abort")
    assert result.get("aborted") is True
    assert m.status == "ABORTED"
    assert m.completed is not None


# ═══════════════════════════════════════════════════════════
#  SQUAD SUPERVISOR — RESERVES
# ═══════════════════════════════════════════════════════════

def test_commit_reserves(supervisor):
    m = supervisor.create_mission("Clear BLDG-PF-01", "BLDG-PF-01",
                                  asset_ids=["CLAW1", "CLAW2"],
                                  reserve_ids=["CLAW3", "PACK1"])
    result = supervisor.commit_reserves(m.id, count=1)
    assert result["status"] == "ok"
    assert len(result["committed"]) == 1
    assert result["remaining_reserves"] == 1
    assert m.retasks == 1
    assert len(m.asset_ids) == 3


def test_commit_more_reserves_than_available(supervisor):
    m = supervisor.create_mission("Clear BLDG-PF-01", "BLDG-PF-01",
                                  asset_ids=["CLAW1"],
                                  reserve_ids=["CLAW2"])
    result = supervisor.commit_reserves(m.id, count=5)
    assert len(result["committed"]) == 1  # only 1 available
    assert result["remaining_reserves"] == 0


# ═══════════════════════════════════════════════════════════
#  SQUAD SUPERVISOR — STATS / LIST
# ═══════════════════════════════════════════════════════════

def test_list_missions(supervisor):
    supervisor.create_mission("M1", "BLDG-PF-01", asset_ids=TEAM)
    supervisor.create_mission("M2", "BLDG-PF-01", asset_ids=TEAM)
    missions = supervisor.list_missions()
    assert len(missions) == 2


def test_get_stats(supervisor):
    supervisor.create_mission("M1", "BLDG-PF-01", asset_ids=TEAM)
    stats = supervisor.get_stats()
    assert stats["total_missions"] == 1
    assert stats["by_status"]["PENDING"] == 1


def test_mission_to_dict(supervisor):
    m = supervisor.create_mission("Clear BLDG-PF-01", "BLDG-PF-01",
                                  asset_ids=TEAM)
    d = m.to_dict()
    assert d["id"] == m.id
    assert d["status"] == "PENDING"
    assert d["objective"] == "Clear BLDG-PF-01"
    assert len(d["events"]) >= 1  # at least the created event


def test_objective_types_defined():
    assert "clear_building" in OBJECTIVE_TYPES
    assert "extract_hvt" in OBJECTIVE_TYPES


def test_mission_statuses_defined():
    assert "PENDING" in MISSION_STATUSES
    assert "COMPLETE" in MISSION_STATUSES
    assert "ABORTED" in MISSION_STATUSES


# ═══════════════════════════════════════════════════════════
#  API ENDPOINTS — PERCEPTION FUSION
# ═══════════════════════════════════════════════════════════

def test_api_perception_stats(auth_client):
    r = auth_client.get("/api/perception/stats")
    assert r.status_code == 200
    assert "total_tracks" in r.get_json()


def test_api_perception_detect(auth_client):
    r = auth_client.post("/api/perception/detect",
                         json={"building_id": "BLDG-01", "floor": 0,
                               "room_id": "R-001", "x_m": 5.0, "y_m": 3.0,
                               "classification": "hostile_armed",
                               "confidence": 0.8, "source_asset": "CLAW1"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert "track" in data


def test_api_perception_tracks(auth_client):
    # Ingest a detection first
    auth_client.post("/api/perception/detect",
                     json={"building_id": "BLDG-01", "floor": 0,
                           "room_id": "R-001", "x_m": 5.0, "y_m": 3.0,
                           "source_asset": "CLAW1"})
    r = auth_client.get("/api/perception/tracks")
    assert r.status_code == 200
    assert "tracks" in r.get_json()


def test_api_perception_slam(auth_client):
    r = auth_client.post("/api/perception/slam",
                         json={"building_id": "BLDG-01", "floor": 0,
                               "asset_id": "CLAW1",
                               "cells": [{"x_m": 1.0, "y_m": 1.0, "value": 1}]})
    assert r.status_code == 200


def test_api_perception_grids(auth_client):
    r = auth_client.get("/api/perception/grids")
    assert r.status_code == 200
    assert "grids" in r.get_json()


def test_api_perception_intel(auth_client):
    r = auth_client.post("/api/perception/intel",
                         json={"building_id": "BLDG-01", "room_id": "R-001",
                               "intel_type": "threat", "details": "IED near door"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"


# ═══════════════════════════════════════════════════════════
#  API ENDPOINTS — SQUAD SUPERVISOR
# ═══════════════════════════════════════════════════════════

def test_api_squad_stats(auth_client):
    r = auth_client.get("/api/squad/stats")
    assert r.status_code == 200
    assert "total_missions" in r.get_json()


def test_api_squad_missions(auth_client):
    r = auth_client.get("/api/squad/missions")
    assert r.status_code == 200
    assert "missions" in r.get_json()


def test_api_squad_create_mission(auth_client):
    r = auth_client.post("/api/squad/missions/create",
                         json={"objective": "Clear Building Alpha",
                               "building_id": "BLDG-01",
                               "asset_ids": ["CLAW1", "CLAW2"]})
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert data["mission"]["status"] == "PENDING"


def test_api_squad_create_mission_missing_fields(auth_client):
    r = auth_client.post("/api/squad/missions/create",
                         json={"objective": ""})
    assert r.status_code == 400
