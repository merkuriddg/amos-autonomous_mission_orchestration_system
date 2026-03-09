#!/usr/bin/env python3
"""AMOS Phase 27 — Geospatial Utilities

Coordinate systems & conversions:
  - WGS-84 lat/lng ↔ UTM (zone/easting/northing)
  - WGS-84 lat/lng ↔ MGRS (Military Grid Reference System)
  - WGS-84 lat/lng → GeoJSON (Point, LineString, Polygon, FeatureCollection)

Distance & bearing:
  - Haversine (fast, ~0.3 % error)
  - Vincenty  (accurate, <0.5 mm error on WGS-84 ellipsoid)
  - Initial bearing, destination point
"""

import math
import json
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

log = logging.getLogger("amos.geo")

# ── WGS-84 ellipsoid constants ──────────────────────────────────
WGS84_A = 6_378_137.0            # semi-major axis (m)
WGS84_B = 6_356_752.314245       # semi-minor axis (m)
WGS84_F = 1 / 298.257223563      # flattening
WGS84_E2 = 2 * WGS84_F - WGS84_F ** 2  # first eccentricity squared

# ── MGRS constants ──────────────────────────────────────────────
_MGRS_COL_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I, O
_MGRS_ROW_LETTERS = "ABCDEFGHJKLMNPQRSTUV"      # no I, O
_MGRS_LAT_BANDS   = "CDEFGHJKLMNPQRSTUVWX"       # 80S → 84N


# ═══════════════════════════════════════════════════════════════
#  Haversine
# ═══════════════════════════════════════════════════════════════
def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres (Haversine formula)."""
    R = 6_371_000  # mean Earth radius
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lng2 - lng1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Initial bearing in degrees (0–360) from point 1 → point 2."""
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δλ = math.radians(lng2 - lng1)
    x = math.sin(Δλ) * math.cos(φ2)
    y = math.cos(φ1) * math.sin(φ2) - math.sin(φ1) * math.cos(φ2) * math.cos(Δλ)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def destination_point(lat: float, lng: float, bearing_deg: float,
                      distance_m: float) -> Tuple[float, float]:
    """Compute destination lat/lng given start, bearing, and distance (Haversine)."""
    R = 6_371_000
    δ = distance_m / R
    θ = math.radians(bearing_deg)
    φ1 = math.radians(lat)
    λ1 = math.radians(lng)
    φ2 = math.asin(math.sin(φ1) * math.cos(δ) +
                    math.cos(φ1) * math.sin(δ) * math.cos(θ))
    λ2 = λ1 + math.atan2(math.sin(θ) * math.sin(δ) * math.cos(φ1),
                          math.cos(δ) - math.sin(φ1) * math.sin(φ2))
    return round(math.degrees(φ2), 8), round(math.degrees(λ2), 8)


