from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.core.models.backtest_models import BacktestSummary

_GREEN = QColor("#4ec9a0")   # mint-green — matches theme accent / success
_RED   = QColor("#f44747")   # VS Code red — matches theme danger
_BOLD = QFont()
_BOLD.setBold(True)


class BacktestStatsWidget(QWidget):
    """Display backtest performance and trade statistics."""

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

    def populate(self, summary: BacktestSummary):
        """Fill summary grids from a BacktestSummary."""
        self._header.setText(
            (
                f"{summary.strategy}  |  {summary.timeframe}  |  "
                f"{summary.backtest_start[:10]} -> {summary.backtest_end[:10]}"
            )
            if summary.backtest_start
            else f"Strategy: {summary.strategy}"
        )

        for grid in (self._perf_grid, self._trade_grid):
            while grid.count():
                item = grid.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        def add_row(
            grid: QGridLayout,
            row: int,
            label: str,
            value: str,
            color: QColor | None = None,
        ):
            lbl = QLabel(label + ":")
            val = QLabel(value)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if color:
                val.setStyleSheet(f"color: {color.name()}; font-weight: bold;")
            grid.addWidget(lbl, row, 0)
            grid.addWidget(val, row, 1)

        profit_color = _GREEN if summary.total_profit_abs >= 0 else _RED
        avg_color = _GREEN if summary.avg_profit >= 0 else _RED
        balance_color = _GREEN if summary.final_balance >= summary.starting_balance else _RED

        row = 0
        if summary.starting_balance:
            add_row(self._perf_grid, row, "Starting Balance", f"{summary.starting_balance:.3f} USDT")
            row += 1
            add_row(self._perf_grid, row, "Final Balance", f"{summary.final_balance:.3f} USDT", balance_color)
            row += 1
        add_row(self._perf_grid, row, "Total Profit %", f"{summary.total_profit:.4f}%", profit_color)
        row += 1
        add_row(self._perf_grid, row, "Total Profit Abs", f"{summary.total_profit_abs:.4f} USDT", profit_color)
        row += 1
        add_row(self._perf_grid, row, "Avg Profit %", f"{summary.avg_profit:.4f}%", avg_color)
        row += 1
        add_row(
            self._perf_grid,
            row,
            "Max Drawdown %",
            f"{summary.max_drawdown:.2f}%",
            _RED if summary.max_drawdown > 0 else None,
        )
        row += 1
        add_row(self._perf_grid, row, "Max DD Abs", f"{summary.max_drawdown_abs:.4f} USDT")
        row += 1
        if summary.profit_factor:
            add_row(
                self._perf_grid,
                row,
                "Profit Factor",
                f"{summary.profit_factor:.4f}",
                _GREEN if summary.profit_factor >= 1 else _RED,
            )
            row += 1
        if summary.expectancy:
            add_row(
                self._perf_grid,
                row,
                "Expectancy",
                f"{summary.expectancy:.4f}",
                _GREEN if summary.expectancy >= 0 else _RED,
            )
            row += 1
        if summary.sharpe_ratio is not None:
            add_row(
                self._perf_grid,
                row,
                "Sharpe",
                f"{summary.sharpe_ratio:.4f}",
                _GREEN if summary.sharpe_ratio >= 0 else _RED,
            )
            row += 1
        if summary.sortino_ratio is not None:
            add_row(
                self._perf_grid,
                row,
                "Sortino",
                f"{summary.sortino_ratio:.4f}",
                _GREEN if summary.sortino_ratio >= 0 else _RED,
            )
            row += 1
        if summary.calmar_ratio is not None:
            add_row(
                self._perf_grid,
                row,
                "Calmar",
                f"{summary.calmar_ratio:.4f}",
                _GREEN if summary.calmar_ratio >= 0 else _RED,
            )
            row += 1

        row = 0
        add_row(self._trade_grid, row, "Total Trades", str(summary.total_trades))
        row += 1
        add_row(self._trade_grid, row, "Wins", str(summary.wins), _GREEN)
        row += 1
        add_row(self._trade_grid, row, "Losses", str(summary.losses), _RED)
        row += 1
        add_row(self._trade_grid, row, "Draws", str(summary.draws))
        row += 1
        add_row(
            self._trade_grid,
            row,
            "Win Rate",
            f"{summary.win_rate:.1f}%",
            _GREEN if summary.win_rate >= 50 else _RED,
        )
        row += 1
        add_row(self._trade_grid, row, "Avg Duration", f"{summary.trade_duration_avg} min")
        row += 1
        if summary.max_consecutive_wins:
            add_row(self._trade_grid, row, "Max Consec. Wins", str(summary.max_consecutive_wins), _GREEN)
            row += 1
        if summary.max_consecutive_losses:
            add_row(self._trade_grid, row, "Max Consec. Losses", str(summary.max_consecutive_losses), _RED)
            row += 1
        if summary.pairlist:
            add_row(self._trade_grid, row, "Pairs", ", ".join(summary.pairlist))
            row += 1
        if summary.timerange:
            add_row(self._trade_grid, row, "Timerange", summary.timerange)
