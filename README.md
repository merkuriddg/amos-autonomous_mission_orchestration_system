# AMOS — Autonomous Mission Operating System

Multi-domain C2 platform for autonomous robotic platoon operations.
**v3.0 — Phase 22: Beyond Lattice**

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

AMOS goes beyond sensor-fusion-and-fire-control platforms by integrating Monte Carlo wargaming, autonomous swarm intelligence, cross-domain effects orchestration, space domain awareness, adaptive human-machine teaming, and resilient mesh networking into a single unified C2 system.

## Architecture

```
Flask + SocketIO (real-time WebSocket)
├── web/app.py              — Main server (~4100 lines, 100+ API routes)
├── web/templates/           — 30+ HTML views
├── mos_core/nodes/          — 22 autonomous subsystems
├── mos_core/docs/           — Document generators (OPORD, CONOP)
├── integrations/            — External system bridges (PX4, TAK, Link 16)
├── db/                      — MariaDB persistence layer (30 tables)
└── config/                  — Platoon config + locations
```

### Backend Modules (mos_core/nodes/)

| Module | Function |
|--------|----------|
| cognitive_engine.py | OODA loop + Monte Carlo COA scoring |
| nlp_mission_parser.py | Natural language mission orders |
| environment_effects.py | GPS denial, comms degradation |
| task_allocator.py | Auction-based multi-agent task assignment |
| red_force_ai.py | Adversarial AI with probe/attack/withdraw |
| sensor_fusion_engine.py | Multi-sensor track correlation + kill chain |
| commander_support.py | Risk scoring + contingency planning |
| learning_engine.py | Anomaly detection + engagement learning |
| kill_web.py | F2T2EA kill chain pipeline |
| roe_engine.py | Rules of engagement enforcement |
| threat_predictor.py | AI threat trajectory prediction |
| wargame_engine.py | Monte Carlo wargaming with Markov chain attrition |
| swarm_intelligence.py | Reynolds flocking, task auctions, emergent behaviors |
| isr_pipeline.py | Automatic target recognition + pattern-of-life analysis |
| effects_chain.py | Cross-domain effects orchestration (Cyber→EW→SIGINT→Kinetic) |
| space_domain.py | Keplerian orbital propagation, SATCOM, JADC2 mesh |
| hmt_engine.py | Human-machine teaming with adaptive autonomy |
| mesh_network.py | MANET with Dijkstra routing + frequency hopping |

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

### Phases 11–15 — Kill Chain & Readiness
- F2T2EA kill web pipeline with human-approval gate at ENGAGE
- Dynamic ROE posture management (WEAPONS HOLD/TIGHT/FREE)
- AI threat trajectory prediction with confidence intervals
- Battle damage assessment + supply chain logistics
- Domain-specific real-time WebSocket channels

### Phase 16 — Monte Carlo Wargaming
- 1000+ iteration Monte Carlo simulations on current force posture
- Markov chain force attrition modeling (operational → degraded → combat ineffective → destroyed)
- 5 approach strategies × 3 tempos with statistical comparison
- Risk assessment engine (LOW / MODERATE / HIGH / EXTREME)
- Auto-evaluation every 10s on live force posture

### Phase 17 — Autonomous Swarm Intelligence
- Reynolds flocking physics (separation, alignment, cohesion) with behavioral DNA profiles
- 5 base behaviors + 6 emergent behaviors (surround, funnel, pincer, screen, relay, decoy)
- Task auction protocol with multi-factor scoring
- Self-healing formations — auto-reorganize when assets are lost

### Phase 18 — ISR/ATR Pipeline
- Automatic Target Recognition with multi-sensor confidence scoring
- Pattern-of-Life analysis (8 states: STATIC through TRANSITING)
- Change detection with severity alerts
- Prioritized collection requirements with auto-sensor tasking

### Phase 19 — Cross-Domain Effects Chain
- Multi-domain strike orchestration: Cyber → EW → SIGINT → Kinetic → ISR
- 5 pre-built templates: SEAD, CYBER_KINETIC, QUICK_STRIKE, FULL_SPECTRUM, EW_CORRIDOR
- Cascade planning with auto-replan on stage failure

### Phase 20 — Space Domain + JADC2
- 9 simulated orbital assets (GPS, SATCOM, ISR, early warning, SIGINT, relay)
- Keplerian orbital propagation with ground track computation
- SATCOM link budget calculation + GPS denial zone management
- Space weather simulation (Kp index, solar flux, geomagnetic storms)
- JADC2 mesh topology with satellite ↔ asset connections

### Phase 21 — Human-Machine Teaming
- 5 autonomy levels: Manual → Advisory → Consensual → Monitored → Autonomous
- Trust calibration per domain, workload classification, fatigue assessment
- Automatic autonomy adaptation based on operator state
- Delegation protocol for domain authority transfer

### Phase 22 — Mesh Networking + Resilient Comms
- MANET simulation with 7 frequency bands (VHF through SATCOM)
- Dijkstra shortest-path routing between all node pairs
- Frequency hopping with 32-element pseudo-random sequences
- Store-and-forward message queuing for disconnected nodes
- Priority-class bandwidth allocation (FLASH/IMMEDIATE/PRIORITY/ROUTINE)
- Network resilience scoring (A–F grade)

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
POST /api/wargame/run               — Run Monte Carlo wargame scenario
GET  /api/swarm/status              — Swarm intelligence status
GET  /api/isr/targets               — ATR tracked targets
POST /api/effects/create            — Create effects chain
GET  /api/space/orbital             — Orbital asset status
GET  /api/hmt/status                — HMT operator status
GET  /api/mesh/topology             — Mesh network topology
GET  /api/mesh/resilience           — Network resilience score
```

## Database

MariaDB — 30 tables including: users, assets, audit_log, missions, mission_events, recording_sessions, recording_frames, chat_messages, asset_locks, wargame_scenarios, wargame_results, isr_collections, target_patterns, effects_chains, orbital_assets, satcom_links

## Tech Stack

- **Backend:** Python 3, Flask, Flask-SocketIO
- **Frontend:** Vanilla JS, Leaflet.js, WebSocket
- **Database:** MariaDB
- **Integrations:** MAVLink, CoT XML, TADIL J, ROS 2

## License

Proprietary — MavrixOne / Merkuri DDG
