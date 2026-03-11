"""AMOS Plugin — ZMeta ISR Metadata Adapter.

Bridges the ZMeta event-based ISR metadata standard into AMOS.  ZMeta
events arrive via UDP, are parsed by the bridge, and emitted as AMOS
EventBus events for consumption by sensor fusion, kill web, EW, SIGINT,
waypoint nav, and AAR subsystems.

Ingest events emitted:
  - ew.emitter_detected          (RF OBSERVATION — freq, power, bandwidth)
  - sensor.contact_detected      (EO/IR/ACOUSTIC OBSERVATION)
  - zmeta.inference              (INFERENCE — classification/anomaly claims)
  - zmeta.track_update           (FUSION — cross-sensor fused track)
  - zmeta.track_state            (STATE — operator-grade belief snapshot)
  - zmeta.link_status            (SYSTEM/LINK_STATUS — transport health)
  - zmeta.task_ack               (SYSTEM/TASK_ACK — command lifecycle)
  - zmeta.command_received       (COMMAND — inbound mission task)
  - zmeta.system_event           (SYSTEM — time/schema events)

Egress hooks:
  - zmeta.emit_state             (trigger STATE_EVENT emission)
  - zmeta.emit_command           (trigger COMMAND_EVENT emission)

See ``integrations/zmeta_bridge.py`` for the full bridge.
"""

import threading
import time

from core.plugin_base import PluginBase


