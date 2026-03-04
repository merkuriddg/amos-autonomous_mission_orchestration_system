# ⬡ MOS — Mission Operating System

> **"Tech as a Teammate"**

**MOS** (pronounced *"moz"*) is a modular, ROS 2-based Mission Operating System designed to
integrate and orchestrate autonomous robotic systems within a Special Operations Robotics Platoon.
MOS acts as the orchestration brain on top of existing open-source frameworks — providing unified
command and control over air, ground, and maritime autonomous assets.

Developed by **Mavrix Dynamics**

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Workspace Structure](#workspace-structure)
- [ROS 2 Nodes](#ros-2-nodes)
- [Web Interfaces](#web-interfaces)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Phase Development Log](#phase-development-log)
  - [Phase 1 — Foundation](#phase-1--foundation)
  - [Phase 2 — Core Autonomy](#phase-2--core-autonomy)
  - [Phase 3 — Threat Detection & Sensor Fusion](#phase-3--threat-detection--sensor-fusion)
  - [Phase 4 — C2 Console & Visualization](#phase-4--c2-console--visualization)
  - [Phase 5 — Comms, AAR & Digital Twin](#phase-5--comms-aar--digital-twin)
  - [Phase 6 — AI Decision Engine, Geofencing, TAK, 3D, Echelon](#phase-6--ai-decision-engine-geofencing-tak-3d-echelon)
  - [Phase 7 — AWACS Autonomous Command Drone](#phase-7--awacs-autonomous-command-drone)
  - [Phase 8 — Hardware Abstraction Layer & Field Deployment](#phase-8--hardware-abstraction-layer--field-deployment)
- [Hardware Integration Guide](#hardware-integration-guide)
- [Docker Deployment](#docker-deployment)
- [ATAK/TAK Integration](#ataktak-integration)
- [Autonomy Model](#autonomy-model)
- [Mission Types](#mission-types)
- [Swarm Commands](#swarm-commands)
- [Safety & DDIL](#safety--ddil)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [License](#license)

---

## Overview

MOS manages a platoon of **25–40 autonomous units** across three domains:

| Domain | Asset Prefix | Examples |
|--------|-------------|----------|
| **Air** | `MVRX-A##` | Reconnaissance drones, strike UAS, AWACS relay |
| **Ground** | `MVRX-G##` | UGVs, logistics robots, sensor platforms |
| **Maritime** | `MVRX-M##` | USVs, underwater sensors |
| **AWACS** | `AWACS-#` | Airborne C2 relay, sensor aggregation |

### Key Capabilities

- **5-Tier Autonomy** — Manual → Assisted → Collaborative → Swarm → Cognitive
- **6 Mission Types** — ISR, Security, Precision Effects, Logistics, SAR, EW/SIGINT
- **AI Decision Engine** — Automatic Course of Action (COA) generation
- **Swarm Control** — Formations, scatter, RTB, hold
- **Sensor Fusion** — EO/IR, SIGINT, RADAR, LIDAR, SONAR
- **Threat Detection** — Automated classification pipeline
- **ATAK/TAK Bridge** — Cursor on Target (CoT) interoperability
- **3D Tactical View** — CesiumJS globe visualization
- **Multi-Echelon C2** — Role-based dashboards (HPL, ASC, BN TOC)
- **AWACS Drone** — Airborne command relay with auto-orbit
- **Hardware Bridge** — Real drone/robot connection via MAVROS/Nav2
- **DDIL Operations** — Denied, Disrupted, Intermittent, Limited comms handling
- **Docker Deployment** — One-command field deployment

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Middleware | ROS 2 Humble + DDS (CycloneDDS) |
| Autopilot | PX4 / ArduPilot via MAVROS |
| Navigation | Nav2 (ground robots) |
| C2 Frontend | Flask + Leaflet.js + CesiumJS |
| Comms | DDS, MAVLink, CoT/XML over UDP multicast |
| Containerization | Docker + Docker Compose |

---

## Architecture
