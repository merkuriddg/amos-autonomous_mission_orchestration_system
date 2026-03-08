"""AMOS Natural Language Mission Parser — Advanced NLP for Compound Orders

Handles complex military-style natural language commands:
  - "Push GHOST flight south to screen the MSR and report any movement"
  - "REAPER-01 orbit over the AO at angels 15 with EO/IR active"
  - "All ground assets RTB, air assets hold position"

Designed with an LLM adapter slot for future GPT/Claude integration.
"""

import re, math, uuid, time
from datetime import datetime, timezone


# ─── Asset Group Resolver ─────────────────────────────────

FLIGHT_GROUPS = {
    "ghost": ["GHOST-01", "GHOST-02", "GHOST-03", "GHOST-04"],
    "reaper": ["REAPER-01", "REAPER-02"],
    "valkyr": ["VALKYR-01", "VALKYR-02"],
    "talon": ["TALON-01", "TALON-02", "TALON-03", "TALON-04"],
    "mule": ["MULE-01", "MULE-02", "MULE-03", "MULE-04"],
    "spectr": ["SPECTR-01", "SPECTR-02", "SPECTR-03", "SPECTR-04"],
    "triton": ["TRITON-01", "TRITON-02"],
    "awacs": ["AWACS-01", "AWACS-02"],
    "kraken": ["KRAKEN-01"],
}

DOMAIN_GROUPS = {
    "air": lambda assets: [a for a in assets.values() if a.get("domain") == "air"],
    "ground": lambda assets: [a for a in assets.values() if a.get("domain") == "ground"],
    "maritime": lambda assets: [a for a in assets.values() if a.get("domain") == "maritime"],
    "all": lambda assets: list(assets.values()),
}

ROLE_GROUPS = {
    "isr": lambda assets: [a for a in assets.values() if a.get("role") in ("isr_strike", "recon", "airborne_c2")],
    "strike": lambda assets: [a for a in assets.values() if a.get("weapons")],
    "ew": lambda assets: [a for a in assets.values() if "EW_JAMMER" in (a.get("sensors") or [])],
    "logistics": lambda assets: [a for a in assets.values() if a.get("role") in ("resupply", "medevac")],
    "sigint": lambda assets: [a for a in assets.values() if a.get("role") == "sigint"],
    "patrol": lambda assets: [a for a in assets.values() if a.get("role") == "coastal_patrol"],
}


def resolve_assets(token, all_assets):
    """Resolve a text token to a list of asset IDs."""
    t = token.strip().lower().replace("-", "").replace("_", "").replace(" ", "")

    # Direct ID match (e.g., "GHOST-01", "reaper01")
    for aid in all_assets:
        if t == aid.lower().replace("-", ""):
            return [aid]

    # Flight/group name (e.g., "ghost flight", "talon")
    for gname, gids in FLIGHT_GROUPS.items():
        if gname in t:
            return [gid for gid in gids if gid in all_assets]

    # Domain (e.g., "all air", "ground assets")
    for dname, dfn in DOMAIN_GROUPS.items():
        if dname in t:
            return [a["id"] for a in dfn(all_assets)]

    # Role (e.g., "ISR assets", "strike package")
    for rname, rfn in ROLE_GROUPS.items():
        if rname in t:
            return [a["id"] for a in rfn(all_assets)]

    # Fuzzy partial match
    for aid in all_assets:
        if t in aid.lower().replace("-", ""):
            return [aid]

    return []


# ─── Spatial Reasoning ────────────────────────────────────

CARDINAL_OFFSETS = {
    "north": (0.03, 0), "south": (-0.03, 0),
    "east": (0, 0.03), "west": (0, -0.03),
    "northeast": (0.02, 0.02), "northwest": (0.02, -0.02),
    "southeast": (-0.02, 0.02), "southwest": (-0.02, -0.02),
}

