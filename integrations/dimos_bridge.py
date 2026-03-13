#!/usr/bin/env python3
"""AMOS B4.1 — DimOS Bridge Adapter

Command and telemetry interface for bipedal humanoid robots via DimOS.
Maps CQB task commands to DimOS navigation / manipulation primitives,
and ingests telemetry (position, posture, perception, health) back into
AMOS asset state.

Follows the ProtocolAdapter pattern (see core/adapter_base.py).  Falls
back to standalone simulation mode when DimOS is unavailable.

DimOS command types mapped:
  NAVIGATE    — move to room/waypoint via indoor nav
  BREACH      — door-opening manipulation sequence
  SCAN        — room perception sweep
  HOLD        — stop and maintain position
  POSTURE     — change bipedal posture (stand, crouch, prone)
  MANIPULATE  — interact with an object (door handle, switch, etc.)
"""

import json
import time
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.adapter_base import ProtocolAdapter
from core.data_model import Track, Detection, Command, SensorReading, Message

log = logging.getLogger("amos.dimos")

# DimOS command vocabulary
DIMOS_COMMANDS = (
    "NAVIGATE", "BREACH", "SCAN", "HOLD",
    "POSTURE", "MANIPULATE", "EXTRACT", "STACK",
)

# DimOS telemetry topics
DIMOS_TELEMETRY_TOPICS = (
    "position", "posture", "perception", "health",
    "battery", "joint_state", "obstacle", "contact",
)


