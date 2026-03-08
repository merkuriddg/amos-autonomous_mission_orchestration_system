"""AMOS Persistence Layer — Write-through DB cache for mission-critical state.
Keeps in-memory dicts as primary (fast), flushes to MariaDB periodically."""

import time
import threading
from db.connection import execute as db_execute, executemany, fetchall, to_json, from_json, check as db_check

_last_flush = 0
_FLUSH_INTERVAL = 30  # seconds
_flush_lock = threading.Lock()

# ─── Track what's been persisted (avoid duplicate writes) ───
_persisted_ids = {
    "engagements": set(),
    "aar": set(),
    "bda": set(),
    "sigint": set(),
    "hal": set(),
    "sitreps": set(),
}


def persist_engagement(e):
    """Write-through: persist a single engagement immediately."""
    eid = e.get("id", "")
    if eid in _persisted_ids["engagements"]:
        return
    try:
        db_execute(
            "INSERT IGNORE INTO engagements (engagement_id,threat_id,engagement_type,operator,elapsed_sec,result) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (eid, e.get("threat_id", ""), e.get("type", ""), e.get("operator", ""),
             e.get("elapsed", 0), "neutralized"))
        _persisted_ids["engagements"].add(eid)
    except Exception:
        pass


def persist_bda(rpt):
    """Write-through: persist a single BDA report immediately."""
    rid = rpt.get("id", "")
    if rid in _persisted_ids["bda"]:
        return
    try:
        db_execute(
            "INSERT IGNORE INTO bda_reports (report_id,reporter,target_id,target_name,lat,lng,"
            "weapon_used,munitions_expended,damage_level,functional_kill,assessment_conf,imagery_available,remarks) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (rid, rpt.get("reporter", ""), rpt.get("target_id", ""), rpt.get("target_name", ""),
             rpt.get("lat", 0), rpt.get("lng", 0), rpt.get("weapon_used", ""),
             rpt.get("munitions_expended", 1), rpt.get("damage_level", "moderate"),
             1 if rpt.get("functional_kill") else 0, rpt.get("assessment_conf", "medium"),
             1 if rpt.get("imagery_available") else 0, rpt.get("remarks", "")))
        _persisted_ids["bda"].add(rid)
    except Exception:
        pass


def persist_sitrep(s):
    """Write-through: persist a SITREP."""
    sid = s.get("id", "")
    if sid in _persisted_ids["sitreps"]:
        return
    try:
        db_execute(
            "INSERT IGNORE INTO sitreps (sitrep_id,generated_by,dtg,classification,data) VALUES(%s,%s,%s,%s,%s)",
            (sid, s.get("generated_by", ""), s.get("dtg", ""), s.get("classification", ""), to_json(s)))
        _persisted_ids["sitreps"].add(sid)
    except Exception:
        pass


def persist_hal_action(r):
    """Write-through: persist a HAL recommendation action."""
    rid = r.get("id", "")
    if rid in _persisted_ids["hal"]:
        return
    try:
        db_execute(
            "INSERT IGNORE INTO hal_actions (rec_id,rec_type,asset_id,target_id,confidence,status) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (rid, r.get("type", ""), r.get("asset", ""), r.get("target", ""),
             r.get("confidence", 0), r.get("status", "pending")))
        _persisted_ids["hal"].add(rid)
    except Exception:
        pass


