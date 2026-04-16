from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
)
from PySide6.QtCore import Qt

from app.app_state.settings_state import SettingsState
from app.core.ai.ai_service import AIService
from app.ui.pages.settings_page import SettingsPage
from app.ui.pages.backtest_page import BacktestPage
from app.ui.pages.download_data_page import DownloadDataPage
from app.ui.pages.optimize_page import OptimizePage
from app.ui.pages.strategy_config_page import StrategyConfigPage
from app.ui.widgets.terminal_widget import TerminalWidget
from app.ui.widgets.ai_chat_dock import AIChatDock


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, settings_state: SettingsState = None):
        super().__init__()
        self.setWindowTitle("Freqtrade GUI")
        self.setGeometry(100, 100, 1400, 900)

        # Initialize state
        if settings_state is None:
            settings_state = SettingsState()
            settings_state.load_settings()

        self.settings_state = settings_state

        # AI service — wires journal, tools, context providers
        self.ai_service = AIService(settings_state)

        # Create central widget with tabs
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout()

        # Tab widget
        self.tabs = QTabWidget()

        # Settings tab
        self.settings_page = SettingsPage(self.settings_state)
        self.tabs.addTab(self.settings_page, "Settings")

        # Backtest tab
        self.backtest_page = BacktestPage(self.settings_state)
        self.tabs.addTab(self.backtest_page, "Backtest")

        # Optimize tab
        self.optimize_page = OptimizePage(self.settings_state)
        self.tabs.addTab(self.optimize_page, "Optimize")

        # Download data tab
        self.download_data_page = DownloadDataPage(self.settings_state)
        self.tabs.addTab(self.download_data_page, "Download Data")

        # Strategy config tab
        self.strategy_config_page = StrategyConfigPage(self.settings_state)
        self.tabs.addTab(self.strategy_config_page, "Strategy Config")

        # Terminal tab (for ad-hoc testing)
        terminal_page = self._create_terminal_tab()
        self.tabs.addTab(terminal_page, "Terminal")

        layout.addWidget(self.tabs)
        self.central_widget.setLayout(layout)

        # AI Chat dock
        self.ai_chat_dock = AIChatDock(self.settings_state, self, ai_service=self.ai_service)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_chat_dock)

        # Wire BacktestJournalAdapter to BacktestService if available
        backtest_service = getattr(self.backtest_page, "backtest_service", None)
        if backtest_service is not None:
            self.ai_service.connect_backtest_service(backtest_service)

        # View menu
        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.ai_chat_dock.toggleViewAction())

        # Apply terminal preferences from loaded settings
        self._apply_terminal_preferences()
        self.settings_state.settings_saved.connect(self._on_settings_saved)

    @property
    def _all_terminals(self):
        """All TerminalWidget instances across the app."""
        return [
            self.terminal_widget,
            self.backtest_page.terminal,
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
        """Re-apply terminal preferences when settings are saved."""
        prefs = settings.terminal_preferences
        for t in self._all_terminals:
            t.apply_preferences(prefs)

    def _create_terminal_tab(self) -> QWidget:
        """Create terminal tab with quick action buttons."""
        tab_widget = QWidget()
        tab_layout = QVBoxLayout()

        # Quick action buttons
        button_layout = QHBoxLayout()

        check_python_btn = QPushButton("Check Python")
        check_python_btn.clicked.connect(self._check_python)
        button_layout.addWidget(check_python_btn)

        check_freqtrade_btn = QPushButton("Check Freqtrade")
        check_freqtrade_btn.clicked.connect(self._check_freqtrade)
        button_layout.addWidget(check_freqtrade_btn)


        button_layout.addStretch()
        tab_layout.addLayout(button_layout)

        # Terminal widget
        self.terminal_widget = TerminalWidget()
        tab_layout.addWidget(self.terminal_widget)

        tab_widget.setLayout(tab_layout)
        return tab_widget

    def _check_python(self):
        """Check Python version."""
        settings = self.settings_state.current_settings
        if not settings or not settings.python_executable:
            self.terminal_widget._append_error("Python executable not configured. Set it in Settings.\n")
            return

        self.terminal_widget.run_command(
            [settings.python_executable, "--version"]
        )

    def _check_freqtrade(self):
        """Check freqtrade availability."""
        settings = self.settings_state.current_settings
        if not settings or not settings.python_executable:
            self.terminal_widget._append_error("Python executable not configured. Set it in Settings.\n")
            return

        self.terminal_widget.run_freqtrade_command("--version", settings=settings)
