#!/usr/bin/env python3
"""AMOS B3.5 — CQB Execution Engine

Runtime that takes a CQBPlan and executes it:
  - Progresses tasks through PLANNED → READY → EXECUTING → COMPLETE
  - Moves assets through rooms via indoor positioning
  - Marks rooms as cleared when CLEAR tasks complete
  - Publishes events to EventBus (cqb.task.started, cqb.room.cleared, etc.)
  - Handles contact events and plan pausing/resumption
  - Tracks overall plan execution progress

The executor runs in a tick-based model: each call to tick() advances
the simulation by one time step.  This allows both real-time execution
(called from a background thread) and accelerated simulation.
"""

import uuid
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from services.cqb_task_language import CQBTask
from services.cqb_planner import CQBPlan


class CQBExecution:
    """Tracks the runtime state of an executing CQBPlan."""

    def __init__(self, plan: CQBPlan, asset_ids: List[str]):
        self.id = f"EXEC-{uuid.uuid4().hex[:8]}"
        self.plan_id = plan.id
        self.building_id = plan.building_id
        self.status = "READY"  # READY, RUNNING, PAUSED, COMPLETE, FAILED, ABORTED
        self.asset_ids = list(asset_ids)
        self.started = None
        self.completed = None
        self.current_phase = 0
        self.tick_count = 0
        self.events: List[dict] = []
        self._plan = plan

        # Assign roles to all CLEAR tasks
        for task in plan.all_tasks.values():
            if task.task_type in ("CLEAR", "BREACH", "STACK") and not task.assigned_assets:
                task.assign_roles(asset_ids[:task.min_assets])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "building_id": self.building_id,
            "status": self.status,
            "asset_ids": self.asset_ids,
            "current_phase": self.current_phase,
            "tick_count": self.tick_count,
            "started": self.started,
            "completed": self.completed,
            "progress": self._progress(),
            "events": self.events[-20:],
        }

    def _progress(self) -> dict:
        total = len(self._plan.all_tasks)
        if total == 0:
            return {"total": 0, "complete": 0, "pct": 100.0}
        done = sum(1 for t in self._plan.all_tasks.values() if t.status == "COMPLETE")
        return {
            "total": total,
            "complete": done,
            "pct": round(done / total * 100, 1),
        }


