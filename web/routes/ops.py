"""AMOS Ops Routes — Readiness, Logistics, Weather, BDA, EOB, Cyber, Theater, Audit, ROE."""

import math
import random
import uuid
from flask import Blueprint, request, jsonify, session
from web.extensions import login_required, ctx, load_locations, save_locations, socketio
from web.state import (
    sim_assets, sim_threats, sim_clock,
    waypoint_nav, commander_support,
    threat_intel, weather, bda_reports, eob_units,
    online_ops, asset_locks,
    ew_capable, ew_active_jams, ew_intercepts,
    sigint_intercepts, sigint_emitter_db,
    cyber_events, cyber_blocked_ips, supply_history,
    cm_log, aar_events,
    _px4, _tak, _link16, ros2_bridge,
    _adsb, _aprs, _ais, _lora, _remoteid, _dragonos, _zmeta, _cot_receiver,
    _sdrpp, _sigdigger,
    base_pos, AO_CENTER, platoon,
    roe_engine, USERS,
    db_execute, fetchall, db_check,
    now_iso, from_json, to_json,
    persist_bda, persist_engagement,
    drone_ref_db,
)

bp = Blueprint("ops", __name__)


# ══════════════════════════════════════════════════════════
#  HEALTH / READINESS PROBES  (no auth — LB / k8s probes)
# ══════════════════════════════════════════════════════════
@bp.route("/healthz")
def healthz():
    """Liveness probe — is the process running?"""
    return jsonify({"status": "ok"})


@bp.route("/readyz")
def readyz():
    """Readiness probe — is the app ready to serve traffic?"""
    checks = {
        "app": True,
        "assets_loaded": len(sim_assets) > 0,
        "db": db_check(),
    }
    ok = all(checks.values())
    return jsonify({"status": "ok" if ok else "degraded", "checks": checks}), 200 if ok else 503


# ══════════════════════════════════════════════════════════
#  SWARM FORMATION CONTROL  (NO @login_required — preserved)
# ══════════════════════════════════════════════════════════
@bp.route("/swarm/formation", methods=["POST"])
def set_swarm_formation():
    """Set swarm formation — assets MOVE to positions via waypoints."""
    import math as _m
    d = request.get_json() or {}
    domain = (d.get("domain") or "ground").lower().strip()
    formation = (d.get("formation") or d.get("pattern") or "LINE").upper().strip()

    theater = (d.get("theater") or "").lower().strip()

    domain_assets = []
    for aid, a in sim_assets.items():
        a_domain = str(a.get("domain", "")).lower().strip()
        a_theater = str(a.get("theater", "tehran")).lower().strip()
        if (a_domain == domain or domain == "all") and \
           (not theater or a_theater == theater):
            domain_assets.append((aid, a))

    if not domain_assets:
        existing = {}
        for aid, a in sim_assets.items():
            dd = str(a.get("domain", "?")).lower()
            existing[dd] = existing.get(dd, 0) + 1
        return jsonify({"error": f"No {domain} assets found. Have: {existing}"}), 400

    n = len(domain_assets)

    def get_pos(a):
        p = a.get("position", a)
        return float(p.get("lat", 0)), float(p.get("lng", 0))

    lats, lngs = [], []
    for aid, a in domain_assets:
        lat, lng = get_pos(a)
        lats.append(lat)
        lngs.append(lng)

    clat = sum(lats) / n
    clng = sum(lngs) / n
    spacing = 0.002 if domain == "ground" else 0.005

    targets = []
    for i, (aid, a) in enumerate(domain_assets):
        if formation == "LINE":
            nlat = clat
            nlng = clng + (i - n / 2) * spacing
        elif formation == "COLUMN":
            nlat = clat + (i - n / 2) * spacing
            nlng = clng
        elif formation == "WEDGE":
            row = i // 2
            side = 1 if i % 2 == 0 else -1
            nlat = clat - row * spacing
            nlng = clng + side * row * spacing * 0.6
        elif formation == "DIAMOND":
            angle = i * (2 * _m.pi / n)
            r = spacing * 2
            nlat = clat + r * _m.cos(angle)
            nlng = clng + r * _m.sin(angle)
        elif formation == "SPREAD":
            row = i // 3
            col = i % 3
            nlat = clat + (row - n / 6) * spacing * 1.5
            nlng = clng + (col - 1) * spacing * 2
        elif formation == "ORBIT":
            angle = i * (2 * _m.pi / n)
            r = spacing * 3
            nlat = clat + r * _m.cos(angle)
            nlng = clng + r * _m.sin(angle)
        else:
            nlat = clat
            nlng = clng + (i - n / 2) * spacing

        nlat = round(nlat, 6)
        nlng = round(nlng, 6)
        waypoint_nav.set_waypoint(aid, nlat, nlng, label=f"FORM-{formation}")
        targets.append({"id": aid, "lat": nlat, "lng": nlng})

    members = []
    for i, (aid, a) in enumerate(domain_assets):
        p = a.get("position", a)
        cur_lat = float(p.get("lat", 0))
        cur_lng = float(p.get("lng", 0))
        tgt = targets[i]
        members.append({
            "id": aid, "callsign": a.get("callsign", aid),
            "lat": cur_lat, "lng": cur_lng,
            "formation_lat": tgt["lat"], "formation_lng": tgt["lng"]
        })

    formation_obj = {
        "pattern": formation.lower(),
        "members": members,
        "center": {"lat": clat, "lng": clng}
    }
    msg = f"{n} {domain} assets moving to {formation} (watch the map!)"
    return jsonify({
        "success": True, "formation": formation_obj, "pattern": formation,
        "domain": domain, "count": n, "positions": targets, "message": msg
    })


@bp.route("/swarm/formation/clear", methods=["POST"])
@bp.route("/swarm/clear", methods=["POST"])
def clear_swarm_formation():
    """Clear formation, return to patrol."""
    d = request.get_json() or {}
    domain = d.get("domain", "ground").lower().strip()
    theater = (d.get("theater") or "").lower().strip()
    count = 0
    for aid, a in sim_assets.items():
        a_domain = str(a.get("domain", "")).lower().strip()
        a_theater = str(a.get("theater", "tehran")).lower().strip()
        if (a_domain == domain or domain == "all") and \
           (not theater or a_theater == theater):
            count += 1
    return jsonify({"success": True, "count": count,
                    "message": f"{count} {domain} assets in {theater or 'all theaters'} returned to patrol"})


@bp.route("/swarm/debug")
def swarm_debug():
    """Debug: show asset structure."""
    info = {"asset_count": len(sim_assets), "domains": {}, "sample_keys": None, "position_sample": None}
    for aid, a in sim_assets.items():
        dom = str(a.get("domain", "?")).lower()
        info["domains"][dom] = info["domains"].get(dom, 0) + 1
        if info["sample_keys"] is None:
            info["sample_keys"] = list(a.keys())[:15]
            if "position" in a:
                info["position_sample"] = a["position"]
            elif "lat" in a:
                info["position_sample"] = {"lat": a["lat"], "lng": a["lng"]}
            info["sample_id"] = aid
    return jsonify(info)


# ═══════════════════════════════════════════════════════════
#  AUDIT API
# ═══════════════════════════════════════════════════════════
@bp.route("/audit")
@login_required
def api_audit():
    c = ctx()
    if "admin" not in c["access"]:
        return jsonify({"error": "Admin access required"}), 403
    limit = request.args.get("limit", 100, type=int)
    rows = fetchall("SELECT * FROM audit_log ORDER BY id DESC LIMIT %s", (limit,))
    return jsonify([{**r, "timestamp": str(r["timestamp"]), "detail": from_json(r.get("detail"))} for r in rows])


# ═══════════════════════════════════════════════════════════
#  BRIDGE APIs (PX4 + TAK + Link 16)
# ═══════════════════════════════════════════════════════════
@bp.route("/bridge/all")
@login_required
def api_bridge_all():
    """Unified status of all integration bridges."""
    def _ss(b):
        if not b:
            return {"available": False, "connected": False}
        s = b.get_status() if hasattr(b, "get_status") else {}
        s["available"] = True
        s["connected"] = getattr(b, "connected", False)
        return s
    return jsonify({
        "px4": _px4.get_status() if _px4 else {"connected": False},
        "tak": _tak.get_status() if _tak else {"connected": False},
        "link16": _link16.get_status() if _link16 else {"connected": False},
        "ros2": ros2_bridge.get_status() if ros2_bridge else {"available": False},
        "adsb": _ss(_adsb), "aprs": _ss(_aprs), "ais": _ss(_ais),
        "lora": _ss(_lora), "remoteid": _ss(_remoteid),
        "dragonos": _ss(_dragonos),
        "zmeta": _ss(_zmeta),
        "cot": _ss(_cot_receiver),
        "sdrpp": _ss(_sdrpp),
        "sigdigger": _ss(_sigdigger),
    })

