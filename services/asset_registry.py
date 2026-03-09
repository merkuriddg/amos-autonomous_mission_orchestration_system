#!/usr/bin/env python3
"""
MOS Phase 1 — Asset Registry Node
Maintains authoritative state for all 27 platoon assets.
"""

import json
import time
import threading
import yaml
from pathlib import Path
from datetime import datetime, timezone


class AssetRegistry:
    """Central registry for all robotic assets in the platoon."""

    def __init__(self, config_path=None):
        self.assets = {}
        self.history = []
        self._lock = threading.Lock()
        self._callbacks = []
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "platoon_config.yaml"
        self._load_config(config_path)

    def _load_config(self, path):
        if Path(path).exists():
            with open(path) as f:
                cfg = yaml.safe_load(f)
            for asset_cfg in cfg.get("assets", []):
                self.register(asset_cfg)
            print(f"[ASSET_REGISTRY] Loaded {len(self.assets)} assets from {path}")
        else:
            print(f"[ASSET_REGISTRY] Config not found: {path}")

    def register(self, config: dict) -> dict:
        asset_id = config["id"]
        spawn = config.get("spawn", {})
        asset = {
            "id": asset_id,
            "type": config.get("type", "unknown"),
            "domain": config.get("domain", "ground"),
            "role": config.get("role", "general"),
            "autonomy_tier": config.get("autonomy_tier", 1),
            "sensors": config.get("sensors", []),
            "weapons": config.get("weapons", []),
            "endurance_hr": config.get("endurance_hr", 0),
            "cargo_lb": config.get("cargo_lb", 0),
            "position": {
                "lat": spawn.get("lat", 27.8491),
                "lng": spawn.get("lng", -82.5212),
                "alt_ft": spawn.get("alt_ft", 0),
            },
            "heading": 0.0,
            "speed_kts": 0.0,
            "status": "standby",
            "mission": "none",
            "health": {
                "battery_pct": 100.0,
                "fuel_pct": 100.0,
                "comms_strength": 95.0,
                "gps_fix": "3D",
                "errors": [],
            },
            "last_update": datetime.now(timezone.utc).isoformat(),
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self.assets[asset_id] = asset
        self._notify("register", asset)
        return asset

    def update(self, asset_id: str, updates: dict) -> dict:
        with self._lock:
            if asset_id not in self.assets:
                return {"error": f"Asset {asset_id} not found"}
            asset = self.assets[asset_id]
            for key, value in updates.items():
                if key in asset:
                    if isinstance(asset[key], dict) and isinstance(value, dict):
                        asset[key].update(value)
                    else:
                        asset[key] = value
            asset["last_update"] = datetime.now(timezone.utc).isoformat()
            self.history.append({
                "asset_id": asset_id,
                "updates": updates,
                "timestamp": asset["last_update"],
            })
            if len(self.history) > 10000:
                self.history = self.history[-10000:]
        self._notify("update", asset)
        return asset

    def get(self, asset_id: str) -> dict:
        return self.assets.get(asset_id, {})

    def get_all(self) -> dict:
        return dict(self.assets)

    def get_by_domain(self, domain: str) -> list:
        return [a for a in self.assets.values() if a["domain"] == domain]

    def get_by_role(self, role: str) -> list:
        return [a for a in self.assets.values() if a["role"] == role]

    def get_by_status(self, status: str) -> list:
        return [a for a in self.assets.values() if a["status"] == status]

    def deregister(self, asset_id: str) -> bool:
        with self._lock:
            if asset_id in self.assets:
                del self.assets[asset_id]
                self._notify("deregister", {"id": asset_id})
                return True
        return False

    def on_change(self, callback):
        self._callbacks.append(callback)

    def _notify(self, event_type, data):
        for cb in self._callbacks:
            try:
                cb(event_type, data)
            except Exception as e:
                print(f"[ASSET_REGISTRY] Callback error: {e}")

    def summary(self) -> dict:
        domains = {}
        statuses = {}
        for a in self.assets.values():
            domains[a["domain"]] = domains.get(a["domain"], 0) + 1
            statuses[a["status"]] = statuses.get(a["status"], 0) + 1
        return {
            "total": len(self.assets),
            "by_domain": domains,
            "by_status": statuses,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


if __name__ == "__main__":
    reg = AssetRegistry()
    print(json.dumps(reg.summary(), indent=2))
    print(f"\nAir assets: {len(reg.get_by_domain('air'))}")
    print(f"Ground assets: {len(reg.get_by_domain('ground'))}")
    print(f"Maritime assets: {len(reg.get_by_domain('maritime'))}")
