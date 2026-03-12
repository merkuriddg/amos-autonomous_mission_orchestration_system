"""AMOS Shared State.

All mutable in-memory state and subsystem instances live here.
Imported by route blueprints and the simulation engine.
Python shares mutable object references, so mutations are globally visible.
"""

import os, sys, random, time
from datetime import datetime, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from web.extensions import config, base_pos, platoon
from web.edition import feature_enabled, is_enterprise, AMOS_EDITION

from db.connection import fetchall, fetchone, execute as db_execute, to_json, from_json, check as db_check
from db.persistence import (flush_periodic as db_flush, persist_engagement, persist_bda,
                            persist_sitrep, persist_hal_action, load_state_from_db)

# ═══════════════════════════════════════════════════════════
#  CORE DATA MODELS
# ═══════════════════════════════════════════════════════════
from core.data_model import Track, Detection, Command, SensorReading, VideoFrame, Message
from core.schema_validator import SchemaValidator
from core.adapter_base import AdapterManager, LegacyBridgeAdapter
from core.event_bus import EventBus
from core.plugin_loader import PluginLoader
from core.geo_utils import (haversine, vincenty, bearing, destination_point,
                            latlng_to_utm, utm_to_latlng, latlng_to_mgrs,
                            mgrs_to_latlng, tracks_to_geojson, bounding_box)

