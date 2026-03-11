"""AMOS Enterprise API Routes — Full access to all enterprise subsystems.

Exposes REST endpoints for:
  - Cognitive Engine (OODA loops, COA analysis)
  - Commander Support (risk, resources, contingency)
  - Learning Engine (anomalies, engagement stats, AAR)
  - Red Force AI (adversarial units, intel, strategy)
  - Wargame Engine (Monte Carlo scenarios, COA comparison)
  - Threat Predictor (movement prediction, heatmaps, intercepts)
  - Swarm Intelligence (swarms, behaviors, task auctions)
  - ISR Pipeline (ATR, pattern-of-life, collections, change detection)
  - Effects Chain (multi-domain effects orchestration)
  - Space Domain (orbital assets, SATCOM, GPS, JADC2 mesh)
  - HMT Engine (operator workload, trust, adaptive autonomy)
  - Kill Web (F2T2EA pipelines, engagement approval)
  - Contested Environment (GPS denial, comms status, mesh topology)
  - NLP Mission Parser (natural language command parsing)
  - COMSEC / Security (encryption, key management, audit trail)
"""

from flask import Blueprint, request, jsonify
from web.extensions import login_required, ctx
from web.state import (
    cognitive_engine, commander_support, learning_engine,
    red_force_ai, wargame_engine, threat_predictor,
    swarm_intel, isr_pipeline, effects_chain,
    space_domain, hmt_engine, kill_web, contested_env,
    nlp_parser, comsec_channel, key_mgr, security_audit,
    sim_assets, sim_threats, sigint_intercepts, eob_units,
    now_iso,
)

bp = Blueprint("enterprise", __name__)


def _unavailable(name):
    return jsonify({"error": f"{name} not available (enterprise feature not loaded)"}), 404


# ═══════════════════════════════════════════════════════════
#  COGNITIVE ENGINE — OODA Loop + COA Analysis
# ═══════════════════════════════════════════════════════════
@bp.route("/cognitive/status")
@login_required
def api_cognitive_status():
    if not cognitive_engine: return _unavailable("Cognitive Engine")
    return jsonify({
        "stats": cognitive_engine.get_stats(),
        "active_loops": cognitive_engine.get_loops(),
    })

@bp.route("/cognitive/recommendations")
@login_required
def api_cognitive_recommendations():
    if not cognitive_engine: return _unavailable("Cognitive Engine")
    limit = request.args.get("limit", 50, type=int)
    return jsonify(cognitive_engine.get_recommendations(limit))

@bp.route("/cognitive/loops")
@login_required
def api_cognitive_loops():
    if not cognitive_engine: return _unavailable("Cognitive Engine")
    return jsonify(cognitive_engine.get_loops())

@bp.route("/cognitive/coas")
@login_required
def api_cognitive_coas():
    if not cognitive_engine: return _unavailable("Cognitive Engine")
    threat_id = request.args.get("threat_id")
    return jsonify(cognitive_engine.get_coas(threat_id))

@bp.route("/cognitive/action", methods=["POST"])
@login_required
def api_cognitive_action():
    """Approve/reject a cognitive engine recommendation."""
    if not cognitive_engine: return _unavailable("Cognitive Engine")
    d = request.json or {}
    rec_id = d.get("recommendation_id", "")
    action = d.get("action", "approved")  # approved, rejected, deferred
    result = cognitive_engine.action_recommendation(rec_id, action, ctx()["user"])
    if result:
        return jsonify({"status": "ok", "recommendation": result})
    return jsonify({"error": "Recommendation not found"}), 404


# ═══════════════════════════════════════════════════════════
#  COMMANDER SUPPORT — Risk, Resources, Contingency
# ═══════════════════════════════════════════════════════════
@bp.route("/commander/risk")
@login_required
def api_commander_risk():
    if not commander_support: return _unavailable("Commander Support")
    return jsonify(commander_support.get_risk())

@bp.route("/commander/risk/trend")
@login_required
def api_commander_risk_trend():
    if not commander_support: return _unavailable("Commander Support")
    points = request.args.get("points", 20, type=int)
    return jsonify(commander_support.get_risk_trend(points))

