"""B4 CQB Execution Engine + DimOS Bridge Tests.

Tests:
  - CQBExecutor: start, tick, pause, resume, abort, contact, progress
  - Task lifecycle: PLANNED → READY → EXECUTING → COMPLETE
  - Room clearing side-effects (mark_cleared, indoor position updates)
  - EventBus publishing
  - DimOS Bridge: connect, emit, ingest, telemetry, command mapping
  - API endpoints: execution CRUD, DimOS status/command
"""

import sys, os, json, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from services.cqb_task_language import CQBTask
from services.cqb_planner import CQBPlanner, CQBPlan
from services.cqb_executor import CQBExecutor, CQBExecution
from services.building_model import BuildingModel
from services.indoor_positioning import IndoorPositioningService
from core.event_bus import EventBus
from integrations.dimos_bridge import DimOSBridge, DIMOS_COMMANDS


# ═══════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════

SAMPLE_BUILDING = {
    "id": "BLDG-EXEC-01",
    "name": "Exec Test Building",
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
def building():
    return BuildingModel(copy.deepcopy(SAMPLE_BUILDING))


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def indoor():
    return IndoorPositioningService()


@pytest.fixture
def executor(building, indoor, event_bus):
    from services.building_model import BuildingManager
    mgr = BuildingManager()
    mgr.buildings[building.id] = building
    return CQBExecutor(building_mgr=mgr, indoor_positioning=indoor,
                       event_bus=event_bus)


@pytest.fixture
def planner():
    return CQBPlanner()


@pytest.fixture
def plan(planner, building):
    return planner.generate_plan(building, team_size=4)


@pytest.fixture
def dimos():
    bridge = DimOSBridge()
    bridge.connect()
    return bridge


# ═══════════════════════════════════════════════════════════
#  CQB EXECUTOR — LIFECYCLE
# ═══════════════════════════════════════════════════════════

def test_executor_creation(executor):
    assert executor.building_mgr is not None
    assert executor.indoor_positioning is not None
    assert executor.event_bus is not None
    assert executor.executions == {}


def test_start_execution(executor, plan):
    ex = executor.start_execution(plan, TEAM)
    assert ex.status == "RUNNING"
    assert ex.started is not None
    assert plan.status == "EXECUTING"
    assert ex.id in executor.executions


def test_execution_to_dict(executor, plan):
    ex = executor.start_execution(plan, TEAM)
    d = ex.to_dict()
    assert d["status"] == "RUNNING"
    assert d["plan_id"] == plan.id
    assert d["progress"]["total"] > 0


def test_tick_advances(executor, plan):
    ex = executor.start_execution(plan, TEAM)
    events = executor.tick(ex.id)
    assert isinstance(events, list)
    assert ex.tick_count == 1


def test_multiple_ticks_complete_plan(executor, plan):
    """Ticking enough times should complete all phases."""
    ex = executor.start_execution(plan, TEAM)
    all_events = []
    for _ in range(50):  # plenty of ticks
        evts = executor.tick(ex.id)
        all_events.extend(evts)
        if ex.status == "COMPLETE":
            break
    assert ex.status == "COMPLETE"
    assert ex.completed is not None
    assert plan.status == "COMPLETE"
    # Should have some completion events
    types = [e["type"] for e in all_events]
    assert "cqb.execution.completed" in types


def test_tick_on_non_running_returns_empty(executor, plan):
    ex = executor.start_execution(plan, TEAM)
    executor.pause(ex.id)
    events = executor.tick(ex.id)
    assert events == []


def test_pause_resume(executor, plan):
    ex = executor.start_execution(plan, TEAM)
    assert executor.pause(ex.id) is True
    assert ex.status == "PAUSED"
    assert executor.resume(ex.id) is True
    assert ex.status == "RUNNING"


def test_pause_non_running_fails(executor, plan):
    ex = executor.start_execution(plan, TEAM)
    executor.abort(ex.id)
    assert executor.pause(ex.id) is False


def test_abort(executor, plan):
    ex = executor.start_execution(plan, TEAM)
    assert executor.abort(ex.id, "test abort") is True
    assert ex.status == "ABORTED"
    assert ex.completed is not None
    # All tasks should be aborted
    for task in plan.all_tasks.values():
        assert task.status in ("ABORTED", "COMPLETE", "FAILED")


def test_abort_from_paused(executor, plan):
    ex = executor.start_execution(plan, TEAM)
    executor.pause(ex.id)
    assert executor.abort(ex.id) is True
    assert ex.status == "ABORTED"


def test_report_contact(executor, plan):
    ex = executor.start_execution(plan, TEAM)
    result = executor.report_contact(ex.id, "R-001", "hostile", "2 pax")
    assert result["type"] == "cqb.contact"
    assert result["room_id"] == "R-001"
    assert len(ex.events) >= 1


def test_report_contact_bad_execution(executor):
    result = executor.report_contact("FAKE-ID", "R-001")
    assert "error" in result


def test_list_executions(executor, plan):
    executor.start_execution(plan, TEAM)
    execs = executor.list_executions()
    assert len(execs) == 1
    assert execs[0]["status"] == "RUNNING"


def test_get_stats(executor, plan):
    stats = executor.get_stats()
    assert stats["total_executions"] == 0
    executor.start_execution(plan, TEAM)
    stats = executor.get_stats()
    assert stats["total_executions"] == 1
    assert stats["by_status"]["RUNNING"] == 1


# ═══════════════════════════════════════════════════════════
#  TASK PROGRESSION
# ═══════════════════════════════════════════════════════════

def test_tasks_get_assigned(plan):
    """Tasks should have assets assigned after execution start."""
    ex = CQBExecution(plan, TEAM)
    for task in plan.all_tasks.values():
        if task.task_type in ("CLEAR", "BREACH", "STACK"):
            assert len(task.assigned_assets) > 0


def test_task_events_include_type(executor, plan):
    ex = executor.start_execution(plan, TEAM)
    events = executor.tick(ex.id)
    for evt in events:
        assert "type" in evt


# ═══════════════════════════════════════════════════════════
#  ROOM CLEARING SIDE EFFECTS
# ═══════════════════════════════════════════════════════════

def test_room_cleared_after_execution(executor, plan, building):
    """After full execution, rooms should be marked as cleared."""
    ex = executor.start_execution(plan, TEAM)
    for _ in range(50):
        executor.tick(ex.id)
        if ex.status == "COMPLETE":
            break
    assert building.clearing_progress > 0


def test_event_bus_receives_events(executor, plan, event_bus):
    """EventBus should receive CQB events during execution."""
    received = []
    event_bus.subscribe("cqb.*", lambda evt: received.append(evt.topic))
    ex = executor.start_execution(plan, TEAM)
    import time; time.sleep(0.05)  # allow async delivery
    for _ in range(50):
        executor.tick(ex.id)
        time.sleep(0.02)  # allow async delivery
        if ex.status == "COMPLETE":
            break
    time.sleep(0.1)  # final flush
    assert len(received) > 0
    assert any("cqb." in t for t in received)


# ═══════════════════════════════════════════════════════════
#  EXECUTION PROGRESS
# ═══════════════════════════════════════════════════════════

def test_progress_starts_at_zero(executor, plan):
    ex = executor.start_execution(plan, TEAM)
    prog = ex.to_dict()["progress"]
    assert prog["complete"] == 0
    assert prog["total"] > 0


def test_progress_reaches_100(executor, plan):
    ex = executor.start_execution(plan, TEAM)
    for _ in range(50):
        executor.tick(ex.id)
        if ex.status == "COMPLETE":
            break
    prog = ex.to_dict()["progress"]
    assert prog["pct"] == 100.0


# ═══════════════════════════════════════════════════════════
#  DIMOS BRIDGE — CONNECT / DISCONNECT
# ═══════════════════════════════════════════════════════════

def test_dimos_constants():
    assert "NAVIGATE" in DIMOS_COMMANDS
    assert "BREACH" in DIMOS_COMMANDS
    assert "SCAN" in DIMOS_COMMANDS


def test_dimos_connect_standalone(dimos):
    assert dimos.connected is True
    assert dimos._standalone is True


def test_dimos_disconnect(dimos):
    assert dimos.disconnect() is True
    assert dimos.connected is False


def test_dimos_status(dimos):
    status = dimos.get_status()
    assert status["adapter_id"] == "dimos"
    assert status["protocol"] == "DimOS"
    assert status["standalone"] is True


# ═══════════════════════════════════════════════════════════
#  DIMOS BRIDGE — EMIT / COMMAND
# ═══════════════════════════════════════════════════════════

def test_dimos_emit(dimos):
    ok = dimos.emit({"type": "test", "data": 123})
    assert ok is True
    assert dimos.stats["messages_out"] >= 1


def test_dimos_emit_disconnected():
    bridge = DimOSBridge()
    # Not connected
    ok = bridge.emit({"type": "test"})
    assert ok is False


def test_dimos_send_command(dimos):
    cmd = dimos.send_command("CLAW1", "NAVIGATE", {"room_id": "R-001"})
    assert cmd["command"] == "NAVIGATE"
    assert cmd["asset_id"] == "CLAW1"


def test_dimos_send_unknown_command(dimos):
    result = dimos.send_command("CLAW1", "TELEPORT")
    assert "error" in result


def test_dimos_send_navigate(dimos):
    cmd = dimos.send_navigate("CLAW1", "BLDG-01", "R-001", floor=0)
    assert cmd["command"] == "NAVIGATE"
    assert cmd["params"]["room_id"] == "R-001"


def test_dimos_send_breach(dimos):
    cmd = dimos.send_breach("CLAW1", "D-001", "explosive")
    assert cmd["command"] == "BREACH"
    assert cmd["params"]["method"] == "explosive"


def test_dimos_send_scan(dimos):
    cmd = dimos.send_scan("CLAW1", "R-001")
    assert cmd["command"] == "SCAN"


def test_dimos_send_posture(dimos):
    cmd = dimos.send_posture("CLAW1", "crouching")
    assert cmd["command"] == "POSTURE"
    assert cmd["params"]["posture"] == "crouching"


def test_dimos_command_log(dimos):
    dimos.send_command("CLAW1", "HOLD", {"sector": "north"})
    dimos.send_command("CLAW2", "SCAN", {"room_id": "R-002"})
    log = dimos.get_command_log()
    assert len(log) >= 2


# ═══════════════════════════════════════════════════════════
#  DIMOS BRIDGE — INGEST / TELEMETRY
# ═══════════════════════════════════════════════════════════

def test_dimos_inject_and_ingest_position(dimos):
    dimos.inject_telemetry("CLAW1", "position", {
        "lat": 35.686, "lng": 51.318, "alt_ft": 0,
    })
    items = dimos.ingest()
    assert len(items) == 1


def test_dimos_inject_health_telemetry(dimos):
    dimos.inject_telemetry("CLAW1", "health", {
        "value": 85,
    })
    items = dimos.ingest()
    assert len(items) == 1


def test_dimos_inject_generic_telemetry(dimos):
    dimos.inject_telemetry("CLAW1", "custom_topic", {"foo": "bar"})
    items = dimos.ingest()
    assert len(items) == 1


def test_dimos_telemetry_cache(dimos):
    dimos.inject_telemetry("CLAW1", "position", {"lat": 35.5, "lng": 51.3})
    dimos.ingest()  # must ingest to populate cache
    telem = dimos.get_telemetry("CLAW1")
    assert telem is not None
    assert telem["topic"] == "position"


def test_dimos_get_all_telemetry(dimos):
    dimos.inject_telemetry("CLAW1", "position", {"lat": 35.5})
    dimos.inject_telemetry("CLAW2", "health", {"value": 99})
    dimos.ingest()
    all_telem = dimos.get_all_telemetry()
    assert "CLAW1" in all_telem
    assert "CLAW2" in all_telem


# ═══════════════════════════════════════════════════════════
#  DIMOS BRIDGE — CQB TASK MAPPING
# ═══════════════════════════════════════════════════════════

def test_dimos_map_stack_task(dimos):
    task = CQBTask("STACK", "BLDG-01", target_id="D-001",
                   assigned_assets=["CLAW1", "CLAW2"])
    commands = dimos.map_cqb_task(task)
    assert len(commands) == 2
    assert all(c["command"] == "NAVIGATE" for c in commands)


def test_dimos_map_breach_task(dimos):
    task = CQBTask("BREACH", "BLDG-01", target_id="D-001",
                   assigned_assets=["CLAW1"])
    commands = dimos.map_cqb_task(task)
    assert len(commands) == 1
    assert commands[0]["command"] == "BREACH"


def test_dimos_map_clear_task(dimos):
    task = CQBTask("CLEAR", "BLDG-01", target_id="R-001",
                   assigned_assets=["CLAW1", "CLAW2"])
    commands = dimos.map_cqb_task(task)
    # 2 NAVIGATE + 1 SCAN
    assert len(commands) == 3
    cmd_types = [c["command"] for c in commands]
    assert "NAVIGATE" in cmd_types
    assert "SCAN" in cmd_types


def test_dimos_map_hold_task(dimos):
    task = CQBTask("HOLD", "BLDG-01", target_id="R-001",
                   assigned_assets=["CLAW1"],
                   params={"sector": "north"})
    commands = dimos.map_cqb_task(task)
    assert len(commands) == 1
    assert commands[0]["command"] == "HOLD"


def test_dimos_map_extract_task(dimos):
    task = CQBTask("EXTRACT", "BLDG-01", target_id="R-001",
                   assigned_assets=["CLAW1", "PACK1"])
    commands = dimos.map_cqb_task(task)
    assert len(commands) == 2
    assert all(c["command"] == "EXTRACT" for c in commands)


# ═══════════════════════════════════════════════════════════
#  API ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════

def test_api_cqb_executions_list(auth_client):
    r = auth_client.get("/api/cqb/executions")
    assert r.status_code == 200
    d = r.get_json()
    assert "executions" in d
    assert "stats" in d


def test_api_cqb_execution_not_found(auth_client):
    r = auth_client.get("/api/cqb/execution/FAKE-ID")
    assert r.status_code == 404


def test_api_cqb_execute_missing_plan(auth_client):
    r = auth_client.post("/api/cqb/execute",
                         json={"plan_id": "FAKE", "asset_ids": ["A1"]})
    assert r.status_code == 404


def test_api_cqb_execute_missing_assets(auth_client):
    r = auth_client.post("/api/cqb/execute",
                         json={"plan_id": "FAKE"})
    # plan_id is provided but invalid — should be 404 or 400
    assert r.status_code in (400, 404)


def test_api_dimos_status(auth_client):
    r = auth_client.get("/api/dimos/status")
    assert r.status_code == 200
    d = r.get_json()
    assert d["adapter_id"] == "dimos"


def test_api_dimos_command(auth_client):
    r = auth_client.post("/api/dimos/command",
                         json={"asset_id": "CLAW1", "command": "HOLD",
                               "params": {"sector": "north"}})
    assert r.status_code == 200
    d = r.get_json()
    assert d["command"] == "HOLD"


def test_api_dimos_command_missing_fields(auth_client):
    r = auth_client.post("/api/dimos/command", json={})
    assert r.status_code == 400


def test_api_dimos_telemetry(auth_client):
    r = auth_client.get("/api/dimos/telemetry")
    assert r.status_code == 200


def test_api_dimos_command_log(auth_client):
    r = auth_client.get("/api/dimos/commands")
    assert r.status_code == 200
    d = r.get_json()
    assert "commands" in d


def test_api_dimos_connect(auth_client):
    r = auth_client.post("/api/dimos/connect", json={})
    assert r.status_code == 200
    d = r.get_json()
    assert d["connected"] is True


# ═══════════════════════════════════════════════════════════
#  END-TO-END: PLAN → EXECUTE → COMPLETE
# ═══════════════════════════════════════════════════════════

def test_e2e_plan_execute_complete(auth_client):
    """Generate a plan via API, then execute it to completion via ticks."""
    # Need a building loaded — use the shared state building_mgr
    from web.state import building_mgr as bm, cqb_planner as cp, cqb_executor as ce
    if not bm or not cp or not ce:
        pytest.skip("Building/CQB services not available")

    # Load test building
    b = BuildingModel(copy.deepcopy(SAMPLE_BUILDING))
    bm.buildings[b.id] = b

    # Generate plan via API
    r = auth_client.post("/api/cqb/plan",
                         json={"building_id": b.id, "team_size": 4})
    assert r.status_code == 200
    plan_data = r.get_json()
    plan_id = plan_data["id"]

    # Start execution via API
    r = auth_client.post("/api/cqb/execute",
                         json={"plan_id": plan_id, "asset_ids": TEAM})
    assert r.status_code == 200
    exec_data = r.get_json()
    exec_id = exec_data["execution"]["id"]

    # Tick until complete
    for _ in range(50):
        r = auth_client.post(f"/api/cqb/execution/{exec_id}/tick", json={})
        assert r.status_code == 200
        d = r.get_json()
        if d["execution"]["status"] == "COMPLETE":
            break

    # Verify final state
    r = auth_client.get(f"/api/cqb/execution/{exec_id}")
    assert r.status_code == 200
    d = r.get_json()
    assert d["status"] == "COMPLETE"
    assert d["progress"]["pct"] == 100.0
