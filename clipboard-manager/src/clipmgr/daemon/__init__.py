"""Daemon package for clipboard listening and system services."""

from clipmgr.daemon.listener import ClipboardDaemon
from clipmgr.daemon.window_detector import WindowDetector

__all__ = ["ClipboardDaemon", "WindowDetector"]
