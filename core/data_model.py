#!/usr/bin/env python3
"""AMOS Phase 23 — Canonical Data Model

Unified data objects for all AMOS subsystems and protocol adapters.
Every adapter normalises external data into these canonical types before
passing to engines.  Every engine emits these types for downstream use.

Types:
  Track         — fused or raw positional track
  Detection     — single sensor detection event
  Command       — control directive (move, engage, jam, …)
  SensorReading — telemetry / spectrum / environmental reading
  VideoFrame    — single video frame with metadata
  Message       — free-text or structured tactical message
  DataProvenance — chain-of-custody record for any data item
"""

import time
import uuid
import math
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str = "D") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# Classification levels
CLASSIFICATIONS = ("UNCLASSIFIED", "CUI", "SECRET", "TOP_SECRET")

# Affiliation codes
AFFILIATIONS = ("FRIENDLY", "HOSTILE", "NEUTRAL", "UNKNOWN", "SUSPECT")

# Domain codes
DOMAINS = ("air", "ground", "maritime", "space", "cyber")


# ═══════════════════════════════════════════════════════════
#  TRACK
# ═══════════════════════════════════════════════════════════

@dataclass
class Track:
    """Unified positional track — the core object flowing through AMOS."""
    id: str = field(default_factory=lambda: _uid("TRK"))
    lat: float = 0.0
    lng: float = 0.0
    alt_m: float = 0.0
    heading_deg: float = 0.0
    speed_mps: float = 0.0
    domain: str = "ground"
    affiliation: str = "UNKNOWN"
    classification_level: str = "UNCLASSIFIED"
    track_type: str = ""           # vehicle_military, personnel_armed, …
    confidence: float = 0.5
    source_count: int = 1
    sources: list = field(default_factory=list)      # adapter/sensor IDs
    first_seen: str = field(default_factory=_now_iso)
    last_seen: str = field(default_factory=_now_iso)
    velocity_lat: float = 0.0
    velocity_lng: float = 0.0
    uncertainty_m: float = 500.0
    associated_id: str = ""        # linked AMOS asset/threat ID
    metadata: dict = field(default_factory=dict)

    # ── Serialisation ─────────────────────────────────────
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Track":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})

    def to_geojson(self) -> dict:
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [self.lng, self.lat, self.alt_m]},
            "properties": {k: v for k, v in self.to_dict().items()
                           if k not in ("lat", "lng", "alt_m")},
        }

    # ── Validation ────────────────────────────────────────
    def validate(self) -> list:
        """Return list of validation errors (empty = valid)."""
        errors = []
        if not (-90 <= self.lat <= 90):
            errors.append(f"lat {self.lat} out of range")
        if not (-180 <= self.lng <= 180):
            errors.append(f"lng {self.lng} out of range")
        if self.affiliation not in AFFILIATIONS:
            errors.append(f"affiliation '{self.affiliation}' invalid")
        if self.domain not in DOMAINS:
            errors.append(f"domain '{self.domain}' invalid")
        if not (0 <= self.confidence <= 1):
            errors.append(f"confidence {self.confidence} out of range 0-1")
        if self.classification_level not in CLASSIFICATIONS:
            errors.append(f"classification_level '{self.classification_level}' invalid")
        return errors


# ═══════════════════════════════════════════════════════════
#  DETECTION
# ═══════════════════════════════════════════════════════════

@dataclass
class Detection:
    """Single sensor detection event — pre-fusion."""
    id: str = field(default_factory=lambda: _uid("DET"))
    sensor_type: str = ""          # EO/IR, RADAR, SIGINT, …
    sensor_id: str = ""            # REAPER-01, SPECTR-02, …
    lat: float = 0.0
    lng: float = 0.0
    alt_m: float = 0.0
    confidence: float = 0.5
    classification: str = "UNKNOWN"
    affiliation: str = "UNKNOWN"
    bearing_deg: float = 0.0
    range_m: float = 0.0
    snr_db: float = 0.0
    freq_mhz: float = 0.0
    timestamp: str = field(default_factory=_now_iso)
    adapter_id: str = ""           # which adapter ingested this
    raw_data: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Detection":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})

    def to_geojson(self) -> dict:
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [self.lng, self.lat, self.alt_m]},
            "properties": {k: v for k, v in self.to_dict().items()
                           if k not in ("lat", "lng", "alt_m")},
        }

    def validate(self) -> list:
        errors = []
        if not (-90 <= self.lat <= 90):
            errors.append(f"lat {self.lat} out of range")
        if not (-180 <= self.lng <= 180):
            errors.append(f"lng {self.lng} out of range")
        if not (0 <= self.confidence <= 1):
            errors.append(f"confidence {self.confidence} out of range 0-1")
        if not self.sensor_type:
            errors.append("sensor_type is required")
        return errors