def flush_periodic(cm_log, aar_events, bda_reports, eob_units, sigint_intercepts,
                   supply_history, weather, threat_intel, sitreps, mission_plans,
                   automation_rules, hal_recommendations):
    """Periodic flush — called from sim_tick every ~30s. Batches inserts."""
    global _last_flush
    now = time.time()
    if now - _last_flush < _FLUSH_INTERVAL:
        return
    if not _flush_lock.acquire(blocking=False):
        return
    try:
        if not db_check():
            return
        _last_flush = now

        # ── Engagements ──
        new_eng = [e for e in cm_log if e.get("id") and e["id"] not in _persisted_ids["engagements"]]
        if new_eng:
            for e in new_eng[-50:]:
                persist_engagement(e)

        # ── AAR Events (batch last 200 unsaved) ──
        new_aar = aar_events[-200:]
        if new_aar:
            batch = []
            for ev in new_aar:
                key = f"{ev.get('type','')}-{ev.get('elapsed',0):.0f}"
                if key not in _persisted_ids["aar"]:
                    batch.append((ev.get("type", ""), ev.get("elapsed", 0), ev.get("details", "")))
                    _persisted_ids["aar"].add(key)
            if batch:
                try:
                    executemany("INSERT INTO aar_log (event_type,elapsed_sec,details) VALUES(%s,%s,%s)", batch)
                except Exception:
                    pass

        # ── BDA Reports ──
        for rpt in bda_reports:
            persist_bda(rpt)

        # ── EOB Units (upsert) ──
        for uid, u in list(eob_units.items())[:50]:
            try:
                lk = u.get("last_known", {})
                db_execute(
                    "INSERT INTO eob_units (unit_id,name,unit_type,affiliation,emitter_type,freq_mhz,"
                    "threat_level,confidence,status,last_lat,last_lng,positions,first_seen,notes) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE last_lat=%s,last_lng=%s,status=%s,positions=%s",
                    (uid, u.get("name", ""), u.get("type", ""), u.get("affiliation", "hostile"),
                     u.get("emitter_type", ""), u.get("freq_mhz", 0),
                     u.get("threat_level", "medium"), u.get("confidence", "medium"),
                     u.get("status", "active"), lk.get("lat", 0), lk.get("lng", 0),
                     to_json(u.get("positions", [])[-20:]), u.get("first_seen"),
                     u.get("notes", ""),
                     lk.get("lat", 0), lk.get("lng", 0), u.get("status", "active"),
                     to_json(u.get("positions", [])[-20:])))
            except Exception:
                pass

        # ── SIGINT (last 100 new) ──
        new_sig = [i for i in sigint_intercepts[-100:]
                   if i.get("id") and i["id"] not in _persisted_ids["sigint"]]
        if new_sig:
            batch = []
            for i in new_sig:
                batch.append((i["id"], i.get("collector", ""), i.get("freq_mhz", 0),
                              i.get("power_dbm", 0), i.get("modulation", ""),
                              i.get("bearing_deg", 0), i.get("classification", ""),
                              i.get("duration_ms", 0)))
                _persisted_ids["sigint"].add(i["id"])
            try:
                executemany(
                    "INSERT IGNORE INTO sigint_log (intercept_id,collector,freq_mhz,power_dbm,"
                    "modulation,bearing_deg,classification,duration_ms) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                    batch)
            except Exception:
                pass

        # ── Supply snapshot ──
        if supply_history:
            last = supply_history[-1]
            try:
                db_execute("INSERT INTO supply_snapshots (avg_fuel,avg_ammo,total_assets) VALUES(%s,%s,%s)",
                           (last.get("avg_fuel", 0), last.get("avg_ammo", 0), len(eob_units)))
            except Exception:
                pass

        # ── Weather snapshot ──
        try:
            db_execute(
                "INSERT INTO weather_log (conditions,wind_speed_kt,wind_dir_deg,visibility_km,"
                "ceiling_ft,precipitation,sea_state,temp_c) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (weather.get("conditions", ""), weather.get("wind_speed_kt", 0),
                 weather.get("wind_dir_deg", 0), weather.get("visibility_km", 0),
                 weather.get("ceiling_ft", 0), weather.get("precipitation", ""),
                 weather.get("sea_state", 0), weather.get("temp_c", 0)))
        except Exception:
            pass

        # ── Threat Intel (upsert) ──
        for ttype, ti in list(threat_intel.items()):
            try:
                db_execute(
                    "INSERT INTO threat_intel_db (threat_type,total_count,engagements,neutralized,"
                    "first_seen,last_seen,positions) VALUES(%s,%s,%s,%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE total_count=%s,engagements=%s,neutralized=%s,last_seen=%s,positions=%s",
                    (ttype, ti.get("count", 0), ti.get("engagements", 0), ti.get("neutralized", 0),
                     ti.get("first_seen"), ti.get("last_seen"), to_json(ti.get("positions", [])[-20:]),
                     ti.get("count", 0), ti.get("engagements", 0), ti.get("neutralized", 0),
                     ti.get("last_seen"), to_json(ti.get("positions", [])[-20:])))
            except Exception:
                pass

        # ── Trim old persisted ID sets to prevent memory growth ──
        for k in _persisted_ids:
            if len(_persisted_ids[k]) > 5000:
                excess = len(_persisted_ids[k]) - 2000
                for _ in range(excess):
                    _persisted_ids[k].pop()

    finally:
        _flush_lock.release()


