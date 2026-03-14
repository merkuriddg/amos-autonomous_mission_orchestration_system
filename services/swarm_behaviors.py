#!/usr/bin/env python3
"""AMOS Sprint 2 — Autonomous Swarm Behaviors

Five mission-level swarm behaviors that go beyond formation holding:
  PERIMETER_SCAN  — Assets orbit a geofence polygon
  AREA_SWEEP      — Parallel-track systematic coverage
  DYNAMIC_TRACK   — Swarm converges on and tracks a fused track
  RELAY_MESH      — Assets self-position to maximize mesh connectivity
  SEARCH_SPIRAL   — Expanding spiral from last-known position

Each behavior implements:
  tick(assets, blackboard, dt) → events[]
  progress()       → {pct, phase, details}
  cancel()         → stop and release assets
  to_dict()        → serializable summary

SwarmBehaviorManager orchestrates active behaviors, connects sensor fusion
events to behavior triggers, and manages sub-task auctions.
"""

import math
import uuid
import threading
import time
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

DEG_PER_M = 1.0 / 111_000  # approximate lat/lng degrees per meter
DEG_PER_NM = 1.0 / 60.0    # approximate lat/lng degrees per nautical mile


def _dist_deg(lat1, lng1, lat2, lng2):
    """Euclidean distance in degrees (cheap approximation)."""
    return math.sqrt((lat2 - lat1) ** 2 + (lng2 - lng1) ** 2)


def _bearing_rad(lat1, lng1, lat2, lng2):
    """Bearing from point 1 to point 2 in radians."""
    return math.atan2(lng2 - lng1, lat2 - lat1)


def _polygon_centroid(vertices):
    """Return centroid of a polygon given as list of {lat, lng} dicts."""
    n = len(vertices)
    if n == 0:
        return 0.0, 0.0
    clat = sum(v["lat"] for v in vertices) / n
    clng = sum(v["lng"] for v in vertices) / n
    return clat, clng


def _polygon_perimeter_points(vertices, count):
    """Generate 'count' evenly-spaced points along polygon perimeter."""
    if not vertices:
        return []
    # Close the polygon
    verts = list(vertices) + [vertices[0]]
    # Calculate total perimeter
    segments = []
    total = 0.0
    for i in range(len(verts) - 1):
        d = _dist_deg(verts[i]["lat"], verts[i]["lng"],
                      verts[i + 1]["lat"], verts[i + 1]["lng"])
        segments.append(d)
        total += d
    if total == 0:
        return [{"lat": verts[0]["lat"], "lng": verts[0]["lng"]}] * count

    points = []
    spacing = total / count
    cum = 0.0
    seg_idx = 0
    seg_cum = 0.0
    for _ in range(count):
        target = cum
        # Walk along perimeter to target distance
        while seg_idx < len(segments) - 1 and seg_cum + segments[seg_idx] < target:
            seg_cum += segments[seg_idx]
            seg_idx += 1
        remain = target - seg_cum
        seg_len = segments[seg_idx] if seg_idx < len(segments) else 1
        frac = remain / seg_len if seg_len > 0 else 0
        frac = max(0, min(1, frac))
        v0 = verts[seg_idx]
        v1 = verts[seg_idx + 1] if seg_idx + 1 < len(verts) else verts[0]
        lat = v0["lat"] + frac * (v1["lat"] - v0["lat"])
        lng = v0["lng"] + frac * (v1["lng"] - v0["lng"])
        points.append({"lat": round(lat, 6), "lng": round(lng, 6)})
        cum += spacing
    return points


# ═══════════════════════════════════════════════════════════
#  BASE BEHAVIOR
# ═══════════════════════════════════════════════════════════

