"""CQB Formation Engine + Asset State API Tests.

Tests the meter-scale CQB formations (B1.3) and the asset state / CQB API endpoints.
"""

import sys, os, math, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.cqb_formations import CQBFormation


# ═══════════════════════════════════════════════════════════
#  CQB FORMATION ENGINE — unit tests
# ═══════════════════════════════════════════════════════════

def test_available_formations():
    """CQBFormation.available() returns all 6 types."""
    avail = CQBFormation.available()
    assert len(avail) == 6
    for f in ("STACK", "BUTTONHOOK", "CRISSCROSS", "BOUNDING_OVERWATCH", "PERIMETER", "CORRIDOR"):
        assert f in avail


def test_stack_count():
    """STACK returns correct number of positions."""
    for n in (1, 4, 8):
        pts = CQBFormation.stack(count=n, use_local=True)
        assert len(pts) == n


def test_stack_lead_at_origin():
    """STACK lead asset is at (0, 0) in local coords."""
    pts = CQBFormation.stack(count=4, use_local=True)
    assert pts[0]["x_m"] == 0.0
    assert pts[0]["y_m"] == 0.0


def test_stack_spacing():
    """STACK assets are spaced correctly along heading=0 (north)."""
    pts = CQBFormation.stack(count=3, heading_deg=0, spacing_m=1.0, use_local=True)
    # Heading 0 = north, so assets stack behind (negative y)
    assert pts[0]["y_m"] == 0.0
    assert abs(pts[1]["y_m"] - (-1.0)) < 0.01
    assert abs(pts[2]["y_m"] - (-2.0)) < 0.01


def test_buttonhook_count():
    """BUTTONHOOK returns correct number of positions."""
    pts = CQBFormation.buttonhook(count=6, use_local=True)
    assert len(pts) == 6


def test_buttonhook_pairs_split():
    """BUTTONHOOK pairs go to opposite sides."""
    pts = CQBFormation.buttonhook(count=4, heading_deg=0, spacing_m=1.5, use_local=True)
    # First pair: asset 0 (left/+x), asset 1 (right/-x)
    assert pts[0]["x_m"] > 0  # left side
    assert pts[1]["x_m"] < 0  # right side


def test_crisscross_count():
    """CRISSCROSS returns correct number of positions."""
    pts = CQBFormation.crisscross(count=5, use_local=True)
    assert len(pts) == 5


def test_crisscross_alternating_sides():
    """CRISSCROSS alternates left/right."""
    pts = CQBFormation.crisscross(count=4, heading_deg=0, spacing_m=1.5, use_local=True)
    # Even indices go one side, odd the other
    assert (pts[0]["x_m"] > 0) != (pts[1]["x_m"] > 0)


def test_bounding_overwatch_count():
    """BOUNDING_OVERWATCH returns correct number of positions."""
    pts = CQBFormation.bounding_overwatch(count=6, use_local=True)
    assert len(pts) == 6


def test_bounding_overwatch_movers_forward():
    """Odd-indexed assets (movers) are forward of even-indexed (overwatchers)."""
    pts = CQBFormation.bounding_overwatch(count=4, heading_deg=0, spacing_m=3.0, use_local=True)
    # Heading=0 means forward = +y
    assert pts[1]["y_m"] > pts[0]["y_m"]  # mover is ahead of overwatcher


def test_perimeter_count():
    """PERIMETER returns correct number of positions."""
    pts = CQBFormation.perimeter(count=8, use_local=True)
    assert len(pts) == 8


def test_perimeter_radius():
    """PERIMETER assets are at specified radius from center."""
    radius = 5.0
    pts = CQBFormation.perimeter(count=4, radius_m=radius, use_local=True)
    for p in pts:
        dist = math.sqrt(p["x_m"] ** 2 + p["y_m"] ** 2)
        assert abs(dist - radius) < 0.01


def test_corridor_count():
    """CORRIDOR returns correct number of positions."""
    pts = CQBFormation.corridor(count=6, use_local=True)
    assert len(pts) == 6


def test_corridor_alternating_walls():
    """CORRIDOR assets alternate left/right walls."""
    pts = CQBFormation.corridor(count=4, heading_deg=0, wall_offset_m=0.5, use_local=True)
    # Even-indexed go one side, odd the other (when heading=0, x = lateral)
    assert (pts[0]["x_m"] > 0) != (pts[1]["x_m"] > 0)


def test_compute_dispatcher():
    """CQBFormation.compute() dispatches correctly."""
    pts = CQBFormation.compute("STACK", 3, use_local=True)
    assert len(pts) == 3


def test_compute_invalid_formation():
    """CQBFormation.compute() raises ValueError for unknown formation."""
    with pytest.raises(ValueError, match="Unknown CQB formation"):
        CQBFormation.compute("NONEXISTENT", 4)


