"""AMOS Enterprise — Intelligence Routes (HAL, COA, Cognitive, Predictions, Wargame)."""

import uuid
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from web.extensions import login_required, ctx
from web.state import (
    hal_recommendations, cognitive_engine, commander_support,
    threat_predictor, wargame_engine, nlp_parser, learning_engine,
    contested_env, red_force_ai,
    sim_assets, sim_threats, sim_clock, aar_events, cm_log,
    waypoint_nav, base_pos, now_iso,
    generate_opord, generate_conop, db_execute, to_json,
)
from web.extensions import platoon

bp = Blueprint("ent_intelligence", __name__)


# ═══════════════════════════════════════════════════════════
#  HAL / COA / COGNITIVE
# ═══════════════════════════════════════════════════════════
@bp.route("/api/hal/recommendations")
@login_required
def api_hal_recs():
    if not cognitive_engine:
        return jsonify(hal_recommendations[-20:])
    # Merge cognitive engine recs with legacy HAL recs
    cog_recs = cognitive_engine.get_recommendations(30)
    merged = []
    for r in cog_recs:
        merged.append({
            "id": r["id"], "type": r["coa"]["coa_name"] if r.get("coa") else "UNKNOWN",
            "asset": ", ".join(r.get("recommended_assets", [])[:3]),
            "target": r.get("threat_id", ""),
            "confidence": r["coa"]["p_success"] if r.get("coa") else 0.5,
            "reasoning": " \u2192 ".join(r.get("reasoning_chain", [])),
            "status": r.get("status", "pending"),
            "tier": 2, "timestamp": r.get("timestamp", ""),
            "risk": r["coa"].get("risk", "MEDIUM") if r.get("coa") else "MEDIUM",
            "score": r["coa"].get("composite_score", 0) if r.get("coa") else 0,
            "all_coas": r.get("all_coas", []),
        })
    for r in hal_recommendations[-20:]:
        merged.append(r)
    return jsonify(merged)

@bp.route("/api/hal/approve", methods=["POST"])
@login_required
def api_hal_approve():
    if not cognitive_engine:
        return jsonify({"error": "Cognitive engine not available"}), 503
    d = request.json or {}
    rid = d.get("rec_id", "")
    c = ctx()
    result = cognitive_engine.approve(rid, c["name"])
    if result:
        aar_events.append({"type": "coa_approve", "timestamp": now_iso(),
            "elapsed": sim_clock["elapsed_sec"],
            "details": f"COA {rid} approved by {c['name']}"})
    return jsonify(result or {"error": "Recommendation not found"})

@bp.route("/api/hal/reject", methods=["POST"])
@login_required
def api_hal_reject():
    if not cognitive_engine:
        return jsonify({"error": "Cognitive engine not available"}), 503
    d = request.json or {}
    rid = d.get("rec_id", "")
    c = ctx()
    result = cognitive_engine.reject(rid, c["name"], d.get("reason", ""))
    return jsonify(result or {"error": "Recommendation not found"})

@bp.route("/api/hal/risk")
@login_required
def api_hal_risk():
    if not commander_support:
        return jsonify({})
    return jsonify(commander_support.get_risk())

@bp.route("/api/hal/risk-trend")
@login_required
def api_hal_risk_trend():
    if not commander_support:
        return jsonify([])
    return jsonify(commander_support.get_risk_trend())


# ═══════════════════════════════════════════════════════════
#  NLP COMMANDER
# ═══════════════════════════════════════════════════════════
@bp.route("/api/nlp/parse", methods=["POST"])
@login_required
def api_nlp_parse():
    if not nlp_parser:
        return jsonify({"error": "NLP engine not available"}), 503
    text = (request.json or {}).get("text", "")
    return jsonify(nlp_parser.parse_command(text))

@bp.route("/api/nlp/intent-history")
@login_required
def api_nlp_intent_history():
    if not nlp_parser:
        return jsonify([])
    return jsonify(nlp_parser.get_history())


# ═══════════════════════════════════════════════════════════
#  LEARNING ENGINE
# ═══════════════════════════════════════════════════════════
@bp.route("/api/learning/patterns")
@login_required
def api_learning_patterns():
    if not learning_engine:
        return jsonify([])
    return jsonify(learning_engine.get_patterns())

