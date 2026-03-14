"""Tests for AMOS Interoperability Layer — Sprint 6."""
import pytest
from services.interop_layer import (
    AutonomyAbstraction,
    BlueUASRegistry,
    IntegrationHealthDashboard,
    InteropOrchestrator,
    FRAMEWORK_CATALOG,
    COMMAND_MAP,
    BLUE_UAS_CATALOG,
)


# ═══════════════════════════════════════════════════════════
#  AUTONOMY ABSTRACTION
# ═══════════════════════════════════════════════════════════

class TestAutonomyAbstraction:
    def test_list_frameworks(self):
        aa = AutonomyAbstraction()
        fws = aa.list_frameworks()
        assert len(fws) == 4
        ids = {f["id"] for f in fws}
        assert ids == {"PX4", "ARDUPILOT", "ROS2_NAV2", "DIMOS"}

    def test_framework_has_required_fields(self):
        for fw in FRAMEWORK_CATALOG.values():
            assert "id" in fw
            assert "name" in fw
            assert "protocol" in fw
            assert "domains" in fw
            assert "commands" in fw

    def test_bind_asset(self):
        aa = AutonomyAbstraction()
        result = aa.bind_asset("UAV-01", "PX4")
        assert result["status"] == "bound"
        assert result["framework"] == "PX4"
        assert result["protocol"] == "MAVLink"

    def test_bind_unknown_framework(self):
        aa = AutonomyAbstraction()
        result = aa.bind_asset("UAV-01", "FAKE")
        assert "error" in result
        assert "available" in result

    def test_unbind_asset(self):
        aa = AutonomyAbstraction()
        aa.bind_asset("UAV-01", "PX4")
        result = aa.unbind_asset("UAV-01")
        assert result["status"] == "unbound"

    def test_unbind_not_bound(self):
        aa = AutonomyAbstraction()
        result = aa.unbind_asset("NOPE")
        assert "error" in result

    def test_translate_waypoint_px4(self):
        aa = AutonomyAbstraction()
        aa.bind_asset("UAV-01", "PX4")
        result = aa.translate_command("UAV-01", "WAYPOINT",
                                      {"lat": 27.85, "lng": -82.52})
        assert result["framework"] == "PX4"
        assert result["protocol"] == "MAVLink"
        assert result["amos_command"] == "WAYPOINT"
        assert "SET_POSITION_TARGET" in result["translated"]["cmd"]
        assert result["translated"]["lat"] == 27.85

    def test_translate_waypoint_ros2(self):
        aa = AutonomyAbstraction()
        aa.bind_asset("UGV-01", "ROS2_NAV2")
        result = aa.translate_command("UGV-01", "WAYPOINT",
                                      {"lat": 27.84, "lng": -82.51})
        assert result["protocol"] == "ROS2"
        assert result["translated"]["cmd"] == "navigate_to_pose"

    def test_translate_rtl(self):
        aa = AutonomyAbstraction()
        aa.bind_asset("UAV-01", "PX4")
        result = aa.translate_command("UAV-01", "RTL")
        assert result["translated"]["mode"] == "RTL"

    def test_translate_hold_dimos(self):
        aa = AutonomyAbstraction()
        aa.bind_asset("ROBOT-01", "DIMOS")
        result = aa.translate_command("ROBOT-01", "HOLD")
        assert result["translated"]["cmd"] == "HOLD"

    def test_translate_breach_dimos(self):
        aa = AutonomyAbstraction()
        aa.bind_asset("ROBOT-01", "DIMOS")
        result = aa.translate_command("ROBOT-01", "BREACH")
        assert result["translated"]["cmd"] == "BREACH"

    def test_translate_unsupported_command(self):
        aa = AutonomyAbstraction()
        aa.bind_asset("UAV-01", "PX4")
        result = aa.translate_command("UAV-01", "BREACH")
        assert "error" in result
        assert "supported" in result

    def test_translate_unbound_asset(self):
        aa = AutonomyAbstraction()
        result = aa.translate_command("NOPE", "WAYPOINT")
        assert "error" in result

    def test_auto_detect_air(self):
        aa = AutonomyAbstraction()
        result = aa.translate_command("UAV-01", "WAYPOINT",
                                      {"domain": "air", "lat": 28.0})
        assert result["framework"] == "PX4"

    def test_auto_detect_ground(self):
        aa = AutonomyAbstraction()
        result = aa.translate_command("UGV-01", "WAYPOINT",
                                      {"domain": "ground", "lat": 28.0})
        assert result["framework"] == "ROS2_NAV2"

    def test_get_binding(self):
        aa = AutonomyAbstraction()
        aa.bind_asset("UAV-01", "PX4")
        b = aa.get_binding("UAV-01")
        assert b["framework"] == "PX4"
        assert b["protocol"] == "MAVLink"

    def test_get_binding_none(self):
        aa = AutonomyAbstraction()
        assert aa.get_binding("NOPE") is None

    def test_list_bindings(self):
        aa = AutonomyAbstraction()
        aa.bind_asset("UAV-01", "PX4")
        aa.bind_asset("UGV-01", "ROS2_NAV2")
        bindings = aa.list_bindings()
        assert len(bindings) == 2

    def test_command_log(self):
        aa = AutonomyAbstraction()
        aa.bind_asset("UAV-01", "PX4")
        aa.translate_command("UAV-01", "WAYPOINT", {"lat": 28.0})
        aa.translate_command("UAV-01", "RTL")
        assert len(aa.command_log) == 2
        assert aa.stats["commands_translated"] == 2

    def test_stats(self):
        aa = AutonomyAbstraction()
        aa.bind_asset("UAV-01", "PX4")
        aa.translate_command("UAV-01", "WAYPOINT")
        aa.translate_command("UAV-01", "BREACH")  # unsupported → fail
        assert aa.stats["commands_translated"] == 1
        assert aa.stats["commands_failed"] == 1

    def test_summary(self):
        aa = AutonomyAbstraction()
        aa.bind_asset("UAV-01", "PX4")
        s = aa.summary()
        assert s["bindings"] == 1
        assert s["frameworks"] == 4


