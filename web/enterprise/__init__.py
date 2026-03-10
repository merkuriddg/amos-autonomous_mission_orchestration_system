"""AMOS Enterprise Route Blueprints.

Gated by AMOS_EDITION: only registers when edition is 'enterprise'.
In open-core mode, enterprise APIs simply don't exist (404).
"""

from web.edition import is_enterprise


def _register_dual(app, bp, name):
    """Register a blueprint at both /api/v1 (primary) and /api (deprecated)."""
    app.register_blueprint(bp, url_prefix="/api/v1", name=f"{name}_v1")
    app.register_blueprint(bp, url_prefix="/api", name=f"{name}_compat")


def register_enterprise_blueprints(app):
    """Register enterprise blueprints (only when AMOS_EDITION=enterprise)."""
    if not is_enterprise():
        print("[AMOS] Edition: OPEN — enterprise blueprints skipped")
        return

    print("[AMOS] Edition: ENTERPRISE — loading enterprise blueprints")

    try:
        from web.enterprise.intelligence import bp as intel_bp
        _register_dual(app, intel_bp, "ent_intelligence")
    except Exception as e:
        print(f"[AMOS] Enterprise intelligence warning: {e}")

    try:
        from web.enterprise.warfare import bp as warfare_bp
        _register_dual(app, warfare_bp, "ent_warfare")
    except Exception as e:
        print(f"[AMOS] Enterprise warfare warning: {e}")

    try:
        from web.enterprise.security import bp as security_bp
        _register_dual(app, security_bp, "ent_security")
    except Exception as e:
        print(f"[AMOS] Enterprise security warning: {e}")

    try:
        from web.enterprise.defense import bp as defense_bp
        _register_dual(app, defense_bp, "ent_defense")
    except Exception as e:
        print(f"[AMOS] Enterprise defense warning: {e}")
