"""AMOS Simulation Routes — Sim control, Automation, Exercise, Recording, Overlays, SITREP, Analytics, AAR."""

import uuid, random, time
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, session
from web.extensions import login_required, ctx
from web.state import (sim_assets, sim_threats, sim_clock, base_pos, waypoint_nav,
                       aar_events, cm_log, hal_recommendations, automation_rules, exercise,
                       recording, sitreps, supply_history, weather, bda_reports, eob_units,
                       threat_intel, training_records, uptime_pings, USERS,
                       cognitive_engine, commander_support, sensor_fusion, ros2_bridge,
                       _px4, _tak, _link16, db_execute, to_json, from_json,
                       fetchall, now_iso, persist_sitrep,
                       db_check, mission_plans)
from web.extensions import api_metrics

bp = Blueprint("simulation", __name__)


# ═══════════════════════════════════════════════════════════
#  SIM CONTROL
# ═══════════════════════════════════════════════════════════
@bp.route("/sim/speed", methods=["POST"])
@login_required
def api_speed():
    sim_clock["speed"] = max(0.1, min(20, request.json.get("speed", 1.0)))
    return jsonify({"status": "ok", "speed": sim_clock["speed"]})

@bp.route("/sim/status")
@login_required
def api_sim(): return jsonify(sim_clock)

@bp.route("/user/role")
@login_required
def api_role(): return jsonify(ctx())

@bp.route("/users")
@login_required
def api_users():
    c = ctx()
    if c["role"] != "commander": return jsonify({"error": "Denied"}), 403
    return jsonify({k: {"name": v["name"], "role": v["role"], "domain": v["domain"]} for k, v in USERS.items()})

@bp.route("/ros2/status")
@login_required
def api_ros2(): return jsonify(ros2_bridge.get_status())


# ═══════════════════════════════════════════════════════════
#  AUTOMATION RULES
# ═══════════════════════════════════════════════════════════
@bp.route("/automation/rules")
@login_required
def api_automation_rules(): return jsonify(automation_rules)

@bp.route("/automation/rules/create", methods=["POST"])
@login_required
def api_automation_rules_create():
    d = request.json or {}
    rid = f"RULE-{uuid.uuid4().hex[:6]}"
    automation_rules[rid] = {
        "id": rid, "name": d.get("name", "Unnamed Rule"),
        "trigger_type": d.get("trigger_type", ""),
        "trigger_params": d.get("trigger_params", {}),
        "action_type": d.get("action_type", ""),
        "action_params": d.get("action_params", {}),
        "enabled": True, "fired_count": 0, "last_fired": None,
        "created_at": now_iso(), "created_by": ctx()["name"]}
    return jsonify({"status": "ok", "rule": automation_rules[rid]})

@bp.route("/automation/rules/toggle", methods=["POST"])
@login_required
def api_automation_rules_toggle():
    rid = (request.json or {}).get("rule_id", "")
    if rid in automation_rules:
        automation_rules[rid]["enabled"] = not automation_rules[rid]["enabled"]
        return jsonify({"status": "ok", "enabled": automation_rules[rid]["enabled"]})
    return jsonify({"error": "Rule not found"}), 404

@bp.route("/automation/rules/delete", methods=["POST"])
@login_required
def api_automation_rules_delete():
    rid = (request.json or {}).get("rule_id", "")
    automation_rules.pop(rid, None)
    return jsonify({"status": "ok"})


# ═══════════════════════════════════════════════════════════
#  EXERCISE MODE
# ═══════════════════════════════════════════════════════════
@bp.route("/exercise/status")
@login_required
def api_exercise_status(): return jsonify(exercise)

