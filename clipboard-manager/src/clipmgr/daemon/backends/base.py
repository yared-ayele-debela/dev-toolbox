"""Base interface for clipboard listening and management backends."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional


class ClipboardBackend(ABC):
    """Abstract base class defining clipboard event listening and retrieval."""

    @abstractmethod
    def start(self, on_change: Callable[[str, Optional[str]], None]) -> None:
        """Start listening for clipboard change events.

        Args:
            on_change: Callback function invoked when new clipboard content arrives.
                       Signature: on_change(content: str, source_app: Optional[str])
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop listening and clean up any resources/subprocesses."""
        pass

    @abstractmethod
    def get_text(self) -> str:
        """Retrieve current text content from system clipboard."""
        pass

    @abstractmethod
    def set_text(self, text: str) -> bool:
        """Set text content onto system clipboard."""
        pass
