"""Voice Command Natural Language Parser"""
import re

class VoiceParser:
    PATTERNS = [
        (r"(?:deploy|move|send|navigate)\s+(\S+[\s-]?\d+)\s+(?:to|toward)\s+(?:coordinates?\s+)?(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)", "move"),
        (r"(?:jam|block)\s+(?:frequency\s+)?(\d+\.?\d*)\s*(?:megahertz|mhz)?", "jam"),
        (r"(?:engage|intercept|neutralize|destroy)\s+(\S+[\s-]?\S*[\s-]?\d+)", "engage"),
        (r"(?:status|report|sitrep)\s+(\S+[\s-]?\d+)", "status"),
        (r"(?:status|sitrep)\s+(?:all|platoon)", "status_all"),
        (r"(?:set\s+)?speed\s+(\d+\.?\d*)\s*x?", "set_speed"),
        (r"(?:generate|create|suggest)\s+(?:course|coa|plan)", "generate_coa"),
        (r"(?:block|ban)\s+(?:ip\s+)?(\d+\.\d+\.\d+\.\d+)", "block_ip"),
        (r"(?:halt|stop|freeze)\s+(\S+[\s-]?\d+)", "halt"),
        (r"(?:halt|stop|freeze)\s+all", "halt_all"),
        (r"(?:return\s+to\s+base|rtb)\s+(\S+[\s-]?\d+)", "rtb"),
        (r"(?:return\s+to\s+base|rtb)\s+all", "rtb_all"),
    ]

    @staticmethod
    def _norm(text):
        t = text.upper().strip()
        t = re.sub(r"\s+", "-", t)
        m = re.match(r"(\w+)-(\d+)", t)
        return f"{m.group(1)}-{m.group(2).zfill(2)}" if m else t

    def parse(self, transcript):
        text = transcript.strip()
        for pattern, cmd in self.PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if not m:
                continue
            g = m.groups()
            if cmd == "move" and len(g) >= 3:
                return {"command": "move", "asset_id": self._norm(g[0]),
                        "lat": float(g[1]), "lng": float(g[2]),
                        "confidence": 0.9, "raw": transcript}
            if cmd == "jam":
                return {"command": "jam", "freq_mhz": float(g[0]),
                        "confidence": 0.85, "raw": transcript}
            if cmd == "engage":
                return {"command": "engage", "threat_id": self._norm(g[0]),
                        "confidence": 0.9, "raw": transcript}
            if cmd == "status":
                return {"command": "status", "asset_id": self._norm(g[0]),
                        "confidence": 0.95, "raw": transcript}
            if cmd == "status_all":
                return {"command": "status_all", "confidence": 0.95, "raw": transcript}
            if cmd == "set_speed":
                return {"command": "set_speed", "speed": float(g[0]),
                        "confidence": 0.95, "raw": transcript}
            if cmd == "generate_coa":
                return {"command": "generate_coa", "confidence": 0.9, "raw": transcript}
            if cmd == "block_ip":
                return {"command": "block_ip", "ip": g[0],
                        "confidence": 0.9, "raw": transcript}
            if cmd == "halt":
                return {"command": "halt", "asset_id": self._norm(g[0]),
                        "confidence": 0.9, "raw": transcript}
            if cmd in ("halt_all", "rtb_all"):
                return {"command": cmd, "confidence": 0.9, "raw": transcript}
            if cmd == "rtb":
                return {"command": "rtb", "asset_id": self._norm(g[0]),
                        "confidence": 0.9, "raw": transcript}
        return {"command": "unknown", "confidence": 0, "raw": transcript,
                "error": "Command not recognized"}
