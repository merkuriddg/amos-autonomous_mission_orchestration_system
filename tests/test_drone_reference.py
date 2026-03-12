"""Tests for the Drone Reference Database service."""

import json
import os
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Minimal reference data for isolated tests
_MINI_REF = {
    "version": "test",
    "generated_by": "test",
    "sources": [{"name": "test", "license": "test", "count": 3}],
    "total": 5,
    "entries": [
        {
            "id": "dji_mavic_3", "name": "DJI Mavic 3", "manufacturer": "DJI",
            "category": "commercial", "platform_type": "multirotor",
            "weight_g": 895, "max_speed_kts": 40.5, "max_speed_ms": 20.8,
            "endurance_min": 46, "range_km": 30, "ceiling_ft": 19685,
            "sensors": ["EO"], "camera_mp": 20.0, "rf_bands": ["2.4 GHz", "5.8 GHz"],
            "tx_protocol": "OcuSync 3+", "gnss": ["gps", "glonass"],
            "ip_rating": "none", "operating_temp": "-10°C to 40°C",
            "serial_prefixes": ["1581F", "1581E"],
            "threat_classification": "commercial", "series": "Mavic",
            "source": "dronecompare.org", "source_license": "CC-BY-4.0", "notes": None,
        },
        {
            "id": "rq11b_raven", "name": "RQ-11B Raven", "manufacturer": "AeroVironment",
            "category": "tactical", "platform_type": "fixed_wing",
            "weight_g": 2132, "max_speed_kts": 44, "max_speed_ms": 22.6,
            "endurance_min": 90, "range_km": 10, "ceiling_ft": 10000,
            "sensors": ["EO", "IR"], "camera_mp": None,
            "rf_bands": ["FHSS digital"], "tx_protocol": "AeroVironment DDL",
            "gnss": ["gps"], "ip_rating": "all-weather",
            "operating_temp": "-30°C to 50°C",
            "serial_prefixes": ["AV-RVN", "RQ11"],
            "threat_classification": "friendly", "series": "SURSS Group 1",
            "source": "navy.mil", "source_license": "public domain",
            "notes": "Hand-launched squad-level ISR.",
        },
        {
            "id": "fpv_racing_modified", "name": "Modified FPV Racing Drone",
            "manufacturer": "Various/DIY", "category": "adversary",
            "platform_type": "multirotor",
            "weight_g": 800, "max_speed_kts": 75, "max_speed_ms": 38.6,
            "endurance_min": 8, "range_km": 5, "ceiling_ft": 3000,
            "sensors": ["EO"], "camera_mp": 2,
            "rf_bands": ["5.8 GHz", "2.4 GHz", "900 MHz"],
            "tx_protocol": "analog/digital FPV", "gnss": [],
            "ip_rating": "none", "operating_temp": None,
            "serial_prefixes": [],
            "threat_classification": "hostile", "series": None,
            "source": "OSINT", "source_license": None,
            "notes": "Weaponized FPV drone.",
        },
        {
            "id": "autel_evo_ii", "name": "Autel EVO II", "manufacturer": "Autel",
            "category": "commercial", "platform_type": "multirotor",
            "weight_g": 1191, "max_speed_kts": 38.9, "max_speed_ms": 20.0,
            "endurance_min": 42, "range_km": 15, "ceiling_ft": 23000,
            "sensors": ["EO"], "camera_mp": 48.0,
            "rf_bands": ["2.4 GHz", "5.8 GHz"],
            "tx_protocol": "Autel SkyLink", "gnss": ["gps", "glonass"],
            "ip_rating": "none", "operating_temp": None,
            "serial_prefixes": ["AU-"],
            "threat_classification": "commercial", "series": "EVO",
            "source": "dronecompare.org", "source_license": "CC-BY-4.0", "notes": None,
        },
        {
            "id": "skydio_x10", "name": "Skydio X10", "manufacturer": "Skydio",
            "category": "commercial", "platform_type": "multirotor",
            "weight_g": 1600, "max_speed_kts": 35, "max_speed_ms": 18.0,
            "endurance_min": 40, "range_km": 12, "ceiling_ft": 15000,
            "sensors": ["EO", "IR"], "camera_mp": 50.0,
            "rf_bands": ["2.4 GHz", "5.8 GHz"],
            "tx_protocol": "Skydio Link", "gnss": ["gps"],
            "ip_rating": "IP55", "operating_temp": "-10°C to 43°C",
            "serial_prefixes": ["SDK", "SKD"],
            "threat_classification": "commercial", "series": "X",
            "source": "dronecompare.org", "source_license": "CC-BY-4.0", "notes": None,
        },
    ],
}


@pytest.fixture
def mini_ref_path(tmp_path):
    """Write mini reference JSON and return its path."""
    p = tmp_path / "drone_reference.json"
    p.write_text(json.dumps(_MINI_REF))
    return str(p)


@pytest.fixture
def db(mini_ref_path):
    """Create a DroneReferenceDB loaded from the mini fixture."""
    from services.drone_reference import DroneReferenceDB
    return DroneReferenceDB(path=mini_ref_path)


# ── Loading ──

def test_load_success(db):
    assert db.loaded is True
    assert len(db.entries) == 5
    assert db.version == "test"


def test_load_missing_file():
    from services.drone_reference import DroneReferenceDB
    bad = DroneReferenceDB(path="/tmp/nonexistent_drone_ref.json")
    assert bad.loaded is False
    assert len(bad.entries) == 0


# ── Lookup by serial ──

def test_lookup_serial_dji(db):
    result = db.lookup_by_serial("1581F5ABCDEF")
    assert result is not None
    assert result["id"] == "dji_mavic_3"
    assert result["manufacturer"] == "DJI"