@bp.route("/commander/resources")
@login_required
def api_commander_resources():
    if not commander_support: return _unavailable("Commander Support")
    projection = request.args.get("projection_minutes", 60, type=int)
    return jsonify(commander_support.get_resources(sim_assets, projection))

@bp.route("/commander/contingency")
@login_required
def api_commander_contingency():
    if not commander_support: return _unavailable("Commander Support")
    return jsonify({
        "plans": commander_support.get_contingency_plans(),
        "triggered": commander_support.get_triggered_plans(),
    })

@bp.route("/commander/contingency/create", methods=["POST"])
@login_required
def api_commander_contingency_create():
    if not commander_support: return _unavailable("Commander Support")
    d = request.json or {}
    plan = commander_support.add_contingency(
        d.get("name", "Custom Plan"),
        d.get("trigger_type", "THREAT_COUNT"),
        d.get("trigger_params", {}),
        d.get("actions", []),
        d.get("priority", 5),
    )
    return jsonify({"status": "ok", "plan": plan})

@bp.route("/commander/contingency/cancel", methods=["POST"])
@login_required
def api_commander_contingency_cancel():
    if not commander_support: return _unavailable("Commander Support")
    pid = (request.json or {}).get("plan_id", "")
    ok = commander_support.cancel_contingency(pid)
    return jsonify({"status": "ok" if ok else "not_found"})


# ═══════════════════════════════════════════════════════════
#  LEARNING ENGINE — Anomalies, Engagement Stats, AAR
# ═══════════════════════════════════════════════════════════
@bp.route("/learning/status")
@login_required
def api_learning_status():
    if not learning_engine: return _unavailable("Learning Engine")
    return jsonify({
        "engagement_stats": learning_engine.get_engagement_stats(),
        "anomaly_count": len(learning_engine.get_anomalies()),
        "swarm_params": learning_engine.get_swarm_params(),
        "tick_count": learning_engine.tick_count,
    })

@bp.route("/learning/anomalies")
@login_required
def api_learning_anomalies():
    if not learning_engine: return _unavailable("Learning Engine")
    limit = request.args.get("limit", 50, type=int)
    return jsonify(learning_engine.get_anomalies(limit))

@bp.route("/learning/engagements")
@login_required
def api_learning_engagements():
    if not learning_engine: return _unavailable("Learning Engine")
    return jsonify({
        "stats": learning_engine.get_engagement_stats(),
        "recent": learning_engine.get_recent_engagements(),
    })

@bp.route("/learning/events")
@login_required
def api_learning_events():
    if not learning_engine: return _unavailable("Learning Engine")
    event_type = request.args.get("type")
    limit = request.args.get("limit", 100, type=int)
    return jsonify(learning_engine.get_events(event_type=event_type, limit=limit))

@bp.route("/learning/aar")
@login_required
def api_learning_aar():
    if not learning_engine: return _unavailable("Learning Engine")
    return jsonify(learning_engine.generate_aar())

@bp.route("/learning/swarm-params")
@login_required
def api_learning_swarm_params():
    if not learning_engine: return _unavailable("Learning Engine")
    return jsonify(learning_engine.get_swarm_params())

@bp.route("/learning/swarm-tune", methods=["POST"])
@login_required
def api_learning_swarm_tune():
    if not learning_engine: return _unavailable("Learning Engine")
    d = request.json or {}
    params = learning_engine.tune_swarm(
        d.get("metric", ""), d.get("score", 0.5), d.get("weight", 1.0))
    return jsonify({"status": "ok", "params": params})


# ═══════════════════════════════════════════════════════════
#  RED FORCE AI — Adversarial Units, Intel, Strategy
# ═══════════════════════════════════════════════════════════
@bp.route("/redforce/status")
@login_required
def api_redforce_status():
    if not red_force_ai: return _unavailable("Red Force AI")
    return jsonify({
        "stats": red_force_ai.get_stats(),
        "intel": red_force_ai.get_intel(),
    })

@bp.route("/redforce/units")
@login_required
def api_redforce_units():
    if not red_force_ai: return _unavailable("Red Force AI")
    return jsonify(red_force_ai.get_units())

