#!/usr/bin/env python3
"""AMOS Plugin Scaffolding Tool.

Generate a new plugin skeleton with the correct structure, lifecycle
hooks, and boilerplate for any of the 6 supported plugin types.

Usage:
    python3 tools/create_plugin.py my_sensor --type sensor_adapter
    python3 tools/create_plugin.py patrol_pack --type mission_pack
    python3 tools/create_plugin.py my_drone --type asset_adapter
"""

import argparse
import os
import sys
import textwrap

PLUGIN_TYPES = {
    "asset_adapter": {
        "domain": "air",
        "capabilities": '["telemetry", "command", "health"]',
        "description": "Asset adapter — bridges a robotic platform into AMOS.",
        "extra_imports": "import uuid\nfrom datetime import datetime, timezone",
        "extra_methods": textwrap.dedent("""\

            def __init__(self):
                super().__init__()
                self.asset_id = f"{name_upper}-{{uuid.uuid4().hex[:4].upper()}}"

            # ── Asset contract ──────────────────────────────────────
            def get_telemetry(self) -> dict:
                \"\"\"Return current telemetry snapshot.\"\"\"
                return {{
                    "asset_id": self.asset_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "position": {{"lat": 0.0, "lng": 0.0, "alt_ft": 0}},
                    "speed_kts": 0,
                    "heading_deg": 0,
                    "battery_pct": 100,
                }}

            def send_command(self, command: dict) -> dict:
                \"\"\"Accept a command from AMOS.\"\"\"
                return {{
                    "status": "accepted",
                    "asset_id": self.asset_id,
                    "command_type": command.get("type", "unknown"),
                }}
        """),
        "activate_body": textwrap.dedent("""\
                self.subscribe("command.issued", self._on_command)
                self.emit("asset.registered", {{
                    "asset_id": self.asset_id,
                    "plugin": self.PLUGIN_NAME,
                }})"""),
        "extra_handlers": textwrap.dedent("""\

            def _on_command(self, event) -> None:
                \"\"\"Handle incoming commands.\"\"\"
                payload = event.payload or {{}}
                if payload.get("target") == self.asset_id:
                    self.emit("command.acknowledged", {{
                        "asset_id": self.asset_id,
                        "command": payload.get("type", "unknown"),
                    }})
        """),
    },
    "sensor_adapter": {
        "domain": "multi",
        "capabilities": '["observations", "health"]',
        "description": "Sensor adapter — integrates an external sensor feed into AMOS.",
        "extra_imports": "from datetime import datetime, timezone",
        "extra_methods": textwrap.dedent("""\

            def get_observations(self) -> list[dict]:
                \"\"\"Return latest sensor observations.\"\"\"
                return [{{
                    "sensor": self.PLUGIN_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "detection",
                    "position": {{"lat": 0.0, "lng": 0.0}},
                    "confidence": 0.0,
                    "raw": {{}},
                }}]
        """),
        "activate_body": textwrap.dedent("""\
                self.emit("sensor.registered", {{
                    "sensor": self.PLUGIN_NAME,
                }})"""),
        "extra_handlers": "",
    },
    "mission_pack": {
        "domain": "multi",
        "capabilities": '["mission_templates", "task_workflows"]',
        "description": "Mission pack — provides domain-specific mission templates and workflows.",
        "extra_imports": "",
        "extra_methods": textwrap.dedent("""\

            def get_templates(self) -> list[dict]:
                \"\"\"Return available mission templates.\"\"\"
                return [{{
                    "id": "{name}_default",
                    "name": "{class_name} Default",
                    "description": "Default mission template",
                    "tasks": [],
                    "constraints": [],
                }}]

            def get_workflows(self) -> list[dict]:
                \"\"\"Return task workflow definitions.\"\"\"
                return []
        """),
        "activate_body": textwrap.dedent("""\
                self.emit("mission_pack.registered", {{
                    "pack": self.PLUGIN_NAME,
                    "templates": len(self.get_templates()),
                }})"""),
        "extra_handlers": "",
    },
    "planner": {
        "domain": "multi",
        "capabilities": '["planning", "replanning"]',
        "description": "Planner plugin — provides mission planning algorithms.",
        "extra_imports": "",
        "extra_methods": textwrap.dedent("""\

            def generate_plan(self, mission: dict) -> dict:
                \"\"\"Generate a mission plan for the given mission parameters.\"\"\"
                return {{
                    "planner": self.PLUGIN_NAME,
                    "mission_id": mission.get("id", "unknown"),
                    "tasks": [],
                    "estimated_duration_sec": 0,
                }}

            def replan(self, mission: dict, reason: str) -> dict:
                \"\"\"Replan an active mission due to changed conditions.\"\"\"
                return self.generate_plan(mission)
        """),
        "activate_body": textwrap.dedent("""\
                self.subscribe("mission.plan_requested", self._on_plan_request)
                self.emit("planner.registered", {{
                    "planner": self.PLUGIN_NAME,
                }})"""),
        "extra_handlers": textwrap.dedent("""\

            def _on_plan_request(self, event) -> None:
                \"\"\"Handle planning requests from the mission manager.\"\"\"
                mission = event.payload or {{}}
                plan = self.generate_plan(mission)
                self.emit("planner.plan_ready", plan)
        """),
    },
    "analytics": {
        "domain": "multi",
        "capabilities": '["analytics", "reports"]',
        "description": "Analytics plugin — provides data analysis and decision support.",
        "extra_imports": "",
        "extra_methods": textwrap.dedent("""\

            def analyze(self, data: dict) -> dict:
                \"\"\"Analyze mission data and return insights.\"\"\"
                return {{
                    "analyzer": self.PLUGIN_NAME,
                    "insights": [],
                    "recommendations": [],
                }}

            def generate_report(self) -> dict:
                \"\"\"Generate an analytical report.\"\"\"
                return {{
                    "report": self.PLUGIN_NAME,
                    "sections": [],
                }}
        """),
        "activate_body": textwrap.dedent("""\
                self.subscribe("telemetry.*", self._on_telemetry)
                self.emit("analytics.registered", {{
                    "analyzer": self.PLUGIN_NAME,
                }})"""),
        "extra_handlers": textwrap.dedent("""\

            def _on_telemetry(self, event) -> None:
                \"\"\"Process incoming telemetry for analysis.\"\"\"
                pass  # Implement your analysis logic here
        """),
    },
    "transport": {
        "domain": "multi",
        "capabilities": '["send", "receive", "health"]',
        "description": "Transport plugin — integrates a communications protocol into AMOS.",
        "extra_imports": "",
        "extra_methods": textwrap.dedent("""\

            def connect(self) -> bool:
                \"\"\"Establish connection to the transport endpoint.\"\"\"
                return True

            def send(self, message: dict) -> bool:
                \"\"\"Send a message via this transport.\"\"\"
                return True

            def receive(self) -> list[dict]:
                \"\"\"Receive pending messages from this transport.\"\"\"
                return []

            def disconnect(self) -> None:
                \"\"\"Close the transport connection.\"\"\"
                pass
        """),
        "activate_body": textwrap.dedent("""\
                self.connect()
                self.emit("transport.registered", {{
                    "transport": self.PLUGIN_NAME,
                }})"""),
        "extra_handlers": "",
    },
}


