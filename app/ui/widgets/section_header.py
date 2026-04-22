"""section_header.py — Titled collapsible section widget for the Freqtrade GUI.

Wraps any QWidget as a collapsible body beneath a clickable title bar.
The title bar contains a QToolButton arrow toggle and a title label.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QLabel,
)

from app.core.utils.app_logger import get_logger
from app.ui.theme import FONT, PALETTE, SPACING

_log = get_logger("ui.section_header")


class SectionHeader(QWidget):
    """Titled collapsible section. Wraps any QWidget as collapsible body.

    Args:
        title: Section heading text.
        body: The widget to show/hide when toggled.
        collapsed: Initial collapsed state (default False = expanded).
        parent: Optional parent widget.

    Signals:
        toggled(bool): Emitted when the section is toggled; True = expanded.
    """

    toggled = Signal(bool)  # True = expanded

    def __init__(
        self,
        title: str,
        body: QWidget,
        collapsed: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._body = body
        self._collapsed = collapsed
        self._build_ui()
        # Apply initial state without emitting signal
        self._apply_state(emit=False)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build title bar + body layout."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Title bar ──────────────────────────────────────────────────
        self._title_bar = QWidget()
        self._title_bar.setObjectName("section_header")
        self._title_bar.setCursor(
            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.PointingHandCursor
        )
        self._title_bar.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )

        bar_layout = QHBoxLayout(self._title_bar)
        bar_layout.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["xs"]
        )
        bar_layout.setSpacing(SPACING["xs"])

        # Arrow toggle button
        self._toggle_btn = QToolButton()
        self._toggle_btn.setFocusPolicy(
            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.NoFocus
        )
        self._toggle_btn.setStyleSheet("border: none; background: transparent;")
        self._toggle_btn.clicked.connect(self._on_toggle_clicked)
        bar_layout.addWidget(self._toggle_btn)

        # Title label — small caps style, secondary colour
        self._title_label = QLabel(self._title)
        self._title_label.setStyleSheet(
            f"color: {PALETTE['text_secondary']};"
            f"font-size: {FONT['size_sm']}px;"
            "font-weight: 600;"
            "letter-spacing: 1px;"
            "text-transform: uppercase;"
        )
        bar_layout.addWidget(self._title_label)
        bar_layout.addStretch()

        outer.addWidget(self._title_bar)

        # ── Body ───────────────────────────────────────────────────────
        outer.addWidget(self._body)

        # Make title bar clickable by installing event filter
        self._title_bar.mousePressEvent = self._on_title_bar_clicked  # type: ignore[method-assign]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_toggle_clicked(self) -> None:
        """Handle toggle button click."""
        self.set_collapsed(not self._collapsed)

    def _on_title_bar_clicked(self, event) -> None:  # noqa: ANN001
        """Handle click anywhere on the title bar."""
        self.set_collapsed(not self._collapsed)

    def _apply_state(self, emit: bool = True) -> None:
        """Show/hide body and update arrow icon based on current state."""
        if self._collapsed:
            self._toggle_btn.setText("▶")
            self._body.hide()
        else:
            self._toggle_btn.setText("▼")
            self._body.show()

        if emit:
            self.toggled.emit(not self._collapsed)
            _log.debug(
                "SectionHeader '%s' toggled: collapsed=%s", self._title, self._collapsed
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_collapsed(self, collapsed: bool) -> None:
        """Set the collapsed state and update the UI.

        Args:
            collapsed: True to collapse (hide body), False to expand (show body).
        """
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        self._apply_state(emit=True)

    def is_collapsed(self) -> bool:
        """Return True if the section is currently collapsed.

        Returns:
            Current collapsed state.
        """
        return self._collapsed
