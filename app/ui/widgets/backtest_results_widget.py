from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QLabel, QGroupBox, QGridLayout, QHeaderView,
    QAbstractItemView, QSizePolicy
)
from PySide6.QtGui import QColor, QFont

from app.core.services.backtest_results_service import BacktestResults, BacktestSummary

_GREEN = QColor("#1a7f37")
_RED   = QColor("#cf222e")
_BOLD  = QFont()
_BOLD.setBold(True)


def _colored_item(text: str, value: float) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setForeground(_GREEN if value >= 0 else _RED)
    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return item


def _right_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return item


class BacktestResultsWidget(QWidget):
    """Widget for displaying backtest results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.results: BacktestResults = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.summary_tab = self._build_summary_tab()
        self.trades_tab = self._build_trades_tab()
        self.tabs.addTab(self.summary_tab, "Summary")
        self.tabs.addTab(self.trades_tab, "Trades")

        layout.addWidget(self.tabs)
        self.setLayout(layout)

    # ------------------------------------------------------------------ #
    # Tab builders                                                         #
    # ------------------------------------------------------------------ #

    def _build_summary_tab(self) -> QWidget:
        """Build summary statistics tab."""
        widget = QWidget()
        outer = QVBoxLayout(widget)

        self._summary_header = QLabel("No results loaded")
        self._summary_header.setFont(_BOLD)
        outer.addWidget(self._summary_header)

        # Two side-by-side groups
        row = QHBoxLayout()

        self._perf_group = QGroupBox("Performance")
        self._perf_grid = QGridLayout(self._perf_group)
        self._perf_grid.setColumnStretch(1, 1)

        self._trade_group = QGroupBox("Trade Stats")
        self._trade_grid = QGridLayout(self._trade_group)
        self._trade_grid.setColumnStretch(1, 1)

        row.addWidget(self._perf_group)
        row.addWidget(self._trade_group)
        outer.addLayout(row)
        outer.addStretch()
        return widget

    def _build_trades_tab(self) -> QWidget:
        """Build trades table tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self._trades_label = QLabel("0 trades")
        layout.addWidget(self._trades_label)

        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(9)
        self.trades_table.setHorizontalHeaderLabels([
            "Pair", "Open Date", "Close Date", "Open Rate",
            "Close Rate", "Profit %", "Profit Abs", "Duration (min)", "Exit Reason",
        ])
        self.trades_table.setSortingEnabled(True)
        self.trades_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.trades_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.trades_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.trades_table.horizontalHeader().setStretchLastSection(True)
        self.trades_table.verticalHeader().setVisible(False)
        self.trades_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addWidget(self.trades_table)
        return widget

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def display_results(self, results: BacktestResults):
        """Display backtest results.

        Args:
            results: BacktestResults object to display
        """
        self.results = results
        self._populate_summary(results.summary)
        self._populate_trades(results.trades)

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _populate_summary(self, s: BacktestSummary):
        """Fill summary grids from a BacktestSummary."""
        self._summary_header.setText(f"Strategy: {s.strategy}")

        # Clear grids
        for grid in (self._perf_grid, self._trade_grid):
            while grid.count():
                item = grid.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        def add_row(grid: QGridLayout, row: int, label: str, value: str, color: QColor = None):
            lbl = QLabel(label + ":")
            val = QLabel(value)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if color:
                val.setStyleSheet(f"color: {color.name()}; font-weight: bold;")
            grid.addWidget(lbl, row, 0)
            grid.addWidget(val, row, 1)

        profit_color = _GREEN if s.total_profit_abs >= 0 else _RED
        avg_color    = _GREEN if s.avg_profit >= 0 else _RED

        # Performance group
        add_row(self._perf_grid, 0, "Total Profit %",  f"{s.total_profit:.2f}%", profit_color)
        add_row(self._perf_grid, 1, "Total Profit Abs", f"{s.total_profit_abs:.4f} USDT", profit_color)
        add_row(self._perf_grid, 2, "Avg Profit %",    f"{s.avg_profit:.4f}%", avg_color)
        add_row(self._perf_grid, 3, "Max Drawdown",    f"{s.max_drawdown:.2f}%")
        add_row(self._perf_grid, 4, "Max DD Abs",      f"{s.max_drawdown_abs:.4f} USDT")
        if s.sharpe_ratio is not None:
            add_row(self._perf_grid, 5, "Sharpe", f"{s.sharpe_ratio:.4f}")
        if s.sortino_ratio is not None:
            add_row(self._perf_grid, 6, "Sortino", f"{s.sortino_ratio:.4f}")

        # Trade stats group
        add_row(self._trade_grid, 0, "Total Trades",   str(s.total_trades))
        add_row(self._trade_grid, 1, "Wins",           str(s.wins), _GREEN)
        add_row(self._trade_grid, 2, "Losses",         str(s.losses), _RED)
        add_row(self._trade_grid, 3, "Draws",          str(s.draws))
        add_row(self._trade_grid, 4, "Win Rate",       f"{s.win_rate:.1f}%",
                _GREEN if s.win_rate >= 50 else _RED)
        add_row(self._trade_grid, 5, "Avg Duration",   f"{s.trade_duration_avg} min")

    def _populate_trades(self, trades):
        """Fill the trades table."""
        self._trades_label.setText(f"{len(trades)} trades")
        self.trades_table.setSortingEnabled(False)
        self.trades_table.setRowCount(len(trades))

        for row, t in enumerate(trades):
            self.trades_table.setItem(row, 0, QTableWidgetItem(t.pair))
            self.trades_table.setItem(row, 1, QTableWidgetItem(
                t.open_date[:16] if t.open_date else ""))
            self.trades_table.setItem(row, 2, QTableWidgetItem(
                (t.close_date[:16] if t.close_date else "OPEN")))
            self.trades_table.setItem(row, 3, _right_item(f"{t.open_rate:.6g}"))
            self.trades_table.setItem(row, 4, _right_item(
                f"{t.close_rate:.6g}" if t.close_rate else "N/A"))
            self.trades_table.setItem(row, 5, _colored_item(f"{t.profit:+.3f}%", t.profit))
            self.trades_table.setItem(row, 6, _colored_item(f"{t.profit_abs:+.4f}", t.profit_abs))
            self.trades_table.setItem(row, 7, _right_item(str(t.duration)))

            # exit reason from raw trade if available
            exit_reason = ""
            if self.results and self.results.raw_data:
                raw_trades = self.results.raw_data.get('result', {}).get('trades', [])
                if row < len(raw_trades):
                    exit_reason = raw_trades[row].get('exit_reason', '')
            self.trades_table.setItem(row, 8, QTableWidgetItem(exit_reason))

        self.trades_table.setSortingEnabled(True)
        self.trades_table.sortByColumn(1, Qt.AscendingOrder)
