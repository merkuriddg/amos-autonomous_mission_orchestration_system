#!/usr/bin/env python3
"""AMOS B2.3 — Indoor Positioning Service

Maintains per-asset positions within buildings for GPS-denied CQB operations.
Ingests position updates from multiple sources (SLAM, UWB, IMU, visual odometry)
and fuses them into a best-estimate indoor position.

Bridges indoor positions back to AMOS's standard lat/lng model by converting
local building coordinates to approximate GPS positions.
"""

import math
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.data_model import IndoorPosition, AssetState

# Approximate meters per degree (mid-latitude)
_M_PER_DEG_LAT = 111_320
_M_PER_DEG_LNG_AT_35 = 91_290


class IndoorPositioningService:
    """Track and fuse indoor positions for assets operating in GPS-denied environments."""

    # Source priority (higher = more trusted)
    SOURCE_PRIORITY = {
        "slam": 4,
        "uwb": 3,
        "visual_odom": 2,
        "imu": 1,
        "manual": 5,
    }

    def __init__(self):
        self._positions: Dict[str, IndoorPosition] = {}  # asset_id -> latest fused position
        self._history: Dict[str, List[dict]] = {}         # asset_id -> position history
        self._lock = threading.Lock()
        self._max_history = 100

    def update_position(self, asset_id: str, building_id: str, floor: int,
                        room: str = "", x_m: float = 0.0, y_m: float = 0.0, z_m: float = 0.0,
                        confidence: float = 0.5, source: str = "slam") -> IndoorPosition:
        """Ingest a position update from a sensor source.

        If a higher-confidence source has recently reported, we weight
        the new position accordingly.  Returns the fused position.
        """
        now = datetime.now(timezone.utc).isoformat()

        new_pos = IndoorPosition(
            building_id=building_id, floor=floor, room=room,
            x_m=x_m, y_m=y_m, z_m=z_m,
            confidence=confidence, source=source, last_update=now,
        )

        with self._lock:
            existing = self._positions.get(asset_id)
            if existing and existing.building_id == building_id:
                # Fuse: weight toward higher-confidence / higher-priority source
                fused = self._fuse(existing, new_pos)
                self._positions[asset_id] = fused
            else:
                # New building or first position — accept directly
                self._positions[asset_id] = new_pos

            # Record history
            hist = self._history.setdefault(asset_id, [])
            hist.append({
                "building_id": building_id, "floor": floor, "room": room,
                "x_m": round(x_m, 3), "y_m": round(y_m, 3), "z_m": round(z_m, 3),
                "confidence": confidence, "source": source, "ts": now,
            })
            if len(hist) > self._max_history:
                del hist[:len(hist) - self._max_history]

            return self._positions[asset_id]

    def _fuse(self, old: IndoorPosition, new: IndoorPosition) -> IndoorPosition:
        """Simple weighted fusion of two positions.

        Higher-priority source and higher confidence get more weight.
        """
        old_pri = self.SOURCE_PRIORITY.get(old.source, 1)
        new_pri = self.SOURCE_PRIORITY.get(new.source, 1)
        old_w = old.confidence * old_pri
        new_w = new.confidence * new_pri
        total = old_w + new_w
        if total == 0:
            return new

        alpha = new_w / total  # weight toward new position
        return IndoorPosition(
            building_id=new.building_id,
            floor=new.floor,
            room=new.room or old.room,
            x_m=round(old.x_m * (1 - alpha) + new.x_m * alpha, 3),
            y_m=round(old.y_m * (1 - alpha) + new.y_m * alpha, 3),
            z_m=round(old.z_m * (1 - alpha) + new.z_m * alpha, 3),
            confidence=round(min(1.0, max(old.confidence, new.confidence) + 0.05), 3),
            source=new.source,
            last_update=new.last_update,
        )

    def get_position(self, asset_id: str) -> Optional[IndoorPosition]:
        """Get the current fused indoor position for an asset."""
        return self._positions.get(asset_id)

    def get_all_positions(self) -> Dict[str, dict]:
        """All current indoor positions as serializable dicts."""
        return {aid: pos.to_dict() for aid, pos in self._positions.items()}

    def get_history(self, asset_id: str, limit: int = 50) -> List[dict]:
        """Position history for an asset."""
        return self._history.get(asset_id, [])[-limit:]

    def get_assets_in_building(self, building_id: str) -> List[str]:
        """List asset IDs currently positioned in a specific building."""
        return [aid for aid, pos in self._positions.items()
                if pos.building_id == building_id]

    def get_assets_in_room(self, building_id: str, room_id: str) -> List[str]:
        """List asset IDs in a specific room."""
        return [aid for aid, pos in self._positions.items()
                if pos.building_id == building_id and pos.room == room_id]

    def get_assets_on_floor(self, building_id: str, floor: int) -> List[str]:
        """List asset IDs on a specific floor."""
        return [aid for aid, pos in self._positions.items()
                if pos.building_id == building_id and pos.floor == floor]

    def remove_asset(self, asset_id: str):
        """Remove an asset's indoor position (e.g. when it exits the building)."""
        self._positions.pop(asset_id, None)
        self._history.pop(asset_id, None)

    def to_latlng(self, position: IndoorPosition, building_location: dict) -> dict:
        """Convert indoor position to approximate lat/lng using building origin.

        Args:
            position: IndoorPosition with x_m, y_m
            building_location: dict with lat, lng (building origin)
        Returns:
            dict with lat, lng, alt_ft
        """
        blat = building_location.get("lat", 0)
        blng = building_location.get("lng", 0)
        balt = building_location.get("alt_m", 0)
        return {
            "lat": round(blat + position.y_m / _M_PER_DEG_LAT, 8),
            "lng": round(blng + position.x_m / _M_PER_DEG_LNG_AT_35, 8),
            "alt_ft": round((balt + position.z_m) * 3.28084, 1),
        }

    def get_stats(self) -> dict:
        """Service statistics."""
        buildings = set()
        for pos in self._positions.values():
            buildings.add(pos.building_id)
        return {
            "tracked_assets": len(self._positions),
            "buildings_active": len(buildings),
            "total_updates": sum(len(h) for h in self._history.values()),
        }