# ── PX4 ──
@bp.route("/bridge/px4/status")
@login_required
def api_px4_status():
    if not _px4:
        return jsonify({"connected": False, "error": "Bridge not loaded"})
    return jsonify(_px4.get_status())

@bp.route("/bridge/px4/telemetry")
@login_required
def api_px4_telemetry():
    if not _px4:
        return jsonify({})
    return jsonify({aid: _px4.get_telemetry(aid) for aid in _px4.vehicles})

@bp.route("/bridge/px4/register", methods=["POST"])
@login_required
def api_px4_register():
    if not _px4:
        return jsonify({"error": "PX4 bridge not available"}), 503
    d = request.get_json() or {}
    amos_id = d.get("asset_id", "").strip().upper()
    sysid = d.get("system_id", 1)
    if not amos_id:
        return jsonify({"error": "asset_id required"}), 400
    _px4.register_vehicle(amos_id, system_id=sysid)
    if amos_id not in sim_assets:
        sim_assets[amos_id] = {
            "id": amos_id, "type": "PX4_SITL", "domain": "air", "role": "recon",
            "autonomy_tier": 3, "sensors": ["GPS", "IMU", "CAMERA"],
            "weapons": [], "endurance_hr": 0.5,
            "position": {"lat": base_pos["lat"], "lng": base_pos["lng"], "alt_ft": 0},
            "status": "standby", "health": {"battery_pct": 100, "comms_strength": 100,
                                            "cpu_temp_c": 40, "gps_fix": True},
            "speed_kts": 0, "heading_deg": 0,
            "integration": "px4", "bridge_addr": _px4.connection_string
        }
    return jsonify({"status": "ok", "asset_id": amos_id, "system_id": sysid})

@bp.route("/bridge/px4/command", methods=["POST"])
@login_required
def api_px4_command():
    if not _px4 or not _px4.connected:
        return jsonify({"error": "PX4 not connected"}), 503
    d = request.get_json() or {}
    aid = d.get("asset_id", "").strip().upper()
    cmd = d.get("command", "").upper()
    ok = False
    if cmd == "ARM":
        ok = _px4.arm(aid)
    elif cmd == "WAYPOINT":
        ok = _px4.send_waypoint(aid, d.get("lat", 0), d.get("lng", 0),
                                d.get("alt_m", 50), d.get("speed_ms", 15))
    elif cmd in ("RTL", "LAND", "HOLD", "OFFBOARD", "AUTO"):
        ok = _px4.set_mode(aid, cmd)
    else:
        return jsonify({"error": f"Unknown command: {cmd}"}), 400
    return jsonify({"status": "ok" if ok else "failed", "command": cmd, "asset_id": aid})

# ── TAK Bridge ──
@bp.route("/bridge/tak/status")
@login_required
def api_tak_status():
    if not _tak:
        return jsonify({"connected": False, "error": "TAK bridge not loaded"})
    return jsonify(_tak.get_status())

@bp.route("/bridge/tak/connect", methods=["POST"])
@login_required
def api_tak_connect():
    if not _tak:
        return jsonify({"error": "TAK bridge not loaded"}), 503
    d = request.json or {}
    _tak.host = d.get("host", _tak.host)
    _tak.port = int(d.get("port", _tak.port))
    _tak.protocol = d.get("protocol", _tak.protocol)
    ok = _tak.connect()
    return jsonify({"status": "ok" if ok else "failed", "connected": _tak.connected})

@bp.route("/bridge/tak/disconnect", methods=["POST"])
@login_required
def api_tak_disconnect():
    if _tak and _tak.sock:
        try: _tak.sock.close()
        except Exception: pass
        _tak.connected = False
    return jsonify({"status": "ok"})

# ── Link 16 ──
@bp.route("/bridge/link16/status")
@login_required
def api_link16_status():
    if not _link16:
        return jsonify({"connected": False, "error": "Link 16 not loaded"})
    return jsonify(_link16.get_status())

@bp.route("/bridge/link16/tracks")
@login_required
def api_link16_tracks():
    if not _link16:
        return jsonify({})
    return jsonify(_link16.get_tactical_picture())

@bp.route("/bridge/link16/messages")
@login_required
def api_link16_messages():
    if not _link16:
        return jsonify([])
    j_type = request.args.get("j_type")
    limit = request.args.get("limit", 50, type=int)
    return jsonify(_link16.get_messages(j_type=j_type, limit=limit))

@bp.route("/bridge/link16/participants")
@login_required
def api_link16_participants():
    if not _link16:
        return jsonify({})
    return jsonify(_link16.get_participants())

@bp.route("/bridge/link16/join", methods=["POST"])
@login_required
def api_link16_join():
    if not _link16:
        return jsonify({"error": "Link 16 not loaded"}), 503
    d = request.json or {}
    aid = d.get("asset_id", "").strip().upper()
    if not aid or aid not in sim_assets:
        return jsonify({"error": "Valid asset_id required"}), 400
    tn = _link16.join(aid, role=d.get("role", "PARTICIPANT"))
    return jsonify({"status": "ok", "asset_id": aid, "track_number": tn})

@bp.route("/bridge/link16/command", methods=["POST"])
@login_required
def api_link16_command():
    if not _link16:
        return jsonify({"error": "Link 16 not loaded"}), 503
    d = request.json or {}
    msg = _link16.send_command(
        d.get("from_id", ""), d.get("to_id", ""),
        d.get("command_type", "ENGAGE"), d.get("params", {}))
    return jsonify({"status": "ok" if msg else "failed", "message": msg})


# ═══════════════════════════════════════════════════════════
#  SENSOR BRIDGES (ADS-B, APRS, AIS, Meshtastic, RemoteID)
# ═══════════════════════════════════════════════════════════
@bp.route("/bridge/sensor/all")
@login_required
def api_sensor_bridges_all():
    """Unified status of all sensor bridges."""
    def _status(bridge, name):
        if not bridge:
            return {"name": name, "available": False, "connected": False}
        s = bridge.get_status() if hasattr(bridge, "get_status") else {}
        s["name"] = name
        s["available"] = True
        s["connected"] = getattr(bridge, "connected", False)
        return s
    return jsonify({
        "adsb": _status(_adsb, "ADS-B"),
        "aprs": _status(_aprs, "APRS"),
        "ais": _status(_ais, "AIS"),
        "lora": _status(_lora, "Meshtastic"),
        "remoteid": _status(_remoteid, "RemoteID"),
        "dragonos": _status(_dragonos, "DragonOS"),
    })

# ── ADS-B ──
@bp.route("/bridge/adsb/status")
@login_required
def api_adsb_status():
    if not _adsb:
        return jsonify({"available": False, "connected": False})
    return jsonify(_adsb.get_status())

@bp.route("/bridge/adsb/connect", methods=["POST"])
@login_required
def api_adsb_connect():
    if not _adsb:
        return jsonify({"error": "ADS-B receiver not loaded"}), 503
    d = request.json or {}
    _adsb.host = d.get("host", _adsb.host)
    _adsb.port = int(d.get("port", _adsb.port))
    # UI sends "protocol" (sbs/beast/raw) → bridge uses "mode" (sbs/beast/json)
    proto = d.get("protocol", _adsb.mode)
    _adsb.mode = "json" if proto == "raw" else proto
    ok = _adsb.connect()
    if ok:
        _adsb.start_tracking()
    return jsonify({"status": "ok" if ok else "failed", "connected": _adsb.connected})

@bp.route("/bridge/adsb/disconnect", methods=["POST"])
@login_required
def api_adsb_disconnect():
    if _adsb:
        _adsb.stop_tracking()
        _adsb.disconnect()
    return jsonify({"status": "ok"})

@bp.route("/bridge/adsb/tracks")
@login_required
def api_adsb_tracks():
    if not _adsb or not _adsb.connected:
        return jsonify({})
    return jsonify(getattr(_adsb, "aircraft", {}))

# ── APRS ──
@bp.route("/bridge/aprs/status")
@login_required
def api_aprs_status():
    if not _aprs:
        return jsonify({"available": False, "connected": False})
    return jsonify(_aprs.get_status())

@bp.route("/bridge/aprs/connect", methods=["POST"])
@login_required
def api_aprs_connect():
    if not _aprs:
        return jsonify({"error": "APRS bridge not loaded"}), 503
    d = request.json or {}
    if hasattr(_aprs, "callsign") and d.get("callsign"):
        _aprs.callsign = d["callsign"]
    if hasattr(_aprs, "server") and d.get("server"):
        _aprs.server = d["server"]
    ok = _aprs.connect()
    return jsonify({"status": "ok" if ok else "failed", "connected": _aprs.connected})

