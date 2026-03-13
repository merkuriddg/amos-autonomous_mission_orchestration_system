#!/usr/bin/env python3
"""AMOS B2.1 — Building / Floorplan Data Model

Loads building JSON files from config/buildings/ and provides:
  - Room, door, window, stairwell queries by ID or floor
  - Adjacency graph (which rooms connect via doors/stairs)
  - Pathfinding between rooms (BFS shortest path)
  - Room-level line-of-sight (rooms connected by doors have LOS)
  - Clearing status tracking
  - Entry point enumeration
"""

import os
import json
import math
from collections import deque
from typing import Dict, List, Optional, Tuple


class BuildingModel:
    """In-memory model of a single building loaded from JSON."""

    def __init__(self, data: dict):
        self.id = data["id"]
        self.name = data.get("name", "")
        self.description = data.get("description", "")
        self.location = data.get("location", {})
        self.dimensions = data.get("dimensions", {})
        self.walls = data.get("walls", {})
        self.entry_points = data.get("entry_points", [])
        self.threats_intel = data.get("threats_intel", {})
        self._raw = data

        # Index floors, rooms, doors by ID for fast lookup
        self._floors: Dict[int, dict] = {}
        self._rooms: Dict[str, dict] = {}
        self._doors: Dict[str, dict] = {}
        self._windows: Dict[str, dict] = {}
        self._stairs: Dict[str, dict] = {}
        self._room_floor: Dict[str, int] = {}   # room_id -> floor number

        for floor_data in data.get("floors", []):
            fn = floor_data["floor"]
            self._floors[fn] = floor_data
            for room in floor_data.get("rooms", []):
                self._rooms[room["id"]] = room
                self._room_floor[room["id"]] = fn
            for door in floor_data.get("doors", []):
                self._doors[door["id"]] = door
            for win in floor_data.get("windows", []):
                self._windows[win["id"]] = win
            for stair in floor_data.get("stairs", []):
                self._stairs[stair["id"]] = stair

        # Build adjacency graph (room_id -> set of connected room_ids)
        self._adjacency: Dict[str, set] = {}
        self._build_adjacency()

    def _build_adjacency(self):
        """Build room adjacency graph from doors and stairs."""
        for room_id in self._rooms:
            self._adjacency.setdefault(room_id, set())

        # Doors create same-floor connections
        for door in self._doors.values():
            fr = door["from_room"]
            to = door["to_room"]
            if fr != "EXTERIOR" and to != "EXTERIOR":
                self._adjacency.setdefault(fr, set()).add(to)
                self._adjacency.setdefault(to, set()).add(fr)

        # Stairs create cross-floor connections
        # Stairs with same position on adjacent floors connect their rooms
        stair_by_pos = {}
        for stair in self._stairs.values():
            room = stair["room"]
            target_floor = stair["connects_to_floor"]
            # Find the stair on the target floor that connects back
            for other in self._stairs.values():
                if (self._room_floor.get(other["room"]) == target_floor and
                        other.get("connects_to_floor") == self._room_floor.get(room)):
                    self._adjacency.setdefault(room, set()).add(other["room"])
                    self._adjacency.setdefault(other["room"], set()).add(room)

    # ── Floor queries ─────────────────────────────────────

    @property
    def floor_count(self) -> int:
        return len(self._floors)

    def get_floors(self) -> List[int]:
        return sorted(self._floors.keys())

    def get_floor(self, floor: int) -> Optional[dict]:
        return self._floors.get(floor)

    # ── Room queries ──────────────────────────────────────

    @property
    def room_count(self) -> int:
        return len(self._rooms)

    def get_room(self, room_id: str) -> Optional[dict]:
        return self._rooms.get(room_id)

    def get_rooms_on_floor(self, floor: int) -> List[dict]:
        return [r for r in self._rooms.values() if self._room_floor.get(r["id"]) == floor]

    def get_room_floor(self, room_id: str) -> Optional[int]:
        return self._room_floor.get(room_id)

    # ── Door queries ──────────────────────────────────────

    def get_door(self, door_id: str) -> Optional[dict]:
        return self._doors.get(door_id)

    def get_doors_for_room(self, room_id: str) -> List[dict]:
        return [d for d in self._doors.values()
                if d["from_room"] == room_id or d["to_room"] == room_id]

    def get_entry_doors(self) -> List[dict]:
        """Doors connecting to EXTERIOR."""
        return [d for d in self._doors.values()
                if d["from_room"] == "EXTERIOR" or d["to_room"] == "EXTERIOR"]

    # ── Adjacency & pathfinding ───────────────────────────

    def get_adjacent_rooms(self, room_id: str) -> List[str]:
        return list(self._adjacency.get(room_id, set()))

    def has_los(self, room_a: str, room_b: str) -> bool:
        """Two rooms have line-of-sight if directly connected by a door."""
        return room_b in self._adjacency.get(room_a, set())

    def find_path(self, from_room: str, to_room: str) -> Optional[List[str]]:
        """BFS shortest path between two rooms. Returns room ID list or None."""
        if from_room == to_room:
            return [from_room]
        if from_room not in self._adjacency or to_room not in self._adjacency:
            return None
        visited = {from_room}
        queue = deque([(from_room, [from_room])])
        while queue:
            current, path = queue.popleft()
            for neighbor in self._adjacency.get(current, set()):
                if neighbor == to_room:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return None

    # ── Clearing status ───────────────────────────────────

    def mark_cleared(self, room_id: str) -> bool:
        room = self._rooms.get(room_id)
        if room:
            room["cleared"] = True
            return True
        return False

    def mark_uncleared(self, room_id: str) -> bool:
        room = self._rooms.get(room_id)
        if room:
            room["cleared"] = False
            return True
        return False

    def get_cleared_rooms(self) -> List[str]:
        return [rid for rid, r in self._rooms.items() if r.get("cleared")]

    def get_uncleared_rooms(self) -> List[str]:
        return [rid for rid, r in self._rooms.items() if not r.get("cleared")]

    @property
    def clearing_progress(self) -> float:
        """Fraction of rooms cleared (0.0 to 1.0)."""
        if not self._rooms:
            return 0.0
        return len(self.get_cleared_rooms()) / len(self._rooms)

    # ── Serialisation ─────────────────────────────────────

    def to_summary(self) -> dict:
        """Compact summary for API listing."""
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "floors": self.floor_count,
            "rooms": self.room_count,
            "entry_points": len(self.entry_points),
            "clearing_progress": round(self.clearing_progress, 2),
        }

    def to_dict(self) -> dict:
        """Full building data."""
        return self._raw


