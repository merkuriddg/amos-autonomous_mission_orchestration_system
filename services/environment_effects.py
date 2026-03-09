"""AMOS Contested Environment Engine — GPS Denial, Comms Degradation, Mesh Networking

Models realistic degraded/denied operating conditions:
  - GPS jamming zones with CEP (Circular Error Probable) growth
  - RF link budget modeling for comms quality between assets
  - Automatic autonomy tier escalation when comms are lost
  - Mesh network topology tracking (who can relay to whom)
"""

import math, random, time, uuid
from datetime import datetime, timezone


# ─── Constants ────────────────────────────────────────────

SPEED_OF_LIGHT = 3e8  # m/s
EARTH_RADIUS_NM = 3440.065
DEFAULT_TX_POWER_DBM = 30  # typical UAS datalink
DEFAULT_RX_SENSITIVITY_DBM = -90
FREQ_MHZ = 915.0  # common ISM band
PATH_LOSS_EXPONENT = 2.5  # urban/suburban mix


def _haversine_nm(lat1, lng1, lat2, lng2):
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return 2 * EARTH_RADIUS_NM * math.asin(min(1, math.sqrt(a)))


def _deg_to_nm(deg):
    return deg * 60.0


# ─── GPS Denial Model ────────────────────────────────────

class GPSDenialZone:
    """A circular GPS jamming zone with power falloff."""

    def __init__(self, lat, lng, radius_nm, power_dbm=40, zone_id=None, name=""):
        self.id = zone_id or f"GPS-DENY-{uuid.uuid4().hex[:6]}"
        self.lat = lat
        self.lng = lng
        self.radius_nm = radius_nm
        self.power_dbm = power_dbm
        self.name = name or self.id
        self.active = True
        self.created = time.time()

    def jammer_to_signal_ratio(self, asset_lat, asset_lng):
        """J/S ratio in dB at asset position. >0 = GPS denied."""
        dist_nm = _haversine_nm(self.lat, self.lng, asset_lat, asset_lng)
        if dist_nm > self.radius_nm * 3:
            return -999  # too far, no effect
        # Free-space path loss from jammer
        dist_m = max(1, dist_nm * 1852)
        path_loss = 20 * math.log10(dist_m) + 20 * math.log10(1575.42e6) - 147.55
        j_received = self.power_dbm - path_loss
        # GPS signal is about -130 dBm at surface
        gps_signal = -130
        return j_received - gps_signal  # positive = jammed

    def cep_degradation(self, j_s_ratio):
        """CEP growth in meters based on J/S ratio."""
        if j_s_ratio < 0:
            return 0  # no degradation
        # Exponential CEP growth: ~5m normal, up to 500m+ when strongly jammed
        return min(1000, 5.0 * math.exp(j_s_ratio * 0.15))

    def to_dict(self):
        return {
            "id": self.id, "lat": self.lat, "lng": self.lng,
            "radius_nm": self.radius_nm, "power_dbm": self.power_dbm,
            "name": self.name, "active": self.active,
        }


# ─── Comms Link Budget Model ─────────────────────────────

class LinkBudget:
    """RF link quality between two points."""

    @staticmethod
    def calculate(tx_lat, tx_lng, rx_lat, rx_lng,
                  tx_power_dbm=DEFAULT_TX_POWER_DBM,
                  rx_sensitivity_dbm=DEFAULT_RX_SENSITIVITY_DBM,
                  freq_mhz=FREQ_MHZ, jammer_zones=None):
        """Calculate link margin and quality percentage."""
        dist_nm = _haversine_nm(tx_lat, tx_lng, rx_lat, rx_lng)
        dist_m = max(1, dist_nm * 1852)

        # Free-space path loss
        fspl = 20 * math.log10(dist_m) + 20 * math.log10(freq_mhz * 1e6) - 147.55
        # Additional environment loss
        env_loss = PATH_LOSS_EXPONENT * 3 * math.log10(max(1, dist_m / 100))

        rx_power = tx_power_dbm - fspl - env_loss

        # Jammer interference
        jammer_noise = -999
        if jammer_zones:
            mid_lat = (tx_lat + rx_lat) / 2
            mid_lng = (tx_lng + rx_lng) / 2
            for jz in jammer_zones:
                if not jz.active:
                    continue
                j_dist = _haversine_nm(jz.lat, jz.lng, mid_lat, mid_lng)
                if j_dist < jz.radius_nm * 2:
                    j_dist_m = max(1, j_dist * 1852)
                    j_loss = 20 * math.log10(j_dist_m) + 20 * math.log10(freq_mhz * 1e6) - 147.55
                    j_rx = jz.power_dbm - j_loss
                    jammer_noise = max(jammer_noise, j_rx)

        effective_noise = max(-100, jammer_noise)
        sinr = rx_power - effective_noise

        margin = rx_power - rx_sensitivity_dbm
        quality = max(0, min(100, (margin + 20) * 2.5))  # 0-100%

        if jammer_noise > -100:
            quality = max(0, quality - max(0, jammer_noise + 80) * 2)

        return {
            "dist_nm": round(dist_nm, 2),
            "rx_power_dbm": round(rx_power, 1),
            "path_loss_db": round(fspl + env_loss, 1),
            "margin_db": round(margin, 1),
            "sinr_db": round(sinr, 1),
            "jammer_interference_dbm": round(jammer_noise, 1) if jammer_noise > -100 else None,
            "quality_pct": round(quality, 1),
            "link_state": "GOOD" if quality > 70 else "DEGRADED" if quality > 30 else "DENIED",
        }


