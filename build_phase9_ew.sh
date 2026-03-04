#!/bin/bash
set -e

R='\033[0;31m';G='\033[0;32m';Y='\033[1;33m';C='\033[0;36m';M='\033[0;35m';NC='\033[0m'
echo ""
echo -e "${R}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${R}║${NC}  ${M}⚡ MOS PHASE 9 — EW / SIGINT / CYBER WARFARE SUITE ⚡${NC}     ${R}║${NC}"
echo -e "${R}║${NC}  ${C}Signal Warrior Mode: ACTIVATED${NC}                              ${R}║${NC}"
echo -e "${R}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

WS=~/mos_ws

###############################################################################
# 1. CREATE PACKAGE STRUCTURE
###############################################################################
echo -e "${C}[PHASE 9] Creating mos_ew package...${NC}"
mkdir -p $WS/src/mos_ew/mos_ew
mkdir -p $WS/src/mos_ew/config
touch $WS/src/mos_ew/mos_ew/__init__.py

###############################################################################
# 2. PACKAGE SETUP
###############################################################################
cat > $WS/src/mos_ew/setup.py << 'SETUPEOF'
from setuptools import setup, find_packages
setup(
    name='mos_ew',
    version='9.0.0',
    packages=find_packages(),
    install_requires=['setuptools'],
    data_files=[
        ('share/mos_ew', ['package.xml']),
        ('share/mos_ew/config', ['config/ew_config.yaml']),
    ],
    entry_points={'console_scripts': [
        'ew_manager = mos_ew.ew_manager:main',
        'sigint_collector = mos_ew.sigint_collector:main',
        'cyber_ops = mos_ew.cyber_ops:main',
        'sdr_bridge = mos_ew.sdr_bridge:main',
        'rf_analyzer = mos_ew.rf_analyzer:main',
    ]},
)
SETUPEOF

cat > $WS/src/mos_ew/package.xml << 'PKGEOF'
<?xml version="1.0"?>
<package format="3">
  <name>mos_ew</name><version>9.0.0</version>
  <description>MOS Electronic Warfare / SIGINT / Cyber Suite</description>
  <maintainer email="ew@mavrix.dev">Mavrix Dynamics</maintainer>
  <license>Proprietary</license>
  <exec_depend>rclpy</exec_depend>
  <exec_depend>std_msgs</exec_depend>
  <buildtool_depend>ament_python</buildtool_depend>
  <export><build_type>ament_python</build_type></export>
</package>
PKGEOF

echo -e "${G}  [+] Package structure created${NC}"

###############################################################################
# 3. EW CONFIG — THE ARSENAL
###############################################################################
echo -e "${C}[PHASE 9] Writing EW configuration (the arsenal)...${NC}"
cat > $WS/src/mos_ew/config/ew_config.yaml << 'EWCFGEOF'
###############################################################################
# MOS EW/SIGINT/CYBER CONFIGURATION
# The complete electronic warfare arsenal configuration
###############################################################################
ew:
  # ── RF Environment Simulation ──────────────────────────────────────
  simulation:
    spectrum_bins: 512            # FFT bins for spectrum display
    update_rate_hz: 2.0           # Spectrum update rate
    noise_floor_dbm: -110         # Ambient noise floor
    center_freq_mhz: 450.0       # Default center frequency
    bandwidth_mhz: 100.0         # Default scan bandwidth
    emitter_spawn_rate_s: 8.0     # New emitter every N seconds
    max_emitters: 50              # Max tracked emitters

  # ── Signal Categories ──────────────────────────────────────────────
  signal_types:
    COMMS_VHF:
      freq_range: [30, 300]
      description: "VHF Voice/Data Communications"
      threat_weight: 0.6
      examples: ["Analog FM voice", "Marine VHF", "Air band"]
    COMMS_UHF:
      freq_range: [300, 3000]
      description: "UHF Tactical Communications"
      threat_weight: 0.8
      examples: ["SINCGARS", "Harris radios", "Motorola trunked"]
    COMMS_HF:
      freq_range: [3, 30]
      description: "HF Long-Range Communications"
      threat_weight: 0.5
      examples: ["ALE", "NVIS", "Shortwave broadcast"]
    WIFI:
      freq_range: [2400, 2500]
      freq_range_5g: [5150, 5850]
      description: "IEEE 802.11 WiFi"
      threat_weight: 0.4
      examples: ["802.11ax", "Mesh networks", "Drone WiFi C2"]
    BLUETOOTH:
      freq_range: [2402, 2480]
      description: "Bluetooth / BLE"
      threat_weight: 0.2
      examples: ["BLE beacons", "Audio devices", "IoT sensors"]
    CELLULAR:
      freq_range: [700, 2600]
      description: "Cellular LTE/5G/GSM"
      threat_weight: 0.7
      examples: ["LTE Band 14 FirstNet", "GSM 900", "5G NR"]
    RADAR:
      freq_range: [1000, 40000]
      description: "RADAR Emissions"
      threat_weight: 0.9
      examples: ["Search radar", "Fire control", "Weather radar"]
    DRONE_C2:
      freq_range: [900, 5800]
      description: "Drone Command & Control Links"
      threat_weight: 1.0
      examples: ["DJI OcuSync", "MAVLink telemetry", "FPV video"]
    GPS_INTERFERENCE:
      freq_range: [1575, 1576]
      description: "GPS L1 Interference/Spoofing"
      threat_weight: 1.0
      examples: ["GPS jammer", "GPS spoofer", "Meaconing"]
    ISM_BAND:
      freq_range: [902, 928]
      description: "ISM Band Devices"
      threat_weight: 0.1
      examples: ["LoRa", "Zigbee", "Z-Wave", "Baby monitors"]
    P25_DMR:
      freq_range: [136, 900]
      description: "Public Safety Trunked Radio"
      threat_weight: 0.3
      examples: ["P25 Phase I/II", "DMR Tier II/III", "NXDN"]
    SATCOM:
      freq_range: [1500, 30000]
      description: "Satellite Communications"
      threat_weight: 0.7
      examples: ["Iridium", "Inmarsat", "MUOS", "Starlink"]
    ADS_B:
      freq_range: [1090, 1090]
      description: "Aircraft Transponders"
      threat_weight: 0.1
      examples: ["ADS-B Out", "Mode S", "TCAS"]
    AIS:
      freq_range: [161, 162]
      description: "Maritime Vessel Tracking"
      threat_weight: 0.1
      examples: ["AIS Class A/B", "SAR transponder"]
    REMOTE_ID:
      freq_range: [2400, 2500]
      description: "FAA Remote ID Broadcast"
      threat_weight: 0.3
      examples: ["Standard Remote ID", "Broadcast Remote ID"]

  # ── Emitter Classification ─────────────────────────────────────────
  classifications:
    FRIENDLY:
      color: "#00ff00"
      response: "MONITOR"
      description: "Known friendly asset RF emission"
    NEUTRAL:
      color: "#ffff00"
      response: "LOG"
      description: "Civilian/commercial — no threat"
    SUSPECT:
      color: "#ff8800"
      response: "INVESTIGATE"
      description: "Unusual pattern or location"
    HOSTILE:
      color: "#ff0000"
      response: "TRACK_REPORT"
      description: "Confirmed threat emitter"
    JAMMER:
      color: "#ff00ff"
      response: "LOCATE_COUNTER"
      description: "Active electronic attack source"

  # ── Jamming Profiles ───────────────────────────────────────────────
  jamming_profiles:
    NOISE:
      description: "Broadband noise jamming"
      bandwidth_mhz: 20
      effectiveness: 0.7
      power_required_dbm: 33
    SPOT:
      description: "Narrowband spot jamming"
      bandwidth_mhz: 1
      effectiveness: 0.9
      power_required_dbm: 27
    SWEEP:
      description: "Swept frequency jamming"
      bandwidth_mhz: 50
      effectiveness: 0.5
      power_required_dbm: 36
    DECEPTIVE:
      description: "False signal injection"
      bandwidth_mhz: 5
      effectiveness: 0.8
      power_required_dbm: 20
    DRFM:
      description: "Digital RF Memory — radar spoofing"
      bandwidth_mhz: 10
      effectiveness: 0.95
      power_required_dbm: 30

  # ── EW Asset Payload Configuration ─────────────────────────────────
  # Which MOS assets carry EW payloads
  ew_assets:
    MVRX-A03:
      role: "SIGINT_PRIMARY"
      payloads: ["RTL-SDR", "HackRF", "DF_ARRAY"]
      capabilities: ["spectrum_monitor", "signal_classify", "direction_find"]
    MVRX-A04:
      role: "EW_ATTACK"
      payloads: ["HackRF", "USRP_B205"]
      capabilities: ["spectrum_monitor", "jamming", "spoofing_detect"]
    MVRX-A05:
      role: "CYBER_RECON"
      payloads: ["WIFI_ADAPTER", "RTL-SDR", "BT_ADAPTER"]
      capabilities: ["wifi_scan", "bt_scan", "spectrum_monitor", "deauth"]
    MVRX-G03:
      role: "GROUND_SIGINT"
      payloads: ["USRP_B205", "DF_ARRAY", "JETSON_DRAGONOS"]
      capabilities: ["spectrum_monitor", "signal_classify", "direction_find", "record"]
    MVRX-G04:
      role: "CYBER_GROUND"
      payloads: ["WIFI_PINEAPPLE", "PACKET_SQUIRREL", "RTL-SDR"]
      capabilities: ["wifi_scan", "network_tap", "mitm", "spectrum_monitor"]
    AWACS-1:
      role: "SIGINT_FUSION"
      payloads: ["USRP_X310", "DF_ARRAY", "SATCOM_RX"]
      capabilities: ["wideband_monitor", "signal_classify", "direction_find", "sigint_fusion"]
    AWACS-2:
      role: "EW_COORDINATOR"
      payloads: ["USRP_X310", "HackRF"]
      capabilities: ["wideband_monitor", "jamming_coord", "spectrum_deconflict"]

  # ── Hardware Payloads ──────────────────────────────────────────────
  payloads:
    RTL-SDR:
      name: "RTL-SDR v3/v4"
      weight_oz: 0.5
      freq_range_mhz: [0.5, 1766]
      bandwidth_mhz: 2.4
      sample_rate_msps: 2.4
      direction: "RX"
      interface: "USB"
      power_w: 0.5
      cost_usd: 30
      dragonos_tools: ["gqrx", "sdr++", "rtl_433", "dump1090", "multimon-ng"]
    HackRF:
      name: "HackRF One"
      weight_oz: 8
      freq_range_mhz: [1, 6000]
      bandwidth_mhz: 20
      sample_rate_msps: 20
      direction: "TX/RX"
      interface: "USB"
      power_w: 1.5
      cost_usd: 350
      dragonos_tools: ["gnu_radio", "gqrx", "sdr++", "inspectrum", "urh"]
    USRP_B205:
      name: "Ettus USRP B205mini-i"
      weight_oz: 5
      freq_range_mhz: [70, 6000]
      bandwidth_mhz: 56
      sample_rate_msps: 61.44
      direction: "TX/RX FULL_DUPLEX"
      interface: "USB 3.0"
      power_w: 3.0
      cost_usd: 1500
      dragonos_tools: ["gnu_radio", "osmo-bts", "gr-gsm", "srsRAN"]
    USRP_X310:
      name: "Ettus USRP X310"
      weight_oz: 80
      freq_range_mhz: [10, 6000]
      bandwidth_mhz: 160
      sample_rate_msps: 200
      direction: "TX/RX FULL_DUPLEX"
      interface: "10GbE / PCIe"
      power_w: 45
      cost_usd: 8000
      dragonos_tools: ["gnu_radio", "srsRAN", "osmo-bts"]
    WIFI_ADAPTER:
      name: "Alfa AWUS036ACH"
      weight_oz: 2
      freq_range_mhz: [2400, 5850]
      direction: "TX/RX"
      interface: "USB"
      power_w: 0.5
      cost_usd: 50
      tools: ["kismet", "aircrack-ng", "bettercap", "hcxdumptool"]
    WIFI_PINEAPPLE:
      name: "Hak5 WiFi Pineapple Mark VII"
      weight_oz: 3
      freq_range_mhz: [2400, 5850]
      direction: "TX/RX DUAL_RADIO"
      interface: "USB-C"
      power_w: 2.5
      cost_usd: 120
      tools: ["pineap", "recon", "evil_portal", "deauth"]
    PACKET_SQUIRREL:
      name: "Hak5 Packet Squirrel"
      weight_oz: 2
      interface: "Ethernet"
      power_w: 1.0
      cost_usd: 80
      tools: ["tcpdump", "nmap", "dns_spoof", "payload_inject"]
    BT_ADAPTER:
      name: "Sena UD100 Long Range BT"
      weight_oz: 1
      freq_range_mhz: [2402, 2480]
      direction: "TX/RX"
      interface: "USB"
      range_m: 300
      tools: ["bluehydra", "bettercap", "hcitool"]
    DF_ARRAY:
      name: "KerberosSDR 4-Ch Coherent"
      weight_oz: 12
      freq_range_mhz: [24, 1766]
      channels: 4
      interface: "USB"
      power_w: 2.0
      cost_usd: 500
      tools: ["krakensdr_doa", "direction_finding"]
    JETSON_DRAGONOS:
      name: "NVIDIA Jetson Orin Nano + DragonOS"
      weight_oz: 5
      interface: "USB/GPIO/PCIe"
      power_w: 15
      cost_usd: 500
      description: "Full AI-enabled SIGINT platform running DragonOS"
      tools: ["ALL_DRAGONOS_TOOLS", "tensorflow", "pytorch"]
    SATCOM_RX:
      name: "Nooelec SAWbird+ LNA + RTL-SDR"
      weight_oz: 3
      freq_range_mhz: [1525, 1559]
      direction: "RX"
      interface: "USB"
      power_w: 0.5
      cost_usd: 80
      tools: ["satdump", "gpredict", "satnogs"]

  # ── DragonOS Tool Inventory ────────────────────────────────────────
  dragonos_tools:
    # -- Spectrum & Reception --
    gnu_radio:
      name: "GNU Radio"
      category: "SIGNAL_PROCESSING"
      description: "Signal processing framework with flowgraph GUI"
      ros2_bridge: true
      binary: "gnuradio-companion"
      capabilities: ["demod", "decode", "filter", "analyze", "transmit"]
    gqrx:
      name: "GQRX"
      category: "RECEIVER"
      description: "SDR receiver with waterfall and audio"
      binary: "gqrx"
      remote_control: "tcp://127.0.0.1:7356"
      capabilities: ["receive", "waterfall", "record", "demod_fm_am_ssb"]
    sdr_plus_plus:
      name: "SDR++"
      category: "RECEIVER"
      description: "Modern cross-platform SDR receiver"
      binary: "sdrpp"
      capabilities: ["receive", "waterfall", "scanner", "multi_vfo"]
    cubicsdr:
      name: "CubicSDR"
      category: "RECEIVER"
      binary: "CubicSDR"
      capabilities: ["receive", "waterfall", "scanner"]
    # -- Decoders --
    sdr_trunk:
      name: "SDR Trunk"
      category: "DECODER"
      description: "Trunked radio decoder (P25, DMR, NXDN)"
      binary: "java -jar sdrtrunk.jar"
      capabilities: ["p25_decode", "dmr_decode", "nxdn_decode", "alias"]
    multimon_ng:
      name: "multimon-ng"
      category: "DECODER"
      description: "Multi-mode digital decoder"
      binary: "multimon-ng"
      capabilities: ["pocsag", "flex", "eas", "dtmf", "zvei", "afsk"]
    rtl_433:
      name: "rtl_433"
      category: "DECODER"
      description: "ISM band generic data receiver"
      binary: "rtl_433"
      json_output: true
      capabilities: ["weather_stations", "tire_pressure", "doorbells", "sensors"]
    dump1090:
      name: "dump1090"
      category: "DECODER"
      description: "ADS-B aircraft transponder decoder"
      binary: "dump1090-mutability"
      web_ui: "http://127.0.0.1:8080"
      json_api: "http://127.0.0.1:8080/data/aircraft.json"
      capabilities: ["adsb_decode", "mlat", "aircraft_tracking"]
    direwolf:
      name: "Direwolf"
      category: "DECODER"
      description: "AX.25 packet radio / APRS TNC"
      binary: "direwolf"
      capabilities: ["aprs", "packet_radio", "ax25", "kiss_tnc"]
      atak_integration: true
    # -- Analysis --
    inspectrum:
      name: "inspectrum"
      category: "ANALYSIS"
      description: "Signal analysis tool for recorded IQ data"
      binary: "inspectrum"
      capabilities: ["iq_analysis", "signal_identification", "timing"]
    urh:
      name: "Universal Radio Hacker"
      category: "ANALYSIS"
      description: "Protocol analysis and reverse engineering"
      binary: "urh"
      capabilities: ["protocol_reverse", "signal_generator", "fuzzing", "simulation"]
    sigdigger:
      name: "SigDigger"
      category: "ANALYSIS"
      binary: "SigDigger"
      capabilities: ["signal_analysis", "measurement", "inspection"]
    baudline:
      name: "Baudline"
      category: "ANALYSIS"
      description: "Time-frequency signal analyzer"
      binary: "baudline"
      capabilities: ["fft", "spectrogram", "histogram", "correlation"]
    # -- Satellite --
    gpredict:
      name: "GPredict"
      category: "SATELLITE"
      description: "Satellite tracking and prediction"
      binary: "gpredict"
      capabilities: ["sat_track", "pass_prediction", "doppler", "rotor_control"]
    satdump:
      name: "SatDump"
      category: "SATELLITE"
      description: "Satellite data decoder (NOAA, GOES, Meteor)"
      binary: "satdump"
      capabilities: ["weather_sat", "image_decode", "live_decode"]
    # -- Network/Cyber --
    kismet:
      name: "Kismet"
      category: "CYBER"
      description: "Wireless network detector and sniffer"
      binary: "kismet"
      rest_api: "http://127.0.0.1:2501"
      capabilities: ["wifi_detect", "bt_detect", "zigbee", "mousejack", "rtl433"]
    aircrack_ng:
      name: "Aircrack-ng Suite"
      category: "CYBER"
      description: "WiFi security assessment toolkit"
      binary: "aircrack-ng"
      capabilities: ["monitor_mode", "packet_capture", "deauth", "wpa_crack", "wep_crack"]
    bettercap:
      name: "Bettercap"
      category: "CYBER"
      description: "Network attack and monitoring framework"
      binary: "bettercap"
      web_ui: "http://127.0.0.1:80"
      capabilities: ["arp_spoof", "dns_spoof", "wifi_recon", "bt_recon", "hid_attack"]
    nmap:
      name: "Nmap"
      category: "CYBER"
      description: "Network discovery and security auditing"
      binary: "nmap"
      capabilities: ["host_discover", "port_scan", "os_detect", "vuln_scan", "scripting"]
    wireshark:
      name: "Wireshark/tshark"
      category: "CYBER"
      description: "Network protocol analyzer"
      binary: "wireshark"
      cli: "tshark"
      capabilities: ["packet_capture", "protocol_decode", "stream_follow", "statistics"]
    # -- Cellular --
    gr_gsm:
      name: "gr-gsm"
      category: "CELLULAR"
      description: "GSM signal decoder for GNU Radio"
      binary: "grgsm_livemon"
      capabilities: ["gsm_decode", "cell_search", "imsi_collect", "sms_decode"]
    kalibrate:
      name: "kalibrate-rtl"
      category: "CELLULAR"
      description: "GSM tower frequency scanner/calibrator"
      binary: "kal"
      capabilities: ["gsm_scan", "freq_calibrate", "tower_locate"]
    srsran:
      name: "srsRAN"
      category: "CELLULAR"
      description: "Open-source 4G/5G software radio suite"
      binary: "srsenb"
      capabilities: ["lte_cell", "lte_ue", "5g_gnb", "core_network"]
    # -- Direction Finding --
    krakensdr:
      name: "KrakenSDR DOA"
      category: "DIRECTION_FINDING"
      description: "Coherent multi-channel direction finding"
      binary: "krakensdr_doa"
      web_ui: "http://127.0.0.1:8042"
      capabilities: ["aoa_estimate", "tdoa", "heatmap", "emitter_locate"]
    # -- Counter-UAS --
    droneid_decoder:
      name: "DJI DroneID Decoder"
      category: "COUNTER_UAS"
      description: "Decode DJI drone identification broadcasts"
      binary: "dji_droneid"
      capabilities: ["dji_detect", "serial_extract", "pilot_locate", "flight_path"]
    remoteid_rx:
      name: "RemoteID Receiver"
      category: "COUNTER_UAS"
      description: "FAA Remote ID broadcast receiver"
      binary: "remoteid_rx"
      capabilities: ["remoteid_decode", "uas_track", "operator_locate"]

  # ── Cyber Operations Config ────────────────────────────────────────
  cyber:
    scan_interval_s: 15.0
    wifi_channels: [1, 6, 11, 36, 40, 44, 48, 149, 153, 157, 161]
    bt_scan_duration_s: 10
    network_scan_range: "10.0.0.0/24"
    vuln_scan_enabled: true
    ids_enabled: true             # Intrusion Detection System
    ros2_dds_monitor: true        # Monitor ROS 2 DDS for anomalies
    honeypot_enabled: false       # Honeypot services
    auto_deauth_hostile: false    # Auto-deauth hostile drone WiFi (DANGEROUS)

  # ── Direction Finding ──────────────────────────────────────────────
  direction_finding:
    method: "AOA"                 # AOA (Angle of Arrival) or TDOA
    min_assets_for_fix: 2         # Minimum DF assets for geolocation
    bearing_accuracy_deg: 5.0     # Simulated bearing accuracy
    update_rate_hz: 1.0
    geolocation_algorithm: "triangulation"  # triangulation | least_squares