@bp.route("/bridge/aprs/disconnect", methods=["POST"])
@login_required
def api_aprs_disconnect():
    if _aprs:
        _aprs.disconnect()
    return jsonify({"status": "ok"})

# ── AIS ──
@bp.route("/bridge/ais/status")
@login_required
def api_ais_status():
    if not _ais:
        return jsonify({"available": False, "connected": False})
    return jsonify(_ais.get_status())

@bp.route("/bridge/ais/connect", methods=["POST"])
@login_required
def api_ais_connect():
    if not _ais:
        return jsonify({"error": "AIS receiver not loaded"}), 503
    d = request.json or {}
    _ais.host = d.get("host", _ais.host)
    _ais.port = int(d.get("port", _ais.port))
    ok = _ais.connect()
    return jsonify({"status": "ok" if ok else "failed", "connected": _ais.connected})

@bp.route("/bridge/ais/disconnect", methods=["POST"])
@login_required
def api_ais_disconnect():
    if _ais:
        _ais.disconnect()
    return jsonify({"status": "ok"})

@bp.route("/bridge/ais/vessels")
@login_required
def api_ais_vessels():
    if not _ais or not _ais.connected:
        return jsonify({})
    return jsonify(getattr(_ais, "vessels", {}))

# ── LoRa / Meshtastic ──
@bp.route("/bridge/lora/status")
@login_required
def api_lora_status():
    if not _lora:
        return jsonify({"available": False, "connected": False})
    return jsonify(_lora.get_status())

@bp.route("/bridge/lora/connect", methods=["POST"])
@login_required
def api_lora_connect():
    if not _lora:
        return jsonify({"error": "LoRa bridge not loaded"}), 503
    d = request.json or {}
    if hasattr(_lora, "connection_type") and d.get("connection_type"):
        _lora.connection_type = d["connection_type"]
    if hasattr(_lora, "device") and d.get("device"):
        _lora.device = d["device"]
    ok = _lora.connect()
    return jsonify({"status": "ok" if ok else "failed", "connected": _lora.connected})

@bp.route("/bridge/lora/disconnect", methods=["POST"])
@login_required
def api_lora_disconnect():
    if _lora:
        _lora.disconnect()
    return jsonify({"status": "ok"})

@bp.route("/bridge/lora/send", methods=["POST"])
@login_required
def api_lora_send():
    if not _lora or not _lora.connected:
        return jsonify({"error": "LoRa not connected"}), 503
    d = request.json or {}
    text = d.get("text", "")
    dest = d.get("destination", "^all")
    ok = _lora.send_message(text, destination=dest)
    return jsonify({"status": "ok" if ok else "failed"})

@bp.route("/bridge/lora/nodes")
@login_required
def api_lora_nodes():
    if not _lora or not _lora.connected:
        return jsonify({})
    return jsonify(getattr(_lora, "nodes", {}))

# ── RemoteID ──
@bp.route("/bridge/remoteid/status")
@login_required
def api_remoteid_status():
    if not _remoteid:
        return jsonify({"available": False, "connected": False})
    return jsonify(_remoteid.get_status())

@bp.route("/bridge/remoteid/connect", methods=["POST"])
@login_required
def api_remoteid_connect():
    if not _remoteid:
        return jsonify({"error": "RemoteID bridge not loaded"}), 503
    ok = _remoteid.connect()
    return jsonify({"status": "ok" if ok else "failed", "connected": _remoteid.connected})

@bp.route("/bridge/remoteid/disconnect", methods=["POST"])
@login_required
def api_remoteid_disconnect():
    if _remoteid:
        _remoteid.disconnect()
    return jsonify({"status": "ok"})

@bp.route("/bridge/remoteid/beacons")
@login_required
def api_remoteid_beacons():
    if not _remoteid or not _remoteid.connected:
        return jsonify({})
    return jsonify(getattr(_remoteid, "beacons", {}))


# ── DragonOS / WarDragon ──
@bp.route("/bridge/dragonos/status")
@login_required
def api_dragonos_status():
    if not _dragonos:
        return jsonify({"available": False, "connected": False})
    return jsonify(_dragonos.get_status())

@bp.route("/bridge/dragonos/connect", methods=["POST"])
@login_required
def api_dragonos_connect():
    if not _dragonos:
        return jsonify({"error": "DragonOS bridge not loaded"}), 503
    d = request.json or {}
    _dragonos.node_id = d.get("node_id", _dragonos.node_id)
    _dragonos.mqtt_host = d.get("mqtt_host", _dragonos.mqtt_host)
    _dragonos.mqtt_port = int(d.get("mqtt_port", _dragonos.mqtt_port))
    if d.get("mqtt_user"): _dragonos.mqtt_user = d["mqtt_user"]
    if d.get("mqtt_pass"): _dragonos.mqtt_pass = d["mqtt_pass"]
    if d.get("kismet_url"): _dragonos.kismet_url = d["kismet_url"]
    if d.get("topic_prefix"): _dragonos.topic_prefix = d["topic_prefix"]
    ok = _dragonos.connect()
    return jsonify({"status": "ok" if ok else "failed", "connected": _dragonos.connected})

@bp.route("/bridge/dragonos/disconnect", methods=["POST"])
@login_required
def api_dragonos_disconnect():
    if _dragonos:
        _dragonos.disconnect()
    return jsonify({"status": "ok"})

@bp.route("/bridge/dragonos/drones")
@login_required
def api_dragonos_drones():
    if not _dragonos or not _dragonos.connected:
        return jsonify([])
    return jsonify(_dragonos.get_drone_detections())

@bp.route("/bridge/dragonos/remoteid")
@login_required
def api_dragonos_remoteid():
    if not _dragonos or not _dragonos.connected:
        return jsonify([])
    return jsonify(_dragonos.get_remoteid_decodes())

@bp.route("/bridge/dragonos/spectrum")
@login_required
def api_dragonos_spectrum():
    if not _dragonos or not _dragonos.connected:
        return jsonify([])
    return jsonify(_dragonos.get_spectrum_events())

@bp.route("/bridge/dragonos/df")
@login_required
def api_dragonos_df():
    if not _dragonos or not _dragonos.connected:
        return jsonify([])
    return jsonify(_dragonos.get_df_bearings())

@bp.route("/bridge/dragonos/kismet")
@login_required
def api_dragonos_kismet():
    if not _dragonos or not _dragonos.connected:
        return jsonify({})
    return jsonify(_dragonos.get_kismet_devices())


# ── ZMeta ISR Metadata ──
@bp.route("/bridge/zmeta/status")
@login_required
def api_zmeta_status():
    if not _zmeta:
        return jsonify({"available": False, "connected": False})
    return jsonify(_zmeta.get_status())

@bp.route("/bridge/zmeta/connect", methods=["POST"])
@login_required
def api_zmeta_connect():
    if not _zmeta:
        return jsonify({"error": "ZMeta bridge not loaded"}), 503
    d = request.json or {}
    _zmeta.listen_host = d.get("listen_host", _zmeta.listen_host)
    _zmeta.listen_port = int(d.get("listen_port", _zmeta.listen_port))
    _zmeta.forward_host = d.get("forward_host", _zmeta.forward_host)
    _zmeta.forward_port = int(d.get("forward_port", _zmeta.forward_port))
    if d.get("profile"): _zmeta.profile = d["profile"].upper()
    if d.get("platform_id"): _zmeta.platform_id = d["platform_id"]
    ok = _zmeta.connect()
    return jsonify({"status": "ok" if ok else "failed", "connected": _zmeta.connected})

@bp.route("/bridge/zmeta/disconnect", methods=["POST"])
@login_required
def api_zmeta_disconnect():
    if _zmeta:
        _zmeta.disconnect()
    return jsonify({"status": "ok"})

@bp.route("/bridge/zmeta/events")
@login_required
def api_zmeta_events():
    if not _zmeta or not _zmeta.connected:
        return jsonify([])
    limit = request.args.get("limit", 100, type=int)
    return jsonify(_zmeta.get_all_events(limit))

@bp.route("/bridge/zmeta/tracks")
@login_required
def api_zmeta_tracks():
    if not _zmeta or not _zmeta.connected:
        return jsonify([])
    return jsonify(_zmeta.get_track_states() + _zmeta.get_fusions())

@bp.route("/bridge/zmeta/commands")
@login_required
def api_zmeta_commands():
    if not _zmeta or not _zmeta.connected:
        return jsonify({"inbound": [], "outbound": []})
    return jsonify({"inbound": _zmeta.get_commands_in(), "outbound": _zmeta.get_commands_out()})

