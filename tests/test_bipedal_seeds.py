"""B1 Bipedal Seed Tests — AssetState, IndoorPosition, environment_type, CQB formations.

Validates the architectural seeds planted for future bipedal squad autonomy.
All new types must be backwards-compatible with existing outdoor assets.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_model import (
    AssetState, IndoorPosition, ENVIRONMENT_TYPES, BIPED_POSTURES,
    BIPED_STANCES, MANIPULATION_STATES, COVER_STATUSES, CQB_FORMATIONS,
    from_dict,
)


# ═══════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════

def test_environment_types_tuple():
    """ENVIRONMENT_TYPES contains the three expected values."""
    assert isinstance(ENVIRONMENT_TYPES, tuple)
    assert "outdoor_open" in ENVIRONMENT_TYPES
    assert "outdoor_urban" in ENVIRONMENT_TYPES
    assert "indoor_cqb" in ENVIRONMENT_TYPES


def test_biped_postures_tuple():
    """BIPED_POSTURES has expected entries."""
    assert isinstance(BIPED_POSTURES, tuple)
    for p in ("standing", "crouching", "prone", "climbing", "breaching", "carrying", "unknown"):
        assert p in BIPED_POSTURES


def test_biped_stances_tuple():
    """BIPED_STANCES has expected entries."""
    assert isinstance(BIPED_STANCES, tuple)
    for s in ("ready", "moving", "covering", "engaging", "disabled", "idle", "unknown"):
        assert s in BIPED_STANCES


def test_manipulation_states_tuple():
    """MANIPULATION_STATES has expected entries."""
    assert isinstance(MANIPULATION_STATES, tuple)
    for m in ("idle", "gripping", "carrying_load", "operating_tool", "weapon_ready", "unknown"):
        assert m in MANIPULATION_STATES


def test_cover_statuses_tuple():
    """COVER_STATUSES has expected entries."""
    assert isinstance(COVER_STATUSES, tuple)
    assert set(COVER_STATUSES) == {"none", "partial", "full"}


def test_cqb_formations_tuple():
    """CQB_FORMATIONS has all six formation types."""
    assert isinstance(CQB_FORMATIONS, tuple)
    expected = {"STACK", "BUTTONHOOK", "CRISSCROSS", "BOUNDING_OVERWATCH", "PERIMETER", "CORRIDOR"}
    assert set(CQB_FORMATIONS) == expected


# ═══════════════════════════════════════════════════════════
#  INDOOR POSITION
# ═══════════════════════════════════════════════════════════

def test_indoor_position_defaults():
    """IndoorPosition defaults are safe (empty/zero)."""
    ip = IndoorPosition()
    assert ip.building_id == ""
    assert ip.floor == 0
    assert ip.room == ""
    assert ip.x_m == 0.0
    assert ip.confidence == 0.0


def test_indoor_position_roundtrip():
    """IndoorPosition serialises and deserialises cleanly."""
    ip = IndoorPosition(building_id="B-01", floor=2, room="R-201", x_m=3.5, y_m=7.2, z_m=5.0,
                        confidence=0.85, source="slam")
    d = ip.to_dict()
    assert d["building_id"] == "B-01"
    assert d["floor"] == 2
    ip2 = IndoorPosition.from_dict(d)
    assert ip2.building_id == "B-01"
    assert ip2.room == "R-201"
    assert ip2.confidence == 0.85


def test_indoor_position_from_none():
    """IndoorPosition.from_dict(None) returns empty instance."""
    ip = IndoorPosition.from_dict(None)
    assert ip.building_id == ""
    assert ip.floor == 0


def test_indoor_position_ignores_unknown_fields():
    """IndoorPosition.from_dict ignores extra keys."""
    ip = IndoorPosition.from_dict({"building_id": "B-02", "bogus_field": 999})
    assert ip.building_id == "B-02"


# ═══════════════════════════════════════════════════════════
#  ASSET STATE
# ═══════════════════════════════════════════════════════════

def test_asset_state_defaults():
    """AssetState defaults are safe for existing outdoor assets."""
    st = AssetState(asset_id="REAPER-01")
    assert st.posture == "unknown"
    assert st.stance == "unknown"
    assert st.manipulation_state == "unknown"
    assert st.cover_status == "none"
    assert st.fatigue_pct == 100.0
    assert st.indoor_position is None
    assert st.environment_type == "outdoor_open"


def test_asset_state_validates_clean():
    """Default AssetState passes validation."""
    st = AssetState(asset_id="TALON-01")
    errors = st.validate()
    assert errors == []


def test_asset_state_validates_bad_posture():
    """Invalid posture triggers validation error."""
    st = AssetState(asset_id="X", posture="flying")
    errors = st.validate()
    assert any("posture" in e for e in errors)


def test_asset_state_validates_bad_stance():
    """Invalid stance triggers validation error."""
    st = AssetState(asset_id="X", stance="dancing")
    errors = st.validate()
    assert any("stance" in e for e in errors)


def test_asset_state_validates_bad_manipulation():
    """Invalid manipulation_state triggers validation error."""
    st = AssetState(asset_id="X", manipulation_state="juggling")
    errors = st.validate()
    assert any("manipulation_state" in e for e in errors)


def test_asset_state_validates_bad_cover():
    """Invalid cover_status triggers validation error."""
    st = AssetState(asset_id="X", cover_status="invisible")
    errors = st.validate()
    assert any("cover_status" in e for e in errors)


def test_asset_state_validates_bad_fatigue():
    """Out-of-range fatigue triggers validation error."""
    st = AssetState(asset_id="X", fatigue_pct=150.0)
    errors = st.validate()
    assert any("fatigue_pct" in e for e in errors)
    st2 = AssetState(asset_id="X", fatigue_pct=-10.0)
    assert any("fatigue_pct" in e for e in st2.validate())


def test_asset_state_validates_bad_environment():
    """Invalid environment_type triggers validation error."""
    st = AssetState(asset_id="X", environment_type="underwater")
    errors = st.validate()
    assert any("environment_type" in e for e in errors)


def test_asset_state_roundtrip():
    """AssetState serialises and deserialises cleanly."""
    st = AssetState(asset_id="BIPED-01", posture="crouching", stance="covering",
                    manipulation_state="weapon_ready", cover_status="partial",
                    fatigue_pct=72.5, environment_type="indoor_cqb")
    d = st.to_dict()
    assert d["asset_id"] == "BIPED-01"
    assert d["posture"] == "crouching"
    assert d["indoor_position"] is None
    st2 = AssetState.from_dict(d)
    assert st2.posture == "crouching"
    assert st2.fatigue_pct == 72.5


def test_asset_state_with_indoor_position():
    """AssetState with IndoorPosition round-trips correctly."""
    ip = IndoorPosition(building_id="B-03", floor=1, room="R-101", x_m=2.0, y_m=4.0)
    st = AssetState(asset_id="CQB-01", posture="standing", stance="ready",
                    indoor_position=ip, environment_type="indoor_cqb")
    d = st.to_dict()
    assert d["indoor_position"]["building_id"] == "B-03"
    st2 = AssetState.from_dict(d)
    assert st2.indoor_position is not None
    assert st2.indoor_position.building_id == "B-03"
    assert st2.indoor_position.room == "R-101"


def test_asset_state_is_mobile():
    """is_mobile property reflects stance and fatigue."""
    st = AssetState(asset_id="X", stance="moving", fatigue_pct=50.0)
    assert st.is_mobile is True
    st2 = AssetState(asset_id="X", stance="disabled")
    assert st2.is_mobile is False
    st3 = AssetState(asset_id="X", stance="ready", fatigue_pct=0.0)
    assert st3.is_mobile is False


def test_asset_state_is_indoor():
    """is_indoor property requires indoor_cqb env and non-None indoor_position."""
    st1 = AssetState(asset_id="X", environment_type="outdoor_open")
    assert st1.is_indoor is False
    st2 = AssetState(asset_id="X", environment_type="indoor_cqb")
    assert st2.is_indoor is False  # no indoor_position yet
    ip = IndoorPosition(building_id="B-01")
    st3 = AssetState(asset_id="X", environment_type="indoor_cqb", indoor_position=ip)
    assert st3.is_indoor is True


def test_asset_state_factory():
    """from_dict('AssetState', {...}) works via the type map."""
    d = {"asset_id": "FACTORY-01", "posture": "prone", "stance": "covering"}
    st = from_dict("AssetState", d)
    assert st.asset_id == "FACTORY-01"
    assert st.posture == "prone"


def test_indoor_position_factory():
    """from_dict('IndoorPosition', {...}) works via the type map."""
    d = {"building_id": "B-99", "floor": 3}
    ip = from_dict("IndoorPosition", d)
    assert ip.building_id == "B-99"
    assert ip.floor == 3


# ═══════════════════════════════════════════════════════════
#  BACKWARDS COMPATIBILITY
# ═══════════════════════════════════════════════════════════

def test_backwards_compat_outdoor_asset():
    """Outdoor asset with default AssetState has no validation errors."""
    # Simulate what state.py does for existing REAPER/TALON assets
    st = AssetState(asset_id="REAPER-01", environment_type="outdoor_open")
    assert st.validate() == []
    assert st.indoor_position is None
    assert st.is_indoor is False
    assert st.is_mobile is True  # unknown stance, 100% fatigue = mobile


def test_backwards_compat_all_postures_valid():
    """Every entry in BIPED_POSTURES validates cleanly."""
    for p in BIPED_POSTURES:
        st = AssetState(asset_id="test", posture=p)
        errors = [e for e in st.validate() if "posture" in e]
        assert errors == [], f"posture '{p}' should be valid"


def test_backwards_compat_all_stances_valid():
    """Every entry in BIPED_STANCES validates cleanly."""
    for s in BIPED_STANCES:
        st = AssetState(asset_id="test", stance=s)
        errors = [e for e in st.validate() if "stance" in e]
        assert errors == [], f"stance '{s}' should be valid"
