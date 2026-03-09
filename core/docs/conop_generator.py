"""AMOS Phase 3 — CONOP Generator
Produces a Concept of Operations summary from live AMOS mission state.
Shorter than OPORD — intended for quick briefing / decision briefs.
"""

import uuid
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).strftime("%d%H%MZ %b %Y").upper()


def generate_conop(platoon_config, assets, threats, coa_data=None,
                   aar_events=None, classification="UNCLASSIFIED"):
    """
    Generate a CONOP summary.

    Args:
        platoon_config: dict with platoon name, callsign, base, ao
        assets: dict of sim_assets
        threats: dict of sim_threats
        coa_data: optional COA analysis dict {threat_id: [coas]}
        aar_events: optional AAR event list for timeline
        classification: security classification

    Returns:
        dict with CONOP sections and text rendering
    """
    dtg = _now()
    name = platoon_config.get("name", "UNNAMED OPERATION")
    callsign = platoon_config.get("callsign", "UNKNOWN")
    base = platoon_config.get("base", {})

    active_threats = {k: v for k, v in threats.items() if not v.get("neutralized")}
    neutralized = {k: v for k, v in threats.items() if v.get("neutralized")}

    # Domain breakdown
    domains = {}
    for a in assets.values():
        d = a.get("domain", "unknown")
        domains[d] = domains.get(d, 0) + 1

    # Capability summary
    capabilities = {
        "isr": len([a for a in assets.values()
                    if a.get("role") in ("recon", "isr", "surveillance")]),
        "ew": len([a for a in assets.values()
                   if any(s in (a.get("sensors") or [])
                          for s in ["EW_JAMMER", "SIGINT", "ELINT"])]),
        "strike": len([a for a in assets.values() if a.get("weapons")]),
        "c2_relay": len([a for a in assets.values()
                        if a.get("role") in ("c2_relay", "overwatch")]),
    }

    # Best COA per threat
    coa_summary = []
    if coa_data:
        for tid, coas in coa_data.items():
            if coas:
                best = coas[0]
                coa_summary.append({
                    "threat_id": tid,
                    "coa_name": best["coa_name"],
                    "score": best["composite_score"],
                    "risk": best["risk"],
                    "p_success": best["p_success"],
                    "description": best["description"],
                })

    # Timeline from AAR events
    timeline = []
    if aar_events:
        for ev in aar_events[-20:]:
            timeline.append({
                "time": ev.get("timestamp", ""),
                "elapsed": ev.get("elapsed", 0),
                "event": ev.get("details", ev.get("type", "")),
            })

    conop = {
        "id": f"CONOP-{uuid.uuid4().hex[:8].upper()}",
        "dtg": dtg,
        "classification": classification,
        "mission_name": name,
        "callsign": callsign,
        "generated_at": datetime.now(timezone.utc).isoformat(),

        "overview": {
            "title": "OPERATIONAL OVERVIEW",
            "mission": f"{callsign} conducts multi-domain autonomous operations to "
                       f"neutralize {len(active_threats)} threats in assigned AO.",
            "ao_center": f"{base.get('lat', 0):.4f}N, {base.get('lng', 0):.4f}E",
            "duration": "Continuous until all threats neutralized or commander orders cease.",
        },

        "force_summary": {
            "title": "FORCE SUMMARY",
            "total_assets": len(assets),
            "domains": domains,
            "capabilities": capabilities,
            "threat_count_active": len(active_threats),
            "threat_count_neutralized": len(neutralized),
        },

        "threat_assessment": {
            "title": "THREAT ASSESSMENT",
            "active": [{
                "id": tid, "type": t.get("type", "UNK"),
                "location": f"{t.get('lat', 0):.4f}N, {t.get('lng', 0):.4f}E",
                "speed_kts": t.get("speed_kts", 0),
            } for tid, t in active_threats.items()],
            "neutralized_count": len(neutralized),
        },

        "concept": {
            "title": "CONCEPT OF OPERATIONS",
            "phases": [
                {"phase": "I — DETECT", "description": "ISR assets establish persistent surveillance. "
                 "Sensor fusion correlates multi-domain tracks."},
                {"phase": "II — DECIDE", "description": "Cognitive engine generates COAs with Monte Carlo scoring. "
                 "Commander reviews and approves via HAL interface."},
                {"phase": "III — ENGAGE", "description": "Strike assets execute approved COA. "
                 "EW assets suppress hostile sensors and C2."},
                {"phase": "IV — ASSESS", "description": "BDA via ISR. Learning engine captures engagement data. "
                 "AAR auto-generated."},
            ],
            "selected_coas": coa_summary,
        },

        "c2_architecture": {
            "title": "C2 ARCHITECTURE",
            "system": "AMOS v2.0",
            "connectivity": "WebSocket real-time (port 2600)",
            "autonomy_tiers": {
                "Tier 1": "Remote — all actions require human command",
                "Tier 2": "Supervised — AI recommends, human approves",
                "Tier 3": "Autonomous — AI acts, human monitors",
            },
            "hal_integration": "Human Autonomy Layer provides approval workflow",
        },

        "risk_assessment": {
            "title": "RISK ASSESSMENT",
            "primary_risks": [
                "Contested communications may degrade C2 link",
                "GPS denial zones affect navigation accuracy",
                "Red force adaptive tactics may exploit sensor gaps",
                "Battery endurance limits sustained operations",
            ],
            "mitigations": [
                "Mesh networking provides redundant comms",
                "INS fallback for GPS-denied navigation",
                "Learning engine adapts to red force patterns",
                "Auto-RTB on critical battery thresholds",
            ],
        },

        "timeline": timeline,
        "text": None,
    }

    conop["text"] = _render_text(conop)
    return conop


