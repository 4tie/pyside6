from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QVBoxLayout, QWidget,
    QPushButton, QHBoxLayout, QToolBar, QApplication,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from app.app_state.settings_state import SettingsState
from app.core.ai.ai_service import AIService
from app.ui.pages.backtest_page import BacktestPage
from app.ui.pages.download_data_page import DownloadDataPage
from app.ui.pages.improve_page import ImprovePage
from app.ui.pages.optimize_page import OptimizePage
from app.ui.pages.strategy_config_page import StrategyConfigPage
from app.ui.widgets.terminal_widget import TerminalWidget
from app.ui.widgets.ai_chat_dock import AIChatDock
from app.core.utils.app_logger import get_logger
from app.ui.theme import ThemeMode, build_stylesheet

_log = get_logger("ui.main_window")


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, settings_state: SettingsState = None):
        super().__init__()
        self.setWindowTitle("Freqtrade GUI")
        self.setMinimumSize(1200, 800)
        self.showMaximized()

        # Initialize state first so theme_mode is available
        if settings_state is None:
            settings_state = SettingsState()
            settings_state.load_settings()
        self.settings_state = settings_state

        # Apply theme from settings
        _mode_str = settings_state.current_settings.theme_mode if settings_state.current_settings else "dark"
        _mode = ThemeMode.DARK if _mode_str != "light" else ThemeMode.LIGHT
        QApplication.instance().setStyleSheet(build_stylesheet(_mode))

        # AI service — wires journal, tools, context providers
        self.ai_service = AIService(settings_state)

        # Toolbar
        self._build_toolbar()

        # Central widget + tabs
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout(self.central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)

        self.backtest_page = BacktestPage(self.settings_state)
        self.tabs.addTab(self.backtest_page, "Backtest")

        self.improve_page = ImprovePage(self.settings_state)
        self.tabs.addTab(self.improve_page, "Improve")

        self.optimize_page = OptimizePage(self.settings_state)
        self.tabs.addTab(self.optimize_page, "Optimize")

        self.download_data_page = DownloadDataPage(self.settings_state)
        self.tabs.addTab(self.download_data_page, "Download")

        self.strategy_config_page = StrategyConfigPage(self.settings_state)
        self.tabs.addTab(self.strategy_config_page, "Strategy")

        terminal_page = self._create_terminal_tab()
        self.tabs.addTab(terminal_page, "Terminal")

        layout.addWidget(self.tabs)

        # AI Chat dock
        self.ai_chat_dock = AIChatDock(self.settings_state, self, ai_service=self.ai_service)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chat_dock)

        # Wire BacktestJournalAdapter to BacktestService if available
        backtest_service = getattr(self.backtest_page, "backtest_service", None)
        if backtest_service is not None:
            self.ai_service.connect_backtest_service(backtest_service)

        # Give AIService a reference to the live BacktestPage
        self.ai_service.set_backtest_page(self.backtest_page)

        # View menu
        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.ai_chat_dock.toggleViewAction())

        # Apply terminal preferences from loaded settings
        self._apply_terminal_preferences()
        self.settings_state.settings_saved.connect(self._on_settings_saved)

        _log.info("MainWindow initialised")

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        """Add the main toolbar with app title and Settings button."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setFixedHeight(40)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        # App title label
        from PySide6.QtWidgets import QLabel
        title_label = QLabel("Freqtrade GUI")
        toolbar.addWidget(title_label)

        # Spacer
        from PySide6.QtWidgets import QWidget as _W
        spacer = _W()
        spacer.setSizePolicy(
            __import__("PySide6.QtWidgets", fromlist=["QSizePolicy"]).QSizePolicy.Expanding,
            __import__("PySide6.QtWidgets", fromlist=["QSizePolicy"]).QSizePolicy.Preferred,
        )
        toolbar.addWidget(spacer)

        settings_action = QAction("⚙  Settings", self)
        settings_action.setToolTip("Open application settings")
        settings_action.triggered.connect(self._open_settings_dialog)
        toolbar.addAction(settings_action)

    def _open_settings_dialog(self) -> None:
        """Open the Settings modal dialog."""
        from app.ui.dialogs.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.settings_state, parent=self)
        dialog.exec()

    # ------------------------------------------------------------------
    # Terminal helpers
    # ------------------------------------------------------------------

    @property
    def _all_terminals(self):
        """All TerminalWidget instances across the app."""
        return [
            self.terminal_widget,
            self.backtest_page.terminal,
            self.improve_page.terminal,
            self.optimize_page.terminal,
            self.download_data_page.terminal,
        ]

    def _apply_terminal_preferences(self):
        """Apply terminal preferences to all terminal widgets."""
        settings = self.settings_state.current_settings
        if not settings:
            return
        prefs = settings.terminal_preferences
        for t in self._all_terminals:
            t.apply_preferences(prefs)

    def _on_settings_saved(self, settings):
        """Re-apply terminal preferences and theme when settings are saved."""
        prefs = settings.terminal_preferences
        for t in self._all_terminals:
            t.apply_preferences(prefs)
        # Re-apply stylesheet if theme_mode changed
        _mode = ThemeMode.DARK if settings.theme_mode != "light" else ThemeMode.LIGHT
        QApplication.instance().setStyleSheet(build_stylesheet(_mode))

    def _create_terminal_tab(self) -> QWidget:
        """Create terminal tab with quick action buttons."""
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)

        button_layout = QHBoxLayout()

        check_python_btn = QPushButton("Check Python")
        check_python_btn.clicked.connect(self._check_python)
        button_layout.addWidget(check_python_btn)

        check_freqtrade_btn = QPushButton("Check Freqtrade")
        check_freqtrade_btn.clicked.connect(self._check_freqtrade)
        button_layout.addWidget(check_freqtrade_btn)

        button_layout.addStretch()
        tab_layout.addLayout(button_layout)

        self.terminal_widget = TerminalWidget()
        tab_layout.addWidget(self.terminal_widget)

        return tab_widget

    def _check_python(self):
        """Check Python version."""
        settings = self.settings_state.current_settings
        if not settings or not settings.python_executable:
            self.terminal_widget._append_error("Python executable not configured. Set it in Settings.\n")
            return
        self.terminal_widget.run_command([settings.python_executable, "--version"])

    def _check_freqtrade(self):
        """Check freqtrade availability."""
        settings = self.settings_state.current_settings
        if not settings or not settings.python_executable:
            self.terminal_widget._append_error("Python executable not configured. Set it in Settings.\n")
            return
        self.terminal_widget.run_freqtrade_command("--version", settings=settings)
