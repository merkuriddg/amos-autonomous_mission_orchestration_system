from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="mos_core",
            executable="asset_registry",
            name="mos_asset_registry",
            output="screen",
            parameters=[{"heartbeat_timeout_sec": 10.0}],
        ),
        Node(
            package="mos_core",
            executable="autonomy_manager",
            name="mos_autonomy_manager",
            output="screen",
        ),
        Node(
            package="mos_mission_planner",
            executable="mission_planner",
            name="mos_mission_planner",
            output="screen",
        ),
        Node(
            package="mos_swarm",
            executable="swarm_orchestrator",
            name="mos_swarm_orchestrator",
            output="screen",
        ),
    ])
