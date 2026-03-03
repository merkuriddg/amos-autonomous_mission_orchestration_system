# ⬡ MOS — Mission Operating System

**Mission Operating System (MOS)** — pronounced "moz" — is an autonomous systems
integration platform designed for special operations robotic platoons. Built on the
"Tech as a Teammate" philosophy, MOS orchestrates 25-40 autonomous assets across
air, ground, and maritime domains under human-on-the-loop supervision.

Developed for the **Mavrix1 Robotic Platoon** specification.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Package Structure](#package-structure)
3. [System Requirements](#system-requirements)
4. [Installation](#installation)
5. [Quick Start](#quick-start)
6. [Package Documentation](#package-documentation)
7. [C2 Console Guide](#c2-console-guide)
8. [ROS 2 Topics](#ros-2-topics)
9. [REST API Reference](#rest-api-reference)
10. [Autonomy Levels](#autonomy-levels)
11. [Mission Types](#mission-types)
12. [Development Roadmap](#development-roadmap)

---

## Architecture Overview
┌─────────────────────────────────────────────────────────────────┐
│ MOS ARCHITECTURE │
│ │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐ │
│ │ C2 │ │ Mission │ │ Autonomy │ │ Swarm │ │
│ │ Console │◄─┤ Planner │◄─┤ Manager │◄─┤ Orchestrator │ │
│ │ (Flask) │ │ │ │ │ │ │ │
│ └────┬─────┘ └────┬─────┘ └────┬─────┘ └───────┬───────┘ │
│ │ │ │ │ │
│ ▼ ▼ ▼ ▼ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Asset Registry (Core) │ │
│ │ Common Operating Picture (COP) │ │
│ └──────────────────────┬──────────────────────────────────┘ │
│ │ │
│ ┌──────────────────────▼──────────────────────────────────┐ │
│ │ ROS 2 Middleware (Humble) │ │
│ └──────────────────────┬──────────────────────────────────┘ │
│ │ │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐ │
│ │ AIR x10 │ │ GND x12 │ │ SEA x3 │ │ Threat │ │
│ │ Assets │ │ Assets │ │ Assets │ │ Detection │ │
│ └──────────┘ └──────────┘ └──────────┘ └───────────────┘ │
└─────────────────────────────────────────────────────────────────┘


**Key Principles:**
- Human-on-the-loop: All lethal effects require HPL (Human Platoon Leader) authorization
- 5-tier autonomy: MANUAL → ASSISTED → COLLABORATIVE → SWARM → COGNITIVE
- Domain agnostic: Unified C2 across air, ground, and maritime assets
- Tech as a Teammate: Autonomous systems augment, not replace, operators

---

## Package Structure
~/mos_ws/src/
├── mos_core/ # Core MOS services
│ └── mos_core/
│ ├── asset_registry.py # Tracks all 25 assets, publishes COP
│ └── autonomy_manager.py # 5-tier autonomy state machine
│
├── mos_mission_planner/ # Mission decomposition & task assignment
│ └── mos_mission_planner/
│ └── mission_planner.py # 6 mission types with task trees
│
├── mos_swarm/ # Swarm behaviors & coordination
│ └── mos_swarm/
│ └── swarm_orchestrator.py # RTB, HOLD, SCATTER, formations
│
├── mos_sim/ # Simulated robotic platoon
│ └── mos_sim/
│ └── simulated_platoon.py # 25 assets with reactive movement
│
├── mos_threat_detection/ # Threat detection pipeline
│ └── mos_threat_detection/
│ ├── threat_injector.py # Simulated enemy contacts
│ └── threat_classifier.py # AI-simulated threat assessment
│
├── mos_c2_console/ # Web-based C2 interface
│ └── mos_c2_console/
│ ├── c2_server.py # Flask REST + ROS 2 bridge
│ └── templates/
│ └── index.html # Tactical map & controls
│
└── mos_interfaces/ # Custom ROS 2 message definitions
├── msg/
│ ├── AssetHeartbeat.msg
│ ├── MissionIntent.msg
│ ├── SwarmCommand.msg
│ ├── ThreatAlert.msg
│ └── AutonomyState.msg
└── srv/
├── RegisterAsset.srv
└── RequestAutonomy.srv


---

## System Requirements

| Component       | Requirement                          |
|-----------------|--------------------------------------|
| OS              | Ubuntu 22.04 LTS                     |
| ROS             | ROS 2 Humble Hawksbill              |
| Python          | 3.10+                                |
| Flask           | pip install flask                    |
| Browser         | Chrome/Firefox (modern)              |
| RAM             | 4 GB minimum                         |
| Network         | localhost (dev) or LAN (deployment)  |

---

## Installation

### Prerequisites

```bash
# ROS 2 Humble (if not installed)
sudo apt update &amp;&amp; sudo apt install -y ros-humble-desktop python3-colcon-common-extensions

# Python dependencies
pip install flask

# Build
cd ~/mos_ws
colcon build
source install/setup.bash


Quick Start

One-command launch (recommended):
cd ~/mos_ws
./launch_mos.sh

This will:

Kill any existing MOS processes
Build the workspace
Start all 8 nodes (sim, core, threat detection, C2)
Open C2 Console at http://localhost:5000
Shutdown:
./shutdown_mos.sh

Or press Ctrl+C in the launch script terminal.

Manual launch (for debugging):
# Terminal 1 — Simulated Platoon
source ~/mos_ws/install/setup.bash
ros2 run mos_sim simulated_platoon

# Terminal 2 — Core Nodes
source ~/mos_ws/install/setup.bash
ros2 run mos_core asset_registry &amp;
ros2 run mos_core autonomy_manager &amp;
ros2 run mos_mission_planner mission_planner &amp;
ros2 run mos_swarm swarm_orchestrator

# Terminal 3 — Threat Detection
source ~/mos_ws/install/setup.bash
ros2 run mos_threat_detection threat_injector &amp;
ros2 run mos_threat_detection threat_classifier

# Terminal 4 — C2 Console
source ~/mos_ws/install/setup.bash
ros2 run mos_c2_console c2_server


mos_core — Asset Registry

Node: asset_registry
Purpose: Maintains the Common Operating Picture (COP) by tracking all asset heartbeats.

Subscriptions:

Topic	Type	Description
/mos/heartbeat	std_msgs/String	Raw asset heartbeats (JSON)
Publications:

Topic	Type	Frequency	Description
/mos/cop/assets	std_msgs/String	2 Hz	Full asset registry snapshot
Behavior:

Receives heartbeat JSON from each of the 25 simulated assets
Maintains an in-memory dictionary of all asset states
Publishes the full COP at 2 Hz for all downstream consumers
Marks assets as FAULT if no heartbeat received for 10 seconds
mos_core — Autonomy Manager

Node: autonomy_manager
Purpose: Manages the 5-tier autonomy state machine with HPL authorization gates.

Autonomy Levels:

Level	Name	Description
0	MANUAL	Full human control, no autonomous behavior
1	ASSISTED	Autonomy suggests, human decides
2	COLLABORATIVE	Shared decision-making
3	SWARM	Autonomous swarm coordination
4	COGNITIVE	Full autonomous decision-making (non-lethal only)
Key Rule: Transitions above COLLABORATIVE require HPL authorization.
Lethal effects ALWAYS require human approval regardless of autonomy level.

mos_mission_planner — Mission Planner

Node: mission_planner
Purpose: Decomposes high-level mission orders into task trees and assigns assets.

Supported Mission Types:

Type	Code	Asset Mix
Intelligence, Surveillance, Recon	ISR	3 AIR + 1 GROUND
Perimeter Security	SECURITY	4 GROUND + 2 AIR
Precision Effects	PRECISION_EFFECTS	2 AIR + 2 GROUND
Logistics/Resupply	LOGISTICS	3 GROUND (MULE)
Search and Rescue	SAR	2 AIR + 2 GROUND + 1 MARITIME
Electronic Warfare/SIGINT	EW_SIGINT	2 AIR + 1 GROUND
mos_swarm — Swarm Orchestrator

Node: swarm_orchestrator
Purpose: Coordinates swarm-level behaviors across all assets.

Swarm Commands:

Command	Behavior
RTB	All assets return to base position
HOLD	All assets freeze in current position
SCATTER	All assets rapidly disperse from current positions
mos_sim — Simulated Platoon

Node: simulated_platoon
Purpose: Simulates 25 robotic assets with realistic movement and mission response.

Asset Roster:

Domain	Count	Callsigns
AIR	10	HAWK-1/2/3, RAVEN-1/2/3, TALON-1/2, OVERWATCH-1/2
GROUND	12	WARHOUND-1/2/3/4, MULE-1/2/3, SENTRY-1/2/3/4, PATHFINDER-1
MARITIME	3	TRITON-1/2/3
Status Lifecycle:




Plaintext
IDLE (gray) → EN_ROUTE (yellow) → EXEC (green) → DONE (blue) → IDLE
                                                        ↓
                                                   FAULT (red)
Movement Speeds (degrees/tick at 2 Hz):

Domain	Speed
AIR	0.0003
GROUND	0.00012
MARITIME	0.00015
mos_threat_detection — Threat Pipeline

Nodes: threat_injector, threat_classifier

Injector: Generates simulated enemy contacts at random intervals near the AO.

Classifier: Receives raw contacts and publishes classified threat assessments with:

Threat level: LOW, MEDIUM, HIGH, CRITICAL
Classification: Infantry, Vehicle, Drone, etc.
Engagement recommendation
mos_c2_console — C2 Console

Node: c2_server
Purpose: Web-based command and control interface bridging browser to ROS 2.

Architecture: Flask REST server + ROS 2 node in background thread.

Features:

Real-time tactical map (Leaflet.js on dark CartoDB tiles)
Asset markers color-coded by domain and status
Threat markers with dashed borders
Mission order buttons (6 mission types)
Swarm command buttons (RTB, HOLD, SCATTER)
Autonomy level controls
Platoon status dashboard
Activity log
C2 Console Guide

Map Legend

Marker	Meaning
Blue circle	AIR asset
Green circle	GROUND asset
Orange circle	MARITIME asset
Gray center dot	IDLE
Yellow center dot	EN_ROUTE
Green center dot	EXECUTING
Blue center dot	DONE
Red center dot	FAULT
Red dashed circle	Threat contact
Issuing a Mission

Click any Mission Order button (ISR, SECURITY, etc.)
Watch the Activity Log for confirmation
Observe assigned assets change from gray (IDLE) to yellow (EN_ROUTE)
Assets move toward objective, then turn green (EXEC)
After executing, assets turn blue (DONE), then return to IDLE
Swarm Commands

RTB: All assets converge back to base deployment area
HOLD: All assets freeze in current position
SCATTER: All assets rapidly disperse outward
ROS 2 Topics

Topic	Type	Publisher	Description
/mos/heartbeat	String	simulated_platoon	Individual asset heartbeats
/mos/cop/assets	String	asset_registry	Full COP snapshot
/mos/mission_command	String	c2_server	Mission orders from C2
/mos/mission/intent	String	mission_planner	Decomposed mission intent
/mos/mission/status	String	mission_planner	Mission execution status
/mos/swarm_command	String	c2_server	Swarm behavior commands
/mos/swarm/command	String	swarm_orchestrator	Processed swarm orders
/mos/autonomy_command	String	c2_server	Autonomy level changes
/mos/autonomy/state	String	autonomy_manager	Current autonomy state
/mos/autonomy/request	String	autonomy_manager	Autonomy transition requests
/mos/threats/raw_contacts	String	threat_injector	Raw sensor contacts
/mos/threats/alerts	String	threat_classifier	Classified threat alerts
/mos/tasks/orders	String	mission_planner	Individual task assignments
REST API Reference

Base URL: http://localhost:5000

GET /api/assets

Returns JSON array of all tracked assets.

Response:
[
  {
    &quot;asset_id&quot;: &quot;MVRX-A01&quot;,
    &quot;asset_type&quot;: &quot;AIR&quot;,
    &quot;callsign&quot;: &quot;HAWK-1&quot;,
    &quot;lat&quot;: 33.9968,
    &quot;lon&quot;: -117.999,
    &quot;alt&quot;: 120.0,
    &quot;heading&quot;: 160.3,
    &quot;speed&quot;: 0.0003,
    &quot;battery&quot;: 78.5,
    &quot;comms&quot;: -67.9,
    &quot;autonomy_mode&quot;: &quot;ASSISTED&quot;,
    &quot;mission_status&quot;: 2
  }
]


GET /api/threats

Returns JSON array of active threats (last 30 seconds).

POST /api/send_mission

Send a mission order.

Body:
{
  &quot;mission_id&quot;: &quot;MVRX-001&quot;,
  &quot;mission_type&quot;: &quot;ISR&quot;,
  &quot;commander_intent&quot;: &quot;Conduct ISR sweep of AO&quot;,
  &quot;objectives&quot;: [&quot;Primary objective&quot;],
  &quot;area_of_operations&quot;: &quot;AO-ALPHA&quot;,
  &quot;priority&quot;: 1
}

POST /api/send_swarm

Send a swarm command.

Body:
{
  &quot;behavior&quot;: &quot;RTB&quot;,
  &quot;domain&quot;: &quot;ALL&quot;
}

POST /api/set_autonomy

Set autonomy level (0-4).

Body:
{
  &quot;target_level&quot;: 3
}


Development Roadmap

Phase 1 — Foundation (COMPLETE ✅)

[x] ROS 2 workspace and package structure
[x] Custom message/service interfaces
[x] Asset Registry with COP
[x] Autonomy Manager (5-tier state machine)
[x] Simulated Platoon (25 assets, 3 domains)
Phase 2 — Mission Intelligence (COMPLETE ✅)

[x] Mission Planner with 6 mission types
[x] Task decomposition and asset assignment
[x] Swarm Orchestrator (RTB, HOLD, SCATTER)
[x] Threat Detection pipeline (injector + classifier)
Phase 3 — C2 Interface (COMPLETE ✅)

[x] Web-based tactical map (Leaflet.js)
[x] Real-time asset tracking with domain-coded markers
[x] Mission order controls
[x] Swarm command controls
[x] Autonomy level controls
[x] Threat visualization
[x] Activity log
Phase 4 — Advanced Behaviors (NEXT)

[ ] Waypoint planning with path visualization
[ ] Formation flying/driving
[ ] Dynamic re-tasking during mission execution
[ ] Asset health monitoring and auto-recovery
[ ] Geofencing and keep-out zones
Phase 5 — Integration

[ ] PX4/ArduPilot integration for real flight controllers
[ ] Nav2 integration for ground navigation
[ ] Gazebo simulation with physics
[ ] Encrypted communications (DDS Security)
[ ] Hardware-in-the-loop testing
Phase 6 — Cognitive Autonomy

[ ] ML-based threat classification
[ ] Predictive mission planning
[ ] Adaptive swarm behaviors
[ ] Natural language mission orders
[ ] After-action review and learning
License

PROPRIETARY — Mavrix Defense Systems

Contact

MOS Development Team



Save: `Ctrl+O`, Enter, `Ctrl+X`

---

### Usage

From now on, to launch the entire system:

```bash
cd ~/mos_ws
./launch_mos.sh


To Shutdown:
./shutdown_mos.sh

Or just Ctrl+C in the launch terminal.
Open http://localhost:5000 in your browser and the full MOS C2 Console is live. Let me know when you're ready for the next phase!






