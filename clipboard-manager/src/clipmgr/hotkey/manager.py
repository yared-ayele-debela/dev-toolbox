"""Hotkey manager orchestrating session detection, X11 listener, and Wayland helpers."""

import logging
from typing import Callable, Optional

from clipmgr.constants import detect_session_type
from clipmgr.hotkey.wayland import is_gnome_available, setup_gnome_shortcut
from clipmgr.hotkey.x11 import X11HotkeyListener

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Coordinates global hotkey handling across X11 and Wayland sessions."""

    def __init__(self, binding: str, on_toggle_callback: Callable[[], None]) -> None:
        self.binding = binding
        self.on_toggle_callback = on_toggle_callback
        self.session_type = detect_session_type()
        self._x11_listener: Optional[X11HotkeyListener] = None

    def start(self) -> None:
        """Initialize and start session-appropriate hotkey listener."""
        if self.session_type == "x11":
            self._x11_listener = X11HotkeyListener(self.binding, self.on_toggle_callback)
            started = self._x11_listener.start()
            if not started:
                logger.info(
                    "X11 global hotkey not registered via Keybinder. Use 'clipmgr toggle' or desktop shortcut."
                )
        elif self.session_type == "wayland":
            logger.info("Wayland session: shortcut managed via compositor or GNOME shortcut ('clipmgr toggle').")

    def stop(self) -> None:
        """Stop active hotkey listeners."""
        if self._x11_listener:
            self._x11_listener.stop()
            self._x11_listener = None
