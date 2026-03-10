"""AMOS Enterprise — Warfare Routes (Kill Web, Swarm Intel, ISR, Effects, Space, HMT, Mesh)."""

from flask import Blueprint, request, jsonify
from web.extensions import login_required, ctx
from web.state import (
    kill_web, swarm_intel, isr_pipeline, effects_chain,
    space_domain, hmt_engine, mesh_network,
    sim_assets, sim_threats, sim_clock, aar_events,
    base_pos, now_iso,
)

bp = Blueprint("ent_warfare", __name__)


# ═══════════════════════════════════════════════════════════
#  KILL WEB
# ═══════════════════════════════════════════════════════════
@bp.route("/api/killweb/pipelines")
@login_required
def api_killweb_pipelines():
    if not kill_web: return jsonify([])
    return jsonify(kill_web.get_pipelines())

@bp.route("/api/killweb/stats")
@login_required
def api_killweb_stats():
    if not kill_web: return jsonify({})
    return jsonify(kill_web.get_stats())

@bp.route("/api/killweb/approve/<pipeline_id>", methods=["POST"])
@login_required
def api_killweb_approve(pipeline_id):
    if not kill_web: return jsonify({"error": "Kill web not available"}), 503
    c = ctx()
    result = kill_web.approve_pipeline(pipeline_id, c["name"])
    if not result:
        return jsonify({"error": "Pipeline not found or not awaiting approval"}), 404
    aar_events.append({"type": "killweb", "timestamp": now_iso(),
        "elapsed": sim_clock["elapsed_sec"],
        "details": f"ENGAGE approved by {c['name']} for {result['threat_id']}"})
    return jsonify({"status": "ok", "pipeline": result})

@bp.route("/api/killweb/abort/<pipeline_id>", methods=["POST"])
@login_required
def api_killweb_abort(pipeline_id):
    if not kill_web: return jsonify({"error": "Kill web not available"}), 503
    reason = (request.json or {}).get("reason", "Manual abort")
    result = kill_web.abort_pipeline(pipeline_id, reason)
    if not result:
        return jsonify({"error": "Pipeline not found"}), 404
    return jsonify({"status": "ok", "pipeline": result})


# ═══════════════════════════════════════════════════════════
#  SWARM INTELLIGENCE
# ═══════════════════════════════════════════════════════════
@bp.route("/api/swarm/create", methods=["POST"])
@login_required
def api_swarm_create():
    if not swarm_intel: return jsonify({"error": "Swarm intel not available"}), 503
    d = request.json or {}
    result = swarm_intel.create_swarm(
        d.get("swarm_id", f"SWM-{__import__('uuid').uuid4().hex[:6]}"),
        d.get("asset_ids", []), d.get("behavior", "scout"),
        d.get("center_lat", base_pos["lat"]), d.get("center_lng", base_pos["lng"]),
        d.get("target"))
    return jsonify(result)

@bp.route("/api/swarm/behavior", methods=["POST"])
@login_required
def api_swarm_behavior():
    if not swarm_intel: return jsonify({"error": "Swarm intel not available"}), 503
    d = request.json or {}
    sid = d.get("swarm_id", "")
    if d.get("emergent"):
        result = swarm_intel.set_emergent_behavior(sid, d["emergent"], d.get("target"))
    else:
        result = swarm_intel.set_behavior(sid, d.get("behavior", "scout"))
    return jsonify(result)

@bp.route("/api/swarm/auction", methods=["POST"])
@login_required
def api_swarm_auction():
    if not swarm_intel: return jsonify({"error": "Swarm intel not available"}), 503
    d = request.json or {}
    result = swarm_intel.create_auction(
        d.get("task_type", "surveil"), d.get("target", {}),
        d.get("priority", 5), d.get("required_sensors"))
    return jsonify(result)

@bp.route("/api/swarm/status")
@login_required
def api_swarm_status():
    if not swarm_intel: return jsonify({})
    return jsonify({"swarms": swarm_intel.get_swarms(),
                    "auctions": swarm_intel.get_auctions(),
                    "stats": swarm_intel.get_stats()})

