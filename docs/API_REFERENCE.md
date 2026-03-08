# AMOS API Reference

All endpoints require authentication via session cookie (login at `/login`).
Base URL: `http://localhost:2600`

## Core APIs

### Assets
- `GET /api/assets` — All assets (filtered by user domain)
- `GET /api/assets/summary` — Count by domain, status, role
- `GET /api/assets/<id>` — Single asset detail + waypoints

### Threats
- `GET /api/threats` — All tracked threats

### Electronic Warfare
- `GET /api/ew/status` — EW assets, active jams, intercepts
- `POST /api/ew/jam` — Activate jammer `{jammer_id, freq_mhz, technique}`
- `POST /api/ew/jam/stop` — Stop jam `{op_id}`

### SIGINT
- `GET /api/sigint` — Recent intercepts (last 100)
- `GET /api/sigint/summary` — Intercept stats
- `GET /api/sigint/emitters` — Known emitter database

### Cyber
- `GET /api/cyber/events` — Cyber events (last 100)
- `GET /api/cyber/summary` — Threat/blocked stats
- `POST /api/cyber/block` — Block IP `{ip}` or event `{event_id}`

### Countermeasures
- `POST /api/cm/engage` — Neutralize threat `{threat_id, type}`
- `GET /api/cm/log` — Engagement log

### HAL (AI Recommendations)
- `GET /api/hal/recommendations` — Pending AI recommendations
- `POST /api/hal/action` — Approve/reject `{id, action}`
- `POST /api/coa/generate` — Generate courses of action

### Navigation
- `GET /api/waypoints` — All active waypoints
- `POST /api/waypoints/set` — Set waypoint `{asset_id, lat, lng}`
- `POST /api/waypoints/add` — Add waypoint to queue
- `POST /api/waypoints/clear` — Clear waypoints `{asset_id}`

### Geofences
- `GET /api/geofences` — All geofences
- `POST /api/geofences/create` — Create geofence
- `POST /api/geofences/delete` — Delete geofence `{id}`
- `GET /api/geofences/alerts` — Active alerts

### Voice Commands
- `POST /api/voice/command` — Process voice `{transcript}`

### Swarm
- `GET /api/swarm` — Active swarms
- `POST /api/swarm/create` — Create swarm `{swarm_id, assets, formation}`
- `POST /api/swarm/formation` — Set formation `{domain, formation}`

## Phase 10 APIs

### Cognitive Engine
- `GET /api/cognitive/ooda` — Active OODA loop states per threat
- `GET /api/cognitive/coa` — Generated courses of action (by threat)
- `GET /api/cognitive/reasoning` — AI reasoning recommendations

### NLP Mission Parser
- `POST /api/nlp/parse` — Parse natural language `{text}` (returns structured orders)
- `POST /api/nlp/execute` — Parse + execute orders `{text}`

### Contested Environment
- `GET /api/contested/status` — GPS denial, comms, mesh, escalations
- `POST /api/contested/gps-denial/add` — Add GPS denial zone `{lat, lng, radius_nm}`
- `POST /api/contested/gps-denial/remove` — Remove zone `{zone_id}`
- `GET /api/contested/mesh` — Mesh network topology

### Task Allocator
- `GET /api/tasks` — All tasks with status
- `GET /api/tasks/gantt` — Gantt chart timeline data
- `POST /api/tasks/assign` — Create task `{task_type, priority, location}`

### Red Force AI
- `GET /api/redforce/status` — Strategy, aggression, stats
- `GET /api/redforce/units` — All red force unit positions/states
- `POST /api/redforce/spawn` — Spawn unit `{unit_type, lat, lng}`

### Sensor Fusion
- `GET /api/fusion/tracks` — Fused tracks with confidence/uncertainty
- `GET /api/fusion/coverage` — Sensor coverage footprints
- `GET /api/fusion/killchain` — Kill chain pipeline (DETECT→ASSESS)
- `GET /api/fusion/gaps` — Coverage gap grid

### Commander Support
- `GET /api/commander/risk` — Current risk score (0-100) and level
- `GET /api/commander/risk/trend` — Risk history (last 20 points)
- `GET /api/commander/resources` — Battery burn-down projections
- `GET /api/commander/contingencies` — Armed contingency plans
- `GET /api/commander/triggered` — Plans that have triggered
- `POST /api/commander/contingency/add` — Create contingency plan
- `POST /api/commander/contingency/cancel` — Cancel plan `{plan_id}`

### Learning Engine
- `GET /api/learning/anomalies` — Detected anomalies
- `GET /api/learning/engagements` — Recent engagements
- `GET /api/learning/engagement-stats` — Hit/miss/abort rates
- `GET /api/learning/swarm-params` — Current swarm tuning parameters
- `POST /api/learning/swarm/tune` — Adjust swarm `{metric, score, weight}`
- `GET /api/learning/aar` — After-action review with patterns
- `GET /api/learning/events` — Event log `?type=&limit=`

## System
- `GET /api/sim/status` — Simulation clock
- `POST /api/sim/speed` — Set sim speed `{speed}`
- `GET /api/ros2/status` — ROS 2 bridge status
- `GET /api/user/role` — Current user role/permissions
