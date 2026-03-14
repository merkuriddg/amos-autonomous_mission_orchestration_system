#!/usr/bin/env python3
"""AMOS Sprint 4 — Investor Demo Engine

Single-click scenarios that exercise the full autonomy pipeline in
time-compressed mode for investor presentations:

  1. RECON_TO_STRIKE — Swarm launches → detection → retask → relay →
     classify → strike decision (the AMOS_Next signature narrative)
  2. BORDER_INTERDICTION — Perimeter scan detects intrusion → converge →
     intercept → report
  3. SWARM_SHOWCASE — All 5 swarm behaviors demonstrated in sequence

Each scenario is a list of timed phases. The DemoRunner advances through
phases, injecting threats, assigning behaviors, and driving the closed
loop. Every autonomous decision is recorded in a narrated timeline for
the event sidebar.

API-driven: start → tick (or auto-advance) → status/timeline → stop.
"""

import copy
import math
import time
import uuid
import threading
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════
#  DEMO SCENARIO DEFINITIONS
# ═══════════════════════════════════════════════════════════

def _scenario_recon_to_strike():
    """The AMOS_Next signature narrative:
    Swarm launches → Drone 1 detects → AMOS retasks Drone 2 →
    Drone 3 becomes relay → classify → strike assigned.
    """
    return {
        "id": "RECON_TO_STRIKE",
        "name": "Recon-to-Strike Pipeline",
        "description": (
            "Demonstrates the full autonomy loop: recon swarm detects a hostile "
            "vehicle, AMOS automatically retasks a tracking drone, assigns a relay "
            "node for connectivity, classifies the target, and assigns a strike "
            "asset — all without human intervention."
        ),
        "duration_sec": 120,
        "phases": [
            {
                "name": "SWARM_LAUNCH",
                "start_sec": 0,
                "narration": "Recon swarm of 4 UAVs launches from FOB into patrol formation",
                "actions": [
                    {"type": "SPAWN_ASSETS", "assets": [
                        {"id": "DEMO-RECON-01", "type": "uav", "domain": "air", "role": "recon",
                         "lat": 27.85, "lng": -82.53, "sensors": ["EO/IR", "SIGINT"],
                         "weapons": [], "heading_deg": 45, "speed_kts": 100},
                        {"id": "DEMO-RECON-02", "type": "uav", "domain": "air", "role": "recon",
                         "lat": 27.85, "lng": -82.52, "sensors": ["AESA_RADAR", "EO/IR"],
                         "weapons": [], "heading_deg": 45, "speed_kts": 110},
                        {"id": "DEMO-RELAY-03", "type": "uav", "domain": "air", "role": "airborne_c2",
                         "lat": 27.85, "lng": -82.51, "sensors": ["SIGINT"],
                         "weapons": [], "heading_deg": 0, "speed_kts": 80},
                        {"id": "DEMO-STRIKE-04", "type": "uav", "domain": "air", "role": "isr_strike",
                         "lat": 27.84, "lng": -82.52, "sensors": ["AESA_RADAR", "EO/IR"],
                         "weapons": ["HELLFIRE"], "heading_deg": 90, "speed_kts": 120},
                    ]},
                    {"type": "ASSIGN_BEHAVIOR", "behavior": "AREA_SWEEP",
                     "swarm_id": "DEMO-RECON", "asset_ids": ["DEMO-RECON-01", "DEMO-RECON-02"],
                     "params": {"bounds": {"north": 27.88, "south": 27.84, "east": -82.48, "west": -82.56}}},
                ],
            },
            {
                "name": "THREAT_DETECTED",
                "start_sec": 20,
                "narration": "DEMO-RECON-01 detects hostile vehicle via EO/IR — fused track created",
                "actions": [
                    {"type": "INJECT_THREAT", "threat": {
                        "id": "DEMO-THR-001", "type": "vehicle", "lat": 27.865, "lng": -82.505,
                        "threat_level": "high", "speed_kts": 15, "neutralized": False}},
                ],
            },
            {
                "name": "AUTO_RETASK",
                "start_sec": 35,
                "narration": "AMOS auto-retasks DEMO-RECON-02 to track the hostile — DYNAMIC_TRACK assigned",
                "actions": [
                    {"type": "ASSIGN_BEHAVIOR", "behavior": "DYNAMIC_TRACK",
                     "swarm_id": "DEMO-TRACK", "asset_ids": ["DEMO-RECON-02"],
                     "params": {"track_id": "DEMO-THR-001", "initial_lat": 27.865, "initial_lng": -82.505}},
                ],
            },
            {
                "name": "RELAY_ASSIGNED",
                "start_sec": 50,
                "narration": "DEMO-RELAY-03 repositions as communication relay between FOB and tracking drone",
                "actions": [
                    {"type": "ASSIGN_BEHAVIOR", "behavior": "RELAY_MESH",
                     "swarm_id": "DEMO-RELAY", "asset_ids": ["DEMO-RELAY-03"],
                     "params": {"endpoints": [
                         {"lat": 27.84, "lng": -82.52, "id": "FOB"},
                         {"lat": 27.865, "lng": -82.505, "id": "TRACK"},
                     ]}},
                ],
            },
            {
                "name": "CLASSIFY_CONFIRM",
                "start_sec": 70,
                "narration": "Multi-sensor correlation confirms HOSTILE with 92% confidence — kill chain advances to DECIDE",
                "actions": [
                    {"type": "ADVANCE_KILL_CHAIN", "phase": "DECIDE"},
                ],
            },
            {
                "name": "STRIKE_ASSIGNED",
                "start_sec": 90,
                "narration": "ROE check passed — DEMO-STRIKE-04 assigned to engage. Awaiting human confirmation.",
                "actions": [
                    {"type": "CREATE_TASK", "task_type": "STRIKE",
                     "location": {"lat": 27.865, "lng": -82.505}, "priority": 1,
                     "description": "Strike hostile vehicle — DEMO scenario"},
                ],
            },
            {
                "name": "MISSION_COMPLETE",
                "start_sec": 110,
                "narration": "Full recon-to-strike pipeline demonstrated in under 2 minutes. All autonomous decisions logged.",
                "actions": [],
            },
        ],
    }


