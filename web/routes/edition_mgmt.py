"""AMOS Edition Management Routes — view and toggle feature flags.

Edition (open/enterprise) is NOT switchable at runtime.
Only runtime-safe feature flags can be toggled via the UI.
All mutations are audited.
"""

from flask import Blueprint, request, jsonify
from web.extensions import login_required, ctx, _audit
from web import edition_service

bp = Blueprint("edition_mgmt", __name__)


@bp.route("/edition/status")
@login_required
def edition_status():
    """Return current edition and all feature flag states."""
    return jsonify(edition_service.current_state())


@bp.route("/edition/bundles")
@login_required
def edition_bundles():
    """Return grouped feature bundles with descriptions."""
    return jsonify(edition_service.list_bundles())


@bp.route("/edition/toggle", methods=["POST"])
@login_required
def edition_toggle():
    """Toggle a runtime-safe feature flag."""
    c = ctx()
    if c["role"] != "commander":
        return jsonify({"error": "Commander access required"}), 403

    d = request.json or {}
    name = d.get("feature", "").strip()
    enabled = d.get("enabled")

    if not name:
        return jsonify({"error": "Feature name required"}), 400
    if enabled is None:
        return jsonify({"error": "Enabled state required (true/false)"}), 400

    success, message = edition_service.set_feature(name, enabled)

    if success:
        _audit(c["user"], "feature_toggle", "edition", name,
               {"feature": name, "enabled": enabled})

    status_code = 200 if success else 400
    return jsonify({"success": success, "message": message,
                    "feature": name, "enabled": enabled}), status_code
