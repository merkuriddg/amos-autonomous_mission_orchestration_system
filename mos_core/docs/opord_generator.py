"""AMOS Phase 3 — 5-Paragraph OPORD Generator
Produces a standard military Operations Order from live mission state.
Paragraphs: 1-SITUATION, 2-MISSION, 3-EXECUTION, 4-SUSTAINMENT, 5-C2
"""

import uuid
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).strftime("%d%H%MZ %b %Y").upper()


def _threat_summary(threats):
    """Build enemy situation summary from threat data."""
    active = [t for t in threats.values() if not t.get("neutralized")]
    neutralized = [t for t in threats.values() if t.get("neutralized")]
    by_type = {}
    for t in active:
        tt = t.get("type", "UNKNOWN")
        by_type[tt] = by_type.get(tt, 0) + 1
    lines = []
    for ttype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        lines.append(f"  - {count}x {ttype}")
    return {
        "active_count": len(active),
        "neutralized_count": len(neutralized),
        "by_type": by_type,
        "detail_lines": lines,
        "active": active,
    }


def _friendly_summary(assets):
    """Build friendly forces summary."""
    by_domain = {}
    by_role = {}
    for a in assets.values():
        d = a.get("domain", "unknown")
        r = a.get("role", "unknown")
        by_domain[d] = by_domain.get(d, 0) + 1
        by_role[r] = by_role.get(r, 0) + 1
    return {
        "total": len(assets),
        "by_domain": by_domain,
        "by_role": by_role,
    }


def _build_task_org(assets):
    """Generate task organization from asset data."""
    orgs = []
    for aid, a in sorted(assets.items()):
        tier = a.get("autonomy_tier", 1)
        tier_label = {1: "REMOTE", 2: "SUPERVISED", 3: "AUTONOMOUS"}.get(tier, "MANUAL")
        weapons = a.get("weapons", [])
        sensors = a.get("sensors", [])
        orgs.append({
            "callsign": aid,
            "type": a.get("type", "UNK"),
            "domain": a.get("domain", "UNK"),
            "role": a.get("role", "UNK"),
            "autonomy": tier_label,
            "weapons": weapons[:3],
            "sensors": sensors[:3],
            "status": a.get("status", "unknown"),
        })
    return orgs


def _execution_tasks(assets, threats):
    """Generate execution tasks based on asset capabilities and threats."""
    tasks = []
    active_threats = [t for t in threats.values() if not t.get("neutralized")]
    # ISR assets → recon
    isr = [a for a in assets.values() if a.get("role") in ("recon", "isr", "surveillance")]
    if isr:
        tasks.append({
            "phase": "PHASE 1 — ISR/RECON",
            "assets": [a["id"] for a in isr],
            "task": f"Conduct area reconnaissance. Confirm {len(active_threats)} threat positions.",
            "priority": "HIGH",
        })
    # EW assets → suppress
    ew = [a for a in assets.values()
          if any(s in (a.get("sensors") or []) for s in ["EW_JAMMER", "SIGINT", "ELINT"])]
    if ew:
        tasks.append({
            "phase": "PHASE 2 — EW/SUPPRESSION",
            "assets": [a["id"] for a in ew],
            "task": "Establish electronic warfare superiority. Jam hostile C2 and radar.",
            "priority": "HIGH",
        })
    # Strike assets → engage
    strike = [a for a in assets.values() if a.get("weapons")]
    if strike:
        tasks.append({
            "phase": "PHASE 3 — ENGAGEMENT",
            "assets": [a["id"] for a in strike[:5]],
            "task": f"Engage and neutralize {len(active_threats)} confirmed threats. ROE applies.",
            "priority": "CRITICAL",
        })
    # Overwatch
    overwatch = [a for a in assets.values()
                 if a.get("role") in ("overwatch", "escort", "c2_relay")]
    if overwatch:
        tasks.append({
            "phase": "PHASE 4 — OVERWATCH/SUPPORT",
            "assets": [a["id"] for a in overwatch],
            "task": "Provide overwatch for engagement force. Maintain C2 relay.",
            "priority": "MEDIUM",
        })
    return tasks


