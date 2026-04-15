from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem,
    QLabel, QScrollArea, QGroupBox, QFormLayout
)
from PySide6.QtGui import QFont

from app.core.services.backtest_results_service import BacktestResults, BacktestSummary


class BacktestResultsWidget(QWidget):
    """Widget for displaying backtest results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.results: BacktestResults = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()

        # Create tabs for Summary and Trades
        self.tabs = QTabWidget()

        self.summary_widget = self._create_summary_tab()
        self.trades_widget = self._create_trades_tab()

        self.tabs.addTab(self.summary_widget, "Summary")
        self.tabs.addTab(self.trades_widget, "Trades")

        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def _create_summary_tab(self) -> QWidget:
        """Create summary statistics tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Scrollable form for summary stats
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        form_widget = QWidget()
        self.form_layout = QFormLayout(form_widget)
        self.form_layout.setSpacing(8)

        scroll.setWidget(form_widget)
        layout.addWidget(scroll)

        widget.setLayout(layout)
        return widget

    def _create_trades_tab(self) -> QWidget:
        """Create trades table tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Trades table
        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(9)
        self.trades_table.setHorizontalHeaderLabels([
            "Pair", "Open Date", "Close Date", "Open Rate", "Close Rate",
            "Profit %", "Profit Abs", "Duration (min)", "Status"
        ])
        self.trades_table.resizeColumnsToContents()
        self.trades_table.setSelectionBehavior(
            self.trades_table.SelectionBehavior.SelectRows
        )

        layout.addWidget(self.trades_table)
        widget.setLayout(layout)
        return widget

    def display_results(self, results: BacktestResults):
        """Display backtest results in the widget.

        Args:
            results: BacktestResults object
        """
        self.results = results

        self._display_summary()
        self._display_trades()

    def _display_summary(self):
        """Display summary statistics."""
        if not self.results:
            return

        summary = self.results.summary

        # Clear existing items
        while self.form_layout.rowCount() > 0:
            self.form_layout.removeRow(0)

        # Add summary stats
        stats = {
            'Strategy': summary.strategy,
            'Timeframe': summary.timeframe,
            'Total Trades': str(summary.total_trades),
            'Wins': f"{summary.wins}",
            'Losses': f"{summary.losses}",
            'Draws': f"{summary.draws}",
            'Win Rate': f"{summary.win_rate:.2f}%",
            'Avg Profit': f"{summary.avg_profit:.4f}%",
            'Total Profit': f"{summary.total_profit:.4f}%",
            'Total Profit (Abs)': f"{summary.total_profit_abs:.8f}",
            'Sharpe Ratio': f"{summary.sharpe_ratio:.4f}" if summary.sharpe_ratio else "N/A",
            'Sortino Ratio': f"{summary.sortino_ratio:.4f}" if summary.sortino_ratio else "N/A",
            'Calmar Ratio': f"{summary.calmar_ratio:.4f}" if summary.calmar_ratio else "N/A",
            'Max Drawdown': f"{summary.max_drawdown:.2f}%",
            'Max Drawdown (Abs)': f"{summary.max_drawdown_abs:.8f}",
            'Avg Trade Duration': f"{summary.trade_duration_avg} min",
        }

        for key, value in stats.items():
            label = QLabel(key)
            label.setFont(QFont("Arial", 10))
            value_label = QLabel(value)
            value_label.setFont(QFont("Courier", 10))

            # Highlight important metrics
            if key in ['Win Rate', 'Total Profit', 'Sharpe Ratio']:
                value_label.setStyleSheet("color: #2196F3; font-weight: bold;")

            self.form_layout.addRow(label, value_label)

    def _display_trades(self):
        """Display trades table."""
        if not self.results:
            return

        trades = self.results.trades

        self.trades_table.setRowCount(len(trades))

        for row, trade in enumerate(trades):
            self.trades_table.setItem(row, 0, QTableWidgetItem(trade.pair))
            self.trades_table.setItem(row, 1, QTableWidgetItem(trade.open_date))
            self.trades_table.setItem(row, 2, QTableWidgetItem(trade.close_date or "OPEN"))
            self.trades_table.setItem(row, 3, QTableWidgetItem(f"{trade.open_rate:.8f}"))
            self.trades_table.setItem(row, 4, QTableWidgetItem(
                f"{trade.close_rate:.8f}" if trade.close_rate else "N/A"
            ))

            profit_item = QTableWidgetItem(f"{trade.profit:.4f}%")
            if trade.profit > 0:
                profit_item.setForeground(Qt.green)
            elif trade.profit < 0:
                profit_item.setForeground(Qt.red)
            self.trades_table.setItem(row, 5, profit_item)

            self.trades_table.setItem(row, 6, QTableWidgetItem(f"{trade.profit_abs:.8f}"))
            self.trades_table.setItem(row, 7, QTableWidgetItem(str(trade.duration)))
            self.trades_table.setItem(row, 8, QTableWidgetItem(
                "OPEN" if trade.is_open else "CLOSED"
            ))

        self.trades_table.resizeColumnsToContents()