@bp.route("/exercise/start", methods=["POST"])
@login_required
def api_exercise_start():
    d = request.json or {}
    exercise["active"] = True
    exercise["name"] = d.get("name", f"Exercise {now_iso()[:10]}")
    exercise["started_at"] = now_iso()
    exercise["injects"] = d.get("injects", [])
    exercise["score"] = 0
    exercise["max_score"] = sum(i.get("points", 10) for i in exercise["injects"])
    exercise["events"] = []
    exercise["completed_injects"] = 0
    aar_events.append({"type": "exercise_start", "timestamp": now_iso(),
        "elapsed": sim_clock["elapsed_sec"],
        "details": f"Exercise '{exercise['name']}' started with {len(exercise['injects'])} injects"})
    return jsonify({"status": "ok", "exercise": exercise})

@bp.route("/exercise/stop", methods=["POST"])
@login_required
def api_exercise_stop():
    exercise["active"] = False
    final = {"name": exercise["name"], "score": exercise["score"],
             "max_score": exercise["max_score"], "completed": exercise["completed_injects"],
             "total_injects": len(exercise["injects"]), "events": exercise["events"]}
    aar_events.append({"type": "exercise_end", "timestamp": now_iso(),
        "elapsed": sim_clock["elapsed_sec"],
        "details": f"Exercise '{exercise['name']}' ended: {exercise['score']}/{exercise['max_score']} pts"})
    c = ctx()
    ms = exercise["max_score"] or 1
    pct = round(exercise["score"] / ms * 100, 1)
    training_records.append({
        "id": f"TR-{uuid.uuid4().hex[:8]}", "operator": c["user"], "name": c["name"],
        "exercise_name": exercise["name"], "score": exercise["score"],
        "max_score": exercise["max_score"], "pct": pct, "passed": pct >= 60,
        "timestamp": now_iso()})
    return jsonify({"status": "ok", "results": final})

@bp.route("/exercise/presets")
@login_required
def api_exercise_presets():
    return jsonify([
        {"name": "Quick React", "description": "3 threat injects over 60s",
         "injects": [
             {"type": "spawn_threat", "trigger_at_sec": sim_clock["elapsed_sec"] + 10,
              "threat_type": "drone", "description": "Enemy drone detected", "points": 20},
             {"type": "spawn_threat", "trigger_at_sec": sim_clock["elapsed_sec"] + 35,
              "threat_type": "missile_launcher", "description": "SAM site active", "points": 30},
             {"type": "degrade_comms", "trigger_at_sec": sim_clock["elapsed_sec"] + 50,
              "amount": 40, "description": "Comms jamming detected", "points": 25},
         ]},
        {"name": "Sustained Ops", "description": "Battery drain + multi-axis threat",
         "injects": [
             {"type": "drain_battery", "trigger_at_sec": sim_clock["elapsed_sec"] + 15,
              "amount": 40, "description": "Extended patrol battery drain", "points": 15},
             {"type": "spawn_threat", "trigger_at_sec": sim_clock["elapsed_sec"] + 30,
              "threat_type": "submarine", "description": "Subsurface contact", "points": 25},
             {"type": "spawn_threat", "trigger_at_sec": sim_clock["elapsed_sec"] + 45,
              "threat_type": "fighter_jet", "description": "Air threat inbound", "points": 30},
             {"type": "message", "trigger_at_sec": sim_clock["elapsed_sec"] + 55,
              "message": "Higher HQ requests SITREP", "description": "SITREP request", "points": 10},
         ]},
    ])


# ═══════════════════════════════════════════════════════════
#  RECORDING
# ═══════════════════════════════════════════════════════════
@bp.route("/recording/start", methods=["POST"])
@login_required
def api_recording_start():
    if recording["active"]:
        return jsonify({"error": "Already recording", "session_id": recording["session_id"]}), 409
    sid = str(uuid.uuid4())
    c = ctx()
    name = request.json.get("name", f"Mission {now_iso()[:10]}")
    db_execute("INSERT INTO recording_sessions (session_id, name, started_by) VALUES(%s,%s,%s)",
        (sid, name, c["user"]))
    recording["active"] = True
    recording["session_id"] = sid
    recording["frame_seq"] = 0
    return jsonify({"status": "ok", "session_id": sid})

