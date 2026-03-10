# AMOS Data Contracts Reference

All data exchanged between plugins and the AMOS core uses these canonical types.
Import them from `amos_sdk.contracts` (or directly from `amos_sdk`).

## AssetPosition

Friendly asset telemetry — drones, UGVs, UUVs, personnel.

| Field       | Type          | Default     | Description                    |
|-------------|---------------|-------------|--------------------------------|
| asset_id    | str           | *required*  | Unique asset identifier        |
| lat         | float         | *required*  | WGS-84 latitude                |
| lon         | float         | *required*  | WGS-84 longitude               |
| alt         | float         | 0.0         | Altitude MSL (metres)          |
| heading     | float         | 0.0         | Heading in degrees (0–360)     |
| speed       | float         | 0.0         | Speed (m/s)                    |
| asset_type  | str           | "unknown"   | drone, ugv, uuv, personnel    |
| callsign    | str           | ""          | Human-readable callsign        |
| timestamp   | float         | time.time() | Unix epoch                     |
| metadata    | dict          | {}          | Arbitrary key-value pairs      |

## SensorReading

Normalised sensor reading from any adapter.

| Field       | Type          | Default     | Description                    |
|-------------|---------------|-------------|--------------------------------|
| sensor_id   | str           | *required*  | Unique sensor identifier       |
| sensor_type | str           | *required*  | adsb, ais, aprs, meshtastic…   |
| lat         | float \| None | None        | WGS-84 latitude (if available) |
| lon         | float \| None | None        | WGS-84 longitude               |
| alt         | float \| None | None        | Altitude MSL (metres)          |
| raw         | str           | ""          | Raw data string                |
| values      | dict          | {}          | Parsed key-value data          |
| timestamp   | float         | time.time() | Unix epoch                     |

## ThreatReport

Hostile or unknown track report.

| Field       | Type          | Default     | Description                    |
|-------------|---------------|-------------|--------------------------------|
| threat_id   | str           | *required*  | Unique threat identifier       |
| threat_type | str           | *required*  | hostile_uav, vessel, unknown…  |
| lat         | float         | *required*  | WGS-84 latitude                |
| lon         | float         | *required*  | WGS-84 longitude               |
| alt         | float         | 0.0         | Altitude MSL (metres)          |
| heading     | float         | 0.0         | Heading in degrees             |
| speed       | float         | 0.0         | Speed (m/s)                    |
| confidence  | float         | 0.0         | 0.0–1.0 confidence score      |
| source      | str           | ""          | Originating plugin/sensor      |
| timestamp   | float         | time.time() | Unix epoch                     |
| metadata    | dict          | {}          | Arbitrary key-value pairs      |

## MissionWaypoint

Single waypoint in a mission plan.

| Field          | Type          | Default     | Description                  |
|----------------|---------------|-------------|------------------------------|
| waypoint_id    | str           | *required*  | Unique waypoint identifier   |
| lat            | float         | *required*  | WGS-84 latitude              |
| lon            | float         | *required*  | WGS-84 longitude             |
| alt            | float         | 0.0         | Altitude MSL (metres)        |
| speed          | float \| None | None        | Target speed (m/s)           |
| action         | str           | "navigate"  | navigate, loiter, land, rtl  |
| loiter_seconds | int           | 0           | Time to loiter (seconds)     |
| radius_m       | float         | 0.0         | Loiter / acceptance radius   |
| metadata       | dict          | {}          | Arbitrary key-value pairs    |

## PluginManifest

Parsed representation of a `plugin.yaml` file.

| Field        | Type       | Default | Description                  |
|--------------|------------|---------|------------------------------|
| name         | str        | *req*   | Plugin identifier            |
| version      | str        | *req*   | Semver string                |
| plugin_type  | str        | *req*   | One of the 6 plugin types    |
| description  | str        | ""      | Human-readable description   |
| author       | str        | ""      | Author name or organisation  |
| license      | str        | "MIT"   | SPDX license identifier      |
| entry_point  | str        | ""      | module:ClassName format      |
| requires     | list[str]  | []      | Required integration bridges |
| capabilities | list[str]  | []      | Advertised capabilities      |
| config       | dict       | {}      | Default configuration        |

## Event Topics

Common event topics used across the platform:

| Topic                     | Payload Type   | Description                    |
|---------------------------|----------------|--------------------------------|
| `sensor.registered`       | dict           | Plugin announces itself        |
| `sensor.reading`          | SensorReading  | Normalised sensor data         |
| `sensor.vessel_position`  | dict           | AIS vessel position            |
| `sensor.mesh_position`    | dict           | Meshtastic node position       |
| `sensor.mesh_telemetry`   | dict           | Meshtastic node metrics        |
| `sensor.mesh_text`        | dict           | Meshtastic text message        |
| `asset.registered`        | dict           | Asset adapter announces itself |
| `asset.position_updated`  | AssetPosition  | Asset telemetry update         |
| `threat.detected`         | ThreatReport   | New threat detection           |
| `mission.waypoint_added`  | MissionWaypoint| New waypoint in plan           |
