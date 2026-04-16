from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QFileDialog, QMessageBox,
)

from app.core.backtests.results_models import BacktestResults
from app.core.backtests.results_store import RunStore
from app.ui.widgets.backtest_stats_widget import BacktestStatsWidget
from app.ui.widgets.backtest_trades_widget import BacktestTradesWidget


class BacktestResultsWidget(QWidget):
    """Container widget for backtest results: summary, trades, and export."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.results: Optional[BacktestResults] = None
        self._export_dir: Optional[Path] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

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
        self.summary_widget = BacktestStatsWidget()
        self.trades_widget = BacktestTradesWidget()
        self.tabs.addTab(self.summary_widget, "Stats")
        self.tabs.addTab(self.trades_widget, "Trades")
        layout.addWidget(self.tabs)

    def display_results(self, results: BacktestResults, export_dir: Optional[str] = None):
        """Display backtest results.

        Args:
            results: BacktestResults object to display
            export_dir: Optional directory to use as default export location
        """
        self.results = results
        self._export_dir = Path(export_dir) if export_dir else None
        self._export_btn.setEnabled(True)
        self._export_path_label.setText(
            str(self._export_dir) if self._export_dir else f"Strategy: {results.summary.strategy}"
        )
        self.summary_widget.populate(results.summary)
        self.trades_widget.populate(results.trades)

    def _on_export(self):
        """Export run folder via RunStore to a chosen directory."""
        if not self.results:
            return

        out_dir = QFileDialog.getExistingDirectory(
            self, "Select Export Directory", str(self._export_dir) if self._export_dir else ""
        )
        if not out_dir:
            return

        try:
            run_dir = RunStore.save(results=self.results, strategy_results_dir=out_dir)
            QMessageBox.information(
                self, "Export Complete",
                f"Run saved to:\n{run_dir}\n\n"
                "Files: meta.json, results.json, trades.json, params.json\n"
                "config.snapshot.json is included when a config path is available."
            )
            self._export_path_label.setText(str(run_dir))
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))
