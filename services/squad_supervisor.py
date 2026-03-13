#!/usr/bin/env python3
"""AMOS B5 — Squad Autonomy Supervisor

The capstone autonomy layer.  A commander sets a high-level objective
(e.g. "Clear Building 4, extract HVT from Room 302") and the supervisor
orchestrates the full pipeline:

  1. Parse objective → identify building, target rooms, objective type
  2. Generate CQB plan via CQBPlanner
  3. Assign assets from available pool
  4. Execute plan via CQBExecutor
  5. Monitor execution events — re-task on contact, manage reserves
  6. Track perception fusion (detections, SLAM coverage)
  7. Generate AAR summary on completion

The supervisor runs as a state machine per mission:
  PENDING → PLANNING → READY → EXECUTING → MONITORING → COMPLETE / FAILED
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional


# Mission objective types
OBJECTIVE_TYPES = (
    "clear_building",   # Clear all rooms in a building
    "clear_floor",      # Clear a specific floor
    "secure_room",      # Secure a specific room
    "extract_hvt",      # Extract high-value target from a room
    "breach_and_clear", # Breach a door and clear the room behind it
    "recon_building",   # Reconnaissance only — no engagement
)

# Mission statuses
MISSION_STATUSES = (
    "PENDING", "PLANNING", "READY", "EXECUTING",
    "MONITORING", "COMPLETE", "FAILED", "ABORTED",
)


class SquadMission:
    """A single supervised CQB mission."""

    def __init__(self, objective: str, building_id: str,
                 objective_type: str = "clear_building",
                 target_room: str = "",
                 asset_ids: List[str] = None):
        self.id = f"MISSION-{uuid.uuid4().hex[:8]}"
        self.objective = objective
        self.building_id = building_id
        self.objective_type = objective_type
        self.target_room = target_room
        self.asset_ids = list(asset_ids or [])
        self.reserve_ids: List[str] = []
        self.status = "PENDING"
        self.created = datetime.now(timezone.utc).isoformat()
        self.started = None
        self.completed = None

        # Linked plan + execution
        self.plan_id: Optional[str] = None
        self.execution_id: Optional[str] = None

        # Mission log
        self.events: List[dict] = []
        self.contacts: List[dict] = []
        self.retasks: int = 0

        # AAR data
        self.aar: Optional[dict] = None

    def log(self, event_type: str, details: str = ""):
        self.events.append({
            "type": event_type,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "objective": self.objective,
            "building_id": self.building_id,
            "objective_type": self.objective_type,
            "target_room": self.target_room,
            "status": self.status,
            "asset_ids": self.asset_ids,
            "reserve_ids": self.reserve_ids,
            "plan_id": self.plan_id,
            "execution_id": self.execution_id,
            "created": self.created,
            "started": self.started,
            "completed": self.completed,
            "contacts": len(self.contacts),
            "retasks": self.retasks,
            "events": self.events[-20:],
            "aar": self.aar,
        }


class SquadSupervisor:
    """Autonomous squad mission orchestrator."""

    def __init__(self, building_mgr=None, cqb_planner=None,
                 cqb_executor=None, perception_fusion=None,
                 dimos_bridge=None, event_bus=None):
        self.building_mgr = building_mgr
        self.cqb_planner = cqb_planner
        self.cqb_executor = cqb_executor
        self.perception_fusion = perception_fusion
        self.dimos_bridge = dimos_bridge
        self.event_bus = event_bus
        self.missions: Dict[str, SquadMission] = {}

    def create_mission(self, objective: str, building_id: str,
                       objective_type: str = "clear_building",
                       target_room: str = "",
                       asset_ids: List[str] = None,
                       reserve_ids: List[str] = None) -> SquadMission:
        """Create a new supervised mission from a commander's objective."""
        mission = SquadMission(
            objective=objective,
            building_id=building_id,
            objective_type=objective_type,
            target_room=target_room,
            asset_ids=asset_ids or [],
        )
        mission.reserve_ids = list(reserve_ids or [])
        self.missions[mission.id] = mission
        mission.log("mission.created", objective)
        self._emit("squad.mission.created", {
            "mission_id": mission.id, "objective": objective,
            "building_id": building_id,
        })
        return mission

    def plan_mission(self, mission_id: str) -> dict:
        """Generate a CQB plan for the mission."""
        mission = self.missions.get(mission_id)
        if not mission:
            return {"error": "Mission not found"}
        if not self.building_mgr or not self.cqb_planner:
            return {"error": "CQB services not available"}

        building = self.building_mgr.get(mission.building_id)
        if not building:
            return {"error": f"Building {mission.building_id} not found"}

        mission.status = "PLANNING"
        mission.log("mission.planning", "Generating CQB plan")

        # Determine floors to clear based on objective type
        floors = None
        if mission.objective_type == "clear_floor" and mission.target_room:
            # Parse floor number from target (e.g. "F1" or just "1")
            try:
                fl = int(mission.target_room.replace("F", "").replace("f", ""))
                floors = [fl]
            except ValueError:
                floors = None

        plan = self.cqb_planner.generate_plan(
            building,
            floors=floors,
            objective_room=mission.target_room if mission.objective_type != "clear_floor" else "",
            team_size=len(mission.asset_ids) if mission.asset_ids else 4,
        )

        mission.plan_id = plan.id
        mission.status = "READY"
        mission.log("mission.planned", f"Plan {plan.id}: {plan.stats['total_tasks']} tasks, {plan.stats['phases']} phases")
        self._emit("squad.mission.planned", {
            "mission_id": mission.id, "plan_id": plan.id,
        })
        return {"status": "ok", "plan_id": plan.id, "stats": plan.stats}

    def execute_mission(self, mission_id: str) -> dict:
        """Start executing the mission plan."""
        mission = self.missions.get(mission_id)
        if not mission:
            return {"error": "Mission not found"}
        if not mission.plan_id:
            return {"error": "Mission has no plan — call plan_mission first"}
        if not mission.asset_ids:
            return {"error": "No assets assigned"}
        if not self.cqb_executor or not self.cqb_planner:
            return {"error": "CQB services not available"}

        plan = self.cqb_planner.get_plan(mission.plan_id)
        if not plan:
            return {"error": "Plan not found"}

        mission.status = "EXECUTING"
        mission.started = datetime.now(timezone.utc).isoformat()
        mission.log("mission.executing", f"Executing with {len(mission.asset_ids)} assets")

        execution = self.cqb_executor.start_execution(plan, mission.asset_ids)
        mission.execution_id = execution.id

        self._emit("squad.mission.executing", {
            "mission_id": mission.id, "execution_id": execution.id,
        })
        return {"status": "ok", "execution_id": execution.id}

    def tick_mission(self, mission_id: str) -> dict:
        """Advance mission by one tick — runs executor + monitors."""
        mission = self.missions.get(mission_id)
        if not mission or not mission.execution_id:
            return {"error": "Mission not executing"}
        if not self.cqb_executor:
            return {"error": "CQB executor not available"}

        events = self.cqb_executor.tick(mission.execution_id)

        # Monitor events for contact / completion
        for evt in events:
            evt_type = evt.get("type", "")
            if evt_type == "cqb.contact":
                mission.contacts.append(evt)
                mission.log("contact", f"Contact in {evt.get('room_id', '?')}: {evt.get('threat_type', 'unknown')}")

            elif evt_type == "cqb.execution.completed":
                mission.status = "COMPLETE"
                mission.completed = datetime.now(timezone.utc).isoformat()
                mission.log("mission.complete", "All tasks complete")
                mission.aar = self._generate_aar(mission)
                self._emit("squad.mission.complete", {
                    "mission_id": mission.id, "aar": mission.aar,
                })

        # Check execution status
        ex = self.cqb_executor.get_execution(mission.execution_id)
        if ex and ex.status in ("FAILED", "ABORTED"):
            mission.status = ex.status
            mission.completed = datetime.now(timezone.utc).isoformat()
            mission.log(f"mission.{ex.status.lower()}", "Execution ended")

        return {
            "status": "ok",
            "mission_status": mission.status,
            "events": events,
            "execution": ex.to_dict() if ex else None,
        }

    def commit_reserves(self, mission_id: str, count: int = 1) -> dict:
        """Move reserve assets into the active mission."""
        mission = self.missions.get(mission_id)
        if not mission:
            return {"error": "Mission not found"}
        moved = []
        for _ in range(min(count, len(mission.reserve_ids))):
            aid = mission.reserve_ids.pop(0)
            mission.asset_ids.append(aid)
            moved.append(aid)
        if moved:
            mission.retasks += 1
            mission.log("reserves.committed", f"Committed {len(moved)} reserves: {', '.join(moved)}")
        return {"status": "ok", "committed": moved,
                "remaining_reserves": len(mission.reserve_ids)}

    def abort_mission(self, mission_id: str, reason: str = "") -> dict:
        """Abort a running mission."""
        mission = self.missions.get(mission_id)
        if not mission:
            return {"error": "Mission not found"}
        if mission.execution_id and self.cqb_executor:
            self.cqb_executor.abort(mission.execution_id, reason)
        mission.status = "ABORTED"
        mission.completed = datetime.now(timezone.utc).isoformat()
        mission.log("mission.aborted", reason)
        self._emit("squad.mission.aborted", {
            "mission_id": mission.id, "reason": reason,
        })
        return {"status": "ok", "aborted": True}

    def get_mission(self, mission_id: str) -> Optional[SquadMission]:
        return self.missions.get(mission_id)

    def list_missions(self) -> List[dict]:
        return [m.to_dict() for m in self.missions.values()]

    def get_stats(self) -> dict:
        by_status = {}
        for m in self.missions.values():
            by_status[m.status] = by_status.get(m.status, 0) + 1
        return {
            "total_missions": len(self.missions),
            "by_status": by_status,
            "total_contacts": sum(len(m.contacts) for m in self.missions.values()),
            "total_retasks": sum(m.retasks for m in self.missions.values()),
        }

    # ── AAR Generation ────────────────────────────────────

    def _generate_aar(self, mission: SquadMission) -> dict:
        """Generate an After Action Report for a completed mission."""
        ex = None
        plan = None
        if mission.execution_id and self.cqb_executor:
            ex = self.cqb_executor.get_execution(mission.execution_id)
        if mission.plan_id and self.cqb_planner:
            plan = self.cqb_planner.get_plan(mission.plan_id)

        total_tasks = len(plan.all_tasks) if plan else 0
        completed_tasks = sum(1 for t in plan.all_tasks.values() if t.status == "COMPLETE") if plan else 0

        # Calculate duration
        duration_sec = None
        if mission.started and mission.completed:
            from datetime import datetime as dt
            try:
                t0 = dt.fromisoformat(mission.started)
                t1 = dt.fromisoformat(mission.completed)
                duration_sec = round((t1 - t0).total_seconds(), 1)
            except Exception:
                pass

        return {
            "mission_id": mission.id,
            "objective": mission.objective,
            "building_id": mission.building_id,
            "result": mission.status,
            "assets_deployed": len(mission.asset_ids),
            "reserves_used": mission.retasks,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "ticks": ex.tick_count if ex else 0,
            "contacts": len(mission.contacts),
            "events_logged": len(mission.events),
            "duration_sec": duration_sec,
            "created": mission.created,
            "completed": mission.completed,
        }

    # ── Internal ──────────────────────────────────────────

    def _emit(self, topic: str, payload: dict):
        if self.event_bus:
            self.event_bus.publish(topic, payload, source="squad_supervisor")
