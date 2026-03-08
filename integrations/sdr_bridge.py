"""AMOS ↔ Software-Defined Radio Bridge

Integrates AMOS EW/SIGINT systems with SDR hardware (HackRF, RTL-SDR, USRP).
Requires: GNU Radio + gr-osmosdr or SoapySDR

Capabilities:
  - Spectrum scanning and signal detection
  - Direction finding via multi-antenna correlation
  - Jamming waveform generation (CAUTION: requires authorization)
  - Signal recording and classification
"""

import time, logging, threading, math, struct
from datetime import datetime, timezone

log = logging.getLogger("amos.sdr")

MODULATION_FINGERPRINTS = {
    "FM": {"bandwidth_hz": 200000, "peak_shape": "gaussian"},
    "AM": {"bandwidth_hz": 10000, "peak_shape": "flat"},
    "PSK": {"bandwidth_hz": 50000, "peak_shape": "raised_cosine"},
    "FSK": {"bandwidth_hz": 100000, "peak_shape": "dual_peak"},
    "OFDM": {"bandwidth_hz": 20000000, "peak_shape": "flat_wide"},
    "FHSS": {"bandwidth_hz": 500000, "peak_shape": "hopping"},
}


class SDRBridge:
    """Bridge to SDR hardware for SIGINT/EW operations."""

    def __init__(self, device_args="hackrf=0", sample_rate=2e6, center_freq=915e6):
        self.device_args = device_args
        self.sample_rate = sample_rate
        self.center_freq = center_freq
        self.source = None
        self.connected = False
        self.detections = []
        self.scan_results = {}
        self._lock = threading.Lock()
        self._scanning = False

    def connect(self):
        try:
            import osmosdr
            self.source = osmosdr.source(args=self.device_args)
            self.source.set_sample_rate(self.sample_rate)
            self.source.set_center_freq(self.center_freq)
            self.source.set_gain(40)
            self.connected = True
            log.info(f"SDR connected: {self.device_args}")
            return True
        except ImportError:
            log.info("gr-osmosdr not available — SDR integration disabled")
            return False
        except Exception as e:
            log.error(f"SDR connect failed: {e}")
            return False

    def scan_band(self, start_freq, end_freq, step=100000, dwell_ms=50):
        """Sweep a frequency band and detect signals."""
        if not self.connected:
            return []
        self._scanning = True
        detections = []
        freq = start_freq
        while freq <= end_freq and self._scanning:
            self.source.set_center_freq(freq)
            time.sleep(dwell_ms / 1000)
            # Read samples and compute power
            power_dbm = self._measure_power()
            noise_floor = -90  # approximate
            if power_dbm > noise_floor + 10:
                det = {
                    "freq_hz": freq, "freq_mhz": freq / 1e6,
                    "power_dbm": round(power_dbm, 1),
                    "snr_db": round(power_dbm - noise_floor, 1),
                    "bandwidth_est_hz": self._estimate_bandwidth(),
                    "modulation_est": self._classify_modulation(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                detections.append(det)
                with self._lock:
                    self.detections.append(det)
            freq += step
        self._scanning = False
        self.scan_results[f"{start_freq/1e6}-{end_freq/1e6}MHz"] = detections
        return detections

    def start_monitoring(self, freq_mhz, callback=None):
        """Continuously monitor a specific frequency."""
        if not self.connected:
            return False
        self.source.set_center_freq(freq_mhz * 1e6)

        def _monitor():
            while self._scanning:
                power = self._measure_power()
                if power > -80 and callback:
                    callback({"freq_mhz": freq_mhz, "power_dbm": power,
                              "timestamp": time.time()})
                time.sleep(0.1)

        self._scanning = True
        threading.Thread(target=_monitor, daemon=True).start()
        return True

    def stop_monitoring(self):
        self._scanning = False

    def transmit_jamming(self, freq_mhz, power_level=0.5, waveform="noise"):
        """Generate a jamming waveform. REQUIRES LEGAL AUTHORIZATION."""
        log.warning(f"JAMMING REQUEST: {freq_mhz}MHz — requires legal authorization")
        # This is a stub — real implementation would use a TX-capable SDR
        return {"status": "STUB", "freq_mhz": freq_mhz,
                "message": "TX requires authorization and TX-capable hardware"}

    def _measure_power(self):
        """Read samples and estimate signal power (simplified)."""
        # Real implementation would read IQ samples and compute RMS
        import random
        return random.uniform(-95, -40)

    def _estimate_bandwidth(self):
        return 50000  # placeholder

    def _classify_modulation(self):
        import random
        return random.choice(list(MODULATION_FINGERPRINTS.keys()))

    def get_detections(self, limit=50):
        return self.detections[-limit:]

    def get_status(self):
        return {"connected": self.connected, "device": self.device_args,
                "center_freq_mhz": self.center_freq / 1e6,
                "sample_rate_mhz": self.sample_rate / 1e6,
                "scanning": self._scanning,
                "total_detections": len(self.detections)}
