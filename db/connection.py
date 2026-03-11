"""AMOS Database Connection Layer
Provides connection pooling and query helpers for MariaDB.

Connection strategy (tried in order):
  1. TCP via AMOS_DB_HOST / AMOS_DB_PORT  (preferred for portability)
  2. Unix socket via AMOS_DB_SOCKET       (faster on localhost)

Set DB credentials in .env or via environment variables.
Run  bash db/setup.sh  to auto-provision the database.
"""

import os
import json
import logging
import threading
import pymysql
from contextlib import contextmanager

log = logging.getLogger("amos.db")

# ── Config ──────────────────────────────────────────────
_DB_USER = os.environ.get("AMOS_DB_USER", "amos")
_DB_PASS = os.environ.get("AMOS_DB_PASS", "")
_DB_NAME = os.environ.get("AMOS_DB_NAME", "amos")
_DB_HOST = os.environ.get("AMOS_DB_HOST", "localhost")
_DB_PORT = int(os.environ.get("AMOS_DB_PORT", "3306"))
_DB_SOCKET = os.environ.get("AMOS_DB_SOCKET", "/tmp/mysql.sock")

_COMMON_OPTS = {
    "user": _DB_USER,
    "password": _DB_PASS,
    "database": _DB_NAME,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}

# Resolved at first connection — "tcp", "socket", or None
_conn_method = None

# ── Simple connection pool ──────────────────────────────
_pool = []
_pool_lock = threading.Lock()
_POOL_SIZE = 5


def _try_tcp():
    """Attempt a TCP connection."""
    cfg = {**_COMMON_OPTS, "host": _DB_HOST, "port": _DB_PORT, "connect_timeout": 3}
    return pymysql.connect(**cfg)


def _try_socket():
    """Attempt a Unix socket connection."""
    if not os.path.exists(_DB_SOCKET):
        raise FileNotFoundError(f"Socket not found: {_DB_SOCKET}")
    cfg = {**_COMMON_OPTS, "unix_socket": _DB_SOCKET, "connect_timeout": 3}
    return pymysql.connect(**cfg)


def _new_conn():
    """Create a fresh database connection using the best available method."""
    global _conn_method

    # If we already know what works, use it directly
    if _conn_method == "tcp":
        return _try_tcp()
    if _conn_method == "socket":
        return _try_socket()

    # First connection — probe TCP then socket
    try:
        conn = _try_tcp()
        _conn_method = "tcp"
        log.info(f"DB connected via TCP ({_DB_HOST}:{_DB_PORT}/{_DB_NAME})")
        return conn
    except Exception:
        pass

    try:
        conn = _try_socket()
        _conn_method = "socket"
        log.info(f"DB connected via socket ({_DB_SOCKET}/{_DB_NAME})")
        return conn
    except Exception:
        pass

    # Both failed — raise with helpful message
    raise pymysql.OperationalError(
        f"Cannot connect to MariaDB. Tried TCP {_DB_HOST}:{_DB_PORT} "
        f"and socket {_DB_SOCKET}. Run 'bash db/setup.sh' or check .env.")


@contextmanager
def get_conn():
    """Get a connection from the pool (or create one). Returns on exit."""
    conn = None
    with _pool_lock:
        if _pool:
            conn = _pool.pop()
    if conn is None:
        conn = _new_conn()
    else:
        try:
            conn.ping(reconnect=True)
        except Exception:
            conn = _new_conn()
    try:
        yield conn
    finally:
        with _pool_lock:
            if len(_pool) < _POOL_SIZE:
                _pool.append(conn)
            else:
                conn.close()


# ── Query helpers ───────────────────────────────────────

def fetchall(sql, params=None):
    """Execute query and return all rows as list of dicts."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()


def fetchone(sql, params=None):
    """Execute query and return first row as dict (or None)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()


def execute(sql, params=None):
    """Execute a write query. Returns lastrowid."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.lastrowid


def executemany(sql, param_list):
    """Execute a batch write. Returns row count."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, param_list)
            return cur.rowcount


def table_count(table):
    """Quick row count for a table."""
    row = fetchone(f"SELECT COUNT(*) AS cnt FROM {table}")
    return row["cnt"] if row else 0


# ── JSON helpers ────────────────────────────────────────

def to_json(obj):
    """Serialize to JSON string for DB storage."""
    return json.dumps(obj, default=str)


def from_json(s):
    """Deserialize JSON string from DB."""
    if s is None:
        return None
    if isinstance(s, (dict, list)):
        return s
    return json.loads(s)


# ── Health check ────────────────────────────────────────

def check():
    """Return True if database is reachable."""
    try:
        row = fetchone("SELECT 1 AS ok")
        return row and row.get("ok") == 1
    except Exception:
        return False
