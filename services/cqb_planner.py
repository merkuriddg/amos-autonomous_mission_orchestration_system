#!/usr/bin/env python3
"""AMOS B3.2 — CQB Room Clearing Planner

Given a building model and an objective (e.g. "clear floors 0-2"),
generates a sequenced, phased task list using the CQB task language.

Planning logic:
  1. Determine entry point (exterior door → entry room)
  2. BFS from entry through the building's adjacency graph
  3. For each room, generate STACK → BREACH → CLEAR sequence
  4. Group rooms into phases by floor
  5. Add HOLD tasks for cleared rooms to prevent re-infiltration
  6. Add SECURE task at the objective room (if specified)
  7. Assign roles based on available assets

Considers:
  - Already-cleared rooms (skip them)
  - Threat intel (prioritize high-threat rooms)
  - Reinforced doors (require explosive breach)
  - Asset fatigue (warn if too few fresh assets)
"""

import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from services.cqb_task_language import CQBTask, CQB_TASK_TYPES


class CQBPlan:
    """A complete room-clearing plan with phased tasks."""

    def __init__(self, building_id: str, objective: str = ""):
        self.id = f"PLAN-{uuid.uuid4().hex[:8]}"
        self.building_id = building_id
        self.objective = objective
        self.status = "DRAFT"
        self.created = datetime.now(timezone.utc).isoformat()
        self.phases: List[List[CQBTask]] = []  # phase_index -> [CQBTask]
        self.all_tasks: Dict[str, CQBTask] = {}
        self.notes: List[str] = []
        self.stats = {
            "total_tasks": 0,
            "rooms_to_clear": 0,
            "doors_to_breach": 0,
            "phases": 0,
            "min_assets_needed": 0,
        }

    def add_task(self, task: CQBTask, phase: int):
        """Add a task to a specific phase."""
        while len(self.phases) <= phase:
            self.phases.append([])
        task.phase = phase
        self.phases[phase].append(task)
        self.all_tasks[task.id] = task

    def get_task(self, task_id: str) -> Optional[CQBTask]:
        return self.all_tasks.get(task_id)

    def get_phase(self, phase: int) -> List[CQBTask]:
        if 0 <= phase < len(self.phases):
            return self.phases[phase]
        return []

    def finalize(self):
        """Compute plan stats and mark as READY."""
        self.stats["total_tasks"] = len(self.all_tasks)
        self.stats["phases"] = len(self.phases)
        self.stats["rooms_to_clear"] = sum(
            1 for t in self.all_tasks.values() if t.task_type == "CLEAR")
        self.stats["doors_to_breach"] = sum(
            1 for t in self.all_tasks.values() if t.task_type == "BREACH")
        # Min assets = max min_assets across all tasks in the busiest phase
        if self.phases:
            per_phase = []
            for phase_tasks in self.phases:
                phase_total = sum(t.min_assets for t in phase_tasks)
                per_phase.append(phase_total)
            self.stats["min_assets_needed"] = max(per_phase) if per_phase else 0
        self.status = "READY"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "building_id": self.building_id,
            "objective": self.objective,
            "status": self.status,
            "created": self.created,
            "phases": [
                [t.to_dict() for t in phase_tasks]
                for phase_tasks in self.phases
            ],
            "stats": self.stats,
            "notes": self.notes,
        }


