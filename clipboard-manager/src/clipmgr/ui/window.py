"""GTK3 modern popup window for ClipFlow / ClipMgr clipboard history browser."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango

from clipmgr.config import ConfigManager
from clipmgr.constants import APP_NAME, APP_TITLE
from clipmgr.daemon.backends.base import ClipboardBackend
from clipmgr.daemon.window_detector import WindowDetector
from clipmgr.models import ClipEntry, ContentType
from clipmgr.search.matcher import FuzzyMatcher
from clipmgr.storage.database import DatabaseManager
from clipmgr.ui.paster import DirectPaster
from clipmgr.ui.preview import PreviewPane

logger = logging.getLogger(__name__)


class ClipboardWindow(Gtk.Window):
    """Main clipboard history popup window styled like Raycast / Alfred."""

    def __init__(
        self,
        db_mgr: DatabaseManager,
        matcher: FuzzyMatcher,
        backend: Optional[ClipboardBackend] = None,
        config_mgr: Optional[ConfigManager] = None,
    ) -> None:
        super().__init__(type=Gtk.WindowType.TOPLEVEL)

        self.db = db_mgr
        self.matcher = matcher
        self.backend = backend
        self.config_mgr = config_mgr or ConfigManager()
        self.window_detector = WindowDetector()
        self.paster = DirectPaster(backend=self.backend)

        self.current_results: List[ClipEntry] = []
        self._active_filter_type: Optional[ContentType] = None
        self._filter_pinned_only = False
        self._target_window_id: Optional[str] = None
        self._target_app_name: Optional[str] = None
        self._is_visible = False

        self._init_window_settings()
        self._load_css()
        self._build_ui()
        self._connect_signals()

        # Initial load
        self.perform_search("")

    def _init_window_settings(self) -> None:
        """Configure GTK window attributes."""
        self.set_title(APP_TITLE)
        self.set_role("clipmgr-popup")
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_resizable(False)

        width = int(self.config_mgr.get("ui.width", 780))
        self.set_default_size(width, -1)

        # Enable RGBA transparency if compositor allows
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        self.get_style_context().add_class("clipmgr-window")

    def _load_css(self) -> None:
        """Load external stylesheet."""
        css_file = Path(__file__).parent / "style.css"
        if css_file.exists():
            provider = Gtk.CssProvider()
            try:
                provider.load_from_path(str(css_file))
                screen = Gdk.Screen.get_default()
                if screen:
                    Gtk.StyleContext.add_provider_for_screen(
                        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )
            except Exception as e:
                logger.warning("Failed to load CSS: %s", e)

    def _build_ui(self) -> None:
        """Construct the visual components of the popup window."""
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.main_box.get_style_context().add_class("main-container")
        self.add(self.main_box)

        # 1. Search Box
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        search_box.get_style_context().add_class("search-box")

        search_icon = Gtk.Image.new_from_icon_name("edit-find-symbolic", Gtk.IconSize.MENU)
        search_icon.get_style_context().add_class("search-icon")
        search_box.pack_start(search_icon, False, False, 0)

        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Search clipboard history... (Esc to close)")
        self.search_entry.set_has_frame(False)
        self.search_entry.get_style_context().add_class("search-entry")
        search_box.pack_start(self.search_entry, True, True, 0)

        self.main_box.pack_start(search_box, False, False, 0)

        # 2. Filter Bar (All, Pinned, Code, URL, Text, Path)
        self.filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.filter_box.get_style_context().add_class("filter-bar")

        self.filter_buttons: Dict[str, Gtk.Button] = {}
        filter_specs = [
            ("all", "All (Alt+1)"),
            ("pinned", "Pinned (Alt+2)"),
            ("code", "Code (Alt+3)"),
            ("url", "URL (Alt+4)"),
            ("text", "Text (Alt+5)"),
            ("path", "Path (Alt+6)"),
        ]

        for key, label in filter_specs:
            btn = Gtk.Button(label=label)
            btn.get_style_context().add_class("filter-btn")
            btn.connect("clicked", self._on_filter_clicked, key)
            self.filter_buttons[key] = btn
            self.filter_box.pack_start(btn, False, False, 0)

        self._update_filter_button_styles("all")
        self.main_box.pack_start(self.filter_box, False, False, 0)

        # 3. Content Split (List on Left, Rich Preview on Right)
        self.content_paned = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Scroller for List
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.get_style_context().add_class("results-scroller")
        self.scroller.set_propagate_natural_height(True)
        max_height = int(self.config_mgr.get("ui.max_height", 480))
        self.scroller.set_max_content_height(max_height)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.get_style_context().add_class("results-list")
        self.scroller.add(self.list_box)

        self.content_paned.pack_start(self.scroller, True, True, 0)

        # Rich Preview Pane
        self.preview_pane = PreviewPane()
        self.content_paned.pack_start(self.preview_pane, False, False, 0)

        self.main_box.pack_start(self.content_paned, True, True, 0)

        # 4. Footer Bar
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        footer.get_style_context().add_class("footer-bar")

        self.count_label = Gtk.Label(label="0 clips")
        self.count_label.get_style_context().add_class("footer-text")
        footer.pack_start(self.count_label, False, False, 0)

        hint_label = Gtk.Label()
        hint_label.set_markup(
            "<span weight='bold' foreground='#89b4fa'>↵</span> <span foreground='#a6adc8'>Copy</span>   "
            "<span weight='bold' foreground='#89b4fa'>Shift+↵</span> <span foreground='#a6adc8'>Paste</span>   "
            "<span weight='bold' foreground='#89b4fa'>Ctrl+P</span> <span foreground='#a6adc8'>Pin</span>   "
            "<span weight='bold' foreground='#89b4fa'>Del</span> <span foreground='#a6adc8'>Remove</span>   "
            "<span weight='bold' foreground='#89b4fa'>Esc</span> <span foreground='#a6adc8'>Dismiss</span>"
        )
        footer.pack_end(hint_label, False, False, 0)

        self.main_box.pack_start(footer, False, False, 0)

    def _connect_signals(self) -> None:
        """Connect GTK event handlers."""
        self.search_entry.connect("changed", self._on_search_changed)
        self.search_entry.connect("key-press-event", self._on_key_press)
        self.connect("key-press-event", self._on_key_press)
        self.connect("focus-out-event", self._on_focus_out)
        self.list_box.connect("row-selected", self._on_row_selected)
        self.list_box.connect("row-activated", self._on_row_activated)

    def reposition_window(self) -> None:
        """Center window horizontally and 18% down from top of active screen."""
        screen = self.get_screen()
        display = screen.get_display()
        pointer = display.get_default_seat().get_pointer()

        if pointer:
            _, x_root, y_root = pointer.get_position()
            monitor = display.get_monitor_at_point(x_root, y_root)
        else:
            monitor = display.get_primary_monitor() or display.get_monitor(0)

        if monitor:
            geom = monitor.get_geometry()
            width = int(self.config_mgr.get("ui.width", 780))
            pos_x = geom.x + (geom.width - width) // 2
            pos_y = geom.y + int(geom.height * 0.18)
            self.move(pos_x, pos_y)
        else:
            self.set_position(Gtk.WindowPosition.CENTER)

    def _on_filter_clicked(self, btn: Gtk.Button, key: str) -> None:
        """Handle filter tab clicks."""
        self._apply_filter_key(key)

    def _apply_filter_key(self, key: str) -> None:
        """Apply a filter preset by key ('all', 'pinned', 'code', etc.)."""
        self._update_filter_button_styles(key)

        if key == "all":
            self._active_filter_type = None
            self._filter_pinned_only = False
        elif key == "pinned":
            self._active_filter_type = None
            self._filter_pinned_only = True
        else:
            self._active_filter_type = ContentType.from_str(key)
            self._filter_pinned_only = False

        self.perform_search(self.search_entry.get_text())

    def _update_filter_button_styles(self, active_key: str) -> None:
        """Highlight the active filter button."""
        for k, btn in self.filter_buttons.items():
            ctx = btn.get_style_context()
            if k == active_key:
                ctx.add_class("active")
            else:
                ctx.remove_class("active")

    def _on_search_changed(self, entry: Gtk.Entry) -> None:
        """Live search query handler."""
        self.perform_search(entry.get_text())

    def perform_search(self, query: str) -> None:
        """Filter database entries and update UI list."""
        max_results = int(self.config_mgr.get("ui.max_results", 25))

        # Fetch candidate entries from database (up to 200 for fuzzy ranking)
        candidates = self.db.get_recent_entries(
            limit=200,
            content_type=self._active_filter_type,
            pinned_only=self._filter_pinned_only,
            include_sensitive=True,
        )

        self.current_results = self.matcher.search(
            query=query,
            entries=candidates,
            limit=max_results,
            content_type=self._active_filter_type,
            pinned_only=self._filter_pinned_only,
            include_sensitive=False,  # exclude protected secrets from search results by default
        )

        # Clear existing rows
        for child in self.list_box.get_children():
            self.list_box.remove(child)

        # Populate rows
        for item in self.current_results:
            row = self._create_row_widget(item)
            self.list_box.add(row)

        self.list_box.show_all()

        # Select first result if available
        first_row = self.list_box.get_row_at_index(0)
        if first_row:
            self.list_box.select_row(first_row)
            self.preview_pane.set_entry(first_row._item_data)
        else:
            self.preview_pane.set_entry(None)

        # Update count
        count = len(self.current_results)
        self.count_label.set_text(f"{count} {'clip' if count == 1 else 'clips'}")

    def _create_row_widget(self, item: ClipEntry) -> Gtk.ListBoxRow:
        """Build a sleek row representing a ClipEntry."""
        row = Gtk.ListBoxRow()
        row.get_style_context().add_class("result-row")
        row._item_data = item

        h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        h_box.set_margin_top(4)
        h_box.set_margin_bottom(4)
        h_box.set_margin_start(6)
        h_box.set_margin_end(6)

        # Pin Indicator
        if item.pinned:
            pin_icon = Gtk.Label(label="📌")
            pin_icon.get_style_context().add_class("item-pin-icon")
            h_box.pack_start(pin_icon, False, False, 0)

        # Type Icon
        icon_name = self._get_icon_for_type(item.content_type)
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        icon.get_style_context().add_class("item-type-icon")
        h_box.pack_start(icon, False, False, 0)

        # Text labels container
        text_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        title_lbl = Gtk.Label(xalign=0)
        title_lbl.set_text(item.get_display_title())
        title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        title_lbl.get_style_context().add_class("item-title")
        text_vbox.pack_start(title_lbl, False, False, 0)

        snippet_lbl = Gtk.Label(xalign=0)
        snippet_lbl.set_text(item.preview)
        snippet_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        snippet_lbl.get_style_context().add_class("item-snippet")
        text_vbox.pack_start(snippet_lbl, False, False, 0)

        meta_lbl = Gtk.Label(xalign=0)
        meta_lbl.set_text(item.get_subtitle())
        meta_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        meta_lbl.get_style_context().add_class("item-meta")
        text_vbox.pack_start(meta_lbl, False, False, 0)

        h_box.pack_start(text_vbox, True, True, 0)

        # Badge pill
        badge_lbl = Gtk.Label()
        badge_lbl.set_text(item.get_badge_label())
        badge_lbl.get_style_context().add_class("badge")
        badge_lbl.get_style_context().add_class(item.get_badge_css_class())
        h_box.pack_end(badge_lbl, False, False, 0)

        row.add(h_box)
        return row

    def _get_icon_for_type(self, ctype: ContentType) -> str:
        """Map ContentType to standard FreeDesktop icon name."""
        mapping = {
            ContentType.CODE: "text-x-script",
            ContentType.URL: "web-browser",
            ContentType.FILE_PATH: "folder",
            ContentType.COLOR: "color-picker",
            ContentType.JSON: "application-json",
            ContentType.IMAGE: "image-x-generic",
            ContentType.TEXT: "edit-paste",
        }
        return mapping.get(ctype, "edit-paste")

    def _on_row_selected(self, list_box: Gtk.ListBox, row: Optional[Gtk.ListBoxRow]) -> None:
        """Update preview pane when selection changes."""
        if row and hasattr(row, "_item_data"):
            self.preview_pane.set_entry(row._item_data)

    def _on_row_activated(self, list_box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        """Handle row activation (Enter key or double click)."""
        if row and hasattr(row, "_item_data"):
            self._copy_entry(row._item_data)
            self.hide_window()

    def _on_key_press(self, widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        """Handle keyboard shortcuts."""
        keyval = event.keyval
        state = event.state

        # Navigation: Down / Ctrl+N / Ctrl+J
        if keyval in (Gdk.KEY_Down, Gdk.KEY_KP_Down) or (
            (state & Gdk.ModifierType.CONTROL_MASK) and keyval in (Gdk.KEY_n, Gdk.KEY_j)
        ):
            self._move_selection(1)
            return True

        # Navigation: Up / Ctrl+P (when not modifier-only) / Ctrl+K
        elif keyval in (Gdk.KEY_Up, Gdk.KEY_KP_Up) or (
            (state & Gdk.ModifierType.CONTROL_MASK) and keyval == Gdk.KEY_k
        ):
            self._move_selection(-1)
            return True

        # Shift+Enter: Direct Paste into target window
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and (state & Gdk.ModifierType.SHIFT_MASK):
            self._paste_selected_item()
            return True

        # Enter: Copy to clipboard and close
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._copy_selected_item()
            return True

        # Ctrl+P: Toggle Pin on selected item
        elif (state & Gdk.ModifierType.CONTROL_MASK) and keyval == Gdk.KEY_p:
            self._toggle_pin_selected()
            return True

        # Delete or Ctrl+D: Remove item
        elif keyval in (Gdk.KEY_Delete, Gdk.KEY_KP_Delete) or (
            (state & Gdk.ModifierType.CONTROL_MASK) and keyval == Gdk.KEY_d
        ):
            self._delete_selected_item()
            return True

        # Filter shortcuts: Alt+1 to Alt+6
        elif state & Gdk.ModifierType.MOD1_MASK:  # Alt key
            key_map = {
                Gdk.KEY_1: "all",
                Gdk.KEY_2: "pinned",
                Gdk.KEY_3: "code",
                Gdk.KEY_4: "url",
                Gdk.KEY_5: "text",
                Gdk.KEY_6: "path",
            }
            if keyval in key_map:
                self._apply_filter_key(key_map[keyval])
                return True

        # Escape: Dismiss
        elif keyval == Gdk.KEY_Escape:
            self.hide_window()
            return True

        return False

    def _move_selection(self, delta: int) -> None:
        """Move list row selection by delta (+1 or -1)."""
        selected_row = self.list_box.get_selected_row()
        if not selected_row:
            target_idx = 0
        else:
            curr_idx = selected_row.get_index()
            target_idx = max(0, min(len(self.current_results) - 1, curr_idx + delta))

        target_row = self.list_box.get_row_at_index(target_idx)
        if target_row:
            self.list_box.select_row(target_row)
            adj = self.scroller.get_vadjustment()
            if adj:
                row_alloc = target_row.get_allocation()
                adj.clamp_page(row_alloc.y, row_alloc.y + row_alloc.height)

    def _copy_selected_item(self) -> None:
        """Copy selected entry to clipboard."""
        selected_row = self.list_box.get_selected_row()
        if selected_row and hasattr(selected_row, "_item_data"):
            self._copy_entry(selected_row._item_data)
            self.hide_window()

    def _copy_entry(self, entry: ClipEntry) -> None:
        """Set entry content to system clipboard."""
        if self.backend:
            self.backend.set_text(entry.content)
        else:
            # Fallback direct GTK clipboard
            cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            cb.set_text(entry.content, -1)
            cb.store()

    def _paste_selected_item(self) -> None:
        """Directly paste selected entry into previous active window."""
        selected_row = self.list_box.get_selected_row()
        if not selected_row or not hasattr(selected_row, "_item_data"):
            return

        entry: ClipEntry = selected_row._item_data
        target_win = self._target_window_id
        target_app = self._target_app_name

        # Hide window immediately before simulating paste
        self.hide_window()

        # Execute paste via DirectPaster
        GLib.idle_add(lambda: self.paster.paste(entry, target_win, target_app))

    def _toggle_pin_selected(self) -> None:
        """Toggle pinned status for selected entry."""
        selected_row = self.list_box.get_selected_row()
        if not selected_row or not hasattr(selected_row, "_item_data"):
            return

        entry: ClipEntry = selected_row._item_data
        if entry.id is not None:
            new_state = self.db.toggle_pinned(entry.id)
            entry.pinned = new_state
            # Refresh view preserving search
            self.perform_search(self.search_entry.get_text())

    def _delete_selected_item(self) -> None:
        """Delete selected entry from database."""
        selected_row = self.list_box.get_selected_row()
        if not selected_row or not hasattr(selected_row, "_item_data"):
            return

        entry: ClipEntry = selected_row._item_data
        if entry.id is not None:
            self.db.delete_entry(entry.id)
            self.perform_search(self.search_entry.get_text())

    def _on_focus_out(self, widget: Gtk.Widget, event: Gdk.EventFocus) -> bool:
        """Auto-hide window when focus is lost."""
        if self.config_mgr.get("ui.hide_on_focus_lost", True):
            self.hide_window()
        return False

    def show_window(self) -> None:
        """Present popup window and capture previous active window target."""
        # Capture current active window ID BEFORE we take focus
        win_info = self.window_detector.get_active_window_info()
        self._target_window_id = win_info.get("window_id")
        self._target_app_name = win_info.get("app_name")

        self.reposition_window()
        self.perform_search("")
        self.show_all()
        self.present()
        self.search_entry.grab_focus()
        self.search_entry.select_region(0, -1)
        self._is_visible = True

    def hide_window(self) -> None:
        """Hide window and reset query."""
        self.hide()
        self.search_entry.set_text("")
        self._is_visible = False

    def toggle(self) -> None:
        """Toggle window between visible and hidden states."""
        if self._is_visible:
            self.hide_window()
        else:
            self.show_window()
