"""Kill Web Pipeline Engine — F2T2EA kill chain automation.

Manages end-to-end kill chains from detection through assessment,
with human-on-the-loop gates for engagement authorization.
"""

import time, uuid, random
from datetime import datetime, timezone

# F2T2EA stages in order
STAGES = ["FIND", "FIX", "TRACK", "TARGET", "ENGAGE", "ASSESS"]

# Stage timeout in seconds (sim-time) before escalation
STAGE_TIMEOUT = {
    "FIND": 120, "FIX": 90, "TRACK": 180,
    "TARGET": 60, "ENGAGE": 30, "ASSESS": 60
}


class KillWebPipeline:
    """Single kill chain pipeline for one threat."""

    def __init__(self, threat_id, threat_type, initial_data=None):
        self.id = f"KW-{uuid.uuid4().hex[:8]}"
        self.threat_id = threat_id
        self.threat_type = threat_type
        self.stage = "FIND"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        self.stage_entered_at = time.time()
        self.completed = False
        self.aborted = False
        self.abort_reason = ""
        self.assigned_assets = {}     # {stage: asset_id}
        self.stage_data = {}          # {stage: {payload}}
        self.awaiting_approval = False
        self.approved_by = None
        self.priority = "MEDIUM"      # LOW / MEDIUM / HIGH / CRITICAL
        self.history = []             # [{stage, timestamp, detail}]

        # Initialize FIND stage
        self.stage_data["FIND"] = initial_data or {}
        self._log("FIND", f"Pipeline created for {threat_id} ({threat_type})")

    def _log(self, stage, detail):
        self.history.append({
            "stage": stage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detail": detail
        })

    def advance(self, next_stage, asset_id=None, data=None):
        """Move pipeline to next stage."""
        if self.completed or self.aborted:
            return False
        idx_cur = STAGES.index(self.stage) if self.stage in STAGES else -1
        idx_nxt = STAGES.index(next_stage) if next_stage in STAGES else -1
        if idx_nxt <= idx_cur:
            return False
        self.stage = next_stage
        self.stage_entered_at = time.time()
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if asset_id:
            self.assigned_assets[next_stage] = asset_id
        if data:
            self.stage_data[next_stage] = data
        self._log(next_stage, f"Advanced to {next_stage}" +
                  (f" (asset: {asset_id})" if asset_id else ""))
        # ASSESS is the final stage — mark complete on entry
        if next_stage == "ASSESS":
            self.completed = True
            self._log("ASSESS", "Kill chain complete")
        return True

    def abort(self, reason=""):
        self.aborted = True
        self.abort_reason = reason
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self._log(self.stage, f"ABORTED: {reason}")

    def request_approval(self):
        """Gate at TARGET→ENGAGE for Tier 1-2 autonomy."""
        self.awaiting_approval = True
        self._log("TARGET", "Awaiting commander approval for ENGAGE")

    def approve(self, approver):
        self.awaiting_approval = False
        self.approved_by = approver
        self._log("TARGET", f"ENGAGE approved by {approver}")
        return self.advance("ENGAGE", data={"approved_by": approver})

    def elapsed_in_stage(self):
        return time.time() - self.stage_entered_at

    def is_timed_out(self):
        timeout = STAGE_TIMEOUT.get(self.stage, 120)
        return self.elapsed_in_stage() > timeout

    def to_dict(self):
        return {
            "id": self.id,
            "threat_id": self.threat_id,
            "threat_type": self.threat_type,
            "stage": self.stage,
            "stage_index": STAGES.index(self.stage) if self.stage in STAGES else -1,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "elapsed_in_stage_sec": round(self.elapsed_in_stage(), 1),
            "completed": self.completed,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
            "awaiting_approval": self.awaiting_approval,
            "approved_by": self.approved_by,
            "priority": self.priority,
            "assigned_assets": self.assigned_assets,
            "stage_data": self.stage_data,
            "history": self.history[-20:],
        }


