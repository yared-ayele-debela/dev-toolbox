"""Sources package for QuickLaunch plugins."""

from quicklaunch.sources.applications import ApplicationsSource
from quicklaunch.sources.base import BaseSource
from quicklaunch.sources.commands import CommandsSource
from quicklaunch.sources.projects import ProjectsSource
from quicklaunch.sources.registry import SourceRegistry
from quicklaunch.sources.vscode import VSCodeSource

__all__ = [
    "ApplicationsSource",
    "BaseSource",
    "SourceRegistry",
    "ProjectsSource",
    "VSCodeSource",
    "CommandsSource",
]
