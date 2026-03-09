# AMOS System Diagram
**Autonomous Mission Operating System (AMOS)**  
System Diagram v0.1

---

## Purpose

This document provides a **single-view architectural diagram** of the AMOS platform so engineers, operators, partners, and evaluators can quickly understand how the system fits together.

AMOS is designed as a **mission operating system for autonomous forces**. It sits above hardware platforms and robotics middleware, orchestrating missions, autonomy, telemetry, authority, and effects across multiple domains.

---

## AMOS in the Stack

```text
┌──────────────────────────────────────────────────────────────┐
│                      Mission Applications                    │
│   Mission Packs • Analytics • OPORD/CONOP • Dashboards      │
└──────────────────────────────────────────────────────────────┘
                             ▲
                             │
┌──────────────────────────────────────────────────────────────┐
│                            AMOS                              │
│         Mission Orchestration • HMT • Swarm Control         │
│         Authority Engine • Event Bus • State Registry       │
└──────────────────────────────────────────────────────────────┘
                             ▲
                             │
┌──────────────────────────────────────────────────────────────┐
│                    Robotics / Protocol Layer                 │
│     ROS2 • PX4 • ArduPilot • MAVLink • CoT • Link-16        │
└──────────────────────────────────────────────────────────────┘
                             ▲
                             │
┌──────────────────────────────────────────────────────────────┐
│                     Physical / Simulated Assets              │
│   UAVs • UGVs • USVs • Sensors • Relay Nodes • Orbital      │
└──────────────────────────────────────────────────────────────┘
```

### What this means

- **Hardware platforms** provide physical or simulated mission assets
- **Robotics and protocol layers** provide low-level communications and control
- **AMOS** provides mission logic, autonomy coordination, authority enforcement, and operator supervision
- **Mission applications** sit above AMOS and use it to run operational workflows

---

## Full System Diagram

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                             OPERATOR LAYER                                 │
│  Tactical Console • Mission Planning UI • COP • Alerts • Collaboration     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MISSION CONTROL LAYER                             │
│  Mission Manager • Task Orchestrator • Authority Engine • State Registry   │
│  Event Bus • Mission Timeline • Audit Log                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AUTONOMY & INTELLIGENCE LAYER                           │
│  Cognitive Engine • COA Generator • Wargame Engine • Swarm Intelligence    │
│  Threat Predictor • HMT Engine • Effects Chain • ROE Engine                │
└─────────────────────────────────────────────────────────────────────────────┘
                         │                    │                    │
                         ▼                    ▼                    ▼
┌────────────────────────────┐ ┌────────────────────────────┐ ┌────────────────────────────┐
│       ASSET ADAPTERS       │ │      SENSOR ADAPTERS       │ │     TRANSPORT ADAPTERS     │
│ PX4 • ROS2 • ArduPilot     │ │ EO/IR • Radar • SIGINT     │ │ MAVLink • CoT • Link-16    │
│ Maritime • Simulated       │ │ Acoustic • External Feeds  │ │ REST • WebSocket • Mesh    │
└────────────────────────────┘ └────────────────────────────┘ └────────────────────────────┘
                         \                    |                    /
                          \                   |                   /
                           \                  |                  /
                            ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ASSETS / SENSORS / NETWORKS                          │
│ UAVs • UGVs • USVs • Towers • Ground Sensors • Relay Nodes • SATCOM        │
│ Threats • Blue Force Units • Orbital Assets • External Data Sources         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     DATA & INFRASTRUCTURE LAYER                            │
│  MariaDB • Telemetry Store • Mission Replay • Analytics • API Services     │
│  Local Node • Edge Compute • Command Center • Cloud Deployment             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Data Flows

### 1. Mission Flow

```text
Operator Intent
   ↓
Mission Manager
   ↓
Task Graph Generation
   ↓
Asset Assignment
   ↓
Autonomous Execution
   ↓
Mission Monitoring / Replan
```

### 2. Sensor-to-Action Flow