NAMED_LOCATIONS = {
    "base": (27.849, -82.521), "macdill": (27.849, -82.521),
    "ao": (27.85, -82.52), "ao center": (27.85, -82.52),
    "harbor": (27.82, -82.545), "port": (27.82, -82.545),
    "perimeter": (27.849, -82.521),
}


def resolve_location(text, reference_pos=None):
    """Extract a lat/lng from text, using cardinal, coordinate, or named location."""
    # Explicit coordinates
    coord_match = re.search(r"(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)", text)
    if coord_match:
        lat, lng = float(coord_match.group(1)), float(coord_match.group(2))
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return {"lat": lat, "lng": lng, "source": "coordinates"}

    # Named locations
    tl = text.lower()
    for name, (lat, lng) in NAMED_LOCATIONS.items():
        if name in tl:
            return {"lat": lat, "lng": lng, "source": f"named:{name}"}

    # Cardinal direction from reference position
    if reference_pos:
        for card, (dlat, dlng) in CARDINAL_OFFSETS.items():
            if card in tl:
                return {
                    "lat": reference_pos["lat"] + dlat,
                    "lng": reference_pos.get("lng", reference_pos.get("lon", 0)) + dlng,
                    "source": f"cardinal:{card}",
                }

    return None


# ─── Task Decomposition ──────────────────────────────────

TASK_PATTERNS = [
    # Movement
    (r"(?:push|move|send|deploy|navigate|proceed)\b", "MOVE"),
    (r"\b(?:rtb|return to base)\b", "RTB"),
    (r"\b(?:orbit|loiter|circle|cap)\b", "ORBIT"),
    (r"\b(?:hold|freeze|station|halt)\b", "HOLD"),
    (r"\b(?:scatter|disperse|spread)\b", "SCATTER"),
    (r"\b(?:rally|converge|consolidate)\b", "RALLY"),
    # Engagement
    (r"\b(?:engage|attack|strike|destroy|neutralize|fire)\b", "ENGAGE"),
    (r"\b(?:jam|suppress|deny)\b", "JAM"),
    (r"\b(?:intercept|block)\b", "INTERCEPT"),
    # ISR
    (r"\b(?:observe|watch|monitor|surveil|screen|recon)\b", "ISR"),
    (r"\b(?:scan|sweep|search)\b", "SCAN"),
    (r"\b(?:report|relay|transmit)\b", "REPORT"),
    # EW
    (r"\b(?:collect|intercept|listen)\b.*(?:sigint|signal|emission)", "SIGINT_COLLECT"),
    (r"\b(?:direction.?find|df|triangulate)\b", "DF"),
    # Formation
    (r"\b(?:form|formation)\b.*(?:line|column|wedge|diamond|spread|echelon)", "FORMATION"),
    # Autonomy
    (r"\b(?:auto|autonomy|autonomous)\b.*(?:level|tier|mode)\s*(\d)", "SET_AUTONOMY"),
    # Speed
    (r"\b(?:speed|sim)\b.*?(\d+\.?\d*)\s*x", "SET_SPEED"),
]

SENSOR_TASKS = {
    "eo/ir": "EO_IR_ACTIVE", "radar": "RADAR_ACTIVE", "sonar": "SONAR_ACTIVE",
    "sigint": "SIGINT_COLLECT", "elint": "ELINT_COLLECT", "lidar": "LIDAR_ACTIVE",
}

TRIGGER_PATTERNS = [
    (r"\b(?:if|when|upon)\b.*(?:contact|detect|see|spot)", "ON_CONTACT"),
    (r"\b(?:report|notify)\b.*(?:movement|contact|hostile)", "REPORT_CONTACT"),
    (r"\b(?:engage if|weapons free)\b", "WEAPONS_FREE"),
    (r"\b(?:do not engage|weapons tight|hold fire)\b", "WEAPONS_TIGHT"),
]


def extract_altitude(text):
    """Extract altitude from text (angels, feet, FL)."""
    m = re.search(r"angels?\s*(\d+)", text, re.I)
    if m:
        return int(m.group(1)) * 1000  # angels = thousands of feet
    m = re.search(r"(\d+)\s*(?:feet|ft)", text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"fl\s*(\d+)", text, re.I)
    if m:
        return int(m.group(1)) * 100
    return None


