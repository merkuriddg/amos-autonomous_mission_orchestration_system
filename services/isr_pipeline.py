#!/usr/bin/env python3
"""AMOS Phase 18 — ISR/ATR Pipeline
Automatic Target Recognition, Pattern-of-Life analysis,
Collection Management, Change Detection."""

import math, random, uuid, time, threading
from datetime import datetime, timezone


class ISRPipeline:
    """Intelligence production pipeline — ATR, POLARIS, collection management."""

    CLASSIFICATION_TYPES = {
        "vehicle_military": {"confidence_base": 0.75, "priority": "HIGH"},
        "vehicle_civilian": {"confidence_base": 0.60, "priority": "LOW"},
        "personnel_armed":  {"confidence_base": 0.65, "priority": "HIGH"},
        "personnel_unarmed": {"confidence_base": 0.55, "priority": "LOW"},
        "installation_fixed": {"confidence_base": 0.85, "priority": "MEDIUM"},
        "emitter_active":    {"confidence_base": 0.80, "priority": "HIGH"},
        "aircraft_rotary":   {"confidence_base": 0.70, "priority": "CRITICAL"},
        "aircraft_fixed":    {"confidence_base": 0.72, "priority": "CRITICAL"},
        "vessel_surface":    {"confidence_base": 0.68, "priority": "MEDIUM"},
        "unknown":           {"confidence_base": 0.30, "priority": "MEDIUM"},
    }

    PATTERN_STATES = ["STATIC", "ROUTINE_PATROL", "IRREGULAR", "EVASIVE",
                      "CONVERGING", "DISPERSING", "STAGING", "TRANSITING"]

    def __init__(self):
        self._lock = threading.Lock()
        self.targets = {}          # {target_id: {atr_data, patterns, observations}}
        self.collections = []       # prioritized collection requirements
        self.changes = []           # detected changes
        self._last_atr = 0
        self._last_pattern = 0
        self._last_change = 0

    def tick(self, assets, threats, eob_units, sigint_intercepts, dt):
        """Main ISR pipeline tick — called from sim_tick."""
        now = time.time()

        # ATR scan every ~5s
        if now - self._last_atr > 5:
            self._last_atr = now
            self._run_atr_scan(assets, threats, eob_units)

        # Pattern analysis every ~15s
        if now - self._last_pattern > 15:
            self._last_pattern = now
            self._analyze_patterns()

        # Change detection every ~10s
        if now - self._last_change > 10:
            self._last_change = now
            self._detect_changes(threats, eob_units)

        # Process collection requirements
        self._process_collections(assets)

    def _run_atr_scan(self, assets, threats, eob_units):
        """Automatic Target Recognition scan — classify all tracked targets."""
        with self._lock:
            # Process threats
            for tid, t in threats.items():
                if t.get("neutralized") or "lat" not in t:
                    continue
                if tid not in self.targets:
                    self.targets[tid] = {
                        "id": tid, "source": "threat",
                        "classifications": [], "observations": [],
                        "pattern": None, "first_seen": datetime.now(timezone.utc).isoformat(),
                        "position_history": [], "atr_confidence": 0,
                        "last_position": None, "change_flags": [],
                    }
                tgt = self.targets[tid]

                # Classify based on type + sensor coverage
                sensors_covering = self._count_sensors_covering(
                    t["lat"], t.get("lng", 0), assets)
                base_type = self._infer_classification(t.get("type", "unknown"))
                base_conf = self.CLASSIFICATION_TYPES.get(
                    base_type, {}).get("confidence_base", 0.5)
                # More sensors = higher confidence
                sensor_bonus = min(0.25, sensors_covering * 0.05)
                # History bonus
                history_bonus = min(0.10, len(tgt["observations"]) * 0.01)
                confidence = min(0.99, base_conf + sensor_bonus + history_bonus +
                                random.uniform(-0.05, 0.05))

                classification = {
                    "type": base_type,
                    "confidence": round(confidence, 3),
                    "sensors_covering": sensors_covering,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                tgt["classifications"].append(classification)
                if len(tgt["classifications"]) > 20:
                    tgt["classifications"] = tgt["classifications"][-20:]
                tgt["atr_confidence"] = round(confidence, 3)

                # Record observation
                obs = {"lat": round(t["lat"], 5), "lng": round(t.get("lng", 0), 5),
                       "speed": t.get("speed_kts", 0),
                       "timestamp": datetime.now(timezone.utc).isoformat()}
                tgt["observations"].append(obs)
                if len(tgt["observations"]) > 100:
                    tgt["observations"] = tgt["observations"][-100:]

                # Position history for pattern analysis
                tgt["position_history"].append({
                    "lat": round(t["lat"], 5), "lng": round(t.get("lng", 0), 5),
                    "ts": time.time()})
                if len(tgt["position_history"]) > 200:
                    tgt["position_history"] = tgt["position_history"][-200:]
                tgt["last_position"] = {"lat": t["lat"], "lng": t.get("lng", 0)}

            # Process EOB units similarly
            for uid, u in eob_units.items():
                lk = u.get("last_known", {})
                if not lk.get("lat"):
                    continue
                if uid not in self.targets:
                    self.targets[uid] = {
                        "id": uid, "source": "eob",
                        "classifications": [], "observations": [],
                        "pattern": None, "first_seen": datetime.now(timezone.utc).isoformat(),
                        "position_history": [], "atr_confidence": 0,
                        "last_position": None, "change_flags": [],
                    }
                tgt = self.targets[uid]
                tgt["last_position"] = {"lat": lk["lat"], "lng": lk["lng"]}
                tgt["position_history"].append({
                    "lat": round(lk["lat"], 5), "lng": round(lk["lng"], 5),
                    "ts": time.time()})
                if len(tgt["position_history"]) > 200:
                    tgt["position_history"] = tgt["position_history"][-200:]

    def _analyze_patterns(self):
        """Pattern-of-Life analysis for all tracked targets."""
        with self._lock:
            for tid, tgt in self.targets.items():
                history = tgt.get("position_history", [])
                if len(history) < 5:
                    tgt["pattern"] = {"state": "INSUFFICIENT_DATA", "confidence": 0}
                    continue

                # Calculate movement metrics
                total_dist = 0
                speeds = []
                heading_changes = []
                for i in range(1, len(history)):
                    dlat = history[i]["lat"] - history[i-1]["lat"]
                    dlng = history[i]["lng"] - history[i-1]["lng"]
                    dist = math.sqrt(dlat**2 + dlng**2)
                    dt_s = max(0.1, history[i]["ts"] - history[i-1]["ts"])
                    total_dist += dist
                    speeds.append(dist / dt_s)
                    if i > 1:
                        prev_dlat = history[i-1]["lat"] - history[i-2]["lat"]
                        prev_dlng = history[i-1]["lng"] - history[i-2]["lng"]
                        dot = dlat*prev_dlat + dlng*prev_dlng
                        mag1 = math.sqrt(dlat**2+dlng**2)
                        mag2 = math.sqrt(prev_dlat**2+prev_dlng**2)
                        if mag1 > 0 and mag2 > 0:
                            cos_a = max(-1, min(1, dot / (mag1 * mag2)))
                            heading_changes.append(math.degrees(math.acos(cos_a)))

                avg_speed = sum(speeds) / len(speeds) if speeds else 0
                max_speed = max(speeds) if speeds else 0
                avg_heading_change = sum(heading_changes) / len(heading_changes) if heading_changes else 0

                # Classify pattern
                if avg_speed < 0.0000001:
                    state = "STATIC"
                elif avg_heading_change > 60:
                    state = "EVASIVE"
                elif avg_heading_change > 30:
                    state = "IRREGULAR"
                elif self._is_circular(history):
                    state = "ROUTINE_PATROL"
                elif avg_speed > 0.00001:
                    # Check if converging toward our center
                    first_dist = math.sqrt(history[0]["lat"]**2 + history[0]["lng"]**2)
                    last_dist = math.sqrt(history[-1]["lat"]**2 + history[-1]["lng"]**2)
                    if last_dist < first_dist * 0.8:
                        state = "CONVERGING"
                    else:
                        state = "TRANSITING"
                else:
                    state = "STATIC"

                tgt["pattern"] = {
                    "state": state,
                    "avg_speed": round(avg_speed * 111000, 1),  # convert to m/s roughly
                    "max_speed": round(max_speed * 111000, 1),
                    "heading_variance": round(avg_heading_change, 1),
                    "total_distance_m": round(total_dist * 111000, 1),
                    "observation_count": len(history),
                    "confidence": min(0.95, len(history) / 50),
                    "last_update": datetime.now(timezone.utc).isoformat(),
                }

    def _is_circular(self, history):
        """Check if track returns near starting position (patrol pattern)."""
        if len(history) < 10:
            return False
        start = history[0]
        end = history[-1]
        dist = math.sqrt((start["lat"]-end["lat"])**2 + (start["lng"]-end["lng"])**2)
        total = sum(math.sqrt((history[i]["lat"]-history[i-1]["lat"])**2 +
                             (history[i]["lng"]-history[i-1]["lng"])**2)
                   for i in range(1, len(history)))
        return dist < total * 0.2 and total > 0.001

    def _detect_changes(self, threats, eob_units):
        """Detect significant changes in tracked targets."""
        with self._lock:
            for tid, tgt in self.targets.items():
                history = tgt.get("position_history", [])
                if len(history) < 3:
                    continue

                # Speed change detection
                if len(history) >= 5:
                    recent_speeds = []
                    for i in range(-4, 0):
                        dlat = history[i]["lat"] - history[i-1]["lat"]
                        dlng = history[i]["lng"] - history[i-1]["lng"]
                        dt_s = max(0.1, history[i]["ts"] - history[i-1]["ts"])
                        recent_speeds.append(math.sqrt(dlat**2+dlng**2) / dt_s)
                    if len(recent_speeds) >= 2:
                        avg_recent = sum(recent_speeds) / len(recent_speeds)
                        avg_old = sum(recent_speeds[:len(recent_speeds)//2]) / max(1, len(recent_speeds)//2)
                        if avg_old > 0 and abs(avg_recent - avg_old) / avg_old > 0.5:
                            change = {
                                "target_id": tid, "type": "SPEED_CHANGE",
                                "severity": "HIGH" if avg_recent > avg_old else "MEDIUM",
                                "details": f"Speed {'increased' if avg_recent > avg_old else 'decreased'} by {abs(avg_recent-avg_old)/avg_old*100:.0f}%",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                            if not any(c["target_id"] == tid and c["type"] == "SPEED_CHANGE"
                                      and time.time() - self._parse_ts(c["timestamp"]) < 30
                                      for c in self.changes):
                                self.changes.append(change)
                                tgt["change_flags"].append(change["type"])

                # Pattern state change
                pattern = tgt.get("pattern", {})
                if pattern.get("state") in ("EVASIVE", "CONVERGING", "STAGING"):
                    change = {
                        "target_id": tid, "type": "PATTERN_ALERT",
                        "severity": "CRITICAL" if pattern["state"] == "CONVERGING" else "HIGH",
                        "details": f"Target exhibiting {pattern['state']} behavior",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    if not any(c["target_id"] == tid and c["type"] == "PATTERN_ALERT"
                              and time.time() - self._parse_ts(c["timestamp"]) < 60
                              for c in self.changes):
                        self.changes.append(change)

            # Trim changes
            if len(self.changes) > 200:
                self.changes = self.changes[-200:]

    def _parse_ts(self, ts_str):
        """Parse ISO timestamp to epoch."""
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0

    def _count_sensors_covering(self, lat, lng, assets):
        """Count how many sensors can see a position."""
        count = 0
        sensor_ranges = {
            "AESA_RADAR": 0.04, "AEW_RADAR": 0.06, "EO/IR": 0.015,
            "EW_JAMMER": 0.03, "SIGINT": 0.035, "ELINT": 0.03,
            "COMINT": 0.025, "LIDAR": 0.01, "SONAR": 0.02, "CAMERA": 0.008,
        }
        for a in assets.values():
            for sensor in a.get("sensors", []):
                rng = sensor_ranges.get(sensor, 0)
                if rng > 0:
                    dist = math.sqrt((a["position"]["lat"]-lat)**2 + (a["position"]["lng"]-lng)**2)
                    if dist <= rng:
                        count += 1
                        break  # count each asset once
        return count

    def _infer_classification(self, threat_type):
        """Map threat type to ATR classification."""
        mapping = {
            "drone": "aircraft_rotary", "fighter_jet": "aircraft_fixed",
            "helicopter": "aircraft_rotary", "missile_launcher": "installation_fixed",
            "tank": "vehicle_military", "apc": "vehicle_military",
            "infantry": "personnel_armed", "submarine": "vessel_surface",
            "patrol_boat": "vessel_surface", "sam_site": "installation_fixed",
            "radar_site": "emitter_active", "artillery": "installation_fixed",
        }
        return mapping.get(threat_type, "unknown")

    def _process_collections(self, assets):
        """Process prioritized collection requirements — auto-task sensors."""
        for coll in self.collections:
            if coll.get("status") != "open":
                continue
            # Find best sensor to task
            best_asset = None
            best_dist = float("inf")
            for a in assets.values():
                if any(s in a.get("sensors", []) for s in coll.get("required_sensors", ["CAMERA"])):
                    dist = math.sqrt((a["position"]["lat"] - coll["target"]["lat"])**2 +
                                    (a["position"]["lng"] - coll["target"]["lng"])**2)
                    if dist < best_dist:
                        best_dist = dist
                        best_asset = a["id"]
            if best_asset:
                coll["assigned_asset"] = best_asset
                coll["status"] = "tasked"

    def add_collection_requirement(self, name, target, priority, required_sensors=None):
        """Add a prioritized intelligence collection requirement."""
        req = {
            "id": f"CR-{uuid.uuid4().hex[:6]}", "name": name,
            "target": target, "priority": priority,
            "required_sensors": required_sensors or ["CAMERA", "EO/IR"],
            "status": "open", "assigned_asset": None,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.collections.append(req)
        self.collections.sort(key=lambda x: x["priority"], reverse=True)
        return req

    def get_targets(self):
        """Get all ATR-tracked targets with classifications."""
        return {tid: {
            "id": t["id"], "source": t["source"],
            "atr_confidence": t["atr_confidence"],
            "latest_class": t["classifications"][-1] if t["classifications"] else None,
            "pattern": t.get("pattern"),
            "observation_count": len(t["observations"]),
            "position": t.get("last_position"),
            "change_flags": t.get("change_flags", [])[-5:],
        } for tid, t in self.targets.items()}

    def get_target_detail(self, tid):
        return self.targets.get(tid, {})

    def get_collections(self):
        return self.collections[-50:]

    def get_changes(self, limit=50):
        return self.changes[-limit:]

    def get_patterns(self):
        return {tid: t.get("pattern", {}) for tid, t in self.targets.items()
                if t.get("pattern") and t["pattern"].get("state") != "INSUFFICIENT_DATA"}

    def get_stats(self):
        tracked = len(self.targets)
        high_conf = sum(1 for t in self.targets.values() if t["atr_confidence"] > 0.7)
        active_changes = sum(1 for c in self.changes
                            if time.time() - self._parse_ts(c["timestamp"]) < 60)
        return {"tracked_targets": tracked, "high_confidence": high_conf,
                "active_changes": active_changes, "collection_reqs": len(self.collections),
                "total_observations": sum(len(t["observations"]) for t in self.targets.values())}
