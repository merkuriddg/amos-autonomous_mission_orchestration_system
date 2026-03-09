#!/usr/bin/env python3
"""
MOS Phase 9 — SIGINT Collector
Aggregates signals intelligence from all sensor assets.
"""

import threading
import random
from datetime import datetime, timezone


class SIGINTCollector:
    """Collects, correlates, and stores signal intercepts."""

    def __init__(self):
        self.intercepts = []
        self.emitter_db = {}
        self.collection_plans = []
        self._lock = threading.Lock()

    def add_intercept(self, intercept: dict) -> dict:
        intercept.setdefault("id", f"SIG-{random.randint(10000,99999)}")
        intercept.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        intercept.setdefault("classification", "UNKNOWN")
        with self._lock:
            self.intercepts.append(intercept)
            if len(self.intercepts) > 10000:
                self.intercepts = self.intercepts[-10000:]
            # Update emitter database
            freq = intercept.get("freq_mhz", 0)
            if freq > 0:
                key = f"{freq:.1f}"
                if key not in self.emitter_db:
                    self.emitter_db[key] = {
                        "freq_mhz": freq,
                        "first_seen": intercept["timestamp"],
                        "count": 0,
                        "classifications": [],
                    }
                self.emitter_db[key]["count"] += 1
                self.emitter_db[key]["last_seen"] = intercept["timestamp"]
                cls = intercept.get("classification", "UNKNOWN")
                if cls not in self.emitter_db[key]["classifications"]:
                    self.emitter_db[key]["classifications"].append(cls)
        return intercept

    def query(self, freq_min=None, freq_max=None, classification=None,
              collector=None, limit=50) -> list:
        results = list(self.intercepts)
        if freq_min is not None:
            results = [i for i in results if i.get("freq_mhz", 0) >= freq_min]
        if freq_max is not None:
            results = [i for i in results if i.get("freq_mhz", 0) <= freq_max]
        if classification:
            results = [i for i in results if i.get("classification") == classification]
        if collector:
            results = [i for i in results if i.get("collector") == collector]
        return results[-limit:]

    def get_emitter_db(self) -> dict:
        return dict(self.emitter_db)

    def summary(self) -> dict:
        cls_counts = {}
        for i in self.intercepts:
            c = i.get("classification", "UNKNOWN")
            cls_counts[c] = cls_counts.get(c, 0) + 1
        return {
            "total_intercepts": len(self.intercepts),
            "unique_emitters": len(self.emitter_db),
            "by_classification": cls_counts,
        }
