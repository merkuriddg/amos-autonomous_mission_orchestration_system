# Swarm Reconnaissance

Drone swarm deploys into contested zone, adapts to GPS jamming and battery loss, and tracks a high-value target — demonstrating emergent swarm behaviors and resilient operations.

**Audience:** Special operations, defense R&D, swarm researchers

## Run

```bash
./run_demo.sh swarm_recon
```

## Scenario Flow (12 injects, ~2 minutes)

1. Swarm of 5 drones launches from forward operating base
2. Swarm enters contested zone — formation shifts to spread search
3. GPS jamming detected — swarm switches to INS/visual navigation
4. Drone 3 detects RF emission — swarm converges for investigation
5. SIGINT confirms high-value target communications
6. Swarm reorganizes into surveillance pattern
7. Drone 2 battery critical — swarm redistributes coverage autonomously
8. Target begins moving — swarm tracks with predictive positioning
9. EW jamming intensifies — mesh network adapts frequencies
10. Operator approves sustained surveillance posture
11. Target reaches destination — AMOS generates intelligence report
12. Swarm returns to base — debrief data uploaded

## Key Capabilities Demonstrated

- Reynolds flocking with emergent behaviors
- Autonomous adaptation to denied environments
- Self-healing swarm (battery/attrition recovery)
- Contested RF environment operations
- Predictive target tracking
