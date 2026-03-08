# AMOS — Autonomous Mission Operating System

Multi-domain C2 platform for autonomous robotic platoon operations.

## Quick Start

```bash
source .venv/bin/activate
python3 web/app.py
```

Open **http://localhost:2600** — Login: `commander` / `mavrix2026`

### All Users

| Username | Password | Role | Domain |
|----------|----------|------|--------|
| commander | mavrix2026 | Commander | All |
| pilot | wings2026 | Pilot | Air |
| grunt | hooah2026 | Ground Op | Ground |
| sailor | anchor2026 | Maritime Op | Maritime |
| observer | watch2026 | Observer | All |
| field | tactical2026 | Field Op | All |

## What AMOS Does

AMOS manages a **25-asset autonomous robotic platoon** across air, ground, and maritime domains. A small team of human operators sets mission objectives; the system coordinates robotic assets to achieve them.

**Core concept:** Human-on-the-loop — operators define *intent*, autonomous systems execute *tasks*.

## Architecture

```
Flask + SocketIO (real-time WebSocket)
├── web/app.py              — Main server (~2000 lines, 60+ API routes)
├── web/templates/           — 20+ HTML views
├── mos_core/nodes/          — 8 autonomous subsystems
├── mos_core/docs/           — Document generators (OPORD, CONOP)
├── integrations/            — External system bridges (PX4, TAK, Link 16)
├── db/                      — MariaDB persistence layer
└── config/                  — Platoon config + locations
```

### Backend Modules (mos_core/nodes/)

| Module | Function |
|--------|----------|
| cognitive_engine.py | OODA loop + Monte Carlo COA scoring |
| nlp_mission_parser.py | Natural language mission orders |
| environment_effects.py | GPS denial, comms degradation, mesh networking |
| task_allocator.py | Auction-based multi-agent task assignment |
| red_force_ai.py | Adversarial AI with probe/attack/withdraw |
| sensor_fusion_engine.py | Multi-sensor track correlation + kill chain |
| commander_support.py | Risk scoring + contingency planning |
| learning_engine.py | Anomaly detection + engagement learning |

### Integration Bridges (integrations/)

| Bridge | Protocol | Status |
|--------|----------|--------|
| PX4 SITL | MAVLink | Auto-connect if running |
| TAK/ATAK | CoT XML (UDP/TCP) | Connect via UI |
| Link 16 | TADIL J simulation | Always active |
| ROS 2 | rclpy bridge | Connect if available |
| ArduPilot | MAVLink dialect | Available |
| MOOS-IvP | Maritime autonomy | Available |
| GNU Radio/SDR | RF hardware | Available |

## Features by Phase

### Phase 10 — Core Platform
- 25 simulated assets (air/ground/maritime) with real-time movement
- 22 threats with autonomous detection and tracking
- C2 console with Leaflet map, asset control, threat engagement
- Digital twin dashboard, AWACS view, field 3D view
- EW warfare, SIGINT analysis, cyber ops
- Countermeasures, swarm formation control (6 patterns)
- HAL autonomy engine, voice commands (18 types)
- NLP mission parser, cognitive engine with OODA + COA
- Contested environment with GPS denial + mesh networking
- Red force AI, sensor fusion, commander support, learning engine

### Phase 1 — Defense-Grade Foundation
- MariaDB persistence (9 tables), hashed password auth
- Asset CRUD with write-through, audit trail on all API writes
- Mission recording with frame-by-frame replay

### Phase 2 — Demo Power
- Multi-operator collaboration with cursor sharing
- Team chat (4 channels), asset locking
- Mobile tactical view, PX4 SITL bridge

### Phase 3 — Differentiation
- AI-driven COA engine (Monte Carlo scored, replaces random recs)
- 5-paragraph OPORD generator from live state
- CONOP generator, mission briefing, document center with download

### Phase 4 — Tactical Integration & Analytics
- TAK/ATAK CoT bridge with connect/disconnect UI
- Link 16 TADIL J simulation (J2.2/J3.2/J7.0 messages)
- Unified integration hub, mission analytics dashboard
- Real-time metrics: threat progress, fleet health, COA decisions, risk trend

## Key API Routes

```
GET  /api/assets                    — All assets
GET  /api/threats                   — All threats
POST /api/coa/generate              — AI-scored COAs
GET  /api/hal/recommendations       — Cognitive engine recommendations
POST /api/docs/opord                — Generate 5-paragraph OPORD
POST /api/docs/conop                — Generate CONOP summary
GET  /api/bridge/all                — All integration statuses
GET  /api/bridge/link16/tracks      — Link 16 tactical picture
GET  /api/analytics/summary         — Aggregated mission metrics
POST /api/voice/command             — Voice command processing
```

## Database

MariaDB (`amos`) — tables: users, assets, audit_log, missions, mission_events, recording_sessions, recording_frames, chat_messages, asset_locks

## Tech Stack

- **Backend:** Python 3, Flask, Flask-SocketIO
- **Frontend:** Vanilla JS, Leaflet.js, WebSocket
- **Database:** MariaDB
- **Integrations:** MAVLink, CoT XML, TADIL J, ROS 2

## License

Proprietary — MavrixOne / Merkuri DDG
