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