@bp.route("/api/learning/metrics")
@login_required
def api_learning_metrics():
    if not learning_engine:
        return jsonify({})
    return jsonify(learning_engine.get_metrics())


# ═══════════════════════════════════════════════════════════
#  PREDICTIONS
# ═══════════════════════════════════════════════════════════
@bp.route("/api/predict/threats")
@login_required
def api_predict_threats():
    if not threat_predictor:
        return jsonify([])
    return jsonify(threat_predictor.get_predictions())

@bp.route("/api/predict/heatmap")
@login_required
def api_predict_heatmap():
    if not threat_predictor:
        return jsonify([])
    return jsonify(threat_predictor.get_heatmap())

@bp.route("/api/predict/intercepts")
@login_required
def api_predict_intercepts():
    if not threat_predictor:
        return jsonify([])
    return jsonify(threat_predictor.get_intercepts(sim_assets, sim_threats))

@bp.route("/api/predict/patterns")
@login_required
def api_predict_patterns():
    if not threat_predictor:
        return jsonify([])
    return jsonify(threat_predictor.get_patterns())


# ═══════════════════════════════════════════════════════════
#  WARGAMING ENGINE
# ═══════════════════════════════════════════════════════════
@bp.route("/api/wargame/run", methods=["POST"])
@login_required
def api_wargame_run():
    if not wargame_engine:
        return jsonify({"error": "Wargame engine not available"}), 503
    d = request.json or {}
    blue = [{"id": a["id"], "type": a["type"], "domain": a["domain"],
             "weapons": a.get("weapons", []), "health": a["health"]["battery_pct"]}
            for a in sim_assets.values() if a["status"] == "operational"]
    red = [{"id": tid, "type": t["type"],
            "threat_level": "high" if t.get("speed_kts", 0) > 50 else "medium"}
           for tid, t in sim_threats.items() if not t.get("neutralized") and "lat" in t]
    coa = {"approach": d.get("approach", "direct"),
           "aggression": d.get("aggression", 0.6),
           "tempo": d.get("tempo", "deliberate")}
    result = wargame_engine.run_scenario(
        d.get("name", "Manual Scenario"), blue, red, coa,
        iterations=d.get("iterations", 1000))
    return jsonify(result)

@bp.route("/api/wargame/results/<sid>")
@login_required
def api_wargame_results(sid):
    if not wargame_engine:
        return jsonify({}), 503
    return jsonify(wargame_engine.get_scenario(sid))

@bp.route("/api/wargame/compare", methods=["POST"])
@login_required
def api_wargame_compare():
    if not wargame_engine:
        return jsonify({}), 503
    ids = (request.json or {}).get("scenario_ids", [])
    return jsonify(wargame_engine.compare_coas(ids))

@bp.route("/api/wargame/history")
@login_required
def api_wargame_history():
    if not wargame_engine:
        return jsonify([])
    return jsonify(wargame_engine.get_history())


# ═══════════════════════════════════════════════════════════
#  HAL ACTION
# ═══════════════════════════════════════════════════════════
@bp.route("/api/hal/action", methods=["POST"])
@login_required
def api_hal_action():
    d = request.json
    rid = d.get("id", "")
    act = d.get("action", "")
    c = ctx()
    # Try cognitive engine first
    result = cognitive_engine.action_recommendation(rid, act, c["name"]) if cognitive_engine else None
    if result:
        if act == "approve":
            aar_events.append({"type": "coa_approved", "timestamp": now_iso(),
                "elapsed": sim_clock["elapsed_sec"],
                "details": f"COA {result['coa']['coa_name']}: threat {result['threat_id']} by {c['name']}"})
            try:
                db_execute("INSERT INTO mission_events (mission_id, event_type, details) VALUES(1,%s,%s)",
                    ("coa_approved", to_json({"rec_id": rid, "coa": result["coa"]["coa_name"],
                     "threat": result["threat_id"], "operator": c["name"]})))
            except Exception:
                pass
        return jsonify({"status": "ok", "source": "cognitive"})
    # Fallback to legacy HAL
    for r in hal_recommendations:
        if r["id"] == rid:
            r["status"] = act
            r["actioned_by"] = c["name"]
            r["actioned_at"] = now_iso()
            if act == "approve":
                aar_events.append({"type": "hal_approved", "timestamp": r["actioned_at"],
                    "elapsed": sim_clock["elapsed_sec"],
                    "details": f"HAL {r['type']}: {r['asset']}->{r['target']} by {c['name']}"})
            break
    return jsonify({"status": "ok"})


