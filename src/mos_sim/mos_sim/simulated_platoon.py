#!/usr/bin/env python3
"""
MOS Simulated Platoon — Mission-Reactive
Assets respond to mission orders, move toward objectives,
change status, and obey swarm commands.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import math
import random
import time

# ── Asset Templates ───────────────────────────────────────────────
TEMPLATES = [
    # 10 AIR
    {"id": "MVRX-A01", "type": "AIR",      "callsign": "HAWK-1"},
    {"id": "MVRX-A02", "type": "AIR",      "callsign": "HAWK-2"},
    {"id": "MVRX-A03", "type": "AIR",      "callsign": "HAWK-3"},
    {"id": "MVRX-A04", "type": "AIR",      "callsign": "RAVEN-1"},
    {"id": "MVRX-A05", "type": "AIR",      "callsign": "RAVEN-2"},
    {"id": "MVRX-A06", "type": "AIR",      "callsign": "RAVEN-3"},
    {"id": "MVRX-A07", "type": "AIR",      "callsign": "TALON-1"},
    {"id": "MVRX-A08", "type": "AIR",      "callsign": "TALON-2"},
    {"id": "MVRX-A09", "type": "AIR",      "callsign": "OVERWATCH-1"},
    {"id": "MVRX-A10", "type": "AIR",      "callsign": "OVERWATCH-2"},
    # 12 GROUND
    {"id": "MVRX-G01", "type": "GROUND",   "callsign": "WARHOUND-1"},
    {"id": "MVRX-G02", "type": "GROUND",   "callsign": "WARHOUND-2"},
    {"id": "MVRX-G03", "type": "GROUND",   "callsign": "WARHOUND-3"},
    {"id": "MVRX-G04", "type": "GROUND",   "callsign": "WARHOUND-4"},
    {"id": "MVRX-G05", "type": "GROUND",   "callsign": "MULE-1"},
    {"id": "MVRX-G06", "type": "GROUND",   "callsign": "MULE-2"},
    {"id": "MVRX-G07", "type": "GROUND",   "callsign": "MULE-3"},
    {"id": "MVRX-G08", "type": "GROUND",   "callsign": "SENTRY-1"},
    {"id": "MVRX-G09", "type": "GROUND",   "callsign": "SENTRY-2"},
    {"id": "MVRX-G10", "type": "GROUND",   "callsign": "SENTRY-3"},
    {"id": "MVRX-G11", "type": "GROUND",   "callsign": "SENTRY-4"},
    {"id": "MVRX-G12", "type": "GROUND",   "callsign": "PATHFINDER-1"},
    # 3 MARITIME
    {"id": "MVRX-M01", "type": "MARITIME",  "callsign": "TRITON-1"},
    {"id": "MVRX-M02", "type": "MARITIME",  "callsign": "TRITON-2"},
    {"id": "MVRX-M03", "type": "MARITIME",  "callsign": "TRITON-3"},
]

# Status codes
IDLE     = 0
EN_ROUTE = 1
EXEC     = 2
DONE     = 3
FAULT    = 4

# Movement speeds (degrees per tick at 2 Hz)
SPEED = {
    "AIR":      0.0003,
    "GROUND":   0.00012,
    "MARITIME":  0.00015,
}


class SimulatedPlatoon(Node):

    def __init__(self):
        super().__init__('simulated_platoon')

        # Publishers
        self.heartbeat_pub = self.create_publisher(String, '/mos/heartbeat', 10)

        # Subscribers — listen for mission & swarm commands
        self.create_subscription(String, '/mos/mission_command', self._on_mission, 10)
        self.create_subscription(String, '/mos/swarm_command', self._on_swarm, 10)
        self.create_subscription(String, '/mos/autonomy_command', self._on_autonomy, 10)

        # Pick a random center for deployment
        self.base_lat = 33.9968 + random.uniform(-0.005, 0.005)
        self.base_lon = -117.999 + random.uniform(-0.005, 0.005)

        # Initialize assets
        self.assets = {}
        for i, t in enumerate(TEMPLATES):
            angle = (2 * math.pi * i) / len(TEMPLATES)
            spread = random.uniform(0.002, 0.008)
            self.assets[t["id"]] = {
                "asset_id":        t["id"],
                "asset_type":      t["type"],
                "callsign":        t["callsign"],
                "lat":             self.base_lat + spread * math.sin(angle),
                "lon":             self.base_lon + spread * math.cos(angle),
                "alt":             random.uniform(50, 300) if t["type"] == "AIR" else 0.0,
                "heading":         random.uniform(0, 360),
                "speed":           0.0,
                "battery":         random.uniform(70, 100),
                "comms":           round(random.uniform(-50, -80), 1),
                "autonomy_mode":   "ASSISTED",
                "mission_status":  IDLE,
                # Movement state
                "target_lat":      None,
                "target_lon":      None,
                "assigned_mission": None,
                "behavior":        "NORMAL",  # NORMAL, HOLD, RTB, SCATTER
                "exec_timer":      0,
            }

        # Tick at 2 Hz
        self.create_timer(0.5, self._tick)
        self.get_logger().info(
            f'[MOS SIM] Platoon deployed: {len(self.assets)} assets near '
            f'({self.base_lat:.4f}, {self.base_lon:.4f})'
        )

    # ── Mission Command Handler ───────────────────────────────────
    def _on_mission(self, msg):
        try:
            data = json.loads(msg.data)
        except Exception:
            return

        mtype = data.get('mission_type', '')
        mission_id = data.get('mission_id', 'UNK')

        # Generate objective point offset from base
        obj_lat = self.base_lat + random.uniform(-0.01, 0.01)
        obj_lon = self.base_lon + random.uniform(-0.01, 0.01)

        # Select which assets to assign based on mission type
        assigned = self._select_assets(mtype)

        for aid in assigned:
            a = self.assets[aid]
            a["target_lat"] = obj_lat + random.uniform(-0.002, 0.002)
            a["target_lon"] = obj_lon + random.uniform(-0.002, 0.002)
            a["assigned_mission"] = mission_id
            a["mission_status"] = EN_ROUTE
            a["behavior"] = "NORMAL"
            a["exec_timer"] = 0
            a["speed"] = SPEED[a["asset_type"]]

        self.get_logger().info(
            f'[MOS SIM] Mission {mission_id} ({mtype}): '
            f'{len(assigned)} assets assigned, objective ({obj_lat:.4f}, {obj_lon:.4f})'
        )

    def _select_assets(self, mtype):
        """Pick idle assets appropriate for mission type."""
        idle = [a for a in self.assets.values() if a["mission_status"] == IDLE]

        if mtype == 'ISR':
            # Prefer AIR for ISR
            air = [a for a in idle if a["asset_type"] == "AIR"]
            gnd = [a for a in idle if a["asset_type"] == "GROUND"]
            picks = air[:3] + gnd[:1]
        elif mtype == 'SECURITY':
            gnd = [a for a in idle if a["asset_type"] == "GROUND"]
            air = [a for a in idle if a["asset_type"] == "AIR"]
            picks = gnd[:4] + air[:2]
        elif mtype == 'PRECISION_EFFECTS':
            air = [a for a in idle if a["asset_type"] == "AIR"]
            gnd = [a for a in idle if a["asset_type"] == "GROUND"]
            picks = air[:2] + gnd[:2]
        elif mtype == 'LOGISTICS':
            gnd = [a for a in idle if a["asset_type"] == "GROUND"]
            picks = gnd[:3]
        elif mtype == 'SAR':
            air = [a for a in idle if a["asset_type"] == "AIR"]
            gnd = [a for a in idle if a["asset_type"] == "GROUND"]
            sea = [a for a in idle if a["asset_type"] == "MARITIME"]
            picks = air[:2] + gnd[:2] + sea[:1]
        elif mtype == 'EW_SIGINT':
            air = [a for a in idle if a["asset_type"] == "AIR"]
            gnd = [a for a in idle if a["asset_type"] == "GROUND"]
            picks = air[:2] + gnd[:1]
        else:
            picks = idle[:4]

        # If not enough idle, grab some from done
        if len(picks) < 2:
            done = [a for a in self.assets.values()
                    if a["mission_status"] == DONE]
            picks += done[:4 - len(picks)]

        return [p["asset_id"] for p in picks]

    # ── Swarm Command Handler ─────────────────────────────────────
    def _on_swarm(self, msg):
        try:
            data = json.loads(msg.data)
        except Exception:
            return

        behavior = data.get('behavior', 'HOLD')
        self.get_logger().info(f'[MOS SIM] Swarm command: {behavior}')

        for a in self.assets.values():
            a["behavior"] = behavior

            if behavior == "RTB":
                a["target_lat"] = self.base_lat + random.uniform(-0.001, 0.001)
                a["target_lon"] = self.base_lon + random.uniform(-0.001, 0.001)
                a["mission_status"] = EN_ROUTE
                a["speed"] = SPEED[a["asset_type"]]

            elif behavior == "HOLD":
                a["target_lat"] = None
                a["target_lon"] = None
                a["speed"] = 0.0

            elif behavior == "SCATTER":
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(0.008, 0.015)
                a["target_lat"] = a["lat"] + dist * math.sin(angle)
                a["target_lon"] = a["lon"] + dist * math.cos(angle)
                a["mission_status"] = EN_ROUTE
                a["speed"] = SPEED[a["asset_type"]] * 1.5

    # ── Autonomy Command Handler ──────────────────────────────────
    def _on_autonomy(self, msg):
        try:
            data = json.loads(msg.data)
        except Exception:
            return
        names = ['MANUAL', 'ASSISTED', 'COLLABORATIVE', 'SWARM', 'COGNITIVE']
        level = data.get('target_level', 1)
        mode = names[level] if level < len(names) else 'ASSISTED'
        for a in self.assets.values():
            a["autonomy_mode"] = mode
        self.get_logger().info(f'[MOS SIM] Autonomy set to {mode}')

    # ── Main Tick — move assets, update status ────────────────────
    def _tick(self):
        for a in self.assets.values():
            # Battery drain
            a["battery"] = max(5.0, a["battery"] - random.uniform(0.01, 0.03))
            a["comms"] = round(random.uniform(-50, -80), 1)

            # ── HOLD behavior: no movement ──
            if a["behavior"] == "HOLD":
                continue

            # ── Movement toward target ──
            if a["target_lat"] is not None and a["mission_status"] in (EN_ROUTE, EXEC):
                dlat = a["target_lat"] - a["lat"]
                dlon = a["target_lon"] - a["lon"]
                dist = math.sqrt(dlat**2 + dlon**2)

                spd = a.get("speed", SPEED[a["asset_type"]])

                if dist < 0.0003:
                    # Arrived
                    if a["mission_status"] == EN_ROUTE:
                        a["mission_status"] = EXEC
                        a["exec_timer"] = random.randint(20, 60)
                        a["speed"] = 0.0
                    elif a["behavior"] == "RTB":
                        a["mission_status"] = IDLE
                        a["target_lat"] = None
                        a["target_lon"] = None
                        a["assigned_mission"] = None
                        a["behavior"] = "NORMAL"
                        a["speed"] = 0.0
                    elif a["behavior"] == "SCATTER":
                        a["behavior"] = "NORMAL"
                        a["mission_status"] = IDLE
                        a["target_lat"] = None
                        a["target_lon"] = None
                        a["speed"] = 0.0
                else:
                    # Move toward target
                    a["heading"] = math.degrees(math.atan2(dlon, dlat)) % 360
                    a["lat"] += (dlat / dist) * spd
                    a["lon"] += (dlon / dist) * spd

            # ── EXEC countdown → DONE ──
            if a["mission_status"] == EXEC:
                a["exec_timer"] -= 1
                # Small patrol movement while executing
                a["lat"] += random.uniform(-0.00005, 0.00005)
                a["lon"] += random.uniform(-0.00005, 0.00005)
                if a["exec_timer"] <= 0:
                    a["mission_status"] = DONE
                    a["target_lat"] = None
                    a["target_lon"] = None

            # ── DONE assets drift back to IDLE after a bit ──
            if a["mission_status"] == DONE:
                if random.random() < 0.02:
                    a["mission_status"] = IDLE
                    a["assigned_mission"] = None

            # ── IDLE drift ──
            if a["mission_status"] == IDLE and a["behavior"] == "NORMAL":
                a["lat"] += random.uniform(-0.00003, 0.00003)
                a["lon"] += random.uniform(-0.00003, 0.00003)

            # Publish heartbeat
            self.heartbeat_pub.publish(String(data=json.dumps(a)))


def main(args=None):
    rclpy.init(args=args)
    node = SimulatedPlatoon()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
