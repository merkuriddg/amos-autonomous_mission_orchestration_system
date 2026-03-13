#!/usr/bin/env python3
"""AMOS B4.2 — Perception Fusion for Indoor CQB

Aggregates perception data from multiple DimOS robots into a shared
indoor situational awareness picture:

  1. SLAM Grid Fusion — merge per-robot occupancy grids into a shared map
  2. Detection Fusion — correlate object detections (hostiles, civilians,
     IEDs, obstacles) across robots into unified CQB threat tracks
  3. Intel Forwarding — push AMOS-level threat intel down to robots
  4. Shared Awareness — maintain a per-building, per-floor detection map

Works alongside SensorFusionEngine (km-scale outdoor) — this handles
meter-scale indoor CQB scenarios.
"""

import uuid
import time
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional


# CQB detection classifications
CQB_CLASSIFICATIONS = (
    "hostile_armed", "hostile_unarmed", "civilian", "friendly",
    "ied", "obstacle", "door_open", "door_closed", "unknown",
)

# Fusion correlation threshold (meters)
CQB_CORRELATION_THRESHOLD_M = 3.0


class CQBDetection:
    """A single indoor detection from a robot's perception system."""

    def __init__(self, building_id: str, floor: int, room_id: str,
                 x_m: float = 0, y_m: float = 0,
                 classification: str = "unknown",
                 confidence: float = 0.5,
                 source_asset: str = ""):
        self.id = f"DET-{uuid.uuid4().hex[:8]}"
        self.building_id = building_id
        self.floor = floor
        self.room_id = room_id
        self.x_m = x_m
        self.y_m = y_m
        self.classification = classification
        self.confidence = confidence
        self.source_asset = source_asset
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id, "building_id": self.building_id,
            "floor": self.floor, "room_id": self.room_id,
            "x_m": self.x_m, "y_m": self.y_m,
            "classification": self.classification,
            "confidence": round(self.confidence, 2),
            "source_asset": self.source_asset,
            "timestamp": self.timestamp,
        }


class CQBThreatTrack:
    """A fused indoor threat track from multiple robot detections."""

    def __init__(self, detection: CQBDetection):
        self.id = f"CTT-{uuid.uuid4().hex[:8]}"
        self.building_id = detection.building_id
        self.floor = detection.floor
        self.room_id = detection.room_id
        self.x_m = detection.x_m
        self.y_m = detection.y_m
        self.classification = detection.classification
        self.confidence = detection.confidence
        self.sources: Dict[str, float] = {detection.source_asset: time.time()}
        self.detections: List[str] = [detection.id]
        self.first_seen = datetime.now(timezone.utc).isoformat()
        self.last_seen = self.first_seen
        self.status = "active"  # active, stale, neutralized

    def correlate(self, det: CQBDetection) -> bool:
        """Check if a detection should merge into this track."""
        if det.building_id != self.building_id or det.floor != self.floor:
            return False
        dist = math.sqrt((det.x_m - self.x_m)**2 + (det.y_m - self.y_m)**2)
        return dist < CQB_CORRELATION_THRESHOLD_M

    def update(self, det: CQBDetection):
        """Merge a new detection into this track."""
        alpha = 0.4
        self.x_m = self.x_m * (1 - alpha) + det.x_m * alpha
        self.y_m = self.y_m * (1 - alpha) + det.y_m * alpha
        self.room_id = det.room_id or self.room_id
        self.sources[det.source_asset] = time.time()
        self.detections.append(det.id)
        self.last_seen = datetime.now(timezone.utc).isoformat()
        # Confidence grows with corroborating sources
        self.confidence = min(0.99, 0.3 + len(self.sources) * 0.2)
        # Upgrade classification if higher confidence
        if det.confidence > 0.5 and det.classification != "unknown":
            self.classification = det.classification

    def to_dict(self) -> dict:
        return {
            "id": self.id, "building_id": self.building_id,
            "floor": self.floor, "room_id": self.room_id,
            "x_m": round(self.x_m, 2), "y_m": round(self.y_m, 2),
            "classification": self.classification,
            "confidence": round(self.confidence, 2),
            "source_count": len(self.sources),
            "sources": list(self.sources.keys()),
            "detection_count": len(self.detections),
            "status": self.status,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
        }