@bp.route("/redforce/events")
@login_required
def api_redforce_events():
    if not red_force_ai: return _unavailable("Red Force AI")
    limit = request.args.get("limit", 50, type=int)
    return jsonify(red_force_ai.get_events(limit))

@bp.route("/redforce/neutralize", methods=["POST"])
@login_required
def api_redforce_neutralize():
    if not red_force_ai: return _unavailable("Red Force AI")
    uid = (request.json or {}).get("unit_id", "")
    ok = red_force_ai.neutralize(uid)
    return jsonify({"status": "ok" if ok else "not_found", "unit_id": uid})


# ═══════════════════════════════════════════════════════════
#  WARGAME ENGINE — Monte Carlo Scenarios
# ═══════════════════════════════════════════════════════════
@bp.route("/wargame/status")
@login_required
def api_wargame_status():
    if not wargame_engine: return _unavailable("Wargame Engine")
    return jsonify(wargame_engine.get_stats())

@bp.route("/wargame/run", methods=["POST"])
@login_required
def api_wargame_run():
    if not wargame_engine: return _unavailable("Wargame Engine")
    d = request.json or {}
    result = wargame_engine.run_scenario(
        d.get("name", "Custom Scenario"),
        d.get("blue_forces", []),
        d.get("red_forces", []),
        d.get("coa_params", {"approach": "direct", "aggression": 0.5, "tempo": "deliberate"}),
        d.get("iterations", 1000),
    )
    return jsonify(result)

@bp.route("/wargame/scenario/<sid>")
@login_required
def api_wargame_scenario(sid):
    if not wargame_engine: return _unavailable("Wargame Engine")
    sc = wargame_engine.get_scenario(sid)
    if not sc:
        return jsonify({"error": "Scenario not found"}), 404
    return jsonify(sc)

@bp.route("/wargame/compare", methods=["POST"])
@login_required
def api_wargame_compare():
    if not wargame_engine: return _unavailable("Wargame Engine")
    ids = (request.json or {}).get("scenario_ids", [])
    return jsonify(wargame_engine.compare_coas(ids))

@bp.route("/wargame/history")
@login_required
def api_wargame_history():
    if not wargame_engine: return _unavailable("Wargame Engine")
    return jsonify(wargame_engine.get_history())

@bp.route("/wargame/auto-eval")
@login_required
def api_wargame_auto_eval():
    if not wargame_engine: return _unavailable("Wargame Engine")
    return jsonify(wargame_engine.get_auto_eval())


# ═══════════════════════════════════════════════════════════
#  THREAT PREDICTOR — Movement Prediction, Heatmaps
# ═══════════════════════════════════════════════════════════
@bp.route("/threat-predict/predictions")
@login_required
def api_threat_predictions():
    if not threat_predictor: return _unavailable("Threat Predictor")
    return jsonify(threat_predictor.get_predictions())

@bp.route("/threat-predict/heatmap")
@login_required
def api_threat_heatmap():
    if not threat_predictor: return _unavailable("Threat Predictor")
    return jsonify(threat_predictor.get_heatmap())

@bp.route("/threat-predict/patterns")
@login_required
def api_threat_patterns():
    if not threat_predictor: return _unavailable("Threat Predictor")
    return jsonify(threat_predictor.get_patterns())

@bp.route("/threat-predict/intercepts")
@login_required
def api_threat_intercepts():
    if not threat_predictor: return _unavailable("Threat Predictor")
    return jsonify(threat_predictor.get_intercepts(sim_assets, sim_threats))


# ═══════════════════════════════════════════════════════════
#  SWARM INTELLIGENCE — Swarms, Behaviors, Auctions
# ═══════════════════════════════════════════════════════════
@bp.route("/swarm-intel/status")
@login_required
def api_swarm_intel_status():
    if not swarm_intel: return _unavailable("Swarm Intelligence")
    return jsonify({
        "stats": swarm_intel.get_stats(),
        "swarms": swarm_intel.get_swarms(),
    })

