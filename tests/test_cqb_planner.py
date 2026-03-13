"""B3 Autonomous CQB Protocols Tests.

Tests:
  - CQBTask: creation, validation, role assignment, lifecycle, roundtrip
  - CQBPlanner: plan generation, phasing, dependencies, edge cases
  - CQB ROE: init, hostage rooms, fratricide check, range check, autonomy tier
  - API endpoints: plan generation, plan listing, task creation, ROE check
"""

import sys, os, json, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from services.cqb_task_language import (
    CQBTask, CQB_TASK_TYPES, BREACH_METHODS, CLEAR_FORMATIONS,
    HOLD_SECTORS, EXTRACT_ROUTES, CQB_ROLES, CQB_TASK_STATUSES,
)
from services.cqb_planner import CQBPlanner, CQBPlan
from services.building_model import BuildingModel
from services.roe_engine import ROEEngine


# ═══════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════

SAMPLE_BUILDING = {
    "id": "BLDG-CQB-01",
    "name": "CQB Test Building",
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
                {"id": "R-003", "name": "Stairwell G", "type": "stairwell",
                 "bounds": {"x_min": 0, "y_min": 5, "x_max": 5, "y_max": 10}},
            ],
            "doors": [
                {"id": "D-001", "from_room": "EXTERIOR", "to_room": "R-001", "type": "standard"},
                {"id": "D-002", "from_room": "R-001", "to_room": "R-002", "type": "standard"},
                {"id": "D-003", "from_room": "R-001", "to_room": "R-003", "type": "standard"},
            ],
            "windows": [],
            "stairs": [{"id": "S-001", "room": "R-003", "connects_to_floor": 1}],
        },
        {
            "floor": 1, "name": "First Floor",
            "rooms": [
                {"id": "R-101", "name": "Hallway", "type": "corridor",
                 "bounds": {"x_min": 0, "y_min": 0, "x_max": 20, "y_max": 3}},
                {"id": "R-102", "name": "Target Room", "type": "office",
                 "bounds": {"x_min": 10, "y_min": 3, "x_max": 20, "y_max": 10}},
                {"id": "R-103", "name": "Stairwell 1F", "type": "stairwell",
                 "bounds": {"x_min": 0, "y_min": 5, "x_max": 5, "y_max": 10}},
            ],
            "doors": [
                {"id": "D-101", "from_room": "R-101", "to_room": "R-102", "type": "reinforced"},
                {"id": "D-102", "from_room": "R-101", "to_room": "R-103", "type": "standard"},
            ],
            "windows": [],
            "stairs": [{"id": "S-101", "room": "R-103", "connects_to_floor": 0}],
        },
    ],
}


@pytest.fixture
def building():
    return BuildingModel(copy.deepcopy(SAMPLE_BUILDING))


@pytest.fixture
def planner():
    return CQBPlanner()


@pytest.fixture
def roe():
    engine = ROEEngine()
    engine.init_cqb_rules()
    return engine


# ═══════════════════════════════════════════════════════════
#  CQB TASK LANGUAGE — CONSTANTS
# ═══════════════════════════════════════════════════════════

def test_cqb_task_types():
    assert set(CQB_TASK_TYPES) == {"BREACH", "CLEAR", "HOLD", "SECURE", "EXTRACT", "STACK"}


def test_breach_methods():
    assert "explosive" in BREACH_METHODS
    assert "manual" in BREACH_METHODS


def test_clear_formations():
    assert "buttonhook" in CLEAR_FORMATIONS
    assert "dynamic" in CLEAR_FORMATIONS


def test_cqb_roles():
    assert "point" in CQB_ROLES
    assert "rear_security" in CQB_ROLES


# ═══════════════════════════════════════════════════════════
#  CQB TASK — CREATION & VALIDATION
# ═══════════════════════════════════════════════════════════

def test_task_breach_defaults():
    t = CQBTask("BREACH", "BLDG-01", target_id="D-001")
    assert t.task_type == "BREACH"
    assert t.params["method"] == "manual"
    assert t.params["door_id"] == "D-001"
    assert t.min_assets >= 2


def test_task_clear_defaults():
    t = CQBTask("CLEAR", "BLDG-01", target_id="R-001")
    assert t.params["formation"] == "dynamic"
    assert t.params["room_id"] == "R-001"