# ─── Mesh Network Topology ───────────────────────────────

class MeshTopology:
    """Track which assets can communicate with each other and with base."""

    def __init__(self, base_pos, min_quality=20):
        self.base_pos = base_pos
        self.min_quality = min_quality
        self.links = {}  # (a, b) -> link_info
        self.connectivity = {}  # asset_id -> {can_reach_base, relay_path, quality}

    def update(self, assets, jammer_zones=None):
        """Recalculate all links and connectivity."""
        self.links.clear()
        self.connectivity.clear()

        asset_list = list(assets.items())
        base_lat = self.base_pos["lat"]
        base_lng = self.base_pos.get("lng", self.base_pos.get("lon", 0))

        # Calculate all pairwise links
        for i, (aid, a) in enumerate(asset_list):
            ap = a.get("position", a)
            a_lat, a_lng = ap.get("lat", 0), ap.get("lng", 0)

            # Link to base
            base_link = LinkBudget.calculate(a_lat, a_lng, base_lat, base_lng,
                                              jammer_zones=jammer_zones)
            self.links[(aid, "BASE")] = base_link

            # Links to other assets
            for j in range(i + 1, len(asset_list)):
                bid, b = asset_list[j]
                bp = b.get("position", b)
                link = LinkBudget.calculate(a_lat, a_lng,
                                            bp.get("lat", 0), bp.get("lng", 0),
                                            jammer_zones=jammer_zones)
                self.links[(aid, bid)] = link
                self.links[(bid, aid)] = link

        # Determine connectivity to base (direct or via relay)
        for aid, a in asset_list:
            base_link = self.links.get((aid, "BASE"), {})
            direct_q = base_link.get("quality_pct", 0)

            if direct_q >= self.min_quality:
                self.connectivity[aid] = {
                    "can_reach_base": True,
                    "path": ["DIRECT"],
                    "quality": direct_q,
                    "method": "direct",
                }
            else:
                # Try single-hop relay
                best_relay, best_q = None, 0
                for bid, _ in asset_list:
                    if bid == aid:
                        continue
                    link_ab = self.links.get((aid, bid), {})
                    link_bbase = self.links.get((bid, "BASE"), {})
                    relay_q = min(link_ab.get("quality_pct", 0),
                                  link_bbase.get("quality_pct", 0))
                    if relay_q > best_q and relay_q >= self.min_quality:
                        best_relay, best_q = bid, relay_q

                if best_relay:
                    self.connectivity[aid] = {
                        "can_reach_base": True,
                        "path": [best_relay, "BASE"],
                        "quality": best_q,
                        "method": "relay",
                    }
                else:
                    self.connectivity[aid] = {
                        "can_reach_base": False,
                        "path": [],
                        "quality": direct_q,
                        "method": "none",
                    }

    def get_topology(self):
        return {
            "links": {f"{a}->{b}": v for (a, b), v in self.links.items()},
            "connectivity": dict(self.connectivity),
            "isolated_assets": [aid for aid, c in self.connectivity.items()
                                if not c["can_reach_base"]],
        }


# ─── Contested Environment Engine (Main Class) ───────────

