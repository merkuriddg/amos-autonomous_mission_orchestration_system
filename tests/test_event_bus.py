"""EventBus tests — subscribe, publish, wildcard matching, history, stats."""

from core.event_bus import EventBus, Event


def test_event_creation():
    """Event objects have required fields."""
    e = Event("test.topic", {"key": "val"}, source="test")
    assert e.topic == "test.topic"
    assert e.payload == {"key": "val"}
    assert e.source == "test"
    assert e.id.startswith("EVT-")
    assert e.timestamp


def test_event_to_dict():
    """Event.to_dict() returns a serializable dict."""
    e = Event("test.topic", {"x": 1})
    d = e.to_dict()
    assert d["topic"] == "test.topic"
    assert d["payload"] == {"x": 1}
    assert "id" in d
    assert "timestamp" in d


def test_publish_sync():
    """publish_sync() delivers to matching handlers."""
    bus = EventBus(async_delivery=False)
    received = []
    bus.subscribe("test.event", lambda e: received.append(e.payload))
    bus.publish_sync("test.event", {"msg": "hello"})
    assert len(received) == 1
    assert received[0]["msg"] == "hello"


def test_exact_match():
    """Exact topic match works."""
    bus = EventBus(async_delivery=False)
    results = []
    bus.subscribe("asset.updated", lambda e: results.append(1))
    bus.publish_sync("asset.updated")
    bus.publish_sync("asset.created")  # should NOT match
    assert len(results) == 1


def test_wildcard_match():
    """Wildcard 'asset.*' matches all asset events."""
    bus = EventBus(async_delivery=False)
    results = []
    bus.subscribe("asset.*", lambda e: results.append(e.topic))
    bus.publish_sync("asset.updated")
    bus.publish_sync("asset.created")
    bus.publish_sync("threat.detected")  # should NOT match
    assert len(results) == 2
    assert "asset.updated" in results
    assert "asset.created" in results


def test_global_wildcard():
    """Wildcard '*' matches everything."""
    bus = EventBus(async_delivery=False)
    results = []
    bus.subscribe("*", lambda e: results.append(1))
    bus.publish_sync("asset.updated")
    bus.publish_sync("threat.detected")
    bus.publish_sync("plugin.loaded")
    assert len(results) == 3


def test_unsubscribe():
    """unsubscribe() removes handler."""
    bus = EventBus(async_delivery=False)
    results = []
    handler = lambda e: results.append(1)
    bus.subscribe("test.event", handler)
    bus.publish_sync("test.event")
    assert len(results) == 1

    removed = bus.unsubscribe("test.event", handler)
    assert removed is True
    bus.publish_sync("test.event")
    assert len(results) == 1  # no new delivery


def test_unsubscribe_nonexistent():
    """unsubscribe() returns False for unknown handler."""
    bus = EventBus(async_delivery=False)
    result = bus.unsubscribe("fake.topic", lambda e: None)
    assert result is False


def test_history():
    """get_history() returns recent events."""
    bus = EventBus(async_delivery=False, history_size=10)
    for i in range(5):
        bus.publish_sync(f"test.event.{i}", {"i": i})
    history = bus.get_history()
    assert len(history) == 5


def test_history_topic_filter():
    """get_history(topic) filters by prefix."""
    bus = EventBus(async_delivery=False)
    bus.publish_sync("asset.updated", {"id": "A1"})
    bus.publish_sync("threat.detected", {"id": "T1"})
    bus.publish_sync("asset.created", {"id": "A2"})
    asset_history = bus.get_history(topic="asset")
    assert len(asset_history) == 2


def test_history_size_limit():
    """History ring buffer respects size limit."""
    bus = EventBus(async_delivery=False, history_size=5)
    for i in range(10):
        bus.publish_sync("test.event", {"i": i})
    history = bus.get_history()
    assert len(history) == 5


def test_stats():
    """get_stats() tracks published/delivered/errors."""
    bus = EventBus(async_delivery=False)
    bus.subscribe("ok", lambda e: None)
    bus.subscribe("fail", lambda e: 1 / 0)  # will raise
    bus.publish_sync("ok")
    bus.publish_sync("fail")
    stats = bus.get_stats()
    assert stats["published"] == 2
    assert stats["delivered"] >= 1
    assert stats["errors"] >= 1
    assert stats["subscribers"] == 2


def test_get_topics():
    """get_topics() returns subscribed topics."""
    bus = EventBus(async_delivery=False)
    bus.subscribe("alpha", lambda e: None)
    bus.subscribe("beta", lambda e: None)
    topics = bus.get_topics()
    assert "alpha" in topics
    assert "beta" in topics


def test_handler_error_does_not_crash():
    """A failing handler doesn't crash other handlers."""
    bus = EventBus(async_delivery=False)
    results = []
    bus.subscribe("test", lambda e: 1 / 0)  # fails
    bus.subscribe("test", lambda e: results.append("ok"))
    bus.publish_sync("test")
    assert "ok" in results
