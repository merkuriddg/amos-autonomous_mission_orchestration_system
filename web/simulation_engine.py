"""AMOS Simulation Engine.

The main simulation tick loop. Drives asset movement, threat dynamics,
subsystem ticks, and WebSocket push updates.
Enterprise subsystem ticks are conditional on availability (not None).
"""

import time, random, uuid

from web.extensions import socketio, base_pos
from web.state import (
    sim_assets, sim_threats, sim_clock, now_iso,
    waypoint_nav, geofence_mgr, ros2_bridge, task_allocator,
    sensor_fusion, mesh_network, roe_engine,
    ew_active_jams, ew_intercepts, sigint_intercepts, sigint_emitter_db,
    cyber_events, cyber_blocked_ips, cm_log, hal_recommendations, aar_events,
    swarms, recording, threat_intel, automation_rules, exercise,
    supply_history, weather, eob_units, bda_reports, mission_plans,
    sitreps, alert_cooldowns, online_ops,
    # Enterprise subsystems (may be None)
    cognitive_engine, contested_env, red_force_ai, commander_support,
    learning_engine, kill_web, threat_predictor, wargame_engine,
    swarm_intel, isr_pipeline, effects_chain, space_domain, hmt_engine,
    # Integrations
    _px4, _tak, _link16,
    # DB
    db_execute, to_json, db_flush,
)


