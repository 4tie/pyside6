"""MetricCard widget for the v2 UI layer.

A ``QFrame`` subclass that displays a KPI title, a large value, and an
optional trend arrow (▲ green / ▼ red).

Requirements: 3.2, 5.1
"""
from typing import Optional

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from app.core.utils.app_logger import get_logger

_log = get_logger("ui_v2.metric_card")


class MetricCard(QFrame):
    """KPI display card: title label + large value + optional trend arrow.

    Args:
        title:  Short label shown above the value (e.g. "Win Rate").
        value:  Initial value string (default ``"—"``).
        trend:  Optional float; positive → green ▲, negative → red ▼.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        title: str,
        value: str = "—",
        trend: Optional[float] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("metric_card")

        self._title = title
        self._value = value
        self._trend = trend

        self._build_ui()
        self._refresh()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the internal layout and child widgets."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Title row
        self._title_label = QLabel(self._title)
        self._title_label.setObjectName("metric_card_title")
        layout.addWidget(self._title_label)

        # Value + trend row
        value_row = QHBoxLayout()
        value_row.setSpacing(6)

        self._value_label = QLabel(self._value)
        self._value_label.setObjectName("metric_card_value")
        value_row.addWidget(self._value_label)

        self._trend_label = QLabel()
        self._trend_label.setObjectName("metric_card_trend")
        value_row.addWidget(self._trend_label)
        value_row.addStretch()

        layout.addLayout(value_row)

    def _refresh(self) -> None:
        """Sync labels to the current ``_value`` / ``_trend`` state."""
        self._value_label.setText(self._value)

        if self._trend is None:
            self._trend_label.setText("")
            self._trend_label.setStyleSheet("")
        elif self._trend >= 0:
            self._trend_label.setText("▲")
            self._trend_label.setStyleSheet("color: #4caf50;")  # green
        else:
            self._trend_label.setText("▼")
            self._trend_label.setStyleSheet("color: #f44336;")  # red

        _log.debug(
            "MetricCard '%s' updated: value=%s trend=%s",
            self._title,
            self._value,
            self._trend,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_value(self, value: str, trend: Optional[float] = None) -> None:
        """Update the displayed value and trend arrow.

        Args:
            value: New value string to display.
            trend: Optional float; positive → ▲ green, negative → ▼ red,
                   ``None`` hides the arrow.
        """
        self._value = value
        self._trend = trend
        self._refresh()
