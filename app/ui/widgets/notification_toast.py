"""notification_toast.py — Transient notification overlay for the Freqtrade GUI.

Displays a brief message in the bottom-right corner of the parent widget
(or screen if no parent) and auto-hides after a configurable duration.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from app.core.utils.app_logger import get_logger
from app.ui.theme import FONT, PALETTE, SPACING

_log = get_logger("ui.notification_toast")

# Mapping from level name to palette colour key
_LEVEL_COLOURS: dict[str, str] = {
    "info":    PALETTE["accent"],
    "success": PALETTE["success"],
    "error":   PALETTE["danger"],
    "warning": PALETTE["warning"],
}

_TOAST_WIDTH = 320
_TOAST_MARGIN = 16  # pixels from the bottom-right edge


class NotificationToast(QWidget):
    """Transient notification overlay shown in the bottom-right corner of the parent.

    Args:
        parent: Optional parent widget used to position the toast.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(
            parent,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the toast layout: message label + close button."""
        self.setFixedWidth(_TOAST_WIDTH)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            SPACING["md"], SPACING["sm"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["sm"])

        self._message_label = QLabel("")
        self._message_label.setWordWrap(True)
        self._message_label.setStyleSheet(
            f"color: {PALETTE['text_primary']}; font-size: {FONT['size_base']}px;"
        )
        layout.addWidget(self._message_label, stretch=1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setFlat(True)
        close_btn.setStyleSheet(
            f"color: {PALETTE['text_secondary']}; border: none; font-size: 10px;"
        )
        close_btn.setToolTip("Dismiss notification")
        close_btn.setAccessibleName("Dismiss notification")
        close_btn.clicked.connect(self._dismiss)
        layout.addWidget(close_btn)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dismiss(self) -> None:
        """Stop the timer and hide the toast."""
        self._timer.stop()
        self.hide()

    def _reposition(self) -> None:
        """Move the toast to the bottom-right of the parent or screen."""
        self.adjustSize()
        h = self.sizeHint().height()
        w = _TOAST_WIDTH

        parent = self.parent()
        if parent is not None and isinstance(parent, QWidget):
            geo = parent.geometry()
            # Map parent's bottom-right to global coordinates
            global_br = parent.mapToGlobal(
                __import__("PySide6.QtCore", fromlist=["QPoint"]).QPoint(
                    geo.width(), geo.height()
                )
            )
            x = global_br.x() - w - _TOAST_MARGIN
            y = global_br.y() - h - _TOAST_MARGIN
        else:
            screen = QApplication.primaryScreen()
            if screen is not None:
                rect = screen.availableGeometry()
                x = rect.right() - w - _TOAST_MARGIN
                y = rect.bottom() - h - _TOAST_MARGIN
            else:
                x, y = 100, 100

        self.move(x, y)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_message(
        self,
        message: str,
        level: str = "info",
        duration_ms: int = 3000,
    ) -> None:
        """Show a toast notification.

        Args:
            message: The text to display.
            level: Severity level — one of "info", "success", "error", "warning".
            duration_ms: How long (ms) to show the toast before auto-hiding.
        """
        if level not in _LEVEL_COLOURS:
            _log.warning("Unknown toast level %r — falling back to 'info'", level)
            level = "info"

        self.setObjectName(f"toast_{level}")

        accent_colour = _LEVEL_COLOURS[level]
        self.setStyleSheet(
            f"QWidget#{self.objectName()} {{"
            f"  background-color: {PALETTE['bg_elevated']};"
            f"  border: 1px solid {PALETTE['border']};"
            f"  border-left: 4px solid {accent_colour};"
            f"  border-radius: 6px;"
            f"}}"
        )

        self._message_label.setText(message)

        self._reposition()
        self.show()
        self.raise_()

        self._timer.stop()
        self._timer.start(duration_ms)

        _log.debug("Toast shown: level=%r message=%r duration=%dms", level, message, duration_ms)
