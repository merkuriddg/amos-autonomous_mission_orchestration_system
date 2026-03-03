# Decomposed task assigned to a specific asset or group
string task_id
string mission_id
string assigned_asset_id
string task_type           # MOVE | OBSERVE | ENGAGE | RELAY | RESUPPLY | LOITER | RTB
float64 target_lat
float64 target_lon
float64 target_alt_m
string[] parameters        # Key-value pairs for task-specific config
uint8 priority
builtin_interfaces/Time deadline
