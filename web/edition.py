"""AMOS Edition & Feature Flags.

Controls which modules and routes are active based on:
  - AMOS_EDITION env var: "open" (default) or "enterprise"
  - Per-feature overrides: AMOS_ENABLE_<FEATURE>=true/false
"""

import os

AMOS_EDITION = os.environ.get("AMOS_EDITION", "open").lower()

# ── Per-feature defaults (enterprise = all on, open = all off) ──
_ENT = AMOS_EDITION == "enterprise"

FEATURES = {
    # Bundle 1 — Mission Intelligence Suite
    "cognitive":    os.environ.get("AMOS_ENABLE_COGNITIVE", str(_ENT)).lower() == "true",
    "nlp":          os.environ.get("AMOS_ENABLE_NLP", str(_ENT)).lower() == "true",
    "coa":          os.environ.get("AMOS_ENABLE_COA", str(_ENT)).lower() == "true",
    "commander":    os.environ.get("AMOS_ENABLE_COMMANDER", str(_ENT)).lower() == "true",
    "learning":     os.environ.get("AMOS_ENABLE_LEARNING", str(_ENT)).lower() == "true",
    "hal":          os.environ.get("AMOS_ENABLE_HAL", str(_ENT)).lower() == "true",
    "predictions":  os.environ.get("AMOS_ENABLE_PREDICTIONS", str(_ENT)).lower() == "true",
    "wargame":      os.environ.get("AMOS_ENABLE_WARGAME", str(_ENT)).lower() == "true",
    "redforce":     os.environ.get("AMOS_ENABLE_REDFORCE", str(_ENT)).lower() == "true",
    "docs_gen":     os.environ.get("AMOS_ENABLE_DOCS_GEN", str(_ENT)).lower() == "true",

    # Bundle 2 — Advanced Swarm & Autonomy Suite
    "swarm":        os.environ.get("AMOS_ENABLE_SWARM", str(_ENT)).lower() == "true",
    "autonomy":     os.environ.get("AMOS_ENABLE_AUTONOMY", str(_ENT)).lower() == "true",

    # Bundle 3 — (merged into 1 above)

    # Bundle 4 — Secure Operations Suite
    "comsec":       os.environ.get("AMOS_ENABLE_COMSEC", str(_ENT)).lower() == "true",
    "security":     os.environ.get("AMOS_ENABLE_SECURITY", str(_ENT)).lower() == "true",

    # Bundle 5 — Defense Integration Suite
    "tak":          os.environ.get("AMOS_ENABLE_TAK", str(_ENT)).lower() == "true",
    "link16":       os.environ.get("AMOS_ENABLE_LINK16", str(_ENT)).lower() == "true",
    "vmf":          os.environ.get("AMOS_ENABLE_VMF", str(_ENT)).lower() == "true",
    "stanag":       os.environ.get("AMOS_ENABLE_STANAG", str(_ENT)).lower() == "true",
    "nffi":         os.environ.get("AMOS_ENABLE_NFFI", str(_ENT)).lower() == "true",
    "ogc":          os.environ.get("AMOS_ENABLE_OGC", str(_ENT)).lower() == "true",
    "kafka":        os.environ.get("AMOS_ENABLE_KAFKA", str(_ENT)).lower() == "true",

    # Bundle 6 — Advanced Simulation & Effects Suite
    "effects":      os.environ.get("AMOS_ENABLE_EFFECTS", str(_ENT)).lower() == "true",
    "isr":          os.environ.get("AMOS_ENABLE_ISR", str(_ENT)).lower() == "true",
    "space":        os.environ.get("AMOS_ENABLE_SPACE", str(_ENT)).lower() == "true",
    "hmt":          os.environ.get("AMOS_ENABLE_HMT", str(_ENT)).lower() == "true",
    "killweb":      os.environ.get("AMOS_ENABLE_KILLWEB", str(_ENT)).lower() == "true",
    "ew":           os.environ.get("AMOS_ENABLE_EW", str(_ENT)).lower() == "true",
    "sigint":       os.environ.get("AMOS_ENABLE_SIGINT", str(_ENT)).lower() == "true",
    "cyber":        os.environ.get("AMOS_ENABLE_CYBER", str(_ENT)).lower() == "true",
    "contested":    os.environ.get("AMOS_ENABLE_CONTESTED", str(_ENT)).lower() == "true",
}


def is_enterprise():
    """True if running enterprise edition."""
    return AMOS_EDITION == "enterprise"


def feature_enabled(name):
    """Check if a specific feature is enabled."""
    return FEATURES.get(name, is_enterprise())
