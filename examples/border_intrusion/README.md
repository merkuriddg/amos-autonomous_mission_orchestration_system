# Border Intrusion Response

Sensor network detects unauthorized border crossing. AMOS coordinates drones and ground robots to investigate, track, and report — fully autonomous with human-in-the-loop approval gates.

**Audience:** DHS, border security, law enforcement

## Run

```bash
./run_demo.sh border_patrol
```

## Scenario Flow (11 injects, ~2 minutes)

1. Seismic sensor triggers along perimeter fence
2. AMOS tasks nearest drone for visual confirmation
3. Drone identifies group of individuals — image sent to operator
4. AMOS queues ground robot to intercept route
5. EW scan detects cell phone signals — SIGINT correlation
6. Operator approves track-and-report posture
7. Second drone repositions for overwatch
8. Ground robot reaches intercept point — live video feed
9. AMOS generates situation report for command
10. Operator escalates to law enforcement liaison
11. Assets return to standby positions — mission summary generated

## Key Capabilities Demonstrated

- Autonomous sensor-to-shooter cueing
- Multi-asset coordination (air + ground)
- SIGINT/EW integration
- Human-in-the-loop checkpoints
- Automated reporting
