#!/usr/bin/env python3
"""Build AMOS Drone Reference Database.

Sources:
  - DroneCompare.org data.json (CC-BY-4.0) — commercial drones
  - Public military UAS specs (Navy.mil, AeroVironment datasheets)
  - Adversary/OSINT threat profiles

Outputs:  config/drone_reference.json
"""

import json
import os
import sys
import urllib.request

CDN_URL = "https://cdn.dronecompare.org/data.json"
OUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "config", "drone_reference.json")


def _val(values, key, default=None):
    """Extract a scalar value from DroneCompare nested value format."""
    v = values.get(key, default)
    if isinstance(v, list):
        if v and isinstance(v[0], dict):
            return v[0].get("value", default)
        return v[0] if v else default
    return v


def _val_list(values, key):
    """Extract a list of scalar values from DroneCompare multi-value format."""
    v = values.get(key, [])
    if isinstance(v, list):
        return [i.get("value", i) if isinstance(i, dict) else i for i in v]
    return [v] if v else []


def ms_to_kts(ms):
    """Convert m/s to knots."""
    if ms is None:
        return None
    try:
        return round(float(ms) * 1.944, 1)
    except (ValueError, TypeError):
        return None


def m_to_ft(m):
    """Convert meters to feet."""
    if m is None:
        return None
    try:
        return round(float(m) * 3.281)
    except (ValueError, TypeError):
        return None


def extract_commercial(data):
    """Extract AMOS-relevant fields from DroneCompare entities."""
    entries = []
    for ent in data.get("entities", []):
        v = ent.get("values", {})
        name = _val(v, "identity.name")
        mfg = _val(v, "identity.manufacturer")
        if not name or not mfg:
            continue

        slug = ent.get("slug", "")
        model_id = f"{mfg.lower().replace(' ', '_')}_{slug.replace('-', '_')}" if slug else \
                   f"{mfg.lower()}_{name.lower().replace(' ', '_')}"

        weight_g = _val(v, "physical.weight")
        max_speed_ms = _val(v, "flight.max_speed")
        max_flight_time = _val(v, "flight.max_flight_time")
        max_range_km = _val(v, "flight.max_range") or _val(v, "transmission.max_range_fcc")
        max_alt_m = _val(v, "flight.max_altitude")
        camera_mp = None
        cam_mp_raw = _val(v, "camera.megapixels")
        if cam_mp_raw is not None:
            try:
                camera_mp = float(cam_mp_raw)
            except (ValueError, TypeError):
                pass

        rf_bands = _val_list(v, "transmission.operating_freq")
        tx_protocol = _val(v, "transmission.protocol")
        gnss = _val_list(v, "navigation.gnss")
        series = _val(v, "identity.series", "")
        platform_type = _val(v, "identity.platform_type", "multirotor")
        ip_rating = _val(v, "physical.ip_rating", "none")

        op_temp = v.get("physical.operating_temp")
        op_temp_str = None
        if isinstance(op_temp, dict):
            op_temp_str = f"{op_temp.get('min', '?')}°C to {op_temp.get('max', '?')}°C"

        # Determine serial prefix patterns from manufacturer
        serial_prefixes = _serial_prefixes_for(mfg)

        entry = {
            "id": model_id,
            "name": name,
            "manufacturer": mfg,
            "category": "commercial",
            "platform_type": platform_type,
            "weight_g": weight_g,
            "max_speed_kts": ms_to_kts(max_speed_ms),
            "max_speed_ms": max_speed_ms,
            "endurance_min": max_flight_time,
            "range_km": max_range_km,
            "ceiling_ft": m_to_ft(max_alt_m),
            "sensors": [],
            "camera_mp": camera_mp,
            "rf_bands": rf_bands,
            "tx_protocol": tx_protocol,
            "gnss": gnss,
            "ip_rating": ip_rating,
            "operating_temp": op_temp_str,
            "serial_prefixes": serial_prefixes,
            "threat_classification": "commercial",
            "series": series,
            "source": "dronecompare.org",
            "source_license": "CC-BY-4.0",
            "notes": None,
        }

        # Build sensor list from camera data
        sensors = []
        if camera_mp:
            sensors.append("EO")
        has_thermal = "thermal" in name.lower() or "dual" in name.lower() or \
                      "640t" in name.lower() or "multispectral" in name.lower()
        if has_thermal:
            sensors.append("IR")
        if _val(v, "navigation.rtk") in ("yes", "addon"):
            sensors.append("RTK")
        entry["sensors"] = sensors

        entries.append(entry)
    return entries


