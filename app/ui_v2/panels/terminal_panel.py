"""TerminalPanel — dockable terminal panel wrapping TerminalWidget.

Requirements: 10.1, 10.2
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget

from app.core.utils.app_logger import get_logger
from app.ui.widgets.terminal_widget import TerminalWidget

_log = get_logger("ui_v2.terminal_panel")


class TerminalPanel(QDockWidget):
    """Dockable terminal panel that wraps :class:`TerminalWidget`.

    Allowed dock areas: bottom and top only.
    Features: closable and movable (no floating).

    Attributes:
        terminal: The embedded :class:`TerminalWidget` instance.
    """

    def __init__(self, parent=None) -> None:
        super().__init__("Terminal", parent)
        self.setObjectName("TerminalPanel")
        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable
        )

        self.terminal = TerminalWidget()
        self.setWidget(self.terminal)

        _log.debug("TerminalPanel initialised")
