#!/usr/bin/env python3
"""AMOS CQB Simulation Seed.

Populates the new CQB subsystems with realistic demo data at startup so
the 3D Tactical Viewer, CQB Ops console, and perception fusion panels
show activity immediately rather than starting empty.

Seeded data:
  - Indoor positions for 4 ground assets in both buildings
  - Perception fusion threat detections (hostiles, civilians, IEDs)
  - SLAM occupancy grid scans (partial floor coverage)
  - One pre-staged demo mission (PENDING, not auto-executed)
"""

import random


# ═══════════════════════════════════════════════════════════
#  SEED INDOOR POSITIONS
# ═══════════════════════════════════════════════════════════

_INDOOR_SEEDS = {
    # Building Alpha — ground floor positions
    "BLD-ALPHA": [
        {"asset_id": "CLAW1", "building_id": "BLD-ALPHA", "floor": 0,
         "room": "R-001", "x_m": 3.0, "y_m": 7.5, "z_m": 0.0,
         "source": "slam", "confidence": 0.92},
        {"asset_id": "CLAW2", "building_id": "BLD-ALPHA", "floor": 0,
         "room": "R-002", "x_m": 9.0, "y_m": 3.5, "z_m": 0.0,
         "source": "slam", "confidence": 0.88},
    ],
    # Embassy Bravo — staged at entry points
    "BLD-BRAVO": [
        {"asset_id": "CLAW3", "building_id": "BLD-BRAVO", "floor": 0,
         "room": "R-G01", "x_m": 4.0, "y_m": 2.0, "z_m": 0.0,
         "source": "slam", "confidence": 0.95},
        {"asset_id": "PACK1", "building_id": "BLD-BRAVO", "floor": 0,
         "room": "R-G08", "x_m": 24.0, "y_m": 5.0, "z_m": 0.0,
         "source": "slam", "confidence": 0.90},
    ],
}

# ═══════════════════════════════════════════════════════════
#  SEED PERCEPTION DETECTIONS
# ═══════════════════════════════════════════════════════════

_DETECTION_SEEDS = [
    # Embassy Bravo — hostiles per threat intel
    {"building_id": "BLD-BRAVO", "floor": 0, "room_id": "R-G02",
     "x_m": 11.0, "y_m": 3.0, "classification": "hostile_armed",
     "confidence": 0.85, "source_asset": "CLAW3"},
    {"building_id": "BLD-BRAVO", "floor": 0, "room_id": "R-G06",
     "x_m": 17.0, "y_m": 9.0, "classification": "hostile_armed",
     "confidence": 0.78, "source_asset": "CLAW3"},
    {"building_id": "BLD-BRAVO", "floor": 0, "room_id": "R-G09",
     "x_m": 24.0, "y_m": 14.0, "classification": "hostile_armed",
     "confidence": 0.72, "source_asset": "PACK1"},
    {"building_id": "BLD-BRAVO", "floor": 1, "room_id": "R-U03",
     "x_m": 14.0, "y_m": 3.5, "classification": "hostile_armed",
     "confidence": 0.65, "source_asset": "CLAW3"},
    # Civilians / hostages
    {"building_id": "BLD-BRAVO", "floor": 1, "room_id": "R-U03",
     "x_m": 13.0, "y_m": 2.0, "classification": "civilian",
     "confidence": 0.70, "source_asset": "CLAW3"},
    {"building_id": "BLD-BRAVO", "floor": 0, "room_id": "R-G04",
     "x_m": 11.0, "y_m": 15.0, "classification": "civilian",
     "confidence": 0.60, "source_asset": "PACK1"},
    # IED detection
    {"building_id": "BLD-BRAVO", "floor": 0, "room_id": "R-G07",
     "x_m": 17.0, "y_m": 15.0, "classification": "ied",
     "confidence": 0.55, "source_asset": "CLAW3"},
    # Compound Alpha — one hostile in guard room
    {"building_id": "BLD-ALPHA", "floor": 0, "room_id": "R-003",
     "x_m": 9.0, "y_m": 11.0, "classification": "hostile_armed",
     "confidence": 0.80, "source_asset": "CLAW1"},
]

# ═══════════════════════════════════════════════════════════
#  SEED SLAM GRIDS
# ═══════════════════════════════════════════════════════════

def _generate_slam_cells(x_min, y_min, x_max, y_max, density=0.6):
    """Generate a partial SLAM scan for a rectangular area."""
    cells = []
    step = 0.5
    x = x_min
    while x < x_max:
        y = y_min
        while y < y_max:
            if random.random() < density:
                cells.append({"x_m": round(x, 1), "y_m": round(y, 1),
                              "value": random.choice([1, 1, 1, 2])})
            y += step
        x += step
    return cells


_SLAM_SEEDS = [
    # Compound Alpha — partial ground floor scan
    {"building_id": "BLD-ALPHA", "floor": 0, "asset_id": "CLAW1",
     "area": (0, 0, 12, 15), "density": 0.5},
    {"building_id": "BLD-ALPHA", "floor": 0, "asset_id": "CLAW2",
     "area": (6, 0, 20, 10), "density": 0.4},
    # Embassy Bravo — lobby and motor pool scanned
    {"building_id": "BLD-BRAVO", "floor": 0, "asset_id": "CLAW3",
     "area": (0, 0, 14, 18), "density": 0.5},
    {"building_id": "BLD-BRAVO", "floor": 0, "asset_id": "PACK1",
     "area": (20, 0, 28, 18), "density": 0.45},
]


# ═══════════════════════════════════════════════════════════
#  MAIN SEED FUNCTION
# ═══════════════════════════════════════════════════════════

def seed_cqb_data(indoor_positioning=None, perception_fusion=None,
                  squad_supervisor=None, building_mgr=None):
    """Populate CQB subsystems with demo data. Safe to call at startup."""
    seeded = {"indoor_positions": 0, "detections": 0, "slam_scans": 0,
              "missions": 0}

    # ── Indoor positions ──
    if indoor_positioning:
        for bld_id, positions in _INDOOR_SEEDS.items():
            for pos in positions:
                try:
                    indoor_positioning.update_position(**pos)
                    seeded["indoor_positions"] += 1
                except Exception:
                    pass

    # ── Perception detections ──
    if perception_fusion:
        for det in _DETECTION_SEEDS:
            try:
                perception_fusion.ingest_detection(**det)
                seeded["detections"] += 1
            except Exception:
                pass

    # ── SLAM grids ──
    if perception_fusion:
        for scan in _SLAM_SEEDS:
            try:
                cells = _generate_slam_cells(*scan["area"],
                                             density=scan["density"])
                perception_fusion.ingest_slam_scan(
                    scan["building_id"], scan["floor"],
                    scan["asset_id"], cells)
                seeded["slam_scans"] += 1
            except Exception:
                pass

    # ── Demo mission (PENDING — not auto-executed) ──
    if squad_supervisor and building_mgr:
        bravo = building_mgr.get("BLD-BRAVO")
        if bravo:
            try:
                squad_supervisor.create_mission(
                    objective="Clear Embassy Bravo — extract hostages from SCIF",
                    building_id="BLD-BRAVO",
                    objective_type="extract_hvt",
                    target_room="R-U03",
                    asset_ids=["CLAW1", "CLAW2", "CLAW3"],
                    reserve_ids=["PACK1"],
                )
                seeded["missions"] += 1
            except Exception:
                pass

    return seeded
