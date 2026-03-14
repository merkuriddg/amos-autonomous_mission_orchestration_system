#!/usr/bin/env python3
"""AMOS Sprint 6 — Interoperability & Autonomy Abstraction Layer

Three components that complete the platform integration story:

1. **AutonomyAbstraction** — Unified command interface that maps AMOS tasks
   to any supported autonomy framework (PX4/MAVLink, ROS2 Nav2, DimOS,
   ArduPilot). Operators issue one command; the abstraction layer translates
   to the correct protocol for each asset.

2. **BlueUASRegistry** — Hardware profile database for DoD Blue UAS
   (Unmanned Aircraft Systems) approved platforms. Maps each drone model to
   AMOS-compatible sensor/weapon/endurance capabilities so task allocation
   knows what each airframe can do.

3. **IntegrationHealthDashboard** — Aggregates connection status, message
   throughput, error rates, and latency for every integration bridge. One
   endpoint gives operators a real-time view of which links are healthy.
"""

import copy
import time
import uuid
import threading
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════
#  AUTONOMY ABSTRACTION LAYER
# ═══════════════════════════════════════════════════════════

# Framework definitions — what protocols each framework uses
FRAMEWORK_CATALOG = {
    "PX4": {
        "id": "PX4",
        "name": "PX4 Autopilot",
        "protocol": "MAVLink",
        "domains": ["air"],
        "commands": ["WAYPOINT", "ORBIT", "RTL", "LAND", "ARM", "DISARM",
                     "SET_MODE", "SET_SPEED", "TAKEOFF"],
        "description": "MAVLink-based autopilot for multirotor and fixed-wing UAS",
    },
    "ARDUPILOT": {
        "id": "ARDUPILOT",
        "name": "ArduPilot",
        "protocol": "MAVLink",
        "domains": ["air", "ground", "maritime"],
        "commands": ["WAYPOINT", "ORBIT", "RTL", "LAND", "ARM", "DISARM",
                     "SET_MODE", "SET_SPEED", "TAKEOFF", "GUIDED"],
        "description": "Open-source autopilot supporting air, ground, and marine vehicles",
    },
    "ROS2_NAV2": {
        "id": "ROS2_NAV2",
        "name": "ROS 2 Navigation2",
        "protocol": "ROS2",
        "domains": ["ground"],
        "commands": ["NAVIGATE", "PATROL", "FOLLOW_PATH", "HOLD",
                     "SET_SPEED", "CANCEL"],
        "description": "ROS 2 Nav2 stack for autonomous ground navigation",
    },
    "DIMOS": {
        "id": "DIMOS",
        "name": "DimOS",
        "protocol": "DimOS",
        "domains": ["ground"],
        "commands": ["NAVIGATE", "BREACH", "SCAN", "HOLD", "POSTURE",
                     "MANIPULATE", "EXTRACT", "STACK"],
        "description": "Bipedal humanoid robot autonomy via DimOS",
    },
}

