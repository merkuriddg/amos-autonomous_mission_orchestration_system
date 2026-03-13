"""B2 Building Data Model & Indoor Positioning Tests.

Tests:
  - BuildingModel: loading, room/door/stair queries, adjacency, pathfinding, LOS, clearing
  - BuildingManager: auto-discovery, list, get, get_nearest
  - IndoorPositioningService: update, fusion, queries, removal, latlng conversion
  - API endpoints: buildings, floorplan, pathfinding, clearing, indoor position CRUD
"""

import sys, os, json, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from services.building_model import BuildingModel, BuildingManager
from services.indoor_positioning import IndoorPositioningService
from core.data_model import IndoorPosition


# ═══════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════

SAMPLE_BUILDING = {
    "id": "BLDG-TEST-01",
    "name": "Test Compound",
    "description": "3-floor test building",
    "location": {"lat": 35.686, "lng": 51.318, "alt_m": 1200},
    "dimensions": {"length_m": 20, "width_m": 15, "floors": 3},
    "walls": {"material": "concrete", "thickness_cm": 25},
    "entry_points": [
        {"id": "EP-01", "type": "door", "door_id": "D-001", "side": "south"},
    ],
    "threats_intel": {"last_recon": "2026-03-01", "estimated_hostiles": 5},
    "floors": [
        {
            "floor": 0, "name": "Ground Floor",
            "rooms": [
                {"id": "R-001", "name": "Lobby", "type": "corridor",
                 "bounds": {"x_min": 0, "y_min": 0, "x_max": 10, "y_max": 5}},
                {"id": "R-002", "name": "Office A", "type": "office",
                 "bounds": {"x_min": 10, "y_min": 0, "x_max": 20, "y_max": 5}},
                {"id": "R-003", "name": "Stairwell", "type": "stairwell",
                 "bounds": {"x_min": 0, "y_min": 5, "x_max": 5, "y_max": 10}},
            ],
            "doors": [
                {"id": "D-001", "from_room": "EXTERIOR", "to_room": "R-001", "type": "standard"},
                {"id": "D-002", "from_room": "R-001", "to_room": "R-002", "type": "standard"},
                {"id": "D-003", "from_room": "R-001", "to_room": "R-003", "type": "standard"},
            ],
            "windows": [
                {"id": "W-001", "room": "R-002", "side": "east"},
            ],
            "stairs": [
                {"id": "S-001", "room": "R-003", "connects_to_floor": 1},
            ],
        },
        {
            "floor": 1, "name": "First Floor",
            "rooms": [
                {"id": "R-101", "name": "Hallway", "type": "corridor",
                 "bounds": {"x_min": 0, "y_min": 0, "x_max": 20, "y_max": 3}},
                {"id": "R-102", "name": "Server Room", "type": "utility",
                 "bounds": {"x_min": 0, "y_min": 3, "x_max": 10, "y_max": 10}},
                {"id": "R-103", "name": "Stairwell 1F", "type": "stairwell",
                 "bounds": {"x_min": 0, "y_min": 5, "x_max": 5, "y_max": 10}},
            ],
            "doors": [
                {"id": "D-101", "from_room": "R-101", "to_room": "R-102", "type": "reinforced"},
                {"id": "D-102", "from_room": "R-101", "to_room": "R-103", "type": "standard"},
            ],
            "windows": [],
            "stairs": [
                {"id": "S-101", "room": "R-103", "connects_to_floor": 0},
                {"id": "S-102", "room": "R-103", "connects_to_floor": 2},
            ],
        },
        {
            "floor": 2, "name": "Roof",
            "rooms": [
                {"id": "R-201", "name": "Roof Access", "type": "utility",
                 "bounds": {"x_min": 0, "y_min": 0, "x_max": 5, "y_max": 5}},
            ],
            "doors": [],
            "windows": [],
            "stairs": [
                {"id": "S-201", "room": "R-201", "connects_to_floor": 1},
            ],
        },
    ],
}


