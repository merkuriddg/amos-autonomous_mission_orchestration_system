#!/usr/bin/env python3
"""
MOS Phase 9 — Cyber Operations Center
Network defense, intrusion detection, threat blocking.
"""

import threading
import random
from datetime import datetime, timezone


class CyberOps:
    """Network defense and cyber threat management."""

    def __init__(self):
        self.events = []
        self.blocked_ips = set()
        self.firewall_rules = []
        self.network_status = {
            "firewall": "active",
            "ids": "monitoring",
            "vpn": "active",
            "mesh_encryption": "AES-256-GCM",
        }
        self._lock = threading.Lock()

    def ingest_event(self, event: dict) -> dict:
        event.setdefault("id", f"CYBER-{random.randint(10000,99999)}")
        event.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        event.setdefault("blocked", False)
        # Auto-block critical from known bad IPs
        if (event.get("severity") == "critical" and
                event.get("source_ip") in self.blocked_ips):
            event["blocked"] = True
            event["auto_blocked"] = True
        with self._lock:
            self.events.append(event)
            if len(self.events) > 5000:
                self.events = self.events[-5000:]
        return event

    def block_ip(self, ip: str, reason: str = "") -> dict:
        self.blocked_ips.add(ip)
        rule = {
            "action": "BLOCK", "ip": ip, "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.firewall_rules.append(rule)
        # Retroactively block existing events
        blocked_count = 0
        for event in self.events:
            if event.get("source_ip") == ip and not event.get("blocked"):
                event["blocked"] = True
                blocked_count += 1
        return {"success": True, "ip": ip, "retroactive_blocks": blocked_count}

    def unblock_ip(self, ip: str) -> dict:
        self.blocked_ips.discard(ip)
        return {"success": True, "ip": ip}

    def block_event(self, event_id: str) -> dict:
        for event in self.events:
            if event["id"] == event_id:
                event["blocked"] = True
                self.blocked_ips.add(event.get("source_ip", ""))
                return {"success": True, "event": event}
        return {"success": False, "error": "Event not found"}

    def get_events(self, severity=None, blocked=None, limit=50) -> list:
        results = list(self.events)
        if severity:
            results = [e for e in results if e.get("severity") == severity]
        if blocked is not None:
            results = [e for e in results if e.get("blocked") == blocked]
        return results[-limit:]

    def summary(self) -> dict:
        sev_counts = {}
        for e in self.events:
            s = e.get("severity", "unknown")
            sev_counts[s] = sev_counts.get(s, 0) + 1
        return {
            "total_events": len(self.events),
            "blocked": sum(1 for e in self.events if e.get("blocked")),
            "active_threats": sum(1 for e in self.events
                                  if not e.get("blocked") and
                                  e.get("severity") in ("high", "critical")),
            "blocked_ips": len(self.blocked_ips),
            "by_severity": sev_counts,
            "network": self.network_status,
        }
