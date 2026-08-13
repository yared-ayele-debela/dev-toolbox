"""Background daemon and listener coordinator for clipboard change events."""

import base64
import json
import logging
import time
from typing import Any, Dict, Optional

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib

from clipmgr.config import ConfigManager
from clipmgr.constants import detect_session_type
from clipmgr.daemon.backends.base import ClipboardBackend
from clipmgr.daemon.backends.wayland import WaylandClipboardBackend
from clipmgr.daemon.backends.x11 import X11ClipboardBackend
from clipmgr.detector import detect_content_type, detect_sensitive_content
from clipmgr.models import ClipEntry, ContentType
from clipmgr.storage.database import DatabaseManager

logger = logging.getLogger(__name__)


class ClipboardDaemon:
    """Core daemon service that listens to system clipboard changes and persists entries."""

    def __init__(
        self,
        config_mgr: Optional[ConfigManager] = None,
        db_mgr: Optional[DatabaseManager] = None,
    ) -> None:
        self.config_mgr = config_mgr or ConfigManager()
        self.db = db_mgr or DatabaseManager(
            retention_days=self.config_mgr.get("storage.retention_days", 30),
            encryption_enabled=self.config_mgr.get("storage.encryption.enabled", False),
        )

        self.backend: Optional[ClipboardBackend] = None
        self.session_type = self._resolve_backend_type()
        self._init_backend()

        # Run auto-purge on launch
        self._run_purge()
        # Schedule hourly retention purge (3600 seconds)
        GLib.timeout_add_seconds(3600, self._run_purge)

    def _resolve_backend_type(self) -> str:
        """Determine backend based on configuration and system session."""
        configured = self.config_mgr.get("daemon.backend", "auto").lower()
        if configured in ("x11", "wayland"):
            return configured
        return detect_session_type()

    def _init_backend(self) -> None:
        """Instantiate the active session clipboard backend."""
        logger.info("Initializing clipboard backend for session type: %s", self.session_type)
        if self.session_type == "wayland":
            self.backend = WaylandClipboardBackend()
        else:
            self.backend = X11ClipboardBackend()

    def start(self) -> None:
        """Start listening for clipboard events."""
        if self.backend:
            self.backend.start(self.process_incoming_clip)
            logger.info("Clipboard daemon started successfully.")

    def stop(self) -> None:
        """Stop backend listener and flush state."""
        if self.backend:
            self.backend.stop()
            logger.info("Clipboard daemon stopped.")

    def _run_purge(self) -> bool:
        """Periodic auto-purge handler. Returns True to keep GLib timer running."""
        try:
            retention_days = int(self.config_mgr.get("storage.retention_days", 30))
            self.db.purge_expired(retention_days)
        except Exception as e:
            logger.error("Error during scheduled retention purge: %s", e)
        return True

    def process_incoming_clip(self, text: str, source_app: Optional[str] = None) -> Optional[ClipEntry]:
        """Process, filter, classify, and persist raw clipboard text."""
        if not text or not text.strip():
            logger.debug("Ignoring empty or whitespace-only clip.")
            return None

        # 1. Size capping (e.g. skip anything over 1MB)
        max_size = int(self.config_mgr.get("storage.max_size_bytes", 1024 * 1024))
        size_bytes = len(text.encode("utf-8", errors="replace"))
        if size_bytes > max_size:
            logger.warning(
                "Skipping clip exceeding size cap (%d bytes > max %d bytes)",
                size_bytes,
                max_size,
            )
            return None

        # 2. Privacy & Secret Detection
        detect_secrets = bool(self.config_mgr.get("privacy.detect_secrets", True))
        is_sensitive = False
        if detect_secrets:
            is_sensitive, reason = detect_sensitive_content(text, source_app)
            if is_sensitive:
                action = self.config_mgr.get("privacy.on_sensitive", "flag").lower()
                if action == "skip":
                    logger.info("Privacy layer dropped sensitive clip: %s", reason)
                    return None
                logger.info("Privacy layer flagged sensitive clip: %s", reason)

        # 3. Content Type Classification
        content_type = detect_content_type(text)

        # 4. Construct ClipEntry
        entry = ClipEntry(
            content=text,
            content_type=content_type,
            source_app=source_app,
            timestamp=time.time(),
            pinned=False,
            size_bytes=size_bytes,
            is_sensitive=is_sensitive,
        )

        # 5. Persist with deduplication
        dedup_strat = self.config_mgr.get("storage.deduplicate_strategy", "bump")
        saved_entry, was_new = self.db.add_entry(entry, deduplicate_strategy=dedup_strat)

        if was_new:
            logger.info(
                "Recorded new clip [type=%s, size=%d, app=%s, sensitive=%s]",
                content_type.value,
                size_bytes,
                source_app or "Unknown",
                is_sensitive,
            )
        else:
            logger.debug("Deduplicated existing clip (ID: %s)", saved_entry.id if saved_entry else None)

        return saved_entry

    def handle_ingest_payload(self, base64_payload: str) -> bool:
        """Handle raw payload piped via IPC from Wayland wl-paste watcher."""
        try:
            raw_bytes = base64.b64decode(base64_payload.encode("ascii"))
            text = raw_bytes.decode("utf-8", errors="replace")
            # If backend is Wayland, trigger its handler
            if isinstance(self.backend, WaylandClipboardBackend):
                self.backend.handle_ingested_content(text)
            else:
                self.process_incoming_clip(text)
            return True
        except Exception as e:
            logger.error("Failed to decode ingest payload: %s", e)
            return False
