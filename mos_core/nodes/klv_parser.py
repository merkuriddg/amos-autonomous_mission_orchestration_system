#!/usr/bin/env python3
"""AMOS Phase 25 — KLV Metadata Parser (STANAG 4609)

Parses Key-Length-Value (KLV) metadata from UAS Full Motion Video streams.
Implements a subset of MISB ST 0601 — UAS Datalink Local Set.

Key fields extracted:
  Tag 2  — UNIX Timestamp
  Tag 5  — Platform Heading
  Tag 13 — Sensor Latitude
  Tag 14 — Sensor Longitude
  Tag 15 — Sensor True Altitude
  Tag 17 — Sensor Horizontal FOV
  Tag 18 — Sensor Vertical FOV
  Tag 21 — Slant Range
  Tag 23 — Target Latitude  (frame center)
  Tag 24 — Target Longitude (frame center)
  Tag 40 — Target Width
  Tag 65 — Platform Latitude
  Tag 66 — Platform Longitude
  Tag 67 — Platform Altitude
  Tag 11 — Image Source Sensor (sensor name string)
"""

import struct
import time
import logging
from datetime import datetime, timezone

log = logging.getLogger("amos.klv")

# MISB ST 0601 Universal Key (16-byte UDS key)
UAS_LOCAL_SET_KEY = bytes([
    0x06, 0x0E, 0x2B, 0x34, 0x02, 0x0B, 0x01, 0x01,
    0x0E, 0x01, 0x03, 0x01, 0x01, 0x00, 0x00, 0x00,
])

# Tag definitions: tag_number -> (name, parser_function)
# Parsers convert raw bytes to Python values

def _parse_uint64_timestamp(data: bytes) -> float:
    """Tag 2: UNIX timestamp in microseconds."""
    if len(data) >= 8:
        return struct.unpack(">Q", data[:8])[0] / 1_000_000
    return 0.0

def _parse_uint16_deg(data: bytes, scale: float = 360.0) -> float:
    """Parse unsigned 16-bit scaled to degrees."""
    if len(data) >= 2:
        raw = struct.unpack(">H", data[:2])[0]
        return raw / 65535 * scale
    return 0.0

def _parse_int32_lat(data: bytes) -> float:
    """Tag 13/23/65: Latitude in ±90° mapped from signed 32-bit."""
    if len(data) >= 4:
        raw = struct.unpack(">i", data[:4])[0]
        return raw / (2**31 - 1) * 90.0
    return 0.0

def _parse_int32_lng(data: bytes) -> float:
    """Tag 14/24/66: Longitude in ±180° mapped from signed 32-bit."""
    if len(data) >= 4:
        raw = struct.unpack(">i", data[:4])[0]
        return raw / (2**31 - 1) * 180.0
    return 0.0

def _parse_uint16_alt(data: bytes) -> float:
    """Tag 15/67: Altitude mapped from uint16 to -900..19000m."""
    if len(data) >= 2:
        raw = struct.unpack(">H", data[:2])[0]
        return raw / 65535 * 19900 - 900
    return 0.0

def _parse_uint32_range(data: bytes) -> float:
    """Tag 21: Slant range in metres from uint32 (0..5M metres)."""
    if len(data) >= 4:
        raw = struct.unpack(">I", data[:4])[0]
        return raw / (2**32 - 1) * 5_000_000
    return 0.0

def _parse_uint16_fov(data: bytes) -> float:
    """Tag 17/18: FOV in degrees from uint16 (0..180°)."""
    if len(data) >= 2:
        raw = struct.unpack(">H", data[:2])[0]
        return raw / 65535 * 180.0
    return 0.0

def _parse_string(data: bytes) -> str:
    """Tag 11: Sensor name as UTF-8 string."""
    return data.decode("utf-8", errors="ignore").strip("\x00")

def _parse_uint16_heading(data: bytes) -> float:
    """Tag 5: Platform heading 0-360°."""
    return _parse_uint16_deg(data, 360.0)

def _parse_uint16_width(data: bytes) -> float:
    """Tag 40: Target width in metres (uint16, 0..10000m)."""
    if len(data) >= 2:
        raw = struct.unpack(">H", data[:2])[0]
        return raw / 65535 * 10000
    return 0.0


