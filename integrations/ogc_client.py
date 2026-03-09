#!/usr/bin/env python3
"""AMOS Phase 27 — OGC WMS / WFS Client

Connects to OGC-compliant geospatial servers for:
  - WMS (Web Map Service)   — map tile/image retrieval
  - WFS (Web Feature Service) — vector feature queries (GeoJSON)

Supports GetCapabilities, GetMap, GetFeature operations.
"""

import logging
import time
import uuid
from urllib.parse import urlencode
from datetime import datetime, timezone

log = logging.getLogger("amos.ogc")


class OGCClient:
    """OGC WMS/WFS client for AMOS geospatial layer ingestion."""

    def __init__(self):
        self.wms_endpoints = {}    # {name: url}
        self.wfs_endpoints = {}    # {name: url}
        self.layers = {}           # cached layer metadata
        self.request_log = []
        self.stats = {"wms_requests": 0, "wfs_requests": 0, "errors": 0}

    # ── Endpoint management ──────────────────────────────────
    def add_wms(self, name: str, url: str) -> dict:
        """Register a WMS endpoint."""
        self.wms_endpoints[name] = url.rstrip("/")
        log.info(f"WMS endpoint added: {name} → {url}")
        return {"name": name, "url": url, "type": "WMS"}

    def add_wfs(self, name: str, url: str) -> dict:
        """Register a WFS endpoint."""
        self.wfs_endpoints[name] = url.rstrip("/")
        log.info(f"WFS endpoint added: {name} → {url}")
        return {"name": name, "url": url, "type": "WFS"}

    def remove_endpoint(self, name: str) -> bool:
        removed = False
        if name in self.wms_endpoints:
            del self.wms_endpoints[name]
            removed = True
        if name in self.wfs_endpoints:
            del self.wfs_endpoints[name]
            removed = True
        return removed

    # ── WMS operations ───────────────────────────────────────
    def wms_get_capabilities_url(self, name: str) -> str:
        """Build WMS GetCapabilities URL."""
        base = self.wms_endpoints.get(name)
        if not base:
            return ""
        params = {"SERVICE": "WMS", "REQUEST": "GetCapabilities",
                  "VERSION": "1.3.0"}
        return f"{base}?{urlencode(params)}"

    def wms_get_map_url(self, name: str, layers: str, bbox: dict,
                        width: int = 512, height: int = 512,
                        srs: str = "EPSG:4326",
                        img_format: str = "image/png") -> str:
        """Build WMS GetMap URL.

        Args:
            bbox: {"min_lat", "min_lng", "max_lat", "max_lng"}
        """
        base = self.wms_endpoints.get(name)
        if not base:
            return ""
        bbox_str = f"{bbox['min_lng']},{bbox['min_lat']},{bbox['max_lng']},{bbox['max_lat']}"
        params = {
            "SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0",
            "LAYERS": layers, "CRS": srs,
            "BBOX": bbox_str, "WIDTH": width, "HEIGHT": height,
            "FORMAT": img_format, "TRANSPARENT": "TRUE",
        }
        self.stats["wms_requests"] += 1
        url = f"{base}?{urlencode(params)}"
        self._log_request("WMS", "GetMap", name, layers)
        return url

    def wms_fetch_map(self, name: str, layers: str, bbox: dict,
                      width: int = 512, height: int = 512) -> dict:
        """Simulate fetching a WMS map tile (returns URL + metadata).

        In production, this would use urllib/requests to fetch the image.
        """
        url = self.wms_get_map_url(name, layers, bbox, width, height)
        if not url:
            self.stats["errors"] += 1
            return {"error": f"Unknown WMS endpoint: {name}"}
        return {
            "id": f"WMS-{uuid.uuid4().hex[:8]}",
            "url": url, "layers": layers,
            "bbox": bbox, "width": width, "height": height,
            "format": "image/png",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── WFS operations ───────────────────────────────────────
    def wfs_get_capabilities_url(self, name: str) -> str:
        """Build WFS GetCapabilities URL."""
        base = self.wfs_endpoints.get(name)
        if not base:
            return ""
        params = {"SERVICE": "WFS", "REQUEST": "GetCapabilities",
                  "VERSION": "2.0.0"}
        return f"{base}?{urlencode(params)}"

    def wfs_get_feature_url(self, name: str, type_name: str,
                            bbox: dict = None, max_features: int = 100,
                            srs: str = "EPSG:4326",
                            output_format: str = "application/json") -> str:
        """Build WFS GetFeature URL."""
        base = self.wfs_endpoints.get(name)
        if not base:
            return ""
        params = {
            "SERVICE": "WFS", "REQUEST": "GetFeature", "VERSION": "2.0.0",
            "TYPENAMES": type_name, "SRSNAME": srs,
            "OUTPUTFORMAT": output_format, "COUNT": max_features,
        }
        if bbox:
            params["BBOX"] = (f"{bbox['min_lat']},{bbox['min_lng']},"
                              f"{bbox['max_lat']},{bbox['max_lng']},{srs}")
        self.stats["wfs_requests"] += 1
        url = f"{base}?{urlencode(params)}"
        self._log_request("WFS", "GetFeature", name, type_name)
        return url

    def wfs_fetch_features(self, name: str, type_name: str,
                           bbox: dict = None,
                           max_features: int = 100) -> dict:
        """Simulate fetching WFS features (returns URL + metadata).

        In production, this would parse the GeoJSON response.
        """
        url = self.wfs_get_feature_url(name, type_name, bbox, max_features)
        if not url:
            self.stats["errors"] += 1
            return {"error": f"Unknown WFS endpoint: {name}"}
        return {
            "id": f"WFS-{uuid.uuid4().hex[:8]}",
            "url": url, "type_name": type_name,
            "bbox": bbox, "max_features": max_features,
            "format": "GeoJSON",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── Layer management ─────────────────────────────────────
    def register_layer(self, name: str, layer_type: str,
                       endpoint_name: str, layer_id: str,
                       description: str = "") -> dict:
        """Register a known layer for quick access."""
        layer = {
            "name": name, "type": layer_type,
            "endpoint": endpoint_name, "layer_id": layer_id,
            "description": description,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        self.layers[name] = layer
        return layer

    def get_layers(self) -> dict:
        return dict(self.layers)

    # ── Internal ─────────────────────────────────────────────
    def _log_request(self, service: str, operation: str,
                     endpoint: str, layer: str):
        entry = {
            "service": service, "operation": operation,
            "endpoint": endpoint, "layer": layer,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.request_log.append(entry)
        if len(self.request_log) > 500:
            self.request_log = self.request_log[-500:]

    def get_request_log(self, limit: int = 50) -> list:
        return self.request_log[-limit:]

    def get_status(self) -> dict:
        return {
            "wms_endpoints": len(self.wms_endpoints),
            "wfs_endpoints": len(self.wfs_endpoints),
            "registered_layers": len(self.layers),
            **self.stats,
        }

    def get_endpoints(self) -> dict:
        return {
            "wms": dict(self.wms_endpoints),
            "wfs": dict(self.wfs_endpoints),
        }
