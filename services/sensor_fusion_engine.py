"""AMOS Sensor Fusion Engine — Track Correlation, Coverage Analysis, Kill Chain

Implements:
  - Multi-sensor track correlation: fuse detections into unified tracks
  - Uncertainty ellipse modeling per fused track
  - Sensor coverage footprint calculation (radar, EO/IR, SIGINT, sonar)
  - Kill chain pipeline: detect→identify→decide→engage→assess with timing
"""

import math, random, time, uuid
from datetime import datetime, timezone


def _dist_deg(lat1, lng1, lat2, lng2):
    return math.sqrt((lat2 - lat1)**2 + (lng2 - lng1)**2)


# ─── Sensor Coverage Models ──────────────────────────────

SENSOR_COVERAGE = {
    "AESA_RADAR":  {"range_nm": 80, "fov_deg": 120, "detect_air": True,  "detect_ground": True,  "detect_maritime": True},
    "AEW_RADAR":   {"range_nm": 200, "fov_deg": 360, "detect_air": True,  "detect_ground": False, "detect_maritime": True},
    "EO/IR":       {"range_nm": 15, "fov_deg": 60,  "detect_air": True,  "detect_ground": True,  "detect_maritime": True},
    "SAR":         {"range_nm": 40, "fov_deg": 90,  "detect_air": False, "detect_ground": True,  "detect_maritime": True},
    "LIDAR":       {"range_nm": 2,  "fov_deg": 30,  "detect_air": False, "detect_ground": True,  "detect_maritime": False},
    "RADAR":       {"range_nm": 25, "fov_deg": 360, "detect_air": True,  "detect_ground": False, "detect_maritime": True},
    "SONAR":       {"range_nm": 10, "fov_deg": 360, "detect_air": False, "detect_ground": False, "detect_maritime": True},
    "ACOUSTIC":    {"range_nm": 3,  "fov_deg": 360, "detect_air": True,  "detect_ground": True,  "detect_maritime": False},
    "SIGINT":      {"range_nm": 30, "fov_deg": 360, "detect_air": True,  "detect_ground": True,  "detect_maritime": True},
    "ELINT":       {"range_nm": 40, "fov_deg": 360, "detect_air": True,  "detect_ground": True,  "detect_maritime": True},
    "COMINT":      {"range_nm": 25, "fov_deg": 360, "detect_air": True,  "detect_ground": True,  "detect_maritime": True},
    "RWR":         {"range_nm": 50, "fov_deg": 360, "detect_air": True,  "detect_ground": False, "detect_maritime": False},
    "AIS":         {"range_nm": 40, "fov_deg": 360, "detect_air": False, "detect_ground": False, "detect_maritime": True},
    "SEISMIC":     {"range_nm": 5,  "fov_deg": 360, "detect_air": False, "detect_ground": True,  "detect_maritime": False},
    "MAGNETIC":    {"range_nm": 3,  "fov_deg": 360, "detect_air": False, "detect_ground": True,  "detect_maritime": True},
    "CBRN":        {"range_nm": 1,  "fov_deg": 360, "detect_air": True,  "detect_ground": True,  "detect_maritime": False},
    "DIRECTION_FINDING": {"range_nm": 35, "fov_deg": 360, "detect_air": True, "detect_ground": True, "detect_maritime": True},
    "EW_JAMMER":   {"range_nm": 20, "fov_deg": 120, "detect_air": True,  "detect_ground": True,  "detect_maritime": True},
    "GPS":         {"range_nm": 0,  "fov_deg": 0,   "detect_air": False, "detect_ground": False, "detect_maritime": False},
}

NM_TO_DEG = 1.0 / 60.0  # approximate


