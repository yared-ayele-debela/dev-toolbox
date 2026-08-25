"""Execution engine for launcher items and actions."""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from quicklaunch.frecency import FrecencyStore
from quicklaunch.models import ItemType, LauncherItem

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Dispatches execution for projects, VS Code workspaces, and saved commands."""

    def __init__(self, frecency_store: Optional[FrecencyStore] = None) -> None:
        self.frecency_store = frecency_store
        self._preferred_terminal: Optional[str] = None

    def find_terminal_emulator(self) -> Optional[str]:
        """Locate an installed terminal emulator."""
        if self._preferred_terminal and shutil.which(self._preferred_terminal):
            return self._preferred_terminal

        # Check $TERMINAL environment variable
        env_term = os.environ.get("TERMINAL")
        if env_term and shutil.which(env_term):
            self._preferred_terminal = env_term
            return env_term

        # List of popular Linux terminals in preference order
        candidates = [
            "gnome-terminal",
            "ptyxis",
            "kitty",
            "alacritty",
            "konsole",
            "wezterm",
            "xfce4-terminal",
            "terminator",
            "x-terminal-emulator",
            "xterm",
        ]

        for cand in candidates:
            if shutil.which(cand):
                self._preferred_terminal = cand
                return cand

        return None

    def _build_terminal_command(
        self,
        command_to_run: str,
        working_dir: Optional[str] = None,
        hold_open: bool = True,
    ) -> List[str]:
        """Construct the terminal process invocation command."""
        term = self.find_terminal_emulator()
        if not term:
            raise RuntimeError("No terminal emulator found on this system.")

        # Wrap command with user pause so output remains readable before closing
        shell_cmd = command_to_run
        if hold_open:
            shell_cmd = f"{command_to_run}; echo; echo '[QuickLaunch: Command finished. Press Enter to exit]'; read -r _"

        bash_invocation = ["bash", "-c", shell_cmd]

        if term in ("gnome-terminal", "ptyxis"):
            cmd = [term]
            if working_dir and os.path.isdir(working_dir):
                cmd.append(f"--working-directory={working_dir}")
            cmd.extend(["--"] + bash_invocation)
            return cmd

        elif term == "kitty":
            cmd = [term]
            if working_dir and os.path.isdir(working_dir):
                cmd.extend(["--directory", working_dir])
            cmd.extend(bash_invocation)
            return cmd

        elif term == "alacritty":
            cmd = [term]
            if working_dir and os.path.isdir(working_dir):
                cmd.extend(["--working-directory", working_dir])
            cmd.extend(["-e"] + bash_invocation)
            return cmd

        elif term == "konsole":
            cmd = [term]
            if working_dir and os.path.isdir(working_dir):
                cmd.extend(["--workdir", working_dir])
            cmd.extend(["-e"] + bash_invocation)
            return cmd

        else:
            # Generic fallback (x-terminal-emulator, xterm, etc.)
            cmd = [term]
            if working_dir and os.path.isdir(working_dir):
                cd_bash = f"cd '{working_dir}' && {shell_cmd}"
                cmd.extend(["-e", "bash", "-c", cd_bash])
            else:
                cmd.extend(["-e"] + bash_invocation)
            return cmd

    def execute_terminal_command(
        self,
        command: str,
        working_dir: Optional[str] = None,
        hold_open: bool = True,
    ) -> None:
        """Spawn command in a new terminal window."""
        args = self._build_terminal_command(command, working_dir, hold_open)
        logger.info("Spawning terminal command: %s (cwd=%s)", args, working_dir)
        subprocess.Popen(
            args,
            cwd=working_dir,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def execute_background_command(
        self,
        command: str,
        working_dir: Optional[str] = None,
    ) -> None:
        """Execute command as a detached background process."""
        logger.info("Spawning detached background command: %s (cwd=%s)", command, working_dir)
        subprocess.Popen(
            command,
            shell=True,
            cwd=working_dir,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def open_path_in_file_manager(self, path: str) -> None:
        """Open directory or file using xdg-open."""
        logger.info("Opening path in default file manager: %s", path)
        subprocess.Popen(
            ["xdg-open", path],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def open_in_vscode(self, path: str) -> None:
        """Open directory or workspace file in VS Code."""
        # Check for code or cursor or codium
        code_bin = shutil.which("code") or shutil.which("cursor") or shutil.which("codium")
        if not code_bin:
            code_bin = "code"

        logger.info("Opening path in editor: %s %s", code_bin, path)
        subprocess.Popen(
            [code_bin, path],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def execute(self, item: LauncherItem, action_type: str = "primary") -> bool:
        """Execute an action for the specified item.

        Args:
            item: The LauncherItem to execute.
            action_type: 'primary', 'open_terminal', 'open_vscode', etc.
        """
        try:
            if item.item_type == ItemType.PROJECT:
                if action_type in ("open_terminal", "secondary"):
                    if item.path:
                        # Open new shell in terminal at this path
                        self.execute_terminal_command("bash", working_dir=item.path, hold_open=False)
                    else:
                        return False
                elif action_type == "open_vscode":
                    if item.path:
                        self.open_in_vscode(item.path)
                    else:
                        return False
                else:
                    # Default primary action: open in file manager
                    if item.path:
                        self.open_path_in_file_manager(item.path)
                    else:
                        return False

            elif item.item_type == ItemType.VSCODE:
                if action_type in ("open_terminal", "secondary"):
                    folder_path = (
                        str(Path(item.path).parent)
                        if item.path and item.path.endswith(".code-workspace")
                        else item.path
                    )
                    if folder_path:
                        self.execute_terminal_command("bash", working_dir=folder_path, hold_open=False)
                    else:
                        return False
                else:
                    # Primary action: open in VS Code
                    if item.path:
                        self.open_in_vscode(item.path)
                    else:
                        return False

            elif item.item_type == ItemType.COMMAND:
                if not item.command:
                    return False
                if item.run_in_terminal:
                    self.execute_terminal_command(
                        item.command,
                        working_dir=item.working_dir,
                        hold_open=True,
                    )
                else:
                    self.execute_background_command(
                        item.command,
                        working_dir=item.working_dir,
                    )

            elif item.item_type == ItemType.APPLICATION:
                desktop_id = item.metadata.get("desktop_id")
                if desktop_id and shutil.which("gtk-launch"):
                    logger.info("Launching desktop app via gtk-launch: %s", desktop_id)
                    subprocess.Popen(
                        ["gtk-launch", desktop_id],
                        start_new_session=True,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                elif item.command:
                    if item.run_in_terminal:
                        self.execute_terminal_command(item.command, hold_open=False)
                    else:
                        self.execute_background_command(item.command)
                else:
                    return False

            else:
                # Custom fallback
                if item.command:
                    if item.run_in_terminal:
                        self.execute_terminal_command(item.command, working_dir=item.working_dir)
                    else:
                        self.execute_background_command(item.command, working_dir=item.working_dir)
                elif item.path:
                    self.open_path_in_file_manager(item.path)
                else:
                    return False

            # Record frecency access on successful launch
            if self.frecency_store:
                self.frecency_store.record_access(item.id)

            return True

        except Exception as e:
            logger.error("Failed to execute item %s (action=%s): %s", item.id, action_type, e, exc_info=True)
            return False