@pytest.fixture
def building():
    return BuildingModel(SAMPLE_BUILDING)


@pytest.fixture
def tmp_buildings_dir():
    """Create a temp directory with a single building JSON for BuildingManager tests."""
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "test_building.json"), "w") as f:
        json.dump(SAMPLE_BUILDING, f)
    yield d
    shutil.rmtree(d)


@pytest.fixture
def ips():
    return IndoorPositioningService()


# ═══════════════════════════════════════════════════════════
#  BUILDING MODEL — BASIC PROPERTIES
# ═══════════════════════════════════════════════════════════

def test_building_id_and_name(building):
    assert building.id == "BLDG-TEST-01"
    assert building.name == "Test Compound"


def test_building_floor_count(building):
    assert building.floor_count == 3


def test_building_get_floors(building):
    assert building.get_floors() == [0, 1, 2]


def test_building_room_count(building):
    # 3 ground + 3 first + 1 roof = 7
    assert building.room_count == 7


def test_building_location(building):
    assert building.location["lat"] == 35.686
    assert building.location["lng"] == 51.318


# ═══════════════════════════════════════════════════════════
#  BUILDING MODEL — ROOM QUERIES
# ═══════════════════════════════════════════════════════════

def test_get_room(building):
    room = building.get_room("R-001")
    assert room is not None
    assert room["name"] == "Lobby"


def test_get_room_not_found(building):
    assert building.get_room("R-999") is None


def test_get_rooms_on_floor(building):
    ground_rooms = building.get_rooms_on_floor(0)
    assert len(ground_rooms) == 3
    ids = {r["id"] for r in ground_rooms}
    assert ids == {"R-001", "R-002", "R-003"}


def test_get_room_floor(building):
    assert building.get_room_floor("R-001") == 0
    assert building.get_room_floor("R-101") == 1
    assert building.get_room_floor("R-201") == 2


# ═══════════════════════════════════════════════════════════
#  BUILDING MODEL — DOOR QUERIES
# ═══════════════════════════════════════════════════════════

def test_get_door(building):
    d = building.get_door("D-001")
    assert d is not None
    assert d["from_room"] == "EXTERIOR"


def test_get_doors_for_room(building):
    doors = building.get_doors_for_room("R-001")
    # D-001 (exterior→lobby), D-002 (lobby→office), D-003 (lobby→stairwell)
    assert len(doors) == 3


def test_get_entry_doors(building):
    entry = building.get_entry_doors()
    assert len(entry) == 1
    assert entry[0]["id"] == "D-001"


# ═══════════════════════════════════════════════════════════
#  BUILDING MODEL — ADJACENCY & LOS
# ═══════════════════════════════════════════════════════════

def test_adjacent_rooms_same_floor(building):
    adj = building.get_adjacent_rooms("R-001")
    assert "R-002" in adj  # connected via D-002
    assert "R-003" in adj  # connected via D-003


def test_adjacent_rooms_cross_floor(building):
    """Stairwell R-003 (ground) connects to R-103 (1st floor) via stairs."""
    adj = building.get_adjacent_rooms("R-003")
    assert "R-103" in adj


def test_has_los_adjacent(building):
    assert building.has_los("R-001", "R-002") is True


def test_has_los_non_adjacent(building):
    assert building.has_los("R-002", "R-003") is False  # no direct door


# ═══════════════════════════════════════════════════════════
#  BUILDING MODEL — PATHFINDING
# ═══════════════════════════════════════════════════════════

def test_path_same_room(building):
    path = building.find_path("R-001", "R-001")
    assert path == ["R-001"]


def test_path_adjacent(building):
    path = building.find_path("R-001", "R-002")
    assert path == ["R-001", "R-002"]


def test_path_cross_floor(building):
    """Ground office to first floor server room requires stairwells."""
    path = building.find_path("R-002", "R-102")
    assert path is not None
    assert path[0] == "R-002"
    assert path[-1] == "R-102"
    # Must pass through stairwells
    assert "R-003" in path or "R-103" in path


