"""AMOS Mission Routes — Waypoints, Geofences, Voice, Tasks, Planning, CommsNet."""

import uuid, random, math
from flask import Blueprint, request, jsonify
from web.extensions import login_required, ctx
from web.state import (sim_assets, sim_threats, sim_clock, base_pos, waypoint_nav,
                       geofence_mgr, voice_parser, task_allocator,
                       aar_events, cm_log, ew_active_jams, cyber_blocked_ips, cyber_events,
                       mission_plans, training_records, now_iso)

bp = Blueprint("missions", __name__)


# ═══════════════════════════════════════════════════════════
#  WAYPOINT API
# ═══════════════════════════════════════════════════════════
@bp.route("/waypoints")
@login_required
def api_wp_all(): return jsonify(waypoint_nav.get_all())

@bp.route("/waypoints/<asset_id>")
@login_required
def api_wp_asset(asset_id): return jsonify(waypoint_nav.get_waypoints(asset_id))

@bp.route("/waypoints/set", methods=["POST"])
@login_required
def api_wp_set():
    d = request.json; aid = d.get("asset_id"); lat = d.get("lat"); lng = d.get("lng")
    if not aid or lat is None or lng is None: return jsonify({"error": "Missing fields"}), 400
    if aid not in sim_assets: return jsonify({"error": "Asset not found"}), 404
    waypoint_nav.set_waypoint(aid, lat, lng, d.get("alt_ft"))
    c = ctx()
    aar_events.append({"type": "waypoint_set", "timestamp": now_iso(),
        "elapsed": sim_clock["elapsed_sec"],
        "details": f"WP set: {aid} -> {lat:.4f},{lng:.4f} by {c['name']}"})
    return jsonify({"status": "ok", "waypoints": waypoint_nav.get_waypoints(aid)})

@bp.route("/waypoints/add", methods=["POST"])
@login_required
def api_wp_add():
    d = request.json; aid = d.get("asset_id"); lat = d.get("lat"); lng = d.get("lng")
    if not aid or lat is None or lng is None: return jsonify({"error": "Missing fields"}), 400
    if aid not in sim_assets: return jsonify({"error": "Asset not found"}), 404
    waypoint_nav.add_waypoint(aid, lat, lng, d.get("alt_ft"))
    return jsonify({"status": "ok", "waypoints": waypoint_nav.get_waypoints(aid)})

@bp.route("/waypoints/clear", methods=["POST"])
@login_required
def api_wp_clear():
    d = request.json; aid = d.get("asset_id")
    if aid: waypoint_nav.clear_waypoints(aid)
    else: waypoint_nav.clear_all()
    return jsonify({"status": "ok"})


# ═══════════════════════════════════════════════════════════
#  GEOFENCE API
# ═══════════════════════════════════════════════════════════
@bp.route("/geofences")
@login_required
def api_gf(): return jsonify(geofence_mgr.get_all())

@bp.route("/geofences/create", methods=["POST"])
@login_required
def api_gf_create():
    d = request.json
    gid = geofence_mgr.add_geofence(d.get("type", "alert"), d.get("points", []),
                                     d.get("name", ""), d.get("id"))
    return jsonify({"status": "ok", "id": gid})

@bp.route("/geofences/delete", methods=["POST"])
@login_required
def api_gf_del():
    geofence_mgr.remove_geofence(request.json.get("id", "")); return jsonify({"status": "ok"})

@bp.route("/geofences/alerts")
@login_required
def api_gf_alerts(): return jsonify(geofence_mgr.get_alerts())


