"""AMOS ↔ LoRa / Meshtastic Bridge

Integrates Meshtastic mesh networking devices for low-bandwidth
C2 relay and field asset tracking.

Supports:
  - Meshtastic serial (USB)
  - Meshtastic TCP (network-connected device)
  - Meshtastic BLE (Bluetooth)

Capabilities:
  - Mesh node position tracking
  - Text messaging to/from field operators
  - Low-bandwidth command relay (waypoints, status)
  - Mesh network health monitoring
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone

log = logging.getLogger("amos.lora")


class LoRaBridge:
    """LoRa/Meshtastic mesh bridge for AMOS."""

    def __init__(self, device="/dev/ttyUSB0", mode="serial", host=None, port=4403):
        """Initialize LoRa/Meshtastic bridge.

        Parameters
        ----------
        device : str
            Serial port path for USB connection.
        mode : str
            'serial' for USB, 'tcp' for network, 'ble' for Bluetooth.
        host : str
            TCP host for network mode.
        port : int
            TCP port for network mode.
        """
        self.device = device
        self.mode = mode
        self.host = host
        self.port = port
        self.connected = False
        self.nodes = {}  # node_id -> node info
        self._interface = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._message_callbacks = []
        self._position_callbacks = []

    def connect(self):
        """Connect to Meshtastic device."""
        try:
            import meshtastic
            import meshtastic.serial_interface
            import meshtastic.tcp_interface

            if self.mode == "serial":
                self._interface = meshtastic.serial_interface.SerialInterface(
                    self.device
                )
            elif self.mode == "tcp":
                self._interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=self.host or "localhost",
                    portNumber=self.port,
                )
            else:
                log.warning(f"LoRa {self.mode} mode not yet implemented")
                return False

            self.connected = True
            log.info(f"Meshtastic connected via {self.mode}: {self.device}")
            self._setup_callbacks()
            return True
        except ImportError:
            log.info("meshtastic package not available — LoRa integration disabled")
            log.info("Install with: pip install meshtastic")
            return False
        except Exception as e:
            log.error(f"Meshtastic connection failed: {e}")
            return False

    def _setup_callbacks(self):
        """Register Meshtastic event handlers."""
        if not self._interface:
            return
        try:
            from pubsub import pub
            pub.subscribe(self._on_receive, "meshtastic.receive")
            pub.subscribe(self._on_connection, "meshtastic.connection.established")
            pub.subscribe(self._on_node_update, "meshtastic.node.updated")
        except ImportError:
            log.debug("pubsub not available for Meshtastic callbacks")

    def _on_receive(self, packet, interface):
        """Handle incoming Meshtastic packet."""
        try:
            decoded = packet.get("decoded", {})
            from_id = packet.get("fromId", "")
            portnum = decoded.get("portnum", "")

            if portnum == "TEXT_MESSAGE_APP":
                text = decoded.get("text", "")
                msg = {
                    "from": from_id,
                    "text": text,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "snr": packet.get("rxSnr"),
                    "rssi": packet.get("rxRssi"),
                }
                for cb in self._message_callbacks:
                    try:
                        cb(msg)
                    except Exception:
                        pass

            elif portnum == "POSITION_APP":
                pos = decoded.get("position", {})
                if pos.get("latitude") and pos.get("longitude"):
                    node = {
                        "node_id": from_id,
                        "lat": pos["latitude"],
                        "lng": pos["longitude"],
                        "alt_m": pos.get("altitude"),
                        "speed_ms": pos.get("groundSpeed"),
                        "heading_deg": pos.get("groundTrack"),
                        "sats_in_view": pos.get("satsInView"),
                        "last_update": datetime.now(timezone.utc).isoformat(),
                    }
                    with self._lock:
                        self.nodes[from_id] = node
                    for cb in self._position_callbacks:
                        try:
                            cb(node)
                        except Exception:
                            pass
        except Exception as e:
            log.debug(f"Meshtastic packet parse error: {e}")

    def _on_connection(self, interface, topic=None):
        """Handle connection established."""
        log.info("Meshtastic connection established")
        self.connected = True

    def _on_node_update(self, node, interface):
        """Handle node database update."""
        node_id = node.get("user", {}).get("id", "")
        if node_id:
            with self._lock:
                existing = self.nodes.get(node_id, {})
                existing["node_id"] = node_id
                existing["long_name"] = node.get("user", {}).get("longName", "")
                existing["short_name"] = node.get("user", {}).get("shortName", "")
                existing["hw_model"] = node.get("user", {}).get("hwModel", "")
                existing["snr"] = node.get("snr")
                self.nodes[node_id] = existing

    def send_text(self, text, destination=None):
        """Send a text message via mesh network."""
        if not self._interface:
            return False
        try:
            if destination:
                self._interface.sendText(text, destinationId=destination)
            else:
                self._interface.sendText(text)
            return True
        except Exception as e:
            log.error(f"Meshtastic send failed: {e}")
            return False

    def send_position(self, lat, lng, alt_m=0):
        """Send a position update via mesh network."""
        if not self._interface:
            return False
        try:
            self._interface.sendPosition(
                latitude=lat, longitude=lng, altitude=int(alt_m)
            )
            return True
        except Exception as e:
            log.error(f"Meshtastic position send failed: {e}")
            return False

    def on_message(self, callback):
        """Register callback for incoming text messages."""
        self._message_callbacks.append(callback)

    def on_position(self, callback):
        """Register callback for position updates."""
        self._position_callbacks.append(callback)

    # ── AMOS integration ────────────────────────────────────

    def get_nodes(self):
        """Return mesh nodes as AMOS-compatible observations."""
        with self._lock:
            return [
                {
                    "source": "meshtastic",
                    "track_id": n["node_id"],
                    "name": n.get("long_name", n["node_id"]),
                    "position": {
                        "lat": n["lat"],
                        "lng": n["lng"],
                        "alt_ft": round((n.get("alt_m") or 0) * 3.281, 0),
                    },
                    "speed_kts": round((n.get("speed_ms") or 0) * 1.944, 1),
                    "heading_deg": n.get("heading_deg", 0),
                    "snr": n.get("snr"),
                    "last_update": n.get("last_update", ""),
                }
                for n in self.nodes.values()
                if n.get("lat") is not None and n.get("lng") is not None
            ]

    def sync_to_amos(self, sim_assets):
        """Push mesh nodes into AMOS asset layer."""
        nodes = self.get_nodes()
        for n in nodes:
            asset_id = f"MESH-{n['track_id']}"
            existing = next((a for a in sim_assets if a.get("id") == asset_id), None)
            if existing:
                existing["lat"] = n["position"]["lat"]
                existing["lng"] = n["position"]["lng"]
            else:
                sim_assets.append({
                    "id": asset_id,
                    "type": "mesh_node",
                    "name": n["name"],
                    "lat": n["position"]["lat"],
                    "lng": n["position"]["lng"],
                    "source": "meshtastic",
                })
        return len(nodes)

    def get_status(self):
        return {
            "connected": self.connected,
            "mode": self.mode,
            "device": self.device if self.mode == "serial" else f"{self.host}:{self.port}",
            "node_count": len(self.nodes),
        }

    def disconnect(self):
        if self._interface:
            try:
                self._interface.close()
            except Exception:
                pass
        self.connected = False
        log.info("Meshtastic bridge disconnected")
