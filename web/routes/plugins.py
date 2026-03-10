"""AMOS Plugin Routes — Adapters, Plugins, Event Bus, Integration Hub."""

from flask import Blueprint, request, jsonify, session
from web.extensions import login_required, ctx
from web.state import (
    adapter_mgr, plugin_loader, event_bus,
    video_pipeline, imagery_handler,
    comsec_channel, key_mgr, security_audit,
    _ogc_client,
)

bp = Blueprint("plugins", __name__)


# ═══════════════════════════════════════════════════════════
#  ADAPTER MANAGER
# ═══════════════════════════════════════════════════════════
@bp.route("/adapters/status")
@login_required
def api_adapters_status():
    return jsonify(adapter_mgr.get_all_status())

@bp.route("/adapters/connect", methods=["POST"])
@login_required
def api_adapters_connect():
    d = request.json or {}
    aid = d.get("adapter_id", "")
    ok = adapter_mgr.connect_adapter(aid)
    security_audit.log_config("ADAPTER_CONNECT", session.get("user", "unknown"), aid)
    return jsonify({"adapter_id": aid, "connected": ok})

@bp.route("/adapters/disconnect", methods=["POST"])
@login_required
def api_adapters_disconnect():
    d = request.json or {}
    aid = d.get("adapter_id", "")
    ok = adapter_mgr.disconnect_adapter(aid)
    return jsonify({"adapter_id": aid, "disconnected": ok})


# ═══════════════════════════════════════════════════════════
#  INTEGRATION HUB
# ═══════════════════════════════════════════════════════════
@bp.route("/integration/hub")
@login_required
def api_integration_hub():
    """Aggregate status for the Integration Hub dashboard."""
    return jsonify({
        "adapters": adapter_mgr.get_all_status(),
        "video": video_pipeline.get_stats(),
        "imagery": imagery_handler.get_stats(),
        "comsec": comsec_channel.get_status(),
        "keys": key_mgr.get_status(),
        "audit": security_audit.get_status(),
        "ogc": _ogc_client.get_status() if _ogc_client else {},
        "plugins": plugin_loader.registry.get_summary(),
    })


# ═══════════════════════════════════════════════════════════
#  PLUGIN APIs
# ═══════════════════════════════════════════════════════════
@bp.route("/plugins")
@login_required
def api_plugins():
    """List all plugins with status."""
    return jsonify({
        "plugins": plugin_loader.registry.get_all_status(),
        "summary": plugin_loader.registry.get_summary(),
        "capabilities": plugin_loader.get_capability_registry(),
    })

@bp.route("/plugins/<name>")
@login_required
def api_plugin_detail(name):
    """Get detailed status for a single plugin."""
    status = plugin_loader.registry.get_plugin_status(name)
    if status:
        return jsonify(status)
    return jsonify({"error": f"Plugin '{name}' not found"}), 404

@bp.route("/plugins/health")
@login_required
def api_plugins_health():
    """Health check across all plugins."""
    return jsonify(plugin_loader.registry.health_check_all())


# ═══════════════════════════════════════════════════════════
#  EVENT BUS
# ═══════════════════════════════════════════════════════════
@bp.route("/events/recent")
@login_required
def api_events_recent():
    """Return recent events from the event bus."""
    topic = request.args.get("topic")
    limit = request.args.get("limit", 50, type=int)
    return jsonify({
        "events": event_bus.get_history(topic=topic, limit=limit),
        "stats": event_bus.get_stats(),
        "topics": event_bus.get_topics(),
    })

@bp.route("/events/publish", methods=["POST"])
@login_required
def api_events_publish():
    """Publish an event to the bus (for operator-initiated events)."""
    d = request.json or {}
    topic = d.get("topic", "")
    if not topic:
        return jsonify({"error": "topic required"}), 400
    evt = event_bus.publish(topic, d.get("payload"), source=ctx()["user"])
    return jsonify(evt.to_dict())