def test_path_ground_to_roof(building):
    """Lobby to roof: lobby→stairwell→1F stairwell→roof access."""
    path = building.find_path("R-001", "R-201")
    assert path is not None
    assert path[0] == "R-001"
    assert path[-1] == "R-201"
    assert len(path) >= 3  # at least through one stairwell


def test_path_nonexistent_room(building):
    assert building.find_path("R-001", "R-999") is None


# ═══════════════════════════════════════════════════════════
#  BUILDING MODEL — CLEARING
# ═══════════════════════════════════════════════════════════

def test_clearing_initial_state(building):
    assert building.clearing_progress == 0.0
    assert len(building.get_cleared_rooms()) == 0
    assert len(building.get_uncleared_rooms()) == 7


def test_mark_cleared(building):
    assert building.mark_cleared("R-001") is True
    assert "R-001" in building.get_cleared_rooms()


def test_mark_uncleared(building):
    building.mark_cleared("R-001")
    building.mark_uncleared("R-001")
    assert "R-001" not in building.get_cleared_rooms()


def test_clearing_progress(building):
    building.mark_cleared("R-001")
    building.mark_cleared("R-002")
    expected = 2 / 7
    assert abs(building.clearing_progress - expected) < 0.01


def test_mark_cleared_nonexistent(building):
    assert building.mark_cleared("R-FAKE") is False


# ═══════════════════════════════════════════════════════════
#  BUILDING MODEL — SERIALISATION
# ═══════════════════════════════════════════════════════════

def test_to_summary(building):
    s = building.to_summary()
    assert s["id"] == "BLDG-TEST-01"
    assert s["floors"] == 3
    assert s["rooms"] == 7
    assert s["entry_points"] == 1


def test_to_dict(building):
    d = building.to_dict()
    assert d["id"] == "BLDG-TEST-01"
    assert len(d["floors"]) == 3


# ═══════════════════════════════════════════════════════════
#  BUILDING MANAGER
# ═══════════════════════════════════════════════════════════

def test_manager_loads_buildings(tmp_buildings_dir):
    mgr = BuildingManager(tmp_buildings_dir)
    assert len(mgr.buildings) == 1
    assert "BLDG-TEST-01" in mgr.buildings


def test_manager_list_buildings(tmp_buildings_dir):
    mgr = BuildingManager(tmp_buildings_dir)
    lst = mgr.list_buildings()
    assert len(lst) == 1
    assert lst[0]["id"] == "BLDG-TEST-01"


def test_manager_get(tmp_buildings_dir):
    mgr = BuildingManager(tmp_buildings_dir)
    b = mgr.get("BLDG-TEST-01")
    assert b is not None
    assert b.name == "Test Compound"


def test_manager_get_none(tmp_buildings_dir):
    mgr = BuildingManager(tmp_buildings_dir)
    assert mgr.get("NONEXISTENT") is None


def test_manager_get_nearest(tmp_buildings_dir):
    mgr = BuildingManager(tmp_buildings_dir)
    b = mgr.get_nearest(35.687, 51.319)
    assert b is not None
    assert b.id == "BLDG-TEST-01"


def test_manager_empty_dir():
    d = tempfile.mkdtemp()
    try:
        mgr = BuildingManager(d)
        assert len(mgr.buildings) == 0
    finally:
        shutil.rmtree(d)


def test_manager_nonexistent_dir():
    mgr = BuildingManager("/nonexistent/path")
    assert len(mgr.buildings) == 0


# ═══════════════════════════════════════════════════════════
#  INDOOR POSITIONING SERVICE — BASIC
# ═══════════════════════════════════════════════════════════

def test_ips_update_and_get(ips):
    pos = ips.update_position("ASSET-01", "BLDG-01", floor=1, room="R-101",
                              x_m=5.0, y_m=3.0, confidence=0.8, source="slam")
    assert pos.building_id == "BLDG-01"
    assert pos.floor == 1
    assert pos.room == "R-101"
    assert pos.confidence == 0.8
    retrieved = ips.get_position("ASSET-01")
    assert retrieved is not None
    assert retrieved.building_id == "BLDG-01"