# ═══════════════════════════════════════════════════════════
#  COA GENERATION
# ═══════════════════════════════════════════════════════════
@bp.route("/api/coa/generate", methods=["POST"])
@login_required
def api_coa():
    """Return real COA analysis from the cognitive engine."""
    if not cognitive_engine:
        return jsonify([])
    all_coas = cognitive_engine.get_coas()
    results = []
    for tid, coas in all_coas.items():
        for c in coas[:3]:
            results.append({
                "rank": c.get("rank", 0), "name": c["coa_name"],
                "score": c["composite_score"], "risk": c["risk"],
                "description": c["description"],
                "p_success": c["p_success"], "p_friendly_loss": c["p_friendly_loss"],
                "avg_time_min": c["avg_time_min"], "threat_id": tid
            })
    results.sort(key=lambda x: x["score"], reverse=True)
    return jsonify(results[:12])

@bp.route("/api/coa/current")
@login_required
def api_coa_current():
    """All active COA recommendations from the cognitive engine."""
    if not cognitive_engine:
        return jsonify([])
    recs = cognitive_engine.get_recommendations(20)
    pending = [r for r in recs if r.get("status") == "pending"]
    return jsonify(pending)

@bp.route("/api/coa/history")
@login_required
def api_coa_history():
    """Past COA decisions (approved/rejected)."""
    if not cognitive_engine:
        return jsonify([])
    recs = cognitive_engine.get_recommendations(100)
    actioned = [r for r in recs if r.get("status") in ("approve", "reject", "approved", "rejected")]
    return jsonify(actioned)


# ═══════════════════════════════════════════════════════════
#  COGNITIVE ENGINE
# ═══════════════════════════════════════════════════════════
@bp.route("/api/cognitive/ooda")
@login_required
def api_cognitive_ooda():
    if not cognitive_engine:
        return jsonify([])
    return jsonify(cognitive_engine.get_loops())

@bp.route("/api/cognitive/coa")
@login_required
def api_cognitive_coa():
    if not cognitive_engine:
        return jsonify({})
    return jsonify(cognitive_engine.get_coas())

@bp.route("/api/cognitive/reasoning")
@login_required
def api_cognitive_reasoning():
    if not cognitive_engine:
        return jsonify([])
    return jsonify(cognitive_engine.get_recommendations())


# ═══════════════════════════════════════════════════════════
#  NLP EXECUTE
# ═══════════════════════════════════════════════════════════
@bp.route("/api/nlp/execute", methods=["POST"])
@login_required
def api_nlp_execute():
    if not nlp_parser:
        return jsonify({"error": "NLP engine not available"}), 503
    text = (request.json or {}).get("text", "")
    parsed = nlp_parser.parse(text)
    executed = []
    for order in parsed.get("orders", []):
        assets = order.get("resolved_assets", [])
        action = order.get("action", "")
        for aid in assets:
            if aid in sim_assets and action in ("move", "patrol", "recon"):
                loc = order.get("location", {})
                if "lat" in loc and "lng" in loc:
                    waypoint_nav.set_waypoint(aid, loc["lat"], loc["lng"])
                    executed.append({"asset": aid, "action": action, "location": loc})
    c = ctx()
    aar_events.append({"type": "nlp_command", "timestamp": now_iso(),
        "elapsed": sim_clock["elapsed_sec"],
        "details": f"NLP [{c['name']}]: {text} -> {len(executed)} actions"})
    return jsonify({"parsed": parsed, "executed": executed})


# ═══════════════════════════════════════════════════════════
#  CONTESTED ENVIRONMENT
# ═══════════════════════════════════════════════════════════
@bp.route("/api/contested/status")
@login_required
def api_contested_status():
    if not contested_env:
        return jsonify({})
    return jsonify(contested_env.get_status())

