"""AMOS Enterprise — Defense Routes (VMF, STANAG 4586, NFFI, OGC WMS/WFS)."""

from flask import Blueprint, request, jsonify, session
from web.extensions import login_required
from web.state import (
    _vmf_adapter, _stanag4586, _nffi_adapter, _ogc_client,
    security_audit,
)

bp = Blueprint("ent_defense", __name__)


# ═══════════════════════════════════════════════════════════
#  VMF (Variable Message Format)
# ═══════════════════════════════════════════════════════════
@bp.route("/api/vmf/status")
@login_required
def api_vmf_status():
    if _vmf_adapter:
        return jsonify(_vmf_adapter.get_status())
    return jsonify({"error": "VMF adapter not available"}), 503

@bp.route("/api/vmf/messages")
@login_required
def api_vmf_messages():
    if _vmf_adapter:
        return jsonify(_vmf_adapter.get_message_log(limit=int(request.args.get("limit", 50))))
    return jsonify([])


# ═══════════════════════════════════════════════════════════
#  STANAG 4586
# ═══════════════════════════════════════════════════════════
@bp.route("/api/stanag4586/status")
@login_required
def api_stanag4586_status():
    if _stanag4586:
        return jsonify(_stanag4586.get_status())
    return jsonify({"error": "STANAG 4586 not available"}), 503

@bp.route("/api/stanag4586/vehicles")
@login_required
def api_stanag4586_vehicles():
    if _stanag4586:
        return jsonify(_stanag4586.get_vehicles())
    return jsonify({})

@bp.route("/api/stanag4586/command", methods=["POST"])
@login_required
def api_stanag4586_command():
    if not _stanag4586:
        return jsonify({"error": "STANAG 4586 not available"}), 503
    d = request.json or {}
    result = _stanag4586.send_vehicle_command(
        d.get("vehicle_id", ""), d.get("command", "HOLD"), d.get("params", {}))
    security_audit.log_access("STANAG4586_CMD", session.get("user", "unknown"),
        f"{d.get('vehicle_id')}: {d.get('command')}")
    return jsonify(result)


# ═══════════════════════════════════════════════════════════
#  NFFI (NATO Friendly Force Information)
# ═══════════════════════════════════════════════════════════
@bp.route("/api/nffi/status")
@login_required
def api_nffi_status():
    if _nffi_adapter:
        return jsonify(_nffi_adapter.get_status())
    return jsonify({"error": "NFFI not available"}), 503

@bp.route("/api/nffi/units")
@login_required
def api_nffi_units():
    if _nffi_adapter:
        return jsonify(_nffi_adapter.get_units())
    return jsonify({})

@bp.route("/api/nffi/contacts")
@login_required
def api_nffi_contacts():
    if _nffi_adapter:
        return jsonify(_nffi_adapter.get_contacts())
    return jsonify([])


# ═══════════════════════════════════════════════════════════
#  OGC WMS / WFS
# ═══════════════════════════════════════════════════════════
@bp.route("/api/ogc/status")
@login_required
def api_ogc_status():
    if _ogc_client:
        return jsonify(_ogc_client.get_status())
    return jsonify({"error": "OGC client not available"}), 503

@bp.route("/api/ogc/endpoints")
@login_required
def api_ogc_endpoints():
    if _ogc_client:
        return jsonify(_ogc_client.get_endpoints())
    return jsonify({"wms": {}, "wfs": {}})

@bp.route("/api/ogc/add", methods=["POST"])
@login_required
def api_ogc_add():
    if not _ogc_client:
        return jsonify({"error": "OGC client not available"}), 503
    d = request.json or {}
    svc = d.get("service", "wms").lower()
    if svc == "wfs":
        return jsonify(_ogc_client.add_wfs(d.get("name", ""), d.get("url", "")))
    return jsonify(_ogc_client.add_wms(d.get("name", ""), d.get("url", "")))