@bp.route("/recording/stop", methods=["POST"])
@login_required
def api_recording_stop():
    if not recording["active"]:
        return jsonify({"error": "Not recording"}), 400
    sid = recording["session_id"]
    db_execute("UPDATE recording_sessions SET status='complete', stopped_at=NOW(), frame_count=%s WHERE session_id=%s",
        (recording["frame_seq"], sid))
    recording["active"] = False
    recording["session_id"] = None
    recording["frame_seq"] = 0
    return jsonify({"status": "ok", "session_id": sid})

@bp.route("/recording/sessions")
@login_required
def api_recording_sessions():
    rows = fetchall("SELECT * FROM recording_sessions ORDER BY started_at DESC LIMIT 50")
    return jsonify([{**r, "started_at": str(r["started_at"]),
                     "stopped_at": str(r["stopped_at"]) if r.get("stopped_at") else None} for r in rows])

@bp.route("/recording/<session_id>/frames")
@login_required
def api_recording_frames(session_id):
    rows = fetchall(
        "SELECT frame_seq, clock_elapsed, asset_state, threat_state, timestamp "
        "FROM recording_frames WHERE session_id=%s ORDER BY frame_seq", (session_id,))
    return jsonify([{"seq": r["frame_seq"], "elapsed": float(r["clock_elapsed"]),
                     "assets": from_json(r["asset_state"]), "threats": from_json(r["threat_state"]),
                     "ts": str(r["timestamp"])} for r in rows])


# ═══════════════════════════════════════════════════════════
#  OVERLAYS
# ═══════════════════════════════════════════════════════════
@bp.route("/overlays/heatmap")
@login_required
def api_overlays_heatmap():
    points = []
    for t in sim_threats.values():
        if t.get("lat") and not t.get("neutralized"):
            points.append({"lat": t["lat"], "lng": t.get("lng", 0), "intensity": 1.0})
    for ti in threat_intel.values():
        for p in ti.get("positions", [])[-10:]:
            points.append({"lat": p["lat"], "lng": p["lng"], "intensity": 0.4})
    return jsonify({"points": points, "count": len(points)})

@bp.route("/overlays/sectors")
@login_required
def api_overlays_sectors():
    sectors = []
    for domain in ["air", "ground", "maritime"]:
        assets = [a for a in sim_assets.values() if a["domain"] == domain]
        if not assets: continue
        lats = [a["position"]["lat"] for a in assets]
        lngs = [a["position"]["lng"] for a in assets]
        sectors.append({"domain": domain, "asset_count": len(assets),
            "bounds": {"north": max(lats) + 0.01, "south": min(lats) - 0.01,
                       "east": max(lngs) + 0.01, "west": min(lngs) - 0.01},
            "center": {"lat": sum(lats) / len(lats), "lng": sum(lngs) / len(lngs)}})
    return jsonify(sectors)

@bp.route("/overlays/engagement-zones")
@login_required
def api_overlays_engagement_zones():
    zones = []
    for a in sim_assets.values():
        if not a.get("weapons"): continue
        rng = 0.015 if a["domain"] == "air" else 0.008
        zones.append({"asset_id": a["id"], "domain": a["domain"],
            "center": {"lat": a["position"]["lat"], "lng": a["position"]["lng"]},
            "radius_deg": rng, "weapons": a["weapons"]})
    return jsonify(zones)

