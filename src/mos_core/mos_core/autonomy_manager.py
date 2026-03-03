"""
MOS Autonomy Mode Manager
Implements the 5-tier autonomy state machine from the Mavrix1 RP concept:
  MANUAL → ASSISTED → COLLABORATIVE → SWARM → COGNITIVE

Transitions are governed by HPL authorization, mission context, and
comms health. Lethal effects always require human approval regardless
of autonomy level.
"""

import rclpy
from rclpy.node import Node
from enum import IntEnum
from std_msgs.msg import String
import json


class AutonomyLevel(IntEnum):
    MANUAL = 0          # Direct teleoperation
    ASSISTED = 1        # Waypoint execution with obstacle avoidance
    COLLABORATIVE = 2   # Multi-asset coordinated tasking
    SWARM = 3           # Emergent swarm behaviors
    COGNITIVE = 4       # Future: predictive autonomous ops


class AutonomyManager(Node):
    """
    Manages autonomy level transitions for the entire platoon and
    individual assets. Enforces human-on-the-loop constraints.
    """

    # Transitions that require explicit HPL authorization
    REQUIRES_HPL_AUTH = {
        (AutonomyLevel.COLLABORATIVE, AutonomyLevel.SWARM),
        (AutonomyLevel.SWARM, AutonomyLevel.COGNITIVE),
    }

    def __init__(self):
        super().__init__("mos_autonomy_manager")
        self.get_logger().info("=== MOS Autonomy Manager Initializing ===")

        # Platoon-wide default autonomy level
        self._platoon_level = AutonomyLevel.ASSISTED

        # Per-asset overrides: asset_id -> AutonomyLevel
        self._asset_overrides: dict[str, AutonomyLevel] = {}

        # HPL authorization queue
        self._pending_auth: list[dict] = []

        # Listen for autonomy change requests
        self.create_subscription(
            String,
            "/mos/autonomy/request",
            self._on_autonomy_request,
            10,
        )

        # Listen for HPL authorization responses
        self.create_subscription(
            String,
            "/mos/autonomy/hpl_auth",
            self._on_hpl_auth,
            10,
        )

        # Publish current autonomy state
        self._state_pub = self.create_publisher(
            String, "/mos/autonomy/state", 10
        )
        self.create_timer(1.0, self._publish_state)

        self.get_logger().info(
            f"Autonomy Manager online. Platoon level: "
            f"{AutonomyLevel(self._platoon_level).name}"
        )

    def _on_autonomy_request(self, msg: String):
        """
        Handle autonomy level change request.
        Expected JSON: {"scope": "platoon"|"asset", "asset_id": "...",
                        "target_level": int, "requestor": "HPL"|"ASC"}
        """
        try:
            req = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().error("Invalid autonomy request JSON")
            return

        target = AutonomyLevel(req["target_level"])
        current = self._platoon_level

        if req.get("scope") == "asset":
            current = self._asset_overrides.get(
                req["asset_id"], self._platoon_level
            )

        transition = (current, target)

        if transition in self.REQUIRES_HPL_AUTH:
            self.get_logger().warn(
                f"[AUTONOMY] Transition {current.name} → {target.name} "
                f"requires HPL authorization. Queuing."
            )
            self._pending_auth.append(req)
            return

        self._apply_transition(req, target)

    def _on_hpl_auth(self, msg: String):
        """HPL approves or denies a queued transition."""
        try:
            auth = json.loads(msg.data)
            # auth = {"approved": true/false, "request_index": int}
        except json.JSONDecodeError:
            return

        if auth.get("approved") and self._pending_auth:
            idx = auth.get("request_index", 0)
            if idx < len(self._pending_auth):
                req = self._pending_auth.pop(idx)
                target = AutonomyLevel(req["target_level"])
                self._apply_transition(req, target)
                self.get_logger().info(
                    f"[AUTONOMY] HPL AUTHORIZED transition to {target.name}"
                )

    def _apply_transition(self, req: dict, target: AutonomyLevel):
        if req.get("scope") == "asset":
            self._asset_overrides[req["asset_id"]] = target
            self.get_logger().info(
                f"[AUTONOMY] Asset {req['asset_id']} → {target.name}"
            )
        else:
            self._platoon_level = target
            self.get_logger().info(
                f"[AUTONOMY] PLATOON → {target.name}"
            )

    def _publish_state(self):
        state = {
            "platoon_level": self._platoon_level,
            "platoon_level_name": AutonomyLevel(self._platoon_level).name,
            "asset_overrides": {
                k: v.name for k, v in self._asset_overrides.items()
            },
            "pending_authorizations": len(self._pending_auth),
        }
        msg = String()
        msg.data = json.dumps(state)
        self._state_pub.publish(msg)

    def is_lethal_authorized(self) -> bool:
        """Lethal effects ALWAYS require HPL in the loop — never autonomous."""
        return False  # Must go through separate engagement authorization flow


def main(args=None):
    rclpy.init(args=args)
    node = AutonomyManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