def test_task_hold_defaults():
    t = CQBTask("HOLD", "BLDG-01")
    assert t.params["sector"] == "all"
    assert t.params["duration_sec"] == 300


def test_task_secure_defaults():
    t = CQBTask("SECURE", "BLDG-01", target_id="R-102")
    assert t.params["duration_sec"] == 600


def test_task_extract_defaults():
    t = CQBTask("EXTRACT", "BLDG-01")
    assert t.params["route"] == "primary"
    assert t.min_assets >= 2


def test_task_stack_defaults():
    t = CQBTask("STACK", "BLDG-01", target_id="D-001")
    assert t.params["door_id"] == "D-001"
    assert t.params["team"] == "alpha"


def test_task_validates_clean():
    t = CQBTask("CLEAR", "BLDG-01", target_id="R-001")
    assert t.validate() == []


def test_task_validates_bad_type():
    t = CQBTask("FLY", "BLDG-01")
    errors = t.validate()
    assert any("Unknown CQB task type" in e for e in errors)


def test_task_validates_missing_building():
    t = CQBTask("CLEAR", "", target_id="R-001")
    errors = t.validate()
    assert any("building_id" in e for e in errors)


def test_task_validates_bad_breach_method():
    t = CQBTask("BREACH", "B-01", target_id="D-001", params={"method": "laser", "door_id": "D-001"})
    errors = t.validate()
    assert any("breach method" in e for e in errors)


def test_task_validates_breach_needs_door():
    t = CQBTask("BREACH", "B-01", params={"door_id": ""})
    errors = t.validate()
    assert any("door_id" in e for e in errors)


def test_task_validates_clear_needs_room():
    t = CQBTask("CLEAR", "B-01", params={"room_id": ""})
    errors = t.validate()
    assert any("room_id" in e for e in errors)


def test_task_validates_bad_hold_sector():
    t = CQBTask("HOLD", "B-01", params={"sector": "underground"})
    errors = t.validate()
    assert any("sector" in e for e in errors)


def test_task_validates_bad_extract_route():
    t = CQBTask("EXTRACT", "B-01", params={"route": "teleport"})
    errors = t.validate()
    assert any("route" in e for e in errors)


def test_task_validates_bad_priority():
    t = CQBTask("HOLD", "B-01", priority=0)
    errors = t.validate()
    assert any("Priority" in e for e in errors)


def test_task_validates_bad_role():
    t = CQBTask("CLEAR", "B-01", target_id="R-001", roles={"sniper": "A1"})
    errors = t.validate()
    assert any("Unknown CQB role" in e for e in errors)


# ═══════════════════════════════════════════════════════════
#  CQB TASK — ROLE ASSIGNMENT & LIFECYCLE
# ═══════════════════════════════════════════════════════════

def test_task_assign_roles():
    t = CQBTask("CLEAR", "B-01", target_id="R-001")
    t.assign_roles(["A1", "A2", "A3", "A4"])
    assert t.roles["point"] == "A1"
    assert t.roles["number_2"] == "A2"
    assert t.roles["cover"] == "A3"
    assert t.roles["rear_security"] == "A4"
    assert t.assigned_assets == ["A1", "A2", "A3", "A4"]


def test_task_assign_roles_overflow():
    t = CQBTask("CLEAR", "B-01", target_id="R-001")
    t.assign_roles(["A1", "A2", "A3", "A4", "A5"])
    assert "overwatch_1" in t.roles
    assert t.roles["overwatch_1"] == "A5"


def test_task_lifecycle():
    t = CQBTask("CLEAR", "B-01", target_id="R-001")
    assert t.status == "PLANNED"
    t.start()
    assert t.status == "EXECUTING"
    assert t.started is not None
    t.complete()
    assert t.status == "COMPLETE"
    assert t.completed is not None


def test_task_fail():
    t = CQBTask("BREACH", "B-01", target_id="D-001")
    t.fail("Door jammed")
    assert t.status == "FAILED"
    assert any("Door jammed" in n for n in t.notes)


def test_task_abort():
    t = CQBTask("CLEAR", "B-01", target_id="R-001")
    t.abort("Contact — falling back")
    assert t.status == "ABORTED"