class SwarmBehavior:
    """Base class for autonomous swarm behaviors."""

    BEHAVIOR_TYPE = "BASE"

    def __init__(self, behavior_id, swarm_id, asset_ids, params=None):
        self.id = behavior_id
        self.swarm_id = swarm_id
        self.asset_ids = list(asset_ids)
        self.params = params or {}
        self.status = "active"   # active | paused | completed | cancelled
        self.phase = "INIT"
        self.tick_count = 0
        self.created = datetime.now(timezone.utc).isoformat()
        self.started = time.time()
        self.coverage_pct = 0.0
        self.events = []

    def tick(self, assets, blackboard, dt=1.0):
        """Execute one behavior tick. Override in subclass."""
        raise NotImplementedError

    def progress(self):
        """Return progress dict."""
        return {
            "id": self.id,
            "type": self.BEHAVIOR_TYPE,
            "swarm_id": self.swarm_id,
            "status": self.status,
            "phase": self.phase,
            "coverage_pct": round(self.coverage_pct, 1),
            "tick_count": self.tick_count,
            "elapsed_sec": round(time.time() - self.started, 1),
        }

    def cancel(self):
        """Cancel the behavior, release assets."""
        self.status = "cancelled"
        self.phase = "CANCELLED"
        return {"id": self.id, "status": "cancelled"}

    def to_dict(self):
        """Full serializable state."""
        return {
            "id": self.id,
            "type": self.BEHAVIOR_TYPE,
            "swarm_id": self.swarm_id,
            "asset_ids": self.asset_ids,
            "params": self.params,
            "status": self.status,
            "phase": self.phase,
            "coverage_pct": round(self.coverage_pct, 1),
            "tick_count": self.tick_count,
            "created": self.created,
            "elapsed_sec": round(time.time() - self.started, 1),
        }


# ═══════════════════════════════════════════════════════════
#  PERIMETER SCAN — orbit a geofence polygon
# ═══════════════════════════════════════════════════════════