def test_lookup_serial_autel(db):
    result = db.lookup_by_serial("AU-12345")
    assert result is not None
    assert result["id"] == "autel_evo_ii"


def test_lookup_serial_skydio(db):
    result = db.lookup_by_serial("SDK99887766")
    assert result is not None
    assert result["manufacturer"] == "Skydio"


def test_lookup_serial_military(db):
    result = db.lookup_by_serial("AV-RVN-001")
    assert result is not None
    assert result["id"] == "rq11b_raven"
    assert result["category"] == "tactical"


def test_lookup_serial_rq11(db):
    result = db.lookup_by_serial("RQ11-0042")
    assert result is not None
    assert result["id"] == "rq11b_raven"


def test_lookup_serial_no_match(db):
    assert db.lookup_by_serial("XXXXXXX") is None


def test_lookup_serial_empty(db):
    assert db.lookup_by_serial("") is None
    assert db.lookup_by_serial(None) is None


# ── Lookup by model ──

def test_lookup_model(db):
    result = db.lookup_by_model("rq11b_raven")
    assert result is not None
    assert result["name"] == "RQ-11B Raven"


def test_lookup_model_not_found(db):
    assert db.lookup_by_model("nonexistent") is None


# ── Lookup by name ──

def test_lookup_name_case_insensitive(db):
    r1 = db.lookup_by_name("DJI Mavic 3")
    r2 = db.lookup_by_name("dji mavic 3")
    assert r1 is not None
    assert r1 == r2


def test_lookup_name_not_found(db):
    assert db.lookup_by_name("Unknown Drone") is None


# ── Category filter ──

def test_get_by_category_commercial(db):
    results = db.get_by_category("commercial")
    assert len(results) == 3
    assert all(e["category"] == "commercial" for e in results)


def test_get_by_category_tactical(db):
    results = db.get_by_category("tactical")
    assert len(results) == 1
    assert results[0]["id"] == "rq11b_raven"


def test_get_by_category_adversary(db):
    results = db.get_by_category("adversary")
    assert len(results) == 1
    assert results[0]["threat_classification"] == "hostile"


def test_get_by_category_empty(db):
    assert db.get_by_category("nonexistent") == []


# ── Manufacturer ──

def test_get_by_manufacturer(db):
    results = db.get_by_manufacturer("DJI")
    assert len(results) == 1
    results2 = db.get_by_manufacturer("dji")
    assert results == results2


# ── Search ──

def test_search_by_name(db):
    results = db.search("mavic")
    assert len(results) >= 1
    assert results[0]["id"] == "dji_mavic_3"


def test_search_by_manufacturer(db):
    results = db.search("AeroVironment")
    assert len(results) >= 1
    assert any(e["id"] == "rq11b_raven" for e in results)


def test_search_by_category(db):
    results = db.search("adversary")
    assert len(results) >= 1
    assert results[0]["category"] == "adversary"


def test_search_empty_query(db):
    assert db.search("") == []


def test_search_no_results(db):
    assert db.search("zzzznotfound") == []


def test_search_limit(db):
    results = db.search("commercial", limit=1)
    assert len(results) <= 1


# ── Enrichment ──

def test_enrich_track_by_serial(db):
    track = {"serial_number": "1581F5ABC", "ua_type": "unknown", "lat": 35.0, "lng": 51.0}
    result = db.enrich_track(track)
    assert result["ref_matched"] is True
    assert result["ref_manufacturer"] == "DJI"
    assert result["ref_name"] == "DJI Mavic 3"
    assert result["ref_category"] == "commercial"
    assert result["ref_max_speed_kts"] == 40.5


def test_enrich_track_by_name(db):
    track = {"serial_number": "", "ua_type": "RQ-11B Raven", "lat": 35.0, "lng": 51.0}
    result = db.enrich_track(track)
    assert result["ref_matched"] is True
    assert result["ref_id"] == "rq11b_raven"
    assert result["ref_threat_classification"] == "friendly"


def test_enrich_track_no_match(db):
    track = {"serial_number": "UNKNOWN123", "ua_type": "unknown", "lat": 35.0, "lng": 51.0}
    result = db.enrich_track(track)
    assert result["ref_matched"] is False
    assert "ref_name" not in result


def test_enrich_track_serial_priority(db):
    """Serial prefix should take priority over ua_type name."""
    track = {"serial_number": "AU-99999", "ua_type": "DJI Mavic 3"}
    result = db.enrich_track(track)
    assert result["ref_matched"] is True
    assert result["ref_manufacturer"] == "Autel"  # serial wins


# ── Stats ──

def test_get_stats(db):
    stats = db.get_stats()
    assert stats["total"] == 5
    assert stats["loaded"] is True
    assert stats["version"] == "test"
    assert stats["by_category"]["commercial"] == 3
    assert stats["by_category"]["tactical"] == 1
    assert stats["by_category"]["adversary"] == 1
    assert stats["manufacturers"] >= 4


# ── Full reference file ──

def test_full_reference_loads():
    """Verify the actual generated reference file loads and has expected counts."""
    ref_path = os.path.join(ROOT, "config", "drone_reference.json")
    if not os.path.exists(ref_path):
        pytest.skip("Full reference file not generated yet")
    from services.drone_reference import DroneReferenceDB
    db = DroneReferenceDB(path=ref_path)
    assert db.loaded is True
    assert len(db.entries) >= 100
    stats = db.get_stats()
    assert stats["by_category"].get("commercial", 0) >= 90
    assert stats["by_category"].get("tactical", 0) >= 5
    assert stats["by_category"].get("adversary", 0) >= 3
