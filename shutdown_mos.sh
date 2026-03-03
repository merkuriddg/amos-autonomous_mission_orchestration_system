#!/bin/bash
# ══════════════════════════════════════════════════════════════════
#  MOS — Shutdown All Processes
# ══════════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}[MOS] Shutting down all MOS processes...${NC}"

pkill -f simulated_platoon 2>/dev/null || true
pkill -f asset_registry 2>/dev/null || true
pkill -f autonomy_manager 2>/dev/null || true
pkill -f mission_planner 2>/dev/null || true
pkill -f swarm_orchestrator 2>/dev/null || true
pkill -f c2_server 2>/dev/null || true
pkill -f threat_injector 2>/dev/null || true
pkill -f threat_classifier 2>/dev/null || true
fuser -k 5000/tcp 2>/dev/null || true

sleep 1
echo -e "${GREEN}[MOS] All processes terminated. MOS offline.${NC}"
