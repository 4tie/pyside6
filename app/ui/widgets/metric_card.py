"""metric_card.py — KPI display card widget for the Freqtrade GUI dashboard.

Displays a title label, a large value label, and an optional trend arrow
(▲ in success colour for positive trends, ▼ in danger colour for negative).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from app.core.utils.app_logger import get_logger
from app.ui.theme import FONT, PALETTE, SPACING

_log = get_logger("ui.metric_card")


class MetricCard(QFrame):
    """KPI display card: title label + large value + optional trend arrow.

    Args:
        title: Short label shown above the value (e.g. "Win Rate").
        value: Initial value string (default "—").
        trend: Optional float; positive → ▲ success colour, negative → ▼ danger colour.
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
        self._build_ui()
        self.set_value(value, trend)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the internal layout: title row + value + trend arrow."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"]
        )
        layout.setSpacing(SPACING["xs"])

        # Title label — small, secondary colour
        self._title_label = QLabel(self._title)
        self._title_label.setStyleSheet(
            f"color: {PALETTE['text_secondary']};"
            f"font-size: {FONT['size_sm']}px;"
            "font-weight: 600;"
            "letter-spacing: 1px;"
            "text-transform: uppercase;"
        )
        layout.addWidget(self._title_label)

        # Value row: large value label + trend arrow side by side
        value_row = QHBoxLayout()
        value_row.setSpacing(SPACING["xs"])
        value_row.setContentsMargins(0, 0, 0, 0)

        self._value_label = QLabel("—")
        self._value_label.setStyleSheet(
            f"color: {PALETTE['text_primary']};"
            f"font-size: {FONT['size_lg']}px;"
            "font-weight: bold;"
        )
        value_row.addWidget(self._value_label)

        self._trend_label = QLabel("")
        self._trend_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._trend_label.hide()
        value_row.addWidget(self._trend_label)
        value_row.addStretch()

        layout.addLayout(value_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_value(self, value: str, trend: Optional[float] = None) -> None:
        """Update displayed value and trend arrow.

        Args:
            value: New value string to display.
            trend: Optional float; positive → ▲ green, negative → ▼ red, None → hidden.
        """
        self._value_label.setText(value)

        if trend is None:
            self._trend_label.hide()
        elif trend > 0:
            self._trend_label.setText("▲")
            self._trend_label.setStyleSheet(
                f"color: {PALETTE['success']}; font-size: {FONT['size_base']}px;"
            )
            self._trend_label.show()
        else:
            self._trend_label.setText("▼")
            self._trend_label.setStyleSheet(
                f"color: {PALETTE['danger']}; font-size: {FONT['size_base']}px;"
            )
            self._trend_label.show()

        _log.debug("MetricCard '%s' updated: value=%r trend=%r", self._title, value, trend)