@bp.route("/bridge/zmeta/link-status")
@login_required
def api_zmeta_link_status():
    if not _zmeta or not _zmeta.connected:
        return jsonify([])
    return jsonify(_zmeta.get_link_status())

@bp.route("/bridge/zmeta/emit-state", methods=["POST"])
@login_required
def api_zmeta_emit_state():
    if not _zmeta or not _zmeta.connected:
        return jsonify({"error": "ZMeta not connected"}), 503
    d = request.json or {}
    ev = _zmeta.emit_track_state(
        track_id=d.get("track_id", ""),
        lat=d.get("lat", 0), lng=d.get("lng", 0),
        alt_m=d.get("alt_m", 0),
        heading_deg=d.get("heading_deg"),
        speed_mps=d.get("speed_mps"),
        confidence=d.get("confidence", 0.8),
        entity_class=d.get("entity_class"),
        valid_for_ms=d.get("valid_for_ms", 5000),
    )
    return jsonify({"status": "ok", "event_id": ev["event"]["event_id"]})

@bp.route("/bridge/zmeta/emit-command", methods=["POST"])
@login_required
def api_zmeta_emit_command():
    if not _zmeta or not _zmeta.connected:
        return jsonify({"error": "ZMeta not connected"}), 503
    d = request.json or {}
    ev = _zmeta.emit_command(
        task_type=d.get("task_type", "GOTO"),
        lat=d.get("lat", 0), lng=d.get("lng", 0),
        valid_for_ms=d.get("valid_for_ms", 600000),
        priority=d.get("priority", "MED"),
        geometry=d.get("geometry"),
    )
    return jsonify({"status": "ok", "task_id": ev["payload"]["task_id"]})


# ── SDR++ ──
@bp.route("/bridge/sdrpp/status")
@login_required
def api_sdrpp_status():
    if not _sdrpp:
        return jsonify({"available": False, "connected": False})
    return jsonify(_sdrpp.get_status())

@bp.route("/bridge/sdrpp/connect", methods=["POST"])
@login_required
def api_sdrpp_connect():
    if not _sdrpp:
        return jsonify({"error": "SDR++ bridge not loaded"}), 503
    d = request.json or {}
    _sdrpp.host = d.get("host", _sdrpp.host)
    _sdrpp.port = int(d.get("port", _sdrpp.port))
    _sdrpp.base_url = f"http://{_sdrpp.host}:{_sdrpp.port}"
    ok = _sdrpp.connect()
    return jsonify({"status": "ok" if ok else "failed", "connected": _sdrpp.connected})

@bp.route("/bridge/sdrpp/disconnect", methods=["POST"])
@login_required
def api_sdrpp_disconnect():
    if _sdrpp:
        _sdrpp.disconnect()
    return jsonify({"status": "ok"})

@bp.route("/bridge/sdrpp/tune", methods=["POST"])
@login_required
def api_sdrpp_tune():
    if not _sdrpp or not _sdrpp.connected:
        return jsonify({"error": "SDR++ not connected"}), 503
    d = request.json or {}
    freq = d.get("frequency_hz", d.get("freq", 0))
    if not freq:
        return jsonify({"error": "frequency_hz required"}), 400
    ok = _sdrpp.set_frequency(int(freq))
    return jsonify({"status": "ok" if ok else "failed", "frequency_hz": int(freq)})

# ── SigDigger ──
@bp.route("/bridge/sigdigger/status")
@login_required
def api_sigdigger_status():
    if not _sigdigger:
        return jsonify({"available": False, "connected": False})
    return jsonify(_sigdigger.get_status())

@bp.route("/bridge/sigdigger/connect", methods=["POST"])
@login_required
def api_sigdigger_connect():
    if not _sigdigger:
        return jsonify({"error": "SigDigger bridge not loaded"}), 503
    d = request.json or {}
    _sigdigger.listen_port = int(d.get("listen_port", _sigdigger.listen_port))
    ok = _sigdigger.connect()
    return jsonify({"status": "ok" if ok else "failed", "connected": _sigdigger.connected})

@bp.route("/bridge/sigdigger/disconnect", methods=["POST"])
@login_required
def api_sigdigger_disconnect():
    if _sigdigger:
        _sigdigger.disconnect()
    return jsonify({"status": "ok"})

@bp.route("/bridge/sigdigger/detections")
@login_required
def api_sigdigger_detections():
    if not _sigdigger or not _sigdigger.connected:
        return jsonify([])
    limit = request.args.get("limit", 100, type=int)
    return jsonify(_sigdigger.get_detections(limit))


# ── CoT (Cursor-on-Target) Receiver ──
@bp.route("/bridge/cot/status")
@login_required
def api_cot_status():
    if not _cot_receiver:
        return jsonify({"available": False, "connected": False})
    return jsonify(_cot_receiver.get_status())

@bp.route("/bridge/cot/connect", methods=["POST"])
@login_required
def api_cot_connect():
    if not _cot_receiver:
        return jsonify({"error": "CoT receiver not loaded"}), 503
    d = request.json or {}
    _cot_receiver.listen_addr = d.get("listen_addr", _cot_receiver.listen_addr)
    _cot_receiver.udp_port = int(d.get("udp_port", _cot_receiver.udp_port))
    _cot_receiver.tcp_port = int(d.get("tcp_port", _cot_receiver.tcp_port))
    if d.get("mcast_group"): _cot_receiver.mcast_group = d["mcast_group"]
    _cot_receiver.enable_udp = d.get("enable_udp", _cot_receiver.enable_udp)
    _cot_receiver.enable_tcp = d.get("enable_tcp", _cot_receiver.enable_tcp)
    ok = _cot_receiver.connect()
    return jsonify({"status": "ok" if ok else "failed", "connected": _cot_receiver.connected})

@bp.route("/bridge/cot/disconnect", methods=["POST"])
@login_required
def api_cot_disconnect():
    if _cot_receiver:
        _cot_receiver.disconnect()
    return jsonify({"status": "ok"})

@bp.route("/bridge/cot/events")
@login_required
def api_cot_events():
    if not _cot_receiver or not _cot_receiver.connected:
        return jsonify([])
    limit = request.args.get("limit", 100, type=int)
    return jsonify(_cot_receiver.get_all_events(limit))

@bp.route("/bridge/cot/tracks")
@login_required
def api_cot_tracks():
    if not _cot_receiver or not _cot_receiver.connected:
        return jsonify([])
    return jsonify(_cot_receiver.get_all_tracks())

@bp.route("/bridge/cot/friendlies")
@login_required
def api_cot_friendlies():
    if not _cot_receiver or not _cot_receiver.connected:
        return jsonify([])
    return jsonify(_cot_receiver.get_friendlies())

@bp.route("/bridge/cot/hostiles")
@login_required
def api_cot_hostiles():
    if not _cot_receiver or not _cot_receiver.connected:
        return jsonify([])
    return jsonify(_cot_receiver.get_hostiles())

@bp.route("/bridge/cot/inject", methods=["POST"])
@login_required
def api_cot_inject():
    """Manually inject a CoT XML event (for testing)."""
    if not _cot_receiver:
        return jsonify({"error": "CoT receiver not loaded"}), 503
    d = request.json or {}
    xml = d.get("xml", "")
    if not xml:
        return jsonify({"error": "xml field required"}), 400
    _cot_receiver.inject_cot_xml(xml)
    return jsonify({"status": "ok", "injected": True})


# ═══════════════════════════════════════════════════════════
#  GeoJSON / KML OVERLAY IMPORT
# ═══════════════════════════════════════════════════════════
from core.geo_import import (
    import_file as geo_import_file,
    list_overlays, get_overlay, delete_overlay, update_overlay,
)

@bp.route("/overlays")
@login_required
def api_overlay_list():
    """List all imported geo overlays."""
    return jsonify(list_overlays())

@bp.route("/overlays/<overlay_id>")
@login_required
def api_overlay_get(overlay_id):
    """Get full overlay including GeoJSON features."""
    ov = get_overlay(overlay_id)
    if not ov:
        return jsonify({"error": "Overlay not found"}), 404
    return jsonify(ov)

@bp.route("/overlays/<overlay_id>/geojson")
@login_required
def api_overlay_geojson(overlay_id):
    """Return overlay as a pure GeoJSON FeatureCollection."""
    ov = get_overlay(overlay_id)
    if not ov:
        return jsonify({"error": "Overlay not found"}), 404
    return jsonify({"type": "FeatureCollection", "features": ov["features"]})

