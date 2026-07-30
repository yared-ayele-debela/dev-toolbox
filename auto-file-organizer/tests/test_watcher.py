"""
Unit tests for watcher stability detection, thread synchronization, and event handlers.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import time
import pytest
from watchdog.events import FileCreatedEvent, FileMovedEvent

from file_organizer.config import AppConfig, StabilityConfig, parse_raw_dict
from file_organizer.watcher import (
    ActiveProcessingTracker,
    DirectoryWatcher,
    OrganizerEventHandler,
    wait_until_file_is_stable,
)


def test_active_processing_tracker():
    tracker = ActiveProcessingTracker()
    path = Path("/tmp/sample_file.txt")

    assert tracker.acquire(path) is True
    # Second attempt on same path should fail (lock held)
    assert tracker.acquire(path) is False
    assert tracker.is_active(path) is True

    tracker.release(path)
    assert tracker.is_active(path) is False
    # Now it can be acquired again
    assert tracker.acquire(path) is True
    tracker.release(path)


def test_active_processing_tracker_concurrency():
    tracker = ActiveProcessingTracker()
    path = Path("/tmp/concurrent_file.txt")
    results = []

    def try_acquire():
        acquired = tracker.acquire(path)
        results.append(acquired)

    threads = [threading.Thread(target=try_acquire) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one thread should succeed in acquiring
    assert results.count(True) == 1
    assert results.count(False) == 9


def test_stability_ignored_extension(tmp_path: Path):
    crdownload_file = tmp_path / "downloading.pdf.crdownload"
    crdownload_file.write_text("partial download", encoding="utf-8")

    config = StabilityConfig(
        check_interval_seconds=0.1,
        min_stable_checks=2,
        max_wait_seconds=1.0,
    )

    # Must immediately return False without blocking on timeout
    start = time.time()
    result = wait_until_file_is_stable(crdownload_file, config)
    duration = time.time() - start

    assert result is False
    assert duration < 0.5


def test_stability_stable_file(tmp_path: Path):
    stable_file = tmp_path / "complete_document.pdf"
    stable_file.write_text("Complete verified content", encoding="utf-8")

    config = StabilityConfig(
        check_interval_seconds=0.1,
        min_stable_checks=2,
        max_wait_seconds=2.0,
    )

    result = wait_until_file_is_stable(stable_file, config)
    assert result is True


def test_stability_growing_file(tmp_path: Path):
    growing_file = tmp_path / "stream.bin"
    growing_file.write_bytes(b"initial")

    config = StabilityConfig(
        check_interval_seconds=0.1,
        min_stable_checks=2,
        max_wait_seconds=2.0,
    )

    def append_bytes():
        for _ in range(3):
            time.sleep(0.08)
            with open(growing_file, "ab") as f:
                f.write(b" more data")

    writer_thread = threading.Thread(target=append_bytes)
    writer_thread.start()

    result = wait_until_file_is_stable(growing_file, config)
    writer_thread.join()

    assert result is True
    assert growing_file.stat().st_size > len(b"initial")


def test_event_handler_ignores_temp_and_hidden(tmp_path: Path):
    raw_data = {
        "watch_directory": str(tmp_path),
        "categories": {
            "PDFs": {"folder": str(tmp_path / "PDFs"), "extensions": [".pdf"]},
        },
    }
    config = parse_raw_dict(raw_data)
    executor = ThreadPoolExecutor(max_workers=1)

    try:
        handler = OrganizerEventHandler(config=config, executor=executor)

        # Temporary download file should not be handled
        assert handler._should_handle_path(tmp_path / "test.pdf.crdownload") is False
        assert handler._should_handle_path(tmp_path / "test.tmp") is False

        # Hidden file should not be handled
        assert handler._should_handle_path(tmp_path / ".test.pdf") is False

        # Valid candidate
        assert handler._should_handle_path(tmp_path / "valid.pdf") is True
    finally:
        executor.shutdown(wait=False)


def test_multi_directory_event_handler_filtering(tmp_path: Path):
    d1 = tmp_path / "Downloads"
    d2 = tmp_path / "Desktop"
    d3 = tmp_path / "Unwatched"
    d1.mkdir()
    d2.mkdir()
    d3.mkdir()

    raw_data = {
        "watch_directories": [str(d1), str(d2)],
        "categories": {
            "PDFs": {"folder": "PDFs", "extensions": [".pdf"]},
        },
    }
    config = parse_raw_dict(raw_data)
    executor = ThreadPoolExecutor(max_workers=1)

    try:
        handler = OrganizerEventHandler(config=config, executor=executor)

        # Files in both watched directories are recognized
        assert handler._should_handle_path(d1 / "a.pdf") is True
        assert handler._should_handle_path(d2 / "b.pdf") is True

        # File in unwatched directory is rejected
        assert handler._should_handle_path(d3 / "c.pdf") is False

        # Files inside destination folders in both directories are rejected
        assert handler._should_handle_path(d1 / "PDFs" / "a.pdf") is False
        assert handler._should_handle_path(d2 / "PDFs" / "b.pdf") is False
    finally:
        executor.shutdown(wait=False)


def test_multi_directory_watcher_lifecycle(tmp_path: Path):
    d1 = tmp_path / "Dir1"
    d2 = tmp_path / "Dir2"
    d1.mkdir()
    d2.mkdir()

    raw_data = {
        "watch_directories": [str(d1), str(d2)],
        "categories": {
            "PDFs": {"folder": "PDFs", "extensions": [".pdf"]},
        },
    }
    config = parse_raw_dict(raw_data)
    watcher = DirectoryWatcher(config=config, max_workers=2)

    try:
        watcher.start()
        assert watcher.observer.is_alive()

        # Dynamic reload with a 3rd directory
        d3 = tmp_path / "Dir3"
        d3.mkdir()
        new_config = parse_raw_dict({
            "watch_directories": [str(d1), str(d2), str(d3)],
            "categories": {
                "PDFs": {"folder": "PDFs", "extensions": [".pdf"]},
            },
        })
        watcher.update_config(new_config)
        assert len(watcher.config.watch_directories) == 3
    finally:
        watcher.stop()
        assert not watcher.observer.is_alive()

