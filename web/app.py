#!/usr/bin/env python3
"""AMOS — Autonomous Mission Operating System v2.0
Multi-Domain Autonomous C2 · Phase 2"""

import os, sys, json, time, random, math, uuid, threading, yaml
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_socketio import SocketIO, emit as sio_emit, join_room, leave_room
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT_DIR)

from mos_core.nodes.waypoint_nav import WaypointNav
from mos_core.nodes.geofence_manager import GeofenceManager
from mos_core.nodes.voice_parser import VoiceParser
from mos_core.nodes.ros2_bridge import ROS2Bridge

# Phase 10
from mos_core.nodes.cognitive_engine import CognitiveEngine
from mos_core.nodes.nlp_mission_parser import NLPMissionParser
from mos_core.nodes.environment_effects import ContestedEnvironment
from mos_core.nodes.task_allocator import TaskAllocator
from mos_core.nodes.red_force_ai import RedForceAI
from mos_core.nodes.sensor_fusion_engine import SensorFusionEngine
from mos_core.nodes.commander_support import CommanderSupport
from mos_core.nodes.learning_engine import LearningEngine

# Phase 3 — Document Generators
from mos_core.docs.opord_generator import generate_opord
from mos_core.docs.conop_generator import generate_conop

# PX4 Bridge (Phase 2)
try:
    sys.path.insert(0, os.path.join(ROOT_DIR, "integrations"))
    from px4_bridge import PX4Bridge
    _px4 = PX4Bridge()
    _px4_ok = _px4.connect()
    if _px4_ok:
        print("[AMOS] PX4 SITL: Connected")
    else:
        print("[AMOS] PX4 SITL: Offline (standalone mode)")
except Exception as e:
    print(f"[AMOS] PX4 SITL: Not available ({e})")
    _px4 = None
    _px4_ok = False

# Phase 4 — TAK Bridge
try:
    from tak_bridge import TAKBridge
    _tak = TAKBridge()
    print("[AMOS] TAK Bridge: Ready (not connected — connect via API)")
except Exception as e:
    print(f"[AMOS] TAK Bridge: Not available ({e})")
    _tak = None

# Phase 4 — Link 16 Tactical Data Link
try:
    from link16_sim import Link16Network
    _link16 = Link16Network(net_id="AMOS-SHADOW-NET")
    # Auto-join all assets
    for _aid in list(sim_assets.keys()) if 'sim_assets' in dir() else []:
        _link16.join(_aid)
    print(f"[AMOS] Link 16: Network initialized")
except Exception as e:
    print(f"[AMOS] Link 16: Not available ({e})")
    _link16 = None

# Database
from db.connection import fetchall, fetchone, execute as db_execute, to_json, from_json, check as db_check


CONFIG_PATH = os.path.join(ROOT_DIR, "config", "platoon_config.yaml")
LOCATIONS_PATH = os.path.join(ROOT_DIR, "config", "locations.json")

def _load_locations():
    """Load saved locations from JSON file."""
    try:
        with open(LOCATIONS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"active": "", "locations": {}}

def _save_locations(data):
    """Persist locations to JSON file."""
    with open(LOCATIONS_PATH, "w") as f:
        json.dump(data, f, indent=2)

app = Flask(__name__,

            template_folder=os.path.join(BASE_DIR, "templates"),


            static_folder=os.path.join(BASE_DIR, "static"))
app.secret_key = os.environ.get("MOS_SECRET", "mos-shadow-forge-2026")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

