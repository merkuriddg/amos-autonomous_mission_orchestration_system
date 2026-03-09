#!/usr/bin/env python3
"""AMOS Phase 26 — NATO Friendly Force Information (NFFI) Adapter

STANAG 5527 / NFFI standard for blue-force tracking across
coalition networks.  Encodes/decodes NFFI XML messages for
position reports, unit status, and logistics data.

NFFI Message Types:
  PositionReport   — lat/lng/alt/heading/speed + unit identity
  StatusReport     — operational status (FULLY_OPERATIONAL, DEGRADED, etc.)
  LogisticsReport  — fuel, ammo, personnel readiness
  ContactReport    — observed hostile/unknown contacts
"""

import uuid
import time
import logging
import threading
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mos_core.adapter_base import ProtocolAdapter
from mos_core.data_model import Track

log = logging.getLogger("amos.nffi")

NFFI_NS = "urn:nato:stanag:5527:nffi"

# MIL-STD-2525 affiliation codes
AFFILIATIONS = {"F": "FRIENDLY", "H": "HOSTILE", "N": "NEUTRAL", "U": "UNKNOWN"}

# Operational status codes
OP_STATUS = {
    "FMC": "FULLY_OPERATIONAL",
    "PMC": "PARTIALLY_OPERATIONAL",
    "NMC": "NON_OPERATIONAL",
    "UNK": "UNKNOWN",
}


class NFFIMessage:
    """Single NFFI message container."""

    def __init__(self, msg_type: str = "PositionReport"):
        self.id = f"NFFI-{uuid.uuid4().hex[:8]}"
        self.msg_type = msg_type
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.unit_id = ""
        self.unit_name = ""
        self.affiliation = "F"
        self.fields = {}

    def to_dict(self) -> dict:
        return {
            "id": self.id, "msg_type": self.msg_type,
            "timestamp": self.timestamp,
            "unit_id": self.unit_id, "unit_name": self.unit_name,
            "affiliation": AFFILIATIONS.get(self.affiliation, "UNKNOWN"),
            "fields": self.fields,
        }

    def to_xml(self) -> str:
        """Serialize to NFFI XML."""
        root = ET.Element("NFFFeed", xmlns=NFFI_NS)
        root.set("timestamp", self.timestamp)
        msg_el = ET.SubElement(root, self.msg_type)
        ET.SubElement(msg_el, "UnitID").text = self.unit_id
        ET.SubElement(msg_el, "UnitName").text = self.unit_name
        ET.SubElement(msg_el, "Affiliation").text = self.affiliation

        if self.msg_type == "PositionReport":
            pos = ET.SubElement(msg_el, "Position")
            ET.SubElement(pos, "Latitude").text = str(self.fields.get("lat", 0))
            ET.SubElement(pos, "Longitude").text = str(self.fields.get("lng", 0))
            ET.SubElement(pos, "Altitude").text = str(self.fields.get("alt_m", 0))
            ET.SubElement(pos, "Heading").text = str(self.fields.get("heading_deg", 0))
            ET.SubElement(pos, "Speed").text = str(self.fields.get("speed_mps", 0))
        elif self.msg_type == "StatusReport":
            ET.SubElement(msg_el, "OpStatus").text = self.fields.get("status", "UNK")
            ET.SubElement(msg_el, "Personnel").text = str(self.fields.get("personnel", 0))
        elif self.msg_type == "LogisticsReport":
            logi = ET.SubElement(msg_el, "Logistics")
            ET.SubElement(logi, "FuelPct").text = str(self.fields.get("fuel_pct", 100))
            ET.SubElement(logi, "AmmoPct").text = str(self.fields.get("ammo_pct", 100))
            ET.SubElement(logi, "ReadinessLevel").text = self.fields.get("readiness", "GREEN")
        elif self.msg_type == "ContactReport":
            ct = ET.SubElement(msg_el, "Contact")
            ET.SubElement(ct, "Latitude").text = str(self.fields.get("lat", 0))
            ET.SubElement(ct, "Longitude").text = str(self.fields.get("lng", 0))
            ET.SubElement(ct, "ContactAffiliation").text = self.fields.get("contact_affil", "U")
            ET.SubElement(ct, "Description").text = self.fields.get("description", "")

        for k, v in self.fields.items():
            if k not in ("lat", "lng", "alt_m", "heading_deg", "speed_mps",
                         "status", "personnel", "fuel_pct", "ammo_pct",
                         "readiness", "contact_affil", "description"):
                ET.SubElement(msg_el, k).text = str(v)

        return ET.tostring(root, encoding="unicode")

    @classmethod
    def from_xml(cls, xml_str: str) -> "NFFIMessage":
        """Parse NFFI XML into NFFIMessage."""
        root = ET.fromstring(xml_str)
        # Find the actual message element (first child of NFFFeed)
        children = list(root)
        if not children:
            raise ValueError("Empty NFFI feed")
        msg_el = children[0]
        msg = cls(msg_type=msg_el.tag)
        msg.timestamp = root.get("timestamp", msg.timestamp)
        uid_el = msg_el.find("UnitID")
        msg.unit_id = uid_el.text if uid_el is not None else ""
        name_el = msg_el.find("UnitName")
        msg.unit_name = name_el.text if name_el is not None else ""
        aff_el = msg_el.find("Affiliation")
        msg.affiliation = aff_el.text if aff_el is not None else "U"

        pos = msg_el.find("Position")
        if pos is not None:
            for child in pos:
                tag_map = {"Latitude": "lat", "Longitude": "lng",
                           "Altitude": "alt_m", "Heading": "heading_deg",
                           "Speed": "speed_mps"}
                key = tag_map.get(child.tag, child.tag)
                try:
                    msg.fields[key] = float(child.text)
                except (TypeError, ValueError):
                    msg.fields[key] = child.text

        status_el = msg_el.find("OpStatus")
        if status_el is not None:
            msg.fields["status"] = status_el.text

        logi = msg_el.find("Logistics")
        if logi is not None:
            for child in logi:
                tag_map = {"FuelPct": "fuel_pct", "AmmoPct": "ammo_pct",
                           "ReadinessLevel": "readiness"}
                key = tag_map.get(child.tag, child.tag)
                try:
                    msg.fields[key] = float(child.text)
                except (TypeError, ValueError):
                    msg.fields[key] = child.text

        ct = msg_el.find("Contact")
        if ct is not None:
            for child in ct:
                tag_map = {"Latitude": "lat", "Longitude": "lng",
                           "ContactAffiliation": "contact_affil",
                           "Description": "description"}
                key = tag_map.get(child.tag, child.tag)
                try:
                    msg.fields[key] = float(child.text)
                except (TypeError, ValueError):
                    msg.fields[key] = child.text

        return msg