class BuildingManager:
    """Loads and manages all building models from config/buildings/."""

    def __init__(self, buildings_dir: str = None):
        if buildings_dir is None:
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            buildings_dir = os.path.join(root, "config", "buildings")
        self.buildings_dir = buildings_dir
        self.buildings: Dict[str, BuildingModel] = {}
        self._load_all()

    def _load_all(self):
        if not os.path.isdir(self.buildings_dir):
            return
        for fname in sorted(os.listdir(self.buildings_dir)):
            if fname.endswith(".json"):
                path = os.path.join(self.buildings_dir, fname)
                try:
                    with open(path) as f:
                        data = json.load(f)
                    bm = BuildingModel(data)
                    self.buildings[bm.id] = bm
                except Exception as e:
                    print(f"[AMOS] Failed to load building {fname}: {e}")

    def get(self, building_id: str) -> Optional[BuildingModel]:
        return self.buildings.get(building_id)

    def list_buildings(self) -> List[dict]:
        return [b.to_summary() for b in self.buildings.values()]

    def get_nearest(self, lat: float, lng: float) -> Optional[BuildingModel]:
        """Find the building closest to a lat/lng point."""
        best, best_dist = None, float("inf")
        for b in self.buildings.values():
            loc = b.location
            if not loc:
                continue
            d = math.sqrt((loc["lat"] - lat) ** 2 + (loc["lng"] - lng) ** 2)
            if d < best_dist:
                best, best_dist = b, d
        return best