def _scenario_border_interdiction():
    """Perimeter scan → intrusion detection → converge → intercept."""
    return {
        "id": "BORDER_INTERDICTION",
        "name": "Border Interdiction",
        "description": (
            "Autonomous perimeter defense: a swarm patrols a border polygon, "
            "detects an intrusion, transitions to search spiral and dynamic "
            "tracking to intercept."
        ),
        "duration_sec": 100,
        "phases": [
            {
                "name": "PERIMETER_PATROL",
                "start_sec": 0,
                "narration": "3 UAVs begin perimeter scan of the border zone",
                "actions": [
                    {"type": "SPAWN_ASSETS", "assets": [
                        {"id": "DEMO-BDR-01", "type": "uav", "domain": "air", "role": "recon",
                         "lat": 27.86, "lng": -82.54, "sensors": ["AESA_RADAR", "EO/IR"],
                         "weapons": [], "heading_deg": 0, "speed_kts": 90},
                        {"id": "DEMO-BDR-02", "type": "uav", "domain": "air", "role": "recon",
                         "lat": 27.86, "lng": -82.52, "sensors": ["EO/IR", "SIGINT"],
                         "weapons": [], "heading_deg": 90, "speed_kts": 95},
                        {"id": "DEMO-BDR-03", "type": "uav", "domain": "air", "role": "recon",
                         "lat": 27.86, "lng": -82.50, "sensors": ["EO/IR"],
                         "weapons": [], "heading_deg": 180, "speed_kts": 85},
                    ]},
                    {"type": "ASSIGN_BEHAVIOR", "behavior": "PERIMETER_SCAN",
                     "swarm_id": "DEMO-BDR", "asset_ids": ["DEMO-BDR-01", "DEMO-BDR-02", "DEMO-BDR-03"],
                     "params": {"vertices": [
                         {"lat": 27.88, "lng": -82.55}, {"lat": 27.88, "lng": -82.49},
                         {"lat": 27.84, "lng": -82.49}, {"lat": 27.84, "lng": -82.55},
                     ]}},
                ],
            },
            {
                "name": "INTRUSION_DETECTED",
                "start_sec": 30,
                "narration": "Anomaly detected at border — unknown vehicle crossing perimeter",
                "actions": [
                    {"type": "INJECT_THREAT", "threat": {
                        "id": "DEMO-INTRUDER", "type": "vehicle", "lat": 27.875, "lng": -82.52,
                        "threat_level": "medium", "speed_kts": 20, "neutralized": False}},
                ],
            },
            {
                "name": "SEARCH_AND_TRACK",
                "start_sec": 50,
                "narration": "AMOS transitions BDR-01 to search spiral, BDR-02 to dynamic tracking",
                "actions": [
                    {"type": "ASSIGN_BEHAVIOR", "behavior": "SEARCH_SPIRAL",
                     "swarm_id": "DEMO-SEARCH", "asset_ids": ["DEMO-BDR-01"],
                     "params": {"center": {"lat": 27.875, "lng": -82.52}}},
                    {"type": "ASSIGN_BEHAVIOR", "behavior": "DYNAMIC_TRACK",
                     "swarm_id": "DEMO-TRACK-BDR", "asset_ids": ["DEMO-BDR-02", "DEMO-BDR-03"],
                     "params": {"track_id": "DEMO-INTRUDER", "initial_lat": 27.875, "initial_lng": -82.52}},
                ],
            },
            {
                "name": "INTERCEPT_COMPLETE",
                "start_sec": 85,
                "narration": "Intruder tracked and classified — interdiction assets converged. Report generated.",
                "actions": [
                    {"type": "CREATE_TASK", "task_type": "INTERCEPT",
                     "location": {"lat": 27.875, "lng": -82.52}, "priority": 2,
                     "description": "Intercept border intruder — DEMO scenario"},
                ],
            },
        ],
    }


