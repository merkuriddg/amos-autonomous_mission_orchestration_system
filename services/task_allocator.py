"""AMOS Multi-Agent Task Allocator — Auction-Based Assignment + Temporal Planning

Implements:
  - Auction-based task assignment: assets bid on tasks by fitness score
  - Dynamic re-tasking: automatic redistribution when assets go FAULT
  - Temporal mission planning: phased execution with dependency chains
"""

import math, random, time, uuid
from datetime import datetime, timezone


def _dist(a, b):
    ap = a.get("position", a)
    return math.sqrt((ap.get("lat", 0) - b.get("lat", 0))**2 +
                     (ap.get("lng", ap.get("lon", 0)) - b.get("lng", b.get("lon", 0)))**2)


# ─── Task Definition ──────────────────────────────────────

class Task:
    STATUSES = ("PENDING", "ASSIGNED", "EN_ROUTE", "EXECUTING", "COMPLETE", "FAILED")

    def __init__(self, task_type, location=None, priority=5, required_sensors=None,
                 required_weapons=False, min_assets=1, phase=0, depends_on=None,
                 description="", duration_sec=120):
        self.id = f"TASK-{uuid.uuid4().hex[:6]}"
        self.type = task_type
        self.location = location or {}
        self.priority = priority  # 1=highest, 10=lowest
        self.required_sensors = required_sensors or []
        self.required_weapons = required_weapons
        self.min_assets = min_assets
        self.phase = phase
        self.depends_on = depends_on or []
        self.description = description
        self.duration_sec = duration_sec
        self.status = "PENDING"
        self.assigned_assets = []
        self.bids = []
        self.created = time.time()
        self.started = None
        self.completed = None

    def to_dict(self):
        return {
            "id": self.id, "type": self.type, "location": self.location,
            "priority": self.priority, "status": self.status, "phase": self.phase,
            "depends_on": self.depends_on, "description": self.description,
            "assigned_assets": self.assigned_assets, "bid_count": len(self.bids),
            "min_assets": self.min_assets, "duration_sec": self.duration_sec,
            "created": self.created, "started": self.started, "completed": self.completed,
            "required_sensors": self.required_sensors,
            "required_weapons": self.required_weapons,
        }


# ─── Bid Calculator ───────────────────────────────────────

def calculate_bid(asset, task):
    """Calculate an asset's fitness score for a task (higher = better fit)."""
    score = 100.0

    # Proximity (0-30 points)
    if task.location and "lat" in task.location:
        d = _dist(asset, task.location)
        score += max(0, 30 - d * 300)

    # Sensor match (0-25 points)
    asset_sensors = set(asset.get("sensors") or [])
    if task.required_sensors:
        matched = len(asset_sensors & set(task.required_sensors))
        score += (matched / len(task.required_sensors)) * 25

    # Weapons match (0-15 points)
    if task.required_weapons:
        if asset.get("weapons"):
            score += 15
        else:
            score -= 50  # strong penalty

    # Battery/endurance (0-15 points)
    batt = asset.get("health", {}).get("battery_pct", 100)
    score += (batt / 100) * 15

    # Domain appropriateness (0-10 points)
    domain = asset.get("domain", "")
    task_needs_air = task.type in ("ISR", "OVERWATCH", "STRIKE", "EW_JAM")
    task_needs_ground = task.type in ("PATROL", "CHECKPOINT", "RESUPPLY")
    task_needs_maritime = task.type in ("COASTAL_PATROL", "SUBSURFACE")
    if (task_needs_air and domain == "air") or \
       (task_needs_ground and domain == "ground") or \
       (task_needs_maritime and domain == "maritime"):
        score += 10

    # Current load penalty
    current_tasks = asset.get("_task_count", 0)
    score -= current_tasks * 20

    # Status penalty
    if asset.get("status") in ("FAULT", "RTB"):
        score -= 200

    # Role bonus
    role = asset.get("role", "")
    role_task_match = {
        "isr_strike": ["ISR", "STRIKE"], "recon": ["ISR", "SCAN"],
        "ew": ["EW_JAM", "SIGINT"], "direct_action": ["ENGAGE", "PATROL"],
        "resupply": ["RESUPPLY"], "medevac": ["MEDEVAC"],
        "coastal_patrol": ["COASTAL_PATROL"], "sigint": ["SIGINT", "DF"],
        "airborne_c2": ["OVERWATCH", "RELAY"],
    }
    if task.type in role_task_match.get(role, []):
        score += 20

    return max(0, round(score, 2))


# ─── Task Allocator (Main Class) ─────────────────────────

