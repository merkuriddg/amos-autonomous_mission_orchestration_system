"""AMOS Scenario Management.

Provides ScenarioLoader for discovering, loading, validating, and exporting
simulation scenarios.  Scenarios are YAML or JSON files that define assets,
threats, area of operations, and optional waypoints/geofences.
"""

import os
import json
import glob
import uuid
from datetime import datetime, timezone

try:
    import yaml
except ImportError:  # graceful fallback
    yaml = None

# ── Built-in scenario catalog ─────────────────────────────────
DEFAULT_SCENARIOS = [
    {
        "id": "tehran-default",
        "name": "Tehran AO — Full Platoon",
        "description": "25-asset multi-domain platoon with 22 threats in the Tehran area of operations.",
        "config_file": "config/platoon_config.yaml",
        "domains": ["air", "ground", "maritime"],
        "asset_count": 25,
        "threat_count": 22,
    },
    {
        "id": "minimal-recon",
        "name": "Minimal Recon Patrol",
        "description": "3-drone ISR patrol for quick testing.",
        "config_file": None,
        "domains": ["air"],
        "asset_count": 3,
        "threat_count": 5,
    },
    {
        "id": "maritime-interdiction",
        "name": "Maritime Interdiction",
        "description": "USV/UUV surface/subsurface interdiction exercise.",
        "config_file": None,
        "domains": ["maritime"],
        "asset_count": 6,
        "threat_count": 8,
    },
]

SCENARIO_VERSION = "amos-scenario-v1"
REQUIRED_FIELDS = {"version", "name", "assets"}


class ScenarioLoader:
    """Discover, load, validate, and export AMOS scenarios.

    Parameters
    ----------
    scenarios_dir : str | None
        Directory to scan for ``*.yaml`` / ``*.json`` scenario files.
        Defaults to ``<project_root>/config``.
    """

    def __init__(self, scenarios_dir: str | None = None):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.scenarios_dir = scenarios_dir or os.path.join(root, "config")

    # ── Discovery ──────────────────────────────────────────────
    def list_scenarios(self) -> list[dict]:
        """Return the built-in catalog plus any user scenario files found on disk."""
        catalog = list(DEFAULT_SCENARIOS)
        for path in self._discover_files():
            try:
                data = self._read_file(path)
                catalog.append({
                    "id": data.get("id", os.path.basename(path)),
                    "name": data.get("name", os.path.basename(path)),
                    "description": data.get("description", ""),
                    "config_file": path,
                    "domains": data.get("domains", []),
                    "asset_count": len(data.get("assets", {})),
                    "threat_count": len(data.get("threats", {})),
                })
            except Exception:
                continue
        return catalog

    # ── Loading ────────────────────────────────────────────────
    def load(self, path: str) -> dict:
        """Load and validate a scenario file.

        Raises ``ValueError`` if the file is invalid.
        """
        data = self._read_file(path)
        self.validate(data)
        return data

    def load_platoon_config(self, path: str | None = None) -> dict:
        """Load the default platoon_config.yaml and return it as a dict."""
        path = path or os.path.join(self.scenarios_dir, "platoon_config.yaml")
        return self._read_file(path)

    # ── Validation ─────────────────────────────────────────────
    @staticmethod
    def validate(data: dict) -> bool:
        """Validate a scenario dict; raise ``ValueError`` on problems."""
        missing = REQUIRED_FIELDS - set(data.keys())
        if missing:
            raise ValueError(f"Scenario missing required fields: {missing}")
        if data.get("version") != SCENARIO_VERSION:
            raise ValueError(
                f"Unsupported scenario version: {data.get('version')}")
        assets = data.get("assets", {})
        if not isinstance(assets, dict) or len(assets) == 0:
            raise ValueError("Scenario must contain at least one asset")
        return True

    # ── Export ─────────────────────────────────────────────────
    @staticmethod
    def export_snapshot(
        *,
        name: str,
        assets: dict,
        threats: dict,
        platoon: dict | None = None,
        waypoints: dict | None = None,
        geofences: list | None = None,
        swarms: dict | None = None,
        elapsed_sec: float = 0,
        exported_by: str = "system",
    ) -> dict:
        """Build a scenario-export dict from live simulation state."""
        return {
            "version": SCENARIO_VERSION,
            "id": f"snap-{uuid.uuid4().hex[:8]}",
            "name": name,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "exported_by": exported_by,
            "elapsed_sec": round(elapsed_sec, 1),
            "platoon": platoon or {},
            "assets": {
                aid: {
                    "id": a.get("id", aid),
                    "type": a.get("type", ""),
                    "domain": a.get("domain", ""),
                    "role": a.get("role", ""),
                    "autonomy_tier": a.get("autonomy_tier", 2),
                    "sensors": a.get("sensors", []),
                    "weapons": a.get("weapons", []),
                    "endurance_hr": a.get("endurance_hr", 0),
                    "position": a.get("position", {}),
                    "status": a.get("status", "operational"),
                    "health": a.get("health", {}),
                    "speed_kts": a.get("speed_kts", 0),
                    "heading_deg": a.get("heading_deg", 0),
                }
                for aid, a in assets.items()
            },
            "threats": {
                tid: {
                    "id": t.get("id", tid),
                    "type": t.get("type", ""),
                    "lat": t.get("lat"),
                    "lng": t.get("lng"),
                    "speed_kts": t.get("speed_kts", 0),
                    "neutralized": t.get("neutralized", False),
                }
                for tid, t in threats.items()
            },
            "waypoints": waypoints or {},
            "geofences": geofences or [],
            "swarms": swarms or {},
        }

    # ── Internals ──────────────────────────────────────────────
    def _discover_files(self) -> list[str]:
        """Find *.yaml and *.json scenario files in the scenarios directory."""
        patterns = ["*.yaml", "*.yml", "*.json"]
        found: list[str] = []
        for pat in patterns:
            found.extend(glob.glob(os.path.join(self.scenarios_dir, pat)))
        return sorted(set(found))

    @staticmethod
    def _read_file(path: str) -> dict:
        """Read a YAML or JSON file and return a dict."""
        with open(path, "r", encoding="utf-8") as fh:
            if path.endswith((".yaml", ".yml")):
                if yaml is None:
                    raise RuntimeError("PyYAML required for YAML scenarios")
                return yaml.safe_load(fh) or {}
            return json.load(fh)
