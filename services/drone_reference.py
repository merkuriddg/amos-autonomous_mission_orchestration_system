"""AMOS Drone Reference Database Service.

Provides lookup, search, and enrichment of drone tracks against a curated
reference database of commercial, military, and adversary UAS platforms.

Sources:
  - DroneCompare.org (CC-BY-4.0) — 93 commercial drones
  - US Navy / AeroVironment public datasheets — military/tactical
  - OSINT / threat intelligence — adversary profiles

Usage:
    from services.drone_reference import DroneReferenceDB
    db = DroneReferenceDB()            # auto-loads config/drone_reference.json
    db.lookup_by_serial("1581F5ABCD")  # -> DJI match
    db.enrich_track(track_dict)        # -> adds ref_* fields in-place
"""

import json
import os
import re
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PATH = os.path.join(_ROOT, "config", "drone_reference.json")


class DroneReferenceDB:
    """In-memory drone reference database with fast prefix / text lookup."""

    def __init__(self, path: str = _DEFAULT_PATH):
        self.path = path
        self.entries: list[dict] = []
        self.by_id: dict[str, dict] = {}
        self._prefix_index: list[tuple[str, dict]] = []  # (prefix, entry)
        self._name_index: dict[str, dict] = {}            # lower(name) -> entry
        self._mfg_index: dict[str, list[dict]] = {}       # lower(manufacturer) -> [entries]
        self.version: str = ""
        self.sources: list[dict] = []
        self._loaded = False
        self._load()

    # ── Loading ────────────────────────────────────────────

    def _load(self):
        """Load and index the reference JSON file."""
        if not os.path.exists(self.path):
            print(f"[DroneRefDB] Reference file not found: {self.path}")
            return
        try:
            with open(self.path) as f:
                data = json.load(f)
            self.version = data.get("version", "?")
            self.sources = data.get("sources", [])
            self.entries = data.get("entries", [])
            self._build_indices()
            self._loaded = True
            print(f"[DroneRefDB] Loaded {len(self.entries)} entries (v{self.version})")
        except Exception as e:
            print(f"[DroneRefDB] Load error: {e}")

    def _build_indices(self):
        """Build fast-lookup indices from entries."""
        self.by_id.clear()
        self._prefix_index.clear()
        self._name_index.clear()
        self._mfg_index.clear()
        for entry in self.entries:
            eid = entry.get("id", "")
            self.by_id[eid] = entry
            # Serial prefix index
            for pfx in entry.get("serial_prefixes", []):
                self._prefix_index.append((pfx.upper(), entry))
            # Name index (lowercase)
            name = entry.get("name", "")
            if name:
                self._name_index[name.lower()] = entry
            # Manufacturer index
            mfg = entry.get("manufacturer", "").lower()
            if mfg:
                self._mfg_index.setdefault(mfg, []).append(entry)
        # Sort prefix index by longest prefix first for greedy matching
        self._prefix_index.sort(key=lambda x: -len(x[0]))

    @property
    def loaded(self) -> bool:
        return self._loaded

    # ── Lookup Methods ─────────────────────────────────────

    def lookup_by_serial(self, serial: str) -> Optional[dict]:
        """Match a RemoteID serial number against known manufacturer prefixes.

        Returns the best-matching entry or None.
        """
        if not serial:
            return None
        serial_upper = serial.upper()
        for prefix, entry in self._prefix_index:
            if serial_upper.startswith(prefix):
                return entry
        return None

    def lookup_by_model(self, model_id: str) -> Optional[dict]:
        """Exact lookup by model ID."""
        return self.by_id.get(model_id)

    def lookup_by_name(self, name: str) -> Optional[dict]:
        """Case-insensitive lookup by drone name."""
        if not name:
            return None
        return self._name_index.get(name.lower())

    def get_by_category(self, category: str) -> list[dict]:
        """Return all entries matching a category (commercial/tactical/adversary)."""
        cat = category.lower()
        return [e for e in self.entries if e.get("category", "").lower() == cat]

    def get_by_manufacturer(self, manufacturer: str) -> list[dict]:
        """Return all entries from a given manufacturer."""
        return self._mfg_index.get(manufacturer.lower(), [])

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Free-text search across name, manufacturer, notes, and ID fields.

        Returns entries sorted by relevance (name match first, then notes).
        """
        if not query:
            return []
        q = query.lower()
        tokens = q.split()
        scored = []
        for entry in self.entries:
            score = 0
            name = entry.get("name", "").lower()
            mfg = entry.get("manufacturer", "").lower()
            notes = (entry.get("notes") or "").lower()
            eid = entry.get("id", "").lower()
            category = entry.get("category", "").lower()
            series = (entry.get("series") or "").lower()
            for tok in tokens:
                if tok in name:
                    score += 10
                if tok in mfg:
                    score += 5
                if tok in eid:
                    score += 3
                if tok in category:
                    score += 3
                if tok in series:
                    score += 2
                if tok in notes:
                    score += 1
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:limit]]

    # ── Enrichment ─────────────────────────────────────────

    def enrich_track(self, track: dict) -> dict:
        """Enrich a drone track dict with reference data.

        Tries serial number first, then ua_type/model name.
        Adds ref_* keys to the track dict and returns it.
        """
        match = None
        serial = track.get("serial_number", "")
        if serial:
            match = self.lookup_by_serial(serial)
        if not match:
            ua_type = track.get("ua_type", "")
            if ua_type and ua_type != "unknown":
                match = self.lookup_by_name(ua_type)
        if match:
            track["ref_id"] = match.get("id")
            track["ref_name"] = match.get("name")
            track["ref_manufacturer"] = match.get("manufacturer")
            track["ref_category"] = match.get("category")
            track["ref_threat_classification"] = match.get("threat_classification")
            track["ref_max_speed_kts"] = match.get("max_speed_kts")
            track["ref_endurance_min"] = match.get("endurance_min")
            track["ref_range_km"] = match.get("range_km")
            track["ref_sensors"] = match.get("sensors", [])
            track["ref_rf_bands"] = match.get("rf_bands", [])
            track["ref_weight_g"] = match.get("weight_g")
            track["ref_platform_type"] = match.get("platform_type")
            track["ref_notes"] = match.get("notes")
            track["ref_matched"] = True
        else:
            track["ref_matched"] = False
        return track

    # ── Stats ──────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return summary statistics about the reference database."""
        cats = {}
        mfgs = set()
        threat_classes = {}
        for e in self.entries:
            cat = e.get("category", "unknown")
            cats[cat] = cats.get(cat, 0) + 1
            mfgs.add(e.get("manufacturer", "Unknown"))
            tc = e.get("threat_classification", "unknown")
            threat_classes[tc] = threat_classes.get(tc, 0) + 1
        return {
            "total": len(self.entries),
            "loaded": self._loaded,
            "version": self.version,
            "by_category": cats,
            "by_threat_class": threat_classes,
            "manufacturers": len(mfgs),
            "sources": self.sources,
        }
