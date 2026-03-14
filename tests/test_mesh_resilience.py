"""Tests for AMOS Mesh Resilience — Sprint 5."""
import time
import pytest
from services.mesh_network import MeshNetwork
from services.task_allocator import TaskAllocator
from services.swarm_behaviors import SwarmBehaviorManager
from services.mesh_resilience import (
    DisconnectedOpsManager,
    AutoRelayAssigner,
    ReconnectionSync,
    MeshResilienceOrchestrator,
)


# ─── Fixtures ──────────────────────────────────────────

def make_assets():
    """Create test assets with comms health."""
    return {
        "UAV-01": {
            "id": "UAV-01", "type": "uav", "domain": "air", "role": "recon",
            "position": {"lat": 27.85, "lng": -82.52},
            "sensors": ["EO/IR", "SIGINT"], "weapons": [],
            "status": "operational", "heading_deg": 45, "speed_kts": 100,
            "health": {"battery_pct": 95, "comms_strength": 90},
        },
        "UAV-02": {
            "id": "UAV-02", "type": "uav", "domain": "air", "role": "recon",
            "position": {"lat": 27.86, "lng": -82.53},
            "sensors": ["AESA_RADAR", "EO/IR"], "weapons": [],
            "status": "operational", "heading_deg": 90, "speed_kts": 110,
            "health": {"battery_pct": 88, "comms_strength": 85},
        },
        "UGV-01": {
            "id": "UGV-01", "type": "ugv", "domain": "ground", "role": "direct_action",
            "position": {"lat": 27.84, "lng": -82.51},
            "sensors": ["LIDAR", "ACOUSTIC"], "weapons": ["M240"],
            "status": "operational", "heading_deg": 180, "speed_kts": 15,
            "health": {"battery_pct": 92, "comms_strength": 95},
        },
        "UAV-03": {
            "id": "UAV-03", "type": "uav", "domain": "air", "role": "airborne_c2",
            "position": {"lat": 27.855, "lng": -82.515},
            "sensors": ["SIGINT"], "weapons": [],
            "status": "operational", "heading_deg": 0, "speed_kts": 80,
            "health": {"battery_pct": 90, "comms_strength": 92},
        },
    }


def make_mesh_with_nodes(assets):
    """Create a MeshNetwork pre-populated with nodes."""
    mesh = MeshNetwork()
    mesh._update_nodes(assets)
    mesh._compute_links([])
    return mesh


def make_orchestrator():
    """Create a fresh MeshResilienceOrchestrator."""
    mesh = MeshNetwork()
    ta = TaskAllocator()
    sbm = SwarmBehaviorManager()
    return MeshResilienceOrchestrator(mesh, sbm, ta)


# ═══════════════════════════════════════════════════════════
#  DISCONNECTED OPS MANAGER
# ═══════════════════════════════════════════════════════════

