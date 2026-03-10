"""AMOS Enterprise — Security Routes (COMSEC, Key Management, Security Audit, Classification)."""

from flask import Blueprint, request, jsonify, session
from web.extensions import login_required
from web.state import (
    comsec_channel, key_mgr, security_audit,
    ClassificationMarker,
)

bp = Blueprint("ent_security", __name__)


# ═══════════════════════════════════════════════════════════
#  COMSEC
# ═══════════════════════════════════════════════════════════
@bp.route("/api/comsec/status")
@login_required
def api_comsec_status():
    return jsonify({
        "channel": comsec_channel.get_status(),
        "key_manager": key_mgr.get_status(),
    })

@bp.route("/api/comsec/keys")
@login_required
def api_comsec_keys():
    return jsonify(key_mgr.list_keys())

@bp.route("/api/comsec/generate-key", methods=["POST"])
@login_required
def api_comsec_gen_key():
    d = request.json or {}
    rec = key_mgr.generate_key(d.get("purpose", "channel"), d.get("ttl", 86400))
    security_audit.log_crypto("KEY_GENERATE", rec.get("key_id", ""))
    return jsonify(rec)

@bp.route("/api/comsec/rotate-key", methods=["POST"])
@login_required
def api_comsec_rotate_key():
    d = request.json or {}
    rec = key_mgr.rotate_key(d.get("key_id", ""))
    security_audit.log_crypto("KEY_ROTATE", d.get("key_id", ""))
    return jsonify(rec)


# ═══════════════════════════════════════════════════════════
#  SECURITY AUDIT
# ═══════════════════════════════════════════════════════════
@bp.route("/api/security/audit")
@login_required
def api_security_audit():
    cat = request.args.get("category")
    sev = request.args.get("severity")
    lim = request.args.get("limit", 50, type=int)
    return jsonify(security_audit.get_events(category=cat, severity=sev, limit=lim))

@bp.route("/api/security/audit/status")
@login_required
def api_security_audit_status():
    return jsonify(security_audit.get_status())


# ═══════════════════════════════════════════════════════════
#  CLASSIFICATION MARKING
# ═══════════════════════════════════════════════════════════
@bp.route("/api/security/classify", methods=["POST"])
@login_required
def api_security_classify():
    if not ClassificationMarker:
        return jsonify({"error": "Classification marker not available"}), 503
    d = request.json or {}
    result = ClassificationMarker.mark(
        d.get("data", {}), d.get("level", "UNCLASSIFIED"),
        d.get("caveats"), d.get("releasability", "RELTO USA"))
    return jsonify(result)
