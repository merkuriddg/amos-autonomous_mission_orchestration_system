#!/bin/bash
# MOS Field Deployment Script
# Deploys MOS to a field laptop or Jetson device

G='\033[0;32m';C='\033[0;36m';R='\033[0;31m';Y='\033[1;33m';NC='\033[0m'

echo -e "${C}"
echo "  ╔════════════════════════════════════════════════╗"
echo "  ║     MOS FIELD DEPLOYMENT                       ║"
echo "  ╚════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${R}Docker not found. Install with: sudo apt install docker.io docker-compose${NC}"
    exit 1
fi

echo -e "${Y}[1/4] Building Docker image...${NC}"
cd ~/mos_ws
docker build -t mos:latest . 2>&1 | tail -5

echo -e "${Y}[2/4] Checking HAL config...${NC}"
if grep -q "source: mavlink" src/mos_core/config/hal_config.yaml; then
    echo -e "${G}  ✓ Real vehicle connections configured${NC}"
else
    echo -e "${Y}  ⚠ No real vehicles in hal_config.yaml — running in simulation mode${NC}"
fi

echo -e "${Y}[3/4] Starting MOS container...${NC}"
docker-compose up -d mos

echo -e "${Y}[4/4] Verifying...${NC}"
sleep 5
if curl -s http://localhost:5000 > /dev/null; then
    echo -e "${G}  ✓ MOS is running${NC}"
else
    echo -e "${R}  ✗ C2 console not responding${NC}"
fi

echo -e "${C}"
echo "  ╔════════════════════════════════════════════════════╗"
echo "  ║  MOS DEPLOYED                                      ║"
echo "  ║  C2: http://localhost:5000                          ║"
echo "  ║  HAL: http://localhost:5000/hal                     ║"
echo "  ║                                                    ║"
echo "  ║  To connect real drone:                             ║"
echo "  ║  1. Edit src/mos_core/config/hal_config.yaml        ║"
echo "  ║  2. docker-compose restart mos                      ║"
echo "  ║                                                    ║"
echo "  ║  To run with PX4 SITL:                              ║"
echo "  ║  docker-compose --profile sitl up                   ║"
echo "  ╚════════════════════════════════════════════════════╝"
echo -e "${NC}"
