"""Wayland clipboard listener backend using wl-paste --watch from wl-clipboard."""

import logging
import os
import shutil
import subprocess
import sys
import threading
from typing import Callable, Optional

from clipmgr.daemon.backends.base import ClipboardBackend
from clipmgr.daemon.window_detector import WindowDetector

logger = logging.getLogger(__name__)


class WaylandClipboardBackend(ClipboardBackend):
    """Event-driven clipboard backend for Wayland desktop sessions.

    Leverages `wl-paste --watch` from wl-clipboard to receive zero-polling notifications
    whenever the Wayland clipboard changes, streaming data to the daemon.
    """

    def __init__(self) -> None:
        self.window_detector = WindowDetector()
        self._on_change: Optional[Callable[[str, Optional[str]], None]] = None
        self._watch_process: Optional[subprocess.Popen] = None
        self._last_set_text: Optional[str] = None
        self._stop_event = threading.Event()

        self._has_wl_paste = shutil.which("wl-paste") is not None
        self._has_wl_copy = shutil.which("wl-copy") is not None

        if not self._has_wl_paste:
            logger.warning("wl-paste is not installed. Install wl-clipboard for full Wayland support.")

    def start(self, on_change: Callable[[str, Optional[str]], None]) -> None:
        """Start wl-paste --watch subprocess to receive clipboard events."""
        self._on_change = on_change
        self._stop_event.clear()

        if not self._has_wl_paste:
            logger.error("Cannot start Wayland listener: wl-paste executable not found.")
            return

        # Launch wl-paste --watch with clipmgr internal ingest command
        # Passing sys.executable -m clipmgr ingest
        cmd = [
            "wl-paste",
            "--watch",
            sys.executable,
            "-m",
            "clipmgr.main",
            "ingest",
        ]

        try:
            self._watch_process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None,
            )
            logger.info("Wayland clipboard listener started with PID %s", self._watch_process.pid)
        except Exception as e:
            logger.error("Failed to start wl-paste --watch: %s", e)

    def handle_ingested_content(self, text: str, source_app: Optional[str] = None) -> None:
        """Receive content pushed from the wl-paste watch runner."""
        if not text:
            return

        if self._last_set_text is not None and text == self._last_set_text:
            self._last_set_text = None
            return

        if not source_app:
            win_info = self.window_detector.get_active_window_info()
            source_app = win_info.get("app_name") or win_info.get("window_title")

        if self._on_change:
            try:
                self._on_change(text, source_app)
            except Exception as e:
                logger.error("Error processing Wayland clipboard change: %s", e)

    def stop(self) -> None:
        """Terminate the wl-paste --watch subprocess."""
        self._stop_event.set()
        if self._watch_process:
            try:
                self._watch_process.terminate()
                self._watch_process.wait(timeout=1.0)
            except Exception:
                try:
                    self._watch_process.kill()
                except Exception:
                    pass
            self._watch_process = None
        logger.info("Wayland clipboard listener stopped")

    def get_text(self) -> str:
        """Retrieve current clipboard text via wl-paste -n."""
        if not self._has_wl_paste:
            return ""
        try:
            return subprocess.check_output(
                ["wl-paste", "-n"],
                stderr=subprocess.DEVNULL,
                timeout=1.0,
            ).decode("utf-8", errors="replace")
        except Exception:
            return ""

    def set_text(self, text: str) -> bool:
        """Set clipboard text via wl-copy."""
        if not self._has_wl_copy:
            logger.error("Cannot set clipboard: wl-copy executable not found.")
            return False
        try:
            self._last_set_text = text
            proc = subprocess.Popen(
                ["wl-copy"],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            proc.communicate(input=text.encode("utf-8"), timeout=1.0)
            return proc.returncode == 0
        except Exception as e:
            logger.error("wl-copy failed: %s", e)
            return False
