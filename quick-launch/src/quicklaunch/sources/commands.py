"""Saved custom commands source plugin."""

import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from quicklaunch.models import ItemAction, ItemType, LauncherItem
from quicklaunch.sources.base import BaseSource

logger = logging.getLogger(__name__)


class CommandsSource(BaseSource):
    """Provides user-configured terminal and background commands."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._items: List[LauncherItem] = []
        self._lock = threading.RLock()

        self._load_commands()

    @property
    def id(self) -> str:
        return "commands"

    @property
    def name(self) -> str:
        return "Saved Commands"

    def _load_commands(self) -> None:
        """Parse commands list from configuration."""
        raw_commands = self.config.get("items", [])
        items: List[LauncherItem] = []

        for idx, cmd_entry in enumerate(raw_commands):
            if not isinstance(cmd_entry, dict):
                continue

            name = cmd_entry.get("name")
            command = cmd_entry.get("command")
            if not name or not command:
                continue

            run_in_term = bool(cmd_entry.get("run_in_terminal", True))
            raw_dir = cmd_entry.get("working_dir")
            working_dir = (
                str(Path(os.path.expanduser(raw_dir)).resolve())
                if raw_dir
                else None
            )
            description = cmd_entry.get("description", command)
            tags = list(cmd_entry.get("tags", []))
            tags.extend(["command", "terminal" if run_in_term else "background"])

            subtitle = command
            if working_dir:
                short_dir = working_dir.replace(str(Path.home()), "~")
                subtitle = f"{command}  [{short_dir}]"

            action_name = "Run in Terminal" if run_in_term else "Run Background Process"
            item = LauncherItem(
                id=f"command:{name}:{idx}",
                title=name,
                subtitle=subtitle,
                item_type=ItemType.COMMAND,
                source_id=self.id,
                command=command,
                run_in_terminal=run_in_term,
                working_dir=working_dir,
                tags=tags,
                icon_name="utilities-terminal" if run_in_term else "system-run",
                metadata={"description": description},
                actions=[
                    ItemAction(
                        id="execute_command",
                        name=action_name,
                        description=description,
                        shortcut_hint="↵",
                        is_primary=True,
                    )
                ],
            )
            items.append(item)

        with self._lock:
            self._items = items
        logger.info("Commands source loaded %d saved commands", len(items))

    def refresh(self) -> None:
        """Reload commands from current configuration."""
        self._load_commands()

    def get_items(self) -> List[LauncherItem]:
        """Return registered command items."""
        with self._lock:
            return list(self._items)

    def on_config_reload(self, config_data: Dict[str, Any]) -> None:
        """Update commands from refreshed configuration."""
        sources_cfg = config_data.get("sources", {})
        self.config = sources_cfg.get("commands", {})
        self.refresh()
