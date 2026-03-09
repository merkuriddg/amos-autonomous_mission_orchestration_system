#!/usr/bin/env python3
"""AMOS Phase 28 — Cryptographic Key Manager

Lifecycle management for symmetric keys used by SecureChannel.
Supports key generation, rotation, revocation, and export (wrapped).
"""

import os
import hashlib
import hmac
import uuid
import time
import logging
import threading
from datetime import datetime, timezone

log = logging.getLogger("amos.keymgr")

# Key states
KEY_ACTIVE      = "ACTIVE"
KEY_ROTATED     = "ROTATED"
KEY_REVOKED     = "REVOKED"
KEY_EXPIRED     = "EXPIRED"


class KeyManager:
    """Manages cryptographic key lifecycle for AMOS COMSEC channels."""

    def __init__(self, master_key: bytes = None):
        self._master = master_key or os.urandom(32)
        self._keys = {}       # {key_id: record}
        self._lock = threading.Lock()
        self.audit_log = []

    def generate_key(self, purpose: str = "channel",
                     ttl_seconds: int = 86400) -> dict:
        """Generate a new 256-bit key and register it."""
        key_id = f"KEY-{uuid.uuid4().hex[:12]}"
        raw = os.urandom(32)
        now = time.time()
        record = {
            "key_id": key_id, "purpose": purpose,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": datetime.fromtimestamp(now + ttl_seconds, tz=timezone.utc).isoformat(),
            "ttl_seconds": ttl_seconds,
            "state": KEY_ACTIVE,
            "_raw": raw,  # never serialised externally
            "fingerprint": hashlib.sha256(raw).hexdigest()[:16],
        }
        with self._lock:
            self._keys[key_id] = record
        self._audit("GENERATE", key_id, purpose)
        log.info(f"Key generated: {key_id} ({purpose}, TTL={ttl_seconds}s)")
        return {k: v for k, v in record.items() if k != "_raw"}

    def get_key(self, key_id: str) -> bytes:
        """Retrieve raw key bytes (for SecureChannel init)."""
        rec = self._keys.get(key_id)
        if not rec:
            raise KeyError(f"Unknown key: {key_id}")
        if rec["state"] not in (KEY_ACTIVE,):
            raise PermissionError(f"Key {key_id} is {rec['state']}")
        return rec["_raw"]

    def rotate_key(self, key_id: str) -> dict:
        """Rotate key: mark old key ROTATED, generate a new one."""
        with self._lock:
            old = self._keys.get(key_id)
            if not old:
                return {"error": f"Unknown key: {key_id}"}
            old["state"] = KEY_ROTATED
        self._audit("ROTATE", key_id, old.get("purpose", ""))
        new_rec = self.generate_key(purpose=old.get("purpose", "channel"),
                                     ttl_seconds=old.get("ttl_seconds", 86400))
        new_rec["rotated_from"] = key_id
        return new_rec

    def revoke_key(self, key_id: str, reason: str = "") -> bool:
        """Immediately revoke a key."""
        with self._lock:
            rec = self._keys.get(key_id)
            if not rec:
                return False
            rec["state"] = KEY_REVOKED
            rec["revoked_at"] = datetime.now(timezone.utc).isoformat()
            rec["revoke_reason"] = reason
        self._audit("REVOKE", key_id, reason)
        log.warning(f"Key revoked: {key_id} — {reason}")
        return True

    def expire_old_keys(self) -> int:
        """Expire keys past their TTL."""
        now = time.time()
        count = 0
        with self._lock:
            for rec in self._keys.values():
                if rec["state"] == KEY_ACTIVE:
                    created_ts = datetime.fromisoformat(rec["created_at"]).timestamp()
                    if now - created_ts > rec.get("ttl_seconds", 86400):
                        rec["state"] = KEY_EXPIRED
                        count += 1
        if count:
            self._audit("EXPIRE_BATCH", "", f"{count} keys expired")
        return count

    def list_keys(self, state: str = None) -> list:
        """List key metadata (never raw bytes)."""
        result = []
        for rec in self._keys.values():
            if state and rec["state"] != state:
                continue
            result.append({k: v for k, v in rec.items() if k != "_raw"})
        return result

    def wrapped_export(self, key_id: str) -> dict:
        """Export a key wrapped (encrypted) with the master key.

        The wrapped blob can be transferred to another AMOS node
        and unwrapped with the same master key.
        """
        raw = self.get_key(key_id)
        # Simple wrapping: XOR with master-derived key
        wrap_key = hashlib.sha256(self._master + key_id.encode()).digest()
        wrapped = bytes(a ^ b for a, b in zip(raw, wrap_key))
        self._audit("EXPORT", key_id, "wrapped")
        return {
            "key_id": key_id,
            "wrapped": wrapped.hex(),
            "fingerprint": hashlib.sha256(raw).hexdigest()[:16],
        }

    def wrapped_import(self, key_id: str, wrapped_hex: str,
                       purpose: str = "channel", ttl_seconds: int = 86400) -> dict:
        """Import a wrapped key."""
        wrapped = bytes.fromhex(wrapped_hex)
        wrap_key = hashlib.sha256(self._master + key_id.encode()).digest()
        raw = bytes(a ^ b for a, b in zip(wrapped, wrap_key))
        now = time.time()
        record = {
            "key_id": key_id, "purpose": purpose,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": datetime.fromtimestamp(now + ttl_seconds, tz=timezone.utc).isoformat(),
            "ttl_seconds": ttl_seconds,
            "state": KEY_ACTIVE,
            "_raw": raw,
            "fingerprint": hashlib.sha256(raw).hexdigest()[:16],
            "imported": True,
        }
        with self._lock:
            self._keys[key_id] = record
        self._audit("IMPORT", key_id, "wrapped")
        return {k: v for k, v in record.items() if k != "_raw"}

    # ── Internal ─────────────────────────────────────────────
    def _audit(self, action: str, key_id: str, detail: str):
        entry = {
            "action": action, "key_id": key_id, "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.audit_log.append(entry)
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-1000:]

    def get_audit_log(self, limit: int = 50) -> list:
        return self.audit_log[-limit:]

    def get_status(self) -> dict:
        states = {}
        for rec in self._keys.values():
            states[rec["state"]] = states.get(rec["state"], 0) + 1
        return {"total_keys": len(self._keys), "by_state": states}
