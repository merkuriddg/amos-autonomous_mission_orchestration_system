"""AMOS Core Route Blueprints — register_core_blueprints() wires all into the Flask app.

API Versioning Strategy:
  - API blueprints are mounted at /api/v1 (primary) and /api (deprecated).
  - Pages and auth remain at root (no version prefix).
  - Deprecated /api routes include Deprecation headers.
"""

from web.routes.auth import bp as auth_bp
from web.routes.pages import bp as pages_bp
from web.routes.settings import bp as settings_bp
from web.routes.assets import bp as assets_bp
from web.routes.missions import bp as missions_bp
from web.routes.simulation import bp as simulation_bp
from web.routes.sensors import bp as sensors_bp
from web.routes.ops import bp as ops_bp
from web.routes.plugins import bp as plugins_bp
from web.routes.scripts import bp as scripts_bp
from web.routes.edition_mgmt import bp as edition_mgmt_bp

# API blueprints — mounted with url_prefix
_API_BLUEPRINTS = [
    (settings_bp, "settings"),
    (assets_bp, "assets"),
    (missions_bp, "missions"),
    (simulation_bp, "simulation"),
    (sensors_bp, "sensors"),
    (ops_bp, "ops"),
    (plugins_bp, "plugins"),
    (scripts_bp, "scripts"),
    (edition_mgmt_bp, "edition_mgmt"),
]


def register_core_blueprints(app):
    """Register all core AMOS blueprints with the Flask app."""
    # Non-API blueprints (no version prefix)
    app.register_blueprint(auth_bp)
    app.register_blueprint(pages_bp)

    # API blueprints — dual-mount at /api/v1 (primary) and /api (deprecated)
    for bp, name in _API_BLUEPRINTS:
        app.register_blueprint(bp, url_prefix="/api/v1", name=f"{name}_v1")
        app.register_blueprint(bp, url_prefix="/api", name=f"{name}_compat")
