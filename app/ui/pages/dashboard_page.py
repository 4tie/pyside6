"""dashboard_page.py — Dashboard overview page for the Freqtrade GUI.

Displays key metrics from the most recent backtest run, a list of recent
runs, and quick-action buttons for common navigation targets.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.app_state.settings_state import SettingsState
from app.core.services.backtest_service import BacktestService
from app.core.utils.app_logger import get_logger
from app.ui.widgets.metric_card import MetricCard

_log = get_logger("ui.dashboard_page")


class DashboardPage(QWidget):
    """Home dashboard showing recent backtest metrics and quick-action buttons.

    Args:
        settings_state: Application settings state.
        parent: Optional parent widget.

    Signals:
        navigate_to(str): Emitted when a quick-action button is clicked.
            The string is the target page ID.
    """

    navigate_to = Signal(str)

    def __init__(self, settings_state: SettingsState, parent=None) -> None:
        super().__init__(parent)
        self._settings_state = settings_state
        self._backtest_service = BacktestService(settings_state.settings_service)
        self._build_ui()
        self._connect_signals()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the dashboard layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # Page title
        title = QLabel("Dashboard")
        title.setObjectName("page_title")
        root.addWidget(title)

        # ── Metric cards (2×2 grid) ────────────────────────────────────
        metrics_group = QGroupBox("Last Backtest")
        grid = QGridLayout(metrics_group)
        grid.setSpacing(8)

        self._card_profit = MetricCard("Last Profit")
        self._card_winrate = MetricCard("Win Rate")
        self._card_trades = MetricCard("Total Trades")
        self._card_strategy = MetricCard("Best Strategy")

        grid.addWidget(self._card_profit, 0, 0)
        grid.addWidget(self._card_winrate, 0, 1)
        grid.addWidget(self._card_trades, 1, 0)
        grid.addWidget(self._card_strategy, 1, 1)

        root.addWidget(metrics_group)

        # ── Recent runs list ───────────────────────────────────────────
        runs_group = QGroupBox("Recent Runs")
        runs_layout = QVBoxLayout(runs_group)

        self._runs_list = QListWidget()
        self._runs_list.setMaximumHeight(160)
        runs_layout.addWidget(self._runs_list)

        self._empty_label = QLabel("Run your first backtest to see results here")
        self._empty_label.setObjectName("hint_label")
        runs_layout.addWidget(self._empty_label)

        root.addWidget(runs_group)

        # ── Quick-action buttons ───────────────────────────────────────
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout(actions_group)

        self._btn_run_last = QPushButton("Run Last Backtest")
        self._btn_run_last.setAccessibleName("Run last backtest")
        self._btn_run_last.setToolTip("Navigate to Backtest page")
        self._btn_run_last.clicked.connect(lambda: self.navigate_to.emit("backtest"))

        self._btn_go_backtest = QPushButton("Go to Backtest")
        self._btn_go_backtest.setAccessibleName("Go to Backtest page")
        self._btn_go_backtest.setToolTip("Open the Backtest page")
        self._btn_go_backtest.clicked.connect(lambda: self.navigate_to.emit("backtest"))

        self._btn_go_strategy = QPushButton("Go to Strategy Lab")
        self._btn_go_strategy.setAccessibleName("Go to Strategy Lab page")
        self._btn_go_strategy.setToolTip("Open the Strategy Lab page")
        self._btn_go_strategy.clicked.connect(lambda: self.navigate_to.emit("strategy"))

        self._btn_go_settings = QPushButton("Go to Settings")
        self._btn_go_settings.setAccessibleName("Go to Settings page")
        self._btn_go_settings.setToolTip("Open the Settings page")
        self._btn_go_settings.clicked.connect(lambda: self.navigate_to.emit("settings"))

        actions_layout.addWidget(self._btn_run_last)
        actions_layout.addWidget(self._btn_go_backtest)
        actions_layout.addWidget(self._btn_go_strategy)
        actions_layout.addWidget(self._btn_go_settings)
        actions_layout.addStretch()

        root.addWidget(actions_group)
        root.addStretch()

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Connect settings changes to refresh."""
        self._settings_state.settings_changed.connect(self._on_settings_changed)

    def _on_settings_changed(self, _=None) -> None:
        """Refresh when settings change."""
        self.refresh()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload data from IndexStore and update all widgets."""
        settings = self._settings_state.current_settings
        backtest_results_dir = self._get_backtest_results_dir(settings)

        all_runs = self._load_all_runs(backtest_results_dir)

        if not all_runs:
            self._show_empty_state()
        else:
            self._show_runs(all_runs)

        _log.debug("DashboardPage refreshed: %d total runs", len(all_runs))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_backtest_results_dir(self, settings) -> Optional[str]:
        """Derive the backtest_results directory from settings."""
        if settings and settings.user_data_path:
            return str(Path(settings.user_data_path) / "backtest_results")
        return None

    def _load_all_runs(self, backtest_results_dir: Optional[str]) -> list:
        """Load all runs from the global index, sorted newest first."""
        if not backtest_results_dir:
            return []
        try:
            index = self._backtest_service.load_index(backtest_results_dir)
            all_runs: list = []
            for strategy_data in index.get("strategies", {}).values():
                all_runs.extend(strategy_data.get("runs", []))
            # Sort by saved_at descending
            all_runs.sort(key=lambda r: r.get("saved_at", ""), reverse=True)
            return all_runs
        except Exception as e:
            _log.warning("Failed to load runs from index: %s", e)
            return []

    def _show_empty_state(self) -> None:
        """Show empty state — no runs available."""
        self._card_profit.set_value("—")
        self._card_winrate.set_value("—")
        self._card_trades.set_value("—")
        self._card_strategy.set_value("—")
        self._runs_list.clear()
        self._runs_list.hide()
        self._empty_label.show()

    def _show_runs(self, all_runs: list) -> None:
        """Populate metric cards and recent runs list from run data."""
        # Most recent run for metric cards
        latest = all_runs[0]
        profit_pct = latest.get("profit_total_pct", 0.0)
        win_rate = latest.get("win_rate_pct", 0.0)
        trades = latest.get("trades_count", 0)
        strategy = latest.get("strategy", "—")

        self._card_profit.set_value(
            f"{profit_pct:+.2f}%",
            trend=profit_pct,
        )
        self._card_winrate.set_value(f"{win_rate:.1f}%")
        self._card_trades.set_value(str(trades))
        self._card_strategy.set_value(strategy)

        # Recent runs list (last 5)
        self._runs_list.clear()
        for run in all_runs[:5]:
            strat = run.get("strategy", "?")
            pct = run.get("profit_total_pct", 0.0)
            saved = run.get("saved_at", "")[:16].replace("T", " ")
            label = f"{strat}  {pct:+.2f}%  {saved}"
            item = QListWidgetItem(label)
            self._runs_list.addItem(item)

        self._runs_list.show()
        self._empty_label.hide()