class ZMetaAdapterPlugin(PluginBase):
    """ZMeta ISR metadata adapter plugin."""

    PLUGIN_NAME = "zmeta_adapter"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "isr_metadata_adapter"

    def __init__(self):
        super().__init__()
        self.bridge = None
        self._poll_thread = None
        self._running = False
        # Track buffer positions to avoid duplicate emissions
        self._last_obs = 0
        self._last_inf = 0
        self._last_fus = 0
        self._last_trk = 0
        self._last_cmd = 0
        self._last_lnk = 0
        self._last_ack = 0
        self._last_sys = 0

    def on_activate(self, event_bus) -> None:
        self.subscribe("zmeta.configure", self._on_configure)
        self.subscribe("zmeta.emit_state", self._on_emit_state)
        self.subscribe("zmeta.emit_command", self._on_emit_command)
        self.emit("sensor.registered", {
            "plugin": self.PLUGIN_NAME,
            "protocol": "zmeta_udp",
            "capabilities": self.get_capabilities(),
            "domains": ["air", "ground", "maritime", "space"],
        })
        # Auto-connect if config provided in manifest
        cfg = self.manifest.get("config", {})
        if cfg.get("listen_port"):
            self._init_bridge(cfg)

    def on_shutdown(self) -> None:
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=3)
        if self.bridge:
            self.bridge.disconnect()

    def get_capabilities(self) -> list[str]:
        return [
            "zmeta_ingest", "zmeta_egress", "observation_rf",
            "observation_eoir", "inference", "fusion_tracks",
            "track_state", "link_status", "task_ack",
            "command_emit", "state_emit", "health",
        ]

    # ── Bridge Init ────────────────────────────────────────

    def _init_bridge(self, cfg: dict):
        try:
            from integrations.zmeta_bridge import ZMetaBridge
            self.bridge = ZMetaBridge(
                listen_host=cfg.get("listen_host", "0.0.0.0"),
                listen_port=int(cfg.get("listen_port", 5555)),
                forward_host=cfg.get("forward_host", "127.0.0.1"),
                forward_port=int(cfg.get("forward_port", 5556)),
                profile=cfg.get("profile", "H"),
                platform_id=cfg.get("platform_id", "amos-gateway"),
            )
            ok = self.bridge.connect()
            if ok:
                self._start_poll()
                self.emit("zmeta.connected", {
                    "listen_addr": f"{self.bridge.listen_host}:{self.bridge.listen_port}",
                    "profile": self.bridge.profile,
                })
        except ImportError:
            pass

    # ── Polling Loop — bridge → AMOS events ────────────────

    def _start_poll(self):
        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True,
            name="zmeta-adapter-poll",
        )
        self._poll_thread.start()

    def _poll_loop(self):
        """Continuously poll the bridge for new data and emit AMOS events."""
        while self._running:
            if not self.bridge or not self.bridge.connected:
                time.sleep(2)
                continue

            # ── OBSERVATION → ew.emitter_detected / sensor.contact_detected
            obs = self.bridge.get_observations()
            for o in obs[self._last_obs:]:
                modality = o.get("modality", "")
                if modality == "RF":
                    self.emit("ew.emitter_detected", {
                        "source": "zmeta",
                        "platform_id": o.get("platform_id"),
                        "freq_hz": o.get("freq_hz"),
                        "power_dbm": o.get("power_dbm"),
                        "bandwidth_hz": o.get("bandwidth_hz"),
                        "signature_hash": o.get("signature_hash"),
                        "lat": o.get("lat"),
                        "lng": o.get("lng"),
                        "confidence": o.get("confidence"),
                        "timestamp": o.get("ts"),
                        "zmeta_event_id": o.get("event_id"),
                    })
                else:
                    self.emit("sensor.contact_detected", {
                        "source": f"zmeta_{modality.lower()}" if modality else "zmeta",
                        "platform_id": o.get("platform_id"),
                        "modality": modality,
                        "lat": o.get("lat"),
                        "lng": o.get("lng"),
                        "alt_ft": o.get("alt_ft"),
                        "confidence": o.get("confidence"),
                        "timestamp": o.get("ts"),
                        "zmeta_event_id": o.get("event_id"),
                    })
            self._last_obs = len(obs)

            # ── INFERENCE → zmeta.inference
            inf = self.bridge.get_inferences()
            for i in inf[self._last_inf:]:
                self.emit("zmeta.inference", {
                    "source": "zmeta",
                    "platform_id": i.get("platform_id"),
                    "inference_type": i.get("inference_type"),
                    "claim": i.get("claim"),
                    "model_name": i.get("model_name"),
                    "model_version": i.get("model_version"),
                    "confidence": i.get("confidence"),
                    "lineage": i.get("lineage"),
                    "timestamp": i.get("ts"),
                    "zmeta_event_id": i.get("event_id"),
                })
            self._last_inf = len(inf)

            # ── FUSION → zmeta.track_update
            fus = self.bridge.get_fusions()
            for f in fus[self._last_fus:]:
                self.emit("zmeta.track_update", {
                    "source": "zmeta",
                    "track_id": f.get("track_id"),
                    "lat": f.get("lat"),
                    "lng": f.get("lng"),
                    "alt_ft": f.get("alt_ft"),
                    "speed_kts": f.get("speed_kts"),
                    "heading_deg": f.get("heading_deg"),
                    "stability": f.get("stability"),
                    "confidence": f.get("confidence"),
                    "lineage": f.get("lineage"),
                    "timestamp": f.get("ts"),
                    "zmeta_event_id": f.get("event_id"),
                })
            self._last_fus = len(fus)

            # ── STATE → zmeta.track_state
            trk = self.bridge.get_track_states()
            for t in trk[self._last_trk:]:
                self.emit("zmeta.track_state", {
                    "source": "zmeta",
                    "track_id": t.get("track_id"),
                    "lat": t.get("lat"),
                    "lng": t.get("lng"),
                    "alt_ft": t.get("alt_ft"),
                    "speed_kts": t.get("speed_kts"),
                    "heading_deg": t.get("heading_deg"),
                    "confidence": t.get("confidence"),
                    "valid_for_ms": t.get("valid_for_ms"),
                    "timestamp": t.get("ts"),
                    "zmeta_event_id": t.get("event_id"),
                })
            self._last_trk = len(trk)

            # ── COMMAND → zmeta.command_received
            cmd = self.bridge.get_commands_in()
            for c in cmd[self._last_cmd:]:
                self.emit("zmeta.command_received", {
                    "source": "zmeta",
                    "task_id": c.get("task_id"),
                    "task_type": c.get("task_type"),
                    "target_lat": c.get("target_lat"),
                    "target_lng": c.get("target_lng"),
                    "valid_for_ms": c.get("valid_for_ms"),
                    "priority": c.get("priority"),
                    "timestamp": c.get("ts"),
                    "zmeta_event_id": c.get("event_id"),
                })
            self._last_cmd = len(cmd)

            # ── LINK_STATUS → zmeta.link_status
            lnk = self.bridge.get_link_status()
            for l in lnk[self._last_lnk:]:
                m = l.get("metrics", {})
                self.emit("zmeta.link_status", {
                    "source": "zmeta",
                    "platform_id": l.get("platform_id"),
                    "link_state": l.get("state"),
                    "link_id": m.get("link_id"),
                    "latency_ms": m.get("latency_ms"),
                    "packet_loss_pct": m.get("packet_loss_pct"),
                    "throughput_bps": m.get("throughput_bps"),
                    "reason_code": m.get("reason_code"),
                    "timestamp": l.get("ts"),
                    "zmeta_event_id": l.get("event_id"),
                })
            self._last_lnk = len(lnk)

            # ── TASK_ACK → zmeta.task_ack
            ack = self.bridge.get_task_acks()
            for a in ack[self._last_ack:]:
                m = a.get("metrics", {})
                self.emit("zmeta.task_ack", {
                    "source": "zmeta",
                    "task_id": m.get("task_id"),
                    "ack_state": a.get("state"),
                    "original_event_id": m.get("original_event_id"),
                    "reason_code": m.get("reason_code"),
                    "timestamp": a.get("ts"),
                    "zmeta_event_id": a.get("event_id"),
                })
            self._last_ack = len(ack)

            time.sleep(2.0)

    # ── Event Handlers ─────────────────────────────────────

    def _on_configure(self, event):
        """Handle runtime reconfiguration."""
        cfg = event.payload or {}
        if self.bridge:
            self.bridge.disconnect()
        self._init_bridge(cfg)

    def _on_emit_state(self, event):
        """Emit a ZMeta STATE_EVENT from AMOS data."""
        if not self.bridge or not self.bridge.connected:
            return
        p = event.payload or {}
        self.bridge.emit_track_state(
            track_id=p.get("track_id", ""),
            lat=p.get("lat", 0), lng=p.get("lng", 0),
            alt_m=p.get("alt_m", 0),
            heading_deg=p.get("heading_deg"),
            speed_mps=p.get("speed_mps"),
            confidence=p.get("confidence", 0.8),
            entity_class=p.get("entity_class"),
            valid_for_ms=p.get("valid_for_ms", 5000),
        )

    def _on_emit_command(self, event):
        """Emit a ZMeta COMMAND_EVENT from AMOS waypoint."""
        if not self.bridge or not self.bridge.connected:
            return
        p = event.payload or {}
        self.bridge.emit_command(
            task_type=p.get("task_type", "GOTO"),
            lat=p.get("lat", 0), lng=p.get("lng", 0),
            valid_for_ms=p.get("valid_for_ms", 600000),
            priority=p.get("priority", "MED"),
            geometry=p.get("geometry"),
        )

    # ── Health ─────────────────────────────────────────────

    def health_check(self) -> dict:
        base = super().health_check()
        if self.bridge:
            st = self.bridge.get_status()
            base["zmeta_connected"] = st["connected"]
            base["listen_addr"] = st["listen_addr"]
            base["forward_addr"] = st["forward_addr"]
            base["profile"] = st["profile"]
            base["stats"] = st["stats"]
            base["buffers"] = st["buffers"]
        else:
            base["zmeta_connected"] = False
        base["polling"] = self._running
        return base
