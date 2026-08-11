"""Application constants, path definitions, and system detection helpers."""

import os
from pathlib import Path

# Application metadata
APP_NAME = "clipmgr"
APP_TITLE = "ClipMgr"
APP_DESCRIPTION = "Advanced Clipboard Manager for Ubuntu Linux"
VERSION = "1.0.0"

# Directories & file paths
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / APP_NAME
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))

CONFIG_FILE = CONFIG_DIR / "config.yaml"
DB_FILE = DATA_DIR / "clipboard.db"
KEY_FILE = DATA_DIR / ".encryption_key"
SOCKET_FILE = RUNTIME_DIR / f"{APP_NAME}.sock" if RUNTIME_DIR.exists() else CACHE_DIR / f"{APP_NAME}.sock"

# Security & size limits
DEFAULT_MAX_SIZE_BYTES = 1024 * 1024  # 1 MB
DEFAULT_RETENTION_DAYS = 30
FILE_MODE_PRIVATE = 0o600  # -rw-------
DIR_MODE_PRIVATE = 0o700   # -rwx------


def detect_session_type() -> str:
    """Detect whether the current desktop session is Wayland or X11.

    Checks $XDG_SESSION_TYPE, falling back to display environment variables.
    Returns:
        'wayland' or 'x11'.
    """
    session = os.environ.get("XDG_SESSION_TYPE", "").lower().strip()
    if session in ("wayland", "x11"):
        return session

    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"

    if os.environ.get("DISPLAY"):
        return "x11"

    # Default fallback
    return "x11"


def ensure_secure_directories() -> None:
    """Ensure config, data, and cache directories exist with restricted permissions (0700)."""
    for directory in (CONFIG_DIR, DATA_DIR, CACHE_DIR):
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(str(directory), DIR_MODE_PRIVATE)
        except OSError:
            pass


def secure_file(path: Path) -> None:
    """Ensure a file exists with restricted permissions (0600)."""
    if path.exists():
        try:
            os.chmod(str(path), FILE_MODE_PRIVATE)
        except OSError:
            pass