@bp.route("/overlays/sensor-coverage")
@login_required
def api_overlays_sensor_coverage():
    _SENSOR_PROFILES = {
        "AESA_RADAR": {"range_deg": 0.04, "arc_deg": 120, "color": "#00ffff"},
        "AEW_RADAR": {"range_deg": 0.06, "arc_deg": 360, "color": "#00ccff"},
        "EO/IR": {"range_deg": 0.015, "arc_deg": 60, "color": "#ffaa00"},
        "EW_JAMMER": {"range_deg": 0.03, "arc_deg": 360, "color": "#ff00ff"},
        "SIGINT": {"range_deg": 0.035, "arc_deg": 360, "color": "#ff66ff"},
        "ELINT": {"range_deg": 0.03, "arc_deg": 360, "color": "#cc66ff"},
        "COMINT": {"range_deg": 0.025, "arc_deg": 360, "color": "#9966ff"},
        "LIDAR": {"range_deg": 0.01, "arc_deg": 90, "color": "#00ff88"},
        "SONAR": {"range_deg": 0.02, "arc_deg": 360, "color": "#4488ff"},
        "CAMERA": {"range_deg": 0.008, "arc_deg": 45, "color": "#ffcc00"},
        "GPS": {"range_deg": 0, "arc_deg": 0, "color": "#888"},
        "IMU": {"range_deg": 0, "arc_deg": 0, "color": "#888"},
    }
    arcs = []
    for a in sim_assets.values():
        for sensor in a.get("sensors", []):
            prof = _SENSOR_PROFILES.get(sensor)
            if not prof or prof["range_deg"] == 0: continue
            arcs.append({
                "asset_id": a["id"], "sensor": sensor, "domain": a["domain"],
                "center": {"lat": a["position"]["lat"], "lng": a["position"]["lng"]},
                "bearing": a["heading_deg"], "range_deg": prof["range_deg"],
                "arc_deg": prof["arc_deg"], "color": prof["color"]})
    return jsonify(arcs)


# ═══════════════════════════════════════════════════════════
#  SITREP
# ═══════════════════════════════════════════════════════════
@bp.route("/sitrep/generate", methods=["POST"])
@login_required
def api_sitrep_generate():
    from web.extensions import platoon
    at = sum(1 for t in sim_threats.values() if not t.get("neutralized"))
    nt = sum(1 for t in sim_threats.values() if t.get("neutralized"))
    risk = commander_support.get_risk() if commander_support else {"level": "LOW", "score": 0}
    c = ctx()
    moving = len(waypoint_nav.routes)
    avg_batt = sum(a["health"]["battery_pct"] for a in sim_assets.values()) / max(1, len(sim_assets))
    sitrep = {
        "id": f"SITREP-{len(sitreps)+1:03d}",
        "dtg": datetime.now(timezone.utc).strftime("%d%H%MZ %b %Y").upper(),
        "generated_by": c["name"],
        "classification": "UNCLASSIFIED//FOUO",
        "mission": platoon.get("name", "UNNAMED"),
        "callsign": platoon.get("callsign", ""),
        "elapsed": round(sim_clock["elapsed_sec"] / 60, 1),
        "line1_enemy": f"{at} active threats, {nt} neutralized. Risk: {risk.get('level','LOW')} ({risk.get('score',0)})",
        "line2_friendly": f"{len(sim_assets)} assets operational, {moving} on mission, avg battery {avg_batt:.0f}%",
        "line3_operations": f"{len(cm_log)} engagements, {len(aar_events)} total events logged",
        "line4_logistics": f"Low battery: {sum(1 for a in sim_assets.values() if a['health']['battery_pct']<30)} assets. Comms degraded: {sum(1 for a in sim_assets.values() if a['health']['comms_strength']<40)}",
        "line5_command": f"Pending approvals: {sum(1 for r in hal_recommendations if r.get('status')=='pending')}. Exercise: {'ACTIVE' if exercise['active'] else 'NONE'}",
    }
    sitreps.append(sitrep)
    persist_sitrep(sitrep)
    return jsonify(sitrep)

@bp.route("/sitrep/history")
@login_required
def api_sitrep_history(): return jsonify(sitreps[-20:])


# ═══════════════════════════════════════════════════════════
#  AAR
# ═══════════════════════════════════════════════════════════
@bp.route("/aar/events")
@login_required
def api_aar_events(): return jsonify(aar_events[-200:])

