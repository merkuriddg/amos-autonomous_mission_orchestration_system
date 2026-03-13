#!/usr/bin/env python3
"""AMOS B1.3 — CQB Formation Engine

Meter-scale tactical formations for close-quarters battle (CQB) operations.
Complements the existing SwarmOrchestrator formations (LINE, WEDGE, DIAMOND…)
which operate at 50-200m spacing.  CQB formations operate at 1-5m spacing
and support both GPS (lat/lng) and local meter coordinates.

Formation types:
  STACK              single-file at doorway, 1m spacing
  BUTTONHOOK         pairs split left/right through doorway
  CRISSCROSS         alternating cross-entry for room clearing
  BOUNDING_OVERWATCH one team moves, one covers, alternate
  PERIMETER          surround structure at entry points
  CORRIDOR           staggered wall-hugging movement

All methods return a list of position dicts.  When `use_local=True`,
positions are returned as `{x_m, y_m}` in local meter coordinates.
When `use_local=False` (default), positions are returned as `{lat, lng}`
offset from a reference point.
"""

import math
from typing import List, Dict, Optional

# Approximate meters per degree latitude (valid at mid-latitudes)
_M_PER_DEG_LAT = 111_320
_M_PER_DEG_LNG_AT_35 = 91_290  # ~cos(35°) * 111,320


def _offset_latlng(lat: float, lng: float, dx_m: float, dy_m: float) -> Dict[str, float]:
    """Offset a lat/lng point by dx (east) and dy (north) in meters."""
    return {
        "lat": round(lat + dy_m / _M_PER_DEG_LAT, 8),
        "lng": round(lng + dx_m / _M_PER_DEG_LNG_AT_35, 8),
    }


def _local_pos(x_m: float, y_m: float) -> Dict[str, float]:
    """Return a local meter-coordinate position dict."""
    return {"x_m": round(x_m, 3), "y_m": round(y_m, 3)}


