"""Scripts route tests — git operations (mocked subprocess)."""

from unittest.mock import patch, MagicMock


def test_git_status(auth_client):
    """GET /api/v1/scripts/git/status returns repo status."""
    with patch("web.routes.scripts._run_git") as mock_git:
        mock_git.side_effect = [
            ("M  web/app.py\n?? newfile.txt\n", "", 0),  # status
            ("main\n", "", 0),  # branch
        ]
        resp = auth_client.get("/api/v1/scripts/git/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "branch" in data
        assert "modified" in data
        assert "untracked" in data


def test_git_status_non_commander(pilot_client):
    """Non-commander cannot access git status."""
    resp = pilot_client.get("/api/v1/scripts/git/status")
    assert resp.status_code == 403


def test_git_log(auth_client):
    """GET /api/v1/scripts/git/log returns commit log."""
    log_output = "abc123|abc|Author|a@b.c|2026-03-10|Test commit\ndef456|def|Author|a@b.c|2026-03-09|Another\n"
    with patch("web.routes.scripts._run_git", return_value=(log_output, "", 0)):
        resp = auth_client.get("/api/v1/scripts/git/log")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "commits" in data
        assert len(data["commits"]) == 2
        assert data["commits"][0]["short_hash"] == "abc"


def test_git_branches(auth_client):
    """GET /api/v1/scripts/git/branches returns branch list."""
    branch_output = "main|*\ndev|\norigin/main|\n"
    with patch("web.routes.scripts._run_git", return_value=(branch_output, "", 0)):
        resp = auth_client.get("/api/v1/scripts/git/branches")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["current"] == "main"
        assert len(data["branches"]) == 3


def test_git_commit_no_message(auth_client):
    """POST /api/v1/scripts/git/commit without message returns 400."""
    resp = auth_client.post("/api/v1/scripts/git/commit", json={
        "files": ["test.py"],
    })
    assert resp.status_code == 400


def test_git_commit_no_files(auth_client):
    """POST /api/v1/scripts/git/commit without files returns 400."""
    resp = auth_client.post("/api/v1/scripts/git/commit", json={
        "message": "test commit",
    })
    assert resp.status_code == 400


def test_git_commit_success(auth_client):
    """POST /api/v1/scripts/git/commit stages and commits selected files."""
    with patch("web.routes.scripts._run_git") as mock_git:
        mock_git.side_effect = [
            ("", "", 0),  # git add
            ("1 file changed\n", "", 0),  # git commit
        ]
        resp = auth_client.post("/api/v1/scripts/git/commit", json={
            "message": "test commit",
            "files": ["web/app.py"],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"


def test_git_diff(auth_client):
    """GET /api/v1/scripts/git/diff returns diff output."""
    with patch("web.routes.scripts._run_git") as mock_git:
        mock_git.side_effect = [
            ("diff --git a/f b/f\n+added\n", "", 0),  # diff
            ("", "", 0),  # diff --cached
        ]
        resp = auth_client.get("/api/v1/scripts/git/diff")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "diff" in data


def test_scripts_page_loads(auth_client):
    """GET /scripts renders the scripts template."""
    resp = auth_client.get("/scripts")
    assert resp.status_code == 200
    assert b"SYSTEM SCRIPTS" in resp.data