@bp.route("/aar/export")
@login_required
def api_aar_export():
    from web.extensions import platoon
    from web.state import swarms, sigint_intercepts, cyber_events
    return jsonify({"mission": platoon["name"], "callsign": platoon["callsign"],
        "export_time": now_iso(), "duration_sec": sim_clock["elapsed_sec"],
        "assets": {k: {"id": v["id"], "type": v["type"], "domain": v["domain"], "status": v["status"]} for k, v in sim_assets.items()},
        "threats": {k: {"id": v["id"], "type": v["type"], "neutralized": v.get("neutralized", False)} for k, v in sim_threats.items()},
        "events": aar_events, "countermeasures": cm_log, "swarms": swarms,
        "sigint_count": len(sigint_intercepts), "cyber_count": len(cyber_events)})

@bp.route("/aar/timeline")
@login_required
def api_aar_timeline():
    etype = request.args.get("type")
    limit = request.args.get("limit", 500, type=int)
    events = aar_events[-limit:]
    if etype:
        events = [e for e in events if e.get("type") == etype]
    type_counts = {}
    for e in aar_events:
        t = e.get("type", "unknown"); type_counts[t] = type_counts.get(t, 0) + 1
    buckets = [0] * 30
    max_elapsed = max((e.get("elapsed", 0) for e in aar_events), default=1) or 1
    for e in aar_events:
        idx = min(29, int((e.get("elapsed", 0) / max_elapsed) * 29))
        buckets[idx] += 1
    return jsonify({"events": events, "type_counts": type_counts,
                    "density": buckets, "total": len(aar_events),
                    "max_elapsed": round(max_elapsed, 1)})


# ═══════════════════════════════════════════════════════════
#  ANALYTICS
# ═══════════════════════════════════════════════════════════
@bp.route("/analytics/summary")
@login_required
def api_analytics_summary():
    at = sum(1 for t in sim_threats.values() if not t.get("neutralized"))
    nt = sum(1 for t in sim_threats.values() if t.get("neutralized"))
    total_t = len(sim_threats)
    moving = len(waypoint_nav.routes)
    idle = len(sim_assets) - moving
    low_batt = sum(1 for a in sim_assets.values() if a["health"]["battery_pct"] < 30)
    cog_recs = cognitive_engine.get_recommendations(200) if cognitive_engine else []
    approved = sum(1 for r in cog_recs if r.get("status") in ("approve", "approved"))
    rejected = sum(1 for r in cog_recs if r.get("status") in ("reject", "rejected"))
    pending = sum(1 for r in cog_recs if r.get("status") == "pending")
    engagements = len(cm_log)
    risk = commander_support.get_risk() if commander_support else {"level": "LOW", "score": 0}
    risk_trend = commander_support.get_risk_trend() if commander_support else []
    event_types = {}
    for ev in aar_events:
        et = ev.get("type", "unknown"); event_types[et] = event_types.get(et, 0) + 1
    by_domain = {}
    for a in sim_assets.values():
        d = a.get("domain", "unknown"); by_domain[d] = by_domain.get(d, 0) + 1
    avg_batt = sum(a["health"]["battery_pct"] for a in sim_assets.values()) / max(1, len(sim_assets))
    avg_comms = sum(a["health"]["comms_strength"] for a in sim_assets.values()) / max(1, len(sim_assets))
    return jsonify({
        "mission_elapsed_sec": round(sim_clock["elapsed_sec"], 1),
        "threats": {"active": at, "neutralized": nt, "total": total_t,
                    "neutralization_pct": round(nt / max(1, total_t) * 100, 1)},
        "assets": {"total": len(sim_assets), "moving": moving, "idle": idle,
                   "low_battery": low_batt, "by_domain": by_domain,
                   "avg_battery_pct": round(avg_batt, 1), "avg_comms_pct": round(avg_comms, 1)},
        "coa": {"approved": approved, "rejected": rejected, "pending": pending,
                "approval_rate": round(approved / max(1, approved + rejected) * 100, 1)},
        "engagements": engagements,
        "risk": {"level": risk.get("level", "LOW"), "score": risk.get("score", 0),
                 "trend": risk_trend[-20:] if isinstance(risk_trend, list) else []},
        "events": {"total": len(aar_events), "by_type": event_types},
        "integrations": {
            "px4": _px4.connected if _px4 else False,
            "tak": _tak.connected if _tak else False,
            "link16": bool(_link16),
            "ros2": ros2_bridge.available if ros2_bridge else False,
        },
    })


