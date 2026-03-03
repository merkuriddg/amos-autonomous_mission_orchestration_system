"""
MOS Platoon Simulator — 25 Robotic Assets (Full Version)
Simulates the Mavrix1 Robotic Platoon across 3 domains:
  10 AIR, 12 GROUND, 3 MARITIME
"""

import rclpy
from rclpy.node import Node
from mos_interfaces.msg import AssetState, TaskOrder
from std_msgs.msg import String

import random
import math
import json
import time


# Base location (Fort Liberty area)
BASE_LAT = 35.1380
BASE_LON = -79.0064

# Platoon manifest
PLATOON_MANIFEST = [
    # AIR assets (10)
    {"id": "MVRX-A01", "type": "AIR",      "callsign": "HAWK-1",    "lat_off": 0.002,  "lon_off": 0.001},
    {"id": "MVRX-A02", "type": "AIR",      "callsign": "HAWK-2",    "lat_off": 0.002,  "lon_off": -0.001},
    {"id": "MVRX-A03", "type": "AIR",      "callsign": "HAWK-3",    "lat_off": 0.003,  "lon_off": 0.002},
    {"id": "MVRX-A04", "type": "AIR",      "callsign": "RAVEN-1",   "lat_off": 0.001,  "lon_off": 0.003},
    {"id": "MVRX-A05", "type": "AIR",      "callsign": "RAVEN-2",   "lat_off": -0.001, "lon_off": 0.003},
    {"id": "MVRX-A06", "type": "AIR",      "callsign": "EAGLE-1",   "lat_off": 0.004,  "lon_off": 0.000},
    {"id": "MVRX-A07", "type": "AIR",      "callsign": "EAGLE-2",   "lat_off": 0.004,  "lon_off": 0.002},
    {"id": "MVRX-A08", "type": "AIR",      "callsign": "OSPREY-1",  "lat_off": 0.005,  "lon_off": 0.001},
    {"id": "MVRX-A09", "type": "AIR",      "callsign": "OSPREY-2",  "lat_off": 0.005,  "lon_off": -0.001},
    {"id": "MVRX-A10", "type": "AIR",      "callsign": "RELAY-1",   "lat_off": 0.003,  "lon_off": 0.000},
    # GROUND assets (12)
    {"id": "MVRX-G01", "type": "GROUND",   "callsign": "WOLF-1",    "lat_off": -0.001, "lon_off": 0.001},
    {"id": "MVRX-G02", "type": "GROUND",   "callsign": "WOLF-2",    "lat_off": -0.001, "lon_off": -0.001},
    {"id": "MVRX-G03", "type": "GROUND",   "callsign": "WOLF-3",    "lat_off": -0.002, "lon_off": 0.002},
    {"id": "MVRX-G04", "type": "GROUND",   "callsign": "WOLF-4",    "lat_off": -0.002, "lon_off": -0.002},
    {"id": "MVRX-G05", "type": "GROUND",   "callsign": "BEAR-1",    "lat_off": -0.003, "lon_off": 0.001},
    {"id": "MVRX-G06", "type": "GROUND",   "callsign": "BEAR-2",    "lat_off": -0.003, "lon_off": -0.001},
    {"id": "MVRX-G07", "type": "GROUND",   "callsign": "RHINO-1",   "lat_off": -0.004, "lon_off": 0.000},
    {"id": "MVRX-G08", "type": "GROUND",   "callsign": "RHINO-2",   "lat_off": -0.004, "lon_off": 0.002},
    {"id": "MVRX-G09", "type": "GROUND",   "callsign": "MULE-1",    "lat_off": -0.005, "lon_off": 0.001},
    {"id": "MVRX-G10", "type": "GROUND",   "callsign": "MULE-2",    "lat_off": -0.005, "lon_off": -0.001},
    {"id": "MVRX-G11", "type": "GROUND",   "callsign": "MULE-3",    "lat_off": -0.006, "lon_off": 0.000},
    {"id": "MVRX-G12", "type": "GROUND",   "callsign": "SENTRY-1",  "lat_off": -0.002, "lon_off": 0.000},
    # MARITIME assets (3)
    {"id": "MVRX-M01", "type": "MARITIME",  "callsign": "SHARK-1",  "lat_off": 0.000,  "lon_off": -0.004},
    {"id": "MVRX-M02", "type": "MARITIME",  "callsign": "SHARK-2",  "lat_off": 0.001,  "lon_off": -0.005},
    {"id": "MVRX-M03", "type": "MARITIME",  "callsign": "ORCA-1",   "lat_off": -0.001, "lon_off": -0.005},
]