@bp.route("/api/swarm/dissolve", methods=["POST"])
@login_required
def api_swarm_dissolve():
    if not swarm_intel: return jsonify({"error": "Swarm intel not available"}), 503
    sid = (request.json or {}).get("swarm_id", "")
    return jsonify(swarm_intel.dissolve(sid))


# ═══════════════════════════════════════════════════════════
#  ISR / ATR PIPELINE
# ═══════════════════════════════════════════════════════════
@bp.route("/api/isr/collections")
@login_required
def api_isr_collections():
    if not isr_pipeline: return jsonify([])
    return jsonify(isr_pipeline.get_collections())

@bp.route("/api/isr/atr/<target_id>")
@login_required
def api_isr_atr(target_id):
    if not isr_pipeline: return jsonify({})
    return jsonify(isr_pipeline.get_target_detail(target_id))

@bp.route("/api/isr/patterns")
@login_required
def api_isr_patterns():
    if not isr_pipeline: return jsonify([])
    return jsonify(isr_pipeline.get_patterns())

@bp.route("/api/isr/changes")
@login_required
def api_isr_changes():
    if not isr_pipeline: return jsonify([])
    limit = request.args.get("limit", 50, type=int)
    return jsonify(isr_pipeline.get_changes(limit))

@bp.route("/api/isr/task", methods=["POST"])
@login_required
def api_isr_task():
    if not isr_pipeline: return jsonify({"error": "ISR pipeline not available"}), 503
    d = request.json or {}
    result = isr_pipeline.add_collection_requirement(
        d.get("name", "Collection Req"), d.get("target", {}),
        d.get("priority", 5), d.get("required_sensors"))
    return jsonify(result)

@bp.route("/api/isr/targets")
@login_required
def api_isr_targets():
    if not isr_pipeline: return jsonify([])
    return jsonify(isr_pipeline.get_targets())


# ═══════════════════════════════════════════════════════════
#  EFFECTS CHAIN
# ═══════════════════════════════════════════════════════════
@bp.route("/api/effects/create", methods=["POST"])
@login_required
def api_effects_create():
    if not effects_chain: return jsonify({"error": "Effects chain not available"}), 503
    d = request.json or {}
    result = effects_chain.create_chain(
        d.get("name", ""), d.get("target", {}),
        stages=d.get("stages"), template=d.get("template"))
    return jsonify(result)

@bp.route("/api/effects/execute/<chain_id>", methods=["POST"])
@login_required
def api_effects_execute(chain_id):
    if not effects_chain: return jsonify({"error": "Effects chain not available"}), 503
    c = ctx()
    result = effects_chain.execute_chain(chain_id, c["name"])
    if "error" not in result:
        aar_events.append({"type": "effects", "timestamp": now_iso(),
            "elapsed": sim_clock["elapsed_sec"],
            "details": f"Effects chain {chain_id} started by {c['name']}"})
    return jsonify(result)

@bp.route("/api/effects/status")
@login_required
def api_effects_status():
    if not effects_chain: return jsonify({})
    return jsonify({"chains": effects_chain.get_chains(),
                    "active": effects_chain.get_active(),
                    "stats": effects_chain.get_stats()})

@bp.route("/api/effects/history")
@login_required
def api_effects_history():
    if not effects_chain: return jsonify([])
    return jsonify(effects_chain.get_history())

@bp.route("/api/effects/templates")
@login_required
def api_effects_templates():
    if not effects_chain: return jsonify([])
    return jsonify(effects_chain.get_templates())

@bp.route("/api/effects/abort/<chain_id>", methods=["POST"])
@login_required
def api_effects_abort(chain_id):
    if not effects_chain: return jsonify({"error": "Effects chain not available"}), 503
    reason = (request.json or {}).get("reason", "Manual abort")
    return jsonify(effects_chain.abort_chain(chain_id, reason))