# ═══════════════════════════════════════════════════════════
#  BLUE UAS REGISTRY
# ═══════════════════════════════════════════════════════════

class TestBlueUASRegistry:
    def test_catalog_populated(self):
        reg = BlueUASRegistry()
        assert len(reg.catalog) == 8

    def test_lookup_by_model_id(self):
        reg = BlueUASRegistry()
        p = reg.lookup("SKYDIO-X10")
        assert p is not None
        assert p["manufacturer"] == "Skydio"
        assert p["blue_uas_approved"] is True

    def test_lookup_nonexistent(self):
        reg = BlueUASRegistry()
        assert reg.lookup("FAKE-DRONE") is None

    def test_search_by_text(self):
        reg = BlueUASRegistry()
        results = reg.search("skydio")
        assert len(results) >= 1
        assert results[0]["model_id"] == "SKYDIO-X10"

    def test_search_by_domain_air(self):
        reg = BlueUASRegistry()
        results = reg.search(domain="air")
        assert len(results) >= 6
        for r in results:
            assert "air" in r["domains"]

    def test_search_by_domain_ground(self):
        reg = BlueUASRegistry()
        results = reg.search(domain="ground")
        assert len(results) >= 2
        for r in results:
            assert "ground" in r["domains"]

    def test_search_with_weapons(self):
        reg = BlueUASRegistry()
        results = reg.search(has_weapons=True)
        assert len(results) >= 1
        for r in results:
            assert len(r["weapons"]) > 0

    def test_search_without_weapons(self):
        reg = BlueUASRegistry()
        results = reg.search(has_weapons=False)
        assert len(results) >= 1
        for r in results:
            assert len(r["weapons"]) == 0

    def test_get_by_framework(self):
        reg = BlueUASRegistry()
        px4_platforms = reg.get_by_framework("PX4")
        assert len(px4_platforms) >= 2
        for p in px4_platforms:
            assert p["autonomy_framework"] == "PX4"

    def test_get_sensors_for_model(self):
        reg = BlueUASRegistry()
        s = reg.get_sensors_for_model("SHIELD-AI-V-BAT")
        assert s is not None
        assert "AESA_RADAR" in s["sensors"]
        assert s["endurance_min"] == 480

    def test_get_sensors_nonexistent(self):
        reg = BlueUASRegistry()
        assert reg.get_sensors_for_model("FAKE") is None

    def test_list_all(self):
        reg = BlueUASRegistry()
        assert len(reg.list_all()) == 8

    def test_all_entries_have_required_fields(self):
        reg = BlueUASRegistry()
        required = {"model_id", "manufacturer", "model", "domains", "sensors",
                     "weapons", "autonomy_framework", "blue_uas_approved"}
        for p in reg.list_all():
            for f in required:
                assert f in p, f"Missing field {f} in {p['model_id']}"

    def test_summary(self):
        reg = BlueUASRegistry()
        s = reg.summary()
        assert s["total_platforms"] == 8
        assert "air" in s["by_domain"]
        assert "ground" in s["by_domain"]
        assert "PX4" in s["by_framework"]


