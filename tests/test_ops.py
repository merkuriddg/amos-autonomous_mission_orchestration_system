"""Ops route tests — swarm, bridge, readiness, sensors, geo."""


def test_swarm_formation(auth_client):
    """POST /api/swarm/formation sets swarm formation."""
    resp = auth_client.post("/api/v1/swarm/formation", json={
        "domain": "ground", "formation": "LINE",
    })
    # May be 200 or 400 depending on loaded assets
    assert resp.status_code in (200, 400)


def test_swarm_debug(auth_client):
    """GET /api/swarm/debug returns asset debug info."""
    resp = auth_client.get("/api/v1/swarm/debug")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "asset_count" in data
    assert "domains" in data


def test_bridge_all(auth_client):
    """GET /api/bridge/all returns all bridge statuses."""
    resp = auth_client.get("/api/v1/bridge/all")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "px4" in data
    assert "tak" in data
    assert "link16" in data
    assert "ros2" in data


def test_bridge_px4_status(auth_client):
    """GET /api/bridge/px4/status returns PX4 bridge info."""
    resp = auth_client.get("/api/v1/bridge/px4/status")
    assert resp.status_code == 200


def test_fusion_tracks(auth_client):
    """GET /api/fusion/tracks returns sensor fusion tracks."""
    resp = auth_client.get("/api/v1/fusion/tracks")
    assert resp.status_code == 200


def test_fusion_coverage(auth_client):
    """GET /api/fusion/coverage returns coverage map."""
    resp = auth_client.get("/api/v1/fusion/coverage")
    assert resp.status_code == 200


def test_geo_distance(auth_client):
    """GET /api/geo/distance calculates distance between points."""
    resp = auth_client.get("/api/v1/geo/distance?lat1=35.0&lng1=69.0&lat2=35.1&lng2=69.1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "distance_m" in data
    assert "bearing_deg" in data
    assert data["distance_m"] > 0


def test_geo_convert(auth_client):
    """GET /api/geo/convert returns UTM and MGRS coordinates."""
    resp = auth_client.get("/api/v1/geo/convert?lat=35.0&lng=69.0")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "utm" in data
    assert "mgrs" in data


def test_schema_validate_valid(auth_client):
    """POST /api/schema/validate with valid track data passes."""
    resp = auth_client.post("/api/v1/schema/validate", json={
        "schema_name": "track",
        "data": {"lat": 35.0, "lng": 69.0},
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["valid"] is True


def test_schema_validate_invalid(auth_client):
    """POST /api/schema/validate with missing required fields fails."""
    resp = auth_client.post("/api/v1/schema/validate", json={
        "schema_name": "track",
        "data": {"alt_m": 100},  # missing lat, lng
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0


def test_video_status(auth_client):
    """GET /api/video/status returns video pipeline stats."""
    resp = auth_client.get("/api/v1/video/status")
    assert resp.status_code == 200


def test_imagery_catalog(auth_client):
    """GET /api/imagery/catalog returns catalog."""
    resp = auth_client.get("/api/v1/imagery/catalog")
    assert resp.status_code == 200
