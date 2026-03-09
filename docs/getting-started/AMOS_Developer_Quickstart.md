# AMOS Developer Quickstart
Run your first **autonomous mission with 5 robotic assets in under two minutes.**

This quickstart launches the AMOS simulator, deploys a small robotic team, and executes a basic mission.

---

## 1. Clone the Repository

```bash
git clone https://github.com/YOUR_ORG/amos.git
cd amos

2. Start the AMOS Platform
python3 web/app.py

You should see:
AMOS server running on http://localhost:2600

⸻

3. Open the Command Console

Open your browser:
http://localhost:2600

Login with:
username: commander
password: mavrix2026


⸻

4. Deploy a 5-Asset Team

From the command console or API:
curl -X POST http://localhost:2600/api/assets/deploy \
-d '{
  "air": 2,
  "ground": 2,
  "maritime": 1
}'

This creates:
	•	2 UAV ISR drones
	•	2 UGV patrol robots
	•	1 USV maritime patrol unit

⸻

5. Launch Your First Mission

Create a patrol mission:
curl -X POST http://localhost:2600/api/missions/create \
-d '{
  "mission_type": "perimeter_security",
  "area": "sector_alpha",
  "autonomy": "monitored"
}'

AMOS will automatically:
	•	allocate assets
	•	generate a task graph
	•	assign mission tasks
	•	begin autonomous patrol operations

⸻

6. Observe the Mission

Open the tactical map and watch:
	•	assets deploy
	•	patrol routes form
	•	telemetry updates stream
	•	mission events appear in real time

You are now running a multi-domain autonomous mission.

⸻

What Just Happened

In under two minutes you launched:
	•	a mission orchestration engine
	•	a robotic team across air, ground, and maritime domains
	•	autonomous task allocation
	•	telemetry streaming
	•	event-driven coordination

All coordinated by AMOS — the Autonomous Mission Operating System.

⸻

Explore Additional Capabilities

Try additional APIs:
/api/coa/generate
/api/wargame/run
/api/swarm/status
/api/isr/targets
/api/mesh/topology

Or run the full 25-asset robotic platoon simulation.

See:
docs/architecture/
for system design and platform documentation.
---

## Where this should live in your repo

Recommended structure now:
amos/
├─ README.md
├─ docs/
│  ├─ getting-started/
│  │  └─ AMOS_Developer_Quickstart.md
│  ├─ architecture/
│  │  ├─ AMOS_Core_Contracts.md
│  │  ├─ AMOS_Platform_Architecture.md
│  │  ├─ AMOS_Plugin_SDK.md
│  │  ├─ AMOS_Mission_Model.md
│  │  ├─ AMOS_Event_Model.md
│  │  └─ AMOS_Simulation_Environment.md

---

## One more small trick (that massively increases adoption)

At the **very top of your README**, add:

```markdown
🚀 **Run a 5-asset autonomous mission in under 2 minutes → [Quickstart](docs/getting-started/AMOS_Developer_Quickstart.md)**