TAG_PARSERS = {
    2:  ("timestamp_us", _parse_uint64_timestamp),
    5:  ("platform_heading_deg", _parse_uint16_heading),
    11: ("sensor_name", _parse_string),
    13: ("sensor_lat", _parse_int32_lat),
    14: ("sensor_lng", _parse_int32_lng),
    15: ("sensor_alt_m", _parse_uint16_alt),
    17: ("horizontal_fov_deg", _parse_uint16_fov),
    18: ("vertical_fov_deg", _parse_uint16_fov),
    21: ("slant_range_m", _parse_uint32_range),
    23: ("target_lat", _parse_int32_lat),
    24: ("target_lng", _parse_int32_lng),
    40: ("target_width_m", _parse_uint16_width),
    65: ("platform_lat", _parse_int32_lat),
    66: ("platform_lng", _parse_int32_lng),
    67: ("platform_alt_m", _parse_uint16_alt),
}


class KLVParser:
    """Parses KLV metadata from MISB ST 0601 UAS Datalink Local Set."""

    def __init__(self):
        self.parsed_count = 0
        self.error_count = 0
        self.last_parsed = {}

    def parse_packet(self, data: bytes) -> dict:
        """Parse a single KLV packet (Local Set).

        Args:
            data: raw bytes starting with the 16-byte UDS key

        Returns:
            dict of parsed metadata fields
        """
        result = {}
        try:
            offset = 0
            # Check for UAS Local Set key
            if data[:16] == UAS_LOCAL_SET_KEY:
                offset = 16
                # Read BER length
                length, offset = self._read_ber_length(data, offset)
                end = offset + length
            else:
                # Assume we're starting inside the local set
                end = len(data)

            # Parse tags
            while offset < end - 1:
                tag = data[offset]
                offset += 1
                if offset >= end:
                    break
                tag_len = data[offset]
                offset += 1
                if offset + tag_len > end:
                    break
                tag_data = data[offset:offset + tag_len]
                offset += tag_len

                if tag in TAG_PARSERS:
                    name, parser = TAG_PARSERS[tag]
                    try:
                        result[name] = parser(tag_data)
                    except Exception:
                        pass

            # Convert timestamp to ISO
            if "timestamp_us" in result:
                ts = result["timestamp_us"]
                try:
                    result["timestamp_iso"] = datetime.fromtimestamp(
                        ts, tz=timezone.utc).isoformat()
                except Exception:
                    result["timestamp_iso"] = ""

            self.parsed_count += 1
            self.last_parsed = result
        except Exception as e:
            self.error_count += 1
            log.error(f"KLV parse error: {e}")

        return result

    def parse_from_dict(self, klv_dict: dict) -> dict:
        """Parse metadata from a pre-extracted dict (for non-binary sources).

        Maps common field names to canonical AMOS format.
        """
        result = {}
        mapping = {
            "platformLatitude": "platform_lat",
            "platformLongitude": "platform_lng",
            "platformAltitude": "platform_alt_m",
            "platformHeading": "platform_heading_deg",
            "sensorLatitude": "sensor_lat",
            "sensorLongitude": "sensor_lng",
            "sensorAltitude": "sensor_alt_m",
            "targetLatitude": "target_lat",
            "targetLongitude": "target_lng",
            "slantRange": "slant_range_m",
            "horizontalFOV": "horizontal_fov_deg",
            "verticalFOV": "vertical_fov_deg",
            "sensorName": "sensor_name",
            "targetWidth": "target_width_m",
        }
        for src_key, dst_key in mapping.items():
            if src_key in klv_dict:
                result[dst_key] = klv_dict[src_key]
        # Pass through already-canonical keys
        for key in TAG_PARSERS.values():
            name = key[0]
            if name in klv_dict:
                result[name] = klv_dict[name]

        self.parsed_count += 1
        self.last_parsed = result
        return result

    def _read_ber_length(self, data: bytes, offset: int) -> tuple:
        """Read BER-encoded length."""
        first = data[offset]
        offset += 1
        if first < 128:
            return first, offset
        num_bytes = first & 0x7F
        length = 0
        for _ in range(num_bytes):
            length = (length << 8) | data[offset]
            offset += 1
        return length, offset

    def get_stats(self) -> dict:
        return {
            "parsed_packets": self.parsed_count,
            "errors": self.error_count,
            "tags_supported": len(TAG_PARSERS),
        }
