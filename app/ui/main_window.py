from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QVBoxLayout, QWidget,
    QPushButton, QHBoxLayout, QToolBar,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from app.app_state.settings_state import SettingsState
from app.core.ai.ai_service import AIService
from app.ui.pages.backtest_page import BacktestPage
from app.ui.pages.download_data_page import DownloadDataPage
from app.ui.pages.optimize_page import OptimizePage
from app.ui.pages.strategy_config_page import StrategyConfigPage
from app.ui.widgets.terminal_widget import TerminalWidget
from app.ui.widgets.ai_chat_dock import AIChatDock
from app.core.utils.app_logger import get_logger

_log = get_logger("ui.main_window")

_STYLESHEET = """
    /* ── Base ─────────────────────────────────────────── */
    QMainWindow, QWidget {
        background-color: #1e1e1e;
        color: #d4d4d4;
    }
    QDialog {
        background-color: #252526;
        color: #d4d4d4;
    }

    /* ── Tabs ─────────────────────────────────────────── */
    QTabWidget::pane {
        border: 1px solid #3c3c3c;
        background-color: #1e1e1e;
    }
    QTabBar::tab {
        background-color: #2d2d2d;
        color: #aaaaaa;
        padding: 8px 18px;
        border: none;
        border-bottom: 2px solid transparent;
        font-size: 13px;
    }
    QTabBar::tab:selected {
        background-color: #1e1e1e;
        color: #ffffff;
        border-bottom: 2px solid #007acc;
    }
    QTabBar::tab:hover:!selected {
        background-color: #3c3c3c;
        color: #cccccc;
    }

    /* ── Toolbar ──────────────────────────────────────── */
    QToolBar {
        background-color: #2d2d2d;
        border-bottom: 1px solid #3c3c3c;
        spacing: 6px;
        padding: 3px 6px;
    }
    QToolBar QToolButton {
        background-color: transparent;
        color: #cccccc;
        border: none;
        padding: 4px 10px;
        border-radius: 3px;
        font-size: 13px;
    }
    QToolBar QToolButton:hover {
        background-color: #3c3c3c;
        color: #ffffff;
    }

    /* ── Buttons ──────────────────────────────────────── */
    QPushButton {
        background-color: #0e639c;
        color: #ffffff;
        border: none;
        padding: 6px 16px;
        border-radius: 4px;
        font-size: 13px;
        font-weight: 500;
    }
    QPushButton:hover {
        background-color: #1177bb;
    }
    QPushButton:pressed {
        background-color: #0a4f7e;
    }
    QPushButton:disabled {
        background-color: #2d2d2d;
        color: #666666;
        border: 1px solid #3c3c3c;
    }

    /* Danger / destructive buttons — use object name "danger" */
    QPushButton#danger {
        background-color: #c72e2e;
        color: #ffffff;
    }
    QPushButton#danger:hover {
        background-color: #e03333;
    }

    /* Secondary / ghost buttons — use object name "secondary" */
    QPushButton#secondary {
        background-color: transparent;
        color: #9cdcfe;
        border: 1px solid #3c3c3c;
    }
    QPushButton#secondary:hover {
        background-color: #2d2d2d;
        border-color: #007acc;
    }

    /* Success buttons — use object name "success" */
    QPushButton#success {
        background-color: #1a7a3c;
        color: #ffffff;
    }
    QPushButton#success:hover {
        background-color: #1e9147;
    }

    /* ── Inputs ───────────────────────────────────────── */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {
        background-color: #3c3c3c;
        color: #d4d4d4;
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 5px 8px;
        font-size: 13px;
        selection-background-color: #264f78;
    }
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
    QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {
        border: 1px solid #007acc;
        background-color: #3c3c3c;
    }
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
    QComboBox QAbstractItemView {
        background-color: #3c3c3c;
        color: #d4d4d4;
        selection-background-color: #094771;
        border: 1px solid #555555;
    }
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
        background-color: #555555;
        border: none;
        width: 16px;
    }

    /* ── Labels ───────────────────────────────────────── */
    QLabel {
        color: #d4d4d4;
        background-color: transparent;
    }

    /* ── Checkboxes ───────────────────────────────────── */
    QCheckBox {
        color: #d4d4d4;
        spacing: 6px;
    }
    QCheckBox::indicator {
        width: 14px;
        height: 14px;
        border: 1px solid #555555;
        border-radius: 3px;
        background-color: #3c3c3c;
    }
    QCheckBox::indicator:checked {
        background-color: #007acc;
        border-color: #007acc;
    }

    /* ── GroupBox ─────────────────────────────────────── */
    QGroupBox {
        color: #9cdcfe;
        border: 1px solid #3c3c3c;
        border-radius: 5px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: 600;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
    }

    /* ── Lists ────────────────────────────────────────── */
    QListWidget {
        background-color: #2d2d2d;
        color: #d4d4d4;
        border: 1px solid #3c3c3c;
        border-radius: 4px;
    }
    QListWidget::item:selected {
        background-color: #094771;
        color: #ffffff;
    }
    QListWidget::item:hover {
        background-color: #3c3c3c;
    }

    /* ── Scrollbars ───────────────────────────────────── */
    QScrollBar:vertical {
        background-color: #1e1e1e;
        width: 10px;
        border: none;
    }
    QScrollBar::handle:vertical {
        background-color: #555555;
        border-radius: 5px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #777777;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    QScrollBar:horizontal {
        background-color: #1e1e1e;
        height: 10px;
        border: none;
    }
    QScrollBar::handle:horizontal {
        background-color: #555555;
        border-radius: 5px;
        min-width: 20px;
    }
    QScrollBar::handle:horizontal:hover {
        background-color: #777777;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0;
    }

    /* ── Dock ─────────────────────────────────────────── */
    QDockWidget {
        color: #d4d4d4;
        titlebar-close-icon: none;
    }
    QDockWidget::title {
        background-color: #2d2d2d;
        color: #cccccc;
        padding: 5px 8px;
        border-bottom: 1px solid #3c3c3c;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* ── MenuBar ──────────────────────────────────────── */
    QMenuBar {
        background-color: #2d2d2d;
        color: #cccccc;
        border-bottom: 1px solid #3c3c3c;
    }
    QMenuBar::item:selected {
        background-color: #3c3c3c;
    }
    QMenu {
        background-color: #2d2d2d;
        color: #d4d4d4;
        border: 1px solid #3c3c3c;
    }
    QMenu::item:selected {
        background-color: #094771;
    }

    /* ── Misc ─────────────────────────────────────────── */
    QScrollArea {
        border: none;
        background-color: transparent;
    }
    QSplitter::handle {
        background-color: #3c3c3c;
    }
    QToolTip {
        background-color: #3c3c3c;
        color: #d4d4d4;
        border: 1px solid #555555;
        padding: 4px;
        border-radius: 3px;
    }
    QMessageBox {
        background-color: #252526;
        color: #d4d4d4;
    }
    QDialogButtonBox QPushButton {
        min-width: 80px;
    }
"""


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, settings_state: SettingsState = None):
        super().__init__()
        self.setWindowTitle("Freqtrade GUI")
        self.setMinimumSize(1200, 800)
        self.showMaximized()

        self.setStyleSheet(_STYLESHEET)

        # Initialize state
        if settings_state is None:
            settings_state = SettingsState()
            settings_state.load_settings()

        self.settings_state = settings_state

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
        toolbar.setStyleSheet(
            "QToolBar { background-color: #2d2d2d; border-bottom: 1px solid #3c3c3c; padding: 4px 8px; spacing: 8px; }"
        )
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        # App title label
        from PySide6.QtWidgets import QLabel
        title_label = QLabel("Freqtrade GUI")
        title_label.setStyleSheet(
            "color: #ffffff; font-size: 14px; font-weight: 600; padding: 0 8px;"
        )
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
