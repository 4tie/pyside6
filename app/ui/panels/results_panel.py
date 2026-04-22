"""ResultsPanel — dockable results panel wrapping BacktestResultsWidget.

Provides a QDockWidget that can be docked to the right or bottom dock
areas of the main window.  The inner BacktestResultsWidget is accessible
via the ``.results_widget`` attribute.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QWidget

from app.app_state.settings_state import SettingsState
from app.core.utils.app_logger import get_logger
from app.ui.widgets.backtest_results_widget import BacktestResultsWidget

_log = get_logger("ui.results_panel")


class ResultsPanel(QDockWidget):
    """Dockable results panel wrapping BacktestResultsWidget."""

    def __init__(
        self,
        settings_state: SettingsState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Results", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.results_widget = BacktestResultsWidget()
        self.setWidget(self.results_widget)
        _log.debug("ResultsPanel initialised")