class TestDisconnectedOpsManager:
    def test_initial_state(self):
        dom = DisconnectedOpsManager()
        assert dom.summary()["disconnected_count"] == 0
        assert dom.summary()["cached_intents"] == 0

    def test_cache_intent(self):
        dom = DisconnectedOpsManager()
        dom.cache_intent("UAV-01", "PATROL", {"center_lat": 27.85, "center_lng": -82.52})
        intent = dom.get_intent("UAV-01")
        assert intent is not None
        assert intent["intent_type"] == "PATROL"
        assert intent["intent_data"]["center_lat"] == 27.85

    def test_cache_overwrite(self):
        dom = DisconnectedOpsManager()
        dom.cache_intent("UAV-01", "PATROL", {"center_lat": 27.85})
        dom.cache_intent("UAV-01", "WAYPOINT", {"lat": 28.0, "lng": -82.0})
        intent = dom.get_intent("UAV-01")
        assert intent["intent_type"] == "WAYPOINT"

    def test_get_intent_nonexistent(self):
        dom = DisconnectedOpsManager()
        assert dom.get_intent("NOPE") is None

    def test_intent_expires(self):
        dom = DisconnectedOpsManager()
        dom.cache_intent("UAV-01", "PATROL", {}, ttl_sec=0)
        # Immediate expiry
        time.sleep(0.01)
        assert dom.get_intent("UAV-01") is None

    def test_mark_disconnected(self):
        dom = DisconnectedOpsManager()
        dom.mark_disconnected("UAV-01", position={"lat": 27.85, "lng": -82.52})
        assert dom.is_disconnected("UAV-01")
        assert not dom.is_disconnected("UAV-02")
        assert dom.stats["disconnects"] == 1

    def test_mark_reconnected(self):
        dom = DisconnectedOpsManager()
        dom.mark_disconnected("UAV-01")
        result = dom.mark_reconnected("UAV-01")
        assert "duration_sec" in result
        assert result["asset_id"] == "UAV-01"
        assert not dom.is_disconnected("UAV-01")
        assert dom.stats["reconnects"] == 1

    def test_reconnect_not_disconnected(self):
        dom = DisconnectedOpsManager()
        result = dom.mark_reconnected("UAV-01")
        assert "error" in result

    def test_list_disconnected(self):
        dom = DisconnectedOpsManager()
        dom.mark_disconnected("UAV-01", reason="jammed")
        dom.mark_disconnected("UAV-02", reason="out_of_range")
        lst = dom.list_disconnected()
        assert len(lst) == 2
        ids = {e["asset_id"] for e in lst}
        assert ids == {"UAV-01", "UAV-02"}
        for entry in lst:
            assert "reason" in entry
            assert "duration_sec" in entry

    def test_tick_autonomous_waypoint(self):
        dom = DisconnectedOpsManager()
        assets = make_assets()
        dom.cache_intent("UAV-01", "WAYPOINT", {"lat": 28.0, "lng": -82.0})
        dom.mark_disconnected("UAV-01", position=assets["UAV-01"]["position"])
        events = dom.tick_autonomous("UAV-01", assets)
        assert len(events) == 1
        assert events[0]["type"] == "AUTONOMOUS_NAVIGATE"
        # Asset should have moved toward waypoint
        assert assets["UAV-01"]["position"]["lat"] > 27.85

    def test_tick_autonomous_patrol(self):
        dom = DisconnectedOpsManager()
        assets = make_assets()
        dom.cache_intent("UAV-01", "PATROL", {
            "center_lat": 27.85, "center_lng": -82.52, "radius_deg": 0.005})
        dom.mark_disconnected("UAV-01")
        events = dom.tick_autonomous("UAV-01", assets)
        assert len(events) == 1
        assert events[0]["type"] == "AUTONOMOUS_PATROL"

    def test_tick_autonomous_rtb(self):
        dom = DisconnectedOpsManager()
        assets = make_assets()
        dom.cache_intent("UAV-01", "RTB", {"base_lat": 27.80, "base_lng": -82.50})
        dom.mark_disconnected("UAV-01")
        events = dom.tick_autonomous("UAV-01", assets)
        assert len(events) == 1
        assert events[0]["type"] == "AUTONOMOUS_RTB"

    def test_tick_autonomous_hold_no_intent(self):
        dom = DisconnectedOpsManager()
        assets = make_assets()
        dom.mark_disconnected("UAV-01")
        events = dom.tick_autonomous("UAV-01", assets)
        assert len(events) == 1
        assert events[0]["type"] == "AUTONOMOUS_HOLD"
        assert events[0]["reason"] == "no_cached_intent"

    def test_tick_autonomous_not_disconnected(self):
        dom = DisconnectedOpsManager()
        assets = make_assets()
        events = dom.tick_autonomous("UAV-01", assets)
        assert events == []

    def test_tick_counts_accumulate(self):
        dom = DisconnectedOpsManager()
        assets = make_assets()
        dom.cache_intent("UAV-01", "PATROL", {
            "center_lat": 27.85, "center_lng": -82.52})
        dom.mark_disconnected("UAV-01")
        for _ in range(5):
            dom.tick_autonomous("UAV-01", assets)
        assert dom.stats["autonomous_ticks"] == 5
        assert dom.disconnected_assets["UAV-01"]["ticks_autonomous"] == 5

    def test_event_log(self):
        dom = DisconnectedOpsManager()
        dom.mark_disconnected("UAV-01")
        dom.mark_reconnected("UAV-01")
        assert len(dom.event_log) == 2
        assert dom.event_log[0]["type"] == "DISCONNECT"
        assert dom.event_log[1]["type"] == "RECONNECT"


