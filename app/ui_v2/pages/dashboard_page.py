"""DashboardPage for the v2 UI layer.

A read-only overview page showing key metrics, recent runs, and quick actions.

Requirements: 3.2, 3.7, 7.5, 16.1
"""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.app_state.settings_state import SettingsState
from app.core.backtests.results_index import IndexStore
from app.core.backtests.results_store import RunStore
from app.core.utils.app_logger import get_logger
from app.ui_v2.widgets.metric_card import MetricCard

_log = get_logger("ui_v2.pages.dashboard_page")


class DashboardPage(QWidget):
    """Dashboard page with metrics, recent runs, and quick actions.

    Args:
        settings_state: Application settings state.
        parent: Optional parent widget.
    """

    # Signals
    navigate_to = Signal(str)  # page_id: "download", "strategy", etc.
    run_last_backtest = Signal()

    def __init__(self, settings_state: SettingsState, parent=None) -> None:
        super().__init__(parent)
        self.settings_state = settings_state

        # Metric cards
        self._profit_card: Optional[MetricCard] = None
        self._win_rate_card: Optional[MetricCard] = None
        self._trades_card: Optional[MetricCard] = None
        self._strategy_card: Optional[MetricCard] = None

        # Recent runs list
        self._runs_list: Optional[QListWidget] = None

        # Empty state label
        self._empty_label: Optional[QLabel] = None

        self._build_ui()
        self._load_data()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the dashboard layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Page title
        title = QLabel("Dashboard")
        title.setObjectName("page_title")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # Metrics grid (2×2)
        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(16)

        self._profit_card = MetricCard("Last Backtest Profit", "—")
        self._win_rate_card = MetricCard("Win Rate", "—")
        self._trades_card = MetricCard("Total Trades", "—")
        self._strategy_card = MetricCard("Best Strategy", "—")

        metrics_grid.addWidget(self._profit_card, 0, 0)
        metrics_grid.addWidget(self._win_rate_card, 0, 1)
        metrics_grid.addWidget(self._trades_card, 1, 0)
        metrics_grid.addWidget(self._strategy_card, 1, 1)

        layout.addLayout(metrics_grid)

        # Recent runs section
        runs_label = QLabel("Recent Runs")
        runs_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(runs_label)

        self._runs_list = QListWidget()
        self._runs_list.setMaximumHeight(200)
        layout.addWidget(self._runs_list)

        # Empty state label (hidden by default)
        self._empty_label = QLabel("No backtest runs found. Run a backtest to get started.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #888; font-size: 14px; padding: 40px;")
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

        # Quick actions
        actions_label = QLabel("Quick Actions")
        actions_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(actions_label)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)

        run_btn = QPushButton("Run Last Backtest")
        run_btn.clicked.connect(self._on_run_last_backtest)
        actions_layout.addWidget(run_btn)

        download_btn = QPushButton("Download Data")
        download_btn.clicked.connect(lambda: self.navigate_to.emit("download"))
        actions_layout.addWidget(download_btn)

        strategy_btn = QPushButton("Open Strategy")
        strategy_btn.clicked.connect(lambda: self.navigate_to.emit("strategy"))
        actions_layout.addWidget(strategy_btn)

        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def _load_data(self) -> None:
        """Load metrics and recent runs from RunStore/IndexStore."""
        if not self.settings_state.current_settings:
            _log.warning("No settings loaded, cannot load dashboard data")
            self._show_empty_state()
            return

        user_data_path = self.settings_state.current_settings.user_data_path
        if not user_data_path:
            _log.info("user_data_path not configured, cannot load dashboard data")
            self._show_empty_state()
            return

        backtest_results_dir = Path(user_data_path) / "backtest_results"

        if not backtest_results_dir.exists():
            _log.info("Backtest results directory does not exist: %s", backtest_results_dir)
            self._show_empty_state()
            return

        try:
            index = IndexStore.load(str(backtest_results_dir))
            strategies = index.get("strategies", {})

            if not strategies:
                _log.info("No strategies found in index")
                self._show_empty_state()
                return

            # Get all runs across all strategies
            all_runs = []
            for strategy_name, strategy_data in strategies.items():
                runs = strategy_data.get("runs", [])
                all_runs.extend(runs)

            if not all_runs:
                _log.info("No runs found in index")
                self._show_empty_state()
                return

            # Sort by saved_at descending
            all_runs.sort(key=lambda r: r.get("saved_at", ""), reverse=True)

            # Update metrics from most recent run
            self._update_metrics(all_runs[0])

            # Populate recent runs list (top 10)
            self._populate_runs_list(all_runs[:10])

            # Hide empty state
            self._empty_label.setVisible(False)
            self._runs_list.setVisible(True)

        except Exception as e:
            _log.error("Failed to load dashboard data: %s", e, exc_info=True)
            self._show_empty_state()

    def _update_metrics(self, latest_run: dict) -> None:
        """Update metric cards from the latest run data.

        Args:
            latest_run: Run entry dict from IndexStore.
        """
        # Last backtest profit
        profit_pct = latest_run.get("profit_total_pct", 0.0)
        self._profit_card.set_value(f"{profit_pct:.2f}%", trend=profit_pct)

        # Win rate
        win_rate = latest_run.get("win_rate_pct", 0.0)
        self._win_rate_card.set_value(f"{win_rate:.1f}%")

        # Total trades
        trades = latest_run.get("trades_count", 0)
        self._trades_card.set_value(str(trades))

        # Best strategy (from latest run)
        strategy = latest_run.get("strategy", "—")
        self._strategy_card.set_value(strategy)

        _log.debug("Metrics updated from run: %s", latest_run.get("run_id"))

    def _populate_runs_list(self, runs: list) -> None:
        """Populate the recent runs list widget.

        Args:
            runs: List of run entry dicts from IndexStore.
        """
        self._runs_list.clear()

        for run in runs:
            strategy = run.get("strategy", "Unknown")
            timeframe = run.get("timeframe", "")
            profit = run.get("profit_total_pct", 0.0)
            saved_at = run.get("saved_at", "")

            # Format: "Strategy (1h) | +5.23% | 2024-01-15 14:30"
            display_text = f"{strategy} ({timeframe}) | {profit:+.2f}% | {saved_at[:16]}"

            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, run)  # Store full run data
            self._runs_list.addItem(item)

        _log.debug("Populated runs list with %d entries", len(runs))

    def _show_empty_state(self) -> None:
        """Show empty state label and hide runs list."""
        self._empty_label.setVisible(True)
        self._runs_list.setVisible(False)

        # Reset metric cards to default
        self._profit_card.set_value("—")
        self._win_rate_card.set_value("—")
        self._trades_card.set_value("—")
        self._strategy_card.set_value("—")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_run_last_backtest(self) -> None:
        """Emit signal to run the last backtest."""
        _log.info("Run last backtest requested from dashboard")
        self.run_last_backtest.emit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload dashboard data from disk."""
        _log.info("Refreshing dashboard data")
        self._load_data()
