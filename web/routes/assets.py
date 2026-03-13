"""AMOS Asset Routes — Asset CRUD, Scenario Save/Load, Threats."""

import json
from flask import Blueprint, request, jsonify
from web.extensions import login_required, ctx
from web.state import (sim_assets, sim_threats, base_pos, waypoint_nav, geofence_mgr,
                       db_execute, to_json, asset_states, environment_type,
                       AssetState)

bp = Blueprint("assets", __name__)


# ═══════════════════════════════════════════════════════════
#  SCENARIO SAVE / LOAD
# ═══════════════════════════════════════════════════════════
@bp.route("/scenario/save", methods=["POST"])
@login_required
def api_scenario_save():
    """Export full mission state as JSON."""
    d = request.json or {}
    from web.state import (sim_clock, aar_events, cm_log, swarms, ew_active_jams,
                           sigint_intercepts, cyber_events)
    scenario = {
        "name": d.get("name", "Unnamed Scenario"),
        "assets": sim_assets,
        "threats": sim_threats,
        "clock": sim_clock,
        "events": aar_events[-200:],
        "cm_log": cm_log,
        "swarms": swarms,
        "ew_jams": ew_active_jams,
        "sigint": sigint_intercepts[-50:],
        "cyber": cyber_events[-50:],
    }
    return jsonify(scenario)


@bp.route("/scenario/load", methods=["POST"])
@login_required
def api_scenario_load():
    """Load a mission scenario from JSON."""
    d = request.json or {}
    if "assets" in d:
        sim_assets.clear()
        sim_assets.update(d["assets"])
    if "threats" in d:
        sim_threats.clear()
        sim_threats.update(d["threats"])
    return jsonify({"status": "ok", "assets": len(sim_assets), "threats": len(sim_threats)})


# ═══════════════════════════════════════════════════════════
#  SETTINGS — ASSET FLEET MANAGEMENT
# ═══════════════════════════════════════════════════════════
@bp.route("/settings/assets")
@login_required
def api_settings_assets():
    """Return full sim_assets dict for fleet management."""
    return jsonify(sim_assets)


@bp.route("/settings/assets/save", methods=["POST"])
@login_required
def api_settings_assets_save():
    """Create or update an asset in sim_assets."""
    d = request.json
    aid = d.get("id", "").strip().upper()
    if not aid:
        return jsonify({"error": "Asset ID required"}), 400
    existing = sim_assets.get(aid, {})
    asset = {
        "id": aid,
        "type": d.get("type", existing.get("type", "unknown")),
        "domain": d.get("domain", existing.get("domain", "ground")),
        "role": d.get("role", existing.get("role", "recon")),
        "autonomy_tier": int(d.get("autonomy_tier", existing.get("autonomy_tier", 2))),
        "sensors": d.get("sensors", existing.get("sensors", [])),
        "weapons": d.get("weapons", existing.get("weapons", [])),
        "endurance_hr": float(d.get("endurance_hr", existing.get("endurance_hr", 0))),
        "position": {
            "lat": float(d.get("lat", existing.get("position", {}).get("lat", base_pos["lat"]))),
            "lng": float(d.get("lng", existing.get("position", {}).get("lng", base_pos["lng"]))),
            "alt_ft": float(d.get("alt_ft", existing.get("position", {}).get("alt_ft", 0)))
        },
        "status": existing.get("status", "standby"),
        "health": existing.get("health", {
            "battery_pct": 100, "comms_strength": 95,
            "cpu_temp_c": 42, "gps_fix": True
        }),
        "speed_kts": existing.get("speed_kts", 0),
        "heading_deg": existing.get("heading_deg", 0),
        "integration": d.get("integration", existing.get("integration", "none")),
        "bridge_addr": d.get("bridge_addr", existing.get("bridge_addr", ""))
    }
    sim_assets[aid] = asset
    try:
        db_execute(
            """INSERT INTO assets (asset_id,type,domain,role,autonomy_tier,sensors,weapons,
               endurance_hr,lat,lng,alt_ft,integration,bridge_addr)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE type=VALUES(type),domain=VALUES(domain),role=VALUES(role),
               autonomy_tier=VALUES(autonomy_tier),sensors=VALUES(sensors),weapons=VALUES(weapons),
               endurance_hr=VALUES(endurance_hr),lat=VALUES(lat),lng=VALUES(lng),alt_ft=VALUES(alt_ft),
               integration=VALUES(integration),bridge_addr=VALUES(bridge_addr)""",
            (aid, asset["type"], asset["domain"], asset["role"], asset["autonomy_tier"],
             to_json(asset["sensors"]), to_json(asset["weapons"]), asset["endurance_hr"],
             asset["position"]["lat"], asset["position"]["lng"], asset["position"]["alt_ft"],
             asset["integration"], asset["bridge_addr"]))
    except Exception as e:
        print(f"[AMOS] DB asset write error: {e}")
    return jsonify({"status": "ok", "id": aid})


