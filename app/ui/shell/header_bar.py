"""HeaderBar — top header bar for the Freqtrade GUI shell.

Displays the application icon, name, breadcrumb separator, current page
title, and right-side action buttons (command palette, settings, theme
toggle).  Fixed height of 48 px.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from app.core.utils.app_logger import get_logger
from app.ui.theme import FONT, PALETTE, SPACING

_log = get_logger("ui.header_bar")

_HEADER_HEIGHT = 48


class HeaderBar(QWidget):
    """Top header bar: app name, breadcrumb, command palette button, theme toggle."""

    theme_toggle_requested = Signal()
    command_palette_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dark_mode = True
        self._build_ui()
        _log.debug("HeaderBar initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_page_title(self, title: str) -> None:
        """Update the breadcrumb page title label.

        Args:
            title: The human-readable page name to display.
        """
        self._page_title_label.setText(title)
        _log.debug("HeaderBar page title set to %r", title)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the header bar layout."""
        self.setFixedHeight(_HEADER_HEIGHT)
        self.setStyleSheet(
            f"background-color: {PALETTE['bg_surface']};"
            f"border-bottom: 1px solid {PALETTE['border']};"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING["md"], 0, SPACING["md"], 0)
        layout.setSpacing(SPACING["sm"])

        # App icon
        app_icon = QLabel("🤖")
        app_icon.setAccessibleName("Application icon")
        app_icon.setToolTip("Freqtrade GUI")
        layout.addWidget(app_icon)

        # App name
        app_name = QLabel("Freqtrade GUI")
        app_name.setStyleSheet(
            f"color: {PALETTE['text_primary']};"
            f"font-weight: bold;"
            f"font-size: {FONT['size_base']}px;"
        )
        app_name.setAccessibleName("Application name")
        layout.addWidget(app_name)

        # Breadcrumb separator
        separator = QLabel("›")
        separator.setStyleSheet(f"color: {PALETTE['text_secondary']};")
        separator.setAccessibleName("Breadcrumb separator")
        layout.addWidget(separator)

        # Page title
        self._page_title_label = QLabel("")
        self._page_title_label.setStyleSheet(
            f"color: {PALETTE['text_secondary']};"
            f"font-size: {FONT['size_base']}px;"
        )
        self._page_title_label.setAccessibleName("Current page title")
        layout.addWidget(self._page_title_label)

        # Stretch to push right-side buttons to the right
        layout.addStretch(1)

        # Command palette button
        self._cmd_btn = QPushButton("🔍")
        self._cmd_btn.setFlat(True)
        self._cmd_btn.setToolTip("Command Palette (Ctrl+P)")
        self._cmd_btn.setAccessibleName("Open command palette")
        self._cmd_btn.setFixedSize(32, 32)
        self._cmd_btn.clicked.connect(self.command_palette_requested)
        layout.addWidget(self._cmd_btn)

        # Settings button
        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setFlat(True)
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.setAccessibleName("Open settings")
        self._settings_btn.setFixedSize(32, 32)
        self._settings_btn.clicked.connect(self.settings_requested)
        layout.addWidget(self._settings_btn)

        # Theme toggle button
        self._theme_btn = QPushButton("☀")
        self._theme_btn.setFlat(True)
        self._theme_btn.setToolTip("Toggle theme (dark/light)")
        self._theme_btn.setAccessibleName("Toggle theme")
        self._theme_btn.setFixedSize(32, 32)
        self._theme_btn.clicked.connect(self._on_theme_toggle)
        layout.addWidget(self._theme_btn)

    def _on_theme_toggle(self) -> None:
        """Toggle the theme icon and emit the theme_toggle_requested signal."""
        self._dark_mode = not self._dark_mode
        self._theme_btn.setText("☀" if self._dark_mode else "🌙")
        self.theme_toggle_requested.emit()
        _log.debug("Theme toggle requested; dark_mode=%s", self._dark_mode)