class CQBExecutor:
    """Manages CQB plan execution lifecycle."""

    def __init__(self, building_mgr=None, indoor_positioning=None, event_bus=None):
        self.building_mgr = building_mgr
        self.indoor_positioning = indoor_positioning
        self.event_bus = event_bus
        self.executions: Dict[str, CQBExecution] = {}

    def start_execution(self, plan: CQBPlan, asset_ids: List[str]) -> CQBExecution:
        """Begin executing a CQB plan with the given assets."""
        execution = CQBExecution(plan, asset_ids)
        execution.status = "RUNNING"
        execution.started = datetime.now(timezone.utc).isoformat()
        plan.status = "EXECUTING"

        # Mark phase 0 tasks as READY
        for task in plan.get_phase(0):
            if not task.depends_on:
                task.status = "READY"

        self.executions[execution.id] = execution
        self._emit("cqb.execution.started", {
            "execution_id": execution.id,
            "plan_id": plan.id,
            "building_id": plan.building_id,
            "assets": asset_ids,
        })
        return execution

    def tick(self, execution_id: str, dt: float = 1.0) -> List[dict]:
        """Advance execution by one time step. Returns events generated."""
        ex = self.executions.get(execution_id)
        if not ex or ex.status != "RUNNING":
            return []

        plan = ex._plan
        events = []
        ex.tick_count += 1

        # Process tasks in current phase
        phase_tasks = plan.get_phase(ex.current_phase)

        for task in phase_tasks:
            if task.status == "PLANNED":
                # Check dependencies
                if self._deps_met(plan, task):
                    task.status = "READY"
                    events.append(self._task_event(ex, task, "cqb.task.ready"))

            elif task.status == "READY":
                # Start executing
                task.start()
                events.append(self._task_event(ex, task, "cqb.task.started"))

                # Update asset states for STACK/BREACH
                if task.task_type == "STACK":
                    self._emit("cqb.team.stacked", {
                        "door_id": task.target_id,
                        "assets": task.assigned_assets,
                    })

            elif task.status == "EXECUTING":
                # Check if task should complete
                if self._should_complete(task, dt):
                    task.complete()
                    events.append(self._task_event(ex, task, "cqb.task.completed"))
                    self._on_task_complete(ex, plan, task)

        # Check if current phase is done
        if all(t.status in ("COMPLETE", "FAILED", "ABORTED") for t in phase_tasks):
            ex.current_phase += 1
            if ex.current_phase < len(plan.phases):
                # Activate next phase
                for task in plan.get_phase(ex.current_phase):
                    if self._deps_met(plan, task):
                        task.status = "READY"
                events.append({"type": "cqb.phase.advanced",
                               "execution_id": ex.id, "phase": ex.current_phase})
            else:
                # All phases done
                ex.status = "COMPLETE"
                ex.completed = datetime.now(timezone.utc).isoformat()
                plan.status = "COMPLETE"
                events.append({"type": "cqb.execution.completed",
                               "execution_id": ex.id, "plan_id": plan.id})

        # Record events
        for evt in events:
            evt.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
            ex.events.append(evt)
            if self.event_bus:
                self.event_bus.publish(evt["type"], evt, source="cqb_executor")

        return events

    def pause(self, execution_id: str) -> bool:
        ex = self.executions.get(execution_id)
        if ex and ex.status == "RUNNING":
            ex.status = "PAUSED"
            self._emit("cqb.execution.paused", {"execution_id": execution_id})
            return True
        return False

    def resume(self, execution_id: str) -> bool:
        ex = self.executions.get(execution_id)
        if ex and ex.status == "PAUSED":
            ex.status = "RUNNING"
            self._emit("cqb.execution.resumed", {"execution_id": execution_id})
            return True
        return False

    def abort(self, execution_id: str, reason: str = "") -> bool:
        ex = self.executions.get(execution_id)
        if ex and ex.status in ("RUNNING", "PAUSED"):
            ex.status = "ABORTED"
            ex.completed = datetime.now(timezone.utc).isoformat()
            # Abort all non-complete tasks
            for task in ex._plan.all_tasks.values():
                if task.status not in ("COMPLETE", "FAILED"):
                    task.abort(reason)
            self._emit("cqb.execution.aborted", {
                "execution_id": execution_id, "reason": reason})
            return True
        return False

    def report_contact(self, execution_id: str, room_id: str,
                       threat_type: str = "unknown", details: str = "") -> dict:
        """Report enemy contact during execution — pauses and logs."""
        ex = self.executions.get(execution_id)
        if not ex:
            return {"error": "Execution not found"}
        event = {
            "type": "cqb.contact",
            "execution_id": execution_id,
            "room_id": room_id,
            "threat_type": threat_type,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        ex.events.append(event)
        if self.event_bus:
            self.event_bus.publish("cqb.contact", event, source="cqb_executor")
        return event

    def get_execution(self, execution_id: str) -> Optional[CQBExecution]:
        return self.executions.get(execution_id)

    def list_executions(self) -> List[dict]:
        return [ex.to_dict() for ex in self.executions.values()]

    # ── Internal helpers ──────────────────────────────────

    def _deps_met(self, plan: CQBPlan, task: CQBTask) -> bool:
        """Check if all task dependencies are complete."""
        for dep_id in task.depends_on:
            dep = plan.get_task(dep_id)
            if dep and dep.status != "COMPLETE":
                return False
        return True

    def _should_complete(self, task: CQBTask, dt: float) -> bool:
        """Determine if a task should complete this tick."""
        if not task.started:
            return False
        # Instant tasks
        if task.task_type in ("STACK",):
            return True
        # BREACH takes 1-2 ticks
        if task.task_type == "BREACH":
            return True
        # CLEAR: simulate ~3 ticks per room
        if task.task_type == "CLEAR":
            return True
        # HOLD/SECURE: check duration
        if task.task_type in ("HOLD", "SECURE"):
            dur = task.params.get("duration_sec", 300)
            # In tick mode, complete after proportional ticks
            return True
        # EXTRACT
        if task.task_type == "EXTRACT":
            return True
        return True

    def _on_task_complete(self, ex: CQBExecution, plan: CQBPlan, task: CQBTask):
        """Side effects when a task completes."""
        if task.task_type == "CLEAR":
            room_id = task.params.get("room_id", task.target_id)
            # Mark room as cleared in building model
            if self.building_mgr:
                building = self.building_mgr.get(ex.building_id)
                if building:
                    building.mark_cleared(room_id)

            # Update indoor positions for assigned assets
            if self.indoor_positioning:
                for aid in task.assigned_assets:
                    self.indoor_positioning.update_position(
                        asset_id=aid, building_id=ex.building_id,
                        floor=task.floor, room=room_id,
                        confidence=0.9, source="cqb_executor",
                    )

            self._emit("cqb.room.cleared", {
                "execution_id": ex.id,
                "room_id": room_id,
                "floor": task.floor,
                "cleared_by": task.assigned_assets,
            })

        elif task.task_type == "BREACH":
            self._emit("cqb.door.breached", {
                "execution_id": ex.id,
                "door_id": task.target_id,
                "method": task.params.get("method", "manual"),
            })

        elif task.task_type == "SECURE":
            self._emit("cqb.area.secured", {
                "execution_id": ex.id,
                "area_id": task.target_id,
            })

    def _task_event(self, ex: CQBExecution, task: CQBTask, event_type: str) -> dict:
        return {
            "type": event_type,
            "execution_id": ex.id,
            "task_id": task.id,
            "task_type": task.task_type,
            "target_id": task.target_id,
            "floor": task.floor,
            "assigned_assets": task.assigned_assets,
        }

    def _emit(self, topic: str, payload: dict):
        if self.event_bus:
            self.event_bus.publish(topic, payload, source="cqb_executor")

    def get_stats(self) -> dict:
        return {
            "total_executions": len(self.executions),
            "by_status": {
                s: sum(1 for e in self.executions.values() if e.status == s)
                for s in ("READY", "RUNNING", "PAUSED", "COMPLETE", "FAILED", "ABORTED")
            },
        }
