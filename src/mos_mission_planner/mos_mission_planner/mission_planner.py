"""
MOS Mission Planner — MERPH Brain (Full Version)
Mission Execution, Resource Planning & Human-integration

Supports all 6 Mavrix1 mission sets:
  1. ISR — Intelligence, Surveillance, Reconnaissance
  2. SECURITY — Force Protection, Perimeter Defense
  3. PRECISION_EFFECTS — Targeting, Strike Coordination
  4. LOGISTICS — Resupply, Casualty Evacuation
  5. SAR — Search and Rescue
  6. EW_SIGINT — Electronic Warfare, Signals Intelligence

Each mission type decomposes into domain-specific task chains
with priority-weighted asset allocation.
"""

import rclpy
from rclpy.node import Node
from mos_interfaces.msg import MissionIntent, TaskOrder
from std_msgs.msg import String

import json
import uuid
import time


# ── Mission Decomposition Templates ──
# Each mission type breaks down into ordered task chains
# with domain preferences and required capabilities.

MISSION_TEMPLATES = {
    "ISR": {
        "name": "Intelligence, Surveillance, Reconnaissance",
        "tasks": [
            {"type": "DEPLOY_ISR",    "domain": "AIR",      "desc": "Deploy aerial ISR platforms to AO",
             "duration_min": 5,  "params": ["altitude=150", "pattern=RACETRACK"]},
            {"type": "ROUTE_RECON",   "domain": "AIR",      "desc": "Conduct route reconnaissance",
             "duration_min": 20, "params": ["sensor=EO_IR", "coverage=100pct"]},
            {"type": "GROUND_RECON",  "domain": "GROUND",   "desc": "Advance ground sensors along axis",
             "duration_min": 30, "params": ["formation=WEDGE", "speed=CAUTIOUS"]},
            {"type": "SIGNALS_SCAN",  "domain": "AIR",      "desc": "Passive SIGINT collection",
             "duration_min": 15, "params": ["band=WIDEBAND", "mode=PASSIVE"]},
            {"type": "RELAY",         "domain": "AIR",      "desc": "Establish comms relay overhead",
             "duration_min": 60, "params": ["altitude=500", "mode=MESH_RELAY"]},
            {"type": "OBSERVE",       "domain": "AIR",      "desc": "Persistent overwatch of NAIs",
             "duration_min": 45, "params": ["pattern=ORBIT", "sensor=MULTI"]},
        ],
    },
    "SECURITY": {
        "name": "Force Protection & Perimeter Defense",
        "tasks": [
            {"type": "ESTABLISH_OP",  "domain": "GROUND",   "desc": "Establish observation posts",
             "duration_min": 10, "params": ["sectors=4", "overlap=15deg"]},
            {"type": "PATROL_ROUTE",  "domain": "GROUND",   "desc": "Conduct mounted patrol routes",
             "duration_min": 60, "params": ["pattern=RANDOM", "speed=PATROL"]},
            {"type": "AERIAL_OVERWATCH", "domain": "AIR",   "desc": "Continuous aerial overwatch",
             "duration_min": 45, "params": ["altitude=200", "pattern=FIGURE8"]},
            {"type": "TRIPWIRE",      "domain": "GROUND",   "desc": "Deploy sensor tripwire line",
             "duration_min": 15, "params": ["sensor_type=ACOUSTIC_SEISMIC", "spacing=50m"]},
            {"type": "QRF_STANDBY",   "domain": "GROUND",   "desc": "Position quick reaction force",
             "duration_min": 0,  "params": ["readiness=2MIN", "loadout=HEAVY"]},
            {"type": "COUNTER_UAS",   "domain": "AIR",      "desc": "Counter-UAS patrol screen",
             "duration_min": 60, "params": ["altitude=100", "sensor=RADAR_RF"]},
        ],
    },
    "PRECISION_EFFECTS": {
        "name": "Precision Strike & Effects Coordination",
        "tasks": [
            {"type": "TARGET_DEVELOP","domain": "AIR",      "desc": "Develop target with ISR",
             "duration_min": 10, "params": ["sensor=EO_IR", "patt=ORBIT"]},
            {"type": "PID_CONFIRM",   "domain": "AIR",      "desc": "Positive ID confirmation",
             "duration_min": 5,  "params": ["sensor=ZOOM_EO", "record=TRUE"]},
            {"type": "STRIKE_COORD",  "domain": "AIR",      "desc": "Coordinate strike geometry",
             "duration_min": 3,  "params": ["deconflict=TRUE", "clearance=HPL_REQUIRED"]},
            {"type": "EFFECTS_DELIVERY","domain": "AIR",     "desc": "Deliver precision effects",
             "duration_min": 1,  "params": ["method=DIRECT", "munition=GUIDED"]},
            {"type": "BDA",           "domain": "AIR",      "desc": "Battle damage assessment",
             "duration_min": 10, "params": ["sensor=EO_IR", "passes=2"]},
            {"type": "SCREEN",        "domain": "GROUND",   "desc": "Ground screen for squirters",
             "duration_min": 30, "params": ["formation=LINE", "spacing=100m"]},
        ],
    },
    "LOGISTICS": {
        "name": "Resupply & Casualty Evacuation",
        "tasks": [
            {"type": "ROUTE_CLEAR",   "domain": "AIR",      "desc": "Clear supply route ahead",
             "duration_min": 15, "params": ["altitude=100", "sensor=EO_IR"]},
            {"type": "SUPPLY_MOVE",   "domain": "GROUND",   "desc": "Move supply vehicles to objective",
             "duration_min": 30, "params": ["cargo=AMMO_WATER", "speed=BEST"]},
            {"type": "AERIAL_RESUPPLY","domain": "AIR",      "desc": "Drone resupply drop",
             "duration_min": 10, "params": ["payload=EMERGENCY", "drop=PRECISION"]},
            {"type": "CASEVAC_PREP",  "domain": "GROUND",   "desc": "Prepare casualty collection point",
             "duration_min": 5,  "params": ["security=LOCAL", "marking=IR_STROBE"]},
            {"type": "CASEVAC_MOVE",  "domain": "GROUND",   "desc": "Transport casualties to CCP",
             "duration_min": 20, "params": ["priority=URGENT", "route=SECURE"]},
            {"type": "OVERWATCH",     "domain": "AIR",      "desc": "Security overwatch for convoy",
             "duration_min": 45, "params": ["altitude=200", "standoff=500m"]},
        ],
    },
    "SAR": {
        "name": "Search and Rescue",
        "tasks": [
            {"type": "SEARCH_GRID",   "domain": "AIR",      "desc": "Aerial grid search pattern",
             "duration_min": 30, "params": ["pattern=EXPANDING_SQUARE", "altitude=80"]},
            {"type": "THERMAL_SCAN",  "domain": "AIR",      "desc": "IR/thermal sweep for survivors",
             "duration_min": 20, "params": ["sensor=IR_THERMAL", "sensitivity=HIGH"]},
            {"type": "GROUND_SWEEP",  "domain": "GROUND",   "desc": "Ground team systematic sweep",
             "duration_min": 45, "params": ["formation=LINE", "spacing=25m"]},
            {"type": "MARITIME_SEARCH","domain": "MARITIME", "desc": "Maritime surface search",
             "duration_min": 30, "params": ["pattern=SECTOR", "speed=SEARCH"]},
            {"type": "BEACON_LOCATE", "domain": "AIR",      "desc": "Locate emergency beacons",
             "duration_min": 10, "params": ["freq=406MHZ", "mode=DF"]},
            {"type": "EXTRACT",       "domain": "GROUND",   "desc": "Extract and secure survivors",
             "duration_min": 15, "params": ["method=GROUND", "security=LOCAL"]},
            {"type": "RELAY",         "domain": "AIR",      "desc": "Comms relay for SAR coordination",
             "duration_min": 60, "params": ["altitude=500", "mode=MESH_RELAY"]},
        ],
    },
    "EW_SIGINT": {
        "name": "Electronic Warfare & Signals Intelligence",
        "tasks": [
            {"type": "SIGINT_COLLECT","domain": "AIR",      "desc": "Airborne SIGINT collection",
             "duration_min": 30, "params": ["band=30MHZ_6GHZ", "mode=INTERCEPT"]},
            {"type": "EMITTER_LOCATE","domain": "AIR",      "desc": "Geolocate hostile emitters",
             "duration_min": 15, "params": ["method=TDOA", "accuracy=50m"]},
            {"type": "GROUND_SIGINT", "domain": "GROUND",   "desc": "Ground-based signals collection",
             "duration_min": 45, "params": ["band=VHF_UHF", "mode=MONITOR"]},
            {"type": "JAMMING",       "domain": "AIR",      "desc": "Targeted communications jamming",
             "duration_min": 10, "params": ["target=SPECIFIC", "power=FOCUSED", "clearance=HPL_REQUIRED"]},
            {"type": "CYBER_PROBE",   "domain": "GROUND",   "desc": "Network reconnaissance probe",
             "duration_min": 20, "params": ["mode=PASSIVE", "target=WIFI_CELLULAR"]},
            {"type": "MARITIME_EW",   "domain": "MARITIME",  "desc": "Maritime electronic surveillance",
             "duration_min": 30, "params": ["band=RADAR_COMMS", "mode=PASSIVE"]},
        ],
    },
}


