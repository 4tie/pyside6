"""ModernMainWindow — sidebar-navigation desktop shell."""
from __future__ import annotations
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget,
    QApplication
)
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QKeySequence, QShortcut

from app.app_state.settings_state import SettingsState
from app.core.services.process_run_manager import ProcessRunManager
from app.ui import theme
from app.ui.shell.sidebar import NavSidebar
from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.backtest_page import BacktestPage
from app.ui.pages.results_page import ResultsPage
from app.ui.pages.compare_page import ComparePage
from app.ui.pages.optimize_page import OptimizePage
from app.ui.pages.download_page import DownloadPage
from app.ui.pages.settings_page import SettingsPage
from app.core.utils.app_logger import get_logger

_log = get_logger("ui.main_window")

_QSETTINGS_APP = "FreqtradeGUI"
_QSETTINGS_ORG = "FreqGUI"


class ModernMainWindow(QMainWindow):
    """Main application window with sidebar navigation."""

    def __init__(
        self,
        settings_state: Optional[SettingsState] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Freqtrade GUI")
        self.setMinimumSize(1100, 680)

        if settings_state is None:
            settings_state = SettingsState()
            settings_state.load_settings()
        self.settings_state = settings_state
        self._process_manager = ProcessRunManager()

        # Apply stylesheet
        QApplication.instance().setStyleSheet(theme.stylesheet())

        self._build_ui()
        self._wire_signals()
        self._register_shortcuts()
        self._restore_geometry()
        self.showMaximized()
        _log.info("ModernMainWindow initialised")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        self.sidebar = NavSidebar()
        root.addWidget(self.sidebar)

        # Page stack
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {theme.BG_BASE};")
        root.addWidget(self.stack, 1)

        # Create pages
        self.dashboard_page  = DashboardPage(self.settings_state)
        self.backtest_page   = BacktestPage(self.settings_state, self._process_manager)
        self.results_page    = ResultsPage(self.settings_state)
        self.compare_page    = ComparePage(self.settings_state)
        self.optimize_page   = OptimizePage(self.settings_state, self._process_manager)
        self.download_page   = DownloadPage(self.settings_state, self._process_manager)
        self.settings_page   = SettingsPage(self.settings_state)

        self._pages = {
            "dashboard": self.dashboard_page,
            "backtest":  self.backtest_page,
            "results":   self.results_page,
            "compare":   self.compare_page,
            "optimize":  self.optimize_page,
            "download":  self.download_page,
            "settings":  self.settings_page,
        }
        for page in self._pages.values():
            self.stack.addWidget(page)

        # Start on dashboard
        self._navigate("dashboard")

    def _wire_signals(self):
        self.sidebar.page_changed.connect(self._navigate)
        self.backtest_page.run_completed.connect(self._on_backtest_done)
        self.settings_page.settings_saved.connect(self._on_settings_saved)

    def _register_shortcuts(self):
        pages = list(self._pages.keys())
        for i, page_id in enumerate(pages):
            sc = QShortcut(QKeySequence(f"Ctrl+{i+1}"), self)
            sc.activated.connect(lambda pid=page_id: self._navigate(pid))

    def _navigate(self, page_id: str):
        page = self._pages.get(page_id)
        if page:
            self.stack.setCurrentWidget(page)
            self.sidebar.navigate_to(page_id)
            _log.debug("Navigated to %s", page_id)

    def _on_backtest_done(self, run_id: str):
        _log.info("Backtest done: %s — refreshing results", run_id)
        QTimer.singleShot(500, self.results_page.refresh)

    def _on_settings_saved(self):
        _log.info("Settings saved — reloading strategies")
        try:
            self.backtest_page._load_strategies()
            self.optimize_page._load_strategies()
        except Exception:
            pass

    def _restore_geometry(self):
        qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        geom = qs.value("geometry")
        if geom:
            self.restoreGeometry(geom)

    def closeEvent(self, event):
        qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        qs.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)