@app.after_request
def add_no_cache(response):
    """Prevent browser from caching during development"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ═══════════════════════════════════════════════════════════
#  MULTI-USER SYSTEM (DB-backed with fallback)
# ═══════════════════════════════════════════════════════════
_FALLBACK_USERS = {
    "commander": {"password": "mavrix2026", "role": "commander",
                   "name": "CDR Mitchell", "domain": "all",
                   "access": ["c2","twin","ew","sigint","cyber","cm","hal","plan","aar","awacs","field","voice","admin","fusion","cognitive","contested","redforce"]},
    "pilot":     {"password": "wings2026", "role": "pilot",
                   "name": "CPT Torres", "domain": "air",
                   "access": ["c2","twin","ew","sigint","hal","plan","aar","awacs","field","voice","fusion","cognitive","contested"]},
    "grunt":     {"password": "hooah2026", "role": "ground_op",
                   "name": "SGT Reeves", "domain": "ground",
                   "access": ["c2","twin","cm","hal","plan","aar","field","voice","fusion","contested"]},
    "sailor":    {"password": "anchor2026", "role": "maritime_op",
                   "name": "PO1 Chen", "domain": "maritime",
                   "access": ["c2","twin","sigint","hal","aar","field","voice","fusion","contested"]},
    "observer":  {"password": "watch2026", "role": "observer",
                   "name": "Analyst Kim", "domain": "all",
                   "access": ["c2","twin","ew","sigint","cyber","aar","awacs","field","fusion","cognitive","redforce"]},
    "field":     {"password": "tactical2026", "role": "field_op",
                   "name": "SPC Davis", "domain": "all",
                   "access": ["c2","field","voice","cm","contested"]},
}

def _load_users_from_db():
    """Load users from MariaDB. Falls back to hardcoded dict."""
    try:
        if not db_check():
            raise Exception("DB offline")
        rows = fetchall("SELECT * FROM users WHERE active=1")
        if not rows:
            raise Exception("No users in DB")
        users = {}
        for r in rows:
            users[r["username"]] = {
                "password_hash": r["password_hash"],
                "role": r["role"], "name": r["name"],
                "domain": r["domain"], "access": from_json(r["access"])
            }
        print(f"[AMOS] Loaded {len(users)} users from DB")
        return users, True
    except Exception as e:
        print(f"[AMOS] DB user load failed ({e}), using fallback")
        return _FALLBACK_USERS, False

USERS, _DB_AUTH = _load_users_from_db()

# Recording state
_recording = {"active": False, "session_id": None, "frame_seq": 0, "tick_count": 0}

# ── Phase 6: Threat Intel Database (in-memory) ──
_threat_intel = {}  # {threat_type: {count, engagements, neutralized, first_seen, last_seen, positions}}

# ── Phase 7: Rule Engine + Exercise Mode ──
_automation_rules = {}  # {rule_id: {name, trigger_type, trigger_params, action_type, action_params, enabled, fired_count, last_fired}}
_exercise = {"active": False, "name": "", "started_at": None, "injects": [], "score": 0, "max_score": 0,
             "events": [], "completed_injects": 0}
_sitreps = []  # list of generated SITREPs

# Online operator tracking  {socket_sid: {user, name, role, page, cursor, connected_at}}
_online_ops = {}
_asset_locks = {}  # {asset_id: {locked_by, locked_at, expires_at}}
def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return dec

def ctx():
    u = session.get("user", "unknown")
    d = USERS.get(u, {})
    return {"user": u, "role": d.get("role",""), "name": d.get("name",u),
            "domain": d.get("domain","all"), "access": d.get("access",[])}

# ═══════════════════════════════════════════════════════════
#  LOAD CONFIG
# ═══════════════════════════════════════════════════════════
with open(CONFIG_PATH) as f:
    config = yaml.safe_load(f)

platoon = config["platoon"]
base_pos = platoon["base"]

sim_assets = {}
for a in config.get("assets", []):
    sp = a.get("spawn", {})
    is_air = a.get("domain") == "air"
    sim_assets[a["id"]] = {
        "id": a["id"], "type": a.get("type",""), "domain": a.get("domain",""),
        "role": a.get("role",""), "autonomy_tier": a.get("autonomy_tier",1),
        "sensors": a.get("sensors",[]), "weapons": a.get("weapons",[]),
        "endurance_hr": a.get("endurance_hr",0),
        "position": {"lat": sp.get("lat", base_pos["lat"]),
                      "lng": sp.get("lng", base_pos["lng"]),
                      "alt_ft": sp.get("alt_ft", 0)},
        "status": "operational",
        "health": {"battery_pct": random.randint(85,100),
                    "comms_strength": random.randint(75,100),
                    "cpu_temp_c": random.randint(35,55), "gps_fix": True},
        "speed_kts": random.randint(80,200) if is_air else random.randint(5,30),
        "heading_deg": random.randint(0,359),
    }
print(f"[AMOS] Loaded {len(sim_assets)} assets")

sim_threats = {}
for t in config.get("threats", []):
    sim_threats[t["id"]] = {**t, "neutralized": False, "detected_by": [], "first_detected": None}
print(f"[AMOS] Loaded {len(sim_threats)} threats")

# ── Subsystems ──
waypoint_nav = WaypointNav()
geofence_mgr = GeofenceManager()
voice_parser = VoiceParser()
ros2_bridge = ROS2Bridge()

# Phase 10 subsystems
cognitive_engine = CognitiveEngine()
nlp_parser = NLPMissionParser(sim_assets)
contested_env = ContestedEnvironment(base_pos)
task_allocator = TaskAllocator()
red_force_ai = RedForceAI(base_pos["lat"], base_pos["lng"])
sensor_fusion = SensorFusionEngine()
commander_support = CommanderSupport()
learning_engine = LearningEngine()

ew_active_jams, ew_intercepts = [], []
sigint_intercepts, sigint_emitter_db = [], {}
cyber_events, cyber_blocked_ips = [], set()
cm_log, hal_recommendations, aar_events = [], [], []
swarms = {}

sim_clock = {"start_time": time.time(), "elapsed_sec": 0, "speed": 1.0, "running": True}

ao = platoon.get("ao", {})
if ao:
    geofence_mgr.add_geofence("operational",
        [{"lat": ao["north"], "lng": ao["west"]}, {"lat": ao["north"], "lng": ao["east"]},
         {"lat": ao["south"], "lng": ao["east"]}, {"lat": ao["south"], "lng": ao["west"]}],
        "Tehran AO", "AO-PRIMARY")
    geofence_mgr.add_geofence("restricted",
        {"center": {"lat": base_pos["lat"], "lng": base_pos["lng"]}, "radius_nm": 1.5},
        "FOB Tehran Restricted", "RESTRICT-FOB-TEHRAN")

ew_capable = [a for a in sim_assets.values()
              if any(s in (a.get("sensors") or [])
                     for s in ["EW_JAMMER","SIGINT","ELINT","COMINT","AESA_RADAR","AEW_RADAR"])]

print(f"\n[AMOS] ═══════════════════════════════════════")
print(f"[AMOS]  Assets:     {len(sim_assets)}")
print(f"[AMOS]  Threats:    {len(sim_threats)}")
print(f"[AMOS]  EW-capable: {len(ew_capable)}")
print(f"[AMOS]  Geofences:  {len(geofence_mgr.get_all())}")
print(f"[AMOS]  Users:      {len(USERS)}")
print(f"[AMOS]  ROS 2:      {'Connected' if ros2_bridge.available else 'Standalone'}")
print(f"[AMOS]  Phase 10:   cognitive, nlp, contested, tasks,")
print(f"[AMOS]              red_force, fusion, commander, learning")
print(f"[AMOS] ═══════════════════════════════════════\n")

# ═══════════════════════════════════════════════════════════
#  SIMULATION ENGINE
# ═══════════════════════════════════════════════════════════
def now_iso():
    return datetime.now(timezone.utc).isoformat()

def sim_tick():
    print("[AMOS] Simulation engine started")
    last = time.time()
    while sim_clock["running"]:
        time.sleep(0.5)
        now = time.time(); real_dt = now - last; dt = real_dt * sim_clock["speed"]
        sim_clock["elapsed_sec"] += dt; last = now

        # Waypoint navigation
        for evt in waypoint_nav.tick(sim_assets, dt):
            aar_events.append({"type":"waypoint_reached","timestamp":now_iso(),
                "elapsed":sim_clock["elapsed_sec"],
                "details":f"{evt['asset_id']} reached WP {evt['waypoint']['lat']:.4f},{evt['waypoint']['lng']:.4f}"})

        # Asset drift (only if no waypoint)
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

        # Threat movement
        for tid, t in sim_threats.items():
            if t.get("neutralized") or "lat" not in t or "lng" not in t:
                continue
            sf = t.get("speed_kts", 20) * 0.00001 * dt
            t["lat"] = round(t["lat"] + random.uniform(-sf, sf), 6)
            t["lng"] = round(t["lng"] + random.uniform(-sf, sf), 6)

        # Geofence checks
        for alert in geofence_mgr.tick(sim_assets, sim_threats):
            aar_events.append({"type":"geofence_alert","timestamp":now_iso(),
                "elapsed":sim_clock["elapsed_sec"],
                "details":f"GF {alert['event'].upper()}: {alert['entity_id']} — {alert['geofence_name']}"})

        # SIGINT generation
        if random.random() < 0.3 * dt:
            cols = [a for a in sim_assets.values()
                    if any(s in (a.get("sensors") or []) for s in ["SIGINT","ELINT","COMINT","AEW_RADAR"])]
            if cols:
                c = random.choice(cols)
                freq = random.choice([433.0,915.0,1575.42,2437.0,5805.0]) + random.uniform(-5,5)
                ix = {"id":f"INT-{uuid.uuid4().hex[:8]}","timestamp":now_iso(),
                      "collector":c["id"],"freq_mhz":round(freq,2),
                      "power_dbm":random.randint(-80,-20),
                      "modulation":random.choice(["FM","AM","PSK","FSK","OFDM","FHSS","DSSS"]),
                      "bearing_deg":random.randint(0,359),
                      "classification":random.choice(["HOSTILE","HOSTILE","SUSPECT","UNKNOWN","FRIENDLY"]),
                      "duration_ms":random.randint(50,5000)}
                sigint_intercepts.append(ix); ew_intercepts.append(ix)
                fk = f"{round(freq,0)}"
                if fk not in sigint_emitter_db:
                    sigint_emitter_db[fk] = {"freq_mhz":round(freq,2),"count":0,
                                              "first_seen":ix["timestamp"],"last_seen":ix["timestamp"]}
                sigint_emitter_db[fk]["count"] += 1
                sigint_emitter_db[fk]["last_seen"] = ix["timestamp"]

        # Cyber events
        if random.random() < 0.15 * dt:
            sip = random.choice(["10.99.1.50","10.99.2.100","10.99.3.75","192.168.99.1"])
            cyber_events.append({"id":f"CYB-{uuid.uuid4().hex[:8]}","timestamp":now_iso(),
                "type":random.choice(["port_scan","brute_force","dns_exfil","c2_beacon","lateral_move"]),
                "source_ip":sip,"target":random.choice(list(sim_assets.keys())),
                "severity":random.choice(["low","medium","high","critical"]),
                "blocked": sip in cyber_blocked_ips})

        # HAL recommendations
        active_t = [t for t in sim_threats.values() if not t.get("neutralized") and "lat" in t]
        if active_t and random.random() < 0.1 * dt:
            th = random.choice(active_t)
            cap = [a for a in sim_assets.values() if a.get("weapons") or "EW_JAMMER" in (a.get("sensors") or [])]
            if cap:
                a = random.choice(cap)
                hal_recommendations.append({"id":f"HAL-{uuid.uuid4().hex[:8]}","timestamp":now_iso(),
                    "type":random.choice(["ENGAGE","JAM","INTERCEPT","RELOCATE","SURVEIL"]),
                    "asset":a["id"],"target":th["id"],
                    "confidence":round(random.uniform(0.6,0.98),2),
                    "reasoning":f"Threat {th['id']} ({th['type']}) detected — recommend {a['id']}",
                    "status":"pending","tier":a.get("autonomy_tier",2)})

        # ROS2 bridge
        if ros2_bridge.available:
            ros2_bridge.publish_assets(sim_assets)

        # PX4 SITL sync — push real telemetry into sim_assets
        if _px4 and _px4.connected:
            _px4.sync_to_amos(sim_assets)

        # ── Phase 4: TAK + Link 16 sync (every ~5s) ──
        if int(sim_clock["elapsed_sec"]) % 5 < 1:
            if _tak and _tak.connected:
                _tak.send_assets(sim_assets)
                _tak.send_threats(sim_threats)
            if _link16:
                _link16.broadcast_all_assets(sim_assets)

        # ── Phase 10 ticks ──
        cognitive_engine.tick(sim_assets, sim_threats, dt)
        contested_env.tick(sim_assets, sim_threats, dt)
        task_allocator.tick(sim_assets, dt)
        red_events = red_force_ai.tick(sim_assets, sim_threats, ew_active_jams, dt)
        for re in red_events:
            aar_events.append({"type": "red_force", "timestamp": now_iso(),
                "elapsed": sim_clock["elapsed_sec"], "details": str(re)})
        sensor_fusion.tick(sim_assets, sim_threats, dt)
        cmdr_events = commander_support.tick(sim_assets, sim_threats, contested_env, dt)
        for ce in cmdr_events:
            aar_events.append({"type": "contingency", "timestamp": now_iso(),
                "elapsed": sim_clock["elapsed_sec"], "details": str(ce)})
            learning_engine.record_event("CONTINGENCY_TRIGGERED", ce)
        learning_anomalies = learning_engine.tick(sim_assets, sim_threats, dt)

        # ── Recording frame capture (every ~2s) ──
        if _recording["active"]:
            _recording["tick_count"] += 1
            if _recording["tick_count"] % 4 == 0:  # every 4 ticks ≈ 2s
                _recording["frame_seq"] += 1
                try:
                    db_execute(
                        "INSERT INTO recording_frames (session_id,frame_seq,clock_elapsed,asset_state,threat_state) "
                        "VALUES(%s,%s,%s,%s,%s)",
                        (_recording["session_id"], _recording["frame_seq"],
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

        # ── Phase 6: Threat Intel tracking ──
        for tid, t in sim_threats.items():
            ttype = t.get("type", "unknown")
            if ttype not in _threat_intel:
                _threat_intel[ttype] = {"count": 0, "engagements": 0, "neutralized": 0,
                    "first_seen": now_iso(), "last_seen": now_iso(), "positions": []}
            ti = _threat_intel[ttype]
            ti["last_seen"] = now_iso()
            if t.get("neutralized"):
                ti["neutralized"] = max(ti["neutralized"], sum(1 for x in sim_threats.values()
                    if x.get("type") == ttype and x.get("neutralized")))
            if t.get("lat") and len(ti["positions"]) < 50:
                pos = {"lat": round(t["lat"], 4), "lng": round(t.get("lng", 0), 4)}
                if not ti["positions"] or ti["positions"][-1] != pos:
                    ti["positions"].append(pos)
        for ttype in _threat_intel:
            _threat_intel[ttype]["count"] = sum(1 for t in sim_threats.values() if t.get("type") == ttype)
            _threat_intel[ttype]["engagements"] = sum(1 for c in cm_log if
                sim_threats.get(c.get("threat_id", ""), {}).get("type") == ttype)

        # Trim
        for lst in [sigint_intercepts, ew_intercepts, cyber_events]:
            if len(lst) > 1000: del lst[:500]
        if len(aar_events) > 5000: del aar_events[:2500]

        # Emit
        act = sum(1 for t in sim_threats.values() if not t.get("neutralized") and "lat" in t)
        phal = sum(1 for r in hal_recommendations if r.get("status") == "pending")
        risk = commander_support.get_risk()
        red_count = len([u for u in red_force_ai.get_units().values() if u["state"] != "DESTROYED"])
        socketio.emit("sim_update", {
            "clock": {"elapsed_sec": round(sim_clock["elapsed_sec"],1), "speed": sim_clock["speed"]},
            "asset_count": len(sim_assets), "threat_count": act,
            "hostile_tracks": act, "pending_hal": phal,
            "gf_alerts": len(geofence_mgr.get_alerts()),
            "active_waypoints": len(waypoint_nav.routes),
            "risk_level": risk.get("level", "LOW"), "risk_score": risk.get("score", 0),
            "red_force_units": red_count,
            "fused_tracks": len(sensor_fusion.get_tracks()),
            "anomalies": len(learning_anomalies)})

        # ── Phase 7: Rule Engine evaluation ──
        for rid, rule in list(_automation_rules.items()):
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
                low_ct = sum(1 for a in sim_assets.values() if a["health"]["battery_pct"] < tparams.get("threshold", 15))
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
                        "elapsed": sim_clock["elapsed_sec"], "details": f"Rule '{rule['name']}': RTB ALL executed"})
                elif ap == "speed_change":
                    sim_clock["speed"] = aparams.get("speed", 1.0)
                elif ap == "disable_rule":
                    rule["enabled"] = False
                _exercise["events"].append({"type": "rule_fired", "rule": rule["name"],
                    "time": now_iso(), "elapsed": round(sim_clock["elapsed_sec"], 1)})

        # ── Phase 7: Exercise inject processing ──
        if _exercise["active"]:
            for inj in _exercise["injects"]:
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
                            sim_assets[aid]["health"]["battery_pct"] = max(5, sim_assets[aid]["health"]["battery_pct"] - inj.get("amount", 50))
                elif it == "message":
                    socketio.emit("amos_alerts", [{"level": "info",
                        "msg": f"[EXERCISE] {inj.get('message', 'Inject triggered')}",
                        "link": "/automation"}])
                _exercise["completed_injects"] += 1
                _exercise["score"] += inj.get("points", 10)
                aar_events.append({"type": "exercise_inject", "timestamp": now_iso(),
                    "elapsed": sim_clock["elapsed_sec"],
                    "details": f"Exercise inject: {it} — {inj.get('description', '')}"})

        # ── Phase 5: Alert system ──
        alerts = []
        if risk.get("level") in ("HIGH", "CRITICAL"):
            alerts.append({"level": "critical", "msg": f"Risk level {risk['level']} — score {risk.get('score',0)}", "link": "/cognitive"})
        low_batt = [a["id"] for a in sim_assets.values() if a["health"]["battery_pct"] < 15]
        if low_batt:
            alerts.append({"level": "warning", "msg": f"Low battery: {', '.join(low_batt[:3])}", "link": "/dashboard"})
        low_comms = [a["id"] for a in sim_assets.values() if a["health"]["comms_strength"] < 25]
        if low_comms:
            alerts.append({"level": "warning", "msg": f"Comms degraded: {', '.join(low_comms[:3])}", "link": "/integrations"})
        if phal > 5:
            alerts.append({"level": "info", "msg": f"{phal} pending HAL approvals", "link": "/hal"})
        if alerts:
            socketio.emit("amos_alerts", alerts)

# ═══════════════════════════════════════════════════════════
#  AUTH ROUTES
# ═══════════════════════════════════════════════════════════

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u, p = request.form.get("username",""), request.form.get("password","")
        usr = USERS.get(u)
        if usr:
            # DB mode: password_hash; Fallback mode: plaintext password
            ok = False
            if _DB_AUTH and "password_hash" in usr:
                ok = check_password_hash(usr["password_hash"], p)
            elif "password" in usr:
                ok = (usr["password"] == p)
            if ok:
                session["user"] = u
                _audit(u, "login", "user", u)
                return redirect("/field" if usr["role"] == "field_op" else "/")
        return render_template("login.html", error="Invalid credentials", users=USERS)
    return render_template("login.html", error=None, users=USERS)

@app.route("/logout")
def logout():
    session.pop("user", None); return redirect("/login")

# ═══════════════════════════════════════════════════════════
#  PAGE ROUTES
# ═══════════════════════════════════════════════════════════
@app.route("/")
@login_required
def index(): return render_template("index.html", **ctx())

@app.route("/dashboard")
@login_required
def dashboard(): return render_template("dashboard.html", **ctx())

@app.route("/ew")
@login_required
def ew(): return render_template("ew.html", **ctx())

@app.route("/sigint")
@login_required
def sigint(): return render_template("sigint.html", **ctx())

@app.route("/cyber")
@login_required
def cyber(): return render_template("cyber.html", **ctx())

@app.route("/countermeasures")
@login_required
def countermeasures(): return render_template("countermeasures.html", **ctx())

@app.route("/hal")
@login_required
def hal(): return render_template("hal.html", **ctx())

@app.route("/planner")
@login_required
def planner(): return render_template("planner.html", **ctx())

@app.route("/aar")
@login_required
def aar(): return render_template("aar.html", **ctx())

@app.route("/awacs")
@login_required
def awacs(): return render_template("awacs.html", **ctx())

@app.route("/field")
@login_required
def field(): return render_template("field.html", **ctx())

@app.route("/fusion")
@login_required
def fusion(): return render_template("fusion.html", **ctx())

@app.route("/cognitive")
@login_required
def cognitive(): return render_template("cognitive.html", **ctx())

@app.route("/contested")
@login_required
def contested(): return render_template("contested.html", **ctx())

@app.route("/redforce")
@login_required
def redforce(): return render_template("redforce.html", **ctx())

@app.route("/readiness")
@login_required
def readiness(): return render_template("readiness.html", **ctx())

@app.route("/automation")
@login_required
def automation(): return render_template("automation.html", **ctx())

@app.route("/settings")
@login_required
def settings_page(): return render_template("settings.html", **ctx())

@app.route("/tactical")
@login_required
def tactical(): return render_template("tactical.html", **ctx())

@app.route("/docs")
@login_required
def docs_page(): return render_template("docs.html", **ctx())

@app.route("/integrations")
@login_required
def integrations_page(): return render_template("integrations.html", **ctx())

@app.route("/analytics")
@login_required
def analytics_page(): return render_template("analytics.html", **ctx())

# ═══════════════════════════════════════════════════════════
#  SETTINGS API
# ═══════════════════════════════════════════════════════════
@app.route("/api/settings/locations")
@login_required
def api_settings_locations():
    return jsonify(_load_locations())

@app.route("/api/settings/locations/save", methods=["POST"])
@login_required
def api_settings_locations_save():
    d = request.json
    data = _load_locations()
    key = d.get("key", "").strip().lower().replace(" ", "_")
    if not key:
        return jsonify({"error": "Key required"}), 400
    data["locations"][key] = {
        "name": d.get("name", key),
        "lat": float(d.get("lat", 0)),
        "lng": float(d.get("lng", 0)),
        "ao": d.get("ao", {"north": 0, "south": 0, "east": 0, "west": 0}),
        "zoom": int(d.get("zoom", 10)),
        "description": d.get("description", "")
    }
    _save_locations(data)
    return jsonify({"status": "ok", "locations": data})

@app.route("/api/settings/locations/delete", methods=["POST"])
@login_required
def api_settings_locations_delete():
    key = request.json.get("key", "")
    data = _load_locations()
    if key in data["locations"]:
        del data["locations"][key]
        if data["active"] == key:
            data["active"] = next(iter(data["locations"]), "")
        _save_locations(data)
    return jsonify({"status": "ok", "locations": data})

@app.route("/api/settings/locations/activate", methods=["POST"])
@login_required
def api_settings_locations_activate():
    key = request.json.get("key", "")
    data = _load_locations()
    if key not in data["locations"]:
        return jsonify({"error": "Location not found"}), 404
    data["active"] = key
    loc = data["locations"][key]
    # Update in-memory base position
    base_pos["lat"] = loc["lat"]
    base_pos["lng"] = loc["lng"]
    base_pos["name"] = loc["name"]
    _save_locations(data)
    return jsonify({"status": "ok", "active": key, "location": loc,
                    "note": "Map center updated. Full scenario reload requires server restart."})

@app.route("/api/settings/password", methods=["POST"])
@login_required
def api_settings_password():
    d = request.json
    u = session.get("user")
    usr = USERS.get(u)
    if not usr:
        return jsonify({"error": "User not found"}), 404
    if d.get("current") != usr["password"]:
        return jsonify({"error": "Current password incorrect"}), 403
    new_pw = d.get("new", "").strip()
    if len(new_pw) < 4:
        return jsonify({"error": "Password must be at least 4 characters"}), 400
    if _DB_AUTH:
        new_hash = generate_password_hash(new_pw)
        usr["password_hash"] = new_hash
        db_execute("UPDATE users SET password_hash=%s WHERE username=%s", (new_hash, u))
    else:
        usr["password"] = new_pw
    return jsonify({"status": "ok"})

@app.route("/api/settings/profile", methods=["POST"])
@login_required
def api_settings_profile():
    d = request.json
    u = session.get("user")
    usr = USERS.get(u)
    if not usr:
        return jsonify({"error": "User not found"}), 404
    if d.get("name"):
        usr["name"] = d["name"].strip()
        if _DB_AUTH:
            db_execute("UPDATE users SET name=%s WHERE username=%s", (usr["name"], u))
    return jsonify({"status": "ok", "name": usr["name"], "role": usr["role"]})

@app.route("/api/settings/system")
@login_required
def api_settings_system():
    loc_data = _load_locations()
    active_loc = loc_data["locations"].get(loc_data.get("active", ""), {})
    return jsonify({
        "base": base_pos,
        "active_location": loc_data.get("active", ""),
        "location_name": active_loc.get("name", "Unknown"),
        "assets": len(sim_assets),
        "threats": len(sim_threats),
        "users": len(USERS),
        "ew_capable": len(ew_capable),
        "ros2": ros2_bridge.available,
        "sim_speed": sim_clock["speed"],
        "uptime_sec": round(time.time() - sim_clock["start_time"], 1)
    })

# ═══════════════════════════════════════════════════════════
#  SETTINGS – USERS (Admin CRUD)
# ═══════════════════════════════════════════════════════════
@app.route("/api/settings/users")
@login_required
def api_settings_users():
    c = ctx()
    if c["role"] != "commander":
        return jsonify({"error": "Commander access required"}), 403
    result = {}
    for u, info in USERS.items():
        result[u] = {"name": info.get("name", u), "role": info.get("role", ""),
                     "domain": info.get("domain", "all"),
                     "access": info.get("access", [])}
    return jsonify(result)

@app.route("/api/settings/users/create", methods=["POST"])
@login_required
def api_settings_users_create():
    c = ctx()
    if c["role"] != "commander":
        return jsonify({"error": "Commander access required"}), 403
    d = request.json or {}
    username = d.get("username", "").strip().lower()
    if not username or len(username) < 2:
        return jsonify({"error": "Username must be at least 2 characters"}), 400
    if username in USERS:
        return jsonify({"error": f"User '{username}' already exists"}), 409
    password = d.get("password", "").strip()
    if len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters"}), 400
    access = d.get("access", ["c2", "twin", "hal", "aar", "field"])
    pw_hash = generate_password_hash(password)
    USERS[username] = {
        "password_hash": pw_hash, "role": d.get("role", "observer"),
        "name": d.get("name", username).strip(),
        "domain": d.get("domain", "all"), "access": access}
    try:
        db_execute(
            "INSERT INTO users (username, password_hash, role, name, domain, access) VALUES(%s,%s,%s,%s,%s,%s)",
            (username, pw_hash, USERS[username]["role"], USERS[username]["name"],
             USERS[username]["domain"], to_json(access)))
    except Exception as e:
        print(f"[AMOS] DB user create error: {e}")
    return jsonify({"status": "ok", "username": username})

@app.route("/api/settings/users/update", methods=["POST"])
@login_required
def api_settings_users_update():
    c = ctx()
    if c["role"] != "commander":
        return jsonify({"error": "Commander access required"}), 403
    d = request.json or {}
    username = d.get("username", "").strip().lower()
    if username not in USERS:
        return jsonify({"error": "User not found"}), 404
    usr = USERS[username]
    if d.get("name"): usr["name"] = d["name"].strip()
    if d.get("role"): usr["role"] = d["role"]
    if d.get("domain"): usr["domain"] = d["domain"]
    if d.get("access"): usr["access"] = d["access"]
    if d.get("password") and len(d["password"]) >= 4:
        usr["password_hash"] = generate_password_hash(d["password"])
    try:
        db_execute(
            "UPDATE users SET role=%s, name=%s, domain=%s, access=%s WHERE username=%s",
            (usr["role"], usr["name"], usr["domain"], to_json(usr["access"]), username))
        if d.get("password"):
            db_execute("UPDATE users SET password_hash=%s WHERE username=%s",
                       (usr["password_hash"], username))
    except Exception:
        pass
    return jsonify({"status": "ok", "username": username})

@app.route("/api/settings/users/delete", methods=["POST"])
@login_required
def api_settings_users_delete():
    c = ctx()
    if c["role"] != "commander":
        return jsonify({"error": "Commander access required"}), 403
    username = (request.json or {}).get("username", "").strip().lower()
    if username == c["user"]:
        return jsonify({"error": "Cannot delete yourself"}), 400
    if username in USERS:
        del USERS[username]
        try:
            db_execute("UPDATE users SET active=0 WHERE username=%s", (username,))
        except Exception:
            pass
    return jsonify({"status": "ok"})

# ═══════════════════════════════════════════════════════════
#  SCENARIO SAVE/LOAD
# ═══════════════════════════════════════════════════════════
@app.route("/api/scenario/save", methods=["POST"])
@login_required
def api_scenario_save():
    """Export full mission state as JSON."""
    d = request.json or {}
    scenario = {
        "version": "amos-scenario-v1",
        "name": d.get("name", f"Scenario {now_iso()[:16]}"),
        "exported_at": now_iso(),
        "exported_by": ctx()["name"],
        "elapsed_sec": round(sim_clock["elapsed_sec"], 1),
        "platoon": platoon,
        "assets": {aid: {
            "id": a["id"], "type": a["type"], "domain": a["domain"],
            "role": a["role"], "autonomy_tier": a["autonomy_tier"],
            "sensors": a["sensors"], "weapons": a["weapons"],
            "endurance_hr": a.get("endurance_hr", 0),
            "position": a["position"], "status": a["status"],
            "health": a["health"], "speed_kts": a["speed_kts"],
            "heading_deg": a["heading_deg"],
        } for aid, a in sim_assets.items()},
        "threats": {tid: {
            "id": t["id"], "type": t["type"],
            "lat": t.get("lat"), "lng": t.get("lng"),
            "speed_kts": t.get("speed_kts", 0),
            "neutralized": t.get("neutralized", False),
        } for tid, t in sim_threats.items()},
        "waypoints": waypoint_nav.get_all(),
        "geofences": geofence_mgr.get_all(),
        "swarms": swarms,
        "ew_active": ew_active_jams,
        "event_count": len(aar_events),
    }
    return jsonify(scenario)

@app.route("/api/scenario/load", methods=["POST"])
@login_required
def api_scenario_load():
    """Import a scenario JSON to restore mission state."""
    d = request.json or {}
    if d.get("version") != "amos-scenario-v1":
        return jsonify({"error": "Invalid scenario format"}), 400
    loaded = {"assets": 0, "threats": 0}
    # Load assets
    for aid, a in d.get("assets", {}).items():
        sim_assets[aid] = {
            "id": aid, "type": a.get("type", ""), "domain": a.get("domain", ""),
            "role": a.get("role", ""), "autonomy_tier": a.get("autonomy_tier", 2),
            "sensors": a.get("sensors", []), "weapons": a.get("weapons", []),
            "endurance_hr": a.get("endurance_hr", 0),
            "position": a.get("position", {"lat": 0, "lng": 0, "alt_ft": 0}),
            "status": a.get("status", "operational"),
            "health": a.get("health", {"battery_pct": 100, "comms_strength": 100,
                                       "cpu_temp_c": 40, "gps_fix": True}),
            "speed_kts": a.get("speed_kts", 0), "heading_deg": a.get("heading_deg", 0),
        }
        loaded["assets"] += 1
    # Load threats
    for tid, t in d.get("threats", {}).items():
        sim_threats[tid] = {
            "id": tid, "type": t.get("type", ""),
            "lat": t.get("lat"), "lng": t.get("lng"),
            "speed_kts": t.get("speed_kts", 0),
            "neutralized": t.get("neutralized", False),
            "detected_by": [], "first_detected": None,
        }
        loaded["threats"] += 1
    aar_events.append({"type": "scenario_loaded", "timestamp": now_iso(),
        "elapsed": sim_clock["elapsed_sec"],
        "details": f"Scenario '{d.get('name','')}' loaded: {loaded['assets']} assets, {loaded['threats']} threats"})
    return jsonify({"status": "ok", "loaded": loaded, "name": d.get("name", "")})

# ═══════════════════════════════════════════════════════════
#  SETTINGS – ASSETS (Fleet CRUD)
# ═══════════════════════════════════════════════════════════
@app.route("/api/settings/assets")
@login_required
def api_settings_assets():
    """Return full sim_assets dict for fleet management."""
    return jsonify(sim_assets)

@app.route("/api/settings/assets/save", methods=["POST"])
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
    # Write-through to DB
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

@app.route("/api/settings/assets/delete", methods=["POST"])
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
@app.route("/api/assets")
@login_required
def api_assets():
    c = ctx()
    if c["domain"] == "all":
        return jsonify(sim_assets)
    return jsonify({k:v for k,v in sim_assets.items() if v["domain"]==c["domain"]})

@app.route("/api/assets/summary")
@login_required
def api_assets_summary():
    bd, bs, br = {}, {}, {}
    for a in sim_assets.values():
        bd[a["domain"]] = bd.get(a["domain"],0)+1
        bs[a["status"]] = bs.get(a["status"],0)+1
        br[a["role"]] = br.get(a["role"],0)+1
    return jsonify({"total":len(sim_assets),"by_domain":bd,"by_status":bs,"by_role":br})

@app.route("/api/assets/<asset_id>")
@login_required
def api_asset_detail(asset_id):
    a = sim_assets.get(asset_id)
    if not a: return jsonify({"error":"Not found"}),404
    r = dict(a); r["waypoints"] = waypoint_nav.get_waypoints(asset_id)
    return jsonify(r)

# ═══════════════════════════════════════════════════════════
#  THREAT API
# ═══════════════════════════════════════════════════════════
@app.route("/api/threats")
@login_required
def api_threats(): return jsonify(sim_threats)

# ═══════════════════════════════════════════════════════════
#  EW API
# ═══════════════════════════════════════════════════════════
@app.route("/api/ew/status")
@login_required
def api_ew_status():
    return jsonify({"ew_assets":len(ew_capable),"active_jams":len(ew_active_jams),
                    "ready":len(ew_capable)-len(ew_active_jams),
                    "operations":ew_active_jams,"intercept_count":len(ew_intercepts)})

@app.route("/api/ew/jam", methods=["POST"])
@login_required
def api_ew_jam():
    d = request.json
    op = {"id":f"JAM-{uuid.uuid4().hex[:8]}","jammer_id":d.get("jammer_id",""),
          "target_freq_mhz":d.get("freq_mhz",0),"technique":d.get("technique","barrage"),
          "power_dbm":random.randint(30,60),"started":now_iso(),"status":"active"}
    ew_active_jams.append(op)
    aar_events.append({"type":"ew_action","timestamp":op["started"],
        "elapsed":sim_clock["elapsed_sec"],
        "details":f"JAM: {op['jammer_id']} @ {op['target_freq_mhz']} MHz ({op['technique']})"})
    return jsonify({"status":"ok","operation":op})

@app.route("/api/ew/jam/stop", methods=["POST"])
@login_required
def api_ew_stop():
    oid = request.json.get("op_id","")
    ew_active_jams[:] = [j for j in ew_active_jams if j["id"] != oid]
    return jsonify({"status":"ok"})

# ═══════════════════════════════════════════════════════════
#  SIGINT API
# ═══════════════════════════════════════════════════════════
@app.route("/api/sigint")
@login_required
def api_sigint(): return jsonify(sigint_intercepts[-100:])

@app.route("/api/sigint/summary")
@login_required
def api_sigint_summary():
    bc = {}
    for i in sigint_intercepts:
        c = i.get("classification","UNKNOWN"); bc[c] = bc.get(c,0)+1
    return jsonify({"total_intercepts":len(sigint_intercepts),
                    "unique_emitters":len(sigint_emitter_db),"by_classification":bc})

@app.route("/api/sigint/emitters")
@login_required
def api_sigint_emitters(): return jsonify(sigint_emitter_db)

# ═══════════════════════════════════════════════════════════
#  CYBER API
# ═══════════════════════════════════════════════════════════
@app.route("/api/cyber/events")
@login_required
def api_cyber_events(): return jsonify(cyber_events[-100:])

@app.route("/api/cyber/summary")
@login_required
def api_cyber_summary():
    a = sum(1 for e in cyber_events if not e.get("blocked"))
    b = sum(1 for e in cyber_events if e.get("blocked"))
    return jsonify({"total_events":len(cyber_events),"active_threats":a,
                    "blocked":b,"blocked_ips":len(cyber_blocked_ips)})

@app.route("/api/cyber/block", methods=["POST"])
@login_required
def api_cyber_block():
    d = request.json
    ip = d.get("ip"); eid = d.get("event_id")
    if ip:
        cyber_blocked_ips.add(ip)
        for e in cyber_events:
            if e["source_ip"]==ip: e["blocked"]=True
    if eid:
        for e in cyber_events:
            if e["id"]==eid: e["blocked"]=True; cyber_blocked_ips.add(e["source_ip"])
    return jsonify({"status":"ok","blocked_ips":list(cyber_blocked_ips)})

# ═══════════════════════════════════════════════════════════
#  COUNTERMEASURES API
# ═══════════════════════════════════════════════════════════
@app.route("/api/cm/engage", methods=["POST"])
@login_required
def api_cm_engage():
    d = request.json; tid = d.get("threat_id",""); ctype = d.get("type","intercept"); c = ctx()
    if tid in sim_threats:
        sim_threats[tid]["neutralized"] = True
        e = {"id":f"CM-{uuid.uuid4().hex[:8]}","threat_id":tid,"type":ctype,
             "operator":c["name"],"timestamp":now_iso(),"elapsed":sim_clock["elapsed_sec"]}
        cm_log.append(e)
        aar_events.append({"type":"countermeasure","timestamp":e["timestamp"],
            "elapsed":sim_clock["elapsed_sec"],"details":f"{ctype.upper()} {tid} by {c['name']}"})
        return jsonify({"status":"ok","result":"neutralized"})
    return jsonify({"error":"Not found"}),404

@app.route("/api/cm/log")
@login_required
def api_cm_log(): return jsonify(cm_log)

# ═══════════════════════════════════════════════════════════
#  HAL API
# ═══════════════════════════════════════════════════════════
@app.route("/api/hal/recommendations")
@login_required
def api_hal_recs():
    # Merge random HAL recs with cognitive engine recommendations
    cog_recs = cognitive_engine.get_recommendations(30)
    merged = []
    for r in cog_recs:
        merged.append({
            "id": r["id"], "type": r["coa"]["coa_name"] if r.get("coa") else "UNKNOWN",
            "asset": ", ".join(r.get("recommended_assets", [])[:3]),
            "target": r.get("threat_id", ""),
            "confidence": r["coa"]["p_success"] if r.get("coa") else 0.5,
            "reasoning": " → ".join(r.get("reasoning_chain", [])),
            "status": r.get("status", "pending"),
            "tier": 2, "timestamp": r.get("timestamp", ""),
            "risk": r["coa"].get("risk", "MEDIUM") if r.get("coa") else "MEDIUM",
            "score": r["coa"].get("composite_score", 0) if r.get("coa") else 0,
            "all_coas": r.get("all_coas", []),
        })
    # Include legacy random recs too
    for r in hal_recommendations[-20:]:
        merged.append(r)
    return jsonify(merged)

@app.route("/api/hal/action", methods=["POST"])
@login_required
def api_hal_action():
    d = request.json; rid = d.get("id",""); act = d.get("action",""); c = ctx()
    # Try cognitive engine first
    result = cognitive_engine.action_recommendation(rid, act, c["name"])
    if result:
        if act == "approve":
            aar_events.append({"type":"coa_approved","timestamp":now_iso(),
                "elapsed":sim_clock["elapsed_sec"],
                "details":f"COA {result['coa']['coa_name']}: threat {result['threat_id']} by {c['name']}"})
            try:
                db_execute("INSERT INTO mission_events (mission_id, event_type, details) VALUES(1,%s,%s)",
                    ("coa_approved", to_json({"rec_id": rid, "coa": result["coa"]["coa_name"],
                     "threat": result["threat_id"], "operator": c["name"]})))
            except Exception:
                pass
        return jsonify({"status":"ok", "source": "cognitive"})
    # Fallback to legacy HAL
    for r in hal_recommendations:
        if r["id"]==rid:
            r["status"]=act; r["actioned_by"]=c["name"]; r["actioned_at"]=now_iso()
            if act=="approve":
                aar_events.append({"type":"hal_approved","timestamp":r["actioned_at"],
                    "elapsed":sim_clock["elapsed_sec"],
                    "details":f"HAL {r['type']}: {r['asset']}->{r['target']} by {c['name']}"})
            break
    return jsonify({"status":"ok"})

@app.route("/api/coa/generate", methods=["POST"])
@login_required
def api_coa():
    """Return real COA analysis from the cognitive engine."""
    all_coas = cognitive_engine.get_coas()
    results = []
    for tid, coas in all_coas.items():
        for c in coas[:3]:  # top 3 per threat
            results.append({
                "rank": c.get("rank", 0), "name": c["coa_name"],
                "score": c["composite_score"], "risk": c["risk"],
                "description": c["description"],
                "p_success": c["p_success"], "p_friendly_loss": c["p_friendly_loss"],
                "avg_time_min": c["avg_time_min"], "threat_id": tid
            })
    results.sort(key=lambda x: x["score"], reverse=True)
    return jsonify(results[:12])

@app.route("/api/coa/current")
@login_required
def api_coa_current():
    """All active COA recommendations from the cognitive engine."""
    recs = cognitive_engine.get_recommendations(20)
    pending = [r for r in recs if r.get("status") == "pending"]
    return jsonify(pending)

@app.route("/api/coa/history")
@login_required
def api_coa_history():
    """Past COA decisions (approved/rejected)."""
    recs = cognitive_engine.get_recommendations(100)
    actioned = [r for r in recs if r.get("status") in ("approve", "reject", "approved", "rejected")]
    return jsonify(actioned)

# ═══════════════════════════════════════════════════════════
#  DOCUMENT GENERATION API (Phase 3)
# ═══════════════════════════════════════════════════════════
@app.route("/api/docs/opord", methods=["POST"])
@login_required
def api_docs_opord():
    """Generate a 5-paragraph OPORD from current mission state."""
    d = request.json or {}
    coa_data = cognitive_engine.get_coas()
    opord = generate_opord(
        platoon_config=platoon, assets=sim_assets, threats=sim_threats,
        coa_data=coa_data, mission_name=d.get("mission_name"),
        classification=d.get("classification", "UNCLASSIFIED"))
    return jsonify(opord)

@app.route("/api/docs/conop", methods=["POST"])
@login_required
def api_docs_conop():
    """Generate a CONOP summary from current mission state."""
    d = request.json or {}
    coa_data = cognitive_engine.get_coas()
    conop = generate_conop(
        platoon_config=platoon, assets=sim_assets, threats=sim_threats,
        coa_data=coa_data, aar_events=aar_events,
        classification=d.get("classification", "UNCLASSIFIED"))
    return jsonify(conop)

@app.route("/api/docs/briefing", methods=["POST"])
@login_required
def api_docs_briefing():
    """Quick mission briefing — combines key data from OPORD + CONOP."""
    coa_data = cognitive_engine.get_coas()
    at = sum(1 for t in sim_threats.values() if not t.get("neutralized"))
    nt = sum(1 for t in sim_threats.values() if t.get("neutralized"))
    risk = commander_support.get_risk()
    # Top COAs
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

# ═══════════════════════════════════════════════════════════
#  SWARM API
# ═══════════════════════════════════════════════════════════
@app.route("/api/swarm")
@login_required
def api_swarm(): return jsonify(swarms)

@app.route("/api/swarm/create", methods=["POST"])
@login_required
def api_swarm_create():
    d = request.json; sid = d.get("swarm_id","")
    swarms[sid] = {"id":sid,"assets":d.get("assets",[]),"formation":d.get("formation","line"),
                   "created":now_iso(),"status":"active"}
    aar_events.append({"type":"swarm_created","timestamp":swarms[sid]["created"],
        "elapsed":sim_clock["elapsed_sec"],
        "details":f"Swarm {sid}: {len(swarms[sid]['assets'])} assets, {swarms[sid]['formation']}"})
    return jsonify({"status":"ok","swarm":swarms[sid]})

# ═══════════════════════════════════════════════════════════
#  AAR API
# ═══════════════════════════════════════════════════════════
@app.route("/api/aar/events")
@login_required
def api_aar_events(): return jsonify(aar_events[-200:])

@app.route("/api/aar/export")
@login_required
def api_aar_export():
    return jsonify({"mission":platoon["name"],"callsign":platoon["callsign"],
        "export_time":now_iso(),"duration_sec":sim_clock["elapsed_sec"],
        "assets":{k:{"id":v["id"],"type":v["type"],"domain":v["domain"],"status":v["status"]} for k,v in sim_assets.items()},
        "threats":{k:{"id":v["id"],"type":v["type"],"neutralized":v.get("neutralized",False)} for k,v in sim_threats.items()},
        "events":aar_events,"countermeasures":cm_log,"swarms":swarms,
        "sigint_count":len(sigint_intercepts),"cyber_count":len(cyber_events)})

# ═══════════════════════════════════════════════════════════
#  WAYPOINT API
# ═══════════════════════════════════════════════════════════
@app.route("/api/waypoints")
@login_required
def api_wp_all(): return jsonify(waypoint_nav.get_all())

@app.route("/api/waypoints/<asset_id>")
@login_required
def api_wp_asset(asset_id): return jsonify(waypoint_nav.get_waypoints(asset_id))

@app.route("/api/waypoints/set", methods=["POST"])
@login_required
def api_wp_set():
    d = request.json; aid = d.get("asset_id"); lat = d.get("lat"); lng = d.get("lng")
    if not aid or lat is None or lng is None: return jsonify({"error":"Missing fields"}),400
    if aid not in sim_assets: return jsonify({"error":"Asset not found"}),404
    waypoint_nav.set_waypoint(aid, lat, lng, d.get("alt_ft"))
    c = ctx()
    aar_events.append({"type":"waypoint_set","timestamp":now_iso(),
        "elapsed":sim_clock["elapsed_sec"],
        "details":f"WP set: {aid} -> {lat:.4f},{lng:.4f} by {c['name']}"})
    return jsonify({"status":"ok","waypoints":waypoint_nav.get_waypoints(aid)})

@app.route("/api/waypoints/add", methods=["POST"])
@login_required
def api_wp_add():
    d = request.json; aid = d.get("asset_id"); lat = d.get("lat"); lng = d.get("lng")
    if not aid or lat is None or lng is None: return jsonify({"error":"Missing fields"}),400
    if aid not in sim_assets: return jsonify({"error":"Asset not found"}),404
    waypoint_nav.add_waypoint(aid, lat, lng, d.get("alt_ft"))
    return jsonify({"status":"ok","waypoints":waypoint_nav.get_waypoints(aid)})

@app.route("/api/waypoints/clear", methods=["POST"])
@login_required
def api_wp_clear():
    d = request.json; aid = d.get("asset_id")
    if aid: waypoint_nav.clear_waypoints(aid)
    else: waypoint_nav.clear_all()
    return jsonify({"status":"ok"})

# ═══════════════════════════════════════════════════════════
#  GEOFENCE API
# ═══════════════════════════════════════════════════════════
@app.route("/api/geofences")
@login_required
def api_gf(): return jsonify(geofence_mgr.get_all())

@app.route("/api/geofences/create", methods=["POST"])
@login_required
def api_gf_create():
    d = request.json
    gid = geofence_mgr.add_geofence(d.get("type","alert"), d.get("points",[]),
                                     d.get("name",""), d.get("id"))
    return jsonify({"status":"ok","id":gid})

@app.route("/api/geofences/delete", methods=["POST"])
@login_required
def api_gf_del():
    geofence_mgr.remove_geofence(request.json.get("id","")); return jsonify({"status":"ok"})

@app.route("/api/geofences/alerts")
@login_required
def api_gf_alerts(): return jsonify(geofence_mgr.get_alerts())

# ═══════════════════════════════════════════════════════════
#  VOICE COMMAND API
# ═══════════════════════════════════════════════════════════
@app.route("/api/voice/command", methods=["POST"])
@login_required
def api_voice():
    transcript = request.json.get("transcript",""); c = ctx()
    parsed = voice_parser.parse(transcript)
    result = {"parsed":parsed,"executed":False,"response":""}
    cmd = parsed.get("command")

    if cmd == "move" and "lat" in parsed and "lng" in parsed:
        aid = parsed["asset_id"]
        if aid in sim_assets:
            waypoint_nav.set_waypoint(aid, parsed["lat"], parsed["lng"])
            result.update(executed=True, response=f"Roger. {aid} navigating to {parsed['lat']:.4f}, {parsed['lng']:.4f}")
    elif cmd == "engage":
        tid = parsed.get("threat_id","")
        if tid in sim_threats and not sim_threats[tid].get("neutralized"):
            sim_threats[tid]["neutralized"] = True
            cm_log.append({"id":f"CM-{uuid.uuid4().hex[:8]}","threat_id":tid,"type":"voice_engage",
                "operator":c["name"],"timestamp":now_iso(),"elapsed":sim_clock["elapsed_sec"]})
            result.update(executed=True, response=f"Roger. {tid} engaged and neutralized.")
    elif cmd == "jam":
        freq = parsed.get("freq_mhz",0)
        jammers = [a for a in sim_assets.values() if "EW_JAMMER" in (a.get("sensors") or [])]
        if jammers:
            j = jammers[0]
            ew_active_jams.append({"id":f"JAM-{uuid.uuid4().hex[:8]}","jammer_id":j["id"],
                "target_freq_mhz":freq,"technique":"barrage","power_dbm":45,
                "started":now_iso(),"status":"active"})
            result.update(executed=True, response=f"Roger. {j['id']} jamming {freq} MHz.")
    elif cmd == "status":
        aid = parsed.get("asset_id","")
        if aid in sim_assets:
            a = sim_assets[aid]
            result.update(executed=True,
                response=f"{aid}: {a['status']}, batt {a['health']['battery_pct']:.0f}%, comms {a['health']['comms_strength']:.0f}%, pos {a['position']['lat']:.4f} {a['position']['lng']:.4f}")
    elif cmd == "status_all":
        at = sum(1 for t in sim_threats.values() if not t.get("neutralized"))
        result.update(executed=True, response=f"Platoon: {len(sim_assets)} assets operational. {at} active threats. {len(ew_active_jams)} active jams.")
    elif cmd == "set_speed":
        sim_clock["speed"] = parsed.get("speed",1.0)
        result.update(executed=True, response=f"Roger. Speed set to {sim_clock['speed']}x.")
    elif cmd == "generate_coa":
        result.update(executed=True, response="Roger. COAs generated. Check HAL panel.")
    elif cmd == "block_ip":
        ip = parsed.get("ip","")
        cyber_blocked_ips.add(ip)
        for e in cyber_events:
            if e["source_ip"]==ip: e["blocked"]=True
        result.update(executed=True, response=f"Roger. Blocked {ip}.")
    elif cmd == "halt":
        aid = parsed.get("asset_id",""); waypoint_nav.clear_waypoints(aid)
        result.update(executed=True, response=f"Roger. {aid} halted.")
    elif cmd == "halt_all":
        waypoint_nav.clear_all(); result.update(executed=True, response="Roger. All assets halted.")
    elif cmd == "rtb":
        aid = parsed.get("asset_id","")
        if aid in sim_assets:
            waypoint_nav.set_waypoint(aid, base_pos["lat"], base_pos["lng"])
            result.update(executed=True, response=f"Roger. {aid} RTB.")
    elif cmd == "rtb_all":
        for aid in sim_assets: waypoint_nav.set_waypoint(aid, base_pos["lat"], base_pos["lng"])
        result.update(executed=True, response="Roger. All assets RTB.")
    else:
        result["response"] = f"Command not recognized: '{transcript}'"

    if result["executed"]:
        aar_events.append({"type":"voice_command","timestamp":now_iso(),
            "elapsed":sim_clock["elapsed_sec"],
            "details":f"VOICE [{c['name']}]: {transcript} -> {result['response']}"})
    return jsonify(result)

# ═══════════════════════════════════════════════════════════
#  COGNITIVE ENGINE API
# ═══════════════════════════════════════════════════════════
@app.route("/api/cognitive/ooda")
@login_required
def api_cognitive_ooda():
    return jsonify(cognitive_engine.get_loops())

@app.route("/api/cognitive/coa")
@login_required
def api_cognitive_coa():
    return jsonify(cognitive_engine.get_coas())

@app.route("/api/cognitive/reasoning")
@login_required
def api_cognitive_reasoning():
    return jsonify(cognitive_engine.get_recommendations())

# ═══════════════════════════════════════════════════════════
#  NLP MISSION PARSER API
# ═══════════════════════════════════════════════════════════
@app.route("/api/nlp/parse", methods=["POST"])
@login_required
def api_nlp_parse():
    text = request.json.get("text", "")
    result = nlp_parser.parse(text)
    return jsonify(result)

@app.route("/api/nlp/execute", methods=["POST"])
@login_required
def api_nlp_execute():
    text = request.json.get("text", "")
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
#  CONTESTED ENVIRONMENT API
# ═══════════════════════════════════════════════════════════
@app.route("/api/contested/status")
@login_required
def api_contested_status():
    return jsonify(contested_env.get_status())

@app.route("/api/contested/gps-denial/add", methods=["POST"])
@login_required
def api_contested_gps_add():
    d = request.json
    contested_env.add_gps_denial_zone(
        d.get("lat", 0), d.get("lng", 0),
        d.get("radius_nm", 5), d.get("js_ratio_db", 20))
    return jsonify({"status": "ok", "zones": len(contested_env.gps_denial_zones)})

@app.route("/api/contested/gps-denial/remove", methods=["POST"])
@login_required
def api_contested_gps_remove():
    zid = request.json.get("zone_id", "")
    contested_env.gps_denial_zones = [
        z for z in contested_env.gps_denial_zones if z.get("id") != zid]
    return jsonify({"status": "ok"})

@app.route("/api/contested/mesh")
@login_required
def api_contested_mesh():
    return jsonify(contested_env.get_mesh())

# ═══════════════════════════════════════════════════════════
#  TASK ALLOCATOR API
# ═══════════════════════════════════════════════════════════
@app.route("/api/tasks")
@login_required
def api_tasks():
    return jsonify(task_allocator.get_tasks())

@app.route("/api/tasks/gantt")
@login_required
def api_tasks_gantt():
    return jsonify(task_allocator.get_gantt())

@app.route("/api/tasks/assign", methods=["POST"])
@login_required
def api_tasks_assign():
    d = request.json
    task_allocator.create_task(
        d.get("task_type", "patrol"), priority=d.get("priority", 5),
        location=d.get("location", {}), required_sensors=d.get("required_capabilities", []))
    return jsonify({"status": "ok", "tasks": len(task_allocator.tasks)})

# ═══════════════════════════════════════════════════════════
#  RED FORCE API
# ═══════════════════════════════════════════════════════════
@app.route("/api/redforce/status")
@login_required
def api_redforce_status():
    return jsonify(red_force_ai.get_stats())

@app.route("/api/redforce/units")
@login_required
def api_redforce_units():
    return jsonify(red_force_ai.get_units())

@app.route("/api/redforce/spawn", methods=["POST"])
@login_required
def api_redforce_spawn():
    d = request.json
    uid = f"RED-SPAWN-{len(red_force_ai.units)+1:02d}"
    from mos_core.nodes.red_force_ai import RedUnit
    lat = d.get("lat", base_pos["lat"] + 0.05)
    lng = d.get("lng", base_pos["lng"] + 0.05)
    utype = d.get("unit_type", "drone")
    unit = RedUnit(uid, lat, lng, utype)
    unit.state = "PROBING"
    red_force_ai.units[uid] = unit
    red_force_ai.stats["units_spawned"] += 1
    return jsonify({"status": "ok", "unit": unit.to_dict()})

# ═══════════════════════════════════════════════════════════
#  SENSOR FUSION API
# ═══════════════════════════════════════════════════════════
@app.route("/api/fusion/tracks")
@login_required
def api_fusion_tracks():
    return jsonify(sensor_fusion.get_tracks())

@app.route("/api/fusion/coverage")
@login_required
def api_fusion_coverage():
    return jsonify(sensor_fusion.get_coverage())

@app.route("/api/fusion/killchain")
@login_required
def api_fusion_killchain():
    return jsonify(sensor_fusion.get_kill_chain_summary())

@app.route("/api/fusion/gaps")
@login_required
def api_fusion_gaps():
    return jsonify(sensor_fusion.get_coverage_gaps())

# ═══════════════════════════════════════════════════════════
#  COMMANDER SUPPORT API
# ═══════════════════════════════════════════════════════════
@app.route("/api/commander/risk")
@login_required
def api_commander_risk():
    return jsonify(commander_support.get_risk())

@app.route("/api/commander/risk/trend")
@login_required
def api_commander_risk_trend():
    return jsonify(commander_support.get_risk_trend())

@app.route("/api/commander/resources")
@login_required
def api_commander_resources():
    mins = request.args.get("minutes", 60, type=int)
    return jsonify(commander_support.get_resources(sim_assets, mins))

@app.route("/api/commander/contingencies")
@login_required
def api_commander_contingencies():
    return jsonify(commander_support.get_contingency_plans())

@app.route("/api/commander/triggered")
@login_required
def api_commander_triggered():
    return jsonify(commander_support.get_triggered_plans())

@app.route("/api/commander/contingency/add", methods=["POST"])
@login_required
def api_commander_contingency_add():
    d = request.json
    plan = commander_support.add_contingency(
        d.get("name", ""), d.get("trigger_type", ""),
        d.get("trigger_params", {}), d.get("actions", []),
        d.get("priority", 5))
    return jsonify({"status": "ok", "plan": plan})

@app.route("/api/commander/contingency/cancel", methods=["POST"])
@login_required
def api_commander_contingency_cancel():
    pid = request.json.get("plan_id", "")
    ok = commander_support.cancel_contingency(pid)
    return jsonify({"status": "ok" if ok else "not_found"})

# ═══════════════════════════════════════════════════════════
#  LEARNING ENGINE API
# ═══════════════════════════════════════════════════════════
@app.route("/api/learning/anomalies")
@login_required
def api_learning_anomalies():
    return jsonify(learning_engine.get_anomalies())

@app.route("/api/learning/engagements")
@login_required
def api_learning_engagements():
    return jsonify(learning_engine.get_recent_engagements())

@app.route("/api/learning/engagement-stats")
@login_required
def api_learning_engagement_stats():
    return jsonify(learning_engine.get_engagement_stats())

@app.route("/api/learning/swarm-params")
@login_required
def api_learning_swarm_params():
    return jsonify(learning_engine.get_swarm_params())

@app.route("/api/learning/swarm/tune", methods=["POST"])
@login_required
def api_learning_swarm_tune():
    d = request.json
    params = learning_engine.tune_swarm(
        d.get("metric", ""), d.get("score", 0.5), d.get("weight", 1.0))
    return jsonify({"status": "ok", "params": params})

@app.route("/api/learning/aar")
@login_required
def api_learning_aar():
    return jsonify(learning_engine.generate_aar())

@app.route("/api/learning/events")
@login_required
def api_learning_events():
    etype = request.args.get("type", None)
    limit = request.args.get("limit", 100, type=int)
    return jsonify(learning_engine.get_events(event_type=etype, limit=limit))

# ═══════════════════════════════════════════════════════════
#  ROS2 / USER / SIM APIs
# ═══════════════════════════════════════════════════════════
@app.route("/api/ros2/status")
@login_required
def api_ros2(): return jsonify(ros2_bridge.get_status())

@app.route("/api/user/role")
@login_required
def api_role(): return jsonify(ctx())

@app.route("/api/users")
@login_required
def api_users():
    c = ctx()
    if c["role"] != "commander": return jsonify({"error":"Denied"}),403
    return jsonify({k:{"name":v["name"],"role":v["role"],"domain":v["domain"]} for k,v in USERS.items()})

@app.route("/api/sim/speed", methods=["POST"])
@login_required
def api_speed():
    sim_clock["speed"] = max(0.1, min(20, request.json.get("speed",1.0)))
    return jsonify({"status":"ok","speed":sim_clock["speed"]})

@app.route("/api/sim/status")
@login_required
def api_sim(): return jsonify(sim_clock)

# ═══════════════════════════════════════════════════════════
#  LAUNCH
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# AMOS Phase 3 — Live State Binding (clean insert)
# ═══════════════════════════════════════════════════════════
try:
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
    from phase3_routes import phase3_bp, init_phase3

    def _amos_state_getter():
        g = globals()
        state = {}
        for aname in ['assets', 'ASSETS', 'asset_registry', 'platoon_assets', 'sim_assets']:
            if aname in g and g[aname]:
                state['assets'] = g[aname]; break
        for tname in ['threats', 'THREATS', 'sim_threats', 'threat_list']:
            if tname in g and g[tname]:
                state['threats'] = g[tname]; break
        for ename in ['events', 'EVENTS', 'sim_events', 'event_log']:
            if ename in g and g[ename]:
                state['events'] = g[ename]; break
        if 'sim' in g and hasattr(g.get('sim'), 'assets'):
            state.setdefault('assets', getattr(g['sim'], 'assets', {}))
        if 'sim' in g and hasattr(g.get('sim'), 'threats'):
            state.setdefault('threats', getattr(g['sim'], 'threats', []))
        if 'sim' in g and hasattr(g.get('sim'), 'events'):
            state.setdefault('events', getattr(g['sim'], 'events', []))
        return state

    init_phase3(_amos_state_getter)
    app.register_blueprint(phase3_bp)
    print("[AMOS] Phase 3 routes registered")
except Exception as _e:
    print(f"[AMOS] Phase 3 warning: {_e}")


# ═══ SWARM FORMATION CONTROL ═══
@app.errorhandler(500)
def internal_error(e):
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": str(e)}), 500
    return str(e), 500

@app.errorhandler(404)
def not_found_error(e):
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": "endpoint not found"}), 404
    return str(e), 404


# ══════════════════════════════════════════════════════════
# SWARM FORMATION CONTROL
# ══════════════════════════════════════════════════════════

@app.route("/api/swarm/formation", methods=["POST"])
def set_swarm_formation():
    """Set swarm formation — assets MOVE to positions via waypoints"""
    import math as _m
    d = request.get_json() or {}
    domain = (d.get("domain") or "ground").lower().strip()
    formation = (d.get("formation") or d.get("pattern") or "LINE").upper().strip()

    # Collect assets for this domain
    domain_assets = []
    for aid, a in sim_assets.items():
        a_domain = str(a.get("domain", "")).lower().strip()
        if a_domain == domain or domain == "all":
            domain_assets.append((aid, a))

    if not domain_assets:
        existing = {}
        for aid, a in sim_assets.items():
            dd = str(a.get("domain", "?")).lower()
            existing[dd] = existing.get(dd, 0) + 1
        return jsonify({"error": f"No {domain} assets found. Have: {existing}"}), 400

    n = len(domain_assets)

    # Get current positions
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

    # Calculate formation target positions
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

        # Set waypoint for animated movement
        waypoint_nav.set_waypoint(aid, nlat, nlng, label=f"FORM-{formation}")
        targets.append({"id": aid, "lat": nlat, "lng": nlng})

    # Build drawable formation object for frontend map
    members = []
    for i, (aid, a) in enumerate(domain_assets):
        p = a.get("position", a)
        cur_lat = float(p.get("lat", 0))
        cur_lng = float(p.get("lng", 0))
        tgt = targets[i]
        members.append({
            "id": aid,
            "callsign": a.get("callsign", aid),
            "lat": cur_lat,
            "lng": cur_lng,
            "formation_lat": tgt["lat"],
            "formation_lng": tgt["lng"]
        })

    formation_obj = {
        "pattern": formation.lower(),
        "members": members,
        "center": {"lat": clat, "lng": clng}
    }

    msg = f"{n} {domain} assets moving to {formation} (watch the map!)"
    return jsonify({
        "success": True,
        "formation": formation_obj,
        "pattern": formation,
        "domain": domain,
        "count": n,
        "positions": targets,
        "message": msg
    })

@app.route("/api/swarm/formation/clear", methods=["POST"])
@app.route("/api/swarm/clear", methods=["POST"])
def clear_swarm_formation():
    """Clear formation, return to patrol"""
    d = request.get_json() or {}
    domain = d.get("domain", "ground").lower().strip()
    count = 0
    for aid, a in sim_assets.items():
        a_domain = str(a.get("domain", "")).lower().strip()
        if a_domain == domain or domain == "all":
            count += 1
    return jsonify({
        "success": True,
        "count": count,
        "message": f"{count} {domain} assets returned to patrol"
    })


@app.route("/api/swarm/debug")
def swarm_debug():
    """Debug: show asset structure"""
    info = {"asset_count": len(sim_assets), "domains": {}, "sample_keys": None, "position_sample": None}
    for aid, a in sim_assets.items():
        dom = str(a.get("domain", "?")).lower()
        info["domains"][dom] = info["domains"].get(dom, 0) + 1
        if info["sample_keys"] is None:
            info["sample_keys"] = list(a.keys())[:15]
            # Show position structure
            if "position" in a:
                info["position_sample"] = a["position"]
            elif "lat" in a:
                info["position_sample"] = {"lat": a["lat"], "lng": a["lng"]}
            info["sample_id"] = aid
    return jsonify(info)

# ═══════════════════════════════════════════════════════════
#  AUDIT TRAIL
# ═══════════════════════════════════════════════════════════
def _audit(user, action, target_type=None, target_id=None, detail=None):
    """Write an audit log entry to the database."""
    try:
        ip = request.remote_addr if request else None
        db_execute(
            "INSERT INTO audit_log (user, action, target_type, target_id, detail, ip) VALUES(%s,%s,%s,%s,%s,%s)",
            (user, action, target_type, target_id, to_json(detail) if detail else None, ip))
    except Exception:
        pass  # Don't crash on audit failures

@app.after_request
def audit_writes(response):
    """Auto-audit all POST/DELETE API calls."""
    if request.method in ("POST", "DELETE") and request.path.startswith("/api/"):
        u = session.get("user", "anonymous")
        _audit(u, f"{request.method} {request.path}", detail=request.get_json(silent=True))
    return response

# ═══════════════════════════════════════════════════════════
#  AUDIT API
# ═══════════════════════════════════════════════════════════
@app.route("/api/audit")
@login_required
def api_audit():
    c = ctx()
    if "admin" not in c["access"]:
        return jsonify({"error": "Admin access required"}), 403
    limit = request.args.get("limit", 100, type=int)
    rows = fetchall("SELECT * FROM audit_log ORDER BY id DESC LIMIT %s", (limit,))
    return jsonify([{**r, "timestamp": str(r["timestamp"]), "detail": from_json(r.get("detail"))} for r in rows])

# ═══════════════════════════════════════════════════════════
#  MISSION RECORDING API
# ═══════════════════════════════════════════════════════════
@app.route("/api/recording/start", methods=["POST"])
@login_required
def api_recording_start():
    if _recording["active"]:
        return jsonify({"error": "Already recording", "session_id": _recording["session_id"]}), 409
    sid = str(uuid.uuid4())
    c = ctx()
    name = request.json.get("name", f"Mission {now_iso()[:10]}")
    db_execute(
        "INSERT INTO recording_sessions (session_id, name, started_by) VALUES(%s,%s,%s)",
        (sid, name, c["user"]))
    _recording["active"] = True
    _recording["session_id"] = sid
    _recording["frame_seq"] = 0
    return jsonify({"status": "ok", "session_id": sid})

@app.route("/api/recording/stop", methods=["POST"])
@login_required
def api_recording_stop():
    if not _recording["active"]:
        return jsonify({"error": "Not recording"}), 400
    sid = _recording["session_id"]
    db_execute(
        "UPDATE recording_sessions SET status='complete', stopped_at=NOW(), frame_count=%s WHERE session_id=%s",
        (_recording["frame_seq"], sid))
    _recording["active"] = False
    _recording["session_id"] = None
    _recording["frame_seq"] = 0
    return jsonify({"status": "ok", "session_id": sid})

@app.route("/api/recording/sessions")
@login_required
def api_recording_sessions():
    rows = fetchall("SELECT * FROM recording_sessions ORDER BY started_at DESC LIMIT 50")
    return jsonify([{**r, "started_at": str(r["started_at"]),
                     "stopped_at": str(r["stopped_at"]) if r.get("stopped_at") else None} for r in rows])

@app.route("/api/recording/<session_id>/frames")
@login_required
def api_recording_frames(session_id):
    rows = fetchall(
        "SELECT frame_seq, clock_elapsed, asset_state, threat_state, timestamp "
        "FROM recording_frames WHERE session_id=%s ORDER BY frame_seq", (session_id,))
    return jsonify([{"seq": r["frame_seq"], "elapsed": float(r["clock_elapsed"]),
                     "assets": from_json(r["asset_state"]), "threats": from_json(r["threat_state"]),
                     "ts": str(r["timestamp"])} for r in rows])

# ═══════════════════════════════════════════════════════════
#  BRIDGE APIs (PX4 + TAK + Link 16)
# ═══════════════════════════════════════════════════════════
@app.route("/api/bridge/all")
@login_required
def api_bridge_all():
    """Unified status of all integration bridges."""
    return jsonify({
        "px4": _px4.get_status() if _px4 else {"connected": False},
        "tak": _tak.get_status() if _tak else {"connected": False},
        "link16": _link16.get_status() if _link16 else {"connected": False},
        "ros2": ros2_bridge.get_status() if ros2_bridge else {"available": False},
    })

# ── PX4 ──
@app.route("/api/bridge/px4/status")
@login_required
def api_px4_status():
    if not _px4:
        return jsonify({"connected": False, "error": "Bridge not loaded"})
    return jsonify(_px4.get_status())

@app.route("/api/bridge/px4/telemetry")
@login_required
def api_px4_telemetry():
    if not _px4:
        return jsonify({})
    return jsonify({aid: _px4.get_telemetry(aid) for aid in _px4.vehicles})

@app.route("/api/bridge/px4/register", methods=["POST"])
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
    # Auto-register in sim_assets if not present
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

@app.route("/api/bridge/px4/command", methods=["POST"])
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
@app.route("/api/bridge/tak/status")
@login_required
def api_tak_status():
    if not _tak:
        return jsonify({"connected": False, "error": "TAK bridge not loaded"})
    return jsonify(_tak.get_status())

@app.route("/api/bridge/tak/connect", methods=["POST"])
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

@app.route("/api/bridge/tak/disconnect", methods=["POST"])
@login_required
def api_tak_disconnect():
    if _tak and _tak.sock:
        try: _tak.sock.close()
        except Exception: pass
        _tak.connected = False
    return jsonify({"status": "ok"})

# ── Link 16 ──
@app.route("/api/bridge/link16/status")
@login_required
def api_link16_status():
    if not _link16:
        return jsonify({"connected": False, "error": "Link 16 not loaded"})
    return jsonify(_link16.get_status())

@app.route("/api/bridge/link16/tracks")
@login_required
def api_link16_tracks():
    if not _link16:
        return jsonify({})
    return jsonify(_link16.get_tactical_picture())

@app.route("/api/bridge/link16/messages")
@login_required
def api_link16_messages():
    if not _link16:
        return jsonify([])
    j_type = request.args.get("j_type")
    limit = request.args.get("limit", 50, type=int)
    return jsonify(_link16.get_messages(j_type=j_type, limit=limit))

@app.route("/api/bridge/link16/participants")
@login_required
def api_link16_participants():
    if not _link16:
        return jsonify({})
    return jsonify(_link16.get_participants())

@app.route("/api/bridge/link16/join", methods=["POST"])
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

@app.route("/api/bridge/link16/command", methods=["POST"])
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
#  ANALYTICS API (Phase 4)
# ═══════════════════════════════════════════════════════════
@app.route("/api/analytics/summary")
@login_required
def api_analytics_summary():
    """Aggregated mission analytics."""
    at = sum(1 for t in sim_threats.values() if not t.get("neutralized"))
    nt = sum(1 for t in sim_threats.values() if t.get("neutralized"))
    total_t = len(sim_threats)
    # Asset utilization
    moving = len(waypoint_nav.routes)
    idle = len(sim_assets) - moving
    low_batt = sum(1 for a in sim_assets.values() if a["health"]["battery_pct"] < 30)
    # COA stats
    cog_recs = cognitive_engine.get_recommendations(200)
    approved = sum(1 for r in cog_recs if r.get("status") in ("approve", "approved"))
    rejected = sum(1 for r in cog_recs if r.get("status") in ("reject", "rejected"))
    pending = sum(1 for r in cog_recs if r.get("status") == "pending")
    # Engagement stats
    engagements = len(cm_log)
    # Risk trend
    risk = commander_support.get_risk()
    risk_trend = commander_support.get_risk_trend()
    # Event counts by type
    event_types = {}
    for ev in aar_events:
        et = ev.get("type", "unknown")
        event_types[et] = event_types.get(et, 0) + 1
    # Domain breakdown
    by_domain = {}
    for a in sim_assets.values():
        d = a.get("domain", "unknown")
        by_domain[d] = by_domain.get(d, 0) + 1
    # Health averages
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
#  PHASE 7: AUTOMATION, EXERCISE, OVERLAYS, SITREP
# ═══════════════════════════════════════════════════════════
@app.route("/api/automation/rules")
@login_required
def api_automation_rules():
    return jsonify(_automation_rules)

@app.route("/api/automation/rules/create", methods=["POST"])
@login_required
def api_automation_rules_create():
    d = request.json or {}
    rid = f"RULE-{uuid.uuid4().hex[:6]}"
    _automation_rules[rid] = {
        "id": rid, "name": d.get("name", "Unnamed Rule"),
        "trigger_type": d.get("trigger_type", ""),
        "trigger_params": d.get("trigger_params", {}),
        "action_type": d.get("action_type", ""),
        "action_params": d.get("action_params", {}),
        "enabled": True, "fired_count": 0, "last_fired": None,
        "created_at": now_iso(), "created_by": ctx()["name"]}
    return jsonify({"status": "ok", "rule": _automation_rules[rid]})

@app.route("/api/automation/rules/toggle", methods=["POST"])
@login_required
def api_automation_rules_toggle():
    rid = (request.json or {}).get("rule_id", "")
    if rid in _automation_rules:
        _automation_rules[rid]["enabled"] = not _automation_rules[rid]["enabled"]
        return jsonify({"status": "ok", "enabled": _automation_rules[rid]["enabled"]})
    return jsonify({"error": "Rule not found"}), 404

@app.route("/api/automation/rules/delete", methods=["POST"])
@login_required
def api_automation_rules_delete():
    rid = (request.json or {}).get("rule_id", "")
    _automation_rules.pop(rid, None)
    return jsonify({"status": "ok"})

# ── Exercise Mode ──
@app.route("/api/exercise/status")
@login_required
def api_exercise_status():
    return jsonify(_exercise)

@app.route("/api/exercise/start", methods=["POST"])
@login_required
def api_exercise_start():
    d = request.json or {}
    _exercise["active"] = True
    _exercise["name"] = d.get("name", f"Exercise {now_iso()[:10]}")
    _exercise["started_at"] = now_iso()
    _exercise["injects"] = d.get("injects", [])
    _exercise["score"] = 0
    _exercise["max_score"] = sum(i.get("points", 10) for i in _exercise["injects"])
    _exercise["events"] = []
    _exercise["completed_injects"] = 0
    aar_events.append({"type": "exercise_start", "timestamp": now_iso(),
        "elapsed": sim_clock["elapsed_sec"],
        "details": f"Exercise '{_exercise['name']}' started with {len(_exercise['injects'])} injects"})
    return jsonify({"status": "ok", "exercise": _exercise})

@app.route("/api/exercise/stop", methods=["POST"])
@login_required
def api_exercise_stop():
    _exercise["active"] = False
    final = {"name": _exercise["name"], "score": _exercise["score"],
             "max_score": _exercise["max_score"], "completed": _exercise["completed_injects"],
             "total_injects": len(_exercise["injects"]), "events": _exercise["events"]}
    aar_events.append({"type": "exercise_end", "timestamp": now_iso(),
        "elapsed": sim_clock["elapsed_sec"],
        "details": f"Exercise '{_exercise['name']}' ended: {_exercise['score']}/{_exercise['max_score']} pts"})
    return jsonify({"status": "ok", "results": final})

@app.route("/api/exercise/presets")
@login_required
def api_exercise_presets():
    """Pre-built exercise scenarios."""
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

# ── Map Overlays ──
@app.route("/api/overlays/heatmap")
@login_required
def api_overlays_heatmap():
    """Threat density heatmap data."""
    points = []
    for t in sim_threats.values():
        if t.get("lat") and not t.get("neutralized"):
            points.append({"lat": t["lat"], "lng": t.get("lng", 0), "intensity": 1.0})
    for ti in _threat_intel.values():
        for p in ti.get("positions", [])[-10:]:
            points.append({"lat": p["lat"], "lng": p["lng"], "intensity": 0.4})
    return jsonify({"points": points, "count": len(points)})

@app.route("/api/overlays/sectors")
@login_required
def api_overlays_sectors():
    """Domain sector coverage."""
    sectors = []
    for domain in ["air", "ground", "maritime"]:
        assets = [a for a in sim_assets.values() if a["domain"] == domain]
        if not assets:
            continue
        lats = [a["position"]["lat"] for a in assets]
        lngs = [a["position"]["lng"] for a in assets]
        sectors.append({"domain": domain, "asset_count": len(assets),
            "bounds": {"north": max(lats) + 0.01, "south": min(lats) - 0.01,
                       "east": max(lngs) + 0.01, "west": min(lngs) - 0.01},
            "center": {"lat": sum(lats) / len(lats), "lng": sum(lngs) / len(lngs)}})
    return jsonify(sectors)

@app.route("/api/overlays/engagement-zones")
@login_required
def api_overlays_engagement_zones():
    """Weapon engagement envelopes."""
    zones = []
    for a in sim_assets.values():
        if not a.get("weapons"):
            continue
        rng = 0.015 if a["domain"] == "air" else 0.008  # approximate range in degrees
        zones.append({"asset_id": a["id"], "domain": a["domain"],
            "center": {"lat": a["position"]["lat"], "lng": a["position"]["lng"]},
            "radius_deg": rng, "weapons": a["weapons"]})
    return jsonify(zones)

# ── SITREP Generator ──
@app.route("/api/sitrep/generate", methods=["POST"])
@login_required
def api_sitrep_generate():
    """Generate a formatted SITREP."""
    at = sum(1 for t in sim_threats.values() if not t.get("neutralized"))
    nt = sum(1 for t in sim_threats.values() if t.get("neutralized"))
    risk = commander_support.get_risk()
    c = ctx()
    moving = len(waypoint_nav.routes)
    avg_batt = sum(a["health"]["battery_pct"] for a in sim_assets.values()) / max(1, len(sim_assets))
    sitrep = {
        "id": f"SITREP-{len(_sitreps)+1:03d}",
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
        "line5_command": f"Pending approvals: {sum(1 for r in hal_recommendations if r.get('status')=='pending')}. Exercise: {'ACTIVE' if _exercise['active'] else 'NONE'}",
    }
    _sitreps.append(sitrep)
    return jsonify(sitrep)

@app.route("/api/sitrep/history")
@login_required
def api_sitrep_history():
    return jsonify(_sitreps[-20:])

# ═══════════════════════════════════════════════════════════
#  PHASE 6: MISSION INTELLIGENCE & REPORTING
# ═══════════════════════════════════════════════════════════
@app.route("/api/aar/timeline")
@login_required
def api_aar_timeline():
    """Enhanced AAR timeline with filtering."""
    etype = request.args.get("type")  # filter by event type
    limit = request.args.get("limit", 500, type=int)
    events = aar_events[-limit:]
    if etype:
        events = [e for e in events if e.get("type") == etype]
    # Build type summary for filter buttons
    type_counts = {}
    for e in aar_events:
        t = e.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    # Build density buckets (30 buckets across timeline)
    buckets = [0] * 30
    max_elapsed = max((e.get("elapsed", 0) for e in aar_events), default=1) or 1
    for e in aar_events:
        idx = min(29, int((e.get("elapsed", 0) / max_elapsed) * 29))
        buckets[idx] += 1
    return jsonify({"events": events, "type_counts": type_counts,
                    "density": buckets, "total": len(aar_events),
                    "max_elapsed": round(max_elapsed, 1)})

@app.route("/api/reports/mission")
@login_required
def api_reports_mission():
    """Generate comprehensive mission report."""
    at = sum(1 for t in sim_threats.values() if not t.get("neutralized"))
    nt = sum(1 for t in sim_threats.values() if t.get("neutralized"))
    risk = commander_support.get_risk()
    cog_recs = cognitive_engine.get_recommendations(200)
    approved = sum(1 for r in cog_recs if r.get("status") in ("approve", "approved"))
    rejected = sum(1 for r in cog_recs if r.get("status") in ("reject", "rejected"))
    # Asset status summary
    asset_summary = []
    for aid, a in sim_assets.items():
        asset_summary.append({"id": aid, "type": a["type"], "domain": a["domain"],
            "status": a["status"], "battery": a["health"]["battery_pct"],
            "comms": a["health"]["comms_strength"]})
    # Event summary by type
    event_types = {}
    for ev in aar_events:
        et = ev.get("type", "unknown")
        event_types[et] = event_types.get(et, 0) + 1
    # Threat intel
    threat_summary = []
    for ttype, ti in _threat_intel.items():
        threat_summary.append({"type": ttype, "count": ti["count"],
            "neutralized": ti["neutralized"], "engagements": ti["engagements"]})
    report = {
        "title": f"MISSION REPORT — {platoon.get('name', 'UNNAMED')}",
        "callsign": platoon.get("callsign", ""),
        "generated_at": now_iso(),
        "dtg": datetime.now(timezone.utc).strftime("%d%H%MZ %b %Y").upper(),
        "elapsed_sec": round(sim_clock["elapsed_sec"], 1),
        "elapsed_min": round(sim_clock["elapsed_sec"] / 60, 1),
        "situation": {
            "total_assets": len(sim_assets), "active_threats": at,
            "neutralized_threats": nt, "total_threats": len(sim_threats),
            "neutralization_pct": round(nt / max(1, len(sim_threats)) * 100, 1),
            "risk_level": risk.get("level", "LOW"), "risk_score": risk.get("score", 0),
        },
        "decisions": {
            "coa_approved": approved, "coa_rejected": rejected,
            "engagements": len(cm_log),
            "countermeasures_deployed": len(cm_log),
            "voice_commands": event_types.get("voice_command", 0),
        },
        "assets": asset_summary,
        "threat_intel": threat_summary,
        "events": {"total": len(aar_events), "by_type": event_types},
        "integrations": {
            "px4": _px4.connected if _px4 else False,
            "tak": _tak.connected if _tak else False,
            "link16": bool(_link16), "ros2": ros2_bridge.available if ros2_bridge else False,
        },
    }
    return jsonify(report)

@app.route("/api/threat-intel")
@login_required
def api_threat_intel():
    """Threat intelligence database."""
    return jsonify(_threat_intel)

@app.route("/api/readiness")
@login_required
def api_readiness():
    """Pre-mission readiness scorecard."""
    total = len(sim_assets)
    # Fleet health
    avg_batt = sum(a["health"]["battery_pct"] for a in sim_assets.values()) / max(1, total)
    avg_comms = sum(a["health"]["comms_strength"] for a in sim_assets.values()) / max(1, total)
    low_batt = sum(1 for a in sim_assets.values() if a["health"]["battery_pct"] < 30)
    gps_fix = sum(1 for a in sim_assets.values() if a["health"].get("gps_fix", True))
    # Sensor coverage
    all_sensors = set()
    for a in sim_assets.values():
        all_sensors.update(a.get("sensors", []))
    # Weapon readiness
    armed = sum(1 for a in sim_assets.values() if a.get("weapons"))
    # Endurance
    avg_endurance = sum(a.get("endurance_hr", 0) for a in sim_assets.values()) / max(1, total)
    # Integration status
    intg = {"px4": _px4.connected if _px4 else False,
            "tak": _tak.connected if _tak else False,
            "link16": bool(_link16),
            "ros2": ros2_bridge.available if ros2_bridge else False}
    intg_score = sum(1 for v in intg.values() if v) / max(1, len(intg)) * 100
    # Domain coverage
    domains = set(a.get("domain", "") for a in sim_assets.values())
    # Compute GO/NO-GO scores
    fleet_score = min(100, avg_batt * 0.4 + avg_comms * 0.3 + (gps_fix / max(1, total) * 100) * 0.3)
    weapon_score = (armed / max(1, total)) * 100
    sensor_score = min(100, len(all_sensors) * 12.5)  # 8 unique sensors = 100%
    endurance_score = min(100, avg_endurance * 10)  # 10hr = 100%
    overall = (fleet_score * 0.35 + weapon_score * 0.2 + sensor_score * 0.2 +
               endurance_score * 0.15 + intg_score * 0.1)
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
        "integrations": {**intg, "score": round(intg_score, 1)},
        "domains": sorted(list(domains)),
        "risk": {"level": risk.get("level", "LOW"), "score": risk.get("score", 0)},
        "asset_details": [{"id": a["id"], "type": a["type"], "domain": a["domain"],
            "battery": a["health"]["battery_pct"], "comms": a["health"]["comms_strength"],
            "gps": a["health"].get("gps_fix", True),
            "armed": bool(a.get("weapons")), "endurance_hr": a.get("endurance_hr", 0),
            "status": a["status"]} for a in sim_assets.values()],
    })

# ═══════════════════════════════════════════════════════════
#  MULTI-OPERATOR COLLABORATION (Phase 2)
# ═══════════════════════════════════════════════════════════
_OP_COLORS = ["#00ff41","#4488ff","#ff4444","#ffaa00","#ff66ff","#00cccc","#ff8800","#88ff00"]

def _broadcast_presence():
    """Send current operator list to all connected clients."""
    ops = []
    for sid, info in _online_ops.items():
        ops.append({"user": info["user"], "name": info["name"], "role": info["role"],
                    "page": info.get("page", ""), "color": info.get("color", "#888")})
    socketio.emit("operator_presence", ops)

@socketio.on("connect")
def ws_connect():
    """Track operator connection."""
    # Session may not have user yet (login page)
    u = session.get("user")
    if not u:
        return
    info = USERS.get(u, {})
    color_idx = len(_online_ops) % len(_OP_COLORS)
    _online_ops[request.sid] = {
        "user": u, "name": info.get("name", u), "role": info.get("role", ""),
        "page": "", "cursor": None, "color": _OP_COLORS[color_idx],
        "connected_at": now_iso()
    }
    _broadcast_presence()

@socketio.on("disconnect")
def ws_disconnect():
    """Clean up on disconnect."""
    sid = request.sid
    op = _online_ops.pop(sid, None)
    if op:
        # Release any asset locks held by this operator
        to_unlock = [aid for aid, lk in _asset_locks.items() if lk["locked_by"] == op["user"]]
        for aid in to_unlock:
            _asset_locks.pop(aid, None)
        _broadcast_presence()
        socketio.emit("asset_locks", _asset_locks)

@socketio.on("operator_page")
def ws_operator_page(data):
    """Operator reports which page they're viewing."""
    sid = request.sid
    if sid in _online_ops:
        _online_ops[sid]["page"] = data.get("page", "")
        _broadcast_presence()

