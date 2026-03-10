# AMOS — Autonomous Mission Orchestration System

**Mission Operating System for Autonomous Systems**

AMOS is a **multi-domain command-and-control platform** that enables small teams of human operators to supervise and coordinate autonomous robotic assets across **air, ground, maritime, cyber, and space domains**.

Operators define **mission intent**.  
AMOS orchestrates assets, sensors, autonomy engines, and communications to execute those missions.

**v5.2 — API Versioning • CI/CD • System Scripts • Edition Dashboard**

---

## Platform Overview

### Mission Console
AMOS provides a unified operational interface for supervising autonomous missions across multiple robotic assets.

<!-- TODO: Add screenshot -->

### Mission Planning
Operators define mission intent and assign assets. AMOS converts mission plans into executable task graphs that coordinate robotic teams.

<!-- TODO: Add screenshot -->

### Simulation Environment
AMOS includes a built-in simulation environment for testing mission scenarios, autonomy behaviors, and swarm coordination.

<!-- TODO: Add screenshot -->

### Telemetry & Event Stream
An event-driven architecture tracks mission state, asset health, and sensor detections in real time.

<!-- TODO: Add screenshot -->

### Extensible Plugin Architecture
AMOS supports asset adapters, sensor integrations, mission packs, and autonomy modules through a modular plugin system.

<!-- TODO: Add screenshot -->

---


## Quick Start

```bash
cp .env.example .env          # configure edition + dev tools
source .venv/bin/activate
python3 web/app.py
```

Open **http://localhost:2600** — Login: `commander` / `amos_op1`

### All Users

| Username | Password | Role | Domain |
|----------|----------|------|--------|
| commander | amos_op1 | Commander | All |
| pilot | wings2026 | Pilot | Air |
| grunt | hooah2026 | Ground Op | Ground |
| sailor | anchor2026 | Maritime Op | Maritime |
| observer | watch2026 | Observer | All |
| field | tactical2026 | Field Op | All |

## What AMOS Does

AMOS coordinates autonomous robotic forces — from small platoons to formations of hundreds or thousands of assets — operating across multiple domains.

A small team of human operators defines mission objectives while autonomous systems execute the operational workload. The default configuration ships with a 25-asset platoon, but the platform scales to arbitrary force sizes across unlimited theaters.

Core capabilities include:
- multi-robot coordination
- sensor fusion and autonomous cueing
- swarm intelligence and task allocation
- mission planning and execution
- real-time telemetry and threat tracking
- contested environment networking
- human-machine teaming

AMOS integrates capabilities normally spread across multiple systems — mission planning, autonomy orchestration, sensor fusion, wargaming, and resilient networking — into a single platform.


## Editions

AMOS ships in two editions controlled by `AMOS_EDITION` in `.env`:

- **Open** (`AMOS_EDITION=open`) — Core C2 platform: 200+ API routes, map, assets, threats, EW, SIGINT, cyber, ROE, waypoints, sensor fusion, mesh networking, voice commands, plugin system. Free and open-source.

- **Enterprise** (`AMOS_EDITION=enterprise`) — Full platform: 300+ API routes. Adds cognitive engine (OODA/COA), NLP mission parser, Monte Carlo wargaming, swarm intelligence, kill web, ISR/ATR, effects chain, space domain, human-machine teaming, COMSEC, TAK/Link 16/VMF/STANAG integrations, OPORD/CONOP generation, and more.

Per-feature overrides let you enable individual enterprise modules in open mode (e.g. `AMOS_ENABLE_COGNITIVE=true`). See `.env.example` for all flags.

## System Architecture

![AMOS Architecture](docs/images/amos_architecture.png)

```
Applications
  Mission Packs • Analytics • Operator Tools
        ▲
        │
AMOS Platform
  Mission Orchestration • Autonomy Engines • Swarm Coordination
        ▲
        │
Integration Layer
  ROS2 • MAVLink • TAK • MQTT • DDS • Link-16
        ▲
        │
Assets & Sensors
  Drones • Ground Robots • Maritime Vehicles • Satellites
```

**Key Features**
- Autonomous mission orchestration
- Multi-robot swarm coordination
- Monte Carlo operational wargaming
- Cross-domain effects planning
- Human-machine teaming
- Resilient mesh networking
- Extensible plugin ecosystem