class OccupancyGrid:
    """Simple 2D occupancy grid for a single building floor.

    Cell values: 0 = unknown, 1 = free, 2 = occupied, 3 = wall
    """

    def __init__(self, building_id: str, floor: int,
                 width_m: float = 30, height_m: float = 20,
                 resolution_m: float = 0.5):
        self.building_id = building_id
        self.floor = floor
        self.resolution = resolution_m
        self.cols = int(width_m / resolution_m)
        self.rows = int(height_m / resolution_m)
        self.grid = [[0] * self.cols for _ in range(self.rows)]
        self.contributors: Dict[str, str] = {}  # asset_id → last_update
        self.last_update = None

    def merge_scan(self, asset_id: str, cells: List[dict]):
        """Merge a partial scan from a robot.

        cells: [{x_m, y_m, value}, ...]
        """
        for c in cells:
            col = int(c.get("x_m", 0) / self.resolution)
            row = int(c.get("y_m", 0) / self.resolution)
            val = c.get("value", 1)
            if 0 <= row < self.rows and 0 <= col < self.cols:
                # Higher-confidence values override unknown
                if self.grid[row][col] == 0 or val > 0:
                    self.grid[row][col] = val
        self.contributors[asset_id] = datetime.now(timezone.utc).isoformat()
        self.last_update = datetime.now(timezone.utc).isoformat()

    def get_explored_pct(self) -> float:
        total = self.rows * self.cols
        known = sum(1 for row in self.grid for c in row if c != 0)
        return round(known / total * 100, 1) if total else 0

    def to_dict(self) -> dict:
        return {
            "building_id": self.building_id,
            "floor": self.floor,
            "resolution_m": self.resolution,
            "cols": self.cols, "rows": self.rows,
            "explored_pct": self.get_explored_pct(),
            "contributors": self.contributors,
            "last_update": self.last_update,
        }


class PerceptionFusion:
    """Indoor CQB perception fusion engine."""

    def __init__(self, event_bus=None, dimos_bridge=None):
        self.event_bus = event_bus
        self.dimos_bridge = dimos_bridge
        self.tracks: Dict[str, CQBThreatTrack] = {}
        self.grids: Dict[str, OccupancyGrid] = {}  # "BLDG-F0" → grid
        self.detections: List[CQBDetection] = []
        self.intel_forwarded: List[dict] = []

    def ingest_detection(self, building_id: str, floor: int, room_id: str,
                         x_m: float = 0, y_m: float = 0,
                         classification: str = "unknown",
                         confidence: float = 0.5,
                         source_asset: str = "") -> CQBThreatTrack:
        """Process a new detection from a robot's perception system."""
        det = CQBDetection(building_id, floor, room_id, x_m, y_m,
                           classification, confidence, source_asset)
        self.detections.append(det)

        # Try to correlate with existing tracks
        for track in self.tracks.values():
            if track.status == "active" and track.correlate(det):
                track.update(det)
                self._emit("perception.track.updated", track.to_dict())
                return track

        # New track
        track = CQBThreatTrack(det)
        self.tracks[track.id] = track
        self._emit("perception.track.new", track.to_dict())
        return track

    def ingest_slam_scan(self, building_id: str, floor: int,
                         asset_id: str, cells: List[dict]):
        """Merge a SLAM occupancy scan into the shared grid."""
        key = f"{building_id}-F{floor}"
        if key not in self.grids:
            self.grids[key] = OccupancyGrid(building_id, floor)
        self.grids[key].merge_scan(asset_id, cells)
        self._emit("perception.grid.updated", {
            "building_id": building_id, "floor": floor,
            "asset_id": asset_id, "explored_pct": self.grids[key].get_explored_pct(),
        })

    def forward_intel(self, building_id: str, room_id: str,
                      intel_type: str = "threat",
                      details: str = "") -> dict:
        """Push threat intel from AMOS down to robots via DimOS."""
        intel = {
            "type": "intel_forward",
            "building_id": building_id,
            "room_id": room_id,
            "intel_type": intel_type,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.intel_forwarded.append(intel)

        # Send to DimOS bridge if available
        if self.dimos_bridge and self.dimos_bridge.connected:
            self.dimos_bridge.emit(intel)

        self._emit("perception.intel.forwarded", intel)
        return intel

    def mark_neutralized(self, track_id: str) -> bool:
        """Mark a CQB threat track as neutralized."""
        track = self.tracks.get(track_id)
        if track:
            track.status = "neutralized"
            self._emit("perception.track.neutralized", track.to_dict())
            return True
        return False

    def get_tracks_in_room(self, building_id: str,
                           room_id: str) -> List[dict]:
        """Get all active tracks in a specific room."""
        return [t.to_dict() for t in self.tracks.values()
                if t.building_id == building_id and t.room_id == room_id
                and t.status == "active"]

    def get_tracks_on_floor(self, building_id: str,
                            floor: int) -> List[dict]:
        """Get all active tracks on a floor."""
        return [t.to_dict() for t in self.tracks.values()
                if t.building_id == building_id and t.floor == floor
                and t.status == "active"]

    def get_grid(self, building_id: str, floor: int) -> Optional[dict]:
        key = f"{building_id}-F{floor}"
        grid = self.grids.get(key)
        return grid.to_dict() if grid else None

    def get_all_grids(self) -> List[dict]:
        return [g.to_dict() for g in self.grids.values()]

    def get_stats(self) -> dict:
        active = sum(1 for t in self.tracks.values() if t.status == "active")
        return {
            "total_tracks": len(self.tracks),
            "active_tracks": active,
            "neutralized": len(self.tracks) - active,
            "total_detections": len(self.detections),
            "grids": len(self.grids),
            "intel_forwarded": len(self.intel_forwarded),
        }

    def _emit(self, topic: str, payload: dict):
        if self.event_bus:
            self.event_bus.publish(topic, payload, source="perception_fusion")
