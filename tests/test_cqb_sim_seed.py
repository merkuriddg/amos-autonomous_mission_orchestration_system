"""CQB Simulation Seed Tests.

Validates that seed_cqb_data correctly populates indoor positioning,
perception fusion (detections + SLAM), and demo missions.
"""

import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from services.cqb_sim_seed import seed_cqb_data, _INDOOR_SEEDS, _DETECTION_SEEDS, _SLAM_SEEDS, _generate_slam_cells
from services.perception_fusion import PerceptionFusion
from services.squad_supervisor import SquadSupervisor
from services.cqb_planner import CQBPlanner
from services.cqb_executor import CQBExecutor
from services.building_model import BuildingModel, BuildingManager
from services.indoor_positioning import IndoorPositioningService
from core.event_bus import EventBus


# ═══════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════

BRAVO_BUILDING = {
    "id": "BLD-BRAVO",
    "name": "Embassy Bravo",
    "location": {"lat": 35.70, "lng": 51.40, "alt_m": 1250},
    "dimensions": {"length_m": 28, "width_m": 18, "floors": 2},
    "walls": {"material": "concrete", "thickness_cm": 30},
    "entry_points": [{"id": "EP-01", "type": "door", "door_id": "D-G01"}],
    "threats_intel": {},
    "floors": [
        {
            "floor": 0, "name": "Ground",
            "rooms": [
                {"id": "R-G01", "name": "Lobby", "type": "corridor",
                 "bounds": {"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 8}},
                {"id": "R-G02", "name": "Office", "type": "office",
                 "bounds": {"x_min": 10, "y_min": 0, "x_max": 16, "y_max": 5}},
                {"id": "R-G04", "name": "Kitchen", "type": "office",
                 "bounds": {"x_min": 10, "y_min": 12, "x_max": 16, "y_max": 18}},
                {"id": "R-G06", "name": "Comms", "type": "office",
                 "bounds": {"x_min": 16, "y_min": 6, "x_max": 22, "y_max": 12}},
                {"id": "R-G07", "name": "Garage", "type": "storage",
                 "bounds": {"x_min": 16, "y_min": 12, "x_max": 22, "y_max": 18}},
                {"id": "R-G08", "name": "Motor Pool", "type": "storage",
                 "bounds": {"x_min": 22, "y_min": 0, "x_max": 28, "y_max": 8}},
                {"id": "R-G09", "name": "Court", "type": "corridor",
                 "bounds": {"x_min": 22, "y_min": 8, "x_max": 28, "y_max": 18}},
            ],
            "doors": [
                {"id": "D-G01", "from_room": "EXTERIOR", "to_room": "R-G01", "type": "standard"},
                {"id": "D-G02", "from_room": "R-G01", "to_room": "R-G02", "type": "standard"},
            ],
            "windows": [], "stairs": [],
        },
        {
            "floor": 1, "name": "Upper",
            "rooms": [
                {"id": "R-U03", "name": "SCIF", "type": "office",
                 "bounds": {"x_min": 10, "y_min": 0, "x_max": 18, "y_max": 6}},
            ],
            "doors": [], "windows": [], "stairs": [],
        },
    ],
}


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def building_mgr():
    mgr = BuildingManager()
    mgr.buildings["BLD-BRAVO"] = BuildingModel(copy.deepcopy(BRAVO_BUILDING))
    return mgr


@pytest.fixture
def indoor():
    return IndoorPositioningService()


@pytest.fixture
def perception(event_bus):
    return PerceptionFusion(event_bus=event_bus)


@pytest.fixture
def planner():
    return CQBPlanner()


@pytest.fixture
def executor(building_mgr, indoor, event_bus):
    return CQBExecutor(building_mgr=building_mgr,
                       indoor_positioning=indoor,
                       event_bus=event_bus)


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
#  seed_cqb_data — full integration
# ═══════════════════════════════════════════════════════════

def test_seed_returns_counts(indoor, perception, supervisor, building_mgr):
    """seed_cqb_data should return a dict with non-zero seeded counts."""
    result = seed_cqb_data(
        indoor_positioning=indoor,
        perception_fusion=perception,
        squad_supervisor=supervisor,
        building_mgr=building_mgr,
    )
    assert isinstance(result, dict)
    assert result["indoor_positions"] > 0
    assert result["detections"] > 0
    assert result["slam_scans"] > 0
    assert result["missions"] >= 0  # mission depends on building_mgr having BLD-BRAVO


def test_seed_populates_indoor_positions(indoor, perception, supervisor, building_mgr):
    """After seeding, indoor positions should be populated for Bravo."""
    seed_cqb_data(indoor_positioning=indoor, perception_fusion=perception,
                  squad_supervisor=supervisor, building_mgr=building_mgr)
    positions = indoor.get_all_positions()
    bravo_pos = [p for p in positions.values() if p.get("building_id") == "BLD-BRAVO"]
    assert len(bravo_pos) >= 2  # CLAW3 + PACK1 at minimum


def test_seed_populates_detections(indoor, perception, supervisor, building_mgr):
    """After seeding, perception fusion should have tracks."""
    seed_cqb_data(indoor_positioning=indoor, perception_fusion=perception,
                  squad_supervisor=supervisor, building_mgr=building_mgr)
    assert len(perception.detections) >= len(_DETECTION_SEEDS)
    assert len(perception.tracks) > 0


def test_seed_populates_slam(indoor, perception, supervisor, building_mgr):
    """SLAM scans should create occupancy grids."""
    seed_cqb_data(indoor_positioning=indoor, perception_fusion=perception,
                  squad_supervisor=supervisor, building_mgr=building_mgr)
    # At least one SLAM grid should exist
    stats = perception.get_stats()
    assert stats.get("grids", 0) > 0 or len(perception.grids) > 0


def test_seed_creates_demo_mission(indoor, perception, supervisor, building_mgr):
    """A demo mission should be created targeting Embassy Bravo."""
    result = seed_cqb_data(indoor_positioning=indoor, perception_fusion=perception,
                           squad_supervisor=supervisor, building_mgr=building_mgr)
    assert result["missions"] == 1
    assert len(supervisor.missions) >= 1


# ═══════════════════════════════════════════════════════════
#  seed_cqb_data — partial / graceful degradation
# ═══════════════════════════════════════════════════════════

def test_seed_with_no_services():
    """Passing None for all services should succeed with zero counts."""
    result = seed_cqb_data()
    assert result["indoor_positions"] == 0
    assert result["detections"] == 0
    assert result["slam_scans"] == 0
    assert result["missions"] == 0


def test_seed_indoor_only(indoor):
    """Only indoor positioning — should seed positions, nothing else."""
    result = seed_cqb_data(indoor_positioning=indoor)
    assert result["indoor_positions"] > 0
    assert result["detections"] == 0
    assert result["slam_scans"] == 0


def test_seed_perception_only(perception):
    """Only perception fusion — should seed detections + SLAM."""
    result = seed_cqb_data(perception_fusion=perception)
    assert result["indoor_positions"] == 0
    assert result["detections"] > 0
    assert result["slam_scans"] > 0


# ═══════════════════════════════════════════════════════════
#  _generate_slam_cells
# ═══════════════════════════════════════════════════════════

def test_generate_slam_cells_produces_output():
    """Cells should be generated within the given bounds."""
    cells = _generate_slam_cells(0, 0, 5, 5, density=1.0)
    assert len(cells) > 0
    for c in cells:
        assert 0 <= c["x_m"] <= 5
        assert 0 <= c["y_m"] <= 5
        assert c["value"] in (1, 2)  # FREE or OCCUPIED


def test_generate_slam_cells_zero_density():
    """Zero density should produce no cells."""
    cells = _generate_slam_cells(0, 0, 5, 5, density=0.0)
    assert len(cells) == 0


# ═══════════════════════════════════════════════════════════
#  Data constants sanity
# ═══════════════════════════════════════════════════════════

def test_indoor_seeds_have_required_keys():
    """All indoor seed entries must have required fields."""
    required = {"asset_id", "building_id", "floor", "room", "x_m", "y_m", "z_m", "source", "confidence"}
    for bld, positions in _INDOOR_SEEDS.items():
        for pos in positions:
            assert required.issubset(pos.keys()), f"Missing keys in {pos}"


def test_detection_seeds_have_required_keys():
    """All detection seeds must have required fields."""
    required = {"building_id", "floor", "room_id", "x_m", "y_m", "classification", "confidence", "source_asset"}
    for det in _DETECTION_SEEDS:
        assert required.issubset(det.keys()), f"Missing keys in {det}"


def test_slam_seeds_have_required_keys():
    """All SLAM seeds must have area tuple and asset_id."""
    for scan in _SLAM_SEEDS:
        assert "building_id" in scan
        assert "floor" in scan
        assert "asset_id" in scan
        assert len(scan["area"]) == 4
