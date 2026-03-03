"""
MOS AI Threat Classifier
Processes raw sensor contacts and produces threat assessments
using a simulated multi-layer classification pipeline:
  1. Contact fusion (deduplicate across sensors)
  2. Pattern-of-life analysis
  3. Threat level classification
  4. Action recommendation
"""

import rclpy
from rclpy.node import Node
from mos_interfaces.msg import ThreatContact, ThreatAssessment
from std_msgs.msg import String

import json
import time
import math
import random


# ── Threat Classification Rules ──
# In production this would be a trained ML model.
# Here we simulate realistic classification logic.

THREAT_PROFILES = {
    # contact_type -> possible classifications with threat levels
    "VEHICLE": {
        "T-72_TANK":        {"threat": 4, "action": "AVOID",    "indicators": ["ARMORED", "TRACKED", "CANNON"]},
        "BMP-2_IFV":        {"threat": 4, "action": "AVOID",    "indicators": ["ARMORED", "AUTOCANNON", "TROOP_CARRIER"]},
        "TECHNICAL":        {"threat": 3, "action": "TRACK",    "indicators": ["MOUNTED_WEAPON", "IRREGULAR", "HIGH_SPEED"]},
        "SUPPLY_TRUCK":     {"threat": 1, "action": "MONITOR",  "indicators": ["LOGISTICS", "SLOW_MOVING", "UNARMED"]},
    },
    "DISMOUNT": {
        "PATROL_3MAN":      {"threat": 2, "action": "TRACK",    "indicators": ["SMALL_UNIT", "ARMED", "PATROLLING"]},
        "PATROL_6MAN":      {"threat": 3, "action": "TRACK",    "indicators": ["SQUAD_SIZE", "ARMED", "TACTICAL_MOVEMENT"]},
        "SNIPER_TEAM":      {"threat": 4, "action": "ENGAGE",   "indicators": ["CONCEALED", "PRECISION_WEAPON", "OVERWATCH"]},
        "OBSERVER":         {"threat": 2, "action": "TRACK",    "indicators": ["OPTICS", "STATIONARY", "REPORTING"]},
    },
    "UAS": {
        "RECON_QUAD":       {"threat": 2, "action": "TRACK",    "indicators": ["SMALL_UAS", "ISR_PAYLOAD", "LOITERING"]},
        "KAMIKAZE_FPV":     {"threat": 4, "action": "ENGAGE",   "indicators": ["FPV", "HIGH_SPEED", "TERMINAL_DIVE"]},
        "MEDIUM_FIXED_WING":{"threat": 3, "action": "TRACK",    "indicators": ["FIXED_WING", "MEDIUM_ALT", "ISR_CAPABLE"]},
    },
    "VESSEL": {
        "FAST_ATTACK":      {"threat": 4, "action": "AVOID",    "indicators": ["HIGH_SPEED", "ARMED", "ATTACK_PROFILE"]},
        "FISHING_DHOW":     {"threat": 1, "action": "MONITOR",  "indicators": ["CIVILIAN", "SLOW", "COMMON_VESSEL"]},
        "RIGID_INFLATABLE": {"threat": 3, "action": "TRACK",    "indicators": ["FAST", "LOW_PROFILE", "POSSIBLE_SOF"]},
    },
    "IED": {
        "ROADSIDE_IED":     {"threat": 4, "action": "AVOID",    "indicators": ["DISTURBED_EARTH", "WIRE", "KILL_ZONE"]},
        "VBIED":            {"threat": 4, "action": "AVOID",    "indicators": ["SUSPICIOUS_VEH", "HEAVY_LOAD", "ABANDONED"]},
        "BURIED_MINE":      {"threat": 3, "action": "AVOID",    "indicators": ["METALLIC_SIG", "DISTURBED_SURFACE"]},
    },
    "ELECTRONIC": {
        "JAMMER":           {"threat": 3, "action": "REPORT",   "indicators": ["RF_EMISSION", "WIDEBAND", "DENIAL"]},
        "RADAR_EMITTER":    {"threat": 2, "action": "REPORT",   "indicators": ["PULSED_RF", "SEARCH_PATTERN"]},
        "COMMS_NODE":       {"threat": 2, "action": "REPORT",   "indicators": ["VHF_UHF", "ENCRYPTED", "C2_NODE"]},
    },
}

