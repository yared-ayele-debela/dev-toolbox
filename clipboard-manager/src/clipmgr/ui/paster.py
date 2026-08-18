"""Direct paste simulator for re-inserting clipboard data into previously active windows."""

import logging
import os
import shutil
import subprocess
import time
from typing import Optional

from clipmgr.constants import detect_session_type
from clipmgr.daemon.backends.base import ClipboardBackend
from clipmgr.models import ClipEntry

logger = logging.getLogger(__name__)

# Known terminal process / window substrings where Ctrl+Shift+V or Shift+Insert is preferred
TERMINAL_NAMES = {
    "terminal", "xterm", "kitty", "alacritty", "konsole", "terminator",
    "tilix", "urxvt", "rxvt", "wezterm", "foot",
}


class DirectPaster:
    """Simulates keystrokes to directly paste clipboard content into target windows."""

    def __init__(self, backend: Optional[ClipboardBackend] = None) -> None:
        self.backend = backend
        self.session_type = detect_session_type()
        self._has_xdotool = shutil.which("xdotool") is not None
        self._has_wtype = shutil.which("wtype") is not None
        self._has_ydotool = shutil.which("ydotool") is not None

    def paste(
        self,
        entry: ClipEntry,
        target_window_id: Optional[str] = None,
        target_app_name: Optional[str] = None,
    ) -> bool:
        """Copy entry to clipboard and simulate paste into the target application window."""
        # 1. First ensure the content is in the system clipboard
        if self.backend:
            self.backend.set_text(entry.content)

        # 2. Brief sleep for window manager focus switch
        time.sleep(0.08)

        # 3. Simulate paste based on session type
        if self.session_type == "x11":
            return self._paste_x11(target_window_id, target_app_name)
        else:
            return self._paste_wayland(target_app_name)

    def _paste_x11(
        self, target_window_id: Optional[str], target_app_name: Optional[str]
    ) -> bool:
        """Simulate paste on X11 via xdotool."""
        if not self._has_xdotool:
            logger.warning("xdotool not installed. Direct paste unavailable.")
            self._notify_fallback("xdotool")
            return False

        try:
            # Reactivate target window if ID is known
            if target_window_id and target_window_id != "0x0":
                try:
                    subprocess.run(
                        ["xdotool", "windowactivate", "--sync", target_window_id],
                        check=False,
                        timeout=0.4,
                        stderr=subprocess.DEVNULL,
                    )
                    time.sleep(0.05)
                except Exception as e:
                    logger.debug("Could not reactivate target window: %s", e)

            # Determine key combo: terminal vs GUI
            is_terminal = False
            if target_app_name:
                app_lower = target_app_name.lower()
                is_terminal = any(term in app_lower for term in TERMINAL_NAMES)

            # Direct paste command
            if is_terminal:
                # Use Shift+Insert or Ctrl+Shift+V for terminals
                subprocess.run(
                    ["xdotool", "key", "--clearmodifiers", "Shift+Insert"],
                    check=True,
                    timeout=0.5,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.run(
                    ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
                    check=True,
                    timeout=0.5,
                    stderr=subprocess.DEVNULL,
                )
            return True
        except Exception as e:
            logger.error("xdotool paste execution failed: %s", e)
            return False

    def _paste_wayland(self, target_app_name: Optional[str]) -> bool:
        """Simulate paste on Wayland via wtype or ydotool."""
        if self._has_wtype:
            try:
                # wtype -M ctrl -k v -m ctrl
                subprocess.run(
                    ["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"],
                    check=True,
                    timeout=0.5,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except Exception as e:
                logger.debug("wtype paste failed: %s", e)

        if self._has_ydotool:
            try:
                # 29 = KEY_LEFTCTRL, 47 = KEY_V
                subprocess.run(
                    ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
                    check=True,
                    timeout=0.5,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except Exception as e:
                logger.debug("ydotool paste failed: %s", e)

        logger.warning("Neither wtype nor ydotool found. Direct paste unavailable.")
        self._notify_fallback("wtype")
        return False

    def _notify_fallback(self, tool_name: str) -> None:
        """Notify user via notify-send that content was copied but direct paste requires tool."""
        if shutil.which("notify-send"):
            try:
                subprocess.run(
                    [
                        "notify-send",
                        "-i", "edit-paste",
                        "ClipMgr: Copied to Clipboard",
                        f"Install '{tool_name}' to enable instant Shift+Enter auto-pasting.",
                    ],
                    check=False,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