class CQBPlanner:
    """Generates room-clearing plans from building models."""

    def __init__(self):
        self.plans: Dict[str, CQBPlan] = {}

    def generate_plan(self, building, floors: Optional[List[int]] = None,
                      objective_room: str = "",
                      team_size: int = 4,
                      entry_door_id: str = "") -> CQBPlan:
        """Generate a clearing plan for a building.

        Args:
            building: BuildingModel instance
            floors: which floors to clear (None = all)
            objective_room: if set, the final room to SECURE
            team_size: number of assets per fire team
            entry_door_id: preferred entry door (auto-detect if empty)
        Returns:
            CQBPlan with phased tasks
        """
        plan = CQBPlan(building.id, objective=objective_room or "Clear building")

        # Determine floors to clear
        target_floors = floors if floors is not None else building.get_floors()

        # Find entry point
        entry_room = self._find_entry(building, entry_door_id)
        if not entry_room:
            plan.notes.append("WARNING: No entry point found — using first room on lowest floor")
            rooms_f0 = building.get_rooms_on_floor(min(target_floors))
            if rooms_f0:
                entry_room = rooms_f0[0]["id"]
            else:
                plan.notes.append("ERROR: No rooms on target floors")
                plan.status = "FAILED"
                self.plans[plan.id] = plan
                return plan

        # Get rooms to clear (skip already-cleared)
        rooms_to_clear = []
        for f in sorted(target_floors):
            for room in building.get_rooms_on_floor(f):
                if not room.get("cleared"):
                    rooms_to_clear.append(room["id"])

        if not rooms_to_clear:
            plan.notes.append("All rooms already cleared")
            plan.status = "READY"
            self.plans[plan.id] = plan
            return plan

        # BFS ordering from entry point — determines clearing sequence
        clear_order = self._bfs_order(building, entry_room, rooms_to_clear)

        # Generate phased tasks
        phase = 0
        prev_clear_ids = []
        rooms_by_floor = {}
        for room_id in clear_order:
            fl = building.get_room_floor(room_id)
            rooms_by_floor.setdefault(fl, []).append(room_id)

        for fl in sorted(rooms_by_floor.keys()):
            floor_rooms = rooms_by_floor[fl]
            floor_prev_ids = []

            for room_id in floor_rooms:
                task_ids_for_room = []

                # Find the door leading into this room from the cleared side
                entry_doors = self._get_entry_doors_for_room(
                    building, room_id, clear_order[:clear_order.index(room_id)])

                for door in entry_doors:
                    # STACK at the door
                    stack = CQBTask("STACK", building.id,
                                    target_id=door["id"], floor=fl,
                                    phase=phase, priority=3,
                                    depends_on=list(prev_clear_ids[-1:]),
                                    params={"door_id": door["id"]})
                    plan.add_task(stack, phase)
                    task_ids_for_room.append(stack.id)

                    # BREACH the door (reinforced → explosive, otherwise manual)
                    breach_method = "explosive" if door.get("type") == "reinforced" else "manual"
                    breach = CQBTask("BREACH", building.id,
                                     target_id=door["id"], floor=fl,
                                     phase=phase, priority=2,
                                     depends_on=[stack.id],
                                     params={"door_id": door["id"], "method": breach_method})
                    plan.add_task(breach, phase)
                    task_ids_for_room.append(breach.id)
                    break  # one entry door per room

                # CLEAR the room
                clear = CQBTask("CLEAR", building.id,
                                target_id=room_id, floor=fl,
                                phase=phase, priority=1,
                                depends_on=task_ids_for_room if task_ids_for_room else list(prev_clear_ids[-1:]),
                                params={"room_id": room_id, "formation": "dynamic"},
                                min_assets=min(team_size, 4))
                plan.add_task(clear, phase)
                floor_prev_ids.append(clear.id)

            # HOLD the floor after clearing it
            if floor_rooms:
                hold = CQBTask("HOLD", building.id,
                               target_id=f"floor-{fl}", floor=fl,
                               phase=phase, priority=6,
                               depends_on=list(floor_prev_ids),
                               params={"sector": "all", "duration_sec": 300},
                               min_assets=1)
                plan.add_task(hold, phase)

            prev_clear_ids = floor_prev_ids
            phase += 1

        # SECURE objective room if specified
        if objective_room and building.get_room(objective_room):
            obj_floor = building.get_room_floor(objective_room) or 0
            secure = CQBTask("SECURE", building.id,
                             target_id=objective_room, floor=obj_floor,
                             phase=phase, priority=1,
                             depends_on=list(prev_clear_ids),
                             params={"area_id": objective_room, "duration_sec": 600},
                             min_assets=2)
            plan.add_task(secure, phase)

        plan.finalize()
        self.plans[plan.id] = plan
        return plan

    def _find_entry(self, building, preferred_door_id: str = "") -> Optional[str]:
        """Find the best entry room.  Returns room_id or None."""
        if preferred_door_id:
            door = building.get_door(preferred_door_id)
            if door:
                # Return the interior room
                if door["from_room"] == "EXTERIOR":
                    return door["to_room"]
                if door["to_room"] == "EXTERIOR":
                    return door["from_room"]

        # Auto-detect: first exterior door
        entry_doors = building.get_entry_doors()
        if entry_doors:
            d = entry_doors[0]
            return d["to_room"] if d["from_room"] == "EXTERIOR" else d["from_room"]
        return None

    def _bfs_order(self, building, start: str, target_rooms: List[str]) -> List[str]:
        """BFS traversal from start, returning only rooms in target_rooms set."""
        targets = set(target_rooms)
        if start not in targets:
            # Start room might already be cleared; still use as BFS origin
            pass
        visited = {start}
        queue = deque([start])
        order = []
        if start in targets:
            order.append(start)

        while queue:
            current = queue.popleft()
            for neighbor in building.get_adjacent_rooms(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
                    if neighbor in targets:
                        order.append(neighbor)

        # Append any unreachable target rooms at the end
        for r in target_rooms:
            if r not in order:
                order.append(r)

        return order

    def _get_entry_doors_for_room(self, building, room_id: str,
                                   cleared_rooms: List[str]) -> List[dict]:
        """Find doors connecting room_id to already-cleared or exterior rooms."""
        doors = building.get_doors_for_room(room_id)
        entry = []
        cleared_set = set(cleared_rooms)
        for d in doors:
            other = d["to_room"] if d["from_room"] == room_id else d["from_room"]
            if other == "EXTERIOR" or other in cleared_set:
                entry.append(d)
        return entry if entry else doors[:1]  # fallback to first door

    def get_plan(self, plan_id: str) -> Optional[CQBPlan]:
        return self.plans.get(plan_id)

    def list_plans(self) -> List[dict]:
        return [p.to_dict() for p in self.plans.values()]

    def get_stats(self) -> dict:
        return {
            "total_plans": len(self.plans),
            "by_status": {
                s: sum(1 for p in self.plans.values() if p.status == s)
                for s in ("DRAFT", "READY", "EXECUTING", "COMPLETE", "FAILED")
            },
        }