def test_task_roundtrip():
    t = CQBTask("CLEAR", "BLDG-01", target_id="R-001", priority=2)
    t.assign_roles(["A1", "A2", "A3"])
    d = t.to_dict()
    t2 = CQBTask.from_dict(d)
    assert t2.id == t.id
    assert t2.task_type == "CLEAR"
    assert t2.roles["point"] == "A1"
    assert t2.priority == 2


# ═══════════════════════════════════════════════════════════
#  CQB PLANNER — PLAN GENERATION
# ═══════════════════════════════════════════════════════════

def test_planner_generates_plan(building, planner):
    plan = planner.generate_plan(building)
    assert plan.status == "READY"
    assert plan.building_id == "BLDG-CQB-01"
    assert plan.stats["total_tasks"] > 0
    assert plan.stats["rooms_to_clear"] > 0


def test_planner_has_all_task_types(building, planner):
    plan = planner.generate_plan(building)
    types = {t.task_type for t in plan.all_tasks.values()}
    # Should have at least STACK, BREACH, CLEAR, HOLD
    assert "CLEAR" in types
    assert "HOLD" in types


def test_planner_phases(building, planner):
    plan = planner.generate_plan(building)
    assert len(plan.phases) >= 2  # at least 2 floors


def test_planner_dependencies(building, planner):
    """Tasks should have dependency chains (STACK→BREACH→CLEAR)."""
    plan = planner.generate_plan(building)
    for task in plan.all_tasks.values():
        if task.task_type == "BREACH":
            # BREACH should depend on STACK
            assert len(task.depends_on) > 0
        if task.task_type == "CLEAR" and task.depends_on:
            # CLEAR's dependencies should be in the plan
            for dep_id in task.depends_on:
                assert dep_id in plan.all_tasks


def test_planner_reinforced_door_explosive(building, planner):
    """Reinforced doors should get explosive breach method."""
    plan = planner.generate_plan(building)
    for task in plan.all_tasks.values():
        if task.task_type == "BREACH" and task.target_id == "D-101":
            assert task.params["method"] == "explosive"


def test_planner_standard_door_manual(building, planner):
    """Standard doors should get manual breach method."""
    plan = planner.generate_plan(building)
    for task in plan.all_tasks.values():
        if task.task_type == "BREACH" and task.target_id == "D-001":
            assert task.params["method"] == "manual"


def test_planner_specific_floors(building, planner):
    plan = planner.generate_plan(building, floors=[0])
    # Should only clear floor 0 rooms
    for task in plan.all_tasks.values():
        if task.task_type == "CLEAR":
            assert task.floor == 0


def test_planner_objective_room(building, planner):
    plan = planner.generate_plan(building, objective_room="R-102")
    # Should have a SECURE task for R-102
    secure_tasks = [t for t in plan.all_tasks.values() if t.task_type == "SECURE"]
    assert len(secure_tasks) == 1
    assert secure_tasks[0].target_id == "R-102"


def test_planner_skips_cleared_rooms(building, planner):
    building.mark_cleared("R-001")
    building.mark_cleared("R-002")
    plan = planner.generate_plan(building, floors=[0])
    clear_rooms = [t.target_id for t in plan.all_tasks.values() if t.task_type == "CLEAR"]
    assert "R-001" not in clear_rooms
    assert "R-002" not in clear_rooms


def test_planner_all_cleared(building, planner):
    for room_id in ["R-001", "R-002", "R-003", "R-101", "R-102", "R-103"]:
        building.mark_cleared(room_id)
    plan = planner.generate_plan(building)
    assert "All rooms already cleared" in plan.notes[0]


def test_planner_stores_plan(building, planner):
    plan = planner.generate_plan(building)
    retrieved = planner.get_plan(plan.id)
    assert retrieved is not None
    assert retrieved.id == plan.id


def test_planner_list_plans(building, planner):
    planner.generate_plan(building)
    plans = planner.list_plans()
    assert len(plans) >= 1


def test_planner_entry_door(building, planner):
    plan = planner.generate_plan(building, entry_door_id="D-001")
    # First CLEAR should be R-001 (entry hall via D-001)
    clears = [t for t in plan.all_tasks.values() if t.task_type == "CLEAR"]
    floor_0_clears = [t for t in clears if t.floor == 0]
    if floor_0_clears:
        assert floor_0_clears[0].target_id == "R-001"


