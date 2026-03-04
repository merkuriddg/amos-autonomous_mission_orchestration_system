#!/bin/bash
# Quick script to test MOS with PX4 SITL
# Prerequisites: PX4-Autopilot built, ros-humble-mavros installed

G='\033[0;32m';C='\033[0;36m';Y='\033[1;33m';NC='\033[0m'

echo -e "${C}[MOS] Connecting to PX4 SITL via MAVROS...${NC}"

# 1. Update HAL config to enable one MAVLink vehicle
python3 << 'PYEOF'
import yaml
cfg_path = '$HOME/mos_ws/src/mos_core/config/hal_config.yaml'.replace('$HOME', __import__('os').environ['HOME'])
with open(cfg_path) as f:
    cfg = yaml.safe_load(f)

cfg['hal']['asset_map']['MVRX-HW01'] = {
    'source': 'mavlink',
    'callsign': 'REAPER-1',
    'type': 'AIR',
    'namespace': '/mavros',
    'connection': 'udp://:14540@127.0.0.1:14557',
}

with open(cfg_path, 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False)
print('HAL config updated with SITL vehicle')
PYEOF

# 2. Launch MAVROS
echo -e "${Y}[MOS] Starting MAVROS node...${NC}"
ros2 launch mavros px4.launch.py fcu_url:=udp://:14540@127.0.0.1:14557 &
sleep 3

echo -e "${G}[MOS] MAVROS started. Now restart MOS to pick up the HAL config.${NC}"
echo -e "${C}[MOS] Run: ./launch_mos.sh${NC}"
echo -e "${C}[MOS] Then check: http://localhost:5000/hal${NC}"
