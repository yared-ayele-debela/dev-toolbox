"""Project folders recursive scanner source plugin."""

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from quicklaunch.models import ItemAction, ItemType, LauncherItem
from quicklaunch.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Try importing watchdog if available
try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


class ProjectsSource(BaseSource):
    """Scans configured root directories for software projects and git repositories."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._items: List[LauncherItem] = []
        self._lock = threading.RLock()
        self._observer: Optional[Any] = None
        self._timer_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._load_config_values()
        # Initial scan in background or sync
        self.refresh()
        self._setup_watcher_and_timer()

    def _load_config_values(self) -> None:
        """Parse configuration parameters."""
        raw_roots = self.config.get("root_dirs", [
            "~/Projects",
            "~/Desktop/Projects",
            "~/dev",
            "~/Documents",
        ])
        self.root_dirs: List[Path] = [
            Path(os.path.expanduser(p)).resolve() for p in raw_roots
        ]
        self.max_depth: int = int(self.config.get("max_depth", 2))
        self.project_markers: Set[str] = set(self.config.get("project_markers", [
            ".git",
            "package.json",
            "pyproject.toml",
            "Cargo.toml",
            "go.mod",
            "composer.json",
            "pom.xml",
            "Makefile",
            "CMakeLists.txt",
        ]))
        self.ignore_patterns: Set[str] = set(self.config.get("ignore_patterns", [
            "node_modules",
            ".git",
            "venv",
            ".venv",
            "env",
            "__pycache__",
            "target",
            "dist",
            "build",
            ".cache",
            ".idea",
            ".vscode",
        ]))
        self.refresh_interval: int = int(self.config.get("refresh_interval_minutes", 10)) * 60
        self.watch_filesystem: bool = bool(self.config.get("watch_filesystem", True))

    @property
    def id(self) -> str:
        return "projects"

    @property
    def name(self) -> str:
        return "Project Folders"

    def _is_ignored(self, name: str) -> bool:
        """Check if directory name matches ignore patterns."""
        if name in self.ignore_patterns:
            return True
        if name.startswith(".") and name != ".git":
            return True
        return False

    def _has_project_marker(self, directory: Path) -> bool:
        """Check whether directory contains any project marker files or folders."""
        try:
            entries = os.listdir(directory)
            for marker in self.project_markers:
                if marker in entries:
                    return True
        except (PermissionError, FileNotFoundError, OSError):
            return False
        return False

    def _scan_directory(self, root: Path, current_depth: int = 1) -> List[LauncherItem]:
        """Recursively scan directory up to max_depth for projects."""
        found: List[LauncherItem] = []
        if not root.exists() or not root.is_dir():
            return found

        try:
            with os.scandir(root) as scanner:
                subdirs: List[Path] = []
                for entry in scanner:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            name = entry.name
                            if self._is_ignored(name):
                                continue
                            subdirs.append(Path(entry.path))
                    except (PermissionError, OSError):
                        continue

            for subdir in subdirs:
                # Check if this subdirectory is a project
                is_proj = self._has_project_marker(subdir)
                
                # If marked as project, or if we are at leaf / depth limit, add it
                if is_proj or current_depth >= self.max_depth:
                    # Create LauncherItem
                    display_path = str(subdir).replace(str(Path.home()), "~")
                    item = LauncherItem(
                        id=f"project:{subdir.resolve()}",
                        title=subdir.name,
                        subtitle=display_path,
                        item_type=ItemType.PROJECT,
                        source_id=self.id,
                        path=str(subdir.resolve()),
                        icon_name="folder-git" if (subdir / ".git").exists() else "folder",
                        tags=["project", "folder", subdir.name.lower()],
                        actions=[
                            ItemAction(
                                id="open_folder",
                                name="Open in File Manager",
                                description=f"Open {subdir.name} in default file manager",
                                shortcut_hint="↵",
                                is_primary=True,
                            ),
                            ItemAction(
                                id="open_terminal",
                                name="Open in Terminal",
                                description=f"Open new terminal at {display_path}",
                                shortcut_hint="Alt+↵",
                            ),
                            ItemAction(
                                id="open_vscode",
                                name="Open in VS Code",
                                description=f"Open {subdir.name} in VS Code",
                                shortcut_hint="Ctrl+↵",
                            ),
                        ],
                    )
                    found.append(item)
                    # If it was identified as a project via markers, do not recurse into its subfolders
                    if is_proj:
                        continue

                # Recurse if below max_depth
                if current_depth < self.max_depth:
                    found.extend(self._scan_directory(subdir, current_depth + 1))

        except (PermissionError, FileNotFoundError, OSError) as e:
            logger.debug("Error scanning directory %s: %s", root, e)

        return found

    def refresh(self) -> None:
        """Scan all configured roots and update cached items."""
        items: List[LauncherItem] = []
        seen_paths: Set[str] = set()

        for root in self.root_dirs:
            if not root.exists():
                continue
            scanned = self._scan_directory(root, current_depth=1)
            for item in scanned:
                if item.path and item.path not in seen_paths:
                    seen_paths.add(item.path)
                    items.append(item)

        with self._lock:
            self._items = items
        logger.info("Project source indexed %d project folders", len(items))

    def get_items(self) -> List[LauncherItem]:
        """Return cached list of project items."""
        with self._lock:
            return list(self._items)

    def _setup_watcher_and_timer(self) -> None:
        """Start watchdog file watcher (if available) and periodic rescan timer."""
        # Watchdog observer setup
        if WATCHDOG_AVAILABLE and self.watch_filesystem:
            try:
                class FolderChangeHandler(FileSystemEventHandler):
                    def __init__(self, on_change_callback):
                        super().__init__()
                        self.on_change = on_change_callback
                        self.last_triggered = 0.0

                    def on_any_event(self, event):
                        if event.is_directory:
                            now = time.time()
                            # Debounce rapid filesystem events
                            if now - self.last_triggered > 2.0:
                                self.last_triggered = now
                                threading.Thread(target=self.on_change, daemon=True).start()

                self._observer = Observer()
                handler = FolderChangeHandler(self.refresh)
                for root in self.root_dirs:
                    if root.exists():
                        self._observer.schedule(handler, str(root), recursive=False)
                self._observer.daemon = True
                self._observer.start()
                logger.info("Watchdog observer started for project roots")
            except Exception as e:
                logger.warning("Could not start watchdog observer: %s", e)

        # Periodic timer thread (always active as a safety net)
        if self.refresh_interval > 0:
            def timer_worker():
                while not self._stop_event.wait(self.refresh_interval):
                    try:
                        self.refresh()
                    except Exception as e:
                        logger.error("Error in project rescan timer: %s", e)

            self._timer_thread = threading.Thread(target=timer_worker, daemon=True)
            self._timer_thread.start()

    def on_config_reload(self, config_data: Dict[str, Any]) -> None:
        """Reload configuration and rescan."""
        sources_cfg = config_data.get("sources", {})
        self.config = sources_cfg.get("projects", {})
        self._load_config_values()
        self.refresh()

    def shutdown(self) -> None:
        """Stop background threads and file observers."""
        self._stop_event.set()
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=1.0)
            except Exception:
                pass
