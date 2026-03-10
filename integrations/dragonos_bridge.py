"""AMOS ↔ DragonOS / WarDragon SDR Integration Bridge

Connects AMOS to DragonOS-based SDR sensor nodes (WarDragon Pro, Pi64,
or any DragonOS deployment).  A DragonOS node can be mounted on an air,
ground, or maritime asset and acts as a mobile SIGINT/EW sensor platform.

Data Ingest Channels:
  1. MQTT  — real-time drone detections, RemoteID decodes, RF events,
             spectrum alerts, system status
  2. Kismet REST API — WiFi / BT device observations, wireless landscape
  3. Spectrum — signal power, frequency, modulation classification
  4. Direction Finding — KrakenSDR DF-Aggregator bearing lines

Requires: paho-mqtt (pip install paho-mqtt), requests
"""

import json
import time
import logging
import threading
from datetime import datetime, timezone

log = logging.getLogger("amos.dragonos")


# ── Default MQTT Topics (WarDragon Pro standard) ───────────

DRAGON_TOPICS = {
    "drone_detections":  "wardragon/drone/#",
    "remoteid":          "wardragon/remoteid/#",
    "spectrum":          "wardragon/spectrum/#",
    "rf_events":         "wardragon/rf/#",
    "system_status":     "wardragon/status/#",
    "adsb":              "wardragon/adsb/#",
    "direction_finding": "wardragon/df/#",
    "alerts":            "wardragon/alerts/#",
}