# ═══════════════════════════════════════════════════════════
#  AUTO RELAY ASSIGNER
# ═══════════════════════════════════════════════════════════

class TestAutoRelayAssigner:
    def test_initial_state(self):
        mesh = MeshNetwork()
        sbm = SwarmBehaviorManager()
        ara = AutoRelayAssigner(mesh, sbm)
        assert ara.summary()["active_relays"] == 0
        assert ara.enabled is True

    def test_no_relay_when_disabled(self):
        mesh = MeshNetwork()
        sbm = SwarmBehaviorManager()
        ara = AutoRelayAssigner(mesh, sbm)
        ara.enabled = False
        events = ara.evaluate(make_assets())
        assert events == []

    def test_no_relay_when_all_connected(self):
        assets = make_assets()
        mesh = make_mesh_with_nodes(assets)
        sbm = SwarmBehaviorManager()
        ara = AutoRelayAssigner(mesh, sbm)
        # All links should be good quality (assets are close together)
        events = ara.evaluate(assets)
        # No degraded links → no relay needed
        assert ara.stats["evaluations"] == 1

    def test_relay_assigned_for_degraded_link(self):
        assets = make_assets()
        mesh = make_mesh_with_nodes(assets)
        sbm = SwarmBehaviorManager()
        ara = AutoRelayAssigner(mesh, sbm)
        # Manually inject a degraded link
        mesh.links["UAV-01<>UGV-01"] = {
            "from": "UAV-01", "to": "UGV-01",
            "quality": 0.1, "bandwidth_mbps": 0.5,
            "distance_km": 40, "latency_ms": 200, "band": "UHF",
        }
        events = ara.evaluate(assets)
        assert len(events) >= 1
        assert events[0]["type"] == "RELAY_ASSIGNED"
        assert ara.stats["relays_assigned"] >= 1

    def test_relay_not_duplicated(self):
        assets = make_assets()
        mesh = make_mesh_with_nodes(assets)
        sbm = SwarmBehaviorManager()
        ara = AutoRelayAssigner(mesh, sbm)
        mesh.links["UAV-01<>UGV-01"] = {
            "from": "UAV-01", "to": "UGV-01",
            "quality": 0.1, "bandwidth_mbps": 0.5,
            "distance_km": 40, "latency_ms": 200, "band": "UHF",
        }
        ara.evaluate(assets)
        first_count = ara.stats["relays_assigned"]
        ara.evaluate(assets)  # same degraded link
        assert ara.stats["relays_assigned"] == first_count  # no duplicate

    def test_release_relay(self):
        assets = make_assets()
        mesh = make_mesh_with_nodes(assets)
        sbm = SwarmBehaviorManager()
        ara = AutoRelayAssigner(mesh, sbm)
        mesh.links["UAV-01<>UGV-01"] = {
            "from": "UAV-01", "to": "UGV-01",
            "quality": 0.1, "bandwidth_mbps": 0.5,
            "distance_km": 40, "latency_ms": 200, "band": "UHF",
        }
        ara.evaluate(assets)
        relay_id = list(ara.active_relays.keys())[0]
        result = ara.release_relay(relay_id)
        assert result["status"] == "released"
        assert ara.stats["relays_released"] == 1
        assert len(ara.active_relays) == 0

    def test_release_nonexistent_relay(self):
        mesh = MeshNetwork()
        sbm = SwarmBehaviorManager()
        ara = AutoRelayAssigner(mesh, sbm)
        result = ara.release_relay("RELAY-NOPE")
        assert "error" in result

    def test_list_active(self):
        assets = make_assets()
        mesh = make_mesh_with_nodes(assets)
        sbm = SwarmBehaviorManager()
        ara = AutoRelayAssigner(mesh, sbm)
        mesh.links["UAV-01<>UGV-01"] = {
            "from": "UAV-01", "to": "UGV-01",
            "quality": 0.1, "bandwidth_mbps": 0.5,
            "distance_km": 40, "latency_ms": 200, "band": "UHF",
        }
        ara.evaluate(assets)
        active = ara.list_active()
        assert len(active) >= 1
        for r in active:
            assert "relay_id" in r
            assert "asset_id" in r
            assert "bridging" in r

    def test_disconnected_node_triggers_relay(self):
        assets = make_assets()
        mesh = MeshNetwork()
        # Add nodes but one with no connections
        mesh.nodes["UAV-01"] = {
            "id": "UAV-01", "lat": 27.85, "lng": -82.52,
            "band": "SATCOM", "status": "operational",
            "comms_strength": 90, "connections": [], "type": "uav", "domain": "air",
            "hop_freq": 0, "store_queue": 0,
        }
        mesh.nodes["UAV-02"] = {
            "id": "UAV-02", "lat": 27.86, "lng": -82.53,
            "band": "SATCOM", "status": "operational",
            "comms_strength": 85, "connections": ["UAV-03"], "type": "uav", "domain": "air",
            "hop_freq": 0, "store_queue": 0,
        }
        sbm = SwarmBehaviorManager()
        ara = AutoRelayAssigner(mesh, sbm)
        events = ara.evaluate(assets)
        # UAV-01 has no connections → should trigger relay
        assert len(events) >= 1


