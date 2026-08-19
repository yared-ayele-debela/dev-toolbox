"""Main entrypoint, CLI dispatcher, and application coordinator for ClipMgr."""

import argparse
import base64
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from clipmgr.config import ConfigManager
from clipmgr.constants import (
    APP_NAME,
    APP_TITLE,
    CONFIG_FILE,
    DB_FILE,
    VERSION,
    ensure_secure_directories,
)
from clipmgr.daemon.listener import ClipboardDaemon
from clipmgr.daemon.window_detector import WindowDetector
from clipmgr.hotkey.manager import HotkeyManager
from clipmgr.hotkey.wayland import is_gnome_available, setup_gnome_shortcut
from clipmgr.ipc import IPCServer, send_ipc_command
from clipmgr.models import ClipEntry, ContentType
from clipmgr.search.matcher import FuzzyMatcher
from clipmgr.storage.database import DatabaseManager
from clipmgr.ui.paster import DirectPaster
from clipmgr.ui.window import ClipboardWindow

logger = logging.getLogger(APP_NAME)


class ClipMgrApp:
    """Central application coordinator holding background listener, UI, and IPC server."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        ensure_secure_directories()

        # 1. Config and Database
        self.config_mgr = ConfigManager(config_path=config_path)
        self.db = DatabaseManager(
            retention_days=self.config_mgr.get("storage.retention_days", 30),
            encryption_enabled=self.config_mgr.get("storage.encryption.enabled", False),
        )

        # 2. Daemon background listener
        self.daemon = ClipboardDaemon(config_mgr=self.config_mgr, db_mgr=self.db)

        # 3. Matcher and UI Window
        self.matcher = FuzzyMatcher()
        self.window = ClipboardWindow(
            db_mgr=self.db,
            matcher=self.matcher,
            backend=self.daemon.backend,
            config_mgr=self.config_mgr,
        )

        # 4. IPC Server
        self.ipc_server = IPCServer(command_handler=self._handle_ipc_command)

        # 5. Global Hotkey Manager
        binding = self.config_mgr.get("hotkey.binding", "Ctrl+Alt+V")
        self.hotkey_mgr = HotkeyManager(
            binding=binding,
            on_toggle_callback=self._on_hotkey_triggered,
        )

    def _on_hotkey_triggered(self) -> None:
        """Global hotkey trigger handler dispatched to GTK loop."""
        GLib.idle_add(self.window.toggle)

    def _handle_ipc_command(self, cmd_line: str) -> str:
        """Dispatch commands received over UNIX domain socket."""
        parts = cmd_line.strip().split(maxsplit=1)
        if not parts:
            return "error: empty command"

        action = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if action == "toggle":
            GLib.idle_add(self.window.toggle)
            return "ok: toggled"
        elif action == "show":
            GLib.idle_add(self.window.show_window)
            return "ok: shown"
        elif action == "hide":
            GLib.idle_add(self.window.hide_window)
            return "ok: hidden"
        elif action == "ping":
            return "pong"
        elif action == "stats":
            return json.dumps(self.db.get_stats())
        elif action == "clear":
            count = self.db.clear_history(keep_pinned=True)
            GLib.idle_add(lambda: self.window.perform_search(""))
            return f"ok: cleared {count} unpinned entries"
        elif action == "clear-all":
            count = self.db.clear_history(keep_pinned=False)
            GLib.idle_add(lambda: self.window.perform_search(""))
            return f"ok: cleared all {count} entries"
        elif action == "ingest":
            if arg:
                success = self.daemon.handle_ingest_payload(arg)
                return "ok" if success else "error: ingest failed"
            return "error: missing payload"
        elif action == "pin":
            try:
                entry_id = int(arg)
                new_pinned = self.db.toggle_pinned(entry_id)
                GLib.idle_add(lambda: self.window.perform_search(""))
                return f"ok: pinned={new_pinned}"
            except ValueError:
                return "error: invalid entry id"
        elif action == "copy":
            try:
                entry_id = int(arg)
                entry = self.db.get_entry(entry_id)
                if entry:
                    if self.daemon.backend:
                        self.daemon.backend.set_text(entry.content)
                    return "ok: copied"
                return "error: entry not found"
            except ValueError:
                return "error: invalid entry id"

        return f"error: unknown action '{action}'"

    def run(self) -> None:
        """Start daemon, IPC server, hotkeys, and GTK event loop."""
        # 1. Start IPC Server
        if not self.ipc_server.start():
            logger.error("Could not start IPC server. Another instance may already be running.")
            sys.exit(1)

        # 2. Start Clipboard Listener Daemon
        self.daemon.start()

        # 3. Start Hotkey Listener
        self.hotkey_mgr.start()

        # 4. Hook termination signals
        def handle_signal(sig, frame):
            logger.info("Received signal %s. Shutting down gracefully...", sig)
            GLib.idle_add(Gtk.main_quit)

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        # 5. Run GTK main loop
        try:
            logger.info("ClipMgr application running.")
            Gtk.main()
        finally:
            self.hotkey_mgr.stop()
            self.daemon.stop()
            self.ipc_server.stop()
            logger.info("ClipMgr application terminated cleanly.")


def run_standalone_popup() -> None:
    """Launch popup window standalone if daemon is not running."""
    db = DatabaseManager()
    matcher = FuzzyMatcher()
    config = ConfigManager()
    win = ClipboardWindow(db_mgr=db, matcher=matcher, config_mgr=config)
    win.connect("destroy", Gtk.main_quit)
    win.show_window()
    Gtk.main()


def main() -> None:
    """Parse command line arguments and dispatch execution."""
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description=f"{APP_TITLE} - Advanced, Privacy-First Clipboard Manager for Ubuntu Linux",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # daemon
    subparsers.add_parser("daemon", help="Run background listener daemon and IPC service")

    # toggle / popup
    subparsers.add_parser("toggle", help="Toggle history popup window (instant <15ms IPC)")
    subparsers.add_parser("popup", help="Show history popup window")

    # list
    list_parser = subparsers.add_parser("list", help="Print recent clipboard history")
    list_parser.add_argument("-n", "--limit", type=int, default=15, help="Number of entries to show (default: 15)")
    list_parser.add_argument("-t", "--type", type=str, choices=["text", "code", "url", "path", "color", "json"], help="Filter by content type")
    list_parser.add_argument("-p", "--pinned", action="store_true", help="Show pinned entries only")

    # search
    search_parser = subparsers.add_parser("search", help="Fuzzy search clipboard history from terminal")
    search_parser.add_argument("query", type=str, help="Search string")
    search_parser.add_argument("-n", "--limit", type=int, default=10, help="Max results (default: 10)")

    # copy
    copy_parser = subparsers.add_parser("copy", help="Copy entry back to clipboard by ID")
    copy_parser.add_argument("id", type=int, help="Entry ID")

    # paste
    paste_parser = subparsers.add_parser("paste", help="Paste entry directly into active window by ID")
    paste_parser.add_argument("id", type=int, help="Entry ID")

    # pin
    pin_parser = subparsers.add_parser("pin", help="Toggle pinned status of entry by ID")
    pin_parser.add_argument("id", type=int, help="Entry ID")

    # delete
    del_parser = subparsers.add_parser("delete", help="Delete entry by ID")
    del_parser.add_argument("id", type=int, help="Entry ID")

    # clear
    clear_parser = subparsers.add_parser("clear", help="Clear clipboard history")
    clear_parser.add_argument("--all", action="store_true", help="Clear all entries including pinned")

    # stats
    subparsers.add_parser("stats", help="Display history and storage statistics")

    # export
    export_parser = subparsers.add_parser("export", help="Export clipboard history to JSON backup")
    export_parser.add_argument("-o", "--output", type=str, help="Output JSON file path (default: stdout)")
    export_parser.add_argument("--include-sensitive", action="store_true", help="Include protected sensitive entries")
    export_parser.add_argument("--pinned-only", action="store_true", help="Export only pinned entries")

    # import
    import_parser = subparsers.add_parser("import", help="Import clipboard history from JSON backup")
    import_parser.add_argument("-i", "--input", type=str, required=True, help="Input JSON file path")
    import_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing unpinned history")

    # ingest (internal used by Wayland wl-paste)
    subparsers.add_parser("ingest", help=argparse.SUPPRESS)

    # setup-hotkey
    subparsers.add_parser("setup-hotkey", help="Register GNOME global shortcut (Ctrl+Alt+V)")

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    cmd = args.subcommand or "toggle"

    # 1. Daemon subcommand
    if cmd == "daemon":
        app = ClipMgrApp()
        app.run()

    # 2. Toggle or Popup
    elif cmd in ("toggle", "popup"):
        res = send_ipc_command("toggle")
        if res:
            sys.exit(0)
        # Daemon not running; launch standalone popup
        logger.info("ClipMgr daemon not running. Launching standalone popup window...")
        run_standalone_popup()

    # 3. Ingest (used by Wayland wl-paste --watch)
    elif cmd == "ingest":
        content = sys.stdin.buffer.read()
        if not content:
            sys.exit(0)
        b64 = base64.b64encode(content).decode("ascii")
        res = send_ipc_command(f"ingest {b64}", timeout=1.0)
        if not res:
            # Daemon not running, ingest directly into DB
            db = DatabaseManager()
            daemon = ClipboardDaemon(db_mgr=db)
            daemon.process_incoming_clip(content.decode("utf-8", errors="replace"))

    # 4. List
    elif cmd == "list":
        db = DatabaseManager()
        ctype = ContentType.from_str(args.type) if args.type else None
        entries = db.get_recent_entries(limit=args.limit, content_type=ctype, pinned_only=args.pinned)

        if not entries:
            print("No clipboard history found.")
            return

        print(f"\n{'ID':<5} {'TYPE':<7} {'PIN':<4} {'TIME':<12} {'SIZE':<8} {'CONTENT'}")
        print("-" * 75)
        for e in entries:
            pin_str = "📌" if e.pinned else "  "
            time_str = e.formatted_timestamp()
            size_str = e.formatted_size()
            preview = e.preview.replace("\n", " ")
            if len(preview) > 38:
                preview = preview[:35] + "..."
            print(f"{e.id:<5} {e.content_type.value:<7} {pin_str:<4} {time_str:<12} {size_str:<8} {preview}")
        print()

    # 5. Search
    elif cmd == "search":
        db = DatabaseManager()
        matcher = FuzzyMatcher()
        candidates = db.get_recent_entries(limit=200, include_sensitive=True)
        results = matcher.search(query=args.query, entries=candidates, limit=args.limit)

        if not results:
            print(f"No entries matching '{args.query}'.")
            return

        print(f"\nTop matches for '{args.query}':")
        print(f"{'ID':<5} {'TYPE':<7} {'PIN':<4} {'TIME':<12} {'CONTENT'}")
        print("-" * 65)
        for e in results:
            pin_str = "📌" if e.pinned else "  "
            preview = e.preview.replace("\n", " ")
            if len(preview) > 35:
                preview = preview[:32] + "..."
            print(f"{e.id:<5} {e.content_type.value:<7} {pin_str:<4} {e.formatted_timestamp():<12} {preview}")
        print()

    # 6. Copy
    elif cmd == "copy":
        res = send_ipc_command(f"copy {args.id}")
        if res and "ok" in res:
            print(f"Entry {args.id} copied to clipboard.")
        else:
            db = DatabaseManager()
            entry = db.get_entry(args.id)
            if not entry:
                print(f"Error: Entry {args.id} not found.", file=sys.stderr)
                sys.exit(1)
            cb = Gtk.Clipboard.get(gi.repository.Gdk.SELECTION_CLIPBOARD)
            cb.set_text(entry.content, -1)
            cb.store()
            print(f"Entry {args.id} copied to clipboard.")

    # 7. Paste
    elif cmd == "paste":
        db = DatabaseManager()
        entry = db.get_entry(args.id)
        if not entry:
            print(f"Error: Entry {args.id} not found.", file=sys.stderr)
            sys.exit(1)
        paster = DirectPaster()
        paster.paste(entry)
        print(f"Entry {args.id} pasted into active window.")

    # 8. Pin
    elif cmd == "pin":
        res = send_ipc_command(f"pin {args.id}")
        if res and "ok" in res:
            print(res)
        else:
            db = DatabaseManager()
            new_state = db.toggle_pinned(args.id)
            print(f"Entry {args.id} {'pinned' if new_state else 'unpinned'}.")

    # 9. Delete
    elif cmd == "delete":
        db = DatabaseManager()
        success = db.delete_entry(args.id)
        if success:
            print(f"Entry {args.id} deleted.")
        else:
            print(f"Entry {args.id} not found.", file=sys.stderr)

    # 10. Clear
    elif cmd == "clear":
        action = "clear-all" if args.all else "clear"
        res = send_ipc_command(action)
        if res and "ok" in res:
            print(res)
        else:
            db = DatabaseManager()
            deleted = db.clear_history(keep_pinned=not args.all)
            print(f"Cleared {deleted} history entries.")

    # 11. Stats
    elif cmd == "stats":
        res = send_ipc_command("stats")
        if res and res.startswith("{"):
            stats = json.loads(res)
        else:
            db = DatabaseManager()
            stats = db.get_stats()

        print("\nClipMgr History & Storage Statistics:")
        print("=" * 45)
        print(f"  Total Clips:        {stats.get('total_entries', 0):,}")
        print(f"  Pinned Clips:       {stats.get('pinned_entries', 0):,}")
        print(f"  Sensitive Clips:    {stats.get('sensitive_entries', 0):,}")
        print(f"  Database File:      {stats.get('database_path')}")
        db_kb = stats.get('database_size_bytes', 0) / 1024
        print(f"  Database Size:      {db_kb:.2f} KB")
        print(f"  Encryption Active:  {'Yes' if stats.get('encryption_active') else 'No'}")
        print("\n  Clips by Type:")
        for t, count in stats.get("type_counts", {}).items():
            print(f"    - {t:<8}: {count}")
        print()

    # 12. Export
    elif cmd == "export":
        db = DatabaseManager()
        exported = db.export_all(
            include_sensitive=args.include_sensitive,
            pinned_only=args.pinned_only,
        )
        json_output = json.dumps(exported, indent=2)
        if args.output:
            out_path = Path(args.output).expanduser()
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(json_output)
            print(f"Exported {len(exported)} entries to {out_path}")
        else:
            print(json_output)

    # 13. Import
    elif cmd == "import":
        in_path = Path(args.input).expanduser()
        if not in_path.exists():
            print(f"Error: Input file '{in_path}' does not exist.", file=sys.stderr)
            sys.exit(1)

        with open(in_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            print("Error: Invalid backup file format. Expected a JSON array.", file=sys.stderr)
            sys.exit(1)

        db = DatabaseManager()
        count = db.import_entries(data, merge=not args.overwrite)
        print(f"Successfully imported {count} entries into clipboard history.")

    # 14. Setup hotkey
    elif cmd == "setup-hotkey":
        cfg = ConfigManager()
        binding = cfg.get("hotkey.binding", "Ctrl+Alt+V")
        success, msg = setup_gnome_shortcut(binding=binding)
        if success:
            print(f"[SUCCESS] {msg}")
        else:
            print(f"[INFO] {msg}")


if __name__ == "__main__":
    main()