# ═══════════════════════════════════════════════════════════
#  USERS (DB-backed with fallback)
# ═══════════════════════════════════════════════════════════
_FALLBACK_USERS = {
    "commander": {"password": "amos_op1", "role": "commander",
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


def _sync_db_passwords():
    """Ensure DB password hashes match _FALLBACK_USERS (source of truth)."""
    try:
        if not db_check():
            return
        from werkzeug.security import generate_password_hash
        for username, info in _FALLBACK_USERS.items():
            db_execute(
                "UPDATE users SET password_hash=%s WHERE username=%s",
                (generate_password_hash(info["password"]), username)
            )
    except Exception:
        pass  # best-effort


def _load_users_from_db():
    """Load users from MariaDB. Falls back to hardcoded dict."""
    try:
        if not db_check():
            raise Exception("DB offline")
        _sync_db_passwords()  # keep DB hashes in sync with fallback
        rows = fetchall("SELECT * FROM users WHERE active=1")
        if not rows:
            raise Exception("No users in DB")
        users = {}
        for r in rows:
            uname = r["username"]
            fb = _FALLBACK_USERS.get(uname, {})
            users[uname] = {
                "password_hash": r["password_hash"],
                "password": fb.get("password", ""),  # for login page display
                "role": r["role"], "name": r["name"],
                "domain": r["domain"], "access": from_json(r["access"])
            }
        print(f"[AMOS] Loaded {len(users)} users from DB")
        return users, True
    except Exception as e:
        print(f"[AMOS] DB user load failed ({e}), using fallback")
        return _FALLBACK_USERS, False


USERS, DB_AUTH = _load_users_from_db()

# ═══════════════════════════════════════════════════════════
#  DB STATE RECOVERY
# ═══════════════════════════════════════════════════════════
_db_state = load_state_from_db()

# ═══════════════════════════════════════════════════════════
#  MUTABLE SHARED STATE
# ═══════════════════════════════════════════════════════════
# Recording
recording = {"active": False, "session_id": None, "frame_seq": 0, "tick_count": 0}

# Threat intel
threat_intel = _db_state.get("threat_intel", {})

# Rule engine + exercise
automation_rules = {}
exercise = {"active": False, "name": "", "started_at": None, "injects": [], "score": 0,
            "max_score": 0, "events": [], "completed_injects": 0}
sitreps = _db_state.get("sitreps", [])
alert_cooldowns = {}

# Mission plans, training, uptime
mission_plans = _db_state.get("mission_plans", {})
training_records = []
uptime_pings = []

# Logistics, weather, BDA, EOB
supply_history = []
bda_reports = _db_state.get("bda_reports", [])
eob_units = {}
weather = {"wind_speed_kt": 12, "wind_dir_deg": 225, "temp_c": 28, "visibility_km": 15,
           "precipitation": "none", "ceiling_ft": 25000, "sea_state": 2,
           "conditions": "Clear", "last_update": None}

# Online operators
online_ops = {}
asset_locks = {}

# Simulation lists
ew_active_jams, ew_intercepts = [], []
sigint_intercepts, sigint_emitter_db = [], {}
cyber_events, cyber_blocked_ips = [], set()
cm_log, hal_recommendations, aar_events = [], [], []
swarms = {}

# Sim clock
sim_clock = {"start_time": time.time(), "elapsed_sec": 0, "speed": 1.0, "running": True}

# ═══════════════════════════════════════════════════════════
#  LOAD ASSETS + THREATS FROM CONFIG
# ═══════════════════════════════════════════════════════════
sim_assets = {}
for a in config.get("assets", []):
    sp = a.get("spawn", {})
    is_air = a.get("domain") == "air"
    sim_assets[a["id"]] = {
        "id": a["id"], "type": a.get("type", ""), "domain": a.get("domain", ""),
        "role": a.get("role", ""), "autonomy_tier": a.get("autonomy_tier", 1),
        "sensors": a.get("sensors", []), "weapons": a.get("weapons", []),
        "endurance_hr": a.get("endurance_hr", 0),
        "position": {"lat": sp.get("lat", base_pos["lat"]),
                      "lng": sp.get("lng", base_pos["lng"]),
                      "alt_ft": sp.get("alt_ft", 0)},
        "status": "operational",
        "health": {"battery_pct": random.randint(85, 100),
                    "comms_strength": random.randint(75, 100),
                    "cpu_temp_c": random.randint(35, 55), "gps_fix": True},
        "speed_kts": random.randint(80, 200) if is_air else random.randint(5, 30),
        "heading_deg": random.randint(0, 359),
        "supplies": {"fuel_pct": random.randint(70, 100),
                     "ammo_rounds": random.randint(50, 200) if a.get("weapons") else 0,
                     "water_hr": random.randint(8, 48), "rations_hr": random.randint(12, 72)},
    }
print(f"[AMOS] Loaded {len(sim_assets)} assets (config)")

sim_threats = {}
for t in config.get("threats", []):
    sim_threats[t["id"]] = {**t, "neutralized": False, "detected_by": [], "first_detected": None}
print(f"[AMOS] Loaded {len(sim_threats)} threats (config)")


# ═══════════════════════════════════════════════════════════
#  THEATER PLATOON GENERATOR — spawn forces at every location
# ═══════════════════════════════════════════════════════════
_THEATER_PLATOON = {
    # Each tuple: (id_suffix, type, domain, role, tier, sensors, weapons, endurance, lat_off, lng_off, alt_ft)
    "air": [
        ("HAWK",  "MQ-9B",        "air", "isr_strike",    3, ["EO/IR","SAR","SIGINT","AESA_RADAR"], ["GBU-38","AGM-114"], 27, 0.006, 0.008, 15000),
        ("HAWK2", "MQ-9B",        "air", "isr_strike",    3, ["EO/IR","SAR","SIGINT","AESA_RADAR"], ["GBU-38","AGM-114"], 27, 0.011, 0.003, 18000),
        ("SPT1",  "small_uas",    "air", "recon",         4, ["EO/IR","SIGINT"],                      [],                   6,  -0.001, 0.013, 400),
        ("SPT2",  "small_uas",    "air", "ew",            4, ["EO/IR","EW_JAMMER"],                   [],                   5,  -0.002, 0.018, 500),
        ("SPT3",  "small_uas",    "air", "recon",         4, ["EO/IR","SIGINT"],                      [],                   6,  -0.003, 0.023, 400),
        ("WING1", "loyal_wingman", "air", "air_superiority",3,["AESA_RADAR","RWR","EO/IR"],           ["AIM-120_SIM"],      3,  0.021, -0.012, 20000),
        ("EYE1",  "high_alt_uas", "air", "airborne_c2",   3, ["AEW_RADAR","SIGINT","COMINT","ELINT"],[],                   24, 0.031, -0.032, 35000),
    ],
    "ground": [
        ("CLAW1", "armed_ugv",    "ground", "direct_action", 2, ["EO/IR","LIDAR","ACOUSTIC"], ["M240_RWS"], 0, -0.009, 0.006, 0),
        ("CLAW2", "armed_ugv",    "ground", "direct_action", 2, ["EO/IR","LIDAR","ACOUSTIC"], ["M240_RWS"], 0, -0.011, 0.010, 0),
        ("CLAW3", "armed_ugv",    "ground", "direct_action", 2, ["EO/IR","LIDAR","ACOUSTIC"], ["MK19_RWS"], 0, -0.013, 0.014, 0),
        ("PACK1", "logistics_ugv", "ground", "resupply",     3, ["LIDAR","GPS"],               [],           0, -0.007, 0.002, 0),
        ("PACK2", "logistics_ugv", "ground", "resupply",     3, ["LIDAR","GPS"],               [],           0, -0.008, 0.004, 0),
        ("PACK3", "logistics_ugv", "ground", "medevac",      3, ["LIDAR","GPS"],               [],           0, -0.010, 0.008, 0),
        ("EARS1", "sensor_ugv",   "ground", "sigint",        4, ["SIGINT","ELINT","COMINT","DIRECTION_FINDING"], [], 0, -0.017, 0.022, 0),
        ("EARS2", "sensor_ugv",   "ground", "cbrn",          4, ["CBRN","SIGINT","LIDAR"],    [],           0, -0.021, 0.030, 0),
    ],
    "maritime": [
        ("SURF1", "usv",  "maritime", "coastal_patrol",    3, ["RADAR","EO/IR","SONAR","AIS"], [], 72, 0.061, 0.088, 0),
        ("SURF2", "usv",  "maritime", "coastal_patrol",    3, ["RADAR","EO/IR","SONAR","AIS"], [], 72, 0.051, 0.108, 0),
        ("DEEP1", "uuv",  "maritime", "subsurface_recon",  4, ["SONAR","MAGNETIC","ACOUSTIC"], [], 48, 0.041, 0.128, 0),
    ],
}

# Domain emphasis per theater — multiplier for how many extra of each domain
_THEATER_EMPHASIS = {
    "tampa":           {"air": 1, "ground": 1, "maritime": 1},
    "south_china_sea": {"air": 1, "ground": 0, "maritime": 2},  # extra maritime, no ground
    "eastern_europe":  {"air": 1, "ground": 2, "maritime": 0},  # extra ground, no maritime
    "test_base":       {"air": 1, "ground": 1, "maritime": 0},
}

_THEATER_PREFIX = {
    "tampa": "TB", "south_china_sea": "SCS", "eastern_europe": "EU", "test_base": "TST",
}

_THREAT_TEMPLATES = [
    {"type": "drone",      "rf_freq_mhz": 915.0,    "speed_kts": 45, "dlat": -0.069, "dlng": 0.138},
    {"type": "drone",      "rf_freq_mhz": 2437.0,   "speed_kts": 35, "dlat": 0.041,  "dlng": -0.092},
    {"type": "drone",      "rf_freq_mhz": 5805.0,   "speed_kts": 50, "dlat": -0.039, "dlng": 0.188},
    {"type": "gps_jammer", "rf_freq_mhz": 1575.42,  "power_dbm": 40, "dlat": 0.021,  "dlng": 0.068},
    {"type": "gps_jammer", "rf_freq_mhz": 1575.42,  "power_dbm": 35, "dlat": -0.029, "dlng": -0.032},
    {"type": "rf_emitter", "rf_freq_mhz": 433.0,    "power_dbm": 25, "dlat": 0.011,  "dlng": 0.108},
]


def _generate_theater_forces():
    """Generate assets + threats for all non-primary theaters from locations.json."""
    from web.extensions import load_locations
    loc_data = load_locations()
    primary = loc_data.get("active", "tehran")
    generated_assets = 0
    generated_threats = 0

    for key, loc in loc_data.get("locations", {}).items():
        if key == "tehran":  # Tehran already has YAML assets from config
            continue
        prefix = _THEATER_PREFIX.get(key)
        if not prefix:
            continue
        emphasis = _THEATER_EMPHASIS.get(key, {"air": 1, "ground": 1, "maritime": 1})
        clat, clng = loc["lat"], loc["lng"]

        # Generate assets per domain
        for domain, templates in _THEATER_PLATOON.items():
            count = emphasis.get(domain, 1)
            if count == 0:
                continue
            for tmpl in templates:
                suffix, atype, dom, role, tier, sensors, weapons, endurance, dlat, dlng, alt = tmpl
                for rep in range(count):
                    rep_tag = f"-{rep+2}" if rep > 0 else ""
                    aid = f"{prefix}-{suffix}{rep_tag}"
                    is_air = dom == "air"
                    lat = clat + dlat + random.uniform(-0.003, 0.003)
                    lng = clng + dlng + random.uniform(-0.003, 0.003)
                    if rep > 0:
                        lat += random.uniform(-0.008, 0.008)
                        lng += random.uniform(-0.008, 0.008)
                    sim_assets[aid] = {
                        "id": aid, "type": atype, "domain": dom,
                        "role": role, "autonomy_tier": tier,
                        "sensors": list(sensors), "weapons": list(weapons),
                        "endurance_hr": endurance,
                        "position": {"lat": round(lat, 6), "lng": round(lng, 6), "alt_ft": alt},
                        "status": "operational",
                        "health": {"battery_pct": random.randint(85, 100),
                                   "comms_strength": random.randint(75, 100),
                                   "cpu_temp_c": random.randint(35, 55), "gps_fix": True},
                        "speed_kts": random.randint(80, 200) if is_air else random.randint(5, 30),
                        "heading_deg": random.randint(0, 359),
                        "supplies": {"fuel_pct": random.randint(70, 100),
                                     "ammo_rounds": random.randint(50, 200) if weapons else 0,
                                     "water_hr": random.randint(8, 48),
                                     "rations_hr": random.randint(12, 72)},
                        "theater": key,
                    }
                    generated_assets += 1

        # Generate threats
        # Maritime theaters get vessel threats; land theaters get ground threats
        for i, tt in enumerate(_THREAT_TEMPLATES):
            if tt["type"] == "drone" and emphasis.get("air", 0) == 0:
                continue
            tid = f"{prefix}-THR-{i+1:03d}"
            tlat = clat + tt["dlat"] + random.uniform(-0.01, 0.01)
            tlng = clng + tt["dlng"] + random.uniform(-0.01, 0.01)
            threat_data = {
                "id": tid, "type": tt["type"],
                "lat": round(tlat, 4), "lng": round(tlng, 4),
                "rf_freq_mhz": tt.get("rf_freq_mhz", 0),
                "neutralized": False, "detected_by": [], "first_detected": None,
            }
            if "speed_kts" in tt:
                threat_data["speed_kts"] = tt["speed_kts"]
            if "power_dbm" in tt:
                threat_data["power_dbm"] = tt["power_dbm"]
            sim_threats[tid] = threat_data
            generated_threats += 1

        # Add vessel threats for maritime-heavy theaters
        if emphasis.get("maritime", 0) > 0:
            for vi in range(2):
                vid = f"{prefix}-VES-{vi+1:03d}"
                sim_threats[vid] = {
                    "id": vid, "type": "vessel",
                    "lat": round(clat + 0.08 + random.uniform(-0.02, 0.02), 4),
                    "lng": round(clng + 0.05 + random.uniform(-0.02, 0.02), 4),
                    "speed_kts": random.randint(15, 25),
                    "neutralized": False, "detected_by": [], "first_detected": None,
                }
                generated_threats += 1

    print(f"[AMOS] Generated {generated_assets} theater assets + {generated_threats} theater threats")


_generate_theater_forces()
print(f"[AMOS] Total: {len(sim_assets)} assets, {len(sim_threats)} threats")

# Auto-populate EOB from threats
for tid, t in sim_threats.items():
    eob_units[tid] = {
        "id": tid, "name": t.get("id", tid), "type": t.get("type", "unknown"),
        "affiliation": "hostile",
        "emitter_type": random.choice(["radar", "comms", "jammer", "datalink"]),
        "freq_mhz": round(random.uniform(200, 18000), 1),
        "equipment": [t.get("type", "unknown")], "capability": "offensive",
        "threat_level": random.choice(["low", "medium", "high", "critical"]),
        "confidence": random.choice(["low", "medium", "high"]),
        "status": "active",
        "last_known": {"lat": t.get("lat", 0), "lng": t.get("lng", 0)},
        "positions": [], "engagements": 0, "first_seen": None, "notes": ""}

# ═══════════════════════════════════════════════════════════
#  CORE SUBSYSTEMS (always available)
# ═══════════════════════════════════════════════════════════
from services.waypoint_nav import WaypointNav
from services.geofence_manager import GeofenceManager
from services.voice_parser import VoiceParser
from services.ros2_bridge import ROS2Bridge
from services.task_allocator import TaskAllocator
from services.roe_engine import ROEEngine
from services.sensor_fusion_engine import SensorFusionEngine
from services.mesh_network import MeshNetwork
from services.video_pipeline import VideoPipeline
from services.klv_parser import KLVParser
from services.imagery_handler import ImageryHandler

waypoint_nav = WaypointNav()
geofence_mgr = GeofenceManager()
voice_parser = VoiceParser()
ros2_bridge = ROS2Bridge()
task_allocator = TaskAllocator()
roe_engine = ROEEngine()
sensor_fusion = SensorFusionEngine()
mesh_network = MeshNetwork()
video_pipeline = VideoPipeline()
klv_parser = KLVParser()
imagery_handler = ImageryHandler()

# Core data stack
adapter_mgr = AdapterManager()
schema_validator = SchemaValidator()

# Plugin system
event_bus = EventBus()
plugin_loader = PluginLoader(os.path.join(ROOT_DIR, "plugins"), event_bus=event_bus)
try:
    _plugin_results = plugin_loader.discover_and_load_all()
    _ps = plugin_loader.registry.get_summary()
    print(f"[AMOS] Plugins: {_ps['active']} active, {_ps['errored']} errored, {_ps['disabled']} disabled")
except Exception as e:
    print(f"[AMOS] Plugin loader error: {e}")

# Geofence setup from config
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
                     for s in ["EW_JAMMER", "SIGINT", "ELINT", "COMINT", "AESA_RADAR", "AEW_RADAR"])]