# AMOS task → framework command mapping
COMMAND_MAP = {
    # (amos_command, framework_id) → translated command
    ("WAYPOINT", "PX4"): {"cmd": "SET_POSITION_TARGET_GLOBAL_INT", "frame": "GLOBAL_RELATIVE_ALT"},
    ("WAYPOINT", "ARDUPILOT"): {"cmd": "NAV_WAYPOINT", "frame": "GLOBAL_RELATIVE_ALT"},
    ("WAYPOINT", "ROS2_NAV2"): {"cmd": "navigate_to_pose", "frame": "map"},
    ("WAYPOINT", "DIMOS"): {"cmd": "NAVIGATE", "frame": "indoor"},
    ("RTL", "PX4"): {"cmd": "SET_MODE", "mode": "RTL"},
    ("RTL", "ARDUPILOT"): {"cmd": "SET_MODE", "mode": "RTL"},
    ("RTL", "ROS2_NAV2"): {"cmd": "navigate_to_pose", "target": "home"},
    ("RTL", "DIMOS"): {"cmd": "NAVIGATE", "target": "base"},
    ("ORBIT", "PX4"): {"cmd": "DO_ORBIT", "frame": "GLOBAL_RELATIVE_ALT"},
    ("ORBIT", "ARDUPILOT"): {"cmd": "DO_ORBIT", "frame": "GLOBAL_RELATIVE_ALT"},
    ("LAND", "PX4"): {"cmd": "SET_MODE", "mode": "LAND"},
    ("LAND", "ARDUPILOT"): {"cmd": "SET_MODE", "mode": "LAND"},
    ("HOLD", "PX4"): {"cmd": "SET_MODE", "mode": "HOLD"},
    ("HOLD", "ARDUPILOT"): {"cmd": "SET_MODE", "mode": "HOLD"},
    ("HOLD", "ROS2_NAV2"): {"cmd": "cancel_navigation"},
    ("HOLD", "DIMOS"): {"cmd": "HOLD"},
    ("SCAN", "DIMOS"): {"cmd": "SCAN"},
    ("BREACH", "DIMOS"): {"cmd": "BREACH"},
    ("ARM", "PX4"): {"cmd": "COMPONENT_ARM_DISARM", "arm": True},
    ("ARM", "ARDUPILOT"): {"cmd": "COMPONENT_ARM_DISARM", "arm": True},
    ("DISARM", "PX4"): {"cmd": "COMPONENT_ARM_DISARM", "arm": False},
    ("DISARM", "ARDUPILOT"): {"cmd": "COMPONENT_ARM_DISARM", "arm": False},
    ("TAKEOFF", "PX4"): {"cmd": "NAV_TAKEOFF"},
    ("TAKEOFF", "ARDUPILOT"): {"cmd": "NAV_TAKEOFF"},
    ("PATROL", "ROS2_NAV2"): {"cmd": "follow_waypoints"},
}


