"""Active window and source application detector for X11 and Wayland."""

import logging
import os
import re
import shutil
import subprocess
from typing import Dict, Optional

from clipmgr.constants import detect_session_type

logger = logging.getLogger(__name__)


class WindowDetector:
    """Detects active window name, process, and application title."""

    def __init__(self) -> None:
        self.session_type = detect_session_type()
        self._has_xprop = shutil.which("xprop") is not None
        self._has_xdotool = shutil.which("xdotool") is not None

    def get_active_window_info(self) -> Dict[str, Optional[str]]:
        """Retrieve details about the currently focused desktop window.

        Returns:
            Dict containing 'app_name', 'window_title', and 'window_id'.
        """
        if self.session_type == "x11":
            return self._get_x11_window_info()
        else:
            return self._get_wayland_window_info()

    def _get_x11_window_info(self) -> Dict[str, Optional[str]]:
        """Query X11 root window atoms to resolve active window attributes."""
        info: Dict[str, Optional[str]] = {
            "app_name": None,
            "window_title": None,
            "window_id": None,
        }

        # 1. Preferred method: xprop (standard X11 utility)
        if self._has_xprop:
            try:
                # Get active window ID
                out = subprocess.check_output(
                    ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                    stderr=subprocess.DEVNULL,
                    timeout=0.3,
                ).decode("utf-8", errors="ignore")
                match = re.search(r"_NET_ACTIVE_WINDOW.*#\s*(0x[0-9a-fA-F]+)", out)
                if match:
                    window_id = match.group(1)
                    info["window_id"] = window_id

                    if window_id and window_id != "0x0":
                        # Query WM_CLASS and _NET_WM_NAME
                        w_out = subprocess.check_output(
                            ["xprop", "-id", window_id, "WM_CLASS", "_NET_WM_NAME", "WM_NAME"],
                            stderr=subprocess.DEVNULL,
                            timeout=0.4,
                        ).decode("utf-8", errors="ignore")

                        # Parse WM_CLASS
                        class_match = re.search(r'WM_CLASS.*?=\s*(?:"([^"]+)")?(?:,\s*"([^"]+)")?', w_out)
                        if class_match:
                            # Usually second item is the capitalized application name
                            app = class_match.group(2) or class_match.group(1)
                            info["app_name"] = app

                        # Parse title
                        title_match = re.search(r'(?:_NET_WM_NAME|WM_NAME).*?=\s*"([^"]+)"', w_out)
                        if title_match:
                            info["window_title"] = title_match.group(1)

                        return info
            except Exception as e:
                logger.debug("xprop window detection failed: %s", e)

        # 2. Fallback: xdotool
        if self._has_xdotool:
            try:
                win_id = subprocess.check_output(
                    ["xdotool", "getactivewindow"],
                    stderr=subprocess.DEVNULL,
                    timeout=0.3,
                ).decode("utf-8", errors="ignore").strip()
                if win_id:
                    info["window_id"] = win_id
                    try:
                        name = subprocess.check_output(
                            ["xdotool", "getwindowname", win_id],
                            stderr=subprocess.DEVNULL,
                            timeout=0.3,
                        ).decode("utf-8", errors="ignore").strip()
                        info["window_title"] = name
                    except Exception:
                        pass
                    return info
            except Exception as e:
                logger.debug("xdotool window detection failed: %s", e)

        return info

    def _get_wayland_window_info(self) -> Dict[str, Optional[str]]:
        """Query Wayland compositor or GNOME shell for active window."""
        info: Dict[str, Optional[str]] = {
            "app_name": None,
            "window_title": None,
            "window_id": None,
        }

        # Under Wayland, security intentionally limits cross-app snooping.
        # Check if GNOME Shell eval or Sway / Hyprland IPC is available
        if shutil.which("swaymsg"):
            try:
                import json
                tree = subprocess.check_output(
                    ["swaymsg", "-t", "get_tree"],
                    stderr=subprocess.DEVNULL,
                    timeout=0.3,
                )
                data = json.loads(tree)

                def find_focused(node: dict) -> Optional[dict]:
                    if node.get("focused"):
                        return node
                    for child in node.get("nodes", []) + node.get("floating_nodes", []):
                        res = find_focused(child)
                        if res:
                            return res
                    return None

                focused = find_focused(data)
                if focused:
                    info["app_name"] = focused.get("app_id") or focused.get("window_properties", {}).get("class")
                    info["window_title"] = focused.get("name")
                    return info
            except Exception:
                pass

        return info
