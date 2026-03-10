"""AMOS SDK Testing — harness and helpers for plugin unit tests.

Usage::

    from amos_sdk.testing import PluginTestHarness

    def test_my_plugin():
        harness = PluginTestHarness(MyPlugin)
        harness.activate()
        harness.inject_event("sensor.raw_nmea", {"sentence": "!AIVDM,..."})
        assert harness.has_event("sensor.vessel_position")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


# ── Mock Event Bus ─────────────────────────────────────────

@dataclass
class MockEvent:
    """Lightweight event for testing."""
    topic: str
    payload: Any = None
    source: str = ""
    timestamp: float = field(default_factory=time.time)


class MockEventBus:
    """In-memory event bus that records all published events."""

    def __init__(self):
        self.events: list[MockEvent] = []
        self._subscribers: dict[str, list[Callable]] = {}

    def publish(self, topic: str, payload=None, source: str = "") -> None:
        event = MockEvent(topic=topic, payload=payload, source=source)
        self.events.append(event)
        for handler in self._subscribers.get(topic, []):
            handler(event)

    def subscribe(self, topic: str, handler: Callable) -> None:
        self._subscribers.setdefault(topic, []).append(handler)

    def get_events(self, topic: str | None = None) -> list[MockEvent]:
        if topic is None:
            return list(self.events)
        return [e for e in self.events if e.topic == topic]

    def clear(self) -> None:
        self.events.clear()
        self._subscribers.clear()


# ── Plugin Test Harness ────────────────────────────────────

class PluginTestHarness:
    """Convenience wrapper for testing an AMOS plugin in isolation.

    Parameters
    ----------
    plugin_class : type
        The plugin class to instantiate and test.
    config : dict, optional
        Config dict to inject into the plugin manifest.
    """

    def __init__(self, plugin_class: type, config: dict | None = None):
        self.bus = MockEventBus()
        self.registry: dict = {}
        self.plugin = plugin_class()
        self.plugin.event_bus = self.bus
        if config:
            self.plugin.manifest["config"] = config

    # ── Lifecycle shortcuts ────────────────────────────────

    def load(self) -> None:
        """Run on_load lifecycle hook."""
        self.plugin.on_load()

    def register(self) -> dict:
        """Run on_register and return the registry."""
        self.plugin.on_register(self.registry)
        return self.registry

    def activate(self) -> None:
        """Run full lifecycle: load → register → activate."""
        self.load()
        self.register()
        self.plugin.on_activate(self.bus)

    def shutdown(self) -> None:
        """Run on_shutdown lifecycle hook."""
        self.plugin.on_shutdown()

    # ── Event helpers ──────────────────────────────────────

    def inject_event(self, topic: str, payload: Any = None, source: str = "test") -> None:
        """Publish an event on the mock bus (simulates external input)."""
        self.bus.publish(topic, payload, source=source)

    def has_event(self, topic: str) -> bool:
        """Return True if at least one event with the given topic was published."""
        return len(self.bus.get_events(topic)) > 0

    def get_events(self, topic: str | None = None) -> list[MockEvent]:
        """Return events, optionally filtered by topic."""
        return self.bus.get_events(topic)

    def last_event(self, topic: str) -> MockEvent | None:
        """Return the most recent event for a topic, or None."""
        events = self.bus.get_events(topic)
        return events[-1] if events else None

    # ── Assertions ─────────────────────────────────────────

    def assert_event_count(self, topic: str, expected: int) -> None:
        """Assert that exactly ``expected`` events were published for a topic."""
        actual = len(self.bus.get_events(topic))
        assert actual == expected, f"Expected {expected} '{topic}' events, got {actual}"

    def assert_healthy(self) -> None:
        """Assert that the plugin reports healthy."""
        health = self.plugin.health_check()
        assert health.get("healthy"), f"Plugin not healthy: {health}"

    def assert_capabilities(self, *expected: str) -> None:
        """Assert the plugin advertises the given capabilities."""
        caps = set(self.plugin.get_capabilities())
        missing = set(expected) - caps
        assert not missing, f"Missing capabilities: {missing}"
