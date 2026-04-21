"""NavSidebar — icon + label navigation rail for the v2 UI shell.

Provides a collapsible sidebar with six navigation items.  Clicking an item
emits ``nav_item_clicked(page_id)`` so ``ModernMainWindow`` can switch the
active page in the ``QStackedWidget``.

Requirements: 2.1, 2.3, 2.6, 2.7
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.utils.app_logger import get_logger

_log = get_logger("ui_v2.shell.sidebar")

# ---------------------------------------------------------------------------
# Nav item definitions: (page_id, icon, label)
# ---------------------------------------------------------------------------

_NAV_ITEMS: List[Tuple[str, str, str]] = [
    ("dashboard", "🏠", "Dashboard"),
    ("backtest", "📊", "Backtest"),
    ("optimize", "🔬", "Optimize"),
    ("download", "⬇", "Download"),
    ("strategy", "📋", "Strategy"),
    ("lab", "🧪", "Strategy Lab"),
    ("settings", "⚙", "Settings"),
]

_COLLAPSED_WIDTH = 48
_EXPANDED_WIDTH = 180
_ANIMATION_DURATION_MS = 200


class NavSidebar(QWidget):
    """Collapsible navigation sidebar.

    Emits ``nav_item_clicked(page_id: str)`` when the user clicks a nav item.
    Call ``set_active(page_id)`` to highlight the currently active page.

    The sidebar can be collapsed to icon-only mode (48 px) or expanded to
    show icons + labels (180 px).  The transition is animated via
    ``QPropertyAnimation`` on ``maximumWidth``.
    """

    nav_item_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._collapsed = False
        self._items: Dict[str, "NavItem"] = {}

        self._build_ui()
        self._setup_animation()

        _log.debug("NavSidebar initialised")

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the sidebar layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(2)

        # Nav items
        for page_id, icon, label in _NAV_ITEMS:
            item = NavItem(icon=icon, label=label, page_id=page_id)
            item.clicked.connect(self._on_item_clicked)
            self._items[page_id] = item
            layout.addWidget(item)

        layout.addStretch()

        # Collapse toggle button
        self._toggle_btn = _CollapseToggle()
        self._toggle_btn.clicked.connect(self._toggle_collapse)
        layout.addWidget(self._toggle_btn)

        # Fixed initial width
        self.setFixedWidth(_EXPANDED_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def _setup_animation(self) -> None:
        """Prepare the width animation."""
        self._anim = QPropertyAnimation(self, b"maximumWidth")
        self._anim.setDuration(_ANIMATION_DURATION_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_active(self, page_id: str) -> None:
        """Update objectName on all items to reflect the active page.

        Args:
            page_id: The id of the page that is now active.
        """
        for pid, item in self._items.items():
            if pid == page_id:
                item.setObjectName("nav_item_active")
            else:
                item.setObjectName("nav_item")
            # Force style re-evaluation after objectName change
            item.style().unpolish(item)
            item.style().polish(item)
            item.update()

    def is_collapsed(self) -> bool:
        """Return ``True`` when the sidebar is in collapsed (icon-only) mode."""
        return self._collapsed

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _on_item_clicked(self) -> None:
        """Re-emit the page id of the clicked NavItem."""
        item: NavItem = self.sender()  # type: ignore[assignment]
        self.nav_item_clicked.emit(item.page_id)

    def _toggle_collapse(self) -> None:
        """Animate the sidebar between expanded and collapsed states."""
        if self._collapsed:
            # Expand
            self._anim.setStartValue(self.maximumWidth())
            self._anim.setEndValue(_EXPANDED_WIDTH)
            self._anim.start()
            self._collapsed = False
            self._toggle_btn.setText("◀")
            for item in self._items.values():
                item.show_label(True)
        else:
            # Collapse
            self._anim.setStartValue(self.maximumWidth())
            self._anim.setEndValue(_COLLAPSED_WIDTH)
            self._anim.start()
            self._collapsed = True
            self._toggle_btn.setText("▶")
            for item in self._items.values():
                item.show_label(False)

        _log.debug("NavSidebar collapsed=%s", self._collapsed)


# ---------------------------------------------------------------------------
# NavItem
# ---------------------------------------------------------------------------


class NavItem(QPushButton):
    """Single navigation entry: icon + label, checkable.

    ``objectName`` is ``"nav_item"`` by default and ``"nav_item_active"``
    when the item represents the currently active page.
    """

    def __init__(
        self,
        icon: str,
        label: str,
        page_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.page_id = page_id
        self.setObjectName("nav_item")
        self.setCheckable(False)
        self.setFlat(True)
        self.setAccessibleName(label)
        self.setToolTip(label)

        # Layout: icon label + text label side by side
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setFixedWidth(20)
        self._icon_lbl.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self._icon_lbl)

        self._text_lbl = QLabel(label)
        self._text_lbl.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self._text_lbl)
        layout.addStretch()

        self.setMinimumHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def show_label(self, visible: bool) -> None:
        """Show or hide the text label (used during collapse/expand).

        Args:
            visible: ``True`` to show the label, ``False`` to hide it.
        """
        self._text_lbl.setVisible(visible)


# ---------------------------------------------------------------------------
# Collapse toggle button (private helper)
# ---------------------------------------------------------------------------


class _CollapseToggle(QPushButton):
    """Small button at the bottom of the sidebar to toggle collapse."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("◀", parent)
        self.setObjectName("nav_item")
        self.setFlat(True)
        self.setFixedHeight(32)
        self.setToolTip("Collapse sidebar")
        self.setAccessibleName("Collapse sidebar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