class DragonOSBridge:
    """Bridge to DragonOS / WarDragon SDR sensor nodes."""

    def __init__(self, node_id="dragon-01",
                 mqtt_host="localhost", mqtt_port=1883,
                 mqtt_user="", mqtt_pass="",
                 kismet_url="", kismet_api_key="",
                 topic_prefix="wardragon"):
        self.node_id = node_id
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_pass = mqtt_pass
        self.kismet_url = kismet_url.rstrip("/") if kismet_url else ""
        self.kismet_api_key = kismet_api_key
        self.topic_prefix = topic_prefix

        self.connected = False
        self._mqtt_client = None
        self._running = False
        self._lock = threading.Lock()

        # Incoming data buffers
        self.drone_detections: list[dict] = []
        self.remoteid_decodes: list[dict] = []
        self.spectrum_events: list[dict] = []
        self.rf_events: list[dict] = []
        self.df_bearings: list[dict] = []
        self.kismet_devices: dict = {}
        self.node_status: dict = {}

        # Stats
        self.stats = {
            "mqtt_messages": 0,
            "drone_detections": 0,
            "remoteid_decodes": 0,
            "spectrum_events": 0,
            "df_bearings": 0,
            "kismet_devices": 0,
            "connected_at": None,
            "last_message_at": None,
        }

    # ── Connection ─────────────────────────────────────────

    def connect(self) -> bool:
        """Connect MQTT subscriber and start Kismet poller."""
        ok = self._connect_mqtt()
        if ok:
            self.connected = True
            self.stats["connected_at"] = time.time()
        if self.kismet_url:
            self._start_kismet_poller()
        return ok

    def disconnect(self):
        self._running = False
        if self._mqtt_client:
            try:
                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()
            except Exception:
                pass
        self.connected = False
        log.info(f"DragonOS [{self.node_id}] disconnected")

    # ── MQTT ───────────────────────────────────────────────

    def _connect_mqtt(self) -> bool:
        try:
            import paho.mqtt.client as mqtt
            self._mqtt_client = mqtt.Client(
                client_id=f"amos-dragon-{self.node_id}",
                protocol=mqtt.MQTTv311,
            )
            if self.mqtt_user:
                self._mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_pass)

            self._mqtt_client.on_connect = self._on_mqtt_connect
            self._mqtt_client.on_message = self._on_mqtt_message
            self._mqtt_client.on_disconnect = self._on_mqtt_disconnect

            self._mqtt_client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            self._mqtt_client.loop_start()
            self._running = True
            log.info(f"DragonOS [{self.node_id}] MQTT connected: "
                     f"{self.mqtt_host}:{self.mqtt_port}")
            return True
        except ImportError:
            log.warning("paho-mqtt not installed — run: pip install paho-mqtt")
            return False
        except Exception as e:
            log.error(f"DragonOS MQTT connect failed: {e}")
            return False

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            # Subscribe to all WarDragon topics
            for name, topic in DRAGON_TOPICS.items():
                actual = topic.replace("wardragon", self.topic_prefix)
                client.subscribe(actual, qos=1)
                log.debug(f"  subscribed: {actual}")
        else:
            log.error(f"DragonOS MQTT rc={rc}")

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {"raw": msg.payload.decode("utf-8", errors="ignore")}

        topic = msg.topic
        now = datetime.now(timezone.utc).isoformat()
        self.stats["mqtt_messages"] += 1
        self.stats["last_message_at"] = now

        with self._lock:
            entry = {"topic": topic, "payload": payload, "ts": now,
                     "node_id": self.node_id}

            if "/drone/" in topic:
                self.drone_detections.append(entry)
                self.stats["drone_detections"] += 1
                self._trim(self.drone_detections)
            elif "/remoteid/" in topic:
                self.remoteid_decodes.append(entry)
                self.stats["remoteid_decodes"] += 1
                self._trim(self.remoteid_decodes)
            elif "/spectrum/" in topic:
                self.spectrum_events.append(entry)
                self.stats["spectrum_events"] += 1
                self._trim(self.spectrum_events)
            elif "/df/" in topic:
                self.df_bearings.append(entry)
                self.stats["df_bearings"] += 1
                self._trim(self.df_bearings)
            elif "/rf/" in topic:
                self.rf_events.append(entry)
                self._trim(self.rf_events)
            elif "/status/" in topic:
                self.node_status = payload
            elif "/adsb/" in topic:
                # ADS-B data — route through existing ADS-B pipeline
                self.rf_events.append(entry)
                self._trim(self.rf_events)
            elif "/alerts/" in topic:
                self.rf_events.append(entry)
                self._trim(self.rf_events)

    def _on_mqtt_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            log.warning(f"DragonOS [{self.node_id}] unexpected disconnect (rc={rc})")

    # ── Kismet REST API ────────────────────────────────────

    def _start_kismet_poller(self):
        self._running = True
        t = threading.Thread(target=self._kismet_poll_loop, daemon=True,
                             name=f"dragon-kismet-{self.node_id}")
        t.start()

    def _kismet_poll_loop(self):
        """Poll Kismet REST API for wireless device observations."""
        while self._running:
            try:
                import requests
                headers = {}
                if self.kismet_api_key:
                    headers["KISMET"] = self.kismet_api_key

                resp = requests.get(
                    f"{self.kismet_url}/devices/last-time/-30/devices.json",
                    headers=headers, timeout=5,
                )
                if resp.ok:
                    devices = resp.json()
                    with self._lock:
                        for dev in devices:
                            key = dev.get("kismet.device.base.macaddr", "")
                            self.kismet_devices[key] = {
                                "mac": key,
                                "name": dev.get("kismet.device.base.name", ""),
                                "type": dev.get("kismet.device.base.type", ""),
                                "signal_dbm": dev.get("kismet.device.base.signal", {}).get(
                                    "kismet.common.signal.last_signal", 0),
                                "channel": dev.get("kismet.device.base.channel", ""),
                                "last_seen": dev.get("kismet.device.base.last_time", 0),
                                "packets": dev.get("kismet.device.base.packets.total", 0),
                                "lat": dev.get("kismet.device.base.location", {}).get(
                                    "kismet.common.location.avg_lat", 0),
                                "lng": dev.get("kismet.device.base.location", {}).get(
                                    "kismet.common.location.avg_lon", 0),
                                "manuf": dev.get("kismet.device.base.manuf", ""),
                            }
                        self.stats["kismet_devices"] = len(self.kismet_devices)
            except ImportError:
                log.debug("requests not installed — Kismet polling disabled")
                break
            except Exception as e:
                log.debug(f"Kismet poll error: {e}")
            time.sleep(10)

    # ── Public API ─────────────────────────────────────────

    def get_drone_detections(self, limit: int = 50) -> list[dict]:
        """Return recent drone/UAV detections from SDR analysis."""
        with self._lock:
            return list(self.drone_detections[-limit:])

    def get_remoteid_decodes(self, limit: int = 50) -> list[dict]:
        """Return recent RemoteID broadcast decodes."""
        with self._lock:
            return list(self.remoteid_decodes[-limit:])

    def get_spectrum_events(self, limit: int = 50) -> list[dict]:
        """Return recent spectrum/signal detection events."""
        with self._lock:
            return list(self.spectrum_events[-limit:])

    def get_df_bearings(self, limit: int = 50) -> list[dict]:
        """Return recent direction-finding bearing lines."""
        with self._lock:
            return list(self.df_bearings[-limit:])

    def get_kismet_devices(self) -> dict:
        """Return current wireless device observations from Kismet."""
        with self._lock:
            return dict(self.kismet_devices)

    def get_rf_events(self, limit: int = 100) -> list[dict]:
        """Return all RF events (ADS-B, alerts, misc)."""
        with self._lock:
            return list(self.rf_events[-limit:])

    def get_status(self) -> dict:
        return {
            "node_id": self.node_id,
            "connected": self.connected,
            "mqtt_broker": f"{self.mqtt_host}:{self.mqtt_port}",
            "kismet_url": self.kismet_url or "disabled",
            "node_health": self.node_status,
            "stats": dict(self.stats),
            "buffers": {
                "drone_detections": len(self.drone_detections),
                "remoteid_decodes": len(self.remoteid_decodes),
                "spectrum_events": len(self.spectrum_events),
                "df_bearings": len(self.df_bearings),
                "kismet_devices": len(self.kismet_devices),
                "rf_events": len(self.rf_events),
            },
        }

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _trim(buf: list, max_size: int = 500):
        if len(buf) > max_size:
            del buf[:-max_size]
