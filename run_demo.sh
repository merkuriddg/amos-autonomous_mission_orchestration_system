#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# AMOS Demo Launcher
# One command to run a fully simulated autonomous mission.
#
# Usage:
#   ./run_demo.sh                     # default: Border Patrol
#   ./run_demo.sh border_patrol       # Border security scenario
#   ./run_demo.sh swarm_recon         # Swarm reconnaissance
#   ./run_demo.sh disaster_response   # Disaster SAR coordination
# ─────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCENARIO="${1:-border_patrol}"
# Look in examples/ first (new layout), fall back to demo/scenarios/ (legacy)
if [[ -f "$SCRIPT_DIR/examples/${SCENARIO}/scenario.json" ]]; then
    SCENARIO_FILE="$SCRIPT_DIR/examples/${SCENARIO}/scenario.json"
elif [[ -f "$SCRIPT_DIR/examples/${SCENARIO}.json" ]]; then
    SCENARIO_FILE="$SCRIPT_DIR/examples/${SCENARIO}.json"
elif [[ -f "$SCRIPT_DIR/demo/scenarios/${SCENARIO}.json" ]]; then
    SCENARIO_FILE="$SCRIPT_DIR/demo/scenarios/${SCENARIO}.json"
else
    SCENARIO_FILE="$SCRIPT_DIR/examples/${SCENARIO}/scenario.json"
fi
PORT=2600
URL="http://localhost:$PORT"
PYTHON="$SCRIPT_DIR/.venv/bin/python3"

# ── Helpers ─────────────────────────────────────────────
info()  { printf "\033[1;34m▸ %s\033[0m\n" "$1"; }
ok()    { printf "\033[1;32m✔ %s\033[0m\n" "$1"; }
fail()  { printf "\033[1;31m✗ %s\033[0m\n" "$1"; exit 1; }

# ── Banner ──────────────────────────────────────────────
echo ""
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║     AMOS — Autonomous Mission Demo        ║"
echo "  ╚═══════════════════════════════════════════╝"
echo ""

# ── Validate scenario ──────────────────────────────────
[[ -f "$SCENARIO_FILE" ]] || {
    fail "Scenario not found: $SCENARIO_FILE"
    echo "  Available scenarios:"
    for d in "$SCRIPT_DIR"/examples/*/; do
        [[ -f "$d/scenario.json" ]] && echo "    $(basename "$d")"
    done
    ls "$SCRIPT_DIR/demo/scenarios/"*.json 2>/dev/null | while read -r f; do
        echo "    $(basename "$f" .json)"
    done
    exit 1
}

SCENARIO_NAME=$(python3 -c "import json; print(json.load(open('$SCENARIO_FILE'))['name'])" 2>/dev/null || echo "$SCENARIO")
info "Scenario: $SCENARIO_NAME"

# ── Environment setup ──────────────────────────────────
if [[ ! -d "$SCRIPT_DIR/.venv" ]]; then
    info "Creating virtual environment"
    python3 -m venv "$SCRIPT_DIR/.venv"
fi

if [[ ! -f "$PYTHON" ]]; then
    PYTHON="python3"
fi

info "Installing dependencies"
"$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt" -q 2>/dev/null

if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    ok "Created .env from .env.example"
fi

# ── Kill any existing AMOS on this port ─────────────────
if lsof -ti:$PORT >/dev/null 2>&1; then
    info "Stopping existing AMOS instance on port $PORT"
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# ── Start AMOS ─────────────────────────────────────────
info "Starting AMOS server"
nohup "$PYTHON" "$SCRIPT_DIR/web/app.py" > /tmp/amos_demo.log 2>&1 &
AMOS_PID=$!
echo "  PID: $AMOS_PID"

# ── Wait for server to be ready ─────────────────────────
info "Waiting for server"
for i in $(seq 1 30); do
    if curl -s "$URL/api/v1/healthz" >/dev/null 2>&1; then
        ok "Server ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        fail "Server did not start within 30s. Check /tmp/amos_demo.log"
    fi
    sleep 1
done

# ── Login and get session cookie ────────────────────────
info "Authenticating as commander"
COOKIE_JAR="/tmp/amos_demo_cookies.txt"
curl -s -c "$COOKIE_JAR" -X POST "$URL/login" \
    -d "username=commander&password=amos_op1" \
    -L -o /dev/null

# ── Get current sim clock for offset calculation ────────
ELAPSED=$(curl -s -b "$COOKIE_JAR" "$URL/api/v1/sim/status" | python3 -c "import sys,json; print(json.load(sys.stdin).get('elapsed_sec',0))" 2>/dev/null || echo "0")

# ── Build exercise payload from scenario file ───────────
info "Loading scenario: $SCENARIO"
PAYLOAD=$("$PYTHON" -c "
import json, sys
with open('$SCENARIO_FILE') as f:
    scenario = json.load(f)
elapsed = float('$ELAPSED')
injects = []
for inj in scenario['injects']:
    entry = dict(inj)
    entry['trigger_at_sec'] = elapsed + entry.pop('trigger_at_offset', 0)
    # Resolve lat/lng offsets relative to current base position
    if 'lat_offset' in entry:
        entry.pop('lat_offset')  # sim engine uses base_pos
    if 'lng_offset' in entry:
        entry.pop('lng_offset')
    injects.append(entry)
payload = {'name': scenario['name'], 'injects': injects}
print(json.dumps(payload))
")

# ── Start the exercise ──────────────────────────────────
RESULT=$(curl -s -b "$COOKIE_JAR" -X POST "$URL/api/v1/exercise/start" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")

INJECT_COUNT=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('exercise',{}).get('injects',[])))" 2>/dev/null || echo "?")
ok "Exercise started — $INJECT_COUNT injects loaded"

# ── Speed up sim slightly for demo pacing ───────────────
curl -s -b "$COOKIE_JAR" -X POST "$URL/api/v1/sim/speed" \
    -H "Content-Type: application/json" \
    -d '{"speed": 2.0}' >/dev/null

# ── Open browser ────────────────────────────────────────
info "Opening browser"
if command -v open >/dev/null 2>&1; then
    open "$URL"
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL"
else
    echo "  Open in your browser: $URL"
fi

# ── Done ────────────────────────────────────────────────
echo ""
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║  AMOS Demo Running                        ║"
echo "  ║                                           ║"
echo "  ║  URL:   $URL                    ║"
echo "  ║  Login: commander / amos_op1              ║"
echo "  ║  Speed: 2x (adjustable in UI)             ║"
echo "  ║                                           ║"
echo "  ║  Watch the alerts panel for mission        ║"
echo "  ║  events as the scenario unfolds.           ║"
echo "  ║                                           ║"
echo "  ║  Press Ctrl+C to stop.                     ║"
echo "  ╚═══════════════════════════════════════════╝"
echo ""

# ── Keep running (trap Ctrl+C to cleanup) ───────────────
cleanup() {
    echo ""
    info "Shutting down AMOS demo"
    kill "$AMOS_PID" 2>/dev/null || true
    rm -f "$COOKIE_JAR"
    ok "Demo stopped"
}
trap cleanup EXIT INT TERM

# Follow the log so the user sees activity
tail -f /tmp/amos_demo.log 2>/dev/null || wait "$AMOS_PID"
