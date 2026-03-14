#!/usr/bin/env python3
"""AMOS Behavior Tree Engine — Autonomous Decision Logic

Implements a standard Behavior Tree framework for autonomous mission execution.
Nodes tick against a shared Blackboard (dict) carrying mission context:
  assets, threats, fused_tracks, tasks, roe_posture, comms_status, etc.

Node types:
  Composites : Selector (OR), Sequence (AND), Parallel (N-of-M)
  Decorators : Inverter, Repeater, Guard, RetryUntilSuccess
  Leaves     : Condition (predicate check), Action (callable side-effect)

Usage:
    tree = BehaviorTree("recon_strike", Sequence([
        Condition("hostile_detected", lambda bb: bb.get("hostile_count", 0) > 0),
        Action("launch_isr", lambda bb: spawn_isr_task(bb)),
        Action("track_target", lambda bb: assign_tracker(bb)),
    ]))
    result = tree.tick(blackboard)
"""

import time
import uuid
import threading
from enum import Enum
from datetime import datetime, timezone


# ─── Node Status ──────────────────────────────────────────

class Status(Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RUNNING = "RUNNING"


# ─── Base Node ────────────────────────────────────────────

class Node:
    """Base class for all BT nodes."""

    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self.status = Status.FAILURE
        self.tick_count = 0
        self.last_tick = None

    def tick(self, bb: dict) -> Status:
        """Execute this node. Override in subclasses."""
        self.tick_count += 1
        self.last_tick = time.time()
        return Status.FAILURE

    def reset(self):
        """Reset node state for re-use."""
        self.status = Status.FAILURE
        self.tick_count = 0

    def to_dict(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "name": self.name,
            "status": self.status.value,
            "tick_count": self.tick_count,
        }


# ─── Leaf Nodes ───────────────────────────────────────────

class Condition(Node):
    """Checks a predicate against the blackboard. No side effects.
    Returns SUCCESS if predicate is truthy, FAILURE otherwise.
    """

    def __init__(self, name: str, predicate):
        super().__init__(name)
        self.predicate = predicate

    def tick(self, bb: dict) -> Status:
        super().tick(bb)
        try:
            result = self.predicate(bb)
            self.status = Status.SUCCESS if result else Status.FAILURE
        except Exception:
            self.status = Status.FAILURE
        return self.status


class Action(Node):
    """Executes a callable against the blackboard.
    The callable should return True/Status.SUCCESS, False/Status.FAILURE,
    or "running"/Status.RUNNING.
    """

    def __init__(self, name: str, action):
        super().__init__(name)
        self.action = action

    def tick(self, bb: dict) -> Status:
        super().tick(bb)
        try:
            result = self.action(bb)
            if isinstance(result, Status):
                self.status = result
            elif result is True:
                self.status = Status.SUCCESS
            elif result is False:
                self.status = Status.FAILURE
            elif result == "running":
                self.status = Status.RUNNING
            else:
                self.status = Status.SUCCESS
        except Exception:
            self.status = Status.FAILURE
        return self.status


# ─── Composite Nodes ─────────────────────────────────────

class Sequence(Node):
    """Runs children in order. Fails on first FAILURE. Returns RUNNING if
    a child is RUNNING. Returns SUCCESS only if ALL children succeed.
    Like a logical AND.
    """

    def __init__(self, children: list, name: str = ""):
        super().__init__(name or "Sequence")
        self.children = children
        self._running_idx = 0

    def tick(self, bb: dict) -> Status:
        super().tick(bb)
        for i in range(self._running_idx, len(self.children)):
            child_status = self.children[i].tick(bb)
            if child_status == Status.FAILURE:
                self._running_idx = 0
                self.status = Status.FAILURE
                return self.status
            if child_status == Status.RUNNING:
                self._running_idx = i
                self.status = Status.RUNNING
                return self.status
        self._running_idx = 0
        self.status = Status.SUCCESS
        return self.status

    def reset(self):
        super().reset()
        self._running_idx = 0
        for c in self.children:
            c.reset()

    def to_dict(self):
        d = super().to_dict()
        d["children"] = [c.to_dict() for c in self.children]
        return d


class Selector(Node):
    """Tries children in order. Returns SUCCESS on first success.
    Returns RUNNING if a child is RUNNING.
    Returns FAILURE only if ALL children fail.
    Like a logical OR / fallback.
    """

    def __init__(self, children: list, name: str = ""):
        super().__init__(name or "Selector")
        self.children = children
        self._running_idx = 0

    def tick(self, bb: dict) -> Status:
        super().tick(bb)
        for i in range(self._running_idx, len(self.children)):
            child_status = self.children[i].tick(bb)
            if child_status == Status.SUCCESS:
                self._running_idx = 0
                self.status = Status.SUCCESS
                return self.status
            if child_status == Status.RUNNING:
                self._running_idx = i
                self.status = Status.RUNNING
                return self.status
        self._running_idx = 0
        self.status = Status.FAILURE
        return self.status

    def reset(self):
        super().reset()
        self._running_idx = 0
        for c in self.children:
            c.reset()

    def to_dict(self):
        d = super().to_dict()
        d["children"] = [c.to_dict() for c in self.children]
        return d


class Parallel(Node):
    """Ticks ALL children every tick. Succeeds when `success_threshold`
    children succeed. Fails when enough children fail that the threshold
    can never be met.
    """

    def __init__(self, children: list, success_threshold: int = None, name: str = ""):
        super().__init__(name or "Parallel")
        self.children = children
        self.success_threshold = success_threshold or len(children)

    def tick(self, bb: dict) -> Status:
        super().tick(bb)
        successes = 0
        failures = 0
        for child in self.children:
            s = child.tick(bb)
            if s == Status.SUCCESS:
                successes += 1
            elif s == Status.FAILURE:
                failures += 1
        if successes >= self.success_threshold:
            self.status = Status.SUCCESS
        elif failures > len(self.children) - self.success_threshold:
            self.status = Status.FAILURE
        else:
            self.status = Status.RUNNING
        return self.status

    def reset(self):
        super().reset()
        for c in self.children:
            c.reset()

    def to_dict(self):
        d = super().to_dict()
        d["success_threshold"] = self.success_threshold
        d["children"] = [c.to_dict() for c in self.children]
        return d


# ─── Decorator Nodes ─────────────────────────────────────

class Inverter(Node):
    """Inverts child result: SUCCESS↔FAILURE. RUNNING passes through."""

    def __init__(self, child: Node, name: str = ""):
        super().__init__(name or f"Inverter({child.name})")
        self.child = child

    def tick(self, bb: dict) -> Status:
        super().tick(bb)
        s = self.child.tick(bb)
        if s == Status.SUCCESS:
            self.status = Status.FAILURE
        elif s == Status.FAILURE:
            self.status = Status.SUCCESS
        else:
            self.status = Status.RUNNING
        return self.status

    def to_dict(self):
        d = super().to_dict()
        d["child"] = self.child.to_dict()
        return d


class Repeater(Node):
    """Repeats child up to `max_repeats` times, or forever if max_repeats=0.
    Returns RUNNING while repeating, SUCCESS when child succeeds on final repeat.
    """

    def __init__(self, child: Node, max_repeats: int = 0, name: str = ""):
        super().__init__(name or f"Repeat({child.name})")
        self.child = child
        self.max_repeats = max_repeats
        self._count = 0

    def tick(self, bb: dict) -> Status:
        super().tick(bb)
        s = self.child.tick(bb)
        if s == Status.SUCCESS:
            self._count += 1
            if self.max_repeats > 0 and self._count >= self.max_repeats:
                self.status = Status.SUCCESS
                return self.status
            self.child.reset()
        elif s == Status.FAILURE:
            self.status = Status.FAILURE
            return self.status
        self.status = Status.RUNNING
        return self.status

    def reset(self):
        super().reset()
        self._count = 0
        self.child.reset()


class Guard(Node):
    """Only ticks child if condition is met, otherwise returns FAILURE."""

    def __init__(self, condition: Node, child: Node, name: str = ""):
        super().__init__(name or f"Guard({condition.name})")
        self.condition = condition
        self.child = child

    def tick(self, bb: dict) -> Status:
        super().tick(bb)
        if self.condition.tick(bb) == Status.SUCCESS:
            self.status = self.child.tick(bb)
        else:
            self.status = Status.FAILURE
        return self.status

    def to_dict(self):
        d = super().to_dict()
        d["condition"] = self.condition.to_dict()
        d["child"] = self.child.to_dict()
        return d


class RetryUntilSuccess(Node):
    """Retries child up to max_attempts. Returns RUNNING while retrying."""

    def __init__(self, child: Node, max_attempts: int = 3, name: str = ""):
        super().__init__(name or f"Retry({child.name})")
        self.child = child
        self.max_attempts = max_attempts
        self._attempts = 0

    def tick(self, bb: dict) -> Status:
        super().tick(bb)
        s = self.child.tick(bb)
        if s == Status.SUCCESS:
            self.status = Status.SUCCESS
            return self.status
        self._attempts += 1
        if self._attempts >= self.max_attempts:
            self.status = Status.FAILURE
            return self.status
        self.child.reset()
        self.status = Status.RUNNING
        return self.status

    def reset(self):
        super().reset()
        self._attempts = 0
        self.child.reset()


# ─── Behavior Tree ────────────────────────────────────────

class BehaviorTree:
    """A named behavior tree with a root node and tick method.

    The blackboard is a shared dict passed through all nodes, carrying
    mission context: assets, threats, fused tracks, ROE posture, etc.
    """

    def __init__(self, name: str, root: Node):
        self.id = f"BT-{uuid.uuid4().hex[:8]}"
        self.name = name
        self.root = root
        self.status = Status.FAILURE
        self.tick_count = 0
        self.created = datetime.now(timezone.utc).isoformat()
        self.last_tick = None
        self.event_log = []
        self._lock = threading.Lock()

    def tick(self, bb: dict) -> Status:
        """Execute one tick of the behavior tree."""
        with self._lock:
            self.tick_count += 1
            self.last_tick = datetime.now(timezone.utc).isoformat()
            self.status = self.root.tick(bb)
            self.event_log.append({
                "tick": self.tick_count,
                "status": self.status.value,
                "timestamp": self.last_tick,
            })
            if len(self.event_log) > 500:
                self.event_log = self.event_log[-500:]
            return self.status

    def reset(self):
        self.root.reset()
        self.status = Status.FAILURE

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "tick_count": self.tick_count,
            "created": self.created,
            "last_tick": self.last_tick,
            "tree": self.root.to_dict(),
        }

    def summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "tick_count": self.tick_count,
            "last_tick": self.last_tick,
        }