class SimAsset:
    """Simulated robotic asset with movement, battery, and task execution."""

    def __init__(self, manifest_entry):
        self.asset_id = manifest_entry["id"]
        self.asset_type = manifest_entry["type"]
        self.callsign = manifest_entry["callsign"]

        self.lat = BASE_LAT + manifest_entry["lat_off"]
        self.lon = BASE_LON + manifest_entry["lon_off"]

        if self.asset_type == "AIR":
            self.alt = random.uniform(80.0, 200.0)
            self.speed = random.uniform(8.0, 20.0)
        elif self.asset_type == "MARITIME":
            self.alt = 0.0
            self.speed = random.uniform(2.0, 6.0)
        else:
            self.alt = 0.0
            self.speed = random.uniform(1.0, 5.0)

        self.heading = random.uniform(0.0, 360.0)
        self.battery = random.uniform(75.0, 100.0)
        self.comms_dbm = random.uniform(-60.0, -30.0)
        self.autonomy_mode = 1  # 0=MANUAL, 1=ASSISTED, 2=COLLABORATIVE, 3=SWARM, 4=COGNITIVE
        self.mission_status = 0  # 0=IDLE

        # Task execution
        self.current_task = None
        self.task_progress = 0.0
        self.target_lat = None
        self.target_lon = None
        self.target_alt = None

    def assign_task(self, task_data):
        """Assign a task to this asset."""
        self.current_task = task_data
        self.mission_status = 1  # EN_ROUTE
        self.task_progress = 0.0
        self.target_lat = task_data.get("target_lat", self.lat)
        self.target_lon = task_data.get("target_lon", self.lon)
        self.target_alt = task_data.get("target_alt", self.alt)

    def tick(self):
        """Update asset state each cycle."""
        # Battery drain
        if self.mission_status in (1, 2):
            self.battery -= random.uniform(0.02, 0.08)
        else:
            self.battery -= random.uniform(0.005, 0.02)
        self.battery = max(0.0, self.battery)

        # Comms jitter
        self.comms_dbm += random.uniform(-2.0, 2.0)
        self.comms_dbm = max(-90.0, min(-20.0, self.comms_dbm))

        if self.mission_status == 0:
            # IDLE — small drift
            self.lat += random.uniform(-0.00005, 0.00005)
            self.lon += random.uniform(-0.00005, 0.00005)
            self.heading += random.uniform(-5.0, 5.0)
            self.heading %= 360.0

        elif self.mission_status == 1:
            # EN_ROUTE — move toward target
            if self.target_lat and self.target_lon:
                dlat = self.target_lat - self.lat
                dlon = self.target_lon - self.lon
                dist = math.sqrt(dlat**2 + dlon**2)

                if dist < 0.0003:
                    self.mission_status = 2  # EXECUTING
                    self.task_progress = 0.0
                else:
                    step = min(0.0003, dist)
                    self.lat += (dlat / dist) * step
                    self.lon += (dlon / dist) * step
                    self.heading = math.degrees(math.atan2(dlon, dlat)) % 360.0

        elif self.mission_status == 2:
            # EXECUTING — progress the task
            self.task_progress += random.uniform(2.0, 8.0)
            self.lat += random.uniform(-0.0001, 0.0001)
            self.lon += random.uniform(-0.0001, 0.0001)
            self.heading += random.uniform(-10.0, 10.0)
            self.heading %= 360.0

            if self.task_progress >= 100.0:
                self.mission_status = 3  # COMPLETE
                self.current_task = None
                self.task_progress = 100.0

        elif self.mission_status == 3:
            # COMPLETE — return to idle after brief pause
            self.mission_status = 0
            self.task_progress = 0.0

        # Fault simulation (rare)
        if self.battery < 10.0 and random.random() < 0.05:
            self.mission_status = 4  # FAULT

    def to_msg(self) -> AssetState:
        """Convert to ROS message."""
        msg = AssetState()
        msg.asset_id = self.asset_id
        msg.asset_type = self.asset_type
        msg.callsign = self.callsign
        msg.latitude = self.lat
        msg.longitude = self.lon
        msg.altitude_m = self.alt
        msg.heading_deg = self.heading
        msg.speed_mps = self.speed
        msg.battery_pct = self.battery
        msg.comms_signal_dbm = self.comms_dbm
        msg.autonomy_mode = self.autonomy_mode
        msg.mission_status = self.mission_status
        return msg