EWCFGEOF
echo -e "${G}  [+] EW Config written (complete arsenal inventory)${NC}"

###############################################################################
# 4. NODE: EW MANAGER
###############################################################################
echo -e "${C}[PHASE 9] Writing EW Manager node...${NC}"
cat > $WS/src/mos_ew/mos_ew/ew_manager.py << 'EWMGREOF'
#!/usr/bin/env python3
"""
MOS EW Manager — Electronic Warfare Operations Center
Orchestrates all EW/SIGINT/Cyber operations across the platoon.
Manages jamming zones, EW missions, RF environment status, and coordinates
EW-capable assets for maximum electromagnetic spectrum dominance.
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, time, random, math

class EWManager(Node):
    def __init__(self):
        super().__init__('ew_manager')
        # Publishers
        self.status_pub = self.create_publisher(String, '/mos/ew/status', 10)
        self.jamming_pub = self.create_publisher(String, '/mos/ew/jamming', 10)
        self.ew_cop_pub = self.create_publisher(String, '/mos/ew/cop', 10)
        self.ew_alert_pub = self.create_publisher(String, '/mos/ew/alerts', 10)
        # Subscribers
        self.create_subscription(String, '/mos/ew/emitters', self._on_emitter, 10)
        self.create_subscription(String, '/mos/ew/command', self._on_command, 10)
        self.create_subscription(String, '/mos/heartbeat', self._on_heartbeat, 10)
        self.create_subscription(String, '/mos/ew/spectrum', self._on_spectrum, 10)
        self.create_subscription(String, '/mos/cyber/alerts', self._on_cyber_alert, 10)
        self.create_subscription(String, '/mos/sdr/status', self._on_sdr_status, 10)
        # State
        self.emitters = {}
        self.jamming_zones = []
        self.active_ops = []
        self.ew_assets = {}
        self.sdr_hardware = {}
        self.cyber_alerts = []
        self.spectrum_snapshot = None
        self.stats = {'emitters_total': 0, 'emitters_hostile': 0,
                      'signals_classified': 0, 'jam_activations': 0}
        # EW-capable assets defined in config
        self.ew_asset_ids = ['MVRX-A03','MVRX-A04','MVRX-A05',
                             'MVRX-G03','MVRX-G04','AWACS-1','AWACS-2']
        # Timers
        self.create_timer(2.0, self._publish_status)
        self.create_timer(5.0, self._publish_cop)
        self.create_timer(10.0, self._assess_rf_threats)
        self.get_logger().info('='*60)
        self.get_logger().info('  ⚡ EW MANAGER ONLINE — ELECTROMAGNETIC DOMINANCE ⚡')
        self.get_logger().info('='*60)

    def _on_heartbeat(self, msg):
        d = json.loads(msg.data)
        aid = d.get('asset_id','')
        if aid in self.ew_asset_ids:
            self.ew_assets[aid] = {
                'asset_id': aid, 'lat': d.get('lat',0), 'lon': d.get('lon',0),
                'alt': d.get('alt',0), 'battery': d.get('battery',0),
                'status': d.get('status','UNKNOWN'), 'last_seen': time.time()
            }

    def _on_emitter(self, msg):
        d = json.loads(msg.data)
        eid = d.get('emitter_id','')
        self.emitters[eid] = d
        self.stats['emitters_total'] = len(self.emitters)
        if d.get('classification') in ['HOSTILE','JAMMER']:
            self.stats['emitters_hostile'] = sum(
                1 for e in self.emitters.values()
                if e.get('classification') in ['HOSTILE','JAMMER'])
            self._publish_alert('THREAT_EMITTER', d)
        if d.get('classification') == 'JAMMER':
            self._publish_alert('JAMMING_DETECTED', d)

    def _on_command(self, msg):
        d = json.loads(msg.data)
        action = d.get('action','')
        if action == 'START_JAM':
            zone = {
                'id': f"JAM-{len(self.jamming_zones)+1:03d}",
                'profile': d.get('profile','NOISE'),
                'center_freq_mhz': d.get('freq_mhz', 462.0),
                'bandwidth_mhz': d.get('bandwidth_mhz', 5.0),
                'lat': d.get('lat', 27.85), 'lon': d.get('lon', -82.52),
                'radius_m': d.get('radius_m', 500),
                'power_dbm': d.get('power_dbm', 30),
                'assigned_asset': d.get('asset_id','MVRX-A04'),
                'active': True, 'start_time': time.time()
            }
            self.jamming_zones.append(zone)
            self.stats['jam_activations'] += 1
            out = String(); out.data = json.dumps({'type':'JAM_ACTIVATE','zone':zone})
            self.jamming_pub.publish(out)
            self.get_logger().warn(f'⚡ JAMMING ACTIVE: {zone["id"]} | '
                                   f'{zone["center_freq_mhz"]} MHz | '
                                   f'{zone["profile"]} | Asset: {zone["assigned_asset"]}')
        elif action == 'STOP_JAM':
            jid = d.get('jam_id','')
            for z in self.jamming_zones:
                if z['id'] == jid:
                    z['active'] = False
                    self.get_logger().info(f'Jamming zone {jid} deactivated')
        elif action == 'START_SCAN':
            op = {'id': f"OP-{len(self.active_ops)+1:03d}", 'type': 'SPECTRUM_SCAN',
                  'asset': d.get('asset_id','MVRX-A03'),
                  'freq_start': d.get('freq_start', 400),
                  'freq_end': d.get('freq_end', 500),
                  'start_time': time.time(), 'status': 'ACTIVE'}
            self.active_ops.append(op)
        elif action == 'DF_LOCATE':
            target_eid = d.get('emitter_id','')
            if target_eid in self.emitters:
                op = {'id': f"OP-{len(self.active_ops)+1:03d}", 'type': 'DF_LOCATE',
                      'target': target_eid, 'status': 'ACTIVE',
                      'assigned_assets': d.get('assets', list(self.ew_assets.keys())[:3]),
                      'start_time': time.time()}
                self.active_ops.append(op)

    def _on_spectrum(self, msg):
        self.spectrum_snapshot = json.loads(msg.data)

    def _on_cyber_alert(self, msg):
        d = json.loads(msg.data)
        self.cyber_alerts.append(d)
        if len(self.cyber_alerts) > 100:
            self.cyber_alerts = self.cyber_alerts[-100:]

    def _on_sdr_status(self, msg):
        d = json.loads(msg.data)
        self.sdr_hardware = d

    def _assess_rf_threats(self):
        hostile = [e for e in self.emitters.values()
                   if e.get('classification') in ['HOSTILE','JAMMER','SUSPECT']]
        if len(hostile) > 3:
            self._publish_alert('HIGH_RF_THREAT_DENSITY',
                {'count': len(hostile), 'message': f'{len(hostile)} threat/suspect emitters active'})
        jammers = [e for e in self.emitters.values() if e.get('classification') == 'JAMMER']
        for j in jammers:
            if j.get('signal_type') == 'GPS_INTERFERENCE':
                self._publish_alert('GPS_THREAT',
                    {'emitter': j, 'message': 'GPS interference detected — check navigation'})

    def _publish_alert(self, alert_type, data):
        alert = {'timestamp': time.time(), 'type': alert_type, 'data': data,
                 'severity': 'CRITICAL' if 'JAMMER' in alert_type or 'GPS' in alert_type else 'WARNING'}
        msg = String(); msg.data = json.dumps(alert)
        self.ew_alert_pub.publish(msg)
        self.get_logger().warn(f'⚠ EW ALERT: {alert_type}')

    def _publish_status(self):
        status = {
            'timestamp': time.time(),
            'ew_assets_online': len([a for a in self.ew_assets.values()
                                     if time.time()-a.get('last_seen',0)<10]),
            'ew_assets': list(self.ew_assets.values()),
            'total_emitters': len(self.emitters),
            'hostile_emitters': self.stats['emitters_hostile'],
            'active_jamming': [z for z in self.jamming_zones if z.get('active')],
            'active_operations': [o for o in self.active_ops if o.get('status')=='ACTIVE'],
            'sdr_hardware': self.sdr_hardware,
            'readiness': 'GREEN' if len(self.ew_assets) >= 3 else
                         'AMBER' if len(self.ew_assets) >= 1 else 'RED',
            'stats': self.stats
        }
        msg = String(); msg.data = json.dumps(status)
        self.status_pub.publish(msg)

    def _publish_cop(self):
        cop = {
            'timestamp': time.time(),
            'emitters': list(self.emitters.values()),
            'jamming_zones': [z for z in self.jamming_zones if z.get('active')],
            'ew_assets': list(self.ew_assets.values()),
            'rf_environment': 'CONTESTED' if self.stats['emitters_hostile']>2 else
                              'DEGRADED' if self.stats['emitters_hostile']>0 else 'PERMISSIVE',
            'spectrum': self.spectrum_snapshot
        }
        msg = String(); msg.data = json.dumps(cop)
        self.ew_cop_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = EWManager()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node()
EWMGREOF
echo -e "${G}  [+] EW Manager node${NC}"

###############################################################################
# 5. NODE: SIGINT COLLECTOR
###############################################################################
echo -e "${C}[PHASE 9] Writing SIGINT Collector node...${NC}"
cat > $WS/src/mos_ew/mos_ew/sigint_collector.py << 'SIGEOF'
#!/usr/bin/env python3
"""
MOS SIGINT Collector — Signals Intelligence Collection & Classification
Detects, classifies, and geolocates RF emitters across the spectrum.
Simulates realistic RF environment with known and unknown signals.
Supports direction finding via multi-asset angle-of-arrival.
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, time, random, math, hashlib

