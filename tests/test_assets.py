"""Asset route tests — listing, CRUD, scenario, threats."""


def test_get_assets(auth_client):
    """GET /api/assets returns assets dict."""
    resp = auth_client.get("/api/v1/assets")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)


def test_get_assets_summary(auth_client):
    """GET /api/assets/summary returns aggregate counts."""
    resp = auth_client.get("/api/v1/assets/summary")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "total" in data
    assert "by_domain" in data
    assert "by_status" in data


def test_get_settings_assets(auth_client):
    """GET /api/settings/assets returns full fleet roster."""
    resp = auth_client.get("/api/v1/settings/assets")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)


def test_save_asset(auth_client):
    """POST /api/settings/assets/save creates a new asset."""
    resp = auth_client.post("/api/v1/settings/assets/save", json={
        "id": "TEST-01", "type": "test_drone", "domain": "air",
        "role": "recon", "lat": 35.0, "lng": 69.0,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["id"] == "TEST-01"


def test_save_asset_no_id(auth_client):
    """POST /api/settings/assets/save without ID returns 400."""
    resp = auth_client.post("/api/v1/settings/assets/save", json={
        "type": "no_id_drone", "domain": "air",
    })
    assert resp.status_code == 400


def test_delete_asset(auth_client):
    """POST /api/settings/assets/delete removes an asset."""
    # Create then delete
    auth_client.post("/api/v1/settings/assets/save", json={
        "id": "DEL-01", "type": "temp", "domain": "ground",
    })
    resp = auth_client.post("/api/v1/settings/assets/delete", json={"id": "DEL-01"})
    assert resp.status_code == 200


def test_get_threats(auth_client):
    """GET /api/threats returns threats dict."""
    resp = auth_client.get("/api/v1/threats")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)


def test_scenario_save(auth_client):
    """POST /api/scenario/save exports mission state."""
    resp = auth_client.post("/api/v1/scenario/save", json={"name": "Test Scenario"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "name" in data
    assert "assets" in data
    assert "threats" in data


def test_scenario_load(auth_client):
    """POST /api/scenario/load imports mission state."""
    resp = auth_client.post("/api/v1/scenario/load", json={
        "assets": {"LOAD-01": {
            "id": "LOAD-01", "type": "test", "domain": "air",
            "status": "operational", "role": "recon",
            "position": {"lat": 35.0, "lng": 69.0, "alt_ft": 1000},
            "health": {"battery_pct": 90, "comms_strength": 95, "cpu_temp_c": 40, "gps_fix": True},
            "speed_kts": 100, "heading_deg": 90, "sensors": [], "weapons": [],
            "supplies": {"fuel_pct": 80, "ammo_rounds": 0, "water_hr": 24, "rations_hr": 48},
        }},
        "threats": {},
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"


def test_asset_detail_found(auth_client):
    """GET /api/assets/<id> returns asset details."""
    # Ensure asset exists
    auth_client.post("/api/v1/settings/assets/save", json={
        "id": "DETAIL-01", "type": "test", "domain": "ground",
    })
    resp = auth_client.get("/api/v1/assets/DETAIL-01")
    assert resp.status_code == 200


def test_asset_detail_not_found(auth_client):
    """GET /api/assets/<id> returns 404 for missing asset."""
    resp = auth_client.get("/api/v1/assets/NONEXISTENT-99")
    assert resp.status_code == 404
