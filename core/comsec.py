#!/usr/bin/env python3
"""AMOS Phase 28 — COMSEC (Communications Security)

Provides:
  SecureChannel  — AES-256-GCM encryption + HMAC message authentication
  ClassificationMarker — Apply/verify classification markings per
                          IC-TF Marking Standard (UNCLASSIFIED → TS//SCI)
"""

import os
import hmac
import hashlib
import base64
import json
import uuid
import logging
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field

log = logging.getLogger("amos.comsec")

# ── Classification levels (ordered) ─────────────────────────
CLASSIFICATION_LEVELS = [
    "UNCLASSIFIED",
    "CUI",              # Controlled Unclassified Information
    "CONFIDENTIAL",
    "SECRET",
    "TOP_SECRET",
    "TS_SCI",           # Top Secret / Sensitive Compartmented Info
]

CLASSIFICATION_RANK = {c: i for i, c in enumerate(CLASSIFICATION_LEVELS)}


# ═══════════════════════════════════════════════════════════════
#  Secure Channel
# ═══════════════════════════════════════════════════════════════
class SecureChannel:
    """AES-256-GCM encryption + HMAC-SHA256 message authentication.

    Uses Python stdlib only. Falls back to XOR-based cipher if
    the ``cryptography`` package is not installed.
    """

    def __init__(self, channel_id: str = "", key: bytes = None):
        self.channel_id = channel_id or f"CH-{uuid.uuid4().hex[:8]}"
        self._key = key or os.urandom(32)  # 256-bit
        self._hmac_key = hashlib.sha256(self._key + b"hmac").digest()
        self._use_aes = False
        self.stats = {"encrypted": 0, "decrypted": 0, "hmac_verified": 0,
                      "hmac_failed": 0}

        # Try to use real AES-256-GCM
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            self._aesgcm = AESGCM(self._key)
            self._use_aes = True
            log.info(f"SecureChannel {self.channel_id}: AES-256-GCM active")
        except ImportError:
            self._aesgcm = None
            log.info(f"SecureChannel {self.channel_id}: fallback cipher (install 'cryptography' for AES)")

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt and return  nonce(12) || ciphertext."""
        nonce = os.urandom(12)
        if self._use_aes:
            ct = self._aesgcm.encrypt(nonce, plaintext, None)
        else:
            ct = self._xor_cipher(plaintext, nonce)
        self.stats["encrypted"] += 1
        return nonce + ct

    def decrypt(self, blob: bytes) -> bytes:
        """Decrypt  nonce(12) || ciphertext → plaintext."""
        nonce, ct = blob[:12], blob[12:]
        if self._use_aes:
            pt = self._aesgcm.decrypt(nonce, ct, None)
        else:
            pt = self._xor_cipher(ct, nonce)
        self.stats["decrypted"] += 1
        return pt

    def sign(self, data: bytes) -> str:
        """Compute HMAC-SHA256 and return hex digest."""
        return hmac.new(self._hmac_key, data, hashlib.sha256).hexdigest()

    def verify(self, data: bytes, signature: str) -> bool:
        """Verify HMAC-SHA256 signature."""
        expected = self.sign(data)
        ok = hmac.compare_digest(expected, signature)
        if ok:
            self.stats["hmac_verified"] += 1
        else:
            self.stats["hmac_failed"] += 1
            log.warning(f"HMAC verification failed on channel {self.channel_id}")
        return ok

    def encrypt_message(self, message: dict) -> dict:
        """Encrypt a JSON-serialisable message dict."""
        raw = json.dumps(message, default=str).encode("utf-8")
        blob = self.encrypt(raw)
        sig = self.sign(blob)
        return {
            "channel": self.channel_id,
            "payload": base64.b64encode(blob).decode("ascii"),
            "signature": sig,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def decrypt_message(self, envelope: dict) -> dict:
        """Decrypt envelope → original message dict."""
        blob = base64.b64decode(envelope["payload"])
        if not self.verify(blob, envelope.get("signature", "")):
            raise ValueError("HMAC verification failed — message tampered")
        raw = self.decrypt(blob)
        return json.loads(raw.decode("utf-8"))

    def _xor_cipher(self, data: bytes, nonce: bytes) -> bytes:
        """Simple repeating-key XOR (fallback only)."""
        key_stream = hashlib.sha256(self._key + nonce).digest()
        key_stream *= (len(data) // 32 + 1)
        return bytes(a ^ b for a, b in zip(data, key_stream[:len(data)]))

    def get_status(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "cipher": "AES-256-GCM" if self._use_aes else "XOR-fallback",
            **self.stats,
        }


# ═══════════════════════════════════════════════════════════════
#  Classification Marking
# ═══════════════════════════════════════════════════════════════
class ClassificationMarker:
    """Apply and enforce classification markings on AMOS data objects."""

    @staticmethod
    def mark(data: dict, level: str = "UNCLASSIFIED",
             caveats: list = None, releasability: str = "RELTO USA") -> dict:
        """Apply classification marking to a data dict."""
        level = level.upper()
        if level not in CLASSIFICATION_RANK:
            level = "UNCLASSIFIED"
        data["_classification"] = {
            "level": level,
            "caveats": caveats or [],
            "releasability": releasability,
            "marked_at": datetime.now(timezone.utc).isoformat(),
            "marked_by": "AMOS",
        }
        return data

    @staticmethod
    def get_level(data: dict) -> str:
        """Return classification level of a marked object."""
        return data.get("_classification", {}).get("level", "UNCLASSIFIED")

    @staticmethod
    def check_access(data: dict, user_clearance: str) -> bool:
        """Check if user clearance meets or exceeds data classification."""
        data_rank = CLASSIFICATION_RANK.get(
            ClassificationMarker.get_level(data), 0)
        user_rank = CLASSIFICATION_RANK.get(user_clearance.upper(), 0)
        return user_rank >= data_rank

    @staticmethod
    def highest(levels: list) -> str:
        """Return the highest classification from a list."""
        max_rank = 0
        for lvl in levels:
            max_rank = max(max_rank, CLASSIFICATION_RANK.get(lvl.upper(), 0))
        for lvl, rank in CLASSIFICATION_RANK.items():
            if rank == max_rank:
                return lvl
        return "UNCLASSIFIED"

    @staticmethod
    def strip(data: dict) -> dict:
        """Remove classification marking from a data dict (for downgrade)."""
        data.pop("_classification", None)
        return data