class NFFIAdapter(ProtocolAdapter):
    """NATO Friendly Force Information adapter for coalition blue-force tracking."""

    def __init__(self):
        super().__init__(
            adapter_id="nffi", protocol="NFFI",
            description="NATO STANAG 5527 Friendly Force Information")
        self._inbox = []
        self._outbox = []
        self._lock = threading.Lock()
        self.units = {}         # {unit_id: last_position_report}
        self.contacts = []      # observed contact reports
        self.message_log = []

    def connect(self, **kwargs) -> bool:
        self.connected = True
        self.stats["connected_at"] = time.time()
        log.info("NFFI adapter ready (simulation mode)")
        return True

    def disconnect(self) -> bool:
        self.connected = False
        return True

    def send_position_report(self, unit_id: str, unit_name: str,
                             lat: float, lng: float, alt_m: float = 0,
                             heading: float = 0, speed: float = 0,
                             affiliation: str = "F") -> dict:
        """Send a blue-force position report."""
        msg = NFFIMessage("PositionReport")
        msg.unit_id = unit_id
        msg.unit_name = unit_name
        msg.affiliation = affiliation
        msg.fields = {"lat": lat, "lng": lng, "alt_m": alt_m,
                       "heading_deg": heading, "speed_mps": speed}
        with self._lock:
            self._outbox.append(msg)
            self.message_log.append(msg.to_dict())
            self.units[unit_id] = msg.to_dict()
        self._record_out()
        return msg.to_dict()

    def send_status_report(self, unit_id: str, unit_name: str,
                           status: str = "FMC", personnel: int = 0) -> dict:
        """Send operational status report."""
        msg = NFFIMessage("StatusReport")
        msg.unit_id = unit_id
        msg.unit_name = unit_name
        msg.fields = {"status": status, "personnel": personnel}
        with self._lock:
            self._outbox.append(msg)
            self.message_log.append(msg.to_dict())
        self._record_out()
        return msg.to_dict()

    def send_logistics_report(self, unit_id: str, unit_name: str,
                              fuel_pct: float = 100, ammo_pct: float = 100,
                              readiness: str = "GREEN") -> dict:
        """Send logistics/readiness report."""
        msg = NFFIMessage("LogisticsReport")
        msg.unit_id = unit_id
        msg.unit_name = unit_name
        msg.fields = {"fuel_pct": fuel_pct, "ammo_pct": ammo_pct,
                       "readiness": readiness}
        with self._lock:
            self._outbox.append(msg)
            self.message_log.append(msg.to_dict())
        self._record_out()
        return msg.to_dict()

    def send_contact_report(self, unit_id: str, lat: float, lng: float,
                            contact_affil: str = "H",
                            description: str = "") -> dict:
        """Report observed hostile/unknown contact."""
        msg = NFFIMessage("ContactReport")
        msg.unit_id = unit_id
        msg.affiliation = "F"  # reporter is friendly
        msg.fields = {"lat": lat, "lng": lng,
                       "contact_affil": contact_affil,
                       "description": description}
        with self._lock:
            self._outbox.append(msg)
            self.message_log.append(msg.to_dict())
            self.contacts.append(msg.to_dict())
        self._record_out()
        return msg.to_dict()

    def ingest(self) -> list:
        """Convert NFFI messages to AMOS Tracks."""
        items = []
        with self._lock:
            raw = list(self._inbox)
            self._inbox.clear()

        for nffi_msg in raw:
            if isinstance(nffi_msg, str):
                try:
                    nffi_msg = NFFIMessage.from_xml(nffi_msg)
                except Exception as e:
                    log.warning(f"NFFI parse error: {e}")
                    continue

            d = nffi_msg if isinstance(nffi_msg, dict) else nffi_msg.to_dict()
            f = d.get("fields", {})
            msg_type = d.get("msg_type", "")
            affil = d.get("affiliation", "UNKNOWN")

            if msg_type in ("PositionReport", "ContactReport"):
                trk = Track(
                    lat=f.get("lat", 0), lng=f.get("lng", 0),
                    alt_m=f.get("alt_m", 0),
                    heading_deg=f.get("heading_deg", 0),
                    speed_mps=f.get("speed_mps", 0),
                    affiliation=affil if msg_type == "PositionReport" else
                                AFFILIATIONS.get(f.get("contact_affil", "U"), "UNKNOWN"),
                    associated_id=d.get("unit_id", ""),
                    metadata={"nffi_type": msg_type, "unit_name": d.get("unit_name", "")},
                )
                items.append(trk)

        if items:
            self._record_in(len(items))
        return items

    def emit(self, data) -> bool:
        """Convert AMOS Track → NFFI PositionReport for outbound sharing."""
        if isinstance(data, Track) and data.affiliation == "FRIENDLY":
            self.send_position_report(
                unit_id=data.associated_id or data.track_id,
                unit_name=data.callsign or data.associated_id or "",
                lat=data.lat, lng=data.lng, alt_m=data.alt_m,
                heading=data.heading_deg, speed=data.speed_mps,
            )
            return True
        return False

    def inject_position(self, unit_id: str, unit_name: str,
                        lat: float, lng: float, affiliation: str = "F"):
        """Inject a simulated incoming position report for testing."""
        msg = NFFIMessage("PositionReport")
        msg.unit_id = unit_id
        msg.unit_name = unit_name
        msg.affiliation = affiliation
        msg.fields = {"lat": lat, "lng": lng}
        with self._lock:
            self._inbox.append(msg)

    def get_units(self) -> dict:
        return dict(self.units)

    def get_contacts(self, limit: int = 50) -> list:
        return self.contacts[-limit:]

    def get_message_log(self, limit: int = 50) -> list:
        return self.message_log[-limit:]

    def get_status(self) -> dict:
        base = super().get_status()
        base["tracked_units"] = len(self.units)
        base["contacts_reported"] = len(self.contacts)
        return base