@bp.route("/overlays/import", methods=["POST"])
@login_required
def api_overlay_import():
    """Import GeoJSON or KML. Accepts JSON body or multipart file upload."""
    # Multipart file upload
    if request.files.get("file"):
        f = request.files["file"]
        raw = f.read().decode("utf-8", errors="ignore")
        fname = f.filename or "upload"
        name = request.form.get("name", "")
        color = request.form.get("color", "#00ff41")
    else:
        d = request.json or {}
        raw = d.get("data", d.get("geojson", d.get("kml", "")))
        fname = d.get("filename", "import.geojson")
        name = d.get("name", "")
        color = d.get("color", "#00ff41")
    if not raw:
        return jsonify({"error": "No file data provided"}), 400
    try:
        ov = geo_import_file(raw, filename=fname, name=name, color=color)
        return jsonify({"status": "ok", "overlay": {
            "id": ov["id"], "name": ov["name"],
            "source_format": ov["source_format"],
            "feature_count": len(ov["features"]),
        }})
    except Exception as e:
        return jsonify({"error": f"Parse failed: {e}"}), 400

@bp.route("/overlays/<overlay_id>", methods=["PATCH"])
@login_required
def api_overlay_update(overlay_id):
    """Update overlay metadata (name, visible, color)."""
    d = request.json or {}
    ov = update_overlay(overlay_id, d)
    if not ov:
        return jsonify({"error": "Overlay not found"}), 404
    return jsonify({"status": "ok", "id": overlay_id})

@bp.route("/overlays/<overlay_id>", methods=["DELETE"])
@login_required
def api_overlay_delete(overlay_id):
    """Delete an imported overlay."""
    ok = delete_overlay(overlay_id)
    if not ok:
        return jsonify({"error": "Overlay not found"}), 404
    return jsonify({"status": "ok"})


# ═══════════════════════════════════════════════════════════
#  THREAT INTELLIGENCE
# ═══════════════════════════════════════════════════════════
@bp.route("/threat-intel")
@login_required
def apithreat_intel():
    """Threat intelligence database."""
    return jsonify(threat_intel)


# ═══════════════════════════════════════════════════════════
#  READINESS SCORECARD
# ═══════════════════════════════════════════════════════════
@bp.route("/readiness")
@login_required
def api_readiness():
    """Pre-mission readiness scorecard."""
    total = len(sim_assets)
    avg_batt = sum(a["health"]["battery_pct"] for a in sim_assets.values()) / max(1, total)
    avg_comms = sum(a["health"]["comms_strength"] for a in sim_assets.values()) / max(1, total)
    low_batt = sum(1 for a in sim_assets.values() if a["health"]["battery_pct"] < 30)
    gps_fix = sum(1 for a in sim_assets.values() if a["health"].get("gps_fix", True))
    all_sensors = set()
    for a in sim_assets.values():
        all_sensors.update(a.get("sensors", []))
    armed = sum(1 for a in sim_assets.values() if a.get("weapons"))
    avg_endurance = sum(a.get("endurance_hr", 0) for a in sim_assets.values()) / max(1, total)
    intg = {"px4": _px4.connected if _px4 else False,
            "tak": _tak.connected if _tak else False,
            "link16": bool(_link16),
            "ros2": ros2_bridge.available if ros2_bridge else False}
    intg_score = sum(1 for v in intg.values() if v) / max(1, len(intg)) * 100
    domains = set(a.get("domain", "") for a in sim_assets.values())
    # Supply readiness
    fuels = [a["supplies"]["fuel_pct"] for a in sim_assets.values() if "supplies" in a]
    ammos = [a["supplies"]["ammo_rounds"] for a in sim_assets.values() if "supplies" in a]
    avg_fuel = sum(fuels) / max(1, len(fuels)) if fuels else 100
    avg_ammo = sum(ammos) / max(1, len(ammos)) if ammos else 100
    low_fuel = sum(1 for f in fuels if f < 25)
    supply_score = min(100, avg_fuel * 0.6 + min(100, avg_ammo / 2) * 0.4)
    # Weather impact
    ws = weather["wind_speed_kt"]; vis = weather["visibility_km"]
    ceil = weather["ceiling_ft"]; precip = weather["precipitation"]
    wx_penalty = (ws / 60) * 20 + (1 - vis / 30) * 25 + (1 - ceil / 40000) * 15
    wx_penalty += 20 if precip in ["heavy_rain", "snow"] else 5 if precip != "none" else 0
    weather_score = max(0, min(100, 100 - wx_penalty))
    # GO/NO-GO scores
    fleet_score = min(100, avg_batt * 0.4 + avg_comms * 0.3 + (gps_fix / max(1, total) * 100) * 0.3)
    weapon_score = (armed / max(1, total)) * 100
    sensor_score = min(100, len(all_sensors) * 12.5)
    endurance_score = min(100, avg_endurance * 10)
    overall = (fleet_score * 0.25 + weapon_score * 0.15 + sensor_score * 0.15 +
               endurance_score * 0.1 + intg_score * 0.05 + supply_score * 0.15 + weather_score * 0.15)
    go_status = "GO" if overall >= 70 else "MARGINAL" if overall >= 50 else "NO-GO"
    risk = commander_support.get_risk()
    return jsonify({
        "overall_score": round(overall, 1), "go_status": go_status,
        "fleet": {"total": total, "avg_battery": round(avg_batt, 1),
                  "avg_comms": round(avg_comms, 1), "low_battery": low_batt,
                  "gps_fix": gps_fix, "score": round(fleet_score, 1)},
        "weapons": {"armed_assets": armed, "unarmed": total - armed,
                    "score": round(weapon_score, 1)},
        "sensors": {"unique_types": sorted(list(all_sensors)),
                    "count": len(all_sensors), "score": round(sensor_score, 1)},
        "endurance": {"avg_hours": round(avg_endurance, 1),
                      "score": round(endurance_score, 1)},
        "supply": {"avg_fuel": round(avg_fuel, 1), "avg_ammo": round(avg_ammo, 1),
                   "low_fuel": low_fuel, "score": round(supply_score, 1)},
        "weather": {"conditions": weather["conditions"], "wind_kt": round(ws, 1),
                    "visibility_km": round(vis, 1), "score": round(weather_score, 1)},
        "integrations": {**intg, "score": round(intg_score, 1)},
        "domains": sorted(list(domains)),
        "risk": {"level": risk.get("level", "LOW"), "score": risk.get("score", 0)},
        "asset_details": [{"id": a["id"], "type": a["type"], "domain": a["domain"],
            "battery": a["health"]["battery_pct"], "comms": a["health"]["comms_strength"],
            "gps": a["health"].get("gps_fix", True),
            "fuel": a.get("supplies", {}).get("fuel_pct", 100),
            "ammo": a.get("supplies", {}).get("ammo_rounds", 0),
            "armed": bool(a.get("weapons")), "endurance_hr": a.get("endurance_hr", 0),
            "status": a["status"]} for a in sim_assets.values()],
    })


# ═══════════════════════════════════════════════════════════
#  MULTI-OPERATOR HTTP ROUTES
# ═══════════════════════════════════════════════════════════
@bp.route("/operators/online")
@login_required
def api_operators_online():
    ops = []
    for sid, info in online_ops.items():
        ops.append({"user": info["user"], "name": info["name"], "role": info["role"],
                    "domain": info.get("domain", "all"),
                    "page": info.get("page", ""), "color": info.get("color"),
                    "cursor": info.get("cursor"),
                    "connected_at": info["connected_at"]})
    return jsonify(ops)

@bp.route("/collaboration/status")
@login_required
def api_collaboration_status():
    """Collaboration summary: online operators, locks, cursors."""
    ops = []
    cursors = []
    for sid, info in online_ops.items():
        ops.append({"user": info["user"], "name": info["name"], "role": info["role"],
                    "domain": info.get("domain", "all"), "page": info.get("page", ""),
                    "color": info.get("color")})
        if info.get("cursor") and info["cursor"].get("lat") is not None:
            cursors.append({"user": info["user"], "name": info["name"],
                            "color": info.get("color"), **info["cursor"]})
    locks = [{"asset_id": aid, **lk} for aid, lk in asset_locks.items()]
    return jsonify({"operators": ops, "operator_count": len(ops),
                    "cursors": cursors, "locks": locks, "lock_count": len(locks)})

@bp.route("/chat/history")
@login_required
def api_chat_history():
    channel = request.args.get("channel", "general")
    limit = request.args.get("limit", 50, type=int)
    rows = fetchall(
        "SELECT sender, message, timestamp FROM chat_messages WHERE channel=%s ORDER BY id DESC LIMIT %s",
        (channel, limit))
    return jsonify([{"sender": r["sender"], "message": r["message"],
                     "timestamp": str(r["timestamp"])} for r in reversed(rows)])

