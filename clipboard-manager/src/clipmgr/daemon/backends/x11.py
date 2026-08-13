"""X11 / GNOME clipboard listener backend using PyGObject Gtk.Clipboard owner-change signal."""

import logging
import subprocess
from typing import Callable, Optional

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from clipmgr.daemon.backends.base import ClipboardBackend
from clipmgr.daemon.window_detector import WindowDetector

logger = logging.getLogger(__name__)


class X11ClipboardBackend(ClipboardBackend):
    """Event-driven clipboard backend for X11 / GNOME environments.

    Uses Gtk.Clipboard's 'owner-change' signal for zero-polling, instant
    notification whenever the clipboard selection changes.
    """

    def __init__(self) -> None:
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.window_detector = WindowDetector()
        self._on_change: Optional[Callable[[str, Optional[str]], None]] = None
        self._signal_id: Optional[int] = None
        self._last_set_text: Optional[str] = None

    def start(self, on_change: Callable[[str, Optional[str]], None]) -> None:
        """Connect to owner-change signal on GTK clipboard."""
        self._on_change = on_change
        self._signal_id = self.clipboard.connect("owner-change", self._on_owner_change)
        logger.info("X11 clipboard listener registered with GTK owner-change signal (id=%s)", self._signal_id)

    def stop(self) -> None:
        """Disconnect GTK signal handler."""
        if self._signal_id is not None:
            try:
                self.clipboard.disconnect(self._signal_id)
            except Exception as e:
                logger.debug("Error disconnecting signal: %s", e)
            self._signal_id = None
        logger.info("X11 clipboard listener stopped")

    def _on_owner_change(self, clipboard: Gtk.Clipboard, event: Gdk.EventOwnerChange) -> None:
        """Callback triggered immediately when clipboard owner changes."""
        # Capture source application right when owner changes
        win_info = self.window_detector.get_active_window_info()
        source_app = win_info.get("app_name") or win_info.get("window_title")

        # Request clipboard text asynchronously to avoid blocking UI/main loop
        clipboard.request_text(self._handle_text_received, source_app)

    def _handle_text_received(
        self, clipboard: Gtk.Clipboard, text: Optional[str], source_app: Optional[str]
    ) -> None:
        """Process incoming clipboard text asynchronously."""
        if text is None:
            return

        # Avoid re-logging text if this backend itself just set it
        if self._last_set_text is not None and text == self._last_set_text:
            self._last_set_text = None
            return

        if self._on_change:
            try:
                self._on_change(text, source_app)
            except Exception as e:
                logger.error("Error processing X11 clipboard change: %s", e)

    def get_text(self) -> str:
        """Retrieve current text synchronously."""
        try:
            text = self.clipboard.wait_for_text()
            if text is not None:
                return text
        except Exception:
            pass

        # Fallback to xclip
        try:
            return subprocess.check_output(
                ["xclip", "-selection", "clipboard", "-out"],
                stderr=subprocess.DEVNULL,
                timeout=1.0,
            ).decode("utf-8", errors="replace")
        except Exception:
            return ""

    def set_text(self, text: str) -> bool:
        """Set text on clipboard and persist it."""
        try:
            self._last_set_text = text
            self.clipboard.set_text(text, -1)
            # Store ensures data survives application close
            self.clipboard.store()
            return True
        except Exception as e:
            logger.warning("Gtk set_text failed: %s. Attempting xclip fallback.", e)
            try:
                proc = subprocess.Popen(
                    ["xclip", "-selection", "clipboard", "-in"],
                    stdin=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                proc.communicate(input=text.encode("utf-8"), timeout=1.0)
                return proc.returncode == 0
            except Exception as ex:
                logger.error("xclip fallback failed: %s", ex)
                return False
