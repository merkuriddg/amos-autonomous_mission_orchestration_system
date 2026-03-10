# AMOS Enterprise

AMOS Open Core provides the mission orchestration platform — multi-domain C2, real-time simulation, sensor fusion, mesh networking, and an extensible plugin system — free and open source under the Apache 2.0 License.

**AMOS Enterprise** adds advanced autonomy, analytics, and secure integrations used in operational deployments.

## Enterprise Modules

- **Cognitive Mission Engine** — OODA loop automation, Monte Carlo COA scoring, commander support with risk assessment and contingency planning
- **Monte Carlo Wargaming** — 1000+ iteration force-on-force simulations with Markov chain attrition modeling and statistical strategy comparison
- **Swarm Autonomy** — Reynolds flocking physics, behavioral DNA profiles, emergent behaviors (surround, funnel, pincer, screen, relay, decoy), task auction protocol
- **ISR / ATR Analytics** — Automatic target recognition, pattern-of-life analysis, change detection, prioritized collection requirements
- **Cross-Domain Effects Chain** — Multi-domain strike orchestration (Cyber → EW → SIGINT → Kinetic → ISR) with pre-built templates and cascade planning
- **COMSEC** — AES-256-GCM encryption, classification markers, cryptographic key lifecycle management
- **TAK / Link-16 / STANAG Integrations** — CoT XML bridge, TADIL J simulation, VMF, STANAG 4586, NFFI, OGC WMS/WFS
- **Human-Machine Teaming** — 5 autonomy levels, trust calibration, workload/fatigue assessment, adaptive delegation
- **Space Domain + JADC2** — Orbital asset propagation, SATCOM link budgets, GPS denial management, JADC2 mesh
- **Operational Planning Tools** — NLP mission parser, 5-paragraph OPORD generator, CONOP generator, mission briefings

## Licensing

Enterprise modules, integrations, and operational deployment tooling are available under commercial license from Merkuri LLC.

For licensing inquiries, contact: **enterprise@merkuri.com**

## Installation

Enterprise customers receive access to the private `amos-enterprise` repository. The enterprise overlay installs into the open-core platform:

```bash
# From your AMOS installation directory
python3 enterprise/install.py
```

Set `AMOS_EDITION=enterprise` in your `.env` file and restart the server.

## Open Core vs Enterprise

| Capability | Open Core | Enterprise |
|---|---|---|
| C2 Console + Tactical Map | ✓ | ✓ |
| Real-time Asset Simulation | ✓ | ✓ |
| Threat Detection + Tracking | ✓ | ✓ |
| EW / SIGINT / Cyber Ops | ✓ | ✓ |
| Waypoints + Geofencing | ✓ | ✓ |
| Sensor Fusion | ✓ | ✓ |
| Mesh Networking | ✓ | ✓ |
| Plugin System | ✓ | ✓ |
| 200+ API Routes | ✓ | ✓ |
| Cognitive Engine + COA | | ✓ |
| Monte Carlo Wargaming | | ✓ |
| Swarm Intelligence | | ✓ |
| ISR / ATR Pipeline | | ✓ |
| Effects Chain | | ✓ |
| COMSEC Encryption | | ✓ |
| TAK / Link-16 / STANAG | | ✓ |
| Human-Machine Teaming | | ✓ |
| Space Domain / JADC2 | | ✓ |
| NLP Mission Planning | | ✓ |
| 300+ API Routes | | ✓ |