def _render_text(conop):
    """Render CONOP as formatted plain text."""
    lines = []
    cls = conop["classification"]
    lines.append(f"{'='*60}")
    lines.append(f"  {cls}")
    lines.append(f"  CONCEPT OF OPERATIONS — {conop['mission_name']}")
    lines.append(f"  DTG: {conop['dtg']}")
    lines.append(f"  CONOP ID: {conop['id']}")
    lines.append(f"{'='*60}")
    lines.append("")

    # Overview
    ov = conop["overview"]
    lines.append("OPERATIONAL OVERVIEW")
    lines.append(f"  Mission: {ov['mission']}")
    lines.append(f"  AO Center: {ov['ao_center']}")
    lines.append(f"  Duration: {ov['duration']}")
    lines.append("")

    # Force summary
    fs = conop["force_summary"]
    lines.append("FORCE SUMMARY")
    lines.append(f"  Total Assets: {fs['total_assets']}")
    for d, c in fs["domains"].items():
        lines.append(f"    {d}: {c}")
    cap = fs["capabilities"]
    lines.append(f"  ISR: {cap['isr']} | EW: {cap['ew']} | Strike: {cap['strike']} | C2: {cap['c2_relay']}")
    lines.append(f"  Active Threats: {fs['threat_count_active']} | Neutralized: {fs['threat_count_neutralized']}")
    lines.append("")

    # Threats
    ta = conop["threat_assessment"]
    lines.append("THREAT ASSESSMENT")
    for t in ta["active"][:10]:
        lines.append(f"  {t['id']}: {t['type']} at {t['location']} ({t['speed_kts']}kts)")
    lines.append("")

    # Concept
    con = conop["concept"]
    lines.append("CONCEPT OF OPERATIONS")
    for p in con["phases"]:
        lines.append(f"  {p['phase']}")
        lines.append(f"    {p['description']}")
    if con["selected_coas"]:
        lines.append("")
        lines.append("  SELECTED COAs:")
        for sc in con["selected_coas"]:
            lines.append(f"    {sc['threat_id']}: {sc['coa_name']} "
                        f"(score={sc['score']:.2f}, risk={sc['risk']}, "
                        f"P(success)={sc['p_success']:.0%})")
    lines.append("")

    # C2
    c2 = conop["c2_architecture"]
    lines.append("C2 ARCHITECTURE")
    lines.append(f"  System: {c2['system']}")
    lines.append(f"  Connectivity: {c2['connectivity']}")
    for tier, desc in c2["autonomy_tiers"].items():
        lines.append(f"  {tier}: {desc}")
    lines.append("")

    # Risk
    ra = conop["risk_assessment"]
    lines.append("RISK ASSESSMENT")
    lines.append("  Risks:")
    for r in ra["primary_risks"]:
        lines.append(f"    - {r}")
    lines.append("  Mitigations:")
    for m in ra["mitigations"]:
        lines.append(f"    - {m}")
    lines.append("")

    lines.append(f"{'='*60}")
    lines.append(f"  {cls}")
    lines.append(f"{'='*60}")

    return "\n".join(lines)
