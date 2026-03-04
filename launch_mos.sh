#!/bin/bash
set +e
G='\033[0;32m';C='\033[0;36m';R='\033[0;31m';Y='\033[1;33m';NC='\033[0m';B='\033[1m'
echo -e "${C}"
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║     ⬡  MOS — MISSION OPERATING SYSTEM          ║"
echo "  ║     Phase 8 — Hardware Bridge + AWACS            ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo -e "${NC}"
MOS_WS="$HOME/mos_ws"
PROCS="simulated_platoon asset_registry autonomy_manager sustainment_monitor \
# ── EW/SIGINT/CYBER NODES (Phase 9) ──────────────────
echo -e "${C}[MOS] Starting EW/SIGINT/Cyber suite...${NC}"
ros2 run mos_ew ew_manager &
sleep 0.3
ros2 run mos_ew sigint_collector &
sleep 0.3
ros2 run mos_ew cyber_ops &
sleep 0.3
ros2 run mos_ew sdr_bridge &
sleep 0.3
ros2 run mos_ew rf_analyzer &
sleep 0.3
echo -e "${G}[MOS] EW suite online — 5 nodes${NC}"

  mission_planner swarm_orchestrator sensor_fusion c2_server threat_injector \
  threat_classifier ai_decision_engine geofence_manager tak_bridge awacs_controller \
  mavlink_bridge"
echo -e "${Y}[1/9] Clearing...${NC}"
for proc in $PROCS; do pkill -f "$proc" 2>/dev/null || true; done
fuser -k 5000/tcp 2>/dev/null || true; sleep 2
echo -e "${G}  ✓ Cleared${NC}"
echo -e "${Y}[2/9] Building...${NC}"
cd "$MOS_WS"; colcon build 2>&1 | tail -3; source install/setup.bash
echo -e "${G}  ✓ Build complete${NC}"
echo -e "${Y}[3/9] Sim platoon + AWACS...${NC}"
ros2 run mos_sim simulated_platoon &
sleep 2
echo -e "${G}  ✓ Platoon online${NC}"
echo -e "${Y}[4/9] Core nodes...${NC}"
ros2 run mos_core asset_registry & sleep 0.3
ros2 run mos_core autonomy_manager & sleep 0.3
ros2 run mos_core sustainment_monitor & sleep 0.3
ros2 run mos_core ai_decision_engine & sleep 0.3
ros2 run mos_core geofence_manager & sleep 0.3
ros2 run mos_core tak_bridge & sleep 0.3
ros2 run mos_core awacs_controller & sleep 0.3
ros2 run mos_core mavlink_bridge & sleep 0.3
echo -e "${G}  ✓ Core: 8 nodes (incl. HAL + AWACS)${NC}"
echo -e "${Y}[5/9] Mission & swarm...${NC}"
ros2 run mos_mission_planner mission_planner & sleep 0.3
ros2 run mos_swarm swarm_orchestrator & sleep 0.3
echo -e "${G}  ✓ Mission Planner, Swarm Orchestrator${NC}"
echo -e "${Y}[6/9] Threat detection...${NC}"
ros2 run mos_threat_detection threat_injector & sleep 0.3
ros2 run mos_threat_detection threat_classifier & sleep 0.3
echo -e "${G}  ✓ Threat Injector, Classifier${NC}"
echo -e "${Y}[7/9] Sensor fusion...${NC}"
ros2 run mos_sim sensor_fusion & sleep 0.3
echo -e "${G}  ✓ Sensor Fusion${NC}"
echo -e "${Y}[8/9] C2 Console...${NC}"
# ── EW/SIGINT/CYBER NODES (Phase 9) ──────────────────
echo -e "${C}[MOS] Starting EW/SIGINT/Cyber suite...${NC}"
ros2 run mos_ew ew_manager &
sleep 0.3
ros2 run mos_ew sigint_collector &
sleep 0.3
ros2 run mos_ew cyber_ops &
sleep 0.3
ros2 run mos_ew sdr_bridge &
sleep 0.3
ros2 run mos_ew rf_analyzer &
sleep 0.3
echo -e "${G}[MOS] EW suite online — 5 nodes${NC}"

ros2 run mos_c2_console c2_server & sleep 2
echo -e "${G}  ✓ C2 Console${NC}"
echo -e "${Y}[9/9] Status check...${NC}"
NODE_COUNT=$(ros2 node list 2>/dev/null | wc -l)
echo -e "${G}  ✓ ${NODE_COUNT} ROS 2 nodes active${NC}"
echo ""
echo -e "${C}  ╔═══════════════════════════════════════════════════════════╗"
echo -e "  ║  ${G}✓ MOS PHASE 8 — HARDWARE BRIDGE + FULL CAPABILITY${C}       ║"
echo -e "  ║                                                           ║"
echo -e "  ║  C2 Console:     ${B}http://localhost:5000${NC}${C}                   ║"
echo -e "  ║  Digital Twin:    ${B}http://localhost:5000/dashboard${NC}${C}         ║"
echo -e "  ║  AWACS View:      ${B}http://localhost:5000/awacs${NC}${C}             ║"
echo -e "  ║  3D Tactical:     ${B}http://localhost:5000/tactical3d${NC}${C}        ║"
echo -e "  ║  Echelon View:    ${B}http://localhost:5000/echelon${NC}${C}           ║"
echo -e "  ║  AAR Replay:      ${B}http://localhost:5000/aar${NC}${C}               ║"
echo -e "  ║  HAL Manager:     ${B}http://localhost:5000/hal${NC}${C}               ║"
echo -e "  ║                                                           ║"
echo -e "  ║  Nodes: 15 | Assets: 27 (25 + 2 AWACS)                   ║"
echo -e "  ║  TAK: UDP 239.2.3.1:6969 | MacDill AFB, Tampa FL         ║"
echo -e "  ║  HAL: sim mode (edit hal_config.yaml for real hardware)   ║"
echo -e "  ║  Press Ctrl+C to shutdown all                              ║"
echo -e "  ╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
cleanup(){
  echo -e "\n${R}[MOS] Shutting down...${NC}"
  for proc in $PROCS; do pkill -f "$proc" 2>/dev/null || true; done
  fuser -k 5000/tcp 2>/dev/null || true
  echo -e "${G}[MOS] Offline.${NC}"; exit 0
}
trap cleanup SIGINT SIGTERM; wait
