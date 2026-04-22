"""compare_widget.py — Compare two backtest runs side-by-side.

Allows user to select two runs from dropdowns and view their diff metrics
(profit, win rate, max drawdown) with a verdict (improved/degraded/neutral).
"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.backtests.results_models import RunComparison

# Color constants for verdict display
_GREEN = "#4ec9a0"
_RED = "#f44747"
_NEUTRAL = "#9cdcfe"


class CompareWidget(QWidget):
    """Display a comparison between two backtest runs.

    Features:
    - Two run selectors (ComboBox) with Compare button
    - Three metric diff rows: Profit, Win Rate, Max Drawdown
    - Verdict label with semantic coloring (green/red/neutral)
    - Prompt label when fewer than 2 runs available
    """

    def __init__(self) -> None:
        super().__init__()

        # Run selectors
        self._combo_run_a = QComboBox()
        self._combo_run_b = QComboBox()
        self._btn_compare = QPushButton("Compare")
        self._btn_compare.setMaximumWidth(100)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Run A:"))
        selector_layout.addWidget(self._combo_run_a)
        selector_layout.addWidget(QLabel("Run B:"))
        selector_layout.addWidget(self._combo_run_b)
        selector_layout.addWidget(self._btn_compare)
        selector_layout.addStretch()

        # Prompt label (shown when < 2 runs)
        self._prompt_label = QLabel(
            "Select two runs to compare. "
            "Run A is the baseline; Run B is the candidate. "
            "Positive diffs mean Run B is better."
        )
        self._prompt_label.setStyleSheet(
            "color: #9cdcfe; background-color: #1e1e1e; padding: 8px; border-radius: 4px;"
        )
        self._prompt_label.setWordWrap(True)
        self._prompt_label.setVisible(True)

        # Comparison results (hidden until comparison shown)
        self._label_profit_diff = QLabel()
        self._label_winrate_diff = QLabel()
        self._label_drawdown_diff = QLabel()
        self._label_verdict = QLabel()

        results_layout = QFormLayout()
        results_layout.addRow("Profit Diff:", self._label_profit_diff)
        results_layout.addRow("Win Rate Diff (%):", self._label_winrate_diff)
        results_layout.addRow("Max Drawdown Diff (%):", self._label_drawdown_diff)
        results_layout.addRow("Verdict:", self._label_verdict)

        results_widget = QWidget()
        results_widget.setLayout(results_layout)
        results_widget.setVisible(False)
        self._results_widget = results_widget

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(selector_layout)
        main_layout.addWidget(self._prompt_label)
        main_layout.addWidget(self._results_widget)
        main_layout.addStretch()
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

    def set_run_choices(self, runs: List[dict]) -> None:
        """Populate run selector dropdowns.

        Args:
            runs: List of run metadata dicts (each with at least 'id' key).
        """
        self._combo_run_a.clear()
        self._combo_run_b.clear()

        if not runs:
            self._prompt_label.setText("No runs available. Run a backtest first.")
            self._prompt_label.setVisible(True)
            self._results_widget.setVisible(False)
            self._btn_compare.setEnabled(False)
            return

        # Add runs to both combos
        for run in runs:
            run_id = run.get("id", "unknown")
            run_label = f"{run_id}"
            self._combo_run_a.addItem(run_label, run)
            self._combo_run_b.addItem(run_label, run)

        # Pre-select first two if available
        if len(runs) >= 2:
            self._combo_run_b.setCurrentIndex(1)
            self._prompt_label.setVisible(True)
            self._btn_compare.setEnabled(True)
        else:
            self._prompt_label.setText(
                "You need at least 2 runs to compare. "
                "Run a backtest to generate a candidate run."
            )
            self._prompt_label.setVisible(True)
            self._results_widget.setVisible(False)
            self._btn_compare.setEnabled(False)

    def display(self, comparison: RunComparison) -> None:
        """Display comparison results.

        Args:
            comparison: RunComparison with diffs and verdict.
        """
        # Profit diff
        profit_text = f"{comparison.profit_diff:+.3f}"
        profit_color = _GREEN if comparison.profit_diff > 0 else (_RED if comparison.profit_diff < 0 else _NEUTRAL)
        self._label_profit_diff.setText(profit_text)
        self._label_profit_diff.setStyleSheet(f"color: {profit_color}; font-weight: bold;")

        # Win rate diff
        winrate_text = f"{comparison.winrate_diff:+.1f}"
        winrate_color = _GREEN if comparison.winrate_diff > 0 else (_RED if comparison.winrate_diff < 0 else _NEUTRAL)
        self._label_winrate_diff.setText(winrate_text)
        self._label_winrate_diff.setStyleSheet(f"color: {winrate_color}; font-weight: bold;")

        # Drawdown diff (positive = worse)
        drawdown_text = f"{comparison.drawdown_diff:+.1f}"
        drawdown_color = _RED if comparison.drawdown_diff > 0 else (_GREEN if comparison.drawdown_diff < 0 else _NEUTRAL)
        self._label_drawdown_diff.setText(drawdown_text)
        self._label_drawdown_diff.setStyleSheet(f"color: {drawdown_color}; font-weight: bold;")

        # Verdict
        verdict_text = comparison.verdict.upper()
        if comparison.verdict == "improved":
            verdict_color = _GREEN
        elif comparison.verdict == "degraded":
            verdict_color = _RED
        else:
            verdict_color = _NEUTRAL

        self._label_verdict.setText(verdict_text)
        self._label_verdict.setStyleSheet(f"color: {verdict_color}; font-weight: bold; font-size: 14px;")

        # Show results, hide prompt
        self._results_widget.setVisible(True)
        self._prompt_label.setVisible(False)

    def get_selected_runs(self) -> tuple:
        """Get currently selected run data.

        Returns:
            Tuple of (run_a_data, run_b_data) or (None, None) if not available.
        """
        run_a = self._combo_run_a.currentData()
        run_b = self._combo_run_b.currentData()
        return (run_a, run_b)