def to_class_name(name: str) -> str:
    """Convert snake_case to PascalCase + 'Plugin'."""
    return "".join(w.capitalize() for w in name.split("_")) + "Plugin"


def generate_init_py(name: str, plugin_type: str) -> str:
    """Generate __init__.py content for the plugin."""
    cfg = PLUGIN_TYPES[plugin_type]
    class_name = to_class_name(name)
    name_upper = name.upper().replace("_", "-")

    extra_imports = f"\n{cfg['extra_imports']}" if cfg["extra_imports"] else ""
    extra_methods = cfg["extra_methods"].format(
        name=name, class_name=class_name, name_upper=name_upper
    )
    activate_body = cfg["activate_body"].format(name=name)
    extra_handlers = cfg.get("extra_handlers", "").format(
        name=name, class_name=class_name, name_upper=name_upper
    )

    return textwrap.dedent(f'''\
        """AMOS Plugin — {class_name.replace("Plugin", "")}.

        {cfg["description"]}

        Plugin lifecycle:
            on_load → on_register → on_activate → (operate) → on_shutdown
        """
{extra_imports}
        from core.plugin_base import PluginBase


        class {class_name}(PluginBase):
            """{cfg["description"]}"""

            PLUGIN_NAME = "{name}"
            PLUGIN_VERSION = "1.0"
            PLUGIN_TYPE = "{plugin_type}"
{extra_methods}
            # ── Lifecycle ──────────────────────────────────────────
            def on_activate(self, event_bus) -> None:
                """Start operating — subscribe to events."""
        {activate_body}

            def on_shutdown(self) -> None:
                """Clean disconnect."""
                self.emit("plugin.shutdown", {{"name": self.PLUGIN_NAME}})

            def get_capabilities(self) -> list[str]:
                return {cfg["capabilities"]}
{extra_handlers}
    ''')


