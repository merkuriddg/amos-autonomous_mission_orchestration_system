"""AMOS Plugin — ATAK/TAK Adapter.

Bidirectional bridge between ATAK (Android Team Awareness Kit) / WinTAK
and AMOS via Cursor-on-Target (CoT) XML.

Egress (AMOS → TAK):
  - Push AMOS assets as blue-force CoT markers
  - Push threats as hostile CoT markers

Ingest (TAK → AMOS):
  - Listen for friendly.cot_update events from the cot_adapter plugin
  - Track external ATAK user positions as blue-force contacts

Data Package Export:
  - Generate ATAK-compatible .zip data packages with CoT XML and KMZ overlays

See ``integrations/tak_bridge.py`` for egress connection,
and ``integrations/cot_receiver.py`` for ingest.
"""

import io
import json
import time
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from xml.etree.ElementTree import Element, SubElement, tostring

from core.plugin_base import PluginBase


class AtakAdapterPlugin(PluginBase):
    """ATAK/TAK bidirectional adapter plugin."""

    PLUGIN_NAME = "atak_adapter"
    PLUGIN_VERSION = "1.1"
    PLUGIN_TYPE = "asset_adapter"

    def __init__(self):
        super().__init__()
        self.bridge = None
        # Blue-force contacts from external ATAK clients (via CoT ingest)
        self.atak_contacts = {}  # uid → contact dict

    def on_activate(self, event_bus) -> None:
        # Egress: forward AMOS state to TAK
        self.subscribe("asset.position_updated", self._on_asset_update)
        self.subscribe("threat.detected", self._on_threat_update)
        # Ingest: receive blue-force from CoT receiver
        self.subscribe("friendly.cot_update", self._on_cot_friendly)
        self.emit("asset.registered", {
            "plugin": self.PLUGIN_NAME,
            "protocol": "cot",
            "capabilities": self.get_capabilities(),
        })
        try:
            from integrations.tak_bridge import TAKBridge
            self.bridge = TAKBridge()
            self.bridge.connect()
        except ImportError:
            pass

    def on_shutdown(self) -> None:
        if self.bridge:
            self.bridge.disconnect()

    def get_capabilities(self) -> list[str]:
        return [
            "telemetry", "cot_publish", "cot_ingest",
            "blue_force_tracking", "data_package", "health",
        ]

    # ── Egress (AMOS → TAK) ─────────────────────────────────

    def push_assets(self, sim_assets):
        """Push AMOS assets to TAK as blue force CoT."""
        if self.bridge:
            self.bridge.send_assets(sim_assets)

    def push_threats(self, sim_threats):
        """Push AMOS threats to TAK as hostile CoT."""
        if self.bridge:
            self.bridge.send_threats(sim_threats)

    def _on_asset_update(self, event):
        """Forward asset position updates to TAK."""
        if self.bridge and event.payload:
            self.bridge.send_assets([event.payload])

    def _on_threat_update(self, event):
        """Forward threat detections to TAK."""
        if self.bridge and event.payload:
            self.bridge.send_threats([event.payload])

    # ── Ingest (TAK → AMOS) ─────────────────────────────────

    def _on_cot_friendly(self, event):
        """Track incoming blue-force CoT from ATAK clients."""
        p = event.payload if hasattr(event, "payload") else event
        if not p:
            return
        uid = p.get("uid", "")
        if not uid:
            return
        self.atak_contacts[uid] = {
            "uid": uid,
            "callsign": p.get("callsign", uid),
            "domain": p.get("domain", "ground"),
            "lat": p.get("lat", 0),
            "lng": p.get("lng", 0),
            "alt_ft": p.get("alt_ft", 0),
            "heading_deg": p.get("heading_deg", 0),
            "speed_kts": p.get("speed_kts", 0),
            "source": "atak",
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
        # Emit as sensor reading for fusion
        self.emit("sensor.blue_force", {
            "source": "atak",
            "uid": uid,
            "callsign": p.get("callsign", uid),
            "lat": p.get("lat", 0),
            "lng": p.get("lng", 0),
            "alt_ft": p.get("alt_ft", 0),
        })

    def get_atak_contacts(self):
        """Return tracked ATAK blue-force contacts."""
        return list(self.atak_contacts.values())

    # ── Data Package Export ─────────────────────────────────

    def generate_data_package(self, sim_assets, sim_threats, package_name="AMOS_Export"):
        """Generate an ATAK-compatible .zip data package.

        Contains:
          - manifest.xml (ATAK data package manifest)
          - cot/ directory with CoT XML files for each asset and threat
          - MANIFEST/manifest.xml

        Returns bytes of the zip file.
        """
        buf = io.BytesIO()
        now = datetime.now(timezone.utc)
        stale = now + timedelta(minutes=10)
        time_fmt = "%Y-%m-%dT%H:%M:%S.000Z"

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            contents = []

            # Assets as blue-force CoT
            for aid, a in sim_assets.items():
                cot_xml = self._build_cot_xml(
                    uid=f"AMOS-{aid}", lat=a["position"]["lat"],
                    lng=a["position"]["lng"],
                    alt_m=a["position"].get("alt_ft", 0) * 0.3048,
                    cot_type=self._domain_to_cot(a.get("domain", "ground"), friendly=True),
                    callsign=aid, heading=a.get("heading_deg", 0),
                    speed_kts=a.get("speed_kts", 0),
                    now=now, stale=stale,
                )
                path = f"cot/asset_{aid}.cot"
                zf.writestr(path, cot_xml)
                contents.append({"path": path, "uid": f"AMOS-{aid}"})

            # Threats as hostile CoT
            for tid, t in sim_threats.items():
                if t.get("neutralized") or "lat" not in t:
                    continue
                cot_xml = self._build_cot_xml(
                    uid=f"THREAT-{tid}", lat=t["lat"], lng=t.get("lng", 0),
                    alt_m=0,
                    cot_type=self._domain_to_cot(t.get("domain", "ground"), friendly=False),
                    callsign=f"HOSTILE-{tid}",
                    heading=0, speed_kts=t.get("speed_kts", 0),
                    now=now, stale=stale,
                )
                path = f"cot/threat_{tid}.cot"
                zf.writestr(path, cot_xml)
                contents.append({"path": path, "uid": f"THREAT-{tid}"})

            # MANIFEST/manifest.xml
            manifest_xml = self._build_manifest(package_name, contents)
            zf.writestr("MANIFEST/manifest.xml", manifest_xml)

        return buf.getvalue()

    @staticmethod
    def _domain_to_cot(domain, friendly=True):
        prefix = "a-f" if friendly else "a-h"
        domain_map = {"air": "A", "ground": "G", "maritime": "S"}
        return f"{prefix}-{domain_map.get(domain, 'G')}"

    @staticmethod
    def _build_cot_xml(uid, lat, lng, alt_m, cot_type, callsign,
                       heading, speed_kts, now, stale):
        time_fmt = "%Y-%m-%dT%H:%M:%S.000Z"
        event = Element("event", {
            "version": "2.0", "uid": uid, "type": cot_type,
            "how": "m-g",
            "time": now.strftime(time_fmt),
            "start": now.strftime(time_fmt),
            "stale": stale.strftime(time_fmt),
        })
        SubElement(event, "point", {
            "lat": str(lat), "lon": str(lng),
            "hae": str(alt_m), "ce": "10", "le": "10",
        })
        detail = SubElement(event, "detail")
        SubElement(detail, "contact", {"callsign": callsign})
        SubElement(detail, "track", {
            "course": str(heading), "speed": str(speed_kts * 0.5144),
        })
        return tostring(event, encoding="unicode")

    @staticmethod
    def _build_manifest(name, contents):
        root = Element("MissionPackageManifest", {"version": "2"})
        config = SubElement(root, "Configuration")
        SubElement(config, "Parameter", {"name": "name", "value": name})
        SubElement(config, "Parameter", {"name": "uid", "value": str(uuid.uuid4())})
        cont = SubElement(root, "Contents")
        for c in contents:
            SubElement(cont, "Content", {
                "ignore": "false", "zipEntry": c["path"],
            })
        return tostring(root, encoding="unicode")

    def health_check(self) -> dict:
        base = super().health_check()
        base["tak_connected"] = bool(self.bridge and self.bridge.connected)
        base["atak_contacts"] = len(self.atak_contacts)
        return base
