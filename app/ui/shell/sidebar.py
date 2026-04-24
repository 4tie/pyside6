"""Collapsible sidebar navigation."""
from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QFrame
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont
from app.ui import theme

_NAV_ITEMS = [
    ("dashboard",  "⬡",  "Dashboard"),
    ("backtest",   "▶",  "Backtest"),
    ("results",    "📊", "Results"),
    ("compare",    "⇄",  "Compare"),
    ("optimize",   "⚙",  "Optimize"),
    ("download",   "↓",  "Download"),
    ("settings",   "⚙",  "Settings"),
]


class NavButton(QPushButton):
    def __init__(self, icon: str, label: str, page_id: str, parent=None):
        super().__init__(parent)
        self.page_id = page_id
        self._icon = icon
        self._label = label
        self._active = False
        self.setCheckable(True)
        self.setFixedHeight(44)
        self._update_style()

    def set_active(self, active: bool):
        self._active = active
        self.setChecked(active)
        self._update_style()

    def _update_style(self):
        if self._active:
            bg = theme.ACCENT_DIM
            color = theme.ACCENT
            border = f"border-left: 3px solid {theme.ACCENT};"
        else:
            bg = "transparent"
            color = theme.TEXT_SECONDARY
            border = "border-left: 3px solid transparent;"

        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {color};
                {border}
                border-right: none;
                border-top: none;
                border-bottom: none;
                border-radius: 0;
                text-align: left;
                padding: 0 16px;
                font-size: 13px;
                font-weight: {'600' if self._active else '400'};
            }}
            QPushButton:hover {{
                background: {theme.BG_ELEVATED};
                color: {theme.TEXT_PRIMARY};
            }}
        """)
        self.setText(f"  {self._icon}  {self._label}")


class NavSidebar(QWidget):
    """Left navigation sidebar."""

    page_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setStyleSheet(f"background: {theme.BG_SURFACE}; border-right: 1px solid {theme.BG_BORDER};")
        self._buttons: dict[str, NavButton] = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo area
        logo_area = QWidget()
        logo_area.setFixedHeight(60)
        logo_area.setStyleSheet(f"background: {theme.BG_BASE}; border-bottom: 1px solid {theme.BG_BORDER};")
        ll = QHBoxLayout(logo_area)
        ll.setContentsMargins(16, 0, 16, 0)
        logo = QLabel("⬡ FreqGUI")
        logo.setStyleSheet(f"color: {theme.ACCENT}; font-size: 16px; font-weight: 700;")
        ll.addWidget(logo)
        layout.addWidget(logo_area)

        layout.addSpacing(8)

        # Nav buttons
        for page_id, icon, label in _NAV_ITEMS:
            btn = NavButton(icon, label, page_id)
            btn.clicked.connect(lambda checked, pid=page_id: self._on_click(pid))
            self._buttons[page_id] = btn
            layout.addWidget(btn)

        layout.addStretch()

        # Version footer
        ver = QLabel("v2.0")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 10px; padding: 8px;")
        layout.addWidget(ver)

    def _on_click(self, page_id: str):
        self.navigate_to(page_id)
        self.page_changed.emit(page_id)

    def navigate_to(self, page_id: str):
        for pid, btn in self._buttons.items():
            btn.set_active(pid == page_id)
