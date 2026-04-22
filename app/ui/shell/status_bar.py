"""AppStatusBar — bottom status bar for the Freqtrade GUI shell.

Displays process status messages with a timestamp.  Messages are
colour-coded by severity level and auto-clear after 10 seconds.
Fixed height of 28 px.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from app.core.utils.app_logger import get_logger
from app.ui.theme import FONT, PALETTE, SPACING

_log = get_logger("ui.status_bar")

_STATUS_HEIGHT = 28
_AUTO_CLEAR_MS = 10_000

# Mapping from level name to palette colour key
_LEVEL_COLORS: dict[str, str] = {
    "info":    PALETTE["text_secondary"],
    "success": PALETTE["success"],
    "error":   PALETTE["danger"],
    "warning": PALETTE["warning"],
}

# Level icons
_LEVEL_ICONS: dict[str, str] = {
    "info":    "ℹ",
    "success": "✔",
    "error":   "✖",
    "warning": "⚠",
}


class AppStatusBar(QWidget):
    """Bottom status bar showing process status messages."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._clear)
        self._build_ui()
        _log.debug("AppStatusBar initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_status(self, message: str, level: str = "info") -> None:
        """Show *message* with a timestamp.  Auto-clears after 10 seconds.

        Args:
            message: The status text to display.
            level:   Severity level — one of ``"info"``, ``"success"``,
                     ``"error"``, or ``"warning"``.  Unknown levels fall
                     back to ``"info"``.
        """
        if level not in _LEVEL_COLORS:
            _log.warning("Unknown status level %r — falling back to 'info'", level)
            level = "info"

        color = _LEVEL_COLORS[level]
        icon = _LEVEL_ICONS[level]
        timestamp = datetime.now().strftime("%H:%M:%S")

        self._icon_label.setText(icon)
        self._icon_label.setStyleSheet(f"color: {color}; font-size: {FONT['size_sm']}px;")

        self._message_label.setText(message)
        self._message_label.setStyleSheet(f"color: {color}; font-size: {FONT['size_sm']}px;")

        self._timestamp_label.setText(timestamp)

        # Restart the auto-clear timer
        self._timer.start(_AUTO_CLEAR_MS)
        _log.debug("Status set [%s]: %s", level, message)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the status bar layout."""
        self.setFixedHeight(_STATUS_HEIGHT)
        self.setStyleSheet(
            f"background-color: {PALETTE['bg_surface']};"
            f"border-top: 1px solid {PALETTE['border']};"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING["sm"], 0, SPACING["sm"], 0)
        layout.setSpacing(SPACING["xs"])

        # Status icon
        self._icon_label = QLabel("")
        self._icon_label.setStyleSheet(
            f"color: {PALETTE['text_secondary']}; font-size: {FONT['size_sm']}px;"
        )
        self._icon_label.setAccessibleName("Status icon")
        layout.addWidget(self._icon_label)

        # Status message
        self._message_label = QLabel("")
        self._message_label.setStyleSheet(
            f"color: {PALETTE['text_secondary']}; font-size: {FONT['size_sm']}px;"
        )
        self._message_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._message_label.setAccessibleName("Status message")
        layout.addWidget(self._message_label, 1)

        # Timestamp (right-aligned)
        self._timestamp_label = QLabel("")
        self._timestamp_label.setStyleSheet(
            f"color: {PALETTE['text_secondary']}; font-size: {FONT['size_sm']}px;"
        )
        self._timestamp_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._timestamp_label.setAccessibleName("Status timestamp")
        layout.addWidget(self._timestamp_label)

    def _clear(self) -> None:
        """Clear the status message after the auto-clear timer fires."""
        self._icon_label.setText("")
        self._message_label.setText("")
        self._timestamp_label.setText("")
        _log.debug("Status bar cleared")
