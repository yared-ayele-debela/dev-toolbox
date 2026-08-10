"""Hotkey management package for global shortcuts."""

from clipmgr.hotkey.manager import HotkeyManager
from clipmgr.hotkey.wayland import is_gnome_available, setup_gnome_shortcut

__all__ = ["HotkeyManager", "setup_gnome_shortcut", "is_gnome_available"]
