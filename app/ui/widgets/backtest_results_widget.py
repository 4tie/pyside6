import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QLabel, QGroupBox, QGridLayout, QHeaderView,
    QAbstractItemView, QSizePolicy, QPushButton, QFileDialog, QMessageBox
)
from PySide6.QtGui import QColor, QFont

from app.core.services.backtest_results_service import BacktestResults, BacktestSummary
from app.core.services.run_store import RunStore

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
        self._export_dir: Optional[Path] = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Export toolbar
        toolbar = QHBoxLayout()
        self._export_path_label = QLabel("No results loaded")
        self._export_path_label.setStyleSheet("color: #555; font-size: 9pt;")
        toolbar.addWidget(self._export_path_label, 1)

        self._export_btn = QPushButton("Export Results")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export)
        toolbar.addWidget(self._export_btn)
        layout.addLayout(toolbar)

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

    def display_results(self, results: BacktestResults, export_dir: Optional[str] = None):
        """Display backtest results.

        Args:
            results: BacktestResults object to display
            export_dir: Optional directory to use as default export location
        """
        self.results = results
        self._export_dir = Path(export_dir) if export_dir else None
        self._export_btn.setEnabled(True)
        if self._export_dir:
            self._export_path_label.setText(str(self._export_dir))
        else:
            self._export_path_label.setText(f"Strategy: {results.summary.strategy}")
        self._populate_summary(results.summary)
        self._populate_trades(results.trades)

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _populate_summary(self, s: BacktestSummary):
        """Fill summary grids from a BacktestSummary."""
        self._summary_header.setText(
            f"{s.strategy}  |  {s.timeframe}  |  {s.backtest_start[:10]} → {s.backtest_end[:10]}"
            if s.backtest_start else f"Strategy: {s.strategy}"
        )

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
        bal_color    = _GREEN if s.final_balance >= s.starting_balance else _RED

        # Performance group
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

        # Trade stats group
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

    # ------------------------------------------------------------------ #
    # Export                                                               #
    # ------------------------------------------------------------------ #

    def _on_export(self):
        """Export run folder via RunStore to a chosen directory."""
        if not self.results:
            return

        default_dir = str(self._export_dir) if self._export_dir else ""
        out_dir = QFileDialog.getExistingDirectory(
            self, "Select Export Directory", default_dir
        )
        if not out_dir:
            return

        try:
            run_dir = RunStore.save(
                results=self.results,
                strategy_results_dir=out_dir,
            )
            QMessageBox.information(
                self, "Export Complete",
                f"Run saved to:\n{run_dir}\n\n"
                "Files: meta.json, results.json, trades.json, "
                "config.snapshot.json, params.json"
            )
            self._export_path_label.setText(str(run_dir))
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))