class DimOSBridge(ProtocolAdapter):
    """DimOS integration adapter for bipedal robot command & telemetry."""

    def __init__(self, host: str = "localhost", port: int = 9090):
        super().__init__(
            adapter_id="dimos", protocol="DimOS",
            description="DimOS bipedal robot command & telemetry bridge")
        self.host = host
        self.port = port
        self._standalone = False
        self._ws = None  # websocket connection (when real DimOS available)
        self._inbox: List[dict] = []
        self._outbox: List[dict] = []
        self._inbox_lock = threading.Lock()
        self._outbox_lock = threading.Lock()
        self._telemetry_cache: Dict[str, dict] = {}  # {asset_id: latest_telem}
        self._command_log: List[dict] = []

    def connect(self, **kwargs) -> bool:
        """Connect to DimOS server. Falls back to standalone if unavailable."""
        host = kwargs.get("host", self.host)
        port = kwargs.get("port", self.port)
        try:
            # Attempt real DimOS connection via websocket
            import websocket
            url = f"ws://{host}:{port}/dimos"
            self._ws = websocket.create_connection(url, timeout=5)
            self.connected = True
            self._standalone = False
            self.stats["connected_at"] = time.time()
            log.info(f"DimOS connected: {url}")
            return True
        except Exception:
            # Standalone simulation mode
            self.connected = True
            self._standalone = True
            self.stats["connected_at"] = time.time()
            log.info("DimOS running in standalone mode (no real robot connection)")
            return True

    def disconnect(self) -> bool:
        """Disconnect from DimOS."""
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        self.connected = False
        log.info("DimOS disconnected")
        return True

    def ingest(self) -> list:
        """Read pending telemetry from DimOS as canonical objects."""
        items = []
        with self._inbox_lock:
            raw = list(self._inbox)
            self._inbox.clear()

        for sample in raw:
            topic = sample.get("topic", "")
            data = sample.get("data", {})
            asset_id = data.get("asset_id", "")
            try:
                if topic == "position":
                    # Indoor position telemetry → Track
                    items.append(Track(
                        id=f"DIMOS-{asset_id}",
                        lat=data.get("lat", 0),
                        lng=data.get("lng", 0),
                        alt_m=data.get("alt_m", data.get("alt_ft", 0) * 0.3048),
                        domain="ground",
                        affiliation="FRIENDLY",
                        sources=[self.adapter_id],
                    ))
                elif topic == "perception":
                    # Perception detections
                    det_data = {k: v for k, v in data.items()
                                if k in {f.name for f in Detection.__dataclass_fields__.values()}}
                    det_data["adapter_id"] = self.adapter_id
                    items.append(Detection(**det_data))
                elif topic in ("health", "battery", "joint_state"):
                    raw_val = data.get("value", 0)
                    items.append(SensorReading(
                        sensor_id=f"DIMOS-{asset_id}-{topic}",
                        sensor_type="dimos",
                        reading_type=topic,
                        value=float(raw_val) if isinstance(raw_val, (int, float)) else 0.0,
                        unit=data.get("unit", ""),
                        adapter_id=self.adapter_id,
                        metadata=data if isinstance(raw_val, dict) else {},
                    ))
                else:
                    items.append(Message(
                        message_type="FREE_TEXT",
                        originator=self.adapter_id,
                        body=json.dumps(data, default=str),
                        protocol="DimOS",
                        adapter_id=self.adapter_id,
                    ))

                # Cache latest telemetry per asset
                if asset_id:
                    self._telemetry_cache[asset_id] = {
                        "topic": topic,
                        "data": data,
                        "timestamp": sample.get("timestamp",
                                                datetime.now(timezone.utc).isoformat()),
                    }
            except Exception:
                pass

        if items:
            self._record_in(len(items))
        return items

    def emit(self, data) -> bool:
        """Send a command to DimOS."""
        if not self.connected:
            return False
        try:
            d = data.to_dict() if hasattr(data, "to_dict") else data
            payload = json.dumps(d, default=str)

            if self._standalone:
                # Log the command for testing/simulation
                self._command_log.append({
                    "command": d,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                self._record_out(1, len(payload))
                return True

            # Real DimOS: send via websocket
            if self._ws:
                self._ws.send(payload)
                self._record_out(1, len(payload))
                return True
            return False
        except Exception as e:
            self._record_error(str(e))
            return False

    # ── DimOS-specific command helpers ─────────────────────

    def send_command(self, asset_id: str, command_type: str,
                     params: dict = None) -> dict:
        """Send a typed command to a specific robot.

        Args:
            asset_id: target robot asset ID
            command_type: one of DIMOS_COMMANDS
            params: command-specific parameters
        Returns:
            command record dict
        """
        if command_type not in DIMOS_COMMANDS:
            return {"error": f"Unknown DimOS command: {command_type}"}
        cmd = {
            "type": "dimos_command",
            "command": command_type,
            "asset_id": asset_id,
            "params": params or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.emit(cmd)
        return cmd

    def send_navigate(self, asset_id: str, building_id: str,
                      room_id: str, floor: int = 0) -> dict:
        """Navigate robot to a specific room."""
        return self.send_command(asset_id, "NAVIGATE", {
            "building_id": building_id,
            "room_id": room_id,
            "floor": floor,
        })

    def send_breach(self, asset_id: str, door_id: str,
                    method: str = "manual") -> dict:
        """Command robot to breach a door."""
        return self.send_command(asset_id, "BREACH", {
            "door_id": door_id,
            "method": method,
        })

    def send_scan(self, asset_id: str, room_id: str) -> dict:
        """Command robot to perform a perception sweep of a room."""
        return self.send_command(asset_id, "SCAN", {"room_id": room_id})

    def send_posture(self, asset_id: str, posture: str) -> dict:
        """Change bipedal posture (standing, crouching, prone)."""
        return self.send_command(asset_id, "POSTURE", {"posture": posture})

    # ── Telemetry injection (for simulation / testing) ────

    def inject_telemetry(self, asset_id: str, topic: str, data: dict):
        """Push simulated telemetry into the ingest pipeline."""
        with self._inbox_lock:
            self._inbox.append({
                "topic": topic,
                "data": {"asset_id": asset_id, **data},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def get_telemetry(self, asset_id: str) -> Optional[dict]:
        """Get latest cached telemetry for an asset."""
        return self._telemetry_cache.get(asset_id)

    def get_all_telemetry(self) -> Dict[str, dict]:
        """All cached telemetry."""
        return dict(self._telemetry_cache)

    # ── CQB task → DimOS command mapping ──────────────────

    def map_cqb_task(self, task, building_id: str = "") -> List[dict]:
        """Convert a CQBTask to one or more DimOS commands.

        Args:
            task: CQBTask instance
            building_id: override building ID
        Returns:
            list of command dicts sent
        """
        bid = building_id or task.building_id
        commands = []

        if task.task_type == "STACK":
            # Navigate each asset to the door area
            for aid in task.assigned_assets:
                cmd = self.send_navigate(aid, bid,
                                         task.target_id, task.floor)
                commands.append(cmd)

        elif task.task_type == "BREACH":
            method = task.params.get("method", "manual")
            # First asset is the breacher
            if task.assigned_assets:
                cmd = self.send_breach(task.assigned_assets[0],
                                       task.target_id, method)
                commands.append(cmd)

        elif task.task_type == "CLEAR":
            room_id = task.params.get("room_id", task.target_id)
            for aid in task.assigned_assets:
                cmd = self.send_navigate(aid, bid, room_id, task.floor)
                commands.append(cmd)
            # Point man scans
            if task.assigned_assets:
                cmd = self.send_scan(task.assigned_assets[0], room_id)
                commands.append(cmd)

        elif task.task_type == "HOLD":
            for aid in task.assigned_assets:
                cmd = self.send_command(aid, "HOLD", {
                    "room_id": task.target_id,
                    "sector": task.params.get("sector", "all"),
                })
                commands.append(cmd)

        elif task.task_type == "SECURE":
            for aid in task.assigned_assets:
                cmd = self.send_navigate(aid, bid,
                                         task.target_id, task.floor)
                commands.append(cmd)

        elif task.task_type == "EXTRACT":
            for aid in task.assigned_assets:
                cmd = self.send_command(aid, "EXTRACT", {
                    "casualty_id": task.params.get("casualty_id", ""),
                    "route": task.params.get("route", "primary"),
                })
                commands.append(cmd)

        return commands

    # ── Status ────────────────────────────────────────────

    def get_status(self) -> dict:
        base = super().get_status()
        base["host"] = self.host
        base["port"] = self.port
        base["standalone"] = self._standalone
        base["telemetry_assets"] = list(self._telemetry_cache.keys())
        base["commands_sent"] = len(self._command_log)
        base["inbox_pending"] = len(self._inbox)
        return base

    def get_command_log(self, limit: int = 50) -> List[dict]:
        """Recent commands sent."""
        return self._command_log[-limit:]