SIGNAL_TYPES = [
    {'type':'COMMS_VHF','freq':(136,174),'bw':(0.012,0.025),'power':(-60,-30),'threat':0.6},
    {'type':'COMMS_UHF','freq':(400,512),'bw':(0.025,0.1),'power':(-70,-35),'threat':0.8},
    {'type':'WIFI','freq':(2412,2462),'bw':(20,40),'power':(-80,-40),'threat':0.4},
    {'type':'WIFI_5G','freq':(5180,5825),'bw':(40,80),'power':(-85,-50),'threat':0.4},
    {'type':'BLUETOOTH','freq':(2402,2480),'bw':(1,2),'power':(-90,-60),'threat':0.2},
    {'type':'CELLULAR','freq':(700,900),'bw':(10,20),'power':(-65,-30),'threat':0.5},
    {'type':'CELLULAR_AWS','freq':(1700,2100),'bw':(10,20),'power':(-65,-30),'threat':0.5},
    {'type':'RADAR','freq':(2700,3500),'bw':(1,5),'power':(-50,-10),'threat':0.9},
    {'type':'DRONE_C2','freq':(900,930),'bw':(0.5,2),'power':(-75,-45),'threat':1.0},
    {'type':'DRONE_C2_5G','freq':(5725,5850),'bw':(10,20),'power':(-70,-40),'threat':1.0},
    {'type':'DRONE_VIDEO','freq':(5800,5900),'bw':(20,40),'power':(-65,-35),'threat':0.9},
    {'type':'GPS_INTERFERENCE','freq':(1575.42,1575.42),'bw':(1,10),'power':(-50,-20),'threat':1.0},
    {'type':'ISM_LORA','freq':(902,928),'bw':(0.125,0.5),'power':(-100,-70),'threat':0.1},
    {'type':'P25','freq':(764,870),'bw':(0.0125,0.0125),'power':(-70,-40),'threat':0.3},
    {'type':'DMR','freq':(400,470),'bw':(0.0125,0.0125),'power':(-70,-35),'threat':0.3},
    {'type':'ADS_B','freq':(1090,1090),'bw':(0.05,0.05),'power':(-60,-20),'threat':0.1},
    {'type':'AIS','freq':(161.975,162.025),'bw':(0.025,0.025),'power':(-70,-30),'threat':0.1},
    {'type':'SATCOM_DL','freq':(1525,1559),'bw':(0.025,0.2),'power':(-120,-90),'threat':0.5},
    {'type':'REMOTE_ID','freq':(2400,2484),'bw':(1,5),'power':(-80,-55),'threat':0.3},
    {'type':'UNKNOWN','freq':(100,5900),'bw':(0.1,5),'power':(-90,-50),'threat':0.7},
]

CLASSIFICATIONS = ['FRIENDLY','NEUTRAL','SUSPECT','HOSTILE','JAMMER']
CLASS_WEIGHTS = [0.20, 0.35, 0.25, 0.15, 0.05]

MODULATIONS = ['FM','AM','SSB','OFDM','FHSS','DSSS','FSK','GFSK','QAM','PSK','CHIRP','PULSE','UNKNOWN']

BASE_LAT, BASE_LON = 27.8506, -82.5214

class SIGINTCollector(Node):
    def __init__(self):
        super().__init__('sigint_collector')
        self.emitter_pub = self.create_publisher(String, '/mos/ew/emitters', 10)
        self.signal_pub = self.create_publisher(String, '/mos/ew/signals', 10)
        self.bearing_pub = self.create_publisher(String, '/mos/ew/bearings', 10)
        self.create_subscription(String, '/mos/heartbeat', self._on_heartbeat, 10)
        self.emitters = {}
        self.signal_db = []
        self.asset_positions = {}
        self.emitter_counter = 0
        self.create_timer(8.0, self._spawn_emitter)
        self.create_timer(3.0, self._update_emitters)
        self.create_timer(5.0, self._compute_bearings)
        self.create_timer(2.0, self._classify_signals)
        self.get_logger().info('📡 SIGINT Collector online — Listening across the spectrum...')

    def _on_heartbeat(self, msg):
        d = json.loads(msg.data)
        self.asset_positions[d.get('asset_id','')] = {
            'lat': d.get('lat',0), 'lon': d.get('lon',0), 'alt': d.get('alt',0)}

    def _spawn_emitter(self):
        if len(self.emitters) >= 50:
            oldest = min(self.emitters, key=lambda k: self.emitters[k].get('first_seen',0))
            del self.emitters[oldest]
        sig = random.choice(SIGNAL_TYPES)
        self.emitter_counter += 1
        freq = random.uniform(sig['freq'][0], sig['freq'][1])
        eid = f"EMT-{self.emitter_counter:04d}"
        classification = random.choices(CLASSIFICATIONS, CLASS_WEIGHTS)[0]
        # Hostile emitters spawn closer; neutral farther
        dist_km = random.uniform(0.1, 1.0) if classification in ['HOSTILE','JAMMER'] \
                  else random.uniform(0.5, 5.0)
        angle = random.uniform(0, 2*math.pi)
        lat = BASE_LAT + (dist_km/111.0)*math.cos(angle)
        lon = BASE_LON + (dist_km/(111.0*math.cos(math.radians(BASE_LAT))))*math.sin(angle)
        emitter = {
            'emitter_id': eid,
            'signal_type': sig['type'],
            'classification': classification,
            'freq_mhz': round(freq, 4),
            'bandwidth_mhz': round(random.uniform(sig['bw'][0], sig['bw'][1]), 4),
            'power_dbm': round(random.uniform(sig['power'][0], sig['power'][1]), 1),
            'modulation': random.choice(MODULATIONS),
            'lat': round(lat, 6), 'lon': round(lon, 6),
            'alt_m': random.uniform(0, 100) if 'DRONE' in sig['type'] else 0,
            'heading': round(random.uniform(0, 360), 1),
            'speed_mps': round(random.uniform(0, 15), 1) if classification in ['HOSTILE','SUSPECT'] else 0,
            'threat_score': round(sig['threat'] * (1.5 if classification == 'HOSTILE' else
                                  2.0 if classification == 'JAMMER' else 1.0), 2),
            'first_seen': time.time(),
            'last_seen': time.time(),
            'confidence': round(random.uniform(0.5, 0.99), 2),
            'geolocation_fix': random.choice(['NONE','ROUGH','GOOD','PRECISE']),
            'detected_by': random.choice(list(self.asset_positions.keys())) if self.asset_positions else 'MVRX-A03',
            'notes': self._generate_notes(sig['type'], classification)
        }
        self.emitters[eid] = emitter
        msg = String(); msg.data = json.dumps(emitter)
        self.emitter_pub.publish(msg)
        icon = '🔴' if classification in ['HOSTILE','JAMMER'] else '🟡' if classification == 'SUSPECT' else '🟢'
        self.get_logger().info(f'{icon} EMITTER {eid}: {sig["type"]} | {freq:.3f} MHz | '
                               f'{emitter["power_dbm"]} dBm | {classification}')

    def _generate_notes(self, sig_type, classification):
        notes = {
            'DRONE_C2': 'Possible hostile UAS command link detected',
            'DRONE_VIDEO': 'FPV video downlink — likely surveillance drone',
            'GPS_INTERFERENCE': 'GPS L1 interference — check navigation integrity',
            'RADAR': 'Search radar emission — possible air defense',
            'COMMS_UHF': 'UHF tactical comms — monitoring for COMSEC violations',
            'WIFI': 'WiFi AP detected — potential network entry point',
            'CELLULAR': 'Cellular emission — may indicate personnel with phones',
            'P25': 'P25 trunked radio — law enforcement or security',
            'UNKNOWN': 'Unclassified emission — requires analysis',
        }
        base = notes.get(sig_type, f'{sig_type} emission detected')
        if classification == 'HOSTILE': base += ' [CONFIRMED HOSTILE]'
        if classification == 'JAMMER': base += ' [ACTIVE JAMMING SOURCE]'
        return base

    def _update_emitters(self):
        now = time.time()
        to_remove = []
        for eid, e in self.emitters.items():
            age = now - e['first_seen']
            if age > 120 and random.random() < 0.1:
                to_remove.append(eid)
                continue
            # Mobile emitters move
            if e.get('speed_mps', 0) > 0:
                hdg_rad = math.radians(e['heading'])
                dt = 3.0
                dlat = (e['speed_mps'] * dt / 111000.0) * math.cos(hdg_rad)
                dlon = (e['speed_mps'] * dt / (111000.0 * math.cos(math.radians(e['lat'])))) * math.sin(hdg_rad)
                e['lat'] += dlat
                e['lon'] += dlon
                e['heading'] = (e['heading'] + random.uniform(-10, 10)) % 360
            # Power fluctuation
            e['power_dbm'] += random.uniform(-2, 2)
            e['last_seen'] = now
            msg = String(); msg.data = json.dumps(e)
            self.emitter_pub.publish(msg)
        for eid in to_remove:
            del self.emitters[eid]

    def _compute_bearings(self):
        ew_assets = {k:v for k,v in self.asset_positions.items()
                     if k in ['MVRX-A03','MVRX-G03','AWACS-1','AWACS-2']}
        if not ew_assets: return
        hostile = [e for e in self.emitters.values()
                   if e.get('classification') in ['HOSTILE','JAMMER','SUSPECT']]
        bearings = []
        for e in hostile[:10]:
            for aid, apos in ew_assets.items():
                dlat = e['lat'] - apos['lat']
                dlon = e['lon'] - apos['lon']
                true_bearing = math.degrees(math.atan2(dlon, dlat)) % 360
                measured = (true_bearing + random.uniform(-5, 5)) % 360
                bearings.append({
                    'emitter_id': e['emitter_id'], 'asset_id': aid,
                    'bearing_deg': round(measured, 1),
                    'from_lat': apos['lat'], 'from_lon': apos['lon'],
                    'timestamp': time.time()
                })
        if bearings:
            msg = String(); msg.data = json.dumps({'bearings': bearings})
            self.bearing_pub.publish(msg)

    def _classify_signals(self):
        for eid, e in list(self.emitters.items()):
            signal = {
                'signal_id': f"SIG-{hashlib.md5(eid.encode()).hexdigest()[:8]}",
                'emitter_id': eid,
                'freq_mhz': e['freq_mhz'],
                'bandwidth_mhz': e['bandwidth_mhz'],
                'power_dbm': e['power_dbm'],
                'modulation': e['modulation'],
                'signal_type': e['signal_type'],
                'classification': e['classification'],
                'threat_score': e['threat_score'],
                'timestamp': time.time()
            }
            self.signal_db.append(signal)
            if len(self.signal_db) > 500:
                self.signal_db = self.signal_db[-500:]
            msg = String(); msg.data = json.dumps(signal)
            self.signal_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = SIGINTCollector()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node()
SIGEOF
echo -e "${G}  [+] SIGINT Collector node${NC}"