# ═══════════════════════════════════════════════════════════
#  VOICE COMMAND API
# ═══════════════════════════════════════════════════════════
@bp.route("/voice/command", methods=["POST"])
@login_required
def api_voice():
    transcript = request.json.get("transcript", ""); c = ctx()
    parsed = voice_parser.parse(transcript)
    result = {"parsed": parsed, "executed": False, "response": ""}
    cmd = parsed.get("command")

    if cmd == "move" and "lat" in parsed and "lng" in parsed:
        aid = parsed["asset_id"]
        if aid in sim_assets:
            waypoint_nav.set_waypoint(aid, parsed["lat"], parsed["lng"])
            result.update(executed=True, response=f"Roger. {aid} navigating to {parsed['lat']:.4f}, {parsed['lng']:.4f}")
    elif cmd == "engage":
        tid = parsed.get("threat_id", "")
        if tid in sim_threats and not sim_threats[tid].get("neutralized"):
            sim_threats[tid]["neutralized"] = True
            cm_log.append({"id": f"CM-{uuid.uuid4().hex[:8]}", "threat_id": tid, "type": "voice_engage",
                "operator": c["name"], "timestamp": now_iso(), "elapsed": sim_clock["elapsed_sec"]})
            result.update(executed=True, response=f"Roger. {tid} engaged and neutralized.")
    elif cmd == "jam":
        freq = parsed.get("freq_mhz", 0)
        jammers = [a for a in sim_assets.values() if "EW_JAMMER" in (a.get("sensors") or [])]
        if jammers:
            j = jammers[0]
            ew_active_jams.append({"id": f"JAM-{uuid.uuid4().hex[:8]}", "jammer_id": j["id"],
                "target_freq_mhz": freq, "technique": "barrage", "power_dbm": 45,
                "started": now_iso(), "status": "active"})
            result.update(executed=True, response=f"Roger. {j['id']} jamming {freq} MHz.")
    elif cmd == "status":
        aid = parsed.get("asset_id", "")
        if aid in sim_assets:
            a = sim_assets[aid]
            result.update(executed=True,
                response=f"{aid}: {a['status']}, batt {a['health']['battery_pct']:.0f}%, comms {a['health']['comms_strength']:.0f}%, pos {a['position']['lat']:.4f} {a['position']['lng']:.4f}")
    elif cmd == "status_all":
        at = sum(1 for t in sim_threats.values() if not t.get("neutralized"))
        result.update(executed=True, response=f"Platoon: {len(sim_assets)} assets operational. {at} active threats. {len(ew_active_jams)} active jams.")
    elif cmd == "set_speed":
        sim_clock["speed"] = parsed.get("speed", 1.0)
        result.update(executed=True, response=f"Roger. Speed set to {sim_clock['speed']}x.")
    elif cmd == "generate_coa":
        result.update(executed=True, response="Roger. COAs generated. Check HAL panel.")
    elif cmd == "block_ip":
        ip = parsed.get("ip", "")
        cyber_blocked_ips.add(ip)
        for e in cyber_events:
            if e["source_ip"] == ip: e["blocked"] = True
        result.update(executed=True, response=f"Roger. Blocked {ip}.")
    elif cmd == "halt":
        aid = parsed.get("asset_id", ""); waypoint_nav.clear_waypoints(aid)
        result.update(executed=True, response=f"Roger. {aid} halted.")
    elif cmd == "halt_all":
        waypoint_nav.clear_all(); result.update(executed=True, response="Roger. All assets halted.")
    elif cmd == "rtb":
        aid = parsed.get("asset_id", "")
        if aid in sim_assets:
            waypoint_nav.set_waypoint(aid, base_pos["lat"], base_pos["lng"])
            result.update(executed=True, response=f"Roger. {aid} RTB.")
    elif cmd == "rtb_all":
        for aid in sim_assets: waypoint_nav.set_waypoint(aid, base_pos["lat"], base_pos["lng"])
        result.update(executed=True, response="Roger. All assets RTB.")
    else:
        result["response"] = f"Command not recognized: '{transcript}'"

    if result["executed"]:
        aar_events.append({"type": "voice_command", "timestamp": now_iso(),
            "elapsed": sim_clock["elapsed_sec"],
            "details": f"VOICE [{c['name']}]: {transcript} -> {result['response']}"})
    return jsonify(result)


# ═══════════════════════════════════════════════════════════
#  TASK ALLOCATOR API
# ═══════════════════════════════════════════════════════════
@bp.route("/tasks")
@login_required
def api_tasks(): return jsonify(task_allocator.get_tasks())

@bp.route("/tasks/gantt")
@login_required
def api_tasks_gantt(): return jsonify(task_allocator.get_gantt())

@bp.route("/tasks/assign", methods=["POST"])
@login_required
def api_tasks_assign():
    d = request.json
    task_allocator.create_task(
        d.get("task_type", "patrol"), priority=d.get("priority", 5),
        location=d.get("location", {}), required_sensors=d.get("required_capabilities", []))
    return jsonify({"status": "ok", "tasks": len(task_allocator.tasks)})