# AO center for overlays
AO_CENTER = {"lat": (ao.get("north", 0) + ao.get("south", 0)) / 2,
             "lng": (ao.get("east", 0) + ao.get("west", 0)) / 2} if ao else {"lat": base_pos["lat"], "lng": base_pos["lng"]}

# ═══════════════════════════════════════════════════════════
#  ENTERPRISE SUBSYSTEMS (conditional)
# ═══════════════════════════════════════════════════════════
cognitive_engine = None
nlp_parser = None
contested_env = None
red_force_ai = None
commander_support = None
learning_engine = None
kill_web = None
threat_predictor = None
wargame_engine = None
swarm_intel = None
isr_pipeline = None
effects_chain = None
space_domain = None
hmt_engine = None
comsec_channel = None
key_mgr = None
security_audit = None

# Bundle 1 — Mission Intelligence Suite
if feature_enabled("cognitive"):
    try:
        from services.cognitive_engine import CognitiveEngine
        cognitive_engine = CognitiveEngine()
    except ImportError:
        pass

if feature_enabled("nlp"):
    try:
        from services.nlp_mission_parser import NLPMissionParser
        nlp_parser = NLPMissionParser(sim_assets)
    except ImportError:
        pass

if feature_enabled("commander"):
    try:
        from services.commander_support import CommanderSupport
        commander_support = CommanderSupport()
    except ImportError:
        pass

