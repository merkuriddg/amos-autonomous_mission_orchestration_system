"""AMOS Enterprise Route Blueprints.

Always registered — individual routes guard themselves with 'if not subsystem' checks.
When the open-core/enterprise split ships, gate registration via is_enterprise().
"""


def register_enterprise_blueprints(app):
    """Register all enterprise blueprints."""

    try:
        from web.enterprise.intelligence import bp as intel_bp
        app.register_blueprint(intel_bp)
    except Exception as e:
        print(f"[AMOS] Enterprise intelligence warning: {e}")

    try:
        from web.enterprise.warfare import bp as warfare_bp
        app.register_blueprint(warfare_bp)
    except Exception as e:
        print(f"[AMOS] Enterprise warfare warning: {e}")

    try:
        from web.enterprise.security import bp as security_bp
        app.register_blueprint(security_bp)
    except Exception as e:
        print(f"[AMOS] Enterprise security warning: {e}")

    try:
        from web.enterprise.defense import bp as defense_bp
        app.register_blueprint(defense_bp)
    except Exception as e:
        print(f"[AMOS] Enterprise defense warning: {e}")
