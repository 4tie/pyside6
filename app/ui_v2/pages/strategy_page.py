"""StrategyPage for the v2 UI layer.

Master-detail layout: left panel shows strategy list with search, right panel
shows tabbed detail view with Parameters (reuses StrategyConfigPage) and
History (run history from IndexStore).

Requirements: 6.1, 6.2, 6.3, 6.5, 6.6, 8.6
"""
import os
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.app_state.settings_state import SettingsState
from app.core.backtests.results_index import IndexStore
from app.core.freqtrade.resolvers.strategy_resolver import list_strategies
from app.core.utils.app_logger import get_logger
from app.ui.pages.strategy_config_page import StrategyConfigPage

_log = get_logger("ui_v2.pages.strategy_page")

_SETTINGS_KEY = "splitter/strategy"


class StrategyPage(QWidget):
    """Master-detail strategy management page.

    Left panel: QListWidget of strategies with search QLineEdit at top.
    Each item shows: strategy name, last modified, last backtest profit.

    Right panel: QTabWidget with:
    - "Parameters" tab: reuses StrategyConfigPage form
    - "History" tab: run history QTableWidget from IndexStore

    Quick Actions toolbar above right panel: "Backtest Now", "Optimize Now" buttons.
    Right-click context menu on strategy list: Backtest, Optimize, Edit.

    Args:
        settings_state: Application settings state.
        parent: Optional parent widget.

    Signals:
        backtest_requested(str): Emitted when "Backtest Now" is clicked with strategy name.
        optimize_requested(str): Emitted when "Optimize Now" is clicked with strategy name.
    """

    backtest_requested = Signal(str)
    optimize_requested = Signal(str)

    def __init__(self, settings_state: SettingsState, parent=None) -> None:
        super().__init__(parent)

        self.settings_state = settings_state
        self._current_strategy: Optional[str] = None

        self._build_ui()
        self._connect_signals()
        self.refresh()
        self._restore_splitter()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the splitter-based master-detail layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(4)
        self._splitter.setChildrenCollapsible(False)

        # ── Left panel ────────────────────────────────────────────────
        left_widget = self._build_left_panel()
        self._splitter.addWidget(left_widget)

        # ── Right panel ───────────────────────────────────────────────
        right_widget = self._build_right_panel()
        self._splitter.addWidget(right_widget)

        # Default proportions: 35% left, 65% right
        self._splitter.setStretchFactor(0, 35)
        self._splitter.setStretchFactor(1, 65)

        root.addWidget(self._splitter)

    def _build_left_panel(self) -> QWidget:
        """Build the left strategy list panel.

        Returns:
            Widget containing search field and strategy list.
        """
        left = QWidget()
        layout = QVBoxLayout(left)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Page title
        title = QLabel("Strategies")
        title.setObjectName("page_title")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # Search field
        self._search_field = QLineEdit()
        self._search_field.setPlaceholderText("Search strategies...")
        self._search_field.setAccessibleName("Search strategies")
        self._search_field.setToolTip("Filter strategies by name")
        self._search_field.textChanged.connect(self._filter_strategies)
        layout.addWidget(self._search_field)

        # Strategy list
        self._strategy_list = QListWidget()
        self._strategy_list.setAccessibleName("Strategy list")
        self._strategy_list.setToolTip("Select a strategy to view details")
        self._strategy_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._strategy_list.customContextMenuRequested.connect(self._show_context_menu)
        self._strategy_list.currentItemChanged.connect(self._on_strategy_selected)
        layout.addWidget(self._strategy_list)

        left.setMinimumWidth(250)
        return left

    def _build_right_panel(self) -> QWidget:
        """Build the right detail panel.

        Returns:
            Widget containing quick actions toolbar and tabbed detail view.
        """
        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Quick Actions toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        toolbar.addWidget(QLabel("Quick Actions:"))

        self._backtest_btn = QPushButton("Backtest Now")
        self._backtest_btn.setAccessibleName("Backtest selected strategy")
        self._backtest_btn.setToolTip("Run backtest with the selected strategy")
        self._backtest_btn.setEnabled(False)
        self._backtest_btn.clicked.connect(self._on_backtest_now)
        toolbar.addWidget(self._backtest_btn)

        self._optimize_btn = QPushButton("Optimize Now")
        self._optimize_btn.setAccessibleName("Optimize selected strategy")
        self._optimize_btn.setToolTip("Run optimization with the selected strategy")
        self._optimize_btn.setEnabled(False)
        self._optimize_btn.clicked.connect(self._on_optimize_now)
        toolbar.addWidget(self._optimize_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Tabbed detail view
        self._detail_tabs = QTabWidget()

        # Parameters tab - reuse StrategyConfigPage
        self._params_page = StrategyConfigPage(self.settings_state)
        self._detail_tabs.addTab(self._params_page, "Parameters")

        # History tab - run history table
        self._history_table = self._build_history_table()
        self._detail_tabs.addTab(self._history_table, "History")

        layout.addWidget(self._detail_tabs)

        return right

    def _build_history_table(self) -> QWidget:
        """Build the history tab with run history table.

        Returns:
            Widget containing the history table.
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._history_widget = QTableWidget(0, 6)
        self._history_widget.setHorizontalHeaderLabels([
            "Run ID", "Timeframe", "Profit %", "Trades", "Win Rate %", "Saved At"
        ])
        self._history_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._history_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._history_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._history_widget.setAlternatingRowColors(True)
        self._history_widget.setAccessibleName("Strategy run history")
        self._history_widget.setToolTip("Historical backtest runs for this strategy")
        layout.addWidget(self._history_widget)

        return container

    # ------------------------------------------------------------------
    # Signal Wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Wire internal signals for live updates."""
        self.settings_state.settings_changed.connect(self._on_settings_changed)

    def _on_settings_changed(self, _settings) -> None:
        """Refresh strategy list when settings change."""
        self.refresh()

    # ------------------------------------------------------------------
    # Strategy List Management
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload strategy list from strategies/ directory.

        Public method called by ModernMainWindow when needed.
        """
        _log.info("StrategyPage.refresh called")
        self._strategy_list.clear()

        settings = self.settings_state.current_settings
        if not settings or not settings.user_data_path:
            _log.debug("No user_data_path configured, strategy list empty")
            return

        user_data = Path(settings.user_data_path).expanduser().resolve()
        strategies_dir = user_data / "strategies"

        if not strategies_dir.exists():
            _log.debug("Strategies directory does not exist: %s", strategies_dir)
            return

        strategies = list_strategies(user_data)
        backtest_results_dir = str(user_data / "backtest_results")

        for strategy_name in strategies:
            strategy_path = strategies_dir / f"{strategy_name}.py"
            
            # Get last modified timestamp
            try:
                mtime = strategy_path.stat().st_mtime
                import datetime
                last_modified = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            except Exception:
                last_modified = "Unknown"

            # Get last backtest profit from index
            runs = IndexStore.get_strategy_runs(backtest_results_dir, strategy_name)
            last_profit = "—"
            if runs:
                last_profit = f"{runs[0].get('profit_total_pct', 0):+.2f}%"

            # Create list item with metadata
            display_text = f"{strategy_name}\n  Modified: {last_modified}  |  Last profit: {last_profit}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, strategy_name)
            self._strategy_list.addItem(item)

        _log.info("Loaded %d strategies", len(strategies))

    def _filter_strategies(self, search_text: str) -> None:
        """Filter strategy list based on search text.

        Args:
            search_text: Search query string.
        """
        search_lower = search_text.lower()
        for i in range(self._strategy_list.count()):
            item = self._strategy_list.item(i)
            strategy_name = item.data(Qt.UserRole)
            item.setHidden(search_lower not in strategy_name.lower())

    def _on_strategy_selected(self, current: QListWidgetItem, _previous: QListWidgetItem) -> None:
        """Handle strategy selection change.

        Args:
            current: Currently selected item.
            _previous: Previously selected item (unused).
        """
        if not current:
            self._current_strategy = None
            self._backtest_btn.setEnabled(False)
            self._optimize_btn.setEnabled(False)
            self._history_widget.setRowCount(0)
            return

        strategy_name = current.data(Qt.UserRole)
        self._current_strategy = strategy_name
        self._backtest_btn.setEnabled(True)
        self._optimize_btn.setEnabled(True)

        _log.debug("Strategy selected: %s", strategy_name)

        # Update history table
        self._load_history(strategy_name)

        # Update parameters tab - trigger combo selection in StrategyConfigPage
        # Find the strategy in the combo and select it
        combo = self._params_page.strategy_combo
        idx = combo.findText(strategy_name)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _load_history(self, strategy_name: str) -> None:
        """Load run history for the selected strategy.

        Args:
            strategy_name: Name of the strategy to load history for.
        """
        settings = self.settings_state.current_settings
        if not settings or not settings.user_data_path:
            return

        backtest_results_dir = str(
            Path(settings.user_data_path).expanduser().resolve() / "backtest_results"
        )
        runs = IndexStore.get_strategy_runs(backtest_results_dir, strategy_name)

        self._history_widget.setRowCount(0)
        for run in runs:
            row = self._history_widget.rowCount()
            self._history_widget.insertRow(row)

            run_id = run.get("run_id", "")[:16]  # Truncate for display
            timeframe = run.get("timeframe", "")
            profit = run.get("profit_total_pct", 0)
            trades = run.get("trades_count", 0)
            win_rate = run.get("win_rate_pct", 0)
            saved_at = run.get("saved_at", "")[:16]  # Truncate timestamp

            self._history_widget.setItem(row, 0, QTableWidgetItem(run_id))
            self._history_widget.setItem(row, 1, QTableWidgetItem(timeframe))
            self._history_widget.setItem(row, 2, QTableWidgetItem(f"{profit:+.2f}"))
            self._history_widget.setItem(row, 3, QTableWidgetItem(str(trades)))
            self._history_widget.setItem(row, 4, QTableWidgetItem(f"{win_rate:.1f}"))
            self._history_widget.setItem(row, 5, QTableWidgetItem(saved_at))

        _log.debug("Loaded %d runs for strategy %s", len(runs), strategy_name)

    # ------------------------------------------------------------------
    # Context Menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        """Show right-click context menu on strategy list.

        Args:
            pos: Position where the context menu was requested.
        """
        item = self._strategy_list.itemAt(pos)
        if not item:
            return

        strategy_name = item.data(Qt.UserRole)

        menu = QMenu(self)

        backtest_action = menu.addAction("Backtest")
        backtest_action.triggered.connect(lambda: self._emit_backtest(strategy_name))

        optimize_action = menu.addAction("Optimize")
        optimize_action.triggered.connect(lambda: self._emit_optimize(strategy_name))

        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda: self._open_strategy_file(strategy_name))

        menu.exec(self._strategy_list.mapToGlobal(pos))

    def _emit_backtest(self, strategy_name: str) -> None:
        """Emit backtest_requested signal.

        Args:
            strategy_name: Name of the strategy to backtest.
        """
        _log.info("Backtest requested for strategy: %s", strategy_name)
        self.backtest_requested.emit(strategy_name)

    def _emit_optimize(self, strategy_name: str) -> None:
        """Emit optimize_requested signal.

        Args:
            strategy_name: Name of the strategy to optimize.
        """
        _log.info("Optimize requested for strategy: %s", strategy_name)
        self.optimize_requested.emit(strategy_name)

    def _open_strategy_file(self, strategy_name: str) -> None:
        """Open strategy file in system default editor.

        Args:
            strategy_name: Name of the strategy to edit.
        """
        settings = self.settings_state.current_settings
        if not settings or not settings.user_data_path:
            return

        strategy_path = (
            Path(settings.user_data_path).expanduser().resolve()
            / "strategies"
            / f"{strategy_name}.py"
        )

        if not strategy_path.exists():
            _log.warning("Strategy file not found: %s", strategy_path)
            return

        _log.info("Opening strategy file: %s", strategy_path)

        # Open with system default editor
        try:
            if os.name == "nt":  # Windows
                os.startfile(str(strategy_path))
            elif os.name == "posix":  # macOS, Linux
                import subprocess
                subprocess.run(["xdg-open", str(strategy_path)], check=False)
        except Exception as e:
            _log.error("Failed to open strategy file: %s", e)

    # ------------------------------------------------------------------
    # Quick Actions
    # ------------------------------------------------------------------

    def _on_backtest_now(self) -> None:
        """Handle "Backtest Now" button click."""
        if self._current_strategy:
            self._emit_backtest(self._current_strategy)

    def _on_optimize_now(self) -> None:
        """Handle "Optimize Now" button click."""
        if self._current_strategy:
            self._emit_optimize(self._current_strategy)

    # ------------------------------------------------------------------
    # Splitter Persistence
    # ------------------------------------------------------------------

    def _restore_splitter(self) -> None:
        """Restore splitter state from QSettings."""
        qs = QSettings("FreqtradeGUI", "ModernUI")
        state = qs.value(_SETTINGS_KEY)
        if state:
            self._splitter.restoreState(state)
            _log.debug("Splitter state restored")

    def _save_splitter(self) -> None:
        """Persist splitter state to QSettings."""
        qs = QSettings("FreqtradeGUI", "ModernUI")
        qs.setValue(_SETTINGS_KEY, self._splitter.saveState())
        _log.debug("Splitter state saved")

    def closeEvent(self, event) -> None:  # noqa: N802
        """Save splitter state on close."""
        self._save_splitter()
        super().closeEvent(event)