###############################################################################
# 6. NODE: CYBER OPS
###############################################################################
echo -e "${C}[PHASE 9] Writing Cyber Operations node...${NC}"
cat > $WS/src/mos_ew/mos_ew/cyber_ops.py << 'CYBEREOF'
#!/usr/bin/env python3
"""
MOS Cyber Operations — Network Recon, WiFi/BT Assessment, IDS
Simulates network discovery, wireless environment assessment,
vulnerability scanning, and intrusion detection across the AO.
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, time, random, hashlib

WIFI_VENDORS = ['Netgear','TP-Link','Cisco','Ubiquiti','DJI','Aruba','Meraki',
                'Samsung','Apple','Huawei','ZTE','MikroTik','Ruckus']
WIFI_SSIDS = ['SETUP-HOME','linksys','ATT-WIFI','NETGEAR5G','DJI-PHANTOM-C2',
              'Hidden','xfinitywifi','DIRECT-drone','MeshNode','TacticalNet',
              'CampWiFi','Guard-Shack','TOC-NET','hotel-guest','OPSEC_VIOLATION',
              'iPhone-12','AndroidAP','Starlink-Router','']
BT_DEVICES = ['AirPods Pro','Galaxy Buds','Fitbit','Apple Watch','Tile Tracker',
              'JBL Speaker','DJI Controller','Garmin GPS','Tactical PTT','Unknown BLE']
VULNS = [
    {'id':'CVE-2024-0001','name':'WPA2 KRACK','severity':'HIGH','service':'WiFi'},
    {'id':'CVE-2024-0002','name':'UPnP Buffer Overflow','severity':'CRITICAL','service':'UPnP'},
    {'id':'CVE-2024-0003','name':'Default Credentials','severity':'HIGH','service':'HTTP/SSH'},
    {'id':'CVE-2024-0004','name':'DNS Rebinding','severity':'MEDIUM','service':'DNS'},
    {'id':'CVE-2024-0005','name':'MAVLink No Auth','severity':'CRITICAL','service':'MAVLink'},
    {'id':'CVE-2024-0006','name':'DDS Open Discovery','severity':'HIGH','service':'ROS2-DDS'},
    {'id':'CVE-2024-0007','name':'Telnet Open','severity':'CRITICAL','service':'Telnet'},
    {'id':'CVE-2024-0008','name':'SNMP Public Community','severity':'MEDIUM','service':'SNMP'},
    {'id':'CVE-2024-0009','name':'FTP Anonymous','severity':'HIGH','service':'FTP'},
    {'id':'CVE-2024-0010','name':'Unencrypted Video Stream','severity':'HIGH','service':'RTSP'},
]
IDS_EVENTS = [
    'Port scan detected from {ip}',
    'Brute force SSH attempt from {ip}',
    'ARP spoofing detected on segment',
    'Rogue DHCP server detected at {ip}',
    'DDS participant from unknown host {ip}',
    'MAVLink heartbeat from unregistered system',
    'Deauthentication flood detected on WiFi channel {ch}',
    'DNS tunnel traffic pattern detected',
    'Suspicious beacon frame — possible Evil Twin AP',
    'Unauthorized RemoteID broadcast modification attempt',
]

class CyberOps(Node):
    def __init__(self):
        super().__init__('cyber_ops')
        self.net_pub = self.create_publisher(String, '/mos/cyber/networks', 10)
        self.dev_pub = self.create_publisher(String, '/mos/cyber/devices', 10)
        self.vuln_pub = self.create_publisher(String, '/mos/cyber/vulns', 10)
        self.alert_pub = self.create_publisher(String, '/mos/cyber/alerts', 10)
        self.status_pub = self.create_publisher(String, '/mos/cyber/status', 10)
        self.networks = {}
        self.devices = {}
        self.vulns_found = []
        self.alerts = []
        self.scan_count = 0
        self.create_timer(12.0, self._discover_network)
        self.create_timer(8.0, self._scan_wifi)
        self.create_timer(15.0, self._scan_bluetooth)
        self.create_timer(20.0, self._vuln_scan)
        self.create_timer(10.0, self._ids_check)
        self.create_timer(5.0, self._publish_status)
        self.get_logger().info('🔓 Cyber Operations online — scanning all domains...')

    def _rand_mac(self):
        return ':'.join(f'{random.randint(0,255):02x}' for _ in range(6))

    def _rand_ip(self):
        return f'10.{random.randint(0,5)}.{random.randint(0,255)}.{random.randint(1,254)}'

    def _discover_network(self):
        self.scan_count += 1
        n_hosts = random.randint(1, 4)
        for _ in range(n_hosts):
            ip = self._rand_ip()
            mac = self._rand_mac()
            device = {
                'ip': ip, 'mac': mac,
                'hostname': random.choice(['laptop','drone-ctrl','router','camera',
                                           'iot-sensor','phone','server','switch',
                                           'ap','printer','unknown']),
                'os': random.choice(['Linux','Windows','Android','iOS','RouterOS',
                                     'DJI FW','Embedded','Unknown']),
                'open_ports': sorted(random.sample(
                    [22,23,53,80,443,554,1883,3389,5353,5760,8080,8554,14550,14555,47100],
                    random.randint(1,5))),
                'vendor': random.choice(WIFI_VENDORS + ['Dell','Raspberry Pi','Unknown']),
                'first_seen': time.time(),
                'risk': random.choice(['LOW','MEDIUM','HIGH','CRITICAL']),
            }
            self.devices[ip] = device
        if len(self.devices) > 60:
            oldest = sorted(self.devices.keys(),
                          key=lambda k: self.devices[k].get('first_seen',0))[:10]
            for k in oldest: del self.devices[k]
        msg = String()
        msg.data = json.dumps({'scan_id': self.scan_count,
                               'hosts_found': len(self.devices),
                               'new_hosts': n_hosts,
                               'devices': list(self.devices.values())[-n_hosts:]})
        self.net_pub.publish(msg)
        self.get_logger().info(f'🌐 Network scan #{self.scan_count}: '
                               f'{len(self.devices)} hosts tracked, {n_hosts} new')

    def _scan_wifi(self):
        n = random.randint(1, 3)
        for _ in range(n):
            bssid = self._rand_mac()
            net = {
                'bssid': bssid,
                'ssid': random.choice(WIFI_SSIDS),
                'channel': random.choice([1,6,11,36,40,44,48,149,153,157,161]),
                'signal_dbm': random.randint(-90, -30),
                'security': random.choice(['WPA3','WPA2','WPA','WEP','OPEN']),
                'vendor': random.choice(WIFI_VENDORS),
                'clients': random.randint(0, 12),
                'band': '5GHz' if random.random() > 0.5 else '2.4GHz',
                'first_seen': time.time(),
                'threat_level': 'NONE',
            }
            if net['security'] in ['WEP','OPEN']:
                net['threat_level'] = 'SUSPECT'
            if 'DJI' in net['ssid'] or 'drone' in net['ssid'].lower():
                net['threat_level'] = 'HIGH'
            if net['ssid'] == '':
                net['threat_level'] = 'SUSPECT'
                net['ssid'] = '[HIDDEN]'
            self.networks[bssid] = net
        if len(self.networks) > 40:
            oldest = sorted(self.networks.keys(),
                          key=lambda k: self.networks[k].get('first_seen',0))[:5]
            for k in oldest: del self.networks[k]
        msg = String()
        msg.data = json.dumps({'wifi_networks': list(self.networks.values())[-n:]})
        self.net_pub.publish(msg)

    def _scan_bluetooth(self):
        n = random.randint(0, 3)
        for _ in range(n):
            dev = {
                'mac': self._rand_mac(), 'name': random.choice(BT_DEVICES),
                'type': random.choice(['BLE','Classic','Dual']),
                'rssi': random.randint(-100, -40),
                'manufacturer': random.choice(['Apple','Samsung','Tile','Garmin','Unknown']),
                'connectable': random.choice([True, False]),
                'first_seen': time.time(),
            }
            msg = String(); msg.data = json.dumps({'bt_device': dev})
            self.dev_pub.publish(msg)

    def _vuln_scan(self):
        if not self.devices: return
        target = random.choice(list(self.devices.values()))
        if random.random() < 0.4:
            vuln = random.choice(VULNS).copy()
            vuln['target_ip'] = target['ip']
            vuln['target_host'] = target['hostname']
            vuln['found_at'] = time.time()
            vuln['status'] = 'OPEN'
            self.vulns_found.append(vuln)
            if len(self.vulns_found) > 100:
                self.vulns_found = self.vulns_found[-100:]
            msg = String(); msg.data = json.dumps(vuln)
            self.vuln_pub.publish(msg)
            self.get_logger().warn(f'🔴 VULN: {vuln["id"]} ({vuln["severity"]}) — '
                                   f'{vuln["name"]} on {target["ip"]}')

    def _ids_check(self):
        if random.random() < 0.3:
            template = random.choice(IDS_EVENTS)
            alert = {
                'timestamp': time.time(),
                'event': template.format(ip=self._rand_ip(), ch=random.choice([1,6,11])),
                'severity': random.choice(['LOW','MEDIUM','HIGH','CRITICAL']),
                'source': random.choice(['IDS','WiFi_Monitor','DDS_Monitor','ARP_Watch']),
                'action_taken': random.choice(['LOGGED','BLOCKED','ALERT_SENT']),
            }
            self.alerts.append(alert)
            if len(self.alerts) > 200:
                self.alerts = self.alerts[-200:]
            msg = String(); msg.data = json.dumps(alert)
            self.alert_pub.publish(msg)
            self.get_logger().warn(f'🛡 IDS: {alert["event"]} [{alert["severity"]}]')

    def _publish_status(self):
        status = {
            'timestamp': time.time(),
            'wifi_networks': len(self.networks),
            'network_hosts': len(self.devices),
            'vulnerabilities_open': sum(1 for v in self.vulns_found if v.get('status')=='OPEN'),
            'ids_alerts_24h': len(self.alerts),
            'scan_count': self.scan_count,
            'threat_networks': sum(1 for n in self.networks.values()
                                   if n.get('threat_level') in ['HIGH','SUSPECT']),
            'critical_vulns': sum(1 for v in self.vulns_found
                                  if v.get('severity')=='CRITICAL'),
        }
        msg = String(); msg.data = json.dumps(status)
        self.status_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = CyberOps()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node()
CYBEREOF
echo -e "${G}  [+] Cyber Operations node${NC}"

###############################################################################
# 7. NODE: SDR BRIDGE
###############################################################################
echo -e "${C}[PHASE 9] Writing SDR Bridge node...${NC}"
cat > $WS/src/mos_ew/mos_ew/sdr_bridge.py << 'SDREOF'
#!/usr/bin/env python3
"""
MOS SDR Bridge — Software Defined Radio Hardware Interface
Detects connected SDR hardware and bridges DragonOS tools to MOS.
Supports: RTL-SDR, HackRF, Airspy, USRP, LimeSDR, KrakenSDR
Interfaces with GNU Radio, GQRX, Kismet, rtl_433, dump1090, etc.
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, time, os, subprocess, glob

SDR_DEVICES = {
    'rtlsdr': {'vid':'0bda','pids':['2832','2838'],'name':'RTL-SDR',
               'tools':['gqrx','sdr++','rtl_433','dump1090','multimon-ng','rtl_power']},
    'hackrf': {'vid':'1d50','pids':['6089'],'name':'HackRF One',
               'tools':['gnu_radio','gqrx','sdr++','hackrf_sweep','inspectrum','urh']},
    'airspy': {'vid':'1d50','pids':['60a1'],'name':'Airspy',
               'tools':['gqrx','sdr++','spyserver']},
    'usrp':   {'vid':'2500','pids':['0020','0021','0022'],'name':'Ettus USRP',
               'tools':['gnu_radio','uhd_fft','osmo-bts','srsRAN','gr-gsm']},
    'limesdr':{'vid':'0403','pids':['601f'],'name':'LimeSDR',
               'tools':['gnu_radio','limesuite','sdr++','srsRAN']},
}

DRAGONOS_TOOLS = {
    'gnuradio-companion': 'GNU Radio Companion',
    'gqrx': 'GQRX SDR Receiver',
    'sdrpp': 'SDR++',
    'rtl_433': 'RTL_433 ISM Decoder',
    'dump1090-mutability': 'dump1090 ADS-B',
    'multimon-ng': 'Multimon-NG',
    'inspectrum': 'Inspectrum',
    'urh': 'Universal Radio Hacker',
    'kismet': 'Kismet',
    'aircrack-ng': 'Aircrack-ng',
    'bettercap': 'Bettercap',
    'nmap': 'Nmap',
    'tshark': 'TShark/Wireshark',
    'direwolf': 'Direwolf APRS',
    'kalibrate': 'Kalibrate-RTL',
    'hackrf_info': 'HackRF Tools',
    'uhd_find_devices': 'UHD (USRP)',
    'SigDigger': 'SigDigger',
    'gpredict': 'GPredict',
}