# ═══════════════════════════════════════════════════════════
#  MISSION PLANNING SUITE
# ═══════════════════════════════════════════════════════════
@bp.route("/missionplan/templates")
@login_required
def api_missionplan_templates():
    return jsonify([
        {"id": "recon_patrol", "name": "Recon Patrol",
         "phases": [{"name": "Departure", "duration_min": 10}, {"name": "Route March", "duration_min": 30},
                    {"name": "ISR Collection", "duration_min": 45}, {"name": "RTB", "duration_min": 20}],
         "pace": {"primary": "SATCOM", "alternate": "HF Radio", "contingency": "Mesh Network", "emergency": "Visual Signal"},
         "asset_roles": ["recon", "isr_strike"], "description": "Standard ISR patrol with 4-phase route"},
        {"id": "strike_mission", "name": "Strike Mission",
         "phases": [{"name": "Assembly", "duration_min": 15}, {"name": "Infiltration", "duration_min": 25},
                    {"name": "Target Acquisition", "duration_min": 20}, {"name": "Execution", "duration_min": 10},
                    {"name": "Exfiltration", "duration_min": 30}],
         "pace": {"primary": "Link-16", "alternate": "SATCOM", "contingency": "HF Radio", "emergency": "Code Word"},
         "asset_roles": ["isr_strike", "direct_action", "ew"], "description": "Coordinated strike with ISR/EW support"},
        {"id": "area_denial", "name": "Area Denial",
         "phases": [{"name": "Deploy", "duration_min": 20}, {"name": "Establish Perimeter", "duration_min": 30},
                    {"name": "Active Denial", "duration_min": 120}, {"name": "Withdrawal", "duration_min": 25}],
         "pace": {"primary": "Mesh Network", "alternate": "SATCOM", "contingency": "UHF", "emergency": "Runner"},
         "asset_roles": ["direct_action", "ew", "recon"], "description": "Perimeter defense with EW support"},
        {"id": "csar", "name": "CSAR (Combat Search & Rescue)",
         "phases": [{"name": "Alert", "duration_min": 5}, {"name": "Ingress", "duration_min": 30},
                    {"name": "Search", "duration_min": 45}, {"name": "Recovery", "duration_min": 15},
                    {"name": "Egress", "duration_min": 25}],
         "pace": {"primary": "SATCOM", "alternate": "Guard Freq", "contingency": "Mesh Network", "emergency": "EPIRB/PLB"},
         "asset_roles": ["medevac", "recon", "air_superiority"], "description": "Personnel recovery with air cover"},
    ])

@bp.route("/missionplan/save", methods=["POST"])
@login_required
def api_missionplan_save():
    d = request.json or {}
    pid = d.get("id") or f"MP-{uuid.uuid4().hex[:8]}"
    c = ctx()
    mission_plans[pid] = {
        "id": pid, "name": d.get("name", "Unnamed Plan"),
        "template": d.get("template", ""),
        "waypoints": d.get("waypoints", []),
        "phases": d.get("phases", []),
        "pace": d.get("pace", {}),
        "assets": d.get("assets", []),
        "created_at": now_iso(), "created_by": c["name"]}
    return jsonify({"status": "ok", "plan": mission_plans[pid]})

@bp.route("/missionplan/list")
@login_required
def api_missionplan_list(): return jsonify(list(mission_plans.values()))

@bp.route("/missionplan/<plan_id>")
@login_required
def api_missionplan_get(plan_id):
    p = mission_plans.get(plan_id)
    if not p: return jsonify({"error": "Plan not found"}), 404
    return jsonify(p)


# ═══════════════════════════════════════════════════════════
#  TRAINING & CERTIFICATION
# ═══════════════════════════════════════════════════════════
_CERT_LEVELS = [
    {"level": 1, "name": "NOVICE", "min_exercises": 0, "min_avg": 0, "color": "#888"},
    {"level": 2, "name": "BASIC", "min_exercises": 2, "min_avg": 40, "color": "#ffaa00"},
    {"level": 3, "name": "QUALIFIED", "min_exercises": 5, "min_avg": 60, "color": "#00ff41"},
    {"level": 4, "name": "EXPERT", "min_exercises": 10, "min_avg": 75, "color": "#00ccff"},
    {"level": 5, "name": "MASTER", "min_exercises": 20, "min_avg": 85, "color": "#ff44ff"},
]

def _compute_cert(user):
    recs = [r for r in training_records if r["operator"] == user]
    count = len(recs)
    avg = sum(r["pct"] for r in recs) / max(1, count)
    best = max((r["pct"] for r in recs), default=0)
    cert = _CERT_LEVELS[0]
    for cl in _CERT_LEVELS:
        if count >= cl["min_exercises"] and avg >= cl["min_avg"]:
            cert = cl
    return {"user": user, "exercises": count, "avg_score": round(avg, 1),
            "best_score": round(best, 1), "cert_level": cert["level"],
            "cert_name": cert["name"], "cert_color": cert["color"]}

@bp.route("/training/history")
@login_required
def api_training_history(): return jsonify(training_records)

