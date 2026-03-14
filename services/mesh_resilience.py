#!/usr/bin/env python3
"""AMOS Sprint 5 — Mesh Resilience

Three capabilities that let the platoon keep fighting when comms degrade:

1. **DisconnectedOpsManager** — Caches each asset's last-known mission intent
   (task, behavior, waypoint). When an asset loses connectivity, it continues
   executing that intent autonomously. On reconnect, AMOS reconciles the
   diverged states.

2. **AutoRelayAssigner** — Monitors mesh link quality. When connectivity
   between two nodes drops below threshold, designates the best-positioned
   idle asset as a RELAY node to bridge the gap.

3. **ReconnectionSync** — Queues commands/events issued while an asset was
   disconnected. On reconnect, replays the queue in order so the asset
   catches up to the current mission state.

All three are orchestrated by MeshResilienceOrchestrator, which wires into
the existing MeshNetwork and TaskAllocator.
"""

import copy
import math
import time
import uuid
import threading
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════
#  DISCONNECTED OPS MANAGER
# ═══════════════════════════════════════════════════════════

class DisconnectedOpsManager:
    """Manages autonomous operation when assets lose connectivity.

    Caches the last-known intent for every asset so disconnected nodes
    can continue their mission without C2 guidance.
    """

    # Intent types that an asset might be executing
    INTENT_TYPES = ("TASK", "BEHAVIOR", "WAYPOINT", "PATROL", "RTB", "HOLD")

    def __init__(self):
        self._lock = threading.Lock()
        # asset_id → {intent_type, intent_data, cached_at, ttl_sec}
        self.intent_cache = {}
        # asset_id → {disconnected_at, last_position, reason, autonomous_mode}
        self.disconnected_assets = {}
        # History of disconnect/reconnect events
        self.event_log = []
        self.stats = {
            "intents_cached": 0,
            "disconnects": 0,
            "reconnects": 0,
            "autonomous_ticks": 0,
        }

    def cache_intent(self, asset_id, intent_type, intent_data, ttl_sec=300):
        """Cache the current mission intent for an asset.

        Called every tick for every connected asset so we always have a
        recent snapshot of what each asset was doing.

        Args:
            asset_id:    Asset identifier
            intent_type: One of INTENT_TYPES
            intent_data: Dict with task/behavior/waypoint details
            ttl_sec:     How long the intent remains valid (default 5 min)
        """
        with self._lock:
            self.intent_cache[asset_id] = {
                "asset_id": asset_id,
                "intent_type": intent_type,
                "intent_data": copy.deepcopy(intent_data),
                "cached_at": time.time(),
                "ttl_sec": ttl_sec,
            }
            self.stats["intents_cached"] += 1

    def get_intent(self, asset_id):
        """Retrieve the cached intent for an asset (or None if expired)."""
        entry = self.intent_cache.get(asset_id)
        if not entry:
            return None
        age = time.time() - entry["cached_at"]
        if age > entry["ttl_sec"]:
            return None  # stale
        return dict(entry)

    def mark_disconnected(self, asset_id, position=None, reason="comms_lost"):
        """Mark an asset as disconnected — it will operate autonomously.

        Args:
            asset_id: Asset identifier
            position: Last known {lat, lng}
            reason:   Why disconnected (comms_lost, jammed, out_of_range)
        """
        with self._lock:
            self.disconnected_assets[asset_id] = {
                "asset_id": asset_id,
                "disconnected_at": time.time(),
                "last_position": position or {},
                "reason": reason,
                "autonomous_mode": True,
                "intent": self.get_intent(asset_id),
                "ticks_autonomous": 0,
            }
            self.stats["disconnects"] += 1
            self._log("DISCONNECT", asset_id,
                      f"Asset disconnected ({reason}), switching to autonomous mode")

    def mark_reconnected(self, asset_id):
        """Mark an asset as reconnected — returns disconnect summary.

        Returns:
            dict with disconnect duration, autonomous ticks, and intent used
        """
        with self._lock:
            entry = self.disconnected_assets.pop(asset_id, None)
            if not entry:
                return {"error": f"Asset {asset_id} was not disconnected"}
            duration = time.time() - entry["disconnected_at"]
            self.stats["reconnects"] += 1
            self._log("RECONNECT", asset_id,
                      f"Reconnected after {duration:.1f}s, "
                      f"{entry['ticks_autonomous']} autonomous ticks")
            return {
                "asset_id": asset_id,
                "duration_sec": round(duration, 1),
                "ticks_autonomous": entry["ticks_autonomous"],
                "intent_used": (entry.get("intent") or {}).get("intent_type", "NONE"),
                "reason": entry["reason"],
            }

    def tick_autonomous(self, asset_id, assets):
        """Simulate one autonomous tick for a disconnected asset.

        The asset continues executing its cached intent — moves toward
        waypoint, continues patrol pattern, or holds position.

        Args:
            asset_id: Disconnected asset
            assets:   Master asset dict (we update position in place)

        Returns:
            list of events generated
        """
        events = []
        with self._lock:
            entry = self.disconnected_assets.get(asset_id)
            if not entry:
                return events
            entry["ticks_autonomous"] += 1
            self.stats["autonomous_ticks"] += 1

            asset = assets.get(asset_id)
            if not asset:
                return events

            intent = entry.get("intent")
            if not intent:
                # No cached intent — hold position
                events.append({
                    "type": "AUTONOMOUS_HOLD",
                    "asset_id": asset_id,
                    "reason": "no_cached_intent",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return events

            itype = intent.get("intent_type", "HOLD")
            idata = intent.get("intent_data", {})

            if itype == "WAYPOINT":
                # Continue toward cached waypoint
                target_lat = idata.get("lat", 0)
                target_lng = idata.get("lng", 0)
                pos = asset.get("position", asset)
                speed = 0.0005  # ~55m per tick
                dlat = target_lat - pos.get("lat", 0)
                dlng = target_lng - pos.get("lng", 0)
                dist = math.sqrt(dlat ** 2 + dlng ** 2)
                if dist > speed:
                    pos["lat"] = pos.get("lat", 0) + (dlat / dist) * speed
                    pos["lng"] = pos.get("lng", 0) + (dlng / dist) * speed
                events.append({
                    "type": "AUTONOMOUS_NAVIGATE",
                    "asset_id": asset_id,
                    "target": {"lat": target_lat, "lng": target_lng},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            elif itype == "PATROL":
                # Continue patrol pattern (orbit around cached center)
                center_lat = idata.get("center_lat", 0)
                center_lng = idata.get("center_lng", 0)
                radius = idata.get("radius_deg", 0.005)
                angle = (entry["ticks_autonomous"] * 0.1) % (2 * math.pi)
                pos = asset.get("position", asset)
                target_lat = center_lat + radius * math.cos(angle)
                target_lng = center_lng + radius * math.sin(angle)
                speed = 0.0003
                dlat = target_lat - pos.get("lat", 0)
                dlng = target_lng - pos.get("lng", 0)
                dist = math.sqrt(dlat ** 2 + dlng ** 2)
                if dist > speed:
                    pos["lat"] = pos.get("lat", 0) + (dlat / dist) * speed
                    pos["lng"] = pos.get("lng", 0) + (dlng / dist) * speed
                events.append({
                    "type": "AUTONOMOUS_PATROL",
                    "asset_id": asset_id,
                    "pattern": "orbit",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            elif itype == "RTB":
                # Return to base
                base_lat = idata.get("base_lat", 0)
                base_lng = idata.get("base_lng", 0)
                pos = asset.get("position", asset)
                speed = 0.001  # faster for RTB
                dlat = base_lat - pos.get("lat", 0)
                dlng = base_lng - pos.get("lng", 0)
                dist = math.sqrt(dlat ** 2 + dlng ** 2)
                if dist > speed:
                    pos["lat"] = pos.get("lat", 0) + (dlat / dist) * speed
                    pos["lng"] = pos.get("lng", 0) + (dlng / dist) * speed
                events.append({
                    "type": "AUTONOMOUS_RTB",
                    "asset_id": asset_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            else:
                # HOLD, TASK, BEHAVIOR — hold position
                events.append({
                    "type": "AUTONOMOUS_HOLD",
                    "asset_id": asset_id,
                    "intent_type": itype,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        return events

    def is_disconnected(self, asset_id):
        """Check if an asset is currently disconnected."""
        return asset_id in self.disconnected_assets

    def list_disconnected(self):
        """Return list of all disconnected assets with details."""
        return [
            {
                "asset_id": k,
                "disconnected_at": datetime.fromtimestamp(
                    v["disconnected_at"], tz=timezone.utc).isoformat(),
                "duration_sec": round(time.time() - v["disconnected_at"], 1),
                "reason": v["reason"],
                "ticks_autonomous": v["ticks_autonomous"],
                "intent_type": (v.get("intent") or {}).get("intent_type", "NONE"),
                "last_position": v.get("last_position", {}),
            }
            for k, v in self.disconnected_assets.items()
        ]

    def summary(self):
        """Quick status."""
        return {
            "cached_intents": len(self.intent_cache),
            "disconnected_count": len(self.disconnected_assets),
            "stats": dict(self.stats),
        }

    def _log(self, event_type, asset_id, detail):
        self.event_log.append({
            "type": event_type,
            "asset_id": asset_id,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self.event_log) > 200:
            self.event_log = self.event_log[-200:]


# ═══════════════════════════════════════════════════════════
#  AUTO RELAY ASSIGNER
# ═══════════════════════════════════════════════════════════

class AutoRelayAssigner:
    """Monitors mesh connectivity and auto-assigns relay nodes.

    When link quality between two nodes drops below a threshold,
    finds the best-positioned idle asset and designates it as a
    communication relay to bridge the gap.
    """

    def __init__(self, mesh_network, swarm_behavior_mgr):
        self.mesh = mesh_network
        self.swarm_mgr = swarm_behavior_mgr
        self._lock = threading.Lock()

        # Config
        self.quality_threshold = 0.3   # below this → assign relay
        self.min_quality_target = 0.6  # target quality for relay position
        self.enabled = True

        # State
        self.active_relays = {}  # relay_id → {asset_id, bridging, assigned_at}
        self.event_log = []
        self.stats = {
            "relays_assigned": 0,
            "relays_released": 0,
            "evaluations": 0,
        }

    def evaluate(self, assets):
        """Check mesh links and assign relays where needed.

        Args:
            assets: dict of asset_id → asset dict

        Returns:
            list of relay assignment events
        """
        if not self.enabled:
            return []

        events = []
        with self._lock:
            self.stats["evaluations"] += 1

            # Find degraded links
            degraded = []
            for lk, link in self.mesh.links.items():
                if link["quality"] < self.quality_threshold:
                    degraded.append(link)

            # Find disconnected node pairs (nodes with no connections)
            for nid, node in self.mesh.nodes.items():
                if not node["connections"] and node["status"] == "operational":
                    degraded.append({
                        "from": nid,
                        "to": "_HQ",  # virtual HQ node
                        "quality": 0.0,
                        "distance_km": 999,
                    })

            for link in degraded:
                src = link["from"]
                dst = link["to"]
                bridge_key = f"{src}<>{dst}"

                # Skip if we already have a relay for this pair
                if any(r["bridging"] == bridge_key for r in self.active_relays.values()):
                    continue

                # Find best candidate relay asset
                candidate = self._find_relay_candidate(assets, src, dst)
                if candidate:
                    relay_id = f"RELAY-{uuid.uuid4().hex[:6]}"
                    self.active_relays[relay_id] = {
                        "relay_id": relay_id,
                        "asset_id": candidate["id"],
                        "bridging": bridge_key,
                        "from_node": src,
                        "to_node": dst,
                        "assigned_at": time.time(),
                        "target_position": candidate["target_position"],
                    }
                    self.stats["relays_assigned"] += 1

                    # Assign RELAY_MESH behavior if possible
                    endpoints = []
                    src_node = self.mesh.nodes.get(src)
                    dst_node = self.mesh.nodes.get(dst)
                    if src_node:
                        endpoints.append({
                            "lat": src_node["lat"], "lng": src_node["lng"], "id": src,
                        })
                    if dst_node:
                        endpoints.append({
                            "lat": dst_node["lat"], "lng": dst_node["lng"], "id": dst,
                        })

                    if len(endpoints) >= 2:
                        self.swarm_mgr.assign_behavior(
                            "RELAY_MESH",
                            f"AUTO-RELAY-{relay_id}",
                            [candidate["id"]],
                            {"endpoints": endpoints},
                        )

                    event = {
                        "type": "RELAY_ASSIGNED",
                        "relay_id": relay_id,
                        "asset_id": candidate["id"],
                        "bridging": bridge_key,
                        "reason": f"Link quality {link['quality']:.2f} < {self.quality_threshold}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    events.append(event)
                    self._log(event)

        return events

    def release_relay(self, relay_id):
        """Release a relay assignment, freeing the asset."""
        with self._lock:
            entry = self.active_relays.pop(relay_id, None)
            if not entry:
                return {"error": f"Relay {relay_id} not found"}
            self.stats["relays_released"] += 1
            self._log({
                "type": "RELAY_RELEASED",
                "relay_id": relay_id,
                "asset_id": entry["asset_id"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return {
                "status": "released",
                "relay_id": relay_id,
                "asset_id": entry["asset_id"],
            }

    def _find_relay_candidate(self, assets, src_id, dst_id):
        """Find the best asset to serve as relay between src and dst.

        Prefers idle assets closest to the midpoint between the two nodes.
        """
        src_node = self.mesh.nodes.get(src_id)
        dst_node = self.mesh.nodes.get(dst_id)
        if not src_node:
            return None

        # Midpoint between src and dst (or just near src if dst unknown)
        if dst_node:
            mid_lat = (src_node["lat"] + dst_node["lat"]) / 2
            mid_lng = (src_node["lng"] + dst_node["lng"]) / 2
        else:
            mid_lat = src_node["lat"]
            mid_lng = src_node["lng"]

        # Already-assigned relay asset IDs
        relay_asset_ids = {r["asset_id"] for r in self.active_relays.values()}

        best = None
        best_dist = float("inf")

        for aid, asset in assets.items():
            # Skip assets already serving as relays
            if aid in relay_asset_ids:
                continue
            # Skip non-operational
            if asset.get("status") != "operational":
                continue
            # Skip the source/dest themselves
            if aid == src_id or aid == dst_id:
                continue
            # Prefer air domain (better relay coverage)
            pos = asset.get("position", asset)
            lat = pos.get("lat", 0)
            lng = pos.get("lng", 0)
            dist = math.sqrt((lat - mid_lat) ** 2 + (lng - mid_lng) ** 2)
            # Air assets get distance bonus
            if asset.get("domain") == "air":
                dist *= 0.7
            if dist < best_dist:
                best_dist = dist
                best = {
                    "id": aid,
                    "target_position": {"lat": mid_lat, "lng": mid_lng},
                }

        return best

    def list_active(self):
        """List all active relay assignments."""
        return [
            {
                "relay_id": k,
                "asset_id": v["asset_id"],
                "bridging": v["bridging"],
                "from_node": v["from_node"],
                "to_node": v["to_node"],
                "duration_sec": round(time.time() - v["assigned_at"], 1),
            }
            for k, v in self.active_relays.items()
        ]

    def summary(self):
        return {
            "enabled": self.enabled,
            "active_relays": len(self.active_relays),
            "quality_threshold": self.quality_threshold,
            "stats": dict(self.stats),
        }

    def _log(self, event):
        self.event_log.append(event)
        if len(self.event_log) > 200:
            self.event_log = self.event_log[-200:]


# ═══════════════════════════════════════════════════════════
#  RECONNECTION SYNC
# ═══════════════════════════════════════════════════════════

class ReconnectionSync:
    """Queues commands while assets are disconnected, replays on reconnect.

    When an asset goes offline, any commands/state changes destined for it
    are queued. On reconnect, the queue is replayed in order so the asset
    catches up to the current mission state.
    """

    # Command types that can be queued
    QUEUEABLE_TYPES = (
        "TASK_ASSIGN", "TASK_CANCEL", "BEHAVIOR_ASSIGN", "BEHAVIOR_CANCEL",
        "WAYPOINT_SET", "ROE_UPDATE", "FORMATION_CHANGE", "MISSION_UPDATE",
        "THREAT_UPDATE", "GEOFENCE_UPDATE",
    )

    def __init__(self):
        self._lock = threading.Lock()
        # asset_id → [queued commands in order]
        self.sync_queue = {}
        # History of sync operations
        self.sync_history = []
        self.stats = {
            "commands_queued": 0,
            "commands_replayed": 0,
            "syncs_completed": 0,
            "commands_expired": 0,
        }

    def queue_command(self, asset_id, command_type, payload, ttl_sec=600):
        """Queue a command for a disconnected asset.

        Args:
            asset_id:     Target asset
            command_type: One of QUEUEABLE_TYPES
            payload:      Command-specific data dict
            ttl_sec:      How long to keep the command (default 10 min)

        Returns:
            dict with queue status
        """
        if command_type not in self.QUEUEABLE_TYPES:
            return {"error": f"Unknown command type: {command_type}",
                    "available": list(self.QUEUEABLE_TYPES)}

        with self._lock:
            if asset_id not in self.sync_queue:
                self.sync_queue[asset_id] = []

            cmd = {
                "id": f"CMD-{uuid.uuid4().hex[:6]}",
                "type": command_type,
                "payload": copy.deepcopy(payload),
                "queued_at": time.time(),
                "ttl_sec": ttl_sec,
                "status": "pending",  # pending | replayed | expired
            }
            self.sync_queue[asset_id].append(cmd)
            self.stats["commands_queued"] += 1

        return {
            "status": "queued",
            "command_id": cmd["id"],
            "asset_id": asset_id,
            "queue_depth": len(self.sync_queue[asset_id]),
        }

    def replay(self, asset_id):
        """Replay all queued commands for a reconnected asset.

        Processes commands in FIFO order, skipping expired ones.

        Returns:
            dict with replay results
        """
        with self._lock:
            queue = self.sync_queue.pop(asset_id, [])
            if not queue:
                return {
                    "asset_id": asset_id,
                    "replayed": 0,
                    "expired": 0,
                    "commands": [],
                }

            now = time.time()
            replayed = []
            expired = []

            for cmd in queue:
                age = now - cmd["queued_at"]
                if age > cmd["ttl_sec"]:
                    cmd["status"] = "expired"
                    expired.append(cmd)
                    self.stats["commands_expired"] += 1
                else:
                    cmd["status"] = "replayed"
                    cmd["replayed_at"] = now
                    replayed.append(cmd)
                    self.stats["commands_replayed"] += 1

            self.stats["syncs_completed"] += 1

            result = {
                "asset_id": asset_id,
                "replayed": len(replayed),
                "expired": len(expired),
                "commands": [
                    {
                        "id": c["id"],
                        "type": c["type"],
                        "payload": c["payload"],
                        "status": c["status"],
                        "age_sec": round(now - c["queued_at"], 1),
                    }
                    for c in replayed
                ],
            }

            self.sync_history.append({
                "asset_id": asset_id,
                "replayed": len(replayed),
                "expired": len(expired),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            if len(self.sync_history) > 100:
                self.sync_history = self.sync_history[-100:]

        return result

    def get_queue(self, asset_id=None):
        """Get pending commands for an asset (or all assets)."""
        if asset_id:
            return {
                "asset_id": asset_id,
                "commands": [
                    {
                        "id": c["id"],
                        "type": c["type"],
                        "age_sec": round(time.time() - c["queued_at"], 1),
                        "ttl_sec": c["ttl_sec"],
                        "status": c["status"],
                    }
                    for c in self.sync_queue.get(asset_id, [])
                ],
                "depth": len(self.sync_queue.get(asset_id, [])),
            }
        return {
            "total_queued": sum(len(q) for q in self.sync_queue.values()),
            "assets": {
                aid: len(cmds) for aid, cmds in self.sync_queue.items()
            },
        }

    def purge_expired(self):
        """Remove expired commands from all queues."""
        now = time.time()
        purged = 0
        with self._lock:
            for aid in list(self.sync_queue.keys()):
                before = len(self.sync_queue[aid])
                self.sync_queue[aid] = [
                    c for c in self.sync_queue[aid]
                    if now - c["queued_at"] <= c["ttl_sec"]
                ]
                diff = before - len(self.sync_queue[aid])
                purged += diff
                self.stats["commands_expired"] += diff
                if not self.sync_queue[aid]:
                    del self.sync_queue[aid]
        return {"purged": purged}

    def summary(self):
        return {
            "queued_assets": len(self.sync_queue),
            "total_commands": sum(len(q) for q in self.sync_queue.values()),
            "stats": dict(self.stats),
        }


# ═══════════════════════════════════════════════════════════
#  MESH RESILIENCE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════

class MeshResilienceOrchestrator:
    """Top-level orchestrator wiring all mesh resilience components.

    tick() runs the full resilience cycle:
      1. Check mesh connectivity for each asset
      2. Mark newly disconnected assets
      3. Tick autonomous ops for disconnected assets
      4. Evaluate relay assignments
      5. Check for reconnections
      6. Replay queued commands for reconnected assets
    """

    def __init__(self, mesh_network, swarm_behavior_mgr, task_allocator):
        self.mesh = mesh_network
        self.disconnected_ops = DisconnectedOpsManager()
        self.relay_assigner = AutoRelayAssigner(mesh_network, swarm_behavior_mgr)
        self.sync = ReconnectionSync()
        self.task_allocator = task_allocator

        self._lock = threading.Lock()
        self.tick_count = 0
        self.connectivity_threshold = 0.15  # below this = "disconnected"
        self.stats = {
            "ticks": 0,
            "auto_disconnects": 0,
            "auto_reconnects": 0,
        }

    def tick(self, assets, threats=None, dt=1.0):
        """Run one resilience cycle.

        Args:
            assets:  dict of asset_id → asset dict
            threats: dict of threat_id → threat dict (for context)
            dt:      time delta

        Returns:
            dict with all events from each subsystem
        """
        all_events = []
        with self._lock:
            self.tick_count += 1
            self.stats["ticks"] += 1

            # ── Step 1: Check connectivity ─────────────────
            for aid, asset in assets.items():
                if asset.get("status") != "operational":
                    continue

                comms = asset.get("health", {}).get("comms_strength", 100)
                node = self.mesh.nodes.get(aid)
                connected = bool(node and node.get("connections"))
                quality = comms / 100.0

                # Cache intent for connected assets
                if not self.disconnected_ops.is_disconnected(aid):
                    if connected or quality > self.connectivity_threshold:
                        intent = self._infer_intent(aid, asset)
                        if intent:
                            self.disconnected_ops.cache_intent(
                                aid, intent["type"], intent["data"])
                    else:
                        # Newly disconnected
                        pos = asset.get("position", {})
                        self.disconnected_ops.mark_disconnected(
                            aid, position=pos, reason="low_connectivity")
                        self.stats["auto_disconnects"] += 1
                        all_events.append({
                            "type": "ASSET_DISCONNECTED",
                            "asset_id": aid,
                            "quality": round(quality, 2),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

            # ── Step 2: Tick autonomous for disconnected ────
            for aid in list(self.disconnected_ops.disconnected_assets.keys()):
                # Check if reconnected
                node = self.mesh.nodes.get(aid)
                comms = assets.get(aid, {}).get("health", {}).get("comms_strength", 0)
                connected = bool(node and node.get("connections"))

                if connected and comms / 100.0 > self.connectivity_threshold:
                    # Reconnected!
                    recon_result = self.disconnected_ops.mark_reconnected(aid)
                    sync_result = self.sync.replay(aid)
                    self.stats["auto_reconnects"] += 1
                    all_events.append({
                        "type": "ASSET_RECONNECTED",
                        "asset_id": aid,
                        "disconnect_duration": recon_result.get("duration_sec", 0),
                        "commands_replayed": sync_result.get("replayed", 0),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                else:
                    # Still disconnected — run autonomous tick
                    auto_events = self.disconnected_ops.tick_autonomous(aid, assets)
                    all_events.extend(auto_events)

            # ── Step 3: Evaluate relay assignments ──────────
            relay_events = self.relay_assigner.evaluate(assets)
            all_events.extend(relay_events)

            # ── Step 4: Purge expired sync commands ─────────
            self.sync.purge_expired()

        return {
            "tick": self.tick_count,
            "events": all_events,
            "event_count": len(all_events),
            "disconnected_count": len(self.disconnected_ops.disconnected_assets),
            "active_relays": len(self.relay_assigner.active_relays),
            "sync_queue_depth": sum(
                len(q) for q in self.sync.sync_queue.values()),
        }

    def simulate_disconnect(self, asset_id, assets, reason="manual_test"):
        """Manually disconnect an asset for testing/demo.

        Args:
            asset_id: Asset to disconnect
            assets:   Master asset dict (comms degraded in place)
            reason:   Reason string

        Returns:
            dict with disconnect info
        """
        asset = assets.get(asset_id)
        if not asset:
            return {"error": f"Asset {asset_id} not found"}
        if self.disconnected_ops.is_disconnected(asset_id):
            return {"error": f"Asset {asset_id} already disconnected"}

        # Degrade comms
        asset.setdefault("health", {})["comms_strength"] = 0
        pos = asset.get("position", {})

        # Cache current intent before disconnect
        intent = self._infer_intent(asset_id, asset)
        if intent:
            self.disconnected_ops.cache_intent(asset_id, intent["type"], intent["data"])

        self.disconnected_ops.mark_disconnected(asset_id, position=pos, reason=reason)

        return {
            "status": "disconnected",
            "asset_id": asset_id,
            "reason": reason,
            "intent_cached": intent["type"] if intent else "NONE",
        }

    def simulate_reconnect(self, asset_id, assets):
        """Manually reconnect an asset.

        Args:
            asset_id: Asset to reconnect
            assets:   Master asset dict (comms restored)

        Returns:
            dict with reconnection + sync info
        """
        asset = assets.get(asset_id)
        if not asset:
            return {"error": f"Asset {asset_id} not found"}
        if not self.disconnected_ops.is_disconnected(asset_id):
            return {"error": f"Asset {asset_id} is not disconnected"}

        # Restore comms
        asset.setdefault("health", {})["comms_strength"] = 85

        recon_result = self.disconnected_ops.mark_reconnected(asset_id)
        sync_result = self.sync.replay(asset_id)

        return {
            "status": "reconnected",
            "disconnect_info": recon_result,
            "sync_result": sync_result,
        }

    def _infer_intent(self, asset_id, asset):
        """Infer the current mission intent for an asset."""
        # Check for active tasks
        for t in self.task_allocator.tasks.values():
            if asset_id in t.assigned_assets and t.status in (
                    "ASSIGNED", "EN_ROUTE", "EXECUTING"):
                return {
                    "type": "TASK",
                    "data": {
                        "task_id": t.id,
                        "task_type": t.type,
                        "location": t.location,
                        "priority": t.priority,
                    },
                }

        # Default: patrol around current position
        pos = asset.get("position", asset)
        return {
            "type": "PATROL",
            "data": {
                "center_lat": pos.get("lat", 0),
                "center_lng": pos.get("lng", 0),
                "radius_deg": 0.005,
            },
        }

    def get_status(self):
        """Full resilience status for the UI."""
        return {
            "tick_count": self.tick_count,
            "connectivity_threshold": self.connectivity_threshold,
            "disconnected_ops": self.disconnected_ops.summary(),
            "relay_assigner": self.relay_assigner.summary(),
            "reconnection_sync": self.sync.summary(),
            "stats": dict(self.stats),
            "disconnected_assets": self.disconnected_ops.list_disconnected(),
            "active_relays": self.relay_assigner.list_active(),
        }