def test_latlng_mode():
    """Default (use_local=False) returns lat/lng positions."""
    pts = CQBFormation.stack(count=2, ref_lat=35.689, ref_lng=51.312)
    assert "lat" in pts[0]
    assert "lng" in pts[0]
    assert "x_m" not in pts[0]


def test_local_mode():
    """use_local=True returns x_m/y_m positions."""
    pts = CQBFormation.stack(count=2, use_local=True)
    assert "x_m" in pts[0]
    assert "y_m" in pts[0]
    assert "lat" not in pts[0]


def test_heading_rotates():
    """Different headings produce different positions for the same formation."""
    pts0 = CQBFormation.corridor(count=4, heading_deg=0, use_local=True)
    pts90 = CQBFormation.corridor(count=4, heading_deg=90, use_local=True)
    # At least one position should differ significantly
    diffs = [abs(a["x_m"] - b["x_m"]) + abs(a["y_m"] - b["y_m"]) for a, b in zip(pts0, pts90)]
    assert max(diffs) > 0.1


# ═══════════════════════════════════════════════════════════
#  API ENDPOINT TESTS (require Flask test client)
# ═══════════════════════════════════════════════════════════

def test_asset_states_endpoint(auth_client):
    """GET /api/v1/assets/state returns environment_type and states dict."""
    resp = auth_client.get("/api/v1/assets/state")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "environment_type" in data
    assert "states" in data
    assert isinstance(data["states"], dict)


def test_asset_state_detail(auth_client):
    """GET /api/v1/assets/<id>/state returns state for known asset."""
    # Use REAPER-01 which should exist from config
    resp = auth_client.get("/api/v1/assets/REAPER-01/state")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["asset_id"] == "REAPER-01"
    assert "posture" in data
    assert "stance" in data


def test_asset_state_detail_missing(auth_client):
    """GET /api/v1/assets/<id>/state returns 404 for unknown asset."""
    resp = auth_client.get("/api/v1/assets/NONEXISTENT-99/state")
    assert resp.status_code == 404


def _ensure_test_asset(auth_client, aid="CQB-TEST-01"):
    """Helper: guarantee an asset exists in sim_assets for PUT tests."""
    auth_client.post("/api/v1/settings/assets/save", json={
        "id": aid, "type": "bipedal", "domain": "ground", "role": "cqb",
    })


def test_asset_state_update(auth_client):
    """PUT /api/v1/assets/<id>/state updates fields."""
    _ensure_test_asset(auth_client, "CQB-TEST-01")
    resp = auth_client.put("/api/v1/assets/CQB-TEST-01/state",
                           json={"posture": "standing", "stance": "ready", "fatigue_pct": 88.5})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["state"]["posture"] == "standing"
    assert data["state"]["fatigue_pct"] == 88.5


def test_asset_state_update_validation(auth_client):
    """PUT /api/v1/assets/<id>/state rejects invalid values."""
    _ensure_test_asset(auth_client, "CQB-TEST-02")
    resp = auth_client.put("/api/v1/assets/CQB-TEST-02/state",
                           json={"posture": "flying_backwards"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_asset_state_update_missing_asset(auth_client):
    """PUT /api/v1/assets/<id>/state returns 404 for unknown asset."""
    resp = auth_client.put("/api/v1/assets/GHOST-99/state",
                           json={"posture": "standing"})
    assert resp.status_code == 404


def test_cqb_formations_list(auth_client):
    """GET /api/v1/cqb/formations returns formation types."""
    resp = auth_client.get("/api/v1/cqb/formations")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "formations" in data
    assert len(data["formations"]) == 6


def test_cqb_compute(auth_client):
    """POST /api/v1/cqb/compute returns positions."""
    resp = auth_client.post("/api/v1/cqb/compute", json={
        "formation": "STACK", "count": 4, "heading_deg": 90, "spacing_m": 1.0
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["formation"] == "STACK"
    assert len(data["positions"]) == 4


def test_cqb_compute_local(auth_client):
    """POST /api/v1/cqb/compute with use_local returns x_m/y_m."""
    resp = auth_client.post("/api/v1/cqb/compute", json={
        "formation": "CORRIDOR", "count": 3, "use_local": True
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "x_m" in data["positions"][0]


def test_cqb_compute_invalid_formation(auth_client):
    """POST /api/v1/cqb/compute with bad formation returns 400."""
    resp = auth_client.post("/api/v1/cqb/compute", json={
        "formation": "NONSENSE", "count": 4
    })
    assert resp.status_code == 400


def test_cqb_compute_count_bounds(auth_client):
    """POST /api/v1/cqb/compute rejects count outside 1-20."""
    resp = auth_client.post("/api/v1/cqb/compute", json={
        "formation": "STACK", "count": 0
    })
    assert resp.status_code == 400
    resp2 = auth_client.post("/api/v1/cqb/compute", json={
        "formation": "STACK", "count": 25
    })
    assert resp2.status_code == 400