# ═══════════════════════════════════════════════════════════
#  SYSCMD
# ═══════════════════════════════════════════════════════════
@bp.route("/syscmd/health")
@login_required
def api_syscmd_health():
    import platform
    uptime_sec = time.time() - api_metrics["start_time"]
    cpu = round(random.uniform(8, 45) + len(sim_assets) * 0.5, 1)
    mem_mb = round(80 + len(sim_assets) * 2.5 + len(aar_events) * 0.01, 1)
    uptime_pings.append({"ts": now_iso(), "cpu": cpu, "mem": mem_mb, "uptime": round(uptime_sec)})
    if len(uptime_pings) > 60: del uptime_pings[:1]
    return jsonify({
        "uptime_sec": round(uptime_sec), "cpu_pct": cpu, "memory_mb": mem_mb,
        "python": platform.python_version(), "flask": "3.x",
        "platform": platform.platform(), "hostname": platform.node(),
        "assets_loaded": len(sim_assets), "threats_loaded": len(sim_threats),
        "aar_events": len(aar_events), "sim_speed": sim_clock["speed"],
        "uptime_history": uptime_pings[-60:]})

@bp.route("/syscmd/metrics")
@login_required
def api_syscmd_metrics():
    top = sorted(api_metrics["by_endpoint"].items(), key=lambda x: x[1]["count"], reverse=True)[:30]
    endpoints = []
    for ep, m in top:
        avg_ms = round(m["total_ms"] / max(1, m["count"]), 2)
        endpoints.append({"endpoint": ep, "count": m["count"], "errors": m["errors"], "avg_ms": avg_ms})
    return jsonify({"total_requests": api_metrics["requests"], "total_errors": api_metrics["errors"],
                    "unique_endpoints": len(api_metrics["by_endpoint"]), "top_endpoints": endpoints})

@bp.route("/syscmd/logs")
@login_required
def api_syscmd_logs():
    lines = []
    try:
        with open("/tmp/amos.log", "r") as f:
            lines = f.readlines()[-50:]
    except Exception:
        lines = ["(Log file not available)\n"]
    return jsonify({"lines": [l.rstrip() for l in lines], "count": len(lines)})

@bp.route("/syscmd/diagnostics")
@login_required
def api_syscmd_diagnostics():
    from web.state import online_ops
    connected_sockets = len(online_ops)
    def _count_db_tables():
        try:
            rows = fetchall("SHOW TABLES")
            return len(rows) if rows else 0
        except Exception: return 0
    return jsonify({
        "socketio_clients": connected_sockets,
        "px4": {"available": bool(_px4), "connected": _px4.connected if _px4 else False},
        "tak": {"available": bool(_tak), "connected": _tak.connected if _tak else False},
        "link16": {"available": bool(_link16), "active": bool(_link16)},
        "ros2": {"available": ros2_bridge.available if ros2_bridge else False},
        "database": {"connected": db_check(), "tables": _count_db_tables()},
        "recording": recording["active"],
        "exercise": exercise["active"],
        "automation_rules": len(automation_rules),
        "mission_plans": len(mission_plans),
        "training_records": len(training_records)})


