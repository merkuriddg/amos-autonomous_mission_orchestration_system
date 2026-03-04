# MOS — Mission Operating System

> *"Tech as a Teammate"*

**MOS** (spoken as "moz") is a Mission Operating System for orchestrating autonomous robotic systems across air, ground, and maritime domains. Designed for special operations, MOS integrates swarm coordination, sensor fusion, electronic warfare, cyber defense, and human-on-the-loop command & control into a single unified platform.

## Quick Start

```bash
# Clone
git clone https://github.com/merkuriddg/mos-mission-operating-system.git
cd mos-mission-operating-system

# Install
pip3 install -r requirements.txt

# Launch
python3 web/app.py
```

Open **http://localhost:5000** → Login: `commander` / `mavrix2026`

### Docker

```bash
docker compose up --build
```

## Architecture

```
┌───────────────────────────────────────────────┐
│                 WEB C2 CONSOLE                │
│  C2 │ EW │ SIGINT │ CYBER │ CM │ HAL │ FIELD │
├───────────────────────────────────────────────┤
│              FLASK + SOCKETIO                 │
│          Real-time WebSocket Push             │
├───────────────────────────────────────────────┤
│              MOS CORE ENGINE                  │
│  Asset Registry │ Autonomy Mgr │ Swarm Orch  │
│  Threat Detect  │ Sensor Fusion │ COA Engine │
│  EW Manager │ SIGINT │ Cyber Ops │ Geofence  │
├───────────────────────────────────────────────┤
│            SIMULATION ENGINE                  │
│  27 Assets │ 10 Threats │ Tampa Bay AO        │
├───────────────────────────────────────────────┤
│            INTEGRATION LAYER                  │
│  ATAK/TAK Bridge │ MAVLink │ ROS 2 (future)  │
└───────────────────────────────────────────────┘
```

## Platoon Composition (27 Assets)

| Callsign | Type | Domain | Role |
|----------|------|--------|------|
| REAPER-01/02 | MQ-9B | Air | ISR / Strike |
| GHOST-01–04 | Small UAS | Air | Recon / EW |
| VALKYR-01/02 | Loyal Wingman | Air | Air Superiority |
| AWACS-01/02 | High-Alt UAS | Air | Airborne C2 |
| TALON-01–04 | Armed UGV | Ground | Direct Action |
| MULE-01–04 | Logistics UGV | Ground | Resupply |
| SPECTR-01–04 | Sensor UGV | Ground | SIGINT / Recon |
| TRITON-01/02 | USV | Maritime | Coastal Patrol |
| KRAKEN-01 | UUV | Maritime | Subsurface Recon |

## Dashboards (13)

| Route | Dashboard | Description |
|-------|-----------|-------------|
| `/` | C2 Console | Main tactical map with live tracks |
| `/dashboard` | Digital Twin | Full platoon status matrix |
| `/ew` | EW Spectrum | RF waterfall + emitter table |
| `/sigint` | SIGINT | Signal intercept database |
| `/cyber` | Cyber Ops | Network event feed + blocking |
| `/countermeasures` | Active CM | Jam/intercept/block controls |
| `/planner` | Mission Plan | Waypoint-based mission creation |
| `/hal` | HAL Engine | AI recommendations + approve/deny |
| `/aar` | After Action | Timeline replay with export |
| `/awacs` | AWACS | Airborne C2 status |
| `/field` | Field View | Mobile-optimized tactical display |
| `/login` | Auth | Role-based login |

## RBAC Roles

| Role | Access Level | Lethal Auth |
|------|-------------|-------------|
| Commander | All dashboards | ✅ |
| EW Officer | EW, SIGINT, CM | ❌ |
| Cyber Operator | Cyber, CM | ❌ |
| Pilot | C2, Planner | ❌ |
| Analyst | SIGINT, AAR | ❌ |
| Observer | C2, Field (read-only) | ❌ |

## Phase History

| Phase | Feature |
|-------|---------|
| 1-4 | Core nodes, asset registry, autonomy, swarm, sensor fusion |
| 5 | Comms mesh, AAR, digital twin |
| 6 | COA engine, geofencing, ATAK bridge, multi-echelon C2 |
| 7 | AWACS autonomous command drone |
| 8 | HAL for real hardware, DDIL ops, Docker |
| 9 | EW/SIGINT/Cyber warfare suite (5 nodes, 3 dashboards) |
| 9.5 | Live simulation engine (Tampa Bay Interdiction) |

## License

Apache 2.0 — Copyright 2026 Mavrix Defense Systems
