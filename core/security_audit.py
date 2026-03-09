#!/usr/bin/env python3
"""AMOS Phase 28 — Security Audit Logger

Tamper-evident audit trail with SHA-256 hash chaining.
Every entry includes a hash of the previous entry, creating
an append-only, verifiable log.

Event categories:
  AUTH    — login, logout, token refresh
  ACCESS  — data access, API calls
  CRYPTO  — key generation, rotation, revocation
  CONFIG  — system configuration changes
  ALERT   — security alerts, anomaly detection
"""

import hashlib
import json
import uuid
import time
import logging
import threading
from datetime import datetime, timezone

log = logging.getLogger("amos.audit")


class SecurityAudit:
    """Tamper-evident security audit logger for AMOS."""

    def __init__(self, max_memory: int = 5000):
        self._entries = []
        self._lock = threading.Lock()
        self._max_memory = max_memory
        self._last_hash = "0" * 64  # genesis hash
        self.stats = {"total_events": 0, "by_category": {}}

    def log_event(self, category: str, action: str,
                  user: str = "system", detail: str = "",
                  severity: str = "INFO", metadata: dict = None) -> dict:
        """Record a security audit event.

        Args:
            category: AUTH, ACCESS, CRYPTO, CONFIG, ALERT
            action: specific action (e.g. LOGIN, KEY_ROTATE, API_CALL)
            severity: INFO, WARNING, CRITICAL
        """
        entry = {
            "id": f"AUD-{uuid.uuid4().hex[:10]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": category.upper(),
            "action": action,
            "user": user,
            "detail": detail,
            "severity": severity.upper(),
            "metadata": metadata or {},
        }

        # Hash chain: each entry includes the hash of the previous
        chain_input = (self._last_hash + json.dumps(entry, sort_keys=True, default=str))
        entry["hash"] = hashlib.sha256(chain_input.encode()).hexdigest()
        entry["prev_hash"] = self._last_hash

        with self._lock:
            self._entries.append(entry)
            self._last_hash = entry["hash"]
            self.stats["total_events"] += 1
            cat = entry["category"]
            self.stats["by_category"][cat] = self.stats["by_category"].get(cat, 0) + 1

            # Memory cap
            if len(self._entries) > self._max_memory:
                self._entries = self._entries[-self._max_memory:]

        if severity == "CRITICAL":
            log.critical(f"SECURITY AUDIT [{category}] {action}: {detail}")
        elif severity == "WARNING":
            log.warning(f"SECURITY AUDIT [{category}] {action}: {detail}")

        return entry

    # ── Convenience methods ──────────────────────────────────
    def log_auth(self, action: str, user: str, detail: str = "",
                 severity: str = "INFO") -> dict:
        return self.log_event("AUTH", action, user, detail, severity)

    def log_access(self, action: str, user: str, resource: str = "",
                   severity: str = "INFO") -> dict:
        return self.log_event("ACCESS", action, user, resource, severity)

    def log_crypto(self, action: str, detail: str = "",
                   severity: str = "INFO") -> dict:
        return self.log_event("CRYPTO", action, "system", detail, severity)

    def log_config(self, action: str, user: str, detail: str = "") -> dict:
        return self.log_event("CONFIG", action, user, detail)

    def log_alert(self, action: str, detail: str,
                  severity: str = "WARNING") -> dict:
        return self.log_event("ALERT", action, "system", detail, severity)

    # ── Query ────────────────────────────────────────────────
    def get_events(self, category: str = None, severity: str = None,
                   user: str = None, limit: int = 50) -> list:
        """Retrieve audit events with optional filters."""
        results = []
        for entry in reversed(self._entries):
            if category and entry["category"] != category.upper():
                continue
            if severity and entry["severity"] != severity.upper():
                continue
            if user and entry["user"] != user:
                continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results

    def verify_chain(self, entries: list = None) -> dict:
        """Verify the integrity of the hash chain.

        Returns:
            {"valid": bool, "checked": int, "broken_at": index or None}
        """
        entries = entries or self._entries
        if not entries:
            return {"valid": True, "checked": 0, "broken_at": None}

        for i in range(1, len(entries)):
            expected_prev = entries[i].get("prev_hash", "")
            actual_prev = entries[i - 1].get("hash", "")
            if expected_prev != actual_prev:
                return {"valid": False, "checked": i,
                        "broken_at": i, "entry_id": entries[i]["id"]}
        return {"valid": True, "checked": len(entries), "broken_at": None}

    def get_status(self) -> dict:
        chain_ok = self.verify_chain()
        return {
            "total_events": self.stats["total_events"],
            "in_memory": len(self._entries),
            "chain_integrity": chain_ok["valid"],
            "by_category": dict(self.stats["by_category"]),
        }