@bp.route("/api/contested/gps-denial/add", methods=["POST"])
@login_required
def api_contested_gps_add():
    if not contested_env:
        return jsonify({"error": "Contested env not available"}), 503
    d = request.json
    contested_env.add_gps_denial_zone(
        d.get("lat", 0), d.get("lng", 0),
        d.get("radius_nm", 5), d.get("js_ratio_db", 20))
    return jsonify({"status": "ok", "zones": len(contested_env.gps_denial_zones)})

@bp.route("/api/contested/gps-denial/remove", methods=["POST"])
@login_required
def api_contested_gps_remove():
    if not contested_env:
        return jsonify({"error": "Contested env not available"}), 503
    zid = request.json.get("zone_id", "")
    contested_env.gps_denial_zones = [
        z for z in contested_env.gps_denial_zones if z.get("id") != zid]
    return jsonify({"status": "ok"})

@bp.route("/api/contested/mesh")
@login_required
def api_contested_mesh():
    if not contested_env:
        return jsonify({})
    return jsonify(contested_env.get_mesh())


# ═══════════════════════════════════════════════════════════
#  RED FORCE
# ═══════════════════════════════════════════════════════════
@bp.route("/api/redforce/status")
@login_required
def api_redforce_status():
    if not red_force_ai:
        return jsonify({})
    return jsonify(red_force_ai.get_stats())

@bp.route("/api/redforce/units")
@login_required
def api_redforce_units():
    if not red_force_ai:
        return jsonify([])
    return jsonify(red_force_ai.get_units())

@bp.route("/api/redforce/spawn", methods=["POST"])
@login_required
def api_redforce_spawn():
    if not red_force_ai:
        return jsonify({"error": "Red force not available"}), 503
    d = request.json
    uid = f"RED-SPAWN-{len(red_force_ai.units)+1:02d}"
    from services.red_force_ai import RedUnit
    lat = d.get("lat", base_pos["lat"] + 0.05)
    lng = d.get("lng", base_pos["lng"] + 0.05)
    utype = d.get("unit_type", "drone")
    unit = RedUnit(uid, lat, lng, utype)
    unit.state = "PROBING"
    red_force_ai.units[uid] = unit
    red_force_ai.stats["units_spawned"] += 1
    return jsonify({"status": "ok", "unit": unit.to_dict()})


# ═══════════════════════════════════════════════════════════
#  COMMANDER SUPPORT
# ═══════════════════════════════════════════════════════════
@bp.route("/api/commander/risk")
@login_required
def api_commander_risk():
    if not commander_support:
        return jsonify({})
    return jsonify(commander_support.get_risk())

@bp.route("/api/commander/risk/trend")
@login_required
def api_commander_risk_trend():
    if not commander_support:
        return jsonify([])
    return jsonify(commander_support.get_risk_trend())

@bp.route("/api/commander/resources")
@login_required
def api_commander_resources():
    if not commander_support:
        return jsonify({})
    mins = request.args.get("minutes", 60, type=int)
    return jsonify(commander_support.get_resources(sim_assets, mins))

@bp.route("/api/commander/contingencies")
@login_required
def api_commander_contingencies():
    if not commander_support:
        return jsonify([])
    return jsonify(commander_support.get_contingency_plans())

@bp.route("/api/commander/triggered")
@login_required
def api_commander_triggered():
    if not commander_support:
        return jsonify([])
    return jsonify(commander_support.get_triggered_plans())

@bp.route("/api/commander/contingency/add", methods=["POST"])
@login_required
def api_commander_contingency_add():
    if not commander_support:
        return jsonify({"error": "Commander support not available"}), 503
    d = request.json
    plan = commander_support.add_contingency(
        d.get("name", ""), d.get("trigger_type", ""),
        d.get("trigger_params", {}), d.get("actions", []),
        d.get("priority", 5))
    return jsonify({"status": "ok", "plan": plan})

@bp.route("/api/commander/contingency/cancel", methods=["POST"])
@login_required
def api_commander_contingency_cancel():
    if not commander_support:
        return jsonify({"error": "Commander support not available"}), 503
    pid = request.json.get("plan_id", "")
    ok = commander_support.cancel_contingency(pid)
    return jsonify({"status": "ok" if ok else "not_found"})


# ═══════════════════════════════════════════════════════════
#  LEARNING ENGINE (extended)
# ═══════════════════════════════════════════════════════════
@bp.route("/api/learning/anomalies")
@login_required
def api_learning_anomalies():
    if not learning_engine:
        return jsonify([])
    return jsonify(learning_engine.get_anomalies())

