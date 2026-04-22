"""TerminalPanel — dockable terminal panel wrapping TerminalWidget.

Provides a QDockWidget that can be docked to the bottom or top dock areas
of the main window.  The inner TerminalWidget is accessible via the
``.terminal`` property.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QWidget

from app.core.utils.app_logger import get_logger
from app.ui.widgets.terminal_widget import TerminalWidget

_log = get_logger("ui.terminal_panel")


class TerminalPanel(QDockWidget):
    """Dockable terminal panel wrapping TerminalWidget."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Terminal", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.TopDockWidgetArea
        )
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self._terminal = TerminalWidget()
        self.setWidget(self._terminal)
        _log.debug("TerminalPanel initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def terminal(self) -> TerminalWidget:
        """The wrapped TerminalWidget instance."""
        return self._terminal
