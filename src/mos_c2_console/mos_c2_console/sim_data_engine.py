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
