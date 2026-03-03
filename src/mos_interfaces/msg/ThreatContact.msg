# Raw sensor contact detected by an asset
string contact_id
string contact_type          # VEHICLE, DISMOUNT, UAS, VESSEL, IED, ELECTRONIC, UNKNOWN
string detecting_asset_id
string detecting_sensor       # EO, IR, RADAR, SIGINT, ACOUSTIC
float64 latitude
float64 longitude
float64 altitude_m
float64 confidence            # 0.0 - 1.0
float64 bearing_deg
float64 range_m
builtin_interfaces/Time stamp
