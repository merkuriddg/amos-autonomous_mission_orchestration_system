"""AMOS GeoJSON / KML Import

Parses GeoJSON and KML files into a normalised overlay structure that
the frontend map (Leaflet) can render directly.

Supported input formats:
  - GeoJSON  (.geojson, .json)  -- FeatureCollection or single Feature
  - KML      (.kml)             -- Placemarks with Point, LineString, Polygon

Each imported file becomes an **overlay** with a unique ID, name, and a
list of normalised features (GeoJSON Features).
"""

import json
import logging
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Optional

log = logging.getLogger("amos.geo_import")


# ═══════════════════════════════════════════════════════════
#  Overlay store (in-memory)
# ═══════════════════════════════════════════════════════════
_overlays: dict = {}   # overlay_id -> overlay dict


def list_overlays() -> List[dict]:
    """Return all loaded overlays (metadata only, no feature geometry)."""
    result = []
    for oid, ov in _overlays.items():
        result.append({
            "id": oid,
            "name": ov["name"],
            "source_format": ov["source_format"],
            "feature_count": len(ov["features"]),
            "visible": ov.get("visible", True),
            "color": ov.get("color", "#00ff41"),
            "imported_at": ov.get("imported_at", ""),
        })
    return result


def get_overlay(overlay_id: str) -> Optional[dict]:
    """Return full overlay including features."""
    return _overlays.get(overlay_id)


def delete_overlay(overlay_id: str) -> bool:
    """Remove an overlay."""
    return _overlays.pop(overlay_id, None) is not None


def update_overlay(overlay_id: str, updates: dict) -> Optional[dict]:
    """Update overlay metadata (name, visible, color)."""
    ov = _overlays.get(overlay_id)
    if not ov:
        return None
    for k in ("name", "visible", "color"):
        if k in updates:
            ov[k] = updates[k]
    return ov


# ═══════════════════════════════════════════════════════════
#  Import dispatcher
# ═══════════════════════════════════════════════════════════
def import_file(raw_text: str, filename: str = "",
                name: str = "", color: str = "#00ff41") -> dict:
    """Parse raw file content, store as overlay, return overlay dict.

    Parameters
    ----------
    raw_text : str
        File content (JSON or XML string).
    filename : str
        Original filename (used for format detection and default name).
    name : str
        Human-readable overlay name (defaults to filename stem).
    color : str
        Default feature color for rendering.

    Returns
    -------
    dict  with keys: id, name, source_format, feature_count, features
    """
    fname_lower = filename.lower()
    if fname_lower.endswith(".kml"):
        features = _parse_kml(raw_text)
        src_fmt = "KML"
    else:
        features = _parse_geojson(raw_text)
        src_fmt = "GeoJSON"

    overlay_name = name or _stem(filename) or f"Import-{uuid.uuid4().hex[:6]}"
    overlay_id = f"OVL-{uuid.uuid4().hex[:8]}"

    overlay = {
        "id": overlay_id,
        "name": overlay_name,
        "source_format": src_fmt,
        "features": features,
        "visible": True,
        "color": color,
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }
    _overlays[overlay_id] = overlay
    log.info(f"Imported overlay '{overlay_name}' ({src_fmt}): {len(features)} features")
    return overlay


# ═══════════════════════════════════════════════════════════
#  GeoJSON parser
# ═══════════════════════════════════════════════════════════
def _parse_geojson(raw: str) -> List[dict]:
    """Parse GeoJSON text into normalised Feature list."""
    data = json.loads(raw)
    features = []

    if data.get("type") == "FeatureCollection":
        for feat in data.get("features", []):
            f = _normalise_feature(feat)
            if f:
                features.append(f)
    elif data.get("type") == "Feature":
        f = _normalise_feature(data)
        if f:
            features.append(f)
    elif data.get("type") in ("Point", "LineString", "Polygon",
                               "MultiPoint", "MultiLineString", "MultiPolygon"):
        features.append({
            "type": "Feature",
            "geometry": data,
            "properties": {},
        })
    return features


def _normalise_feature(feat: dict) -> Optional[dict]:
    """Ensure a GeoJSON Feature has valid geometry."""
    geom = feat.get("geometry")
    if not geom or not geom.get("type"):
        return None
    props = feat.get("properties") or {}
    return {
        "type": "Feature",
        "geometry": geom,
        "properties": {
            "name": props.get("name", props.get("Name", "")),
            "description": props.get("description", props.get("Description", "")),
            **{k: v for k, v in props.items()
               if k.lower() not in ("name", "description")},
        },
    }


# ═══════════════════════════════════════════════════════════
#  KML parser
# ═══════════════════════════════════════════════════════════
_KML_NS = {
    "kml": "http://www.opengis.net/kml/2.2",
    "gx": "http://www.google.com/kml/ext/2.2",
}


def _parse_kml(raw: str) -> List[dict]:
    """Parse KML text into normalised GeoJSON Feature list."""
    features = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        log.error(f"KML parse error: {e}")
        return features

    # Strip namespace for easier access
    ns = _detect_ns(root)

    for pm in root.iter(f"{{{ns}}}Placemark" if ns else "Placemark"):
        name = _kml_text(pm, "name", ns)
        desc = _kml_text(pm, "description", ns)

        geom = _kml_geometry(pm, ns)
        if geom:
            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {"name": name, "description": desc},
            })
    return features


def _detect_ns(root) -> str:
    """Detect the primary KML namespace from root element."""
    tag = root.tag
    if tag.startswith("{"):
        return tag[1:tag.index("}")]
    return ""


def _kml_text(el, tag: str, ns: str) -> str:
    """Extract text content from a KML child element."""
    child = el.find(f"{{{ns}}}{tag}" if ns else tag)
    return (child.text or "").strip() if child is not None else ""


def _kml_geometry(pm, ns: str) -> Optional[dict]:
    """Extract geometry from a KML Placemark and convert to GeoJSON."""
    # Point
    point = pm.find(f".//{{{ns}}}Point/{{{ns}}}coordinates" if ns
                    else ".//Point/coordinates")
    if point is not None:
        coords = _kml_coords(point.text)
        if coords:
            return {"type": "Point", "coordinates": coords[0]}

    # LineString
    line = pm.find(f".//{{{ns}}}LineString/{{{ns}}}coordinates" if ns
                   else ".//LineString/coordinates")
    if line is not None:
        coords = _kml_coords(line.text)
        if coords:
            return {"type": "LineString", "coordinates": coords}

    # Polygon (outer boundary only)
    poly = pm.find(
        f".//{{{ns}}}Polygon/{{{ns}}}outerBoundaryIs/{{{ns}}}LinearRing/{{{ns}}}coordinates"
        if ns else ".//Polygon/outerBoundaryIs/LinearRing/coordinates")
    if poly is not None:
        coords = _kml_coords(poly.text)
        if coords:
            return {"type": "Polygon", "coordinates": [coords]}

    return None


def _kml_coords(text: str) -> List[list]:
    """Parse KML coordinate string → list of [lng, lat, alt]."""
    if not text:
        return []
    coords = []
    for token in text.strip().split():
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                lng = float(parts[0])
                lat = float(parts[1])
                alt = float(parts[2]) if len(parts) > 2 else 0
                coords.append([lng, lat, alt])
            except (ValueError, IndexError):
                continue
    return coords


# ═══════════════════════════════════════════════════════════
#  Utility
# ═══════════════════════════════════════════════════════════
def _stem(filename: str) -> str:
    """Get filename stem without extension."""
    if not filename:
        return ""
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return name.rsplit(".", 1)[0] if "." in name else name
