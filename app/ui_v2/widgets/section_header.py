"""SectionHeader widget for the v2 UI layer.

A titled, collapsible section that wraps any ``QWidget`` body.  A
``QToolButton`` arrow toggle shows/hides the body with a simple
``QPropertyAnimation`` on ``maximumHeight``.

Requirements: 3.3, 3.6
"""
from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.utils.app_logger import get_logger

_log = get_logger("ui_v2.section_header")

_ANIM_DURATION_MS = 200


class SectionHeader(QWidget):
    """Titled collapsible section.

    Wraps any ``QWidget`` as a collapsible body.  The title bar carries
    ``objectName = "section_header"`` for QSS styling.

    Args:
        title:     Text shown in the title bar.
        body:      The ``QWidget`` to show/hide.
        collapsed: Initial collapsed state (default ``False``).
        parent:    Optional parent widget.

    Signals:
        toggled(bool): Emitted when the section is expanded (``True``) or
                       collapsed (``False``).
    """

    toggled = Signal(bool)  # True = expanded, False = collapsed

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
        self._animation: QPropertyAnimation | None = None

        # Apply initial state without animation
        if self._collapsed:
            self._body.setMaximumHeight(0)
            self._body.hide()
            self._toggle_btn.setArrowType(Qt.RightArrow)
        else:
            self._toggle_btn.setArrowType(Qt.DownArrow)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the title bar and body layout."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Title bar ──────────────────────────────────────────────────
        self._title_bar = QWidget()
        self._title_bar.setObjectName("section_header")
        title_layout = QHBoxLayout(self._title_bar)
        title_layout.setContentsMargins(8, 4, 8, 4)
        title_layout.setSpacing(6)

        self._toggle_btn = QToolButton()
        self._toggle_btn.setArrowType(Qt.DownArrow)
        self._toggle_btn.setCheckable(False)
        self._toggle_btn.setAutoRaise(True)
        self._toggle_btn.setText(self._title)
        self._toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._toggle_btn.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )
        self._toggle_btn.clicked.connect(self._on_toggle)
        title_layout.addWidget(self._toggle_btn)

        outer.addWidget(self._title_bar)

        # ── Body ───────────────────────────────────────────────────────
        outer.addWidget(self._body)

    def _on_toggle(self) -> None:
        """Handle toggle button click — animate body show/hide."""
        self._collapsed = not self._collapsed
        self._animate(collapse=self._collapsed)
        self.toggled.emit(not self._collapsed)  # True = expanded
        _log.debug(
            "SectionHeader '%s' %s",
            self._title,
            "collapsed" if self._collapsed else "expanded",
        )

    def _animate(self, collapse: bool) -> None:
        """Run a height animation to show or hide the body widget."""
        # Stop any running animation
        if self._animation and self._animation.state() == QPropertyAnimation.Running:
            self._animation.stop()

        if collapse:
            start_h = self._body.sizeHint().height()
            end_h = 0
            self._toggle_btn.setArrowType(Qt.RightArrow)
        else:
            self._body.show()
            self._body.setMaximumHeight(16_777_215)  # Qt QWIDGETSIZE_MAX
            start_h = 0
            end_h = self._body.sizeHint().height()
            self._toggle_btn.setArrowType(Qt.DownArrow)

        anim = QPropertyAnimation(self._body, b"maximumHeight", self)
        anim.setDuration(_ANIM_DURATION_MS)
        anim.setStartValue(start_h)
        anim.setEndValue(end_h)
        anim.setEasingCurve(QEasingCurve.InOutQuad)

        if collapse:
            anim.finished.connect(self._body.hide)

        self._animation = anim
        anim.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_collapsed(self) -> bool:
        """Return ``True`` when the body is currently collapsed."""
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        """Programmatically collapse or expand the section.

        Args:
            collapsed: ``True`` to collapse, ``False`` to expand.
        """
        if collapsed != self._collapsed:
            self._on_toggle()
