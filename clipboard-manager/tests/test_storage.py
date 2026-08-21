"""Unit tests for SQLite storage, deduplication logic, pinning, retention, and encryption."""

import os
import stat
import time
from pathlib import Path

import pytest
from clipmgr.models import ClipEntry, ContentType
from clipmgr.storage.database import DatabaseManager
from clipmgr.storage.encryption import ContentCipher


@pytest.fixture
def temp_db(tmp_path: Path) -> DatabaseManager:
    """Create an isolated temporary DatabaseManager for testing."""
    db_file = tmp_path / "test_clipboard.db"
    return DatabaseManager(db_path=db_file, retention_days=14, encryption_enabled=False)


@pytest.fixture
def temp_enc_db(tmp_path: Path) -> DatabaseManager:
    """Create an isolated temporary DatabaseManager with encryption enabled."""
    db_file = tmp_path / "test_encrypted.db"
    return DatabaseManager(db_path=db_file, retention_days=14, encryption_enabled=True)


class TestDatabaseSecurityAndPermissions:
    """Verify file permissions on creation."""

    def test_file_permissions(self, temp_db: DatabaseManager) -> None:
        assert temp_db.db_path.exists()
        file_mode = stat.S_IMODE(os.stat(temp_db.db_path).st_mode)
        # Should be 0600 (-rw-------)
        assert file_mode == 0o600


class TestDeduplicationLogic:
    """Verify deduplication behaviors on repeated copies."""

    def test_dedup_bump_strategy(self, temp_db: DatabaseManager) -> None:
        entry1 = ClipEntry(content="Identical snippet of text", source_app="AppA")
        saved1, was_new1 = temp_db.add_entry(entry1, deduplicate_strategy="bump")
        assert was_new1 is True
        assert saved1 is not None
        original_id = saved1.id
        original_time = saved1.timestamp

        # Wait small fraction and add identical clip
        time.sleep(0.05)
        entry2 = ClipEntry(content="Identical snippet of text", source_app="AppB")
        saved2, was_new2 = temp_db.add_entry(entry2, deduplicate_strategy="bump")

        assert was_new2 is False
        assert saved2 is not None
        # Must retain original ID and have updated timestamp
        assert saved2.id == original_id
        assert saved2.timestamp >= original_time

        # Total entries in DB must still be exactly 1
        stats = temp_db.get_stats()
        assert stats["total_entries"] == 1

    def test_dedup_ignore_strategy(self, temp_db: DatabaseManager) -> None:
        entry1 = ClipEntry(content="Repeatable content", source_app="Terminal")
        saved1, was_new1 = temp_db.add_entry(entry1, deduplicate_strategy="ignore")
        assert was_new1 is True

        entry2 = ClipEntry(content="Repeatable content", source_app="Terminal")
        saved2, was_new2 = temp_db.add_entry(entry2, deduplicate_strategy="ignore")
        assert was_new2 is False
        assert saved2.id == saved1.id

        stats = temp_db.get_stats()
        assert stats["total_entries"] == 1

    def test_different_content_is_not_deduped(self, temp_db: DatabaseManager) -> None:
        e1 = ClipEntry(content="Content 1")
        e2 = ClipEntry(content="Content 2")
        _, new1 = temp_db.add_entry(e1)
        _, new2 = temp_db.add_entry(e2)

        assert new1 is True
        assert new2 is True
        assert temp_db.get_stats()["total_entries"] == 2


class TestPinningAndOrdering:
    """Test pinned behavior and result ranking."""

    def test_pinned_sorting_priority(self, temp_db: DatabaseManager) -> None:
        # Add 3 items
        temp_db.add_entry(ClipEntry(content="Item 1", timestamp=100))
        temp_db.add_entry(ClipEntry(content="Item 2", timestamp=200))
        saved3, _ = temp_db.add_entry(ClipEntry(content="Item 3", timestamp=300))

        # Item 3 is newest; pin item 1
        all_recent = temp_db.get_recent_entries()
        item1 = [e for e in all_recent if e.content == "Item 1"][0]
        assert item1.id is not None
        temp_db.toggle_pinned(item1.id)

        # Query recent items: pinned item 1 must be FIRST despite older timestamp
        ordered = temp_db.get_recent_entries()
        assert ordered[0].content == "Item 1"
        assert ordered[0].pinned is True

    def test_toggle_pinned(self, temp_db: DatabaseManager) -> None:
        saved, _ = temp_db.add_entry(ClipEntry(content="Toggle me"))
        assert saved.id is not None

        # Initially unpinned
        assert saved.pinned is False

        # Pin
        new_state = temp_db.toggle_pinned(saved.id)
        assert new_state is True
        fetched = temp_db.get_entry(saved.id)
        assert fetched is not None and fetched.pinned is True

        # Unpin
        new_state2 = temp_db.toggle_pinned(saved.id)
        assert new_state2 is False
        fetched2 = temp_db.get_entry(saved.id)
        assert fetched2 is not None and fetched2.pinned is False


class TestRetentionAutoPurge:
    """Test retention window purging logic."""

    def test_purge_removes_old_unpinned_preserves_pinned(self, temp_db: DatabaseManager) -> None:
        now = time.time()
        old_time = now - (40 * 86400)  # 40 days ago

        # Add old unpinned clip
        temp_db.add_entry(ClipEntry(content="Old unpinned clip", timestamp=old_time, pinned=False))

        # Add old PINNED clip
        old_pinned = ClipEntry(content="Old PINNED clip", timestamp=old_time, pinned=True)
        temp_db.add_entry(old_pinned)

        # Add fresh clip
        temp_db.add_entry(ClipEntry(content="Fresh clip", timestamp=now, pinned=False))

        assert temp_db.get_stats()["total_entries"] == 3

        # Purge entries older than 30 days
        deleted = temp_db.purge_expired(retention_days=30)
        assert deleted == 1

        remaining = temp_db.get_recent_entries()
        remaining_contents = [e.content for e in remaining]

        # Fresh clip must remain
        assert "Fresh clip" in remaining_contents
        # Old pinned clip MUST remain
        assert "Old PINNED clip" in remaining_contents
        # Old unpinned clip must be gone
        assert "Old unpinned clip" not in remaining_contents


class TestEncryptionAtRest:
    """Verify transparent encryption at rest."""

    def test_content_is_encrypted_in_sqlite(self, temp_enc_db: DatabaseManager) -> None:
        secret_content = "SuperSensitiveInformationToEncrypt123"
        saved, _ = temp_enc_db.add_entry(ClipEntry(content=secret_content))

        # 1. High-level retrieval returns decrypted content seamlessly
        fetched = temp_enc_db.get_entry(saved.id)
        assert fetched is not None
        assert fetched.content == secret_content

        # 2. Raw SQLite query returns ciphertext starting with ENC:
        with temp_enc_db._get_connection() as conn:
            cursor = conn.execute("SELECT content FROM clipboard_entries WHERE id = ?;", (saved.id,))
            raw_content = cursor.fetchone()["content"]
            assert raw_content.startswith("ENC:")
            assert secret_content not in raw_content
