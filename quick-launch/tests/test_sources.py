"""Unit tests for search source plugins (Projects, VS Code, Commands)."""

import json
from pathlib import Path

from quicklaunch.models import ItemType
from quicklaunch.sources.commands import CommandsSource
from quicklaunch.sources.projects import ProjectsSource
from quicklaunch.sources.vscode import VSCodeSource


def test_projects_source_scanner(temp_dir: Path) -> None:
    """Verify ProjectsSource detects project markers and ignores blacklisted dirs."""
    dev_root = temp_dir / "dev"
    dev_root.mkdir()

    # 1. Project with .git
    proj1 = dev_root / "my-python-app"
    proj1.mkdir()
    (proj1 / ".git").mkdir()

    # 2. Project with package.json
    proj2 = dev_root / "web-frontend"
    proj2.mkdir()
    (proj2 / "package.json").write_text("{}", encoding="utf-8")

    # 3. Ignored directory (node_modules)
    node_modules = proj2 / "node_modules" / "some-lib"
    node_modules.mkdir(parents=True)
    (node_modules / "package.json").write_text("{}", encoding="utf-8")

    # 4. Plain non-project folder
    plain_dir = dev_root / "misc"
    plain_dir.mkdir()

    cfg = {
        "root_dirs": [str(dev_root)],
        "max_depth": 1,
        "watch_filesystem": False,
        "refresh_interval_minutes": 0,
    }

    source = ProjectsSource(config=cfg)
    items = source.get_items()

    item_names = {item.title for item in items}
    assert "my-python-app" in item_names
    assert "web-frontend" in item_names
    assert "some-lib" not in item_names
    source.shutdown()


def test_vscode_source_parser(temp_dir: Path) -> None:
    """Verify VSCodeSource extracts workspace paths from storage.json."""
    # Create mock existing directories on disk
    ws1 = temp_dir / "workspace-one"
    ws1.mkdir()
    ws2 = temp_dir / "workspace-two"
    ws2.mkdir()

    storage_file = temp_dir / "storage.json"
    data = {
        "profileAssociations": {
            "workspaces": {
                f"file://{ws1}": "__default__profile__"
            }
        },
        "backupWorkspaces": {
            "folders": [
                {"folderUri": f"file://{ws2}"}
            ]
        }
    }
    storage_file.write_text(json.dumps(data), encoding="utf-8")

    cfg = {
        "storage_paths": [str(storage_file)],
    }
    source = VSCodeSource(config=cfg)
    items = source.get_items()

    assert len(items) == 2
    titles = {item.title for item in items}
    assert "workspace-one" in titles
    assert "workspace-two" in titles


def test_commands_source_loading() -> None:
    """Verify CommandsSource creates LauncherItems with correct attributes."""
    cfg = {
        "items": [
            {
                "name": "Docker Logs",
                "command": "docker logs -f my_app",
                "run_in_terminal": True,
                "tags": ["docker", "logs"],
            },
            {
                "name": "Background Backup",
                "command": "rsync -a /data /backup",
                "run_in_terminal": False,
                "tags": ["backup"],
            }
        ]
    }

    source = CommandsSource(config=cfg)
    items = source.get_items()

    assert len(items) == 2

    dock = next(it for it in items if it.title == "Docker Logs")
    assert dock.item_type == ItemType.COMMAND
    assert dock.run_in_terminal is True
    assert "docker" in dock.tags

    bak = next(it for it in items if it.title == "Background Backup")
    assert bak.run_in_terminal is False


def test_applications_source_parser(temp_dir: Path) -> None:
    """Verify ApplicationsSource parses .desktop files, strips field codes, and extracts metadata."""
    from quicklaunch.sources.applications import ApplicationsSource

    app_dir = temp_dir / "applications"
    app_dir.mkdir()

    desktop_content = """[Desktop Entry]
Version=1.0
Type=Application
Name=Visual Studio Code
GenericName=Text Editor
Comment=Code Editing. Refined.
Exec=/usr/share/code/code --unity-launch %F
Icon=vscode
Terminal=false
Categories=Utility;Development;IDE;
Keywords=vscode;code;
"""
    (app_dir / "code.desktop").write_text(desktop_content, encoding="utf-8")

    # A hidden app that should be ignored
    hidden_content = """[Desktop Entry]
Type=Application
Name=Hidden Internal Tool
Exec=tool %u
NoDisplay=true
"""
    (app_dir / "hidden.desktop").write_text(hidden_content, encoding="utf-8")

    cfg = {"app_dirs": [str(app_dir)]}
    source = ApplicationsSource(config=cfg)
    items = source.get_items()

    assert len(items) == 1
    app = items[0]
    assert app.title == "Visual Studio Code"
    assert app.item_type == ItemType.APPLICATION
    assert app.command == "/usr/share/code/code --unity-launch"
    assert app.icon_name == "vscode"
    assert "development" in app.tags