def sim_tick():
    """Main simulation loop — runs in a daemon thread."""
    print("[AMOS] Simulation engine started")
    last = time.time()
    while sim_clock["running"]:
        time.sleep(0.5)
        now = time.time(); real_dt = now - last; dt = real_dt * sim_clock["speed"]
        sim_clock["elapsed_sec"] += dt; last = now

        # ── Waypoint navigation ──
        for evt in waypoint_nav.tick(sim_assets, dt):
            aar_events.append({"type": "waypoint_reached", "timestamp": now_iso(),
                "elapsed": sim_clock["elapsed_sec"],
                "details": f"{evt['asset_id']} reached WP {evt['waypoint']['lat']:.4f},{evt['waypoint']['lng']:.4f}"})

        # ── Asset drift (only if no waypoint) ──
        for aid, a in sim_assets.items():
            if aid in waypoint_nav.routes:
                continue
            p = a["position"]; d = 0.00003 * dt
            p["lat"] = round(p["lat"] + random.uniform(-d, d), 6)
            p["lng"] = round(p["lng"] + random.uniform(-d, d), 6)
            if a["domain"] == "air" and "alt_ft" in p:
                p["alt_ft"] = max(100, p["alt_ft"] + random.uniform(-50, 50) * dt)
            h = a["health"]
            h["battery_pct"] = max(5, min(100, h["battery_pct"] + random.uniform(-0.1, 0.05) * dt))
            h["comms_strength"] = max(20, min(100, h["comms_strength"] + random.uniform(-0.5, 0.5) * dt))
            a["heading_deg"] = (a["heading_deg"] + random.uniform(-2, 2) * dt) % 360

        # ── Threat movement ──
        for tid, t in sim_threats.items():
            if t.get("neutralized") or "lat" not in t or "lng" not in t:
                continue
            sf = t.get("speed_kts", 20) * 0.00001 * dt
            t["lat"] = round(t["lat"] + random.uniform(-sf, sf), 6)
            t["lng"] = round(t["lng"] + random.uniform(-sf, sf), 6)

        # ── Geofence checks ──
        for alert in geofence_mgr.tick(sim_assets, sim_threats):
            aar_events.append({"type": "geofence_alert", "timestamp": now_iso(),
                "elapsed": sim_clock["elapsed_sec"],
                "details": f"GF {alert['event'].upper()}: {alert['entity_id']} — {alert['geofence_name']}"})

        # ── SIGINT generation ──
        if random.random() < 0.3 * dt:
            cols = [a for a in sim_assets.values()
                    if any(s in (a.get("sensors") or []) for s in ["SIGINT", "ELINT", "COMINT", "AEW_RADAR"])]
            if cols:
                c = random.choice(cols)
                freq = random.choice([433.0, 915.0, 1575.42, 2437.0, 5805.0]) + random.uniform(-5, 5)
                ix = {"id": f"INT-{uuid.uuid4().hex[:8]}", "timestamp": now_iso(),
                      "collector": c["id"], "freq_mhz": round(freq, 2),
                      "power_dbm": random.randint(-80, -20),
                      "modulation": random.choice(["FM", "AM", "PSK", "FSK", "OFDM", "FHSS", "DSSS"]),
                      "bearing_deg": random.randint(0, 359),
                      "classification": random.choice(["HOSTILE", "HOSTILE", "SUSPECT", "UNKNOWN", "FRIENDLY"]),
                      "duration_ms": random.randint(50, 5000)}
                sigint_intercepts.append(ix); ew_intercepts.append(ix)
                fk = f"{round(freq, 0)}"
                if fk not in sigint_emitter_db:
                    sigint_emitter_db[fk] = {"freq_mhz": round(freq, 2), "count": 0,
                                              "first_seen": ix["timestamp"], "last_seen": ix["timestamp"]}
                sigint_emitter_db[fk]["count"] += 1
                sigint_emitter_db[fk]["last_seen"] = ix["timestamp"]

        # ── Cyber events ──
        if random.random() < 0.15 * dt:
            sip = random.choice(["*" * 10, "*" * 11, "*" * 10, "*" * 12])
            cyber_events.append({"id": f"CYB-{uuid.uuid4().hex[:8]}", "timestamp": now_iso(),
                "type": random.choice(["port_scan", "brute_force", "dns_exfil", "c2_beacon", "lateral_move"]),
                "source_ip": sip, "target": random.choice(list(sim_assets.keys())),
                "severity": random.choice(["low", "medium", "high", "critical"]),
                "blocked": sip in cyber_blocked_ips})

        # ── HAL recommendations ──
        active_t = [t for t in sim_threats.values() if not t.get("neutralized") and "lat" in t]
        if active_t and random.random() < 0.1 * dt:
            th = random.choice(active_t)
            cap = [a for a in sim_assets.values() if a.get("weapons") or "EW_JAMMER" in (a.get("sensors") or [])]
            if cap:
                a = random.choice(cap)
                hal_recommendations.append({"id": f"HAL-{uuid.uuid4().hex[:8]}", "timestamp": now_iso(),
                    "type": random.choice(["ENGAGE", "JAM", "INTERCEPT", "RELOCATE", "SURVEIL"]),
                    "asset": a["id"], "target": th["id"],
                    "confidence": round(random.uniform(0.6, 0.98), 2),
                    "reasoning": f"Threat {th['id']} ({th['type']}) detected — recommend {a['id']}",
                    "status": "pending", "tier": a.get("autonomy_tier", 2)})

        # ── ROS2 bridge ──
        if ros2_bridge.available:
            ros2_bridge.publish_assets(sim_assets)

        # ── PX4 SITL sync ──
        if _px4 and _px4.connected:
            _px4.sync_to_amos(sim_assets)

        # ── TAK + Link 16 sync (every ~5s) ──
        if int(sim_clock["elapsed_sec"]) % 5 < 1:
            if _tak and _tak.connected:
                _tak.send_assets(sim_assets)
                _tak.send_threats(sim_threats)
            if _link16:
                _link16.broadcast_all_assets(sim_assets)

        # ── Core subsystem ticks ──
        task_allocator.tick(sim_assets, dt)
        sensor_fusion.tick(sim_assets, sim_threats, dt)
        mesh_network.tick(sim_assets, ew_active_jams, dt)

        # ── Enterprise subsystem ticks (conditional) ──
        if cognitive_engine:
            cognitive_engine.tick(sim_assets, sim_threats, dt)
        if contested_env:
            contested_env.tick(sim_assets, sim_threats, dt)

        if red_force_ai:
            red_events = red_force_ai.tick(sim_assets, sim_threats, ew_active_jams, dt)
            for re in red_events:
                aar_events.append({"type": "red_force", "timestamp": now_iso(),
                    "elapsed": sim_clock["elapsed_sec"], "details": str(re)})

        if commander_support:
            cmdr_events = commander_support.tick(sim_assets, sim_threats, contested_env, dt)
            for ce in cmdr_events:
                aar_events.append({"type": "contingency", "timestamp": now_iso(),
                    "elapsed": sim_clock["elapsed_sec"], "details": str(ce)})
                if learning_engine:
                    learning_engine.record_event("CONTINGENCY_TRIGGERED", ce)

        learning_anomalies = []
        if learning_engine:
            learning_anomalies = learning_engine.tick(sim_assets, sim_threats, dt)

        if threat_predictor:
            threat_predictor.tick(sim_threats, eob_units, sim_assets, dt)

        if kill_web:
            kw_events = kill_web.tick(sim_threats, sigint_intercepts,
                sensor_fusion.get_tracks(), cm_log, bda_reports, sim_assets, dt)
            for kwe in kw_events:
                aar_events.append({"type": "killweb", "timestamp": now_iso(),
                    "elapsed": sim_clock["elapsed_sec"], "details": kwe})

        if wargame_engine:
            wargame_engine.auto_evaluate(sim_assets, sim_threats, dt)

        if swarm_intel:
            swarm_events = swarm_intel.tick(sim_assets, sim_threats, dt)
            for se in swarm_events:
                aar_events.append({"type": "swarm", "timestamp": now_iso(),
                    "elapsed": sim_clock["elapsed_sec"], "details": se})

        if isr_pipeline:
            isr_pipeline.tick(sim_assets, sim_threats, eob_units, sigint_intercepts, dt)

        if effects_chain:
            fx_events = effects_chain.tick(sim_threats, sim_assets, ew_active_jams,
                                           cyber_events, sigint_intercepts, dt)
            for fe in fx_events:
                aar_events.append({"type": "effects", "timestamp": now_iso(),
                    "elapsed": sim_clock["elapsed_sec"], "details": fe})

        if space_domain:
            space_domain.tick(base_pos["lat"], base_pos["lng"], sim_assets, dt)

        if hmt_engine:
            hmt_engine.tick(len(online_ops),
                sum(1 for r in hal_recommendations if r.get("status") == "pending"),
                sum(1 for t in sim_threats.values() if not t.get("neutralized")), dt)

        # ── Recording frame capture (every ~2s) ──
        if recording["active"]:
            recording["tick_count"] += 1
            if recording["tick_count"] % 4 == 0:
                recording["frame_seq"] += 1
                try:
                    db_execute(
                        "INSERT INTO recording_frames (session_id,frame_seq,clock_elapsed,asset_state,threat_state) "
                        "VALUES(%s,%s,%s,%s,%s)",
                        (recording["session_id"], recording["frame_seq"],
                         round(sim_clock["elapsed_sec"], 1),
                         to_json({aid: {"lat": a["position"]["lat"], "lng": a["position"]["lng"],
                                        "alt_ft": a["position"].get("alt_ft", 0), "status": a["status"],
                                        "heading": a["heading_deg"], "type": a["type"], "domain": a["domain"]}
                                  for aid, a in sim_assets.items()}),
                         to_json({tid: {"lat": t.get("lat"), "lng": t.get("lng"), "type": t["type"],
                                        "neutralized": t.get("neutralized", False)}
                                  for tid, t in sim_threats.items() if not t.get("neutralized")})))
                except Exception:
                    pass

        # ── Threat Intel tracking ──
        for tid, t in sim_threats.items():
            ttype = t.get("type", "unknown")
            if ttype not in threat_intel:
                threat_intel[ttype] = {"count": 0, "engagements": 0, "neutralized": 0,
                    "first_seen": now_iso(), "last_seen": now_iso(), "positions": []}
            ti = threat_intel[ttype]
            ti["last_seen"] = now_iso()
            if t.get("neutralized"):
                ti["neutralized"] = max(ti["neutralized"], sum(1 for x in sim_threats.values()
                    if x.get("type") == ttype and x.get("neutralized")))
            if t.get("lat") and len(ti["positions"]) < 50:
                pos = {"lat": round(t["lat"], 4), "lng": round(t.get("lng", 0), 4)}
                if not ti["positions"] or ti["positions"][-1] != pos:
                    ti["positions"].append(pos)
        for ttype in threat_intel:
            threat_intel[ttype]["count"] = sum(1 for t in sim_threats.values() if t.get("type") == ttype)
            threat_intel[ttype]["engagements"] = sum(1 for c in cm_log if
                sim_threats.get(c.get("threat_id", ""), {}).get("type") == ttype)

        # ── Supply burn ──
        for a in sim_assets.values():
            sup = a.get("supplies", {})
            if sup:
                sup["fuel_pct"] = max(0, sup.get("fuel_pct", 100) - random.uniform(0.005, 0.02) * dt)
                if sup.get("ammo_rounds", 0) > 0 and random.random() < 0.01 * dt:
                    sup["ammo_rounds"] = max(0, sup["ammo_rounds"] - random.randint(0, 2))
                sup["water_hr"] = max(0, sup.get("water_hr", 48) - 0.001 * dt)
                sup["rations_hr"] = max(0, sup.get("rations_hr", 72) - 0.0008 * dt)

        # Supply history snapshot (every ~10s)
        if int(sim_clock["elapsed_sec"]) % 10 < 1:
            fuels = [a["supplies"]["fuel_pct"] for a in sim_assets.values() if "supplies" in a]
            ammos = [a["supplies"]["ammo_rounds"] for a in sim_assets.values()
                     if "supplies" in a and a["supplies"]["ammo_rounds"] > 0]
            supply_history.append({"ts": now_iso(),
                "avg_fuel": round(sum(fuels) / max(1, len(fuels)), 1),
                "avg_ammo": round(sum(ammos) / max(1, len(ammos)), 1) if ammos else 0})
            if len(supply_history) > 120:
                del supply_history[:1]

        # ── Weather drift ──
        if random.random() < 0.05 * dt:
            weather["wind_speed_kt"] = max(0, min(60, weather["wind_speed_kt"] + random.uniform(-3, 3)))
            weather["wind_dir_deg"] = (weather["wind_dir_deg"] + random.uniform(-15, 15)) % 360
            weather["temp_c"] = max(-10, min(50, weather["temp_c"] + random.uniform(-1, 1)))
            weather["visibility_km"] = max(0.5, min(30, weather["visibility_km"] + random.uniform(-2, 2)))
            weather["ceiling_ft"] = max(500, min(40000, weather["ceiling_ft"] + random.uniform(-2000, 2000)))
            weather["sea_state"] = max(0, min(9, weather["sea_state"] + random.choice([-1, 0, 0, 0, 1])))
            precip_opts = ["none", "none", "none", "light_rain", "rain", "heavy_rain", "dust", "fog", "snow"]
            weather["precipitation"] = random.choice(precip_opts)
            cond_map = {"none": "Clear", "light_rain": "Light Rain", "rain": "Rain",
                        "heavy_rain": "Heavy Rain", "dust": "Dust Storm", "fog": "Fog", "snow": "Snow"}
            weather["conditions"] = cond_map.get(weather["precipitation"], "Clear")
            weather["last_update"] = now_iso()

        # ── EOB position tracking ──
        for tid, t in sim_threats.items():
            if tid in eob_units and t.get("lat"):
                eu = eob_units[tid]
                eu["last_known"] = {"lat": round(t["lat"], 4), "lng": round(t.get("lng", 0), 4)}
                if not eu["first_seen"]:
                    eu["first_seen"] = now_iso()
                if len(eu["positions"]) < 100:
                    eu["positions"].append({"lat": round(t["lat"], 4),
                                            "lng": round(t.get("lng", 0), 4), "ts": now_iso()})

        # ── Persistence flush ──
        db_flush(cm_log, aar_events, bda_reports, eob_units, sigint_intercepts,
                 supply_history, weather, threat_intel, sitreps, mission_plans,
                 automation_rules, hal_recommendations)

        # ── Trim lists ──
        for lst in [sigint_intercepts, ew_intercepts, cyber_events]:
            if len(lst) > 1000:
                del lst[:500]
        if len(aar_events) > 5000:
            del aar_events[:2500]

        # ── WebSocket emit ──
        act = sum(1 for t in sim_threats.values() if not t.get("neutralized") and "lat" in t)
        phal = sum(1 for r in hal_recommendations if r.get("status") == "pending")
        risk = commander_support.get_risk() if commander_support else {"level": "LOW", "score": 0}
        red_count = len([u for u in red_force_ai.get_units().values()
                         if u["state"] != "DESTROYED"]) if red_force_ai else 0

        socketio.emit("sim_update", {
            "clock": {"elapsed_sec": round(sim_clock["elapsed_sec"], 1), "speed": sim_clock["speed"]},
            "asset_count": len(sim_assets), "threat_count": act,
            "hostile_tracks": act, "pending_hal": phal,
            "gf_alerts": len(geofence_mgr.get_alerts()),
            "active_waypoints": len(waypoint_nav.routes),
            "risk_level": risk.get("level", "LOW"), "risk_score": risk.get("score", 0),
            "red_force_units": red_count,
            "fused_tracks": len(sensor_fusion.get_tracks()),
            "anomalies": len(learning_anomalies),
            "killweb_active": kill_web.get_stats().get("active", 0) if kill_web else 0,
            "killweb_awaiting": kill_web.get_stats().get("awaiting_approval", 0) if kill_web else 0,
            "roe_posture": roe_engine.posture,
            "predictions_count": len(threat_predictor.predictions) if threat_predictor else 0,
            "wargame_running": wargame_engine.get_stats().get("running", 0) if wargame_engine else 0,
            "swarm_active": swarm_intel.get_stats().get("active_swarms", 0) if swarm_intel else 0,
            "isr_tracked": isr_pipeline.get_stats().get("tracked_targets", 0) if isr_pipeline else 0,
            "effects_active": effects_chain.get_stats().get("active", 0) if effects_chain else 0,
            "satellites_visible": space_domain.get_stats().get("visible", 0) if space_domain else 0,
            "mesh_resilience": mesh_network.get_stats().get("resilience_grade", "?")})

        # ── Domain-specific WebSocket push (every ~2s) ──
        if int(sim_clock["elapsed_sec"]) % 2 < 1:
            socketio.emit("asset_update", {
                aid: {"lat": a["position"]["lat"], "lng": a["position"]["lng"],
                      "alt_ft": a["position"].get("alt_ft", 0), "status": a["status"],
                      "heading": a["heading_deg"], "speed": a["speed_kts"],
                      "battery": a["health"]["battery_pct"], "comms": a["health"]["comms_strength"],
                      "domain": a["domain"], "type": a["type"]}
                for aid, a in sim_assets.items()})
            socketio.emit("threat_update", {
                tid: {"lat": t.get("lat"), "lng": t.get("lng"), "type": t["type"],
                      "neutralized": t.get("neutralized", False), "speed": t.get("speed_kts", 0)}
                for tid, t in sim_threats.items() if not t.get("neutralized")})
            if sigint_intercepts:
                socketio.emit("sigint_update", sigint_intercepts[-5:])
            socketio.emit("weather_update", weather)
            if kill_web:
                socketio.emit("killweb_update", kill_web.get_stats())
            if wargame_engine:
                socketio.emit("wargame_update", wargame_engine.get_stats())
            if swarm_intel:
                socketio.emit("swarm_update", swarm_intel.get_stats())
            if isr_pipeline:
                socketio.emit("isr_update", isr_pipeline.get_stats())
            if effects_chain:
                socketio.emit("effects_update", effects_chain.get_stats())
            if space_domain:
                socketio.emit("space_update", space_domain.get_stats())
            if hmt_engine:
                socketio.emit("hmt_update", hmt_engine.get_stats())
            socketio.emit("mesh_update", mesh_network.get_stats())

        # ── Rule Engine evaluation ──
        for rid, rule in list(automation_rules.items()):
            if not rule.get("enabled"):
                continue
            triggered = False
            tp = rule.get("trigger_type", "")
            tparams = rule.get("trigger_params", {})
            if tp == "threat_count" and act >= tparams.get("threshold", 999):
                triggered = True
            elif tp == "risk_level" and risk.get("level") in tparams.get("levels", []):
                triggered = True
            elif tp == "battery_low":
                low_ct = sum(1 for a in sim_assets.values()
                             if a["health"]["battery_pct"] < tparams.get("threshold", 15))
                if low_ct >= tparams.get("min_count", 1):
                    triggered = True
            elif tp == "pending_hal" and phal >= tparams.get("threshold", 10):
                triggered = True
            elif tp == "elapsed_time" and sim_clock["elapsed_sec"] >= tparams.get("seconds", 9999):
                triggered = True
            if triggered:
                rule["fired_count"] = rule.get("fired_count", 0) + 1
                rule["last_fired"] = now_iso()
                ap = rule.get("action_type", "")
                aparams = rule.get("action_params", {})
                if ap == "alert":
                    socketio.emit("amos_alerts", [{"level": aparams.get("level", "warning"),
                        "msg": f"[RULE] {rule['name']}: {aparams.get('message', 'Triggered')}",
                        "link": aparams.get("link", "/automation")}])
                elif ap == "rtb_all":
                    for aid in sim_assets:
                        waypoint_nav.set_waypoint(aid, base_pos["lat"], base_pos["lng"])
                    aar_events.append({"type": "automation", "timestamp": now_iso(),
                        "elapsed": sim_clock["elapsed_sec"],
                        "details": f"Rule '{rule['name']}': RTB ALL executed"})
                elif ap == "speed_change":
                    sim_clock["speed"] = aparams.get("speed", 1.0)
                elif ap == "disable_rule":
                    rule["enabled"] = False
                exercise["events"].append({"type": "rule_fired", "rule": rule["name"],
                    "time": now_iso(), "elapsed": round(sim_clock["elapsed_sec"], 1)})

        # ── Exercise inject processing ──
        if exercise["active"]:
            for inj in exercise["injects"]:
                if inj.get("fired") or sim_clock["elapsed_sec"] < inj.get("trigger_at_sec", 9999):
                    continue
                inj["fired"] = True
                inj["fired_at"] = now_iso()
                it = inj.get("type", "")
                if it == "spawn_threat":
                    tid = f"EX-{uuid.uuid4().hex[:6]}"
                    sim_threats[tid] = {"id": tid, "type": inj.get("threat_type", "drone"),
                        "lat": inj.get("lat", base_pos["lat"] + 0.03),
                        "lng": inj.get("lng", base_pos["lng"] + 0.03),
                        "speed_kts": inj.get("speed_kts", 30), "neutralized": False,
                        "detected_by": [], "first_detected": None}
                elif it == "degrade_comms":
                    for a in sim_assets.values():
                        a["health"]["comms_strength"] = max(5, a["health"]["comms_strength"] - inj.get("amount", 40))
                elif it == "drain_battery":
                    targets = inj.get("targets", list(sim_assets.keys())[:3])
                    for aid in targets:
                        if aid in sim_assets:
                            sim_assets[aid]["health"]["battery_pct"] = max(5,
                                sim_assets[aid]["health"]["battery_pct"] - inj.get("amount", 50))
                elif it == "message":
                    socketio.emit("amos_alerts", [{"level": "info",
                        "msg": f"[EXERCISE] {inj.get('message', 'Inject triggered')}",
                        "link": "/automation"}])
                exercise["completed_injects"] += 1
                exercise["score"] += inj.get("points", 10)
                aar_events.append({"type": "exercise_inject", "timestamp": now_iso(),
                    "elapsed": sim_clock["elapsed_sec"],
                    "details": f"Exercise inject: {it} — {inj.get('description', '')}"})

        # ── Alert system (throttled — 30s cooldown) ──
        _ALERT_COOLDOWN_SEC = 30
        alerts = []
        if risk.get("level") in ("HIGH", "CRITICAL"):
            alerts.append({"key": "risk", "level": "critical",
                           "msg": f"Risk level {risk['level']} — score {risk.get('score', 0)}",
                           "link": "/cognitive"})
        low_batt = [a["id"] for a in sim_assets.values() if a["health"]["battery_pct"] < 15]
        if low_batt:
            alerts.append({"key": "low_batt", "level": "warning",
                           "msg": f"Low battery: {', '.join(low_batt[:3])}", "link": "/dashboard"})
        low_comms = [a["id"] for a in sim_assets.values() if a["health"]["comms_strength"] < 25]
        if low_comms:
            alerts.append({"key": "low_comms", "level": "warning",
                           "msg": f"Comms degraded: {', '.join(low_comms[:3])}", "link": "/integrations"})
        if phal > 5:
            alerts.append({"key": "pending_hal", "level": "info",
                           "msg": f"{phal} pending HAL approvals", "link": "/hal"})
        ready = []
        for al in alerts:
            k = al.pop("key")
            if now - alert_cooldowns.get(k, 0) >= _ALERT_COOLDOWN_SEC:
                alert_cooldowns[k] = now
                ready.append(al)
        if ready:
            socketio.emit("amos_alerts", ready)