def load_state_from_db():
    """Load persisted state from DB on startup. Returns dict of loaded data."""
    result = {"loaded": False}
    try:
        if not db_check():
            return result

        # BDA reports
        rows = fetchall("SELECT * FROM bda_reports ORDER BY id DESC LIMIT 500")
        if rows:
            result["bda_reports"] = [{
                "id": r["report_id"], "timestamp": str(r["timestamp"]),
                "reporter": r["reporter"], "target_id": r["target_id"],
                "target_name": r["target_name"], "lat": float(r["lat"]),
                "lng": float(r["lng"]), "weapon_used": r["weapon_used"],
                "munitions_expended": r["munitions_expended"],
                "damage_level": r["damage_level"],
                "functional_kill": bool(r["functional_kill"]),
                "assessment_conf": r["assessment_conf"],
                "imagery_available": bool(r["imagery_available"]),
                "remarks": r.get("remarks", "")
            } for r in reversed(rows)]
            for rpt in result["bda_reports"]:
                _persisted_ids["bda"].add(rpt["id"])

        # Engagements
        rows = fetchall("SELECT * FROM engagements ORDER BY id DESC LIMIT 500")
        if rows:
            result["cm_log"] = [{
                "id": r["engagement_id"], "threat_id": r["threat_id"],
                "type": r["engagement_type"], "operator": r["operator"],
                "elapsed": float(r["elapsed_sec"]), "timestamp": str(r["timestamp"])
            } for r in reversed(rows)]
            for e in result["cm_log"]:
                _persisted_ids["engagements"].add(e["id"])

        # Threat Intel
        rows = fetchall("SELECT * FROM threat_intel_db")
        if rows:
            result["threat_intel"] = {}
            for r in rows:
                result["threat_intel"][r["threat_type"]] = {
                    "count": r["total_count"], "engagements": r["engagements"],
                    "neutralized": r["neutralized"],
                    "first_seen": str(r["first_seen"]) if r["first_seen"] else None,
                    "last_seen": str(r["last_seen"]) if r["last_seen"] else None,
                    "positions": from_json(r["positions"]) or []
                }

        # SITREPs
        rows = fetchall("SELECT * FROM sitreps ORDER BY id DESC LIMIT 50")
        if rows:
            result["sitreps"] = [from_json(r["data"]) or {} for r in reversed(rows)]
            for s in result["sitreps"]:
                _persisted_ids["sitreps"].add(s.get("id", ""))

        # Mission plans
        rows = fetchall("SELECT * FROM saved_mission_plans ORDER BY id DESC LIMIT 100")
        if rows:
            result["mission_plans"] = {}
            for r in rows:
                data = from_json(r["data"]) or {}
                data["id"] = r["plan_id"]
                data["name"] = r["name"]
                result["mission_plans"][r["plan_id"]] = data

        # Automation rules
        rows = fetchall("SELECT * FROM automation_rules")
        if rows:
            result["automation_rules"] = {}
            for r in rows:
                result["automation_rules"][r["rule_id"]] = {
                    "name": r["name"], "trigger_type": r["trigger_type"],
                    "trigger_params": from_json(r["trigger_params"]) or {},
                    "action_type": r["action_type"],
                    "action_params": from_json(r["action_params"]) or {},
                    "enabled": bool(r["enabled"]), "fired_count": r["fired_count"],
                    "last_fired": str(r["last_fired"]) if r["last_fired"] else None
                }

        result["loaded"] = True
        loaded_items = sum(1 for k, v in result.items() if k != "loaded" and v)
        print(f"[AMOS] Persistence: Loaded {loaded_items} data sets from DB")
    except Exception as e:
        print(f"[AMOS] Persistence: Load failed ({e})")
    return result