@bp.route("/asset/locks")
@login_required
def apiasset_locks():
    return jsonify(asset_locks)


# ═══════════════════════════════════════════════════════════
#  CYBER OPS CENTER
# ═══════════════════════════════════════════════════════════
@bp.route("/cyber/topology")
@login_required
def api_cyber_topology():
    """Network topology graph for cyber ops visualization."""
    nodes = [
        {"id": "hq", "name": "HQ-NET", "type": "command", "status": "secure"},
        {"id": "mesh1", "name": "MESH-1", "type": "mesh", "status": "secure"},
        {"id": "mesh2", "name": "MESH-2", "type": "mesh", "status": "secure"},
        {"id": "sat", "name": "SAT-COM", "type": "comms", "status": "secure"},
        {"id": "gnd", "name": "GND-CTRL", "type": "control", "status": "secure"},
        {"id": "air", "name": "AIR-NET", "type": "control", "status": "secure"},
        {"id": "ew", "name": "EW-NODE", "type": "sensor", "status": "secure"},
        {"id": "sig", "name": "SIGINT", "type": "sensor", "status": "secure"},
        {"id": "sea", "name": "MAR-NET", "type": "control", "status": "secure"},
        {"id": "ext", "name": "EXTERN", "type": "external", "status": "warning"},
    ]
    links = [
        {"from": "hq", "to": "mesh1", "active": True},
        {"from": "hq", "to": "mesh2", "active": True},
        {"from": "hq", "to": "sat", "active": True},
        {"from": "mesh1", "to": "gnd", "active": True},
        {"from": "mesh1", "to": "air", "active": True},
        {"from": "mesh2", "to": "ew", "active": True},
        {"from": "mesh2", "to": "sig", "active": True},
        {"from": "mesh2", "to": "sea", "active": True},
        {"from": "sat", "to": "air", "active": True},
        {"from": "ext", "to": "hq", "active": True, "attack": False},
    ]
    recent = cyber_events[-50:]
    attacked_targets = set()
    for e in recent:
        if not e.get("blocked") and e.get("severity") in ("high", "critical"):
            attacked_targets.add(e.get("target", ""))
    for n in nodes:
        if n["id"] == "ext":
            has_active = any(not e.get("blocked") for e in recent)
            n["status"] = "compromised" if has_active else "warning"
        elif n["id"] in ("gnd", "air", "sea"):
            domain_assets = {a["id"] for a in sim_assets.values()
                            if a["domain"] == {"gnd": "ground", "air": "air", "sea": "maritime"}.get(n["id"], "")}
            if domain_assets & attacked_targets:
                n["status"] = "under_attack"
    for lnk in links:
        if lnk["from"] == "ext":
            lnk["attack"] = any(not e.get("blocked") for e in recent)
    return jsonify({"nodes": nodes, "links": links, "active_attacks": len(attacked_targets)})

@bp.route("/cyber/killchain")
@login_required
def api_cyber_killchain():
    """Map cyber events to intrusion kill chain stages."""
    stages = [
        {"id": "recon", "name": "RECON", "types": ["port_scan", "dns_exfil"], "events": [], "count": 0},
        {"id": "weaponize", "name": "WEAPONIZE", "types": [], "events": [], "count": 0},
        {"id": "deliver", "name": "DELIVER", "types": ["brute_force", "c2_beacon"], "events": [], "count": 0},
        {"id": "exploit", "name": "EXPLOIT", "types": ["lateral_move"], "events": [], "count": 0},
        {"id": "control", "name": "C2", "types": ["c2_beacon"], "events": [], "count": 0},
        {"id": "execute", "name": "EXECUTE", "types": ["dns_exfil", "lateral_move"], "events": [], "count": 0},
    ]
    stage_map = {}
    for s in stages:
        for t in s["types"]:
            stage_map.setdefault(t, []).append(s)
    for e in cyber_events[-100:]:
        etype = e.get("type", "")
        for s in stage_map.get(etype, []):
            s["count"] += 1
            if len(s["events"]) < 5:
                s["events"].append({"id": e["id"], "type": etype,
                    "severity": e.get("severity"), "blocked": e.get("blocked", False)})
    return jsonify(stages)


# ═══════════════════════════════════════════════════════════
#  THEATER OPERATIONS
# ═══════════════════════════════════════════════════════════
@bp.route("/theater/list")
@login_required
def api_theater_list():
    """List all available theaters."""
    data = load_locations()
    theaters = []
    for key, loc in data.get("locations", {}).items():
        theaters.append({"key": key, "name": loc.get("name", key),
            "lat": loc.get("lat", 0), "lng": loc.get("lng", 0),
            "zoom": loc.get("zoom", 10), "description": loc.get("description", ""),
            "active": key == data.get("active", "")})
    return jsonify(theaters)

@bp.route("/theater/switch", methods=["POST"])
@login_required
def api_theater_switch():
    """Switch active theater — updates map center for all clients."""
    d = request.json or {}
    key = d.get("key", "")
    data = load_locations()
    if key not in data.get("locations", {}):
        return jsonify({"error": "Theater not found"}), 404
    loc = data["locations"][key]
    data["active"] = key
    save_locations(data)
    base_pos["lat"] = loc["lat"]
    base_pos["lng"] = loc["lng"]
    base_pos["name"] = loc.get("name", key)
    socketio.emit("theater_changed", {
        "key": key, "name": loc.get("name", key),
        "lat": loc["lat"], "lng": loc["lng"],
        "zoom": loc.get("zoom", 10)
    })
    c = ctx()
    aar_events.append({"type": "theater_switch", "timestamp": now_iso(),
        "elapsed": sim_clock["elapsed_sec"],
        "details": f"Theater switched to {loc.get('name', key)} by {c['name']}"})
    return jsonify({"status": "ok", "theater": key, "name": loc.get("name", key),
                    "lat": loc["lat"], "lng": loc["lng"], "zoom": loc.get("zoom", 10)})


# ═══════════════════════════════════════════════════════════
#  LOGISTICS & SUPPLY CHAIN
# ═══════════════════════════════════════════════════════════
@bp.route("/logistics/status")
@login_required
def api_logistics_status():
    """Per-asset supply snapshot."""
    rows = []
    for aid, a in sim_assets.items():
        sup = a.get("supplies", {})
        if not sup:
            continue
        fuel = sup.get("fuel_pct", 100)
        ammo = sup.get("ammo_rounds", 0)
        water = sup.get("water_hr", 0)
        rations = sup.get("rations_hr", 0)
        status = "GREEN" if fuel > 50 and ammo > 50 else "AMBER" if fuel > 20 and ammo > 10 else "RED"
        rows.append({"asset_id": aid, "callsign": a.get("callsign", aid), "type": a["type"],
                     "domain": a["domain"], "fuel_pct": round(fuel, 1), "ammo_rounds": ammo,
                     "water_hr": round(water, 1), "rations_hr": round(rations, 1), "status": status})
    return jsonify(rows)

@bp.route("/logistics/history")
@login_required
def api_logistics_history():
    """Supply consumption timeline."""
    return jsonify(supply_history)

@bp.route("/logistics/resupply", methods=["POST"])
@login_required
def api_logistics_resupply():
    """Resupply an asset."""
    d = request.json or {}
    aid = d.get("asset_id")
    if aid not in sim_assets:
        return jsonify({"error": "Unknown asset"}), 404
    a = sim_assets[aid]
    sup = a.get("supplies")
    if not sup:
        return jsonify({"error": "Asset has no supply tracking"}), 400
    sup["fuel_pct"] = min(100, sup.get("fuel_pct", 0) + float(d.get("fuel", 0)))
    sup["ammo_rounds"] = min(500, sup.get("ammo_rounds", 0) + int(d.get("ammo", 0)))
    sup["water_hr"] = min(96, sup.get("water_hr", 0) + float(d.get("water", 0)))
    sup["rations_hr"] = min(144, sup.get("rations_hr", 0) + float(d.get("rations", 0)))
    c = ctx()
    cm_log.append({"ts": now_iso(), "user": c["user"], "msg": f"RESUPPLY → {a.get('callsign', aid)}",
                   "fuel": d.get("fuel", 0), "ammo": d.get("ammo", 0)})
    return jsonify({"status": "ok", "asset_id": aid, "supplies": sup})


# ═══════════════════════════════════════════════════════════
#  WEATHER & ENVIRONMENT
# ═══════════════════════════════════════════════════════════
@bp.route("/weather/current")
@login_required
def apiweather_current():
    """Live weather conditions."""
    return jsonify(weather)

