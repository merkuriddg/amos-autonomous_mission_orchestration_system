"""AMOS Auto-Generated OpenAPI 3.0 Spec + Swagger UI.

Introspects all registered Flask routes and emits an OpenAPI 3.0 JSON
spec.  Serves interactive docs at ``/api/docs`` via Swagger-UI CDN.
"""

import re
from flask import Blueprint, jsonify, render_template_string

bp = Blueprint("swagger", __name__)

# ── Swagger-UI HTML (loaded from CDN) ──────────────────────

_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AMOS API Documentation</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
<style>
  body { margin:0; background:#0a0e14; }
  .swagger-ui .topbar { display:none; }
  .swagger-ui { max-width:1200px; margin:auto; }
  /* match AMOS dark theme */
  .swagger-ui, .swagger-ui .info .title,
  .swagger-ui .opblock-tag { color:#e0e0e0; }
  .swagger-ui .scheme-container { background:#111820; }
  #amos-header {
    background:linear-gradient(135deg,#0a0e14 0%,#111820 100%);
    color:#00ff41; text-align:center; padding:16px 0 8px;
    font-family:'Courier New',monospace;
  }
  #amos-header h1 { margin:0; font-size:1.4rem; }
  #amos-header p  { margin:4px 0 0; font-size:.85rem; color:#888; }
</style>
</head>
<body>
<div id="amos-header">
  <h1>AMOS — API Documentation</h1>
  <p>Autonomous Mission Orchestration System &middot; OpenAPI 3.0</p>
</div>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
SwaggerUIBundle({
  url: '/api/v1/openapi.json',
  dom_id: '#swagger-ui',
  deepLinking: true,
  layout: 'BaseLayout',
  defaultModelsExpandDepth: -1,
  docExpansion: 'list',
  filter: true,
  tryItOutEnabled: true,
});
</script>
</body>
</html>"""


# ── Helpers ────────────────────────────────────────────────

_FLASK_TO_OA = re.compile(r"<(?:\w+:)?(\w+)>")  # <int:id> → {id}

# Map route prefix segments → OpenAPI tags
_TAG_MAP = {
    "assets":     "Assets",
    "missions":   "Missions",
    "simulation": "Simulation",
    "settings":   "Settings",
    "sensors":    "Sensors",
    "ops":        "Operations",
    "plugins":    "Plugins",
    "scripts":    "System Scripts",
    "edition":    "Edition Management",
    "auth":       "Authentication",
    "waypoints":  "Missions",
    "geofences":  "Missions",
    "voice":      "Missions",
    "tasks":      "Missions",
    "training":   "Missions",
    "missionplan":"Missions",
    "threats":    "Operations",
    "alerts":     "Operations",
    "ew":         "Electronic Warfare",
    "killchain":  "Operations",
    "aar":        "Operations",
    "cyber":      "Operations",
    "metrics":    "Operations",
    "comms":      "Operations",
    "swarm":      "Simulation",
    "adapters":   "Operations",
    "events":     "Operations",
    "hal":        "Operations",
    "link16":     "Operations",
    "integrations":"Operations",
    "mobile":     "Mobile UI",
}


def _tag_for(rule_str: str) -> str:
    """Guess an OpenAPI tag from the URL rule string."""
    parts = rule_str.strip("/").split("/")
    for p in parts:
        if p in ("api", "v1", ""):
            continue
        clean = p.lower().rstrip("s").replace("_", "")
        for key, tag in _TAG_MAP.items():
            if key.startswith(clean) or clean.startswith(key.rstrip("s")):
                return tag
        # Fallback to capitalised segment
        return p.replace("_", " ").title()
    return "General"


def _flask_to_openapi_path(rule_str: str) -> str:
    """Convert Flask ``<int:id>`` style params to ``{id}``."""
    return _FLASK_TO_OA.sub(r"{\1}", rule_str)


def _params_from_rule(rule) -> list[dict]:
    """Extract path parameters from a Flask rule."""
    params = []
    for match in _FLASK_TO_OA.finditer(rule.rule):
        name = match.group(1)
        params.append({
            "name": name,
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        })
    return params


def _build_spec(app) -> dict:
    """Walk every registered Flask rule and emit an OpenAPI 3.0 dict."""
    paths: dict = {}
    seen_tags: set = set()

    ignored_prefixes = ("/static", "/socket.io")
    ignored_endpoints = {"static", "swagger.openapi_spec", "swagger.swagger_ui"}

    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        if any(rule.rule.startswith(p) for p in ignored_prefixes):
            continue
        if rule.endpoint in ignored_endpoints:
            continue
        # Skip HEAD-only duplicates
        methods = sorted(rule.methods - {"OPTIONS", "HEAD"})
        if not methods:
            continue

        oa_path = _flask_to_openapi_path(rule.rule)
        tag = _tag_for(rule.rule)
        seen_tags.add(tag)
        params = _params_from_rule(rule)

        for method in methods:
            op: dict = {
                "tags": [tag],
                "summary": rule.endpoint.replace("_", " ").replace(".", " › ").title(),
                "operationId": f"{method.lower()}_{rule.endpoint.replace('.', '_')}",
                "responses": {
                    "200": {"description": "Success"},
                    "401": {"description": "Not authenticated"},
                },
            }
            if params:
                op["parameters"] = params
            if method in ("POST", "PUT", "PATCH"):
                op["requestBody"] = {
                    "content": {"application/json": {"schema": {"type": "object"}}},
                    "required": False,
                }

            paths.setdefault(oa_path, {})[method.lower()] = op

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "AMOS — Autonomous Mission Orchestration System",
            "version": "5.0.0",
            "description": (
                "Multi-domain autonomous C2 platform API.  Provides "
                "asset management, mission planning, sensor fusion, "
                "electronic warfare, cyber ops, and plugin management."
            ),
            "contact": {"name": "Merkuri DG", "url": "https://github.com/merkuriddg/amos-autonomous_mission_orchestration_system"},
            "license": {"name": "MIT"},
        },
        "servers": [
            {"url": "/api/v1", "description": "Primary (v1)"},
            {"url": "/api", "description": "Compat (deprecated)"},
        ],
        "tags": sorted(
            [{"name": t} for t in seen_tags],
            key=lambda t: t["name"],
        ),
        "paths": paths,
    }


# ── Routes ─────────────────────────────────────────────────

@bp.route("/api/v1/openapi.json")
def openapi_spec():
    """Return the auto-generated OpenAPI 3.0 JSON spec."""
    from flask import current_app
    spec = _build_spec(current_app)
    return jsonify(spec)


@bp.route("/api/docs")
def swagger_ui():
    """Serve interactive Swagger UI."""
    return _SWAGGER_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}
