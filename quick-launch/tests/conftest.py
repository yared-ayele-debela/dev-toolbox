"""Shared pytest fixtures for QuickLaunch unit tests."""

import os
import tempfile
import time
from pathlib import Path
from typing import Generator, List
import pytest

from quicklaunch.frecency import FrecencyStore
from quicklaunch.models import ItemAction, ItemType, LauncherItem


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory cleaned up after each test."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def frecency_store(temp_dir: Path) -> FrecencyStore:
    """Provide a clean FrecencyStore instance backed by temp file."""
    history_file = temp_dir / "test_frecency.json"
    return FrecencyStore(file_path=history_file)


@pytest.fixture
def sample_items() -> List[LauncherItem]:
    """Provide diverse sample items representing all three sources."""
    return [
        LauncherItem(
            id="project:/home/user/Projects/Ecommerce-ERP",
            title="Ecommerce-ERP",
            subtitle="~/Projects/Ecommerce-ERP",
            item_type=ItemType.PROJECT,
            source_id="projects",
            path="/home/user/Projects/Ecommerce-ERP",
            tags=["project", "laravel", "php"],
        ),
        LauncherItem(
            id="vscode:/home/user/Projects/quicklaunch",
            title="quicklaunch",
            subtitle="~/Projects/quicklaunch",
            item_type=ItemType.VSCODE,
            source_id="vscode",
            path="/home/user/Projects/quicklaunch",
            tags=["vscode", "code", "python"],
        ),
        LauncherItem(
            id="command:docker-ps",
            title="Docker Containers",
            subtitle="docker ps -a",
            item_type=ItemType.COMMAND,
            source_id="commands",
            command="docker ps -a",
            run_in_terminal=True,
            tags=["docker", "containers", "command"],
        ),
        LauncherItem(
            id="command:sys-update",
            title="System Package Update",
            subtitle="sudo apt update && sudo apt upgrade -y",
            item_type=ItemType.COMMAND,
            source_id="commands",
            command="sudo apt update && sudo apt upgrade -y",
            run_in_terminal=True,
            tags=["apt", "update", "system"],
        ),
    ]