@socketio.on("operator_cursor")
def ws_operator_cursor(data):
    """Relay cursor position to all other operators."""
    sid = request.sid
    op = _online_ops.get(sid)
    if not op:
        return
    op["cursor"] = {"lat": data.get("lat"), "lng": data.get("lng")}
    socketio.emit("cursor_update", {
        "user": op["user"], "name": op["name"], "color": op["color"],
        "lat": data.get("lat"), "lng": data.get("lng")
    }, include_self=False)

@socketio.on("team_chat")
def ws_team_chat(data):
    """Broadcast a chat message and persist it."""
    sid = request.sid
    op = _online_ops.get(sid)
    u = op["user"] if op else session.get("user", "anonymous")
    name = op["name"] if op else u
    channel = data.get("channel", "general")
    msg = (data.get("message", "") or "").strip()
    if not msg:
        return
    try:
        db_execute("INSERT INTO chat_messages (channel, sender, message) VALUES(%s,%s,%s)",
                   (channel, u, msg))
    except Exception:
        pass
    socketio.emit("chat_message", {
        "channel": channel, "sender": u, "name": name,
        "message": msg, "timestamp": now_iso(),
        "color": op.get("color", "#888") if op else "#888"
    })

@socketio.on("asset_lock")
def ws_asset_lock(data):
    """Lock an asset for exclusive control."""
    sid = request.sid
    op = _online_ops.get(sid)
    if not op:
        return
    aid = data.get("asset_id", "").strip().upper()
    if not aid:
        return
    existing = _asset_locks.get(aid)
    if existing and existing["locked_by"] != op["user"]:
        sio_emit("lock_denied", {"asset_id": aid, "locked_by": existing["locked_by"]})
        return
    _asset_locks[aid] = {"locked_by": op["user"], "locked_at": now_iso()}
    try:
        db_execute(
            "INSERT INTO asset_locks (asset_id, locked_by) VALUES(%s,%s) "
            "ON DUPLICATE KEY UPDATE locked_by=%s, locked_at=CURRENT_TIMESTAMP",
            (aid, op["user"], op["user"]))
    except Exception:
        pass
    socketio.emit("asset_locks", _asset_locks)

