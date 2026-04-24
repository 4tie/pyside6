"""NavSidebar — collapsible left navigation sidebar for the Freqtrade GUI.

Provides a vertical list of NavItem buttons (icon + label) and a collapse
toggle at the bottom that animates the sidebar width between icon-only (48 px)
and expanded (200 px) modes.
"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Signal
from PySide6.QtWidgets import (
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.utils.app_logger import get_logger
from app.ui.theme import PALETTE, SPACING

_log = get_logger("ui.sidebar")

# Sidebar width constants
_WIDTH_COLLAPSED = 48
_WIDTH_EXPANDED = 200
_ANIMATION_DURATION_MS = 200

# Nav items: (page_id, icon, label)
_NAV_ITEMS: list[tuple[str, str, str]] = [
    ("dashboard", "🏠", "Dashboard"),
    ("backtest", "📊", "Backtest"),
    ("optimize", "🔬", "Optimize"),
    ("download", "⬇", "Download"),
    ("strategy", "📋", "Strategy"),
    ("strategy_lab", "🧪", "Strategy Lab"),
    ("settings", "⚙", "Settings"),
]


class NavSidebar(QWidget):
    """Collapsible left navigation sidebar."""

    nav_item_clicked = Signal(str)  # emits page_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._collapsed = False
        self._items: dict[str, NavSidebar.NavItem] = {}
        self._build_ui()
        _log.debug("NavSidebar initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_active(self, page_id: str) -> None:
        """Mark *page_id* as the active nav item and deactivate all others.

        Args:
            page_id: The page identifier to activate.
        """
        for pid, btn in self._items.items():
            if pid == page_id:
                btn.setObjectName("nav_item_active")
            else:
                btn.setObjectName("nav_item")
            # Force QSS re-evaluation
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        _log.debug("NavSidebar active page set to %r", page_id)

    def set_collapsed(self, collapsed: bool) -> None:
        """Collapse or expand the sidebar with an animation.

        Args:
            collapsed: ``True`` to collapse to icon-only, ``False`` to expand.
        """
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self._run_animation(collapsed)
        self._update_item_labels()
        self._toggle_btn.setText("▶" if collapsed else "◀")
        _log.debug("NavSidebar collapsed=%s", collapsed)

    def is_collapsed(self) -> bool:
        """Return whether the sidebar is currently in collapsed (icon-only) mode."""
        return self._collapsed

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the sidebar layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["xs"], SPACING["sm"], SPACING["xs"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        # Nav items
        for page_id, icon, label in _NAV_ITEMS:
            item = NavSidebar.NavItem(icon, label, self)
            item.setObjectName("nav_item")
            item.clicked.connect(self._make_click_handler(page_id))
            self._items[page_id] = item
            layout.addWidget(item)

        layout.addStretch(1)

        # Collapse toggle button
        self._toggle_btn = QToolButton(self)
        self._toggle_btn.setText("◀")
        self._toggle_btn.setToolTip("Collapse sidebar")
        self._toggle_btn.setAccessibleName("Toggle sidebar")
        self._toggle_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._toggle_btn.clicked.connect(self._on_toggle_clicked)
        layout.addWidget(self._toggle_btn)

        # Initial width
        self.setMaximumWidth(_WIDTH_EXPANDED)
        self.setMinimumWidth(_WIDTH_COLLAPSED)

        # Scoped stylesheet — prevents child buttons from inheriting global QWidget bg
        self.setObjectName("NavSidebar")
        self.setStyleSheet(f"""
            QWidget#NavSidebar {{
                background-color: {PALETTE['bg_surface']};
                border-right: 1px solid {PALETTE['border']};
            }}
            QWidget#NavSidebar QToolButton {{
                background-color: transparent;
                border: none;
                color: {PALETTE['text_secondary']};
                padding: 4px;
            }}
            QWidget#NavSidebar QToolButton:hover {{
                background-color: {PALETTE['bg_elevated']};
                border-radius: 4px;
            }}
        """)

    def _make_click_handler(self, page_id: str):
        """Return a slot that emits nav_item_clicked with *page_id*."""
        def _handler() -> None:
            self.nav_item_clicked.emit(page_id)
        return _handler

    def _on_toggle_clicked(self) -> None:
        """Handle the collapse/expand toggle button click."""
        self.set_collapsed(not self._collapsed)

    def _run_animation(self, collapse: bool) -> None:
        """Animate maximumWidth between expanded and collapsed values."""
        anim = QPropertyAnimation(self, b"maximumWidth", self)
        anim.setDuration(_ANIMATION_DURATION_MS)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        if collapse:
            anim.setStartValue(self.maximumWidth())
            anim.setEndValue(_WIDTH_COLLAPSED)
        else:
            anim.setStartValue(self.maximumWidth())
            anim.setEndValue(_WIDTH_EXPANDED)
        anim.start()
        # Keep reference so it isn't garbage-collected before finishing
        self._animation = anim

    def _update_item_labels(self) -> None:
        """Show or hide the text label portion of each NavItem."""
        for item in self._items.values():
            item.set_label_visible(not self._collapsed)

    # ------------------------------------------------------------------
    # Inner class
    # ------------------------------------------------------------------

    class NavItem(QPushButton):
        """Single nav entry: icon text + label, checkable."""

        def __init__(
            self,
            icon: str,
            label: str,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self._icon_text = icon
            self._label_text = label
            self._label_visible = True
            self._refresh_text()
            self.setCheckable(False)
            self.setObjectName("nav_item")
            self.setToolTip(label)
            self.setAccessibleName(label)
            self.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            self.setMinimumHeight(36)

        def set_label_visible(self, visible: bool) -> None:
            """Show or hide the label text (icon always shown).

            Args:
                visible: ``True`` to show icon + label, ``False`` for icon only.
            """
            self._label_visible = visible
            self._refresh_text()

        def _refresh_text(self) -> None:
            """Update button text based on current label visibility."""
            if self._label_visible:
                self.setText(f"{self._icon_text}  {self._label_text}")
            else:
                self.setText(self._icon_text)
