"""AMOS Edition Service — abstraction layer for feature flag management.

Routes never mutate the FEATURES dict directly. All changes go through
this service layer which provides: validation, audit hooks, and
future persistence support.

Edition (open/enterprise) is NOT switchable at runtime — only feature
flags within the loaded edition can be toggled.
"""

from web.edition import FEATURES, AMOS_EDITION, is_enterprise, feature_enabled

# ── Bundle definitions (feature groupings with metadata) ──
BUNDLES = {
    "mission_intelligence": {
        "name": "Mission Intelligence Suite",
        "description": "Cognitive engine, NLP, COA generation, commander support, learning",
        "features": ["cognitive", "nlp", "coa", "commander", "learning", "hal",
                     "predictions", "wargame", "redforce", "docs_gen"],
    },
    "swarm_autonomy": {
        "name": "Advanced Swarm & Autonomy Suite",
        "description": "Swarm intelligence, autonomous behaviors",
        "features": ["swarm", "autonomy"],
    },
    "secure_ops": {
        "name": "Secure Operations Suite",
        "description": "COMSEC encryption, security audit logging",
        "features": ["comsec", "security"],
    },
    "defense_integration": {
        "name": "Defense Integration Suite",
        "description": "TAK, Link-16, VMF, STANAG, NFFI, OGC, Kafka bridges",
        "features": ["tak", "link16", "vmf", "stanag", "nffi", "ogc", "kafka"],
    },
    "simulation_effects": {
        "name": "Advanced Simulation & Effects Suite",
        "description": "Effects chain, ISR/ATR, space/JADC2, HMT, kill web, EW, SIGINT, cyber, contested ops",
        "features": ["effects", "isr", "space", "hmt", "killweb", "ew", "sigint", "cyber", "contested"],
    },
}

# Features that require restart when toggled (blueprints need re-registration)
_RESTART_REQUIRED = {"comsec", "security", "tak", "link16", "vmf", "stanag", "nffi", "ogc", "kafka"}


def current_state():
    """Return current edition and all feature flag states."""
    return {
        "edition": AMOS_EDITION,
        "is_enterprise": is_enterprise(),
        "features": {name: {"enabled": val, "restart_required": name in _RESTART_REQUIRED}
                     for name, val in FEATURES.items()},
        "total_features": len(FEATURES),
        "enabled_count": sum(1 for v in FEATURES.values() if v),
    }


def set_feature(name, enabled):
    """Toggle a feature flag at runtime.

    Returns (success, message) tuple.
    Only allows toggling features that exist and are runtime-safe.
    """
    if name not in FEATURES:
        return False, f"Unknown feature: {name}"

    if name in _RESTART_REQUIRED:
        return False, f"Feature '{name}' requires restart to change. Update env and restart."

    FEATURES[name] = bool(enabled)
    return True, f"Feature '{name}' {'enabled' if enabled else 'disabled'}"


def is_safe_toggle(name):
    """Check if a feature can be toggled without restart."""
    if name not in FEATURES:
        return False
    return name not in _RESTART_REQUIRED


def list_bundles():
    """Return feature bundles with current status for each feature."""
    result = []
    for bundle_id, bundle in BUNDLES.items():
        features = []
        for fname in bundle["features"]:
            features.append({
                "name": fname,
                "enabled": FEATURES.get(fname, False),
                "restart_required": fname in _RESTART_REQUIRED,
                "safe_toggle": fname not in _RESTART_REQUIRED,
            })
        enabled_count = sum(1 for f in features if f["enabled"])
        result.append({
            "id": bundle_id,
            "name": bundle["name"],
            "description": bundle["description"],
            "features": features,
            "enabled_count": enabled_count,
            "total_count": len(features),
        })
    return result