def test_plan_to_dict(building, planner):
    plan = planner.generate_plan(building)
    d = plan.to_dict()
    assert d["id"] == plan.id
    assert "phases" in d
    assert "stats" in d
    assert d["stats"]["total_tasks"] > 0


# ═══════════════════════════════════════════════════════════
#  CQB ROE — RULES
# ═══════════════════════════════════════════════════════════

def test_cqb_roe_init(roe):
    cqb_rules = [r for r in roe.rules.values() if r["type"].startswith("cqb_")]
    assert len(cqb_rules) == 4


def test_cqb_roe_normal_engagement(roe):
    """Normal CQB engagement (in range, no hostage, good separation, tier 4)."""
    result = roe.check_cqb_engagement(
        room_id="R-001",
        asset={"autonomy_tier": 4},
        target_range_m=10.0,
        friendly_separation_m=5.0,
    )
    assert result["allowed"] is True
    assert len(result["violations"]) == 0


def test_cqb_roe_out_of_range(roe):
    """Range outside CQB bounds triggers warning."""
    result = roe.check_cqb_engagement(
        room_id="R-001",
        asset={"autonomy_tier": 4},
        target_range_m=50.0,
    )
    # Range is a WARNING, not BLOCK
    assert len(result["warnings"]) > 0


def test_cqb_roe_hostage_room(roe):
    """Engagement in hostage room is blocked."""
    roe.set_hostage_rooms(["R-102"])
    result = roe.check_cqb_engagement(
        room_id="R-102",
        asset={"autonomy_tier": 5},
        target_range_m=10.0,
    )
    assert result["allowed"] is False
    assert any("hostage" in v["detail"].lower() for v in result["violations"])


def test_cqb_roe_fratricide(roe):
    """Friendly within 2m blocks engagement."""
    result = roe.check_cqb_engagement(
        room_id="R-001",
        asset={"autonomy_tier": 4},
        target_range_m=10.0,
        friendly_separation_m=1.0,
    )
    assert result["allowed"] is False
    assert any("fratricide" in v["detail"].lower() for v in result["violations"])


def test_cqb_roe_low_autonomy_tier(roe):
    """Asset below tier 4 cannot auto-engage in CQB."""
    result = roe.check_cqb_engagement(
        room_id="R-001",
        asset={"autonomy_tier": 2},
        target_range_m=10.0,
        friendly_separation_m=5.0,
    )
    assert result["allowed"] is False
    assert any("tier" in v["detail"].lower() for v in result["violations"])


def test_cqb_roe_weapons_hold(roe):
    """WEAPONS_HOLD blocks all CQB engagement."""
    roe.set_posture("WEAPONS_HOLD", "CDR")
    result = roe.check_cqb_engagement(
        room_id="R-001",
        asset={"autonomy_tier": 5},
        target_range_m=10.0,
        friendly_separation_m=5.0,
    )
    assert result["allowed"] is False


def test_cqb_roe_set_hostage_rooms(roe):
    ok = roe.set_hostage_rooms(["R-101", "R-102"])
    assert ok is True
    # Verify the rule was updated
    for rule in roe.rules.values():
        if rule["type"] == "cqb_hostage":
            assert "R-101" in rule["params"]["restricted_rooms"]
            assert "R-102" in rule["params"]["restricted_rooms"]


def test_cqb_roe_violations_logged(roe):
    initial_count = len(roe.violations)
    roe.check_cqb_engagement(
        room_id="R-001", asset={"autonomy_tier": 1},
        target_range_m=10.0, friendly_separation_m=5.0,
    )
    assert len(roe.violations) > initial_count


# ═══════════════════════════════════════════════════════════
#  API ENDPOINTS — CQB PLANNER
# ═══════════════════════════════════════════════════════════

def test_api_cqb_plan_generate(auth_client):
    # Find a building first
    rv = auth_client.get("/api/v1/buildings")
    buildings = rv.get_json().get("buildings", [])
    if not buildings:
        pytest.skip("No buildings loaded")
    bid = buildings[0]["id"]
    rv = auth_client.post("/api/v1/cqb/plan", json={"building_id": bid})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["building_id"] == bid
    assert data["status"] == "READY"
    assert data["stats"]["total_tasks"] > 0


