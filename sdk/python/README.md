# AMOS Plugin SDK

Build plugins for the **Autonomous Mission Orchestration System** (AMOS).

## Install

```bash
pip install amos-sdk          # from PyPI (when published)
pip install -e sdk/python     # from source (inside AMOS repo)
```

## Quick Start

```python
from amos_sdk import PluginBase, SensorReading

class MyPlugin(PluginBase):
    PLUGIN_NAME = "my_plugin"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "sensor_adapter"

    def on_activate(self, event_bus):
        self.subscribe("sensor.raw_data", self.handle)

    def handle(self, event):
        reading = SensorReading(
            sensor_id="my-sensor-001",
            sensor_type="custom",
            lat=event.payload.get("lat"),
            lon=event.payload.get("lon"),
        )
        self.emit("sensor.reading", reading.__dict__)
```

## Plugin Types

| Type             | Description                           |
|------------------|---------------------------------------|
| `asset_adapter`  | Bridges drones / UGVs / UUVs to AMOS |
| `sensor_adapter` | Ingests sensor feeds (ADS-B, AIS …)   |
| `mission_pack`   | Mission templates & waypoints         |
| `planner`        | Path / task planning algorithms       |
| `analytics`      | Post-mission or real-time analytics   |
| `transport`      | Custom comms layers (LoRa, HF …)     |

## Data Contracts

- `AssetPosition` — friendly asset telemetry
- `SensorReading` — normalised sensor data
- `ThreatReport`  — hostile / unknown track
- `MissionWaypoint` — single waypoint in a plan
- `PluginManifest` — parsed `plugin.yaml`

## Testing

```python
from amos_sdk.testing import PluginTestHarness

def test_my_plugin():
    h = PluginTestHarness(MyPlugin)
    h.activate()
    h.inject_event("sensor.raw_data", {"lat": 33.0, "lon": -117.0})
    assert h.has_event("sensor.reading")
    h.assert_healthy()
```

## Helpers

```python
from amos_sdk import haversine_m, bearing_deg, load_manifest, validate_manifest

dist = haversine_m(33.0, -117.0, 34.0, -118.0)  # metres
brg  = bearing_deg(33.0, -117.0, 34.0, -118.0)   # degrees

manifest = load_manifest("plugins/my_plugin")
errors   = validate_manifest(manifest)
```

## Scaffold a New Plugin

```bash
python tools/create_plugin.py my_plugin --type sensor_adapter
```

## License

MIT — see the top-level LICENSE file.
