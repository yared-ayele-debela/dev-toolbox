"""Unit tests for JSON export and import."""

import json
from pathlib import Path

import pytest
from clipmgr.models import ClipEntry, ContentType
from clipmgr.storage.database import DatabaseManager


@pytest.fixture
def temp_db(tmp_path: Path) -> DatabaseManager:
    """Create isolated DatabaseManager."""
    db_file = tmp_path / "test_export_import.db"
    return DatabaseManager(db_path=db_file)


class TestExportImport:
    """Test full backup export and import cycle."""

    def test_export_and_import_cycle(self, temp_db: DatabaseManager, tmp_path: Path) -> None:
        # 1. Add entries
        temp_db.add_entry(ClipEntry(content="Entry One", content_type=ContentType.TEXT, pinned=True))
        temp_db.add_entry(ClipEntry(content="Entry Two", content_type=ContentType.CODE, source_app="VSCode"))
        temp_db.add_entry(ClipEntry(content="Secret", is_sensitive=True))

        assert temp_db.get_stats()["total_entries"] == 3

        # 2. Export entries (excluding sensitive)
        exported = temp_db.export_all(include_sensitive=False)
        assert len(exported) == 2

        # 3. Create fresh DB and import
        fresh_db_file = tmp_path / "fresh_imported.db"
        fresh_db = DatabaseManager(db_path=fresh_db_file)
        assert fresh_db.get_stats()["total_entries"] == 0

        imported_count = fresh_db.import_entries(exported)
        assert imported_count == 2
        assert fresh_db.get_stats()["total_entries"] == 2

        # 4. Verify properties preserved
        recent = fresh_db.get_recent_entries()
        contents = [e.content for e in recent]
        assert "Entry One" in contents
        assert "Entry Two" in contents

        pinned_items = [e for e in recent if e.pinned]
        assert len(pinned_items) == 1
        assert pinned_items[0].content == "Entry One"