# ═══════════════════════════════════════════════════════════
#  RECONNECTION SYNC
# ═══════════════════════════════════════════════════════════

class TestReconnectionSync:
    def test_initial_state(self):
        sync = ReconnectionSync()
        s = sync.summary()
        assert s["queued_assets"] == 0
        assert s["total_commands"] == 0

    def test_queue_command(self):
        sync = ReconnectionSync()
        result = sync.queue_command("UAV-01", "TASK_ASSIGN", {"task_id": "T1"})
        assert result["status"] == "queued"
        assert result["queue_depth"] == 1
        assert sync.stats["commands_queued"] == 1

    def test_queue_multiple_commands(self):
        sync = ReconnectionSync()
        sync.queue_command("UAV-01", "TASK_ASSIGN", {"task_id": "T1"})
        sync.queue_command("UAV-01", "WAYPOINT_SET", {"lat": 28.0})
        sync.queue_command("UAV-01", "ROE_UPDATE", {"posture": "weapons_free"})
        q = sync.get_queue("UAV-01")
        assert q["depth"] == 3
        assert len(q["commands"]) == 3

    def test_queue_invalid_type(self):
        sync = ReconnectionSync()
        result = sync.queue_command("UAV-01", "INVALID_TYPE", {})
        assert "error" in result
        assert "available" in result

    def test_replay_commands(self):
        sync = ReconnectionSync()
        sync.queue_command("UAV-01", "TASK_ASSIGN", {"task_id": "T1"})
        sync.queue_command("UAV-01", "WAYPOINT_SET", {"lat": 28.0})
        result = sync.replay("UAV-01")
        assert result["replayed"] == 2
        assert result["expired"] == 0
        assert len(result["commands"]) == 2
        assert sync.stats["commands_replayed"] == 2
        assert sync.stats["syncs_completed"] == 1

    def test_replay_empty_queue(self):
        sync = ReconnectionSync()
        result = sync.replay("UAV-01")
        assert result["replayed"] == 0
        assert result["commands"] == []

    def test_replay_clears_queue(self):
        sync = ReconnectionSync()
        sync.queue_command("UAV-01", "TASK_ASSIGN", {"task_id": "T1"})
        sync.replay("UAV-01")
        q = sync.get_queue("UAV-01")
        assert q["depth"] == 0

    def test_expired_commands_not_replayed(self):
        sync = ReconnectionSync()
        sync.queue_command("UAV-01", "TASK_ASSIGN", {"task_id": "T1"}, ttl_sec=0)
        time.sleep(0.01)
        result = sync.replay("UAV-01")
        assert result["replayed"] == 0
        assert result["expired"] == 1

    def test_get_queue_all_assets(self):
        sync = ReconnectionSync()
        sync.queue_command("UAV-01", "TASK_ASSIGN", {"task_id": "T1"})
        sync.queue_command("UAV-02", "ROE_UPDATE", {"posture": "weapons_tight"})
        q = sync.get_queue()
        assert q["total_queued"] == 2
        assert "UAV-01" in q["assets"]
        assert "UAV-02" in q["assets"]

    def test_purge_expired(self):
        sync = ReconnectionSync()
        sync.queue_command("UAV-01", "TASK_ASSIGN", {"task_id": "T1"}, ttl_sec=0)
        sync.queue_command("UAV-01", "WAYPOINT_SET", {"lat": 28.0}, ttl_sec=600)
        time.sleep(0.01)
        result = sync.purge_expired()
        assert result["purged"] == 1
        q = sync.get_queue("UAV-01")
        assert q["depth"] == 1

    def test_replay_preserves_fifo_order(self):
        sync = ReconnectionSync()
        sync.queue_command("UAV-01", "TASK_ASSIGN", {"order": 1})
        sync.queue_command("UAV-01", "WAYPOINT_SET", {"order": 2})
        sync.queue_command("UAV-01", "ROE_UPDATE", {"order": 3})
        result = sync.replay("UAV-01")
        payloads = [c["payload"] for c in result["commands"]]
        assert payloads[0]["order"] == 1
        assert payloads[1]["order"] == 2
        assert payloads[2]["order"] == 3

    def test_multi_asset_queues_independent(self):
        sync = ReconnectionSync()
        sync.queue_command("UAV-01", "TASK_ASSIGN", {"task_id": "T1"})
        sync.queue_command("UAV-02", "TASK_ASSIGN", {"task_id": "T2"})
        result = sync.replay("UAV-01")
        assert result["replayed"] == 1
        # UAV-02 still has its command
        q = sync.get_queue("UAV-02")
        assert q["depth"] == 1