```text
Sensor Detection
   ↓
Event Bus
   ↓
Threat Classification
   ↓
COA Recommendation
   ↓
Authority Check
   ↓
Tasking / Effect Execution
```

### 3. Telemetry Flow

```text
Asset State
   ↓
Telemetry Stream
   ↓
State Registry
   ↓
COP / Analytics / Alerts
```

### 4. Degraded-Comms Flow

```text
Link Loss / Jamming / GPS Denial
   ↓
Health / Network Event
   ↓
Local Autonomy / Store-and-Forward
   ↓
Mission Continuity
   ↓
Resync When Link Restored
```

---

## Layer Definitions

| Layer | Role |
|---|---|
| Operator Layer | Human command, supervision, visualization, and approvals |
| Mission Control Layer | Mission lifecycle, tasking, authority, and orchestration |
| Autonomy & Intelligence Layer | Decision support, swarm logic, planning, and prediction |
| Adapter Layer | Integration boundary between AMOS and external systems |
| Asset / Sensor Layer | Physical and simulated platforms executing missions |
| Data & Infrastructure Layer | Storage, replay, analytics, APIs, and deployment services |

---

## AMOS Core Control Plane

The AMOS control plane is the stable platform layer responsible for mission-level coordination.

### Control Plane Services

| Service | Function |
|---|---|
| Mission Manager | Creates, updates, and tracks missions |
| Task Orchestrator | Converts intent into executable task graphs |
| Authority Engine | Enforces approval and delegation rules |
| Event Bus | Distributes platform events |
| State Registry | Maintains current operational state |
| Telemetry Services | Ingests and distributes state updates |
| Plugin Manager | Loads extensions and domain packs |

---

## Plugin Integration Points

AMOS is extensible through well-defined integration points.

```text
                  ┌──────────────────────────────┐
                  │        Mission Packs         │
                  └──────────────────────────────┘
                               ▲
                               │
┌───────────────┐  ┌──────────────────────────────┐  ┌───────────────────────┐
│ Asset Plugins │  │        AMOS Core            │  │  Analytics Plugins    │
└───────────────┘  └──────────────────────────────┘  └───────────────────────┘
                               ▲
                               │
                  ┌──────────────────────────────┐
                  │     Transport / Sensor       │
                  │          Plugins             │
                  └──────────────────────────────┘
```

### Plugin categories

- Asset Adapters
- Sensor Adapters
- Mission Packs
- Planner Plugins
- Analytics Plugins
- Transport Plugins

All plugin types rely on **AMOS Core Contracts**.

---

## Deployment Topologies

### Single-Node Development

```text
Laptop / Workstation
 ├─ Web UI
 ├─ Mission Engine
 ├─ Simulated Assets
 ├─ Event Bus
 └─ Database
```

### Edge Deployment

```text
Field Node
 ├─ Local Mission Services
 ├─ Edge Autonomy
 ├─ Transport Bridges
 └─ Store-and-Forward Queue
```

### Federated Deployment

```text
Regional / Theater Node
 ├─ Multi-Mission Coordination
 ├─ Shared Analytics
 ├─ Cross-Node State Exchange
 └─ Operator Collaboration
```

---

## Recommended README Insert

Add this near the top of the README:

```markdown
## Where AMOS Fits

AMOS sits **above robotics middleware** and **below mission applications**.

- Robotics frameworks like **ROS2, PX4, and ArduPilot** control individual platforms
- AMOS coordinates **missions across many autonomous systems simultaneously**
- It provides the missing layer for:
  - mission orchestration
  - human-machine teaming
  - swarm coordination
  - cross-domain autonomy
```

---

## Summary

AMOS is not just a robotics dashboard or simulation tool.

It is a **mission operating system** that coordinates assets, sensors, autonomy engines, and human operators into a unified control plane for autonomous operations.

This diagram is intended to help developers and partners immediately understand:

- where AMOS sits in the technology stack
- how mission data flows through the system
- how plugins extend the platform
- how AMOS becomes the operating system for autonomous mission systems
