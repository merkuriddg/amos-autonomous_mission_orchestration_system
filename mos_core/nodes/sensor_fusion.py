#!/usr/bin/env python3
"""
MOS Phase 4 — Sensor Fusion Engine
Fuses multi-sensor data (EO/IR, RADAR, SIGINT, LIDAR, SONAR)
into unified tracks using weighted Bayesian approach.
"""

import math
import threading
from datetime import datetime, timezone


class SensorFusion:
    """Merges detections from multiple sensors into fused tracks."""

    SENSOR_WEIGHTS = {
        "EO/IR": 0.85, "AESA_RADAR": 0.90, "SAR": 0.80,
        "SIGINT": 0.70, "ELINT": 0.65, "COMINT": 0.60,
        "LIDAR": 0.88, "SONAR": 0.75, "RADAR": 0.82,
        "AIS": 0.50, "ACOUSTIC": 0.55, "SEISMIC": 0.45,
        "RWR": 0.70, "GMTI": 0.78, "DIRECTION_FINDING": 0.72,
        "AEW_RADAR": 0.92, "MAGNETIC": 0.40, "CBRN": 0.60,
    }

    CORRELATION_RADIUS_DEG = 0.005  # ~550m

    def __init__(self):
        self.fused_tracks = {}
        self.raw_detections = []
        self._lock = threading.Lock()

    def ingest(self, detection: dict) -> dict:
        """
        detection = {
            "sensor_type": "EO/IR",
            "sensor_id": "REAPER-01",
            "lat": 27.78, "lng": -82.55,
            "confidence": 0.85,
            "classification": "UNKNOWN",
            "metadata": {...}
        }
        """
        detection["timestamp"] = datetime.now(timezone.utc).isoformat()
        detection["weight"] = self.SENSOR_WEIGHTS.get(
            detection.get("sensor_type", ""), 0.5
        ) * detection.get("confidence", 0.5)

        self.raw_detections.append(detection)
        if len(self.raw_detections) > 5000:
            self.raw_detections = self.raw_detections[-5000:]

        # Try to correlate with existing track
        correlated_id = self._correlate(detection)
        if correlated_id:
            return self._update_track(correlated_id, detection)
        else:
            return self._create_track(detection)

    def _correlate(self, detection: dict) -> str:
        """Find existing track within correlation radius."""
        det_lat = detection.get("lat", 0)
        det_lng = detection.get("lng", 0)
        best_id, best_dist = None, float("inf")
        for track_id, track in self.fused_tracks.items():
            dist = math.sqrt(
                (track["lat"] - det_lat)**2 + (track["lng"] - det_lng)**2
            )
            if dist < self.CORRELATION_RADIUS_DEG and dist < best_dist:
                best_dist = dist
                best_id = track_id
        return best_id

    def _create_track(self, detection: dict) -> dict:
        import random
        track_id = f"FUSED-{random.randint(10000, 99999)}"
        track = {
            "track_id": track_id,
            "lat": detection.get("lat", 0),
            "lng": detection.get("lng", 0),
            "classification": detection.get("classification", "UNKNOWN"),
            "confidence": detection.get("weight", 0.5),
            "contributing_sensors": [detection.get("sensor_type", "unknown")],
            "sensor_count": 1,
            "first_seen": detection["timestamp"],
            "last_seen": detection["timestamp"],
            "detections": [detection],
        }
        with self._lock:
            self.fused_tracks[track_id] = track
        return track

    def _update_track(self, track_id: str, detection: dict) -> dict:
        with self._lock:
            track = self.fused_tracks[track_id]
            # Weighted position update
            old_w = track["confidence"]
            new_w = detection.get("weight", 0.5)
            total_w = old_w + new_w
            track["lat"] = (track["lat"] * old_w + detection.get("lat", 0) * new_w) / total_w
            track["lng"] = (track["lng"] * old_w + detection.get("lng", 0) * new_w) / total_w
            # Update confidence (capped at 0.99)
            track["confidence"] = min(0.99, total_w / (total_w + 0.2))
            # Track sensors
            sensor = detection.get("sensor_type", "unknown")
            if sensor not in track["contributing_sensors"]:
                track["contributing_sensors"].append(sensor)
            track["sensor_count"] = len(track["contributing_sensors"])
            track["last_seen"] = detection["timestamp"]
            # Keep last 20 detections
            track["detections"].append(detection)
            if len(track["detections"]) > 20:
                track["detections"] = track["detections"][-20:]
            # Promote classification if higher-weight sensor provides one
            if (detection.get("classification", "UNKNOWN") != "UNKNOWN" and
                    new_w > old_w * 0.8):
                track["classification"] = detection["classification"]
        return track

    def get_track(self, track_id: str) -> dict:
        return self.fused_tracks.get(track_id, {})

    def get_all(self) -> dict:
        return dict(self.fused_tracks)

    def summary(self) -> dict:
        multi = sum(1 for t in self.fused_tracks.values() if t["sensor_count"] > 1)
        return {
            "total_fused_tracks": len(self.fused_tracks),
            "multi_sensor_tracks": multi,
            "raw_detections": len(self.raw_detections),
        }


if __name__ == "__main__":
    import json
    sf = SensorFusion()
    # Two sensors see same target
    sf.ingest({"sensor_type": "EO/IR", "sensor_id": "REAPER-01",
               "lat": 27.78, "lng": -82.55, "confidence": 0.85,
               "classification": "UNKNOWN"})
    sf.ingest({"sensor_type": "SIGINT", "sensor_id": "SPECTR-01",
               "lat": 27.7805, "lng": -82.5498, "confidence": 0.70,
               "classification": "HOSTILE"})
    # Different target
    sf.ingest({"sensor_type": "RADAR", "sensor_id": "TRITON-01",
               "lat": 27.72, "lng": -82.60, "confidence": 0.80,
               "classification": "UNKNOWN"})
    print(json.dumps(sf.summary(), indent=2))
    for tid, t in sf.get_all().items():
        print(f"  {tid}: {t['classification']} ({t['confidence']:.2f}) "
              f"sensors={t['contributing_sensors']}")
