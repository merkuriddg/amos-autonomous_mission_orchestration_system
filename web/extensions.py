"""AMOS Flask Application & Shared Helpers.

Creates the Flask app, SocketIO instance, and shared decorators/utilities
used across all route blueprints.
"""

import os, json, time, yaml
from functools import wraps
from flask import Flask, request, redirect, url_for, session
from flask_socketio import SocketIO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

# ── Flask app ──
app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"))
app.secret_key = os.environ.get("MOS_SECRET", "mos-shadow-forge-2026")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── Config paths ──
CONFIG_PATH = os.path.join(ROOT_DIR, "config", "platoon_config.yaml")
LOCATIONS_PATH = os.path.join(ROOT_DIR, "config", "locations.json")

# ── Load platoon config ──
with open(CONFIG_PATH) as f:
    config = yaml.safe_load(f)
platoon = config["platoon"]
base_pos = platoon["base"]


# ── API metrics (shared) ──
api_metrics = {"requests": 0, "errors": 0, "by_endpoint": {}, "start_time": time.time()}


@app.before_request
def _track_request_start():
    """Track request start time for API metrics."""
    request._amos_start = time.time()


@app.after_request
def _add_no_cache(response):
    """Prevent browser caching during development + track API metrics."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    if request.path.startswith("/api/"):
        ep = request.path
        api_metrics["requests"] += 1
        if response.status_code >= 400:
            api_metrics["errors"] += 1
        if ep not in api_metrics["by_endpoint"]:
            api_metrics["by_endpoint"][ep] = {"count": 0, "errors": 0, "total_ms": 0}
        m = api_metrics["by_endpoint"][ep]
        m["count"] += 1
        if response.status_code >= 400:
            m["errors"] += 1
        elapsed_ms = (time.time() - getattr(request, '_amos_start', time.time())) * 1000
        m["total_ms"] += elapsed_ms
    return response


# ── Auth decorator ──
def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if "user" not in session:
            return redirect(url_for("auth.login"))
        return f(*a, **kw)
    return dec


# ── Template context helper ──
def ctx():
    from web.state import USERS
    u = session.get("user", "unknown")
    d = USERS.get(u, {})
    return {"user": u, "role": d.get("role", ""), "name": d.get("name", u),
            "domain": d.get("domain", "all"), "access": d.get("access", [])}


# ── Location persistence helpers ──
def load_locations():
    """Load saved locations from JSON file."""
    try:
        with open(LOCATIONS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"active": "", "locations": {}}


def save_locations(data):
    """Persist locations to JSON file."""
    with open(LOCATIONS_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ── Audit helper ──
def _audit(user, action, target_type=None, target_id=None, detail=None):
    """Write an audit log entry to the database."""
    from db.connection import execute as db_execute, to_json
    try:
        ip = request.remote_addr if request else None
        db_execute(
            "INSERT INTO audit_log (user, action, target_type, target_id, detail, ip) VALUES(%s,%s,%s,%s,%s,%s)",
            (user, action, target_type, target_id, to_json(detail) if detail else None, ip))
    except Exception:
        pass


@app.after_request
def _audit_writes(response):
    """Auto-audit all POST/DELETE API calls."""
    if request.method in ("POST", "DELETE") and request.path.startswith("/api/"):
        u = session.get("user", "anonymous")
        _audit(u, f"{request.method} {request.path}", detail=request.get_json(silent=True))
    return response
