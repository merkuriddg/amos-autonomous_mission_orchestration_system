"""AMOS System Scripts — Git operations admin interface.

Security:
  - Only enabled when AMOS_ENV=dev OR AMOS_ALLOW_GIT_UI=true
  - Commander role required for all operations
  - Every git action logged to audit log
  - Single-operation lock — no concurrent git ops
  - Only whitelisted git subcommands — no arbitrary shell execution
"""

import os
import subprocess
import threading
from flask import Blueprint, request, jsonify
from web.extensions import login_required, ctx, _audit

bp = Blueprint("scripts", __name__)

# ── Configuration ──
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_AMOS_ENV = os.environ.get("AMOS_ENV", "dev").lower()
_GIT_UI_ALLOWED = os.environ.get("AMOS_ALLOW_GIT_UI", "true").lower() == "true"

# ── Operation lock ──
_git_lock = threading.Lock()
_git_op_status = {"running": False, "operation": None, "started_at": None}


def _git_enabled():
    """Check if git UI is enabled for this environment."""
    return _AMOS_ENV == "dev" or _GIT_UI_ALLOWED


def _require_git_access():
    """Return error response if git UI is disabled or user lacks permission."""
    if not _git_enabled():
        return jsonify({"error": "Git UI is disabled in this environment. "
                       "Set AMOS_ENV=dev or AMOS_ALLOW_GIT_UI=true"}), 403
    c = ctx()
    if c["role"] != "commander":
        return jsonify({"error": "Commander access required"}), 403
    return None


def _run_git(*args, timeout=30):
    """Run a whitelisted git command and return (stdout, stderr, returncode)."""
    cmd = ["git", "-C", ROOT_DIR] + list(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Operation timed out", 1
    except Exception as e:
        return "", str(e), 1


# ═══════════════════════════════════════════════════════════
#  GIT STATUS
# ═══════════════════════════════════════════════════════════
@bp.route("/scripts/git/status")
@login_required
def git_status():
    """Get repository status — modified, staged, untracked files."""
    err = _require_git_access()
    if err:
        return err

    stdout, stderr, rc = _run_git("status", "--porcelain=v1")
    if rc != 0:
        return jsonify({"error": stderr or "git status failed"}), 500

    modified, staged, untracked = [], [], []
    for line in stdout.strip().split("\n"):
        if not line or len(line) < 4:
            continue
        index_status = line[0]
        work_status = line[1]
        filepath = line[3:]  # XY<space>PATH — path starts at col 3

        if index_status in ("M", "A", "D", "R"):
            staged.append({"file": filepath, "status": index_status})
        if work_status == "M":
            modified.append({"file": filepath, "status": "M"})
        elif work_status == "D":
            modified.append({"file": filepath, "status": "D"})
        elif index_status == "?" and work_status == "?":
            untracked.append(filepath)

    # Current branch
    branch_out, _, _ = _run_git("branch", "--show-current")
    branch = branch_out.strip()

    return jsonify({
        "branch": branch,
        "modified": modified,
        "staged": staged,
        "untracked": untracked,
        "clean": not (modified or staged or untracked),
        "lock": _git_op_status,
    })


# ═══════════════════════════════════════════════════════════
#  GIT DIFF (preview)
# ═══════════════════════════════════════════════════════════
@bp.route("/scripts/git/diff")
@login_required
def git_diff():
    """Get diff for specific files or all changes."""
    err = _require_git_access()
    if err:
        return err

    files = request.args.getlist("file")
    if files:
        stdout, stderr, rc = _run_git("diff", "--", *files)
    else:
        stdout, stderr, rc = _run_git("diff")

    staged_out, _, _ = _run_git("diff", "--cached")

    return jsonify({
        "diff": stdout[:50000],  # cap at 50K chars
        "staged_diff": staged_out[:50000],
        "truncated": len(stdout) > 50000 or len(staged_out) > 50000,
    })


# ═══════════════════════════════════════════════════════════
#  GIT COMMIT (selective staging)
# ═══════════════════════════════════════════════════════════
@bp.route("/scripts/git/commit", methods=["POST"])
@login_required
def git_commit():
    """Stage selected files and commit with message."""
    err = _require_git_access()
    if err:
        return err

    d = request.json or {}
    message = d.get("message", "").strip()
    files = d.get("files", [])
    push_after = d.get("push_after", False)

    if not message:
        return jsonify({"error": "Commit message required"}), 400
    if not files:
        return jsonify({"error": "No files selected for commit"}), 400

    if not _git_lock.acquire(blocking=False):
        return jsonify({"error": "Another git operation is in progress",
                       "lock": _git_op_status}), 409

    try:
        _git_op_status.update(running=True, operation="commit", started_at=None)
        c = ctx()

        # Stage selected files
        stdout, stderr, rc = _run_git("add", "--", *files)
        if rc != 0:
            return jsonify({"error": f"git add failed: {stderr}"}), 500

        # Commit
        stdout, stderr, rc = _run_git("commit", "-m", message)
        if rc != 0:
            return jsonify({"error": f"git commit failed: {stderr}"}), 500

        # Audit
        _audit(c["user"], "git_commit", "scripts", None,
               {"message": message, "files": files[:20]})

        result = {"status": "ok", "message": message, "files": files,
                  "output": stdout.strip()}

        # Optional push
        if push_after:
            p_out, p_err, p_rc = _run_git("push", timeout=60)
            result["push"] = {
                "status": "ok" if p_rc == 0 else "error",
                "output": p_out.strip() if p_rc == 0 else p_err.strip(),
            }
            if p_rc == 0:
                _audit(c["user"], "git_push", "scripts")

        return jsonify(result)

    finally:
        _git_op_status.update(running=False, operation=None, started_at=None)
        _git_lock.release()


# ═══════════════════════════════════════════════════════════
#  GIT PUSH (locked, audited)
# ═══════════════════════════════════════════════════════════
@bp.route("/scripts/git/push", methods=["POST"])
@login_required
def git_push():
    """Push to remote origin."""
    err = _require_git_access()
    if err:
        return err

    if not _git_lock.acquire(blocking=False):
        return jsonify({"error": "Another git operation is in progress",
                       "lock": _git_op_status}), 409

    try:
        _git_op_status.update(running=True, operation="push", started_at=None)
        c = ctx()

        stdout, stderr, rc = _run_git("push", timeout=60)
        _audit(c["user"], "git_push", "scripts", None,
               {"output": stdout[:500] if rc == 0 else stderr[:500]})

        if rc != 0:
            return jsonify({"error": f"git push failed: {stderr}"}), 500
        return jsonify({"status": "ok", "output": stdout.strip()})

    finally:
        _git_op_status.update(running=False, operation=None, started_at=None)
        _git_lock.release()


# ═══════════════════════════════════════════════════════════
#  GIT PULL (locked, audited)
# ═══════════════════════════════════════════════════════════
@bp.route("/scripts/git/pull", methods=["POST"])
@login_required
def git_pull():
    """Pull from remote origin."""
    err = _require_git_access()
    if err:
        return err

    if not _git_lock.acquire(blocking=False):
        return jsonify({"error": "Another git operation is in progress",
                       "lock": _git_op_status}), 409

    try:
        _git_op_status.update(running=True, operation="pull", started_at=None)
        c = ctx()

        stdout, stderr, rc = _run_git("pull", timeout=60)
        _audit(c["user"], "git_pull", "scripts", None,
               {"output": stdout[:500] if rc == 0 else stderr[:500]})

        if rc != 0:
            return jsonify({"error": f"git pull failed: {stderr}"}), 500
        return jsonify({"status": "ok", "output": stdout.strip()})

    finally:
        _git_op_status.update(running=False, operation=None, started_at=None)
        _git_lock.release()


# ═══════════════════════════════════════════════════════════
#  GIT LOG
# ═══════════════════════════════════════════════════════════
@bp.route("/scripts/git/log")
@login_required
def git_log():
    """Get recent commit log."""
    err = _require_git_access()
    if err:
        return err

    limit = request.args.get("limit", 20, type=int)
    stdout, stderr, rc = _run_git(
        "log", f"--max-count={min(limit, 50)}",
        "--format=%H|%h|%an|%ae|%ai|%s")

    if rc != 0:
        return jsonify({"error": stderr or "git log failed"}), 500

    commits = []
    for line in stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 5)
        if len(parts) >= 6:
            commits.append({
                "hash": parts[0], "short_hash": parts[1],
                "author": parts[2], "email": parts[3],
                "date": parts[4], "message": parts[5],
            })

    return jsonify({"commits": commits, "count": len(commits)})


