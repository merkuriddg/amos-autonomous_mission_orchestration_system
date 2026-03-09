#!/usr/bin/env python3
"""AMOS Phase 23 — Schema Validator

Validates incoming data against canonical schemas before it enters the
AMOS processing pipeline.  Provides rate-limiting, duplicate detection,
and detailed error reporting.
"""

import time
import hashlib
import json
import threading
from datetime import datetime, timezone

from mos_core.data_model import (
    Track, Detection, Command, SensorReading, VideoFrame, Message,
    CLASSIFICATIONS, AFFILIATIONS, DOMAINS, COMMAND_TYPES, MESSAGE_TYPES,
)


class ValidationError(Exception):
    """Raised when input fails schema validation."""
    def __init__(self, errors: list, schema: str = ""):
        self.errors = errors
        self.schema = schema
        super().__init__(f"Validation failed ({schema}): {errors}")


# ═══════════════════════════════════════════════════════════
#  SCHEMA DEFINITIONS (dict-based, no external deps)
# ═══════════════════════════════════════════════════════════

SCHEMAS = {
    "track": {
        "required": ["lat", "lng"],
        "types": {
            "lat": (int, float), "lng": (int, float), "alt_m": (int, float),
            "heading_deg": (int, float), "speed_mps": (int, float),
            "domain": str, "affiliation": str, "confidence": (int, float),
            "sources": list, "track_type": str, "associated_id": str,
        },
        "ranges": {
            "lat": (-90, 90), "lng": (-180, 180),
            "confidence": (0, 1), "heading_deg": (0, 360),
        },
        "enums": {
            "domain": DOMAINS, "affiliation": AFFILIATIONS,
            "classification_level": CLASSIFICATIONS,
        },
    },
    "detection": {
        "required": ["sensor_type", "lat", "lng"],
        "types": {
            "sensor_type": str, "sensor_id": str,
            "lat": (int, float), "lng": (int, float), "alt_m": (int, float),
            "confidence": (int, float), "bearing_deg": (int, float),
            "range_m": (int, float), "snr_db": (int, float),
            "freq_mhz": (int, float),
        },
        "ranges": {
            "lat": (-90, 90), "lng": (-180, 180), "confidence": (0, 1),
        },
        "enums": {"affiliation": AFFILIATIONS},
    },
    "command": {
        "required": ["command_type", "target_ids"],
        "types": {
            "command_type": str, "target_ids": list,
            "parameters": dict, "priority": str, "issuer": str,
        },
        "ranges": {},
        "enums": {
            "command_type": COMMAND_TYPES,
            "priority": ("FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"),
            "classification_level": CLASSIFICATIONS,
        },
    },
    "sensor_reading": {
        "required": ["sensor_type", "reading_type"],
        "types": {
            "sensor_type": str, "sensor_id": str, "reading_type": str,
            "value": (int, float), "unit": str,
            "lat": (int, float), "lng": (int, float),
            "freq_mhz": (int, float), "bandwidth_hz": (int, float),
        },
        "ranges": {
            "lat": (-90, 90), "lng": (-180, 180),
        },
        "enums": {},
    },
    "video_meta": {
        "required": ["feed_id"],
        "types": {
            "feed_id": str, "frame_number": int,
            "width": int, "height": int, "encoding": str,
            "platform_lat": (int, float), "platform_lng": (int, float),
        },
        "ranges": {
            "platform_lat": (-90, 90), "platform_lng": (-180, 180),
        },
        "enums": {},
    },
    "message": {
        "required": ["originator"],
        "types": {
            "message_type": str, "originator": str, "recipients": list,
            "priority": str, "subject": str, "body": str,
        },
        "ranges": {},
        "enums": {
            "message_type": MESSAGE_TYPES,
            "priority": ("FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"),
            "classification_level": CLASSIFICATIONS,
        },
    },
}


# ═══════════════════════════════════════════════════════════
#  VALIDATOR
# ═══════════════════════════════════════════════════════════

