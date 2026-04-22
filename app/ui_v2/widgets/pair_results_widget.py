"""pair_results_widget.py — Display per-pair backtest metrics.

Shows a table of pair statistics (Pair, Profit, Win Rate, Trades, Max Drawdown)
with highlighting for best/worst performing pairs. Displays concentration
warnings when a single pair dominates profitability.
"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.backtests.results_models import PairAnalysis

# Style constants for best/worst pair rows
_PAIR_TABLE_STYLES = {
    "best_row_bg": "#4ec9a0",  # green
    "best_row_fg": "#ffffff",  # white text
    "best_row_weight": "bold",
    "worst_row_bg": "#f44747",  # red
    "worst_row_fg": "#ffffff",  # white text
    "worst_row_weight": "italic",
}


class PairResultsWidget(QWidget):
    """Displays per-pair metrics from a backtest run.

    Features:
    - Table with 5 columns: Pair | Profit (%) | Win Rate (%) | Trades | Max Drawdown (%)
    - Highlighting: best pairs (green+bold), worst pairs (red+italic)
    - Concentration warning: shown when single pair profit_share > 60%
    """

    def __init__(self) -> None:
        super().__init__()
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Pair", "Profit (%)", "Win Rate (%)", "Trades", "Max Drawdown (%)"]
        )
        self._table.setColumnWidth(0, 120)
        for i in range(1, 5):
            self._table.setColumnWidth(i, 120)

        self._concentration_warning = QLabel()
        self._concentration_warning.setStyleSheet(
            "color: #ce9178; font-weight: bold; background-color: #1e1e1e; padding: 8px; border-radius: 4px;"
        )
        self._concentration_warning.setWordWrap(True)
        self._concentration_warning.hide()

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addWidget(self._concentration_warning)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def display(self, analysis: PairAnalysis) -> None:
        """Display pair analysis results in the table.

        Args:
            analysis: PairAnalysis from PairAnalysisService.
        """
        self._table.setRowCount(0)

        if not analysis.pair_metrics:
            self._table.setRowCount(1)
            item = QTableWidgetItem("No pairs to display")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(0, 0, item)
            self._concentration_warning.hide()
            return

        # Populate table rows
        best_pair_names = {pm.pair for pm in analysis.best_pairs}
        worst_pair_names = {pm.pair for pm in analysis.worst_pairs}

        for pm in analysis.pair_metrics:
            row = self._table.rowCount()
            self._table.insertRow(row)

            # Pair name
            pair_item = QTableWidgetItem(pm.pair)
            self._table.setItem(row, 0, pair_item)

            # Profit (%)
            profit_item = QTableWidgetItem(f"{pm.total_profit_pct:.3f}")
            profit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 1, profit_item)

            # Win Rate (%)
            winrate_item = QTableWidgetItem(f"{pm.win_rate:.1f}")
            winrate_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 2, winrate_item)

            # Trade Count
            trade_item = QTableWidgetItem(str(pm.trade_count))
            trade_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 3, trade_item)

            # Max Drawdown (%)
            dd_item = QTableWidgetItem(f"{pm.max_drawdown_pct:.3f}")
            dd_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 4, dd_item)

            # Apply styling
            if pm.pair in best_pair_names:
                for col in range(5):
                    item = self._table.item(row, col)
                    item.setBackground(_PAIR_TABLE_STYLES["best_row_bg"])
                    item.setForeground(_PAIR_TABLE_STYLES["best_row_fg"])
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)

            elif pm.pair in worst_pair_names:
                for col in range(5):
                    item = self._table.item(row, col)
                    item.setBackground(_PAIR_TABLE_STYLES["worst_row_bg"])
                    item.setForeground(_PAIR_TABLE_STYLES["worst_row_fg"])
                    font = item.font()
                    font.setItalic(True)
                    item.setFont(font)

        # Show concentration warning if present
        if "profit_concentration" in analysis.dominance_flags:
            self._concentration_warning.setText(
                "⚠️ Profit concentration detected: A single pair contributes over 60% of profits. "
                "Consider diversifying your strategy across more pairs to reduce risk."
            )
            self._concentration_warning.show()
        else:
            self._concentration_warning.hide()

    def clear(self) -> None:
        """Clear the table and show empty state."""
        self._table.setRowCount(1)
        item = QTableWidgetItem("No results loaded")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
        self._table.setItem(0, 0, item)
        self._concentration_warning.hide()
