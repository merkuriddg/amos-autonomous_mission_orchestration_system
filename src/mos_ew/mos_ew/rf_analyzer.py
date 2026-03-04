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
