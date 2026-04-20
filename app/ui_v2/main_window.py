"""ModernMainWindow — top-level shell for the v2 UI layer.

Replaces ``MainWindow`` with a sidebar-navigation shell built from
``NavSidebar``, ``QStackedWidget``, ``HeaderBar``, ``AppStatusBar``, and
dockable ``TerminalPanel`` / ``AiPanel``.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 2.4, 8.1, 8.2,
              11.2, 18.4, 18.5, 20.1
"""
from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.app_state.settings_state import SettingsState
from app.core.ai.ai_service import AIService
from app.core.utils.app_logger import get_logger
from app.ui_v2.panels.ai_panel import AiPanel
from app.ui_v2.panels.terminal_panel import TerminalPanel
from app.ui_v2.pages.backtest_page import BacktestPage
from app.ui_v2.pages.dashboard_page import DashboardPage
from app.ui_v2.pages.download_page import DownloadPage
from app.ui_v2.pages.optimize_page import OptimizePage
from app.ui_v2.pages.settings_page import SettingsPage
from app.ui_v2.pages.strategy_page import StrategyPage
from app.ui_v2.shell.header_bar import HeaderBar
from app.ui_v2.shell.sidebar import NavSidebar
from app.ui_v2.shell.status_bar import AppStatusBar
from app.ui_v2.theme import (
    FONT,
    PALETTE,
    SPACING,
    ThemeMode,
    _LIGHT_PALETTE,
    build_stylesheet,
    build_v2_additions,
)
from app.ui_v2.widgets.command_palette import CommandPalette
from app.ui_v2.widgets.onboarding_wizard import OnboardingWizard

_log = get_logger("ui_v2.main_window")

# ---------------------------------------------------------------------------
# Page registry: (page_id, title, index)
# ---------------------------------------------------------------------------

_PAGE_DEFS: List[tuple[str, str]] = [
    ("dashboard", "Dashboard"),
    ("backtest", "Backtest"),
    ("optimize", "Optimize"),
    ("download", "Download Data"),
    ("strategy", "Strategy"),
    ("settings", "Settings"),
]

_QSETTINGS_APP = "FreqtradeGUI"
_QSETTINGS_ORG = "ModernUI"