class SDRBridge(Node):
    def __init__(self):
        super().__init__('sdr_bridge')
        self.status_pub = self.create_publisher(String, '/mos/sdr/status', 10)
        self.data_pub = self.create_publisher(String, '/mos/sdr/data', 10)
        self.create_subscription(String, '/mos/sdr/command', self._on_command, 10)
        self.detected_hardware = {}
        self.available_tools = {}
        self.active_tools = {}
        self.running_processes = {}
        self.create_timer(10.0, self._scan_hardware)
        self.create_timer(30.0, self._scan_tools)
        self.create_timer(5.0, self._publish_status)
        # Initial scan
        self._scan_hardware()
        self._scan_tools()
        self.get_logger().info('📻 SDR Bridge online — scanning for hardware...')

    def _scan_hardware(self):
        self.detected_hardware = {}
        # Check USB devices
        try:
            usb_devices = glob.glob('/sys/bus/usb/devices/*/idVendor')
            for vpath in usb_devices:
                try:
                    vid = open(vpath).read().strip()
                    pid = open(vpath.replace('idVendor','idProduct')).read().strip()
                    for sdr_key, sdr_info in SDR_DEVICES.items():
                        if vid == sdr_info['vid'] and pid in sdr_info['pids']:
                            dev_path = os.path.dirname(vpath)
                            self.detected_hardware[sdr_key] = {
                                'type': sdr_key,
                                'name': sdr_info['name'],
                                'path': dev_path,
                                'vid': vid, 'pid': pid,
                                'available_tools': sdr_info['tools'],
                                'status': 'CONNECTED'
                            }
                            self.get_logger().info(f'📻 SDR DETECTED: {sdr_info["name"]} ({vid}:{pid})')
                except: pass
        except: pass
        if not self.detected_hardware:
            self.get_logger().info('📻 No SDR hardware detected — simulation mode')

    def _scan_tools(self):
        self.available_tools = {}
        for binary, name in DRAGONOS_TOOLS.items():
            try:
                result = subprocess.run(['which', binary], capture_output=True, timeout=2)
                if result.returncode == 0:
                    path = result.stdout.decode().strip()
                    self.available_tools[binary] = {
                        'name': name, 'binary': binary, 'path': path,
                        'installed': True, 'running': binary in self.running_processes
                    }
            except: pass
        n = len(self.available_tools)
        self.get_logger().info(f'🔧 {n} DragonOS/SDR tools available on this system')

    def _on_command(self, msg):
        d = json.loads(msg.data)
        action = d.get('action','')
        tool = d.get('tool','')
        if action == 'START_TOOL' and tool in self.available_tools:
            try:
                args = d.get('args', [])
                proc = subprocess.Popen([tool] + args, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
                self.running_processes[tool] = proc
                self.get_logger().info(f'🔧 Started tool: {tool} (PID {proc.pid})')
            except Exception as e:
                self.get_logger().error(f'Failed to start {tool}: {e}')
        elif action == 'STOP_TOOL' and tool in self.running_processes:
            self.running_processes[tool].terminate()
            del self.running_processes[tool]
            self.get_logger().info(f'🔧 Stopped tool: {tool}')

    def _publish_status(self):
        # Check running processes
        for tool, proc in list(self.running_processes.items()):
            if proc.poll() is not None:
                del self.running_processes[tool]
        status = {
            'timestamp': time.time(),
            'hardware_detected': len(self.detected_hardware),
            'hardware': list(self.detected_hardware.values()),
            'tools_available': len(self.available_tools),
            'tools': {k: {**v, 'running': k in self.running_processes}
                      for k, v in self.available_tools.items()},
            'active_tools': list(self.running_processes.keys()),
            'mode': 'HARDWARE' if self.detected_hardware else 'SIMULATION',
        }
        msg = String(); msg.data = json.dumps(status)
        self.status_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = SDRBridge()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        for proc in node.running_processes.values():
            proc.terminate()
        node.destroy_node()
SDREOF
echo -e "${G}  [+] SDR Bridge node${NC}"

###############################################################################
# 8. NODE: RF ANALYZER
###############################################################################
echo -e "${C}[PHASE 9] Writing RF Analyzer node...${NC}"
cat > $WS/src/mos_ew/mos_ew/rf_analyzer.py << 'RFEOF'
#!/usr/bin/env python3
"""
MOS RF Analyzer — Spectrum Analysis & Visualization Data
Generates simulated (or real) spectrum sweep data for the EW waterfall display.
Produces 512-bin FFT data with realistic noise floor and injected signals.
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json, time, random, math

class RFAnalyzer(Node):
    def __init__(self):
        super().__init__('rf_analyzer')
        self.spectrum_pub = self.create_publisher(String, '/mos/ew/spectrum', 10)
        self.anomaly_pub = self.create_publisher(String, '/mos/ew/anomalies', 10)
        self.create_subscription(String, '/mos/ew/emitters', self._on_emitter, 10)
        self.bins = 512
        self.center_freq = 450.0    # MHz
        self.bandwidth = 100.0      # MHz
        self.noise_floor = -110.0   # dBm
        self.emitters = {}
        self.sweep_count = 0
        self.anomalies = []
        self.baseline = [self.noise_floor] * self.bins
        self.create_timer(0.5, self._sweep)  # 2 Hz sweep rate
        self.create_timer(10.0, self._update_baseline)
        self.get_logger().info(f'📊 RF Analyzer online — {self.bins} bins, '
                               f'{self.center_freq} MHz center, {self.bandwidth} MHz span')

    def _on_emitter(self, msg):
        d = json.loads(msg.data)
        self.emitters[d.get('emitter_id','')] = d

    def _freq_to_bin(self, freq_mhz):
        start = self.center_freq - self.bandwidth / 2
        end = self.center_freq + self.bandwidth / 2
        if freq_mhz < start or freq_mhz > end: return -1
        return int((freq_mhz - start) / self.bandwidth * self.bins)

    def _sweep(self):
        self.sweep_count += 1
        spectrum = []
        for i in range(self.bins):
            # Base noise floor with some variation
            power = self.noise_floor + random.gauss(0, 2.0)
            spectrum.append(power)
        # Inject known emitter signals
        for eid, e in self.emitters.items():
            freq = e.get('freq_mhz', 0)
            pwr = e.get('power_dbm', -100)
            bw = e.get('bandwidth_mhz', 1)
            center_bin = self._freq_to_bin(freq)
            if center_bin < 0: continue
            bw_bins = max(1, int(bw / self.bandwidth * self.bins))
            for b in range(max(0, center_bin - bw_bins//2),
                           min(self.bins, center_bin + bw_bins//2 + 1)):
                dist = abs(b - center_bin) / max(1, bw_bins//2)
                rolloff = max(0, 1.0 - dist * dist)
                signal_pwr = pwr * rolloff + random.gauss(0, 1.0)
                spectrum[b] = max(spectrum[b], signal_pwr)
        # Add some persistent environmental signals
        for sig_freq, sig_pwr, sig_bw in [
            (462.5625, -55, 0.025),   # FRS/GMRS
            (462.7125, -60, 0.025),   # FRS/GMRS
            (446.0, -70, 10),         # UHF TV
            (420.0, -75, 5),          # Amateur 70cm
        ]:
            b = self._freq_to_bin(sig_freq)
            if 0 <= b < self.bins:
                bw_bins = max(1, int(sig_bw / self.bandwidth * self.bins))
                for bb in range(max(0,b-bw_bins//2), min(self.bins,b+bw_bins//2+1)):
                    spectrum[bb] = max(spectrum[bb], sig_pwr + random.gauss(0,2))
        # Publish
        freq_start = self.center_freq - self.bandwidth / 2
        data = {
            'timestamp': time.time(),
            'sweep_id': self.sweep_count,
            'center_freq_mhz': self.center_freq,
            'bandwidth_mhz': self.bandwidth,
            'freq_start_mhz': freq_start,
            'freq_end_mhz': freq_start + self.bandwidth,
            'bins': self.bins,
            'noise_floor_dbm': self.noise_floor,
            'spectrum_dbm': [round(s, 1) for s in spectrum],
            'peak_freq_mhz': round(freq_start + spectrum.index(max(spectrum)) *
                                   self.bandwidth / self.bins, 3),
            'peak_power_dbm': round(max(spectrum), 1),
        }
        msg = String(); msg.data = json.dumps(data)
        self.spectrum_pub.publish(msg)
        # Anomaly detection
        for i, pwr in enumerate(spectrum):
            if pwr > self.baseline[i] + 20:
                freq = freq_start + i * self.bandwidth / self.bins
                anomaly = {'freq_mhz': round(freq,3), 'power_dbm': round(pwr,1),
                           'excess_db': round(pwr - self.baseline[i],1),
                           'timestamp': time.time(), 'bin': i}
                if not any(abs(a['freq_mhz']-freq) < 1.0 for a in self.anomalies[-20:]):
                    self.anomalies.append(anomaly)
                    msg2 = String(); msg2.data = json.dumps(anomaly)
                    self.anomaly_pub.publish(msg2)

    def _update_baseline(self):
        # Slowly adapt baseline to long-term average
        pass  # In production, this would use exponential moving average

def main(args=None):
    rclpy.init(args=args)
    node = RFAnalyzer()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node()
RFEOF
echo -e "${G}  [+] RF Analyzer node${NC}"

###############################################################################
# 9. EW API ROUTES (Flask Blueprint for c2_server)
###############################################################################
echo -e "${C}[PHASE 9] Writing EW API routes...${NC}"
cat > $WS/src/mos_c2_console/mos_c2_console/ew_api.py << 'EWAPIEOF'
#!/usr/bin/env python3
"""
MOS EW/SIGINT/Cyber API Routes
Registers Flask endpoints for the EW suite and manages ROS 2 subscriptions.
"""
from flask import jsonify, request, render_template
from std_msgs.msg import String
import json, time, threading

# Data stores (populated by ROS 2 callbacks)
ew_data = {
    'status': {}, 'emitters': {}, 'spectrum': {}, 'signals': [],
    'bearings': [], 'jamming': [], 'alerts': [], 'cop': {},
    'cyber_status': {}, 'cyber_networks': {}, 'cyber_devices': {},
    'cyber_vulns': [], 'cyber_alerts': [],
    'sdr_status': {}, 'anomalies': [],
}
_lock = threading.Lock()

def register_ew_routes(app, node):
    """Register all EW/SIGINT/Cyber Flask routes and ROS 2 subscribers."""

    # ── ROS 2 Subscriptions ──────────────────────────────────────────
    def _cb(topic_key):
        def callback(msg):
            d = json.loads(msg.data)
            with _lock:
                if topic_key == 'emitters':
                    eid = d.get('emitter_id','')
                    if eid: ew_data['emitters'][eid] = d
                elif topic_key == 'signals':
                    ew_data['signals'].append(d)
                    if len(ew_data['signals']) > 500:
                        ew_data['signals'] = ew_data['signals'][-500:]
                elif topic_key == 'bearings':
                    ew_data['bearings'] = d.get('bearings', [])
                elif topic_key == 'ew_alerts':
                    ew_data['alerts'].append(d)
                    if len(ew_data['alerts']) > 200:
                        ew_data['alerts'] = ew_data['alerts'][-200:]
                elif topic_key == 'cyber_vulns':
                    ew_data['cyber_vulns'].append(d)
                    if len(ew_data['cyber_vulns']) > 100:
                        ew_data['cyber_vulns'] = ew_data['cyber_vulns'][-100:]
                elif topic_key == 'cyber_alerts':
                    ew_data['cyber_alerts'].append(d)
                    if len(ew_data['cyber_alerts']) > 200:
                        ew_data['cyber_alerts'] = ew_data['cyber_alerts'][-200:]
                elif topic_key == 'cyber_networks':
                    nets = d.get('wifi_networks', d.get('devices', []))
                    for n in (nets if isinstance(nets, list) else []):
                        key = n.get('bssid', n.get('ip', ''))
                        if key: ew_data['cyber_networks'][key] = n
                elif topic_key == 'anomalies':
                    ew_data['anomalies'].append(d)
                    if len(ew_data['anomalies']) > 100:
                        ew_data['anomalies'] = ew_data['anomalies'][-100:]
                else:
                    ew_data[topic_key] = d
        return callback

    subs = [
        ('/mos/ew/status', 'status'), ('/mos/ew/emitters', 'emitters'),
        ('/mos/ew/spectrum', 'spectrum'), ('/mos/ew/signals', 'signals'),
        ('/mos/ew/bearings', 'bearings'), ('/mos/ew/cop', 'cop'),
        ('/mos/ew/alerts', 'ew_alerts'), ('/mos/ew/anomalies', 'anomalies'),
        ('/mos/cyber/status', 'cyber_status'), ('/mos/cyber/networks', 'cyber_networks'),
        ('/mos/cyber/vulns', 'cyber_vulns'), ('/mos/cyber/alerts', 'cyber_alerts'),
        ('/mos/sdr/status', 'sdr_status'),
    ]
    for topic, key in subs:
        node.create_subscription(String, topic, _cb(key), 10)

    # Command publishers
    ew_cmd_pub = node.create_publisher(String, '/mos/ew/command', 10)
    sdr_cmd_pub = node.create_publisher(String, '/mos/sdr/command', 10)

    # ── Page Routes ──────────────────────────────────────────────────
    @app.route('/ew')
    def ew_page():
        return render_template('ew.html')

    @app.route('/sigint')
    def sigint_page():
        return render_template('sigint.html')

    @app.route('/cyber')
    def cyber_page():
        return render_template('cyber.html')

    # ── EW API ───────────────────────────────────────────────────────
    @app.route('/api/ew/status')
    def api_ew_status():
        with _lock: return jsonify(ew_data['status'])

    @app.route('/api/ew/emitters')
    def api_ew_emitters():
        with _lock: return jsonify(list(ew_data['emitters'].values()))

    @app.route('/api/ew/spectrum')
    def api_ew_spectrum():
        with _lock: return jsonify(ew_data['spectrum'])

    @app.route('/api/ew/signals')
    def api_ew_signals():
        with _lock: return jsonify(ew_data['signals'][-100:])

    @app.route('/api/ew/bearings')
    def api_ew_bearings():
        with _lock: return jsonify(ew_data['bearings'])

    @app.route('/api/ew/alerts')
    def api_ew_alerts():
        with _lock: return jsonify(ew_data['alerts'][-50:])

    @app.route('/api/ew/cop')
    def api_ew_cop():
        with _lock: return jsonify(ew_data['cop'])

    @app.route('/api/ew/anomalies')
    def api_ew_anomalies():
        with _lock: return jsonify(ew_data['anomalies'][-50:])

    @app.route('/api/ew/jam', methods=['POST'])
    def api_ew_jam():
        d = request.json or {}
        d['action'] = d.get('action', 'START_JAM')
        msg = String(); msg.data = json.dumps(d)
        ew_cmd_pub.publish(msg)
        return jsonify({'status': 'ok', 'command': d})

    @app.route('/api/ew/scan', methods=['POST'])
    def api_ew_scan():
        d = request.json or {}
        d['action'] = 'START_SCAN'
        msg = String(); msg.data = json.dumps(d)
        ew_cmd_pub.publish(msg)
        return jsonify({'status': 'ok'})

    @app.route('/api/ew/df', methods=['POST'])
    def api_ew_df():
        d = request.json or {}
        d['action'] = 'DF_LOCATE'
        msg = String(); msg.data = json.dumps(d)
        ew_cmd_pub.publish(msg)
        return jsonify({'status': 'ok'})

    # ── Cyber API ────────────────────────────────────────────────────
    @app.route('/api/cyber/status')
    def api_cyber_status():
        with _lock: return jsonify(ew_data['cyber_status'])

    @app.route('/api/cyber/networks')
    def api_cyber_networks():
        with _lock: return jsonify(list(ew_data['cyber_networks'].values()))

    @app.route('/api/cyber/vulns')
    def api_cyber_vulns():
        with _lock: return jsonify(ew_data['cyber_vulns'][-50:])

    @app.route('/api/cyber/alerts')
    def api_cyber_alerts():
        with _lock: return jsonify(ew_data['cyber_alerts'][-50:])

    # ── SDR API ──────────────────────────────────────────────────────
    @app.route('/api/sdr/status')
    def api_sdr_status():
        with _lock: return jsonify(ew_data['sdr_status'])

    @app.route('/api/sdr/tool', methods=['POST'])
    def api_sdr_tool():
        d = request.json or {}
        msg = String(); msg.data = json.dumps(d)
        sdr_cmd_pub.publish(msg)
        return jsonify({'status': 'ok', 'command': d})

    node.get_logger().info('[EW API] 18 EW/SIGINT/Cyber endpoints registered')
EWAPIEOF
echo -e "${G}  [+] EW API routes (18 endpoints)${NC}"

###############################################################################
# 10. EW DASHBOARD HTML — THE SHOWSTOPPER
###############################################################################
echo -e "${C}[PHASE 9] Writing EW Dashboard (waterfall + spectrum)...${NC}"
cat > $WS/src/mos_c2_console/mos_c2_console/templates/ew.html << 'EWHTMLEOF'
<!DOCTYPE html>
<html><head>
<title>MOS ⚡ EW/SIGINT Dashboard</title>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;color:#00ff41;font-family:'Courier New',monospace;overflow:hidden}
.header{background:linear-gradient(90deg,#1a0a2e,#0a0a0a,#1a0a2e);padding:8px 20px;
  display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #ff006688}
.header h1{font-size:18px;color:#ff0066;text-shadow:0 0 10px #ff006688}
.nav a{color:#00ccff;text-decoration:none;margin:0 8px;font-size:12px}
.nav a:hover{color:#fff;text-shadow:0 0 5px #00ccff}
.nav a.active{color:#ff0066;border-bottom:1px solid #ff0066}
.status-bar{display:flex;gap:15px;align-items:center}
.status-pill{padding:2px 10px;border-radius:10px;font-size:11px;font-weight:bold}
.pill-green{background:#00ff4133;color:#00ff41;border:1px solid #00ff41}
.pill-amber{background:#ffaa0033;color:#ffaa00;border:1px solid #ffaa00}
.pill-red{background:#ff000033;color:#ff3333;border:1px solid #ff3333}
.main{display:grid;grid-template-columns:280px 1fr 300px;grid-template-rows:220px 1fr 180px;
  height:calc(100vh - 45px);gap:2px;padding:2px}
.panel{background:#0d0d0d;border:1px solid #1a3a1a;border-radius:3px;padding:8px;overflow:auto}
.panel-title{color:#00ccff;font-size:11px;text-transform:uppercase;margin-bottom:6px;
  border-bottom:1px solid #00ccff33;padding-bottom:3px;letter-spacing:2px}
/* Spectrum analyzer */
#spectrumPanel{grid-column:1/4}
#spectrumCanvas{width:100%;height:170px;background:#050510;border:1px solid #1a1a3a;cursor:crosshair}
/* Emitter map */
#mapPanel{grid-column:2/3}
#emitterMap{width:100%;height:100%;border-radius:3px}
/* Waterfall */
#waterfallPanel{grid-column:1/4}
#waterfallCanvas{width:100%;height:140px;background:#050510;border:1px solid #1a1a3a}
/* Emitter list */
.emitter-item{padding:4px 6px;margin:2px 0;border-radius:3px;font-size:10px;
  border-left:3px solid;cursor:pointer}
.emitter-item:hover{background:#ffffff11}
.emitter-item.hostile{border-color:#ff0000;background:#ff000011}
.emitter-item.jammer{border-color:#ff00ff;background:#ff00ff11}
.emitter-item.suspect{border-color:#ff8800;background:#ff880011}
.emitter-item.neutral{border-color:#ffff00;background:#ffff0011}
.emitter-item.friendly{border-color:#00ff41;background:#00ff4111}
.badge{display:inline-block;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:bold}
/* Operations panel */
.op-item{padding:4px;margin:3px 0;background:#0a1a2a;border:1px solid #00ccff33;
  border-radius:3px;font-size:10px}
/* Alerts */
.alert-item{padding:3px 6px;margin:2px 0;font-size:10px;border-radius:3px}
.alert-CRITICAL{background:#ff000022;border-left:3px solid #ff0000}
.alert-WARNING{background:#ff880022;border-left:3px solid #ff8800}
.alert-INFO{background:#00ccff22;border-left:3px solid #00ccff}
/* SDR status */
.sdr-card{padding:4px;margin:3px 0;background:#1a0a2e;border:1px solid #8800ff44;
  border-radius:3px;font-size:10px}
.tool-badge{display:inline-block;padding:1px 4px;margin:1px;border-radius:2px;
  font-size:8px;background:#00ff4122;color:#00ff41;border:1px solid #00ff4144}
.tool-badge.running{background:#ff006633;color:#ff0066;border-color:#ff0066}
.freq-label{position:absolute;color:#00ccff88;font-size:9px;pointer-events:none}
/* Buttons */
.btn{padding:4px 10px;border:1px solid;border-radius:3px;background:transparent;
  color:inherit;cursor:pointer;font-family:inherit;font-size:10px}
.btn-red{color:#ff3333;border-color:#ff3333}.btn-red:hover{background:#ff333333}
.btn-cyan{color:#00ccff;border-color:#00ccff}.btn-cyan:hover{background:#00ccff33}
.btn-green{color:#00ff41;border-color:#00ff41}.btn-green:hover{background:#00ff4133}
.btn-magenta{color:#ff00ff;border-color:#ff00ff}.btn-magenta:hover{background:#ff00ff33}
</style>
</head><body>
<div class="header">
  <h1>⚡ MOS EW/SIGINT DASHBOARD</h1>
  <div class="nav">
    <a href="/">C2 MAP</a><a href="/dashboard">TWIN</a><a href="/ew" class="active">EW/SIGINT</a>
    <a href="/sigint">SIGINT DB</a><a href="/cyber">CYBER</a><a href="/awacs">AWACS</a>
    <a href="/tactical3d">3D</a><a href="/echelon">ECHELON</a><a href="/hal">HAL</a>
  </div>
  <div class="status-bar">
    <span id="rfEnv" class="status-pill pill-green">RF: PERMISSIVE</span>
    <span id="emitterCount" class="status-pill pill-green">EMITTERS: 0</span>
    <span id="sdrMode" class="status-pill pill-amber">SDR: SIM</span>
  </div>
</div>
<div class="main">
  <!-- Row 1: Spectrum Analyzer (full width) -->
  <div class="panel" id="spectrumPanel">
    <div class="panel-title">📊 RF SPECTRUM ANALYZER — <span id="specFreq">400-500 MHz</span>
      <span style="float:right;color:#ff0066" id="peakInfo">Peak: --- MHz / --- dBm</span></div>
    <canvas id="spectrumCanvas"></canvas>
  </div>
  <!-- Row 2: Emitter List | Map | Operations -->
  <div class="panel" id="emitterListPanel" style="overflow-y:auto">
    <div class="panel-title">📡 DETECTED EMITTERS (<span id="emtTotal">0</span>)
      <button class="btn btn-cyan" onclick="filterEmitters('ALL')" style="float:right;margin-left:4px">ALL</button>
      <button class="btn btn-red" onclick="filterEmitters('HOSTILE')" style="float:right">THR</button>
    </div>
    <div id="emitterList"></div>
  </div>
  <div class="panel" id="mapPanel">
    <div id="emitterMap"></div>
  </div>
  <div class="panel" style="overflow-y:auto">
    <div class="panel-title">⚡ ACTIVE OPERATIONS</div>
    <div id="activeOps"></div>
    <div class="panel-title" style="margin-top:10px">🚨 EW ALERTS</div>
    <div id="ewAlerts"></div>
    <div class="panel-title" style="margin-top:10px">📻 SDR HARDWARE</div>
    <div id="sdrStatus"></div>
    <div class="panel-title" style="margin-top:10px">🔧 TOOLS</div>
    <div id="toolStatus"></div>
    <div style="margin-top:8px">
      <button class="btn btn-magenta" onclick="startJam()">⚡ ACTIVATE JAM</button>
      <button class="btn btn-cyan" onclick="startScan()">📡 NEW SCAN</button>
    </div>
  </div>
  <!-- Row 3: Waterfall (full width) -->
  <div class="panel" id="waterfallPanel">
    <div class="panel-title">🌊 RF WATERFALL — TIME vs FREQUENCY
      <span style="float:right;color:#666">Scroll: newest at top</span></div>
    <canvas id="waterfallCanvas"></canvas>
  </div>
</div>
<script>
// === Map Setup ===
const map = L.map('emitterMap',{zoomControl:false}).setView([27.8506,-82.5214],13);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{
  maxZoom:19,attribution:'MOS EW'}).addTo(map);
const emitterMarkers={}, bearingLines=[], jamCircles=[];

// === Spectrum Canvas ===
const specCvs=document.getElementById('spectrumCanvas');
const specCtx=specCvs.getContext('2d');
let specData=null;

function resizeCanvases(){
  specCvs.width=specCvs.parentElement.clientWidth-16;
  specCvs.height=170;
  wfCvs.width=wfCvs.parentElement.clientWidth-16;
  wfCvs.height=140;
}

function drawSpectrum(data){
  if(!data||!data.spectrum_dbm)return;
  specData=data;
  const w=specCvs.width, h=specCvs.height;
  const bins=data.spectrum_dbm;
  const n=bins.length;
  specCtx.fillStyle='#050510';
  specCtx.fillRect(0,0,w,h);
  // Grid
  specCtx.strokeStyle='#1a1a3a';specCtx.lineWidth=0.5;
  for(let i=0;i<10;i++){
    const y=i*h/10;
    specCtx.beginPath();specCtx.moveTo(0,y);specCtx.lineTo(w,y);specCtx.stroke();
  }
  for(let i=0;i<n;i+=n/10){
    const x=i/n*w;
    specCtx.beginPath();specCtx.moveTo(x,0);specCtx.lineTo(x,h);specCtx.stroke();
  }
  // Noise floor line
  const nfY=h-((-110-(-120))/(0-(-120)))*h;
  specCtx.strokeStyle='#333';specCtx.setLineDash([4,4]);
  specCtx.beginPath();specCtx.moveTo(0,nfY);specCtx.lineTo(w,nfY);specCtx.stroke();
  specCtx.setLineDash([]);
  // Spectrum fill
  const grad=specCtx.createLinearGradient(0,h,0,0);
  grad.addColorStop(0,'rgba(0,255,65,0.05)');grad.addColorStop(0.5,'rgba(0,204,255,0.15)');
  grad.addColorStop(0.8,'rgba(255,0,102,0.3)');grad.addColorStop(1,'rgba(255,0,0,0.5)');
  specCtx.fillStyle=grad;
  specCtx.beginPath();specCtx.moveTo(0,h);
  for(let i=0;i<n;i++){
    const x=i/n*w;
    const pwr=bins[i];
    const y=h-((pwr-(-120))/(0-(-120)))*h;
    specCtx.lineTo(x,Math.max(0,Math.min(h,y)));
  }
  specCtx.lineTo(w,h);specCtx.closePath();specCtx.fill();
  // Spectrum line
  specCtx.strokeStyle='#00ff41';specCtx.lineWidth=1.5;specCtx.beginPath();
  for(let i=0;i<n;i++){
    const x=i/n*w;const pwr=bins[i];
    const y=h-((pwr-(-120))/(0-(-120)))*h;
    i===0?specCtx.moveTo(x,y):specCtx.lineTo(x,y);
  }
  specCtx.stroke();
  // Peak marker
  const peakIdx=bins.indexOf(Math.max(...bins));
  const peakX=peakIdx/n*w;
  const peakPwr=bins[peakIdx];
  const peakY=h-((peakPwr-(-120))/(0-(-120)))*h;
  specCtx.fillStyle='#ff0066';specCtx.beginPath();
  specCtx.arc(peakX,peakY,4,0,Math.PI*2);specCtx.fill();
  // Freq labels
  specCtx.fillStyle='#00ccff88';specCtx.font='9px monospace';
  const fStart=data.freq_start_mhz, fEnd=data.freq_end_mhz;
  for(let i=0;i<=10;i++){
    const f=fStart+i*(fEnd-fStart)/10;
    specCtx.fillText(f.toFixed(1),i/10*w+2,h-3);
  }
  // dBm labels
  specCtx.fillStyle='#66666688';
  for(let db=-120;db<=0;db+=20){
    const y=h-((db-(-120))/(0-(-120)))*h;
    specCtx.fillText(db+'dBm',3,y-2);
  }
  document.getElementById('specFreq').textContent=`${fStart.toFixed(0)}-${fEnd.toFixed(0)} MHz`;
  const peakFreq=fStart+peakIdx/n*(fEnd-fStart);
  document.getElementById('peakInfo').textContent=`Peak: ${peakFreq.toFixed(3)} MHz / ${peakPwr.toFixed(1)} dBm`;
}

// === Waterfall Canvas ===
const wfCvs=document.getElementById('waterfallCanvas');
const wfCtx=wfCvs.getContext('2d');
let wfImageData=null;

function drawWaterfall(data){
  if(!data||!data.spectrum_dbm)return;
  const w=wfCvs.width, h=wfCvs.height;
  const bins=data.spectrum_dbm;
  const n=bins.length;
  // Scroll existing data down by 1 pixel
  const existing=wfCtx.getImageData(0,0,w,h);
  wfCtx.putImageData(existing,0,1);
  // Draw new row at top
  for(let x=0;x<w;x++){
    const bi=Math.floor(x/w*n);
    const pwr=bins[bi]||(-110);
    const norm=Math.max(0,Math.min(1,(pwr+120)/80));// -120 to -40 range
    let r,g,b;
    if(norm<0.25){r=0;g=0;b=Math.floor(norm*4*180);}
    else if(norm<0.5){r=0;g=Math.floor((norm-0.25)*4*255);b=180;}
    else if(norm<0.75){r=Math.floor((norm-0.5)*4*255);g=255;b=180-Math.floor((norm-0.5)*4*180);}
    else{r=255;g=255-Math.floor((norm-0.75)*4*200);b=0;}
    wfCtx.fillStyle=`rgb(${r},${g},${b})`;
    wfCtx.fillRect(x,0,1,1);
  }
}

// === Emitter List & Map ===
let allEmitters=[], currentFilter='ALL';
const classColors={HOSTILE:'#ff0000',JAMMER:'#ff00ff',SUSPECT:'#ff8800',NEUTRAL:'#ffff00',FRIENDLY:'#00ff41'};

function filterEmitters(f){currentFilter=f;}

function updateEmitters(emitters){
  allEmitters=emitters;
  const filtered=currentFilter==='ALL'?emitters:emitters.filter(e=>e.classification===currentFilter);
  document.getElementById('emtTotal').textContent=emitters.length;
  // Sort: hostile/jammer first
  const priority={JAMMER:0,HOSTILE:1,SUSPECT:2,NEUTRAL:3,FRIENDLY:4};
  filtered.sort((a,b)=>(priority[a.classification]||5)-(priority[b.classification]||5));
  let html='';
  for(const e of filtered.slice(0,30)){
    const cls=e.classification.toLowerCase();
    html+=`<div class="emitter-item ${cls}" onclick="focusEmitter('${e.emitter_id}')">
      <b>${e.emitter_id}</b> <span class="badge" style="background:${classColors[e.classification]}33;
        color:${classColors[e.classification]}">${e.classification}</span>
      <span class="badge" style="background:#00ccff22;color:#00ccff">${e.signal_type}</span><br>
      ${e.freq_mhz.toFixed(3)} MHz | ${e.power_dbm} dBm | ${e.modulation}<br>
      <span style="color:#666">${e.notes||''}</span></div>`;
  }
  document.getElementById('emitterList').innerHTML=html||'<div style="color:#666;padding:20px">No emitters detected</div>';
  // Map markers
  const seen=new Set();
  for(const e of emitters){
    seen.add(e.emitter_id);
    const color=classColors[e.classification]||'#ffffff';
    if(emitterMarkers[e.emitter_id]){
      emitterMarkers[e.emitter_id].setLatLng([e.lat,e.lon]);
    }else{
      const icon=L.divIcon({className:'',html:`<div style="width:12px;height:12px;
        border-radius:50%;background:${color};border:2px solid ${color};opacity:0.8;
        box-shadow:0 0 8px ${color}88"></div>`,iconSize:[12,12],iconAnchor:[6,6]});
      emitterMarkers[e.emitter_id]=L.marker([e.lat,e.lon],{icon}).addTo(map)
        .bindPopup(`<b style="color:${color}">${e.emitter_id}</b><br>${e.signal_type}<br>
          ${e.freq_mhz.toFixed(3)} MHz | ${e.power_dbm} dBm<br>${e.classification} | ${e.modulation}`);
    }
  }
  for(const eid of Object.keys(emitterMarkers)){
    if(!seen.has(eid)){map.removeLayer(emitterMarkers[eid]);delete emitterMarkers[eid];}
  }
}

function focusEmitter(eid){
  const e=allEmitters.find(x=>x.emitter_id===eid);
  if(e)map.setView([e.lat,e.lon],15);
}

function updateBearings(bearings){
  bearingLines.forEach(l=>map.removeLayer(l));
  bearingLines.length=0;
  for(const b of bearings){
    const rad=b.bearing_deg*Math.PI/180;
    const len=0.02;
    const eLat=b.from_lat+len*Math.cos(rad);
    const eLon=b.from_lon+len*Math.sin(rad);
    const line=L.polyline([[b.from_lat,b.from_lon],[eLat,eLon]],
      {color:'#ff006688',weight:1,dashArray:'4 4'}).addTo(map);
    bearingLines.push(line);
  }
}

// === Operations, Alerts, SDR ===
function updateOps(status){
  let html='';
  const ops=status.active_operations||[];
  for(const op of ops){
    html+=`<div class="op-item">🔵 ${op.id} | ${op.type} | ${op.asset||'—'}</div>`;
  }
  const jams=status.active_jamming||[];
  for(const j of jams){
    html+=`<div class="op-item" style="border-color:#ff00ff">⚡ ${j.id} | ${j.center_freq_mhz} MHz |
      ${j.profile} | ${j.assigned_asset}</div>`;
  }
  document.getElementById('activeOps').innerHTML=html||'<div style="color:#666">No active ops</div>';
  // Status pills
  const env=status.readiness||'RED';
  const envEl=document.getElementById('rfEnv');
  const he=status.hostile_emitters||0;
  envEl.textContent=`RF: ${he>2?'CONTESTED':he>0?'DEGRADED':'PERMISSIVE'}`;
  envEl.className='status-pill '+(he>2?'pill-red':he>0?'pill-amber':'pill-green');
  document.getElementById('emitterCount').textContent=`EMITTERS: ${status.total_emitters||0}`;
}

function updateAlerts(alerts){
  let html='';
  for(const a of alerts.slice(-8).reverse()){
    const sev=a.severity||'INFO';
    const t=new Date(a.timestamp*1000).toLocaleTimeString();
    html+=`<div class="alert-item alert-${sev}">${t} [${sev}] ${a.type}</div>`;
  }
  document.getElementById('ewAlerts').innerHTML=html||'<div style="color:#666">No alerts</div>';
}

function updateSDR(sdr){
  let html='';
  const hw=sdr.hardware||[];
  if(hw.length===0){
    html='<div class="sdr-card">📻 No SDR hardware — SIM mode</div>';
  }
  for(const h of hw){
    html+=`<div class="sdr-card">📻 <b>${h.name}</b> [${h.status}]</div>`;
  }
  document.getElementById('sdrStatus').innerHTML=html;
  const mode=sdr.mode||'SIMULATION';
  const modeEl=document.getElementById('sdrMode');
  modeEl.textContent=`SDR: ${mode==='HARDWARE'?'HW':'SIM'}`;
  modeEl.className='status-pill '+(mode==='HARDWARE'?'pill-green':'pill-amber');
  // Tools
  const tools=sdr.tools||{};
  let thtml='';
  for(const[k,v] of Object.entries(tools)){
    const running=v.running?'running':'';
    thtml+=`<span class="tool-badge ${running}">${v.name||k}</span>`;
  }
  document.getElementById('toolStatus').innerHTML=thtml||'<span style="color:#666">No tools detected</span>';
}

function startJam(){
  const freq=prompt('Jamming center frequency (MHz):','462.0');
  if(!freq)return;
  fetch('/api/ew/jam',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'START_JAM',freq_mhz:parseFloat(freq),bandwidth_mhz:5,
      radius_m:500,profile:'NOISE',lat:27.85,lon:-82.52})});
}
function startScan(){
  fetch('/api/ew/scan',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({asset_id:'MVRX-A03',freq_start:400,freq_end:500})});
}

// === Data Fetching Loop ===
async function fetchLoop(){
  try{
    const[spec,emitters,bearings,status,alerts,sdr]=await Promise.all([
      fetch('/api/ew/spectrum').then(r=>r.json()),
      fetch('/api/ew/emitters').then(r=>r.json()),
      fetch('/api/ew/bearings').then(r=>r.json()),
      fetch('/api/ew/status').then(r=>r.json()),
      fetch('/api/ew/alerts').then(r=>r.json()),
      fetch('/api/sdr/status').then(r=>r.json()),
    ]);
    drawSpectrum(spec);
    drawWaterfall(spec);
    updateEmitters(emitters);
    updateBearings(bearings);
    updateOps(status);
    updateAlerts(alerts);
    updateSDR(sdr);
  }catch(e){}
}

window.addEventListener('resize',resizeCanvases);
resizeCanvases();
setInterval(fetchLoop,1000);
setTimeout(fetchLoop,500);
</script>
</body></html>
EWHTMLEOF
echo -e "${G}  [+] EW Dashboard HTML (spectrum + waterfall + emitter map)${NC}"

###############################################################################
# 11. SIGINT DATABASE HTML
###############################################################################
echo -e "${C}[PHASE 9] Writing SIGINT Database view...${NC}"
cat > $WS/src/mos_c2_console/mos_c2_console/templates/sigint.html << 'SIGHTMLEOF'
<!DOCTYPE html>
<html><head>
<title>MOS 📡 SIGINT Database</title>
<meta charset="utf-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;color:#00ff41;font-family:'Courier New',monospace}
.header{background:#0d0d0d;padding:8px 20px;display:flex;justify-content:space-between;
  align-items:center;border-bottom:1px solid #00ccff44}
.header h1{font-size:16px;color:#00ccff}
.nav a{color:#00ccff;text-decoration:none;margin:0 8px;font-size:12px}
.nav a:hover{color:#fff}.nav a.active{color:#ff0066}
.main{display:grid;grid-template-columns:1fr 350px;grid-template-rows:auto 1fr;
  height:calc(100vh - 45px);gap:2px;padding:2px}
.panel{background:#0d0d0d;border:1px solid #1a3a1a;border-radius:3px;padding:10px;overflow:auto}
.panel-title{color:#00ccff;font-size:11px;text-transform:uppercase;margin-bottom:8px;
  border-bottom:1px solid #00ccff33;padding-bottom:4px;letter-spacing:2px}
.stats-bar{grid-column:1/3;display:flex;gap:15px;padding:8px 15px;flex-wrap:wrap}
.stat{background:#0d1a0d;border:1px solid #00ff4133;padding:5px 12px;border-radius:3px}
.stat-val{font-size:18px;font-weight:bold;color:#00ff41}
.stat-label{font-size:9px;color:#666;text-transform:uppercase}
table{width:100%;border-collapse:collapse;font-size:11px}
th{background:#0a1a2a;color:#00ccff;padding:6px;text-align:left;position:sticky;top:0;
  border-bottom:1px solid #00ccff44;cursor:pointer}
th:hover{color:#fff}
td{padding:5px 6px;border-bottom:1px solid #111}
tr:hover{background:#ffffff08}
.class-HOSTILE{color:#ff3333}.class-JAMMER{color:#ff00ff}
.class-SUSPECT{color:#ff8800}.class-NEUTRAL{color:#ffff00}.class-FRIENDLY{color:#00ff41}
.sig-badge{display:inline-block;padding:1px 5px;border-radius:3px;font-size:9px}
.filter-bar{display:flex;gap:5px;margin-bottom:8px;flex-wrap:wrap}
.filter-btn{padding:3px 8px;border:1px solid #333;border-radius:3px;background:transparent;
  color:#888;cursor:pointer;font-family:inherit;font-size:10px}
.filter-btn:hover,.filter-btn.active{color:#00ccff;border-color:#00ccff;background:#00ccff11}
.detail-section{margin:8px 0;padding:8px;background:#0a0a1a;border:1px solid #1a1a3a;border-radius:3px}
.detail-section h3{color:#ff0066;font-size:12px;margin-bottom:5px}
.detail-row{display:flex;justify-content:space-between;padding:2px 0;font-size:11px}
.detail-row .label{color:#666}.detail-row .value{color:#00ff41}
canvas{width:100%;height:80px;background:#050510;border:1px solid #1a1a3a;margin-top:5px}
</style>
</head><body>
<div class="header">
  <h1>📡 SIGINT DATABASE — SIGNAL INTELLIGENCE</h1>
  <div class="nav">
    <a href="/">C2</a><a href="/ew">EW</a><a href="/sigint" class="active">SIGINT</a>
    <a href="/cyber">CYBER</a><a href="/dashboard">TWIN</a><a href="/awacs">AWACS</a>
  </div>
</div>
<div class="main">
  <div class="stats-bar">
    <div class="stat"><div class="stat-val" id="totalSig">0</div><div class="stat-label">Total Signals</div></div>
    <div class="stat"><div class="stat-val" id="hostileSig" style="color:#ff3333">0</div><div class="stat-label">Hostile</div></div>
    <div class="stat"><div class="stat-val" id="jammerSig" style="color:#ff00ff">0</div><div class="stat-label">Jammers</div></div>
    <div class="stat"><div class="stat-val" id="suspectSig" style="color:#ff8800">0</div><div class="stat-label">Suspect</div></div>
    <div class="stat"><div class="stat-val" id="dronesSig" style="color:#ff0066">0</div><div class="stat-label">Drone Links</div></div>
    <div class="stat"><div class="stat-val" id="wifiSig" style="color:#00ccff">0</div><div class="stat-label">WiFi</div></div>
    <div class="stat"><div class="stat-val" id="cellSig" style="color:#ffaa00">0</div><div class="stat-label">Cellular</div></div>
    <div class="stat"><div class="stat-val" id="uniqueTypes">0</div><div class="stat-label">Signal Types</div></div>
  </div>
  <!-- Signal Table -->
  <div class="panel">
    <div class="panel-title">📊 SIGNAL DATABASE</div>
    <div class="filter-bar">
      <button class="filter-btn active" onclick="setFilter('ALL',this)">ALL</button>
      <button class="filter-btn" onclick="setFilter('HOSTILE',this)">HOSTILE</button>
      <button class="filter-btn" onclick="setFilter('JAMMER',this)">JAMMER</button>
      <button class="filter-btn" onclick="setFilter('SUSPECT',this)">SUSPECT</button>
      <button class="filter-btn" onclick="setFilter('DRONE_C2',this)">DRONE</button>
      <button class="filter-btn" onclick="setFilter('WIFI',this)">WIFI</button>
      <button class="filter-btn" onclick="setFilter('CELLULAR',this)">CELL</button>
      <button class="filter-btn" onclick="setFilter('RADAR',this)">RADAR</button>
      <button class="filter-btn" onclick="setFilter('COMMS',this)">COMMS</button>
    </div>
    <div style="max-height:calc(100vh - 200px);overflow-y:auto">
      <table><thead><tr>
        <th>ID</th><th>CLASS</th><th>TYPE</th><th>FREQ (MHz)</th>
        <th>PWR (dBm)</th><th>BW</th><th>MOD</th><th>THREAT</th><th>TIME</th>
      </tr></thead><tbody id="sigTable"></tbody></table>
    </div>
  </div>
  <!-- Detail Panel -->
  <div class="panel">
    <div class="panel-title">🔍 SIGNAL DETAIL</div>
    <div id="sigDetail"><div style="color:#666;padding:20px;text-align:center">
      Select a signal from the table</div></div>
    <div class="panel-title" style="margin-top:15px">📈 SIGNAL WAVEFORM</div>
    <canvas id="waveformCanvas"></canvas>
    <div class="panel-title" style="margin-top:15px">🛠 RECOMMENDED TOOLS</div>
    <div id="recTools" style="color:#666">—</div>
  </div>
</div>
<script>
let emitters=[], filter='ALL', selectedEmitter=null;
const toolRecs={
  DRONE_C2:['Universal Radio Hacker','GNU Radio','inspectrum'],
  WIFI:['Kismet','Aircrack-ng','Bettercap','Wireshark'],
  CELLULAR:['gr-gsm','kalibrate-rtl','srsRAN'],
  BLUETOOTH:['BlueHydra','Bettercap','hcitool'],
  COMMS_VHF:['SDR Trunk','GQRX','multimon-ng','Direwolf'],
  COMMS_UHF:['SDR Trunk','GQRX','SDR++'],
  RADAR:['GNU Radio','inspectrum','baudline'],
  P25:['SDR Trunk','OP25','DSD+'],
  DMR:['SDR Trunk','DSD+'],
  ADS_B:['dump1090','tar1090'],
  ISM_LORA:['rtl_433','GNU Radio'],
  GPS_INTERFERENCE:['GNU Radio','SigDigger','GNSS-SDR'],
  REMOTE_ID:['RemoteID Receiver','Kismet'],
};

function setFilter(f,btn){
  filter=f;
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
  if(btn)btn.classList.add('active');
}

function selectEmitter(eid){
  selectedEmitter=emitters.find(e=>e.emitter_id===eid);
  if(!selectedEmitter)return;
  const e=selectedEmitter;
  let html=`<div class="detail-section"><h3 style="color:${
    {HOSTILE:'#ff3333',JAMMER:'#ff00ff',SUSPECT:'#ff8800',NEUTRAL:'#ffff00',FRIENDLY:'#00ff41'}[e.classification]||'#fff'
  }">${e.emitter_id} — ${e.classification}</h3>
  <div class="detail-row"><span class="label">Signal Type</span><span class="value">${e.signal_type}</span></div>
  <div class="detail-row"><span class="label">Frequency</span><span class="value">${e.freq_mhz.toFixed(4)} MHz</span></div>
  <div class="detail-row"><span class="label">Bandwidth</span><span class="value">${e.bandwidth_mhz.toFixed(4)} MHz</span></div>
  <div class="detail-row"><span class="label">Power</span><span class="value">${e.power_dbm} dBm</span></div>
  <div class="detail-row"><span class="label">Modulation</span><span class="value">${e.modulation}</span></div>
  <div class="detail-row"><span class="label">Threat Score</span><span class="value" style="color:${e.threat_score>0.7?'#ff3333':'#ffaa00'}">${e.threat_score}</span></div>
  <div class="detail-row"><span class="label">Confidence</span><span class="value">${(e.confidence*100).toFixed(0)}%</span></div>
  <div class="detail-row"><span class="label">GeoFix</span><span class="value">${e.geolocation_fix}</span></div>
  <div class="detail-row"><span class="label">Location</span><span class="value">${e.lat.toFixed(5)}, ${e.lon.toFixed(5)}</span></div>
  <div class="detail-row"><span class="label">Detected By</span><span class="value">${e.detected_by}</span></div>
  <div style="margin-top:6px;padding:5px;background:#1a0a0a;border-radius:3px;font-size:10px;color:#ff8800">${e.notes||'—'}</div>
  </div>`;
  document.getElementById('sigDetail').innerHTML=html;
  // Tool recommendations
  const sigBase=e.signal_type.replace('_5G','');
  const tools=toolRecs[sigBase]||toolRecs[e.signal_type]||['GNU Radio','GQRX','inspectrum'];
  document.getElementById('recTools').innerHTML=tools.map(t=>
    `<span style="display:inline-block;padding:2px 6px;margin:2px;background:#00ff4122;
    border:1px solid #00ff4144;border-radius:3px;font-size:10px;color:#00ff41">${t}</span>`
  ).join('');
  drawWaveform(e);
}

function drawWaveform(e){
  const cvs=document.getElementById('waveformCanvas');
  cvs.width=cvs.parentElement.clientWidth-20;cvs.height=80;
  const ctx=cvs.getContext('2d');
  ctx.fillStyle='#050510';ctx.fillRect(0,0,cvs.width,cvs.height);
  const w=cvs.width,h=cvs.height;
  ctx.strokeStyle='#00ff4188';ctx.lineWidth=1;ctx.beginPath();
  const mod=e.modulation;
  for(let x=0;x<w;x++){
    const t=x/w*4*Math.PI;
    let y=0;
    if(mod==='FM')y=Math.sin(t+2*Math.sin(t*3));
    else if(mod==='AM')y=(1+0.5*Math.sin(t*0.3))*Math.sin(t*5);
    else if(mod==='OFDM')y=Math.sin(t*3)+0.5*Math.sin(t*7)+0.3*Math.sin(t*11);
    else if(mod==='FHSS')y=Math.sin(t*Math.floor(t)%5*3);
    else if(mod==='PULSE')y=((t*2)%6.28<1)?1:0;
    else if(mod==='CHIRP')y=Math.sin(t*t*0.5);
    else y=Math.sin(t*4+Math.random()*0.3);
    y=h/2-y*(h/2-5);
    x===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
  }
  ctx.stroke();
}

async function fetchData(){
  try{
    const data=await fetch('/api/ew/emitters').then(r=>r.json());
    emitters=data;
    let filtered=emitters;
    if(filter!=='ALL'){
      if(['HOSTILE','JAMMER','SUSPECT','NEUTRAL','FRIENDLY'].includes(filter))
        filtered=emitters.filter(e=>e.classification===filter);
      else if(filter==='COMMS')
        filtered=emitters.filter(e=>e.signal_type.startsWith('COMMS'));
      else
        filtered=emitters.filter(e=>e.signal_type.includes(filter));
    }
    // Stats
    document.getElementById('totalSig').textContent=emitters.length;
    document.getElementById('hostileSig').textContent=emitters.filter(e=>e.classification==='HOSTILE').length;
    document.getElementById('jammerSig').textContent=emitters.filter(e=>e.classification==='JAMMER').length;
    document.getElementById('suspectSig').textContent=emitters.filter(e=>e.classification==='SUSPECT').length;
    document.getElementById('dronesSig').textContent=emitters.filter(e=>e.signal_type.includes('DRONE')).length;
    document.getElementById('wifiSig').textContent=emitters.filter(e=>e.signal_type.includes('WIFI')).length;
    document.getElementById('cellSig').textContent=emitters.filter(e=>e.signal_type.includes('CELLULAR')).length;
    document.getElementById('uniqueTypes').textContent=new Set(emitters.map(e=>e.signal_type)).size;
    // Table
    let html='';
    const priority={JAMMER:0,HOSTILE:1,SUSPECT:2,NEUTRAL:3,FRIENDLY:4};
    filtered.sort((a,b)=>(priority[a.classification]||5)-(priority[b.classification]||5));
    for(const e of filtered){
      const t=new Date(e.first_seen*1000).toLocaleTimeString();
      html+=`<tr onclick="selectEmitter('${e.emitter_id}')" style="cursor:pointer">
        <td>${e.emitter_id}</td>
        <td class="class-${e.classification}">${e.classification}</td>
        <td>${e.signal_type}</td>
        <td>${e.freq_mhz.toFixed(3)}</td>
        <td>${e.power_dbm}</td>
        <td>${e.bandwidth_mhz.toFixed(3)}</td>
        <td>${e.modulation}</td>
        <td style="color:${e.threat_score>0.7?'#ff3333':'#ffaa00'}">${e.threat_score}</td>
        <td style="color:#666">${t}</td></tr>`;
    }
    document.getElementById('sigTable').innerHTML=html;
  }catch(e){}
}
setInterval(fetchData,2000);
setTimeout(fetchData,500);
</script>
</body></html>
SIGHTMLEOF
echo -e "${G}  [+] SIGINT Database HTML${NC}"

###############################################################################
# 12. CYBER OPERATIONS HTML
###############################################################################
echo -e "${C}[PHASE 9] Writing Cyber Operations view...${NC}"
cat > $WS/src/mos_c2_console/mos_c2_console/templates/cyber.html << 'CYBHTMLEOF'
<!DOCTYPE html>
<html><head>
<title>MOS 🔓 Cyber Operations</title>
<meta charset="utf-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;color:#00ff41;font-family:'Courier New',monospace}
.header{background:#0d0d0d;padding:8px 20px;display:flex;justify-content:space-between;
  align-items:center;border-bottom:1px solid #ff006644}
.header h1{font-size:16px;color:#ff0066}
.nav a{color:#00ccff;text-decoration:none;margin:0 8px;font-size:12px}
.nav a:hover{color:#fff}.nav a.active{color:#ff0066}
.main{display:grid;grid-template-columns:1fr 1fr 1fr;grid-template-rows:auto 1fr 1fr;
  height:calc(100vh - 45px);gap:2px;padding:2px}
.panel{background:#0d0d0d;border:1px solid #1a1a1a;border-radius:3px;padding:10px;overflow:auto}
.panel-title{color:#ff0066;font-size:11px;text-transform:uppercase;margin-bottom:6px;
  border-bottom:1px solid #ff006633;padding-bottom:3px;letter-spacing:2px}
.stats-bar{grid-column:1/4;display:flex;gap:10px;padding:6px 10px;flex-wrap:wrap}
.stat{background:#1a0a0a;border:1px solid #ff006633;padding:4px 10px;border-radius:3px}
.stat-val{font-size:16px;font-weight:bold}.stat-label{font-size:9px;color:#666}
table{width:100%;border-collapse:collapse;font-size:10px}
th{background:#1a0a1a;color:#ff0066;padding:5px;text-align:left;position:sticky;top:0}
td{padding:4px 5px;border-bottom:1px solid #111}
tr:hover{background:#ffffff08}
.sev-CRITICAL{color:#ff0000;font-weight:bold}.sev-HIGH{color:#ff6600}
.sev-MEDIUM{color:#ffaa00}.sev-LOW{color:#00ccff}
.net-card{padding:6px;margin:3px 0;background:#0a0a1a;border:1px solid #1a1a3a;
  border-radius:3px;font-size:10px}
.net-card.threat{border-color:#ff000044;background:#1a0a0a}
.alert-item{padding:4px 6px;margin:2px 0;font-size:10px;border-radius:3px;border-left:3px solid}
.alert-CRITICAL{border-color:#ff0000;background:#ff000011}
.alert-HIGH{border-color:#ff6600;background:#ff660011}
.alert-MEDIUM{border-color:#ffaa00;background:#ffaa0011}
.alert-LOW{border-color:#00ccff;background:#00ccff11}
.device-card{padding:5px;margin:3px 0;background:#0a1a0a;border:1px solid #00ff4122;
  border-radius:3px;font-size:10px}
.risk-CRITICAL{border-left:3px solid #ff0000}.risk-HIGH{border-left:3px solid #ff6600}
.risk-MEDIUM{border-left:3px solid #ffaa00}.risk-LOW{border-left:3px solid #00ccff}
.sec-badge{display:inline-block;padding:1px 4px;border-radius:2px;font-size:8px;margin-left:4px}
.sec-WPA3{background:#00ff4122;color:#00ff41}.sec-WPA2{background:#00ccff22;color:#00ccff}
.sec-WEP{background:#ff000022;color:#ff3333}.sec-OPEN{background:#ff000033;color:#ff0000;font-weight:bold}
.sec-WPA{background:#ffaa0022;color:#ffaa00}
.btn{padding:4px 10px;border:1px solid;border-radius:3px;background:transparent;
  color:inherit;cursor:pointer;font-family:inherit;font-size:10px;margin:2px}
.btn-red{color:#ff3333;border-color:#ff3333}.btn-red:hover{background:#ff333322}
.btn-cyan{color:#00ccff;border-color:#00ccff}.btn-cyan:hover{background:#00ccff22}
</style>
</head><body>
<div class="header">
  <h1>🔓 CYBER OPERATIONS CENTER</h1>
  <div class="nav">
    <a href="/">C2</a><a href="/ew">EW</a><a href="/sigint">SIGINT</a>
    <a href="/cyber" class="active">CYBER</a><a href="/dashboard">TWIN</a>
    <a href="/awacs">AWACS</a><a href="/hal">HAL</a>
  </div>
</div>
<div class="main">
  <div class="stats-bar">
    <div class="stat"><div class="stat-val" id="netHosts" style="color:#00ccff">0</div><div class="stat-label">Network Hosts</div></div>
    <div class="stat"><div class="stat-val" id="wifiNets" style="color:#00ff41">0</div><div class="stat-label">WiFi Networks</div></div>
    <div class="stat"><div class="stat-val" id="threatNets" style="color:#ff6600">0</div><div class="stat-label">Threat Networks</div></div>
    <div class="stat"><div class="stat-val" id="openVulns" style="color:#ff0000">0</div><div class="stat-label">Open Vulns</div></div>
    <div class="stat"><div class="stat-val" id="critVulns" style="color:#ff0000">0</div><div class="stat-label">Critical</div></div>
    <div class="stat"><div class="stat-val" id="idsAlerts" style="color:#ff8800">0</div><div class="stat-label">IDS Alerts</div></div>
    <div class="stat"><div class="stat-val" id="scanCount" style="color:#666">0</div><div class="stat-label">Scans Run</div></div>
  </div>
  <!-- WiFi Networks -->
  <div class="panel">
    <div class="panel-title">📶 WiFi Environment</div>
    <div id="wifiList" style="max-height:calc(50vh - 60px);overflow-y:auto"></div>
  </div>
  <!-- Discovered Devices -->
  <div class="panel">
    <div class="panel-title">🖥 Discovered Devices</div>
    <div id="deviceList" style="max-height:calc(50vh - 60px);overflow-y:auto"></div>
  </div>
  <!-- IDS Alerts -->
  <div class="panel">
    <div class="panel-title">🛡 Intrusion Detection</div>
    <div id="idsList" style="max-height:calc(50vh - 60px);overflow-y:auto"></div>
  </div>
  <!-- Vulnerabilities -->
  <div class="panel" style="grid-column:1/3">
    <div class="panel-title">🔴 Vulnerability Findings</div>
    <div style="max-height:calc(50vh - 60px);overflow-y:auto">
      <table><thead><tr>
        <th>CVE</th><th>SEVERITY</th><th>NAME</th><th>SERVICE</th><th>TARGET</th><th>TIME</th>
      </tr></thead><tbody id="vulnTable"></tbody></table>
    </div>
  </div>
  <!-- Cyber Tools -->
  <div class="panel">
    <div class="panel-title">🛠 Cyber Toolkit</div>
    <div style="font-size:10px">
      <div style="margin:5px 0"><b style="color:#ff0066">RECON</b></div>
      <button class="btn btn-cyan" onclick="runTool('nmap')">Nmap Scan</button>
      <button class="btn btn-cyan" onclick="runTool('kismet')">Kismet</button>
      <div style="margin:5px 0"><b style="color:#ff0066">WIFI</b></div>
      <button class="btn btn-cyan" onclick="runTool('aircrack-ng')">Aircrack-ng</button>
      <button class="btn btn-cyan" onclick="runTool('bettercap')">Bettercap</button>
      <div style="margin:5px 0"><b style="color:#ff0066">ANALYSIS</b></div>
      <button class="btn btn-cyan" onclick="runTool('tshark')">TShark</button>
      <button class="btn btn-cyan" onclick="runTool('wireshark')">Wireshark</button>
      <div style="margin:5px 0"><b style="color:#ff0066">COUNTER-UAS</b></div>
      <button class="btn btn-red" onclick="runTool('dji_droneid')">DroneID Scan</button>
      <button class="btn btn-red" onclick="runTool('remoteid_rx')">RemoteID RX</button>
    </div>
  </div>
</div>
<script>
function runTool(tool){
  fetch('/api/sdr/tool',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'START_TOOL',tool:tool})});
  alert('Tool launched: '+tool);
}
async function fetchData(){
  try{
    const[status,nets,vulns,alerts]=await Promise.all([
      fetch('/api/cyber/status').then(r=>r.json()),
      fetch('/api/cyber/networks').then(r=>r.json()),
      fetch('/api/cyber/vulns').then(r=>r.json()),
      fetch('/api/cyber/alerts').then(r=>r.json()),
    ]);
    // Stats
    document.getElementById('netHosts').textContent=status.network_hosts||0;
    document.getElementById('wifiNets').textContent=status.wifi_networks||0;
    document.getElementById('threatNets').textContent=status.threat_networks||0;
    document.getElementById('openVulns').textContent=status.vulnerabilities_open||0;
    document.getElementById('critVulns').textContent=status.critical_vulns||0;
    document.getElementById('idsAlerts').textContent=status.ids_alerts_24h||0;
    document.getElementById('scanCount').textContent=status.scan_count||0;
    // WiFi
    const wifiNets=nets.filter(n=>n.bssid);
    const devices=nets.filter(n=>n.ip);
    let whtml='';
    for(const n of wifiNets.sort((a,b)=>b.signal_dbm-a.signal_dbm).slice(0,20)){
      const threat=n.threat_level==='HIGH'||n.threat_level==='SUSPECT';
      whtml+=`<div class="net-card ${threat?'threat':''}">
        <b>${n.ssid||'[Hidden]'}</b> <span class="sec-badge sec-${n.security}">${n.security}</span>
        ${threat?'<span style="color:#ff3333;float:right">⚠ '+n.threat_level+'</span>':''}
        <br><span style="color:#666">Ch ${n.channel} | ${n.signal_dbm} dBm | ${n.band} | ${n.clients} clients | ${n.vendor}</span>
      </div>`;
    }
    document.getElementById('wifiList').innerHTML=whtml||'<div style="color:#666">Scanning...</div>';
    // Devices
    let dhtml='';
    for(const d of Object.values(devices).slice(-20)){
      dhtml+=`<div class="device-card risk-${d.risk||'LOW'}">
        <b>${d.ip}</b> <span style="color:#00ccff">${d.hostname||'?'}</span>
        <span style="float:right;color:#666">${d.os||'?'}</span><br>
        <span style="color:#666">Ports: ${(d.open_ports||[]).join(', ')} | ${d.vendor||'?'}</span>
      </div>`;
    }
    document.getElementById('deviceList').innerHTML=dhtml||'<div style="color:#666">Scanning...</div>';
    // Vulns
    let vhtml='';
    for(const v of vulns.slice(-30).reverse()){
      const t=new Date(v.found_at*1000).toLocaleTimeString();
      vhtml+=`<tr><td>${v.id}</td><td class="sev-${v.severity}">${v.severity}</td>
        <td>${v.name}</td><td>${v.service}</td><td>${v.target_ip} (${v.target_host||'?'})</td>
        <td style="color:#666">${t}</td></tr>`;
    }
    document.getElementById('vulnTable').innerHTML=vhtml;
    // IDS
    let ahtml='';
    for(const a of alerts.slice(-15).reverse()){
      const t=new Date(a.timestamp*1000).toLocaleTimeString();
      ahtml+=`<div class="alert-item alert-${a.severity}">${t} <b>[${a.severity}]</b>
        ${a.event}<br><span style="color:#666">${a.source} → ${a.action_taken}</span></div>`;
    }
    document.getElementById('idsList').innerHTML=ahtml||'<div style="color:#666">Monitoring...</div>';
  }catch(e){}
}
setInterval(fetchData,3000);
setTimeout(fetchData,500);
</script>
</body></html>
CYBHTMLEOF
echo -e "${G}  [+] Cyber Operations HTML${NC}"

###############################################################################
# 13. PATCH C2_SERVER.PY — Add EW imports and registration
###############################################################################
echo -e "${C}[PHASE 9] Patching c2_server.py to include EW routes...${NC}"

C2_FILE=$WS/src/mos_c2_console/mos_c2_console/c2_server.py

# Check if already patched
if grep -q "register_ew_routes" "$C2_FILE" 2>/dev/null; then
    echo -e "${Y}  [!] c2_server.py already patched — skipping${NC}"
else
    # Add import near top (after other imports)
    sed -i '/^import json/a\
# Phase 9: EW/SIGINT/Cyber routes\
try:\
    from mos_c2_console.ew_api import register_ew_routes\
    EW_AVAILABLE = True\
except ImportError:\
    EW_AVAILABLE = False' "$C2_FILE"

    # Add registration call — find where app routes are defined and add after Flask app creation
    # Look for "app = Flask" or similar and add registration after the node+app are both ready
    # We'll add it right before the main spin/run section
    sed -i '/flask_thread.*=.*Thread/i\
    # Register EW/SIGINT/Cyber routes (Phase 9)\
    if EW_AVAILABLE:\
        register_ew_routes(app, node)\
        node.get_logger().info("[MOS] EW/SIGINT/Cyber suite registered (Phase 9)")' "$C2_FILE"

    echo -e "${G}  [+] c2_server.py patched with EW route registration${NC}"
fi

###############################################################################
# 14. UPDATE LAUNCH SCRIPT
###############################################################################
echo -e "${C}[PHASE 9] Updating launch_mos.sh with EW nodes...${NC}"

LAUNCH_FILE=$WS/launch_mos.sh

if grep -q "ew_manager" "$LAUNCH_FILE" 2>/dev/null; then
    echo -e "${Y}  [!] launch_mos.sh already includes EW nodes — skipping${NC}"
else
    # Add EW nodes before the C2 console launch
    sed -i '/# Terminal.*C2 Console\|c2_server\|c2 console/i\
# ── EW/SIGINT/CYBER NODES (Phase 9) ──────────────────\
echo -e "${C}[MOS] Starting EW/SIGINT/Cyber suite...${NC}"\
ros2 run mos_ew ew_manager &\
sleep 0.3\
ros2 run mos_ew sigint_collector &\
sleep 0.3\
ros2 run mos_ew cyber_ops &\
sleep 0.3\
ros2 run mos_ew sdr_bridge &\
sleep 0.3\
ros2 run mos_ew rf_analyzer &\
sleep 0.3\
echo -e "${G}[MOS] EW suite online — 5 nodes${NC}"\
' "$LAUNCH_FILE"

    echo -e "${G}  [+] launch_mos.sh updated with 5 EW nodes${NC}"
fi

###############################################################################
# 15. BUILD
###############################################################################
echo ""
echo -e "${C}[PHASE 9] Building workspace...${NC}"
cd $WS
colcon build 2>&1 | tail -5
source install/setup.bash

###############################################################################
# PHASE 9 COMPLETE
###############################################################################
echo ""
echo -e "${R}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${R}║${NC}  ${G}✅ PHASE 9 COMPLETE — EW/SIGINT/CYBER WARFARE SUITE${NC}        ${R}║${NC}"
echo -e "${R}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${M}NEW NODES (5):${NC}"
echo "  ⚡ ew_manager       — EW operations center, jamming, RF environment"
echo "  📡 sigint_collector  — SIGINT collection, emitter geolocation, DF"
echo "  🔓 cyber_ops         — Network recon, WiFi/BT scan, IDS, vuln scan"
echo "  📻 sdr_bridge        — SDR hardware detection, DragonOS tool bridge"
echo "  📊 rf_analyzer       — Spectrum analysis, waterfall data, anomalies"
echo ""
echo -e "${M}NEW WEB VIEWS (3):${NC}"
echo "  /ew      — EW Dashboard (spectrum analyzer + waterfall + emitter map)"
echo "  /sigint  — SIGINT Database (signal table + waveform + tool recommendations)"
echo "  /cyber   — Cyber Ops Center (WiFi scan + devices + vulns + IDS alerts)"
echo ""
echo -e "${M}NEW API ENDPOINTS (18):${NC}"
echo "  GET  /api/ew/status       GET  /api/ew/emitters     GET  /api/ew/spectrum"
echo "  GET  /api/ew/signals      GET  /api/ew/bearings     GET  /api/ew/alerts"
echo "  GET  /api/ew/cop          GET  /api/ew/anomalies    POST /api/ew/jam"
echo "  POST /api/ew/scan         POST /api/ew/df           GET  /api/cyber/status"
echo "  GET  /api/cyber/networks  GET  /api/cyber/vulns     GET  /api/cyber/alerts"
echo "  GET  /api/sdr/status      POST /api/sdr/tool"
echo ""
echo -e "${M}SDR HARDWARE SUPPORTED:${NC}"
echo "  RTL-SDR v3/v4 · HackRF One · Airspy · Ettus USRP B205/X310"
echo "  LimeSDR · KrakenSDR (Direction Finding)"
echo ""
echo -e "${M}DRAGONOS TOOLS INDEXED (20+):${NC}"
echo "  GNU Radio · GQRX · SDR++ · SDR Trunk · rtl_433 · dump1090"
echo "  multimon-ng · Kismet · Aircrack-ng · Bettercap · Nmap · Wireshark"
echo "  URH · inspectrum · Direwolf · gr-gsm · kalibrate · srsRAN"
echo "  KrakenSDR DOA · GPredict · SatDump · DJI DroneID · RemoteID RX"
echo ""
echo -e "${M}EW-CAPABLE ASSETS:${NC}"
echo "  AIR:  MVRX-A03 (SIGINT) · MVRX-A04 (EW Attack) · MVRX-A05 (Cyber)"
echo "  GND:  MVRX-G03 (SIGINT+DF) · MVRX-G04 (Cyber Ground)"
echo "  C2:   AWACS-1 (SIGINT Fusion) · AWACS-2 (EW Coordinator)"
echo ""
echo -e "${C}SYSTEM TOTALS:${NC}"
echo "  Nodes:      20 (was 15)"
echo "  Web Views:  10 (was 7)"
echo "  API Endpoints: ~43 (was ~25)"
echo "  ROS 2 Topics:  ~35 (was ~21)"
echo ""
echo -e "${G}Launch: ./launch_mos.sh${NC}"
echo -e "${G}EW Dashboard: http://localhost:5000/ew${NC}"
echo -e "${G}SIGINT DB:    http://localhost:5000/sigint${NC}"
echo -e "${G}Cyber Ops:    http://localhost:5000/cyber${NC}"
