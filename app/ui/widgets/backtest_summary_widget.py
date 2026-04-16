from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QGridLayout,
)
from PySide6.QtGui import QColor, QFont

from app.core.backtests.results_models import BacktestSummary

_GREEN = QColor("#1a7f37")
_RED   = QColor("#cf222e")
_BOLD  = QFont()
_BOLD.setBold(True)


class BacktestSummaryWidget(QWidget):
    """Displays backtest performance and trade-stats summary."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)

        self._header = QLabel("No results loaded")
        self._header.setFont(_BOLD)
        outer.addWidget(self._header)

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

    def populate(self, s: BacktestSummary):
        """Fill summary grids from a BacktestSummary.

        Args:
            s: BacktestSummary to display
        """
        self._header.setText(
            f"{s.strategy}  |  {s.timeframe}  |  {s.backtest_start[:10]} → {s.backtest_end[:10]}"
            if s.backtest_start else f"Strategy: {s.strategy}"
        )

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
        bal_color    = _GREEN if s.final_balance >= s.starting_balance else _RED

        r = 0
        if s.starting_balance:
            add_row(self._perf_grid, r, "Starting Balance", f"{s.starting_balance:.3f} USDT"); r += 1
            add_row(self._perf_grid, r, "Final Balance",    f"{s.final_balance:.3f} USDT", bal_color); r += 1
        add_row(self._perf_grid, r, "Total Profit %",   f"{s.total_profit:.4f}%", profit_color); r += 1
        add_row(self._perf_grid, r, "Total Profit Abs", f"{s.total_profit_abs:.4f} USDT", profit_color); r += 1
        add_row(self._perf_grid, r, "Avg Profit %",     f"{s.avg_profit:.4f}%", avg_color); r += 1
        add_row(self._perf_grid, r, "Max Drawdown %",   f"{s.max_drawdown:.2f}%", _RED if s.max_drawdown > 0 else None); r += 1
        add_row(self._perf_grid, r, "Max DD Abs",       f"{s.max_drawdown_abs:.4f} USDT"); r += 1
        if s.profit_factor:
            add_row(self._perf_grid, r, "Profit Factor", f"{s.profit_factor:.4f}",
                    _GREEN if s.profit_factor >= 1 else _RED); r += 1
        if s.expectancy:
            add_row(self._perf_grid, r, "Expectancy", f"{s.expectancy:.4f}",
                    _GREEN if s.expectancy >= 0 else _RED); r += 1
        if s.sharpe_ratio is not None:
            add_row(self._perf_grid, r, "Sharpe",  f"{s.sharpe_ratio:.4f}",
                    _GREEN if s.sharpe_ratio >= 0 else _RED); r += 1
        if s.sortino_ratio is not None:
            add_row(self._perf_grid, r, "Sortino", f"{s.sortino_ratio:.4f}",
                    _GREEN if s.sortino_ratio >= 0 else _RED); r += 1
        if s.calmar_ratio is not None:
            add_row(self._perf_grid, r, "Calmar",  f"{s.calmar_ratio:.4f}",
                    _GREEN if s.calmar_ratio >= 0 else _RED); r += 1

        r = 0
        add_row(self._trade_grid, r, "Total Trades",  str(s.total_trades)); r += 1
        add_row(self._trade_grid, r, "Wins",          str(s.wins), _GREEN); r += 1
        add_row(self._trade_grid, r, "Losses",        str(s.losses), _RED); r += 1
        add_row(self._trade_grid, r, "Draws",         str(s.draws)); r += 1
        add_row(self._trade_grid, r, "Win Rate",      f"{s.win_rate:.1f}%",
                _GREEN if s.win_rate >= 50 else _RED); r += 1
        add_row(self._trade_grid, r, "Avg Duration",  f"{s.trade_duration_avg} min"); r += 1
        if s.max_consecutive_wins:
            add_row(self._trade_grid, r, "Max Consec. Wins",   str(s.max_consecutive_wins), _GREEN); r += 1
        if s.max_consecutive_losses:
            add_row(self._trade_grid, r, "Max Consec. Losses", str(s.max_consecutive_losses), _RED); r += 1
        if s.pairlist:
            add_row(self._trade_grid, r, "Pairs", ", ".join(s.pairlist)); r += 1
        if s.timerange:
            add_row(self._trade_grid, r, "Timerange", s.timerange); r += 1