def compute_coverage_footprint(asset):
    """Calculate sensor coverage arcs for an asset."""
    ap = asset.get("position", asset)
    lat, lng = ap.get("lat", 0), ap.get("lng", 0)
    heading = asset.get("heading_deg", 0)
    sensors = asset.get("sensors") or []
    footprints = []

    for sensor_name in sensors:
        spec = SENSOR_COVERAGE.get(sensor_name)
        if not spec or spec["range_nm"] == 0:
            continue
        range_deg = spec["range_nm"] * NM_TO_DEG
        fov = spec["fov_deg"]
        if fov >= 360:
            start_bearing, end_bearing = 0, 360
        else:
            start_bearing = (heading - fov / 2) % 360
            end_bearing = (heading + fov / 2) % 360

        footprints.append({
            "sensor": sensor_name,
            "center_lat": lat, "center_lng": lng,
            "range_deg": round(range_deg, 4),
            "range_nm": spec["range_nm"],
            "fov_deg": fov,
            "start_bearing": round(start_bearing, 1),
            "end_bearing": round(end_bearing, 1),
            "detect_air": spec["detect_air"],
            "detect_ground": spec["detect_ground"],
            "detect_maritime": spec["detect_maritime"],
        })

    return footprints


# ─── Fused Track ──────────────────────────────────────────

class FusedTrack:
    """A correlated track from multiple sensor detections."""

    def __init__(self, track_id, lat, lng, source_id):
        self.id = track_id
        self.lat = lat
        self.lng = lng
        self.sources = {source_id: time.time()}
        self.confidence = 0.5
        self.classification = "UNKNOWN"
        self.threat_level = "UNKNOWN"
        self.velocity_lat = 0.0
        self.velocity_lng = 0.0
        self.uncertainty_semi_major = 0.005  # degrees
        self.uncertainty_semi_minor = 0.003
        self.uncertainty_angle = 0.0
        self.last_update = time.time()
        self.created = time.time()
        self.kill_chain_phase = "DETECT"
        self.kill_chain_times = {"DETECT": time.time()}
        self.associated_threat_id = None

    def update(self, lat, lng, source_id, classification=None, threat_level=None):
        """Update track with new detection."""
        now = time.time()
        dt = max(0.01, now - self.last_update)

        # Kalman-like weighted update
        alpha = 0.3 if len(self.sources) > 2 else 0.5
        self.velocity_lat = (lat - self.lat) / dt
        self.velocity_lng = (lng - self.lng) / dt
        self.lat = self.lat * (1 - alpha) + lat * alpha
        self.lng = self.lng * (1 - alpha) + lng * alpha

        self.sources[source_id] = now
        self.last_update = now

        # Confidence increases with more sources
        self.confidence = min(0.99, 0.3 + len(self.sources) * 0.15)

        # Uncertainty shrinks with more sources
        n = len(self.sources)
        self.uncertainty_semi_major = max(0.0005, 0.005 / math.sqrt(n))
        self.uncertainty_semi_minor = max(0.0003, 0.003 / math.sqrt(n))

        if classification and classification != "UNKNOWN":
            self.classification = classification
        if threat_level and threat_level != "UNKNOWN":
            self.threat_level = threat_level

        # Advance kill chain
        self._advance_kill_chain()

    def predict(self, dt_sec):
        """Predict position dt seconds into the future."""
        return {
            "lat": round(self.lat + self.velocity_lat * dt_sec, 6),
            "lng": round(self.lng + self.velocity_lng * dt_sec, 6),
            "uncertainty_growth": round(self.uncertainty_semi_major * (1 + dt_sec * 0.01), 4),
        }

    def _advance_kill_chain(self):
        now = time.time()
        if self.kill_chain_phase == "DETECT" and self.confidence > 0.4:
            self.kill_chain_phase = "IDENTIFY"
            self.kill_chain_times["IDENTIFY"] = now
        elif self.kill_chain_phase == "IDENTIFY" and self.confidence > 0.7 and self.classification != "UNKNOWN":
            self.kill_chain_phase = "DECIDE"
            self.kill_chain_times["DECIDE"] = now

    def to_dict(self):
        return {
            "id": self.id, "lat": round(self.lat, 6), "lng": round(self.lng, 6),
            "confidence": round(self.confidence, 2),
            "classification": self.classification,
            "threat_level": self.threat_level,
            "source_count": len(self.sources),
            "sources": list(self.sources.keys()),
            "velocity": {"lat": round(self.velocity_lat, 6), "lng": round(self.velocity_lng, 6)},
            "uncertainty": {
                "semi_major_deg": round(self.uncertainty_semi_major, 4),
                "semi_minor_deg": round(self.uncertainty_semi_minor, 4),
                "angle_deg": round(self.uncertainty_angle, 1),
            },
            "kill_chain": {
                "phase": self.kill_chain_phase,
                "times": {k: round(v, 1) for k, v in self.kill_chain_times.items()},
                "elapsed_sec": {k: round(time.time() - v, 1)
                                for k, v in self.kill_chain_times.items()},
            },
            "predicted_5min": self.predict(300),
            "predicted_15min": self.predict(900),
            "age_sec": round(time.time() - self.created, 1),
            "associated_threat_id": self.associated_threat_id,
        }


