"""Rich preview widget with syntax, monospace formatting, and metadata rendering."""

import html
import json
import logging
import os
from pathlib import Path
from typing import Optional

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk, Pango

from clipmgr.detector import mask_sensitive
from clipmgr.models import ClipEntry, ContentType

logger = logging.getLogger(__name__)


class PreviewPane(Gtk.Box):
    """Side/Split preview pane that renders rich, syntax-aware previews of selected entries."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.get_style_context().add_class("preview-pane")
        self.set_size_request(320, -1)

        self._current_entry: Optional[ClipEntry] = None
        self._revealed = False

        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the visual hierarchy of the preview pane."""
        # 1. Header with Metadata
        self.header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.header_box.get_style_context().add_class("preview-header")

        self.type_badge = Gtk.Label()
        self.type_badge.get_style_context().add_class("badge")
        self.header_box.pack_start(self.type_badge, False, False, 0)

        self.meta_label = Gtk.Label(xalign=0)
        self.meta_label.get_style_context().add_class("preview-meta")
        self.meta_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.header_box.pack_start(self.meta_label, True, True, 0)

        self.pack_start(self.header_box, False, False, 0)

        # 2. Color Swatch Container (for color entries)
        self.color_swatch = Gtk.Box()
        self.color_swatch.set_size_request(-1, 32)
        self.color_swatch.get_style_context().add_class("color-swatch")
        self.color_swatch.set_no_show_all(True)
        self.pack_start(self.color_swatch, False, False, 0)

        # 3. Content Scroller with TextView
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scroller.get_style_context().add_class("preview-scroller")

        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_view.get_style_context().add_class("preview-text")
        self.text_view.set_left_margin(10)
        self.text_view.set_right_margin(10)
        self.text_view.set_top_margin(8)
        self.text_view.set_bottom_margin(8)

        self.scroller.add(self.text_view)
        self.pack_start(self.scroller, True, True, 0)

        # 4. Sensitive mask button container
        self.sensitive_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.sensitive_box.set_no_show_all(True)
        self.sensitive_btn = Gtk.Button(label="👁 Reveal Secret")
        self.sensitive_btn.get_style_context().add_class("reveal-btn")
        self.sensitive_btn.connect("clicked", self._on_toggle_reveal)
        self.sensitive_box.pack_start(self.sensitive_btn, True, True, 0)
        self.pack_start(self.sensitive_box, False, False, 0)

        # 5. Footer Stats
        self.footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.footer_box.get_style_context().add_class("preview-footer")

        self.stats_label = Gtk.Label(xalign=0)
        self.stats_label.get_style_context().add_class("preview-stats")
        self.footer_box.pack_start(self.stats_label, True, True, 0)

        self.pack_start(self.footer_box, False, False, 0)

    def set_entry(self, entry: Optional[ClipEntry]) -> None:
        """Update preview pane with the specified entry."""
        self._current_entry = entry
        self._revealed = False

        if not entry:
            self._clear_view()
            return

        # Header Badge & Meta
        self.type_badge.set_text(entry.get_badge_label())
        # Clear old classes
        for cls in ("badge-text", "badge-code", "badge-url", "badge-path", "badge-color", "badge-json", "badge-pinned"):
            self.type_badge.get_style_context().remove_class(cls)
        self.type_badge.get_style_context().add_class(entry.get_badge_css_class())

        app_name = entry.source_app or "System Clipboard"
        self.meta_label.set_text(f"{app_name} • {entry.formatted_timestamp()}")

        # Handle Color Swatch
        if entry.content_type == ContentType.COLOR:
            color_str = entry.content.strip()
            rgba = Gdk.RGBA()
            if rgba.parse(color_str):
                self.color_swatch.override_background_color(
                    Gtk.StateFlags.NORMAL, rgba
                )
                self.color_swatch.show()
            else:
                self.color_swatch.hide()
        else:
            self.color_swatch.hide()

        # Handle Sensitive
        if entry.is_sensitive and not self._revealed:
            self._render_text(mask_sensitive(entry.content), is_code=False)
            self.sensitive_btn.set_label("👁 Reveal Secret")
            self.sensitive_box.show()
        else:
            self.sensitive_box.hide()
            self._render_entry_content(entry)

        # Footer Stats
        line_count = len(entry.content.splitlines())
        char_count = len(entry.content)
        self.stats_label.set_text(f"{char_count} chars • {line_count} lines • {entry.formatted_size()}")

    def _render_entry_content(self, entry: ClipEntry) -> None:
        """Render the entry's content based on type."""
        is_code = entry.content_type in (ContentType.CODE, ContentType.JSON)

        # Style font
        if is_code or entry.content_type == ContentType.FILE_PATH:
            self.text_view.get_style_context().add_class("code-font")
        else:
            self.text_view.get_style_context().remove_class("code-font")

        # Pretty-print JSON if applicable
        display_text = entry.content
        if entry.content_type == ContentType.JSON:
            try:
                parsed = json.loads(entry.content)
                display_text = json.dumps(parsed, indent=2)
            except Exception:
                pass

        self._render_text(display_text, is_code=is_code)

    def _render_text(self, text: str, is_code: bool = False) -> None:
        """Populate the text view buffer."""
        buffer = self.text_view.get_buffer()
        buffer.set_text(text)

    def _on_toggle_reveal(self, btn: Gtk.Button) -> None:
        """Toggle sensitive content masking."""
        if not self._current_entry:
            return

        self._revealed = not self._revealed
        if self._revealed:
            self._render_entry_content(self._current_entry)
            self.sensitive_btn.set_label("🔒 Hide Secret")
        else:
            self._render_text(mask_sensitive(self._current_entry.content), is_code=False)
            self.sensitive_btn.set_label("👁 Reveal Secret")

    def _clear_view(self) -> None:
        """Reset preview pane when no entry is selected."""
        self.type_badge.set_text("")
        self.meta_label.set_text("Select an item to preview")
        self.color_swatch.hide()
        self.sensitive_box.hide()
        self.text_view.get_buffer().set_text("")
        self.stats_label.set_text("")
