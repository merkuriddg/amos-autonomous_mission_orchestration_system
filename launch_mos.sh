#!/bin/bash
# ══════════════════════════════════════════════════════════════════
#  MOS — Mission Operating System Launch Script
#  Clears all previous processes and starts the full stack
# ══════════════════════════════════════════════════════════════════

set +e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║     ⬡  MOS — MISSION OPERATING SYSTEM          ║"
echo "  ║        Launch Sequence Initiated                 ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

MOS_WS="$HOME/mos_ws"

# ── Phase 1: Kill all existing processes ──────────────────────────
echo -e "${YELLOW}[1/6] Clearing previous processes...${NC}"
pkill -f simulated_platoon 2>/dev/null || true
pkill -f asset_registry 2>/dev/null || true
pkill -f autonomy_manager 2>/dev/null || true
pkill -f mission_planner 2>/dev/null || true
pkill -f swarm_orchestrator 2>/dev/null || true
pkill -f c2_server 2>/dev/null || true
pkill -f threat_injector 2>/dev/null || true
pkill -f threat_classifier 2>/dev/null || true
fuser -k 5000/tcp 2>/dev/null || true
sleep 2
echo -e "${GREEN}  ✓ All previous MOS processes cleared${NC}"

# ── Phase 2: Build ────────────────────────────────────────────────
echo -e "${YELLOW}[2/6] Building workspace...${NC}"
cd "$MOS_WS"
colcon build 2>&1 | tail -3
source install/setup.bash
echo -e "${GREEN}  ✓ Build complete${NC}"

# ── Phase 3: Start Simulated Platoon ─────────────────────────────
echo -e "${YELLOW}[3/6] Deploying simulated platoon (25 assets)...${NC}"
ros2 run mos_sim simulated_platoon &
SIM_PID=$!
sleep 2
echo -e "${GREEN}  ✓ Simulated platoon running (PID: $SIM_PID)${NC}"

# ── Phase 4: Start Core Nodes ────────────────────────────────────
echo -e "${YELLOW}[4/6] Starting MOS core nodes...${NC}"
ros2 run mos_core asset_registry &
AR_PID=$!
sleep 0.5

ros2 run mos_core autonomy_manager &
AM_PID=$!
sleep 0.5

ros2 run mos_mission_planner mission_planner &
MP_PID=$!
sleep 0.5

ros2 run mos_swarm swarm_orchestrator &
SO_PID=$!
sleep 0.5

echo -e "${GREEN}  ✓ Asset Registry   (PID: $AR_PID)${NC}"
echo -e "${GREEN}  ✓ Autonomy Manager (PID: $AM_PID)${NC}"
echo -e "${GREEN}  ✓ Mission Planner  (PID: $MP_PID)${NC}"
echo -e "${GREEN}  ✓ Swarm Orchestrator (PID: $SO_PID)${NC}"

# ── Phase 5: Start Threat Detection (optional) ───────────────────
echo -e "${YELLOW}[5/6] Starting threat detection...${NC}"
ros2 run mos_threat_detection threat_injector &
TI_PID=$!
sleep 0.5

ros2 run mos_threat_detection threat_classifier &
TC_PID=$!
sleep 0.5

echo -e "${GREEN}  ✓ Threat Injector   (PID: $TI_PID)${NC}"
echo -e "${GREEN}  ✓ Threat Classifier (PID: $TC_PID)${NC}"

# ── Phase 6: Start C2 Console ────────────────────────────────────
echo -e "${YELLOW}[6/6] Starting C2 Console...${NC}"
ros2 run mos_c2_console c2_server &
C2_PID=$!
sleep 2
echo -e "${GREEN}  ✓ C2 Console running (PID: $C2_PID)${NC}"

# ── Summary ──────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}  ╔══════════════════════════════════════════════════╗"
echo -e "  ║  ${GREEN}✓ MOS FULLY OPERATIONAL${CYAN}                         ║"
echo -e "  ║                                                  ║"
echo -e "  ║  C2 Console: ${BOLD}http://localhost:5000${NC}${CYAN}              ║"
echo -e "  ║  Assets API: ${BOLD}http://localhost:5000/api/assets${NC}${CYAN}   ║"
echo -e "  ║  Threats API: ${BOLD}http://localhost:5000/api/threats${NC}${CYAN}  ║"
echo -e "  ║                                                  ║"
echo -e "  ║  Processes: 8 nodes running                      ║"
echo -e "  ║  Press Ctrl+C to shutdown all                    ║"
echo -e "  ╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Trap Ctrl+C to clean shutdown ────────────────────────────────
cleanup() {
    echo ""
    echo -e "${RED}[MOS] Shutting down all processes...${NC}"
    kill $SIM_PID $AR_PID $AM_PID $MP_PID $SO_PID $TI_PID $TC_PID $C2_PID 2>/dev/null || true
    fuser -k 5000/tcp 2>/dev/null || true
    echo -e "${GREEN}[MOS] All processes terminated. MOS offline.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Keep script running
wait