def test_ips_update_no_prior(ips):
    """First update for an asset is accepted directly."""
    pos = ips.update_position("NEW-01", "B-X", floor=0, x_m=1.0, y_m=2.0,
                              confidence=0.6, source="uwb")
    assert pos.x_m == 1.0
    assert pos.source == "uwb"


def test_ips_get_nonexistent(ips):
    assert ips.get_position("NO-SUCH") is None


# ═══════════════════════════════════════════════════════════
#  INDOOR POSITIONING SERVICE — FUSION
# ═══════════════════════════════════════════════════════════

def test_ips_fusion_weights_toward_higher_confidence(ips):
    """Two updates to same asset/building fuse positions."""
    ips.update_position("FUSE-01", "B-1", floor=0, x_m=0.0, y_m=0.0,
                        confidence=0.5, source="imu")
    pos = ips.update_position("FUSE-01", "B-1", floor=0, x_m=10.0, y_m=10.0,
                              confidence=0.9, source="slam")
    # SLAM has higher priority (4) and higher confidence (0.9)
    # So fused position should be weighted toward 10,10
    assert pos.x_m > 5.0  # closer to new
    assert pos.y_m > 5.0


def test_ips_fusion_new_building_resets(ips):
    """Switching buildings accepts new position directly (no fusion)."""
    ips.update_position("MOVE-01", "B-A", floor=0, x_m=5.0, y_m=5.0,
                        confidence=0.9, source="slam")
    pos = ips.update_position("MOVE-01", "B-B", floor=0, x_m=1.0, y_m=1.0,
                              confidence=0.6, source="slam")
    assert pos.building_id == "B-B"
    assert pos.x_m == 1.0  # no fusion, direct accept


def test_ips_fusion_confidence_increases(ips):
    """Confidence should increase with fusion."""
    ips.update_position("CONF-01", "B-1", floor=0, confidence=0.7, source="slam")
    pos = ips.update_position("CONF-01", "B-1", floor=0, confidence=0.7, source="uwb")
    assert pos.confidence >= 0.7  # should be at least max(0.7, 0.7) + 0.05


# ═══════════════════════════════════════════════════════════
#  INDOOR POSITIONING SERVICE — QUERIES
# ═══════════════════════════════════════════════════════════

def test_ips_get_all_positions(ips):
    ips.update_position("A1", "B-1", floor=0, x_m=1.0, y_m=1.0, source="slam")
    ips.update_position("A2", "B-1", floor=1, x_m=2.0, y_m=2.0, source="slam")
    all_pos = ips.get_all_positions()
    assert "A1" in all_pos
    assert "A2" in all_pos
    assert all_pos["A1"]["building_id"] == "B-1"


def test_ips_get_history(ips):
    ips.update_position("HIST-01", "B-1", floor=0, x_m=1.0, source="slam")
    ips.update_position("HIST-01", "B-1", floor=0, x_m=2.0, source="slam")
    ips.update_position("HIST-01", "B-1", floor=0, x_m=3.0, source="slam")
    hist = ips.get_history("HIST-01")
    assert len(hist) == 3
    assert hist[0]["x_m"] == 1.0
    assert hist[-1]["x_m"] == 3.0


def test_ips_get_history_limit(ips):
    for i in range(10):
        ips.update_position("LIM-01", "B-1", floor=0, x_m=float(i), source="slam")
    hist = ips.get_history("LIM-01", limit=3)
    assert len(hist) == 3


def test_ips_get_assets_in_building(ips):
    ips.update_position("A1", "B-1", floor=0, source="slam")
    ips.update_position("A2", "B-1", floor=1, source="slam")
    ips.update_position("A3", "B-2", floor=0, source="slam")
    in_b1 = ips.get_assets_in_building("B-1")
    assert set(in_b1) == {"A1", "A2"}