# ─── Sensor Fusion Engine (Main Class) ───────────────────

class SensorFusionEngine:
    """Multi-sensor fusion with track correlation and coverage analysis."""

    CORRELATION_THRESHOLD_DEG = 0.02  # ~1.2 km

    def __init__(self):
        self.tracks = {}  # track_id -> FusedTrack
        self.coverage_cache = {}  # asset_id -> [footprints]
        self.coverage_gaps = []
        self.kill_chain_log = []
        self.stats = {"tracks_created": 0, "correlations": 0,
                      "coverage_updates": 0, "kill_chain_advances": 0}

    def tick(self, assets, threats, dt=1.0):
        """Update fusion: correlate threats with sensor detections."""
        events = []

        # Update coverage footprints
        self.coverage_cache.clear()
        for aid, a in assets.items():
            self.coverage_cache[aid] = compute_coverage_footprint(a)
        self.stats["coverage_updates"] += 1

        # Correlate threats into fused tracks
        for tid, t in threats.items():
            if t.get("neutralized") or "lat" not in t:
                continue

            t_lat = t["lat"]
            t_lng = t.get("lng", t.get("lon", 0))

            # Find which assets can detect this threat
            detecting_assets = []
            for aid, a in assets.items():
                if self._can_detect(a, t_lat, t_lng, t.get("type", "")):
                    detecting_assets.append(aid)

            if not detecting_assets:
                continue

            # Try to correlate with existing track
            best_track, best_dist = None, float("inf")
            for trk in self.tracks.values():
                d = _dist_deg(trk.lat, trk.lng, t_lat, t_lng)
                if d < self.CORRELATION_THRESHOLD_DEG and d < best_dist:
                    best_track, best_dist = trk, d

            if best_track:
                # Update existing track
                for aid in detecting_assets:
                    best_track.update(t_lat, t_lng, aid,
                                      classification=t.get("type"),
                                      threat_level=t.get("threat_level"))
                best_track.associated_threat_id = tid
                self.stats["correlations"] += 1
            else:
                # Create new track
                trk_id = f"TRK-{uuid.uuid4().hex[:6]}"
                trk = FusedTrack(trk_id, t_lat, t_lng, detecting_assets[0])
                trk.associated_threat_id = tid
                trk.classification = t.get("type", "UNKNOWN")
                for aid in detecting_assets[1:]:
                    trk.update(t_lat, t_lng, aid)
                self.tracks[trk_id] = trk
                self.stats["tracks_created"] += 1
                events.append({
                    "type": "NEW_TRACK", "track_id": trk_id,
                    "threat_id": tid, "sources": detecting_assets,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        # Age out stale tracks
        now = time.time()
        stale = [tid for tid, t in self.tracks.items() if now - t.last_update > 60]
        for tid in stale:
            del self.tracks[tid]

        # Compute coverage gaps
        self._compute_gaps(assets)

        return events

    def advance_kill_chain(self, track_id, phase, operator="SYSTEM"):
        """Manually advance a track's kill chain (DECIDE→ENGAGE→ASSESS)."""
        trk = self.tracks.get(track_id)
        if not trk:
            return None
        valid_advances = {
            "DECIDE": "ENGAGE", "ENGAGE": "ASSESS", "IDENTIFY": "DECIDE",
        }
        if trk.kill_chain_phase in valid_advances and \
           valid_advances[trk.kill_chain_phase] == phase:
            trk.kill_chain_phase = phase
            trk.kill_chain_times[phase] = time.time()
            self.stats["kill_chain_advances"] += 1
            entry = {
                "track_id": track_id, "phase": phase, "operator": operator,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_elapsed_sec": round(time.time() - trk.created, 1),
            }
            self.kill_chain_log.append(entry)
            return entry
        return None

    def get_tracks(self):
        return {tid: t.to_dict() for tid, t in self.tracks.items()}

    def get_coverage(self):
        return dict(self.coverage_cache)

    def get_coverage_gaps(self):
        return list(self.coverage_gaps)

    def get_kill_chain_summary(self):
        phases = {"DETECT": 0, "IDENTIFY": 0, "DECIDE": 0, "ENGAGE": 0, "ASSESS": 0}
        for t in self.tracks.values():
            phases[t.kill_chain_phase] = phases.get(t.kill_chain_phase, 0) + 1
        avg_times = {}
        for entry in self.kill_chain_log[-100:]:
            p = entry["phase"]
            avg_times.setdefault(p, []).append(entry["total_elapsed_sec"])
        return {
            "phase_counts": phases,
            "avg_time_to_phase": {p: round(sum(t)/len(t), 1)
                                  for p, t in avg_times.items() if t},
            "total_tracks": len(self.tracks),
            "log": self.kill_chain_log[-20:],
        }

    def get_stats(self):
        return dict(self.stats)

    # ─── Helpers ──────────────────────────

    def _can_detect(self, asset, threat_lat, threat_lng, threat_type=""):
        ap = asset.get("position", asset)
        a_lat, a_lng = ap.get("lat", 0), ap.get("lng", 0)
        sensors = asset.get("sensors") or []
        domain_map = {"drone": "air", "vessel": "maritime", "gps_jammer": "ground",
                      "rf_emitter": "ground", "cyber": None}
        threat_domain = domain_map.get(threat_type.lower(), "ground")

        for sensor_name in sensors:
            spec = SENSOR_COVERAGE.get(sensor_name)
            if not spec or spec["range_nm"] == 0:
                continue
            range_deg = spec["range_nm"] * NM_TO_DEG
            d = _dist_deg(a_lat, a_lng, threat_lat, threat_lng)
            if d > range_deg:
                continue
            # Check domain detection capability
            if threat_domain == "air" and spec["detect_air"]:
                return True
            if threat_domain == "ground" and spec["detect_ground"]:
                return True
            if threat_domain == "maritime" and spec["detect_maritime"]:
                return True
            if threat_domain is None:
                return True
        return False

    def _compute_gaps(self, assets):
        """Identify areas not covered by any sensor."""
        if not assets:
            return
        # Sample grid around the AO
        lats = [a.get("position", a).get("lat", 0) for a in assets.values()]
        lngs = [a.get("position", a).get("lng", 0) for a in assets.values()]
        center_lat = sum(lats) / len(lats)
        center_lng = sum(lngs) / len(lngs)

        gaps = []
        step = 0.01
        for di in range(-5, 6):
            for dj in range(-5, 6):
                check_lat = center_lat + di * step
                check_lng = center_lng + dj * step
                covered = False
                for aid, a in assets.items():
                    if self._can_detect(a, check_lat, check_lng, "drone"):
                        covered = True
                        break
                if not covered:
                    gaps.append({"lat": round(check_lat, 4), "lng": round(check_lng, 4)})

        self.coverage_gaps = gaps
