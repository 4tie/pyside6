"""Reusable metric/stat card widget."""
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from app.ui import theme


class StatCard(QWidget):
    """A card showing a metric label, value, and optional delta."""

    def __init__(
        self,
        label: str,
        value: str = "—",
        delta: str = "",
        positive: bool | None = None,
        accent_color: str = theme.ACCENT,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._accent = accent_color
        self._build(label, value, delta, positive)

    def _build(self, label: str, value: str, delta: str, positive: bool | None):
        self.setObjectName("surface")
        self.setMinimumWidth(140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        # Accent bar at top
        bar = QWidget()
        bar.setFixedHeight(3)
        bar.setStyleSheet(f"background: {self._accent}; border-radius: 2px;")
        layout.addWidget(bar)
        layout.addSpacing(6)

        # Label
        lbl = QLabel(label.upper())
        lbl.setObjectName("metric_label")
        lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 10px; font-weight: 600; letter-spacing: 1px;")
        layout.addWidget(lbl)

        # Value
        self._value_lbl = QLabel(value)
        self._value_lbl.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        layout.addWidget(self._value_lbl)

        # Delta
        if delta:
            self._delta_lbl = QLabel(delta)
            color = theme.GREEN if positive else (theme.RED if positive is False else theme.TEXT_SECONDARY)
            self._delta_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {color};")
            layout.addWidget(self._delta_lbl)
        else:
            self._delta_lbl = None

        self.setStyleSheet(f"""
            QWidget#surface {{
                background: {theme.BG_SURFACE};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 10px;
            }}
            QWidget#surface:hover {{
                border-color: {self._accent}55;
            }}
        """)

    def set_value(self, value: str, delta: str = "", positive: bool | None = None):
        self._value_lbl.setText(value)
        if self._delta_lbl and delta:
            self._delta_lbl.setText(delta)
            color = theme.GREEN if positive else (theme.RED if positive is False else theme.TEXT_SECONDARY)
            self._delta_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {color};")
