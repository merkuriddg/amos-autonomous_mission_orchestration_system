"""AMOS After Action Review (AAR) Recorder

Captures periodic snapshots of the full simulation state so operators
can scrub through a mission timeline and replay events frame-by-frame.

Usage:
    recorder = AARRecorder()
    recorder.start(sim_assets, sim_threats, aar_events, sim_clock)
    # ... simulation runs ...
    recorder.stop()

    # Replay
    frames = recorder.get_frames()
    frame  = recorder.get_frame_at(elapsed_sec=120)
"""

import copy
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import List, Optional

log = logging.getLogger("amos.aar_recorder")


class AARRecorder:
    """Records periodic state snapshots for after-action replay."""

    def __init__(self, interval_sec: float = 5.0, max_frames: int = 5000):
        self.interval_sec = interval_sec
        self.max_frames = max_frames
        self._frames: List[dict] = []
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        # References set by start()
        self._assets = None
        self._threats = None
        self._events = None
        self._clock = None
        self._session_id = ""
        self._start_time = 0
        self._last_event_idx = 0

    # ── Control ────────────────────────────────────────────

    def start(self, sim_assets: dict, sim_threats: dict,
              aar_events: list, sim_clock: dict) -> str:
        """Begin recording. Returns session ID."""
        if self._running:
            return self._session_id
        self._assets = sim_assets
        self._threats = sim_threats
        self._events = aar_events
        self._clock = sim_clock
        self._frames = []
        self._last_event_idx = 0
        self._start_time = time.time()
        self._session_id = f"AAR-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="aar-recorder",
        )
        self._thread.start()
        log.info(f"AAR recording started: {self._session_id}")
        return self._session_id

    def stop(self) -> dict:
        """Stop recording and return summary."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        summary = self.get_summary()
        log.info(f"AAR recording stopped: {len(self._frames)} frames")
        return summary

    @property
    def recording(self) -> bool:
        return self._running

    # ── Capture ────────────────────────────────────────────

    def _capture_loop(self):
        """Background loop that snapshots state at regular intervals."""
        while self._running:
            try:
                self._capture_frame()
            except Exception as e:
                log.debug(f"AAR capture error: {e}")
            time.sleep(self.interval_sec)

    def _capture_frame(self):
        """Take a single snapshot of current state."""
        if not self._assets:
            return

        elapsed = self._clock.get("elapsed_sec", 0) if self._clock else 0

        # Snapshot asset positions + status (lightweight copy)
        assets_snap = {}
        for aid, a in self._assets.items():
            pos = a.get("position", {})
            assets_snap[aid] = {
                "id": aid,
                "type": a.get("type", ""),
                "domain": a.get("domain", ""),
                "status": a.get("status", ""),
                "lat": pos.get("lat", 0),
                "lng": pos.get("lng", 0),
                "alt_ft": pos.get("alt_ft", 0),
                "heading_deg": a.get("heading_deg", 0),
                "speed_kts": a.get("speed_kts", 0),
                "battery_pct": a.get("health", {}).get("battery_pct", 0),
            }

        # Snapshot threat positions
        threats_snap = {}
        for tid, t in self._threats.items():
            threats_snap[tid] = {
                "id": tid,
                "type": t.get("type", ""),
                "lat": t.get("lat", 0),
                "lng": t.get("lng", 0),
                "neutralized": t.get("neutralized", False),
            }

        # Events since last frame
        current_event_count = len(self._events)
        new_events = []
        if current_event_count > self._last_event_idx:
            new_events = list(self._events[self._last_event_idx:current_event_count])
            self._last_event_idx = current_event_count

        frame = {
            "frame_id": len(self._frames),
            "elapsed_sec": round(elapsed, 1),
            "wall_time": datetime.now(timezone.utc).isoformat(),
            "asset_count": len(assets_snap),
            "threat_count": len(threats_snap),
            "assets": assets_snap,
            "threats": threats_snap,
            "events": new_events,
            "event_total": current_event_count,
        }

        with self._lock:
            self._frames.append(frame)
            if len(self._frames) > self.max_frames:
                self._frames = self._frames[-self.max_frames:]

    # ── Replay Queries ────────────────────────────────────

    def get_frames(self, start: int = 0, limit: int = 100) -> List[dict]:
        """Return frame metadata (without full asset/threat snapshots)."""
        with self._lock:
            subset = self._frames[start:start + limit]
            return [
                {
                    "frame_id": f["frame_id"],
                    "elapsed_sec": f["elapsed_sec"],
                    "wall_time": f["wall_time"],
                    "asset_count": f["asset_count"],
                    "threat_count": f["threat_count"],
                    "events": f["events"],
                    "event_total": f["event_total"],
                }
                for f in subset
            ]

    def get_frame(self, frame_id: int) -> Optional[dict]:
        """Return a specific full frame (with asset/threat snapshots)."""
        with self._lock:
            if 0 <= frame_id < len(self._frames):
                return self._frames[frame_id]
        return None

    def get_frame_at(self, elapsed_sec: float) -> Optional[dict]:
        """Find the frame closest to the given mission elapsed time."""
        with self._lock:
            if not self._frames:
                return None
            best = min(self._frames,
                       key=lambda f: abs(f["elapsed_sec"] - elapsed_sec))
            return best

    def get_summary(self) -> dict:
        """Recording summary."""
        with self._lock:
            frame_count = len(self._frames)
            duration = (self._frames[-1]["elapsed_sec"] - self._frames[0]["elapsed_sec"]
                        if frame_count > 1 else 0)
            return {
                "session_id": self._session_id,
                "recording": self._running,
                "frame_count": frame_count,
                "interval_sec": self.interval_sec,
                "duration_sec": round(duration, 1),
                "start_time": self._frames[0]["wall_time"] if self._frames else "",
                "end_time": self._frames[-1]["wall_time"] if self._frames else "",
            }

    def export_json(self) -> str:
        """Export full recording as JSON string."""
        with self._lock:
            return json.dumps({
                "session_id": self._session_id,
                "frames": self._frames,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            }, default=str)