if feature_enabled("learning"):
    try:
        from services.learning_engine import LearningEngine
        learning_engine = LearningEngine()
    except ImportError:
        pass

if feature_enabled("redforce"):
    try:
        from services.red_force_ai import RedForceAI
        red_force_ai = RedForceAI(base_pos["lat"], base_pos["lng"])
    except ImportError:
        pass

if feature_enabled("wargame"):
    try:
        from services.wargame_engine import WargameEngine
        wargame_engine = WargameEngine()
    except ImportError:
        pass

if feature_enabled("predictions"):
    try:
        from services.threat_predictor import ThreatPredictor
        threat_predictor = ThreatPredictor()
    except ImportError:
        pass

# Bundle 2 — Advanced Swarm & Autonomy
if feature_enabled("swarm"):
    try:
        from services.swarm_intelligence import SwarmIntelligence
        swarm_intel = SwarmIntelligence()
    except ImportError:
        pass

# Bundle 4 — Secure Operations
ClassificationMarker = None
if feature_enabled("comsec"):
    try:
        from core.comsec import SecureChannel, ClassificationMarker as _CM
        from core.key_manager import KeyManager
        from core.security_audit import SecurityAudit
        ClassificationMarker = _CM
        comsec_channel = SecureChannel(channel_id="AMOS-PRIMARY")
        key_mgr = KeyManager()
        security_audit = SecurityAudit()
    except ImportError:
        pass