def generate_opord(platoon_config, assets, threats, coa_data=None,
                   mission_name=None, classification="UNCLASSIFIED"):
    """
    Generate a complete 5-paragraph OPORD.

    Args:
        platoon_config: dict with platoon name, callsign, base, ao
        assets: dict of sim_assets
        threats: dict of sim_threats
        coa_data: optional COA analysis from cognitive engine
        mission_name: override mission name
        classification: security classification

    Returns:
        dict with OPORD paragraphs and metadata
    """
    dtg = _now()
    name = mission_name or platoon_config.get("name", "UNNAMED OPERATION")
    callsign = platoon_config.get("callsign", "UNKNOWN")
    base = platoon_config.get("base", {})
    ao = platoon_config.get("ao", {})
    threat_info = _threat_summary(threats)
    friendly_info = _friendly_summary(assets)
    task_org = _build_task_org(assets)
    exec_tasks = _execution_tasks(assets, threats)

    # Select best COA if available
    selected_coa = None
    if coa_data:
        for tid, coas in coa_data.items():
            if coas:
                if not selected_coa or coas[0].get("composite_score", 0) > selected_coa.get("composite_score", 0):
                    selected_coa = coas[0]

    opord = {
        "id": f"OPORD-{uuid.uuid4().hex[:8].upper()}",
        "dtg": dtg,
        "classification": classification,
        "mission_name": name,
        "callsign": callsign,
        "generated_at": datetime.now(timezone.utc).isoformat(),

        # PARAGRAPH 1 — SITUATION
        "para_1_situation": {
            "title": "1. SITUATION",
            "a_enemy_forces": {
                "title": "a. Enemy Forces",
                "active_threats": threat_info["active_count"],
                "neutralized": threat_info["neutralized_count"],
                "composition": threat_info["by_type"],
                "detail": threat_info["detail_lines"],
                "summary": (f"{threat_info['active_count']} active threats identified in AO. "
                           f"{threat_info['neutralized_count']} previously neutralized. "
                           f"Primary threat types: {', '.join(threat_info['by_type'].keys()) or 'None identified'}.")
            },
            "b_friendly_forces": {
                "title": "b. Friendly Forces",
                "total_assets": friendly_info["total"],
                "by_domain": friendly_info["by_domain"],
                "by_role": friendly_info["by_role"],
                "summary": (f"{friendly_info['total']} autonomous/semi-autonomous assets assigned. "
                           f"Domains: {', '.join(f'{d}({c})' for d, c in friendly_info['by_domain'].items())}.")
            },
            "c_environment": {
                "title": "c. Operational Environment",
                "ao_bounds": ao,
                "base_position": base,
                "summary": (f"AO centered on {base.get('lat', 0):.4f}N, {base.get('lng', 0):.4f}E. "
                           f"FOB established. Multi-domain autonomous operations authorized.")
            }
        },

        # PARAGRAPH 2 — MISSION
        "para_2_mission": {
            "title": "2. MISSION",
            "statement": (f"{callsign} conducts multi-domain autonomous operations NLT {dtg} "
                         f"in assigned AO to detect, track, and neutralize "
                         f"{threat_info['active_count']} identified threats "
                         f"IOT establish area dominance and protect friendly forces."),
        },

        # PARAGRAPH 3 — EXECUTION
        "para_3_execution": {
            "title": "3. EXECUTION",
            "a_concept": {
                "title": "a. Commander's Intent",
                "purpose": "Achieve battlespace dominance through coordinated autonomous operations.",
                "key_tasks": [
                    "Establish persistent ISR coverage across AO",
                    "Achieve EW superiority prior to kinetic engagement",
                    "Engage and neutralize all confirmed threats",
                    "Maintain continuous C2 connectivity"
                ],
                "endstate": "All threats neutralized. AO secured. Assets RTB or on station.",
                "selected_coa": selected_coa["coa_name"] if selected_coa else "Commander's discretion",
                "coa_score": selected_coa["composite_score"] if selected_coa else None,
            },
            "b_tasks": exec_tasks,
            "c_task_organization": task_org,
            "d_coordinating_instructions": [
                f"ROE: Tier 2+ assets require human approval before engagement",
                f"Tier 3 assets authorized autonomous defensive engagement",
                "All assets maintain geofence compliance",
                "HAL recommendations require commander approval for offensive actions",
                "Minimum 2-asset coordination for kinetic operations",
            ]
        },

        # PARAGRAPH 4 — SUSTAINMENT
        "para_4_sustainment": {
            "title": "4. SUSTAINMENT",
            "logistics": {
                "base": f"FOB at {base.get('lat', 0):.4f}N, {base.get('lng', 0):.4f}E",
                "rtb_criteria": "Battery < 20% OR comms < 30% OR mission complete",
                "endurance_notes": [f"{a['id']}: {a.get('endurance_hr', 0)}hr" for a in
                                   sorted(assets.values(), key=lambda x: x.get('endurance_hr', 0))[:5]],
            },
            "comms": {
                "primary": "SocketIO mesh network",
                "backup": "ROS2 bridge (if available)",
                "px4": "PX4 SITL MAVLink (if connected)",
            },
            "maintenance": "Automated health monitoring. Auto-RTB on critical battery/comms."
        },

        # PARAGRAPH 5 — COMMAND AND SIGNAL
        "para_5_c2": {
            "title": "5. COMMAND AND SIGNAL",
            "commander": platoon_config.get("commander", "CDR Mitchell"),
            "c2_system": "AMOS v2.0 — Autonomous Mission Operating System",
            "succession": ["CDR Mitchell", "CPT Torres", "SGT Reeves"],
            "signal": {
                "primary_net": "AMOS WebSocket (port 2600)",
                "reports": "Automated via sim_tick",
                "voice": "Voice command interface active",
            }
        },

        # Text rendering
        "text": None,
    }

    # Generate plain-text rendering
    opord["text"] = _render_text(opord)
    return opord


