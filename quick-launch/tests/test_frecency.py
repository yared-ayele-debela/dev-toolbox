"""Unit tests for frecency calculation, decay rates, and persistence."""

import time
from pathlib import Path
from quicklaunch.frecency import FrecencyStore


def test_recency_weights(frecency_store: FrecencyStore) -> None:
    """Verify recency weight bucket degradation across elapsed time."""
    now = time.time()

    # < 4 hours
    assert frecency_store.get_recency_weight(now - 3600, now) == 100.0
    # < 24 hours
    assert frecency_store.get_recency_weight(now - 12 * 3600, now) == 80.0
    # < 3 days (48 hrs)
    assert frecency_store.get_recency_weight(now - 48 * 3600, now) == 60.0
    # < 7 days (5 days)
    assert frecency_store.get_recency_weight(now - 5 * 86400, now) == 40.0
    # < 14 days (10 days)
    assert frecency_store.get_recency_weight(now - 10 * 86400, now) == 20.0
    # < 30 days (20 days)
    assert frecency_store.get_recency_weight(now - 20 * 86400, now) == 10.0
    # > 30 days
    assert frecency_store.get_recency_weight(now - 40 * 86400, now) == 5.0


def test_frecency_scoring_and_persistence(temp_dir: Path) -> None:
    """Verify recording accesses updates score and persists atomically."""
    hist_file = temp_dir / "frecency.json"
    store = FrecencyStore(file_path=hist_file)

    now = time.time()
    store.record_access("item_a", timestamp=now)
    store.record_access("item_a", timestamp=now)
    store.record_access("item_b", timestamp=now)

    raw_a = store.get_raw_score("item_a", now=now)
    raw_b = store.get_raw_score("item_b", now=now)

    assert raw_a > raw_b > 0.0
    assert 0.0 < store.get_normalized_score("item_a", now=now) <= 100.0

    # Ensure persisted on disk
    assert hist_file.exists()

    # Create new store from same file and verify values match
    reloaded_store = FrecencyStore(file_path=hist_file)
    assert reloaded_store.get_raw_score("item_a", now=now) == raw_a
    assert reloaded_store.get_raw_score("item_b", now=now) == raw_b


def test_top_items_order(frecency_store: FrecencyStore) -> None:
    """Verify get_top_item_ids accurately returns highest frecency items first."""
    now = time.time()
    # item_frequent: 5 accesses today
    for _ in range(5):
        frecency_store.record_access("item_frequent", timestamp=now)

    # item_old: 10 accesses 25 days ago
    for _ in range(10):
        frecency_store.record_access("item_old", timestamp=now - 25 * 86400)

    top = frecency_store.get_top_item_ids(limit=5)
    top_ids = [item_id for item_id, _ in top]
    assert top_ids[0] == "item_frequent"