# ─── BT Registry ─────────────────────────────────────────

class BTRegistry:
    """Manages active behavior trees."""

    def __init__(self):
        self.trees = {}  # bt_id -> BehaviorTree
        self._lock = threading.Lock()

    def register(self, bt: BehaviorTree) -> str:
        with self._lock:
            self.trees[bt.id] = bt
        return bt.id

    def unregister(self, bt_id: str) -> bool:
        with self._lock:
            return self.trees.pop(bt_id, None) is not None

    def get(self, bt_id: str):
        return self.trees.get(bt_id)

    def tick_all(self, bb: dict) -> list:
        """Tick all registered trees. Returns list of (id, status) pairs."""
        results = []
        for bt_id, bt in list(self.trees.items()):
            status = bt.tick(bb)
            results.append({"id": bt_id, "name": bt.name, "status": status.value})
        return results

    def list_all(self) -> list:
        return [bt.summary() for bt in self.trees.values()]

    def summary(self) -> dict:
        by_status = {}
        for bt in self.trees.values():
            s = bt.status.value
            by_status[s] = by_status.get(s, 0) + 1
        return {
            "total": len(self.trees),
            "by_status": by_status,
        }


if __name__ == "__main__":
    # Quick self-test
    import json

    bb = {"hostile_count": 2, "confidence": 0.8, "roe_posture": "weapons_hold"}

    tree = BehaviorTree("test_recon", Sequence([
        Condition("has_hostiles", lambda b: b.get("hostile_count", 0) > 0),
        Condition("high_confidence", lambda b: b.get("confidence", 0) > 0.6),
        Selector([
            Sequence([
                Condition("weapons_free", lambda b: b.get("roe_posture") == "weapons_free"),
                Action("engage", lambda b: print("  → ENGAGING")),
            ]),
            Action("track_only", lambda b: print("  → TRACKING (weapons hold)")),
        ]),
    ]))

    print(f"Tree: {tree.name} ({tree.id})")
    result = tree.tick(bb)
    print(f"Result: {result.value}")
    print(json.dumps(tree.to_dict(), indent=2))
