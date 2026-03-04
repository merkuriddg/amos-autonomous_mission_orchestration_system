#!/usr/bin/env python3
"""
MOS Phase 4 — Threat Detection & Classification
Multi-layer threat assessment with confidence scoring.
"""

import math
import threading
import random
from datetime import datetime, timezone

BASE_LAT = 27.8491
BASE_LNG = -82.5212


class ThreatClassification:
    HOSTILE = "HOSTILE"
    SUSPECT = "SUSPECT"
    UNKNOWN = "UNKNOWN"
    NEUTRAL = "NEUTRAL"
    FRIENDLY = "FRIENDLY"


class ThreatDetector:
    """Fuses sensor data to detect, track, and classify threats."""

    def __init__(self):
        self.tracks = {}
        self.classification_log = []
        self._lock = threading.Lock()
        self.rules = [
            {"name": "rf_hostile_freq", "weight": 0.3,
             "check": lambda t: t.get("rf_freq_mhz", 0) in [915.0, 2437.0, 5805.0]},
            {"name": "high_speed_approach", "weight": 0.25,
             "check": lambda t: t.get("speed_kts", 0) > 40 and t.get("closing", False)},
            {"name": "no_transponder", "weight": 0.2,
             "check": lambda t: not t.get("transponder", False)},
            {"name": "rf_power_anomaly", "weight": 0.15,
             "check": lambda t: t.get("power_dbm", -100) > 30},
            {"name": "known_signature", "weight": 0.1,
             "check": lambda t: t.get("signature_match", False)},
        ]

    def ingest(self, detection: dict) -> dict:
        """Process a new sensor detection."""
        track_id = detection.get("id", f"TRK-{random.randint(10000,99999)}")
        detection["track_id"] = track_id
        detection["first_seen"] = detection.get("first_seen",
                                                 datetime.now(timezone.utc).isoformat())
        detection["last_seen"] = datetime.now(timezone.utc).isoformat()

        # Calculate distance to base
        lat = detection.get("lat", 0)
        lng = detection.get("lng", 0)
        dist_deg = math.sqrt((lat - BASE_LAT)**2 + (lng - BASE_LNG)**2)
        detection["distance_nm"] = round(dist_deg * 60, 1)

        # Check if closing
        if track_id in self.tracks:
            old_dist = self.tracks[track_id].get("distance_nm", 999)
            detection["closing"] = detection["distance_nm"] < old_dist
        else:
            detection["closing"] = True

        # Classify
        classification = self._classify(detection)
        detection["classification"] = classification["classification"]
        detection["confidence"] = classification["confidence"]
        detection["threat_score"] = classification["threat_score"]
        detection["matched_rules"] = classification["matched_rules"]

        with self._lock:
            self.tracks[track_id] = detection

        if classification["threat_score"] > 0.5:
            self.classification_log.append({
                "track_id": track_id,
                "classification": classification["classification"],
                "confidence": classification["confidence"],
                "distance_nm": detection["distance_nm"],
                "timestamp": detection["last_seen"],
            })
            if len(self.classification_log) > 1000:
                self.classification_log = self.classification_log[-1000:]

        return detection

    def _classify(self, detection: dict) -> dict:
        score = 0.0
        matched = []
        for rule in self.rules:
            try:
                if rule["check"](detection):
                    score += rule["weight"]
                    matched.append(rule["name"])
            except Exception:
                pass
        score = min(1.0, score)
        if score > 0.7:
            classification = ThreatClassification.HOSTILE
        elif score > 0.4:
            classification = ThreatClassification.SUSPECT
        elif score > 0.2:
            classification = ThreatClassification.UNKNOWN
        else:
            classification = ThreatClassification.NEUTRAL
        confidence = min(0.95, 0.5 + score * 0.5)
        return {
            "classification": classification,
            "confidence": round(confidence, 2),
            "threat_score": round(score, 3),
            "matched_rules": matched,
        }

    def get_track(self, track_id: str) -> dict:
        return self.tracks.get(track_id, {})

    def get_all_tracks(self) -> dict:
        return dict(self.tracks)

    def get_hostile_tracks(self) -> list:
        return [t for t in self.tracks.values()
                if t.get("classification") == ThreatClassification.HOSTILE]

    def get_tracks_within(self, radius_nm: float) -> list:
        return [t for t in self.tracks.values()
                if t.get("distance_nm", 999) <= radius_nm]

    def drop_track(self, track_id: str) -> bool:
        if track_id in self.tracks:
            del self.tracks[track_id]
            return True
        return False

    def summary(self) -> dict:
        cls_counts = {}
        for t in self.tracks.values():
            c = t.get("classification", "UNKNOWN")
            cls_counts[c] = cls_counts.get(c, 0) + 1
        return {
            "total_tracks": len(self.tracks),
            "by_classification": cls_counts,
            "hostile_within_10nm": len([t for t in self.tracks.values()
                                        if t.get("classification") == "HOSTILE"
                                        and t.get("distance_nm", 999) <= 10]),
        }


if __name__ == "__main__":
    import json
    td = ThreatDetector()
    td.ingest({"id": "HOSTILE-DRO-001", "lat": 27.78, "lng": -82.55,
               "rf_freq_mhz": 915.0, "speed_kts": 50, "power_dbm": 25,
               "transponder": False})
    td.ingest({"id": "CIVIL-001", "lat": 27.90, "lng": -82.40,
               "rf_freq_mhz": 122.8, "speed_kts": 120, "power_dbm": -10,
               "transponder": True})
    print(json.dumps(td.summary(), indent=2))
    for t in td.get_hostile_tracks():
        print(f"  HOSTILE: {t['track_id']} at {t['distance_nm']}nm, "
              f"confidence={t['confidence']}")
