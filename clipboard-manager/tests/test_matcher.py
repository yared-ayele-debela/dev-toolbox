"""Unit tests for fuzzy search and ranking engine."""

import pytest
from clipmgr.models import ClipEntry, ContentType
from clipmgr.search.matcher import FuzzyMatcher


@pytest.fixture
def sample_entries() -> list[ClipEntry]:
    """Provide a diverse set of test entries."""
    return [
        ClipEntry(
            id=1,
            content="https://github.com/torvalds/linux",
            content_type=ContentType.URL,
            source_app="Google Chrome",
            timestamp=1000,
            pinned=False,
        ),
        ClipEntry(
            id=2,
            content="def calculate_sha256(filepath: str) -> str:\n    return hashlib.sha256().hexdigest()",
            content_type=ContentType.CODE,
            source_app="VS Code",
            timestamp=2000,
            pinned=False,
        ),
        ClipEntry(
            id=3,
            content="Important meeting notes for Q3 roadmap",
            content_type=ContentType.TEXT,
            source_app="Slack",
            timestamp=3000,
            pinned=True,  # PINNED
        ),
        ClipEntry(
            id=4,
            content="/var/log/syslog",
            content_type=ContentType.FILE_PATH,
            source_app="Terminal",
            timestamp=4000,
            pinned=False,
        ),
        ClipEntry(
            id=5,
            content="AKI" + "AIOSFODNN7EXAMPLE",
            content_type=ContentType.TEXT,
            source_app="Bitwarden",
            timestamp=5000,
            is_sensitive=True,
            pinned=False,
        ),
    ]


class TestFuzzyMatcher:
    """Test RapidFuzz scoring, filtering, and pinned priority."""

    def test_empty_query_returns_pinned_first(self, sample_entries: list[ClipEntry]) -> None:
        matcher = FuzzyMatcher()
        results = matcher.search("", sample_entries)

        # ID 3 is pinned, so it must be first
        assert len(results) > 0
        assert results[0].id == 3
        assert results[0].pinned is True

    def test_exact_substring_match(self, sample_entries: list[ClipEntry]) -> None:
        matcher = FuzzyMatcher()
        results = matcher.search("github", sample_entries)

        assert len(results) >= 1
        assert results[0].id == 1  # GitHub URL

    def test_fuzzy_typo_tolerance(self, sample_entries: list[ClipEntry]) -> None:
        matcher = FuzzyMatcher()
        # Query with typo: 'sha256' -> 'sha25'
        results = matcher.search("calculate_sha", sample_entries)

        assert len(results) >= 1
        assert results[0].id == 2  # Python function

    def test_filter_by_content_type(self, sample_entries: list[ClipEntry]) -> None:
        matcher = FuzzyMatcher()
        # Search specifically for CODE
        results = matcher.search("", sample_entries, content_type=ContentType.CODE)

        assert len(results) == 1
        assert results[0].content_type == ContentType.CODE
        assert results[0].id == 2

    def test_filter_by_pinned_only(self, sample_entries: list[ClipEntry]) -> None:
        matcher = FuzzyMatcher()
        results = matcher.search("", sample_entries, pinned_only=True)

        assert len(results) == 1
        assert results[0].id == 3
        assert results[0].pinned is True

    def test_sensitive_items_excluded_by_default(self, sample_entries: list[ClipEntry]) -> None:
        matcher = FuzzyMatcher()
        results = matcher.search("", sample_entries, include_sensitive=False)

        ids = [e.id for e in results]
        assert 5 not in ids  # Sensitive ID 5 excluded

    def test_sensitive_items_included_when_requested(self, sample_entries: list[ClipEntry]) -> None:
        matcher = FuzzyMatcher()
        results = matcher.search("", sample_entries, include_sensitive=True)

        ids = [e.id for e in results]
        assert 5 in ids
