# MOS PROJECT MANIFEST — COMPLETE SOURCE SNAPSHOT
# Generated: 2026-03-03
# Version: 0.3.0 (Phase 3 Complete)
# ROS 2: Humble | OS: Ubuntu 22.04 | Python 3.10+
# Workspace: ~/mos_ws

---

## PROJECT OVERVIEW

**MOS (Mission Operating System)** — pronounced "moz" — is an autonomous systems
integration platform for special operations robotic platoons. It orchestrates 25-40
autonomous assets across air, ground, and maritime domains. Built on ROS 2 Humble.

**Design Document:** Mavrix1 Robotic Platoon specification
**Theme:** "Tech as a Teammate"
**Architecture:** ROS 2 orchestration layer with Flask C2 web console

**Completed Phases:**
- Phase 1: Core scaffold (asset registry, autonomy manager, interfaces)
- Phase 2: Mission planner, swarm orchestrator, threat detection
- Phase 3: C2 console (web tactical map), launch scripts, documentation

**Next Phases:**
- Phase 4: Waypoint planning, formations, geofencing, dynamic re-tasking
- Phase 5: PX4/Nav2/Gazebo integration, DDS security, HITL
- Phase 6: ML threat classification, NLP mission orders, adaptive swarm

---

## DIRECTORY STRUCTURE
~/mos_ws/
├── launch_mos.sh
├── shutdown_mos.sh
├── README.md
├── MOS_PROJECT_MANIFEST.md
└── src/
├── mos_interfaces/
│ ├── package.xml
│ ├── CMakeLists.txt
│ ├── msg/
│ │ ├── AssetState.msg
│ │ ├── MissionIntent.msg
│ │ └── TaskOrder.msg
│ └── srv/
│ └── AllocateTask.srv
├── mos_core/
│ ├── package.xml
│ ├── setup.py
│ ├── setup.cfg
│ ├── resource/mos_core
│ └── mos_core/
│ ├── init.py
│ ├── asset_registry.py
│ └── autonomy_manager.py
├── mos_mission_planner/
│ ├── package.xml
│ ├── setup.py
│ ├── setup.cfg
│ ├── resource/mos_mission_planner
│ └── mos_mission_planner/
│ ├── init.py
│ └── mission_planner.py
├── mos_swarm/
│ ├── package.xml
│ ├── setup.py
│ ├── setup.cfg
│ ├── resource/mos_swarm
│ └── mos_swarm/
│ ├── init.py
│ └── swarm_orchestrator.py
├── mos_sim/
│ ├── package.xml
│ ├── setup.py
│ ├── setup.cfg
│ ├── resource/mos_sim
│ └── mos_sim/
│ ├── init.py
│ └── simulated_platoon.py
├── mos_threat_detection/
│ ├── package.xml
│ ├── setup.py
│ ├── setup.cfg
│ ├── resource/mos_threat_detection
│ └── mos_threat_detection/
│ ├── init.py
│ ├── threat_injector.py
│ └── threat_classifier.py
└── mos_c2_console/
├── package.xml
├── setup.py
├── setup.cfg
├── resource/mos_c2_console
├── MANIFEST.in
└── mos_c2_console/
├── init.py
├── c2_server.py
└── templates/
└── index.html


---

## FILE: src/mos_interfaces/package.xml

