"""Smoke tests — verify AMOS boots cleanly."""


def test_app_exists(app):
    """App object is created."""
    assert app is not None


def test_app_testing_mode(app):
    """App is in testing mode."""
    assert app.config["TESTING"] is True


def test_app_has_routes(app):
    """App has registered routes."""
    rules = [r.rule for r in app.url_map.iter_rules()]
    assert "/" in rules
    assert "/login" in rules


def test_unauthenticated_redirect(client):
    """Unauthenticated access to / redirects to login."""
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")


def test_login_page_loads(client):
    """Login page renders without error."""
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"AMOS" in resp.data or b"login" in resp.data.lower()


def test_authenticated_index(auth_client):
    """Authenticated user can access index page."""
    resp = auth_client.get("/")
    assert resp.status_code == 200
