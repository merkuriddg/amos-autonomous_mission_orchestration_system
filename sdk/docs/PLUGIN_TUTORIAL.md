# Building Your First AMOS Plugin

This tutorial walks you through creating a sensor adapter plugin from scratch.

## Prerequisites

- Python 3.10+
- AMOS repository cloned
- Basic understanding of the AMOS event bus

## Step 1 — Scaffold

Use the built-in scaffolding tool:

```bash
python tools/create_plugin.py my_sensor --type sensor_adapter
```

This creates:
```
plugins/my_sensor/
├── __init__.py       # Plugin class with lifecycle hooks
└── plugin.yaml       # Manifest (name, version, type, config)
```

## Step 2 — Edit the Manifest

Open `plugins/my_sensor/plugin.yaml`:

```yaml
name: my_sensor
version: "1.0"
type: sensor_adapter
description: "My custom sensor feed"
author: Your Name
license: MIT
entry_point: __init__:MySensorPlugin
capabilities:
  - custom_feed
  - health
config:
  host: "127.0.0.1"
  port: 5000
```

### Required Fields

- **name** — unique plugin identifier (snake_case)
- **version** — semver string
- **type** — one of: `asset_adapter`, `sensor_adapter`, `mission_pack`, `planner`, `analytics`, `transport`
- **entry_point** — `module:ClassName` format

## Step 3 — Implement the Plugin Class

```python
from core.plugin_base import PluginBase

class MySensorPlugin(PluginBase):
    PLUGIN_NAME = "my_sensor"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "sensor_adapter"

    def __init__(self):
        super().__init__()
        self.connection = None

    def on_activate(self, event_bus):
        # Subscribe to events you care about
        self.subscribe("sensor.raw_data", self._on_raw_data)

        # Announce yourself
        self.emit("sensor.registered", {
            "plugin": self.PLUGIN_NAME,
            "protocol": "custom",
        })

    def on_shutdown(self):
        if self.connection:
            self.connection.close()

    def get_capabilities(self):
        return ["custom_feed", "health"]

    def _on_raw_data(self, event):
        # Process incoming data
        processed = self._process(event.payload)
        self.emit("sensor.reading", processed)

    def _process(self, raw):
        return {"source": "my_sensor", "data": raw}

    def health_check(self):
        base = super().health_check()
        base["connected"] = self.connection is not None
        return base
```

## Step 4 — Plugin Lifecycle

AMOS calls your plugin methods in this order:

```
on_load()       →  Validate config, check dependencies
on_register()   →  Register capabilities with the platform
on_activate()   →  Start operating — subscribe to events
  ... (plugin runs) ...
on_shutdown()   →  Clean up connections and resources
```

### Key Rules

1. **on_activate** is the only required method (abstract in PluginBase)
2. **Never block** in lifecycle hooks — use async or background threads
3. **Always clean up** in on_shutdown (close sockets, stop threads)
4. **Use emit/subscribe** for all communication — never import other plugins directly

## Step 5 — Use SDK Data Contracts

Import typed dataclasses to ensure event compatibility:

```python
from amos_sdk import SensorReading, AssetPosition, ThreatReport

reading = SensorReading(
    sensor_id="my-sensor-001",
    sensor_type="custom",
    lat=33.123,
    lon=-117.456,
    values={"temperature": 42.5},
)

# Emit as dict for the event bus
self.emit("sensor.reading", reading.__dict__)
```

## Step 6 — Write Tests

```python
from amos_sdk.testing import PluginTestHarness
from plugins.my_sensor import MySensorPlugin

def test_lifecycle():
    h = PluginTestHarness(MySensorPlugin)
    h.activate()
    h.assert_healthy()
    h.assert_capabilities("custom_feed", "health")

def test_event_processing():
    h = PluginTestHarness(MySensorPlugin)
    h.activate()
    h.inject_event("sensor.raw_data", {"value": 42})
    assert h.has_event("sensor.reading")

def test_shutdown():
    h = PluginTestHarness(MySensorPlugin)
    h.activate()
    h.shutdown()
    # Verify resources released
```

Run tests:

```bash
python -m pytest tests/ -v -k "my_sensor"
```

## Step 7 — Validate Your Manifest

```python
from amos_sdk import load_manifest, validate_manifest

manifest = load_manifest("plugins/my_sensor")
errors = validate_manifest(manifest)
if errors:
    print("Manifest errors:", errors)
else:
    print("Manifest valid!")
```

## Next Steps

- See [CONTRACTS.md](CONTRACTS.md) for the full data contract reference
- See [INTEGRATION_PATTERNS.md](INTEGRATION_PATTERNS.md) for bridge patterns
- Browse `plugins/example_sensor/` and `plugins/example_mission_pack/` for reference implementations
- Check `integrations/` for available protocol bridges