# ═══════════════════════════════════════════════════════════
#  COMMAND
# ═══════════════════════════════════════════════════════════

COMMAND_TYPES = (
    "MOVE", "RTB", "ORBIT", "HOLD", "ENGAGE", "JAM", "INTERCEPT",
    "SCAN", "ISR", "REPORT", "SET_MODE", "ARM", "DISARM", "LAND",
    "FORMATION", "SCATTER", "RALLY", "SET_AUTONOMY", "PAYLOAD_CMD",
)


@dataclass
class Command:
    """Control directive — issued by operator, NLP, or automation."""
    id: str = field(default_factory=lambda: _uid("CMD"))
    command_type: str = "MOVE"
    target_ids: list = field(default_factory=list)    # asset IDs
    parameters: dict = field(default_factory=dict)    # lat, lng, mode, freq, …
    priority: str = "ROUTINE"     # FLASH, IMMEDIATE, PRIORITY, ROUTINE
    issuer: str = ""              # operator name or "SYSTEM"
    classification_level: str = "UNCLASSIFIED"
    roe_check: str = "PENDING"    # PENDING, APPROVED, DENIED
    timestamp: str = field(default_factory=_now_iso)
    expires: str = ""
    status: str = "PENDING"       # PENDING, SENT, ACKNOWLEDGED, EXECUTED, FAILED
    adapter_id: str = ""          # adapter that will deliver this
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Command":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})

    def validate(self) -> list:
        errors = []
        if self.command_type not in COMMAND_TYPES:
            errors.append(f"command_type '{self.command_type}' invalid")
        if not self.target_ids:
            errors.append("target_ids is required")
        if self.priority not in ("FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"):
            errors.append(f"priority '{self.priority}' invalid")
        if self.classification_level not in CLASSIFICATIONS:
            errors.append(f"classification_level '{self.classification_level}' invalid")
        return errors


# ═══════════════════════════════════════════════════════════
#  SENSOR READING
# ═══════════════════════════════════════════════════════════

@dataclass
class SensorReading:
    """Telemetry / spectrum / environmental reading from a sensor."""
    id: str = field(default_factory=lambda: _uid("SR"))
    sensor_type: str = ""
    sensor_id: str = ""
    reading_type: str = ""        # power, temperature, position, spectrum, …
    value: float = 0.0
    unit: str = ""                # dBm, celsius, meters, MHz, …
    lat: float = 0.0
    lng: float = 0.0
    alt_m: float = 0.0
    freq_mhz: float = 0.0
    bandwidth_hz: float = 0.0
    modulation: str = ""
    timestamp: str = field(default_factory=_now_iso)
    adapter_id: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SensorReading":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})

    def validate(self) -> list:
        errors = []
        if not self.sensor_type:
            errors.append("sensor_type is required")
        if not self.reading_type:
            errors.append("reading_type is required")
        return errors


# ═══════════════════════════════════════════════════════════
#  VIDEO FRAME
# ═══════════════════════════════════════════════════════════

@dataclass
class VideoFrame:
    """Single video frame with optional KLV metadata."""
    id: str = field(default_factory=lambda: _uid("VF"))
    feed_id: str = ""
    frame_number: int = 0
    width: int = 0
    height: int = 0
    encoding: str = "jpeg"        # jpeg, png, h264, h265
    timestamp: str = field(default_factory=_now_iso)
    # KLV metadata (STANAG 4609)
    platform_lat: float = 0.0
    platform_lng: float = 0.0
    platform_alt_m: float = 0.0
    sensor_lat: float = 0.0
    sensor_lng: float = 0.0
    target_lat: float = 0.0
    target_lng: float = 0.0
    sensor_name: str = ""
    fov_deg: float = 0.0
    slant_range_m: float = 0.0
    platform_heading_deg: float = 0.0
    # Frame data (not serialised by default)
    data: bytes = field(default=b"", repr=False)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("data", None)  # never serialise raw bytes
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "VideoFrame":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known and k != "data"})

    def validate(self) -> list:
        errors = []
        if not self.feed_id:
            errors.append("feed_id is required")
        if self.width <= 0 or self.height <= 0:
            errors.append("width and height must be positive")
        return errors


