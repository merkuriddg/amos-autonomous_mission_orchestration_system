"""AMOS Database Connection Layer
Provides connection pooling and query helpers for MariaDB."""

import os
import json
import threading
import pymysql
from contextlib import contextmanager

# ── Config ──────────────────────────────────────────────
DB_CONFIG = {
    "unix_socket": os.environ.get("AMOS_DB_SOCKET", "/tmp/mysql.sock"),
    "user": os.environ.get("AMOS_DB_USER", "rpmbbu"),
    "password": os.environ.get("AMOS_DB_PASS", "z8468RPMerkuri123!"),
    "database": os.environ.get("AMOS_DB_NAME", "amos"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}

# ── Simple connection pool ──────────────────────────────
_pool = []
_pool_lock = threading.Lock()
_POOL_SIZE = 5


def _new_conn():
    """Create a fresh database connection."""
    return pymysql.connect(**DB_CONFIG)


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