class TaskAllocator:
    """Auction-based task allocation with temporal planning."""

    def __init__(self):
        self.tasks = {}  # task_id -> Task
        self.missions = []  # high-level missions with phase structure
        self.assignment_log = []
        self.stats = {"tasks_created": 0, "tasks_assigned": 0,
                      "tasks_completed": 0, "retasks": 0}

    def create_task(self, task_type, **kwargs):
        t = Task(task_type, **kwargs)
        self.tasks[t.id] = t
        self.stats["tasks_created"] += 1
        return t.to_dict()

    def create_mission(self, name, phases):
        """Create a multi-phase mission.
        phases: [{tasks: [{type, location, ...}], depends_on_phase: int}, ...]
        """
        mission_id = f"MSN-{uuid.uuid4().hex[:6]}"
        mission_tasks = []

        for pi, phase in enumerate(phases):
            phase_task_ids = []
            dep_phase = phase.get("depends_on_phase")
            dep_ids = []
            if dep_phase is not None and dep_phase < len(mission_tasks):
                dep_ids = mission_tasks[dep_phase]

            for td in phase.get("tasks", []):
                t = Task(
                    task_type=td.get("type", "GENERIC"),
                    location=td.get("location"),
                    priority=td.get("priority", 5),
                    required_sensors=td.get("required_sensors"),
                    required_weapons=td.get("required_weapons", False),
                    min_assets=td.get("min_assets", 1),
                    phase=pi,
                    depends_on=dep_ids,
                    description=td.get("description", ""),
                    duration_sec=td.get("duration_sec", 120),
                )
                self.tasks[t.id] = t
                phase_task_ids.append(t.id)
                self.stats["tasks_created"] += 1

            mission_tasks.append(phase_task_ids)

        mission = {
            "id": mission_id, "name": name,
            "phases": mission_tasks, "phase_count": len(phases),
            "created": datetime.now(timezone.utc).isoformat(),
            "status": "ACTIVE",
        }
        self.missions.append(mission)
        return mission

    def allocate(self, assets):
        """Run auction-based allocation for all pending tasks."""
        events = []
        # Track task counts per asset
        task_counts = {}
        for t in self.tasks.values():
            if t.status in ("ASSIGNED", "EN_ROUTE", "EXECUTING"):
                for aid in t.assigned_assets:
                    task_counts[aid] = task_counts.get(aid, 0) + 1

        for aid in assets:
            assets[aid]["_task_count"] = task_counts.get(aid, 0)

        pending = [t for t in self.tasks.values() if t.status == "PENDING"]
        # Sort by priority (lower number = higher priority)
        pending.sort(key=lambda t: t.priority)

        for task in pending:
            # Check dependencies
            deps_met = all(
                self.tasks.get(dep_id, task).status == "COMPLETE"
                for dep_id in task.depends_on
            )
            if not deps_met:
                continue

            # Collect bids
            bids = []
            for aid, a in assets.items():
                if a.get("status") in ("FAULT",):
                    continue
                score = calculate_bid(a, task)
                bids.append({"asset_id": aid, "score": score})

            bids.sort(key=lambda b: b["score"], reverse=True)
            task.bids = bids

            # Assign top N assets
            winners = [b["asset_id"] for b in bids[:task.min_assets]
                       if b["score"] > 50]

            if len(winners) >= task.min_assets:
                task.assigned_assets = winners
                task.status = "ASSIGNED"
                task.started = time.time()
                self.stats["tasks_assigned"] += 1
                for aid in winners:
                    assets[aid]["_task_count"] = assets[aid].get("_task_count", 0) + 1

                event = {
                    "type": "TASK_ASSIGNED", "task_id": task.id,
                    "task_type": task.type, "assets": winners,
                    "top_bid": bids[0]["score"] if bids else 0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                self.assignment_log.append(event)
                events.append(event)

        # Clean temp field
        for aid in assets:
            assets[aid].pop("_task_count", None)

        return events

    def tick(self, assets, dt=1.0):
        """Progress active tasks and handle re-tasking."""
        events = []

        for tid, task in self.tasks.items():
            if task.status == "ASSIGNED":
                task.status = "EN_ROUTE"
            elif task.status == "EN_ROUTE":
                # Check if assets have arrived (simplified)
                if task.started and time.time() - task.started > 10:
                    task.status = "EXECUTING"
            elif task.status == "EXECUTING":
                elapsed = time.time() - (task.started or time.time())
                if elapsed > task.duration_sec:
                    task.status = "COMPLETE"
                    task.completed = time.time()
                    self.stats["tasks_completed"] += 1
                    events.append({
                        "type": "TASK_COMPLETE", "task_id": tid,
                        "task_type": task.type, "assets": task.assigned_assets,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

            # Re-task if assigned asset goes FAULT
            if task.status in ("ASSIGNED", "EN_ROUTE", "EXECUTING"):
                lost = [aid for aid in task.assigned_assets
                        if aid not in assets or assets.get(aid, {}).get("status") == "FAULT"]
                if lost:
                    for aid in lost:
                        task.assigned_assets.remove(aid)
                    if len(task.assigned_assets) < task.min_assets:
                        task.status = "PENDING"
                        task.bids.clear()
                        self.stats["retasks"] += 1
                        events.append({
                            "type": "RETASK", "task_id": tid,
                            "reason": f"Assets lost: {lost}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

        # Run allocation for any newly pending tasks
        alloc_events = self.allocate(assets)
        events.extend(alloc_events)

        # Update mission statuses
        for mission in self.missions:
            if mission["status"] != "ACTIVE":
                continue
            all_done = all(
                self.tasks.get(tid, Task("x")).status == "COMPLETE"
                for phase in mission["phases"] for tid in phase
            )
            if all_done:
                mission["status"] = "COMPLETE"
                events.append({
                    "type": "MISSION_COMPLETE", "mission_id": mission["id"],
                    "name": mission["name"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        # Trim logs
        if len(self.assignment_log) > 500:
            self.assignment_log = self.assignment_log[-500:]

        return events

    def get_tasks(self, status=None):
        if status:
            return [t.to_dict() for t in self.tasks.values() if t.status == status]
        return [t.to_dict() for t in self.tasks.values()]

    def get_missions(self):
        return list(self.missions)

    def get_gantt(self):
        """Return Gantt-chart-ready timeline data."""
        items = []
        for t in self.tasks.values():
            items.append({
                "id": t.id, "type": t.type, "phase": t.phase,
                "status": t.status, "priority": t.priority,
                "start": t.started or t.created,
                "end": t.completed or (t.started + t.duration_sec if t.started else t.created + t.duration_sec),
                "assets": t.assigned_assets, "depends_on": t.depends_on,
            })
        items.sort(key=lambda x: (x["phase"], x["start"]))
        return items

    def get_stats(self):
        return dict(self.stats)
