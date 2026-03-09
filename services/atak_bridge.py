#!/usr/bin/env python3
"""
MOS Phase 6 — ATAK/TAK Bridge
Translates MOS asset data to/from Cursor-on-Target (CoT) XML
for integration with ATAK/WinTAK/iTAK.
"""

import socket
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta


class ATAKBridge:
    """Bidirectional bridge between MOS and ATAK via CoT over UDP."""

    COT_TYPES = {
        "MQ-9B": "a-f-A-M-F-Q",
        "small_uas": "a-f-A-M-F-Q",
        "loyal_wingman": "a-f-A-M-F",
        "high_alt_uas": "a-f-A-M-F-Q",
        "armed_ugv": "a-f-G-U-C",
        "logistics_ugv": "a-f-G-U-C",
        "sensor_ugv": "a-f-G-U-C",
        "usv": "a-f-S-X",
        "uuv": "a-f-S-X-S",
    }

    HOSTILE_TYPE = "a-h-X"

    def __init__(self, multicast_addr="239.2.3.1", port=6969):
        self.multicast_addr = multicast_addr
        self.port = port
        self.sock = None
        self.running = False
        self.received_cot = []
        self._lock = threading.Lock()

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
        self.running = True
        threading.Thread(target=self._listen, daemon=True).start()
        print(f"[ATAK_BRIDGE] Broadcasting to {self.multicast_addr}:{self.port}")

    def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()

    def send_asset(self, asset: dict):
        """Convert MOS asset to CoT XML and broadcast."""
        cot_type = self.COT_TYPES.get(asset.get("type", ""), "a-f-G")
        cot_xml = self._build_cot(
            uid=f"MOS.{asset['id']}",
            cot_type=cot_type,
            lat=asset.get("lat", 0),
            lng=asset.get("lng", 0),
            alt_m=asset.get("alt_ft", 0) * 0.3048,
            callsign=asset["id"],
            heading=asset.get("heading", 0),
            speed_mps=asset.get("speed_kts", 0) * 0.5144,
        )
        self._broadcast(cot_xml)

    def send_threat(self, threat: dict):
        """Send hostile track as CoT."""
        cot_xml = self._build_cot(
            uid=f"MOS.THREAT.{threat['id']}",
            cot_type=self.HOSTILE_TYPE,
            lat=threat.get("lat", 0),
            lng=threat.get("lng", 0),
            alt_m=threat.get("alt_ft", 0) * 0.3048,
            callsign=threat["id"],
            remarks=f"Threat: {threat.get('type','unknown')} | "
                    f"RF: {threat.get('rf_freq_mhz',0)}MHz",
        )
        self._broadcast(cot_xml)

    def _build_cot(self, uid, cot_type, lat, lng, alt_m=0,
                   callsign="", heading=0, speed_mps=0, remarks=""):
        now = datetime.now(timezone.utc)
        stale = now + timedelta(minutes=5)
        event = ET.Element("event", {
            "version": "2.0",
            "uid": uid,
            "type": cot_type,
            "how": "m-g",
            "time": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "start": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "stale": stale.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        })
        point = ET.SubElement(event, "point", {
            "lat": str(lat), "lon": str(lng),
            "hae": str(alt_m), "ce": "10", "le": "10",
        })
        detail = ET.SubElement(event, "detail")
        contact = ET.SubElement(detail, "contact", {"callsign": callsign})
        if heading or speed_mps:
            track = ET.SubElement(detail, "track", {
                "course": str(heading), "speed": str(speed_mps),
            })
        if remarks:
            rem = ET.SubElement(detail, "remarks")
            rem.text = remarks
        # MOS-specific extension
        mos_ext = ET.SubElement(detail, "__mos", {"version": "1.0"})
        return ET.tostring(event, encoding="unicode")

    def _broadcast(self, xml_str: str):
        if self.sock and self.running:
            try:
                self.sock.sendto(
                    xml_str.encode("utf-8"),
                    (self.multicast_addr, self.port)
                )
            except Exception as e:
                print(f"[ATAK_BRIDGE] Send error: {e}")

    def _listen(self):
        """Listen for incoming CoT from ATAK devices."""
        listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listen_sock.bind(("", self.port))
            import struct
            mreq = struct.pack("4sl",
                               socket.inet_aton(self.multicast_addr),
                               socket.INADDR_ANY)
            listen_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            listen_sock.settimeout(1.0)
        except Exception as e:
            print(f"[ATAK_BRIDGE] Listen setup error: {e}")
            return

        while self.running:
            try:
                data, addr = listen_sock.recvfrom(65535)
                cot_str = data.decode("utf-8", errors="ignore")
                if not cot_str.startswith("MOS."):  # Don't echo our own
                    with self._lock:
                        self.received_cot.append({
                            "from": addr[0],
                            "xml": cot_str,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                        if len(self.received_cot) > 200:
                            self.received_cot = self.received_cot[-200:]
            except socket.timeout:
                continue
            except Exception:
                continue

    def get_received(self) -> list:
        return list(self.received_cot)


if __name__ == "__main__":
    bridge = ATAKBridge()
    bridge.start()
    bridge.send_asset({
        "id": "REAPER-01", "type": "MQ-9B",
        "lat": 27.855, "lng": -82.515, "alt_ft": 15000,
        "heading": 90, "speed_kts": 180,
    })
    print("[ATAK_BRIDGE] Sent test CoT")
    time.sleep(2)
    bridge.stop()