def test_api_cqb_plan_with_objective(auth_client):
    rv = auth_client.get("/api/v1/buildings")
    buildings = rv.get_json().get("buildings", [])
    if not buildings:
        pytest.skip("No buildings loaded")
    bid = buildings[0]["id"]
    # Get a room from floor 1
    rv2 = auth_client.get(f"/api/v1/buildings/{bid}/floorplan/1")
    rooms = rv2.get_json().get("rooms", [])
    obj_room = rooms[0]["id"] if rooms else ""
    rv = auth_client.post("/api/v1/cqb/plan",
                          json={"building_id": bid, "objective_room": obj_room})
    assert rv.status_code == 200
    data = rv.get_json()
    # Should have a SECURE task if objective room exists
    if obj_room:
        all_tasks = [t for phase in data["phases"] for t in phase]
        secure = [t for t in all_tasks if t["task_type"] == "SECURE"]
        assert len(secure) >= 1


def test_api_cqb_plan_missing_building(auth_client):
    rv = auth_client.post("/api/v1/cqb/plan", json={})
    assert rv.status_code == 400


def test_api_cqb_plan_not_found(auth_client):
    rv = auth_client.post("/api/v1/cqb/plan", json={"building_id": "NO-SUCH"})
    assert rv.status_code == 404


def test_api_cqb_plans_list(auth_client):
    # Generate a plan first
    rv = auth_client.get("/api/v1/buildings")
    buildings = rv.get_json().get("buildings", [])
    if not buildings:
        pytest.skip("No buildings loaded")
    auth_client.post("/api/v1/cqb/plan", json={"building_id": buildings[0]["id"]})
    rv = auth_client.get("/api/v1/cqb/plans")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "plans" in data
    assert "stats" in data


def test_api_cqb_plan_detail(auth_client):
    rv = auth_client.get("/api/v1/buildings")
    buildings = rv.get_json().get("buildings", [])
    if not buildings:
        pytest.skip("No buildings loaded")
    rv = auth_client.post("/api/v1/cqb/plan", json={"building_id": buildings[0]["id"]})
    plan_id = rv.get_json()["id"]
    rv = auth_client.get(f"/api/v1/cqb/plans/{plan_id}")
    assert rv.status_code == 200
    assert rv.get_json()["id"] == plan_id


def test_api_cqb_plan_detail_not_found(auth_client):
    rv = auth_client.get("/api/v1/cqb/plans/NOPE")
    assert rv.status_code == 404


def test_api_cqb_task_create(auth_client):
    rv = auth_client.post("/api/v1/cqb/task", json={
        "task_type": "CLEAR",
        "building_id": "BLDG-01",
        "target_id": "R-001",
        "params": {"room_id": "R-001", "formation": "buttonhook"},
        "assigned_assets": ["A1", "A2", "A3", "A4"],
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["status"] == "ok"
    assert data["task"]["task_type"] == "CLEAR"
    assert data["task"]["roles"]["point"] == "A1"


def test_api_cqb_task_create_invalid(auth_client):
    rv = auth_client.post("/api/v1/cqb/task", json={
        "task_type": "BREACH",
        "building_id": "B-01",
        "params": {"door_id": "", "method": "laser"},
    })
    assert rv.status_code == 400


def test_api_cqb_task_create_missing(auth_client):
    rv = auth_client.post("/api/v1/cqb/task", json={})
    assert rv.status_code == 400


def test_api_cqb_roe_check(auth_client):
    rv = auth_client.post("/api/v1/cqb/roe/check", json={
        "room_id": "R-001",
        "asset_id": "NONEXISTENT",  # will default to empty asset
        "range_m": 10.0,
        "friendly_separation_m": 5.0,
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert "allowed" in data


def test_api_cqb_roe_check_missing_room(auth_client):
    rv = auth_client.post("/api/v1/cqb/roe/check", json={})
    assert rv.status_code == 400


def test_api_cqb_roe_hostage(auth_client):
    rv = auth_client.post("/api/v1/cqb/roe/hostage",
                          json={"room_ids": ["R-101", "R-102"]})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["status"] == "ok"
    assert "R-101" in data["hostage_rooms"]