class PerimeterScan(SwarmBehavior):
    """Assets orbit evenly around a geofence polygon perimeter.

    Params:
        vertices: list of {lat, lng} defining the polygon
        orbit_radius_m: offset distance outside polygon (default 200m)
        speed_factor: movement rate multiplier (default 0.05)
    """
    BEHAVIOR_TYPE = "PERIMETER_SCAN"

    def __init__(self, behavior_id, swarm_id, asset_ids, params=None):
        super().__init__(behavior_id, swarm_id, asset_ids, params)
        self.vertices = self.params.get("vertices", [])
        self.orbit_radius_m = self.params.get("orbit_radius_m", 200)
        self.speed = self.params.get("speed_factor", 0.05)
        self.orbit_phase = 0.0  # 0..1 progress around perimeter
        self.laps_completed = 0

    def tick(self, assets, blackboard, dt=1.0):
        events = []
        if self.status != "active" or not self.vertices:
            return events
        self.tick_count += 1
        self.phase = "SCANNING"

        n = len(self.asset_ids)
        waypoints = _polygon_perimeter_points(self.vertices, n)

        # Advance orbit phase — each tick moves assets along the perimeter
        advance = self.speed * dt / max(n, 1)
        self.orbit_phase = (self.orbit_phase + advance) % 1.0

        for i, aid in enumerate(self.asset_ids):
            a = assets.get(aid)
            if not a:
                continue
            # Each asset is offset by i/n around the perimeter
            idx = int(((i / n) + self.orbit_phase) * len(waypoints)) % len(waypoints)
            target = waypoints[idx]

            # Offset outward from centroid
            clat, clng = _polygon_centroid(self.vertices)
            bearing = _bearing_rad(clat, clng, target["lat"], target["lng"])
            offset_deg = self.orbit_radius_m * DEG_PER_M
            desired_lat = target["lat"] + math.cos(bearing) * offset_deg
            desired_lng = target["lng"] + math.sin(bearing) * offset_deg

            # Move toward desired position
            pos = a.get("position", a)
            pos["lat"] += (desired_lat - pos["lat"]) * self.speed * dt
            pos["lng"] += (desired_lng - pos["lng"]) * self.speed * dt

        # Track laps for coverage
        if self.orbit_phase < advance:
            self.laps_completed += 1
            events.append({
                "type": "PERIMETER_LAP", "behavior_id": self.id,
                "lap": self.laps_completed,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # Coverage: 100% after first full lap, then keeps going
        self.coverage_pct = min(100.0, self.orbit_phase * 100 + self.laps_completed * 100)
        if self.coverage_pct >= 100.0:
            self.phase = "COMPLETE_LAP"
        return events


# ═══════════════════════════════════════════════════════════
#  AREA SWEEP — parallel-track systematic coverage
# ═══════════════════════════════════════════════════════════

class AreaSweep(SwarmBehavior):
    """Parallel-track lawnmower sweep across an area.

    Params:
        bounds: {north, south, east, west} of the area
        track_spacing_m: distance between parallel tracks (default 300m)
        speed_factor: movement rate (default 0.04)
    """
    BEHAVIOR_TYPE = "AREA_SWEEP"

    def __init__(self, behavior_id, swarm_id, asset_ids, params=None):
        super().__init__(behavior_id, swarm_id, asset_ids, params)
        bounds = self.params.get("bounds", {})
        self.north = bounds.get("north", 0)
        self.south = bounds.get("south", 0)
        self.east = bounds.get("east", 0)
        self.west = bounds.get("west", 0)
        self.track_spacing = self.params.get("track_spacing_m", 300) * DEG_PER_M
        self.speed = self.params.get("speed_factor", 0.04)
        self._generate_tracks()
        self.current_track = 0
        self.track_progress = 0.0  # 0..1 along current track

    def _generate_tracks(self):
        """Generate parallel tracks across the area, distributed among assets."""
        n_assets = len(self.asset_ids)
        width = abs(self.east - self.west)
        n_tracks = max(1, int(width / self.track_spacing)) if self.track_spacing > 0 else n_assets
        self.tracks = []
        for i in range(n_tracks):
            lng = self.west + (i + 0.5) * (width / n_tracks)
            # Alternate north-south direction
            if i % 2 == 0:
                self.tracks.append({"lng": lng, "start_lat": self.south, "end_lat": self.north})
            else:
                self.tracks.append({"lng": lng, "start_lat": self.north, "end_lat": self.south})
        self.total_tracks = len(self.tracks)

    def tick(self, assets, blackboard, dt=1.0):
        events = []
        if self.status != "active":
            return events
        self.tick_count += 1
        self.phase = "SWEEPING"

        n = len(self.asset_ids)
        if not self.tracks:
            self.status = "completed"
            self.phase = "COMPLETE"
            self.coverage_pct = 100.0
            return events

        # Assign concurrent tracks to assets
        for i, aid in enumerate(self.asset_ids):
            a = assets.get(aid)
            if not a:
                continue
            track_idx = self.current_track + i
            if track_idx >= len(self.tracks):
                continue
            track = self.tracks[track_idx]
            pos = a.get("position", a)

            # Move along the track
            target_lat = track["start_lat"] + self.track_progress * (track["end_lat"] - track["start_lat"])
            target_lng = track["lng"]
            pos["lat"] += (target_lat - pos["lat"]) * self.speed * dt
            pos["lng"] += (target_lng - pos["lng"]) * self.speed * dt

        # Advance track progress
        self.track_progress += self.speed * dt
        if self.track_progress >= 1.0:
            self.track_progress = 0.0
            self.current_track += n  # Move all assets to next batch of tracks
            events.append({
                "type": "SWEEP_TRACK_COMPLETE",
                "behavior_id": self.id,
                "tracks_completed": min(self.current_track, self.total_tracks),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # Check completion
        if self.current_track >= self.total_tracks:
            self.status = "completed"
            self.phase = "COMPLETE"
            self.coverage_pct = 100.0
        else:
            completed_tracks = self.current_track + self.track_progress * min(n, self.total_tracks - self.current_track)
            self.coverage_pct = min(100.0, (completed_tracks / self.total_tracks) * 100)

        return events


# ═══════════════════════════════════════════════════════════
#  DYNAMIC TRACK — swarm converges on and follows a fused track
# ═══════════════════════════════════════════════════════════

class DynamicTrack(SwarmBehavior):
    """Swarm converges on and tracks a moving fused track.

    Params:
        track_id: ID of the fused track to follow
        orbit_radius_m: standoff distance (default 500m)
        speed_factor: approach rate (default 0.06)
    """
    BEHAVIOR_TYPE = "DYNAMIC_TRACK"

    def __init__(self, behavior_id, swarm_id, asset_ids, params=None):
        super().__init__(behavior_id, swarm_id, asset_ids, params)
        self.track_id = self.params.get("track_id", "")
        self.orbit_radius = self.params.get("orbit_radius_m", 500) * DEG_PER_M
        self.speed = self.params.get("speed_factor", 0.06)
        self.target_lat = self.params.get("initial_lat", 0)
        self.target_lng = self.params.get("initial_lng", 0)
        self.last_seen = time.time()
        self.orbit_angle = 0.0

    def tick(self, assets, blackboard, dt=1.0):
        events = []
        if self.status != "active":
            return events
        self.tick_count += 1
        self.phase = "TRACKING"

        # Update target from blackboard if available
        fused_tracks = blackboard.get("fused_tracks", {})
        trk = fused_tracks.get(self.track_id)
        if trk:
            self.target_lat = trk.get("lat", self.target_lat)
            self.target_lng = trk.get("lng", self.target_lng)
            self.last_seen = time.time()
        elif time.time() - self.last_seen > 120:
            # Track lost for >2 min → transition to search
            self.phase = "TRACK_LOST"
            events.append({
                "type": "TRACK_LOST", "behavior_id": self.id,
                "track_id": self.track_id,
                "last_position": {"lat": self.target_lat, "lng": self.target_lng},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return events

        n = len(self.asset_ids)
        self.orbit_angle += 0.02 * dt  # slowly rotate orbit

        # Position assets in orbit around target
        for i, aid in enumerate(self.asset_ids):
            a = assets.get(aid)
            if not a:
                continue
            angle = self.orbit_angle + (2 * math.pi * i) / n
            desired_lat = self.target_lat + math.cos(angle) * self.orbit_radius
            desired_lng = self.target_lng + math.sin(angle) * self.orbit_radius

            pos = a.get("position", a)
            pos["lat"] += (desired_lat - pos["lat"]) * self.speed * dt
            pos["lng"] += (desired_lng - pos["lng"]) * self.speed * dt

        # Coverage = how well we've surrounded the target
        swarm_positions = []
        for aid in self.asset_ids:
            a = assets.get(aid)
            if a:
                p = a.get("position", a)
                swarm_positions.append((p.get("lat", 0), p.get("lng", 0)))

        if swarm_positions:
            # Measure angular coverage around target
            angles = sorted(
                math.atan2(p[1] - self.target_lng, p[0] - self.target_lat)
                for p in swarm_positions
            )
            if len(angles) > 1:
                max_gap = 0
                for j in range(len(angles)):
                    gap = angles[(j + 1) % len(angles)] - angles[j]
                    if gap < 0:
                        gap += 2 * math.pi
                    max_gap = max(max_gap, gap)
                self.coverage_pct = min(100.0, (1 - max_gap / (2 * math.pi)) * 100)
            else:
                self.coverage_pct = min(100.0, 25.0)

        return events


# ═══════════════════════════════════════════════════════════
#  RELAY MESH — self-position for maximum connectivity
# ═══════════════════════════════════════════════════════════

class RelayMesh(SwarmBehavior):
    """Assets self-position to maximize mesh network connectivity.

    Distributes assets to bridge gaps between endpoints.

    Params:
        endpoints: list of {lat, lng, id} — fixed nodes to connect
        max_link_range_m: maximum communication range (default 5000m)
        speed_factor: repositioning rate (default 0.04)
    """
    BEHAVIOR_TYPE = "RELAY_MESH"

    def __init__(self, behavior_id, swarm_id, asset_ids, params=None):
        super().__init__(behavior_id, swarm_id, asset_ids, params)
        self.endpoints = self.params.get("endpoints", [])
        self.max_range = self.params.get("max_link_range_m", 5000) * DEG_PER_M
        self.speed = self.params.get("speed_factor", 0.04)
        self.connectivity = 0.0  # 0..1

    def tick(self, assets, blackboard, dt=1.0):
        events = []
        if self.status != "active":
            return events
        self.tick_count += 1
        self.phase = "POSITIONING"

        if len(self.endpoints) < 2:
            self.phase = "INSUFFICIENT_ENDPOINTS"
            return events

        n_assets = len(self.asset_ids)
        n_endpoints = len(self.endpoints)

        # Strategy: distribute relay assets evenly along paths between endpoints
        # Simple approach: for each pair of consecutive endpoints, assign relay nodes
        pairs = []
        for i in range(n_endpoints):
            for j in range(i + 1, n_endpoints):
                d = _dist_deg(self.endpoints[i]["lat"], self.endpoints[i]["lng"],
                              self.endpoints[j]["lat"], self.endpoints[j]["lng"])
                pairs.append((i, j, d))
        # Sort by distance (longest gaps need relays most)
        pairs.sort(key=lambda x: -x[2])

        # Assign assets to gaps
        assignment_idx = 0
        for pi, pj, gap_dist in pairs:
            if assignment_idx >= n_assets:
                break
            ep_i = self.endpoints[pi]
            ep_j = self.endpoints[pj]
            # How many relays needed for this gap?
            relays_needed = max(1, int(gap_dist / self.max_range))
            relays_for_gap = min(relays_needed, n_assets - assignment_idx)

            for r in range(relays_for_gap):
                if assignment_idx >= n_assets:
                    break
                aid = self.asset_ids[assignment_idx]
                a = assets.get(aid)
                if not a:
                    assignment_idx += 1
                    continue
                frac = (r + 1) / (relays_for_gap + 1)
                desired_lat = ep_i["lat"] + frac * (ep_j["lat"] - ep_i["lat"])
                desired_lng = ep_i["lng"] + frac * (ep_j["lng"] - ep_i["lng"])

                pos = a.get("position", a)
                pos["lat"] += (desired_lat - pos["lat"]) * self.speed * dt
                pos["lng"] += (desired_lng - pos["lng"]) * self.speed * dt
                assignment_idx += 1

        # Measure connectivity: check if all endpoints can reach each other
        # via relay chain within max_range
        all_nodes = list(self.endpoints)
        for aid in self.asset_ids:
            a = assets.get(aid)
            if a:
                p = a.get("position", a)
                all_nodes.append({"lat": p.get("lat", 0), "lng": p.get("lng", 0)})

        connected_pairs = 0
        total_pairs = 0
        for i in range(n_endpoints):
            for j in range(i + 1, n_endpoints):
                total_pairs += 1
                if self._can_reach(all_nodes, i, j):
                    connected_pairs += 1

        self.connectivity = connected_pairs / total_pairs if total_pairs > 0 else 0
        self.coverage_pct = self.connectivity * 100

        if self.connectivity >= 1.0:
            self.phase = "MESH_CONNECTED"
            events.append({
                "type": "MESH_CONNECTED", "behavior_id": self.id,
                "connectivity": self.connectivity,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return events

    def _can_reach(self, nodes, src_idx, dst_idx):
        """BFS to check if src can reach dst within max_range hops."""
        visited = {src_idx}
        queue = [src_idx]
        while queue:
            current = queue.pop(0)
            if current == dst_idx:
                return True
            cn = nodes[current]
            for ni in range(len(nodes)):
                if ni not in visited:
                    nn = nodes[ni]
                    if _dist_deg(cn["lat"], cn["lng"], nn["lat"], nn["lng"]) <= self.max_range:
                        visited.add(ni)
                        queue.append(ni)
        return False


# ═══════════════════════════════════════════════════════════
#  SEARCH SPIRAL — expanding spiral from last-known position
# ═══════════════════════════════════════════════════════════

class SearchSpiral(SwarmBehavior):
    """Expanding spiral search from a last-known position.

    Params:
        center: {lat, lng} — last-known position
        initial_radius_m: starting radius (default 100m)
        expansion_rate: how fast radius grows per tick (default 50m)
        max_radius_m: max search radius before declaring search complete (default 5000m)
        speed_factor: movement rate (default 0.05)
    """
    BEHAVIOR_TYPE = "SEARCH_SPIRAL"

    def __init__(self, behavior_id, swarm_id, asset_ids, params=None):
        super().__init__(behavior_id, swarm_id, asset_ids, params)
        center = self.params.get("center", {})
        self.center_lat = center.get("lat", 0)
        self.center_lng = center.get("lng", 0)
        self.radius = self.params.get("initial_radius_m", 100) * DEG_PER_M
        self.expansion_rate = self.params.get("expansion_rate", 50) * DEG_PER_M
        self.max_radius = self.params.get("max_radius_m", 5000) * DEG_PER_M
        self.speed = self.params.get("speed_factor", 0.05)
        self.spiral_angle = 0.0
        self.found_target = False

    def tick(self, assets, blackboard, dt=1.0):
        events = []
        if self.status != "active":
            return events
        self.tick_count += 1
        self.phase = "SEARCHING"

        # Check if target has been re-acquired
        if blackboard.get("target_reacquired"):
            self.found_target = True
            self.status = "completed"
            self.phase = "TARGET_FOUND"
            self.coverage_pct = 100.0
            events.append({
                "type": "SEARCH_TARGET_FOUND", "behavior_id": self.id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return events

        n = len(self.asset_ids)
        self.spiral_angle += 0.1 * dt

        # Each asset takes a different angular sector of the spiral
        for i, aid in enumerate(self.asset_ids):
            a = assets.get(aid)
            if not a:
                continue
            angle = self.spiral_angle + (2 * math.pi * i) / n
            desired_lat = self.center_lat + math.cos(angle) * self.radius
            desired_lng = self.center_lng + math.sin(angle) * self.radius

            pos = a.get("position", a)
            pos["lat"] += (desired_lat - pos["lat"]) * self.speed * dt
            pos["lng"] += (desired_lng - pos["lng"]) * self.speed * dt

        # Expand radius
        self.radius += self.expansion_rate * dt
        self.coverage_pct = min(100.0, (self.radius / self.max_radius) * 100)

        if self.radius >= self.max_radius:
            self.status = "completed"
            self.phase = "MAX_RADIUS_REACHED"
            self.coverage_pct = 100.0
            events.append({
                "type": "SEARCH_MAX_RADIUS", "behavior_id": self.id,
                "radius_deg": round(self.radius, 6),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return events


# ═══════════════════════════════════════════════════════════
#  BEHAVIOR CATALOG
# ═══════════════════════════════════════════════════════════

BEHAVIOR_CATALOG = {
    "PERIMETER_SCAN": {
        "class": PerimeterScan,
        "description": "Assets orbit a geofence polygon perimeter for surveillance",
        "min_assets": 2,
        "required_params": ["vertices"],
    },
    "AREA_SWEEP": {
        "class": AreaSweep,
        "description": "Parallel-track systematic area coverage (lawnmower pattern)",
        "min_assets": 1,
        "required_params": ["bounds"],
    },
    "DYNAMIC_TRACK": {
        "class": DynamicTrack,
        "description": "Swarm converges on and orbits a moving fused track",
        "min_assets": 2,
        "required_params": ["track_id"],
    },
    "RELAY_MESH": {
        "class": RelayMesh,
        "description": "Assets self-position to bridge communication gaps between endpoints",
        "min_assets": 1,
        "required_params": ["endpoints"],
    },
    "SEARCH_SPIRAL": {
        "class": SearchSpiral,
        "description": "Expanding spiral search from a last-known position",
        "min_assets": 1,
        "required_params": ["center"],
    },
}


# ═══════════════════════════════════════════════════════════
#  SWARM BEHAVIOR MANAGER
# ═══════════════════════════════════════════════════════════

class SwarmBehaviorManager:
    """Orchestrates active swarm behaviors, connects sensor fusion events
    to behavior triggers, and manages sub-task auctions."""

    def __init__(self):
        self._lock = threading.Lock()
        self.active_behaviors = {}   # id → SwarmBehavior
        self.completed = []          # recent completed behaviors
        self.event_log = []
        self.stats = {
            "behaviors_created": 0,
            "behaviors_completed": 0,
            "behaviors_cancelled": 0,
            "ticks": 0,
            "sensor_triggers": 0,
        }
        # Sensor fusion trigger rules
        self.auto_triggers = [
            {
                "id": "AUTOTRIG-TRACK-HOSTILE",
                "description": "Hostile fused track → spawn DYNAMIC_TRACK",
                "condition": lambda trk: trk.get("classification") == "HOSTILE" and trk.get("confidence", 0) > 0.6,
                "behavior": "DYNAMIC_TRACK",
                "params_fn": lambda trk: {"track_id": trk["id"], "initial_lat": trk["lat"], "initial_lng": trk["lng"]},
                "cooldown_sec": 30,
                "last_fired": 0,
                "enabled": True,
            },
            {
                "id": "AUTOTRIG-LOST-SEARCH",
                "description": "Track lost → spawn SEARCH_SPIRAL at last position",
                "condition": lambda trk: trk.get("status") == "LOST",
                "behavior": "SEARCH_SPIRAL",
                "params_fn": lambda trk: {"center": {"lat": trk.get("lat", 0), "lng": trk.get("lng", 0)}},
                "cooldown_sec": 60,
                "last_fired": 0,
                "enabled": True,
            },
        ]

    # ─── Create ──────────────────────────────────────

    def assign_behavior(self, behavior_type, swarm_id, asset_ids, params=None):
        """Create and activate a swarm behavior.

        Args:
            behavior_type: key from BEHAVIOR_CATALOG
            swarm_id: identifier for the swarm
            asset_ids: list of asset IDs to participate
            params: behavior-specific parameters

        Returns:
            dict with behavior info or error
        """
        if behavior_type not in BEHAVIOR_CATALOG:
            return {"error": f"Unknown behavior: {behavior_type}",
                    "available": list(BEHAVIOR_CATALOG.keys())}

        spec = BEHAVIOR_CATALOG[behavior_type]
        if len(asset_ids) < spec["min_assets"]:
            return {"error": f"{behavior_type} requires {spec['min_assets']}+ assets, got {len(asset_ids)}"}

        params = params or {}
        missing = [p for p in spec["required_params"] if p not in params]
        if missing:
            return {"error": f"Missing required params: {missing}"}

        bid = f"SB-{uuid.uuid4().hex[:8]}"
        behavior = spec["class"](bid, swarm_id, asset_ids, params)

        with self._lock:
            self.active_behaviors[bid] = behavior
            self.stats["behaviors_created"] += 1

        self._log("ASSIGN", bid, f"{behavior_type} → swarm {swarm_id} ({len(asset_ids)} assets)")
        return behavior.to_dict()

    # ─── Tick ────────────────────────────────────────

    def tick(self, assets, blackboard, dt=1.0):
        """Tick all active behaviors. Returns aggregated events."""
        events = []
        self.stats["ticks"] += 1
        with self._lock:
            to_remove = []
            for bid, behavior in self.active_behaviors.items():
                if behavior.status != "active":
                    continue
                try:
                    bev = behavior.tick(assets, blackboard, dt)
                    events.extend(bev)
                except Exception as e:
                    events.append({"type": "BEHAVIOR_ERROR", "behavior_id": bid, "error": str(e)})

                if behavior.status in ("completed", "cancelled"):
                    to_remove.append(bid)

            for bid in to_remove:
                b = self.active_behaviors.pop(bid)
                self.completed.append(b.to_dict())
                if len(self.completed) > 100:
                    self.completed = self.completed[-100:]
                if b.status == "completed":
                    self.stats["behaviors_completed"] += 1
                else:
                    self.stats["behaviors_cancelled"] += 1

        return events

    # ─── Sensor Fusion Triggers ──────────────────────

    def evaluate_sensor_triggers(self, fused_tracks, available_swarms):
        """Check fused tracks against auto-trigger rules.

        Args:
            fused_tracks: list of fused track dicts
            available_swarms: dict of swarm_id → {asset_ids: [...]}

        Returns:
            list of spawned behavior dicts
        """
        spawned = []
        now = time.time()
        for trigger in self.auto_triggers:
            if not trigger["enabled"]:
                continue
            if now - trigger["last_fired"] < trigger["cooldown_sec"]:
                continue
            for trk in fused_tracks:
                try:
                    if trigger["condition"](trk):
                        # Find a swarm to assign
                        for sid, swarm in available_swarms.items():
                            aids = swarm.get("asset_ids") or swarm.get("assets", [])
                            if len(aids) >= BEHAVIOR_CATALOG[trigger["behavior"]]["min_assets"]:
                                params = trigger["params_fn"](trk)
                                result = self.assign_behavior(
                                    trigger["behavior"], sid, aids, params)
                                if "error" not in result:
                                    spawned.append(result)
                                    trigger["last_fired"] = now
                                    self.stats["sensor_triggers"] += 1
                                    self._log("SENSOR_TRIGGER", trigger["id"],
                                              f"{trigger['behavior']} for track {trk.get('id')}")
                                break
                except Exception:
                    pass  # trigger condition evaluation failed
        return spawned

    # ─── Cancel / Query ──────────────────────────────

    def cancel_behavior(self, behavior_id):
        """Cancel an active behavior."""
        with self._lock:
            b = self.active_behaviors.get(behavior_id)
            if not b:
                return {"error": "Not found"}
            result = b.cancel()
            self.completed.append(b.to_dict())
            del self.active_behaviors[behavior_id]
            self.stats["behaviors_cancelled"] += 1
        self._log("CANCEL", behavior_id, "")
        return result

    def get_behavior(self, behavior_id):
        """Get a single behavior's state."""
        b = self.active_behaviors.get(behavior_id)
        if b:
            return b.to_dict()
        # Check completed
        for c in self.completed:
            if c["id"] == behavior_id:
                return c
        return None

    def list_active(self):
        """List all active behaviors."""
        return [b.to_dict() for b in self.active_behaviors.values()]

    def list_catalog(self):
        """List available behavior types."""
        return [
            {
                "type": k,
                "description": v["description"],
                "min_assets": v["min_assets"],
                "required_params": v["required_params"],
            }
            for k, v in BEHAVIOR_CATALOG.items()
        ]

    def get_triggers(self):
        """List auto-trigger rules."""
        return [
            {
                "id": t["id"],
                "description": t["description"],
                "behavior": t["behavior"],
                "cooldown_sec": t["cooldown_sec"],
                "enabled": t["enabled"],
            }
            for t in self.auto_triggers
        ]

    def toggle_trigger(self, trigger_id):
        """Enable/disable an auto-trigger."""
        for t in self.auto_triggers:
            if t["id"] == trigger_id:
                t["enabled"] = not t["enabled"]
                return {"id": trigger_id, "enabled": t["enabled"]}
        return {"error": "Trigger not found"}

    def summary(self):
        """Dashboard summary."""
        return {
            "active_count": len(self.active_behaviors),
            "completed_count": len(self.completed),
            "catalog_count": len(BEHAVIOR_CATALOG),
            "triggers_enabled": sum(1 for t in self.auto_triggers if t["enabled"]),
            "stats": dict(self.stats),
        }

    # ─── Internal ────────────────────────────────────

    def _log(self, action, bid, details=""):
        self.event_log.append({
            "action": action, "id": bid, "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self.event_log) > 500:
            self.event_log = self.event_log[-500:]