```
amos/
├── web/
│   ├── app.py               — Slim orchestrator (registers blueprints)
│   ├── extensions.py        — Flask app factory, config, login
│   ├── state.py             — Shared mutable state + subsystem init
│   ├── edition.py           — AMOS_EDITION feature flags
│   ├── edition_service.py   — Feature toggle abstraction layer
│   ├── simulation_engine.py — Background sim tick loop
│   ├── websockets.py        — Socket.IO event handlers
│   ├── routes/              — 11 core blueprints (auth, assets, ops, scripts, edition, etc.)
│   ├── enterprise/          — 4 enterprise blueprints (intelligence, warfare, security, defense)
│   └── templates/           — Terminal-aesthetic UI (40+ views)
├── core/                    — Data model, adapters, COMSEC, geo utilities
├── services/                — 36 autonomous subsystems
├── integrations/            — PX4, TAK, Link 16, MQTT, DDS, Kafka bridges
├── plugins/                 — Plugin system (PX4, ROS 2, example drone)
├── enterprise/              — Overlay installer for private enterprise repo
├── db/                      — MariaDB persistence (36 tables)
├── config/                  — Platoon config + theater locations
├── tests/                   — 209 automated tests (3-layer: route, service, contract)
├── .github/workflows/       — CI/CD pipelines (core + enterprise)
└── docs/                    — Architecture, SDK, simulation, API versioning
```

### Core (core/)

| Module | Function |
|--------|----------|
| data_model.py | Canonical data model (Track, Detection, Command, etc.) |
| schema_validator.py | Schema validation for data contracts |
| adapter_base.py | Adapter manager + legacy bridge |
| geo_utils.py | Haversine, Vincenty, UTM, MGRS, GeoJSON conversion |
| comsec.py | AES-256-GCM encryption + classification markers |
| key_manager.py | Cryptographic key lifecycle management |
| security_audit.py | Security audit logging |

### Services (services/)

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
| video_pipeline.py | Full-motion video processing pipeline |
| klv_parser.py | KLV metadata extraction |
| imagery_handler.py | Imagery ingest and management |

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

All API routes are dual-mounted at `/api/v1/` (primary) and `/api/` (deprecated compat).
See `docs/platform/API_VERSIONING.md` for the full versioning policy.

```
GET  /api/v1/assets                 — All assets
GET  /api/v1/threats                — All threats
POST /api/v1/coa/generate           — AI-scored COAs
GET  /api/v1/hal/recommendations    — Cognitive engine recommendations
POST /api/v1/docs/opord             — Generate 5-paragraph OPORD
GET  /api/v1/bridge/all             — All integration statuses
GET  /api/v1/theater/list           — Theater locations
GET  /api/v1/healthz                — Liveness probe (no auth)
GET  /api/v1/readyz                 — Readiness probe (no auth)
GET  /api/v1/scripts/git/status     — Git repo status (commander, dev only)
GET  /api/v1/edition/status         — Current edition + feature flags
POST /api/v1/edition/toggle         — Toggle runtime feature flag
GET  /api/v1/edition/bundles        — Feature bundles with status
GET  /api/v1/analytics/summary      — Aggregated mission metrics
POST /api/v1/voice/command          — Voice command processing
POST /api/v1/wargame/run            — Run Monte Carlo wargame scenario
GET  /api/v1/mesh/resilience        — Network resilience score
```

## Testing

209 automated tests across 3 layers:

- **Route tests** — auth, pages, assets, missions, simulation, ops, scripts, edition management
- **Service tests** — edition service, plugin loader, event bus
- **Contract tests** — schema validation, smoke tests for both editions

```bash
# Run all tests
python3 -m pytest tests/ -v --tb=short

# With coverage
python3 -m pytest tests/ --cov=web --cov=core --cov=services --cov-report=term-missing
```

## CI/CD

GitHub Actions workflows in `.github/workflows/`:

- **core-ci.yml** — Lint (ruff) + tests on Python 3.11/3.12 for core edition
- **enterprise-ci.yml** — Same matrix + smoke tests for enterprise paths

Both enforce 50% coverage threshold.

## Database

MariaDB — 36 tables including: users, assets, audit_log, missions, mission_events, recording_sessions, recording_frames, chat_messages, asset_locks, wargame_scenarios, wargame_results, isr_collections, target_patterns, effects_chains, orbital_assets, satcom_links, tracks, detections, video_streams, security_audit

## Tech Stack

- **Backend:** Python 3, Flask, Flask-SocketIO
- **Frontend:** Vanilla JS, Leaflet.js, CesiumJS, WebSocket
- **Database:** MariaDB
- **Testing:** pytest, pytest-cov
- **CI/CD:** GitHub Actions (ruff lint, Python 3.11+3.12 matrix)
- **Integrations:** MAVLink, CoT XML, TADIL J, ROS 2, MQTT, DDS, Kafka, VMF, STANAG 4586, NFFI, OGC WMS/WFS
- **Security:** AES-256-GCM encryption, HMAC, key management, security audit logging

## Plugin Development

See `docs/platform/AMOS_Plugin_SDK.md` for the full Plugin SDK guide.
Example plugins live in `plugins/` — copy `plugins/example_drone/` to start building your own.

## License

Proprietary — merkuri, llc
