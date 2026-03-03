"""
MOS Threat Injector
Simulates hostile and unknown contacts appearing in the battlespace.
Contacts move, change behavior, and sometimes disappear.
"""

import rclpy
from rclpy.node import Node
from mos_interfaces.msg import ThreatContact, AssetState
from builtin_interfaces.msg import Time

import random
import math
import time
import uuid


class SimulatedContact:
    """A simulated hostile or unknown contact."""

    CONTACT_TYPES = [
        {"type": "VEHICLE", "subtypes": ["T-72_TANK", "BMP-2_IFV", "TECHNICAL", "SUPPLY_TRUCK"],
         "speed_range": (2.0, 8.0), "alt": 0.0},
        {"type": "DISMOUNT", "subtypes": ["PATROL_3MAN", "PATROL_6MAN", "SNIPER_TEAM", "OBSERVER"],
         "speed_range": (0.5, 2.0), "alt": 0.0},
        {"type": "UAS", "subtypes": ["RECON_QUAD", "KAMIKAZE_FPV", "MEDIUM_FIXED_WING"],
         "speed_range": (5.0, 20.0), "alt": 80.0},
        {"type": "VESSEL", "subtypes": ["FAST_ATTACK", "FISHING_DHOW", "RIGID_INFLATABLE"],
         "speed_range": (2.0, 10.0), "alt": 0.0},
        {"type": "IED", "subtypes": ["ROADSIDE_IED", "VBIED", "BURIED_MINE"],
         "speed_range": (0.0, 0.0), "alt": 0.0},
        {"type": "ELECTRONIC", "subtypes": ["JAMMER", "RADAR_EMITTER", "COMMS_NODE"],
         "speed_range": (0.0, 1.0), "alt": 0.0},
    ]

    def __init__(self, center_lat: float, center_lon: float):
        template = random.choice(self.CONTACT_TYPES)

        self.contact_id = f"TANGO-{uuid.uuid4().hex[:6].upper()}"
        self.contact_type = template["type"]
        self.subtype = random.choice(template["subtypes"])
        self.speed = random.uniform(*template["speed_range"])
        self.heading = random.uniform(0, 360)

        # Spawn at random offset from center
        offset_lat = random.uniform(-0.008, 0.008)
        offset_lon = random.uniform(-0.008, 0.008)
        self.lat = center_lat + offset_lat
        self.lon = center_lon + offset_lon
        self.alt = template["alt"] + random.uniform(-5, 20)

        self.alive = True
        self.age = 0.0
        self.max_age = random.uniform(60.0, 300.0)  # Lives 1-5 minutes

        # Movement behavior
        self.behavior = random.choice(["LINEAR", "PATROL", "STATIONARY", "APPROACH"])
        self.patrol_center_lat = self.lat
        self.patrol_center_lon = self.lon
        self.patrol_radius = random.uniform(0.001, 0.003)
        self.patrol_angle = 0.0

    def update(self, dt: float, platoon_center_lat: float, platoon_center_lon: float):
        """Advance the contact simulation."""
        self.age += dt

        if self.age > self.max_age:
            self.alive = False
            return

        if self.behavior == "STATIONARY":
            return

        if self.behavior == "LINEAR":
            move_deg = (self.speed * dt) / 111320.0
            self.lat += move_deg * math.cos(math.radians(self.heading))
            self.lon += move_deg * math.sin(math.radians(self.heading))

        elif self.behavior == "PATROL":
            self.patrol_angle += (self.speed * dt) / (self.patrol_radius * 111320.0)
            self.lat = self.patrol_center_lat + self.patrol_radius * math.cos(self.patrol_angle)
            self.lon = self.patrol_center_lon + self.patrol_radius * math.sin(self.patrol_angle)

        elif self.behavior == "APPROACH":
            dlat = platoon_center_lat - self.lat
            dlon = platoon_center_lon - self.lon
            dist = math.sqrt(dlat**2 + dlon**2)
            if dist > 0.0005:
                move_deg = (self.speed * dt) / 111320.0
                self.lat += (dlat / dist) * move_deg
                self.lon += (dlon / dist) * move_deg
            self.heading = math.degrees(math.atan2(dlon, dlat)) % 360

        # Random heading changes for linear
        if self.behavior == "LINEAR" and random.random() < 0.01:
            self.heading += random.uniform(-30, 30)
            self.heading %= 360

    def to_msg(self, detecting_asset: str, sensor: str) -> ThreatContact:
        msg = ThreatContact()
        msg.contact_id = self.contact_id
        msg.contact_type = self.contact_type
        msg.detecting_asset_id = detecting_asset
        msg.detecting_sensor = sensor
        msg.latitude = self.lat
        msg.longitude = self.lon
        msg.altitude_m = self.alt
        msg.confidence = random.uniform(0.5, 0.95)
        msg.bearing_deg = self.heading
        msg.range_m = random.uniform(100, 2000)
        now = time.time()
        msg.stamp.sec = int(now)
        msg.stamp.nanosec = int((now % 1) * 1e9)
        return msg


