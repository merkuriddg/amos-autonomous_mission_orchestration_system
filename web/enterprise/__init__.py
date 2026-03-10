"""AMOS Enterprise Route Blueprints.

Gated by AMOS_EDITION: only registers when edition is 'enterprise'.
In open-core mode, enterprise APIs simply don't exist (404).
"""

from web.edition import is_enterprise


def register_enterprise_blueprints(app):
    """Register enterprise blueprints (only when AMOS_EDITION=enterprise)."""
    if not is_enterprise():
        print("[AMOS] Edition: OPEN — enterprise blueprints skipped")
        return

    print("[AMOS] Edition: ENTERPRISE — loading enterprise blueprints")

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
