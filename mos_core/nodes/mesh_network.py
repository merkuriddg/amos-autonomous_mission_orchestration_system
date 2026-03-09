#!/usr/bin/env python3
"""AMOS Phase 22 — Mesh Networking + Resilient Comms
MANET simulation, multi-hop routing, store-and-forward,
frequency hopping, bandwidth allocation, resilience scoring."""

import math, random, time, uuid, threading
from datetime import datetime, timezone


class MeshNetwork:
    """Mobile Ad-hoc Network simulation with resilient communications."""

    FREQUENCY_BANDS = {
        "VHF": {"range_km": 30, "bandwidth_mbps": 1, "jam_resist": 0.3},
        "UHF": {"range_km": 50, "bandwidth_mbps": 5, "jam_resist": 0.5},
        "L_BAND": {"range_km": 80, "bandwidth_mbps": 10, "jam_resist": 0.6},
        "S_BAND": {"range_km": 40, "bandwidth_mbps": 25, "jam_resist": 0.7},
        "C_BAND": {"range_km": 25, "bandwidth_mbps": 50, "jam_resist": 0.8},
        "KU_BAND": {"range_km": 15, "bandwidth_mbps": 100, "jam_resist": 0.4},
        "SATCOM": {"range_km": 999, "bandwidth_mbps": 20, "jam_resist": 0.9},
    }

    PRIORITY_CLASSES = {
        "FLASH": {"weight": 10, "max_latency_ms": 100},
        "IMMEDIATE": {"weight": 8, "max_latency_ms": 500},
        "PRIORITY": {"weight": 5, "max_latency_ms": 2000},
        "ROUTINE": {"weight": 2, "max_latency_ms": 10000},
    }

    def __init__(self):
        self._lock = threading.Lock()
        self.nodes = {}            # {node_id: {position, band, connections, ...}}
        self.links = {}            # {link_key: {from, to, quality, bandwidth, ...}}
        self.routes = {}           # {src-dst: [path]}
        self.store_forward = []    # messages queued for disconnected nodes
        self.freq_hop_state = {}   # {node_id: {current_freq, hop_sequence, hop_index}}
        self.bandwidth_alloc = {}  # {link_key: {allocated, by_priority}}
        self._last_tick = 0

    def tick(self, assets, ew_jams, dt):
        """Main mesh network tick — topology, routing, frequency hop."""
        now = time.time()
        if now - self._last_tick < 5:
            return
        self._last_tick = now

        with self._lock:
            # 1. Update node positions from assets
            self._update_nodes(assets)

            # 2. Compute link quality
            self._compute_links(ew_jams)

            # 3. Frequency hopping
            self._frequency_hop()

            # 4. Route computation (Dijkstra)
            self._compute_routes()

            # 5. Process store-and-forward
            self._process_store_forward()

            # 6. Bandwidth allocation
            self._allocate_bandwidth()

    def _update_nodes(self, assets):
        """Sync mesh nodes with current asset positions."""
        for aid, a in assets.items():
            band = "SATCOM" if a["domain"] == "air" else "UHF"
            if any(s in a.get("sensors", []) for s in ["AESA_RADAR", "AEW_RADAR"]):
                band = "S_BAND"
            self.nodes[aid] = {
                "id": aid, "type": a["type"], "domain": a["domain"],
                "lat": a["position"]["lat"], "lng": a["position"]["lng"],
                "band": band, "status": a["status"],
                "comms_strength": a["health"]["comms_strength"],
                "connections": [],
                "hop_freq": self.freq_hop_state.get(aid, {}).get("current_freq", 0),
                "store_queue": sum(1 for m in self.store_forward if m["dest"] == aid),
            }
            if aid not in self.freq_hop_state:
                self.freq_hop_state[aid] = {
                    "current_freq": random.choice([225, 400, 900, 1200, 1800, 2400, 5800]),
                    "hop_sequence": [random.randint(200, 6000) for _ in range(32)],
                    "hop_index": 0,
                }

    def _compute_links(self, ew_jams):
        """Compute link quality between all node pairs."""
        self.links = {}
        node_list = list(self.nodes.values())
        for i, n1 in enumerate(node_list):
            for n2 in node_list[i+1:]:
                dist_deg = math.sqrt((n1["lat"]-n2["lat"])**2 + (n1["lng"]-n2["lng"])**2)
                dist_km = dist_deg * 111
                # Check range
                band1 = self.FREQUENCY_BANDS.get(n1["band"], {})
                band2 = self.FREQUENCY_BANDS.get(n2["band"], {})
                max_range = min(band1.get("range_km", 50), band2.get("range_km", 50))
                if dist_km > max_range:
                    continue

                # Base quality: distance-based
                quality = max(0, 1.0 - dist_km / max_range)

                # Comms strength factor
                quality *= (n1["comms_strength"] / 100) * (n2["comms_strength"] / 100)

                # EW jamming degradation
                jam_resist = min(band1.get("jam_resist", 0.5), band2.get("jam_resist", 0.5))
                for jam in ew_jams:
                    if isinstance(jam, dict) and "lat" in jam:
                        jd = math.sqrt((jam["lat"]-n1["lat"])**2+(jam["lng"]-n1["lng"])**2) * 111
                        if jd < 20:
                            quality *= jam_resist * (jd / 20)

                if quality < 0.1:
                    continue

                link_key = f"{n1['id']}<>{n2['id']}"
                bandwidth = min(band1.get("bandwidth_mbps", 5), band2.get("bandwidth_mbps", 5))
                self.links[link_key] = {
                    "from": n1["id"], "to": n2["id"],
                    "quality": round(quality, 3),
                    "bandwidth_mbps": round(bandwidth * quality, 1),
                    "distance_km": round(dist_km, 1),
                    "latency_ms": round(dist_km / 300 * 1000 + random.uniform(1, 20), 1),
                    "band": n1["band"],
                }
                n1["connections"].append(n2["id"])
                n2["connections"].append(n1["id"])

    def _frequency_hop(self):
        """Advance frequency hopping for all nodes."""
        for nid, fh in self.freq_hop_state.items():
            fh["hop_index"] = (fh["hop_index"] + 1) % len(fh["hop_sequence"])
            fh["current_freq"] = fh["hop_sequence"][fh["hop_index"]]
            if nid in self.nodes:
                self.nodes[nid]["hop_freq"] = fh["current_freq"]

    def _compute_routes(self):
        """Dijkstra routing between all pairs with link quality as weight."""
        self.routes = {}
        node_ids = list(self.nodes.keys())
        # Build adjacency
        adj = {nid: {} for nid in node_ids}
        for lk, link in self.links.items():
            cost = 1.0 / max(0.01, link["quality"])
            adj[link["from"]][link["to"]] = cost
            adj[link["to"]][link["from"]] = cost

        # Compute shortest paths for key pairs (limit to avoid O(n^3))
        for src in node_ids[:20]:  # cap for performance
            dist = {n: float("inf") for n in node_ids}
            prev = {n: None for n in node_ids}
            dist[src] = 0
            unvisited = set(node_ids)
            while unvisited:
                u = min(unvisited, key=lambda n: dist[n])
                if dist[u] == float("inf"):
                    break
                unvisited.remove(u)
                for v, w in adj.get(u, {}).items():
                    alt = dist[u] + w
                    if alt < dist[v]:
                        dist[v] = alt
                        prev[v] = u
            # Store routes
            for dst in node_ids:
                if dst == src or dist[dst] == float("inf"):
                    continue
                path = []
                n = dst
                while n:
                    path.append(n)
                    n = prev[n]
                path.reverse()
                if len(path) > 1:
                    self.routes[f"{src}->{dst}"] = {
                        "path": path, "hops": len(path) - 1,
                        "total_cost": round(dist[dst], 2),
                        "quality": round(1.0 / max(0.01, dist[dst] / len(path)), 3),
                    }

    def _process_store_forward(self):
        """Deliver queued messages when nodes reconnect."""
        delivered = []
        for i, msg in enumerate(self.store_forward):
            dest = msg["dest"]
            if dest in self.nodes and self.nodes[dest]["connections"]:
                delivered.append(i)
        for i in reversed(delivered):
            self.store_forward.pop(i)

    def _allocate_bandwidth(self):
        """Allocate bandwidth by mission priority class."""
        self.bandwidth_alloc = {}
        for lk, link in self.links.items():
            total_bw = link["bandwidth_mbps"]
            alloc = {}
            remaining = total_bw
            for pclass, pinfo in sorted(self.PRIORITY_CLASSES.items(),
                                         key=lambda x: x[1]["weight"], reverse=True):
                share = min(remaining, total_bw * pinfo["weight"] / 25)
                alloc[pclass] = round(share, 1)
                remaining -= share
            self.bandwidth_alloc[lk] = {"total": total_bw, "by_priority": alloc}

    def queue_message(self, src, dest, priority="ROUTINE", size_kb=1):
        """Queue a message for store-and-forward delivery."""
        msg = {
            "id": f"MSG-{uuid.uuid4().hex[:6]}", "src": src, "dest": dest,
            "priority": priority, "size_kb": size_kb,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }
        self.store_forward.append(msg)
        return msg

    def degrade_link(self, node_id, amount=30):
        """Manually degrade a node's comms (simulate interference)."""
        if node_id in self.nodes:
            self.nodes[node_id]["comms_strength"] = max(5, self.nodes[node_id]["comms_strength"] - amount)
            return {"status": "ok", "new_strength": self.nodes[node_id]["comms_strength"]}
        return {"error": "Node not found"}

    def get_topology(self):
        return {"nodes": dict(self.nodes), "links": dict(self.links)}

    def get_routes(self):
        return dict(self.routes)

    def get_bandwidth(self):
        return dict(self.bandwidth_alloc)

    def get_resilience(self):
        """Compute network resilience score."""
        if not self.nodes:
            return {"score": 0, "grade": "F", "details": {}}
        total_nodes = len(self.nodes)
        connected = sum(1 for n in self.nodes.values() if n["connections"])
        avg_connections = sum(len(n["connections"]) for n in self.nodes.values()) / max(1, total_nodes)
        avg_quality = sum(l["quality"] for l in self.links.values()) / max(1, len(self.links))
        redundant_paths = sum(1 for r in self.routes.values() if r["hops"] >= 2)
        store_pending = len(self.store_forward)

        score = (
            (connected / total_nodes) * 30 +
            min(avg_connections / 3, 1) * 25 +
            avg_quality * 25 +
            min(redundant_paths / max(1, len(self.routes)) * 10, 10) +
            max(0, 10 - store_pending)
        )
        grade = "A" if score > 85 else "B" if score > 70 else "C" if score > 50 else "D" if score > 30 else "F"
        return {
            "score": round(score, 1), "grade": grade,
            "connected_pct": round(connected / total_nodes * 100, 1),
            "avg_connections": round(avg_connections, 1),
            "avg_link_quality": round(avg_quality, 3),
            "redundant_paths": redundant_paths,
            "store_forward_pending": store_pending,
            "total_nodes": total_nodes, "total_links": len(self.links),
        }

    def get_stats(self):
        r = self.get_resilience()
        return {"nodes": len(self.nodes), "links": len(self.links),
                "routes": len(self.routes), "resilience_score": r["score"],
                "resilience_grade": r["grade"],
                "store_forward": len(self.store_forward),
                "hopping_nodes": len(self.freq_hop_state)}