@bp.route("/weather/overlay")
@login_required
def apiweather_overlay():
    """Generate Leaflet-compatible weather overlay data."""
    center_lat = AO_CENTER["lat"]
    center_lng = AO_CENTER["lng"]
    points = []
    ws = weather["wind_speed_kt"]
    wd = weather["wind_dir_deg"]
    vis = weather["visibility_km"]
    for i in range(30):
        lat = center_lat + random.uniform(-0.15, 0.15)
        lng = center_lng + random.uniform(-0.15, 0.15)
        local_ws = max(0, ws + random.uniform(-5, 5))
        local_wd = (wd + random.uniform(-20, 20)) % 360
        local_vis = max(0.5, vis + random.uniform(-3, 3))
        points.append({"lat": round(lat, 4), "lng": round(lng, 4),
                       "wind_speed": round(local_ws, 1), "wind_dir": round(local_wd),
                       "visibility": round(local_vis, 1),
                       "precip": weather["precipitation"]})
    return jsonify({"points": points, "timestamp": now_iso()})

@bp.route("/weather/impact")
@login_required
def apiweather_impact():
    """Mission impact scores by domain."""
    ws = weather["wind_speed_kt"]
    vis = weather["visibility_km"]
    ceil = weather["ceiling_ft"]
    ss = weather["sea_state"]
    precip = weather["precipitation"]
    air_wx = min(100, (ws / 60) * 30 + (1 - vis / 30) * 25 + (1 - ceil / 40000) * 25
              + (20 if precip in ["heavy_rain", "snow"] else 5 if precip != "none" else 0))
    gnd_wx = min(100, (ws / 60) * 15 + (1 - vis / 30) * 35
              + (25 if precip in ["heavy_rain", "snow", "dust"] else 10 if precip != "none" else 0))
    sea_wx = min(100, (ss / 9) * 40 + (ws / 60) * 25 + (1 - vis / 30) * 20
              + (15 if precip in ["heavy_rain", "fog"] else 0))
    cyber_wx = min(100, (10 if precip == "heavy_rain" else 0) + random.uniform(0, 5))
    return jsonify({"air": round(air_wx, 1), "ground": round(gnd_wx, 1),
                    "maritime": round(sea_wx, 1), "cyber": round(cyber_wx, 1),
                    "overall": round((air_wx + gnd_wx + sea_wx + cyber_wx) / 4, 1),
                    "recommendation": "HOLD" if max(air_wx, gnd_wx, sea_wx) > 70
                    else "CAUTION" if max(air_wx, gnd_wx, sea_wx) > 40 else "GO",
                    "timestamp": now_iso()})


# ═══════════════════════════════════════════════════════════
#  BATTLE DAMAGE ASSESSMENT (BDA)
# ═══════════════════════════════════════════════════════════
@bp.route("/bda/list")
@login_required
def api_bda_list():
    """All BDA reports."""
    return jsonify(bda_reports)

@bp.route("/bda/report", methods=["POST"])
@login_required
def api_bda_report():
    """Submit a BDA report."""
    d = request.json or {}
    c = ctx()
    rpt = {
        "id": f"BDA-{uuid.uuid4().hex[:8]}",
        "timestamp": now_iso(),
        "reporter": c["user"],
        "target_id": d.get("target_id", "UNK"),
        "target_name": d.get("target_name", "Unknown Target"),
        "lat": float(d.get("lat", 0)),
        "lng": float(d.get("lng", 0)),
        "weapon_used": d.get("weapon_used", "N/A"),
        "munitions_expended": int(d.get("munitions_expended", 1)),
        "damage_level": d.get("damage_level", "moderate"),
        "functional_kill": d.get("functional_kill", False),
        "assessment_conf": d.get("assessment_conf", "medium"),
        "imagery_available": d.get("imagery_available", False),
        "remarks": d.get("remarks", ""),
    }
    bda_reports.append(rpt)
    persist_bda(rpt)
    cm_log.append({"ts": now_iso(), "user": c["user"],
                   "msg": f"BDA REPORT: {rpt['target_name']} — {rpt['damage_level']}"})
    return jsonify({"status": "ok", "report": rpt})

@bp.route("/bda/analytics")
@login_required
def api_bda_analytics():
    """BDA effectiveness analytics."""
    total = len(bda_reports)
    if total == 0:
        return jsonify({"total": 0, "by_damage": {}, "by_weapon": {}, "fk_rate": 0, "conf_dist": {}})
    by_dmg = {}
    by_wpn = {}
    fk_count = 0
    conf_dist = {"high": 0, "medium": 0, "low": 0}
    for r in bda_reports:
        dl = r.get("damage_level", "unknown")
        by_dmg[dl] = by_dmg.get(dl, 0) + 1
        wp = r.get("weapon_used", "N/A")
        by_wpn[wp] = by_wpn.get(wp, 0) + 1
        if r.get("functional_kill"):
            fk_count += 1
        conf_dist[r.get("assessment_conf", "medium")] = conf_dist.get(r.get("assessment_conf", "medium"), 0) + 1
    return jsonify({"total": total, "by_damage": by_dmg, "by_weapon": by_wpn,
                    "fk_rate": round(fk_count / total * 100, 1),
                    "conf_dist": conf_dist})


# ═══════════════════════════════════════════════════════════
#  ELECTRONIC ORDER OF BATTLE (EOB)
# ═══════════════════════════════════════════════════════════
@bp.route("/eob/units")
@login_required
def apieob_units():
    """All tracked EOB units."""
    return jsonify(list(eob_units.values()))

@bp.route("/eob/unit/<uid>")
@login_required
def api_eob_unit(uid):
    """Single EOB unit detail."""
    u = eob_units.get(uid)
    if not u:
        return jsonify({"error": "Unit not found"}), 404
    return jsonify(u)

@bp.route("/eob/unit", methods=["POST"])
@login_required
def api_eob_unit_add():
    """Manually add / update an EOB entry."""
    d = request.json or {}
    uid = d.get("id", f"EOB-{uuid.uuid4().hex[:6]}")
    eob_units[uid] = {
        "id": uid,
        "name": d.get("name", "Unknown Emitter"),
        "type": d.get("type", "unknown"),
        "affiliation": d.get("affiliation", "hostile"),
        "emitter_type": d.get("emitter_type", "radar"),
        "freq_mhz": d.get("freq_mhz", 0),
        "first_seen": d.get("first_seen", now_iso()),
        "last_known": d.get("last_known", {"lat": 0, "lng": 0}),
        "positions": d.get("positions", []),
        "status": d.get("status", "active"),
        "confidence": d.get("confidence", "medium"),
        "notes": d.get("notes", ""),
    }
    return jsonify({"status": "ok", "unit": eob_units[uid]})

@bp.route("/eob/map")
@login_required
def api_eob_map():
    """EOB map layer data (positions + track history)."""
    features = []
    for u in eob_units.values():
        lk = u.get("last_known", {})
        if lk.get("lat"):
            features.append({"id": u["id"], "name": u["name"], "type": u["type"],
                             "affiliation": u["affiliation"], "lat": lk["lat"], "lng": lk["lng"],
                             "status": u["status"], "confidence": u["confidence"],
                             "track_count": len(u.get("positions", []))})
    return jsonify({"features": features, "count": len(features)})


# ═══════════════════════════════════════════════════════════
#  RULES OF ENGAGEMENT (ROE)
# ═══════════════════════════════════════════════════════════
@bp.route("/roe/status")
@login_required
def api_roe_status():
    return jsonify(roe_engine.get_status())

@bp.route("/roe/set", methods=["POST"])
@login_required
def api_roe_set():
    c = ctx()
    if c["role"] != "commander":
        return jsonify({"error": "Commander access required"}), 403
    posture = (request.json or {}).get("posture", "")
    result = roe_engine.set_posture(posture, c["name"])
    if not result:
        return jsonify({"error": "Invalid posture"}), 400
    aar_events.append({"type": "roe_change", "timestamp": now_iso(),
        "elapsed": sim_clock["elapsed_sec"],
        "details": f"ROE changed: {result['old']} → {result['new']} by {c['name']}"})
    return jsonify({"status": "ok", **result})

@bp.route("/roe/rules")
@login_required
def api_roe_rules():
    return jsonify(roe_engine.get_rules())

@bp.route("/roe/rule", methods=["POST"])
@login_required
def api_roe_rule_add():
    d = request.json or {}
    rule = roe_engine.add_rule(
        d.get("name", "Custom Rule"), d.get("type", "custom"),
        d.get("params", {}), d.get("description", ""),
        d.get("severity", "WARNING"))
    return jsonify({"status": "ok", "rule": rule})

@bp.route("/roe/toggle", methods=["POST"])
@login_required
def api_roe_toggle():
    rid = (request.json or {}).get("rule_id", "")
    result = roe_engine.toggle_rule(rid)
    if not result:
        return jsonify({"error": "Rule not found"}), 404
    return jsonify({"status": "ok", "rule": result})