def _serial_prefixes_for(manufacturer):
    """Return known RemoteID serial number prefixes by manufacturer."""
    prefixes = {
        "DJI":       ["1581F", "1581E", "1581D", "3030", "3032"],
        "Autel":     ["AU-"],
        "Skydio":    ["SDK", "SKD"],
        "Parrot":    ["PI0", "PAR"],
        "Freefly":   ["FF-"],
        "Wingcopter":["WC-"],
        "RigiTech":  ["RGT"],
        "Antigravity":["AG-"],
    }
    return prefixes.get(manufacturer, [])


def build_military_entries():
    """Military/tactical UAS from public sources (Navy.mil, datasheets)."""
    return [
        {
            "id": "rq11b_raven",
            "name": "RQ-11B Raven",
            "manufacturer": "AeroVironment",
            "category": "tactical",
            "platform_type": "fixed_wing",
            "weight_g": 2132,  # 4.7 lbs
            "max_speed_kts": 44,
            "max_speed_ms": 22.6,
            "endurance_min": 90,
            "range_km": 10,
            "ceiling_ft": 10000,
            "sensors": ["EO", "IR"],
            "camera_mp": None,
            "rf_bands": ["FHSS digital"],
            "tx_protocol": "AeroVironment DDL",
            "gnss": ["gps"],
            "ip_rating": "all-weather",
            "operating_temp": "-30°C to 50°C",
            "serial_prefixes": ["AV-RVN", "RQ11"],
            "threat_classification": "friendly",
            "series": "SURSS Group 1",
            "source": "navy.mil",
            "source_license": "public domain",
            "notes": "Hand-launched, battery-powered. Standard US Army/Marine squad-level ISR.",
        },
        {
            "id": "rq12a_wasp",
            "name": "RQ-12A Wasp IV",
            "manufacturer": "AeroVironment",
            "category": "tactical",
            "platform_type": "fixed_wing",
            "weight_g": 1361,  # < 3 lbs
            "max_speed_kts": 40,
            "max_speed_ms": 20.6,
            "endurance_min": 50,
            "range_km": 5,
            "ceiling_ft": 5000,
            "sensors": ["EO", "IR"],
            "camera_mp": None,
            "rf_bands": ["FHSS digital"],
            "tx_protocol": "AeroVironment DDL",
            "gnss": ["gps"],
            "ip_rating": "all-weather",
            "operating_temp": "-30°C to 50°C",
            "serial_prefixes": ["AV-WSP", "RQ12"],
            "threat_classification": "friendly",
            "series": "SURSS Group 1",
            "source": "navy.mil",
            "source_license": "public domain",
            "notes": "Smallest SURSS UAS. Platoon/squad-level front-line recon.",
        },
        {
            "id": "rq20b_puma",
            "name": "RQ-20B Puma AE",
            "manufacturer": "AeroVironment",
            "category": "tactical",
            "platform_type": "fixed_wing",
            "weight_g": 6124,  # 13.5 lbs
            "max_speed_kts": 45,
            "max_speed_ms": 23.1,
            "endurance_min": 210,  # 3.5 hours
            "range_km": 28,
            "ceiling_ft": 10500,
            "sensors": ["EO", "IR", "laser_illuminator"],
            "camera_mp": None,
            "rf_bands": ["FHSS digital"],
            "tx_protocol": "AeroVironment DDL",
            "gnss": ["gps"],
            "ip_rating": "all-environment",
            "operating_temp": "-30°C to 50°C",
            "serial_prefixes": ["AV-PMA", "RQ20"],
            "threat_classification": "friendly",
            "series": "SURSS Group 1",
            "source": "navy.mil",
            "source_license": "public domain",
            "notes": "Largest SURSS. Company-level persistent ISR. Waterproof, land/sea recovery.",
        },
        {
            "id": "switchblade_300",
            "name": "Switchblade 300",
            "manufacturer": "AeroVironment",
            "category": "tactical",
            "platform_type": "loitering_munition",
            "weight_g": 2500,  # ~5.5 lbs
            "max_speed_kts": 85,
            "max_speed_ms": 43.7,
            "endurance_min": 15,
            "range_km": 10,
            "ceiling_ft": 5000,
            "sensors": ["EO", "IR"],
            "camera_mp": None,
            "rf_bands": ["FHSS digital"],
            "tx_protocol": "AeroVironment DDL",
            "gnss": ["gps"],
            "ip_rating": "field-rated",
            "operating_temp": "-20°C to 50°C",
            "serial_prefixes": ["AV-SB3"],
            "threat_classification": "friendly",
            "series": "Switchblade",
            "source": "wikipedia/public",
            "source_license": "public domain",
            "notes": "Man-portable loitering munition. Anti-personnel focused blast warhead.",
        },
        {
            "id": "switchblade_600",
            "name": "Switchblade 600",
            "manufacturer": "AeroVironment",
            "category": "tactical",
            "platform_type": "loitering_munition",
            "weight_g": 22700,  # ~50 lbs
            "max_speed_kts": 100,
            "max_speed_ms": 51.4,
            "endurance_min": 40,
            "range_km": 40,
            "ceiling_ft": 10000,
            "sensors": ["EO", "IR", "laser_designator"],
            "camera_mp": None,
            "rf_bands": ["FHSS digital", "SATCOM"],
            "tx_protocol": "AeroVironment DDL",
            "gnss": ["gps"],
            "ip_rating": "field-rated",
            "operating_temp": "-20°C to 50°C",
            "serial_prefixes": ["AV-SB6"],
            "threat_classification": "friendly",
            "series": "Switchblade",
            "source": "wikipedia/public",
            "source_license": "public domain",
            "notes": "Anti-armor loitering munition. Multi-purpose warhead, Javelin-class.",
        },
        {
            "id": "pd100_black_hornet",
            "name": "PD-100 Black Hornet 3",
            "manufacturer": "FLIR/Teledyne",
            "category": "tactical",
            "platform_type": "nano_rotorcraft",
            "weight_g": 33,
            "max_speed_kts": 11.6,
            "max_speed_ms": 6.0,
            "endurance_min": 25,
            "range_km": 2,
            "ceiling_ft": 1000,
            "sensors": ["EO", "IR"],
            "camera_mp": 2,
            "rf_bands": ["digital encrypted"],
            "tx_protocol": "proprietary encrypted",
            "gnss": ["gps"],
            "ip_rating": "IP67",
            "operating_temp": "-10°C to 43°C",
            "serial_prefixes": ["BH3"],
            "threat_classification": "friendly",
            "series": "Black Hornet",
            "source": "flir.com/public",
            "source_license": "public domain",
            "notes": "Nano UAS for individual soldier. Virtually silent. GPS-denied capable.",
        },
        {
            "id": "scan_eagle",
            "name": "ScanEagle",
            "manufacturer": "Insitu/Boeing",
            "category": "tactical",
            "platform_type": "fixed_wing",
            "weight_g": 18100,  # ~40 lbs
            "max_speed_kts": 70,
            "max_speed_ms": 36.0,
            "endurance_min": 1440,  # 24+ hours
            "range_km": 100,
            "ceiling_ft": 19500,
            "sensors": ["EO", "IR", "SIGINT"],
            "camera_mp": None,
            "rf_bands": ["C-band", "Ku-band"],
            "tx_protocol": "proprietary",
            "gnss": ["gps"],
            "ip_rating": "all-weather",
            "operating_temp": "-30°C to 50°C",
            "serial_prefixes": ["INS-SE"],
            "threat_classification": "friendly",
            "series": "Group 2",
            "source": "insitu.com/public",
            "source_license": "public domain",
            "notes": "Long-endurance Group 2 ISR. Catapult launched, SkyHook recovery.",
        },
    ]


