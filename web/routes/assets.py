"""AMOS Asset Routes — Asset CRUD, Scenario Save/Load, Threats."""

import json
from flask import Blueprint, request, jsonify
from web.extensions import login_required, ctx
from web.state import (sim_assets, sim_threats, base_pos, waypoint_nav, geofence_mgr,
                       db_execute, to_json)

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
#  THREAT API
# ═══════════════════════════════════════════════════════════
@bp.route("/threats")
@login_required
def api_threats():
    return jsonify(sim_threats)