@bp.route("/roe/violations")
@login_required
def api_roe_violations():
    limit = request.args.get("limit", 50, type=int)
    return jsonify(roe_engine.get_violations(limit))


# ═══════════════════════════════════════════════════════════
#  EW API
# ═══════════════════════════════════════════════════════════
@bp.route("/ew/status")
@login_required
def api_ew_status():
    return jsonify({"ew_assets": len(ew_capable), "active_jams": len(ew_active_jams),
                    "ready": len(ew_capable) - len(ew_active_jams),
                    "operations": ew_active_jams, "intercept_count": len(ew_intercepts)})

@bp.route("/ew/jam", methods=["POST"])
@login_required
def api_ew_jam():
    d = request.json
    op = {"id": f"JAM-{uuid.uuid4().hex[:8]}", "jammer_id": d.get("jammer_id", ""),
          "target_freq_mhz": d.get("freq_mhz", 0), "technique": d.get("technique", "barrage"),
          "power_dbm": random.randint(30, 60), "started": now_iso(), "status": "active"}
    ew_active_jams.append(op)
    aar_events.append({"type": "ew_action", "timestamp": op["started"],
        "elapsed": sim_clock["elapsed_sec"],
        "details": f"JAM: {op['jammer_id']} @ {op['target_freq_mhz']} MHz ({op['technique']})"})
    return jsonify({"status": "ok", "operation": op})

@bp.route("/ew/jam/stop", methods=["POST"])
@login_required
def api_ew_stop():
    oid = request.json.get("op_id", "")
    ew_active_jams[:] = [j for j in ew_active_jams if j["id"] != oid]
    return jsonify({"status": "ok"})


# ═══════════════════════════════════════════════════════════
#  SIGINT API
# ═══════════════════════════════════════════════════════════
@bp.route("/sigint")
@login_required
def api_sigint():
    return jsonify(sigint_intercepts[-100:])

@bp.route("/sigint/summary")
@login_required
def api_sigint_summary():
    bc = {}
    for i in sigint_intercepts:
        c = i.get("classification", "UNKNOWN")
        bc[c] = bc.get(c, 0) + 1
    return jsonify({"total_intercepts": len(sigint_intercepts),
                    "unique_emitters": len(sigint_emitter_db), "by_classification": bc})

@bp.route("/sigint/emitters")
@login_required
def api_sigint_emitters():
    return jsonify(sigint_emitter_db)


# ═══════════════════════════════════════════════════════════
#  CYBER API
# ═══════════════════════════════════════════════════════════
@bp.route("/cyber/events")
@login_required
def api_cyber_events():
    return jsonify(cyber_events[-100:])

@bp.route("/cyber/summary")
@login_required
def api_cyber_summary():
    a = sum(1 for e in cyber_events if not e.get("blocked"))
    b = sum(1 for e in cyber_events if e.get("blocked"))
    return jsonify({"total_events": len(cyber_events), "active_threats": a,
                    "blocked": b, "blocked_ips": len(cyber_blocked_ips)})

@bp.route("/cyber/block", methods=["POST"])
@login_required
def api_cyber_block():
    d = request.json
    ip = d.get("ip")
    eid = d.get("event_id")
    if ip:
        cyber_blocked_ips.add(ip)
        for e in cyber_events:
            if e["source_ip"] == ip:
                e["blocked"] = True
    if eid:
        for e in cyber_events:
            if e["id"] == eid:
                e["blocked"] = True
                cyber_blocked_ips.add(e["source_ip"])
    return jsonify({"status": "ok", "blocked_ips": list(cyber_blocked_ips)})


# ═══════════════════════════════════════════════════════════
#  COUNTERMEASURES API
# ═══════════════════════════════════════════════════════════
@bp.route("/cm/engage", methods=["POST"])
@login_required
def api_cm_engage():
    d = request.json
    tid = d.get("threat_id", "")
    ctype = d.get("type", "intercept")
    c = ctx()
    # ROE compliance check
    if tid in sim_threats:
        roe_result = roe_engine.check_engagement(
            sim_threats[tid], sim_assets.get(d.get("asset_id", ""), {}), c["name"], ctype)
        if not roe_result["allowed"]:
            aar_events.append({"type": "roe_violation", "timestamp": now_iso(),
                "elapsed": sim_clock["elapsed_sec"],
                "details": f"ROE BLOCK: {ctype} on {tid} by {c['name']} — {roe_result['violations'][0]['detail']}"})
            return jsonify({"error": "ROE violation", "roe": roe_result}), 403
    if tid in sim_threats:
        sim_threats[tid]["neutralized"] = True
        e = {"id": f"CM-{uuid.uuid4().hex[:8]}", "threat_id": tid, "type": ctype,
             "operator": c["name"], "timestamp": now_iso(), "elapsed": sim_clock["elapsed_sec"]}
        cm_log.append(e)
        persist_engagement(e)
        aar_events.append({"type": "countermeasure", "timestamp": e["timestamp"],
            "elapsed": sim_clock["elapsed_sec"], "details": f"{ctype.upper()} {tid} by {c['name']}"})
        # Auto-generate BDA report for this engagement
        t = sim_threats[tid]
        bda_rpt = {
            "id": f"BDA-{uuid.uuid4().hex[:8]}",
            "timestamp": e["timestamp"],
            "reporter": c["user"],
            "target_id": tid,
            "target_name": t.get("type", "Unknown"),
            "lat": t.get("lat", t.get("position", {}).get("lat", 0)),
            "lng": t.get("lng", t.get("position", {}).get("lng", 0)),
            "weapon_used": ctype,
            "munitions_expended": 1,
            "damage_level": "destroyed" if ctype == "intercept" else "moderate",
            "functional_kill": ctype == "intercept",
            "assessment_conf": "high" if ctype == "intercept" else "medium",
            "imagery_available": False,
            "remarks": f"Auto-BDA: {ctype} engagement on {tid}",
        }
        bda_reports.append(bda_rpt)
        persist_bda(bda_rpt)
        return jsonify({"status": "ok", "result": "neutralized"})
    return jsonify({"error": "Not found"}), 404

@bp.route("/cm/log")
@login_required
def api_cm_log():
    return jsonify(cm_log)


# ═══════════════════════════════════════════════════════════
#  DRONE REFERENCE DATABASE API
# ═══════════════════════════════════════════════════════════
@bp.route("/drone-reference")
@login_required
def api_drone_ref_list():
    """List all drone reference entries, optionally filtered by category."""
    if not drone_ref_db or not drone_ref_db.loaded:
        return jsonify({"error": "Drone reference DB not loaded"}), 503
    cat = request.args.get("category")
    if cat:
        entries = drone_ref_db.get_by_category(cat)
    else:
        entries = drone_ref_db.entries
    return jsonify({"total": len(entries), "entries": entries})

@bp.route("/drone-reference/stats")
@login_required
def api_drone_ref_stats():
    """Return summary statistics for the drone reference DB."""
    if not drone_ref_db or not drone_ref_db.loaded:
        return jsonify({"error": "Drone reference DB not loaded"}), 503
    return jsonify(drone_ref_db.get_stats())

@bp.route("/drone-reference/lookup")
@login_required
def api_drone_ref_lookup():
    """Lookup a drone by serial number or model name."""
    if not drone_ref_db or not drone_ref_db.loaded:
        return jsonify({"error": "Drone reference DB not loaded"}), 503
    serial = request.args.get("serial", "")
    name = request.args.get("name", "")
    result = None
    if serial:
        result = drone_ref_db.lookup_by_serial(serial)
    elif name:
        result = drone_ref_db.lookup_by_name(name)
    if result:
        return jsonify({"matched": True, "entry": result})
    return jsonify({"matched": False, "entry": None})

@bp.route("/drone-reference/search")
@login_required
def api_drone_ref_search():
    """Free-text search across the drone reference database."""
    if not drone_ref_db or not drone_ref_db.loaded:
        return jsonify({"error": "Drone reference DB not loaded"}), 503
    q = request.args.get("q", "")
    limit = request.args.get("limit", 20, type=int)
    results = drone_ref_db.search(q, limit=limit)
    return jsonify({"query": q, "total": len(results), "results": results})

@bp.route("/drone-reference/<model_id>")
@login_required
def api_drone_ref_detail(model_id):
    """Get a single drone reference entry by model ID."""
    if not drone_ref_db or not drone_ref_db.loaded:
        return jsonify({"error": "Drone reference DB not loaded"}), 503
    entry = drone_ref_db.lookup_by_model(model_id)
    if entry:
        return jsonify(entry)
    return jsonify({"error": "Not found"}), 404