# Bundle 6 — Advanced Simulation & Effects
if feature_enabled("contested"):
    try:
        from services.environment_effects import ContestedEnvironment
        contested_env = ContestedEnvironment(base_pos)
    except ImportError:
        pass

if feature_enabled("killweb"):
    try:
        from services.kill_web import KillWeb
        kill_web = KillWeb()
    except ImportError:
        pass

if feature_enabled("isr"):
    try:
        from services.isr_pipeline import ISRPipeline
        isr_pipeline = ISRPipeline()
    except ImportError:
        pass

if feature_enabled("effects"):
    try:
        from services.effects_chain import EffectsChain
        effects_chain = EffectsChain()
    except ImportError:
        pass

if feature_enabled("space"):
    try:
        from services.space_domain import SpaceDomain
        space_domain = SpaceDomain()
    except ImportError:
        pass

if feature_enabled("hmt"):
    try:
        from services.hmt_engine import HMTEngine
        hmt_engine = HMTEngine()
    except ImportError:
        pass

# Drone Reference Database (always loaded — no feature gate)
drone_ref_db = None
try:
    from services.drone_reference import DroneReferenceDB
    drone_ref_db = DroneReferenceDB()
except Exception as e:
    print(f"[AMOS] Drone Reference DB: Not available ({e})")