# ═══════════════════════════════════════════════════════════
#  REPORTS
# ═══════════════════════════════════════════════════════════
@bp.route("/reports/mission")
@login_required
def api_reports_mission():
    from web.extensions import platoon
    at = sum(1 for t in sim_threats.values() if not t.get("neutralized"))
    nt = sum(1 for t in sim_threats.values() if t.get("neutralized"))
    risk = commander_support.get_risk() if commander_support else {"level": "LOW", "score": 0}
    cog_recs = cognitive_engine.get_recommendations(200) if cognitive_engine else []
    approved = sum(1 for r in cog_recs if r.get("status") in ("approve", "approved"))
    rejected = sum(1 for r in cog_recs if r.get("status") in ("reject", "rejected"))
    asset_summary = [{"id": aid, "type": a["type"], "domain": a["domain"],
        "status": a["status"], "battery": a["health"]["battery_pct"],
        "comms": a["health"]["comms_strength"]} for aid, a in sim_assets.items()]
    event_types = {}
    for ev in aar_events:
        et = ev.get("type", "unknown"); event_types[et] = event_types.get(et, 0) + 1
    threat_summary = [{"type": ttype, "count": ti["count"],
        "neutralized": ti["neutralized"], "engagements": ti["engagements"]}
        for ttype, ti in threat_intel.items()]
    fuels = [a.get("supplies", {}).get("fuel_pct", 100) for a in sim_assets.values()]
    ammos = [a.get("supplies", {}).get("ammo_rounds", 0) for a in sim_assets.values()]
    avg_fuel = round(sum(fuels) / max(1, len(fuels)), 1)
    avg_ammo = round(sum(ammos) / max(1, len(ammos)), 1)
    wx = {"conditions": weather["conditions"], "wind_speed_kt": round(weather["wind_speed_kt"], 1),
          "wind_dir_deg": round(weather["wind_dir_deg"]), "visibility_km": round(weather["visibility_km"], 1),
          "ceiling_ft": weather["ceiling_ft"], "precipitation": weather["precipitation"], "sea_state": weather["sea_state"]}
    bda_total = len(bda_reports)
    bda_destroyed = sum(1 for r in bda_reports if r.get("damage_level") == "destroyed")
    bda_fk = sum(1 for r in bda_reports if r.get("functional_kill"))
    eob_total = len(eob_units)
    eob_active = sum(1 for u in eob_units.values() if u.get("status") == "active")
    return jsonify({
        "title": f"MISSION REPORT — {platoon.get('name', 'UNNAMED')}",
        "callsign": platoon.get("callsign", ""),
        "generated_at": now_iso(),
        "dtg": datetime.now(timezone.utc).strftime("%d%H%MZ %b %Y").upper(),
        "elapsed_sec": round(sim_clock["elapsed_sec"], 1),
        "elapsed_min": round(sim_clock["elapsed_sec"] / 60, 1),
        "situation": {"total_assets": len(sim_assets), "active_threats": at,
            "neutralized_threats": nt, "total_threats": len(sim_threats),
            "neutralization_pct": round(nt / max(1, len(sim_threats)) * 100, 1),
            "risk_level": risk.get("level", "LOW"), "risk_score": risk.get("score", 0)},
        "decisions": {"coa_approved": approved, "coa_rejected": rejected,
            "engagements": len(cm_log), "countermeasures_deployed": len(cm_log),
            "voice_commands": event_types.get("voice_command", 0)},
        "logistics": {"avg_fuel_pct": avg_fuel, "avg_ammo_rounds": avg_ammo,
            "low_fuel_assets": sum(1 for f in fuels if f < 25)},
        "weather": wx,
        "bda": {"total_reports": bda_total, "destroyed": bda_destroyed,
            "functional_kills": bda_fk, "fk_rate": round(bda_fk / max(1, bda_total) * 100, 1)},
        "eob": {"total_units": eob_total, "active": eob_active, "inactive": eob_total - eob_active},
        "assets": asset_summary, "threat_intel": threat_summary,
        "events": {"total": len(aar_events), "by_type": event_types},
        "integrations": {"px4": _px4.connected if _px4 else False,
            "tak": _tak.connected if _tak else False,
            "link16": bool(_link16), "ros2": ros2_bridge.available if ros2_bridge else False},
    })
