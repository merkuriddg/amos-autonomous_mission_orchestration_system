"""Mission route tests — waypoints, geofences, tasks, mission plans."""


def test_get_waypoints(auth_client):
    """GET /api/waypoints returns all waypoints."""
    resp = auth_client.get("/api/v1/waypoints")
    assert resp.status_code == 200


def test_set_waypoint(auth_client):
    """POST /api/waypoints/set creates a waypoint for an asset."""
    # Need a valid asset — use one from config
    assets_resp = auth_client.get("/api/v1/assets")
    assets = assets_resp.get_json()
    if not assets:
        return  # skip if no assets loaded
    aid = next(iter(assets))
    resp = auth_client.post("/api/v1/waypoints/set", json={
        "asset_id": aid, "lat": 35.1, "lng": 69.1,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"


def test_set_waypoint_missing_fields(auth_client):
    """POST /api/waypoints/set without required fields returns 400."""
    resp = auth_client.post("/api/v1/waypoints/set", json={"asset_id": "X"})
    assert resp.status_code == 400


def test_set_waypoint_unknown_asset(auth_client):
    """POST /api/waypoints/set for nonexistent asset returns 404."""
    resp = auth_client.post("/api/v1/waypoints/set", json={
        "asset_id": "FAKE-999", "lat": 35.0, "lng": 69.0,
    })
    assert resp.status_code == 404


def test_clear_waypoints(auth_client):
    """POST /api/waypoints/clear clears waypoints."""
    resp = auth_client.post("/api/v1/waypoints/clear", json={})
    assert resp.status_code == 200


def test_get_geofences(auth_client):
    """GET /api/geofences returns geofence list."""
    resp = auth_client.get("/api/v1/geofences")
    assert resp.status_code == 200


def test_create_geofence(auth_client):
    """POST /api/geofences/create adds a geofence."""
    resp = auth_client.post("/api/v1/geofences/create", json={
        "type": "alert", "name": "Test Zone",
        "points": [{"lat": 35.0, "lng": 69.0}, {"lat": 35.1, "lng": 69.1}, {"lat": 35.0, "lng": 69.1}],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "id" in data


def test_get_tasks(auth_client):
    """GET /api/tasks returns task list."""
    resp = auth_client.get("/api/v1/tasks")
    assert resp.status_code == 200


def test_get_mission_templates(auth_client):
    """GET /api/missionplan/templates returns templates."""
    resp = auth_client.get("/api/v1/missionplan/templates")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]
    assert "phases" in data[0]
