#!/usr/bin/env python3
"""AMOS Sprint 3 — Sensor-to-Mission Closed Loop Orchestrator

Connects all autonomy subsystems into one continuous cycle:

  sensor_fusion.tick()           — correlate detections into fused tracks
       ↓
  mission_pipeline.tick()        — evaluate trigger rules, spawn tasks
       ↓
  task_allocator.allocate()      — auction-based assignment of spawned tasks
       ↓
  swarm_behavior_mgr.evaluate_sensor_triggers()  — auto-assign swarm behaviors
       ↓
  swarm_behavior_mgr.tick()      — execute active swarm behaviors
       ↓
  mission_pipeline.bt_registry.tick_all()  — tick all active behavior trees
       ↓
  events aggregated + COP generated

Also provides the Common Operating Picture (COP) — a unified snapshot of:
  - Fused tracks with kill chain phase
  - Asset positions and status
  - Sensor coverage footprints
  - Active tasks and missions
  - Active behavior trees
  - Active swarm behaviors with coverage progress
  - Pipeline trigger rule status
  - Event timeline
"""

import time
import threading
from datetime import datetime, timezone


class ClosedLoopOrchestrator:
    """Single tick() drives the full autonomy cycle."""

    def __init__(self, sensor_fusion, mission_pipeline, task_allocator,
                 swarm_behavior_mgr, swarm_intel=None):
        """
        Args:
            sensor_fusion:      SensorFusionEngine instance
            mission_pipeline:   MissionPipeline instance (has bt_registry)
            task_allocator:     TaskAllocator instance
            swarm_behavior_mgr: SwarmBehaviorManager instance
            swarm_intel:        SwarmIntelligence instance (optional)
        """
        self.sensor_fusion = sensor_fusion
        self.mission_pipeline = mission_pipeline
        self.task_allocator = task_allocator
        self.swarm_behavior_mgr = swarm_behavior_mgr
        self.swarm_intel = swarm_intel

        self._lock = threading.Lock()
        self.tick_count = 0
        self.last_tick = 0
        self.events_history = []    # rolling window of recent events
        self.stats = {
            "ticks": 0,
            "fusion_events": 0,
            "pipeline_events": 0,
            "task_events": 0,
            "swarm_trigger_events": 0,
            "swarm_behavior_events": 0,
            "bt_ticks": 0,
            "total_events": 0,
        }

    def tick(self, assets, threats, dt=1.0, blackboard=None):
        """Execute one full closed-loop cycle.

        Args:
            assets:     dict of asset_id → asset dict (position, sensors, etc.)
            threats:    dict of threat_id → threat dict
            dt:         time delta for physics
            blackboard: shared context dict (ROE posture, comms health, etc.)

        Returns:
            dict with all events from each subsystem plus summary
        """
        blackboard = blackboard or {}
        now = time.time()
        all_events = []

        with self._lock:
            self.tick_count += 1
            self.stats["ticks"] += 1

            # ── Step 1: Sensor Fusion ──────────────────────
            # Correlate threats into fused tracks
            fusion_events = self.sensor_fusion.tick(assets, threats, dt)
            all_events.extend(fusion_events)
            self.stats["fusion_events"] += len(fusion_events)

            # Build fused track list for downstream consumers
            fused_tracks_dict = self.sensor_fusion.get_tracks()
            fused_tracks_list = list(fused_tracks_dict.values())

            # Inject into blackboard for BTs and swarm behaviors
            blackboard["fused_tracks"] = fused_tracks_dict
            blackboard["fused_tracks_list"] = fused_tracks_list
            blackboard["track_count"] = len(fused_tracks_list)
            blackboard.setdefault("comms_health", 0.9)
            blackboard.setdefault("roe_posture", "weapons_tight")

            # ── Step 2: Mission Pipeline Trigger Rules ─────
            # Evaluate fused tracks against trigger rules, spawn tasks
            pipeline_events = self.mission_pipeline.tick(fused_tracks_list, blackboard)
            all_events.extend(pipeline_events)
            self.stats["pipeline_events"] += len(pipeline_events)

            # ── Step 3: Task Allocator ─────────────────────
            # Create tasks for any new spawned items from pipeline
            for ev in pipeline_events:
                if ev.get("type") == "RULE_FIRED":
                    action = ev.get("action", {})
                    task_type = action.get("task_type", "ISR")
                    location = action.get("location", {})
                    priority = action.get("priority", 5)
                    self.task_allocator.create_task(
                        task_type,
                        location=location,
                        priority=priority,
                        required_sensors=action.get("required_sensors"),
                        description=f"Auto-spawned from trigger: {ev.get('rule_name', '?')}",
                    )

            # Run allocation + tick
            task_events = self.task_allocator.tick(assets, dt)
            all_events.extend(task_events)
            self.stats["task_events"] += len(task_events)

            # ── Step 4: Swarm Behavior Sensor Triggers ─────
            # Build available swarms from swarm_intel if present
            available_swarms = {}
            if self.swarm_intel:
                for sid, sw in self.swarm_intel.swarms.items():
                    if sw.get("status") == "active":
                        available_swarms[sid] = {"asset_ids": sw["assets"]}

            if available_swarms and fused_tracks_list:
                trigger_spawned = self.swarm_behavior_mgr.evaluate_sensor_triggers(
                    fused_tracks_list, available_swarms)
                all_events.extend([
                    {"type": "SWARM_BEHAVIOR_TRIGGERED", **sb}
                    for sb in trigger_spawned
                ])
                self.stats["swarm_trigger_events"] += len(trigger_spawned)

            # ── Step 5: Tick Swarm Behaviors ───────────────
            swarm_events = self.swarm_behavior_mgr.tick(assets, blackboard, dt)
            all_events.extend(swarm_events)
            self.stats["swarm_behavior_events"] += len(swarm_events)

            # ── Step 6: Tick All Behavior Trees ────────────
            bt_results = self.mission_pipeline.bt_registry.tick_all(blackboard)
            self.stats["bt_ticks"] += len(bt_results)
            for r in bt_results:
                all_events.append({
                    "type": "BT_TICK",
                    "bt_id": r.get("id", ""),
                    "bt_name": r.get("name", ""),
                    "status": r.get("status", ""),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            # ── Bookkeeping ────────────────────────────────
            self.stats["total_events"] += len(all_events)
            self.last_tick = now

            # Add timestamp to events that don't have one
            ts = datetime.now(timezone.utc).isoformat()
            for ev in all_events:
                ev.setdefault("timestamp", ts)
                ev.setdefault("tick", self.tick_count)

            # Rolling event history (last 500)
            self.events_history.extend(all_events)
            if len(self.events_history) > 500:
                self.events_history = self.events_history[-500:]

        return {
            "tick": self.tick_count,
            "events": all_events,
            "event_count": len(all_events),
            "summary": {
                "fused_tracks": len(fused_tracks_list),
                "active_tasks": len(self.task_allocator.get_tasks("ASSIGNED")) +
                                len(self.task_allocator.get_tasks("EN_ROUTE")) +
                                len(self.task_allocator.get_tasks("EXECUTING")),
                "active_bts": len(self.mission_pipeline.bt_registry.list_all()),
                "active_swarm_behaviors": len(self.swarm_behavior_mgr.list_active()),
                "pipeline_rules": len(self.mission_pipeline.rules),
            },
            "timestamp": ts,
        }

    def cop(self, assets, threats):
        """Generate the Common Operating Picture — unified snapshot of everything.

        Returns a dict with all operational layers merged into one view.
        """
        # Fused tracks
        fused_tracks = self.sensor_fusion.get_tracks()

        # Sensor coverage
        coverage = self.sensor_fusion.get_coverage()
        coverage_gaps = self.sensor_fusion.get_coverage_gaps()

        # Kill chain summary
        kill_chain = self.sensor_fusion.get_kill_chain_summary()

        # Assets (safe copy of positions + status)
        asset_layer = {}
        for aid, a in assets.items():
            pos = a.get("position", a)
            asset_layer[aid] = {
                "id": aid,
                "type": a.get("type", "unknown"),
                "domain": a.get("domain", "unknown"),
                "role": a.get("role", ""),
                "lat": pos.get("lat", 0),
                "lng": pos.get("lng", 0),
                "status": a.get("status", "unknown"),
                "heading_deg": a.get("heading_deg", 0),
                "speed_kts": a.get("speed_kts", 0),
                "battery_pct": a.get("health", {}).get("battery_pct", 0),
                "sensors": a.get("sensors", []),
            }

        # Threats
        threat_layer = {}
        for tid, t in threats.items():
            threat_layer[tid] = {
                "id": tid,
                "type": t.get("type", "unknown"),
                "lat": t.get("lat", 0),
                "lng": t.get("lng", 0),
                "neutralized": t.get("neutralized", False),
                "fused_track_id": None,
            }
        # Cross-reference threats with fused tracks
        for trk_id, trk in fused_tracks.items():
            assoc = trk.get("associated_threat_id")
            if assoc and assoc in threat_layer:
                threat_layer[assoc]["fused_track_id"] = trk_id

        # Active tasks
        active_tasks = [
            t for t in self.task_allocator.get_tasks()
            if t["status"] in ("PENDING", "ASSIGNED", "EN_ROUTE", "EXECUTING")
        ]

        # Active missions
        active_missions = [
            m for m in self.task_allocator.get_missions()
            if m.get("status") == "ACTIVE"
        ]

        # Behavior trees
        active_bts = self.mission_pipeline.bt_registry.list_all()

        # Swarm behaviors
        active_swarm_behaviors = self.swarm_behavior_mgr.list_active()

        # Pipeline rules
        pipeline_rules = self.mission_pipeline.get_rules()

        # Swarm behavior triggers
        swarm_triggers = self.swarm_behavior_mgr.get_triggers()

        # Recent events timeline (last 50)
        timeline = self.events_history[-50:]

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tick": self.tick_count,
            "layers": {
                "assets": asset_layer,
                "threats": threat_layer,
                "fused_tracks": fused_tracks,
                "coverage": {
                    "footprints": coverage,
                    "gaps": coverage_gaps[:50],
                    "gap_count": len(coverage_gaps),
                },
                "kill_chain": kill_chain,
            },
            "operations": {
                "active_tasks": active_tasks,
                "active_missions": active_missions,
                "behavior_trees": active_bts,
                "swarm_behaviors": active_swarm_behaviors,
            },
            "autonomy": {
                "pipeline_rules": pipeline_rules,
                "swarm_triggers": swarm_triggers,
                "pipeline_stats": self.mission_pipeline.summary(),
                "swarm_stats": self.swarm_behavior_mgr.summary(),
                "task_stats": self.task_allocator.get_stats(),
            },
            "timeline": timeline,
            "stats": dict(self.stats),
            "counts": {
                "assets": len(asset_layer),
                "threats": len(threat_layer),
                "fused_tracks": len(fused_tracks),
                "active_tasks": len(active_tasks),
                "active_missions": len(active_missions),
                "active_bts": len(active_bts),
                "active_swarm_behaviors": len(active_swarm_behaviors),
                "coverage_gaps": len(coverage_gaps),
            },
        }

    def summary(self):
        """Quick status for dashboard."""
        return {
            "tick_count": self.tick_count,
            "last_tick": self.last_tick,
            "stats": dict(self.stats),
            "recent_events": len(self.events_history),
        }