# ═══════════════════════════════════════════════════════════
#  SPACE DOMAIN + JADC2
# ═══════════════════════════════════════════════════════════
@bp.route("/api/space/orbital")
@login_required
def api_space_orbital():
    if not space_domain: return jsonify({})
    return jsonify(space_domain.get_orbital_status())

@bp.route("/api/space/satcom")
@login_required
def api_space_satcom():
    if not space_domain: return jsonify({})
    return jsonify(space_domain.get_satcom_links())

@bp.route("/api/space/gps")
@login_required
def api_space_gps():
    if not space_domain: return jsonify({})
    return jsonify(space_domain.get_gps_status())

@bp.route("/api/space/weather")
@login_required
def api_space_weather():
    if not space_domain: return jsonify({})
    return jsonify(space_domain.get_space_weather())

@bp.route("/api/space/mesh")
@login_required
def api_space_mesh():
    if not space_domain: return jsonify({})
    return jsonify(space_domain.get_mesh())

@bp.route("/api/space/gps-denial", methods=["POST"])
@login_required
def api_space_gps_denial():
    if not space_domain: return jsonify({"error": "Space domain not available"}), 503
    d = request.json or {}
    zone = space_domain.add_gps_denial_zone(
        d.get("lat", base_pos["lat"]), d.get("lng", base_pos["lng"]),
        d.get("radius_km", 20), d.get("severity", "moderate"))
    return jsonify(zone)


# ═══════════════════════════════════════════════════════════
#  HUMAN-MACHINE TEAMING
# ═══════════════════════════════════════════════════════════
@bp.route("/api/hmt/status")
@login_required
def api_hmt_status():
    if not hmt_engine: return jsonify({})
    return jsonify(hmt_engine.get_status())

@bp.route("/api/hmt/trust")
@login_required
def api_hmt_trust():
    if not hmt_engine: return jsonify({})
    user = request.args.get("user")
    return jsonify(hmt_engine.get_trust_details(user))

@bp.route("/api/hmt/delegate", methods=["POST"])
@login_required
def api_hmt_delegate():
    if not hmt_engine: return jsonify({"error": "HMT engine not available"}), 503
    c = ctx()
    d = request.json or {}
    result = hmt_engine.delegate(c["user"], d.get("domain", "all"),
        d.get("level", 4), d.get("target_user"))
    return jsonify(result)

@bp.route("/api/hmt/workload")
@login_required
def api_hmt_workload():
    if not hmt_engine: return jsonify({})
    user = request.args.get("user")
    return jsonify(hmt_engine.get_workload(user))

@bp.route("/api/hmt/autonomy", methods=["POST"])
@login_required
def api_hmt_autonomy():
    if not hmt_engine: return jsonify({"error": "HMT engine not available"}), 503
    c = ctx()
    d = request.json or {}
    return jsonify(hmt_engine.set_global_autonomy(d.get("level", 3), c["name"]))


# ═══════════════════════════════════════════════════════════
#  MESH NETWORK
# ═══════════════════════════════════════════════════════════
@bp.route("/api/mesh/topology")
@login_required
def api_mesh_topology():
    if not mesh_network: return jsonify({})
    return jsonify(mesh_network.get_topology())

@bp.route("/api/mesh/routes")
@login_required
def api_mesh_routes():
    if not mesh_network: return jsonify({})
    return jsonify(mesh_network.get_routes())

@bp.route("/api/mesh/bandwidth")
@login_required
def api_mesh_bandwidth():
    if not mesh_network: return jsonify({})
    return jsonify(mesh_network.get_bandwidth())

@bp.route("/api/mesh/resilience")
@login_required
def api_mesh_resilience():
    if not mesh_network: return jsonify({})
    return jsonify(mesh_network.get_resilience())

@bp.route("/api/mesh/degrade", methods=["POST"])
@login_required
def api_mesh_degrade():
    if not mesh_network: return jsonify({"error": "Mesh network not available"}), 503
    d = request.json or {}
    return jsonify(mesh_network.degrade_link(d.get("node_id", ""), d.get("amount", 30)))