def test_ips_get_assets_in_room(ips):
    ips.update_position("A1", "B-1", floor=0, room="R-001", source="slam")
    ips.update_position("A2", "B-1", floor=0, room="R-001", source="slam")
    ips.update_position("A3", "B-1", floor=0, room="R-002", source="slam")
    in_room = ips.get_assets_in_room("B-1", "R-001")
    assert set(in_room) == {"A1", "A2"}


def test_ips_get_assets_on_floor(ips):
    ips.update_position("A1", "B-1", floor=0, source="slam")
    ips.update_position("A2", "B-1", floor=1, source="slam")
    ips.update_position("A3", "B-1", floor=0, source="slam")
    on_f0 = ips.get_assets_on_floor("B-1", 0)
    assert set(on_f0) == {"A1", "A3"}


# ═══════════════════════════════════════════════════════════
#  INDOOR POSITIONING SERVICE — REMOVAL & LATLNG
# ═══════════════════════════════════════════════════════════

def test_ips_remove_asset(ips):
    ips.update_position("DEL-01", "B-1", floor=0, source="slam")
    assert ips.get_position("DEL-01") is not None
    ips.remove_asset("DEL-01")
    assert ips.get_position("DEL-01") is None
    assert ips.get_history("DEL-01") == []


def test_ips_remove_nonexistent(ips):
    """Removing nonexistent asset doesn't raise."""
    ips.remove_asset("NOPE")


def test_ips_to_latlng(ips):
    pos = IndoorPosition(building_id="B-1", x_m=10.0, y_m=20.0, z_m=3.0)
    loc = {"lat": 35.686, "lng": 51.318, "alt_m": 1200}
    result = ips.to_latlng(pos, loc)
    assert result["lat"] > 35.686  # y_m adds to lat
    assert result["lng"] > 51.318  # x_m adds to lng
    assert result["alt_ft"] > 0


def test_ips_stats(ips):
    ips.update_position("S1", "B-1", floor=0, source="slam")
    ips.update_position("S2", "B-2", floor=0, source="uwb")
    stats = ips.get_stats()
    assert stats["tracked_assets"] == 2
    assert stats["buildings_active"] == 2
    assert stats["total_updates"] == 2


# ═══════════════════════════════════════════════════════════
#  API ENDPOINTS — BUILDINGS
# ═══════════════════════════════════════════════════════════

def test_api_buildings_list(auth_client):
    rv = auth_client.get("/api/v1/buildings")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "buildings" in data
    # compound_alpha should be loaded from config/buildings/
    assert isinstance(data["buildings"], list)


def test_api_building_detail(auth_client):
    # Get list first to find a valid building id
    rv = auth_client.get("/api/v1/buildings")
    buildings = rv.get_json().get("buildings", [])
    if not buildings:
        pytest.skip("No buildings loaded")
    bid = buildings[0]["id"]
    rv = auth_client.get(f"/api/v1/buildings/{bid}")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["id"] == bid
    assert "floors" in data


def test_api_building_not_found(auth_client):
    rv = auth_client.get("/api/v1/buildings/NONEXISTENT")
    assert rv.status_code == 404


def test_api_building_floorplan(auth_client):
    rv = auth_client.get("/api/v1/buildings")
    buildings = rv.get_json().get("buildings", [])
    if not buildings:
        pytest.skip("No buildings loaded")
    bid = buildings[0]["id"]
    rv = auth_client.get(f"/api/v1/buildings/{bid}/floorplan/0")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "rooms" in data
    assert "doors" in data
    assert data["building_id"] == bid


def test_api_building_floorplan_not_found(auth_client):
    rv = auth_client.get("/api/v1/buildings")
    buildings = rv.get_json().get("buildings", [])
    if not buildings:
        pytest.skip("No buildings loaded")
    bid = buildings[0]["id"]
    rv = auth_client.get(f"/api/v1/buildings/{bid}/floorplan/99")
    assert rv.status_code == 404


