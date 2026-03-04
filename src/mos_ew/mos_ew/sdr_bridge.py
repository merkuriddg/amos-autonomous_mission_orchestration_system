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