# ═══════════════════════════════════════════════════════════
#  INTEGRATION HEALTH DASHBOARD
# ═══════════════════════════════════════════════════════════

class MockBridge:
    """Minimal bridge mock for health dashboard tests."""
    def __init__(self, connected=True, protocol="TEST"):
        self._connected = connected
        self._protocol = protocol
    def get_status(self):
        return {"connected": self._connected, "protocol": self._protocol,
                "stats": {"messages_in": 42, "errors": 0}}


class TestIntegrationHealthDashboard:
    def test_initial_state(self):
        dash = IntegrationHealthDashboard()
        assert dash.summary()["total_bridges"] == 0

    def test_register_bridge(self):
        dash = IntegrationHealthDashboard()
        dash.register_bridge("px4", protocol="MAVLink", connected=True)
        assert dash.summary()["total_bridges"] == 1
        assert dash.summary()["connected"] == 1

    def test_register_known_bridge(self):
        dash = IntegrationHealthDashboard()
        dash.register_bridge("ros2", connected=True)
        b = dash.get_bridge("ros2")
        assert b["protocol"] == "ROS2"
        assert b["description"] == "ROS 2 Bridge"

    def test_update_from_object(self):
        dash = IntegrationHealthDashboard()
        bridge = MockBridge(connected=True, protocol="MAVLink")
        dash.update_from_object("px4", bridge)
        b = dash.get_bridge("px4")
        assert b["connected"] is True
        assert b["stats"]["messages_in"] == 42

    def test_check_all(self):
        dash = IntegrationHealthDashboard()
        bridges = {
            "px4": MockBridge(True, "MAVLink"),
            "ros2": MockBridge(False, "ROS2"),
            "dimos": MockBridge(True, "DimOS"),
        }
        dash.check_all(bridges)
        assert dash.summary()["total_bridges"] == 3
        assert dash.summary()["connected"] == 2
        assert dash.summary()["disconnected"] == 1

    def test_alerts_for_disconnected(self):
        dash = IntegrationHealthDashboard()
        dash.register_bridge("px4", connected=False)
        dash._evaluate_alerts()
        assert len(dash.alerts) >= 1
        assert dash.alerts[0]["severity"] == "warning"

    def test_alerts_for_errors(self):
        dash = IntegrationHealthDashboard()
        dash.register_bridge("px4", connected=True, stats={"errors": 15})
        dash._evaluate_alerts()
        error_alerts = [a for a in dash.alerts if a["severity"] == "error"]
        assert len(error_alerts) >= 1

    def test_get_dashboard(self):
        dash = IntegrationHealthDashboard()
        dash.register_bridge("px4", connected=True)
        dash.register_bridge("ros2", connected=False)
        d = dash.get_dashboard()
        assert "summary" in d
        assert "bridges" in d
        assert "alerts" in d
        assert d["summary"]["total_bridges"] == 2
        assert d["summary"]["health_pct"] == 50.0

    def test_list_connected(self):
        dash = IntegrationHealthDashboard()
        dash.register_bridge("px4", connected=True)
        dash.register_bridge("ros2", connected=False)
        assert len(dash.list_connected()) == 1
        assert len(dash.list_disconnected()) == 1

    def test_none_bridges_skipped(self):
        dash = IntegrationHealthDashboard()
        bridges = {"px4": MockBridge(True), "bad": None}
        dash.check_all(bridges)
        assert dash.summary()["total_bridges"] == 1


# ═══════════════════════════════════════════════════════════
#  INTEROP ORCHESTRATOR
# ═══════════════════════════════════════════════════════════

class TestInteropOrchestrator:
    def test_creates_all_components(self):
        orch = InteropOrchestrator()
        assert orch.autonomy is not None
        assert orch.blue_uas is not None
        assert orch.health is not None

    def test_get_status(self):
        orch = InteropOrchestrator()
        s = orch.get_status()
        assert "autonomy_abstraction" in s
        assert "blue_uas_registry" in s
        assert "integration_health" in s
        assert s["blue_uas_registry"]["total_platforms"] == 8
