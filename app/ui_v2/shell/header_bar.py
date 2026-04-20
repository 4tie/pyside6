"""HeaderBar — top application bar for the v2 UI shell.

Displays the app icon, app name, breadcrumb separator, and the current page
title.  Provides quick-action buttons for the command palette, settings, and
theme toggling.

The theme toggle cycles Dark → Light → Dark.  It emits ``theme_changed``
so ``ModernMainWindow`` can apply the new stylesheet.

Requirements: 2.3, 9.1, 18.1, 18.5
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from app.core.utils.app_logger import get_logger
from app.ui_v2.theme import (
    FONT,
    PALETTE,
    SPACING,
    ThemeMode,
    _LIGHT_PALETTE,
    build_stylesheet,
    build_v2_additions,
)

_log = get_logger("ui_v2.shell.header_bar")

_HEADER_HEIGHT = 48


class HeaderBar(QWidget):
    """Fixed-height top bar with breadcrumb and quick-action buttons.

    Signals:
        theme_changed(ThemeMode): Emitted when the user toggles the theme.
            ``ModernMainWindow`` should connect this to apply the stylesheet.
        command_palette_requested(): Emitted when the 🔍 button is clicked.
        settings_requested(): Emitted when the ⚙ button is clicked.
    """

    theme_changed = Signal(object)  # ThemeMode
    command_palette_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._current_mode: ThemeMode = ThemeMode.DARK

        self.setFixedHeight(_HEADER_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._build_ui()

        _log.debug("HeaderBar initialised")

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the header layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING["md"], 0, SPACING["md"], 0)
        layout.setSpacing(SPACING["sm"])

        # App icon (emoji placeholder — replace with QIcon if available)
        app_icon_lbl = QLabel("📈")
        app_icon_lbl.setFixedWidth(24)
        app_icon_lbl.setStyleSheet("background: transparent; font-size: 18px;")
        layout.addWidget(app_icon_lbl)

        # App name
        app_name_lbl = QLabel("Freqtrade GUI")
        app_name_lbl.setStyleSheet(
            f"background: transparent; font-weight: 600; font-size: {FONT['size_base']}px;"
        )
        layout.addWidget(app_name_lbl)

        # Breadcrumb separator
        sep_lbl = QLabel("›")
        sep_lbl.setStyleSheet(
            f"background: transparent; color: {PALETTE['text_secondary']}; font-size: {FONT['size_base']}px;"
        )
        layout.addWidget(sep_lbl)

        # Page title label (updated by set_page_title)
        self._page_title_lbl = QLabel("Dashboard")
        self._page_title_lbl.setObjectName("page_title")
        self._page_title_lbl.setStyleSheet(
            f"background: transparent; font-size: {FONT['size_base']}px;"
        )
        layout.addWidget(self._page_title_lbl)

        # Spacer pushes action buttons to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer.setStyleSheet("background: transparent;")
        layout.addWidget(spacer)

        # Command palette button
        self._cmd_btn = QPushButton("🔍")
        self._cmd_btn.setObjectName("secondary")
        self._cmd_btn.setFixedSize(32, 32)
        self._cmd_btn.setToolTip("Command Palette (Ctrl+P)")
        self._cmd_btn.setAccessibleName("Command Palette")
        self._cmd_btn.clicked.connect(self.command_palette_requested)
        layout.addWidget(self._cmd_btn)

        # Settings shortcut button
        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setObjectName("secondary")
        self._settings_btn.setFixedSize(32, 32)
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.setAccessibleName("Settings")
        self._settings_btn.clicked.connect(self.settings_requested)
        layout.addWidget(self._settings_btn)

        # Theme toggle button
        self._theme_btn = QPushButton("🌙 Dark")
        self._theme_btn.setObjectName("secondary")
        self._theme_btn.setFixedHeight(32)
        self._theme_btn.setToolTip("Toggle theme (Dark / Light)")
        self._theme_btn.setAccessibleName("Toggle theme")
        self._theme_btn.clicked.connect(self._on_theme_toggle)
        layout.addWidget(self._theme_btn)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_page_title(self, title: str) -> None:
        """Update the breadcrumb page title label.

        Args:
            title: Human-readable page name to display.
        """
        self._page_title_lbl.setText(title)
        _log.debug("HeaderBar page title set to %r", title)

    def current_theme_mode(self) -> ThemeMode:
        """Return the currently active ``ThemeMode``."""
        return self._current_mode

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _on_theme_toggle(self) -> None:
        """Cycle the theme Dark → Light → Dark and apply the stylesheet."""
        if self._current_mode == ThemeMode.DARK:
            self._current_mode = ThemeMode.LIGHT
            self._theme_btn.setText("☀ Light")
            palette = _LIGHT_PALETTE
        else:
            self._current_mode = ThemeMode.DARK
            self._theme_btn.setText("🌙 Dark")
            palette = PALETTE

        # Build and apply the combined stylesheet
        qss = build_stylesheet(self._current_mode) + build_v2_additions(
            palette, SPACING, FONT
        )
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss)

        self.theme_changed.emit(self._current_mode)
        _log.info("Theme toggled to %s", self._current_mode.value)
