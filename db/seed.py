#!/usr/bin/env python3
"""AMOS Database Seed Script
Populates users, assets, threats, and theaters from config files."""

import os, sys, json, yaml
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash
from db.connection import execute, executemany, fetchone, table_count, to_json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "platoon_config.yaml")
LOCATIONS_PATH = os.path.join(ROOT, "config", "locations.json")

# ── Load config ─────────────────────────────────────────
with open(CONFIG_PATH) as f:
    config = yaml.safe_load(f)

platoon = config["platoon"]
base_pos = platoon["base"]

# ── Users (from hardcoded USERS dict) ───────────────────
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


def seed_users():
    if table_count("users") > 0:
        print(f"  [users] Already seeded ({table_count('users')} rows), skipping")
        return
    for username, info in USERS.items():
        execute(
            """INSERT INTO users (username, password_hash, name, role, domain, access)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (username, generate_password_hash(info["password"]),
             info["name"], info["role"], info["domain"], to_json(info["access"]))
        )
    print(f"  [users] Seeded {len(USERS)} users")


def seed_assets():
    if table_count("assets") > 0:
        print(f"  [assets] Already seeded ({table_count('assets')} rows), skipping")
        return
    assets = config.get("assets", [])
    for a in assets:
        sp = a.get("spawn", {})
        execute(
            """INSERT INTO assets (asset_id, type, domain, role, autonomy_tier,
               sensors, weapons, endurance_hr, lat, lng, alt_ft)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (a["id"], a.get("type",""), a.get("domain","ground"), a.get("role","recon"),
             a.get("autonomy_tier", 2),
             to_json(a.get("sensors", [])), to_json(a.get("weapons", [])),
             a.get("endurance_hr", 0),
             sp.get("lat", base_pos["lat"]), sp.get("lng", base_pos["lng"]),
             sp.get("alt_ft", 0))
        )
    print(f"  [assets] Seeded {len(assets)} assets")


def seed_threats():
    if table_count("threats") > 0:
        print(f"  [threats] Already seeded ({table_count('threats')} rows), skipping")
        return
    threats = config.get("threats", [])
    for t in threats:
        execute(
            """INSERT INTO threats (threat_id, type, lat, lng, speed_kts)
               VALUES (%s, %s, %s, %s, %s)""",
            (t["id"], t.get("type",""), t.get("lat"), t.get("lng"),
             t.get("speed_kts", 0))
        )
    print(f"  [threats] Seeded {len(threats)} threats")


def seed_theaters():
    if table_count("theaters") > 0:
        print(f"  [theaters] Already seeded ({table_count('theaters')} rows), skipping")
        return
    try:
        with open(LOCATIONS_PATH) as f:
            loc_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("  [theaters] No locations.json found, skipping")
        return
    active = loc_data.get("active", "")
    for key, loc in loc_data.get("locations", {}).items():
        ao = loc.get("ao", {})
        execute(
            """INSERT INTO theaters (theater_key, name, lat, lng,
               ao_north, ao_south, ao_east, ao_west, zoom, description, active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (key, loc.get("name", key), loc.get("lat", 0), loc.get("lng", 0),
             ao.get("north"), ao.get("south"), ao.get("east"), ao.get("west"),
             loc.get("zoom", 10), loc.get("description", ""),
             1 if key == active else 0)
        )
    print(f"  [theaters] Seeded {len(loc_data.get('locations', {}))} theaters")


if __name__ == "__main__":
    print("AMOS Database Seed")
    print("=" * 40)
    seed_users()
    seed_assets()
    seed_threats()
    seed_theaters()
    print("=" * 40)
    print("Done!")
