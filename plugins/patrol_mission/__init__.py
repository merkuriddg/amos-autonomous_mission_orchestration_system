"""AMOS Plugin — Patrol Mission Pack.

Production patrol mission pack providing advanced route planning,
loiter patterns, sensor sweep modes, and real-time re-routing when
threats are detected along the patrol path.
"""

import math
from core.plugin_base import PluginBase


class PatrolMissionPlugin(PluginBase):
    """Advanced patrol mission pack."""

    PLUGIN_NAME = "patrol_mission"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "mission_pack"

    # ── Mission Templates ──────────────────────────────────

    TEMPLATES = [
        {
            "id": "linear_patrol",
            "name": "Linear Patrol",
            "description": "Point-to-point patrol along a defined route with optional return leg.",
            "domain": "multi",
            "min_assets": 1,
            "tasks": [
                {"type": "navigate", "desc": "Move to start point"},
                {"type": "patrol",   "desc": "Follow waypoint route"},
                {"type": "observe",  "desc": "Sensor sweep during transit"},
                {"type": "report",   "desc": "Report contacts to HQ"},
            ],
            "parameters": {
                "waypoints": "list[{lat,lng}]",
                "speed_kts": "int  (default 25)",
                "altitude_ft": "int  (default 200, air assets only)",
                "sensor_mode": "active | passive | auto",
                "return_leg": "bool (default true)",
            },
        },
        {
            "id": "orbit_patrol",
            "name": "Orbit / Race-Track Patrol",
            "description": "Continuous orbit (race-track) around a reference point at configurable radius.",
            "domain": "air",
            "min_assets": 1,
            "tasks": [
                {"type": "navigate", "desc": "Transit to orbit entry"},
                {"type": "orbit",    "desc": "Execute race-track pattern"},
                {"type": "observe",  "desc": "Continuous sensor coverage"},
                {"type": "report",   "desc": "Relay detections"},
            ],
            "parameters": {
                "center": "{lat,lng}",
                "radius_nm": "float  (default 2.0)",
                "altitude_ft": "int   (default 5000)",
                "direction": "cw | ccw  (default cw)",
                "legs": "int  orbit count (default 0 = unlimited)",
            },
        },
        {
            "id": "sector_sweep",
            "name": "Sector Sweep",
            "description": "Fan-shaped sweep of a defined sector, useful for clearing an area ahead of a convoy.",
            "domain": "multi",
            "min_assets": 1,
            "tasks": [
                {"type": "navigate",    "desc": "Move to sector origin"},
                {"type": "sweep",       "desc": "Execute sector scan"},
                {"type": "classify",    "desc": "Classify contacts"},
                {"type": "clear_report","desc": "Report sector clear / threat"},
            ],
            "parameters": {
                "origin": "{lat,lng}",
                "bearing_deg": "int  centre-line bearing",
                "width_deg": "int  sector width (default 90)",
                "depth_nm": "float  sweep depth (default 5.0)",
                "legs": "int  number of sweep lines (default 5)",
            },
        },
    ]

    WORKFLOWS = [
        {
            "id": "standard_patrol",
            "name": "Standard Patrol Workflow",
            "steps": [
                {"action": "assign_assets",     "desc": "Select available assets"},
                {"action": "generate_waypoints","desc": "Create patrol route"},
                {"action": "brief_operator",    "desc": "Display mission brief"},
                {"action": "execute",           "desc": "Begin patrol execution"},
                {"action": "monitor",           "desc": "Continuous monitoring loop"},
                {"action": "reroute_on_threat", "desc": "Dynamic reroute if threat detected"},
                {"action": "debrief",           "desc": "Generate patrol AAR summary"},
            ],
        },
    ]

    # ── Lifecycle ──────────────────────────────────────────

    def on_activate(self, event_bus) -> None:
        self.subscribe("mission.template_requested", self._on_template_request)
        self.subscribe("threat.detected", self._on_threat_reroute)
        self.emit("mission_pack.registered", {
            "pack": self.PLUGIN_NAME,
            "templates": [t["id"] for t in self.TEMPLATES],
        })

    def get_capabilities(self) -> list[str]:
        return [
            "mission_templates", "waypoint_generation",
            "orbit_pattern", "sector_sweep", "dynamic_reroute",
        ]

    # ── Template / Waypoint Generation ─────────────────────

    def get_templates(self) -> list[dict]:
        return self.TEMPLATES

    def get_workflows(self) -> list[dict]:
        return self.WORKFLOWS

    def generate_waypoints(self, template_id: str, params: dict) -> list[dict]:
        dispatch = {
            "linear_patrol": self._gen_linear,
            "orbit_patrol":  self._gen_orbit,
            "sector_sweep":  self._gen_sector,
        }
        fn = dispatch.get(template_id)
        return fn(params) if fn else []

    # ── Generators ─────────────────────────────────────────

    @staticmethod
    def _gen_linear(p: dict) -> list[dict]:
        wps = p.get("waypoints", [])
        alt = p.get("altitude_ft", 200)
        spd = p.get("speed_kts", 25)
        out: list[dict] = []
        for i, w in enumerate(wps):
            out.append({
                "seq": i + 1, "lat": w["lat"], "lng": w["lng"],
                "alt_ft": alt, "speed_kts": spd, "action": "patrol",
            })
        if p.get("return_leg", True) and len(wps) > 1:
            for i, w in enumerate(reversed(wps[:-1]), start=len(wps) + 1):
                out.append({
                    "seq": i, "lat": w["lat"], "lng": w["lng"],
                    "alt_ft": alt, "speed_kts": spd, "action": "return",
                })
        return out

    @staticmethod
    def _gen_orbit(p: dict) -> list[dict]:
        c = p.get("center", {})
        r_nm = p.get("radius_nm", 2.0)
        alt = p.get("altitude_ft", 5000)
        direction = 1 if p.get("direction", "cw") == "cw" else -1
        points = 12  # 30° increments
        r_deg = r_nm / 60.0
        out: list[dict] = []
        for i in range(points):
            angle = math.radians(direction * i * 30)
            out.append({
                "seq": i + 1,
                "lat": c.get("lat", 0) + r_deg * math.cos(angle),
                "lng": c.get("lng", 0) + r_deg * math.sin(angle),
                "alt_ft": alt, "action": "orbit",
            })
        out.append({"seq": points + 1, **out[0], "action": "loop_start"})
        return out

    @staticmethod
    def _gen_sector(p: dict) -> list[dict]:
        origin = p.get("origin", {})
        bearing = p.get("bearing_deg", 0)
        width = p.get("width_deg", 90)
        depth = p.get("depth_nm", 5.0)
        legs = p.get("legs", 5)
        d_deg = depth / 60.0
        out: list[dict] = []
        half = width / 2.0
        for i in range(legs):
            angle = math.radians(bearing - half + (width / max(legs - 1, 1)) * i)
            out.append({
                "seq": i + 1,
                "lat": origin.get("lat", 0) + d_deg * math.cos(angle),
                "lng": origin.get("lng", 0) + d_deg * math.sin(angle),
                "action": "sweep",
            })
            # return to origin between legs
            out.append({
                "seq": i + 1, "lat": origin.get("lat", 0),
                "lng": origin.get("lng", 0), "action": "return_origin",
            })
        return out

    # ── Event Handlers ─────────────────────────────────────

    def _on_template_request(self, event):
        self.emit("mission_pack.templates", {
            "pack": self.PLUGIN_NAME, "templates": self.TEMPLATES,
        })

    def _on_threat_reroute(self, event):
        """Emit reroute advisory when threat appears on patrol path."""
        if event.payload and event.payload.get("on_patrol_route"):
            self.emit("patrol.reroute_advisory", {
                "threat_id": event.payload.get("threat_id"),
                "original_wp": event.payload.get("nearest_wp"),
            })