class MissionPlanner(Node):
    """
    Full MOS Mission Planner — decomposes commander's intent
    into domain-specific task chains for all 6 Mavrix1 mission sets.
    Supports simultaneous multi-mission management.
    """

    def __init__(self):
        super().__init__("mos_mission_planner")
        self.get_logger().info("=" * 60)
        self.get_logger().info("  MOS MISSION PLANNER — MERPH BRAIN (FULL)")
        self.get_logger().info("  Supported mission types:")
        for mtype in MISSION_TEMPLATES:
            name = MISSION_TEMPLATES[mtype]["name"]
            tasks = len(MISSION_TEMPLATES[mtype]["tasks"])
            self.get_logger().info(f"    ✓ {mtype:22s} ({tasks} task templates)")
        self.get_logger().info("=" * 60)

        # Active missions tracking
        self.active_missions = {}

        # Subscribers
        self.create_subscription(
            MissionIntent, "/mos/mission/intent",
            self._on_mission_intent, 10
        )

        # Publishers
        self._task_pub = self.create_publisher(TaskOrder, "/mos/tasks/orders", 10)
        self._status_pub = self.create_publisher(String, "/mos/mission/status", 10)

        # Mission status check every 10 seconds
        self.create_timer(10.0, self._mission_status_check)

        self.get_logger().info("Mission Planner online. Awaiting commander's intent...")

    def _on_mission_intent(self, msg: MissionIntent):
        """Receive and decompose a mission intent."""
        self.get_logger().info("")
        self.get_logger().info("=" * 50)
        self.get_logger().info(f"  NEW MISSION ORDER RECEIVED")
        self.get_logger().info(f"  ID:       {msg.mission_id}")
        self.get_logger().info(f"  Type:     {msg.mission_type}")
        self.get_logger().info(f"  Intent:   {msg.commander_intent}")
        self.get_logger().info(f"  AO:       {msg.area_of_operations}")
        self.get_logger().info(f"  Priority: {msg.priority}")
        if msg.objectives:
            for obj in msg.objectives:
                self.get_logger().info(f"  Objective: {obj}")
        self.get_logger().info("=" * 50)

        template = MISSION_TEMPLATES.get(msg.mission_type)

        if not template:
            self.get_logger().error(
                f"Unknown mission type: {msg.mission_type}. "
                f"Valid types: {list(MISSION_TEMPLATES.keys())}"
            )
            self._publish_status(msg.mission_id, "REJECTED",
                                 f"Unknown mission type: {msg.mission_type}")
            return

        self.get_logger().info(
            f"[PLANNER] Decomposing {msg.mission_type}: {template['name']}"
        )

        # Track this mission
        mission_record = {
            "mission_id": msg.mission_id,
            "mission_type": msg.mission_type,
            "intent": msg.commander_intent,
            "ao": msg.area_of_operations,
            "priority": msg.priority,
            "status": "PLANNING",
            "tasks": [],
            "start_time": time.time(),
        }

        # Decompose into tasks
        task_count = 0
        for task_template in template["tasks"]:
            task_id = str(uuid.uuid4())
            task_count += 1

            # Build task order
            order = TaskOrder()
            order.task_id = task_id
            order.mission_id = msg.mission_id
            order.task_type = task_template["type"]
            order.priority = msg.priority
            order.assigned_asset_id = ""  # Will be assigned by allocator or sim

            # Merge template params with mission context
            params = list(task_template["params"])
            params.append(f"domain={task_template['domain']}")
            params.append(f"ao={msg.area_of_operations}")
            params.append(f"duration={task_template['duration_min']}min")
            params.append(f"description={task_template['desc']}")
            params.append(f"sequence={task_count}")
            order.parameters = params

            self._task_pub.publish(order)

            mission_record["tasks"].append({
                "task_id": task_id[:8],
                "type": task_template["type"],
                "domain": task_template["domain"],
                "desc": task_template["desc"],
                "status": "PUBLISHED",
            })

            self.get_logger().info(
                f"  [{task_count}] {task_template['type']:20s} "
                f"domain={task_template['domain']:10s} "
                f"→ {task_template['desc']}"
            )

        mission_record["status"] = "EXECUTING"
        self.active_missions[msg.mission_id] = mission_record

        self.get_logger().info(
            f"[PLANNER] Mission {msg.mission_id} decomposed into "
            f"{task_count} tasks across "
            f"{len(set(t['domain'] for t in template['tasks']))} domains"
        )

        self._publish_status(
            msg.mission_id, "EXECUTING",
            f"Decomposed into {task_count} tasks"
        )

    def _mission_status_check(self):
        """Periodic check and report on active missions."""
        if not self.active_missions:
            return

        self.get_logger().info(
            f"[PLANNER SITREP] Active missions: {len(self.active_missions)}"
        )
        for mid, mission in self.active_missions.items():
            elapsed = int(time.time() - mission["start_time"])
            self.get_logger().info(
                f"  {mid}: {mission['mission_type']} "
                f"status={mission['status']} "
                f"tasks={len(mission['tasks'])} "
                f"elapsed={elapsed}s"
            )

    def _publish_status(self, mission_id: str, status: str, detail: str):
        """Publish mission status update."""
        msg = String()
        msg.data = json.dumps({
            "mission_id": mission_id,
            "status": status,
            "detail": detail,
            "time": time.time(),
        })
        self._status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = MissionPlanner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
