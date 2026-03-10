"""Auth route tests — login, logout, session."""


def test_login_get(client):
    """GET /login returns the login form."""
    resp = client.get("/login")
    assert resp.status_code == 200


def test_login_valid_credentials(client):
    """POST /login with valid creds redirects to /."""
    resp = client.post("/login", data={
        "username": "commander",
        "password": "amos_op1",
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers.get("Location", "").endswith("/")


def test_login_invalid_credentials(client):
    """POST /login with bad creds re-renders login page."""
    resp = client.post("/login", data={
        "username": "commander",
        "password": "wrongpassword",
    })
    assert resp.status_code == 200
    assert b"Invalid" in resp.data or b"invalid" in resp.data.lower()


def test_login_nonexistent_user(client):
    """POST /login with unknown user shows error."""
    resp = client.post("/login", data={
        "username": "nobody",
        "password": "nope",
    })
    assert resp.status_code == 200


def test_logout(auth_client):
    """GET /logout clears session and redirects to /login."""
    resp = auth_client.get("/logout", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")


def test_session_persists(auth_client):
    """Authenticated session persists across requests."""
    resp1 = auth_client.get("/")
    assert resp1.status_code == 200
    resp2 = auth_client.get("/settings")
    assert resp2.status_code == 200


def test_field_op_redirects_to_field(client):
    """Field operators redirect to /field on login."""
    resp = client.post("/login", data={
        "username": "field",
        "password": "tactical2026",
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert "/field" in resp.headers.get("Location", "")