def decompose_order(text, all_assets, base_pos=None):
    """Decompose a natural language order into structured tasks."""
    if base_pos is None:
        base_pos = {"lat": 27.849, "lng": -82.521}

    sentences = re.split(r"[.;]|\band\b|\bthen\b", text)
    tasks = []

    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue

        # Find task type
        task_type = None
        for pattern, ttype in TASK_PATTERNS:
            if re.search(pattern, s, re.I):
                task_type = ttype
                break

        if not task_type:
            continue

        # Find assets
        asset_ids = []
        # Try to find asset reference before the verb
        asset_match = re.search(
            r"((?:all\s+)?(?:air|ground|maritime|ghost|reaper|talon|mule|spectr|triton|valkyr|awacs|kraken)"
            r"(?:\s+(?:flight|team|group|assets?|package|element))?|"
            r"[A-Z]+-\d+)",
            s, re.I)
        if asset_match:
            asset_ids = resolve_assets(asset_match.group(0), all_assets)

        # Location
        location = resolve_location(s, base_pos)

        # Altitude
        alt = extract_altitude(s)

        # Sensor tasking
        sensor_tasks = []
        sl = s.lower()
        for sensor_key, sensor_task in SENSOR_TASKS.items():
            if sensor_key in sl:
                sensor_tasks.append(sensor_task)

        # Triggers / ROE
        triggers = []
        for tpat, ttype in TRIGGER_PATTERNS:
            if re.search(tpat, s, re.I):
                triggers.append(ttype)

        task = {
            "id": f"TSK-{uuid.uuid4().hex[:6]}",
            "type": task_type,
            "asset_ids": asset_ids,
            "raw_text": s.strip(),
            "confidence": 0.85 if asset_ids and (location or task_type in ("RTB", "HOLD", "ORBIT")) else 0.5,
        }
        if location:
            task["location"] = location
        if alt:
            task["altitude_ft"] = alt
        if sensor_tasks:
            task["sensor_tasks"] = sensor_tasks
        if triggers:
            task["triggers"] = triggers

        tasks.append(task)

    return tasks


# ─── NLP Mission Parser (Main Class) ─────────────────────

class NLPMissionParser:
    """Full NLP mission parser with history and LLM adapter slot."""

    def __init__(self, base_pos=None):
        self.base_pos = base_pos or {"lat": 27.849, "lng": -82.521}
        self.history = []
        self.llm_adapter = None  # slot for future LLM backend

    def parse(self, transcript, assets):
        """Parse a natural language order into structured tasks."""
        ts = datetime.now(timezone.utc).isoformat()

        # Use LLM if available, otherwise pattern-based
        if self.llm_adapter and callable(self.llm_adapter):
            try:
                tasks = self.llm_adapter(transcript, assets, self.base_pos)
            except Exception:
                tasks = decompose_order(transcript, assets, self.base_pos)
        else:
            tasks = decompose_order(transcript, assets, self.base_pos)

        result = {
            "id": f"ORD-{uuid.uuid4().hex[:6]}",
            "timestamp": ts,
            "raw_transcript": transcript,
            "tasks": tasks,
            "task_count": len(tasks),
            "overall_confidence": round(
                sum(t["confidence"] for t in tasks) / max(len(tasks), 1), 2),
            "assets_involved": list(set(
                aid for t in tasks for aid in t.get("asset_ids", []))),
            "parser": "llm" if self.llm_adapter else "pattern",
        }

        self.history.append(result)
        if len(self.history) > 200:
            self.history = self.history[-200:]

        return result

    def set_llm_adapter(self, adapter_fn):
        """Set an LLM backend: adapter_fn(transcript, assets, base_pos) -> [tasks]"""
        self.llm_adapter = adapter_fn

    def get_history(self, limit=50):
        return self.history[-limit:]