def build_adversary_entries():
    """Adversary / OSINT-derived threat drone profiles."""
    return [
        {
            "id": "fpv_racing_modified",
            "name": "Modified FPV Racing Drone",
            "manufacturer": "Various/DIY",
            "category": "adversary",
            "platform_type": "multirotor",
            "weight_g": 800,
            "max_speed_kts": 75,
            "max_speed_ms": 38.6,
            "endurance_min": 8,
            "range_km": 5,
            "ceiling_ft": 3000,
            "sensors": ["EO"],
            "camera_mp": 2,
            "rf_bands": ["5.8 GHz", "2.4 GHz", "900 MHz"],
            "tx_protocol": "analog/digital FPV",
            "gnss": [],
            "ip_rating": "none",
            "operating_temp": None,
            "serial_prefixes": [],
            "threat_classification": "hostile",
            "series": None,
            "source": "OSINT",
            "source_license": None,
            "notes": "Weaponized FPV drone. Common in Ukraine conflict. Carries grenades/shaped charges.",
        },
        {
            "id": "dji_mavic_modified",
            "name": "Modified DJI Mavic (weaponized)",
            "manufacturer": "DJI (modified)",
            "category": "adversary",
            "platform_type": "multirotor",
            "weight_g": 1200,
            "max_speed_kts": 40,
            "max_speed_ms": 20.6,
            "endurance_min": 25,
            "range_km": 8,
            "ceiling_ft": 5000,
            "sensors": ["EO"],
            "camera_mp": 20,
            "rf_bands": ["2.4 GHz", "5.8 GHz"],
            "tx_protocol": "OcuSync modified",
            "gnss": ["gps", "glonass"],
            "ip_rating": "none",
            "operating_temp": None,
            "serial_prefixes": ["1581F", "1581E"],
            "threat_classification": "hostile",
            "series": None,
            "source": "OSINT",
            "source_license": None,
            "notes": "Commercial DJI drone modified as ISR/drop platform. Common threat profile.",
        },
        {
            "id": "generic_commercial_threat",
            "name": "Unknown Commercial Drone (unclassified)",
            "manufacturer": "Unknown",
            "category": "adversary",
            "platform_type": "multirotor",
            "weight_g": 500,
            "max_speed_kts": 35,
            "max_speed_ms": 18.0,
            "endurance_min": 25,
            "range_km": 5,
            "ceiling_ft": 4000,
            "sensors": ["EO"],
            "camera_mp": 12,
            "rf_bands": ["2.4 GHz", "5.8 GHz"],
            "tx_protocol": "unknown",
            "gnss": ["gps"],
            "ip_rating": "none",
            "operating_temp": None,
            "serial_prefixes": [],
            "threat_classification": "unknown",
            "series": None,
            "source": "OSINT",
            "source_license": None,
            "notes": "Default profile for unidentified commercial-class drone in AO.",
        },
        {
            "id": "shahed_136",
            "name": "Shahed-136 (Geran-2)",
            "manufacturer": "HESA (Iran)",
            "category": "adversary",
            "platform_type": "loitering_munition",
            "weight_g": 200000,  # ~200 kg
            "max_speed_kts": 100,
            "max_speed_ms": 51.4,
            "endurance_min": 300,  # ~5 hours
            "range_km": 2500,
            "ceiling_ft": 12000,
            "sensors": ["GPS_INS"],
            "camera_mp": None,
            "rf_bands": ["GPS L1"],
            "tx_protocol": "pre-programmed/GPS",
            "gnss": ["gps", "glonass"],
            "ip_rating": "field-rated",
            "operating_temp": None,
            "serial_prefixes": [],
            "threat_classification": "hostile",
            "series": "Shahed",
            "source": "OSINT",
            "source_license": None,
            "notes": "Delta-wing loitering munition. ~40 kg warhead. Used extensively in Ukraine.",
        },
        {
            "id": "orlan_10",
            "name": "Orlan-10",
            "manufacturer": "UZGA (Russia)",
            "category": "adversary",
            "platform_type": "fixed_wing",
            "weight_g": 18000,  # ~18 kg
            "max_speed_kts": 81,
            "max_speed_ms": 41.7,
            "endurance_min": 960,  # ~16 hours
            "range_km": 120,
            "ceiling_ft": 16400,
            "sensors": ["EO", "IR", "SIGINT", "EW"],
            "camera_mp": None,
            "rf_bands": ["UHF", "L-band"],
            "tx_protocol": "proprietary",
            "gnss": ["glonass", "gps"],
            "ip_rating": "field-rated",
            "operating_temp": "-30°C to 40°C",
            "serial_prefixes": [],
            "threat_classification": "hostile",
            "series": "Orlan",
            "source": "OSINT",
            "source_license": None,
            "notes": "Russian tactical ISR/EW UAS. Can jam GPS, direct artillery. Common threat.",
        },
    ]


