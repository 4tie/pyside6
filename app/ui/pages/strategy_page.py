"""strategy_page.py — Strategy management and history page.

Provides a master-detail layout: left panel lists discovered strategy files
with search filtering, right panel shows parameters and run history tabs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
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
from PySide6.QtCore import QSettings

from app.app_state.settings_state import SettingsState
from app.core.backtests.results_index import IndexStore
from app.core.utils.app_logger import get_logger
from app.ui.pages.strategy_config_page import StrategyConfigPage

_log = get_logger("ui.strategy_page")

_QSETTINGS_ORG = "FreqtradeGUI"
_QSETTINGS_APP = "ModernUI"
_SPLITTER_KEY = "splitter/strategy"


class StrategyPage(QWidget):
    """Strategy management page with list, parameters, and history.

    Args:
        settings_state: Application settings state.
        parent: Optional parent widget.

    Signals:
        backtest_requested(str): Emitted when user requests a backtest for a strategy.
        optimize_requested(str): Emitted when user requests optimization for a strategy.
    """

    backtest_requested = Signal(str)
    optimize_requested = Signal(str)

    def __init__(self, settings_state: SettingsState, parent=None) -> None:
        super().__init__(parent)
        self._settings_state = settings_state
        self._build_ui()
        self._connect_signals()
        self.refresh()
        self._restore_state()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the master-detail splitter layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Page title + quick actions toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 12, 16, 8)

        title_label = QLabel("Strategy")
        title_label.setObjectName("page_title")
        toolbar_layout.addWidget(title_label)
        toolbar_layout.addStretch()

        self._backtest_now_btn = QPushButton("Backtest Now")
        self._backtest_now_btn.setObjectName("success")
        self._backtest_now_btn.setAccessibleName("Backtest selected strategy")
        self._backtest_now_btn.setToolTip("Run a backtest for the selected strategy")
        self._backtest_now_btn.setEnabled(False)
        toolbar_layout.addWidget(self._backtest_now_btn)

        self._optimize_now_btn = QPushButton("Optimize Now")
        self._optimize_now_btn.setAccessibleName("Optimize selected strategy")
        self._optimize_now_btn.setToolTip("Run hyperopt for the selected strategy")
        self._optimize_now_btn.setEnabled(False)
        toolbar_layout.addWidget(self._optimize_now_btn)

        root.addWidget(toolbar)

        # Main splitter
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(4)
        root.addWidget(self._splitter)

        # ── Left panel — strategy list ─────────────────────────────────
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search strategies…")
        self._search_edit.setAccessibleName("Strategy search filter")
        self._search_edit.setToolTip("Filter the strategy list by name")
        left_layout.addWidget(self._search_edit)

        self._strategy_list = QListWidget()
        self._strategy_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._strategy_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._strategy_list.setAccessibleName("Strategy list")
        self._strategy_list.setToolTip("Select a strategy to view its details")
        left_layout.addWidget(self._strategy_list)

        left_widget.setMinimumWidth(180)
        self._splitter.addWidget(left_widget)

        # ── Right panel — detail tabs ──────────────────────────────────
        self._detail_tabs = QTabWidget()

        # Parameters tab — reuse StrategyConfigPage
        self._strategy_config = StrategyConfigPage(self._settings_state)
        self._detail_tabs.addTab(self._strategy_config, "Parameters")

        # History tab
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        history_layout.setContentsMargins(8, 8, 8, 8)

        self._history_table = QTableWidget(0, 4)
        self._history_table.setHorizontalHeaderLabels(
            ["Run ID", "Profit %", "Trades", "Date"]
        )
        self._history_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self._history_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self._history_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self._history_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeToContents
        )
        self._history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._history_table.verticalHeader().setVisible(False)
        self._history_table.setAlternatingRowColors(True)
        history_layout.addWidget(self._history_table)

        self._detail_tabs.addTab(history_widget, "History")

        self._splitter.addWidget(self._detail_tabs)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Wire all internal signals."""
        self._strategy_list.currentItemChanged.connect(self._on_strategy_selected)
        self._strategy_list.customContextMenuRequested.connect(self._on_context_menu)
        self._search_edit.textChanged.connect(self._on_search_changed)
        self._backtest_now_btn.clicked.connect(self._on_backtest_now)
        self._optimize_now_btn.clicked.connect(self._on_optimize_now)
        self._settings_state.settings_changed.connect(self._on_settings_changed)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_strategy_selected(self, current: Optional[QListWidgetItem], _=None) -> None:
        """Update detail panel when a strategy is selected."""
        has_selection = current is not None
        self._backtest_now_btn.setEnabled(has_selection)
        self._optimize_now_btn.setEnabled(has_selection)

        if not has_selection:
            return

        strategy_name = current.data(Qt.UserRole)
        if not strategy_name:
            return

        self._refresh_history(strategy_name)
        _log.debug("Strategy selected: %s", strategy_name)

    def _on_context_menu(self, pos) -> None:
        """Show right-click context menu on strategy list."""
        item = self._strategy_list.itemAt(pos)
        if not item:
            return

        strategy_name = item.data(Qt.UserRole)
        menu = QMenu(self)

        backtest_action = QAction("Backtest", self)
        backtest_action.triggered.connect(
            lambda: self.backtest_requested.emit(strategy_name)
        )
        menu.addAction(backtest_action)

        optimize_action = QAction("Optimize", self)
        optimize_action.triggered.connect(
            lambda: self.optimize_requested.emit(strategy_name)
        )
        menu.addAction(optimize_action)

        menu.exec(self._strategy_list.mapToGlobal(pos))

    def _on_search_changed(self, text: str) -> None:
        """Filter strategy list by search text."""
        text_lower = text.lower()
        for i in range(self._strategy_list.count()):
            item = self._strategy_list.item(i)
            strategy_name = item.data(Qt.UserRole) or ""
            item.setHidden(text_lower not in strategy_name.lower())

    def _on_backtest_now(self) -> None:
        """Emit backtest_requested for the selected strategy."""
        strategy = self._selected_strategy()
        if strategy:
            self.backtest_requested.emit(strategy)

    def _on_optimize_now(self) -> None:
        """Emit optimize_requested for the selected strategy."""
        strategy = self._selected_strategy()
        if strategy:
            self.optimize_requested.emit(strategy)

    def _on_settings_changed(self, _=None) -> None:
        """Refresh strategy list when settings change."""
        self.refresh()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Rescan strategies directory and repopulate the list."""
        settings = self._settings_state.current_settings
        if not settings or not settings.user_data_path:
            self._strategy_list.clear()
            _log.debug("No user_data_path — strategy list cleared")
            return

        strategies_dir = Path(settings.user_data_path) / "strategies"
        if not strategies_dir.is_dir():
            self._strategy_list.clear()
            _log.debug("Strategies directory not found: %s", strategies_dir)
            return

        current_strategy = self._selected_strategy()

        self._strategy_list.blockSignals(True)
        self._strategy_list.clear()

        py_files = sorted(
            p for p in strategies_dir.iterdir()
            if p.suffix == ".py" and not p.name.startswith("_")
        )

        for py_file in py_files:
            strategy_name = py_file.stem
            try:
                mtime = py_file.stat().st_mtime
                from datetime import datetime
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
            except Exception:
                mtime_str = ""

            display = f"{strategy_name}  ({mtime_str})" if mtime_str else strategy_name
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, strategy_name)
            self._strategy_list.addItem(item)

        self._strategy_list.blockSignals(False)

        # Restore previous selection
        if current_strategy:
            for i in range(self._strategy_list.count()):
                item = self._strategy_list.item(i)
                if item.data(Qt.UserRole) == current_strategy:
                    self._strategy_list.setCurrentItem(item)
                    break

        _log.debug("Strategy list refreshed: %d strategies", len(py_files))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _selected_strategy(self) -> Optional[str]:
        """Return the currently selected strategy name, or None."""
        item = self._strategy_list.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return None

    def _refresh_history(self, strategy_name: str) -> None:
        """Populate the history table for the given strategy."""
        self._history_table.setRowCount(0)

        settings = self._settings_state.current_settings
        if not settings or not settings.user_data_path:
            return

        backtest_results_dir = str(
            Path(settings.user_data_path) / "backtest_results"
        )

        try:
            runs = IndexStore.get_strategy_runs(backtest_results_dir, strategy_name)
        except Exception as e:
            _log.warning("Failed to load history for %s: %s", strategy_name, e)
            return

        for run in runs:
            row = self._history_table.rowCount()
            self._history_table.insertRow(row)

            run_id = run.get("run_id", "?")
            profit = run.get("profit_total_pct", 0.0)
            trades = run.get("trades_count", 0)
            saved = run.get("saved_at", "")[:16].replace("T", " ")

            self._history_table.setItem(row, 0, QTableWidgetItem(run_id))
            self._history_table.setItem(row, 1, QTableWidgetItem(f"{profit:+.2f}%"))
            self._history_table.setItem(row, 2, QTableWidgetItem(str(trades)))
            self._history_table.setItem(row, 3, QTableWidgetItem(saved))

    def _restore_state(self) -> None:
        """Restore splitter state from QSettings."""
        qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        state = qs.value(_SPLITTER_KEY)
        if state is not None:
            self._splitter.restoreState(state)

    def _save_state(self) -> None:
        """Persist splitter state to QSettings."""
        qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        qs.setValue(_SPLITTER_KEY, self._splitter.saveState())

    def hideEvent(self, event) -> None:  # noqa: N802
        """Save splitter state when page is hidden."""
        self._save_state()
        super().hideEvent(event)