# ═══════════════════════════════════════════════════════════════
#  Vincenty
# ═══════════════════════════════════════════════════════════════
def vincenty(lat1: float, lng1: float, lat2: float, lng2: float,
             max_iter: int = 200) -> float:
    """Geodesic distance on WGS-84 ellipsoid (Vincenty, metres).

    Falls back to Haversine on convergence failure (antipodal points).
    """
    if lat1 == lat2 and lng1 == lng2:
        return 0.0

    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    L = math.radians(lng2 - lng1)
    U1 = math.atan((1 - WGS84_F) * math.tan(φ1))
    U2 = math.atan((1 - WGS84_F) * math.tan(φ2))
    sinU1, cosU1 = math.sin(U1), math.cos(U1)
    sinU2, cosU2 = math.sin(U2), math.cos(U2)

    λ = L
    for _ in range(max_iter):
        sinλ, cosλ = math.sin(λ), math.cos(λ)
        sinσ = math.sqrt((cosU2 * sinλ) ** 2 +
                         (cosU1 * sinU2 - sinU1 * cosU2 * cosλ) ** 2)
        if sinσ == 0:
            return 0.0  # coincident points
        cosσ = sinU1 * sinU2 + cosU1 * cosU2 * cosλ
        σ = math.atan2(sinσ, cosσ)
        sinα = cosU1 * cosU2 * sinλ / sinσ
        cos2α = 1 - sinα ** 2
        cos2σm = cosσ - 2 * sinU1 * sinU2 / cos2α if cos2α != 0 else 0
        C = WGS84_F / 16 * cos2α * (4 + WGS84_F * (4 - 3 * cos2α))
        λ_prev = λ
        λ = L + (1 - C) * WGS84_F * sinα * (
            σ + C * sinσ * (cos2σm + C * cosσ * (-1 + 2 * cos2σm ** 2)))
        if abs(λ - λ_prev) < 1e-12:
            break
    else:
        log.debug("Vincenty did not converge, falling back to Haversine")
        return haversine(lat1, lng1, lat2, lng2)

    u2 = cos2α * (WGS84_A ** 2 - WGS84_B ** 2) / WGS84_B ** 2
    A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    Δσ = B * sinσ * (cos2σm + B / 4 * (
        cosσ * (-1 + 2 * cos2σm ** 2) -
        B / 6 * cos2σm * (-3 + 4 * sinσ ** 2) * (-3 + 4 * cos2σm ** 2)))
    return WGS84_B * A * (σ - Δσ)


# ═══════════════════════════════════════════════════════════════
#  UTM  (Universal Transverse Mercator)
# ═══════════════════════════════════════════════════════════════
def latlng_to_utm(lat: float, lng: float) -> dict:
    """Convert WGS-84 lat/lng → UTM zone, easting, northing."""
    zone = int((lng + 180) / 6) + 1
    # Special zones for Norway/Svalbard
    if 56 <= lat < 64 and 3 <= lng < 12:
        zone = 32
    elif 72 <= lat < 84:
        if 0 <= lng < 9:
            zone = 31
        elif 9 <= lng < 21:
            zone = 33
        elif 21 <= lng < 33:
            zone = 35
        elif 33 <= lng < 42:
            zone = 37

    λ0 = math.radians((zone - 1) * 6 - 180 + 3)  # central meridian
    φ = math.radians(lat)
    λ = math.radians(lng)

    k0 = 0.9996
    e = math.sqrt(WGS84_E2)
    ep2 = WGS84_E2 / (1 - WGS84_E2)
    N = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(φ) ** 2)
    T = math.tan(φ) ** 2
    C = ep2 * math.cos(φ) ** 2
    A_val = math.cos(φ) * (λ - λ0)
    M = WGS84_A * (
        (1 - WGS84_E2 / 4 - 3 * WGS84_E2 ** 2 / 64) * φ
        - (3 * WGS84_E2 / 8 + 3 * WGS84_E2 ** 2 / 32) * math.sin(2 * φ)
        + (15 * WGS84_E2 ** 2 / 256) * math.sin(4 * φ))

    easting = k0 * N * (
        A_val + (1 - T + C) * A_val ** 3 / 6 +
        (5 - 18 * T + T ** 2) * A_val ** 5 / 120) + 500_000

    northing = k0 * (M + N * math.tan(φ) * (
        A_val ** 2 / 2 + (5 - T + 9 * C + 4 * C ** 2) * A_val ** 4 / 24 +
        (61 - 58 * T + T ** 2) * A_val ** 6 / 720))
    if lat < 0:
        northing += 10_000_000

    hemisphere = "N" if lat >= 0 else "S"
    return {"zone": zone, "hemisphere": hemisphere,
            "easting": round(easting, 2), "northing": round(northing, 2)}