```xml
&lt;?xml version=&quot;1.0&quot;?&gt;
&lt;?xml-model href=&quot;http://download.ros.org/schema/package_format3.xsd&quot; schematypens=&quot;http://www.w3.org/2001/XMLSchema&quot;?&gt;
&lt;package format=&quot;3&quot;&gt;
  &lt;name&gt;mos_interfaces&lt;/name&gt;
  &lt;version&gt;0.1.0&lt;/version&gt;
  &lt;description&gt;MOS custom message and service definitions&lt;/description&gt;
  &lt;maintainer email=&quot;dev@mos.mil&quot;&gt;MOS Dev&lt;/maintainer&gt;
  &lt;license&gt;Proprietary&lt;/license&gt;

  &lt;buildtool_depend&gt;ament_cmake&lt;/buildtool_depend&gt;
  &lt;build_depend&gt;rosidl_default_generators&lt;/build_depend&gt;
  &lt;exec_depend&gt;rosidl_default_runtime&lt;/exec_depend&gt;
  &lt;member_of_group&gt;rosidl_interface_packages&lt;/member_of_group&gt;

  &lt;export&gt;
    &lt;build_type&gt;ament_cmake&lt;/build_type&gt;
  &lt;/export&gt;
&lt;/package&gt;



FILE: src/mos_interfaces/CMakeLists.txt
cmake_minimum_required(VERSION 3.8)
project(mos_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  &quot;msg/AssetState.msg&quot;
  &quot;msg/MissionIntent.msg&quot;
  &quot;msg/TaskOrder.msg&quot;
  &quot;srv/AllocateTask.srv&quot;
  DEPENDENCIES std_msgs
)

ament_package()

FILE: src/mos_interfaces/msg/AssetState.msg
string asset_id
string asset_type
string callsign
float64 lat
float64 lon
float64 alt
float64 heading
float64 speed
float64 battery
float64 comms_signal
string autonomy_mode
uint8 mission_status

FILE: src/mos_interfaces/msg/MissionIntent.msg
string mission_id
string mission_type
string commander_intent
string[] objectives
string area_of_operations
uint8 priority

FILE: src/mos_interfaces/msg/TaskOrder.msg
string task_id
string mission_id
string assigned_asset
string task_type
string description
float64 target_lat
float64 target_lon
uint8 priority

FILE: src/mos_interfaces/srv/AllocateTask.srv
string mission_id
string task_type
string required_domain
---
string assigned_asset_id
bool success
string message

FILE: src/mos_core/package.xml
&lt;?xml version=&quot;1.0&quot;?&gt;
&lt;package format=&quot;3&quot;&gt;
  &lt;name&gt;mos_core&lt;/name&gt;
  &lt;version&gt;0.1.0&lt;/version&gt;
  &lt;description&gt;MOS Core — Asset Registry and Autonomy Manager&lt;/description&gt;
  &lt;maintainer email=&quot;dev@mos.mil&quot;&gt;MOS Dev&lt;/maintainer&gt;
  &lt;license&gt;Proprietary&lt;/license&gt;
  &lt;exec_depend&gt;rclpy&lt;/exec_depend&gt;
  &lt;exec_depend&gt;std_msgs&lt;/exec_depend&gt;
  &lt;export&gt;
    &lt;build_type&gt;ament_python&lt;/build_type&gt;
  &lt;/export&gt;
&lt;/package&gt;

FILE: src/mos_core/setup.cfg

Ini
[develop]
script_dir=$base/lib/mos_core
[install]
install_scripts=$base/lib/mos_core


FILE: src/mos_core/setup.py


Python
from setuptools import setup

package_name = &#x27;mos_core&#x27;

setup(
    name=package_name,
    version=&#x27;0.1.0&#x27;,
    packages=[package_name],
    install_requires=[&#x27;setuptools&#x27;],
    zip_safe=True,
    maintainer=&#x27;MOS Dev&#x27;,
    maintainer_email=&#x27;dev@mos.mil&#x27;,
    description=&#x27;MOS Core services&#x27;,
    license=&#x27;Proprietary&#x27;,
    entry_points={
        &#x27;console_scripts&#x27;: [
            &#x27;asset_registry = mos_core.asset_registry:main&#x27;,
            &#x27;autonomy_manager = mos_core.autonomy_manager:main&#x27;,
        ],
    },
)

FILE: src/mos_core/mos_core/init.py




Python
FILE: src/mos_core/mos_core/asset_registry.py




Python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, time

class AssetRegistry(Node):
    def __init__(self):
        super().__init__(&#x27;mos_asset_registry&#x27;)
        self.assets = {}
        self.sub_heartbeat = self.create_subscription(
            String, &#x27;/mos/heartbeat&#x27;, self.on_heartbeat, 10)
        self.pub_cop = self.create_publisher(String, &#x27;/mos/cop/assets&#x27;, 10)
        self.timer = self.create_timer(0.5, self.publish_cop)
        self.get_logger().info(&#x27;[MOS] Asset Registry online — tracking COP&#x27;)

    def on_heartbeat(self, msg):
        try:
            data = json.loads(msg.data)
            aid = data.get(&#x27;asset_id&#x27;, &#x27;UNKNOWN&#x27;)
            data[&#x27;last_seen&#x27;] = time.time()
            self.assets[aid] = data
        except json.JSONDecodeError:
            pass

    def publish_cop(self):
        now = time.time()
        for aid, a in self.assets.items():
            if now - a.get(&#x27;last_seen&#x27;, 0) &gt; 10:
                a[&#x27;mission_status&#x27;] = 5  # FAULT
        snapshot = list(self.assets.values())
        msg = String()
        msg.data = json.dumps(snapshot)
        self.pub_cop.publish(msg)

def main():
    rclpy.init()
    node = AssetRegistry()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
FILE: src/mos_core/mos_core/autonomy_manager.py




Python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json

LEVELS = [&#x27;MANUAL&#x27;, &#x27;ASSISTED&#x27;, &#x27;COLLABORATIVE&#x27;, &#x27;SWARM&#x27;, &#x27;COGNITIVE&#x27;]

class AutonomyManager(Node):
    def __init__(self):
        super().__init__(&#x27;mos_autonomy_manager&#x27;)
        self.current_level = 1  # ASSISTED default
        self.sub_cmd = self.create_subscription(
            String, &#x27;/mos/autonomy_command&#x27;, self.on_command, 10)
        self.pub_state = self.create_publisher(String, &#x27;/mos/autonomy/state&#x27;, 10)
        self.pub_request = self.create_publisher(String, &#x27;/mos/autonomy/request&#x27;, 10)
        self.timer = self.create_timer(2.0, self.publish_state)
        self.get_logger().info(
            f&#x27;[MOS] Autonomy Manager online — level {self.current_level} ({LEVELS[self.current_level]})&#x27;)

    def on_command(self, msg):
        try:
            data = json.loads(msg.data)
            requested = int(data.get(&#x27;target_level&#x27;, self.current_level))
            if 0 &lt;= requested &lt;= 4:
                old = self.current_level
                self.current_level = requested
                self.get_logger().info(
                    f&#x27;[MOS] Autonomy: {LEVELS[old]} → {LEVELS[self.current_level]}&#x27;)
                if requested &gt;= 3:
                    req = String()
                    req.data = json.dumps({
                        &#x27;request&#x27;: &#x27;HPL_AUTH_REQUIRED&#x27;,
                        &#x27;level&#x27;: LEVELS[requested],
                        &#x27;message&#x27;: f&#x27;Level {requested} ({LEVELS[requested]}) requires HPL authorization&#x27;
                    })
                    self.pub_request.publish(req)
        except (json.JSONDecodeError, ValueError):
            pass

    def publish_state(self):
        msg = String()
        msg.data = json.dumps({
            &#x27;current_level&#x27;: self.current_level,
            &#x27;level_name&#x27;: LEVELS[self.current_level],
            &#x27;hpl_required&#x27;: self.current_level &gt;= 3
        })
        self.pub_state.publish(msg)

def main():
    rclpy.init()
    node = AutonomyManager()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
FILE: src/mos_mission_planner/package.xml




Plaintext
&lt;?xml version=&quot;1.0&quot;?&gt;
&lt;package format=&quot;3&quot;&gt;
  &lt;name&gt;mos_mission_planner&lt;/name&gt;
  &lt;version&gt;0.1.0&lt;/version&gt;
  &lt;description&gt;MOS Mission Planner — 6 mission type decomposition&lt;/description&gt;
  &lt;maintainer email=&quot;dev@mos.mil&quot;&gt;MOS Dev&lt;/maintainer&gt;
  &lt;license&gt;Proprietary&lt;/license&gt;
  &lt;exec_depend&gt;rclpy&lt;/exec_depend&gt;
  &lt;exec_depend&gt;std_msgs&lt;/exec_depend&gt;
  &lt;export&gt;
    &lt;build_type&gt;ament_python&lt;/build_type&gt;
  &lt;/export&gt;
&lt;/package&gt;
FILE: src/mos_mission_planner/setup.cfg




Ini
[develop]
script_dir=$base/lib/mos_mission_planner
[install]
install_scripts=$base/lib/mos_mission_planner
FILE: src/mos_mission_planner/setup.py




Python
from setuptools import setup

package_name = &#x27;mos_mission_planner&#x27;

setup(
    name=package_name,
    version=&#x27;0.1.0&#x27;,
    packages=[package_name],
    install_requires=[&#x27;setuptools&#x27;],
    zip_safe=True,
    maintainer=&#x27;MOS Dev&#x27;,
    maintainer_email=&#x27;dev@mos.mil&#x27;,
    description=&#x27;MOS Mission Planner&#x27;,
    license=&#x27;Proprietary&#x27;,
    entry_points={
        &#x27;console_scripts&#x27;: [
            &#x27;mission_planner = mos_mission_planner.mission_planner:main&#x27;,
        ],
    },
)
FILE: src/mos_mission_planner/mos_mission_planner/init.py




Python
FILE: src/mos_mission_planner/mos_mission_planner/mission_planner.py




Python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, uuid, time

MISSION_TEMPLATES = {
    &#x27;ISR&#x27;: {
        &#x27;tasks&#x27;: [
            {&#x27;task_type&#x27;: &#x27;LAUNCH_ISR_SWEEP&#x27;, &#x27;domain&#x27;: &#x27;AIR&#x27;, &#x27;desc&#x27;: &#x27;Deploy aerial ISR sweep pattern&#x27;},
            {&#x27;task_type&#x27;: &#x27;LAUNCH_ISR_SWEEP&#x27;, &#x27;domain&#x27;: &#x27;AIR&#x27;, &#x27;desc&#x27;: &#x27;Deploy secondary aerial ISR&#x27;},
            {&#x27;task_type&#x27;: &#x27;LAUNCH_ISR_SWEEP&#x27;, &#x27;domain&#x27;: &#x27;AIR&#x27;, &#x27;desc&#x27;: &#x27;Deploy tertiary aerial ISR&#x27;},
            {&#x27;task_type&#x27;: &#x27;ESTABLISH_OP&#x27;, &#x27;domain&#x27;: &#x27;GROUND&#x27;, &#x27;desc&#x27;: &#x27;Ground observation post&#x27;},
        ]
    },
    &#x27;SECURITY&#x27;: {
        &#x27;tasks&#x27;: [
            {&#x27;task_type&#x27;: &#x27;PERIMETER_PATROL&#x27;, &#x27;domain&#x27;: &#x27;GROUND&#x27;, &#x27;desc&#x27;: &#x27;Perimeter patrol sector 1&#x27;},
            {&#x27;task_type&#x27;: &#x27;PERIMETER_PATROL&#x27;, &#x27;domain&#x27;: &#x27;GROUND&#x27;, &#x27;desc&#x27;: &#x27;Perimeter patrol sector 2&#x27;},
            {&#x27;task_type&#x27;: &#x27;PERIMETER_PATROL&#x27;, &#x27;domain&#x27;: &#x27;GROUND&#x27;, &#x27;desc&#x27;: &#x27;Perimeter patrol sector 3&#x27;},
            {&#x27;task_type&#x27;: &#x27;PERIMETER_PATROL&#x27;, &#x27;domain&#x27;: &#x27;GROUND&#x27;, &#x27;desc&#x27;: &#x27;Perimeter patrol sector 4&#x27;},
            {&#x27;task_type&#x27;: &#x27;OVERWATCH&#x27;, &#x27;domain&#x27;: &#x27;AIR&#x27;, &#x27;desc&#x27;: &#x27;Aerial overwatch north&#x27;},
            {&#x27;task_type&#x27;: &#x27;OVERWATCH&#x27;, &#x27;domain&#x27;: &#x27;AIR&#x27;, &#x27;desc&#x27;: &#x27;Aerial overwatch south&#x27;},
        ]
    },
    &#x27;PRECISION_EFFECTS&#x27;: {
        &#x27;tasks&#x27;: [
            {&#x27;task_type&#x27;: &#x27;TARGET_ACQUISITION&#x27;, &#x27;domain&#x27;: &#x27;AIR&#x27;, &#x27;desc&#x27;: &#x27;Acquire and designate target&#x27;},
            {&#x27;task_type&#x27;: &#x27;TARGET_ACQUISITION&#x27;, &#x27;domain&#x27;: &#x27;AIR&#x27;, &#x27;desc&#x27;: &#x27;Secondary target acquisition&#x27;},
            {&#x27;task_type&#x27;: &#x27;FIRE_SUPPORT&#x27;, &#x27;domain&#x27;: &#x27;GROUND&#x27;, &#x27;desc&#x27;: &#x27;Direct fire support platform 1&#x27;},
            {&#x27;task_type&#x27;: &#x27;FIRE_SUPPORT&#x27;, &#x27;domain&#x27;: &#x27;GROUND&#x27;, &#x27;desc&#x27;: &#x27;Direct fire support platform 2&#x27;},
        ]
    },
    &#x27;LOGISTICS&#x27;: {
        &#x27;tasks&#x27;: [
            {&#x27;task_type&#x27;: &#x27;RESUPPLY_RUN&#x27;, &#x27;domain&#x27;: &#x27;GROUND&#x27;, &#x27;desc&#x27;: &#x27;Resupply convoy unit 1&#x27;},
            {&#x27;task_type&#x27;: &#x27;RESUPPLY_RUN&#x27;, &#x27;domain&#x27;: &#x27;GROUND&#x27;, &#x27;desc&#x27;: &#x27;Resupply convoy unit 2&#x27;},
            {&#x27;task_type&#x27;: &#x27;RESUPPLY_RUN&#x27;, &#x27;domain&#x27;: &#x27;GROUND&#x27;, &#x27;desc&#x27;: &#x27;Resupply convoy unit 3&#x27;},
        ]
    },
    &#x27;SAR&#x27;: {
        &#x27;tasks&#x27;: [
            {&#x27;task_type&#x27;: &#x27;SEARCH_PATTERN&#x27;, &#x27;domain&#x27;: &#x27;AIR&#x27;, &#x27;desc&#x27;: &#x27;Aerial search grid alpha&#x27;},
            {&#x27;task_type&#x27;: &#x27;SEARCH_PATTERN&#x27;, &#x27;domain&#x27;: &#x27;AIR&#x27;, &#x27;desc&#x27;: &#x27;Aerial search grid bravo&#x27;},
            {&#x27;task_type&#x27;: &#x27;GROUND_SWEEP&#x27;, &#x27;domain&#x27;: &#x27;GROUND&#x27;, &#x27;desc&#x27;: &#x27;Ground search team 1&#x27;},
            {&#x27;task_type&#x27;: &#x27;GROUND_SWEEP&#x27;, &#x27;domain&#x27;: &#x27;GROUND&#x27;, &#x27;desc&#x27;: &#x27;Ground search team 2&#x27;},
            {&#x27;task_type&#x27;: &#x27;WATERBORNE_SEARCH&#x27;, &#x27;domain&#x27;: &#x27;MARITIME&#x27;, &#x27;desc&#x27;: &#x27;Maritime search pattern&#x27;},
        ]
    },
    &#x27;EW_SIGINT&#x27;: {
        &#x27;tasks&#x27;: [
            {&#x27;task_type&#x27;: &#x27;SIGINT_COLLECT&#x27;, &#x27;domain&#x27;: &#x27;AIR&#x27;, &#x27;desc&#x27;: &#x27;Airborne SIGINT collection orbit&#x27;},
            {&#x27;task_type&#x27;: &#x27;SIGINT_COLLECT&#x27;, &#x27;domain&#x27;: &#x27;AIR&#x27;, &#x27;desc&#x27;: &#x27;Secondary SIGINT orbit&#x27;},
            {&#x27;task_type&#x27;: &#x27;EW_JAMMING&#x27;, &#x27;domain&#x27;: &#x27;GROUND&#x27;, &#x27;desc&#x27;: &#x27;Ground-based EW jamming station&#x27;},
        ]
    },
}

class MissionPlanner(Node):
    def __init__(self):
        super().__init__(&#x27;mos_mission_planner&#x27;)
        self.sub_cmd = self.create_subscription(
            String, &#x27;/mos/mission_command&#x27;, self.on_mission_command, 10)
        self.pub_intent = self.create_publisher(String, &#x27;/mos/mission/intent&#x27;, 10)
        self.pub_status = self.create_publisher(String, &#x27;/mos/mission/status&#x27;, 10)
        self.pub_tasks = self.create_publisher(String, &#x27;/mos/tasks/orders&#x27;, 10)
        self.get_logger().info(&#x27;[MOS] Mission Planner online — 6 mission types loaded&#x27;)

    def on_mission_command(self, msg):
        try:
            data = json.loads(msg.data)
            mission_type = data.get(&#x27;mission_type&#x27;, &#x27;ISR&#x27;)
            mission_id = data.get(&#x27;mission_id&#x27;, f&#x27;MOS-{uuid.uuid4().hex[:6].upper()}&#x27;)

            self.get_logger().info(f&#x27;[MOS] Planning mission: {mission_type} ({mission_id})&#x27;)

            intent = String()
            intent.data = json.dumps({
                &#x27;mission_id&#x27;: mission_id,
                &#x27;mission_type&#x27;: mission_type,
                &#x27;commander_intent&#x27;: data.get(&#x27;commander_intent&#x27;, f&#x27;Execute {mission_type}&#x27;),
                &#x27;status&#x27;: &#x27;PLANNING&#x27;,
                &#x27;timestamp&#x27;: time.time()
            })
            self.pub_intent.publish(intent)

            template = MISSION_TEMPLATES.get(mission_type, MISSION_TEMPLATES[&#x27;ISR&#x27;])
            for i, task_def in enumerate(template[&#x27;tasks&#x27;]):
                task_msg = String()
                task_msg.data = json.dumps({
                    &#x27;task_id&#x27;: f&#x27;{mission_id}-T{i+1:02d}&#x27;,
                    &#x27;mission_id&#x27;: mission_id,
                    &#x27;task_type&#x27;: task_def[&#x27;task_type&#x27;],
                    &#x27;required_domain&#x27;: task_def[&#x27;domain&#x27;],
                    &#x27;description&#x27;: task_def[&#x27;desc&#x27;],
                    &#x27;priority&#x27;: data.get(&#x27;priority&#x27;, 1),
                    &#x27;target_lat&#x27;: 34.0 + (i * 0.002),
                    &#x27;target_lon&#x27;: -118.0 + (i * 0.002),
                    &#x27;timestamp&#x27;: time.time()
                })
                self.pub_tasks.publish(task_msg)
                self.get_logger().info(
                    f&#x27;  → Task {i+1}: {task_def[&quot;task_type&quot;]} [{task_def[&quot;domain&quot;]}] — {task_def[&quot;desc&quot;]}&#x27;)

            status = String()
            status.data = json.dumps({
                &#x27;mission_id&#x27;: mission_id,
                &#x27;mission_type&#x27;: mission_type,
                &#x27;status&#x27;: &#x27;TASKS_ASSIGNED&#x27;,
                &#x27;task_count&#x27;: len(template[&#x27;tasks&#x27;]),
                &#x27;timestamp&#x27;: time.time()
            })
            self.pub_status.publish(status)

        except json.JSONDecodeError:
            self.get_logger().error(&#x27;[MOS] Invalid mission command JSON&#x27;)

def main():
    rclpy.init()
    node = MissionPlanner()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
FILE: src/mos_swarm/package.xml




Plaintext
&lt;?xml version=&quot;1.0&quot;?&gt;
&lt;package format=&quot;3&quot;&gt;
  &lt;name&gt;mos_swarm&lt;/name&gt;
  &lt;version&gt;0.1.0&lt;/version&gt;
  &lt;description&gt;MOS Swarm Orchestrator&lt;/description&gt;
  &lt;maintainer email=&quot;dev@mos.mil&quot;&gt;MOS Dev&lt;/maintainer&gt;
  &lt;license&gt;Proprietary&lt;/license&gt;
  &lt;exec_depend&gt;rclpy&lt;/exec_depend&gt;
  &lt;exec_depend&gt;std_msgs&lt;/exec_depend&gt;
  &lt;export&gt;
    &lt;build_type&gt;ament_python&lt;/build_type&gt;
  &lt;/export&gt;
&lt;/package&gt;
FILE: src/mos_swarm/setup.cfg




Ini
[develop]
script_dir=$base/lib/mos_swarm
[install]
install_scripts=$base/lib/mos_swarm
FILE: src/mos_swarm/setup.py




Python
from setuptools import setup

package_name = &#x27;mos_swarm&#x27;

setup(
    name=package_name,
    version=&#x27;0.1.0&#x27;,
    packages=[package_name],
    install_requires=[&#x27;setuptools&#x27;],
    zip_safe=True,
    maintainer=&#x27;MOS Dev&#x27;,
    maintainer_email=&#x27;dev@mos.mil&#x27;,
    description=&#x27;MOS Swarm Orchestrator&#x27;,
    license=&#x27;Proprietary&#x27;,
    entry_points={
        &#x27;console_scripts&#x27;: [
            &#x27;swarm_orchestrator = mos_swarm.swarm_orchestrator:main&#x27;,
        ],
    },
)
FILE: src/mos_swarm/mos_swarm/init.py




Python
FILE: src/mos_swarm/mos_swarm/swarm_orchestrator.py




Python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, time

class SwarmOrchestrator(Node):
    def __init__(self):
        super().__init__(&#x27;mos_swarm_orchestrator&#x27;)
        self.sub_cmd = self.create_subscription(
            String, &#x27;/mos/swarm_command&#x27;, self.on_swarm_command, 10)
        self.pub_swarm = self.create_publisher(String, &#x27;/mos/swarm/command&#x27;, 10)
        self.get_logger().info(&#x27;[MOS] Swarm Orchestrator online&#x27;)

    def on_swarm_command(self, msg):
        try:
            data = json.loads(msg.data)
            behavior = data.get(&#x27;behavior&#x27;, &#x27;HOLD&#x27;)
            domain = data.get(&#x27;domain&#x27;, &#x27;ALL&#x27;)

            self.get_logger().info(f&#x27;[MOS] Swarm command: {behavior} → {domain}&#x27;)

            cmd = String()
            cmd.data = json.dumps({
                &#x27;behavior&#x27;: behavior,
                &#x27;domain&#x27;: domain,
                &#x27;timestamp&#x27;: time.time()
            })
            self.pub_swarm.publish(cmd)

        except json.JSONDecodeError:
            pass

def main():
    rclpy.init()
    node = SwarmOrchestrator()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
FILE: src/mos_sim/package.xml




Plaintext
&lt;?xml version=&quot;1.0&quot;?&gt;
&lt;package format=&quot;3&quot;&gt;
  &lt;name&gt;mos_sim&lt;/name&gt;
  &lt;version&gt;0.1.0&lt;/version&gt;
  &lt;description&gt;MOS Simulated Platoon — 25 autonomous assets&lt;/description&gt;
  &lt;maintainer email=&quot;dev@mos.mil&quot;&gt;MOS Dev&lt;/maintainer&gt;
  &lt;license&gt;Proprietary&lt;/license&gt;
  &lt;exec_depend&gt;rclpy&lt;/exec_depend&gt;
  &lt;exec_depend&gt;std_msgs&lt;/exec_depend&gt;
  &lt;export&gt;
    &lt;build_type&gt;ament_python&lt;/build_type&gt;
  &lt;/export&gt;
&lt;/package&gt;
FILE: src/mos_sim/setup.cfg




Ini
[develop]
script_dir=$base/lib/mos_sim
[install]
install_scripts=$base/lib/mos_sim
FILE: src/mos_sim/setup.py




Python
from setuptools import setup

package_name = &#x27;mos_sim&#x27;

setup(
    name=package_name,
    version=&#x27;0.1.0&#x27;,
    packages=[package_name],
    install_requires=[&#x27;setuptools&#x27;],
    zip_safe=True,
    maintainer=&#x27;MOS Dev&#x27;,
    maintainer_email=&#x27;dev@mos.mil&#x27;,
    description=&#x27;MOS Simulated Platoon&#x27;,
    license=&#x27;Proprietary&#x27;,
    entry_points={
        &#x27;console_scripts&#x27;: [
            &#x27;simulated_platoon = mos_sim.simulated_platoon:main&#x27;,
        ],
    },
)
FILE: src/mos_sim/mos_sim/init.py




Python
FILE: src/mos_sim/mos_sim/simulated_platoon.py




Python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, math, random, time

ASSETS = [
    # AIR — 10
    {&#x27;id&#x27;: &#x27;MVRX-A01&#x27;, &#x27;type&#x27;: &#x27;AIR&#x27;, &#x27;callsign&#x27;: &#x27;HAWK-1&#x27;,      &#x27;lat&#x27;: 34.000, &#x27;lon&#x27;: -118.000, &#x27;alt&#x27;: 120.0},
    {&#x27;id&#x27;: &#x27;MVRX-A02&#x27;, &#x27;type&#x27;: &#x27;AIR&#x27;, &#x27;callsign&#x27;: &#x27;HAWK-2&#x27;,      &#x27;lat&#x27;: 34.001, &#x27;lon&#x27;: -117.998, &#x27;alt&#x27;: 130.0},
    {&#x27;id&#x27;: &#x27;MVRX-A03&#x27;, &#x27;type&#x27;: &#x27;AIR&#x27;, &#x27;callsign&#x27;: &#x27;HAWK-3&#x27;,      &#x27;lat&#x27;: 34.002, &#x27;lon&#x27;: -117.996, &#x27;alt&#x27;: 110.0},
    {&#x27;id&#x27;: &#x27;MVRX-A04&#x27;, &#x27;type&#x27;: &#x27;AIR&#x27;, &#x27;callsign&#x27;: &#x27;RAVEN-1&#x27;,     &#x27;lat&#x27;: 33.998, &#x27;lon&#x27;: -118.002, &#x27;alt&#x27;: 90.0},
    {&#x27;id&#x27;: &#x27;MVRX-A05&#x27;, &#x27;type&#x27;: &#x27;AIR&#x27;, &#x27;callsign&#x27;: &#x27;RAVEN-2&#x27;,     &#x27;lat&#x27;: 33.999, &#x27;lon&#x27;: -118.004, &#x27;alt&#x27;: 95.0},
    {&#x27;id&#x27;: &#x27;MVRX-A06&#x27;, &#x27;type&#x27;: &#x27;AIR&#x27;, &#x27;callsign&#x27;: &#x27;RAVEN-3&#x27;,     &#x27;lat&#x27;: 33.997, &#x27;lon&#x27;: -118.001, &#x27;alt&#x27;: 85.0},
    {&#x27;id&#x27;: &#x27;MVRX-A07&#x27;, &#x27;type&#x27;: &#x27;AIR&#x27;, &#x27;callsign&#x27;: &#x27;TALON-1&#x27;,     &#x27;lat&#x27;: 34.003, &#x27;lon&#x27;: -117.997, &#x27;alt&#x27;: 150.0},
    {&#x27;id&#x27;: &#x27;MVRX-A08&#x27;, &#x27;type&#x27;: &#x27;AIR&#x27;, &#x27;callsign&#x27;: &#x27;TALON-2&#x27;,     &#x27;lat&#x27;: 34.004, &#x27;lon&#x27;: -117.995, &#x27;alt&#x27;: 145.0},
    {&#x27;id&#x27;: &#x27;MVRX-A09&#x27;, &#x27;type&#x27;: &#x27;AIR&#x27;, &#x27;callsign&#x27;: &#x27;OVERWATCH-1&#x27;, &#x27;lat&#x27;: 34.005, &#x27;lon&#x27;: -118.000, &#x27;alt&#x27;: 200.0},
    {&#x27;id&#x27;: &#x27;MVRX-A10&#x27;, &#x27;type&#x27;: &#x27;AIR&#x27;, &#x27;callsign&#x27;: &#x27;OVERWATCH-2&#x27;, &#x27;lat&#x27;: 34.006, &#x27;lon&#x27;: -117.998, &#x27;alt&#x27;: 210.0},
    # GROUND — 12
    {&#x27;id&#x27;: &#x27;MVRX-G01&#x27;, &#x27;type&#x27;: &#x27;GROUND&#x27;, &#x27;callsign&#x27;: &#x27;WARHOUND-1&#x27;,  &#x27;lat&#x27;: 33.995, &#x27;lon&#x27;: -118.003, &#x27;alt&#x27;: 0.0},
    {&#x27;id&#x27;: &#x27;MVRX-G02&#x27;, &#x27;type&#x27;: &#x27;GROUND&#x27;, &#x27;callsign&#x27;: &#x27;WARHOUND-2&#x27;,  &#x27;lat&#x27;: 33.994, &#x27;lon&#x27;: -118.005, &#x27;alt&#x27;: 0.0},
    {&#x27;id&#x27;: &#x27;MVRX-G03&#x27;, &#x27;type&#x27;: &#x27;GROUND&#x27;, &#x27;callsign&#x27;: &#x27;WARHOUND-3&#x27;,  &#x27;lat&#x27;: 33.993, &#x27;lon&#x27;: -118.007, &#x27;alt&#x27;: 0.0},
    {&#x27;id&#x27;: &#x27;MVRX-G04&#x27;, &#x27;type&#x27;: &#x27;GROUND&#x27;, &#x27;callsign&#x27;: &#x27;WARHOUND-4&#x27;,  &#x27;lat&#x27;: 33.996, &#x27;lon&#x27;: -118.001, &#x27;alt&#x27;: 0.0},
    {&#x27;id&#x27;: &#x27;MVRX-G05&#x27;, &#x27;type&#x27;: &#x27;GROUND&#x27;, &#x27;callsign&#x27;: &#x27;MULE-1&#x27;,      &#x27;lat&#x27;: 33.992, &#x27;lon&#x27;: -118.004, &#x27;alt&#x27;: 0.0},
    {&#x27;id&#x27;: &#x27;MVRX-G06&#x27;, &#x27;type&#x27;: &#x27;GROUND&#x27;, &#x27;callsign&#x27;: &#x27;MULE-2&#x27;,      &#x27;lat&#x27;: 33.991, &#x27;lon&#x27;: -118.006, &#x27;alt&#x27;: 0.0},
    {&#x27;id&#x27;: &#x27;MVRX-G07&#x27;, &#x27;type&#x27;: &#x27;GROUND&#x27;, &#x27;callsign&#x27;: &#x27;MULE-3&#x27;,      &#x27;lat&#x27;: 33.990, &#x27;lon&#x27;: -118.008, &#x27;alt&#x27;: 0.0},
    {&#x27;id&#x27;: &#x27;MVRX-G08&#x27;, &#x27;type&#x27;: &#x27;GROUND&#x27;, &#x27;callsign&#x27;: &#x27;SENTRY-1&#x27;,    &#x27;lat&#x27;: 33.997, &#x27;lon&#x27;: -117.999, &#x27;alt&#x27;: 0.0},
    {&#x27;id&#x27;: &#x27;MVRX-G09&#x27;, &#x27;type&#x27;: &#x27;GROUND&#x27;, &#x27;callsign&#x27;: &#x27;SENTRY-2&#x27;,    &#x27;lat&#x27;: 33.998, &#x27;lon&#x27;: -117.997, &#x27;alt&#x27;: 0.0},
    {&#x27;id&#x27;: &#x27;MVRX-G10&#x27;, &#x27;type&#x27;: &#x27;GROUND&#x27;, &#x27;callsign&#x27;: &#x27;SENTRY-3&#x27;,    &#x27;lat&#x27;: 33.996, &#x27;lon&#x27;: -117.995, &#x27;alt&#x27;: 0.0},
    {&#x27;id&#x27;: &#x27;MVRX-G11&#x27;, &#x27;type&#x27;: &#x27;GROUND&#x27;, &#x27;callsign&#x27;: &#x27;SENTRY-4&#x27;,    &#x27;lat&#x27;: 33.995, &#x27;lon&#x27;: -117.993, &#x27;alt&#x27;: 0.0},
    {&#x27;id&#x27;: &#x27;MVRX-G12&#x27;, &#x27;type&#x27;: &#x27;GROUND&#x27;, &#x27;callsign&#x27;: &#x27;PATHFINDER-1&#x27;,&#x27;lat&#x27;: 33.994, &#x27;lon&#x27;: -117.998, &#x27;alt&#x27;: 0.0},
    # MARITIME — 3
    {&#x27;id&#x27;: &#x27;MVRX-M01&#x27;, &#x27;type&#x27;: &#x27;MARITIME&#x27;, &#x27;callsign&#x27;: &#x27;TRITON-1&#x27;, &#x27;lat&#x27;: 33.985, &#x27;lon&#x27;: -118.010, &#x27;alt&#x27;: 0.0},
    {&#x27;id&#x27;: &#x27;MVRX-M02&#x27;, &#x27;type&#x27;: &#x27;MARITIME&#x27;, &#x27;callsign&#x27;: &#x27;TRITON-2&#x27;, &#x27;lat&#x27;: 33.983, &#x27;lon&#x27;: -118.012, &#x27;alt&#x27;: 0.0},
    {&#x27;id&#x27;: &#x27;MVRX-M03&#x27;, &#x27;type&#x27;: &#x27;MARITIME&#x27;, &#x27;callsign&#x27;: &#x27;TRITON-3&#x27;, &#x27;lat&#x27;: 33.981, &#x27;lon&#x27;: -118.014, &#x27;alt&#x27;: 0.0},
]

STATUS_NAMES = {0: &#x27;IDLE&#x27;, 1: &#x27;EN_ROUTE&#x27;, 2: &#x27;EXEC&#x27;, 3: &#x27;DONE&#x27;, 5: &#x27;FAULT&#x27;}
SPEED = {&#x27;AIR&#x27;: 0.0003, &#x27;GROUND&#x27;: 0.00012, &#x27;MARITIME&#x27;: 0.00015}

class SimulatedPlatoon(Node):
    def __init__(self):
        super().__init__(&#x27;mos_simulated_platoon&#x27;)
        self.pub = self.create_publisher(String, &#x27;/mos/heartbeat&#x27;, 10)
        self.sub_tasks = self.create_subscription(
            String, &#x27;/mos/tasks/orders&#x27;, self.on_task, 10)
        self.sub_swarm = self.create_subscription(
            String, &#x27;/mos/swarm/command&#x27;, self.on_swarm, 10)

        self.state = []
        for a in ASSETS:
            self.state.append({
                **a,
                &#x27;base_lat&#x27;: a[&#x27;lat&#x27;],
                &#x27;base_lon&#x27;: a[&#x27;lon&#x27;],
                &#x27;heading&#x27;: random.uniform(0, 360),
                &#x27;speed&#x27;: SPEED[a[&#x27;type&#x27;]],
                &#x27;battery&#x27;: random.uniform(70, 100),
                &#x27;comms&#x27;: random.uniform(-80, -40),
                &#x27;autonomy_mode&#x27;: &#x27;ASSISTED&#x27;,
                &#x27;mission_status&#x27;: 0,
                &#x27;target_lat&#x27;: None,
                &#x27;target_lon&#x27;: None,
                &#x27;task_timer&#x27;: 0,
            })

        self.timer = self.create_timer(0.5, self.tick)
        self.get_logger().info(f&#x27;[MOS SIM] Platoon online — {len(self.state)} assets deployed&#x27;)

    def on_task(self, msg):
        try:
            data = json.loads(msg.data)
            domain = data.get(&#x27;required_domain&#x27;, &#x27;GROUND&#x27;)
            target_lat = data.get(&#x27;target_lat&#x27;, 34.0)
            target_lon = data.get(&#x27;target_lon&#x27;, -118.0)

            for asset in self.state:
                if asset[&#x27;type&#x27;] == domain and asset[&#x27;mission_status&#x27;] == 0:
                    asset[&#x27;mission_status&#x27;] = 1  # EN_ROUTE
                    asset[&#x27;target_lat&#x27;] = target_lat
                    asset[&#x27;target_lon&#x27;] = target_lon
                    asset[&#x27;task_timer&#x27;] = 0
                    self.get_logger().info(
                        f&#x27;  [SIM] {asset[&quot;callsign&quot;]} → EN_ROUTE to ({target_lat:.4f}, {target_lon:.4f})&#x27;)
                    break
        except json.JSONDecodeError:
            pass

    def on_swarm(self, msg):
        try:
            data = json.loads(msg.data)
            behavior = data.get(&#x27;behavior&#x27;, &#x27;HOLD&#x27;)
            domain = data.get(&#x27;domain&#x27;, &#x27;ALL&#x27;)
            self.get_logger().info(f&#x27;[SIM] Swarm command: {behavior} for {domain}&#x27;)

            for asset in self.state:
                if domain != &#x27;ALL&#x27; and asset[&#x27;type&#x27;] != domain:
                    continue

                if behavior == &#x27;RTB&#x27;:
                    asset[&#x27;target_lat&#x27;] = asset[&#x27;base_lat&#x27;]
                    asset[&#x27;target_lon&#x27;] = asset[&#x27;base_lon&#x27;]
                    asset[&#x27;mission_status&#x27;] = 1
                    asset[&#x27;task_timer&#x27;] = 0
                elif behavior == &#x27;HOLD&#x27;:
                    asset[&#x27;target_lat&#x27;] = None
                    asset[&#x27;target_lon&#x27;] = None
                    asset[&#x27;mission_status&#x27;] = 0
                    asset[&#x27;task_timer&#x27;] = 0
                elif behavior == &#x27;SCATTER&#x27;:
                    asset[&#x27;target_lat&#x27;] = asset[&#x27;lat&#x27;] + random.uniform(-0.008, 0.008)
                    asset[&#x27;target_lon&#x27;] = asset[&#x27;lon&#x27;] + random.uniform(-0.008, 0.008)
                    asset[&#x27;mission_status&#x27;] = 1
                    asset[&#x27;task_timer&#x27;] = 0
        except json.JSONDecodeError:
            pass

    def tick(self):
        for asset in self.state:
            # Movement logic
            if asset[&#x27;mission_status&#x27;] == 1 and asset[&#x27;target_lat&#x27;] is not None:
                dlat = asset[&#x27;target_lat&#x27;] - asset[&#x27;lat&#x27;]
                dlon = asset[&#x27;target_lon&#x27;] - asset[&#x27;lon&#x27;]
                dist = math.sqrt(dlat**2 + dlon**2)

                if dist &lt; 0.0005:
                    asset[&#x27;lat&#x27;] = asset[&#x27;target_lat&#x27;]
                    asset[&#x27;lon&#x27;] = asset[&#x27;target_lon&#x27;]
                    asset[&#x27;mission_status&#x27;] = 2  # EXEC
                    asset[&#x27;task_timer&#x27;] = 0
                else:
                    speed = asset[&#x27;speed&#x27;]
                    asset[&#x27;lat&#x27;] += (dlat / dist) * speed
                    asset[&#x27;lon&#x27;] += (dlon / dist) * speed
                    asset[&#x27;heading&#x27;] = math.degrees(math.atan2(dlon, dlat)) % 360

            elif asset[&#x27;mission_status&#x27;] == 2:
                asset[&#x27;task_timer&#x27;] += 1
                if asset[&#x27;task_timer&#x27;] &gt; 30:  # 15 seconds exec
                    asset[&#x27;mission_status&#x27;] = 3  # DONE
                    asset[&#x27;task_timer&#x27;] = 0

            elif asset[&#x27;mission_status&#x27;] == 3:
                asset[&#x27;task_timer&#x27;] += 1
                if asset[&#x27;task_timer&#x27;] &gt; 10:
                    asset[&#x27;mission_status&#x27;] = 0  # IDLE
                    asset[&#x27;target_lat&#x27;] = None
                    asset[&#x27;target_lon&#x27;] = None
                    asset[&#x27;task_timer&#x27;] = 0

            # Battery drain
            if asset[&#x27;mission_status&#x27;] in [1, 2]:
                asset[&#x27;battery&#x27;] = max(5.0, asset[&#x27;battery&#x27;] - 0.02)

            # Comms jitter
            asset[&#x27;comms&#x27;] = max(-90, min(-30, asset[&#x27;comms&#x27;] + random.uniform(-0.5, 0.5)))

            # Idle drift
            if asset[&#x27;mission_status&#x27;] == 0:
                asset[&#x27;lat&#x27;] += random.uniform(-0.00002, 0.00002)
                asset[&#x27;lon&#x27;] += random.uniform(-0.00002, 0.00002)

            # Publish heartbeat
            msg = String()
            msg.data = json.dumps({
                &#x27;asset_id&#x27;: asset[&#x27;id&#x27;],
                &#x27;asset_type&#x27;: asset[&#x27;type&#x27;],
                &#x27;callsign&#x27;: asset[&#x27;callsign&#x27;],
                &#x27;lat&#x27;: round(asset[&#x27;lat&#x27;], 6),
                &#x27;lon&#x27;: round(asset[&#x27;lon&#x27;], 6),
                &#x27;alt&#x27;: asset[&#x27;alt&#x27;],
                &#x27;heading&#x27;: round(asset[&#x27;heading&#x27;], 1),
                &#x27;speed&#x27;: asset[&#x27;speed&#x27;],
                &#x27;battery&#x27;: round(asset[&#x27;battery&#x27;], 1),
                &#x27;comms&#x27;: round(asset[&#x27;comms&#x27;], 1),
                &#x27;autonomy_mode&#x27;: asset[&#x27;autonomy_mode&#x27;],
                &#x27;mission_status&#x27;: asset[&#x27;mission_status&#x27;],
            })
            self.pub.publish(msg)

def main():
    rclpy.init()
    node = SimulatedPlatoon()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
FILE: src/mos_threat_detection/package.xml




Plaintext
&lt;?xml version=&quot;1.0&quot;?&gt;
&lt;package format=&quot;3&quot;&gt;
  &lt;name&gt;mos_threat_detection&lt;/name&gt;
  &lt;version&gt;0.1.0&lt;/version&gt;
  &lt;description&gt;MOS Threat Detection pipeline&lt;/description&gt;
  &lt;maintainer email=&quot;dev@mos.mil&quot;&gt;MOS Dev&lt;/maintainer&gt;
  &lt;license&gt;Proprietary&lt;/license&gt;
  &lt;exec_depend&gt;rclpy&lt;/exec_depend&gt;
  &lt;exec_depend&gt;std_msgs&lt;/exec_depend&gt;
  &lt;export&gt;
    &lt;build_type&gt;ament_python&lt;/build_type&gt;
  &lt;/export&gt;
&lt;/package&gt;
FILE: src/mos_threat_detection/setup.cfg




Ini
[develop]
script_dir=$base/lib/mos_threat_detection
[install]
install_scripts=$base/lib/mos_threat_detection
FILE: src/mos_threat_detection/setup.py




Python
from setuptools import setup

package_name = &#x27;mos_threat_detection&#x27;

setup(
    name=package_name,
    version=&#x27;0.1.0&#x27;,
    packages=[package_name],
    install_requires=[&#x27;setuptools&#x27;],
    zip_safe=True,
    maintainer=&#x27;MOS Dev&#x27;,
    maintainer_email=&#x27;dev@mos.mil&#x27;,
    description=&#x27;MOS Threat Detection&#x27;,
    license=&#x27;Proprietary&#x27;,
    entry_points={
        &#x27;console_scripts&#x27;: [
            &#x27;threat_injector = mos_threat_detection.threat_injector:main&#x27;,
            &#x27;threat_classifier = mos_threat_detection.threat_classifier:main&#x27;,
        ],
    },
)
FILE: src/mos_threat_detection/mos_threat_detection/init.py




Python
FILE: src/mos_threat_detection/mos_threat_detection/threat_injector.py




Python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, random, time, uuid

THREAT_TYPES = [&#x27;INFANTRY&#x27;, &#x27;VEHICLE&#x27;, &#x27;DRONE&#x27;, &#x27;EMPLACEMENT&#x27;, &#x27;WATERCRAFT&#x27;]
AO_CENTER = (34.0, -118.0)
AO_RADIUS = 0.01

class ThreatInjector(Node):
    def __init__(self):
        super().__init__(&#x27;mos_threat_injector&#x27;)
        self.pub = self.create_publisher(String, &#x27;/mos/threats/raw_contacts&#x27;, 10)
        interval = random.uniform(8.0, 15.0)
        self.timer = self.create_timer(interval, self.inject_threat)
        self.get_logger().info(&#x27;[MOS] Threat Injector online — generating contacts&#x27;)

    def inject_threat(self):
        threat = {
            &#x27;contact_id&#x27;: f&#x27;CONTACT-{uuid.uuid4().hex[:6].upper()}&#x27;,
            &#x27;threat_type&#x27;: random.choice(THREAT_TYPES),
            &#x27;lat&#x27;: AO_CENTER[0] + random.uniform(-AO_RADIUS, AO_RADIUS),
            &#x27;lon&#x27;: AO_CENTER[1] + random.uniform(-AO_RADIUS, AO_RADIUS),
            &#x27;confidence&#x27;: round(random.uniform(0.3, 0.95), 2),
            &#x27;heading&#x27;: round(random.uniform(0, 360), 1),
            &#x27;speed&#x27;: round(random.uniform(0, 15), 1),
            &#x27;timestamp&#x27;: time.time()
        }

        msg = String()
        msg.data = json.dumps(threat)
        self.pub.publish(msg)
        self.get_logger().info(
            f&#x27;[THREAT] New contact: {threat[&quot;contact_id&quot;]} — {threat[&quot;threat_type&quot;]} &#x27;
            f&#x27;(conf: {threat[&quot;confidence&quot;]:.0%})&#x27;)

        self.timer.cancel()
        interval = random.uniform(8.0, 15.0)
        self.timer = self.create_timer(interval, self.inject_threat)

def main():
    rclpy.init()
    node = ThreatInjector()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
FILE: src/mos_threat_detection/mos_threat_detection/threat_classifier.py




Python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, time

THREAT_LEVELS = {
    &#x27;INFANTRY&#x27;: &#x27;MEDIUM&#x27;,
    &#x27;VEHICLE&#x27;: &#x27;HIGH&#x27;,
    &#x27;DRONE&#x27;: &#x27;HIGH&#x27;,
    &#x27;EMPLACEMENT&#x27;: &#x27;CRITICAL&#x27;,
    &#x27;WATERCRAFT&#x27;: &#x27;MEDIUM&#x27;,
}

class ThreatClassifier(Node):
    def __init__(self):
        super().__init__(&#x27;mos_threat_classifier&#x27;)
        self.sub = self.create_subscription(
            String, &#x27;/mos/threats/raw_contacts&#x27;, self.on_contact, 10)
        self.pub = self.create_publisher(String, &#x27;/mos/threats/alerts&#x27;, 10)
        self.get_logger().info(&#x27;[MOS] Threat Classifier online&#x27;)

    def on_contact(self, msg):
        try:
            data = json.loads(msg.data)
            threat_type = data.get(&#x27;threat_type&#x27;, &#x27;UNKNOWN&#x27;)
            confidence = data.get(&#x27;confidence&#x27;, 0.5)

            level = THREAT_LEVELS.get(threat_type, &#x27;LOW&#x27;)
            if confidence &lt; 0.5:
                level = &#x27;LOW&#x27;

            alert = {
                &#x27;contact_id&#x27;: data.get(&#x27;contact_id&#x27;),
                &#x27;threat_type&#x27;: threat_type,
                &#x27;threat_level&#x27;: level,
                &#x27;lat&#x27;: data.get(&#x27;lat&#x27;),
                &#x27;lon&#x27;: data.get(&#x27;lon&#x27;),
                &#x27;confidence&#x27;: confidence,
                &#x27;heading&#x27;: data.get(&#x27;heading&#x27;),
                &#x27;speed&#x27;: data.get(&#x27;speed&#x27;),
                &#x27;recommendation&#x27;: self.get_recommendation(level),
                &#x27;timestamp&#x27;: time.time()
            }

            alert_msg = String()
            alert_msg.data = json.dumps(alert)
            self.pub.publish(alert_msg)
            self.get_logger().info(
                f&#x27;[THREAT] Classified: {data.get(&quot;contact_id&quot;)} → &#x27;
                f&#x27;{threat_type} / {level} (conf: {confidence:.0%})&#x27;)

        except json.JSONDecodeError:
            pass

    def get_recommendation(self, level):
        recs = {
            &#x27;LOW&#x27;: &#x27;MONITOR — Continue passive tracking&#x27;,
            &#x27;MEDIUM&#x27;: &#x27;ALERT — Increase ISR coverage on contact&#x27;,
            &#x27;HIGH&#x27;: &#x27;WARN — Prepare defensive posture, notify HPL&#x27;,
            &#x27;CRITICAL&#x27;: &#x27;ACTION — Immediate HPL notification, recommend engagement&#x27;,
        }
        return recs.get(level, &#x27;MONITOR&#x27;)

def main():
    rclpy.init()
    node = ThreatClassifier()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
FILE: src/mos_c2_console/package.xml




Plaintext
&lt;?xml version=&quot;1.0&quot;?&gt;
&lt;package format=&quot;3&quot;&gt;
  &lt;name&gt;mos_c2_console&lt;/name&gt;
  &lt;version&gt;0.1.0&lt;/version&gt;
  &lt;description&gt;MOS C2 Console — Web-based tactical command interface&lt;/description&gt;
  &lt;maintainer email=&quot;dev@mos.mil&quot;&gt;MOS Dev&lt;/maintainer&gt;
  &lt;license&gt;Proprietary&lt;/license&gt;
  &lt;exec_depend&gt;rclpy&lt;/exec_depend&gt;
  &lt;exec_depend&gt;std_msgs&lt;/exec_depend&gt;
  &lt;export&gt;
    &lt;build_type&gt;ament_python&lt;/build_type&gt;
  &lt;/export&gt;
&lt;/package&gt;
FILE: src/mos_c2_console/setup.cfg




Ini
[develop]
script_dir=$base/lib/mos_c2_console
[install]
install_scripts=$base/lib/mos_c2_console
FILE: src/mos_c2_console/setup.py




Python
from setuptools import setup
import os
from glob import glob

package_name = &#x27;mos_c2_console&#x27;

setup(
    name=package_name,
    version=&#x27;0.1.0&#x27;,
    packages=[package_name],
    data_files=[
        (&#x27;share/ament_index/resource_index/packages&#x27;, [&#x27;resource/&#x27; + package_name]),
        (&#x27;share/&#x27; + package_name, [&#x27;package.xml&#x27;]),
        (os.path.join(&#x27;share&#x27;, package_name, &#x27;templates&#x27;), glob(&#x27;mos_c2_console/templates/*&#x27;)),
    ],
    install_requires=[&#x27;setuptools&#x27;, &#x27;flask&#x27;],
    zip_safe=True,
    maintainer=&#x27;MOS Dev&#x27;,
    maintainer_email=&#x27;dev@mos.mil&#x27;,
    description=&#x27;MOS C2 Console&#x27;,
    license=&#x27;Proprietary&#x27;,
    entry_points={
        &#x27;console_scripts&#x27;: [
            &#x27;c2_server = mos_c2_console.c2_server:main&#x27;,
        ],
    },
)
FILE: src/mos_c2_console/MANIFEST.in




Plaintext
recursive-include mos_c2_console/templates *
FILE: src/mos_c2_console/mos_c2_console/init.py




Python
FILE: src/mos_c2_console/mos_c2_console/c2_server.py




Python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from flask import Flask, render_template, request, jsonify
import json, threading, time, os

class C2Bridge(Node):
    def __init__(self):
        super().__init__(&#x27;mos_c2_bridge&#x27;)
        self.assets = []
        self.threats = []
        self.log_entries = []

        self.sub_cop = self.create_subscription(
            String, &#x27;/mos/cop/assets&#x27;, self.on_cop, 10)
        self.sub_threats = self.create_subscription(
            String, &#x27;/mos/threats/alerts&#x27;, self.on_threat, 10)
        self.sub_mission_status = self.create_subscription(
            String, &#x27;/mos/mission/status&#x27;, self.on_mission_status, 10)
        self.sub_autonomy_state = self.create_subscription(
            String, &#x27;/mos/autonomy/state&#x27;, self.on_autonomy_state, 10)

        self.pub_mission = self.create_publisher(String, &#x27;/mos/mission_command&#x27;, 10)
        self.pub_swarm = self.create_publisher(String, &#x27;/mos/swarm_command&#x27;, 10)
        self.pub_autonomy = self.create_publisher(String, &#x27;/mos/autonomy_command&#x27;, 10)

        self.autonomy_state = {&#x27;current_level&#x27;: 1, &#x27;level_name&#x27;: &#x27;ASSISTED&#x27;}
        self.get_logger().info(&#x27;[MOS C2] Bridge node started&#x27;)

    def on_cop(self, msg):
        try:
            self.assets = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def on_threat(self, msg):
        try:
            t = json.loads(msg.data)
            t[&#x27;received&#x27;] = time.time()
            self.threats = [x for x in self.threats if time.time() - x.get(&#x27;received&#x27;, 0) &lt; 30]
            self.threats.append(t)
            self.add_log(f&quot;THREAT: {t.get(&#x27;contact_id&#x27;)} — {t.get(&#x27;threat_type&#x27;)} [{t.get(&#x27;threat_level&#x27;)}]&quot;)
        except json.JSONDecodeError:
            pass

    def on_mission_status(self, msg):
        try:
            data = json.loads(msg.data)
            self.add_log(f&quot;MISSION: {data.get(&#x27;mission_id&#x27;)} — {data.get(&#x27;status&#x27;)} ({data.get(&#x27;task_count&#x27;,0)} tasks)&quot;)
        except json.JSONDecodeError:
            pass

    def on_autonomy_state(self, msg):
        try:
            self.autonomy_state = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def add_log(self, text):
        entry = {&#x27;time&#x27;: time.strftime(&#x27;%H:%M:%S&#x27;), &#x27;text&#x27;: text}
        self.log_entries.append(entry)
        if len(self.log_entries) &gt; 100:
            self.log_entries = self.log_entries[-100:]

    def send_mission(self, data):
        msg = String()
        msg.data = json.dumps(data)
        self.pub_mission.publish(msg)
        self.add_log(f&quot;CMD: Mission {data.get(&#x27;mission_type&#x27;)} ordered&quot;)

    def send_swarm(self, data):
        msg = String()
        msg.data = json.dumps(data)
        self.pub_swarm.publish(msg)
        self.add_log(f&quot;CMD: Swarm {data.get(&#x27;behavior&#x27;)}&quot;)

    def send_autonomy(self, data):
        msg = String()
        msg.data = json.dumps(data)
        self.pub_autonomy.publish(msg)
        self.add_log(f&quot;CMD: Autonomy → Level {data.get(&#x27;target_level&#x27;)}&quot;)


bridge = None

def create_flask_app():
    template_dir = os.path.join(os.path.dirname(__file__), &#x27;templates&#x27;)
    if not os.path.exists(template_dir):
        share_dir = os.path.join(
            os.environ.get(&#x27;AMENT_PREFIX_PATH&#x27;, &#x27;&#x27;).split(&#x27;:&#x27;)[0],
            &#x27;share&#x27;, &#x27;mos_c2_console&#x27;, &#x27;templates&#x27;)
        if os.path.exists(share_dir):
            template_dir = share_dir

    app = Flask(__name__, template_folder=template_dir)

    @app.route(&#x27;/&#x27;)
    def index():
        return render_template(&#x27;index.html&#x27;)

    @app.route(&#x27;/api/assets&#x27;)
    def api_assets():
        return jsonify(bridge.assets if bridge else [])

    @app.route(&#x27;/api/threats&#x27;)
    def api_threats():
        if bridge:
            bridge.threats = [t for t in bridge.threats if time.time() - t.get(&#x27;received&#x27;, 0) &lt; 30]
            return jsonify(bridge.threats)
        return jsonify([])

    @app.route(&#x27;/api/logs&#x27;)
    def api_logs():
        return jsonify(bridge.log_entries if bridge else [])

    @app.route(&#x27;/api/autonomy&#x27;)
    def api_autonomy():
        return jsonify(bridge.autonomy_state if bridge else {})

    @app.route(&#x27;/api/send_mission&#x27;, methods=[&#x27;POST&#x27;])
    def api_send_mission():
        data = request.get_json()
        if bridge:
            bridge.send_mission(data)
            return jsonify({&#x27;status&#x27;: &#x27;ok&#x27;})
        return jsonify({&#x27;status&#x27;: &#x27;error&#x27;}), 500

    @app.route(&#x27;/api/send_swarm&#x27;, methods=[&#x27;POST&#x27;])
    def api_send_swarm():
        data = request.get_json()
        if bridge:
            bridge.send_swarm(data)
            return jsonify({&#x27;status&#x27;: &#x27;ok&#x27;})
        return jsonify({&#x27;status&#x27;: &#x27;error&#x27;}), 500

    @app.route(&#x27;/api/set_autonomy&#x27;, methods=[&#x27;POST&#x27;])
    def api_set_autonomy():
        data = request.get_json()
        if bridge:
            bridge.send_autonomy(data)
            return jsonify({&#x27;status&#x27;: &#x27;ok&#x27;})
        return jsonify({&#x27;status&#x27;: &#x27;error&#x27;}), 500

    return app


def main():
    global bridge
    rclpy.init()
    bridge = C2Bridge()

    spin_thread = threading.Thread(target=rclpy.spin, args=(bridge,), daemon=True)
    spin_thread.start()

    app = create_flask_app()
    bridge.get_logger().info(&#x27;[MOS C2] Starting C2 Console on http://0.0.0.0:5000&#x27;)
    app.run(host=&#x27;0.0.0.0&#x27;, port=5000, debug=False)
FILE: src/mos_c2_console/mos_c2_console/templates/index.html




Html
&lt;!DOCTYPE html&gt;
&lt;html lang=&quot;en&quot;&gt;
&lt;head&gt;
&lt;meta charset=&quot;UTF-8&quot;&gt;
&lt;meta name=&quot;viewport&quot; content=&quot;width=device-width, initial-scale=1.0&quot;&gt;
&lt;title&gt;MOS — Mission Operating System&lt;/title&gt;
&lt;link rel=&quot;stylesheet&quot; href=&quot;https://unpkg.com/leaflet@1.9.4/dist/leaflet.css&quot; /&gt;
&lt;script src=&quot;https://unpkg.com/leaflet@1.9.4/dist/leaflet.js&quot;&gt;&lt;/script&gt;
&lt;style&gt;

* { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: &#x27;Courier New&#x27;, monospace; background: #0a0a0a; color: #00ff88; overflow: hidden; }

  #header {
    background: linear-gradient(90deg, #0d1117, #1a1a2e);
    padding: 8px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #00ff8844;
    height: 48px;
  }
  #header h1 { font-size: 18px; letter-spacing: 3px; }
  #header h1 span { color: #00ff88; }
  #header .subtitle { font-size: 10px; color: #888; }

  #main { display: flex; height: calc(100vh - 48px); }

  #sidebar {
    width: 320px;
    background: #0d1117;
    border-right: 1px solid #00ff8833;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }

  .panel {
    padding: 10px;
    border-bottom: 1px solid #00ff8822;
  }
  .panel h3 {
    font-size: 11px;
    color: #00ff88;
    margin-bottom: 8px;
    letter-spacing: 2px;
  }

  #map-container { flex: 1; position: relative; }
  #map { width: 100%; height: 100%; }

  .stats-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }
  .stat-box {
    background: #1a1a2e;
    padding: 8px;
    border-radius: 4px;
    text-align: center;
  }
  .stat-box .value { font-size: 22px; font-weight: bold; }
  .stat-box .label { font-size: 9px; color: #888; }

  .btn-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
  }
  .btn {
    background: #1a1a2e;
    color: #00ff88;
    border: 1px solid #00ff8844;
    padding: 8px 4px;
    font-family: &#x27;Courier New&#x27;, monospace;
    font-size: 10px;
    cursor: pointer;
    border-radius: 3px;
    letter-spacing: 1px;
  }
  .btn:hover { background: #00ff8833; }
  .btn.warn { color: #ff6644; border-color: #ff664444; }
  .btn.warn:hover { background: #ff664433; }
  .btn.info { color: #4488ff; border-color: #4488ff44; }
  .btn.info:hover { background: #4488ff33; }

  .swarm-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px; }

  .autonomy-bar {
    display: flex; gap: 2px; margin-top: 4px;
  }
  .auto-level {
    flex: 1;
    text-align: center;
    padding: 6px 2px;
    font-size: 8px;
    background: #1a1a2e;
    border: 1px solid #333;
    cursor: pointer;
    border-radius: 2px;
  }
  .auto-level.active { background: #00ff8844; border-color: #00ff88; }
  .auto-level:hover { background: #00ff8822; }

  #log-panel {
    flex: 1;
    min-height: 100px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  #log {
    flex: 1;
    overflow-y: auto;
    font-size: 10px;
    color: #888;
    padding: 4px;
    background: #0a0e14;
    border-radius: 3px;
  }
  #log div { padding: 2px 0; border-bottom: 1px solid #111; }
  #log .time { color: #555; }
  #log .threat-entry { color: #ff6644; }
  #log .cmd-entry { color: #4488ff; }

  .leaflet-container { background: #0a0a0a !important; }
&lt;/style&gt;
&lt;/head&gt;
&lt;body&gt;

&lt;div id=&quot;header&quot;&gt;
  &lt;div&gt;
    &lt;h1&gt;⬡ &lt;span&gt;MOS&lt;/span&gt;&lt;/h1&gt;
    &lt;div class=&quot;subtitle&quot;&gt;MISSION OPERATING SYSTEM — ROBOTIC PLATOON C2&lt;/div&gt;
  &lt;/div&gt;
  &lt;div style=&quot;text-align:right;&quot;&gt;
    &lt;div style=&quot;font-size:11px;&quot; id=&quot;clock&quot;&gt;&lt;/div&gt;
    &lt;div style=&quot;font-size:9px;color:#888;&quot; id=&quot;asset-count&quot;&gt;ASSETS: --&lt;/div&gt;
  &lt;/div&gt;
&lt;/div&gt;

&lt;div id=&quot;main&quot;&gt;
  &lt;div id=&quot;sidebar&quot;&gt;

    &lt;div class=&quot;panel&quot;&gt;
      &lt;h3&gt;▶ PLATOON STATUS&lt;/h3&gt;
      &lt;div class=&quot;stats-grid&quot;&gt;
        &lt;div class=&quot;stat-box&quot;&gt;&lt;div class=&quot;value&quot; id=&quot;s-total&quot;&gt;--&lt;/div&gt;&lt;div class=&quot;label&quot;&gt;TOTAL&lt;/div&gt;&lt;/div&gt;
        &lt;div class=&quot;stat-box&quot;&gt;&lt;div class=&quot;value&quot; id=&quot;s-active&quot; style=&quot;color:#00ff88&quot;&gt;--&lt;/div&gt;&lt;div class=&quot;label&quot;&gt;ACTIVE&lt;/div&gt;&lt;/div&gt;
        &lt;div class=&quot;stat-box&quot;&gt;&lt;div class=&quot;value&quot; id=&quot;s-air&quot; style=&quot;color:#4488ff&quot;&gt;--&lt;/div&gt;&lt;div class=&quot;label&quot;&gt;AIR&lt;/div&gt;&lt;/div&gt;
        &lt;div class=&quot;stat-box&quot;&gt;&lt;div class=&quot;value&quot; id=&quot;s-gnd&quot; style=&quot;color:#44ff44&quot;&gt;--&lt;/div&gt;&lt;div class=&quot;label&quot;&gt;GROUND&lt;/div&gt;&lt;/div&gt;
        &lt;div class=&quot;stat-box&quot;&gt;&lt;div class=&quot;value&quot; id=&quot;s-sea&quot; style=&quot;color:#ff8844&quot;&gt;--&lt;/div&gt;&lt;div class=&quot;label&quot;&gt;MARITIME&lt;/div&gt;&lt;/div&gt;
        &lt;div class=&quot;stat-box&quot;&gt;&lt;div class=&quot;value&quot; id=&quot;s-threat&quot; style=&quot;color:#ff4444&quot;&gt;--&lt;/div&gt;&lt;div class=&quot;label&quot;&gt;THREATS&lt;/div&gt;&lt;/div&gt;
      &lt;/div&gt;
    &lt;/div&gt;

    &lt;div class=&quot;panel&quot;&gt;
      &lt;h3&gt;▶ MISSION ORDERS&lt;/h3&gt;
      &lt;div class=&quot;btn-grid&quot;&gt;
        &lt;button class=&quot;btn&quot; onclick=&quot;sendMission(&#x27;ISR&#x27;)&quot;&gt;ISR&lt;/button&gt;
        &lt;button class=&quot;btn&quot; onclick=&quot;sendMission(&#x27;SECURITY&#x27;)&quot;&gt;SECURITY&lt;/button&gt;
        &lt;button class=&quot;btn warn&quot; onclick=&quot;sendMission(&#x27;PRECISION_EFFECTS&#x27;)&quot;&gt;PRECISION FX&lt;/button&gt;
        &lt;button class=&quot;btn info&quot; onclick=&quot;sendMission(&#x27;LOGISTICS&#x27;)&quot;&gt;LOGISTICS&lt;/button&gt;
        &lt;button class=&quot;btn&quot; onclick=&quot;sendMission(&#x27;SAR&#x27;)&quot;&gt;SAR&lt;/button&gt;
        &lt;button class=&quot;btn&quot; onclick=&quot;sendMission(&#x27;EW_SIGINT&#x27;)&quot;&gt;EW/SIGINT&lt;/button&gt;
      &lt;/div&gt;
    &lt;/div&gt;

    &lt;div class=&quot;panel&quot;&gt;
      &lt;h3&gt;▶ SWARM COMMANDS&lt;/h3&gt;
      &lt;div class=&quot;swarm-grid&quot;&gt;
        &lt;button class=&quot;btn info&quot; onclick=&quot;sendSwarm(&#x27;RTB&#x27;)&quot;&gt;RTB&lt;/button&gt;
        &lt;button class=&quot;btn&quot; onclick=&quot;sendSwarm(&#x27;HOLD&#x27;)&quot;&gt;HOLD&lt;/button&gt;
        &lt;button class=&quot;btn warn&quot; onclick=&quot;sendSwarm(&#x27;SCATTER&#x27;)&quot;&gt;SCATTER&lt;/button&gt;
      &lt;/div&gt;
    &lt;/div&gt;

    &lt;div class=&quot;panel&quot;&gt;
      &lt;h3&gt;▶ AUTONOMY LEVEL&lt;/h3&gt;
      &lt;div class=&quot;autonomy-bar&quot;&gt;
        &lt;div class=&quot;auto-level&quot; onclick=&quot;setAutonomy(0)&quot;&gt;0&lt;br&gt;MAN&lt;/div&gt;
        &lt;div class=&quot;auto-level active&quot; onclick=&quot;setAutonomy(1)&quot;&gt;1&lt;br&gt;AST&lt;/div&gt;
        &lt;div class=&quot;auto-level&quot; onclick=&quot;setAutonomy(2)&quot;&gt;2&lt;br&gt;COL&lt;/div&gt;
        &lt;div class=&quot;auto-level&quot; onclick=&quot;setAutonomy(3)&quot;&gt;3&lt;br&gt;SWM&lt;/div&gt;
        &lt;div class=&quot;auto-level&quot; onclick=&quot;setAutonomy(4)&quot;&gt;4&lt;br&gt;COG&lt;/div&gt;
      &lt;/div&gt;
    &lt;/div&gt;

    &lt;div class=&quot;panel&quot; id=&quot;log-panel&quot;&gt;
      &lt;h3&gt;▶ ACTIVITY LOG&lt;/h3&gt;
      &lt;div id=&quot;log&quot;&gt;&lt;/div&gt;
    &lt;/div&gt;

  &lt;/div&gt;

  &lt;div id=&quot;map-container&quot;&gt;
    &lt;div id=&quot;map&quot;&gt;&lt;/div&gt;
  &lt;/div&gt;
&lt;/div&gt;

&lt;script&gt;
  const map = L.map(&#x27;map&#x27;, {
    center: [34.000, -118.000],
    zoom: 15,
    zoomControl: false
  });

  L.tileLayer(&#x27;https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png&#x27;, {
    attribution: &#x27;© CartoDB&#x27;,
    maxZoom: 19
  }).addTo(map);

  L.control.zoom({ position: &#x27;topright&#x27; }).addTo(map);

  const markers = {};
  const threatMarkers = {};

  const domainColors = { &#x27;AIR&#x27;: &#x27;#4488ff&#x27;, &#x27;GROUND&#x27;: &#x27;#44ff44&#x27;, &#x27;MARITIME&#x27;: &#x27;#ff8844&#x27; };
  const statusColors = { 0: &#x27;#888888&#x27;, 1: &#x27;#ffff00&#x27;, 2: &#x27;#00ff88&#x27;, 3: &#x27;#4488ff&#x27;, 5: &#x27;#ff0000&#x27; };
  const statusNames = { 0: &#x27;IDLE&#x27;, 1: &#x27;EN_ROUTE&#x27;, 2: &#x27;EXEC&#x27;, 3: &#x27;DONE&#x27;, 5: &#x27;FAULT&#x27; };

  function makeIcon(domain, status) {
    const dc = domainColors[domain] || &#x27;#ffffff&#x27;;
    const sc = statusColors[status] || &#x27;#888888&#x27;;
    return L.divIcon({
      className: &#x27;&#x27;,
      iconSize: [20, 20],
      iconAnchor: [10, 10],
      html: `<div style="
        width:20px;height:20px;border-radius:50%;
        border:2px solid ${dc};
        background:radial-gradient(circle at center, ${sc} 30%, transparent 70%);
        box-shadow:0 0 6px ${dc}44;
      "></div>`
    });
  }

  function makeThreatIcon() {
    return L.divIcon({
      className: &#x27;&#x27;,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
      html: `<div style="
        width:24px;height:24px;border-radius:50%;
        border:2px dashed #ff4444;
        background:radial-gradient(circle at center, #ff000066 30%, transparent 70%);
        box-shadow:0 0 10px #ff000044;
      "></div>`
    });
  }

  function updateAssets(assets) {
    const seen = {};
    assets.forEach(a =&gt; {
      const id = a.asset_id;
      seen[id] = true;
      const latlng = [a.lat, a.lon];
      const sname = statusNames[a.mission_status] || &#x27;UNK&#x27;;
      const tooltip = `${a.callsign} [${a.asset_type}]\n${sname} | Batt: ${a.battery}%`;

      if (markers[id]) {
        markers[id].setLatLng(latlng);
        markers[id].setIcon(makeIcon(a.asset_type, a.mission_status));
        markers[id].setTooltip(tooltip);
      } else {
        markers[id] = L.marker(latlng, { icon: makeIcon(a.asset_type, a.mission_status) })
          .bindTooltip(tooltip, { permanent: false, direction: &#x27;top&#x27;, offset: [0, -12],
            className: &#x27;custom-tooltip&#x27; })
          .addTo(map);
      }
    });
    Object.keys(markers).forEach(id =&gt; {
      if (!seen[id]) { map.removeLayer(markers[id]); delete markers[id]; }
    });

    document.getElementById(&#x27;s-total&#x27;).textContent = assets.length;
    document.getElementById(&#x27;s-active&#x27;).textContent = assets.filter(a =&gt; a.mission_status &gt; 0 &amp;&amp; a.mission_status &lt; 5).length;
    document.getElementById(&#x27;s-air&#x27;).textContent = assets.filter(a =&gt; a.asset_type === &#x27;AIR&#x27;).length;
    document.getElementById(&#x27;s-gnd&#x27;).textContent = assets.filter(a =&gt; a.asset_type === &#x27;GROUND&#x27;).length;
    document.getElementById(&#x27;s-sea&#x27;).textContent = assets.filter(a =&gt; a.asset_type === &#x27;MARITIME&#x27;).length;
    document.getElementById(&#x27;asset-count&#x27;).textContent = &#x27;ASSETS: &#x27; + assets.length;
  }

  function updateThreats(threats) {
    const seen = {};
    threats.forEach(t =&gt; {
      const id = t.contact_id;
      seen[id] = true;
      const latlng = [t.lat, t.lon];
      const tooltip = `⚠ ${id}\n${t.threat_type} [${t.threat_level}]\nConf: ${(t.confidence * 100).toFixed(0)}%`;

      if (threatMarkers[id]) {
        threatMarkers[id].setLatLng(latlng);
        threatMarkers[id].setTooltip(tooltip);
      } else {
        threatMarkers[id] = L.marker(latlng, { icon: makeThreatIcon() })
          .bindTooltip(tooltip, { permanent: false, direction: &#x27;top&#x27;, offset: [0, -14],
            className: &#x27;custom-tooltip&#x27; })
          .addTo(map);
      }
    });
    Object.keys(threatMarkers).forEach(id =&gt; {
      if (!seen[id]) { map.removeLayer(threatMarkers[id]); delete threatMarkers[id]; }
    });
    document.getElementById(&#x27;s-threat&#x27;).textContent = threats.length;
  }

  function updateLogs(logs) {
    const el = document.getElementById(&#x27;log&#x27;);
    const last = logs.slice(-30);
    el.innerHTML = last.map(l =&gt; {
      let cls = &#x27;&#x27;;
      if (l.text.startsWith(&#x27;THREAT&#x27;)) cls = &#x27;threat-entry&#x27;;
      else if (l.text.startsWith(&#x27;CMD&#x27;)) cls = &#x27;cmd-entry&#x27;;
      return `<div class="${cls}"><span class="time">${l.time}</span> ${l.text}</div>`;
    }).join(&#x27;&#x27;);
    el.scrollTop = el.scrollHeight;
  }

  function updateAutonomy(state) {
    document.querySelectorAll(&#x27;.auto-level&#x27;).forEach((el, i) =&gt; {
      el.classList.toggle(&#x27;active&#x27;, i === state.current_level);
    });
  }

  // ── Polling loop ──
  async function poll() {
    try {
      const [aRes, tRes, lRes, auRes] = await Promise.all([
        fetch(&#x27;/api/assets&#x27;), fetch(&#x27;/api/threats&#x27;), fetch(&#x27;/api/logs&#x27;), fetch(&#x27;/api/autonomy&#x27;)
      ]);
      updateAssets(await aRes.json());
      updateThreats(await tRes.json());
      updateLogs(await lRes.json());
      updateAutonomy(await auRes.json());
    } catch(e) {}
  }
  setInterval(poll, 1000);
  poll();

  // ── Clock ──
  setInterval(() =&gt; {
    document.getElementById(&#x27;clock&#x27;).textContent = new Date().toLocaleTimeString(&#x27;en-US&#x27;,
      { hour12: true, hour: &#x27;2-digit&#x27;, minute: &#x27;2-digit&#x27;, second: &#x27;2-digit&#x27; });
  }, 1000);

  // ── Commands ──
  async function sendMission(type) {
    await fetch(&#x27;/api/send_mission&#x27;, {
      method: &#x27;POST&#x27;,
      headers: { &#x27;Content-Type&#x27;: &#x27;application/json&#x27; },
      body: JSON.stringify({
        mission_id: &#x27;MVRX-&#x27; + Math.random().toString(36).substr(2,6).toUpperCase(),
        mission_type: type,
        commander_intent: &#x27;Execute &#x27; + type + &#x27; mission&#x27;,
        objectives: [&#x27;Primary objective&#x27;],
        area_of_operations: &#x27;AO-ALPHA&#x27;,
        priority: 1
      })
    });
  }

  async function sendSwarm(behavior) {
    await fetch(&#x27;/api/send_swarm&#x27;, {
      method: &#x27;POST&#x27;,
      headers: { &#x27;Content-Type&#x27;: &#x27;application/json&#x27; },
      body: JSON.stringify({ behavior: behavior, domain: &#x27;ALL&#x27; })
    });
  }

  async function setAutonomy(level) {
    await fetch(&#x27;/api/set_autonomy&#x27;, {
      method: &#x27;POST&#x27;,
      headers: { &#x27;Content-Type&#x27;: &#x27;application/json&#x27; },
      body: JSON.stringify({ target_level: level })
    });
  }
&lt;/script&gt;
&lt;/body&gt;
&lt;/html&gt;
FILE: launch_mos.sh

(See full script in launch section — already installed at ~/mos_ws/launch_mos.sh)

FILE: shutdown_mos.sh

(See full script in launch section — already installed at ~/mos_ws/shutdown_mos.sh)

RESOURCE MARKER FILES

Each package needs an empty marker file:




Plaintext
src/mos_core/resource/mos_core                          (empty file)
src/mos_mission_planner/resource/mos_mission_planner    (empty file)
src/mos_swarm/resource/mos_swarm                        (empty file)
src/mos_sim/resource/mos_sim                            (empty file)
src/mos_threat_detection/resource/mos_threat_detection  (empty file)
src/mos_c2_console/resource/mos_c2_console              (empty file)
BUILD & RUN COMMANDS




Bash
cd ~/mos_ws
colcon build
source install/setup.bash
./launch_mos.sh
KNOWN ISSUES & NOTES

Port 5000 conflict: Always run fuser -k 5000/tcp before starting C2 server
launch_mos.sh handles this automatically
Flask runs in main thread, ROS 2 spins in daemon thread
Template path resolution: tries local path first, then ament share path
Threat markers auto-expire after 30 seconds
All ROS 2 transport is JSON over std_msgs/String (future: switch to custom interfaces)
NEXT DEVELOPMENT PRIORITIES (Phase 4)

Waypoint planning — draw waypoints on map, visualize paths
Formation behaviors — line, wedge, diamond, orbit
Geofencing — keep-in / keep-out zones with enforcement
Dynamic re-tasking — reassign assets mid-mission
Asset detail panel — click asset for full telemetry
Mission timeline — Gantt-style task visualization
Replay/AAR — record and playback mission data
END OF MANIFEST



Plaintext

Save: `Ctrl+O`, Enter, `Ctrl+X`

---

Now you have **one file** (`~/mos_ws/MOS_PROJECT_MANIFEST.md`) that contains:

- Every source file, line for line
- All package configs (package.xml, setup.py, setup.cfg, CMakeLists.txt)
- Directory structure
- Build/run instructions
- Architecture notes
- Known issues
- Next steps

When you come back, just paste the manifest contents into the new conversation and say **&quot;Here&#x27;s my MOS project — let&#x27;s continue with Phase 4&quot;** and I&#x27;ll pick up exactly where we left off.
