# AI-generated threat assessment
string contact_id
string classification         # Specific type (e.g., T-72_TANK, TECHNICAL, CIVILIAN_VEH)
uint8 threat_level            # 0=NONE, 1=LOW, 2=MEDIUM, 3=HIGH, 4=CRITICAL
float64 confidence            # 0.0 - 1.0
string recommended_action     # MONITOR, TRACK, AVOID, ENGAGE, REPORT
string[] indicators           # Evidence supporting the classification
float64 latitude
float64 longitude
float64 altitude_m
string assigned_tracker_id    # Asset assigned to track this threat
builtin_interfaces/Time stamp