class ContestedEnvironment:
    """Manages all contested environment effects."""

    def __init__(self, base_pos):
        self.base_pos = base_pos
        self.gps_denial_zones = []
        self.mesh = MeshTopology(base_pos)
        self.asset_gps_status = {}  # asset_id -> {jammed, cep_m, ...}
        self.asset_comms_status = {}  # asset_id -> {quality, can_reach_base, ...}
        self.auto_escalations = []  # log of autonomy escalations
        self.stats = {"gps_denied_assets": 0, "comms_denied_assets": 0, "escalations": 0}

    def add_gps_denial_zone(self, lat, lng, radius_nm, power_dbm=40, name=""):
        zone = GPSDenialZone(lat, lng, radius_nm, power_dbm, name=name)
        self.gps_denial_zones.append(zone)
        return zone.to_dict()

    def remove_gps_denial_zone(self, zone_id):
        self.gps_denial_zones = [z for z in self.gps_denial_zones if z.id != zone_id]

    def tick(self, assets, threats, dt=1.0):
        """Update all contested environment effects. Called from sim_tick."""
        events = []

        # Gather all jammer zones (from config + active threat jammers)
        active_jammers = list(self.gps_denial_zones)
        for tid, t in threats.items():
            if t.get("neutralized"):
                continue
            if t.get("type") in ("gps_jammer",) and "lat" in t:
                active_jammers.append(GPSDenialZone(
                    t["lat"], t.get("lng", t.get("lon", 0)),
                    radius_nm=t.get("jam_radius_nm", 3),
                    power_dbm=t.get("power_dbm", 35),
                    zone_id=tid, name=f"THREAT-{tid}"))

        # GPS status per asset
        gps_denied_count = 0
        for aid, a in assets.items():
            ap = a.get("position", a)
            a_lat, a_lng = ap.get("lat", 0), ap.get("lng", 0)

            worst_js = -999
            worst_zone = None
            for jz in active_jammers:
                if not jz.active:
                    continue
                js = jz.jammer_to_signal_ratio(a_lat, a_lng)
                if js > worst_js:
                    worst_js = js
                    worst_zone = jz

            jammed = worst_js > 0
            cep = worst_zone.cep_degradation(worst_js) if worst_zone and jammed else 0

            if jammed:
                gps_denied_count += 1
                # Apply position drift from GPS degradation
                drift = min(0.001, cep * 0.000001 * dt)
                ap["lat"] += random.gauss(0, drift)
                ap["lng"] += random.gauss(0, drift)

            self.asset_gps_status[aid] = {
                "jammed": jammed,
                "j_s_ratio_db": round(worst_js, 1) if worst_js > -100 else None,
                "cep_m": round(cep, 1),
                "jammer_id": worst_zone.id if worst_zone and jammed else None,
                "nav_mode": "INS_DRIFT" if jammed else "GPS_LOCK",
            }
            a.get("health", {})["gps_fix"] = not jammed

        # Mesh topology and comms status
        self.mesh.update(assets, active_jammers)
        comms_denied_count = 0
        for aid, conn in self.mesh.connectivity.items():
            self.asset_comms_status[aid] = {
                "can_reach_base": conn["can_reach_base"],
                "quality_pct": conn["quality"],
                "relay_path": conn["path"],
                "method": conn["method"],
                "comms_state": "GOOD" if conn["quality"] > 70 else
                               "DEGRADED" if conn["quality"] > 30 else "DENIED",
            }
            if not conn["can_reach_base"]:
                comms_denied_count += 1

            # Update asset health
            if aid in assets:
                assets[aid].get("health", {})["comms_strength"] = conn["quality"]

        # Auto-escalate autonomy for isolated assets
        for aid, comms in self.asset_comms_status.items():
            if aid not in assets:
                continue
            a = assets[aid]
            current_tier = a.get("autonomy_tier", 1)

            if not comms["can_reach_base"] and current_tier < 3:
                # Escalate to SWARM (tier 3) for autonomous operation
                a["autonomy_tier"] = 3
                esc = {
                    "id": f"ESC-{uuid.uuid4().hex[:6]}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "asset_id": aid,
                    "from_tier": current_tier,
                    "to_tier": 3,
                    "reason": "COMMS_LOST",
                    "comms_quality": comms["quality_pct"],
                }
                self.auto_escalations.append(esc)
                events.append(esc)
                self.stats["escalations"] += 1

            elif comms["can_reach_base"] and comms["quality_pct"] > 60 and current_tier == 3:
                # De-escalate when comms restored (only if we escalated it)
                was_escalated = any(e["asset_id"] == aid and e["reason"] == "COMMS_LOST"
                                    for e in self.auto_escalations[-20:])
                if was_escalated:
                    a["autonomy_tier"] = 2
                    events.append({
                        "id": f"DEESC-{uuid.uuid4().hex[:6]}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "asset_id": aid, "from_tier": 3, "to_tier": 2,
                        "reason": "COMMS_RESTORED",
                    })

        self.stats["gps_denied_assets"] = gps_denied_count
        self.stats["comms_denied_assets"] = comms_denied_count

        # Trim escalation log
        if len(self.auto_escalations) > 500:
            self.auto_escalations = self.auto_escalations[-500:]

        return events

    def get_status(self):
        return {
            "gps_denial_zones": [z.to_dict() for z in self.gps_denial_zones],
            "gps_status": dict(self.asset_gps_status),
            "comms_status": dict(self.asset_comms_status),
            "mesh_topology": self.mesh.get_topology(),
            "auto_escalations": self.auto_escalations[-20:],
            "stats": dict(self.stats),
        }

    def get_gps_status(self):
        return dict(self.asset_gps_status)

    def get_comms_status(self):
        return dict(self.asset_comms_status)

    def get_mesh(self):
        return self.mesh.get_topology()
