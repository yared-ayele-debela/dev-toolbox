"""Hotkey package for X11 and Wayland session support."""

from quicklaunch.hotkey.manager import HotkeyManager
from quicklaunch.hotkey.wayland import setup_gnome_shortcut
from quicklaunch.hotkey.x11 import X11HotkeyListener

__all__ = ["HotkeyManager", "X11HotkeyListener", "setup_gnome_shortcut"]
