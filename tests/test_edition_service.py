"""Edition service tests — feature flags, is_enterprise, feature_enabled."""

from web.edition import FEATURES, feature_enabled, is_enterprise, AMOS_EDITION


def test_edition_is_set():
    """AMOS_EDITION is a recognized value."""
    assert AMOS_EDITION in ("open", "enterprise")


def test_is_enterprise_matches_env():
    """is_enterprise() reflects AMOS_EDITION."""
    if AMOS_EDITION == "enterprise":
        assert is_enterprise() is True
    else:
        assert is_enterprise() is False


def test_features_dict_not_empty():
    """FEATURES dict has entries."""
    assert len(FEATURES) > 0


def test_all_features_are_bool():
    """Every feature flag value is a boolean."""
    for name, val in FEATURES.items():
        assert isinstance(val, bool), f"Feature '{name}' is {type(val)}, expected bool"


def test_feature_enabled_known():
    """feature_enabled() returns bool for known features."""
    for name in FEATURES:
        result = feature_enabled(name)
        assert isinstance(result, bool)


def test_feature_enabled_unknown_defaults():
    """feature_enabled() for unknown feature defaults to is_enterprise()."""
    result = feature_enabled("totally_fake_feature_xyz")
    assert result == is_enterprise()


def test_enterprise_features_in_enterprise_mode():
    """In enterprise mode, default features should be enabled."""
    if AMOS_EDITION != "enterprise":
        return  # only test in enterprise mode
    core_features = ["cognitive", "hal", "swarm", "ew", "sigint"]
    for f in core_features:
        assert feature_enabled(f) is True, f"Feature '{f}' should be enabled in enterprise"


def test_feature_list_completeness():
    """Critical feature categories are represented."""
    expected_categories = ["cognitive", "hal", "swarm", "comsec", "tak", "link16", "ew", "sigint"]
    for cat in expected_categories:
        assert cat in FEATURES, f"Expected feature '{cat}' in FEATURES dict"