# Document generators
generate_opord = None
generate_conop = None
if feature_enabled("docs_gen"):
    try:
        from core.docs.opord_generator import generate_opord as _gen_opord
        from core.docs.conop_generator import generate_conop as _gen_conop
        generate_opord = _gen_opord
        generate_conop = _gen_conop
    except ImportError:
        pass

# ═══════════════════════════════════════════════════════════
#  INTEGRATION ADAPTERS (conditional)
# ═══════════════════════════════════════════════════════════
_px4 = None
_px4_ok = False
_tak = None
_link16 = None
_adsb = None
_aprs = None
_ais = None
_lora = None
_remoteid = None
_dragonos = None
_zmeta = None
_cot_receiver = None
_mqtt_adapter = None
_dds_adapter = None
_kafka_adapter = None
_vmf_adapter = None
_stanag4586 = None
_nffi_adapter = None
_ogc_client = None

# Open integrations
try:
    sys.path.insert(0, os.path.join(ROOT_DIR, "integrations"))
    from px4_bridge import PX4Bridge
    _px4 = PX4Bridge()
    _px4_ok = _px4.connect()
    print(f"[AMOS] PX4 SITL: {'Connected' if _px4_ok else 'Offline (standalone mode)'}")
except Exception as e:
    print(f"[AMOS] PX4 SITL: Not available ({e})")

