# Unique identifier for each robotic asset
string asset_id
string asset_type          # AIR | GROUND | MARITIME
string callsign

# Position (WGS84)
float64 latitude
float64 longitude
float64 altitude_m

# Heading and speed
float32 heading_deg
float32 speed_mps

# Health & sustainment
float32 battery_pct
float32 comms_signal_dbm
uint8 autonomy_mode        # 0=MANUAL 1=ASSISTED 2=COLLABORATIVE 3=SWARM 4=COGNITIVE
uint8 mission_status       # 0=IDLE 1=TASKED 2=EXECUTING 3=RTB 4=FAULT

# Timestamp
builtin_interfaces/Time stamp