@bp.route("/settings/assets/delete", methods=["POST"])
@login_required
def api_settings_assets_delete():
    """Remove an asset from sim_assets."""
    aid = request.json.get("id", "").strip().upper()
    if aid in sim_assets:
        del sim_assets[aid]
        try:
            db_execute("DELETE FROM assets WHERE asset_id=%s", (aid,))
        except Exception:
            pass
    return jsonify({"status": "ok", "id": aid})


# ═══════════════════════════════════════════════════════════
#  ASSET API
# ═══════════════════════════════════════════════════════════
@bp.route("/assets")
@login_required
def api_assets():
    c = ctx()
    if c["domain"] == "all":
        return jsonify(sim_assets)
    return jsonify({k: v for k, v in sim_assets.items() if v["domain"] == c["domain"]})


@bp.route("/assets/summary")
@login_required
def api_assets_summary():
    bd, bs, br = {}, {}, {}
    for a in sim_assets.values():
        bd[a["domain"]] = bd.get(a["domain"], 0) + 1
        bs[a["status"]] = bs.get(a["status"], 0) + 1
        br[a["role"]] = br.get(a["role"], 0) + 1
    return jsonify({"total": len(sim_assets), "by_domain": bd, "by_status": bs, "by_role": br})


@bp.route("/assets/<asset_id>")
@login_required
def api_asset_detail(asset_id):
    a = sim_assets.get(asset_id)
    if not a:
        return jsonify({"error": "Not found"}), 404
    r = dict(a)
    r["waypoints"] = waypoint_nav.get_waypoints(asset_id)
    return jsonify(r)


# ═══════════════════════════════════════════════════════════
#  ASSET STATE API (B1 bipedal seeds)
# ═══════════════════════════════════════════════════════════

@bp.route("/assets/state")
@login_required
def api_asset_states():
    """All asset extended states (posture, stance, fatigue, etc.)."""
    return jsonify({
        "environment_type": environment_type,
        "states": {aid: st.to_dict() for aid, st in asset_states.items()},
    })


@bp.route("/assets/<asset_id>/state", methods=["GET", "PUT"])
@login_required
def api_asset_state_detail(asset_id):
    """GET: return extended state.  PUT: update extended state."""
    if request.method == "GET":
        st = asset_states.get(asset_id)
        if not st:
            return jsonify({"error": "Asset state not found"}), 404
        return jsonify(st.to_dict())
    # ── PUT ──
    if asset_id not in sim_assets:
        return jsonify({"error": "Asset not found"}), 404
    d = request.json or {}
    st = asset_states.get(asset_id)
    if not st:
        st = AssetState(asset_id=asset_id, environment_type=environment_type)
        asset_states[asset_id] = st
    # Apply provided fields
    for fld in ("posture", "stance", "manipulation_state", "cover_status", "environment_type"):
        if fld in d:
            setattr(st, fld, d[fld])
    if "fatigue_pct" in d:
        st.fatigue_pct = float(d["fatigue_pct"])
    if "indoor_position" in d and d["indoor_position"]:
        from core.data_model import IndoorPosition
        st.indoor_position = IndoorPosition.from_dict(d["indoor_position"])
    elif "indoor_position" in d and d["indoor_position"] is None:
        st.indoor_position = None
    # Validate
    errors = st.validate()
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400
    return jsonify({"status": "ok", "state": st.to_dict()})


# ═══════════════════════════════════════════════════════════
#  CQB FORMATION API (B1.3 bipedal seed)
# ═══════════════════════════════════════════════════════════

@bp.route("/cqb/formations")
@login_required
def api_cqb_formations():
    """List available CQB formation types."""
    from services.cqb_formations import CQBFormation
    return jsonify({"formations": CQBFormation.available()})


@bp.route("/cqb/compute", methods=["POST"])
@login_required
def api_cqb_compute():
    """Compute CQB formation positions for a given squad size."""
    from services.cqb_formations import CQBFormation
    d = request.json or {}
    formation = d.get("formation", "STACK")
    count = int(d.get("count", 4))
    if count < 1 or count > 20:
        return jsonify({"error": "count must be 1-20"}), 400
    try:
        positions = CQBFormation.compute(
            formation, count,
            heading_deg=float(d.get("heading_deg", 0)),
            spacing_m=float(d.get("spacing_m", 1.5)),
            ref_lat=float(d.get("ref_lat", 0)),
            ref_lng=float(d.get("ref_lng", 0)),
            use_local=bool(d.get("use_local", False)),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"formation": formation, "count": count, "positions": positions})


# ═══════════════════════════════════════════════════════════
#  THREAT API
# ═══════════════════════════════════════════════════════════
@bp.route("/threats")
@login_required
def api_threats():
    return jsonify(sim_threats)