@bp.route("/swarm-intel/create", methods=["POST"])
@login_required
def api_swarm_intel_create():
    if not swarm_intel: return _unavailable("Swarm Intelligence")
    d = request.json or {}
    swarm = swarm_intel.create_swarm(
        d.get("swarm_id", f"SW-{now_iso()[:10]}"),
        d.get("asset_ids", []),
        d.get("behavior", "scout"),
        d.get("center_lat", 0), d.get("center_lng", 0),
        d.get("target"),
    )
    return jsonify({"status": "ok", "swarm": {k: v for k, v in swarm.items() if k != "velocities"}})

@bp.route("/swarm-intel/<swarm_id>")
@login_required
def api_swarm_intel_detail(swarm_id):
    if not swarm_intel: return _unavailable("Swarm Intelligence")
    s = swarm_intel.get_swarm(swarm_id)
    if not s:
        return jsonify({"error": "Swarm not found"}), 404
    return jsonify({k: v for k, v in s.items() if k != "velocities"})

@bp.route("/swarm-intel/behavior", methods=["POST"])
@login_required
def api_swarm_intel_behavior():
    if not swarm_intel: return _unavailable("Swarm Intelligence")
    d = request.json or {}
    return jsonify(swarm_intel.set_behavior(d.get("swarm_id", ""), d.get("behavior", "scout")))

@bp.route("/swarm-intel/emergent", methods=["POST"])
@login_required
def api_swarm_intel_emergent():
    if not swarm_intel: return _unavailable("Swarm Intelligence")
    d = request.json or {}
    return jsonify(swarm_intel.set_emergent_behavior(
        d.get("swarm_id", ""), d.get("behavior", "surround"), d.get("target")))

@bp.route("/swarm-intel/dissolve", methods=["POST"])
@login_required
def api_swarm_intel_dissolve():
    if not swarm_intel: return _unavailable("Swarm Intelligence")
    sid = (request.json or {}).get("swarm_id", "")
    return jsonify(swarm_intel.dissolve(sid))

@bp.route("/swarm-intel/auction", methods=["POST"])
@login_required
def api_swarm_intel_auction():
    if not swarm_intel: return _unavailable("Swarm Intelligence")
    d = request.json or {}
    auction = swarm_intel.create_auction(
        d.get("task_type", "surveil"), d.get("target", {}),
        d.get("priority", 5), d.get("required_sensors"))
    return jsonify({"status": "ok", "auction": auction})

@bp.route("/swarm-intel/auctions")
@login_required
def api_swarm_intel_auctions():
    if not swarm_intel: return _unavailable("Swarm Intelligence")
    return jsonify(swarm_intel.get_auctions())


# ═══════════════════════════════════════════════════════════
#  ISR PIPELINE — ATR, Pattern-of-Life, Collections
# ═══════════════════════════════════════════════════════════
@bp.route("/isr/status")
@login_required
def api_isr_status():
    if not isr_pipeline: return _unavailable("ISR Pipeline")
    return jsonify(isr_pipeline.get_stats())

@bp.route("/isr/targets")
@login_required
def api_isr_targets():
    if not isr_pipeline: return _unavailable("ISR Pipeline")
    return jsonify(isr_pipeline.get_targets())

@bp.route("/isr/target/<tid>")
@login_required
def api_isr_target_detail(tid):
    if not isr_pipeline: return _unavailable("ISR Pipeline")
    detail = isr_pipeline.get_target_detail(tid)
    if not detail:
        return jsonify({"error": "Target not found"}), 404
    return jsonify(detail)

@bp.route("/isr/patterns")
@login_required
def api_isr_patterns():
    if not isr_pipeline: return _unavailable("ISR Pipeline")
    return jsonify(isr_pipeline.get_patterns())

@bp.route("/isr/changes")
@login_required
def api_isr_changes():
    if not isr_pipeline: return _unavailable("ISR Pipeline")
    limit = request.args.get("limit", 50, type=int)
    return jsonify(isr_pipeline.get_changes(limit))

@bp.route("/isr/collections")
@login_required
def api_isr_collections():
    if not isr_pipeline: return _unavailable("ISR Pipeline")
    return jsonify(isr_pipeline.get_collections())

