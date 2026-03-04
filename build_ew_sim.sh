#!/bin/bash
set -e

DIR=~/mos_ws/src/mos_c2_console/mos_c2_console
TEMPLATES=$DIR/templates
C2=$DIR/c2_server.py

echo "══════════════════════════════════════════════════════"
echo "  MOS Phase 9.5 — Live EW/SIGINT/Cyber Simulation"
echo "══════════════════════════════════════════════════════"
echo ""
echo "  Scenario: TAMPA BAY INTERDICTION"
echo "  - T+0:00  Baseline surveillance"
echo "  - T+1:00  Unknown FHSS contact over bay"
echo "  - T+1:30  AI classifies as drone C2"
echo "  - T+2:00  Confirmed hostile"
echo "  - T+2:30  GPS jamming begins"
echo "  - T+3:00  Second hostile drone"
echo "  - T+3:30  Suspicious WiFi near perimeter"
echo "  - T+4:00  Drone swarm pattern detected"
echo "  - T+5:00  Port scan + cyber recon"
echo "  - T+5:30  Vulnerability scan results"
echo "  - T+6:00  Adversary comms network"
echo "  - T+7:00  GPS jamming intensifies (L1+L2)"
echo "  - T+8:00  Hostile radar emission"
echo "  - T+9:00  WiFi deauth attack on mesh"
echo ""

mkdir -p "$TEMPLATES"

# ═══════════════════════════════════════════════════
#  [1/4] SIMULATION DATA ENGINE
# ═══════════════════════════════════════════════════
echo "[1/4] Creating simulation data engine..."

cat > "$DIR/sim_data_engine.py" << 'SIMEOF'
"""
MOS Simulation Data Engine — Tampa Bay Interdiction Scenario
Generates realistic EW/SIGINT/Cyber data around MacDill AFB (27.849, -82.521)
"""
import threading, time, math, random
from datetime import datetime, timezone

class MOSSimEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._tick = 0
        self._running = False
        self.emitters = []
        self.signals = []
        self.spectrum_bins = [0.0]*512
        self.ew_alerts = []
        self.wifi_networks = []
        self.hosts = []
        self.vulns = []
        self.ids_alerts = []
        self._init_baseline()

    def _ts(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _init_baseline(self):
        ts = self._ts()
        base = [
            ("EMT-0001",27.849,-82.521,1030.0,-28,"FRIENDLY","IFF_RADAR",0.0,"PULSE","MacDill ASR-9",False,3.0),
            ("EMT-0002",27.975,-82.533,1090.0,-32,"FRIENDLY","SSR",0.0,"PULSE","TPA TRACON",False,1.0),
            ("EMT-0003",27.855,-82.505,462.56,-55,"FRIENDLY","LMR",0.0,"P25","Base Security",True,0.0125),
            ("EMT-0004",27.840,-82.535,156.80,-48,"NEUTRAL","MARITIME",0.0,"FM","VHF Ch16 CG",False,0.025),
            ("EMT-0005",27.870,-82.490,1960.0,-38,"NEUTRAL","CELL",0.0,"LTE","T-Mobile eNB",False,20.0),
            ("EMT-0006",27.880,-82.555,739.0,-42,"NEUTRAL","CELL",0.0,"LTE","AT&T B12",False,10.0),
            ("EMT-0007",27.862,-82.510,5745.0,-60,"FRIENDLY","WIFI",0.0,"OFDM","OPSNET-5G",False,80.0),
        ]
        for eid,lat,lon,freq,pwr,cls,typ,thr,mod,name,mob,bw in base:
            self.emitters.append({"id":eid,"lat":lat,"lon":lon,"freq":freq,"power":pwr,
                "classification":cls,"type":typ,"threat":thr,"modulation":mod,"name":name,
                "mobile":mob,"bandwidth":bw,"active":True,"first_seen":ts,"last_seen":ts,
                "_bp":pwr})
            self.signals.append({"id":"SIG-"+eid.split("-")[1],"freq":freq,"power":pwr,
                "modulation":mod,"classification":cls,"type":typ,"threat":thr,
                "bandwidth":bw,"encrypted":mod in("P25","LTE"),"first_seen":ts,"name":name})

        self.wifi_networks = [
            {"ssid":"MACDILL-FOUO","bssid":"AA:BB:CC:01:23:45","enc":"WPA3-ENT","ch":36,"sig":-42,"suspicious":False},
            {"ssid":"MOS-MESH-01","bssid":"AA:BB:CC:11:22:33","enc":"WPA3-SAE","ch":149,"sig":-38,"suspicious":False},
            {"ssid":"MOS-MESH-02","bssid":"AA:BB:CC:11:22:34","enc":"WPA3-SAE","ch":153,"sig":-41,"suspicious":False},
            {"ssid":"VISITOR-WIFI","bssid":"DE:AD:00:00:00:01","enc":"WPA2","ch":6,"sig":-55,"suspicious":False},
            {"ssid":"ATT-5G-2B4F","bssid":"DE:AD:BE:EF:2B:4F","enc":"WPA2","ch":11,"sig":-68,"suspicious":False},
        ]
        self.hosts = [
            {"ip":"10.0.1.1","type":"Gateway","os":"Cisco IOS 17","ports":"22,80,443","status":"up"},
            {"ip":"10.0.1.10","type":"MOS GCS","os":"Ubuntu 22.04","ports":"22,5000,14550","status":"up"},
            {"ip":"10.0.1.20","type":"AWACS-1","os":"Linux 5.15","ports":"22,80,7400","status":"up"},
            {"ip":"10.0.1.21","type":"AWACS-2","os":"Linux 5.15","ports":"22,80,7400","status":"up"},
            {"ip":"10.0.1.100","type":"UAV Alpha-1","os":"PX4 NuttX","ports":"14550,8080","status":"up"},
            {"ip":"10.0.1.101","type":"UAV Alpha-2","os":"ArduCopter 4.5","ports":"14550,8080","status":"up"},
            {"ip":"10.0.1.102","type":"UAV Alpha-3","os":"PX4 NuttX","ports":"14550","status":"up"},
            {"ip":"10.0.1.150","type":"UGV-01","os":"Ubuntu+Nav2","ports":"22,9090,7400","status":"up"},
            {"ip":"10.0.1.151","type":"UGV-02","os":"Ubuntu+Nav2","ports":"22,9090,7400","status":"up"},
            {"ip":"10.0.1.200","type":"USV-01","os":"Linux+MOOS","ports":"22,80,9090","status":"up"},
        ]
        self.ew_alerts.append({"time":ts,"severity":"INFO","message":"EW/SIGINT online — monitoring 400-6000 MHz — 7 baseline emitters"})

    def start(self):
        if self._running: return
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self._running:
            self._do_tick()
            time.sleep(1.0)

    def _do_tick(self):
        with self._lock:
            self._tick += 1
            self._dynamics()
            self._gen_spectrum()
            self._scenario()
            for w in self.wifi_networks:
                w["sig"] = max(-90, min(-30, w["sig"]+random.randint(-2,2)))

    def _dynamics(self):
        for e in self.emitters:
            if not e["active"]: continue
            e["power"] = round(e["_bp"]+random.gauss(0,2), 1)
            if e["mobile"]:
                e["lat"] += random.gauss(0,0.0003)
                e["lon"] += random.gauss(0,0.0003)
            e["last_seen"] = self._ts()

    def _gen_spectrum(self):
        bins, fs, fe = 512, 400.0, 6000.0
        sp = [round(-88+random.gauss(0,1.5),1) for _ in range(bins)]
        for e in self.emitters:
            if not e["active"]: continue
            f = e["freq"]
            if f < fs or f > fe: continue
            cb = int((f-fs)/(fe-fs)*bins)
            bw = max(2, int(e.get("bandwidth",1)/(fe-fs)*bins))
            for off in range(-bw*2, bw*2+1):
                idx = cb+off
                if 0 <= idx < bins:
                    att = (off/max(bw,1))**2*15
                    sp[idx] = round(max(sp[idx], e["power"]-att+random.gauss(0,0.5)),1)
        self.spectrum_bins = sp

    def _spawn(self, eid,lat,lon,freq,pwr,cls,typ,thr,mod,name,bw):
        ts = self._ts()
        self.emitters.append({"id":eid,"lat":lat,"lon":lon,"freq":freq,"power":pwr,
            "classification":cls,"type":typ,"threat":thr,"modulation":mod,"name":name,
            "mobile":True,"bandwidth":bw,"active":True,"first_seen":ts,"last_seen":ts,"_bp":pwr})

    def _reclass(self, eid, cls, typ, thr):
        for e in self.emitters:
            if e["id"]==eid: e["classification"],e["type"],e["threat"]=cls,typ,thr
        for s in self.signals:
            if s["id"]=="SIG-"+eid.split("-")[1]: s["classification"],s["type"],s["threat"]=cls,typ,thr

    def _ew_alert(self, sev, msg):
        self.ew_alerts.insert(0,{"time":self._ts(),"severity":sev,"message":msg})
        self.ew_alerts = self.ew_alerts[:100]

    def _ids_alert(self, sev, msg):
        self.ids_alerts.insert(0,{"time":self._ts(),"severity":sev,"message":msg})
        self.ids_alerts = self.ids_alerts[:100]

    def _sig(self, sid,freq,mod,cls,typ,thr,name=""):
        self.signals.insert(0,{"id":sid,"freq":freq,"modulation":mod,"classification":cls,
            "type":typ,"threat":thr,"power":round(-30-random.random()*40,1),
            "bandwidth":round(0.1+random.random()*20,1),"encrypted":"ENCRYPT" in mod.upper(),
            "first_seen":self._ts(),"name":name})

    def _scenario(self):
        t = self._tick

        if t==30: self._ew_alert("INFO","Commencing 360-degree spectrum surveillance — all bands nominal")

        # T+60: Unknown contact
        if t==60:
            self._spawn("EMT-0010",27.790,-82.460,915.3,-58,"UNKNOWN","UNK_SIGNAL",0.4,"FHSS","Unknown FHSS",5.0)
            self._ew_alert("WARN","NEW CONTACT: Unknown FHSS emitter at 915.3 MHz — bearing 145 from base")
            self._sig("SIG-0010",915.3,"FHSS","UNKNOWN","UNK_SIGNAL",0.4,"Unknown FHSS — analyzing")

        if t==90:
            self._reclass("EMT-0010","SUSPECT","DRONE_C2",0.7)
            self._ew_alert("HIGH","AI CLASSIFICATION: EMT-0010 matches DJI OcuSync pattern (87% confidence)")

        if t==120:
            self._reclass("EMT-0010","HOSTILE","DRONE_C2",0.92)
            self._ew_alert("CRITICAL","EMT-0010 CONFIRMED HOSTILE — drone C2 link matches known threat actor")

        # T+150: GPS jamming
        if t==150:
            self._spawn("EMT-0011",27.775,-82.445,1575.42,-25,"HOSTILE","GPS_JAMMER",1.0,"NOISE","GPS L1 Jammer",40.0)
            self._ew_alert("CRITICAL","GPS JAMMING DETECTED — L1 band 1575.42 MHz — J/S ratio >20 dB")
            self._sig("SIG-0011",1575.42,"NOISE","HOSTILE","GPS_JAMMER",1.0,"GPS L1 broadband jammer")

        if t==180:
            self._spawn("EMT-0012",27.800,-82.455,2437.0,-52,"HOSTILE","DRONE_C2",0.88,"WIFI","Hostile Drone 2",20.0)
            self._ew_alert("HIGH","SECOND HOSTILE DRONE: C2 on 2.4 GHz WiFi band")
            self._sig("SIG-0012",2437.0,"WIFI","HOSTILE","DRONE_C2",0.88,"WiFi-based drone C2")

        if t==210:
            self.wifi_networks.append({"ssid":"DJI-MAVIC3-C2","bssid":"66:77:88:AA:BB:CC","enc":"WPA2","ch":6,"sig":-48,"suspicious":True})
            self.wifi_networks.append({"ssid":"[HIDDEN]","bssid":"66:77:88:DD:EE:FF","enc":"NONE","ch":1,"sig":-62,"suspicious":True})
            self._ids_alert("HIGH","Suspicious AP 'DJI-MAVIC3-C2' near perimeter — non-authorized drone")
            self._ids_alert("WARN","Hidden SSID probes from 66:77:88:DD:EE:FF — recon behavior")

        if t==240:
            self._spawn("EMT-0013",27.810,-82.465,868.0,-56,"HOSTILE","DRONE_C2",0.85,"LORA","Hostile Drone 3",0.5)
            self._ew_alert("CRITICAL","DRONE SWARM: 3 hostile C2 links — coordinated formation from SE")
            self._sig("SIG-0013",868.0,"LORA","HOSTILE","DRONE_C2",0.85,"LoRa mesh drone C2")

        if t==300:
            self.hosts.append({"ip":"10.0.3.15","type":"Unknown","os":"Unknown","ports":"—","status":"scanning"})
            self._ids_alert("CRITICAL","SYN SCAN from 10.0.3.15 targeting 10.0.1.0/24 — 1024 ports in 3s")
            self._ids_alert("HIGH","Rogue MAC 66:77:88:DD:EE:FF on wired network")

        if t==330:
            self.vulns = [
                {"cve":"CVE-2024-31320","sev":"CRITICAL","desc":"MAVLink v1 no auth — command injection","host":"10.0.1.100","cvss":9.8},
                {"cve":"CVE-2024-28847","sev":"CRITICAL","desc":"RTSP buffer overflow — RCE","host":"10.0.1.200","cvss":9.1},
                {"cve":"CVE-2024-22198","sev":"HIGH","desc":"DDS open discovery — topic injection","host":"10.0.1.150","cvss":8.2},
                {"cve":"CVE-2024-21762","sev":"HIGH","desc":"Unencrypted MAVLink telemetry","host":"10.0.1.101","cvss":7.5},
                {"cve":"CVE-2024-20931","sev":"MEDIUM","desc":"Default autopilot web UI creds","host":"10.0.1.102","cvss":5.3},
                {"cve":"CVE-2024-19824","sev":"HIGH","desc":"SSH weak key exchange","host":"10.0.1.10","cvss":7.1},
            ]
            self._ids_alert("CRITICAL","VULN SCAN COMPLETE — 6 issues: 2 CRITICAL, 3 HIGH, 1 MEDIUM")
            self._ew_alert("HIGH","CYBER: Critical vulnerabilities in platoon assets — MAVLink + RTSP")

        if t==360:
            for i in range(3):
                self._spawn(f"EMT-002{i}",27.785+i*0.008,-82.450+i*0.006,468.0+i*0.5,-62,
                    "HOSTILE","COMMS_NET",0.78,"ENCRYPTED",f"Adversary Node {i+1}",0.025)
                self._sig(f"SIG-002{i}",468.0+i*0.5,"ENCRYPTED","HOSTILE","COMMS_NET",0.78,f"Encrypted net node {i+1}")
            self._ew_alert("CRITICAL","ADVERSARY COMMS NET: 3-node encrypted tactical net — 468 MHz TDMA")

        if t==420:
            for e in self.emitters:
                if e["id"]=="EMT-0011": e["_bp"]=-18; e["bandwidth"]=80.0
            self._spawn("EMT-0014",27.778,-82.448,1227.60,-22,"HOSTILE","GPS_JAMMER",1.0,"NOISE","GPS L2 Jammer",40.0)
            self._ew_alert("CRITICAL","GPS JAMMING INTENSIFIED — L1+L2 affected — nav degraded")
            self._sig("SIG-0014",1227.60,"NOISE","HOSTILE","GPS_JAMMER",1.0,"GPS L2 jammer co-located")

        if t==480:
            self._spawn("EMT-0015",27.808,-82.472,5800.0,-35,"HOSTILE","RADAR",0.95,"PULSE_DOPPLER","Hostile Radar",50.0)
            self._ew_alert("CRITICAL","HOSTILE RADAR — 5.8 GHz pulse-doppler — possible targeting")
            self._sig("SIG-0015",5800.0,"PULSE_DOPPLER","HOSTILE","RADAR",0.95,"Tracking mode radar")

        if t==540:
            self._ids_alert("CRITICAL","WIFI DEAUTH FLOOD ch6 — targeting MOS-MESH-01 — 500+ frames/sec")
            self._ids_alert("CRITICAL","WIFI DEAUTH FLOOD ch149 — targeting MOS-MESH-02")
            self._ew_alert("CRITICAL","CYBER ATTACK: Deauth attack against MOS mesh network")

        # Periodic
        if t>60 and t%20==0:
            msgs=[("INFO","Spectrum sweep complete — no new contacts"),("WARN","Signal strength change EMT-0010 — altitude shift"),
                ("INFO","DF update — triangulation CEP 35m"),("WARN","Freq hop detected — EMT-0010 channel set B"),
                ("HIGH","Power increase on hostile emitter — mode change"),("INFO","SIGINT burst captured 468.5 MHz"),
                ("WARN","Jam margin decreasing near 1575 MHz"),("INFO","Hostile track update — 45 kt NW")]
            s,m=random.choice(msgs); self._ew_alert(s,m)

        if t>300 and t%35==0:
            msgs=[("HIGH","SSH brute force 10.0.3.15 -> 10.0.1.10"),("WARN","ARP poisoning on VLAN 10"),
                ("HIGH","Unauth MAVLink COMMAND_LONG from 10.0.3.15"),("WARN","DNS exfil to suspicious TLD"),
                ("CRITICAL","TCP RST injection on MAVLink:14550"),("HIGH","Rogue DDS participant from 10.0.3.15"),
                ("WARN","ICMP tunnel from 10.0.3.15"),("HIGH","Rogue DHCP server 10.0.3.15")]
            s,m=random.choice(msgs); self._ids_alert(s,m)

        # Move hostiles toward base
        if t>60:
            for e in self.emitters:
                if e.get("classification")=="HOSTILE" and e.get("mobile"):
                    e["lat"] += (27.849-e["lat"])*0.003+random.gauss(0,0.0002)
                    e["lon"] += (-82.521-e["lon"])*0.003+random.gauss(0,0.0002)

    # ── Public API ──
    def get_tick(self):
        with self._lock: return self._tick

    def get_emitters(self):
        with self._lock:
            return [{k:v for k,v in e.items() if not k.startswith("_")} for e in self.emitters if e.get("active")]

    def get_spectrum(self):
        with self._lock:
            return {"bins":list(self.spectrum_bins),"freq_start":400.0,"freq_end":6000.0,"bin_count":512}

    def get_ew_alerts(self):
        with self._lock: return list(self.ew_alerts)

    def get_ew_stats(self):
        with self._lock:
            a=[e for e in self.emitters if e.get("active")]
            return {"total":len(a),"hostile":sum(1 for e in a if e["classification"]=="HOSTILE"),
                "jammers":sum(1 for e in a if "JAM" in e.get("type","")),"friendly":sum(1 for e in a if e["classification"]=="FRIENDLY"),
                "suspect":sum(1 for e in a if e["classification"] in("SUSPECT","UNKNOWN")),"neutral":sum(1 for e in a if e["classification"]=="NEUTRAL")}

    def get_signals(self):
        with self._lock: return list(self.signals)

    def get_cyber(self):
        with self._lock:
            return {"wifi":list(self.wifi_networks),"hosts":[dict(h) for h in self.hosts],
                "vulns":list(self.vulns),"ids_alerts":list(self.ids_alerts)}
SIMEOF
echo "  ✅ sim_data_engine.py"

# ═══════════════════════════════════════════════════
#  [2/4] PATCH C2 SERVER WITH API ENDPOINTS
# ═══════════════════════════════════════════════════
echo "[2/4] Patching C2 server with API endpoints..."

python3 << 'PATCHEOF'
import os, sys

c2path = os.path.expanduser("~/mos_ws/src/mos_c2_console/mos_c2_console/c2_server.py")
if not os.path.exists(c2path):
    print(f"  ERROR: {c2path} not found!")
    sys.exit(1)

with open(c2path, 'r') as f:
    code = f.read()

changed = False

# 1. Add sim engine import
if 'sim_data_engine' not in code:
    lines = code.split('\n')
    # Find last import
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            insert_at = i + 1
    inject = [
        '',
        '# ── EW/SIGINT/Cyber Simulation Engine ──',
        'import sys as _sys, os as _os',
        '_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))',
        'from sim_data_engine import MOSSimEngine',
        '_sim = MOSSimEngine()',
        '_sim.start()',
    ]
    for j, line in enumerate(inject):
        lines.insert(insert_at + j, line)
    code = '\n'.join(lines)
    changed = True
    print("  ✅ Simulation engine import added")

# 2. Ensure jsonify imported
if 'jsonify' not in code:
    code = code.replace('from flask import', 'from flask import jsonify, ', 1)
    changed = True
    print("  ✅ jsonify import added")

# 3. Add API routes
if '/api/ew/emitters' not in code:
    routes = '''
# ══════════════════════════════════════════════════════
#  EW / SIGINT / CYBER SIMULATION API
# ══════════════════════════════════════════════════════

@app.route('/api/ew/emitters')
def api_ew_emitters():
    return jsonify({"emitters": _sim.get_emitters(), "stats": _sim.get_ew_stats(), "tick": _sim.get_tick()})

@app.route('/api/ew/spectrum')
def api_ew_spectrum():
    return jsonify(_sim.get_spectrum())

@app.route('/api/ew/alerts')
def api_ew_alerts():
    return jsonify({"alerts": _sim.get_ew_alerts()})

@app.route('/api/sigint/signals')
def api_sigint_signals():
    return jsonify({"signals": _sim.get_signals()})

@app.route('/api/cyber/status')
def api_cyber_status():
    return jsonify(_sim.get_cyber())

'''
    if 'if __name__' in code:
        code = code.replace("if __name__", routes + "\nif __name__", 1)
    elif 'def main' in code:
        code = code.replace("def main", routes + "\ndef main", 1)
    else:
        code += routes
    changed = True
    print("  ✅ 5 API endpoints added")

if changed:
    with open(c2path, 'w') as f:
        f.write(code)
    print("  ✅ c2_server.py saved")
else:
    print("  [skip] Already patched")
PATCHEOF

# ═══════════════════════════════════════════════════
#  [3/4] API-DRIVEN DASHBOARDS
# ═══════════════════════════════════════════════════
echo "[3/4] Creating API-driven dashboards..."

# ─────── ew.html ───────
cat > "$TEMPLATES/ew.html" << 'EWEOF'
<!DOCTYPE html>
<html><head>
<title>MOS — EW/SIGINT</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;color:#00ff88;font-family:'Courier New',monospace;overflow-x:hidden}
.nav{display:flex;gap:12px;padding:5px 15px;background:#0a0a0aee;border-bottom:1px solid #ff006644;font-size:11px;position:fixed;top:0;left:0;right:0;z-index:9999}
.nav a{color:#00ccff;text-decoration:none}.nav a:hover{color:#fff}.nav .act{color:#ff0066;font-weight:bold}.nav .b{color:#ff0066;font-weight:bold;margin-right:8px}
.top{margin-top:28px;padding:6px 10px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #333}
.top h1{color:#ff0066;font-size:15px}
.top .clk{color:#888;font-size:12px}
.sb{display:flex;gap:14px;padding:6px 10px;background:#111;border-bottom:1px solid #222;font-size:11px;flex-wrap:wrap}
.sb span{color:#888}.sb strong{color:#00ff88}
.scenario{background:#1a0011;padding:4px 10px;font-size:11px;border-bottom:1px solid #ff006633;color:#ff0066}
.g{display:grid;gap:6px;padding:6px}
.g2{grid-template-columns:1fr 1fr}
.g3{grid-template-columns:2fr 1fr}
.p{background:#111;border:1px solid #282828;border-radius:4px;padding:8px}
.p h2{color:#00ccff;font-size:12px;margin-bottom:6px;border-bottom:1px solid #1a1a1a;padding-bottom:3px}
canvas{width:100%;background:#000;border:1px solid #282828;border-radius:3px}
#map{height:280px;border-radius:3px;border:1px solid #282828}
.elist{max-height:260px;overflow-y:auto;font-size:10px}
.er{display:flex;justify-content:space-between;padding:3px 4px;border-bottom:1px solid #151515;gap:4px;align-items:center}
.er:hover{background:#151515}
.t{display:inline-block;padding:1px 5px;border-radius:2px;font-size:9px;font-weight:bold}
.t-h{background:#ff004422;color:#ff0044;border:1px solid #ff004466}
.t-s{background:#ffaa0022;color:#ffaa00;border:1px solid #ffaa0066}
.t-f{background:#00ff8822;color:#00ff88;border:1px solid #00ff8866}
.t-n{background:#44444422;color:#888;border:1px solid #44444466}
.t-u{background:#ff006622;color:#ff0066;border:1px solid #ff006666}
.afeed{max-height:180px;overflow-y:auto;font-size:10px}
.ar{padding:3px 5px;margin-bottom:2px;border-left:3px solid #ff0044;background:#0f0000}
.ar.w{border-color:#ffaa00;background:#0f0f00}
.ar.i{border-color:#00ccff;background:#000a0f}
.ar.h{border-color:#ff6600;background:#0f0500}
</style>
</head><body>
<div class="nav"><span class="b">MOS</span><a href="/">C2 Map</a><a href="/dashboard">Twin</a><a class="act" href="/ew">⚡ EW/SIGINT</a><a href="/sigint">📡 SIGINT DB</a><a href="/cyber">🔓 Cyber</a><a href="/awacs">AWACS</a><a href="/tactical3d">3D</a><a href="/echelon">Echelon</a><a href="/hal">HAL</a></div>
<div class="top"><h1>⚡ EW / SIGINT DASHBOARD</h1><span class="clk" id="clk"></span></div>
<div class="scenario" id="scn">SCENARIO: TAMPA BAY INTERDICTION | T+00:00 | INITIALIZING...</div>
<div class="sb">
  <span>EMITTERS: <strong id="s-tot">—</strong></span>
  <span>HOSTILE: <strong style="color:#ff0044" id="s-hos">—</strong></span>
  <span>JAMMERS: <strong style="color:#ffaa00" id="s-jam">—</strong></span>
  <span>FRIENDLY: <strong id="s-fri">—</strong></span>
  <span>SUSPECT: <strong style="color:#ff0066" id="s-sus">—</strong></span>
  <span>SDR: <strong style="color:#00ccff">SIMULATED</strong></span>
</div>
<div class="g g2">
  <div>
    <div class="p"><h2>📊 SPECTRUM ANALYZER (400 — 6000 MHz)</h2><canvas id="spec" height="160"></canvas></div>
    <div class="p" style="margin-top:6px"><h2>📍 EMITTER MAP</h2><div id="map"></div></div>
  </div>
  <div>
    <div class="p"><h2>📡 DETECTED EMITTERS</h2><div class="elist" id="elist"></div></div>
    <div class="p" style="margin-top:6px"><h2>🌊 WATERFALL</h2><canvas id="wf" height="120"></canvas></div>
    <div class="p" style="margin-top:6px"><h2>🚨 EW ALERTS</h2><div class="afeed" id="afeed"></div></div>
  </div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const $=id=>document.getElementById(id);
setInterval(()=>{$('clk').textContent=new Date().toISOString().replace('T',' ').split('.')[0]+'Z'},1000);

// Map
const map=L.map('map',{zoomControl:false}).setView([27.835,-82.50],12);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{maxZoom:19}).addTo(map);
// MacDill marker
L.circleMarker([27.849,-82.521],{radius:8,color:'#00ccff',fillColor:'#00ccff',fillOpacity:0.3,weight:2}).addTo(map).bindPopup('<b>MacDill AFB</b>');
const markers={};

// Spectrum canvas
const sc=$('spec'), sx=sc.getContext('2d');
function rsc(){sc.width=sc.clientWidth;sc.height=sc.clientHeight}
rsc();window.addEventListener('resize',rsc);

// Waterfall canvas
const wc=$('wf'), wx=wc.getContext('2d');
function rwc(){wc.width=wc.clientWidth;wc.height=wc.clientHeight}
rwc();window.addEventListener('resize',rwc);

function drawSpectrum(bins){
  const W=sc.width,H=sc.height;
  sx.fillStyle='#000';sx.fillRect(0,0,W,H);
  // Grid
  sx.strokeStyle='#111';sx.lineWidth=1;
  for(let y=0;y<H;y+=H/5){sx.beginPath();sx.moveTo(0,y);sx.lineTo(W,y);sx.stroke()}
  for(let x=0;x<W;x+=W/10){sx.beginPath();sx.moveTo(x,0);sx.lineTo(x,H);sx.stroke()}
  // Noise floor line
  sx.strokeStyle='#331111';sx.setLineDash([4,4]);sx.beginPath();
  const nfY=H-(((-88)+100)/80)*H;
  sx.moveTo(0,nfY);sx.lineTo(W,nfY);sx.stroke();sx.setLineDash([]);
  // Spectrum
  sx.beginPath();sx.strokeStyle='#00ff88';sx.lineWidth=1.5;
  bins.forEach((v,i)=>{
    const x=(i/bins.length)*W, y=H-(((v)+100)/80)*H;
    i===0?sx.moveTo(x,y):sx.lineTo(x,y);
  });
  sx.stroke();
  // Fill
  const last=bins.length-1;
  sx.lineTo(W,H);sx.lineTo(0,H);sx.closePath();
  sx.fillStyle='rgba(0,255,136,0.04)';sx.fill();
  // Peaks (red highlights above -60)
  bins.forEach((v,i)=>{
    if(v>-55){
      const x=(i/bins.length)*W, y=H-(((v)+100)/80)*H;
      sx.fillStyle='rgba(255,0,68,0.6)';sx.beginPath();sx.arc(x,y,3,0,Math.PI*2);sx.fill();
    }
  });
  // Labels
  sx.fillStyle='#555';sx.font='9px monospace';
  const freqs=[400,1000,2000,3000,4000,5000,6000];
  freqs.forEach(f=>{
    const x=((f-400)/5600)*W;
    sx.fillText(f>=1000?(f/1000)+'G':f+'M',x,H-3);
  });
  sx.fillText('-20 dBm',2,12);sx.fillText('-100 dBm',2,H-10);
}

function drawWaterfall(bins){
  const W=wc.width,H=wc.height;
  const img=wx.getImageData(0,0,W,H-1);
  wx.putImageData(img,0,1);
  bins.forEach((v,i)=>{
    const x=Math.floor((i/bins.length)*W);
    const n=Math.max(0,Math.min(1,(v+100)/70));
    const r=Math.floor(n*255),g=Math.floor(n*100+50),b=Math.floor((1-n)*60);
    wx.fillStyle=`rgb(${r},${g},${b})`;
    wx.fillRect(x,0,Math.ceil(W/bins.length)+1,1);
  });
}

function clsTag(c){
  return c==='HOSTILE'?'t-h':c==='SUSPECT'?'t-s':c==='FRIENDLY'?'t-f':c==='NEUTRAL'?'t-n':'t-u';
}
function thColor(t){return t>0.7?'#ff0044':t>0.4?'#ffaa00':'#00ff88'}

// ── Data Fetching ──
async function fetchEmitters(){
  try{
    const r=await fetch('/api/ew/emitters');
    const d=await r.json();
    const {emitters,stats,tick}=d;
    // Scenario bar
    const mm=Math.floor(tick/60),ss=tick%60;
    const phase=tick<60?'SURVEILLANCE':tick<150?'CONTACT ANALYSIS':tick<300?'ACTIVE THREAT':tick<420?'MULTI-DOMAIN':tick<540?'ESCALATION':'FULL ENGAGEMENT';
    const threat=tick<60?'LOW':tick<150?'MODERATE':tick<300?'ELEVATED':tick<420?'HIGH':'CRITICAL';
    const tc=threat==='CRITICAL'?'#ff0044':threat==='HIGH'?'#ff6600':threat==='ELEVATED'?'#ffaa00':'#00ff88';
    $('scn').innerHTML=`SCENARIO: TAMPA BAY INTERDICTION | T+${String(mm).padStart(2,'0')}:${String(ss).padStart(2,'0')} | PHASE: ${phase} | THREAT: <span style="color:${tc}">${threat}</span>`;
    // Stats
    $('s-tot').textContent=stats.total;
    $('s-hos').textContent=stats.hostile;
    $('s-jam').textContent=stats.jammers;
    $('s-fri').textContent=stats.friendly;
    $('s-sus').textContent=stats.suspect;
    // Map markers
    const seen=new Set();
    emitters.forEach(e=>{
      seen.add(e.id);
      const color=e.classification==='HOSTILE'?'#ff0044':e.classification==='SUSPECT'?'#ffaa00':e.classification==='FRIENDLY'?'#00ff88':'#888';
      if(markers[e.id]){
        markers[e.id].setLatLng([e.lat,e.lon]);
        markers[e.id].setStyle({color,fillColor:color});
      }else{
        markers[e.id]=L.circleMarker([e.lat,e.lon],{radius:e.classification==='HOSTILE'?7:5,color,fillColor:color,fillOpacity:0.5,weight:1.5}).addTo(map)
          .bindPopup(`<b>${e.id}</b><br>${e.name}<br>${e.classification} — ${e.type}<br>${e.freq} MHz / ${e.power} dBm`);
      }
    });
    // Remove gone markers
    Object.keys(markers).forEach(id=>{if(!seen.has(id)){map.removeLayer(markers[id]);delete markers[id]}});
    // Emitter list
    const el=$('elist');
    el.innerHTML=emitters.sort((a,b)=>b.threat-a.threat).map(e=>
      `<div class="er"><span style="color:#aaa;width:65px">${e.id}</span><span class="t ${clsTag(e.classification)}">${e.classification}</span><span style="width:70px">${e.type}</span><span style="width:60px">${e.freq}M</span><span style="width:40px">${e.power}dB</span><span style="color:${thColor(e.threat)};width:30px">${e.threat}</span></div>`
    ).join('');
  }catch(err){$('scn').innerHTML='<span style="color:#ff0044">⚠ DISCONNECTED — retrying...</span>'}
}

async function fetchSpectrum(){
  try{
    const r=await fetch('/api/ew/spectrum');
    const d=await r.json();
    drawSpectrum(d.bins);
    drawWaterfall(d.bins);
  }catch(e){}
}

async function fetchAlerts(){
  try{
    const r=await fetch('/api/ew/alerts');
    const d=await r.json();
    const feed=$('afeed');
    feed.innerHTML=d.alerts.slice(0,30).map(a=>{
      const sc=a.severity==='CRITICAL'?'':a.severity==='HIGH'?'h':a.severity==='WARN'?'w':'i';
      const ts=a.time.split('T')[1].replace('Z','');
      return `<div class="ar ${sc}"><span style="color:#666">[${ts}]</span> <strong>${a.severity}</strong> — ${a.message}</div>`;
    }).join('');
  }catch(e){}
}

// ── Polling ──
setInterval(fetchSpectrum, 500);
setInterval(fetchEmitters, 2000);
setInterval(fetchAlerts, 3000);
fetchEmitters();fetchSpectrum();fetchAlerts();
</script>
</body></html>
EWEOF
echo "  ✅ ew.html (API-driven)"

# ─────── sigint.html ───────
cat > "$TEMPLATES/sigint.html" << 'SIGEOF'
<!DOCTYPE html>
<html><head>
<title>MOS — SIGINT Database</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;color:#00ff88;font-family:'Courier New',monospace}
.nav{display:flex;gap:12px;padding:5px 15px;background:#0a0a0aee;border-bottom:1px solid #ff006644;font-size:11px;position:fixed;top:0;left:0;right:0;z-index:9999}
.nav a{color:#00ccff;text-decoration:none}.nav a:hover{color:#fff}.nav .act{color:#ff0066;font-weight:bold}.nav .b{color:#ff0066;font-weight:bold;margin-right:8px}
.top{margin-top:28px;padding:6px 10px;display:flex;justify-content:space-between;border-bottom:1px solid #333}
.top h1{color:#ff0066;font-size:15px}
.filters{display:flex;gap:6px;padding:8px 10px;flex-wrap:wrap}
.fb{padding:3px 10px;background:#1a1a1a;border:1px solid #333;color:#888;cursor:pointer;border-radius:3px;font-family:inherit;font-size:10px}
.fb:hover,.fb.on{background:#ff006633;color:#ff0066;border-color:#ff0066}
.g{display:grid;grid-template-columns:5fr 3fr;gap:8px;padding:0 10px 10px}
.p{background:#111;border:1px solid #282828;border-radius:4px;padding:8px}
.p h2{color:#00ccff;font-size:12px;margin-bottom:6px;border-bottom:1px solid #1a1a1a;padding-bottom:3px}
table{width:100%;border-collapse:collapse;font-size:10px}
th{text-align:left;color:#666;padding:4px;border-bottom:1px solid #333}
td{padding:4px;border-bottom:1px solid #151515}
tr:hover{background:#151515;cursor:pointer}
tr.sel{background:#ff006622}
.t{display:inline-block;padding:1px 5px;border-radius:2px;font-size:9px;font-weight:bold}
.t-h{background:#ff004422;color:#ff0044}.t-s{background:#ffaa0022;color:#ffaa00}.t-f{background:#00ff8822;color:#00ff88}.t-n{background:#44444422;color:#888}.t-u{background:#ff006622;color:#ff0066}
.dr{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #151515;font-size:11px}
.dr .l{color:#666}
canvas{width:100%;height:100px;background:#000;border:1px solid #282828;border-radius:3px}
.tools{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}
.tool{padding:2px 8px;background:#0a2a1a;border:1px solid #00ff8833;color:#00ff88;border-radius:3px;font-size:9px}
</style>
</head><body>
<div class="nav"><span class="b">MOS</span><a href="/">C2 Map</a><a href="/dashboard">Twin</a><a href="/ew">⚡ EW/SIGINT</a><a class="act" href="/sigint">📡 SIGINT DB</a><a href="/cyber">🔓 Cyber</a><a href="/awacs">AWACS</a><a href="/tactical3d">3D</a><a href="/echelon">Echelon</a><a href="/hal">HAL</a></div>
<div class="top"><h1>📡 SIGINT DATABASE</h1><span style="color:#888;font-size:12px" id="clk"></span></div>
<div class="filters" id="filters">
  <button class="fb on" data-f="ALL">ALL</button>
  <button class="fb" data-f="HOSTILE">HOSTILE</button>
  <button class="fb" data-f="SUSPECT">SUSPECT</button>
  <button class="fb" data-f="UNKNOWN">UNKNOWN</button>
  <button class="fb" data-f="FRIENDLY">FRIENDLY</button>
  <button class="fb" data-f="NEUTRAL">NEUTRAL</button>
</div>
<div class="g">
  <div class="p" style="overflow-x:auto">
    <h2>SIGNAL DATABASE (<span id="cnt">0</span> signals)</h2>
    <table><thead><tr><th>ID</th><th>CLASS</th><th>TYPE</th><th>FREQ</th><th>PWR</th><th>MOD</th><th>BW</th><th>THREAT</th><th>FIRST SEEN</th></tr></thead>
    <tbody id="tb"></tbody></table>
  </div>
  <div>
    <div class="p"><h2>🔍 SIGNAL DETAIL</h2><div id="det"><span style="color:#555">Select a signal...</span></div></div>
    <div class="p" style="margin-top:8px"><h2>📈 WAVEFORM</h2><canvas id="wv"></canvas></div>
    <div class="p" style="margin-top:8px"><h2>🛠 ANALYSIS TOOLS</h2>
      <div class="tools"><span class="tool">GNU Radio</span><span class="tool">URH</span><span class="tool">inspectrum</span><span class="tool">SigDigger</span><span class="tool">Wireshark</span><span class="tool">gr-satellites</span></div>
    </div>
  </div>
</div>
<script>
const $=id=>document.getElementById(id);
setInterval(()=>{$('clk').textContent=new Date().toISOString().replace('T',' ').split('.')[0]+'Z'},1000);

let allSignals=[],currentFilter='ALL',selectedSig=null;

document.querySelectorAll('.fb').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.querySelectorAll('.fb').forEach(b=>b.classList.remove('on'));
    btn.classList.add('on');
    currentFilter=btn.dataset.f;
    render();
  });
});

function clsTag(c){return c==='HOSTILE'?'t-h':c==='SUSPECT'?'t-s':c==='FRIENDLY'?'t-f':c==='NEUTRAL'?'t-n':'t-u'}
function thColor(t){return t>0.7?'#ff0044':t>0.4?'#ffaa00':'#00ff88'}

function render(){
  const filtered=currentFilter==='ALL'?allSignals:allSignals.filter(s=>s.classification===currentFilter);
  $('cnt').textContent=filtered.length;
  $('tb').innerHTML=filtered.map((s,i)=>
    `<tr onclick="selectSig('${s.id}')" class="${selectedSig&&selectedSig.id===s.id?'sel':''}"><td>${s.id}</td><td><span class="t ${clsTag(s.classification)}">${s.classification}</span></td><td>${s.type}</td><td>${s.freq}M</td><td>${s.power}dB</td><td>${s.modulation}</td><td>${s.bandwidth}M</td><td style="color:${thColor(s.threat)}">${s.threat}</td><td style="color:#555">${(s.first_seen||'').split('T')[1]||''}</td></tr>`
  ).join('');
}

window.selectSig=function(id){
  selectedSig=allSignals.find(s=>s.id===id);
  if(!selectedSig)return;
  const s=selectedSig;
  $('det').innerHTML=[
    ['ID',s.id],['Classification',s.classification],['Type',s.type],['Frequency',s.freq+' MHz'],
    ['Power',s.power+' dBm'],['Modulation',s.modulation],['Bandwidth',s.bandwidth+' MHz'],
    ['Encrypted',s.encrypted?'YES':'NO'],['Threat','<span style="color:'+thColor(s.threat)+'">'+s.threat+'</span>'],
    ['Name',s.name||'—']
  ].map(([l,v])=>`<div class="dr"><span class="l">${l}</span><span>${v}</span></div>`).join('');
  drawWaveform(s);
  render();
};

function drawWaveform(s){
  const c=$('wv'),ctx=c.getContext('2d');
  c.width=c.clientWidth;c.height=c.clientHeight;
  ctx.fillStyle='#000';ctx.fillRect(0,0,c.width,c.height);
  ctx.strokeStyle='#00ff88';ctx.lineWidth=1;ctx.beginPath();
  const f=s.freq/200,phase=Math.random()*Math.PI*2;
  for(let x=0;x<c.width;x++){
    const base=Math.sin(x*f*0.05+phase)*25;
    const mod=s.modulation.includes('FM')?Math.sin(x*0.3)*10:s.modulation.includes('PULSE')?((x%40)<10?30:-30):0;
    const noise=(Math.random()-0.5)*8;
    const y=c.height/2+base+mod+noise;
    x===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
  }
  ctx.stroke();
  ctx.fillStyle='#333';ctx.font='9px monospace';
  ctx.fillText(s.modulation+' — '+s.freq+' MHz',4,12);
}

async function fetchSignals(){
  try{
    const r=await fetch('/api/sigint/signals');
    const d=await r.json();
    allSignals=d.signals;
    render();
  }catch(e){}
}
setInterval(fetchSignals,3000);
fetchSignals();
</script>
</body></html>
SIGEOF
echo "  ✅ sigint.html (API-driven)"

# ─────── cyber.html ───────
cat > "$TEMPLATES/cyber.html" << 'CYEOF'
<!DOCTYPE html>
<html><head>
<title>MOS — Cyber Operations</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;color:#00ff88;font-family:'Courier New',monospace}
.nav{display:flex;gap:12px;padding:5px 15px;background:#0a0a0aee;border-bottom:1px solid #ff006644;font-size:11px;position:fixed;top:0;left:0;right:0;z-index:9999}
.nav a{color:#00ccff;text-decoration:none}.nav a:hover{color:#fff}.nav .act{color:#ff0066;font-weight:bold}.nav .b{color:#ff0066;font-weight:bold;margin-right:8px}
.top{margin-top:28px;padding:6px 10px;display:flex;justify-content:space-between;border-bottom:1px solid #333}
.top h1{color:#ff0066;font-size:15px}
.sb{display:flex;gap:14px;padding:6px 10px;background:#111;border-bottom:1px solid #222;font-size:11px;flex-wrap:wrap}
.sb span{color:#888}.sb strong{color:#00ff88}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;padding:8px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:0 8px 8px}
.p{background:#111;border:1px solid #282828;border-radius:4px;padding:8px}
.p h2{color:#00ccff;font-size:12px;margin-bottom:6px;border-bottom:1px solid #1a1a1a;padding-bottom:3px}
table{width:100%;border-collapse:collapse;font-size:10px}
th{text-align:left;color:#666;padding:4px;border-bottom:1px solid #333}
td{padding:4px;border-bottom:1px solid #151515}
tr:hover{background:#151515}
.sc{font-weight:bold}.sc.c{color:#ff0044}.sc.h{color:#ff6600}.sc.m{color:#ffaa00}.sc.l{color:#00ff88}
.wi{padding:5px;border-bottom:1px solid #151515;display:flex;justify-content:space-between;align-items:center}
.wi:hover{background:#151515}
.bars{display:flex;gap:1px;align-items:flex-end}
.bar{width:3px;background:#00ff88;border-radius:1px}
.ids{max-height:280px;overflow-y:auto}
.ia{padding:4px 6px;margin-bottom:2px;border-left:3px solid #ff0044;background:#0f0000;font-size:10px}
.ia.w{border-color:#ffaa00;background:#0f0f00}
canvas{width:100%;height:250px;background:#000;border:1px solid #282828;border-radius:3px}
</style>
</head><body>
<div class="nav"><span class="b">MOS</span><a href="/">C2 Map</a><a href="/dashboard">Twin</a><a href="/ew">⚡ EW/SIGINT</a><a href="/sigint">📡 SIGINT DB</a><a class="act" href="/cyber">🔓 Cyber</a><a href="/awacs">AWACS</a><a href="/tactical3d">3D</a><a href="/echelon">Echelon</a><a href="/hal">HAL</a></div>
<div class="top"><h1>🔓 CYBER OPERATIONS CENTER</h1><span style="color:#888;font-size:12px" id="clk"></span></div>
<div class="sb">
  <span>NETWORKS: <strong id="s-net">—</strong></span>
  <span>HOSTS: <strong id="s-host">—</strong></span>
  <span>VULNS: <strong style="color:#ff0044" id="s-vuln">—</strong></span>
  <span>IDS ALERTS: <strong style="color:#ffaa00" id="s-ids">—</strong></span>
  <span>MODE: <strong style="color:#00ccff">PASSIVE RECON</strong></span>
</div>
<div class="g3">
  <div class="p">
    <h2>📶 WiFi Networks</h2>
    <div id="wlist"></div>
  </div>
  <div class="p">
    <h2>🖥 Discovered Devices</h2>
    <table><thead><tr><th>IP</th><th>TYPE</th><th>OS</th><th>PORTS</th><th>STATUS</th></tr></thead>
    <tbody id="dtb"></tbody></table>
  </div>
  <div class="p">
    <h2>🛡 IDS Alerts</h2>
    <div class="ids" id="ids"></div>
  </div>
</div>
<div class="g2">
  <div class="p">
    <h2>🔴 VULNERABILITIES</h2>
    <table><thead><tr><th>CVE</th><th>SEV</th><th>CVSS</th><th>DESCRIPTION</th><th>HOST</th></tr></thead>
    <tbody id="vtb"></tbody></table>
    <div id="novuln" style="color:#555;font-size:11px;padding:8px;text-align:center">Vulnerability scan pending...</div>
  </div>
  <div class="p">
    <h2>📊 NETWORK TOPOLOGY</h2>
    <canvas id="topo"></canvas>
  </div>
</div>
<script>
const $=id=>document.getElementById(id);
setInterval(()=>{$('clk').textContent=new Date().toISOString().replace('T',' ').split('.')[0]+'Z'},1000);

function drawTopo(hosts){
  const c=$('topo'),ctx=c.getContext('2d');
  c.width=c.clientWidth;c.height=c.clientHeight;
  const W=c.width,H=c.height;
  ctx.fillStyle='#000';ctx.fillRect(0,0,W,H);
  const cx=W/2,cy=H/2;
  // Gateway center
  ctx.fillStyle='#ff0066';ctx.beginPath();ctx.arc(cx,cy,14,0,Math.PI*2);ctx.fill();
  ctx.fillStyle='#fff';ctx.font='9px monospace';ctx.textAlign='center';ctx.fillText('GW',cx,cy+3);
  // Nodes
  hosts.forEach((h,i)=>{
    const ang=(i/hosts.length)*Math.PI*2-Math.PI/2;
    const r=Math.min(W,H)*0.36;
    const x=cx+Math.cos(ang)*r, y=cy+Math.sin(ang)*r;
    ctx.strokeStyle=h.status==='scanning'?'#ff004466':'#222';ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(cx,cy);ctx.lineTo(x,y);ctx.stroke();
    const col=h.type==='Unknown'?'#ff0044':h.type.includes('UA')||h.type.includes('UGV')||h.type.includes('USV')?'#00ff88':h.type.includes('AWACS')?'#ffaa00':'#00ccff';
    ctx.fillStyle=col;ctx.beginPath();ctx.arc(x,y,8,0,Math.PI*2);ctx.fill();
    ctx.fillStyle='#888';ctx.font='8px monospace';ctx.textAlign='center';
    ctx.fillText(h.ip.split('.').pop(),x,y+20);
    ctx.fillText(h.type.substring(0,10),x,y-14);
  });
  ctx.textAlign='start';
}

async function fetchCyber(){
  try{
    const r=await fetch('/api/cyber/status');
    const d=await r.json();
    // Stats
    $('s-net').textContent=d.wifi.length;
    $('s-host').textContent=d.hosts.length;
    $('s-vuln').textContent=d.vulns.length;
    $('s-ids').textContent=d.ids_alerts.length;
    // WiFi
    $('wlist').innerHTML=d.wifi.map(w=>{
      const bars=Math.min(4,Math.floor((w.sig+90)/12)+1);
      const bh=[5,10,15,20];
      const barsHtml=bh.map((h,i)=>`<div class="bar" style="height:${h}px;opacity:${i<bars?1:0.15}"></div>`).join('');
      return `<div class="wi"><div><span style="color:${w.suspicious?'#ff0044':'#00ff88'}">${w.suspicious?'⚠':'✓'} ${w.ssid||'[HIDDEN]'}</span><br><span style="color:#555;font-size:9px">${w.enc} · Ch${w.ch} · ${w.sig}dBm</span></div><div class="bars">${barsHtml}</div></div>`;
    }).join('');
    // Devices
    $('dtb').innerHTML=d.hosts.map(h=>{
      const sc=h.status==='scanning'?'color:#ffaa00':h.status==='up'?'color:#00ff88':'color:#ff0044';
      return `<tr><td style="color:#00ccff">${h.ip}</td><td>${h.type}</td><td style="color:#888">${h.os}</td><td style="color:#555">${h.ports}</td><td style="${sc}">${h.status}</td></tr>`;
    }).join('');
    // Vulns
    if(d.vulns.length>0){
      $('novuln').style.display='none';
      $('vtb').innerHTML=d.vulns.map(v=>{
        const sc=v.sev==='CRITICAL'?'c':v.sev==='HIGH'?'h':v.sev==='MEDIUM'?'m':'l';
        return `<tr><td>${v.cve}</td><td class="sc ${sc}">${v.sev}</td><td>${v.cvss||'—'}</td><td>${v.desc}</td><td style="color:#00ccff">${v.host}</td></tr>`;
      }).join('');
    }
    // IDS
    $('ids').innerHTML=d.ids_alerts.slice(0,25).map(a=>{
      const ts=(a.time||'').split('T')[1]||'';
      return `<div class="ia ${a.severity==='WARN'?'w':''}">[${ts.replace('Z','')}] <strong>${a.severity}</strong> — ${a.message}</div>`;
    }).join('');
    // Topology
    drawTopo(d.hosts);
  }catch(e){}
}
setInterval(fetchCyber,3000);
fetchCyber();
</script>
</body></html>
CYEOF
echo "  ✅ cyber.html (API-driven)"

# ═══════════════════════════════════════════════════
#  [4/4] DONE
# ═══════════════════════════════════════════════════
echo ""
echo "══════════════════════════════════════════════════════"
echo "  ✅ Phase 9.5 COMPLETE — Live Simulation Data"
echo "══════════════════════════════════════════════════════"
echo ""
echo "  Files created/modified:"
echo "    📄 sim_data_engine.py  — Scenario engine (Tampa Bay Interdiction)"
echo "    📄 c2_server.py        — 5 new API endpoints"
echo "    📄 ew.html             — API-driven EW dashboard"
echo "    📄 sigint.html         — API-driven SIGINT database"
echo "    📄 cyber.html          — API-driven Cyber Ops center"
echo ""
echo "  API Endpoints:"
echo "    GET /api/ew/emitters   — Emitter positions, classifications, stats"
echo "    GET /api/ew/spectrum   — 512-bin spectrum data (400-6000 MHz)"
echo "    GET /api/ew/alerts     — EW alert feed"
echo "    GET /api/sigint/signals — Signal intelligence database"
echo "    GET /api/cyber/status  — WiFi, hosts, vulns, IDS alerts"
echo ""
echo "  Scenario Timeline:"
echo "    T+0:00  Baseline (7 emitters, 5 WiFi, 10 hosts)"
echo "    T+1:00  Unknown FHSS contact over Tampa Bay"
echo "    T+1:30  AI classifies as drone C2 (87%)"
echo "    T+2:00  Confirmed HOSTILE"
echo "    T+2:30  GPS L1 JAMMING begins"
echo "    T+3:00  Second hostile drone (2.4 GHz)"
echo "    T+3:30  Suspicious WiFi + hidden AP"
echo "    T+4:00  DRONE SWARM (3 hostiles, LoRa)"
echo "    T+5:00  Cyber recon (port scan from rogue host)"
echo "    T+5:30  6 CVEs found (2 CRITICAL)"
echo "    T+6:00  Adversary comms net (3-node encrypted)"
echo "    T+7:00  GPS L1+L2 jamming intensified"
echo "    T+8:00  Hostile radar emission (5.8 GHz)"
echo "    T+9:00  WiFi deauth attack on mesh"
echo "    T+9:00+ Periodic alerts continue indefinitely"
echo ""
echo "  Restart now:"
echo "    cd ~/mos_ws && ./launch_mos.sh"
echo ""
echo "  Then open:"
echo "    http://localhost:5000/ew     ⚡ Watch the scenario unfold"
echo "    http://localhost:5000/sigint  📡 Signals populate over time"
echo "    http://localhost:5000/cyber   🔓 Cyber data builds up"
echo "══════════════════════════════════════════════════════"