class ThreatInjector(Node):
    """
    Spawns simulated enemy/unknown contacts in the battlespace.
    Contacts are detected by nearby friendly assets and published
    as raw sensor contacts for the AI classifier to process.
    """

    def __init__(self):
        super().__init__("mos_threat_injector")
        self.get_logger().info("=" * 60)
        self.get_logger().info("  MOS THREAT INJECTOR — HOSTILE CONTACT SIMULATOR")
        self.get_logger().info("=" * 60)

        # Battlespace center (where our platoon is)
        self.center_lat = 33.998
        self.center_lon = -118.003

        # Active contacts
        self.contacts: list[SimulatedContact] = []

        # Track friendly asset positions for detection range
        self.friendly_assets: dict[str, dict] = {}

        # Available sensors per domain
        self.domain_sensors = {
            "AIR": ["EO", "IR", "RADAR"],
            "GROUND": ["EO", "IR", "ACOUSTIC", "RADAR"],
            "MARITIME": ["RADAR", "ACOUSTIC", "EO"],
        }

        # Publisher
        self.contact_pub = self.create_publisher(
            ThreatContact, "/mos/threats/raw_contacts", 10
        )

        # Subscribe to asset states to know where friendlies are
        self.create_subscription(
            AssetState, "/mos/cop/assets", self._on_friendly_asset, 50
        )

        # Spawn new contacts every 8-15 seconds
        self.create_timer(2.0, self._spawn_tick)
        self._spawn_cooldown = 0.0

        # Simulate contacts at 5 Hz
        self.create_timer(0.2, self._sim_tick)

        # Detection scan at 1 Hz
        self.create_timer(1.0, self._detection_scan)

        # Status report
        self.create_timer(10.0, self._status_report)

        self.get_logger().info("Threat injector online. Hostiles will appear shortly...")

    def _on_friendly_asset(self, msg: AssetState):
        self.friendly_assets[msg.asset_id] = {
            "asset_id": msg.asset_id,
            "asset_type": msg.asset_type,
            "lat": msg.latitude,
            "lon": msg.longitude,
            "alt": msg.altitude_m,
        }

    def _spawn_tick(self):
        """Periodically spawn new contacts."""
        self._spawn_cooldown -= 2.0

        if self._spawn_cooldown <= 0 and len(self.contacts) < 8:
            # Spawn 1-3 contacts
            count = random.randint(1, 2)
            for _ in range(count):
                contact = SimulatedContact(self.center_lat, self.center_lon)
                self.contacts.append(contact)
                self.get_logger().info(
                    f"[THREAT] NEW CONTACT: {contact.contact_id} "
                    f"type={contact.contact_type} subtype={contact.subtype} "
                    f"behavior={contact.behavior}"
                )

            self._spawn_cooldown = random.uniform(8.0, 20.0)

    def _sim_tick(self):
        """Update all contact positions."""
        for contact in self.contacts:
            contact.update(0.2, self.center_lat, self.center_lon)

        # Remove dead contacts
        before = len(self.contacts)
        self.contacts = [c for c in self.contacts if c.alive]
        removed = before - len(self.contacts)
        if removed > 0:
            self.get_logger().info(f"[THREAT] {removed} contact(s) lost from battlespace")

    def _detection_scan(self):
        """Check which friendlies can detect which contacts, publish detections."""
        for contact in self.contacts:
            for asset_id, asset in self.friendly_assets.items():
                # Calculate range
                dlat = contact.lat - asset["lat"]
                dlon = contact.lon - asset["lon"]
                range_m = math.sqrt(dlat**2 + dlon**2) * 111320.0

                # Detection range by domain
                max_range = {
                    "AIR": 3000.0,      # Air assets see further
                    "GROUND": 1500.0,
                    "MARITIME": 2000.0,
                }.get(asset["asset_type"], 1000.0)

                if range_m < max_range:
                    # This asset detects this contact
                    sensor = random.choice(
                        self.domain_sensors.get(asset["asset_type"], ["EO"])
                    )
                    msg = contact.to_msg(asset_id, sensor)
                    msg.range_m = range_m

                    # Confidence degrades with range
                    msg.confidence = max(0.3, 1.0 - (range_m / max_range) * 0.5)

                    self.contact_pub.publish(msg)

    def _status_report(self):
        types = {}
        for c in self.contacts:
            types[c.contact_type] = types.get(c.contact_type, 0) + 1
        type_str = " | ".join(f"{k}:{v}" for k, v in types.items()) or "NONE"
        self.get_logger().info(
            f"[THREAT SITREP] Active contacts: {len(self.contacts)} — {type_str}"
        )


def main(args=None):
    rclpy.init(args=args)
    node = ThreatInjector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
