"""AMOS Test Fixtures — shared across all test modules.

Provides:
- app: Flask app instance for testing
- client: Flask test client with auto-login support
- auth_session: pre-authenticated session (commander role)
- mock_db: patched DB layer that returns empty results
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Ensure project root is on path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)


# ── Mock DB layer BEFORE importing anything that triggers state.py ──
_DB_PATCHES = []


def _setup_db_mocks():
    """Patch all DB functions so state.py loads without a real database."""
    patches = [
        patch("db.connection.execute", return_value=None),
        patch("db.connection.fetchall", return_value=[]),
        patch("db.connection.fetchone", return_value=None),
        patch("db.connection.check", return_value=False),
        patch("db.connection.to_json", side_effect=lambda x: __import__("json").dumps(x) if x else "null"),
        patch("db.connection.from_json", side_effect=lambda x: __import__("json").loads(x) if x else None),
        patch("db.persistence.flush_periodic", return_value=None),
        patch("db.persistence.persist_engagement", return_value=None),
        patch("db.persistence.persist_bda", return_value=None),
        patch("db.persistence.persist_sitrep", return_value=None),
        patch("db.persistence.persist_hal_action", return_value=None),
        patch("db.persistence.load_state_from_db", return_value={}),
    ]
    mocks = []
    for p in patches:
        m = p.start()
        mocks.append(m)
    return patches, mocks


# Start DB mocks before any app imports
_DB_PATCHES, _DB_MOCKS = _setup_db_mocks()

# Now safe to import app (must go through web.app to register blueprints)
# Force-set (not setdefault) because _setup_db_mocks triggers import of
# db.connection which loads .env via python-dotenv, setting AMOS_EDITION=open
os.environ["AMOS_EDITION"] = "enterprise"
import web.app  # noqa: E402 — triggers blueprint registration
from web.extensions import app as _flask_app  # noqa: E402


@pytest.fixture(scope="session")
def app():
    """Create and configure a test Flask app."""
    _flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "SERVER_NAME": "localhost",
    })
    yield _flask_app


@pytest.fixture
def client(app):
    """Flask test client (not logged in)."""
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_client(app):
    """Flask test client pre-authenticated as commander."""
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user"] = "commander"
        yield c


@pytest.fixture
def pilot_client(app):
    """Flask test client pre-authenticated as pilot (limited access)."""
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user"] = "pilot"
        yield c


@pytest.fixture
def observer_client(app):
    """Flask test client pre-authenticated as observer (read-heavy role)."""
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user"] = "observer"
        yield c


# ── Cleanup DB patches at end of session ──
def pytest_sessionfinish(session, exitstatus):
    for p in _DB_PATCHES:
        try:
            p.stop()
        except RuntimeError:
            pass
