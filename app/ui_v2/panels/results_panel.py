"""ResultsPanel — dockable backtest results panel wrapping BacktestResultsWidget.

Requirements: 4.4, 5.1
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget

from app.core.utils.app_logger import get_logger
from app.ui.widgets.backtest_results_widget import BacktestResultsWidget

_log = get_logger("ui_v2.results_panel")


class ResultsPanel(QDockWidget):
    """Dockable results panel that wraps :class:`BacktestResultsWidget`.

    Allowed dock areas: right and bottom only.
    Features: closable and movable (no floating).

    Attributes:
        results_widget: The embedded :class:`BacktestResultsWidget` instance.
    """

    def __init__(self, parent=None) -> None:
        super().__init__("Results", parent)
        self.setObjectName("ResultsPanel")
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable
        )

        self.results_widget = BacktestResultsWidget()
        self.setWidget(self.results_widget)

        _log.debug("ResultsPanel initialised")
