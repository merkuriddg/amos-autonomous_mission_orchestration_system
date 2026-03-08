# AMOS Integration Guide

How to connect AMOS to real hardware and external systems.

## PX4 / ArduPilot (Drones & Rovers)

```python
from integrations.px4_bridge import PX4Bridge

bridge = PX4Bridge("udp:127.0.0.1:14540")
bridge.connect()
bridge.register_vehicle("GHOST-1", system_id=1)
bridge.send_waypoint("GHOST-1", 27.85, -82.52, alt_m=50)
bridge.sync_to_amos(sim_assets)  # pushes real telemetry into AMOS
```

**Requirements:** `pip install pymavlink`
**Supported:** PX4 SITL, Pixhawk hardware, ArduCopter/Plane/Rover/Sub

## TAK (ATAK / WinTAK)

```python
from integrations.tak_bridge import TAKBridge

tak = TAKBridge(host="239.2.3.1", port=6969, protocol="udp")
tak.connect()
tak.send_assets(sim_assets)    # push blue force as CoT
tak.send_threats(sim_threats)  # push threats as hostile CoT
```

**Protocols:** UDP multicast (SA), TCP (TAK Server), TLS (secure)

## ROS 2 (Full Integration)

```python
from integrations.ros2_integration import ROS2Integration

ros2 = ROS2Integration(node_name="amos_bridge")
ros2.init()
ros2.publish_assets(sim_assets)
ros2.publish_threats(sim_threats)
ros2.sync_to_amos(sim_assets)
```

**Requirements:** Ubuntu 22.04 + ROS 2 Humble
**Topics:** `/amos/assets`, `/amos/threats`, `/amos/commands`, `/amos/telemetry`

## Nav2 (Ground UGV Navigation)

```python
from integrations.nav2_bridge import Nav2Bridge

nav2 = Nav2Bridge()
nav2.init()
nav2.send_goal("TALON-1", lat=27.85, lng=-82.52)
```

**Requirements:** ROS 2 + Nav2 stack

## MOOS-IvP (Marine Vehicles)

```python
from integrations.moos_bridge import MOOSBridge

moos = MOOSBridge(moos_host="localhost", moos_port=9000)
moos.connect()
moos.register_vehicle("TRITON-1", lat_origin=27.849, lng_origin=-82.521)
moos.send_waypoint("TRITON-1", 27.85, -82.53, speed_kts=10)
```

**Requirements:** `pip install pymoos` or MOOS-IvP installation

## SDR (SIGINT/EW Hardware)

```python
from integrations.sdr_bridge import SDRBridge

sdr = SDRBridge(device_args="hackrf=0", sample_rate=2e6)
sdr.connect()
detections = sdr.scan_band(400e6, 500e6, step=100000)
```

**Supported hardware:** HackRF One, RTL-SDR, USRP, LimeSDR
**Requirements:** GNU Radio + gr-osmosdr

## Link-16 (Tactical Data Link)

```python
from integrations.link16_sim import Link16Network

l16 = Link16Network(net_id="AMOS-NET-1")
l16.join("GHOST-1", track_number="TN-0001", role="PARTICIPANT")
l16.broadcast_all_assets(sim_assets)
picture = l16.get_tactical_picture()
```

**Messages:** J2.2 (air track), J3.2 (surface track), J7.0 (command)

## General Pattern

All bridges follow the same pattern:
1. **Instantiate** with connection parameters
2. **Connect** to the hardware/network
3. **Register** AMOS assets to hardware IDs
4. **Send** commands (waypoints, modes, etc.)
5. **Sync** real telemetry back into `sim_assets` via `sync_to_amos()`
