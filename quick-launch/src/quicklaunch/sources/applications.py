"""Desktop applications source plugin scanning .desktop files."""

import configparser
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from quicklaunch.models import ItemAction, ItemType, LauncherItem
from quicklaunch.sources.base import BaseSource

logger = logging.getLogger(__name__)


class ApplicationsSource(BaseSource):
    """Indexes installed desktop applications across system, snap, and flatpak directories."""

    DEFAULT_APP_DIRS = [
        "~/.local/share/applications",
        "/usr/share/applications",
        "/usr/local/share/applications",
        "/var/lib/snapd/desktop/applications",
        "/var/lib/flatpak/exports/share/applications",
        "~/.local/share/flatpak/exports/share/applications",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._items: List[LauncherItem] = []
        self._lock = threading.RLock()

        self._load_config_values()
        self.refresh()

    def _load_config_values(self) -> None:
        """Parse application source configuration parameters."""
        raw_dirs = self.config.get("app_dirs", self.DEFAULT_APP_DIRS)
        self.app_dirs: List[Path] = [
            Path(os.path.expanduser(d)).resolve() for d in raw_dirs
        ]

    @property
    def id(self) -> str:
        return "applications"

    @property
    def name(self) -> str:
        return "Applications"

    def _clean_exec_command(self, raw_exec: str) -> str:
        """Remove XDG desktop file field codes (%f, %u, %F, %U, etc.)."""
        # Field codes are % followed by single character
        cleaned = re.sub(r"%[a-zA-Z]", "", raw_exec)
        # Strip trailing unquoted double dashes or spaces
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _parse_desktop_file(self, file_path: Path) -> Optional[LauncherItem]:
        """Read a .desktop file and construct a LauncherItem if valid."""
        parser = configparser.RawConfigParser(interpolation=None, strict=False)
        try:
            # Desktop files are UTF-8 ini-like files
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                parser.read_file(f)
        except Exception as e:
            logger.debug("Failed parsing desktop file %s: %s", file_path, e)
            return None

        section = "Desktop Entry"
        if not parser.has_section(section):
            return None

        entry = parser[section]

        # Ignore non-application entries or hidden/NoDisplay items
        entry_type = entry.get("Type", "").strip()
        if entry_type and entry_type.lower() != "application":
            return None

        if entry.get("NoDisplay", "false").lower() == "true":
            return None

        if entry.get("Hidden", "false").lower() == "true":
            return None

        name = entry.get("Name", "").strip()
        raw_exec = entry.get("Exec", "").strip()
        if not name or not raw_exec:
            return None

        cleaned_exec = self._clean_exec_command(raw_exec)
        icon_name = entry.get("Icon", "application-x-executable").strip()
        comment = entry.get("Comment", "").strip()
        generic_name = entry.get("GenericName", "").strip()
        terminal = entry.get("Terminal", "false").lower() == "true"

        # Build subtitle
        subtitle = comment or generic_name or cleaned_exec

        # Tags for searchability
        tags = ["app", "application", name.lower()]
        if generic_name:
            tags.append(generic_name.lower())
        categories = entry.get("Categories", "")
        if categories:
            tags.extend([c.lower() for c in categories.split(";") if c])
        keywords = entry.get("Keywords", "")
        if keywords:
            tags.extend([k.lower() for k in keywords.split(";") if k])

        desktop_id = file_path.name

        return LauncherItem(
            id=f"app:{desktop_id}",
            title=name,
            subtitle=subtitle,
            item_type=ItemType.APPLICATION,
            source_id=self.id,
            command=cleaned_exec,
            run_in_terminal=terminal,
            tags=tags,
            icon_name=icon_name,
            metadata={"desktop_id": desktop_id, "desktop_path": str(file_path)},
            actions=[
                ItemAction(
                    id="launch_app",
                    name="Launch Application",
                    description=f"Launch {name}",
                    shortcut_hint="↵",
                    is_primary=True,
                )
            ],
        )

    def refresh(self) -> None:
        """Scan all application directories and extract desktop entries."""
        items: List[LauncherItem] = []
        seen_names: Set[str] = set()
        seen_ids: Set[str] = set()

        for dir_path in self.app_dirs:
            if not dir_path.exists() or not dir_path.is_dir():
                continue

            try:
                for entry in dir_path.iterdir():
                    if entry.suffix != ".desktop":
                        continue

                    # Earlier directories in app_dirs (user-local) take precedence over system ones
                    if entry.name in seen_ids:
                        continue
                    seen_ids.add(entry.name)

                    item = self._parse_desktop_file(entry)
                    if item:
                        # Avoid duplicate app titles pointing to same command
                        dedup_key = f"{item.title.lower()}:{item.command}"
                        if dedup_key in seen_names:
                            continue
                        seen_names.add(dedup_key)
                        items.append(item)
            except Exception as e:
                logger.debug("Error scanning app dir %s: %s", dir_path, e)

        # Sort alphabetically
        items.sort(key=lambda x: x.title.lower())

        with self._lock:
            self._items = items
        logger.info("Applications source indexed %d installed applications", len(items))

    def get_items(self) -> List[LauncherItem]:
        """Return indexed application items."""
        with self._lock:
            return list(self._items)

    def on_config_reload(self, config_data: Dict[str, Any]) -> None:
        """Reload configuration and rescan."""
        sources_cfg = config_data.get("sources", {})
        self.config = sources_cfg.get("applications", {})
        self._load_config_values()
        self.refresh()
