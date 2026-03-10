"""AMOS Plugin — Perimeter Security Mission Pack.

Provides perimeter-defence mission templates: static sensor overwatch,
roving security patrol, and layered tripwire zones.  Reacts to
intrusion events by dispatching QRF assets to the breach point.
"""

import math
from core.plugin_base import PluginBase


class PerimeterSecurityMissionPlugin(PluginBase):
    """Perimeter Security mission pack."""

    PLUGIN_NAME = "perimeter_security_mission"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "mission_pack"

    # ── Templates ──────────────────────────────────────────

    TEMPLATES = [
        {
            "id": "static_overwatch",
            "name": "Static Overwatch",
            "description": (
                "Position assets at fixed observation points around "
                "a defended perimeter for continuous surveillance."
            ),
            "domain": "multi",
            "min_assets": 2,
            "tasks": [
                {"type": "navigate",  "desc": "Move to overwatch position"},
                {"type": "observe",   "desc": "Maintain sensor coverage"},
                {"type": "alert",     "desc": "Report intrusions instantly"},
                {"type": "handoff",   "desc": "Hand-off to QRF on breach"},
            ],
            "parameters": {
                "perimeter": "list[{lat,lng}]  polygon vertices",
                "positions": "int  number of overwatch points (default: auto)",
                "sensor_range_m": "int  assumed sensor range (default 500)",
                "altitude_ft": "int  (air assets, default 300)",
            },
        },
        {
            "id": "roving_patrol",
            "name": "Roving Security Patrol",
            "description": (
                "Continuous patrol along the perimeter boundary with "
                "random timing variation to avoid predictability."
            ),
            "domain": "multi",
            "min_assets": 1,
            "tasks": [
                {"type": "navigate", "desc": "Move to patrol start"},
                {"type": "patrol",   "desc": "Follow perimeter route"},
                {"type": "loiter",   "desc": "Random dwell at checkpoints"},
                {"type": "report",   "desc": "Report anomalies"},
            ],
            "parameters": {
                "perimeter": "list[{lat,lng}]",
                "speed_kts": "int  patrol speed (default 15)",
                "dwell_sec": "int  max random dwell (default 120)",
                "loops": "int  number of loops (default 0 = unlimited)",
            },
        },
        {
            "id": "tripwire_zones",
            "name": "Layered Tripwire Zones",
            "description": (
                "Concentric buffer zones around a defended area.  "
                "Outer zones provide early warning; inner zones trigger QRF."
            ),
            "domain": "multi",
            "min_assets": 3,
            "tasks": [
                {"type": "deploy",   "desc": "Position sensors / assets at zone boundaries"},
                {"type": "monitor",  "desc": "Watch for zone breaches"},
                {"type": "escalate", "desc": "Escalate alerts per zone severity"},
                {"type": "respond",  "desc": "Dispatch QRF to breach sector"},
            ],
            "parameters": {
                "center": "{lat,lng}  defended point",
                "zones": "int  number of rings (default 3)",
                "outer_radius_m": "int  outermost ring radius (default 2000)",
                "assets_per_zone": "int  (default 1)",
            },
        },
    ]

    WORKFLOWS = [
        {
            "id": "perimeter_defense",
            "name": "Perimeter Defense Workflow",
            "steps": [
                {"action": "define_perimeter",  "desc": "Draw or import perimeter polygon"},
                {"action": "assign_assets",     "desc": "Allocate assets to positions/routes"},
                {"action": "deploy",            "desc": "Move assets to stations"},
                {"action": "activate_sensors",  "desc": "Enable sensor coverage"},
                {"action": "monitor",           "desc": "Continuous watch"},
                {"action": "breach_response",   "desc": "QRF dispatch on intrusion"},
                {"action": "secure",            "desc": "Re-establish perimeter"},
                {"action": "debrief",           "desc": "AAR & lessons learned"},
            ],
        },
    ]

    # ── Lifecycle ──────────────────────────────────────────

    def on_activate(self, event_bus) -> None:
        self.subscribe("mission.template_requested", self._on_template_request)
        self.subscribe("geofence.breach", self._on_breach)
        self.emit("mission_pack.registered", {
            "pack": self.PLUGIN_NAME,
            "templates": [t["id"] for t in self.TEMPLATES],
        })

    def get_capabilities(self) -> list[str]:
        return [
            "mission_templates", "waypoint_generation",
            "static_overwatch", "roving_patrol", "tripwire_zones",
            "breach_response", "qrf_dispatch",
        ]

    # ── Waypoint Generation ────────────────────────────────

    def get_templates(self) -> list[dict]:
        return self.TEMPLATES

    def get_workflows(self) -> list[dict]:
        return self.WORKFLOWS

    def generate_waypoints(self, template_id: str, params: dict) -> list[dict]:
        dispatch = {
            "static_overwatch": self._gen_overwatch,
            "roving_patrol":    self._gen_roving,
            "tripwire_zones":   self._gen_tripwire,
        }
        fn = dispatch.get(template_id)
        return fn(params) if fn else []

    # ── Generators ─────────────────────────────────────────

    @staticmethod
    def _gen_overwatch(p: dict) -> list[dict]:
        """Evenly distribute overwatch positions along the perimeter."""
        perimeter = p.get("perimeter", [])
        if not perimeter:
            return []
        n = p.get("positions") or max(2, len(perimeter))
        alt = p.get("altitude_ft", 300)
        out: list[dict] = []
        total = len(perimeter)
        step = max(1, total // n)
        for i in range(0, total, step):
            pt = perimeter[i % total]
            out.append({
                "seq": len(out) + 1, "lat": pt["lat"], "lng": pt["lng"],
                "alt_ft": alt, "action": "overwatch",
            })
        return out

    @staticmethod
    def _gen_roving(p: dict) -> list[dict]:
        """Patrol route that follows the perimeter polygon and closes the loop."""
        perimeter = p.get("perimeter", [])
        spd = p.get("speed_kts", 15)
        out: list[dict] = []
        for i, pt in enumerate(perimeter):
            out.append({
                "seq": i + 1, "lat": pt["lat"], "lng": pt["lng"],
                "speed_kts": spd, "action": "patrol",
            })
        if perimeter:
            out.append({
                "seq": len(perimeter) + 1,
                "lat": perimeter[0]["lat"], "lng": perimeter[0]["lng"],
                "speed_kts": spd, "action": "loop_start",
            })
        return out

    @staticmethod
    def _gen_tripwire(p: dict) -> list[dict]:
        """Generate concentric ring waypoints around the defended center."""
        center = p.get("center", {})
        zones = p.get("zones", 3)
        outer_r = p.get("outer_radius_m", 2000)
        per_zone = p.get("assets_per_zone", 1)

        clat, clng = center.get("lat", 0), center.get("lng", 0)
        out: list[dict] = []
        seq = 1
        for z in range(1, zones + 1):
            r_m = outer_r * z / zones
            r_deg = r_m / 111_320.0
            pts = max(4, per_zone * 4)
            for i in range(pts):
                angle = math.radians(i * (360 / pts))
                out.append({
                    "seq": seq,
                    "lat": clat + r_deg * math.cos(angle),
                    "lng": clng + r_deg * math.sin(angle),
                    "zone": z,
                    "action": f"tripwire_z{z}",
                })
                seq += 1
        return out

    # ── Event Handlers ─────────────────────────────────────

    def _on_template_request(self, event):
        self.emit("mission_pack.templates", {
            "pack": self.PLUGIN_NAME, "templates": self.TEMPLATES,
        })

    def _on_breach(self, event):
        """On geofence breach, emit QRF dispatch advisory."""
        payload = event.payload or {}
        self.emit("perimeter.breach_alert", {
            "geofence_id": payload.get("geofence_id"),
            "asset_id": payload.get("asset_id"),
            "lat": payload.get("lat"),
            "lng": payload.get("lng"),
            "severity": payload.get("zone", "unknown"),
        })