class AutonomyAbstraction:
    """Unified command interface across all autonomy frameworks.

    Translates AMOS-standard commands into framework-specific protocols
    so operators issue one command regardless of what platform runs beneath.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.asset_bindings = {}  # asset_id → framework_id
        self.command_log = []
        self.stats = {
            "commands_translated": 0,
            "commands_failed": 0,
            "bindings": 0,
        }

    def bind_asset(self, asset_id, framework_id):
        """Bind an asset to an autonomy framework.

        Args:
            asset_id:     AMOS asset identifier
            framework_id: key from FRAMEWORK_CATALOG

        Returns:
            dict with binding info or error
        """
        if framework_id not in FRAMEWORK_CATALOG:
            return {"error": f"Unknown framework: {framework_id}",
                    "available": list(FRAMEWORK_CATALOG.keys())}
        with self._lock:
            self.asset_bindings[asset_id] = framework_id
            self.stats["bindings"] = len(self.asset_bindings)
        return {
            "status": "bound",
            "asset_id": asset_id,
            "framework": framework_id,
            "protocol": FRAMEWORK_CATALOG[framework_id]["protocol"],
        }

    def unbind_asset(self, asset_id):
        """Remove framework binding for an asset."""
        with self._lock:
            removed = self.asset_bindings.pop(asset_id, None)
            self.stats["bindings"] = len(self.asset_bindings)
        if not removed:
            return {"error": f"Asset {asset_id} not bound"}
        return {"status": "unbound", "asset_id": asset_id}

    def translate_command(self, asset_id, amos_command, params=None):
        """Translate an AMOS command to the asset's framework protocol.

        Args:
            asset_id:      Target asset
            amos_command:  AMOS-standard command (WAYPOINT, RTL, ORBIT, etc.)
            params:        Command parameters (lat, lng, alt, speed, etc.)

        Returns:
            dict with translated command or error
        """
        params = params or {}
        framework_id = self.asset_bindings.get(asset_id)

        if not framework_id:
            # Auto-detect from domain
            framework_id = self._auto_detect_framework(asset_id, params)
            if not framework_id:
                self.stats["commands_failed"] += 1
                return {"error": f"Asset {asset_id} not bound to any framework",
                        "hint": "Use bind_asset() first or provide asset domain"}

        mapping_key = (amos_command.upper(), framework_id)
        mapping = COMMAND_MAP.get(mapping_key)

        if not mapping:
            self.stats["commands_failed"] += 1
            fw = FRAMEWORK_CATALOG[framework_id]
            return {
                "error": f"Command {amos_command} not supported on {framework_id}",
                "supported": fw["commands"],
            }

        translated = {
            "asset_id": asset_id,
            "framework": framework_id,
            "protocol": FRAMEWORK_CATALOG[framework_id]["protocol"],
            "amos_command": amos_command.upper(),
            "translated": {**mapping, **params},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            self.stats["commands_translated"] += 1
            self.command_log.append(translated)
            if len(self.command_log) > 500:
                self.command_log = self.command_log[-500:]

        return translated

    def get_binding(self, asset_id):
        """Get framework binding for an asset."""
        fw_id = self.asset_bindings.get(asset_id)
        if not fw_id:
            return None
        return {
            "asset_id": asset_id,
            "framework": fw_id,
            **FRAMEWORK_CATALOG[fw_id],
        }

    def list_bindings(self):
        """List all asset-to-framework bindings."""
        return [
            {"asset_id": aid, "framework": fid,
             "protocol": FRAMEWORK_CATALOG[fid]["protocol"]}
            for aid, fid in self.asset_bindings.items()
        ]

    @staticmethod
    def list_frameworks():
        """Return all supported autonomy frameworks."""
        return list(FRAMEWORK_CATALOG.values())

    def _auto_detect_framework(self, asset_id, params):
        """Try to guess the right framework from context."""
        domain = params.get("domain", "")
        if domain == "air":
            return "PX4"
        elif domain == "ground":
            return "ROS2_NAV2"
        return None

    def summary(self):
        return {
            "bindings": len(self.asset_bindings),
            "frameworks": len(FRAMEWORK_CATALOG),
            "stats": dict(self.stats),
        }


# ═══════════════════════════════════════════════════════════
#  BLUE UAS REGISTRY
# ═══════════════════════════════════════════════════════════

# Blue UAS approved platforms with AMOS-compatible capability profiles
BLUE_UAS_CATALOG = [
    {
        "model_id": "SKYDIO-X10",
        "manufacturer": "Skydio",
        "model": "X10",
        "category": "sUAS",
        "max_takeoff_weight_kg": 2.2,
        "endurance_min": 35,
        "max_speed_kts": 35,
        "range_km": 6,
        "domains": ["air"],
        "sensors": ["EO/IR", "LIDAR"],
        "weapons": [],
        "autonomy_framework": "PX4",
        "comms": ["WiFi", "LTE", "UHF"],
        "swap_c": {"size": 0.15, "weight_kg": 2.2, "power_w": 180, "cost_usd": 12000},
        "blue_uas_approved": True,
        "description": "AI-powered autonomous drone with obstacle avoidance and 3D scanning",
    },
    {
        "model_id": "SHIELD-AI-V-BAT",
        "manufacturer": "Shield AI",
        "model": "V-BAT",
        "category": "Group 3 VTOL",
        "max_takeoff_weight_kg": 50,
        "endurance_min": 480,
        "max_speed_kts": 90,
        "range_km": 100,
        "domains": ["air"],
        "sensors": ["EO/IR", "AESA_RADAR", "SIGINT"],
        "weapons": [],
        "autonomy_framework": "PX4",
        "comms": ["SATCOM", "UHF", "L_BAND"],
        "swap_c": {"size": 0.5, "weight_kg": 50, "power_w": 2500, "cost_usd": 800000},
        "blue_uas_approved": True,
        "description": "VTOL UAS with 8hr endurance for persistent ISR operations",
    },
    {
        "model_id": "AEROVIRONMENT-SWITCHBLADE-600",
        "manufacturer": "AeroVironment",
        "model": "Switchblade 600",
        "category": "Loitering Munition",
        "max_takeoff_weight_kg": 23,
        "endurance_min": 40,
        "max_speed_kts": 100,
        "range_km": 40,
        "domains": ["air"],
        "sensors": ["EO/IR"],
        "weapons": ["WARHEAD_AT"],
        "autonomy_framework": "ARDUPILOT",
        "comms": ["UHF", "L_BAND"],
        "swap_c": {"size": 0.35, "weight_kg": 23, "power_w": 800, "cost_usd": 120000},
        "blue_uas_approved": True,
        "description": "Anti-armor loitering munition with precision strike capability",
    },
    {
        "model_id": "L3HARRIS-FVR-90",
        "manufacturer": "L3Harris",
        "model": "FVR-90",
        "category": "Group 2 Fixed-Wing",
        "max_takeoff_weight_kg": 11.3,
        "endurance_min": 540,
        "max_speed_kts": 70,
        "range_km": 90,
        "domains": ["air"],
        "sensors": ["EO/IR", "SIGINT", "AESA_RADAR"],
        "weapons": [],
        "autonomy_framework": "ARDUPILOT",
        "comms": ["SATCOM", "UHF", "C_BAND"],
        "swap_c": {"size": 0.4, "weight_kg": 11.3, "power_w": 400, "cost_usd": 250000},
        "blue_uas_approved": True,
        "description": "Long-endurance fixed-wing for persistent surveillance",
    },
    {
        "model_id": "TEAL-GOLDEN-EAGLE",
        "manufacturer": "Teal Drones",
        "model": "Golden Eagle 2",
        "category": "sUAS",
        "max_takeoff_weight_kg": 1.8,
        "endurance_min": 70,
        "max_speed_kts": 40,
        "range_km": 4,
        "domains": ["air"],
        "sensors": ["EO/IR"],
        "weapons": [],
        "autonomy_framework": "PX4",
        "comms": ["WiFi", "AES256_MESH"],
        "swap_c": {"size": 0.12, "weight_kg": 1.8, "power_w": 150, "cost_usd": 8000},
        "blue_uas_approved": True,
        "description": "Ruggedized sUAS for dismounted infantry operations",
    },
    {
        "model_id": "ALTAVIAN-NOVA-F7200",
        "manufacturer": "Altavian",
        "model": "Nova F7200",
        "category": "Group 2 Fixed-Wing",
        "max_takeoff_weight_kg": 9.5,
        "endurance_min": 360,
        "max_speed_kts": 55,
        "range_km": 50,
        "domains": ["air"],
        "sensors": ["EO/IR", "LIDAR", "MULTISPECTRAL"],
        "weapons": [],
        "autonomy_framework": "ARDUPILOT",
        "comms": ["UHF", "L_BAND", "LTE"],
        "swap_c": {"size": 0.35, "weight_kg": 9.5, "power_w": 300, "cost_usd": 150000},
        "blue_uas_approved": True,
        "description": "Mapping and survey fixed-wing with multi-sensor payload",
    },
    {
        "model_id": "GHOST-ROBOTICS-VISION60",
        "manufacturer": "Ghost Robotics",
        "model": "Vision 60",
        "category": "UGV Quadruped",
        "max_takeoff_weight_kg": 51,
        "endurance_min": 180,
        "max_speed_kts": 5,
        "range_km": 10,
        "domains": ["ground"],
        "sensors": ["EO/IR", "LIDAR", "ACOUSTIC"],
        "weapons": [],
        "autonomy_framework": "ROS2_NAV2",
        "comms": ["WiFi", "UHF", "MESH"],
        "swap_c": {"size": 0.6, "weight_kg": 51, "power_w": 600, "cost_usd": 175000},
        "blue_uas_approved": True,
        "description": "All-terrain quadruped robot for perimeter security and patrol",
    },
    {
        "model_id": "BOSTON-DYNAMICS-SPOT",
        "manufacturer": "Boston Dynamics",
        "model": "Spot",
        "category": "UGV Quadruped",
        "max_takeoff_weight_kg": 32,
        "endurance_min": 90,
        "max_speed_kts": 3,
        "range_km": 5,
        "domains": ["ground"],
        "sensors": ["EO/IR", "LIDAR", "ACOUSTIC"],
        "weapons": [],
        "autonomy_framework": "ROS2_NAV2",
        "comms": ["WiFi", "LTE"],
        "swap_c": {"size": 0.5, "weight_kg": 32, "power_w": 450, "cost_usd": 75000},
        "blue_uas_approved": True,
        "description": "Agile quadruped robot for inspection and ISR operations",
    },
]


class BlueUASRegistry:
    """Registry of Blue UAS approved platforms with AMOS capability profiles.

    Enables the task allocator to know exactly what each airframe can do
    when selecting assets for mission assignment.
    """

    def __init__(self):
        self.catalog = {p["model_id"]: dict(p) for p in BLUE_UAS_CATALOG}

    def lookup(self, model_id):
        """Get a Blue UAS profile by model ID."""
        return self.catalog.get(model_id)

    def search(self, query="", domain=None, has_weapons=None, limit=20):
        """Search Blue UAS catalog.

        Args:
            query:       Free-text search across name/manufacturer/description
            domain:      Filter by domain (air, ground, maritime)
            has_weapons: Filter by weapon capability
            limit:       Max results

        Returns:
            list of matching profiles
        """
        results = []
        q = query.lower()
        for p in self.catalog.values():
            # Text search
            if q:
                searchable = f"{p['manufacturer']} {p['model']} {p['description']} {p['category']}".lower()
                if q not in searchable:
                    continue
            # Domain filter
            if domain and domain.lower() not in [d.lower() for d in p["domains"]]:
                continue
            # Weapon filter
            if has_weapons is True and not p["weapons"]:
                continue
            if has_weapons is False and p["weapons"]:
                continue
            results.append(p)
            if len(results) >= limit:
                break
        return results

    def get_by_framework(self, framework_id):
        """Get all platforms using a specific autonomy framework."""
        return [p for p in self.catalog.values()
                if p.get("autonomy_framework") == framework_id]

    def get_sensors_for_model(self, model_id):
        """Get sensor capabilities for a specific model."""
        p = self.catalog.get(model_id)
        if not p:
            return None
        return {
            "model_id": model_id,
            "sensors": p["sensors"],
            "endurance_min": p["endurance_min"],
            "range_km": p["range_km"],
            "comms": p["comms"],
        }

    def list_all(self):
        """Return all Blue UAS profiles."""
        return list(self.catalog.values())

    def summary(self):
        domains = {}
        frameworks = {}
        for p in self.catalog.values():
            for d in p["domains"]:
                domains[d] = domains.get(d, 0) + 1
            fw = p.get("autonomy_framework", "unknown")
            frameworks[fw] = frameworks.get(fw, 0) + 1
        return {
            "total_platforms": len(self.catalog),
            "by_domain": domains,
            "by_framework": frameworks,
        }


# ═══════════════════════════════════════════════════════════
#  INTEGRATION HEALTH DASHBOARD
# ═══════════════════════════════════════════════════════════

class IntegrationHealthDashboard:
    """Aggregates health status for all integration bridges.

    Provides a single-pane view of which bridges are connected, their
    throughput, error rates, and any alerts.
    """

    # Well-known bridge names and their expected protocols
    KNOWN_BRIDGES = {
        "px4": {"protocol": "MAVLink", "description": "PX4 Autopilot"},
        "ardupilot": {"protocol": "MAVLink", "description": "ArduPilot"},
        "ros2": {"protocol": "ROS2", "description": "ROS 2 Bridge"},
        "dimos": {"protocol": "DimOS", "description": "DimOS Bipedal Robots"},
        "atak": {"protocol": "CoT", "description": "ATAK/TAK"},
        "link16": {"protocol": "Link-16", "description": "Link-16 Tactical Data"},
        "mqtt": {"protocol": "MQTT", "description": "MQTT Broker"},
        "adsb": {"protocol": "ADS-B", "description": "ADS-B Aircraft Tracking"},
        "ais": {"protocol": "AIS", "description": "AIS Maritime Tracking"},
        "lora": {"protocol": "LoRa", "description": "LoRa Mesh Network"},
        "meshtastic": {"protocol": "Meshtastic", "description": "Meshtastic Radio Mesh"},
        "cot": {"protocol": "CoT", "description": "Cursor on Target Receiver"},
    }

    def __init__(self):
        self._lock = threading.Lock()
        self.bridge_status = {}   # bridge_id → {connected, last_activity, stats}
        self.alerts = []
        self.check_history = []

    def register_bridge(self, bridge_id, protocol="", connected=False, stats=None):
        """Register or update a bridge's status.

        Args:
            bridge_id:  Bridge identifier (e.g., 'px4', 'ros2')
            protocol:   Protocol name
            connected:  Whether the bridge is currently connected
            stats:      Dict with messages_in, messages_out, errors, etc.
        """
        known = self.KNOWN_BRIDGES.get(bridge_id, {})
        with self._lock:
            self.bridge_status[bridge_id] = {
                "bridge_id": bridge_id,
                "protocol": protocol or known.get("protocol", "unknown"),
                "description": known.get("description", bridge_id),
                "connected": connected,
                "last_check": datetime.now(timezone.utc).isoformat(),
                "stats": stats or {},
            }

    def update_from_object(self, bridge_id, bridge_obj):
        """Extract status from a bridge object with get_status() method."""
        try:
            if hasattr(bridge_obj, "get_status"):
                status = bridge_obj.get_status()
            elif hasattr(bridge_obj, "health_check"):
                status = bridge_obj.health_check()
            else:
                status = {}

            connected = status.get("connected", False) or status.get("available", False)
            stats = status.get("stats", {})
            protocol = status.get("protocol", "")

            self.register_bridge(bridge_id, protocol=protocol,
                                 connected=connected, stats=stats)
        except Exception:
            self.register_bridge(bridge_id, connected=False,
                                 stats={"error": "status_check_failed"})

    def check_all(self, bridges_dict):
        """Update status for all bridges from a dict of {id: bridge_obj}.

        Args:
            bridges_dict: dict of bridge_id → bridge object
        """
        for bid, bobj in bridges_dict.items():
            if bobj is not None:
                self.update_from_object(bid, bobj)

        # Generate alerts
        self._evaluate_alerts()

        # Record check
        self.check_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "connected": sum(1 for b in self.bridge_status.values() if b["connected"]),
            "total": len(self.bridge_status),
        })
        if len(self.check_history) > 100:
            self.check_history = self.check_history[-100:]

    def _evaluate_alerts(self):
        """Generate alerts for disconnected or unhealthy bridges."""
        self.alerts = []
        for bid, b in self.bridge_status.items():
            if not b["connected"]:
                self.alerts.append({
                    "bridge_id": bid,
                    "severity": "warning",
                    "message": f"{b['description']} ({b['protocol']}) is disconnected",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            errors = b.get("stats", {}).get("errors", 0)
            if errors > 10:
                self.alerts.append({
                    "bridge_id": bid,
                    "severity": "error",
                    "message": f"{b['description']} has {errors} errors",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

    def get_dashboard(self):
        """Return full dashboard status."""
        total = len(self.bridge_status)
        connected = sum(1 for b in self.bridge_status.values() if b["connected"])
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_bridges": total,
                "connected": connected,
                "disconnected": total - connected,
                "health_pct": round(connected / total * 100, 1) if total else 0,
            },
            "bridges": list(self.bridge_status.values()),
            "alerts": self.alerts,
        }

    def get_bridge(self, bridge_id):
        """Get status of a specific bridge."""
        return self.bridge_status.get(bridge_id)

    def list_connected(self):
        """List only connected bridges."""
        return [b for b in self.bridge_status.values() if b["connected"]]

    def list_disconnected(self):
        """List only disconnected bridges."""
        return [b for b in self.bridge_status.values() if not b["connected"]]

    def summary(self):
        total = len(self.bridge_status)
        connected = sum(1 for b in self.bridge_status.values() if b["connected"])
        return {
            "total_bridges": total,
            "connected": connected,
            "disconnected": total - connected,
            "alerts": len(self.alerts),
        }


# ═══════════════════════════════════════════════════════════
#  INTEROP ORCHESTRATOR — Top-level facade
# ═══════════════════════════════════════════════════════════

class InteropOrchestrator:
    """Top-level orchestrator for all interoperability components."""

    def __init__(self):
        self.autonomy = AutonomyAbstraction()
        self.blue_uas = BlueUASRegistry()
        self.health = IntegrationHealthDashboard()

    def get_status(self):
        """Full interop layer status."""
        return {
            "autonomy_abstraction": self.autonomy.summary(),
            "blue_uas_registry": self.blue_uas.summary(),
            "integration_health": self.health.summary(),
        }