THREAT_LEVEL_NAMES = {
    0: "NONE", 1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"
}


class TrackedContact:
    """Fused contact being tracked by the classifier."""

    def __init__(self, contact_id: str):
        self.contact_id = contact_id
        self.contact_type = "UNKNOWN"
        self.lat = 0.0
        self.lon = 0.0
        self.alt = 0.0
        self.detections = 0
        self.sensors_used = set()
        self.detecting_assets = set()
        self.first_seen = time.time()
        self.last_seen = time.time()
        self.confidence_sum = 0.0
        self.classified = False
        self.classification = "UNKNOWN"
        self.threat_level = 0
        self.recommended_action = "MONITOR"
        self.indicators = []
        self.assigned_tracker = ""

    def update_from_detection(self, msg: ThreatContact):
        """Fuse a new detection into this tracked contact."""
        self.contact_type = msg.contact_type
        # Weighted position update (simple exponential moving average)
        alpha = 0.3
        self.lat = self.lat * (1 - alpha) + msg.latitude * alpha
        self.lon = self.lon * (1 - alpha) + msg.longitude * alpha
        self.alt = self.alt * (1 - alpha) + msg.altitude_m * alpha
        self.detections += 1
        self.sensors_used.add(msg.detecting_sensor)
        self.detecting_assets.add(msg.detecting_asset_id)
        self.last_seen = time.time()
        self.confidence_sum += msg.confidence

    @property
    def avg_confidence(self) -> float:
        return self.confidence_sum / max(1, self.detections)

    @property
    def multi_sensor(self) -> bool:
        return len(self.sensors_used) >= 2

    @property
    def age(self) -> float:
        return time.time() - self.first_seen


