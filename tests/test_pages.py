"""Page route tests — verify all HTML pages load for authenticated users."""

import pytest

# All pages that should be accessible to commander
PAGES = [
    "/", "/dashboard", "/ew", "/sigint", "/cyber", "/countermeasures",
    "/hal", "/planner", "/aar", "/awacs", "/field", "/fusion",
    "/cognitive", "/contested", "/redforce", "/readiness", "/killweb",
    "/roe", "/predictions", "/automation", "/settings", "/tactical",
    "/docs", "/integrations", "/video", "/analytics", "/missionplan",
    "/syscmd", "/training", "/commsnet", "/logistics", "/weather",
    "/bda", "/eob", "/wargame", "/swarm", "/isr", "/effects",
    "/space", "/hmt", "/mesh", "/scripts", "/edition", "/manual",
    "/drone-reference",
]


@pytest.mark.parametrize("path", PAGES)
def test_page_loads_authenticated(auth_client, path):
    """Each page returns 200 for an authenticated commander."""
    resp = auth_client.get(path)
    assert resp.status_code == 200, f"{path} returned {resp.status_code}"


@pytest.mark.parametrize("path", PAGES)
def test_page_redirects_unauthenticated(client, path):
    """Each page redirects to /login when not authenticated."""
    resp = client.get(path, follow_redirects=False)
    assert resp.status_code == 302, f"{path} returned {resp.status_code}"
    assert "/login" in resp.headers.get("Location", "")
