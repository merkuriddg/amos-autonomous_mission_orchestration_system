"""Settings route tests — locations, users, password, profile, system."""

import json


def test_get_locations(auth_client):
    """GET /api/settings/locations returns location data."""
    resp = auth_client.get("/api/v1/settings/locations")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "locations" in data


def test_save_location(auth_client):
    """POST /api/settings/locations/save creates a location."""
    resp = auth_client.post("/api/v1/settings/locations/save",
        json={"key": "test_base", "name": "Test Base", "lat": 35.0, "lng": 69.0, "zoom": 10})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "test_base" in data["locations"]["locations"]


def test_save_location_missing_key(auth_client):
    """POST /api/settings/locations/save without key returns 400."""
    resp = auth_client.post("/api/v1/settings/locations/save",
        json={"name": "No Key", "lat": 0, "lng": 0})
    assert resp.status_code == 400


def test_delete_location(auth_client):
    """POST /api/settings/locations/delete removes a location."""
    # Create then delete
    auth_client.post("/api/v1/settings/locations/save",
        json={"key": "to_delete", "name": "Delete Me", "lat": 0, "lng": 0})
    resp = auth_client.post("/api/v1/settings/locations/delete",
        json={"key": "to_delete"})
    assert resp.status_code == 200


def test_get_system_info(auth_client):
    """GET /api/settings/system returns system status."""
    resp = auth_client.get("/api/v1/settings/system")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "assets" in data
    assert "threats" in data
    assert "uptime_sec" in data


def test_update_profile(auth_client):
    """POST /api/settings/profile updates display name."""
    resp = auth_client.post("/api/v1/settings/profile",
        json={"name": "CDR Test"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"


def test_get_users_commander_only(auth_client, pilot_client):
    """Only commander can list users."""
    resp_cmd = auth_client.get("/api/v1/settings/users")
    assert resp_cmd.status_code == 200

    resp_pilot = pilot_client.get("/api/v1/settings/users")
    assert resp_pilot.status_code == 403


def test_create_user(auth_client):
    """POST /api/settings/users/create adds a user."""
    resp = auth_client.post("/api/v1/settings/users/create",
        json={"username": "testuser", "password": "test1234",
              "name": "Test User", "role": "observer"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["username"] == "testuser"


def test_create_user_short_username(auth_client):
    """Short username is rejected."""
    resp = auth_client.post("/api/v1/settings/users/create",
        json={"username": "x", "password": "test1234"})
    assert resp.status_code == 400


def test_create_user_short_password(auth_client):
    """Short password is rejected."""
    resp = auth_client.post("/api/v1/settings/users/create",
        json={"username": "validuser", "password": "ab"})
    assert resp.status_code == 400


def test_create_duplicate_user(auth_client):
    """Duplicate username is rejected."""
    resp = auth_client.post("/api/v1/settings/users/create",
        json={"username": "commander", "password": "test1234"})
    assert resp.status_code == 409


def test_unauthenticated_settings(client):
    """Unauthenticated access redirects."""
    resp = client.get("/api/v1/settings/locations", follow_redirects=False)
    assert resp.status_code == 302