class ModernMainWindow(QMainWindow):
    """Modern sidebar-navigation main window for the v2 UI layer.

    Args:
        settings_state: Application settings state.  If ``None`` a new
            ``SettingsState`` is created and settings are loaded from disk.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        settings_state: Optional[SettingsState] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Freqtrade GUI")
        self.setMinimumSize(1024, 600)

        # ── Settings state ────────────────────────────────────────────
        if settings_state is None:
            settings_state = SettingsState()
            settings_state.load_settings()
        self.settings_state = settings_state

        # ── Apply initial stylesheet ──────────────────────────────────
        self._current_theme_mode: ThemeMode = ThemeMode.DARK
        _mode_str = (
            settings_state.current_settings.theme_mode
            if settings_state.current_settings
            else "dark"
        )
        if _mode_str == "light":
            self._current_theme_mode = ThemeMode.LIGHT
        self._apply_stylesheet(self._current_theme_mode)

        # ── AI service ────────────────────────────────────────────────
        self.ai_service = AIService(settings_state)

        # ── Build UI ──────────────────────────────────────────────────
        self._build_ui()

        # ── Wire signals ──────────────────────────────────────────────
        self._wire_signals()

        # ── Register keyboard shortcuts ───────────────────────────────
        self._register_shortcuts()

        # ── Build command palette ─────────────────────────────────────
        self._command_palette: Optional[CommandPalette] = None
        self._build_command_palette()

        # ── Restore geometry / state ──────────────────────────────────
        self._restore_geometry()

        # ── Show maximised ────────────────────────────────────────────
        self.showMaximized()

        # ── Trigger onboarding if venv not configured ─────────────────
        QTimer.singleShot(0, self._maybe_show_onboarding)

        _log.info("ModernMainWindow initialised")

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the main window layout."""
        # ── Central widget wrapper ────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────
        self.header_bar = HeaderBar(parent=central)
        root_layout.addWidget(self.header_bar)

        # ── Body: sidebar + stacked widget ───────────────────────────
        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.nav_sidebar = NavSidebar(parent=body_widget)
        body_layout.addWidget(self.nav_sidebar)

        self.stacked_widget = QStackedWidget()
        body_layout.addWidget(self.stacked_widget, 1)

        root_layout.addWidget(body_widget, 1)

        # ── Status bar ────────────────────────────────────────────────
        self.app_status_bar = AppStatusBar(parent=central)
        root_layout.addWidget(self.app_status_bar)

        # ── Pages ─────────────────────────────────────────────────────
        self._pages: Dict[str, QWidget] = {}
        self._page_titles: Dict[str, str] = {pid: title for pid, title in _PAGE_DEFS}

        self.dashboard_page = DashboardPage(self.settings_state)
        self.backtest_page = BacktestPage(self.settings_state)
        self.optimize_page = OptimizePage(self.settings_state)
        self.download_page = DownloadPage(self.settings_state)
        self.strategy_page = StrategyPage(self.settings_state)
        self.settings_page = SettingsPage(self.settings_state)

        for page_id, page in [
            ("dashboard", self.dashboard_page),
            ("backtest", self.backtest_page),
            ("optimize", self.optimize_page),
            ("download", self.download_page),
            ("strategy", self.strategy_page),
            ("settings", self.settings_page),
        ]:
            self._pages[page_id] = page
            self.stacked_widget.addWidget(page)

        # ── Dock widgets ──────────────────────────────────────────────
        self.terminal_panel = TerminalPanel(parent=self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.terminal_panel)

        self.ai_panel = AiPanel(
            settings_state=self.settings_state,
            parent=self,
            ai_service=self.ai_service,
        )
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_panel)

        # ── Navigate to default page ──────────────────────────────────
        self._navigate_to("dashboard")

    # ------------------------------------------------------------------
    # Signal Wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        """Wire all Qt signals — mirrors the wiring in the original MainWindow."""
        # Nav sidebar → page switch
        self.nav_sidebar.nav_item_clicked.connect(self._navigate_to)

        # Header bar → command palette / settings / theme
        self.header_bar.command_palette_requested.connect(self._show_command_palette)
        self.header_bar.settings_requested.connect(lambda: self._navigate_to("settings"))
        self.header_bar.theme_changed.connect(self._on_theme_changed)

        # Settings state → on_settings_saved
        self.settings_state.settings_saved.connect(self._on_settings_saved)

        # Backtest loop_completed → strategy_page.refresh
        self.backtest_page.loop_completed.connect(self.strategy_page.refresh)

        # AI service → backtest service
        backtest_service = getattr(self.backtest_page, "_backtest_service", None)
        if backtest_service is not None:
            self.ai_service.connect_backtest_service(backtest_service)

        # Give AIService a reference to the live BacktestPage
        if hasattr(self.ai_service, "set_backtest_page"):
            self.ai_service.set_backtest_page(self.backtest_page)

        # Dashboard quick-action signals
        self.dashboard_page.navigate_to.connect(self._navigate_to)
        self.dashboard_page.run_last_backtest.connect(
            lambda: self._navigate_to("backtest")
        )

        # Strategy page quick-action signals
        self.strategy_page.backtest_requested.connect(self._on_strategy_backtest)
        self.strategy_page.optimize_requested.connect(self._on_strategy_optimize)

        _log.debug("All signals wired")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigate_to(self, page_id: str) -> None:
        """Switch the active page.

        Args:
            page_id: One of the registered page ids.
        """
        page = self._pages.get(page_id)
        if page is None:
            _log.warning("Unknown page_id: %r", page_id)
            return

        self.stacked_widget.setCurrentWidget(page)
        title = self._page_titles.get(page_id, page_id.capitalize())
        self.header_bar.set_page_title(title)
        self.nav_sidebar.set_active(page_id)
        self.app_status_bar.set_status(f"Navigated to {title}", level="info")

        _log.debug("Navigated to page: %s", page_id)

    # ------------------------------------------------------------------
    # Keyboard Shortcuts
    # ------------------------------------------------------------------

    def _register_shortcuts(self) -> None:
        """Register all keyboard shortcuts via QShortcut."""
        # Ctrl+1 – Ctrl+6: navigate to pages in order
        page_ids = [pid for pid, _ in _PAGE_DEFS]
        for i, page_id in enumerate(page_ids, start=1):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            shortcut.activated.connect(
                lambda pid=page_id: self._navigate_to(pid)
            )

        # Ctrl+P: command palette
        sc_cmd = QShortcut(QKeySequence("Ctrl+P"), self)
        sc_cmd.activated.connect(self._show_command_palette)

        # Ctrl+`: toggle terminal panel
        sc_terminal = QShortcut(QKeySequence("Ctrl+`"), self)
        sc_terminal.activated.connect(self._toggle_terminal_panel)

        # Ctrl+Shift+A: toggle AI chat panel
        sc_ai = QShortcut(QKeySequence("Ctrl+Shift+A"), self)
        sc_ai.activated.connect(self._toggle_ai_panel)

        # F5: re-run last backtest (navigate to backtest page)
        sc_f5 = QShortcut(QKeySequence("F5"), self)
        sc_f5.activated.connect(lambda: self._navigate_to("backtest"))

        _log.debug("Keyboard shortcuts registered")

    # ------------------------------------------------------------------
    # Command Palette
    # ------------------------------------------------------------------

    def _build_command_palette(self) -> None:
        """Build the CommandPalette with all registered commands."""
        commands: List[dict] = [
            {
                "id": "nav_dashboard",
                "label": "Go to Dashboard",
                "shortcut": "Ctrl+1",
                "action": lambda: self._navigate_to("dashboard"),
            },
            {
                "id": "nav_backtest",
                "label": "Go to Backtest",
                "shortcut": "Ctrl+2",
                "action": lambda: self._navigate_to("backtest"),
            },
            {
                "id": "nav_optimize",
                "label": "Go to Optimize",
                "shortcut": "Ctrl+3",
                "action": lambda: self._navigate_to("optimize"),
            },
            {
                "id": "nav_download",
                "label": "Go to Download Data",
                "shortcut": "Ctrl+4",
                "action": lambda: self._navigate_to("download"),
            },
            {
                "id": "nav_strategy",
                "label": "Go to Strategy",
                "shortcut": "Ctrl+5",
                "action": lambda: self._navigate_to("strategy"),
            },
            {
                "id": "nav_settings",
                "label": "Go to Settings",
                "shortcut": "Ctrl+6",
                "action": lambda: self._navigate_to("settings"),
            },
            {
                "id": "toggle_terminal",
                "label": "Toggle Terminal Panel",
                "shortcut": "Ctrl+`",
                "action": self._toggle_terminal_panel,
            },
            {
                "id": "toggle_ai",
                "label": "Toggle AI Chat Panel",
                "shortcut": "Ctrl+Shift+A",
                "action": self._toggle_ai_panel,
            },
            {
                "id": "run_backtest",
                "label": "Re-run Last Backtest",
                "shortcut": "F5",
                "action": lambda: self._navigate_to("backtest"),
            },
        ]

        self._command_palette = CommandPalette(commands=commands, parent=self)
        _log.debug("CommandPalette built with %d commands", len(commands))

    def _show_command_palette(self) -> None:
        """Show the command palette dialog centred on the main window."""
        if self._command_palette is None:
            return
        # Centre over the main window
        geo = self.geometry()
        cp_width = self._command_palette.minimumWidth()
        x = geo.x() + (geo.width() - cp_width) // 2
        y = geo.y() + geo.height() // 4
        self._command_palette.move(x, y)
        self._command_palette.exec()

    # ------------------------------------------------------------------
    # Panel Toggles
    # ------------------------------------------------------------------

    def _toggle_terminal_panel(self) -> None:
        """Toggle the terminal dock widget visibility."""
        if self.terminal_panel.isVisible():
            self.terminal_panel.hide()
        else:
            self.terminal_panel.show()

    def _toggle_ai_panel(self) -> None:
        """Toggle the AI chat dock widget visibility."""
        if self.ai_panel.isVisible():
            self.ai_panel.hide()
        else:
            self.ai_panel.show()

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_stylesheet(self, mode: ThemeMode) -> None:
        """Build and apply the combined stylesheet for the given theme mode.

        Args:
            mode: The ``ThemeMode`` to apply.
        """
        palette = PALETTE if mode == ThemeMode.DARK else _LIGHT_PALETTE
        qss = build_stylesheet(mode) + build_v2_additions(palette, SPACING, FONT)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss)
        self._current_theme_mode = mode

    def _on_theme_changed(self, mode: ThemeMode) -> None:
        """Handle theme toggle from HeaderBar.

        Args:
            mode: The new ``ThemeMode``.
        """
        self._apply_stylesheet(mode)
        _log.info("Theme changed to %s", mode.value)

    # ------------------------------------------------------------------
    # Settings Saved
    # ------------------------------------------------------------------

    def _on_settings_saved(self, settings) -> None:
        """Re-apply terminal preferences and theme when settings are saved.

        Args:
            settings: The newly saved ``AppSettings`` instance.
        """
        # Re-apply theme if theme_mode changed
        mode_str = getattr(settings, "theme_mode", "dark")
        new_mode = ThemeMode.LIGHT if mode_str == "light" else ThemeMode.DARK
        if new_mode != self._current_theme_mode:
            self._apply_stylesheet(new_mode)

        # Apply terminal preferences to the global terminal panel
        prefs = getattr(settings, "terminal_preferences", None)
        if prefs is not None:
            self.terminal_panel.terminal.apply_preferences(prefs)

        self.app_status_bar.set_status("Settings saved", level="success")
        _log.info("Settings saved — theme=%s", mode_str)

    # ------------------------------------------------------------------
    # Strategy page quick-action handlers
    # ------------------------------------------------------------------

    def _on_strategy_backtest(self, strategy_name: str) -> None:
        """Navigate to backtest page and pre-select the strategy.

        Args:
            strategy_name: Name of the strategy to backtest.
        """
        self._navigate_to("backtest")
        cfg = self.backtest_page.run_config_form.get_config()
        cfg["strategy"] = strategy_name
        self.backtest_page.run_config_form.set_config(cfg)

    def _on_strategy_optimize(self, strategy_name: str) -> None:
        """Navigate to optimize page and pre-select the strategy.

        Args:
            strategy_name: Name of the strategy to optimize.
        """
        self._navigate_to("optimize")
        cfg = self.optimize_page.run_config_form.get_config()
        cfg["strategy"] = strategy_name
        self.optimize_page.run_config_form.set_config(cfg)

    # ------------------------------------------------------------------
    # Onboarding
    # ------------------------------------------------------------------

    def _maybe_show_onboarding(self) -> None:
        """Show the OnboardingWizard if venv_path is not configured."""
        settings = self.settings_state.current_settings
        venv_path = getattr(settings, "venv_path", None) if settings else None
        if not venv_path:
            _log.info("venv_path not configured — showing OnboardingWizard")
            wizard = OnboardingWizard(settings_state=self.settings_state, parent=self)
            wizard.exec()

    # ------------------------------------------------------------------
    # Geometry / State Persistence
    # ------------------------------------------------------------------

    def _restore_geometry(self) -> None:
        """Restore window geometry, dock state, sidebar, and last page."""
        qs = QSettings(_QSETTINGS_APP, _QSETTINGS_ORG)

        geometry = qs.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        window_state = qs.value("windowState")
        if window_state:
            self.restoreState(window_state)

        sidebar_collapsed = qs.value("sidebar/collapsed", False, type=bool)
        if sidebar_collapsed and not self.nav_sidebar.is_collapsed():
            self.nav_sidebar._toggle_collapse()

        last_page = qs.value("lastPage", "dashboard")
        if last_page in self._pages:
            self._navigate_to(last_page)

        _log.debug("Geometry restored (lastPage=%s)", last_page)

    def _save_geometry(self) -> None:
        """Persist window geometry, dock state, sidebar, and last page."""
        qs = QSettings(_QSETTINGS_APP, _QSETTINGS_ORG)

        qs.setValue("geometry", self.saveGeometry())
        qs.setValue("windowState", self.saveState())
        qs.setValue("sidebar/collapsed", self.nav_sidebar.is_collapsed())

        # Determine current page id
        current_widget = self.stacked_widget.currentWidget()
        current_page_id = "dashboard"
        for pid, page in self._pages.items():
            if page is current_widget:
                current_page_id = pid
                break
        qs.setValue("lastPage", current_page_id)

        _log.debug("Geometry saved (lastPage=%s)", current_page_id)

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        """Save geometry and state before closing.

        Args:
            event: The close event.
        """
        self._save_geometry()
        super().closeEvent(event)