@bp.route("/isr/collections/add", methods=["POST"])
@login_required
def api_isr_collection_add():
    if not isr_pipeline: return _unavailable("ISR Pipeline")
    d = request.json or {}
    req = isr_pipeline.add_collection_requirement(
        d.get("name", "Collection Requirement"),
        d.get("target", {}),
        d.get("priority", 5),
        d.get("required_sensors"),
    )
    return jsonify({"status": "ok", "requirement": req})


# ═══════════════════════════════════════════════════════════
#  EFFECTS CHAIN — Multi-Domain Effects Orchestration
# ═══════════════════════════════════════════════════════════
@bp.route("/effects/status")
@login_required
def api_effects_status():
    if not effects_chain: return _unavailable("Effects Chain")
    return jsonify(effects_chain.get_stats())

@bp.route("/effects/chains")
@login_required
def api_effects_chains():
    if not effects_chain: return _unavailable("Effects Chain")
    return jsonify(effects_chain.get_chains())

@bp.route("/effects/active")
@login_required
def api_effects_active():
    if not effects_chain: return _unavailable("Effects Chain")
    return jsonify(effects_chain.get_active())

@bp.route("/effects/templates")
@login_required
def api_effects_templates():
    if not effects_chain: return _unavailable("Effects Chain")
    return jsonify(effects_chain.get_templates())

@bp.route("/effects/create", methods=["POST"])
@login_required
def api_effects_create():
    if not effects_chain: return _unavailable("Effects Chain")
    d = request.json or {}
    chain = effects_chain.create_chain(
        d.get("name", ""), d.get("target", {}),
        stages=d.get("stages"), template=d.get("template"))
    return jsonify(chain)

@bp.route("/effects/execute", methods=["POST"])
@login_required
def api_effects_execute():
    if not effects_chain: return _unavailable("Effects Chain")
    d = request.json or {}
    result = effects_chain.execute_chain(d.get("chain_id", ""), ctx()["user"])
    return jsonify(result)

@bp.route("/effects/abort", methods=["POST"])
@login_required
def api_effects_abort():
    if not effects_chain: return _unavailable("Effects Chain")
    d = request.json or {}
    return jsonify(effects_chain.abort_chain(d.get("chain_id", ""), d.get("reason", "Manual abort")))

@bp.route("/effects/history")
@login_required
def api_effects_history():
    if not effects_chain: return _unavailable("Effects Chain")
    return jsonify(effects_chain.get_history())


# ═══════════════════════════════════════════════════════════
#  SPACE DOMAIN — Orbital Assets, SATCOM, GPS, JADC2
# ═══════════════════════════════════════════════════════════
@bp.route("/space/status")
@login_required
def api_space_status():
    if not space_domain: return _unavailable("Space Domain")
    return jsonify(space_domain.get_stats())

@bp.route("/space/orbital")
@login_required
def api_space_orbital():
    if not space_domain: return _unavailable("Space Domain")
    return jsonify(space_domain.get_orbital_status())

@bp.route("/space/satcom")
@login_required
def api_space_satcom():
    if not space_domain: return _unavailable("Space Domain")
    return jsonify(space_domain.get_satcom_links())

@bp.route("/space/gps")
@login_required
def api_space_gps():
    if not space_domain: return _unavailable("Space Domain")
    return jsonify(space_domain.get_gps_status())

@bp.route("/space/weather")
@login_required
def api_space_weather():
    if not space_domain: return _unavailable("Space Domain")
    return jsonify(space_domain.get_space_weather())

@bp.route("/space/mesh")
@login_required
def api_space_mesh():
    if not space_domain: return _unavailable("Space Domain")
    return jsonify(space_domain.get_mesh())

@bp.route("/space/gps-denial/add", methods=["POST"])
@login_required
def api_space_gps_denial_add():
    if not space_domain: return _unavailable("Space Domain")
    d = request.json or {}
    zone = space_domain.add_gps_denial_zone(
        d.get("lat", 0), d.get("lng", 0),
        d.get("radius_km", 20), d.get("severity", "moderate"))
    return jsonify({"status": "ok", "zone": zone})