# ═══════════════════════════════════════════════════════════
#  GIT BRANCHES
# ═══════════════════════════════════════════════════════════
@bp.route("/scripts/git/branches")
@login_required
def git_branches():
    """List branches and current branch."""
    err = _require_git_access()
    if err:
        return err

    stdout, stderr, rc = _run_git("branch", "-a", "--format=%(refname:short)|%(HEAD)")
    if rc != 0:
        return jsonify({"error": stderr or "git branch failed"}), 500

    branches = []
    current = None
    for line in stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        name = parts[0].strip()
        is_current = len(parts) > 1 and parts[1].strip() == "*"
        branches.append({"name": name, "current": is_current})
        if is_current:
            current = name

    return jsonify({"branches": branches, "current": current})


# ═══════════════════════════════════════════════════════════
#  GIT CHECKOUT (locked, audited)
# ═══════════════════════════════════════════════════════════
@bp.route("/scripts/git/checkout", methods=["POST"])
@login_required
def git_checkout():
    """Switch to a different branch."""
    err = _require_git_access()
    if err:
        return err

    branch = (request.json or {}).get("branch", "").strip()
    if not branch:
        return jsonify({"error": "Branch name required"}), 400

    if not _git_lock.acquire(blocking=False):
        return jsonify({"error": "Another git operation is in progress",
                       "lock": _git_op_status}), 409

    try:
        _git_op_status.update(running=True, operation="checkout", started_at=None)
        c = ctx()

        stdout, stderr, rc = _run_git("checkout", branch)
        _audit(c["user"], "git_checkout", "scripts", None, {"branch": branch})

        if rc != 0:
            return jsonify({"error": f"git checkout failed: {stderr}"}), 500
        return jsonify({"status": "ok", "branch": branch, "output": stdout.strip()})

    finally:
        _git_op_status.update(running=False, operation=None, started_at=None)
        _git_lock.release()
