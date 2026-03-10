"""AMOS Sensor Routes — Fusion, Video, Imagery, Geospatial, Schema."""

from flask import Blueprint, request, jsonify
from web.extensions import login_required
from web.state import (sensor_fusion, video_pipeline, imagery_handler, schema_validator,
                       haversine, vincenty, bearing, latlng_to_utm, latlng_to_mgrs,
                       mgrs_to_latlng, tracks_to_geojson)

bp = Blueprint("sensors", __name__)


# ═══════════════════════════════════════════════════════════
#  SENSOR FUSION
# ═══════════════════════════════════════════════════════════
@bp.route("/api/fusion/tracks")
@login_required
def api_fusion_tracks(): return jsonify(sensor_fusion.get_tracks())

@bp.route("/api/fusion/coverage")
@login_required
def api_fusion_coverage(): return jsonify(sensor_fusion.get_coverage())

@bp.route("/api/fusion/killchain")
@login_required
def api_fusion_killchain(): return jsonify(sensor_fusion.get_kill_chain_summary())

@bp.route("/api/fusion/gaps")
@login_required
def api_fusion_gaps(): return jsonify(sensor_fusion.get_coverage_gaps())


# ═══════════════════════════════════════════════════════════
#  VIDEO / IMAGERY
# ═══════════════════════════════════════════════════════════
@bp.route("/api/video/status")
@login_required
def api_video_status(): return jsonify(video_pipeline.get_stats())

@bp.route("/api/video/feeds")
@login_required
def api_video_feeds(): return jsonify(video_pipeline.get_feeds())

@bp.route("/api/imagery/catalog")
@login_required
def api_imagery_catalog():
    limit = request.args.get("limit", 50, type=int)
    return jsonify(imagery_handler.get_catalog(limit))

@bp.route("/api/imagery/status")
@login_required
def api_imagery_status(): return jsonify(imagery_handler.get_stats())


# ═══════════════════════════════════════════════════════════
#  GEOSPATIAL
# ═══════════════════════════════════════════════════════════
@bp.route("/api/geo/distance")
@login_required
def api_geo_distance():
    lat1 = request.args.get("lat1", 0, type=float)
    lng1 = request.args.get("lng1", 0, type=float)
    lat2 = request.args.get("lat2", 0, type=float)
    lng2 = request.args.get("lng2", 0, type=float)
    method = request.args.get("method", "vincenty")
    dist = vincenty(lat1, lng1, lat2, lng2) if method == "vincenty" else haversine(lat1, lng1, lat2, lng2)
    brg = bearing(lat1, lng1, lat2, lng2)
    return jsonify({"distance_m": round(dist, 2), "bearing_deg": round(brg, 2), "method": method})

@bp.route("/api/geo/convert")
@login_required
def api_geo_convert():
    lat = request.args.get("lat", 0, type=float)
    lng = request.args.get("lng", 0, type=float)
    return jsonify({"utm": latlng_to_utm(lat, lng), "mgrs": latlng_to_mgrs(lat, lng)})

@bp.route("/api/geo/mgrs")
@login_required
def api_geo_mgrs():
    mgrs_str = request.args.get("mgrs", "")
    if not mgrs_str:
        return jsonify({"error": "mgrs parameter required"}), 400
    try:
        lat, lng = mgrs_to_latlng(mgrs_str)
        return jsonify({"lat": lat, "lng": lng, "mgrs": mgrs_str})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.route("/api/geo/tracks")
@login_required
def api_geo_tracks():
    tracks = sensor_fusion.get_tracks()
    return jsonify(tracks_to_geojson(tracks))


# ═══════════════════════════════════════════════════════════
#  SCHEMA VALIDATOR
# ═══════════════════════════════════════════════════════════
@bp.route("/api/schema/validate", methods=["POST"])
@login_required
def api_schema_validate():
    d = request.json or {}
    result = schema_validator.validate(d.get("data", {}), d.get("schema_name", "track"))
    return jsonify(result)