def main():
    # ── Download DroneCompare data ──
    print(f"[BUILD] Downloading DroneCompare data from CDN...")
    cache_path = "/tmp/dronecompare_data.json"
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 10000:
        print(f"[BUILD] Using cached {cache_path}")
        with open(cache_path) as f:
            dc_data = json.load(f)
    else:
        req = urllib.request.Request(CDN_URL, headers={"User-Agent": "AMOS-ETL/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            dc_data = json.loads(resp.read().decode())
        with open(cache_path, "w") as f:
            json.dump(dc_data, f)
        print(f"[BUILD] Downloaded and cached ({os.path.getsize(cache_path)} bytes)")

    # ── Extract commercial ──
    commercial = extract_commercial(dc_data)
    print(f"[BUILD] Extracted {len(commercial)} commercial drones from DroneCompare")

    # ── Military / tactical ──
    military = build_military_entries()
    print(f"[BUILD] Added {len(military)} military/tactical entries")

    # ── Adversary / OSINT ──
    adversary = build_adversary_entries()
    print(f"[BUILD] Added {len(adversary)} adversary/OSINT entries")

    # ── Combine and write ──
    all_entries = commercial + military + adversary

    output = {
        "version": "1.0",
        "generated_by": "tools/build_drone_ref.py",
        "sources": [
            {"name": "DroneCompare.org", "license": "CC-BY-4.0",
             "url": "https://dronecompare.org", "count": len(commercial)},
            {"name": "US Navy / AeroVironment (public)", "license": "public domain",
             "count": len(military)},
            {"name": "OSINT / threat intelligence", "license": "N/A",
             "count": len(adversary)},
        ],
        "total": len(all_entries),
        "entries": all_entries,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[BUILD] Wrote {len(all_entries)} entries to {OUT_PATH}")
    print(f"[BUILD]   Commercial: {len(commercial)}")
    print(f"[BUILD]   Military:   {len(military)}")
    print(f"[BUILD]   Adversary:  {len(adversary)}")


if __name__ == "__main__":
    main()