class PlatoonSim(Node):
    """Simulates the full 25-asset Mavrix1 Robotic Platoon."""

    def __init__(self):
        super().__init__("mos_platoon_sim")
        self.get_logger().info("=" * 60)
        self.get_logger().info("  MOS PLATOON SIMULATOR — MAVRIX-1")
        self.get_logger().info("=" * 60)

        # Create all assets
        self.assets = {}
        for entry in PLATOON_MANIFEST:
            asset = SimAsset(entry)
            self.assets[asset.asset_id] = asset

        air = sum(1 for a in self.assets.values() if a.asset_type == "AIR")
        gnd = sum(1 for a in self.assets.values() if a.asset_type == "GROUND")
        sea = sum(1 for a in self.assets.values() if a.asset_type == "MARITIME")
        self.get_logger().info(f"  Platoon: {len(self.assets)} assets")
        self.get_logger().info(f"    AIR:      {air}")
        self.get_logger().info(f"    GROUND:   {gnd}")
        self.get_logger().info(f"    MARITIME: {sea}")

        # Publishers
        self._asset_pub = self.create_publisher(AssetState, "/mos/cop/assets", 50)

        # Subscribers
        self.create_subscription(
            TaskOrder, "/mos/tasks/orders", self._on_task_order, 10
        )
        self.create_subscription(
            String, "/mos/swarm/command", self._on_swarm_command, 10
        )

        # Timers
        self.create_timer(1.0, self._tick_and_publish)
        self.create_timer(15.0, self._sitrep)

        self.get_logger().info("  Platoon simulation running. Publishing heartbeats...")
        self.get_logger().info("=" * 60)

    def _tick_and_publish(self):
        """Update all assets and publish heartbeats."""
        for asset in self.assets.values():
            asset.tick()
            self._asset_pub.publish(asset.to_msg())

    def _on_task_order(self, msg: TaskOrder):
        """Assign tasks to assets based on domain matching and availability."""
        domain = None
        description = ""
        sequence = ""
        for param in msg.parameters:
            if param.startswith("domain="):
                domain = param.split("=")[1]
            elif param.startswith("description="):
                description = param.split("=", 1)[1]
            elif param.startswith("sequence="):
                sequence = param.split("=")[1]

        if not domain:
            return

        # Find best available asset: prefer IDLE, then lowest battery drain
        best_asset = None
        for asset in self.assets.values():
            if asset.asset_type == domain and asset.mission_status == 0:
                if best_asset is None or asset.battery > best_asset.battery:
                    best_asset = asset

        # If no idle assets, find one that's executing but has high battery
        if best_asset is None:
            for asset in self.assets.values():
                if asset.asset_type == domain and asset.battery > 50.0:
                    if best_asset is None or asset.battery > best_asset.battery:
                        best_asset = asset

        if best_asset:
            best_asset.assign_task({
                "task_id": msg.task_id,
                "target_lat": best_asset.lat + random.uniform(-0.005, 0.005),
                "target_lon": best_asset.lon + random.uniform(-0.005, 0.005),
                "target_alt": best_asset.alt,
            })
            self.get_logger().info(
                f"  -> {best_asset.callsign} ({best_asset.asset_id}) "
                f"assigned [{msg.task_type}] {description}"
            )
        else:
            self.get_logger().warn(
                f"  WARNING: NO ASSET AVAILABLE for {msg.task_type} "
                f"(domain={domain}) — task queued"
            )

    def _on_swarm_command(self, msg: String):
        """Handle swarm-level commands."""
        try:
            cmd = json.loads(msg.data)
            behavior = cmd.get("behavior", "UNKNOWN")
            target_domain = cmd.get("domain", "ALL")

            self.get_logger().info(
                f"[SWARM CMD] {behavior} for domain={target_domain}"
            )

            for asset in self.assets.values():
                if target_domain == "ALL" or asset.asset_type == target_domain:
                    if behavior == "RTB":
                        asset.assign_task({
                            "task_id": "SWARM-RTB",
                            "target_lat": BASE_LAT,
                            "target_lon": BASE_LON,
                            "target_alt": asset.alt,
                        })
                    elif behavior == "HOLD":
                        asset.mission_status = 0
                        asset.current_task = None
                    elif behavior == "SCATTER":
                        asset.assign_task({
                            "task_id": "SWARM-SCATTER",
                            "target_lat": asset.lat + random.uniform(-0.01, 0.01),
                            "target_lon": asset.lon + random.uniform(-0.01, 0.01),
                            "target_alt": asset.alt,
                        })

        except json.JSONDecodeError:
            self.get_logger().error("Invalid swarm command JSON")

    def _sitrep(self):
        """Periodic situation report."""
        total = len(self.assets)
        idle = sum(1 for a in self.assets.values() if a.mission_status == 0)
        enroute = sum(1 for a in self.assets.values() if a.mission_status == 1)
        executing = sum(1 for a in self.assets.values() if a.mission_status == 2)
        complete = sum(1 for a in self.assets.values() if a.mission_status == 3)
        fault = sum(1 for a in self.assets.values() if a.mission_status == 4)
        low_batt = sum(1 for a in self.assets.values() if a.battery < 20.0)

        self.get_logger().info(
            f"[SITREP] Platoon: {total} assets | "
            f"IDLE: {idle} | EN_ROUTE: {enroute} | EXEC: {executing} | "
            f"DONE: {complete} | FAULT: {fault} | LOW_BATT: {low_batt}"
        )


def main(args=None):
    rclpy.init(args=args)
    node = PlatoonSim()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
