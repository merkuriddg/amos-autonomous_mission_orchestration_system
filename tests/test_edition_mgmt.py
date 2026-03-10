"""Edition Management route tests — status, bundles, toggle."""


def test_edition_status(auth_client):
    """GET /api/v1/edition/status returns edition info."""
    resp = auth_client.get("/api/v1/edition/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "edition" in data
    assert "features" in data
    assert "total_features" in data
    assert "enabled_count" in data
    assert data["is_enterprise"] is True  # conftest sets AMOS_EDITION=enterprise


def test_edition_bundles(auth_client):
    """GET /api/v1/edition/bundles returns feature groupings."""
    resp = auth_client.get("/api/v1/edition/bundles")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) == 5  # 5 bundles defined
    for bundle in data:
        assert "id" in bundle
        assert "name" in bundle
        assert "features" in bundle
        assert "enabled_count" in bundle


def test_edition_toggle_success(auth_client):
    """POST /api/v1/edition/toggle toggles a runtime-safe feature."""
    resp = auth_client.post("/api/v1/edition/toggle", json={
        "feature": "cognitive",
        "enabled": False,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True

    # Toggle back on
    resp2 = auth_client.post("/api/v1/edition/toggle", json={
        "feature": "cognitive",
        "enabled": True,
    })
    assert resp2.status_code == 200
    assert resp2.get_json()["success"] is True


def test_edition_toggle_restart_required(auth_client):
    """POST /api/v1/edition/toggle rejects restart-required features."""
    resp = auth_client.post("/api/v1/edition/toggle", json={
        "feature": "comsec",
        "enabled": False,
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "restart" in data["message"].lower()


def test_edition_toggle_unknown_feature(auth_client):
    """POST /api/v1/edition/toggle rejects unknown features."""
    resp = auth_client.post("/api/v1/edition/toggle", json={
        "feature": "nonexistent_feature",
        "enabled": True,
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False


def test_edition_toggle_missing_feature_name(auth_client):
    """POST /api/v1/edition/toggle requires feature name."""
    resp = auth_client.post("/api/v1/edition/toggle", json={
        "enabled": True,
    })
    assert resp.status_code == 400


def test_edition_toggle_missing_enabled(auth_client):
    """POST /api/v1/edition/toggle requires enabled state."""
    resp = auth_client.post("/api/v1/edition/toggle", json={
        "feature": "cognitive",
    })
    assert resp.status_code == 400


def test_edition_toggle_non_commander(pilot_client):
    """Non-commander cannot toggle features."""
    resp = pilot_client.post("/api/v1/edition/toggle", json={
        "feature": "cognitive",
        "enabled": False,
    })
    assert resp.status_code == 403


def test_edition_status_any_role(pilot_client):
    """Any authenticated user can view edition status."""
    resp = pilot_client.get("/api/v1/edition/status")
    assert resp.status_code == 200


def test_edition_bundles_any_role(observer_client):
    """Any authenticated user can view bundles."""
    resp = observer_client.get("/api/v1/edition/bundles")
    assert resp.status_code == 200
