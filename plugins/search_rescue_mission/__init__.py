"""AMOS Plugin — Search & Rescue Mission Pack.

Provides SAR-specific mission templates including expanding-square
search, parallel track, and creeping-line-ahead patterns.  Includes
casualty detection event handling and extraction workflows.
"""

import math
from core.plugin_base import PluginBase


class SearchRescueMissionPlugin(PluginBase):
    """Search & Rescue mission pack."""

    PLUGIN_NAME = "search_rescue_mission"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "mission_pack"

    # ── Templates ──────────────────────────────────────────

    TEMPLATES = [
        {
            "id": "expanding_square",
            "name": "Expanding Square Search",
            "description": (
                "Spiral outward from a datum point — best when the "
                "last-known position is fairly accurate."
            ),
            "domain": "multi",
            "min_assets": 1,
            "tasks": [
                {"type": "navigate",   "desc": "Transit to datum"},
                {"type": "search",     "desc": "Execute expanding square"},
                {"type": "detect",     "desc": "Mark any contacts / survivors"},
                {"type": "report",     "desc": "Report findings"},
            ],
            "parameters": {
                "datum": "{lat,lng}  last-known position",
                "initial_leg_nm": "float  first leg length (default 0.5)",
                "track_spacing_nm": "float  spacing between legs (default 0.25)",
                "max_legs": "int  stop after N legs (default 20)",
            },
        },
        {
            "id": "parallel_track",
            "name": "Parallel Track Search",
            "description": (
                "Systematic lawnmower pattern across a rectangular area — "
                "best for wide-area search with multiple assets."
            ),
            "domain": "multi",
            "min_assets": 1,
            "tasks": [
                {"type": "navigate", "desc": "Transit to search area"},
                {"type": "search",   "desc": "Execute parallel tracks"},
                {"type": "detect",   "desc": "Mark contacts"},
                {"type": "report",   "desc": "Report findings"},
            ],
            "parameters": {
                "corner_sw": "{lat,lng}  SW corner of search box",
                "corner_ne": "{lat,lng}  NE corner of search box",
                "track_spacing_nm": "float  (default 0.25)",
                "orientation_deg": "int  track heading (default 0 = N-S)",
            },
        },
        {
            "id": "creeping_line",
            "name": "Creeping Line Ahead",
            "description": (
                "Back-and-forth tracks advancing toward a reference "
                "bearing — ideal when drift is predictable."
            ),
            "domain": "multi",
            "min_assets": 1,
            "tasks": [
                {"type": "navigate", "desc": "Transit to start"},
                {"type": "search",   "desc": "Execute creeping line"},
                {"type": "detect",   "desc": "Mark detections"},
                {"type": "report",   "desc": "Report"},
            ],
            "parameters": {
                "start": "{lat,lng}",
                "bearing_deg": "int  advance direction",
                "track_length_nm": "float  (default 5.0)",
                "track_spacing_nm": "float  (default 0.25)",
                "tracks": "int  number of legs (default 10)",
            },
        },
    ]

    WORKFLOWS = [
        {
            "id": "sar_standard",
            "name": "Standard SAR Workflow",
            "steps": [
                {"action": "alert_received",   "desc": "SAR alert / EPIRB trigger"},
                {"action": "plan_search",      "desc": "Select pattern & assign assets"},
                {"action": "brief_teams",      "desc": "Briefing & comms check"},
                {"action": "execute_search",   "desc": "Run search pattern"},
                {"action": "casualty_detected","desc": "Mark & classify survivor"},
                {"action": "extract",          "desc": "Dispatch extraction asset"},
                {"action": "medevac",          "desc": "Casualty evacuation"},
                {"action": "debrief",          "desc": "AAR & lessons learned"},
            ],
        },
    ]

    # ── Lifecycle ──────────────────────────────────────────

    def on_activate(self, event_bus) -> None:
        self.subscribe("mission.template_requested", self._on_template_request)
        self.subscribe("sensor.contact_detected", self._on_contact)
        self.emit("mission_pack.registered", {
            "pack": self.PLUGIN_NAME,
            "templates": [t["id"] for t in self.TEMPLATES],
        })

    def get_capabilities(self) -> list[str]:
        return [
            "mission_templates", "waypoint_generation",
            "expanding_square", "parallel_track", "creeping_line",
            "casualty_detection", "extraction_workflow",
        ]

    # ── Waypoint Generation ────────────────────────────────

    def get_templates(self) -> list[dict]:
        return self.TEMPLATES

    def get_workflows(self) -> list[dict]:
        return self.WORKFLOWS

    def generate_waypoints(self, template_id: str, params: dict) -> list[dict]:
        dispatch = {
            "expanding_square": self._gen_expanding_square,
            "parallel_track":   self._gen_parallel_track,
            "creeping_line":    self._gen_creeping_line,
        }
        fn = dispatch.get(template_id)
        return fn(params) if fn else []

    # ── Pattern generators ─────────────────────────────────

    @staticmethod
    def _gen_expanding_square(p: dict) -> list[dict]:
        datum = p.get("datum", {})
        leg = p.get("initial_leg_nm", 0.5)
        spacing = p.get("track_spacing_nm", 0.25)
        max_legs = p.get("max_legs", 20)

        lat, lng = datum.get("lat", 0), datum.get("lng", 0)
        out: list[dict] = [{"seq": 1, "lat": lat, "lng": lng, "action": "datum"}]
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # E, N, W, S
        current_leg = leg
        seq = 2
        for i in range(max_legs):
            dlat, dlng = directions[i % 4]
            lat += dlat * current_leg / 60.0
            lng += dlng * current_leg / 60.0
            out.append({"seq": seq, "lat": lat, "lng": lng, "action": "search"})
            seq += 1
            if i % 2 == 1:
                current_leg += spacing
        return out

    @staticmethod
    def _gen_parallel_track(p: dict) -> list[dict]:
        sw = p.get("corner_sw", {})
        ne = p.get("corner_ne", {})
        spacing = p.get("track_spacing_nm", 0.25) / 60.0
        orient = math.radians(p.get("orientation_deg", 0))

        lat0, lng0 = sw.get("lat", 0), sw.get("lng", 0)
        lat1, lng1 = ne.get("lat", 0), ne.get("lng", 0)

        out: list[dict] = []
        seq = 1
        x = lng0
        flip = False
        while x <= lng1:
            if flip:
                out.append({"seq": seq, "lat": lat1, "lng": x, "action": "search"})
                out.append({"seq": seq + 1, "lat": lat0, "lng": x, "action": "search"})
            else:
                out.append({"seq": seq, "lat": lat0, "lng": x, "action": "search"})
                out.append({"seq": seq + 1, "lat": lat1, "lng": x, "action": "search"})
            flip = not flip
            seq += 2
            x += spacing
        return out

    @staticmethod
    def _gen_creeping_line(p: dict) -> list[dict]:
        start = p.get("start", {})
        bearing = math.radians(p.get("bearing_deg", 0))
        trk_len = p.get("track_length_nm", 5.0) / 60.0
        spacing = p.get("track_spacing_nm", 0.25) / 60.0
        tracks = p.get("tracks", 10)

        lat, lng = start.get("lat", 0), start.get("lng", 0)
        out: list[dict] = []
        seq = 1
        for i in range(tracks):
            # Search leg (perpendicular to advance bearing)
            perp = bearing + math.pi / 2
            direction = 1 if i % 2 == 0 else -1
            end_lat = lat + direction * trk_len * math.cos(perp)
            end_lng = lng + direction * trk_len * math.sin(perp)
            out.append({"seq": seq, "lat": end_lat, "lng": end_lng, "action": "search"})
            seq += 1
            # Advance along bearing
            lat += spacing * math.cos(bearing)
            lng += spacing * math.sin(bearing)
            out.append({"seq": seq, "lat": lat, "lng": lng, "action": "advance"})
            seq += 1
        return out

    # ── Event Handlers ─────────────────────────────────────

    def _on_template_request(self, event):
        self.emit("mission_pack.templates", {
            "pack": self.PLUGIN_NAME, "templates": self.TEMPLATES,
        })

    def _on_contact(self, event):
        """When a sensor contact is classified as a survivor, emit extraction event."""
        payload = event.payload or {}
        if payload.get("classification") in ("survivor", "casualty", "person"):
            self.emit("sar.casualty_detected", {
                "contact_id": payload.get("contact_id"),
                "lat": payload.get("lat"),
                "lng": payload.get("lng"),
                "classification": payload.get("classification"),
            })
