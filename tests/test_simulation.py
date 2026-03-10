"""Simulation route tests — sim control, AAR, analytics, syscmd."""


def test_sim_status(auth_client):
    """GET /api/sim/status returns simulation state."""
    resp = auth_client.get("/api/v1/sim/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "running" in data
    assert "speed" in data
    assert "elapsed_sec" in data


def test_sim_speed(auth_client):
    """POST /api/sim/speed sets simulation speed."""
    resp = auth_client.post("/api/v1/sim/speed", json={"speed": 2.0})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["speed"] == 2.0
    # Reset
    auth_client.post("/api/v1/sim/speed", json={"speed": 1.0})


def test_aar_events(auth_client):
    """GET /api/aar/events returns event list."""
    resp = auth_client.get("/api/v1/aar/events")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)


def test_analytics_summary(auth_client):
    """GET /api/analytics/summary returns analytics data."""
    resp = auth_client.get("/api/v1/analytics/summary")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "threats" in data
    assert "assets" in data
    assert "risk" in data


def test_syscmd_health(auth_client):
    """GET /api/syscmd/health returns health info."""
    resp = auth_client.get("/api/v1/syscmd/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "uptime_sec" in data
    assert "cpu_pct" in data
    assert "memory_mb" in data
    assert "python" in data


def test_syscmd_metrics(auth_client):
    """GET /api/syscmd/metrics returns API metrics."""
    resp = auth_client.get("/api/v1/syscmd/metrics")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "total_requests" in data
    assert "unique_endpoints" in data


def test_syscmd_logs(auth_client):
    """GET /api/syscmd/logs returns log lines."""
    resp = auth_client.get("/api/v1/syscmd/logs")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "lines" in data


def test_syscmd_diagnostics(auth_client):
    """GET /api/syscmd/diagnostics returns system diagnostics."""
    resp = auth_client.get("/api/v1/syscmd/diagnostics")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "socketio_clients" in data
    assert "px4" in data
    assert "database" in data


def test_reports_mission(auth_client):
    """GET /api/reports/mission returns full mission report."""
    resp = auth_client.get("/api/v1/reports/mission")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "title" in data
    assert "situation" in data
    assert "assets" in data