@bp.route("/training/leaderboard")
@login_required
def api_training_leaderboard():
    operators = set(r["operator"] for r in training_records)
    board = []
    for op in operators:
        info = _compute_cert(op)
        total = sum(r["score"] for r in training_records if r["operator"] == op)
        info["total_score"] = total
        info["name"] = next((r["name"] for r in training_records if r["operator"] == op), op)
        board.append(info)
    board.sort(key=lambda x: x["total_score"], reverse=True)
    for i, b in enumerate(board):
        b["rank"] = i + 1
    return jsonify(board)

@bp.route("/training/cert/<user>")
@login_required
def api_training_cert(user): return jsonify(_compute_cert(user))

@bp.route("/training/record", methods=["POST"])
@login_required
def api_training_record():
    d = request.json or {}; c = ctx()
    score = int(d.get("score", 0)); mx = int(d.get("max_score", 100))
    pct = round(score / max(1, mx) * 100, 1)
    rec = {"id": f"TR-{uuid.uuid4().hex[:8]}", "operator": d.get("operator", c["user"]),
           "name": d.get("name", c["name"]), "exercise_name": d.get("exercise_name", "Manual Entry"),
           "score": score, "max_score": mx, "pct": pct, "passed": pct >= 60,
           "timestamp": now_iso()}
    training_records.append(rec)
    return jsonify({"status": "ok", "record": rec})


# ═══════════════════════════════════════════════════════════
#  COMMS NETWORK
# ═══════════════════════════════════════════════════════════
@bp.route("/commsnet/topology")
@login_required
def api_commsnet_topology():
    nodes, links = [], []
    for aid, a in sim_assets.items():
        cs = a["health"]["comms_strength"]
        status = "good" if cs > 60 else "degraded" if cs > 25 else "denied"
        nodes.append({"id": aid, "type": a["type"], "domain": a["domain"],
            "lat": a["position"]["lat"], "lng": a["position"]["lng"],
            "comms_pct": round(cs), "status": status,
            "method": "SATCOM" if a["domain"] == "air" else "Mesh",
            "relay_hops": random.randint(0, 2) if cs > 25 else 0})
    asset_list = list(sim_assets.values())
    for i, a in enumerate(asset_list):
        for j in range(i + 1, len(asset_list)):
            b = asset_list[j]
            dlat = abs(a["position"]["lat"] - b["position"]["lat"])
            dlng = abs(a["position"]["lng"] - b["position"]["lng"])
            dist = math.sqrt(dlat ** 2 + dlng ** 2)
            if dist < 0.08:
                quality = max(10, 100 - dist * 1200 + random.uniform(-10, 10))
                links.append({"from": a["id"], "to": b["id"],
                    "quality": round(min(100, quality)), "distance_deg": round(dist, 4),
                    "active": quality > 20, "encrypted": True,
                    "bandwidth_kbps": round(random.uniform(128, 2048) * (quality / 100))})
    return jsonify({"nodes": nodes, "links": links,
                    "total_nodes": len(nodes), "active_links": sum(1 for l in links if l["active"]),
                    "avg_quality": round(sum(n["comms_pct"] for n in nodes) / max(1, len(nodes)), 1)})

@bp.route("/commsnet/links")
@login_required
def api_commsnet_links():
    link_details = []
    for aid, a in sim_assets.items():
        cs = a["health"]["comms_strength"]
        snr = round(cs * 0.3 + random.uniform(-2, 2), 1)
        link_details.append({"asset_id": aid, "domain": a["domain"],
            "signal_dbm": round(-90 + cs * 0.6 + random.uniform(-3, 3)),
            "noise_dbm": round(-110 + random.uniform(-5, 5)),
            "snr_db": max(0, snr), "bandwidth_util_pct": round(random.uniform(15, 85), 1),
            "latency_ms": round(random.uniform(5, 200) * (100 / max(10, cs))),
            "packet_loss_pct": round(max(0, (100 - cs) * 0.15 + random.uniform(-1, 1)), 2),
            "encryption": "AES-256", "protocol": "MANET" if a["domain"] != "air" else "SATCOM"})
    return jsonify(link_details)

@bp.route("/commsnet/heatmap")
@login_required
def api_commsnet_heatmap():
    points = []
    for a in sim_assets.values():
        cs = a["health"]["comms_strength"]
        if cs < 70:
            intensity = (70 - cs) / 70
            points.append({"lat": a["position"]["lat"], "lng": a["position"]["lng"],
                           "intensity": round(intensity, 2)})
            for _ in range(2):
                points.append({"lat": a["position"]["lat"] + random.uniform(-0.01, 0.01),
                               "lng": a["position"]["lng"] + random.uniform(-0.01, 0.01),
                               "intensity": round(intensity * 0.6, 2)})
    return jsonify({"points": points, "count": len(points)})
