"""Source registry to manage, aggregate, and query all source plugins."""

import logging
import threading
from typing import Dict, List, Optional

from quicklaunch.models import LauncherItem
from quicklaunch.sources.base import BaseSource

logger = logging.getLogger(__name__)


class SourceRegistry:
    """Manages active source plugins and aggregates their items."""

    def __init__(self) -> None:
        self._sources: Dict[str, BaseSource] = {}
        self._items_cache: List[LauncherItem] = []
        self._lock = threading.RLock()

    def register(self, source: BaseSource) -> None:
        """Register a new source plugin."""
        with self._lock:
            self._sources[source.id] = source
            logger.info("Registered source plugin: %s (%s)", source.name, source.id)

    def unregister(self, source_id: str) -> None:
        """Unregister a source plugin by ID."""
        with self._lock:
            if source_id in self._sources:
                source = self._sources.pop(source_id)
                source.shutdown()

    def get_source(self, source_id: str) -> Optional[BaseSource]:
        """Get a registered source by ID."""
        with self._lock:
            return self._sources.get(source_id)

    def refresh_all(self) -> None:
        """Trigger a refresh on all registered sources and update aggregated cache."""
        with self._lock:
            sources = list(self._sources.values())

        all_items: List[LauncherItem] = []
        for source in sources:
            try:
                source.refresh()
                items = source.get_items()
                all_items.extend(items)
            except Exception as e:
                logger.error("Error refreshing source '%s': %s", source.id, e, exc_info=True)

        with self._lock:
            self._items_cache = all_items

    def get_all_items(self) -> List[LauncherItem]:
        """Return the combined list of items from all sources."""
        with self._lock:
            if not self._items_cache and self._sources:
                # Initial population if cache is empty
                self.refresh_all()
            return list(self._items_cache)

    def handle_action(self, item: LauncherItem, action_type: str = "primary") -> bool:
        """Dispatch item execution to the responsible source plugin if implemented."""
        with self._lock:
            source = self._sources.get(item.source_id)
        if source:
            try:
                return source.handle_action(item, action_type)
            except Exception as e:
                logger.error("Error handling action in source '%s': %s", item.source_id, e)
        return False

    def notify_config_reload(self, config_data: dict) -> None:
        """Notify all sources of configuration updates."""
        with self._lock:
            sources = list(self._sources.values())
        for source in sources:
            try:
                source.on_config_reload(config_data)
            except Exception as e:
                logger.error("Error in on_config_reload for '%s': %s", source.id, e)
        self.refresh_all()

    def shutdown_all(self) -> None:
        """Shutdown all registered sources and release resources."""
        with self._lock:
            for source in self._sources.values():
                try:
                    source.shutdown()
                except Exception:
                    pass
            self._sources.clear()
            self._items_cache.clear()