@bp.route("/api/learning/engagements")
@login_required
def api_learning_engagements():
    if not learning_engine:
        return jsonify([])
    return jsonify(learning_engine.get_recent_engagements())

@bp.route("/api/learning/engagement-stats")
@login_required
def api_learning_engagement_stats():
    if not learning_engine:
        return jsonify({})
    return jsonify(learning_engine.get_engagement_stats())

@bp.route("/api/learning/swarm-params")
@login_required
def api_learning_swarm_params():
    if not learning_engine:
        return jsonify({})
    return jsonify(learning_engine.get_swarm_params())

@bp.route("/api/learning/swarm/tune", methods=["POST"])
@login_required
def api_learning_swarm_tune():
    if not learning_engine:
        return jsonify({"error": "Learning engine not available"}), 503
    d = request.json
    params = learning_engine.tune_swarm(
        d.get("metric", ""), d.get("score", 0.5), d.get("weight", 1.0))
    return jsonify({"status": "ok", "params": params})

@bp.route("/api/learning/aar")
@login_required
def api_learning_aar():
    if not learning_engine:
        return jsonify({})
    return jsonify(learning_engine.generate_aar())

@bp.route("/api/learning/events")
@login_required
def api_learning_events():
    if not learning_engine:
        return jsonify([])
    etype = request.args.get("type", None)
    limit = request.args.get("limit", 100, type=int)
    return jsonify(learning_engine.get_events(event_type=etype, limit=limit))


# ═══════════════════════════════════════════════════════════
#  DOCUMENT GENERATION
# ═══════════════════════════════════════════════════════════
@bp.route("/api/docs/opord", methods=["POST"])
@login_required
def api_docs_opord():
    """Generate a 5-paragraph OPORD from current mission state."""
    d = request.json or {}
    coa_data = cognitive_engine.get_coas() if cognitive_engine else {}
    opord = generate_opord(
        platoon_config=platoon, assets=sim_assets, threats=sim_threats,
        coa_data=coa_data, mission_name=d.get("mission_name"),
        classification=d.get("classification", "UNCLASSIFIED"))
    return jsonify(opord)

@bp.route("/api/docs/conop", methods=["POST"])
@login_required
def api_docs_conop():
    """Generate a CONOP summary from current mission state."""
    d = request.json or {}
    coa_data = cognitive_engine.get_coas() if cognitive_engine else {}
    conop = generate_conop(
        platoon_config=platoon, assets=sim_assets, threats=sim_threats,
        coa_data=coa_data, aar_events=aar_events,
        classification=d.get("classification", "UNCLASSIFIED"))
    return jsonify(conop)

@bp.route("/api/docs/briefing", methods=["POST"])
@login_required
def api_docs_briefing():
    """Quick mission briefing — combines key data from OPORD + CONOP."""
    coa_data = cognitive_engine.get_coas() if cognitive_engine else {}
    at = sum(1 for t in sim_threats.values() if not t.get("neutralized"))
    nt = sum(1 for t in sim_threats.values() if t.get("neutralized"))
    risk = commander_support.get_risk() if commander_support else {}
    top_coas = []
    for tid, coas in coa_data.items():
        if coas:
            top_coas.append({"threat": tid, "coa": coas[0]["coa_name"],
                            "score": coas[0]["composite_score"], "risk": coas[0]["risk"]})
    return jsonify({
        "mission": platoon.get("name", "UNNAMED"),
        "callsign": platoon.get("callsign", "UNKNOWN"),
        "dtg": datetime.now(timezone.utc).strftime("%d%H%MZ %b %Y").upper(),
        "assets": len(sim_assets),
        "active_threats": at, "neutralized_threats": nt,
        "risk_level": risk.get("level", "LOW"), "risk_score": risk.get("score", 0),
        "elapsed_sec": round(sim_clock["elapsed_sec"], 1),
        "top_coas": top_coas[:5],
        "pending_hal": sum(1 for r in hal_recommendations if r.get("status") == "pending"),
        "recent_events": [{"type": e.get("type"), "details": e.get("details", "")[:100]}
                          for e in aar_events[-10:]],
    })
