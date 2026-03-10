# Quickstart — Hello AMOS

Minimal example showing how to connect to a running AMOS instance and interact with the API.

## Prerequisites

```bash
# Start AMOS
python3 web/app.py
```

## Connect via Python

```python
import requests

AMOS_URL = "http://localhost:2600"

# Login
session = requests.Session()
session.post(f"{AMOS_URL}/login", data={
    "username": "commander",
    "password": "amos_op1"
})

# Get all assets
assets = session.get(f"{AMOS_URL}/api/v1/assets").json()
print(f"Assets: {len(assets)}")

# Get threats
threats = session.get(f"{AMOS_URL}/api/v1/threats").json()
print(f"Threats: {len(threats)}")

# Send a waypoint command
session.post(f"{AMOS_URL}/api/v1/assets/GHOST-1/waypoint", json={
    "lat": 27.85,
    "lng": -82.52,
    "alt_ft": 500
})

# Get simulation status
status = session.get(f"{AMOS_URL}/api/v1/sim/status").json()
print(f"Sim time: {status['elapsed_sec']}s")
```

## Connect via curl

```bash
# Login and save cookie
curl -c cookies.txt -X POST http://localhost:2600/login \
    -d "username=commander&password=amos_op1" -L

# List assets
curl -b cookies.txt http://localhost:2600/api/v1/assets | python3 -m json.tool

# Send waypoint
curl -b cookies.txt -X POST http://localhost:2600/api/v1/assets/GHOST-1/waypoint \
    -H "Content-Type: application/json" \
    -d '{"lat": 27.85, "lng": -82.52, "alt_ft": 500}'
```
