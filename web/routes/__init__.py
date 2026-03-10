"""AMOS Core Route Blueprints — register_core_blueprints() wires all into the Flask app."""

from web.routes.auth import bp as auth_bp
from web.routes.pages import bp as pages_bp
from web.routes.settings import bp as settings_bp
from web.routes.assets import bp as assets_bp
from web.routes.missions import bp as missions_bp
from web.routes.simulation import bp as simulation_bp
from web.routes.sensors import bp as sensors_bp
from web.routes.ops import bp as ops_bp
from web.routes.plugins import bp as plugins_bp


def register_core_blueprints(app):
    """Register all core AMOS blueprints with the Flask app."""
    for bp in (
        auth_bp,
        pages_bp,
        settings_bp,
        assets_bp,
        missions_bp,
        simulation_bp,
        sensors_bp,
        ops_bp,
        plugins_bp,
    ):
        app.register_blueprint(bp)