def generate_plugin_yaml(name: str, plugin_type: str) -> str:
    """Generate plugin.yaml manifest."""
    cfg = PLUGIN_TYPES[plugin_type]
    class_name = to_class_name(name)
    return textwrap.dedent(f"""\
        name: {name}
        version: "1.0"
        type: {plugin_type}
        domain: {cfg["domain"]}
        author: AMOS Developer
        enabled: true
        entry_point: {class_name}
        description: >
          {cfg["description"]}
        dependencies:
          - amos-core >=1.0
    """)


def generate_readme(name: str, plugin_type: str) -> str:
    """Generate README.md for the plugin."""
    cfg = PLUGIN_TYPES[plugin_type]
    class_name = to_class_name(name)
    return textwrap.dedent(f"""\
        # {class_name.replace("Plugin", "")}

        {cfg["description"]}

        ## Quick Start

        1. Copy this plugin to `plugins/{name}/`
        2. Edit `__init__.py` to implement your logic
        3. Set `enabled: true` in `plugin.yaml`
        4. Restart AMOS — the plugin loads automatically

        ## Plugin Type: `{plugin_type}`

        ## Files

        - `__init__.py` — Plugin implementation
        - `plugin.yaml` — Plugin manifest (name, version, type, dependencies)
        - `README.md` — This file
    """)


def main():
    parser = argparse.ArgumentParser(
        description="AMOS Plugin Scaffolding Tool",
        epilog="Example: python3 tools/create_plugin.py my_sensor --type sensor_adapter",
    )
    parser.add_argument("name", help="Plugin name (snake_case)")
    parser.add_argument(
        "--type",
        required=True,
        choices=list(PLUGIN_TYPES.keys()),
        help="Plugin type",
        dest="plugin_type",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: plugins/<name>)",
    )
    args = parser.parse_args()

    # Determine output directory
    if args.output_dir:
        plugin_dir = args.output_dir
    else:
        # Find plugins/ relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(script_dir)
        plugin_dir = os.path.join(repo_root, "plugins", args.name)

    if os.path.exists(plugin_dir):
        print(f"Error: Directory already exists: {plugin_dir}")
        sys.exit(1)

    os.makedirs(plugin_dir, exist_ok=True)

    # Generate files
    files = {
        "__init__.py": generate_init_py(args.name, args.plugin_type),
        "plugin.yaml": generate_plugin_yaml(args.name, args.plugin_type),
        "README.md": generate_readme(args.name, args.plugin_type),
    }

    for filename, content in files.items():
        filepath = os.path.join(plugin_dir, filename)
        with open(filepath, "w") as f:
            f.write(content)
        print(f"  Created {filepath}")

    print(f"\n✔ Plugin '{args.name}' ({args.plugin_type}) created at {plugin_dir}")
    print(f"  Edit plugins/{args.name}/__init__.py to implement your logic.")


if __name__ == "__main__":
    main()