try:
    from integrations.mqtt_adapter import MQTTAdapter
    _mqtt_adapter = MQTTAdapter()
    adapter_mgr.register(_mqtt_adapter)
    print("[AMOS] MQTT Adapter: Registered")
except Exception as e:
    print(f"[AMOS] MQTT Adapter: Not available ({e})")

try:
    from integrations.dds_adapter import DDSAdapter
    _dds_adapter = DDSAdapter()
    adapter_mgr.register(_dds_adapter)
    print("[AMOS] DDS Adapter: Registered")
except Exception as e:
    print(f"[AMOS] DDS Adapter: Not available ({e})")

# Enterprise integrations
if feature_enabled("tak"):
    try:
        from tak_bridge import TAKBridge
        _tak = TAKBridge()
        print("[AMOS] TAK Bridge: Ready")
    except Exception as e:
        print(f"[AMOS] TAK Bridge: Not available ({e})")

if feature_enabled("link16"):
    try:
        from link16_sim import Link16Network
        _link16 = Link16Network(net_id="AMOS-SHADOW-NET")
        print("[AMOS] Link 16: Network initialized")
    except Exception as e:
        print(f"[AMOS] Link 16: Not available ({e})")

# Open sensor bridges (no feature gate — always available)
try:
    from integrations.adsb_receiver import ADSBReceiver
    _adsb = ADSBReceiver()
    print("[AMOS] ADS-B Receiver: Ready")
except Exception as e:
    print(f"[AMOS] ADS-B Receiver: Not available ({e})")

try:
    from integrations.aprs_bridge import APRSBridge
    _aprs = APRSBridge()
    print("[AMOS] APRS Bridge: Ready")
except Exception as e:
    print(f"[AMOS] APRS Bridge: Not available ({e})")

try:
    from integrations.ais_receiver import AISReceiver
    _ais = AISReceiver()
    print("[AMOS] AIS Receiver: Ready")
except Exception as e:
    print(f"[AMOS] AIS Receiver: Not available ({e})")

try:
    from integrations.lora_bridge import LoRaBridge
    _lora = LoRaBridge()
    print("[AMOS] LoRa/Meshtastic: Ready")
except Exception as e:
    print(f"[AMOS] LoRa/Meshtastic: Not available ({e})")

try:
    from integrations.remoteid_bridge import RemoteIDBridge
    _remoteid = RemoteIDBridge()
    print("[AMOS] RemoteID: Ready")
except Exception as e:
    print(f"[AMOS] RemoteID: Not available ({e})")

try:
    from integrations.dragonos_bridge import DragonOSBridge
    _dragonos = DragonOSBridge()
    print("[AMOS] DragonOS/WarDragon: Ready")
except Exception as e:
    print(f"[AMOS] DragonOS/WarDragon: Not available ({e})")

try:
    from integrations.zmeta_bridge import ZMetaBridge
    _zmeta = ZMetaBridge()
    print("[AMOS] ZMeta ISR Metadata: Ready")
except Exception as e:
    print(f"[AMOS] ZMeta ISR Metadata: Not available ({e})")

try:
    from integrations.cot_receiver import CoTReceiver
    _cot_receiver = CoTReceiver()
    print("[AMOS] CoT Receiver: Ready")
except Exception as e:
    print(f"[AMOS] CoT Receiver: Not available ({e})")