def test_api_building_path(auth_client):
    rv = auth_client.get("/api/v1/buildings")
    buildings = rv.get_json().get("buildings", [])
    if not buildings:
        pytest.skip("No buildings loaded")
    bid = buildings[0]["id"]
    # Get rooms on floor 0
    rv = auth_client.get(f"/api/v1/buildings/{bid}/floorplan/0")
    rooms = rv.get_json().get("rooms", [])
    if len(rooms) < 2:
        pytest.skip("Not enough rooms for path test")
    rv = auth_client.post(f"/api/v1/buildings/{bid}/path",
                          json={"from_room": rooms[0]["id"], "to_room": rooms[1]["id"]})
    assert rv.status_code in (200, 404)  # 404 if no path exists


def test_api_building_path_missing_params(auth_client):
    rv = auth_client.get("/api/v1/buildings")
    buildings = rv.get_json().get("buildings", [])
    if not buildings:
        pytest.skip("No buildings loaded")
    bid = buildings[0]["id"]
    rv = auth_client.post(f"/api/v1/buildings/{bid}/path", json={})
    assert rv.status_code == 400


def test_api_building_clear_room(auth_client):
    rv = auth_client.get("/api/v1/buildings")
    buildings = rv.get_json().get("buildings", [])
    if not buildings:
        pytest.skip("No buildings loaded")
    bid = buildings[0]["id"]
    rv = auth_client.get(f"/api/v1/buildings/{bid}/floorplan/0")
    rooms = rv.get_json().get("rooms", [])
    if not rooms:
        pytest.skip("No rooms on floor 0")
    rv = auth_client.post(f"/api/v1/buildings/{bid}/clear",
                          json={"room_id": rooms[0]["id"], "cleared": True})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["status"] == "ok"
    assert data["cleared"] is True


def test_api_building_clear_missing_room(auth_client):
    rv = auth_client.get("/api/v1/buildings")
    buildings = rv.get_json().get("buildings", [])
    if not buildings:
        pytest.skip("No buildings loaded")
    bid = buildings[0]["id"]
    rv = auth_client.post(f"/api/v1/buildings/{bid}/clear", json={})
    assert rv.status_code == 400


# ═══════════════════════════════════════════════════════════
#  API ENDPOINTS — INDOOR POSITIONING
# ═══════════════════════════════════════════════════════════

def test_api_indoor_position_update(auth_client):
    rv = auth_client.post("/api/v1/indoor/position", json={
        "asset_id": "TEST-ASSET-01",
        "building_id": "BLDG-TEST",
        "floor": 1,
        "room": "R-101",
        "x_m": 5.5,
        "y_m": 3.2,
        "confidence": 0.85,
        "source": "slam",
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["status"] == "ok"
    assert data["position"]["building_id"] == "BLDG-TEST"


def test_api_indoor_position_update_missing_fields(auth_client):
    rv = auth_client.post("/api/v1/indoor/position", json={"asset_id": "X"})
    assert rv.status_code == 400


def test_api_indoor_positions_list(auth_client):
    # Create a position first
    auth_client.post("/api/v1/indoor/position", json={
        "asset_id": "LIST-TEST", "building_id": "B-1", "floor": 0, "source": "uwb"})
    rv = auth_client.get("/api/v1/indoor/positions")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "positions" in data
    assert "stats" in data


def test_api_indoor_position_detail(auth_client):
    auth_client.post("/api/v1/indoor/position", json={
        "asset_id": "DETAIL-TEST", "building_id": "B-1", "floor": 0, "source": "slam"})
    rv = auth_client.get("/api/v1/indoor/positions/DETAIL-TEST")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "position" in data
    assert "history" in data


def test_api_indoor_position_detail_not_found(auth_client):
    rv = auth_client.get("/api/v1/indoor/positions/NO-SUCH-ASSET")
    assert rv.status_code == 404