def utm_to_latlng(zone: int, hemisphere: str,
                  easting: float, northing: float) -> Tuple[float, float]:
    """Convert UTM → WGS-84 lat/lng."""
    k0 = 0.9996
    e1 = (1 - math.sqrt(1 - WGS84_E2)) / (1 + math.sqrt(1 - WGS84_E2))
    ep2 = WGS84_E2 / (1 - WGS84_E2)

    x = easting - 500_000
    y = northing
    if hemisphere.upper() == "S":
        y -= 10_000_000

    M = y / k0
    mu = M / (WGS84_A * (1 - WGS84_E2 / 4 - 3 * WGS84_E2 ** 2 / 64))
    φ1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
           + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
           + (151 * e1 ** 3 / 96) * math.sin(6 * mu))

    N1 = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(φ1) ** 2)
    T1 = math.tan(φ1) ** 2
    C1 = ep2 * math.cos(φ1) ** 2
    R1 = WGS84_A * (1 - WGS84_E2) / (1 - WGS84_E2 * math.sin(φ1) ** 2) ** 1.5
    D = x / (N1 * k0)

    lat = φ1 - (N1 * math.tan(φ1) / R1) * (
        D ** 2 / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * ep2) * D ** 4 / 24 +
        (61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 3 * C1 ** 2 - 252 * ep2) * D ** 6 / 720)

    lng_rad = ((zone - 1) * 6 - 180 + 3) * math.pi / 180
    lng = lng_rad + (D - (1 + 2 * T1 + C1) * D ** 3 / 6 +
                     (5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * ep2 + 24 * T1 ** 2)
                     * D ** 5 / 120) / math.cos(φ1)

    return round(math.degrees(lat), 8), round(math.degrees(lng), 8)


# ═══════════════════════════════════════════════════════════════
#  MGRS  (Military Grid Reference System)
# ═══════════════════════════════════════════════════════════════
def latlng_to_mgrs(lat: float, lng: float, precision: int = 5) -> str:
    """Convert WGS-84 lat/lng → MGRS string (default 1 m precision).

    Args:
        precision: 1 (10 km) to 5 (1 m)
    """
    utm = latlng_to_utm(lat, lng)
    zone = utm["zone"]

    # Latitude band letter
    band_idx = min(max(int((lat + 80) / 8), 0), len(_MGRS_LAT_BANDS) - 1)
    band = _MGRS_LAT_BANDS[band_idx]

    # 100 km grid square column letter
    col_idx = (int(utm["easting"] / 100_000) - 1) % 8
    set_num = (zone - 1) % 6
    col_letter = _MGRS_COL_LETTERS[(set_num * 8 + col_idx) % len(_MGRS_COL_LETTERS)]

    # 100 km grid square row letter
    row_idx = int(utm["northing"] / 100_000) % 20
    row_offset = 0 if (zone % 2) == 1 else 5
    row_letter = _MGRS_ROW_LETTERS[(row_idx + row_offset) % len(_MGRS_ROW_LETTERS)]

    # Numerical portion
    e = int(utm["easting"]) % 100_000
    n = int(utm["northing"]) % 100_000
    divisor = 10 ** (5 - precision)
    e_str = str(e // divisor).zfill(precision)
    n_str = str(n // divisor).zfill(precision)

    return f"{zone:02d}{band}{col_letter}{row_letter}{e_str}{n_str}"


def mgrs_to_latlng(mgrs_str: str) -> Tuple[float, float]:
    """Convert MGRS string → approximate WGS-84 lat/lng (centre of grid cell).

    Supports 2–10 digit numerical portions (10 km → 1 m precision).
    """
    mgrs_str = mgrs_str.strip().upper()
    # Parse zone number (1-2 digits), band letter, grid letters, numerics
    idx = 0
    while idx < len(mgrs_str) and mgrs_str[idx].isdigit():
        idx += 1
    zone = int(mgrs_str[:idx])
    band = mgrs_str[idx]
    col_letter = mgrs_str[idx + 1]
    row_letter = mgrs_str[idx + 2]
    nums = mgrs_str[idx + 3:]
    precision = len(nums) // 2
    divisor = 10 ** (5 - precision)
    e_val = int(nums[:precision]) * divisor + divisor // 2
    n_val = int(nums[precision:]) * divisor + divisor // 2

    # Recover 100 km easting
    set_num = (zone - 1) % 6
    col_pos = _MGRS_COL_LETTERS.index(col_letter)
    e_100k = ((col_pos - set_num * 8) % len(_MGRS_COL_LETTERS)) + 1
    easting = e_100k * 100_000 + e_val

    # Recover 100 km northing (approximate via band)
    band_idx = _MGRS_LAT_BANDS.index(band)
    approx_lat = -80 + band_idx * 8 + 4
    utm_ref = latlng_to_utm(approx_lat, (zone - 1) * 6 - 180 + 3)
    n_base = int(utm_ref["northing"] / 100_000) * 100_000

    row_offset = 0 if (zone % 2) == 1 else 5
    row_pos = (_MGRS_ROW_LETTERS.index(row_letter) - row_offset) % 20
    northing = n_base + row_pos * 100_000 + n_val

    hemisphere = "N" if approx_lat >= 0 else "S"
    return utm_to_latlng(zone, hemisphere, easting, northing)


# ═══════════════════════════════════════════════════════════════
#  GeoJSON helpers
# ═══════════════════════════════════════════════════════════════
def point_geojson(lat: float, lng: float, properties: dict = None) -> dict:
    """Create a GeoJSON Feature with a Point geometry."""
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": properties or {},
    }


def line_geojson(coords: List[Tuple[float, float]],
                 properties: dict = None) -> dict:
    """Create GeoJSON LineString.  coords = [(lat, lng), ...]."""
    return {
        "type": "Feature",
        "geometry": {"type": "LineString",
                     "coordinates": [[lng, lat] for lat, lng in coords]},
        "properties": properties or {},
    }


def polygon_geojson(coords: List[Tuple[float, float]],
                    properties: dict = None) -> dict:
    """Create GeoJSON Polygon (auto-closes ring).  coords = [(lat, lng), ...]."""
    ring = [[lng, lat] for lat, lng in coords]
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": properties or {},
    }


