# Contributing to AMOS

Thank you for your interest in contributing to **AMOS — the Autonomous Mission Operating System**.

AMOS is an open platform designed to enable **mission orchestration for autonomous systems across air, ground, maritime, cyber, and space domains**.

We welcome contributions from engineers, robotics researchers, autonomy developers, and system integrators.

---

# Ways to Contribute

You can contribute to AMOS in several ways:

### Platform Development

Improve the core system:

- Mission orchestration
- Event architecture
- Autonomy engines
- State management
- Authority enforcement

### Plugin Development

Create plugins that extend AMOS capabilities:

- Asset adapters (robots, drones, vehicles)
- Sensor adapters
- Mission packs
- Planning algorithms
- Analytics modules
- Transport integrations

### Documentation

Improve:

- architecture documentation
- developer guides
- plugin SDK examples
- tutorials

### Simulation

Extend the simulator:

- new asset models
- threat behaviors
- environment models
- test scenarios

---

# Development Setup

Clone the repository:

```bash
git clone https://github.com/YOUR_ORG/amos.git
cd amos

Install dependencies:
pip install -r requirements.txt

Run AMOS locally:
python3 web/app.py

Open:
http://localhost:2600





Plugin Development

Plugins are the preferred way to extend AMOS.

See:
docs/platform/AMOS_Plugin_SDK.md

Example plugin types:
	•	Asset adapters
	•	Sensor integrations
	•	Mission packs
	•	Autonomy planners
	•	Analytics modules

⸻

Pull Request Process
	1.	Fork the repository
	2.	Create a feature branch

git checkout -b feature/my-feature

	3.	Commit your changes
git commit -m "Add feature"

	4.	Push your branch

git push origin feature/my-feature

	5.	Open a Pull Request


⸻

Code Style

General guidelines:
	•	Write clear, readable Python
	•	Follow PEP8 where practical
	•	Document public functions
	•	Avoid unnecessary complexity

Architecture changes should include documentation updates.

⸻

Reporting Issues

If you discover a bug or have a feature request:

Create an issue with:
	•	clear description
	•	steps to reproduce
	•	expected behavior
	•	screenshots if applicable

⸻

Community

AMOS aims to build an ecosystem of developers working on autonomous mission systems.

We encourage:
	•	collaboration
	•	respectful discussion
	•	constructive feedback

Thank you for helping build the future of autonomous mission platforms.


---

# 2️⃣ LICENSE (Apache 2.0 – recommended)

Save this as:

LICENSE
```markdown
Apache License
Version 2.0, January 2004

Copyright 2026 Mavrix / Merkuri

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at:

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions
and limitations under the License.

Why Apache 2.0?

It:
	•	protects contributors
	•	allows commercial use
	•	is common for platforms (Kubernetes, ROS, etc.)