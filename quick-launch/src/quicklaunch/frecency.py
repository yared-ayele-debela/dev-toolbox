"""Usage-frequency and recency (Frecency) scoring engine for QuickLaunch."""

import json
import math
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from quicklaunch.constants import DATA_DIR, FRECENCY_FILE


class FrecencyStore:
    """Manages persistent usage history and computes frecency scores.

    Frecency combines Frequency (how many times an item has been launched)
    and Recency (how recently it was launched) to dynamically rank frequently
    and recently accessed items higher.
    """

    def __init__(self, file_path: Optional[Path] = None, half_life_days: float = 14.0) -> None:
        self.file_path = Path(file_path) if file_path else FRECENCY_FILE
        self.half_life_days = max(1.0, float(half_life_days))
        self._lock = threading.Lock()
        self._items: Dict[str, Dict] = {}
        self.load()

    def load(self) -> None:
        """Load history from JSON file."""
        with self._lock:
            if not self.file_path.exists():
                self._items = {}
                return

            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._items = data.get("items", {})
            except Exception:
                # Corrupted or unreadable history; reset gracefully
                self._items = {}

    def save(self) -> None:
        """Atomically persist history to JSON file."""
        with self._lock:
            try:
                self.file_path.parent.mkdir(parents=True, exist_ok=True)
                data = {
                    "version": 1,
                    "updated_at": time.time(),
                    "items": self._items,
                }
                
                # Write to temp file in same directory then rename (atomic operation)
                with tempfile.NamedTemporaryFile(
                    "w", dir=self.file_path.parent, delete=False, encoding="utf-8"
                ) as tf:
                    json.dump(data, tf, indent=2)
                    temp_name = tf.name
                os.replace(temp_name, self.file_path)
            except Exception:
                pass

    def record_access(self, item_id: str, timestamp: Optional[float] = None) -> None:
        """Record an execution event for the given item."""
        if not item_id:
            return

        ts = timestamp if timestamp is not None else time.time()
        with self._lock:
            entry = self._items.setdefault(item_id, {"count": 0, "last_used": ts, "history": []})
            entry["count"] += 1
            entry["last_used"] = ts
            # Keep the last 10 execution timestamps to avoid unbounded growth
            history = entry.setdefault("history", [])
            history.append(ts)
            if len(history) > 10:
                entry["history"] = history[-10:]

        self.save()

    def get_recency_weight(self, last_used: float, now: Optional[float] = None) -> float:
        """Calculate recency weight based on time elapsed since last use.

        Weights:
        - Within 4 hours: 100
        - Within 24 hours: 80
        - Within 3 days: 60
        - Within 7 days: 40
        - Within 14 days: 20
        - Within 30 days: 10
        - Older: 5
        """
        current_time = now if now is not None else time.time()
        elapsed_seconds = max(0.0, current_time - last_used)
        elapsed_hours = elapsed_seconds / 3600.0

        if elapsed_hours <= 4.0:
            return 100.0
        elif elapsed_hours <= 24.0:
            return 80.0
        elif elapsed_hours <= 72.0:  # 3 days
            return 60.0
        elif elapsed_hours <= 168.0:  # 7 days
            return 40.0
        elif elapsed_hours <= 336.0:  # 14 days
            return 20.0
        elif elapsed_hours <= 720.0:  # 30 days
            return 10.0
        else:
            return 5.0

    def get_raw_score(self, item_id: str, now: Optional[float] = None) -> float:
        """Compute the unnormalized frecency score for an item."""
        with self._lock:
            entry = self._items.get(item_id)
            if not entry:
                return 0.0

            count = entry.get("count", 0)
            last_used = entry.get("last_used", 0.0)

        if count <= 0 or last_used <= 0.0:
            return 0.0

        recency_weight = self.get_recency_weight(last_used, now)
        # Logarithmic scaling on count prevents extremely frequent items from starving out others
        frequency_factor = math.log1p(count)
        return frequency_factor * recency_weight

    def get_normalized_score(self, item_id: str, now: Optional[float] = None) -> float:
        """Return a score bounded roughly between 0.0 and 100.0."""
        raw = self.get_raw_score(item_id, now)
        if raw <= 0.0:
            return 0.0
        # Map raw score (typically 0 - 300) smoothly into 0 - 100
        # e.g., raw=100 -> ~63.2, raw=250 -> ~91.8
        return 100.0 * (1.0 - math.exp(-raw / 100.0))

    def get_top_item_ids(self, limit: int = 10) -> List[Tuple[str, float]]:
        """Get the top items sorted by frecency score."""
        with self._lock:
            ids = list(self._items.keys())

        now = time.time()
        scored = [(item_id, self.get_raw_score(item_id, now)) for item_id in ids]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def clear(self) -> None:
        """Clear all frecency history."""
        with self._lock:
            self._items.clear()
        self.save()