class ThreatClassifier(Node):
    """
    AI Threat Classification Node.
    Fuses raw contacts, classifies threats, recommends actions.
    """

    def __init__(self):
        super().__init__("mos_threat_classifier")
        self.get_logger().info("=" * 60)
        self.get_logger().info("  MOS AI THREAT CLASSIFIER")
        self.get_logger().info("  Classification Engine: Rule-based + Bayesian Fusion")
        self.get_logger().info("=" * 60)

        # Contact tracking database
        self.tracked: dict[str, TrackedContact] = {}

        # Subscribers
        self.create_subscription(
            ThreatContact, "/mos/threats/raw_contacts",
            self._on_raw_contact, 50
        )

        # Publishers
        self.assessment_pub = self.create_publisher(
            ThreatAssessment, "/mos/threats/assessments", 10
        )
        self.alert_pub = self.create_publisher(
            String, "/mos/threats/alerts", 10
        )

        # Classification cycle at 2 Hz
        self.create_timer(0.5, self._classify_cycle)

        # Cleanup stale contacts every 10s
        self.create_timer(10.0, self._cleanup)

        # Status report
        self.create_timer(10.0, self._status_report)

        self.get_logger().info("Classifier online. Monitoring for hostile contacts...")

    def _on_raw_contact(self, msg: ThreatContact):
        """Receive and fuse raw sensor detections."""
        cid = msg.contact_id

        if cid not in self.tracked:
            tc = TrackedContact(cid)
            tc.lat = msg.latitude
            tc.lon = msg.longitude
            tc.alt = msg.altitude_m
            self.tracked[cid] = tc

        self.tracked[cid].update_from_detection(msg)

    def _classify_cycle(self):
        """Run classification on all tracked contacts."""
        for cid, tc in self.tracked.items():
            # Need minimum detections for classification
            if tc.detections < 2:
                continue

            # Classify if not yet done, or re-classify periodically
            if not tc.classified or tc.detections % 5 == 0:
                self._classify_contact(tc)

    def _classify_contact(self, tc: TrackedContact):
        """Run the classification pipeline on a contact."""
        profiles = THREAT_PROFILES.get(tc.contact_type, {})
        if not profiles:
            tc.classification = f"UNKNOWN_{tc.contact_type}"
            tc.threat_level = 1
            tc.recommended_action = "MONITOR"
            tc.indicators = ["UNCLASSIFIED"]
            tc.classified = True
            self._publish_assessment(tc)
            return

        # Pick a classification based on weighted random (simulating ML inference)
        # In production: actual model inference here
        subtypes = list(profiles.items())
        chosen_name, profile = random.choice(subtypes)

        # Boost confidence with multi-sensor fusion
        base_confidence = tc.avg_confidence
        if tc.multi_sensor:
            base_confidence = min(0.98, base_confidence * 1.2)

        # Boost with repeated detections
        detection_boost = min(0.15, tc.detections * 0.01)
        final_confidence = min(0.99, base_confidence + detection_boost)

        tc.classification = chosen_name
        tc.threat_level = profile["threat"]
        tc.recommended_action = profile["action"]
        tc.indicators = list(profile["indicators"])

        # Add fusion indicators
        if tc.multi_sensor:
            tc.indicators.append("MULTI_SENSOR_CONFIRMED")
        if tc.detections >= 5:
            tc.indicators.append("PERSISTENT_TRACK")
        if len(tc.detecting_assets) >= 3:
            tc.indicators.append("MULTI_ASSET_DETECTION")

        was_classified = tc.classified
        tc.classified = True

        self._publish_assessment(tc, final_confidence)

        # Alert on HIGH and CRITICAL threats (first classification only)
        if not was_classified and tc.threat_level >= 3:
            self._publish_alert(tc, final_confidence)

    def _publish_assessment(self, tc: TrackedContact, confidence: float = 0.0):
        """Publish a threat assessment message."""
        msg = ThreatAssessment()
        msg.contact_id = tc.contact_id
        msg.classification = tc.classification
        msg.threat_level = tc.threat_level
        msg.confidence = confidence or tc.avg_confidence
        msg.recommended_action = tc.recommended_action
        msg.indicators = tc.indicators
        msg.latitude = tc.lat
        msg.longitude = tc.lon
        msg.altitude_m = tc.alt
        msg.assigned_tracker_id = tc.assigned_tracker
        now = time.time()
        msg.stamp.sec = int(now)
        msg.stamp.nanosec = int((now % 1) * 1e9)
        self.assessment_pub.publish(msg)

    def _publish_alert(self, tc: TrackedContact, confidence: float):
        """Publish high-priority threat alert."""
        level_name = THREAT_LEVEL_NAMES.get(tc.threat_level, "UNKNOWN")
        alert = {
            "alert_type": "THREAT",
            "contact_id": tc.contact_id,
            "classification": tc.classification,
            "threat_level": tc.threat_level,
            "threat_level_name": level_name,
            "confidence": round(confidence, 2),
            "recommended_action": tc.recommended_action,
            "lat": round(tc.lat, 6),
            "lon": round(tc.lon, 6),
            "sensors": list(tc.sensors_used),
            "detecting_assets": list(tc.detecting_assets),
            "indicators": tc.indicators,
            "time": time.time(),
        }

        msg = String()
        msg.data = json.dumps(alert)
        self.alert_pub.publish(msg)

        self.get_logger().warn(
            f"⚠️  THREAT ALERT: {level_name} — {tc.classification} "
            f"({tc.contact_id}) confidence={confidence:.0%} "
            f"action={tc.recommended_action} "
            f"sensors={list(tc.sensors_used)}"
        )

    def _cleanup(self):
        """Remove contacts not seen for 30+ seconds."""
        now = time.time()
        stale = [cid for cid, tc in self.tracked.items() if now - tc.last_seen > 30]
        for cid in stale:
            tc = self.tracked.pop(cid)
            self.get_logger().info(
                f"[CLASSIFY] Contact {cid} lost — last classified as "
                f"{tc.classification} (threat={tc.threat_level})"
            )

    def _status_report(self):
        """Periodic classification summary."""
        if not self.tracked:
            return

        by_level = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
        for tc in self.tracked.values():
            by_level[tc.threat_level] = by_level.get(tc.threat_level, 0) + 1

        self.get_logger().info(
            f"[AI SITREP] Tracking {len(self.tracked)} contacts — "
            f"CRIT:{by_level[4]} HIGH:{by_level[3]} "
            f"MED:{by_level[2]} LOW:{by_level[1]} NONE:{by_level[0]}"
        )


def main(args=None):
    rclpy.init(args=args)
    node = ThreatClassifier()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