@bp.route("/space/gps-denial/remove", methods=["POST"])
@login_required
def api_space_gps_denial_remove():
    if not space_domain: return _unavailable("Space Domain")
    zid = (request.json or {}).get("zone_id", "")
    return jsonify(space_domain.remove_gps_denial_zone(zid))


# ═══════════════════════════════════════════════════════════
#  HMT ENGINE — Operator Workload, Trust, Autonomy
# ═══════════════════════════════════════════════════════════
@bp.route("/hmt/status")
@login_required
def api_hmt_status():
    if not hmt_engine: return _unavailable("HMT Engine")
    return jsonify({
        "operators": hmt_engine.get_status(),
        "stats": hmt_engine.get_stats(),
        "delegations": hmt_engine.get_delegations(),
        "autonomy_levels": hmt_engine.get_autonomy_levels(),
    })

@bp.route("/hmt/workload")
@login_required
def api_hmt_workload():
    if not hmt_engine: return _unavailable("HMT Engine")
    user = request.args.get("user")
    return jsonify(hmt_engine.get_workload(user))

@bp.route("/hmt/trust")
@login_required
def api_hmt_trust():
    if not hmt_engine: return _unavailable("HMT Engine")
    user = request.args.get("user")
    return jsonify(hmt_engine.get_trust_details(user))

@bp.route("/hmt/autonomy", methods=["POST"])
@login_required
def api_hmt_set_autonomy():
    if not hmt_engine: return _unavailable("HMT Engine")
    d = request.json or {}
    return jsonify(hmt_engine.set_global_autonomy(d.get("level", 3), ctx()["user"]))

@bp.route("/hmt/delegate", methods=["POST"])
@login_required
def api_hmt_delegate():
    if not hmt_engine: return _unavailable("HMT Engine")
    d = request.json or {}
    return jsonify(hmt_engine.delegate(
        ctx()["user"], d.get("domain", ""),
        d.get("level", 3), d.get("target_user")))

@bp.route("/hmt/revoke", methods=["POST"])
@login_required
def api_hmt_revoke():
    if not hmt_engine: return _unavailable("HMT Engine")
    d = request.json or {}
    return jsonify(hmt_engine.revoke_delegation(ctx()["user"], d.get("domain", "")))

@bp.route("/hmt/interaction", methods=["POST"])
@login_required
def api_hmt_interaction():
    """Record an operator interaction for workload/fatigue tracking."""
    if not hmt_engine: return _unavailable("HMT Engine")
    d = request.json or {}
    hmt_engine.record_interaction(
        ctx()["user"], d.get("action_type", "click"),
        d.get("response_time_ms"))
    return jsonify({"status": "ok"})


# ═══════════════════════════════════════════════════════════
#  KILL WEB — F2T2EA Pipelines
# ═══════════════════════════════════════════════════════════
@bp.route("/killweb/status")
@login_required
def api_killweb_status():
    if not kill_web: return _unavailable("Kill Web")
    return jsonify(kill_web.get_stats())

@bp.route("/killweb/pipelines")
@login_required
def api_killweb_pipelines():
    if not kill_web: return _unavailable("Kill Web")
    include_completed = request.args.get("include_completed", "true").lower() == "true"
    return jsonify(kill_web.get_pipelines(include_completed))

@bp.route("/killweb/approve", methods=["POST"])
@login_required
def api_killweb_approve():
    if not kill_web: return _unavailable("Kill Web")
    d = request.json or {}
    result = kill_web.approve_pipeline(d.get("pipeline_id", ""), ctx()["user"])
    if result:
        return jsonify({"status": "ok", "pipeline": result})
    return jsonify({"error": "Pipeline not found or not awaiting approval"}), 404

@bp.route("/killweb/abort", methods=["POST"])
@login_required
def api_killweb_abort():
    if not kill_web: return _unavailable("Kill Web")
    d = request.json or {}
    result = kill_web.abort_pipeline(d.get("pipeline_id", ""), d.get("reason", "Manual abort"))
    if result:
        return jsonify({"status": "ok", "pipeline": result})
    return jsonify({"error": "Pipeline not found"}), 404


