"""Threat Predictor — movement prediction, probability heatmaps, pattern detection.

Uses threat position history for linear extrapolation, velocity estimation,
and predicted intercept opportunities.
"""

import math, random
from datetime import datetime, timezone


class ThreatPredictor:
    """Predicts threat movement and generates probability heatmaps."""

    def __init__(self):
        self.predictions = {}    # {threat_id: prediction_dict}
        self.patterns = {}       # {threat_id: pattern_dict}
        self.heatmap_grid = []   # [{lat, lng, probability}]
        self._history = {}       # {threat_id: [(lat, lng, timestamp)]}

    def tick(self, sim_threats, eob_units, sim_assets, dt):
        """
        Update predictions based on latest threat positions.
        Called from sim_tick.
        """
        # 1) Collect position history from EOB + threats
        for tid, t in sim_threats.items():
            if t.get("neutralized") or "lat" not in t:
                continue
            if tid not in self._history:
                self._history[tid] = []
            hist = self._history[tid]
            pos = (t["lat"], t.get("lng", 0))
            if not hist or hist[-1][:2] != pos:
                hist.append((pos[0], pos[1], datetime.now(timezone.utc).isoformat()))
            # Keep last 100 points
            if len(hist) > 100:
                del hist[:50]

        # Also pull from EOB position trails
        for uid, eu in eob_units.items():
            if uid not in self._history:
                self._history[uid] = []
            for p in eu.get("positions", [])[-20:]:
                pos = (p.get("lat", 0), p.get("lng", 0))
                hist = self._history[uid]
                if not hist or hist[-1][:2] != pos:
                    hist.append((pos[0], pos[1], p.get("ts", "")))

        # 2) Compute predictions for each active threat
        self.predictions = {}
        for tid, t in sim_threats.items():
            if t.get("neutralized") or "lat" not in t:
                continue
            hist = self._history.get(tid, [])
            if len(hist) < 2:
                continue
            pred = self._predict_positions(tid, t, hist)
            self.predictions[tid] = pred

        # 3) Detect movement patterns
        self.patterns = {}
        for tid, hist in self._history.items():
            if len(hist) >= 5:
                pattern = self._detect_pattern(tid, hist)
                if pattern:
                    self.patterns[tid] = pattern

        # 4) Generate heatmap
        self._generate_heatmap(sim_threats)

    def _predict_positions(self, tid, threat, history):
        """Linear extrapolation of threat position."""
        if len(history) < 2:
            return None
        # Get velocity from last few positions
        recent = history[-min(10, len(history)):]
        dlat = recent[-1][0] - recent[0][0]
        dlng = recent[-1][1] - recent[0][1]
        n = len(recent) - 1
        if n == 0:
            return None
        vlat = dlat / n  # degrees per sample
        vlng = dlng / n

        # Speed estimate (rough — degrees to km)
        speed_deg_per_sample = math.sqrt(vlat**2 + vlng**2)
        speed_kmh = speed_deg_per_sample * 111 * 3600 / 2  # very rough

        cur_lat, cur_lng = recent[-1][0], recent[-1][1]
        heading = math.degrees(math.atan2(vlng, vlat)) % 360

        # Predict at T+5, T+10, T+15 min (samples ≈ every 2s, so ~150 samples per 5 min)
        predictions = []
        for minutes in [5, 10, 15]:
            factor = minutes * 30  # ~30 samples per minute
            p_lat = round(cur_lat + vlat * factor, 6)
            p_lng = round(cur_lng + vlng * factor, 6)
            predictions.append({
                "t_minutes": minutes,
                "lat": p_lat, "lng": p_lng,
                "confidence": max(0.2, 1.0 - minutes * 0.05),
            })

        return {
            "threat_id": tid,
            "threat_type": threat.get("type", "unknown"),
            "current": {"lat": cur_lat, "lng": cur_lng},
            "velocity": {"dlat": round(vlat, 8), "dlng": round(vlng, 8)},
            "heading_deg": round(heading, 1),
            "speed_est_kmh": round(speed_kmh, 1),
            "predicted_positions": predictions,
            "history_points": len(history),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _detect_pattern(self, tid, history):
        """Detect movement patterns: circling, approaching, flanking, static."""
        if len(history) < 5:
            return None

        recent = history[-20:]
        lats = [p[0] for p in recent]
        lngs = [p[1] for p in recent]

        # Calculate total displacement vs total distance
        total_dist = sum(math.sqrt((recent[i][0] - recent[i-1][0])**2 +
                                    (recent[i][1] - recent[i-1][1])**2)
                         for i in range(1, len(recent)))
        displacement = math.sqrt((recent[-1][0] - recent[0][0])**2 +
                                  (recent[-1][1] - recent[0][1])**2)

        if total_dist < 0.0001:
            pattern_type = "STATIC"
            confidence = 0.9
        elif displacement < total_dist * 0.3:
            pattern_type = "CIRCLING"
            confidence = round(1.0 - displacement / max(0.001, total_dist), 2)
        else:
            # Check heading consistency
            headings = []
            for i in range(1, len(recent)):
                dy = recent[i][0] - recent[i-1][0]
                dx = recent[i][1] - recent[i-1][1]
                if abs(dy) + abs(dx) > 0.00001:
                    headings.append(math.degrees(math.atan2(dx, dy)) % 360)
            if headings:
                avg_heading = sum(headings) / len(headings)
                heading_var = sum((h - avg_heading)**2 for h in headings) / len(headings)
                if heading_var < 500:
                    pattern_type = "LINEAR_APPROACH"
                    confidence = max(0.5, 1.0 - heading_var / 1000)
                else:
                    pattern_type = "EVASIVE"
                    confidence = min(0.9, heading_var / 2000)
            else:
                pattern_type = "UNKNOWN"
                confidence = 0.3

        return {
            "threat_id": tid,
            "pattern": pattern_type,
            "confidence": round(confidence, 2),
            "total_distance_deg": round(total_dist, 6),
            "displacement_deg": round(displacement, 6),
            "samples": len(recent),
        }

    def _generate_heatmap(self, sim_threats):
        """Generate probability heatmap grid from predictions."""
        points = []
        for tid, pred in self.predictions.items():
            if not pred:
                continue
            # Current position — high probability
            points.append({
                "lat": pred["current"]["lat"],
                "lng": pred["current"]["lng"],
                "probability": 0.95,
                "source": "current",
            })
            # Predicted positions — decreasing probability
            for pp in pred.get("predicted_positions", []):
                points.append({
                    "lat": pp["lat"],
                    "lng": pp["lng"],
                    "probability": round(pp["confidence"] * 0.7, 2),
                    "source": f"T+{pp['t_minutes']}min",
                })
                # Add uncertainty spread around prediction
                spread = 0.005 * pp["t_minutes"]
                for _ in range(3):
                    points.append({
                        "lat": round(pp["lat"] + random.uniform(-spread, spread), 6),
                        "lng": round(pp["lng"] + random.uniform(-spread, spread), 6),
                        "probability": round(pp["confidence"] * 0.3, 2),
                        "source": "uncertainty",
                    })
        self.heatmap_grid = points

    def get_predictions(self):
        return list(self.predictions.values())

    def get_heatmap(self):
        return self.heatmap_grid

    def get_patterns(self):
        return list(self.patterns.values())

    def get_intercepts(self, sim_assets, sim_threats):
        """Calculate optimal intercept windows — which asset can reach which threat."""
        intercepts = []
        for tid, pred in self.predictions.items():
            if not pred or not pred.get("predicted_positions"):
                continue
            t_cur = pred["current"]
            for a in sim_assets.values():
                if not a.get("weapons") and "EW_JAMMER" not in (a.get("sensors") or []):
                    continue
                a_lat = a["position"]["lat"]
                a_lng = a["position"]["lng"]
                # Distance to current threat position
                dist = math.sqrt((a_lat - t_cur["lat"])**2 + (a_lng - t_cur["lng"])**2)
                # Rough time to intercept (assuming asset speed)
                speed_deg_s = a.get("speed_kts", 50) * 0.00001
                if speed_deg_s > 0:
                    time_to_intercept_sec = dist / speed_deg_s
                else:
                    time_to_intercept_sec = 9999
                # Only include if intercept within 15 min
                if time_to_intercept_sec < 900:
                    intercepts.append({
                        "asset_id": a["id"],
                        "threat_id": tid,
                        "threat_type": pred["threat_type"],
                        "distance_deg": round(dist, 6),
                        "time_to_intercept_sec": round(time_to_intercept_sec),
                        "time_to_intercept_min": round(time_to_intercept_sec / 60, 1),
                        "feasibility": "HIGH" if time_to_intercept_sec < 120 else
                                       "MEDIUM" if time_to_intercept_sec < 300 else "LOW",
                    })
        intercepts.sort(key=lambda x: x["time_to_intercept_sec"])
        return intercepts[:30]
