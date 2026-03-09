## Where AMOS Fits in the Autonomous Systems Stack

                ┌───────────────────────────────┐
                │        Applications            │
                │  Mission Packs / Analytics     │
                └───────────────────────────────┘
                              ▲
                              │
                ┌───────────────────────────────┐
                │            AMOS                │
                │  Autonomous Mission Operating  │
                │           System               │
                │  Mission Orchestration Layer   │
                └───────────────────────────────┘
                              ▲
                              │
        ┌───────────────────────────────┐
        │ Robotics Middleware           │
        │ ROS2 / PX4 / ArduPilot        │
        └───────────────────────────────┘
                              ▲
                              │
        ┌───────────────────────────────┐
        │ Hardware Platforms            │
        │ Drones / Robots / Sensors     │
        └───────────────────────────────┘

AMOS sits **above robotics middleware** and **below mission applications**.

Robotics frameworks like **ROS2 and PX4 control individual platforms**.

AMOS coordinates **missions across many autonomous systems simultaneously**.

It provides the missing layer for:

• mission orchestration  
• human-machine teaming  
• swarm coordination  
• cross-domain autonomy


docs/getting-started/AMOS_Developer_Quickstart.md