# ═══════════════════════════════════════════════════════════
#  CONTESTED ENVIRONMENT — GPS Denial, Comms, Mesh
# ═══════════════════════════════════════════════════════════
@bp.route("/contested/status")
@login_required
def api_contested_status():
    if not contested_env: return _unavailable("Contested Environment")
    return jsonify(contested_env.get_status())

@bp.route("/contested/gps")
@login_required
def api_contested_gps():
    if not contested_env: return _unavailable("Contested Environment")
    return jsonify(contested_env.get_gps_status())

@bp.route("/contested/comms")
@login_required
def api_contested_comms():
    if not contested_env: return _unavailable("Contested Environment")
    return jsonify(contested_env.get_comms_status())

@bp.route("/contested/mesh")
@login_required
def api_contested_mesh():
    if not contested_env: return _unavailable("Contested Environment")
    return jsonify(contested_env.get_mesh())

@bp.route("/contested/gps-denial/add", methods=["POST"])
@login_required
def api_contested_gps_denial_add():
    if not contested_env: return _unavailable("Contested Environment")
    d = request.json or {}
    zone = contested_env.add_gps_denial_zone(
        d.get("lat", 0), d.get("lng", 0),
        d.get("radius_nm", 3), d.get("power_dbm", 40),
        d.get("name", ""))
    return jsonify({"status": "ok", "zone": zone})

@bp.route("/contested/gps-denial/remove", methods=["POST"])
@login_required
def api_contested_gps_denial_remove():
    if not contested_env: return _unavailable("Contested Environment")
    zid = (request.json or {}).get("zone_id", "")
    contested_env.remove_gps_denial_zone(zid)
    return jsonify({"status": "ok"})


# ═══════════════════════════════════════════════════════════
#  NLP MISSION PARSER — Natural Language Command Parsing
# ═══════════════════════════════════════════════════════════
@bp.route("/nlp/parse", methods=["POST"])
@login_required
def api_nlp_parse():
    if not nlp_parser: return _unavailable("NLP Mission Parser")
    d = request.json or {}
    transcript = d.get("transcript", d.get("command", ""))
    if not transcript:
        return jsonify({"error": "transcript required"}), 400
    result = nlp_parser.parse(transcript, sim_assets)
    return jsonify(result)

@bp.route("/nlp/history")
@login_required
def api_nlp_history():
    if not nlp_parser: return _unavailable("NLP Mission Parser")
    limit = request.args.get("limit", 50, type=int)
    return jsonify(nlp_parser.get_history(limit))


# ═══════════════════════════════════════════════════════════
#  COMSEC / SECURITY — Encryption, Keys, Audit
# ═══════════════════════════════════════════════════════════
@bp.route("/comsec/status")
@login_required
def api_comsec_status():
    if not comsec_channel: return _unavailable("COMSEC")
    return jsonify(comsec_channel.get_status())

@bp.route("/comsec/encrypt", methods=["POST"])
@login_required
def api_comsec_encrypt():
    if not comsec_channel: return _unavailable("COMSEC")
    d = request.json or {}
    message = d.get("message", {})
    if not message:
        return jsonify({"error": "message dict required"}), 400
    envelope = comsec_channel.encrypt_message(message)
    return jsonify(envelope)

@bp.route("/comsec/decrypt", methods=["POST"])
@login_required
def api_comsec_decrypt():
    if not comsec_channel: return _unavailable("COMSEC")
    envelope = request.json or {}
    try:
        plaintext = comsec_channel.decrypt_message(envelope)
        return jsonify({"status": "ok", "message": plaintext})
    except ValueError as e:
        return jsonify({"error": str(e)}), 403

@bp.route("/keys/status")
@login_required
def api_keys_status():
    if not key_mgr: return _unavailable("Key Manager")
    return jsonify(key_mgr.get_status())

@bp.route("/keys/list")
@login_required
def api_keys_list():
    if not key_mgr: return _unavailable("Key Manager")
    state = request.args.get("state")
    return jsonify(key_mgr.list_keys(state))