def _scenario_swarm_showcase():
    """Demonstrate all 5 swarm behaviors in sequence."""
    return {
        "id": "SWARM_SHOWCASE",
        "name": "Swarm Behavior Showcase",
        "description": (
            "Cycles through all 5 autonomous swarm behaviors: Area Sweep, "
            "Perimeter Scan, Dynamic Track, Relay Mesh, and Search Spiral. "
            "Shows how AMOS coordinates multi-asset autonomous operations."
        ),
        "duration_sec": 100,
        "phases": [
            {
                "name": "SETUP",
                "start_sec": 0,
                "narration": "Deploying 5 UAVs for swarm behavior demonstration",
                "actions": [
                    {"type": "SPAWN_ASSETS", "assets": [
                        {"id": f"DEMO-SW-0{i}", "type": "uav", "domain": "air", "role": "recon",
                         "lat": 27.85 + i * 0.002, "lng": -82.52, "sensors": ["EO/IR"],
                         "weapons": [], "heading_deg": 0, "speed_kts": 90}
                        for i in range(1, 6)
                    ]},
                ],
            },
            {
                "name": "AREA_SWEEP",
                "start_sec": 5,
                "narration": "Behavior 1: AREA_SWEEP — parallel-track lawnmower coverage pattern",
                "actions": [
                    {"type": "ASSIGN_BEHAVIOR", "behavior": "AREA_SWEEP",
                     "swarm_id": "DEMO-SW", "asset_ids": [f"DEMO-SW-0{i}" for i in range(1, 6)],
                     "params": {"bounds": {"north": 27.87, "south": 27.83, "east": -82.49, "west": -82.55}}},
                ],
            },
            {
                "name": "PERIMETER_SCAN",
                "start_sec": 25,
                "narration": "Behavior 2: PERIMETER_SCAN — orbital surveillance of a geofence polygon",
                "actions": [
                    {"type": "CANCEL_ALL_BEHAVIORS"},
                    {"type": "ASSIGN_BEHAVIOR", "behavior": "PERIMETER_SCAN",
                     "swarm_id": "DEMO-SW", "asset_ids": [f"DEMO-SW-0{i}" for i in range(1, 6)],
                     "params": {"vertices": [
                         {"lat": 27.87, "lng": -82.54}, {"lat": 27.87, "lng": -82.50},
                         {"lat": 27.83, "lng": -82.50}, {"lat": 27.83, "lng": -82.54},
                     ]}},
                ],
            },
            {
                "name": "DYNAMIC_TRACK",
                "start_sec": 45,
                "narration": "Behavior 3: DYNAMIC_TRACK — swarm converges on a moving target",
                "actions": [
                    {"type": "CANCEL_ALL_BEHAVIORS"},
                    {"type": "INJECT_THREAT", "threat": {
                        "id": "DEMO-SW-THR", "type": "vehicle", "lat": 27.855, "lng": -82.51,
                        "threat_level": "medium", "speed_kts": 10, "neutralized": False}},
                    {"type": "ASSIGN_BEHAVIOR", "behavior": "DYNAMIC_TRACK",
                     "swarm_id": "DEMO-SW", "asset_ids": [f"DEMO-SW-0{i}" for i in range(1, 4)],
                     "params": {"track_id": "DEMO-SW-THR", "initial_lat": 27.855, "initial_lng": -82.51}},
                ],
            },
            {
                "name": "RELAY_MESH",
                "start_sec": 65,
                "narration": "Behavior 4: RELAY_MESH — assets bridge communication gaps between nodes",
                "actions": [
                    {"type": "CANCEL_ALL_BEHAVIORS"},
                    {"type": "ASSIGN_BEHAVIOR", "behavior": "RELAY_MESH",
                     "swarm_id": "DEMO-SW", "asset_ids": [f"DEMO-SW-0{i}" for i in range(1, 4)],
                     "params": {"endpoints": [
                         {"lat": 27.84, "lng": -82.55, "id": "HQ"},
                         {"lat": 27.87, "lng": -82.49, "id": "FOB"},
                     ]}},
                ],
            },
            {
                "name": "SEARCH_SPIRAL",
                "start_sec": 85,
                "narration": "Behavior 5: SEARCH_SPIRAL — expanding spiral from last-known position",
                "actions": [
                    {"type": "CANCEL_ALL_BEHAVIORS"},
                    {"type": "ASSIGN_BEHAVIOR", "behavior": "SEARCH_SPIRAL",
                     "swarm_id": "DEMO-SW", "asset_ids": [f"DEMO-SW-0{i}" for i in range(1, 4)],
                     "params": {"center": {"lat": 27.855, "lng": -82.52}}},
                ],
            },
        ],
    }


