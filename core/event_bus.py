"""AMOS EventBus — the platform nervous system.

Lightweight pub/sub event bus with topic-based routing.  All AMOS
components (core engines, plugins, adapters) communicate through
events rather than direct coupling.

Topics use dot-notation hierarchy::

    asset.updated
    threat.detected
    mission.created
    plugin.loaded
    plugin.error

Subscribers can use wildcards::

    asset.*      — all asset events
    *            — everything

Usage::

    bus = EventBus()
    bus.subscribe("threat.detected", my_handler)
    bus.publish("threat.detected", {"id": "T-01", "lat": 35.7})
"""

import time
import uuid
import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

log = logging.getLogger("amos.events")


class Event:
    """Immutable event record."""

    __slots__ = ("id", "topic", "payload", "timestamp", "source")

    def __init__(self, topic: str, payload: Any = None, source: str = ""):
        self.id = f"EVT-{uuid.uuid4().hex[:8]}"
        self.topic = topic
        self.payload = payload
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.source = source

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "source": self.source,
        }


class EventBus:
    """Topic-based pub/sub event bus.

    Parameters
    ----------
    history_size : int
        Max events retained in the ring buffer (default 2000).
    async_delivery : bool
        If True, handlers run in a daemon thread (default True).
        Set False for lifecycle events that need synchronous ordering.
    """

    def __init__(self, history_size: int = 2000, async_delivery: bool = True):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._history: list[dict] = []
        self._history_size = history_size
        self._async = async_delivery
        self._lock = threading.Lock()
        self._stats = {
            "published": 0,
            "delivered": 0,
            "errors": 0,
            "subscribers": 0,
        }

    # ── Publish ────────────────────────────────────────────
    def publish(self, topic: str, payload: Any = None,
                source: str = "") -> Event:
        """Publish an event to all matching subscribers.

        Returns the Event object for reference.
        """
        event = Event(topic, payload, source)

        # Store in history
        with self._lock:
            self._history.append(event.to_dict())
            if len(self._history) > self._history_size:
                self._history = self._history[-self._history_size:]
            self._stats["published"] += 1

        # Find matching handlers
        handlers = self._match(topic)

        if self._async and handlers:
            threading.Thread(
                target=self._deliver, args=(handlers, event),
                daemon=True, name=f"evt-{topic}"
            ).start()
        else:
            self._deliver(handlers, event)

        return event

    def publish_sync(self, topic: str, payload: Any = None,
                     source: str = "") -> Event:
        """Publish with synchronous delivery (blocks until all handlers run)."""
        event = Event(topic, payload, source)

        with self._lock:
            self._history.append(event.to_dict())
            if len(self._history) > self._history_size:
                self._history = self._history[-self._history_size:]
            self._stats["published"] += 1

        self._deliver(self._match(topic), event)
        return event

    # ── Subscribe ──────────────────────────────────────────
    def subscribe(self, topic: str, handler: Callable) -> None:
        """Subscribe a handler to a topic.

        ``topic`` may contain wildcards:
          - ``asset.*``  matches ``asset.updated``, ``asset.created``, etc.
          - ``*``        matches everything
        """
        with self._lock:
            self._subscribers[topic].append(handler)
            self._stats["subscribers"] = sum(
                len(v) for v in self._subscribers.values())

    def unsubscribe(self, topic: str, handler: Callable) -> bool:
        """Remove a handler. Returns True if found."""
        with self._lock:
            subs = self._subscribers.get(topic, [])
            if handler in subs:
                subs.remove(handler)
                self._stats["subscribers"] = sum(
                    len(v) for v in self._subscribers.values())
                return True
        return False

    # ── Query ──────────────────────────────────────────────
    def get_history(self, topic: str = None, limit: int = 50) -> list[dict]:
        """Return recent events, optionally filtered by topic prefix."""
        with self._lock:
            events = list(self._history)
        if topic:
            events = [e for e in events if e["topic"].startswith(topic)]
        return events[-limit:]

    def get_stats(self) -> dict:
        with self._lock:
            return dict(self._stats)

    def get_topics(self) -> list[str]:
        """Return all topics that have subscribers."""
        with self._lock:
            return sorted(self._subscribers.keys())

    # ── Internal ───────────────────────────────────────────
    def _match(self, topic: str) -> list[Callable]:
        """Find all handlers matching a topic (exact + wildcard)."""
        handlers = []
        with self._lock:
            for pattern, subs in self._subscribers.items():
                if pattern == "*":
                    handlers.extend(subs)
                elif pattern.endswith(".*"):
                    prefix = pattern[:-2]
                    if topic.startswith(prefix):
                        handlers.extend(subs)
                elif pattern == topic:
                    handlers.extend(subs)
        return handlers

    def _deliver(self, handlers: list[Callable], event: Event) -> None:
        """Invoke all handlers for an event."""
        for handler in handlers:
            try:
                handler(event)
                with self._lock:
                    self._stats["delivered"] += 1
            except Exception as exc:
                with self._lock:
                    self._stats["errors"] += 1
                log.error(f"Event handler error on '{event.topic}': {exc}")