def feature_collection(features: list) -> dict:
    """Wrap a list of GeoJSON features into a FeatureCollection."""
    return {"type": "FeatureCollection", "features": features}


def tracks_to_geojson(tracks: list) -> dict:
    """Convert a list of AMOS Track objects to a GeoJSON FeatureCollection."""
    features = []
    for t in tracks:
        d = t.to_dict() if hasattr(t, "to_dict") else t
        feat = point_geojson(
            d.get("lat", 0), d.get("lng", 0),
            properties={
                "track_id": d.get("track_id", ""),
                "callsign": d.get("callsign", ""),
                "affiliation": d.get("affiliation", ""),
                "domain": d.get("domain", ""),
                "speed_mps": d.get("speed_mps", 0),
                "heading_deg": d.get("heading_deg", 0),
                "alt_m": d.get("alt_m", 0),
            },
        )
        features.append(feat)
    return feature_collection(features)


# ═══════════════════════════════════════════════════════════════
#  Utility
# ═══════════════════════════════════════════════════════════════
def bounding_box(lat: float, lng: float,
                 radius_m: float) -> dict:
    """Compute an approximate bounding box around a centre point."""
    d_lat = radius_m / 111_320
    d_lng = radius_m / (111_320 * math.cos(math.radians(lat)))
    return {
        "min_lat": round(lat - d_lat, 8), "max_lat": round(lat + d_lat, 8),
        "min_lng": round(lng - d_lng, 8), "max_lng": round(lng + d_lng, 8),
    }


def midpoint(lat1: float, lng1: float,
             lat2: float, lng2: float) -> Tuple[float, float]:
    """Geographic midpoint between two WGS-84 coordinates."""
    φ1, λ1 = math.radians(lat1), math.radians(lng1)
    φ2, λ2 = math.radians(lat2), math.radians(lng2)
    Bx = math.cos(φ2) * math.cos(λ2 - λ1)
    By = math.cos(φ2) * math.sin(λ2 - λ1)
    φm = math.atan2(math.sin(φ1) + math.sin(φ2),
                     math.sqrt((math.cos(φ1) + Bx) ** 2 + By ** 2))
    λm = λ1 + math.atan2(By, math.cos(φ1) + Bx)
    return round(math.degrees(φm), 8), round(math.degrees(λm), 8)
