#!/usr/bin/env python3
"""AMOS Phase 25 — Video Pipeline Engine

Manages multiple live video feeds from ISR assets.
RTSP stream handling via OpenCV, frame extraction, thumbnail gen,
feed state machine, and KLV metadata overlay integration.

Requires: opencv-python (pip install opencv-python)
"""

import time
import uuid
import threading
import logging
import base64
from datetime import datetime, timezone

log = logging.getLogger("amos.video")

FEED_STATES = ("IDLE", "CONNECTING", "STREAMING", "PAUSED", "DISCONNECTED", "ERROR")


class VideoFeed:
    """Represents a single video feed from an ISR asset."""

    def __init__(self, feed_id, source_url, asset_id="", sensor_name=""):
        self.feed_id = feed_id
        self.source_url = source_url
        self.asset_id = asset_id
        self.sensor_name = sensor_name
        self.state = "IDLE"
        self.width = 0
        self.height = 0
        self.fps = 0
        self.frame_count = 0
        self.last_frame_time = None
        self.capture = None
        self._thread = None
        self._running = False
        self._lock = threading.Lock()
        self._latest_frame = None
        self._latest_thumbnail = None
        self.klv_metadata = {}
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.stats = {"frames_captured": 0, "frames_dropped": 0, "errors": 0}

    def start(self) -> bool:
        """Start capturing from the source URL."""
        if self.state == "STREAMING":
            return True
        self.state = "CONNECTING"
        try:
            import cv2
            self.capture = cv2.VideoCapture(self.source_url)
            if not self.capture.isOpened():
                self.state = "ERROR"
                self.stats["errors"] += 1
                return False
            self.width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.fps = self.capture.get(cv2.CAP_PROP_FPS) or 30
            self._running = True
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()
            self.state = "STREAMING"
            log.info(f"Video feed started: {self.feed_id} ({self.width}x{self.height} @ {self.fps}fps)")
            return True
        except ImportError:
            log.warning("opencv-python not installed — video pipeline disabled")
            self.state = "ERROR"
            return False
        except Exception as e:
            log.error(f"Video feed start failed: {e}")
            self.state = "ERROR"
            self.stats["errors"] += 1
            return False

    def stop(self):
        self._running = False
        if self.capture:
            try:
                self.capture.release()
            except Exception:
                pass
        self.state = "DISCONNECTED"

    def pause(self):
        self._running = False
        self.state = "PAUSED"

    def resume(self):
        if self.state == "PAUSED" and self.capture and self.capture.isOpened():
            self._running = True
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()
            self.state = "STREAMING"

    def get_frame_jpeg(self) -> bytes:
        """Get latest frame as JPEG bytes."""
        with self._lock:
            return self._latest_frame or b""

    def get_frame_b64(self) -> str:
        """Get latest frame as base64-encoded JPEG."""
        frame = self.get_frame_jpeg()
        return base64.b64encode(frame).decode("ascii") if frame else ""

    def get_thumbnail_b64(self) -> str:
        """Get latest thumbnail as base64-encoded JPEG."""
        with self._lock:
            thumb = self._latest_thumbnail or b""
        return base64.b64encode(thumb).decode("ascii") if thumb else ""

    def _capture_loop(self):
        """Background capture loop."""
        import cv2
        target_interval = 1.0 / min(self.fps, 15)  # cap at 15fps for processing
        while self._running:
            try:
                ret, frame = self.capture.read()
                if not ret:
                    self.stats["frames_dropped"] += 1
                    time.sleep(0.1)
                    continue

                # Encode as JPEG
                _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                # Generate thumbnail (160x120)
                thumb_frame = cv2.resize(frame, (160, 120))
                _, thumb_jpeg = cv2.imencode(".jpg", thumb_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])

                with self._lock:
                    self._latest_frame = jpeg.tobytes()
                    self._latest_thumbnail = thumb_jpeg.tobytes()
                    self.frame_count += 1
                    self.last_frame_time = time.time()
                    self.stats["frames_captured"] += 1

                time.sleep(target_interval)
            except Exception as e:
                self.stats["errors"] += 1
                time.sleep(0.5)

    def to_dict(self) -> dict:
        return {
            "feed_id": self.feed_id, "source_url": self.source_url,
            "asset_id": self.asset_id, "sensor_name": self.sensor_name,
            "state": self.state, "width": self.width, "height": self.height,
            "fps": self.fps, "frame_count": self.frame_count,
            "last_frame_time": self.last_frame_time,
            "has_klv": bool(self.klv_metadata),
            "klv": dict(self.klv_metadata),
            "created_at": self.created_at,
            "stats": dict(self.stats),
        }


class VideoPipeline:
    """Manages all video feeds for AMOS ISR operations."""

    def __init__(self):
        self.feeds = {}         # {feed_id: VideoFeed}
        self._lock = threading.Lock()

    def add_feed(self, source_url: str, asset_id: str = "",
                 sensor_name: str = "", feed_id: str = "") -> dict:
        """Add a new video feed."""
        fid = feed_id or f"VF-{uuid.uuid4().hex[:6]}"
        feed = VideoFeed(fid, source_url, asset_id, sensor_name)
        with self._lock:
            self.feeds[fid] = feed
        return feed.to_dict()

    def start_feed(self, feed_id: str) -> bool:
        feed = self.feeds.get(feed_id)
        return feed.start() if feed else False

    def stop_feed(self, feed_id: str) -> bool:
        feed = self.feeds.get(feed_id)
        if feed:
            feed.stop()
            return True
        return False

    def pause_feed(self, feed_id: str) -> bool:
        feed = self.feeds.get(feed_id)
        if feed:
            feed.pause()
            return True
        return False

    def resume_feed(self, feed_id: str) -> bool:
        feed = self.feeds.get(feed_id)
        if feed:
            feed.resume()
            return True
        return False

    def remove_feed(self, feed_id: str) -> bool:
        feed = self.feeds.pop(feed_id, None)
        if feed:
            feed.stop()
            return True
        return False

    def get_frame(self, feed_id: str) -> str:
        """Get latest frame as base64 JPEG."""
        feed = self.feeds.get(feed_id)
        return feed.get_frame_b64() if feed else ""

    def get_thumbnail(self, feed_id: str) -> str:
        feed = self.feeds.get(feed_id)
        return feed.get_thumbnail_b64() if feed else ""

    def update_klv(self, feed_id: str, klv_data: dict):
        """Update KLV metadata for a feed (from klv_parser)."""
        feed = self.feeds.get(feed_id)
        if feed:
            feed.klv_metadata = klv_data

    def tick(self, assets, dt):
        """Pipeline tick — auto-connect feeds for ISR assets with video URLs."""
        # Could auto-discover RTSP feeds from asset configuration
        pass

    def get_feeds(self) -> list:
        return [f.to_dict() for f in self.feeds.values()]

    def get_active_feeds(self) -> list:
        return [f.to_dict() for f in self.feeds.values()
                if f.state == "STREAMING"]

    def get_stats(self) -> dict:
        return {
            "total_feeds": len(self.feeds),
            "streaming": sum(1 for f in self.feeds.values() if f.state == "STREAMING"),
            "paused": sum(1 for f in self.feeds.values() if f.state == "PAUSED"),
            "errors": sum(1 for f in self.feeds.values() if f.state == "ERROR"),
            "total_frames": sum(f.frame_count for f in self.feeds.values()),
        }
