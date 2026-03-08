#!/usr/bin/env python3
"""AMOS — Autonomous Mission Operating System v2.0
Multi-Domain Autonomous C2 · Phase 2"""

import os, sys, json, time, random, math, uuid, threading, yaml
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_socketio import SocketIO

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

# Phase 3
import sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__)))


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
#  MULTI-USER SYSTEM
# ═══════════════════════════════════════════════════════════
USERS = {
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

# ═══════════════════════════════════════════════════════════
#  AUTH ROUTES
# ═══════════════════════════════════════════════════════════

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u, p = request.form.get("username",""), request.form.get("password","")
        usr = USERS.get(u)
        if usr and usr["password"] == p:
            session["user"] = u
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

@app.route("/settings")
@login_required
def settings_page(): return render_template("settings.html", **ctx())

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
    sim_assets[aid] = {
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
    return jsonify({"status": "ok", "id": aid})

@app.route("/api/settings/assets/delete", methods=["POST"])
@login_required
def api_settings_assets_delete():
    """Remove an asset from sim_assets."""
    aid = request.json.get("id", "").strip().upper()
    if aid in sim_assets:
        del sim_assets[aid]
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
def api_hal_recs(): return jsonify(hal_recommendations[-50:])

@app.route("/api/hal/action", methods=["POST"])
@login_required
def api_hal_action():
    d = request.json; rid = d.get("id",""); act = d.get("action",""); c = ctx()
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
    at = sum(1 for t in sim_threats.values() if not t.get("neutralized"))
    return jsonify([
        {"rank":1,"name":"OVERWHELMING FORCE","score":round(random.uniform(.75,.95),2),
         "risk":"LOW","description":f"All assets engage {at} threats simultaneously. Max ISR + EW."},
        {"rank":2,"name":"SEQUENTIAL ENGAGE","score":round(random.uniform(.65,.85),2),
         "risk":"MEDIUM","description":"Priority targeting. GHOST recon, TALON engage, REAPER overwatch."},
        {"rank":3,"name":"CYBER-EW FIRST","score":round(random.uniform(.55,.80),2),
         "risk":"MEDIUM","description":"Degrade C2 via cyber/EW before kinetic. Blind then strike."},
        {"rank":4,"name":"DEFENSIVE HOLD","score":round(random.uniform(.50,.70),2),
         "risk":"LOW","description":"Consolidate at FOB Tehran. Sensor perimeter. Engage on approach only."}])

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

if __name__ == "__main__":
    threading.Thread(target=sim_tick, daemon=True, name="sim_tick").start()
    print("\n" + "=" * 58)
    print("  AMOS — Autonomous Mission Operating System v2.0 + Phase 10")
    print("  http://localhost:2600")
    print("-" * 58)
    for u, i in USERS.items():
        print(f"  {u:12s} / {i['password']:14s} [{i['role']}]")
    print("=" * 58 + "\n")
    socketio.run(app, host="0.0.0.0", port=2600, allow_unsafe_werkzeug=True)
