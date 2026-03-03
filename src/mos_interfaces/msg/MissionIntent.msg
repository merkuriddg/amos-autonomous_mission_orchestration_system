# Commander's intent — top-level mission directive
string mission_id
string mission_type        # ISR | SECURITY | PRECISION_EFFECTS | LOGISTICS | SAR | EW_SIGINT
string commander_intent    # Free-text intent statement
string[] objectives        # Decomposed objectives
string area_of_operations  # Geofence or AO identifier
uint8 priority             # 1=CRITICAL 2=HIGH 3=ROUTINE
builtin_interfaces/Time time_on_target
