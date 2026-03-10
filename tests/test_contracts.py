"""Contract tests — validate AMOS data schemas are enforced correctly."""

from core.schema_validator import SchemaValidator, SCHEMAS


def test_schemas_exist():
    """All expected schemas are defined."""
    expected = ["track", "detection", "command", "sensor_reading", "video_meta", "message"]
    for name in expected:
        assert name in SCHEMAS, f"Schema '{name}' missing from SCHEMAS"


# ── Track Schema ──

def test_track_valid():
    """Valid track passes validation."""
    v = SchemaValidator()
    result = v.validate({"lat": 35.0, "lng": 69.0}, "track")
    assert result["valid"] is True
    assert len(result["errors"]) == 0


def test_track_missing_lat():
    """Track without lat fails."""
    v = SchemaValidator()
    result = v.validate({"lng": 69.0}, "track")
    assert result["valid"] is False
    assert any("lat" in e for e in result["errors"])


def test_track_out_of_range():
    """Track with lat > 90 fails range check."""
    v = SchemaValidator()
    result = v.validate({"lat": 91.0, "lng": 69.0}, "track")
    assert result["valid"] is False
    assert any("range" in e.lower() for e in result["errors"])


def test_track_bad_type():
    """Track with string lat fails type check."""
    v = SchemaValidator()
    result = v.validate({"lat": "not_a_number", "lng": 69.0}, "track")
    assert result["valid"] is False


# ── Command Schema ──

def test_command_valid():
    """Valid command passes."""
    v = SchemaValidator()
    result = v.validate({
        "command_type": "MOVE",
        "target_ids": ["FALCON-01"],
    }, "command")
    assert result["valid"] is True


def test_command_missing_type():
    """Command without command_type fails."""
    v = SchemaValidator()
    result = v.validate({"target_ids": ["A1"]}, "command")
    assert result["valid"] is False


def test_command_missing_targets():
    """Command without target_ids fails."""
    v = SchemaValidator()
    result = v.validate({"command_type": "MOVE"}, "command")
    assert result["valid"] is False


# ── Detection Schema ──

def test_detection_valid():
    """Valid detection passes."""
    v = SchemaValidator()
    result = v.validate({
        "sensor_type": "EO/IR",
        "lat": 35.0,
        "lng": 69.0,
    }, "detection")
    assert result["valid"] is True


def test_detection_missing_sensor():
    """Detection without sensor_type fails."""
    v = SchemaValidator()
    result = v.validate({"lat": 35.0, "lng": 69.0}, "detection")
    assert result["valid"] is False


# ── Message Schema ──

def test_message_valid():
    """Valid message passes."""
    v = SchemaValidator()
    result = v.validate({"originator": "CDR Mitchell"}, "message")
    assert result["valid"] is True


def test_message_missing_originator():
    """Message without originator fails."""
    v = SchemaValidator()
    result = v.validate({"body": "hello"}, "message")
    assert result["valid"] is False


# ── Unknown Schema ──

def test_unknown_schema():
    """Validating against unknown schema returns error."""
    v = SchemaValidator()
    result = v.validate({"foo": "bar"}, "nonexistent_schema")
    assert result["valid"] is False
    assert any("Unknown" in e for e in result["errors"])


# ── Validator Stats ──

def test_validator_stats():
    """Validator tracks validation and rejection counts."""
    v = SchemaValidator()
    v.validate({"lat": 35.0, "lng": 69.0}, "track")  # valid
    v.validate({}, "track")  # invalid
    assert v.stats["validated"] >= 1
    assert v.stats["rejected"] >= 1
