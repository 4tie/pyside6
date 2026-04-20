"""AppStatusBar — custom status bar widget for the v2 UI shell.

Replaces the default ``QStatusBar`` with a plain ``QWidget`` that shows
process status messages with a timestamp.  Messages auto-clear after 10
seconds via ``QTimer``.

Requirements: 3.2, 16.2
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

_log = get_logger("ui_v2.shell.status_bar")

_AUTO_CLEAR_MS = 10_000  # 10 seconds

# Colour map for each level (inline style fallback — QSS can override)
_LEVEL_COLOURS: dict[str, str] = {
    "info":    "#d4d4d4",
    "success": "#4ec9a0",
    "warning": "#ce9178",
    "error":   "#f44747",
}


class AppStatusBar(QWidget):
    """Thin status bar that displays timestamped process messages.

    Usage::

        status_bar = AppStatusBar()
        status_bar.set_status("Backtest started", level="info")
        status_bar.set_status("Run failed", level="error")

    Messages are cleared automatically after 10 seconds.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setFixedHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._build_ui()

        # Auto-clear timer
        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.setInterval(_AUTO_CLEAR_MS)
        self._clear_timer.timeout.connect(self._clear_message)

        _log.debug("AppStatusBar initialised")

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the status bar layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        # Timestamp label
        self._ts_lbl = QLabel("")
        self._ts_lbl.setFixedWidth(70)
        self._ts_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._ts_lbl.setStyleSheet("color: #9d9d9d; font-size: 11px; background: transparent;")
        layout.addWidget(self._ts_lbl)

        # Message label
        self._msg_lbl = QLabel("")
        self._msg_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._msg_lbl.setStyleSheet("background: transparent; font-size: 12px;")
        layout.addWidget(self._msg_lbl)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_status(self, message: str, level: str = "info") -> None:
        """Display a status message with a timestamp.

        The message is automatically cleared after 10 seconds.

        Args:
            message: Human-readable status text.
            level:   Severity level — one of ``"info"``, ``"success"``,
                     ``"warning"``, ``"error"``.  Controls text colour.
        """
        colour = _LEVEL_COLOURS.get(level, _LEVEL_COLOURS["info"])
        ts = datetime.now().strftime("%H:%M:%S")

        self._ts_lbl.setText(ts)
        self._msg_lbl.setText(message)
        self._msg_lbl.setStyleSheet(
            f"background: transparent; font-size: 12px; color: {colour};"
        )

        # Restart the auto-clear timer
        self._clear_timer.start()

        _log.debug("AppStatusBar status [%s]: %s", level, message)

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _clear_message(self) -> None:
        """Clear the displayed message after the auto-clear timeout."""
        self._ts_lbl.setText("")
        self._msg_lbl.setText("")
        self._msg_lbl.setStyleSheet("background: transparent; font-size: 12px;")
        _log.debug("AppStatusBar message cleared")