@bp.route("/keys/generate", methods=["POST"])
@login_required
def api_keys_generate():
    if not key_mgr: return _unavailable("Key Manager")
    d = request.json or {}
    key = key_mgr.generate_key(
        d.get("purpose", "channel"), d.get("ttl_seconds", 86400))
    if security_audit:
        security_audit.log_crypto("KEY_GENERATE", f"Key {key['key_id']} for {key.get('purpose')}")
    return jsonify({"status": "ok", "key": key})

@bp.route("/keys/rotate", methods=["POST"])
@login_required
def api_keys_rotate():
    if not key_mgr: return _unavailable("Key Manager")
    kid = (request.json or {}).get("key_id", "")
    result = key_mgr.rotate_key(kid)
    if security_audit:
        security_audit.log_crypto("KEY_ROTATE", f"Rotated {kid}")
    return jsonify(result)

@bp.route("/keys/revoke", methods=["POST"])
@login_required
def api_keys_revoke():
    if not key_mgr: return _unavailable("Key Manager")
    d = request.json or {}
    ok = key_mgr.revoke_key(d.get("key_id", ""), d.get("reason", ""))
    if security_audit:
        security_audit.log_crypto("KEY_REVOKE", f"Revoked {d.get('key_id')}: {d.get('reason')}")
    return jsonify({"status": "ok" if ok else "not_found"})

@bp.route("/audit/events")
@login_required
def api_audit_events():
    if not security_audit: return _unavailable("Security Audit")
    category = request.args.get("category")
    severity = request.args.get("severity")
    user = request.args.get("user")
    limit = request.args.get("limit", 50, type=int)
    return jsonify(security_audit.get_events(category, severity, user, limit))

@bp.route("/audit/verify")
@login_required
def api_audit_verify():
    if not security_audit: return _unavailable("Security Audit")
    return jsonify(security_audit.verify_chain())

@bp.route("/audit/status")
@login_required
def api_audit_status():
    if not security_audit: return _unavailable("Security Audit")
    return jsonify(security_audit.get_status())


# ═══════════════════════════════════════════════════════════
#  ENTERPRISE SUMMARY — Aggregate status of all modules
# ═══════════════════════════════════════════════════════════
@bp.route("/enterprise/status")
@login_required
def api_enterprise_summary():
    """Aggregate status of all enterprise modules."""
    modules = {}
    if cognitive_engine:
        modules["cognitive_engine"] = cognitive_engine.get_stats()
    if commander_support:
        modules["commander_support"] = {"risk": commander_support.get_risk()}
    if learning_engine:
        modules["learning_engine"] = {
            "engagement_stats": learning_engine.get_engagement_stats(),
            "anomaly_count": len(learning_engine.get_anomalies()),
        }
    if red_force_ai:
        modules["red_force_ai"] = red_force_ai.get_stats()
    if wargame_engine:
        modules["wargame_engine"] = wargame_engine.get_stats()
    if threat_predictor:
        modules["threat_predictor"] = {
            "predictions": len(threat_predictor.get_predictions()),
            "patterns": len(threat_predictor.get_patterns()),
        }
    if swarm_intel:
        modules["swarm_intelligence"] = swarm_intel.get_stats()
    if isr_pipeline:
        modules["isr_pipeline"] = isr_pipeline.get_stats()
    if effects_chain:
        modules["effects_chain"] = effects_chain.get_stats()
    if space_domain:
        modules["space_domain"] = space_domain.get_stats()
    if hmt_engine:
        modules["hmt_engine"] = hmt_engine.get_stats()
    if kill_web:
        modules["kill_web"] = kill_web.get_stats()
    if contested_env:
        modules["contested_environment"] = contested_env.get_status().get("stats", {})
    if nlp_parser:
        modules["nlp_parser"] = {"history_count": len(nlp_parser.get_history())}
    if comsec_channel:
        modules["comsec"] = comsec_channel.get_status()
    if key_mgr:
        modules["key_manager"] = key_mgr.get_status()
    if security_audit:
        modules["security_audit"] = security_audit.get_status()

    return jsonify({
        "modules_loaded": len(modules),
        "modules": modules,
        "timestamp": now_iso(),
    })
