from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
)
from PySide6.QtCore import Qt

from app.app_state.settings_state import SettingsState
from app.ui.pages.settings_page import SettingsPage
from app.ui.widgets.terminal_widget import TerminalWidget


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Freqtrade GUI")
        self.setGeometry(100, 100, 1200, 800)

        # Initialize state
        self.settings_state = SettingsState()
        self.settings_state.load_settings()

        # Create central widget with tabs
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout()

        # Tab widget
        self.tabs = QTabWidget()

        # Settings tab
        self.settings_page = SettingsPage(self.settings_state)
        self.tabs.addTab(self.settings_page, "Settings")

        # Terminal tab
        self.terminal_widget = TerminalWidget()
        terminal_page = self._create_terminal_tab()
        self.tabs.addTab(terminal_page, "Terminal")

        layout.addWidget(self.tabs)
        self.central_widget.setLayout(layout)

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

        version_btn = QPushButton("Freqtrade --version")
        version_btn.clicked.connect(self._freqtrade_version)
        button_layout.addWidget(version_btn)

        button_layout.addStretch()
        tab_layout.addLayout(button_layout)

        # Terminal widget
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

    def _freqtrade_version(self):
        """Run freqtrade --version."""
        settings = self.settings_state.current_settings
        if not settings or not settings.python_executable:
            self.terminal_widget._append_error("Python executable not configured. Set it in Settings.\n")
            return

        self.terminal_widget.run_freqtrade_command("--version", settings=settings)
