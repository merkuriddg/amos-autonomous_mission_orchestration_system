# DragonOS / WarDragon SDR Integration

AMOS integrates with **DragonOS**-based SDR sensor nodes (WarDragon Pro,
Raspberry Pi with DragonOS Pi64, or any DragonOS deployment) to provide
real-time drone detection, spectrum monitoring, direction finding, and
wireless device tracking.

## Concept of Operations

Each DragonOS node is registered as a **sensor asset** in AMOS. Mount a
WarDragon on a UGV, drone, boat, or fixed position — AMOS ingests its
sensor output and feeds detections into the common operating picture.

```
DragonOS Node (air/ground/sea)
    ├── MQTT → wardragon/drone/#        → AMOS threat.detected
    ├── MQTT → wardragon/remoteid/#     → AMOS sensor.contact_detected
    ├── MQTT → wardragon/spectrum/#     → AMOS ew.emitter_detected
    ├── MQTT → wardragon/df/#           → AMOS sensor.bearing_fix
    ├── MQTT → wardragon/status/#       → AMOS dragonos.node_status
    └── Kismet REST API                 → AMOS sigint.device_observed
```

## Hardware

- **WarDragon Pro** — headless SDR platform with ANTSDR E200 (70 MHz–6 GHz),
  drone detection, RemoteID decode, Kismet wireless, optional KrakenSDR DF
- **Raspberry Pi + DragonOS Pi64** — RTL-SDR or HackRF + DragonOS image
- **Any x86 box running DragonOS Focal/Noble** + any supported SDR

## Prerequisites

1. DragonOS node running with MQTT broker enabled (Mosquitto is pre-installed)
2. Network connectivity between AMOS and the DragonOS node (WiFi, Ethernet, or mesh)
3. Optional: Kismet running on the DragonOS node (default port 2501)

## Setup Steps

### 1. Enable MQTT on DragonOS

Mosquitto is included in DragonOS. Ensure it's running:

```bash
# On the DragonOS node
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

### 2. Configure DragonOS to Publish

The WarDragon Pro publishes to `wardragon/#` topics by default. For custom
DragonOS setups, configure your SDR tools to publish to MQTT:

```bash
# Example: dump1090 ADS-B → MQTT
dump1090 --net --quiet | mosquitto_pub -t wardragon/adsb/aircraft -l

# Example: RemoteID → MQTT (via DragonOS built-in)
# Already configured on WarDragon Pro
```

### 3. Connect from AMOS UI

1. Open AMOS → **Integrations** page
2. Find the **DragonOS** card under Sensor Bridges
3. Enter the MQTT broker host/port of your DragonOS node
4. Optionally enter the Kismet URL (e.g., `http://192.168.1.50:2501`)
5. Click **CONNECT**

### 4. Connect via API

```bash
curl -X POST http://localhost:2600/api/v1/bridge/dragonos/connect \
  -H "Content-Type: application/json" \
  -d '{
    "mqtt_host": "192.168.1.50",
    "mqtt_port": 1883,
    "kismet_url": "http://192.168.1.50:2501",
    "node_id": "dragon-ugv-01"
  }'
```

### 5. Connect via Plugin Config

Edit `plugins/dragonos_adapter/plugin.yaml`:

```yaml
config:
  node_id: "dragon-ugv-01"
  mqtt_host: "192.168.1.50"
  mqtt_port: 1883
  kismet_url: "http://192.168.1.50:2501"
  topic_prefix: "wardragon"
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/bridge/dragonos/status` | Node status + buffer counts |
| `POST /api/v1/bridge/dragonos/connect` | Connect to DragonOS MQTT |
| `POST /api/v1/bridge/dragonos/disconnect` | Disconnect |
| `GET /api/v1/bridge/dragonos/drones` | Drone/UAV detections |
| `GET /api/v1/bridge/dragonos/remoteid` | RemoteID decodes |
| `GET /api/v1/bridge/dragonos/spectrum` | Spectrum/signal events |
| `GET /api/v1/bridge/dragonos/df` | Direction-finding bearings |
| `GET /api/v1/bridge/dragonos/kismet` | Kismet wireless devices |

## MQTT Topic Map

| DragonOS Topic | AMOS Event | Description |
|----------------|------------|-------------|
| `wardragon/drone/#` | `threat.detected` | SDR-based drone detection |
| `wardragon/remoteid/#` | `sensor.contact_detected` | FAA RemoteID broadcasts |
| `wardragon/spectrum/#` | `ew.emitter_detected` | Signal detections |
| `wardragon/df/#` | `sensor.bearing_fix` | KrakenSDR DF bearings |
| `wardragon/rf/#` | RF event buffer | General RF events |
| `wardragon/adsb/#` | RF event buffer | ADS-B via DragonOS |
| `wardragon/status/#` | `dragonos.node_status` | Node health/heartbeat |
| `wardragon/alerts/#` | RF event buffer | Alert conditions |

## Deployment Examples

**Fixed Sensor Post:** WarDragon Pro on a mast with omnidirectional antenna.
Covers a 360° perimeter with drone detection and spectrum monitoring.

**Mobile Ground Asset:** Raspberry Pi + RTL-SDR + DragonOS Pi64 mounted on a
UGV. Registers as a mobile SIGINT sensor in AMOS.

**Airborne Platform:** WarDragon on a drone payload. ADS-B + RemoteID in flight,
feeding detections back to AMOS via mesh radio or LTE.

**Maritime:** WarDragon on a USV. AIS + spectrum monitoring + drone detection
while at sea, backhaul via SATCOM or mesh.

## Troubleshooting

- **MQTT connection refused:** Ensure Mosquitto is running on the DragonOS node
  and the firewall allows port 1883
- **No data flowing:** Verify topics with `mosquitto_sub -h <host> -t wardragon/#`
- **Kismet not responding:** Check Kismet is running (`sudo kismet`) and the API
  key is correct (see `/root/.kismet/kismet_httpd.conf`)
