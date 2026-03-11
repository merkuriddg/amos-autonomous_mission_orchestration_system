# ZMeta ISR Metadata Integration — Setup Guide

## Overview

AMOS integrates with the [ZMeta v1.0 specification](https://github.com/JTC-byte/zmeta-spec),
a transport-agnostic, event-based metadata standard for resilient ISR.  The
integration supports **bidirectional** data flow:

- **Ingest** — UDP listener receives ZMeta events from edge nodes, drones,
  sensors, or the ZMeta reference gateway.
- **Egress** — AMOS emits its fused picture as ZMeta STATE_EVENTs and
  waypoint commands as COMMAND_EVENTs.

## Requirements

- AMOS running (any edition — no feature gate)
- Python 3.11+ (no extra pip dependencies — stdlib only)
- A ZMeta-compatible sensor node, gateway, or the reference replay tool

## Quick Start

### 1. Start AMOS

```bash
AMOS_EDITION=enterprise nohup .venv/bin/python3 web/app.py > /tmp/amos.log 2>&1 &
```

### 2. Connect the ZMeta Bridge

From the AMOS web UI:
1. Navigate to **Integrations** → **ISR METADATA** section
2. Set the **Listen Port** (default: 5555) — this is where ZMeta events arrive
3. Set **Forward Host/Port** — where AMOS will emit egress events
4. Choose a **Profile** (H = full fidelity, M = IP radio, L = LoRa thin)
5. Click **CONNECT**

Or via API:
```bash
curl -X POST http://localhost:2600/api/v1/bridge/zmeta/connect \
  -H 'Content-Type: application/json' \
  -d '{"listen_port": 5555, "forward_host": "127.0.0.1", "forward_port": 5556, "profile": "H"}'
```

### 3. Send Test Events

Use the ZMeta reference tools to send sample events:

```bash
# Clone the ZMeta spec repo
git clone https://github.com/JTC-byte/zmeta-spec.git
cd zmeta-spec

# Send example events to AMOS
python tools/udp_sender.py --file examples/zmeta-examples-1.0.jsonl --host 127.0.0.1 --port 5555

# Or replay with timing
python tools/replay.py --file examples/zmeta-command-examples.jsonl --delay-ms 200 --host 127.0.0.1 --port 5555
```

### 4. Verify

Check bridge status:
```bash
curl http://localhost:2600/api/v1/bridge/zmeta/status
```

View ingested events:
```bash
curl http://localhost:2600/api/v1/bridge/zmeta/events
```

View fused tracks:
```bash
curl http://localhost:2600/api/v1/bridge/zmeta/tracks
```

## API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/v1/bridge/zmeta/status` | GET | Bridge status + metrics |
| `/api/v1/bridge/zmeta/connect` | POST | Start UDP listener |
| `/api/v1/bridge/zmeta/disconnect` | POST | Stop listener |
| `/api/v1/bridge/zmeta/events` | GET | All recent events (all types) |
| `/api/v1/bridge/zmeta/tracks` | GET | STATE + FUSION track events |
| `/api/v1/bridge/zmeta/commands` | GET | Inbound + outbound commands |
| `/api/v1/bridge/zmeta/link-status` | GET | Transport health events |
| `/api/v1/bridge/zmeta/emit-state` | POST | Emit a STATE_EVENT from AMOS |
| `/api/v1/bridge/zmeta/emit-command` | POST | Emit a COMMAND_EVENT from AMOS |

## ZMeta Event Types → AMOS Mapping

| ZMeta Event | AMOS EventBus | Description |
|-------------|---------------|-------------|
| OBSERVATION_EVENT (RF) | `ew.emitter_detected` | RF signal observation |
| OBSERVATION_EVENT (EO/IR/ACOUSTIC) | `sensor.contact_detected` | Non-RF observation |
| INFERENCE_EVENT | `zmeta.inference` | AI/ML classification claim |
| FUSION_EVENT | `zmeta.track_update` | Cross-sensor fused track |
| STATE_EVENT | `zmeta.track_state` | Operator-grade belief snapshot |
| COMMAND_EVENT | `zmeta.command_received` | Inbound waypoint/mission task |
| SYSTEM_EVENT (LINK_STATUS) | `zmeta.link_status` | Transport health |
| SYSTEM_EVENT (TASK_ACK) | `zmeta.task_ack` | Command acknowledgement |

## Egress — Emitting ZMeta Events

### Emit a Track State

```bash
curl -X POST http://localhost:2600/api/v1/bridge/zmeta/emit-state \
  -H 'Content-Type: application/json' \
  -d '{"track_id": "TRK-001", "lat": 34.05, "lng": -118.24, "alt_m": 120, "confidence": 0.85}'
```

### Emit a Command

```bash
curl -X POST http://localhost:2600/api/v1/bridge/zmeta/emit-command \
  -H 'Content-Type: application/json' \
  -d '{"task_type": "GOTO", "lat": 34.01, "lng": -118.01, "priority": "HIGH"}'
```

## Architecture

```
Edge Sensors/Drones (ZMeta EDGE nodes)
        │ UDP (ZMeta v1.0 JSON)
        ▼
    ┌─────────────────────────────┐
    │   AMOS ZMeta Bridge         │
    │   (integrations/zmeta_bridge│
    │    .py)                     │
    │                             │
    │   UDP Listener ← Ingest    │
    │   UDP Sender  → Egress     │
    └─────────┬───────────────────┘
              │
              ▼
    ┌─────────────────────────────┐
    │   AMOS EventBus             │
    │                             │
    │   → sensor_fusion           │
    │   → kill_web                │
    │   → ew / sigint             │
    │   → waypoint_nav            │
    │   → aar_events              │
    │   → comms_monitor           │
    └─────────────────────────────┘
```

## Profiles

ZMeta supports three bandwidth profiles:

- **H (Full)** — All event types, full fidelity.  Use on LTE/broadband links.
- **M (IP Radio)** — STATE + FUSION + selective OBSERVATION + COMMAND.
  Balanced for constrained IP links.
- **L (LoRa Thin)** — STATE + COMMAND + SYSTEM only.  Severe bandwidth
  constraint / denied environment.

The profile selection affects **egress only** — AMOS ingests events from
all profiles.  Set the profile in the UI or via the `profile` field in
the connect API call.

## Optional: ZMeta Reference Gateway

For full policy enforcement, schema validation, and CoT emission, you can
run the ZMeta reference gateway upstream of AMOS:

```bash
cd zmeta-spec
python tools/run_gateway.py --profile H --listen-port 5554 --forward-port 5555
```

This validates events before they reach AMOS and can also emit CoT XML to
a TAK server.

## Files

| File | Description |
|------|-------------|
| `integrations/zmeta_bridge.py` | ZMetaBridge class — UDP ingest + egress |
| `plugins/zmeta_adapter/__init__.py` | Plugin adapter — EventBus wiring |
| `plugins/zmeta_adapter/plugin.yaml` | Plugin manifest |
