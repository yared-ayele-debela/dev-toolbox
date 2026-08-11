"""Data models and type definitions for clipboard entries."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ContentType(str, Enum):
    """Classified content types for clipboard entries."""

    TEXT = "text"
    CODE = "code"
    URL = "url"
    FILE_PATH = "path"
    COLOR = "color"
    JSON = "json"
    IMAGE = "image"

    @classmethod
    def from_str(cls, value: Optional[str]) -> ContentType:
        """Safely parse string into ContentType, defaulting to TEXT."""
        if not value:
            return cls.TEXT
        val = value.lower().strip()
        for member in cls:
            if member.value == val:
                return member
        return cls.TEXT


@dataclass
class ClipEntry:
    """Represents an individual clipboard entry recorded in history."""

    content: str
    content_type: ContentType = ContentType.TEXT
    source_app: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    pinned: bool = False
    size_bytes: int = 0
    is_sensitive: bool = False
    content_hash: str = ""
    preview: str = ""
    extra_data: Optional[Dict[str, Any]] = None
    id: Optional[int] = None

    def __post_init__(self) -> None:
        """Normalize fields, calculate hash and size if not provided."""
        if not self.size_bytes:
            self.size_bytes = len(self.content.encode("utf-8", errors="replace"))

        if not self.content_hash and self.content:
            self.content_hash = hashlib.sha256(
                self.content.encode("utf-8", errors="replace")
            ).hexdigest()

        if not self.preview:
            self.preview = self._generate_preview()

    def _generate_preview(self) -> str:
        """Generate a concise one-to-three line preview snippet."""
        if self.is_sensitive:
            return "•••••••••••••••• (Sensitive Content Hidden)"

        lines = [line.strip() for line in self.content.splitlines() if line.strip()]
        if not lines:
            return ""
        # Return first 2 non-empty lines joined
        preview_lines = lines[:2]
        joined = "  ↵  ".join(preview_lines)
        if len(joined) > 160:
            return joined[:157] + "..."
        return joined

    def get_display_title(self) -> str:
        """Return the primary single-line title for UI list rendering."""
        if self.is_sensitive:
            return "•••••••••••••••• [Protected Secret]"

        first_line = ""
        for line in self.content.splitlines():
            stripped = line.strip()
            if stripped:
                first_line = stripped
                break

        if not first_line:
            first_line = "[Empty or Whitespace]"

        if len(first_line) > 85:
            return first_line[:82] + "..."
        return first_line

    def get_subtitle(self) -> str:
        """Return secondary contextual details (app, timestamp, size)."""
        app = self.source_app if self.source_app else "Clipboard"
        time_str = self.formatted_timestamp()
        size_str = self.formatted_size()
        sensitive_tag = " • 🔒 Sensitive" if self.is_sensitive else ""
        return f"{app} • {time_str} • {size_str}{sensitive_tag}"

    def get_badge_label(self) -> str:
        """Return a compact uppercase badge text."""
        if self.pinned:
            return "PINNED"
        return self.content_type.value.upper()

    def get_badge_css_class(self) -> str:
        """Return the CSS class for badge rendering."""
        if self.pinned:
            return "badge-pinned"
        type_map = {
            ContentType.TEXT: "badge-text",
            ContentType.CODE: "badge-code",
            ContentType.URL: "badge-url",
            ContentType.FILE_PATH: "badge-path",
            ContentType.COLOR: "badge-color",
            ContentType.JSON: "badge-json",
            ContentType.IMAGE: "badge-image",
        }
        return type_map.get(self.content_type, "badge-text")

    def formatted_timestamp(self) -> str:
        """Format epoch timestamp into a human-friendly relative string."""
        now = time.time()
        diff = max(0, int(now - self.timestamp))

        if diff < 10:
            return "just now"
        if diff < 60:
            return f"{diff}s ago"
        if diff < 3600:
            mins = diff // 60
            return f"{mins}m ago"
        if diff < 86400:
            hours = diff // 3600
            return f"{hours}h ago"
        days = diff // 86400
        if days == 1:
            return "yesterday"
        if days < 30:
            return f"{days}d ago"

        import datetime
        dt = datetime.datetime.fromtimestamp(self.timestamp)
        return dt.strftime("%b %d")

    def formatted_size(self) -> str:
        """Format size in bytes to human-readable string."""
        b = self.size_bytes
        if b < 1024:
            return f"{b} B"
        if b < 1024 * 1024:
            return f"{b / 1024:.1f} KB"
        return f"{b / (1024 * 1024):.2f} MB"

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry into serializable dictionary."""
        data = asdict(self)
        data["content_type"] = self.content_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ClipEntry:
        """Construct a ClipEntry from a dictionary."""
        content_type = ContentType.from_str(data.get("content_type"))
        return cls(
            id=data.get("id"),
            content=data.get("content", ""),
            content_type=content_type,
            source_app=data.get("source_app"),
            timestamp=float(data.get("timestamp", time.time())),
            pinned=bool(data.get("pinned", False)),
            size_bytes=int(data.get("size_bytes", 0)),
            is_sensitive=bool(data.get("is_sensitive", False)),
            content_hash=data.get("content_hash", ""),
            preview=data.get("preview", ""),
            extra_data=data.get("extra_data"),
        )
