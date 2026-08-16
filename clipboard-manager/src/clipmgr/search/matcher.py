"""Fuzzy search and ranking engine using RapidFuzz."""

import logging
import time
from typing import List, Optional, Tuple

from rapidfuzz import fuzz

from clipmgr.models import ClipEntry, ContentType

logger = logging.getLogger(__name__)


class FuzzyMatcher:
    """Ranks and filters clipboard entries using RapidFuzz and recency/pinned weights."""

    def __init__(self, score_threshold: float = 40.0) -> None:
        self.score_threshold = score_threshold

    def search(
        self,
        query: str,
        entries: List[ClipEntry],
        limit: int = 25,
        content_type: Optional[ContentType] = None,
        pinned_only: bool = False,
        include_sensitive: bool = False,
    ) -> List[ClipEntry]:
        """Filter and rank entries based on query, type, and pinned priority.

        Args:
            query: User's typed search query.
            entries: Candidate entries from database.
            limit: Maximum results to return.
            content_type: Optional filter by content classification.
            pinned_only: If True, only return pinned entries.
            include_sensitive: If False, omit protected secrets from search results.

        Returns:
            List of ranked ClipEntry objects.
        """
        q = query.strip().lower()

        # Filter out ineligible entries first
        filtered: List[ClipEntry] = []
        for entry in entries:
            if not include_sensitive and entry.is_sensitive:
                continue
            if pinned_only and not entry.pinned:
                continue
            if content_type and entry.content_type != content_type:
                continue
            filtered.append(entry)

        # If query is empty, return pinned items first, then ordered by recency
        if not q:
            filtered.sort(key=lambda e: (e.pinned, e.timestamp), reverse=True)
            return filtered[:limit]

        # Calculate fuzzy scores for matching entries
        scored_entries: List[Tuple[float, ClipEntry]] = []
        for entry in filtered:
            score = self._compute_score(q, entry)
            if score >= self.score_threshold:
                scored_entries.append((score, entry))

        # Sort: match score DESC, pinned DESC, timestamp DESC
        scored_entries.sort(
            key=lambda item: (
                item[0],
                1 if item[1].pinned else 0,
                item[1].timestamp,
            ),
            reverse=True,
        )

        return [item[1] for item in scored_entries[:limit]]

    def _compute_score(self, query: str, entry: ClipEntry) -> float:
        """Compute comprehensive match score for an entry."""
        # Use first 1500 characters of content for fast evaluation
        content_sample = entry.content[:1500].lower()
        app_name = (entry.source_app or "").lower()

        # 1. Fuzzy ratios
        ratio_content = fuzz.partial_ratio(query, content_sample)
        wratio_content = fuzz.WRatio(query, content_sample)
        base_content_score = max(ratio_content, wratio_content)

        # 2. Source app matching
        app_score = fuzz.WRatio(query, app_name) if app_name else 0.0

        best_score = max(base_content_score, app_score)

        # 3. Exact substring boost
        if query in content_sample:
            best_score += 25.0

        # 4. Prefix match boost
        if content_sample.startswith(query):
            best_score += 35.0

        # 5. Word boundary match boost
        if f" {query}" in content_sample:
            best_score += 15.0

        # 6. Pinned relevance boost
        if entry.pinned:
            best_score += 25.0

        return best_score
