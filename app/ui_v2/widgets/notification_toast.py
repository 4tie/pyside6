"""NotificationToast widget for the v2 UI layer.

A transient overlay notification shown in the bottom-right corner of its
parent widget.  Auto-hides after a configurable duration via ``QTimer``.

Requirements: 7.3, 16.2
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from app.core.utils.app_logger import get_logger

_log = get_logger("ui_v2.notification_toast")

_VALID_LEVELS = frozenset({"info", "success", "error", "warning"})
_LEVEL_ICONS = {
    "info": "ℹ",
    "success": "✓",
    "error": "✗",
    "warning": "⚠",
}
_MARGIN = 16  # px from parent edges


class NotificationToast(QWidget):
    """Transient notification shown in the bottom-right corner.

    Attach to a parent widget so that ``move()`` positions it correctly.

    Args:
        parent: The parent widget over which the toast is overlaid.

    Usage::

        toast = NotificationToast(parent=main_window)
        toast.show_message("Backtest complete!", level="success")
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Frameless, always-on-top overlay
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        self._build_ui()
        self.hide()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the toast layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self._icon_label = QLabel()
        layout.addWidget(self._icon_label)

        self._message_label = QLabel()
        self._message_label.setWordWrap(True)
        layout.addWidget(self._message_label, stretch=1)

        close_btn = QPushButton("✕")
        close_btn.setFlat(True)
        close_btn.setFixedSize(20, 20)
        close_btn.setAccessibleName("Dismiss notification")
        close_btn.clicked.connect(self._dismiss)
        layout.addWidget(close_btn)

        self.setMinimumWidth(260)
        self.setMaximumWidth(420)

    def _dismiss(self) -> None:
        """Stop the timer and hide immediately."""
        self._timer.stop()
        self.hide()

    def _reposition(self) -> None:
        """Move the toast to the bottom-right of the parent widget."""
        parent = self.parent()
        if parent is None:
            return
        self.adjustSize()
        parent_rect = parent.rect()
        x = parent_rect.right() - self.width() - _MARGIN
        y = parent_rect.bottom() - self.height() - _MARGIN
        # Map to global if parent is a QWidget
        try:
            global_pos = parent.mapToGlobal(parent_rect.bottomRight())
            x = global_pos.x() - self.width() - _MARGIN
            y = global_pos.y() - self.height() - _MARGIN
        except Exception:
            pass
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
        """Display a notification message.

        Args:
            message:     The text to display.
            level:       Severity level — one of ``"info"``, ``"success"``,
                         ``"error"``, ``"warning"``.  Controls the
                         ``objectName`` (and therefore QSS styling).
            duration_ms: How long (ms) before the toast auto-hides.
                         Pass ``0`` to keep it visible until dismissed.
        """
        if level not in _VALID_LEVELS:
            _log.warning("Unknown toast level %r — falling back to 'info'", level)
            level = "info"

        self.setObjectName(f"toast_{level}")
        # Force QSS re-evaluation after objectName change
        self.style().unpolish(self)
        self.style().polish(self)

        self._icon_label.setText(_LEVEL_ICONS.get(level, ""))
        self._message_label.setText(message)

        self._reposition()
        self.show()
        self.raise_()

        self._timer.stop()
        if duration_ms > 0:
            self._timer.start(duration_ms)

        _log.debug("Toast [%s]: %s (duration=%dms)", level, message, duration_ms)
