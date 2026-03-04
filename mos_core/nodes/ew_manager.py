#!/usr/bin/env python3
"""
MOS Phase 9 — Electronic Warfare Manager
Coordinates EW assets, manages jamming operations,
monitors the electromagnetic spectrum.
"""

import threading
import random
from datetime import datetime, timezone


class EWManager:
    """Central EW coordination node."""

    BANDS = {
        "HF": (3, 30), "VHF": (30, 300), "UHF": (300, 3000),
        "L": (1000, 2000), "S": (2000, 4000), "C": (4000, 8000),
        "X": (8000, 12000), "GPS_L1": (1575.42, 1575.42),
    }

    def __init__(self):
        self.active_jammers = {}
        self.spectrum_alerts = []
        self.ew_assets = {}
        self.operation_log = []
        self._lock = threading.Lock()

    def register_ew_asset(self, asset_id: str, capabilities: dict):
        self.ew_assets[asset_id] = {
            "id": asset_id,
            "capabilities": capabilities,
            "status": "ready",
            "current_op": None,
            "registered": datetime.now(timezone.utc).isoformat(),
        }

    def activate_jammer(self, jammer_id: str, target_freq_mhz: float,
                        bandwidth_mhz: float = 10, power_dbm: float = 30,
                        technique: str = "barrage") -> dict:
        """
        technique: barrage | spot | sweep | reactive
        """
        op = {
            "id": f"EW-OP-{random.randint(10000,99999)}",
            "jammer_id": jammer_id,
            "target_freq_mhz": target_freq_mhz,
            "bandwidth_mhz": bandwidth_mhz,
            "power_dbm": power_dbm,
            "technique": technique,
            "status": "active",
            "started": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self.active_jammers[op["id"]] = op
            if jammer_id in self.ew_assets:
                self.ew_assets[jammer_id]["status"] = "jamming"
                self.ew_assets[jammer_id]["current_op"] = op["id"]
        self._log("JAM_ACTIVATE", op)
        return {"success": True, "operation": op}

    def deactivate_jammer(self, op_id: str) -> dict:
        if op_id in self.active_jammers:
            op = self.active_jammers[op_id]
            op["status"] = "stopped"
            op["stopped"] = datetime.now(timezone.utc).isoformat()
            jammer_id = op["jammer_id"]
            if jammer_id in self.ew_assets:
                self.ew_assets[jammer_id]["status"] = "ready"
                self.ew_assets[jammer_id]["current_op"] = None
            del self.active_jammers[op_id]
            self._log("JAM_DEACTIVATE", op)
            return {"success": True}
        return {"success": False, "error": "Operation not found"}

    def spectrum_scan(self, freq_min_mhz: float = 30, freq_max_mhz: float = 6000,
                      step_mhz: float = 1) -> list:
        """Simulate a spectrum scan result."""
        readings = []
        freq = freq_min_mhz
        while freq <= freq_max_mhz:
            noise = random.uniform(-110, -80)
            # Inject signals at known threat frequencies
            for alert_freq in [915.0, 1575.42, 2437.0, 5805.0]:
                if abs(freq - alert_freq) < step_mhz:
                    noise = random.uniform(-30, 10)
            readings.append({
                "freq_mhz": round(freq, 1),
                "power_dbm": round(noise, 1),
            })
            freq += step_mhz
        return readings

    def get_status(self) -> dict:
        return {
            "ew_assets": len(self.ew_assets),
            "ready": sum(1 for a in self.ew_assets.values() if a["status"] == "ready"),
            "active_jams": len(self.active_jammers),
            "operations": list(self.active_jammers.values()),
            "alerts": self.spectrum_alerts[-20:],
        }

    def _log(self, action, data):
        self.operation_log.append({
            "action": action, "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self.operation_log) > 1000:
            self.operation_log = self.operation_log[-1000:]
