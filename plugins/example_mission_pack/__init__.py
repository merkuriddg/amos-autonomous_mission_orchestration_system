"""AMOS Plugin — Example Mission Pack (Patrol).

Reference implementation of an AMOS mission-pack plugin.  Copy this
directory and customize it to create domain-specific mission templates.

This example provides a simple perimeter patrol mission template with
waypoint generation and task workflows.

Plugin lifecycle:
    on_load → on_register → on_activate → (operate) → on_shutdown
"""

from core.plugin_base import PluginBase


class ExampleMissionPackPlugin(PluginBase):
    """Patrol mission pack — reference implementation."""

    PLUGIN_NAME = "example_mission_pack"
    PLUGIN_VERSION = "1.0"
    PLUGIN_TYPE = "mission_pack"

    # ── Mission templates ─────────────────────────────────
    TEMPLATES = [
        {
            "id": "perimeter_patrol",
            "name": "Perimeter Patrol",
            "description": "Continuous patrol of a defined perimeter using one or more assets.",
            "domain": "multi",
            "min_assets": 1,
            "tasks": [
                {"type": "navigate", "description": "Move to patrol start point"},
                {"type": "patrol", "description": "Follow waypoint loop"},
                {"type": "observe", "description": "Monitor sensors during patrol"},
                {"type": "report", "description": "Report anomalies to operator"},
            ],
            "constraints": [
                {"type": "geofence", "description": "Stay within patrol boundary"},
                {"type": "altitude", "description": "Maintain assigned altitude band"},
                {"type": "speed", "description": "Maintain patrol speed"},
            ],
            "parameters": {
                "waypoints": "list of lat/lng points defining the patrol route",
                "loop": "whether to loop continuously (default: true)",
                "speed_kts": "patrol speed in knots",
                "altitude_ft": "patrol altitude for air assets",
                "sensor_mode": "active | passive | auto",
            },
        },
        {
            "id": "area_search",
            "name": "Area Search",
            "description": "Systematic search of a defined area using parallel tracks.",
            "domain": "multi",
            "min_assets": 1,
            "tasks": [
                {"type": "navigate", "description": "Move to search area start"},
                {"type": "search", "description": "Execute parallel track pattern"},
                {"type": "classify", "description": "Classify any detections"},
                {"type": "report", "description": "Report findings"},
            ],
            "constraints": [
                {"type": "geofence", "description": "Stay within search area"},
                {"type": "coverage", "description": "Ensure full area coverage"},
            ],
            "parameters": {
                "area": "polygon defining the search area",
                "track_spacing_m": "distance between parallel tracks",
                "orientation_deg": "search track heading",
            },
        },
    ]

    WORKFLOWS = [
        {
            "id": "patrol_workflow",
            "name": "Standard Patrol Workflow",
            "steps": [
                {"action": "assign_assets", "description": "Select available assets"},
                {"action": "generate_waypoints", "description": "Create patrol route"},
                {"action": "brief_operator", "description": "Display mission brief"},
                {"action": "execute", "description": "Begin patrol execution"},
                {"action": "monitor", "description": "Continuous monitoring"},
                {"action": "debrief", "description": "Generate patrol summary"},
            ],
        },
    ]

    # ── Lifecycle ──────────────────────────────────────────
    def on_activate(self, event_bus) -> None:
        """Register mission templates with the platform."""
        self.subscribe("mission.template_requested", self._on_template_request)
        self.emit("mission_pack.registered", {
            "pack": self.PLUGIN_NAME,
            "templates": len(self.TEMPLATES),
            "workflows": len(self.WORKFLOWS),
        })

    def on_shutdown(self) -> None:
        self.emit("mission_pack.unregistered", {"pack": self.PLUGIN_NAME})

    def get_capabilities(self) -> list[str]:
        return ["mission_templates", "task_workflows", "waypoint_generation"]

    # ── Mission pack contract ─────────────────────────────
    def get_templates(self) -> list[dict]:
        """Return available mission templates."""
        return self.TEMPLATES

    def get_workflows(self) -> list[dict]:
        """Return task workflow definitions."""
        return self.WORKFLOWS

    def generate_waypoints(self, template_id: str, params: dict) -> list[dict]:
        """Generate mission waypoints from template + parameters.

        Parameters
        ----------
        template_id : str
            ID of the mission template to use.
        params : dict
            Mission parameters (area, speed, altitude, etc.).

        Returns
        -------
        list[dict]
            List of waypoints: [{lat, lng, alt_ft, action, sequence}]
        """
        if template_id == "perimeter_patrol":
            return self._generate_patrol_waypoints(params)
        elif template_id == "area_search":
            return self._generate_search_waypoints(params)
        return []

    def _generate_patrol_waypoints(self, params):
        """Generate waypoints for a perimeter patrol."""
        waypoints = params.get("waypoints", [])
        altitude = params.get("altitude_ft", 200)
        result = []
        for i, wp in enumerate(waypoints):
            result.append({
                "sequence": i + 1,
                "lat": wp["lat"],
                "lng": wp["lng"],
                "alt_ft": altitude,
                "action": "patrol",
                "speed_kts": params.get("speed_kts", 30),
            })
        # Close the loop if requested
        if params.get("loop", True) and waypoints:
            result.append({
                "sequence": len(waypoints) + 1,
                "lat": waypoints[0]["lat"],
                "lng": waypoints[0]["lng"],
                "alt_ft": altitude,
                "action": "loop_start",
                "speed_kts": params.get("speed_kts", 30),
            })
        return result

    def _generate_search_waypoints(self, params):
        """Generate parallel-track search waypoints (simplified)."""
        # Real implementation would compute lawnmower pattern from polygon
        return [{"sequence": 1, "lat": 0, "lng": 0, "action": "search_start"}]

    # ── Event handlers ────────────────────────────────────
    def _on_template_request(self, event):
        """Handle template listing requests."""
        self.emit("mission_pack.templates", {
            "pack": self.PLUGIN_NAME,
            "templates": self.TEMPLATES,
        })