@socketio.on("asset_unlock")
def ws_asset_unlock(data):
    """Release an asset lock."""
    sid = request.sid
    op = _online_ops.get(sid)
    if not op:
        return
    aid = data.get("asset_id", "").strip().upper()
    existing = _asset_locks.get(aid)
    if existing and existing["locked_by"] == op["user"]:
        _asset_locks.pop(aid, None)
        try:
            db_execute("DELETE FROM asset_locks WHERE asset_id=%s", (aid,))
        except Exception:
            pass
    socketio.emit("asset_locks", _asset_locks)

@app.route("/api/operators/online")
@login_required
def api_operators_online():
    ops = []
    for sid, info in _online_ops.items():
        ops.append({"user": info["user"], "name": info["name"], "role": info["role"],
                    "page": info.get("page", ""), "color": info.get("color"),
                    "connected_at": info["connected_at"]})
    return jsonify(ops)

@app.route("/api/chat/history")
@login_required
def api_chat_history():
    channel = request.args.get("channel", "general")
    limit = request.args.get("limit", 50, type=int)
    rows = fetchall(
        "SELECT sender, message, timestamp FROM chat_messages WHERE channel=%s ORDER BY id DESC LIMIT %s",
        (channel, limit))
    return jsonify([{"sender": r["sender"], "message": r["message"],
                     "timestamp": str(r["timestamp"])} for r in reversed(rows)])

@app.route("/api/asset/locks")
@login_required
def api_asset_locks():
    return jsonify(_asset_locks)

if __name__ == "__main__":
    threading.Thread(target=sim_tick, daemon=True, name="sim_tick").start()
    db_ok = "✓ Connected" if db_check() else "✗ Offline"
    print("\n" + "=" * 58)
    print("  AMOS — Autonomous Mission Operating System v2.0 + Phase 7")
    print("  http://localhost:2600")
    print(f"  Database: {db_ok}")
    print("-" * 58)
    for u, i in USERS.items():
        print(f"  {u:12s} [{i.get('role','')}]")
    print("=" * 58 + "\n")
    socketio.run(app, host="0.0.0.0", port=2600, allow_unsafe_werkzeug=True)
