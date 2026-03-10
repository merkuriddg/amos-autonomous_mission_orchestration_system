#!/usr/bin/env python3
"""AMOS — Autonomous Mission Orchestration System v5.0
Multi-Domain Autonomous C2 · Modular Blueprint Architecture"""

import os, sys, threading
from flask import request, jsonify

# ── Path setup ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, ROOT_DIR)

# ── Core extensions (creates Flask app + SocketIO) ──
from web.extensions import app, socketio

# ── State & subsystems (must import before blueprints) ──
import web.state  # noqa: F401  — triggers all subsystem instantiation

# ── Register core blueprints ──
from web.routes import register_core_blueprints
register_core_blueprints(app)

# ── Register enterprise blueprints (if edition=enterprise) ──
from web.enterprise import register_enterprise_blueprints
register_enterprise_blueprints(app)

# ── Register WebSocket handlers ──
from web.websockets import register_websockets
register_websockets(socketio)

# ── Simulation engine (background thread) ──
from web.simulation_engine import sim_tick

# ── Phase 3: Live document generators ──
try:
    sys.path.insert(0, BASE_DIR)
    from phase3_routes import phase3_bp, init_phase3
    from web.state import sim_assets, sim_threats

    def _amos_state_getter():
        g = globals()
        state = {}
        for aname in ['assets', 'ASSETS', 'asset_registry', 'platoon_assets', 'sim_assets']:
            if aname in g and g[aname]:
                state['assets'] = g[aname]; break
        state.setdefault('assets', sim_assets)
        for tname in ['threats', 'THREATS', 'sim_threats', 'threat_list']:
            if tname in g and g[tname]:
                state['threats'] = g[tname]; break
        state.setdefault('threats', sim_threats)
        return state

    init_phase3(_amos_state_getter)
    app.register_blueprint(phase3_bp)
    print("[AMOS] Phase 3 routes registered")
except Exception as _e:
    print(f"[AMOS] Phase 3 warning: {_e}")


# ═══════════════════════════════════════════════════════════
#  ERROR HANDLERS
# ═══════════════════════════════════════════════════════════
@app.errorhandler(500)
def internal_error(e):
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": str(e)}), 500
    return str(e), 500

@app.errorhandler(404)
def not_found_error(e):
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": "endpoint not found"}), 404
    return str(e), 404


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    from web.state import (
        adapter_mgr, plugin_loader, event_bus,
        comsec_channel, USERS, db_check, AMOS_EDITION,
    )

    threading.Thread(target=sim_tick, daemon=True, name="sim_tick").start()

    db_ok = "✓ Connected" if db_check() else "✗ Offline"
    adapter_count = len(adapter_mgr.get_all_status())
    ps = plugin_loader.registry.get_summary()
    comsec_str = comsec_channel.get_status()["cipher"] if comsec_channel else "N/A (open edition)"

    print("\n" + "=" * 58)
    print("  AMOS — Autonomous Mission Orchestration System v5.0")
    print(f"  Edition: {AMOS_EDITION.upper()}")
    print("  http://localhost:2600")
    print(f"  Database: {db_ok}")
    print(f"  Adapters: {adapter_count} registered")
    print(f"  Plugins:  {ps['active']} active / {ps['total']} discovered")
    print(f"  EventBus: {event_bus.get_stats()['subscribers']} subscribers")
    print(f"  COMSEC:   {comsec_str}")
    print("-" * 58)
    for u, i in USERS.items():
        print(f"  {u:12s} [{i.get('role','')}]")
    print("=" * 58 + "\n")

    socketio.run(app, host="0.0.0.0", port=2600, allow_unsafe_werkzeug=True)