def _render_text(opord):
    """Render OPORD as formatted plain text."""
    lines = []
    cls = opord["classification"]
    lines.append(f"{'='*60}")
    lines.append(f"  {cls}")
    lines.append(f"  OPERATIONS ORDER — {opord['mission_name']}")
    lines.append(f"  DTG: {opord['dtg']}")
    lines.append(f"  OPORD ID: {opord['id']}")
    lines.append(f"{'='*60}")
    lines.append("")

    # Para 1
    p1 = opord["para_1_situation"]
    lines.append(f"1. SITUATION")
    lines.append(f"")
    lines.append(f"   a. Enemy Forces")
    lines.append(f"      {p1['a_enemy_forces']['summary']}")
    for d in p1["a_enemy_forces"]["detail"]:
        lines.append(f"      {d}")
    lines.append(f"")
    lines.append(f"   b. Friendly Forces")
    lines.append(f"      {p1['b_friendly_forces']['summary']}")
    lines.append(f"")
    lines.append(f"   c. Operational Environment")
    lines.append(f"      {p1['c_environment']['summary']}")
    lines.append(f"")

    # Para 2
    lines.append(f"2. MISSION")
    lines.append(f"   {opord['para_2_mission']['statement']}")
    lines.append(f"")

    # Para 3
    p3 = opord["para_3_execution"]
    lines.append(f"3. EXECUTION")
    lines.append(f"")
    lines.append(f"   a. Commander's Intent")
    lines.append(f"      Purpose: {p3['a_concept']['purpose']}")
    lines.append(f"      Key Tasks:")
    for kt in p3["a_concept"]["key_tasks"]:
        lines.append(f"        - {kt}")
    lines.append(f"      Endstate: {p3['a_concept']['endstate']}")
    if p3["a_concept"]["selected_coa"]:
        lines.append(f"      Selected COA: {p3['a_concept']['selected_coa']}")
        if p3["a_concept"]["coa_score"]:
            lines.append(f"      COA Score: {p3['a_concept']['coa_score']:.2f}")
    lines.append(f"")
    lines.append(f"   b. Tasks to Subordinate Units")
    for task in p3["b_tasks"]:
        lines.append(f"      {task['phase']}")
        lines.append(f"        Task: {task['task']}")
        lines.append(f"        Assets: {', '.join(task['assets'][:5])}")
        lines.append(f"        Priority: {task['priority']}")
        lines.append(f"")
    lines.append(f"   c. Coordinating Instructions")
    for ci in p3["d_coordinating_instructions"]:
        lines.append(f"      - {ci}")
    lines.append(f"")

    # Para 4
    p4 = opord["para_4_sustainment"]
    lines.append(f"4. SUSTAINMENT")
    lines.append(f"   Base: {p4['logistics']['base']}")
    lines.append(f"   RTB Criteria: {p4['logistics']['rtb_criteria']}")
    lines.append(f"   Comms Primary: {p4['comms']['primary']}")
    lines.append(f"")

    # Para 5
    p5 = opord["para_5_c2"]
    lines.append(f"5. COMMAND AND SIGNAL")
    lines.append(f"   Commander: {p5['commander']}")
    lines.append(f"   C2 System: {p5['c2_system']}")
    lines.append(f"   Primary Net: {p5['signal']['primary_net']}")
    lines.append(f"")
    lines.append(f"{'='*60}")
    lines.append(f"  {cls}")
    lines.append(f"{'='*60}")

    return "\n".join(lines)