# Catalog
DEMO_SCENARIOS = {
    "RECON_TO_STRIKE": _scenario_recon_to_strike,
    "BORDER_INTERDICTION": _scenario_border_interdiction,
    "SWARM_SHOWCASE": _scenario_swarm_showcase,
}


# ═══════════════════════════════════════════════════════════
#  DEMO RUNNER
# ═══════════════════════════════════════════════════════════

class DemoRunner:
    """Executes a demo scenario phase-by-phase.

    Drives the closed-loop pipeline, injects scripted events,
    and records a narrated timeline for the UI.
    """

    def __init__(self, closed_loop, swarm_behavior_mgr, task_allocator):
        self.closed_loop = closed_loop
        self.swarm_behavior_mgr = swarm_behavior_mgr
        self.task_allocator = task_allocator

        self._lock = threading.Lock()
        self.scenario = None
        self.status = "idle"  # idle | running | paused | completed
        self.sim_time = 0.0   # simulated seconds elapsed
        self.speed = 1.0      # time multiplier (2.0 = 2x speed)
        self.current_phase_idx = 0
        self.tick_count = 0
        self.started_at = None

        # Injected demo assets and threats (isolated from main sim)
        self.demo_assets = {}
        self.demo_threats = {}

        # Narrated timeline — the investor-facing event log
        self.timeline = []

    # ─── Lifecycle ───────────────────────────────────

    def start(self, scenario_id, speed=1.0):
        """Start a demo scenario."""
        if scenario_id not in DEMO_SCENARIOS:
            return {"error": f"Unknown scenario: {scenario_id}",
                    "available": list(DEMO_SCENARIOS.keys())}
        if self.status == "running":
            return {"error": "Demo already running. Stop first."}

        with self._lock:
            self.scenario = DEMO_SCENARIOS[scenario_id]()
            self.status = "running"
            self.sim_time = 0.0
            self.speed = max(0.1, speed)
            self.current_phase_idx = 0
            self.tick_count = 0
            self.started_at = time.time()
            self.demo_assets = {}
            self.demo_threats = {}
            self.timeline = []

            self._add_timeline("DEMO_START", self.scenario["name"],
                               f"Starting scenario: {self.scenario['description']}")

        return {
            "status": "running",
            "scenario": self.scenario["id"],
            "name": self.scenario["name"],
            "duration_sec": self.scenario["duration_sec"],
            "phase_count": len(self.scenario["phases"]),
            "speed": self.speed,
        }

    def stop(self):
        """Stop the running demo."""
        with self._lock:
            if self.status == "idle":
                return {"error": "No demo running"}
            self._add_timeline("DEMO_STOP", "Demo stopped",
                               f"Completed {self.tick_count} ticks, {len(self.timeline)} events")
            self.status = "idle"
            result = self.get_status()
        return result

    def tick(self, dt=1.0):
        """Advance the demo by dt simulated seconds (scaled by speed).

        Returns events and current status.
        """
        if self.status != "running":
            return {"status": self.status, "events": []}

        events = []
        with self._lock:
            effective_dt = dt * self.speed
            self.sim_time += effective_dt
            self.tick_count += 1

            # Execute any phases that are now due
            while self.current_phase_idx < len(self.scenario["phases"]):
                phase = self.scenario["phases"][self.current_phase_idx]
                if self.sim_time >= phase["start_sec"]:
                    phase_events = self._execute_phase(phase)
                    events.extend(phase_events)
                    self.current_phase_idx += 1
                else:
                    break

            # Run closed-loop tick with demo assets+threats
            if self.demo_assets:
                loop_result = self.closed_loop.tick(
                    self.demo_assets, self.demo_threats, dt=effective_dt)
                for ev in loop_result.get("events", []):
                    ev["demo"] = True
                    events.append(ev)

            # Check completion
            if self.sim_time >= self.scenario["duration_sec"]:
                self.status = "completed"
                self._add_timeline("DEMO_COMPLETE", "Scenario complete",
                                   f"Full pipeline demonstrated in {self.scenario['duration_sec']}s")

        return {
            "status": self.status,
            "tick": self.tick_count,
            "sim_time": round(self.sim_time, 1),
            "phase": self._current_phase_name(),
            "progress_pct": round(min(100, self.sim_time / self.scenario["duration_sec"] * 100), 1),
            "events": events,
            "event_count": len(events),
        }

    # ─── Phase Execution ─────────────────────────────

    def _execute_phase(self, phase):
        """Execute all actions in a scenario phase."""
        events = []
        self._add_timeline("PHASE", phase["name"], phase["narration"])

        for action in phase.get("actions", []):
            atype = action["type"]

            if atype == "SPAWN_ASSETS":
                for adef in action.get("assets", []):
                    aid = adef["id"]
                    self.demo_assets[aid] = {
                        "id": aid,
                        "type": adef.get("type", "uav"),
                        "domain": adef.get("domain", "air"),
                        "role": adef.get("role", "recon"),
                        "position": {"lat": adef.get("lat", 27.85),
                                     "lng": adef.get("lng", -82.52)},
                        "sensors": adef.get("sensors", []),
                        "weapons": adef.get("weapons", []),
                        "status": "operational",
                        "heading_deg": adef.get("heading_deg", 0),
                        "speed_kts": adef.get("speed_kts", 100),
                        "health": {"battery_pct": 100, "comms_strength": 95},
                    }
                    events.append({"type": "ASSET_SPAWNED", "asset_id": aid,
                                   "demo": True})

            elif atype == "INJECT_THREAT":
                thr = action["threat"]
                self.demo_threats[thr["id"]] = dict(thr)
                events.append({"type": "THREAT_INJECTED", "threat_id": thr["id"],
                               "demo": True})
                self._add_timeline("DETECTION",
                                   f"Threat {thr['id']} detected",
                                   f"{thr['type']} at ({thr['lat']}, {thr['lng']})")

            elif atype == "ASSIGN_BEHAVIOR":
                result = self.swarm_behavior_mgr.assign_behavior(
                    action["behavior"], action.get("swarm_id", ""),
                    action.get("asset_ids", []), action.get("params", {}))
                if "error" not in result:
                    events.append({"type": "BEHAVIOR_ASSIGNED", **result, "demo": True})
                    self._add_timeline("AUTONOMOUS_DECISION",
                                       f"{action['behavior']} assigned",
                                       f"Swarm {action.get('swarm_id')} → "
                                       f"{len(action.get('asset_ids', []))} assets")

            elif atype == "CANCEL_ALL_BEHAVIORS":
                for bid in list(self.swarm_behavior_mgr.active_behaviors.keys()):
                    self.swarm_behavior_mgr.cancel_behavior(bid)
                events.append({"type": "BEHAVIORS_CANCELLED", "demo": True})

            elif atype == "CREATE_TASK":
                result = self.task_allocator.create_task(
                    action.get("task_type", "ISR"),
                    location=action.get("location"),
                    priority=action.get("priority", 5),
                    description=action.get("description", ""),
                )
                events.append({"type": "TASK_CREATED", **result, "demo": True})
                self._add_timeline("AUTONOMOUS_DECISION",
                                   f"Task {action.get('task_type')} created",
                                   action.get("description", ""))

            elif atype == "ADVANCE_KILL_CHAIN":
                # Advance any active fused tracks
                for trk_id in list(self.closed_loop.sensor_fusion.tracks.keys()):
                    self.closed_loop.sensor_fusion.advance_kill_chain(
                        trk_id, action["phase"], operator="DEMO")
                events.append({"type": "KILL_CHAIN_ADVANCED",
                               "phase": action["phase"], "demo": True})
                self._add_timeline("KILL_CHAIN",
                                   f"Kill chain → {action['phase']}",
                                   "Multi-sensor confirmation complete")

        return events

    # ─── Timeline ────────────────────────────────────

    def _add_timeline(self, event_type, title, detail=""):
        """Add a narrated event to the investor timeline."""
        self.timeline.append({
            "sim_time": round(self.sim_time, 1),
            "wall_time": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "title": title,
            "detail": detail,
            "phase": self._current_phase_name(),
        })

    def _current_phase_name(self):
        if not self.scenario or not self.scenario.get("phases"):
            return "IDLE"
        idx = min(self.current_phase_idx, len(self.scenario["phases"]) - 1)
        return self.scenario["phases"][idx]["name"]

    # ─── Status / Query ──────────────────────────────

    def get_status(self):
        """Full demo status for the UI."""
        return {
            "status": self.status,
            "scenario": self.scenario["id"] if self.scenario else None,
            "scenario_name": self.scenario["name"] if self.scenario else None,
            "sim_time": round(self.sim_time, 1),
            "duration_sec": self.scenario["duration_sec"] if self.scenario else 0,
            "progress_pct": round(
                min(100, self.sim_time / self.scenario["duration_sec"] * 100), 1
            ) if self.scenario else 0,
            "speed": self.speed,
            "tick_count": self.tick_count,
            "current_phase": self._current_phase_name(),
            "phases_completed": self.current_phase_idx,
            "total_phases": len(self.scenario["phases"]) if self.scenario else 0,
            "demo_assets": len(self.demo_assets),
            "demo_threats": len(self.demo_threats),
            "timeline_count": len(self.timeline),
        }

    def get_timeline(self, limit=100):
        """Return the narrated timeline (most recent first)."""
        return list(reversed(self.timeline[-limit:]))

    @staticmethod
    def list_scenarios():
        """Return catalog of available demo scenarios."""
        return [
            {
                "id": sid,
                "name": fn()["name"],
                "description": fn()["description"],
                "duration_sec": fn()["duration_sec"],
                "phase_count": len(fn()["phases"]),
            }
            for sid, fn in DEMO_SCENARIOS.items()
        ]
