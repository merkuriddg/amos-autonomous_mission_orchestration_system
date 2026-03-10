# Disaster Response — Earthquake SAR

Major earthquake strikes urban area. AMOS coordinates drones for aerial damage mapping, ground robots for structural inspection, and prioritizes rescue operations — demonstrating civil/humanitarian applications.

**Audience:** FEMA, first responders, civil robotics, humanitarian organizations

## Run

```bash
./run_demo.sh disaster_response
```

## Scenario Flow (14 injects, ~2 minutes)

1. Earthquake alert received — AMOS activates emergency response mode
2. Drones launch for rapid aerial damage assessment
3. First drone identifies collapsed structure — marks priority zone
4. Ground robot dispatched for structural inspection
5. Thermal sensors detect survivors in rubble
6. AMOS prioritizes rescue tasks based on survivor probability
7. Second drone maps road blockages and access routes
8. Ground robot confirms structural stability for rescue team entry
9. AMOS coordinates helicopter landing zone clearance
10. Medical supply drone dispatched to triage point
11. Aftershock detected — AMOS reassesses structural risks
12. Updated rescue priorities distributed to all teams
13. Operator approves expanded search radius
14. Shift change — AMOS generates handoff briefing with full situational picture

## Key Capabilities Demonstrated

- Multi-domain coordination (air + ground + logistics)
- Autonomous task prioritization
- Thermal/sensor fusion for survivor detection
- Dynamic replanning (aftershock adaptation)
- Automated briefing generation