try:
    from integrations.sdrpp_bridge import SDRppBridge
    _sdrpp = SDRppBridge()
    print("[AMOS] SDR++ Bridge: Ready")
except Exception as e:
    _sdrpp = None
    print(f"[AMOS] SDR++ Bridge: Not available ({e})")

try:
    from integrations.sigdigger_bridge import SigDiggerBridge
    _sigdigger = SigDiggerBridge()
    print("[AMOS] SigDigger Bridge: Ready")
except Exception as e:
    _sigdigger = None
    print(f"[AMOS] SigDigger Bridge: Not available ({e})")

if feature_enabled("kafka"):
    try:
        from integrations.kafka_adapter import KafkaAdapter
        _kafka_adapter = KafkaAdapter()
        adapter_mgr.register(_kafka_adapter)
        print("[AMOS] Kafka Adapter: Registered")
    except Exception as e:
        print(f"[AMOS] Kafka Adapter: Not available ({e})")

if feature_enabled("vmf"):
    try:
        from integrations.vmf_adapter import VMFAdapter
        _vmf_adapter = VMFAdapter()
        adapter_mgr.register(_vmf_adapter)
        print("[AMOS] VMF Adapter: Registered")
    except Exception as e:
        print(f"[AMOS] VMF Adapter: Not available ({e})")

if feature_enabled("stanag"):
    try:
        from integrations.stanag4586_adapter import STANAG4586Adapter
        _stanag4586 = STANAG4586Adapter()
        adapter_mgr.register(_stanag4586)
        print("[AMOS] STANAG 4586: Registered")
    except Exception as e:
        print(f"[AMOS] STANAG 4586: Not available ({e})")

if feature_enabled("nffi"):
    try:
        from integrations.nffi_adapter import NFFIAdapter
        _nffi_adapter = NFFIAdapter()
        adapter_mgr.register(_nffi_adapter)
        print("[AMOS] NFFI Adapter: Registered")
    except Exception as e:
        print(f"[AMOS] NFFI Adapter: Not available ({e})")

if feature_enabled("ogc"):
    try:
        from integrations.ogc_client import OGCClient
        _ogc_client = OGCClient()
        print("[AMOS] OGC WMS/WFS: Ready")
    except Exception as e:
        print(f"[AMOS] OGC Client: Not available ({e})")

# ═══════════════════════════════════════════════════════════
#  HELPER
# ═══════════════════════════════════════════════════════════
def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ── Startup summary ──
print(f"\n[AMOS] ═══════════════════════════════════════")
print(f"[AMOS]  Assets:     {len(sim_assets)}")
print(f"[AMOS]  Threats:    {len(sim_threats)}")
print(f"[AMOS]  EW-capable: {len(ew_capable)}")
print(f"[AMOS]  Geofences:  {len(geofence_mgr.get_all())}")
print(f"[AMOS]  Users:      {len(USERS)}")
print(f"[AMOS]  ROS 2:      {'Connected' if ros2_bridge.available else 'Standalone'}")
_ent_loaded = [n for n, v in [
    ("cognitive", cognitive_engine), ("nlp", nlp_parser),
    ("commander", commander_support), ("learning", learning_engine),
    ("red_force", red_force_ai), ("wargame", wargame_engine),
    ("swarm", swarm_intel), ("comsec", comsec_channel),
    ("effects", effects_chain), ("isr", isr_pipeline),
    ("space", space_domain), ("hmt", hmt_engine),
    ("killweb", kill_web), ("contested", contested_env),
    ("threat_pred", threat_predictor),
] if v is not None]
print(f"[AMOS]  Edition:    {AMOS_EDITION.upper()}")
print(f"[AMOS]  Enterprise: {len(_ent_loaded)} modules loaded")
if _ent_loaded:
    print(f"[AMOS]              {', '.join(_ent_loaded)}")
print(f"[AMOS] ═══════════════════════════════════════\n")