# ═══════════════════════════════════════════════════════════
#  MESSAGE
# ═══════════════════════════════════════════════════════════

MESSAGE_TYPES = (
    "FREE_TEXT", "POSITION_REPORT", "TRACK_REPORT", "ALERT",
    "SITREP", "SPOT_REPORT", "CAS_REQUEST", "MEDEVAC_REQUEST",
    "FIRE_MISSION", "INTEL_REPORT", "BDA_REPORT",
)


@dataclass
class Message:
    """Tactical message — free-text or structured."""
    id: str = field(default_factory=lambda: _uid("MSG"))
    message_type: str = "FREE_TEXT"
    originator: str = ""
    recipients: list = field(default_factory=list)
    classification_level: str = "UNCLASSIFIED"
    priority: str = "ROUTINE"
    subject: str = ""
    body: str = ""
    dtg: str = field(default_factory=_now_iso)  # date-time group
    references: list = field(default_factory=list)
    position: dict = field(default_factory=dict)  # optional lat/lng
    attachments: list = field(default_factory=list)
    protocol: str = ""            # VMF, NFFI, CoT, …
    adapter_id: str = ""
    status: str = "DRAFT"         # DRAFT, SENT, DELIVERED, READ
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})

    def validate(self) -> list:
        errors = []
        if self.message_type not in MESSAGE_TYPES:
            errors.append(f"message_type '{self.message_type}' invalid")
        if not self.originator:
            errors.append("originator is required")
        if self.classification_level not in CLASSIFICATIONS:
            errors.append(f"classification_level '{self.classification_level}' invalid")
        if self.priority not in ("FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"):
            errors.append(f"priority '{self.priority}' invalid")
        return errors


# ═══════════════════════════════════════════════════════════
#  DATA PROVENANCE
# ═══════════════════════════════════════════════════════════

@dataclass
class DataProvenance:
    """Chain-of-custody record for any data item in AMOS."""
    id: str = field(default_factory=lambda: _uid("PROV"))
    data_id: str = ""              # ID of the Track/Detection/etc.
    data_type: str = ""            # "Track", "Detection", "Command", …
    source_adapter: str = ""       # adapter ID that ingested
    source_protocol: str = ""      # "MAVLink", "CoT", "Link16", …
    raw_format: str = ""           # "XML", "JSON", "binary", …
    ingested_at: str = field(default_factory=_now_iso)
    validated: bool = False
    validation_errors: list = field(default_factory=list)
    normalised_at: str = ""
    engines_processed: list = field(default_factory=list)  # engine names
    classification_level: str = "UNCLASSIFIED"
    signature: str = ""            # HMAC if COMSEC enabled
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DataProvenance":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})


# ═══════════════════════════════════════════════════════════
#  FACTORY / CONVERSION HELPERS
# ═══════════════════════════════════════════════════════════

_TYPE_MAP = {
    "Track": Track,
    "Detection": Detection,
    "Command": Command,
    "SensorReading": SensorReading,
    "VideoFrame": VideoFrame,
    "Message": Message,
    "DataProvenance": DataProvenance,
}


def from_dict(data_type: str, d: dict):
    """Generic factory: from_dict('Track', {...}) -> Track instance."""
    cls = _TYPE_MAP.get(data_type)
    if not cls:
        raise ValueError(f"Unknown data type: {data_type}")
    return cls.from_dict(d)


def detection_to_track(det: Detection) -> Track:
    """Promote a Detection into a new Track."""
    return Track(
        lat=det.lat, lng=det.lng, alt_m=det.alt_m,
        confidence=det.confidence, affiliation=det.affiliation,
        track_type=det.classification, sources=[det.sensor_id],
        domain="air" if det.alt_m > 100 else "ground",
        first_seen=det.timestamp, last_seen=det.timestamp,
    )


def track_distance_m(a: Track, b: Track) -> float:
    """Haversine distance between two Tracks in metres."""
    R = 6_371_000
    dlat = math.radians(b.lat - a.lat)
    dlng = math.radians(b.lng - a.lng)
    sa = (math.sin(dlat / 2) ** 2 +
          math.cos(math.radians(a.lat)) * math.cos(math.radians(b.lat)) *
          math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(sa), math.sqrt(1 - sa))
