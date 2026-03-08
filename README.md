# AMOS — Autonomous Mission Operating System v2.0 + Phase 10

**AMOS** is an autonomous systems integration platform for robotic platoon command and control.
It orchestrates 25+ autonomous assets across air, ground, and maritime domains under
human-on-the-loop supervision with AI-powered decision support.

Developed for the **Mavrix1 Robotic Platoon** specification.

## Quick Start (macOS / Standalone)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install flask flask-socketio pyyaml
python3 web/app.py
# Open http://localhost:2600
```

**Logins:** `commander`/`mavrix2026` (full access), `pilot`/`wings2026`, `grunt`/`hooah2026`, `sailor`/`anchor2026`, `observer`/`watch2026`, `field`/`tactical2026`

## Phase 10 Modules (`mos_core/nodes/`)

- **cognitive_engine.py** — OODA loop pipeline, Monte Carlo COA generation, explainable reasoning
- **nlp_mission_parser.py** — Natural language order decomposition, asset/group resolution
- **environment_effects.py** — GPS denial zones, RF link budget, mesh topology, auto-escalation
- **task_allocator.py** — Auction-based task assignment, dynamic re-tasking, temporal planning
- **red_force_ai.py** — Adversarial AI with probe/attack/withdraw FSM, frequency hopping, deception
- **sensor_fusion_engine.py** — Multi-sensor track correlation, uncertainty ellipses, kill chain
- **commander_support.py** — Resource burn-down, contingency planning, mission risk scoring
- **learning_engine.py** — AAR pattern extraction, anomaly detection, swarm behavior tuning

## Frontend Pages

`/fusion` — Sensor fusion tracks, kill chain, coverage gaps
`/cognitive` — OODA loops, COAs, reasoning chains
`/contested` — GPS denial, mesh topology, comms status
`/redforce` — Red force units, strategy, spawn controls

## Integration Bridges (`integrations/`)

PX4, ArduPilot (MAVLink), ROS 2 (Humble), TAK (CoT/ATAK), Nav2, MOOS-IvP, SDR (GNU Radio), Link-16 simulator

## API Routes

See `docs/API_REFERENCE.md` for full details. Key Phase 10 endpoints:

- `GET /api/cognitive/ooda` — OODA loop states
- `GET /api/fusion/tracks` — Fused sensor tracks
- `GET /api/contested/status` — GPS/comms environment
- `GET /api/redforce/units` — Red force positions
- `GET /api/commander/risk` — Mission risk score
- `GET /api/learning/aar` — After-action review
- `POST /api/nlp/execute` — Natural language orders
- `POST /api/tasks/assign` — Task allocation

## Dual-Mode Operation

**Standalone (macOS/Any OS):** Flask/SocketIO web app with simulated assets. No ROS 2 required.

**Full ROS 2 (Ubuntu):** Hardware-in-the-loop via integration bridges.

## Principles

- Human-on-the-loop: All lethal effects require HPL authorization
- 5-tier autonomy: MANUAL, ASSISTED, COLLABORATIVE, SWARM, COGNITIVE
- Domain agnostic: Unified C2 across air, ground, maritime
- Contested-ready: GPS-denied, comms-degraded environment support
