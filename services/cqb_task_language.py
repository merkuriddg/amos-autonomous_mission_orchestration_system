#!/usr/bin/env python3
"""AMOS B3.1 — CQB Task Language

Extends AMOS mission tasking beyond waypoint navigation with room-scale
CQB-specific task types.  Each task carries role assignments, breach
methods, formation preferences, and room-level targeting.

Task Types:
  BREACH   — breach a door (explosive, mechanical, manual, ballistic)
  CLEAR    — clear a room using a CQB formation
  HOLD     — hold a position with a sector of fire
  SECURE   — secure an area for a specified duration
  EXTRACT  — extract a casualty or HVT along a route
  STACK    — stack a team at a door in preparation for entry
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════
#  CQB TASK TYPES & CONSTANTS
# ═══════════════════════════════════════════════════════════

CQB_TASK_TYPES = ("BREACH", "CLEAR", "HOLD", "SECURE", "EXTRACT", "STACK")

BREACH_METHODS = ("explosive", "mechanical", "manual", "ballistic")

CLEAR_FORMATIONS = ("buttonhook", "crisscross", "dynamic", "stack")

HOLD_SECTORS = ("north", "south", "east", "west", "all", "door", "window")

EXTRACT_ROUTES = ("primary", "alternate", "emergency")

# CQB role assignments within a fire team
CQB_ROLES = ("point", "number_2", "cover", "rear_security", "breacher", "medic", "overwatch")

# Task status progression
CQB_TASK_STATUSES = ("PLANNED", "READY", "EXECUTING", "COMPLETE", "FAILED", "ABORTED")


# ═══════════════════════════════════════════════════════════
#  CQB TASK
# ═══════════════════════════════════════════════════════════

class CQBTask:
    """A single CQB task with type-specific parameters and role assignments."""

    def __init__(self, task_type: str, building_id: str = "", **kwargs):
        self.id = f"CQB-{uuid.uuid4().hex[:8]}"
        self.task_type = task_type.upper()
        self.building_id = building_id
        self.status = "PLANNED"
        self.created = datetime.now(timezone.utc).isoformat()
        self.started = None
        self.completed = None
        self.phase = kwargs.get("phase", 0)
        self.priority = kwargs.get("priority", 5)
        self.depends_on: List[str] = kwargs.get("depends_on", [])

        # Target reference (room, door, position)
        self.target_id = kwargs.get("target_id", "")  # room_id or door_id
        self.floor = kwargs.get("floor", 0)

        # Role assignments: {role: asset_id}
        self.roles: Dict[str, str] = kwargs.get("roles", {})
        self.assigned_assets: List[str] = kwargs.get("assigned_assets", [])
        self.min_assets = kwargs.get("min_assets", 2)

        # Type-specific parameters
        self.params = kwargs.get("params", {})
        self._set_defaults()

        # Execution notes
        self.notes: List[str] = []
        self.roe_override: Optional[str] = kwargs.get("roe_override", None)

    def _set_defaults(self):
        """Set type-specific default parameters."""
        if self.task_type == "BREACH":
            self.params.setdefault("method", "manual")
            self.params.setdefault("door_id", self.target_id)
            self.min_assets = max(self.min_assets, 2)
        elif self.task_type == "CLEAR":
            self.params.setdefault("formation", "dynamic")
            self.params.setdefault("room_id", self.target_id)
            self.min_assets = max(self.min_assets, 2)
        elif self.task_type == "HOLD":
            self.params.setdefault("sector", "all")
            self.params.setdefault("duration_sec", 300)
        elif self.task_type == "SECURE":
            self.params.setdefault("duration_sec", 600)
            self.params.setdefault("area_id", self.target_id)
        elif self.task_type == "EXTRACT":
            self.params.setdefault("route", "primary")
            self.params.setdefault("casualty_id", "")
            self.min_assets = max(self.min_assets, 2)
        elif self.task_type == "STACK":
            self.params.setdefault("door_id", self.target_id)
            self.params.setdefault("team", "alpha")

    def validate(self) -> List[str]:
        """Validate the task. Returns list of errors (empty = valid)."""
        errors = []
        if self.task_type not in CQB_TASK_TYPES:
            errors.append(f"Unknown CQB task type: {self.task_type}")
        if not self.building_id:
            errors.append("building_id is required")
        if self.task_type == "BREACH":
            m = self.params.get("method", "")
            if m and m not in BREACH_METHODS:
                errors.append(f"Invalid breach method: {m}")
            if not self.params.get("door_id"):
                errors.append("BREACH requires door_id")
        elif self.task_type == "CLEAR":
            f = self.params.get("formation", "")
            if f and f not in CLEAR_FORMATIONS:
                errors.append(f"Invalid clear formation: {f}")
            if not self.params.get("room_id"):
                errors.append("CLEAR requires room_id")
        elif self.task_type == "HOLD":
            s = self.params.get("sector", "")
            if s and s not in HOLD_SECTORS:
                errors.append(f"Invalid hold sector: {s}")
        elif self.task_type == "EXTRACT":
            r = self.params.get("route", "")
            if r and r not in EXTRACT_ROUTES:
                errors.append(f"Invalid extract route: {r}")
        elif self.task_type == "STACK":
            if not self.params.get("door_id"):
                errors.append("STACK requires door_id")
        for role in self.roles:
            if role not in CQB_ROLES:
                errors.append(f"Unknown CQB role: {role}")
        if self.priority < 1 or self.priority > 10:
            errors.append(f"Priority must be 1-10, got {self.priority}")
        return errors

    def assign_roles(self, asset_ids: List[str]):
        """Auto-assign CQB roles to a list of assets.

        First asset = point, second = number_2, third = cover,
        fourth = rear_security. Additional assets get overwatch.
        """
        role_order = ["point", "number_2", "cover", "rear_security"]
        self.assigned_assets = list(asset_ids)
        self.roles = {}
        for i, aid in enumerate(asset_ids):
            if i < len(role_order):
                self.roles[role_order[i]] = aid
            else:
                self.roles[f"overwatch_{i - len(role_order) + 1}"] = aid

    def start(self):
        """Mark task as executing."""
        self.status = "EXECUTING"
        self.started = datetime.now(timezone.utc).isoformat()

    def complete(self):
        """Mark task as complete."""
        self.status = "COMPLETE"
        self.completed = datetime.now(timezone.utc).isoformat()

    def fail(self, reason: str = ""):
        """Mark task as failed."""
        self.status = "FAILED"
        self.completed = datetime.now(timezone.utc).isoformat()
        if reason:
            self.notes.append(f"FAILED: {reason}")

    def abort(self, reason: str = ""):
        """Abort the task."""
        self.status = "ABORTED"
        self.completed = datetime.now(timezone.utc).isoformat()
        if reason:
            self.notes.append(f"ABORTED: {reason}")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_type": self.task_type,
            "building_id": self.building_id,
            "target_id": self.target_id,
            "floor": self.floor,
            "status": self.status,
            "phase": self.phase,
            "priority": self.priority,
            "depends_on": self.depends_on,
            "roles": self.roles,
            "assigned_assets": self.assigned_assets,
            "min_assets": self.min_assets,
            "params": self.params,
            "notes": self.notes,
            "roe_override": self.roe_override,
            "created": self.created,
            "started": self.started,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CQBTask":
        """Reconstruct a CQBTask from a dict."""
        t = cls(
            task_type=d.get("task_type", "CLEAR"),
            building_id=d.get("building_id", ""),
            target_id=d.get("target_id", ""),
            floor=d.get("floor", 0),
            phase=d.get("phase", 0),
            priority=d.get("priority", 5),
            depends_on=d.get("depends_on", []),
            roles=d.get("roles", {}),
            assigned_assets=d.get("assigned_assets", []),
            min_assets=d.get("min_assets", 2),
            params=d.get("params", {}),
            roe_override=d.get("roe_override"),
        )
        if d.get("id"):
            t.id = d["id"]
        t.status = d.get("status", "PLANNED")
        t.notes = d.get("notes", [])
        t.created = d.get("created", t.created)
        t.started = d.get("started")
        t.completed = d.get("completed")
        return t

    def __repr__(self):
        return f"<CQBTask {self.id} {self.task_type} target={self.target_id} status={self.status}>"
