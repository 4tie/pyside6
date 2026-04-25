"""Collapsible sidebar navigation."""
from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
)
from PySide6.QtCore import Qt, Signal
from app.ui import theme

_NAV_ITEMS = [
    ("dashboard",  "⬡",  "Dashboard"),
    ("backtest",   "▶",  "Backtest"),
    ("parneeds",   "P",  "ParNeeds"),
    ("results",    "📊", "Results"),
    ("compare",    "⇄",  "Compare"),
    ("optimize",   "⚙",  "Optimize"),
    ("optimizer",  "⚡",  "Optimizer"),
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
        self._collapsed = False
        self.setCheckable(True)
        self.setFixedHeight(44)
        self.setToolTip(label)
        self._update_style()

    def set_active(self, active: bool):
        self._active = active
        self.setChecked(active)
        self._update_style()

    def set_collapsed(self, collapsed: bool):
        self._collapsed = collapsed
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

        padding = "0 0" if self._collapsed else "0 16px"
        align = "center" if self._collapsed else "left"
        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {color};
                {border}
                border-right: none;
                border-top: none;
                border-bottom: none;
                border-radius: 0;
                text-align: {align};
                padding: {padding};
                font-size: 13px;
                font-weight: {'600' if self._active else '400'};
            }}
            QPushButton:hover {{
                background: {theme.BG_ELEVATED};
                color: {theme.TEXT_PRIMARY};
            }}
        """)
        self.setText(self._icon if self._collapsed else f"  {self._icon}  {self._label}")


class NavSidebar(QWidget):
    """Left navigation sidebar."""

    page_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._expanded_width = 200
        self._collapsed_width = 58
        self._collapsed = False
        self.setFixedWidth(self._expanded_width)
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
        self._logo = QLabel("⬡ FreqGUI")
        self._logo.setStyleSheet(f"color: {theme.ACCENT}; font-size: 16px; font-weight: 700;")
        ll.addWidget(self._logo)
        layout.addWidget(logo_area)

        layout.addSpacing(8)

        # Nav buttons
        for page_id, icon, label in _NAV_ITEMS:
            btn = NavButton(icon, label, page_id)
            btn.clicked.connect(lambda checked, pid=page_id: self._on_click(pid))
            self._buttons[page_id] = btn
            layout.addWidget(btn)

        layout.addStretch()

        footer = QWidget()
        footer.setFixedHeight(44)
        footer.setStyleSheet(f"background: {theme.BG_ELEVATED}; border-top: 1px solid {theme.BG_BORDER};")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 6, 10, 6)
        footer_layout.addStretch()
        self._collapse_btn = QPushButton("‹")
        self._collapse_btn.setFixedSize(30, 30)
        self._collapse_btn.setToolTip("Collapse navigation")
        self._collapse_btn.clicked.connect(self._toggle_collapsed)
        self._collapse_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {theme.TEXT_SECONDARY};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 4px;
                padding: 0;
                font-size: 20px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {theme.BG_BORDER};
                color: {theme.TEXT_PRIMARY};
                border-color: {theme.ACCENT_DIM};
            }}
        """)
        footer_layout.addWidget(self._collapse_btn)
        layout.addWidget(footer)
        self._apply_collapsed_state()

    def _on_click(self, page_id: str):
        self.navigate_to(page_id)
        self.page_changed.emit(page_id)

    def navigate_to(self, page_id: str):
        for pid, btn in self._buttons.items():
            btn.set_active(pid == page_id)

    def _toggle_collapsed(self):
        self._collapsed = not self._collapsed
        self._apply_collapsed_state()

    def _apply_collapsed_state(self):
        self.setFixedWidth(self._collapsed_width if self._collapsed else self._expanded_width)
        self._logo.setText("⬡" if self._collapsed else "⬡ FreqGUI")
        self._logo.setAlignment(Qt.AlignCenter if self._collapsed else Qt.AlignLeft | Qt.AlignVCenter)
        self._collapse_btn.setText("›" if self._collapsed else "‹")
        self._collapse_btn.setToolTip("Expand navigation" if self._collapsed else "Collapse navigation")
        for btn in self._buttons.values():
            btn.set_collapsed(self._collapsed)
