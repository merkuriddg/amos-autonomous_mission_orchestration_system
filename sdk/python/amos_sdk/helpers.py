"""AMOS SDK Helpers — utility functions for plugin developers.

Geo-math, manifest loading, and validation helpers that plugin authors
use frequently.
"""

from __future__ import annotations

import math
import pathlib
from typing import Any

import yaml  # PyYAML — already an AMOS dependency


# ── Manifest helpers ───────────────────────────────────────

def load_manifest(plugin_dir: str | pathlib.Path) -> dict[str, Any]:
    """Load and return a plugin.yaml manifest as a dict.

    Parameters
    ----------
    plugin_dir : str | Path
        Path to the plugin directory containing ``plugin.yaml``.

    Raises
    ------
    FileNotFoundError
        If ``plugin.yaml`` does not exist.
    yaml.YAMLError
        If the YAML is malformed.
    """
    path = pathlib.Path(plugin_dir) / "plugin.yaml"
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


_REQUIRED_MANIFEST_KEYS = {"name", "version", "type", "entry_point"}


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """Validate a plugin manifest dict and return a list of errors.

    Returns an empty list when the manifest is valid.
    """
    errors: list[str] = []
    for key in _REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            errors.append(f"Missing required key: {key}")

    if "type" in manifest:
        valid_types = {
            "asset_adapter", "sensor_adapter", "mission_pack",
            "planner", "analytics", "transport",
        }
        if manifest["type"] not in valid_types:
            errors.append(
                f"Invalid type '{manifest['type']}' — must be one of {sorted(valid_types)}"
            )

    if "entry_point" in manifest:
        ep = manifest["entry_point"]
        if ":" not in ep:
            errors.append(
                f"entry_point '{ep}' must be in 'module:ClassName' format"
            )

    return errors


# ── Geo-math ───────────────────────────────────────────────

_EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in **metres** between two WGS-84 points."""
    rlat1, rlon1, rlat2, rlon2 = (math.radians(v) for v in (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing in degrees (0–360) from point 1 to point 2."""
    rlat1, rlon1, rlat2, rlon2 = (math.radians(v) for v in (lat1, lon1, lat2, lon2))
    dlon = rlon2 - rlon1
    x = math.sin(dlon) * math.cos(rlat2)
    y = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def format_mgrs(lat: float, lon: float) -> str:
    """Return a rough MGRS-style grid string (UTM zone + 100 km square).

    This is a *simplified* MGRS formatter suitable for display.  For
    mil-spec accuracy use the ``mgrs`` PyPI package.
    """
    zone_number = int((lon + 180) / 6) + 1
    zone_letter = _utm_letter(lat)
    easting_100k = chr(ord("A") + int(((lon % 6) + 3) / 1) % 8)
    northing_100k = chr(ord("A") + int(lat % 8))
    return f"{zone_number:02d}{zone_letter} {easting_100k}{northing_100k}"


def _utm_letter(lat: float) -> str:
    """Return the UTM latitude band letter for a given latitude."""
    letters = "CDEFGHJKLMNPQRSTUVWX"
    idx = int((lat + 80) / 8)
    idx = max(0, min(idx, len(letters) - 1))
    return letters[idx]