class SchemaValidator:
    """Validates dicts against AMOS canonical schemas."""

    def __init__(self, rate_limit_per_sec: int = 500, dedup_window_sec: int = 5):
        self._lock = threading.Lock()
        self._rate_limit = rate_limit_per_sec
        self._dedup_window = dedup_window_sec
        self._request_times = []       # sliding window of timestamps
        self._recent_hashes = {}       # {hash: timestamp} for dedup
        self.stats = {
            "validated": 0, "rejected": 0, "duplicates": 0, "rate_limited": 0,
        }

    def validate(self, data: dict, schema_name: str, strict: bool = False) -> dict:
        """Validate data dict against named schema.

        Args:
            data: the input dict to validate
            schema_name: one of SCHEMAS keys
            strict: if True, raises ValidationError; if False, returns result dict

        Returns:
            {"valid": bool, "errors": [...], "warnings": [...]}
        """
        schema = SCHEMAS.get(schema_name)
        if not schema:
            err = f"Unknown schema: {schema_name}"
            if strict:
                raise ValidationError([err], schema_name)
            return {"valid": False, "errors": [err], "warnings": []}

        errors = []
        warnings = []

        # Required fields
        for req in schema.get("required", []):
            if req not in data or data[req] is None:
                errors.append(f"Missing required field: {req}")
            elif isinstance(data[req], str) and not data[req].strip():
                errors.append(f"Required field is empty: {req}")

        # Type checks
        for field_name, expected_type in schema.get("types", {}).items():
            if field_name in data and data[field_name] is not None:
                if not isinstance(data[field_name], expected_type):
                    errors.append(
                        f"Field '{field_name}' expected {expected_type.__name__ if isinstance(expected_type, type) else expected_type}, "
                        f"got {type(data[field_name]).__name__}")

        # Range checks
        for field_name, (lo, hi) in schema.get("ranges", {}).items():
            if field_name in data and isinstance(data[field_name], (int, float)):
                v = data[field_name]
                if v < lo or v > hi:
                    errors.append(f"Field '{field_name}' value {v} out of range [{lo}, {hi}]")

        # Enum checks
        for field_name, allowed in schema.get("enums", {}).items():
            if field_name in data and data[field_name]:
                if data[field_name] not in allowed:
                    errors.append(
                        f"Field '{field_name}' value '{data[field_name]}' not in {list(allowed)}")

        result = {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

        with self._lock:
            if errors:
                self.stats["rejected"] += 1
            else:
                self.stats["validated"] += 1

        if strict and errors:
            raise ValidationError(errors, schema_name)

        return result

    def check_rate_limit(self, source_id: str = "") -> bool:
        """Returns True if request is allowed, False if rate-limited."""
        now = time.time()
        with self._lock:
            # Clean old entries (sliding 1-second window)
            self._request_times = [t for t in self._request_times if now - t < 1.0]
            if len(self._request_times) >= self._rate_limit:
                self.stats["rate_limited"] += 1
                return False
            self._request_times.append(now)
        return True

    def check_duplicate(self, data: dict) -> bool:
        """Returns True if this data was seen recently (duplicate)."""
        # Hash the data for dedup
        data_str = json.dumps(data, sort_keys=True, default=str)
        h = hashlib.md5(data_str.encode()).hexdigest()
        now = time.time()
        with self._lock:
            # Clean expired
            expired = [k for k, t in self._recent_hashes.items()
                       if now - t > self._dedup_window]
            for k in expired:
                del self._recent_hashes[k]
            # Check
            if h in self._recent_hashes:
                self.stats["duplicates"] += 1
                return True
            self._recent_hashes[h] = now
        return False

    def validate_and_check(self, data: dict, schema_name: str,
                           source_id: str = "") -> dict:
        """Full validation pipeline: rate limit → dedup → schema validate.

        Returns:
            {"valid": bool, "errors": [...], "warnings": [...],
             "rate_limited": bool, "duplicate": bool}
        """
        result = {"valid": False, "errors": [], "warnings": [],
                  "rate_limited": False, "duplicate": False}

        # Rate limit
        if not self.check_rate_limit(source_id):
            result["rate_limited"] = True
            result["errors"].append("Rate limited")
            return result

        # Dedup
        if self.check_duplicate(data):
            result["duplicate"] = True
            result["warnings"].append("Duplicate data detected")
            # Duplicates are warnings, not errors — still valid
            result["valid"] = True
            return result

        # Schema validation
        schema_result = self.validate(data, schema_name)
        result.update(schema_result)
        return result

    def get_stats(self) -> dict:
        return dict(self.stats)