class KillWeb:
    """Manages all active kill chain pipelines."""

    def __init__(self):
        self.pipelines = {}   # {pipeline_id: KillWebPipeline}
        self.stats = {
            "total_created": 0,
            "completed": 0,
            "aborted": 0,
            "avg_completion_sec": 0,
            "by_stage": {s: 0 for s in STAGES},
        }
        self._completion_times = []
        self._known_threats = set()   # threats already in a pipeline

    # ── Tick — called from sim_tick ────────────────────────
    def tick(self, sim_threats, sigint_intercepts, fusion_tracks,
             cm_log, bda_reports, sim_assets, dt):
        """
        Auto-advance pipelines based on new data.
        Returns list of events for aar_events.
        """
        events = []

        # 1) Auto-create pipelines from SIGINT detections (FIND)
        for ix in sigint_intercepts[-20:]:
            if ix.get("classification") == "HOSTILE":
                # Check if any threat matches this frequency/bearing
                for tid, t in sim_threats.items():
                    if t.get("neutralized") or tid in self._known_threats:
                        continue
                    if "lat" in t:
                        pid = self._create_pipeline(tid, t.get("type", "unknown"), {
                            "source": "SIGINT",
                            "intercept_id": ix["id"],
                            "freq_mhz": ix.get("freq_mhz"),
                            "bearing": ix.get("bearing_deg"),
                        })
                        if pid:
                            events.append(f"Kill Web: Pipeline {pid} created for {tid}")
                        break  # one per tick

        # 2) Auto-advance FIND→FIX if fusion has correlated the threat
        for pid, p in list(self.pipelines.items()):
            if p.completed or p.aborted:
                continue

            if p.stage == "FIND":
                # Check if fusion tracks correlate
                for ft in fusion_tracks:
                    if ft.get("threat_id") == p.threat_id or (
                        ft.get("sources", 0) >= 2 and
                        ft.get("classification") in ("HOSTILE", "SUSPECT")
                    ):
                        # Find nearest sensor asset
                        sensor_asset = self._nearest_sensor(
                            sim_assets, sim_threats.get(p.threat_id, {}))
                        p.advance("FIX", asset_id=sensor_asset, data={
                            "fusion_track": ft.get("id", ""),
                            "sources": ft.get("sources", 0),
                            "confidence": ft.get("confidence", 0),
                        })
                        events.append(f"Kill Web: {pid} → FIX (fusion correlated)")
                        break

            elif p.stage == "FIX":
                # Auto-advance to TRACK after brief dwell (simulated 15s)
                if p.elapsed_in_stage() > 15:
                    tracker = self._nearest_sensor(
                        sim_assets, sim_threats.get(p.threat_id, {}))
                    p.advance("TRACK", asset_id=tracker, data={
                        "track_quality": random.choice(["firm", "tentative", "firm"]),
                    })
                    events.append(f"Kill Web: {pid} → TRACK")

            elif p.stage == "TRACK":
                # Auto-advance to TARGET after sustained track (simulated 20s)
                if p.elapsed_in_stage() > 20:
                    # Find best weapon asset
                    weapon_asset = self._nearest_weapon(
                        sim_assets, sim_threats.get(p.threat_id, {}))
                    p.advance("TARGET", asset_id=weapon_asset, data={
                        "weapon_asset": weapon_asset,
                        "solution_quality": random.choice(["good", "marginal", "good"]),
                    })
                    # Request human approval
                    p.request_approval()
                    events.append(f"Kill Web: {pid} → TARGET (awaiting approval)")

            elif p.stage == "TARGET" and not p.awaiting_approval:
                # Already approved — advance to ENGAGE
                p.advance("ENGAGE", data={"method": "auto"})
                events.append(f"Kill Web: {pid} → ENGAGE")

            elif p.stage == "ENGAGE":
                # Check if threat was neutralized in cm_log
                for cm in cm_log[-20:]:
                    if cm.get("threat_id") == p.threat_id:
                        # Find BDA report
                        bda = None
                        for b in bda_reports[-20:]:
                            if b.get("target_id") == p.threat_id:
                                bda = b
                                break
                        p.advance("ASSESS", data={
                            "engagement_id": cm.get("id", ""),
                            "bda": bda.get("damage_level") if bda else "pending",
                        })
                        self.stats["completed"] += 1
                        elapsed = time.time() - p.stage_entered_at
                        self._completion_times.append(elapsed)
                        events.append(f"Kill Web: {pid} → ASSESS (complete)")
                        break
                # Also check if threat is neutralized directly
                t = sim_threats.get(p.threat_id)
                if t and t.get("neutralized"):
                    p.advance("ASSESS", data={
                        "engagement_id": "auto",
                        "bda": "destroyed",
                    })
                    self.stats["completed"] += 1
                    events.append(f"Kill Web: {pid} → ASSESS (threat neutralized)")

            # Timeout check — escalate priority
            if p.is_timed_out() and not p.completed and not p.aborted:
                if p.priority == "MEDIUM":
                    p.priority = "HIGH"
                elif p.priority == "HIGH":
                    p.priority = "CRITICAL"
                p._log(p.stage, f"Stage timeout — escalated to {p.priority}")

        # 3) Update stats
        self._update_stats()

        return events

    def _create_pipeline(self, threat_id, threat_type, initial_data):
        if threat_id in self._known_threats:
            return None
        pipe = KillWebPipeline(threat_id, threat_type, initial_data)
        self.pipelines[pipe.id] = pipe
        self._known_threats.add(threat_id)
        self.stats["total_created"] += 1
        return pipe.id

    def _nearest_sensor(self, sim_assets, threat):
        """Find nearest sensor-equipped asset to threat."""
        if not threat or "lat" not in threat:
            return None
        sensor_assets = [a for a in sim_assets.values()
                         if any(s in (a.get("sensors") or [])
                                for s in ["AESA_RADAR", "AEW_RADAR", "EO/IR", "SIGINT", "ELINT"])]
        if not sensor_assets:
            return None
        tlat, tlng = threat.get("lat", 0), threat.get("lng", 0)
        best = min(sensor_assets,
                   key=lambda a: abs(a["position"]["lat"] - tlat) + abs(a["position"]["lng"] - tlng))
        return best["id"]

    def _nearest_weapon(self, sim_assets, threat):
        """Find nearest weapon-equipped asset to threat."""
        if not threat or "lat" not in threat:
            return None
        armed = [a for a in sim_assets.values() if a.get("weapons")]
        if not armed:
            return None
        tlat, tlng = threat.get("lat", 0), threat.get("lng", 0)
        best = min(armed,
                   key=lambda a: abs(a["position"]["lat"] - tlat) + abs(a["position"]["lng"] - tlng))
        return best["id"]

    def _update_stats(self):
        self.stats["by_stage"] = {s: 0 for s in STAGES}
        for p in self.pipelines.values():
            if not p.completed and not p.aborted:
                self.stats["by_stage"][p.stage] = self.stats["by_stage"].get(p.stage, 0) + 1
        self.stats["aborted"] = sum(1 for p in self.pipelines.values() if p.aborted)
        if self._completion_times:
            self.stats["avg_completion_sec"] = round(
                sum(self._completion_times) / len(self._completion_times), 1)

    # ── Public API helpers ──────────────────────────────────
    def get_pipelines(self, include_completed=True):
        result = []
        for p in sorted(self.pipelines.values(),
                        key=lambda x: x.created_at, reverse=True):
            if not include_completed and (p.completed or p.aborted):
                continue
            result.append(p.to_dict())
        return result

    def get_stats(self):
        active = sum(1 for p in self.pipelines.values()
                     if not p.completed and not p.aborted)
        awaiting = sum(1 for p in self.pipelines.values()
                       if p.awaiting_approval)
        return {**self.stats, "active": active, "awaiting_approval": awaiting}

    def approve_pipeline(self, pipeline_id, approver):
        p = self.pipelines.get(pipeline_id)
        if not p or not p.awaiting_approval:
            return None
        p.approve(approver)
        return p.to_dict()

    def abort_pipeline(self, pipeline_id, reason="Manual abort"):
        p = self.pipelines.get(pipeline_id)
        if not p or p.completed or p.aborted:
            return None
        p.abort(reason)
        self.stats["aborted"] += 1
        return p.to_dict()
