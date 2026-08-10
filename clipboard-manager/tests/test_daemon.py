"""Unit tests for daemon processing, size capping, and privacy handling."""

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from clipmgr.config import ConfigManager
from clipmgr.daemon.listener import ClipboardDaemon
from clipmgr.models import ContentType
from clipmgr.storage.database import DatabaseManager


@pytest.fixture
def mock_daemon(tmp_path: Path) -> ClipboardDaemon:
    """Create an isolated test daemon with temporary DB and config."""
    db_file = tmp_path / "daemon_test.db"
    cfg_file = tmp_path / "daemon_config.yaml"

    cfg = ConfigManager(config_path=cfg_file)
    cfg.set("storage.max_size_bytes", 1024)  # 1 KB limit for testing
    cfg.set("privacy.on_sensitive", "skip")

    db = DatabaseManager(db_path=db_file)
    daemon = ClipboardDaemon(config_mgr=cfg, db_mgr=db)
    daemon.backend = MagicMock()
    return daemon


class TestDaemonProcessing:
    """Test daemon processing pipelines."""

    def test_empty_or_whitespace_ignored(self, mock_daemon: ClipboardDaemon) -> None:
        assert mock_daemon.process_incoming_clip("") is None
        assert mock_daemon.process_incoming_clip("   \n\t  ") is None
        assert mock_daemon.db.get_stats()["total_entries"] == 0

    def test_size_capping_drops_huge_clips(self, mock_daemon: ClipboardDaemon) -> None:
        # Max size configured to 1024 bytes (1 KB)
        huge_text = "A" * 2048  # 2 KB
        result = mock_daemon.process_incoming_clip(huge_text)
        assert result is None
        assert mock_daemon.db.get_stats()["total_entries"] == 0

        # Normal text under limit is stored
        normal_text = "Small clip within limit"
        result2 = mock_daemon.process_incoming_clip(normal_text)
        assert result2 is not None
        assert mock_daemon.db.get_stats()["total_entries"] == 1

    def test_privacy_skip_action(self, mock_daemon: ClipboardDaemon) -> None:
        # 1. Block policy (default)
        daemon = mock_daemon
        db = mock_daemon.db
        secret = "AKI" + "AIOSFODNN7EXAMPLE"
        entry = daemon.process_incoming_clip(secret)
        assert entry is None
        assert db.get_stats()["total_entries"] == 0

    def test_sensitive_flagged_stored_as_masked(self, tmp_path: Path) -> None:
        db_file = tmp_path / "flag_test.db"
        cfg_file = tmp_path / "flag_config.yaml"
        cfg = ConfigManager(config_path=cfg_file)
        cfg.set("privacy.on_sensitive", "flag")

        db = DatabaseManager(db_path=db_file)
        daemon = ClipboardDaemon(config_mgr=cfg, db_mgr=db)
        daemon.backend = MagicMock()

        secret = "gh" + "p_1234567890abcdefghijklmnopqrstuvwxyzAB"
        entry = daemon.process_incoming_clip(secret)

        assert entry is not None
        assert entry.is_sensitive is True
        assert "••••" in entry.preview