class CQBFormation:
    """Compute CQB formation positions for a squad of assets.

    Parameters common to all methods:
        count       — number of assets
        heading_deg — direction the squad is facing (0=north, 90=east)
        spacing_m   — base spacing between assets (default 1.0m)
        ref_lat/ref_lng — reference point for lat/lng mode
        use_local   — if True, return local {x_m, y_m}; else {lat, lng}
    """

    @staticmethod
    def stack(count: int, heading_deg: float = 0, spacing_m: float = 1.0,
              ref_lat: float = 0, ref_lng: float = 0,
              use_local: bool = False) -> List[Dict]:
        """Single-file at doorway.  Lead asset at reference point,
        each subsequent asset directly behind at `spacing_m`."""
        h = math.radians(heading_deg)
        positions = []
        for i in range(count):
            # Each asset is i * spacing behind the lead
            dy = -i * spacing_m * math.cos(h)
            dx = -i * spacing_m * math.sin(h)
            if use_local:
                positions.append(_local_pos(dx, dy))
            else:
                positions.append(_offset_latlng(ref_lat, ref_lng, dx, dy))
        return positions

    @staticmethod
    def buttonhook(count: int, heading_deg: float = 0, spacing_m: float = 1.5,
                   ref_lat: float = 0, ref_lng: float = 0,
                   use_local: bool = False) -> List[Dict]:
        """Pairs split left/right through a doorway.
        Lead pair hooks left and right, second pair follows offset behind."""
        h = math.radians(heading_deg)
        perp = h + math.pi / 2
        positions = []
        for i in range(count):
            pair_idx = i // 2        # which pair (0, 1, 2…)
            side = 1 if i % 2 == 0 else -1  # left or right
            # Forward offset: each pair steps deeper into the room
            fwd = (pair_idx + 1) * spacing_m
            lateral = side * spacing_m
            dy = fwd * math.cos(h) + lateral * math.cos(perp)
            dx = fwd * math.sin(h) + lateral * math.sin(perp)
            if use_local:
                positions.append(_local_pos(dx, dy))
            else:
                positions.append(_offset_latlng(ref_lat, ref_lng, dx, dy))
        return positions

    @staticmethod
    def crisscross(count: int, heading_deg: float = 0, spacing_m: float = 1.5,
                   ref_lat: float = 0, ref_lng: float = 0,
                   use_local: bool = False) -> List[Dict]:
        """Alternating cross-entry for room clearing.
        Assets cross to the opposite side of the room alternately."""
        h = math.radians(heading_deg)
        perp = h + math.pi / 2
        positions = []
        for i in range(count):
            # Each asset goes to alternating sides with increasing depth
            side = 1 if i % 2 == 0 else -1
            depth = (i + 1) * spacing_m
            lateral = side * spacing_m * 1.5   # wider than buttonhook
            dy = depth * math.cos(h) + lateral * math.cos(perp)
            dx = depth * math.sin(h) + lateral * math.sin(perp)
            if use_local:
                positions.append(_local_pos(dx, dy))
            else:
                positions.append(_offset_latlng(ref_lat, ref_lng, dx, dy))
        return positions

    @staticmethod
    def bounding_overwatch(count: int, heading_deg: float = 0, spacing_m: float = 3.0,
                           ref_lat: float = 0, ref_lng: float = 0,
                           use_local: bool = False) -> List[Dict]:
        """One element moves while the other covers, then alternates.
        Returns positions for the current phase (movers forward, overwatchers back).
        Even-indexed assets = overwatch (rear), odd-indexed = bounding (forward)."""
        h = math.radians(heading_deg)
        perp = h + math.pi / 2
        positions = []
        for i in range(count):
            is_mover = i % 2 == 1
            rank = i // 2
            fwd = spacing_m * 2 if is_mover else 0  # movers are forward
            lateral = (rank - (count // 4)) * spacing_m
            dy = fwd * math.cos(h) + lateral * math.cos(perp)
            dx = fwd * math.sin(h) + lateral * math.sin(perp)
            if use_local:
                positions.append(_local_pos(dx, dy))
            else:
                positions.append(_offset_latlng(ref_lat, ref_lng, dx, dy))
        return positions

    @staticmethod
    def perimeter(count: int, heading_deg: float = 0, radius_m: float = 5.0,
                  ref_lat: float = 0, ref_lng: float = 0,
                  use_local: bool = False) -> List[Dict]:
        """Surround a structure at entry points.
        Assets evenly distributed around a circle of radius_m."""
        positions = []
        for i in range(count):
            angle = (2 * math.pi * i) / count + math.radians(heading_deg)
            dx = radius_m * math.sin(angle)
            dy = radius_m * math.cos(angle)
            if use_local:
                positions.append(_local_pos(dx, dy))
            else:
                positions.append(_offset_latlng(ref_lat, ref_lng, dx, dy))
        return positions

    @staticmethod
    def corridor(count: int, heading_deg: float = 0, spacing_m: float = 2.0,
                 wall_offset_m: float = 0.5,
                 ref_lat: float = 0, ref_lng: float = 0,
                 use_local: bool = False) -> List[Dict]:
        """Staggered wall-hugging movement down a corridor.
        Assets alternate left/right walls with forward spacing."""
        h = math.radians(heading_deg)
        perp = h + math.pi / 2
        positions = []
        for i in range(count):
            side = 1 if i % 2 == 0 else -1
            fwd = i * spacing_m
            lateral = side * wall_offset_m
            dy = fwd * math.cos(h) + lateral * math.cos(perp)
            dx = fwd * math.sin(h) + lateral * math.sin(perp)
            if use_local:
                positions.append(_local_pos(dx, dy))
            else:
                positions.append(_offset_latlng(ref_lat, ref_lng, dx, dy))
        return positions

    # ── Dispatcher ────────────────────────────────────────
    FORMATIONS = {
        "STACK": "stack",
        "BUTTONHOOK": "buttonhook",
        "CRISSCROSS": "crisscross",
        "BOUNDING_OVERWATCH": "bounding_overwatch",
        "PERIMETER": "perimeter",
        "CORRIDOR": "corridor",
    }

    @classmethod
    def compute(cls, formation: str, count: int, **kwargs) -> List[Dict]:
        """Dispatch to the named formation method.

        Args:
            formation: one of CQB_FORMATIONS (e.g. "STACK", "CORRIDOR")
            count: number of assets
            **kwargs: heading_deg, spacing_m, ref_lat, ref_lng, use_local, etc.
        Returns:
            List of position dicts.
        Raises:
            ValueError if formation is unknown.
        """
        method_name = cls.FORMATIONS.get(formation)
        if not method_name:
            raise ValueError(f"Unknown CQB formation: {formation}")
        method = getattr(cls, method_name)
        return method(count=count, **kwargs)

    @classmethod
    def available(cls) -> list:
        """Return list of available CQB formation names."""
        return list(cls.FORMATIONS.keys())
