from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSizePolicy,
)
from PySide6.QtGui import QColor

from app.core.services.backtest_results_service import BacktestTrade

_GREEN = QColor("#1a7f37")
_RED   = QColor("#cf222e")


def _colored_item(text: str, value: float) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setForeground(_GREEN if value >= 0 else _RED)
    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return item


def _right_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return item


class BacktestTradesWidget(QWidget):
    """Displays the trades table for a backtest result."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_data: Optional[dict] = None
        self._strategy_name: str = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self._count_label = QLabel("0 trades")
        layout.addWidget(self._count_label)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Pair", "Open Date", "Close Date", "Open Rate",
            "Close Rate", "Profit %", "Profit Abs", "Duration (min)", "Exit Reason",
        ])
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.table)

    def populate(self, trades: List[BacktestTrade], raw_data: Optional[dict] = None, strategy_name: str = ""):
        """Fill the trades table.

        Args:
            trades: List of BacktestTrade objects
            raw_data: Optional raw JSON data for exit_reason lookup
            strategy_name: Strategy name for raw_data lookup
        """
        self._raw_data = raw_data
        self._strategy_name = strategy_name
        self._count_label.setText(f"{len(trades)} trades")
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(trades))

        for row, t in enumerate(trades):
            self.table.setItem(row, 0, QTableWidgetItem(t.pair))
            self.table.setItem(row, 1, QTableWidgetItem(
                t.open_date[:16] if t.open_date else ""))
            self.table.setItem(row, 2, QTableWidgetItem(
                t.close_date[:16] if t.close_date else "OPEN"))
            self.table.setItem(row, 3, _right_item(f"{t.open_rate:.6g}"))
            self.table.setItem(row, 4, _right_item(
                f"{t.close_rate:.6g}" if t.close_rate else "N/A"))
            self.table.setItem(row, 5, _colored_item(f"{t.profit:+.3f}%", t.profit))
            self.table.setItem(row, 6, _colored_item(f"{t.profit_abs:+.4f}", t.profit_abs))
            self.table.setItem(row, 7, _right_item(str(t.duration)))

            exit_reason = ""
            if raw_data:
                strategy_block = raw_data.get("strategy", {})
                if isinstance(strategy_block, dict):
                    raw_trades = strategy_block.get(strategy_name, {}).get("trades", [])
                else:
                    raw_trades = raw_data.get("result", {}).get("trades", [])
                if row < len(raw_trades):
                    exit_reason = raw_trades[row].get("exit_reason", "")
            self.table.setItem(row, 8, QTableWidgetItem(exit_reason))

        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, Qt.AscendingOrder)
