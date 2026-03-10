# AMOS Integration Patterns

How to write integration bridges and connect external protocols to AMOS.

## Architecture

```
External Protocol                AMOS Core
─────────────────    ┌─────────┐    ──────────
ADS-B (1090 MHz) ──▶│ Bridge  │──▶ Event Bus ──▶ Plugins
APRS-IS (TCP)    ──▶│  Layer  │──▶            ──▶
AIS (NMEA)       ──▶│         │──▶            ──▶
TAK (CoT XML)    ◀─▶│         │◀─▶            ◀─▶
Meshtastic (LoRa)◀─▶│         │◀─▶            ◀─▶
                     └─────────┘
```

### Layer Responsibilities

- **Bridge** (`integrations/`) — handles raw protocol I/O (sockets, serial, HTTP). No business logic.
- **Plugin** (`plugins/`) — processes data, emits typed events, provides health checks. Contains domain logic.

## Pattern: Read-Only Sensor Bridge

For protocols where AMOS only *receives* data (ADS-B, AIS, APRS):

```python
class MyBridge:
    def __init__(self, host="127.0.0.1", port=5000):
        self.host = host
        self.port = port
        self.connected = False
        self._socket = None

    def connect(self):
        import socket
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((self.host, self.port))
        self.connected = True

    def receive(self):
        """Blocking read — call from a background thread."""
        data = self._socket.recv(4096)
        return data.decode("ascii", errors="replace")

    def disconnect(self):
        if self._socket:
            self._socket.close()
        self.connected = False
```

## Pattern: Bidirectional Bridge

For protocols where AMOS both sends and receives (TAK/CoT, Meshtastic):

```python
class MyBidiBridge:
    def connect(self):
        # Establish two-way connection
        ...

    def receive(self):
        # Read incoming messages
        ...

    def send(self, message):
        # Send outgoing messages
        ...

    def send_assets(self, assets):
        """Push AMOS assets to external system."""
        for asset in assets:
            msg = self._encode(asset)
            self.send(msg)

    def send_threats(self, threats):
        """Push AMOS threats to external system."""
        ...
```

## Pattern: Plugin ↔ Bridge Wiring

The plugin creates and owns the bridge instance:

```python
class MySensorPlugin(PluginBase):
    def on_activate(self, event_bus):
        from integrations.my_bridge import MyBridge
        self.bridge = MyBridge()
        self.bridge.connect()
        self.subscribe("sensor.poll", self._poll)

    def _poll(self, event):
        raw = self.bridge.receive()
        processed = self._decode(raw)
        self.emit("sensor.reading", processed)

    def on_shutdown(self):
        self.bridge.disconnect()
```

### Key Practices

1. **Lazy import** bridges in `on_activate` — use `try/except ImportError` so the plugin can still load without optional dependencies.
2. **Own the connection** — the plugin creates, manages, and tears down the bridge.
3. **Background threads** for blocking I/O — never block the event bus.
4. **Graceful degradation** — if the bridge can't connect, set `self.bridge = None` and continue without it.

## Available Bridges

| Bridge                | Protocol        | Direction  | Module                       |
|-----------------------|-----------------|------------|------------------------------|
| TAK Bridge            | CoT XML / TCP   | Bidi       | `integrations.tak_bridge`    |
| ADS-B Receiver        | Beast / SBS-1   | Read       | `integrations.adsb_receiver` |
| APRS Bridge           | APRS-IS / TCP   | Read       | `integrations.aprs_bridge`   |
| AIS Receiver          | NMEA / TCP      | Read       | `integrations.ais_receiver`  |
| RemoteID Bridge       | BT/WiFi Beacon  | Read       | `integrations.remoteid_bridge` |
| LoRa Bridge           | Meshtastic      | Bidi       | `integrations.lora_bridge`   |
| NMEA Bridge           | GPS / Marine    | Read       | `integrations.nmea_bridge`   |
| PX4 Bridge            | MAVLink / UDP   | Bidi       | `integrations.px4_bridge`    |
| ROS 2 Bridge          | DDS / Topics    | Bidi       | `integrations.ros2_bridge`   |
| MAVLink Bridge        | MAVLink         | Bidi       | `integrations.mavlink_bridge`|

## Adding a New Bridge

1. Create `integrations/my_protocol_bridge.py`
2. Implement `connect()`, `disconnect()`, `receive()`, and optionally `send()`
3. Add a `connected` property for health checks
4. Create a corresponding plugin in `plugins/my_protocol_adapter/`
5. Wire the bridge to the event bus in the plugin's `on_activate`
6. Update `integrations/__init__.py` with the new bridge

## Error Handling

```python
def connect(self):
    try:
        self._socket.connect((self.host, self.port))
        self.connected = True
    except (ConnectionRefusedError, TimeoutError) as exc:
        log.warning("Bridge connection failed: %s", exc)
        self.connected = False
        # Plugin should handle bridge=None gracefully
```

Always log connection failures and allow the plugin to continue in degraded mode.
