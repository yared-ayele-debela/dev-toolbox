"""VS Code workspaces and recent projects source plugin."""

import glob
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import unquote, urlparse

from quicklaunch.models import ItemAction, ItemType, LauncherItem
from quicklaunch.sources.base import BaseSource

logger = logging.getLogger(__name__)


class VSCodeSource(BaseSource):
    """Parses VS Code storage.json and workspaceStorage to index recent workspaces."""

    DEFAULT_STORAGE_PATHS = [
        "~/.config/Code/User/globalStorage/storage.json",
        "~/.config/Code/User/workspaceStorage",
        "~/.config/VSCodium/User/globalStorage/storage.json",
        "~/.config/VSCodium/User/workspaceStorage",
        "~/.config/Cursor/User/globalStorage/storage.json",
        "~/.config/Cursor/User/workspaceStorage",
        "~/.config/Code - OSS/User/globalStorage/storage.json",
        "~/.config/Code - OSS/User/workspaceStorage",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._items: List[LauncherItem] = []
        self._lock = threading.RLock()
        self._last_mtimes: Dict[str, float] = {}

        self._load_config_values()
        self.refresh()

    def _load_config_values(self) -> None:
        """Parse configuration parameters."""
        raw_paths = self.config.get("storage_paths", self.DEFAULT_STORAGE_PATHS)
        self.storage_paths: List[Path] = [
            Path(os.path.expanduser(p)).resolve() for p in raw_paths
        ]

    @property
    def id(self) -> str:
        return "vscode"

    @property
    def name(self) -> str:
        return "VS Code Workspaces"

    @staticmethod
    def _uri_to_path(uri: str) -> Optional[str]:
        """Convert a file:// URI to a local file system path."""
        if not uri or not isinstance(uri, str):
            return None

        if uri.startswith("file://"):
            parsed = urlparse(uri)
            clean_path = unquote(parsed.path)
            return clean_path
        elif uri.startswith("/"):
            return uri
        return None

    def _extract_from_storage_json(self, storage_file: Path) -> List[str]:
        """Parse VS Code globalStorage/storage.json for workspace paths."""
        found_paths: List[str] = []
        if not storage_file.exists() or not storage_file.is_file():
            return found_paths

        try:
            with open(storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.debug("Failed reading storage.json at %s: %s", storage_file, e)
            return found_paths

        # 1. Check profileAssociations.workspaces (Modern VS Code)
        profile_workspaces = data.get("profileAssociations", {}).get("workspaces", {})
        if isinstance(profile_workspaces, dict):
            for uri in profile_workspaces.keys():
                path = self._uri_to_path(uri)
                if path:
                    found_paths.append(path)

        # 2. Check openedPathsList (Classic format)
        opened_paths = data.get("openedPathsList", {})
        if isinstance(opened_paths, dict):
            for key in ("workspaces3", "folders2", "files2"):
                items = opened_paths.get(key, [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, str):
                            p = self._uri_to_path(item)
                            if p:
                                found_paths.append(p)
                        elif isinstance(item, dict):
                            uri = item.get("folderUri") or item.get("workspace") or item.get("fileUri")
                            p = self._uri_to_path(uri)
                            if p:
                                found_paths.append(p)

            # Check entries list in openedPathsList
            for entry in opened_paths.get("entries", []):
                if isinstance(entry, dict):
                    uri = entry.get("folderUri") or entry.get("workspaceUri")
                    p = self._uri_to_path(uri)
                    if p:
                        found_paths.append(p)

        # 3. Check backupWorkspaces
        backup = data.get("backupWorkspaces", {})
        if isinstance(backup, dict):
            for key in ("folders", "workspaces"):
                for entry in backup.get(key, []):
                    if isinstance(entry, dict):
                        uri = entry.get("folderUri") or entry.get("workspaceUri")
                        p = self._uri_to_path(uri)
                        if p:
                            found_paths.append(p)

        # 4. Check windowsState
        windows_state = data.get("windowsState", {})
        if isinstance(windows_state, dict):
            last_win = windows_state.get("lastActiveWindow")
            if isinstance(last_win, dict):
                uri = last_win.get("folder") or last_win.get("workspace")
                p = self._uri_to_path(uri)
                if p:
                    found_paths.append(p)

            for win in windows_state.get("openedWindows", []):
                if isinstance(win, dict):
                    uri = win.get("folder") or win.get("workspace")
                    p = self._uri_to_path(uri)
                    if p:
                        found_paths.append(p)

        return found_paths

    def _extract_from_workspace_storage(self, dir_path: Path) -> List[str]:
        """Parse workspaceStorage/<hash>/workspace.json files."""
        found_paths: List[str] = []
        if not dir_path.exists() or not dir_path.is_dir():
            return found_paths

        pattern = str(dir_path / "*" / "workspace.json")
        for ws_file in glob.glob(pattern):
            try:
                with open(ws_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    uri = data.get("folder") or data.get("workspace") or data.get("configuration")
                    p = self._uri_to_path(uri)
                    if p:
                        found_paths.append(p)
            except Exception:
                continue

        return found_paths

    def refresh(self) -> None:
        """Scan storage files and extract recent workspaces."""
        all_paths: List[str] = []

        for p in self.storage_paths:
            if not p.exists():
                continue
            if p.is_file():
                all_paths.extend(self._extract_from_storage_json(p))
            elif p.is_dir():
                all_paths.extend(self._extract_from_workspace_storage(p))

        items: List[LauncherItem] = []
        seen: Set[str] = set()

        for path_str in all_paths:
            if path_str in seen:
                continue
            seen.add(path_str)

            path_obj = Path(path_str)
            # Only include paths that actually exist on disk
            if not path_obj.exists():
                continue

            display_path = str(path_obj).replace(str(Path.home()), "~")
            is_workspace_file = path_obj.suffix == ".code-workspace"
            title = path_obj.stem if is_workspace_file else path_obj.name

            item = LauncherItem(
                id=f"vscode:{path_obj.resolve()}",
                title=title,
                subtitle=display_path,
                item_type=ItemType.VSCODE,
                source_id=self.id,
                path=str(path_obj.resolve()),
                icon_name="code" if not is_workspace_file else "text-x-generic",
                tags=["vscode", "code", "workspace", title.lower()],
                actions=[
                    ItemAction(
                        id="open_vscode",
                        name="Open in VS Code",
                        description=f"Launch '{title}' in VS Code",
                        shortcut_hint="↵",
                        is_primary=True,
                    ),
                    ItemAction(
                        id="open_terminal",
                        name="Open in Terminal",
                        description=f"Open terminal at {display_path}",
                        shortcut_hint="Alt+↵",
                    ),
                ],
            )
            items.append(item)

        with self._lock:
            self._items = items
        logger.info("VS Code source indexed %d recent workspaces", len(items))

    def get_items(self) -> List[LauncherItem]:
        """Return indexed VS Code workspace items."""
        with self._lock:
            return list(self._items)

    def on_config_reload(self, config_data: Dict[str, Any]) -> None:
        """Reload configuration and rescan."""
        sources_cfg = config_data.get("sources", {})
        self.config = sources_cfg.get("vscode", {})
        self._load_config_values()
        self.refresh()