# ═══════════════════════════════════════════════════════════
#  MESH RESILIENCE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════

class TestMeshResilienceOrchestrator:
    def test_initial_state(self):
        orch = make_orchestrator()
        status = orch.get_status()
        assert status["tick_count"] == 0
        assert len(status["disconnected_assets"]) == 0
        assert len(status["active_relays"]) == 0

    def test_tick_returns_result(self):
        orch = make_orchestrator()
        assets = make_assets()
        result = orch.tick(assets)
        assert "tick" in result
        assert "events" in result
        assert "disconnected_count" in result
        assert "active_relays" in result
        assert result["tick"] == 1

    def test_tick_increments(self):
        orch = make_orchestrator()
        assets = make_assets()
        orch.tick(assets)
        orch.tick(assets)
        assert orch.tick_count == 2

    def test_simulate_disconnect(self):
        orch = make_orchestrator()
        assets = make_assets()
        result = orch.simulate_disconnect("UAV-01", assets)
        assert result["status"] == "disconnected"
        assert result["asset_id"] == "UAV-01"
        assert assets["UAV-01"]["health"]["comms_strength"] == 0
        assert orch.disconnected_ops.is_disconnected("UAV-01")

    def test_simulate_disconnect_nonexistent(self):
        orch = make_orchestrator()
        assets = make_assets()
        result = orch.simulate_disconnect("NOPE", assets)
        assert "error" in result

    def test_simulate_disconnect_already_disconnected(self):
        orch = make_orchestrator()
        assets = make_assets()
        orch.simulate_disconnect("UAV-01", assets)
        result = orch.simulate_disconnect("UAV-01", assets)
        assert "error" in result

    def test_simulate_reconnect(self):
        orch = make_orchestrator()
        assets = make_assets()
        orch.simulate_disconnect("UAV-01", assets)
        result = orch.simulate_reconnect("UAV-01", assets)
        assert result["status"] == "reconnected"
        assert assets["UAV-01"]["health"]["comms_strength"] == 85
        assert not orch.disconnected_ops.is_disconnected("UAV-01")

    def test_simulate_reconnect_not_disconnected(self):
        orch = make_orchestrator()
        assets = make_assets()
        result = orch.simulate_reconnect("UAV-01", assets)
        assert "error" in result

    def test_disconnect_caches_intent(self):
        orch = make_orchestrator()
        assets = make_assets()
        result = orch.simulate_disconnect("UAV-01", assets)
        # Should have inferred PATROL intent
        assert result["intent_cached"] == "PATROL"

    def test_autonomous_tick_after_disconnect(self):
        orch = make_orchestrator()
        assets = make_assets()
        orch.simulate_disconnect("UAV-01", assets)
        # Tick — UAV-01 should get autonomous events
        result = orch.tick(assets)
        auto_events = [e for e in result["events"]
                       if e.get("type", "").startswith("AUTONOMOUS_")]
        assert len(auto_events) >= 1

    def test_sync_queue_during_disconnect(self):
        orch = make_orchestrator()
        assets = make_assets()
        orch.simulate_disconnect("UAV-01", assets)
        # Queue a command while disconnected
        orch.sync.queue_command("UAV-01", "TASK_ASSIGN", {"task_id": "T1"})
        assert orch.sync.get_queue("UAV-01")["depth"] == 1

    def test_reconnect_replays_sync_queue(self):
        orch = make_orchestrator()
        assets = make_assets()
        orch.simulate_disconnect("UAV-01", assets)
        orch.sync.queue_command("UAV-01", "TASK_ASSIGN", {"task_id": "T1"})
        orch.sync.queue_command("UAV-01", "WAYPOINT_SET", {"lat": 28.0})
        result = orch.simulate_reconnect("UAV-01", assets)
        assert result["sync_result"]["replayed"] == 2

    def test_full_disconnect_reconnect_cycle(self):
        orch = make_orchestrator()
        assets = make_assets()

        # 1. Disconnect
        d_result = orch.simulate_disconnect("UAV-01", assets)
        assert d_result["status"] == "disconnected"

        # 2. Run a few autonomous ticks
        for _ in range(3):
            orch.tick(assets)

        # 3. Queue commands during disconnect
        orch.sync.queue_command("UAV-01", "ROE_UPDATE", {"posture": "weapons_free"})

        # 4. Reconnect
        r_result = orch.simulate_reconnect("UAV-01", assets)
        assert r_result["status"] == "reconnected"
        assert r_result["disconnect_info"]["ticks_autonomous"] >= 3
        assert r_result["sync_result"]["replayed"] == 1

    def test_get_status_comprehensive(self):
        orch = make_orchestrator()
        assets = make_assets()
        orch.simulate_disconnect("UAV-01", assets)
        orch.tick(assets)
        status = orch.get_status()
        assert "disconnected_ops" in status
        assert "relay_assigner" in status
        assert "reconnection_sync" in status
        assert "disconnected_assets" in status
        assert "active_relays" in status
        assert len(status["disconnected_assets"]) == 1

    def test_infer_intent_default_patrol(self):
        orch = make_orchestrator()
        assets = make_assets()
        intent = orch._infer_intent("UAV-01", assets["UAV-01"])
        assert intent["type"] == "PATROL"
        assert "center_lat" in intent["data"]

    def test_infer_intent_from_task(self):
        orch = make_orchestrator()
        assets = make_assets()
        # Create and assign a task
        orch.task_allocator.create_task("ISR", location={"lat": 28.0, "lng": -82.0}, priority=1)
        task = list(orch.task_allocator.tasks.values())[0]
        task.assigned_assets = ["UAV-01"]
        task.status = "EXECUTING"
        intent = orch._infer_intent("UAV-01", assets["UAV-01"])
        assert intent["type"] == "TASK"
        assert intent["data"]["task_type"] == "ISR"
