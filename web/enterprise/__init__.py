"""AMOS Enterprise Route Blueprints.

Registers the enterprise API blueprint providing REST access to all
enterprise subsystems (cognitive engine, wargame, swarm intel, ISR,
effects chain, space domain, HMT, kill web, etc.).
"""


def register_enterprise_blueprints(app):
    """Register enterprise blueprints with dual API mount."""
    try:
        from web.enterprise.routes import bp as enterprise_bp
        app.register_blueprint(enterprise_bp, url_prefix="/api/v1", name="enterprise_v1")
        app.register_blueprint(enterprise_bp, url_prefix="/api", name="enterprise_compat")
        print("[AMOS] Enterprise blueprints: Registered (80+ endpoints)")
    except Exception as e:
        print(f"[AMOS] Enterprise blueprints: Not available ({e})")
