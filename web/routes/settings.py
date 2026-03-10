"""AMOS Settings Routes — Locations, Users, Profile, System."""

import time
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash

from web.extensions import login_required, ctx, load_locations, save_locations
from web.state import (USERS, DB_AUTH, base_pos, sim_assets, sim_threats, ew_capable,
                       sim_clock, ros2_bridge, db_execute, to_json, from_json)

bp = Blueprint("settings", __name__)


# ═══════════════════════════════════════════════════════════
#  LOCATIONS
# ═══════════════════════════════════════════════════════════
@bp.route("/settings/locations")
@login_required
def api_settings_locations():
    return jsonify(load_locations())


@bp.route("/settings/locations/save", methods=["POST"])
@login_required
def api_settings_locations_save():
    d = request.json
    data = load_locations()
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
    save_locations(data)
    return jsonify({"status": "ok", "locations": data})


@bp.route("/settings/locations/delete", methods=["POST"])
@login_required
def api_settings_locations_delete():
    key = request.json.get("key", "")
    data = load_locations()
    if key in data["locations"]:
        del data["locations"][key]
        if data["active"] == key:
            data["active"] = next(iter(data["locations"]), "")
        save_locations(data)
    return jsonify({"status": "ok", "locations": data})


@bp.route("/settings/locations/activate", methods=["POST"])
@login_required
def api_settings_locations_activate():
    key = request.json.get("key", "")
    data = load_locations()
    if key not in data["locations"]:
        return jsonify({"error": "Location not found"}), 404
    data["active"] = key
    loc = data["locations"][key]
    base_pos["lat"] = loc["lat"]
    base_pos["lng"] = loc["lng"]
    base_pos["name"] = loc["name"]
    save_locations(data)
    return jsonify({"status": "ok", "active": key, "location": loc,
                    "note": "Map center updated. Full scenario reload requires server restart."})


# ═══════════════════════════════════════════════════════════
#  PASSWORD & PROFILE
# ═══════════════════════════════════════════════════════════
@bp.route("/settings/password", methods=["POST"])
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
    if DB_AUTH:
        new_hash = generate_password_hash(new_pw)
        usr["password_hash"] = new_hash
        db_execute("UPDATE users SET password_hash=%s WHERE username=%s", (new_hash, u))
    else:
        usr["password"] = new_pw
    return jsonify({"status": "ok"})


@bp.route("/settings/profile", methods=["POST"])
@login_required
def api_settings_profile():
    d = request.json
    u = session.get("user")
    usr = USERS.get(u)
    if not usr:
        return jsonify({"error": "User not found"}), 404
    if d.get("name"):
        usr["name"] = d["name"].strip()
        if DB_AUTH:
            db_execute("UPDATE users SET name=%s WHERE username=%s", (usr["name"], u))
    return jsonify({"status": "ok", "name": usr["name"], "role": usr["role"]})


@bp.route("/settings/system")
@login_required
def api_settings_system():
    loc_data = load_locations()
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
#  USER CRUD (Admin)
# ═══════════════════════════════════════════════════════════
@bp.route("/settings/users")
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


@bp.route("/settings/users/create", methods=["POST"])
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


@bp.route("/settings/users/update", methods=["POST"])
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


@bp.route("/settings/users/delete", methods=["POST"])
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
