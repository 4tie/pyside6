"""
improve_page.py — ImprovePage: strategy improvement workflow UI.
"""
import copy
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QScrollArea, QFormLayout, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.app_state.settings_state import SettingsState
from app.core.backtests.results_models import BacktestResults, BacktestSummary
from app.core.models.improve_models import DiagnosedIssue, ParameterSuggestion
from app.core.services.backtest_service import BacktestService
from app.core.services.improve_service import ImproveService
from app.core.services.results_diagnosis_service import ResultsDiagnosisService
from app.core.services.rule_suggestion_service import RuleSuggestionService
from app.core.utils.app_logger import get_logger
from app.ui.widgets.terminal_widget import TerminalWidget

_log = get_logger("ui.improve_page")


# ---------------------------------------------------------------------------
# Module-level pure functions (testable without instantiating ImprovePage)
# ---------------------------------------------------------------------------

def _build_run_label(run: dict) -> str:
    """Format a run metadata dict into a combo-box display string."""
    return (
        f"{run.get('run_id', '')} | "
        f"{run.get('profit_total_pct', 0):.2f}% | "
        f"{run.get('trades_count', 0)} trades | "
        f"{run.get('saved_at', '')}"
    )


def compute_diff(baseline: dict, candidate: dict) -> dict:
    """Return top-level keys where candidate differs from baseline."""
    return {k: v for k, v in candidate.items() if v != baseline.get(k)}


def compute_highlight(metric: str, baseline_val: float, candidate_val: float) -> Optional[str]:
    """Return 'green', 'red', or None based on metric direction."""
    HIGHER_IS_BETTER = {
        "win_rate", "total_profit", "sharpe_ratio",
        "profit_factor", "expectancy", "total_trades",
    }
    LOWER_IS_BETTER = {"max_drawdown"}
    if metric in HIGHER_IS_BETTER:
        if candidate_val > baseline_val:
            return "green"
        elif candidate_val < baseline_val:
            return "red"
        return None
    elif metric in LOWER_IS_BETTER:
        if candidate_val < baseline_val:
            return "green"
        elif candidate_val > baseline_val:
            return "red"
        return None
    return None


def simulate_history(ops: List[str]) -> Tuple[List[dict], dict]:
    """Simulate accept/rollback operations on a baseline history stack."""
    history: List[dict] = []
    current: dict = {"stoploss": -0.10}
    for op in ops:
        if op == "accept":
            history.append(copy.deepcopy(current))
            current = dict(current)
            current["stoploss"] = round(current.get("stoploss", -0.10) + 0.01, 10)
        elif op == "rollback" and history:
            current = history.pop()
    return history, current


# ---------------------------------------------------------------------------
# ImprovePage
# ---------------------------------------------------------------------------

class ImprovePage(QWidget):
    """Strategy improvement workflow page."""

    def __init__(self, settings_state: SettingsState, parent=None):
        super().__init__(parent)

        self._settings_state = settings_state

        # Services
        self._improve_service = ImproveService(
            settings_state.settings_service,
            BacktestService(settings_state.settings_service),
        )
        self._diagnosis_service = ResultsDiagnosisService()
        self._suggestion_service = RuleSuggestionService()

        # Internal state
        self._baseline_run: Optional[BacktestResults] = None
        self._baseline_params: Optional[dict] = None
        self._candidate_config: dict = {}
        self._candidate_run: Optional[BacktestResults] = None
        self._baseline_history: List[dict] = []
        self._sandbox_dir: Optional[Path] = None
        self._export_dir: Optional[Path] = None
        self._run_started_at: float = 0.0

        # Run data parallel to run_combo items
        self._run_data: List[dict] = []

        # Terminal (created early so it's always available)
        self._terminal = TerminalWidget()

        # Pre-create comparison buttons (added to layout in _update_comparison_view)
        self.accept_btn = QPushButton("Accept")
        self.accept_btn.clicked.connect(self._on_accept)
        self.reject_btn = QPushButton("Reject")
        self.reject_btn.clicked.connect(self._on_reject)
        self.rollback_btn = QPushButton("Rollback")
        self.rollback_btn.clicked.connect(self._on_rollback)

        # Connect settings signal
        settings_state.settings_changed.connect(self._refresh_strategies)

        self._init_ui()
        self._refresh_strategies()

    # ------------------------------------------------------------------
    # terminal property
    # ------------------------------------------------------------------

    @property
    def terminal(self) -> TerminalWidget:
        """Return the candidate terminal widget."""
        return self._terminal

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        """Build the page layout."""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # ---- Top controls row ----
        top_controls = QHBoxLayout()
        top_controls.setSpacing(6)

        top_controls.addWidget(QLabel("Strategy:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.setMinimumWidth(180)
        top_controls.addWidget(self.strategy_combo)

        top_controls.addWidget(QLabel("Run:"))
        self.run_combo = QComboBox()
        self.run_combo.setMinimumWidth(320)
        top_controls.addWidget(self.run_combo, 1)

        self.load_latest_btn = QPushButton("Load Latest")
        self.load_latest_btn.clicked.connect(self._on_load_latest)
        top_controls.addWidget(self.load_latest_btn)

        self.analyze_btn = QPushButton("Analyze")
        self.analyze_btn.clicked.connect(self._on_analyze)
        top_controls.addWidget(self.analyze_btn)

        top_controls.addStretch()
        main_layout.addLayout(top_controls)

        # ---- Scrollable results area ----
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(4, 4, 4, 4)
        scroll_layout.setSpacing(8)

        # Status label
        self.status_label = QLabel("")
        scroll_layout.addWidget(self.status_label)

        # Baseline Summary group
        self.baseline_group = QGroupBox("Baseline Summary")
        self.baseline_group.setVisible(False)
        self._baseline_form = QFormLayout()
        self.baseline_group.setLayout(self._baseline_form)
        scroll_layout.addWidget(self.baseline_group)

        # Detected Issues group
        self.issues_group = QGroupBox("Detected Issues")
        self.issues_group.setVisible(False)
        self._issues_layout = QVBoxLayout()
        self.issues_group.setLayout(self._issues_layout)
        scroll_layout.addWidget(self.issues_group)

        # Suggested Actions group
        self.suggestions_group = QGroupBox("Suggested Actions")
        self.suggestions_group.setVisible(False)
        self._suggestions_layout = QVBoxLayout()
        self.suggestions_group.setLayout(self._suggestions_layout)
        scroll_layout.addWidget(self.suggestions_group)

        # Candidate Preview group
        self.candidate_group = QGroupBox("Candidate Preview")
        self.candidate_group.setVisible(False)
        self._candidate_layout = QVBoxLayout()
        self.candidate_group.setLayout(self._candidate_layout)
        scroll_layout.addWidget(self.candidate_group)

        # Comparison group
        self.comparison_group = QGroupBox("Comparison")
        self.comparison_group.setVisible(False)
        self._comparison_layout = QVBoxLayout()
        self.comparison_group.setLayout(self._comparison_layout)
        scroll_layout.addWidget(self.comparison_group)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area, 1)

        self.setLayout(main_layout)

        # Connect combo signals
        self.strategy_combo.currentTextChanged.connect(self._refresh_runs)

    # ------------------------------------------------------------------
    # Strategy / run selector helpers
    # ------------------------------------------------------------------

    def _refresh_strategies(self) -> None:
        """Populate strategy_combo from ImproveService."""
        strategies = self._improve_service.get_available_strategies()
        current = self.strategy_combo.currentText()

        self.strategy_combo.blockSignals(True)
        self.strategy_combo.clear()
        if strategies:
            self.strategy_combo.addItems(strategies)
            idx = self.strategy_combo.findText(current)
            if idx >= 0:
                self.strategy_combo.setCurrentIndex(idx)
        else:
            self.strategy_combo.addItem("(no strategies found)")
        self.strategy_combo.blockSignals(False)

        # Trigger run refresh for the (possibly new) current strategy
        self._refresh_runs()

    def _refresh_runs(self) -> None:
        """Populate run_combo for the currently selected strategy."""
        strategy = self.strategy_combo.currentText().strip()

        self.run_combo.blockSignals(True)
        self.run_combo.clear()
        self._run_data = []

        if strategy and not strategy.startswith("("):
            runs = self._improve_service.get_strategy_runs(strategy)
        else:
            runs = []

        if runs:
            for run in runs:
                label = _build_run_label(run)
                self.run_combo.addItem(label)
                self._run_data.append(run)
            self.analyze_btn.setEnabled(True)
        else:
            self.run_combo.addItem("(No saved runs found for this strategy)")
            self.analyze_btn.setEnabled(False)

        self.run_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_load_latest(self) -> None:
        """Select the most recent run (index 0, newest-first)."""
        if self.run_combo.count() > 0:
            self.run_combo.setCurrentIndex(0)

    def _on_analyze(self) -> None:
        """Load baseline, run diagnosis, and display issues and suggestions."""
        index = self.run_combo.currentIndex()
        if index < 0 or index >= len(self._run_data):
            return

        run = self._run_data[index]
        settings = self._settings_state.settings_service.load_settings()
        backtest_results_dir = Path(settings.user_data_path) / "backtest_results"
        run_dir = backtest_results_dir / run.get("run_dir", "")

        self.analyze_btn.setEnabled(False)
        self.status_label.setText("Loading...")

        try:
            baseline = self._improve_service.load_baseline(run_dir)
            params = self._improve_service.load_baseline_params(run_dir)
            self._baseline_run = baseline
            self._baseline_params = params
            self._candidate_config = copy.deepcopy(params)
            self._display_baseline_summary(baseline.summary)
            self._display_issues_and_suggestions(baseline.summary, params)
            self.status_label.setText("")
        except (FileNotFoundError, ValueError) as e:
            self.status_label.setText(f"Error: {e}")
        finally:
            self.analyze_btn.setEnabled(True)

    def _display_baseline_summary(self, summary: BacktestSummary) -> None:
        """Clear and repopulate the baseline summary form."""
        while self._baseline_form.rowCount() > 0:
            self._baseline_form.removeRow(0)

        self._baseline_form.addRow("Strategy:", QLabel(summary.strategy))
        self._baseline_form.addRow("Timeframe:", QLabel(summary.timeframe))
        self._baseline_form.addRow("Total Trades:", QLabel(str(summary.total_trades)))
        self._baseline_form.addRow("Win Rate:", QLabel(f"{summary.win_rate:.2f}%"))
        self._baseline_form.addRow("Total Profit:", QLabel(f"{summary.total_profit:.4f}%"))
        self._baseline_form.addRow("Max Drawdown:", QLabel(f"{summary.max_drawdown:.2f}%"))
        sharpe = f"{summary.sharpe_ratio:.4f}" if summary.sharpe_ratio is not None else "N/A"
        self._baseline_form.addRow("Sharpe Ratio:", QLabel(sharpe))
        self._baseline_form.addRow(
            "Date Range:", QLabel(f"{summary.backtest_start} → {summary.backtest_end}")
        )

        self.baseline_group.setVisible(True)

    def _display_issues_and_suggestions(self, summary: BacktestSummary, params: dict) -> None:
        """Run diagnosis and suggestion services, then populate the UI groups."""
        # Clear issues layout
        while self._issues_layout.count():
            item = self._issues_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        issues = ResultsDiagnosisService.diagnose(summary)

        if not issues:
            self._issues_layout.addWidget(QLabel("No issues detected — results look healthy"))
        else:
            for issue in issues:
                lbl = QLabel(f"• {issue.issue_id}: {issue.description}")
                lbl.setWordWrap(True)
                self._issues_layout.addWidget(lbl)

        self.issues_group.setVisible(True)

        # Clear suggestions layout
        while self._suggestions_layout.count():
            item = self._suggestions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        suggestions = RuleSuggestionService.suggest(issues, params)

        if not suggestions:
            self._suggestions_layout.addWidget(QLabel("No suggestions available"))
        else:
            for suggestion in suggestions:
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)

                value_text = "Advisory" if suggestion.is_advisory else str(suggestion.proposed_value)
                lbl = QLabel(
                    f"{suggestion.parameter}: {value_text} — "
                    f"{suggestion.reason} → {suggestion.expected_effect}"
                )
                lbl.setWordWrap(True)
                row_layout.addWidget(lbl, 1)

                apply_btn = QPushButton("Apply")
                apply_btn.clicked.connect(lambda checked=False, s=suggestion: self._on_apply_suggestion(s))
                row_layout.addWidget(apply_btn)

                self._suggestions_layout.addWidget(row_widget)

        self.suggestions_group.setVisible(True)

    def _on_apply_suggestion(self, suggestion: ParameterSuggestion) -> None:
        """Apply a suggestion to the candidate config and update the diff preview."""
        if suggestion.is_advisory:
            # Mark as applied in UI but don't add to candidate config diff
            _log.debug("Advisory suggestion applied (no param change): %s", suggestion.parameter)
            self._update_candidate_preview()
            return

        # Merge suggestion into candidate config
        self._candidate_config[suggestion.parameter] = suggestion.proposed_value
        _log.debug("Applied suggestion: %s = %s", suggestion.parameter, suggestion.proposed_value)
        self._update_candidate_preview()

    def _update_candidate_preview(self) -> None:
        """Recompute and display the diff between baseline and candidate config."""
        # Clear existing widgets
        while self._candidate_layout.count():
            item = self._candidate_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Clear sub-layouts
                sub = item.layout()
                while sub.count():
                    sub_item = sub.takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().deleteLater()

        diff = compute_diff(self._baseline_params or {}, self._candidate_config)

        if not diff:
            self._candidate_layout.addWidget(QLabel("No changes applied yet"))
        else:
            for key, value in diff.items():
                self._candidate_layout.addWidget(QLabel(f"{key}: {value}"))

        # Buttons row
        btn_row = QHBoxLayout()
        self.run_backtest_btn = QPushButton("Run Backtest on Candidate")
        self.run_backtest_btn.setEnabled(bool(diff))
        self.run_backtest_btn.clicked.connect(self._on_run_candidate)
        btn_row.addWidget(self.run_backtest_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._on_stop_candidate)
        btn_row.addWidget(self.stop_btn)

        self.reset_candidate_btn = QPushButton("Reset Candidate")
        self.reset_candidate_btn.clicked.connect(self._on_reset_candidate)
        btn_row.addWidget(self.reset_candidate_btn)

        btn_widget = QWidget()
        btn_widget.setLayout(btn_row)
        self._candidate_layout.addWidget(btn_widget)

        self._candidate_layout.addWidget(self._terminal)

        self.candidate_group.setVisible(True)

    def _on_reset_candidate(self) -> None:
        """Reset candidate config to baseline params."""
        if self._baseline_params is not None:
            self._candidate_config = copy.deepcopy(self._baseline_params)
        else:
            self._candidate_config = {}
        self._update_candidate_preview()

    def _on_run_candidate(self) -> None:
        """Prepare sandbox, build command, and start candidate backtest."""
        if self._baseline_run is None:
            return

        strategy_name = self.strategy_combo.currentText().strip()
        if not strategy_name or strategy_name.startswith("("):
            return

        try:
            sandbox_dir = self._improve_service.prepare_sandbox(strategy_name, self._candidate_config)
            self._sandbox_dir = sandbox_dir
        except FileNotFoundError as e:
            self.status_label.setText(f"Error: {e}")
            return

        command, export_dir = self._improve_service.build_candidate_command(
            strategy_name, self._baseline_run, sandbox_dir
        )
        self._export_dir = export_dir
        self._run_started_at = time.time()

        # Disable run button, show stop button
        self.run_backtest_btn.setEnabled(False)
        self.stop_btn.setVisible(True)

        # Stream to terminal
        self._terminal.clear_output()
        self._terminal.append_output(f"$ {' '.join(command.as_list())}\n\n")

        # Get settings for environment
        settings = self._settings_state.settings_service.load_settings()
        from app.core.services.process_service import ProcessService
        env = None
        if settings.venv_path:
            env = ProcessService.build_environment(settings.venv_path)

        try:
            self._terminal.process_service.execute_command(
                command=command.as_list(),
                on_output=self._terminal.append_output,
                on_error=self._terminal.append_error,
                on_finished=self._on_candidate_finished,
                working_directory=command.cwd,
                env=env,
            )
        except Exception as e:
            self.status_label.setText(f"Process error: {e}")
            self.run_backtest_btn.setEnabled(True)
            self.stop_btn.setVisible(False)

    def _on_stop_candidate(self) -> None:
        """Stop the running candidate backtest."""
        self._terminal.process_service.stop_process()
        self.run_backtest_btn.setEnabled(True)
        self.stop_btn.setVisible(False)

    def _on_candidate_finished(self, exit_code: int) -> None:
        """Handle candidate backtest process completion."""
        self.run_backtest_btn.setEnabled(True)
        self.stop_btn.setVisible(False)

        self._terminal.append_output(f"\n[Process finished] exit_code={exit_code}\n")

        if exit_code == 0:
            try:
                candidate_run = self._improve_service.parse_candidate_run(
                    self._export_dir, self._run_started_at
                )
                self._candidate_run = candidate_run
                self._update_comparison_view()
            except (FileNotFoundError, ValueError) as e:
                self.status_label.setText(f"Error loading candidate results: {e}")
        else:
            self.status_label.setText("Candidate backtest failed — see terminal output")

    def _update_comparison_view(self) -> None:
        """Build or rebuild the comparison table when both runs are available."""
        # Clear all items from comparison layout
        while self._comparison_layout.count():
            item = self._comparison_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._baseline_run is None or self._candidate_run is None:
            self.comparison_group.setVisible(False)
            return

        METRICS = [
            ("total_trades", "Total Trades", lambda s: float(s.total_trades)),
            ("win_rate", "Win Rate (%)", lambda s: s.win_rate),
            ("total_profit", "Total Profit (%)", lambda s: s.total_profit),
            ("max_drawdown", "Max Drawdown (%)", lambda s: s.max_drawdown),
            ("sharpe_ratio", "Sharpe Ratio", lambda s: s.sharpe_ratio or 0.0),
            ("profit_factor", "Profit Factor", lambda s: s.profit_factor),
            ("expectancy", "Expectancy", lambda s: s.expectancy),
        ]

        table = QTableWidget(len(METRICS), 3)
        table.setHorizontalHeaderLabels(["Metric", "Baseline", "Candidate"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)

        baseline_summary = self._baseline_run.summary
        candidate_summary = self._candidate_run.summary

        for row, (metric_key, display_name, getter) in enumerate(METRICS):
            baseline_val = getter(baseline_summary)
            candidate_val = getter(candidate_summary)

            # Format values
            if metric_key == "total_trades":
                b_str = str(int(baseline_val))
                c_str = str(int(candidate_val))
            elif metric_key in ("win_rate", "total_profit", "max_drawdown"):
                b_str = f"{baseline_val:.2f}%"
                c_str = f"{candidate_val:.2f}%"
            else:
                b_str = f"{baseline_val:.4f}"
                c_str = f"{candidate_val:.4f}"

            table.setItem(row, 0, QTableWidgetItem(display_name))
            table.setItem(row, 1, QTableWidgetItem(b_str))

            candidate_item = QTableWidgetItem(c_str)
            color = compute_highlight(metric_key, baseline_val, candidate_val)
            if color == "green":
                candidate_item.setBackground(QColor("#2ecc71"))
            elif color == "red":
                candidate_item.setBackground(QColor("#e74c3c"))
            table.setItem(row, 2, candidate_item)

        self._comparison_layout.addWidget(table)

        # Re-add accept/reject/rollback buttons
        self.accept_btn.setVisible(True)
        self.reject_btn.setVisible(True)
        self.rollback_btn.setVisible(len(self._baseline_history) > 0)

        arb_row = QHBoxLayout()
        arb_row.addWidget(self.accept_btn)
        arb_row.addWidget(self.reject_btn)
        arb_row.addWidget(self.rollback_btn)
        arb_widget = QWidget()
        arb_widget.setLayout(arb_row)
        self._comparison_layout.addWidget(arb_widget)

        self.comparison_group.setVisible(True)

    def _on_accept(self) -> None:
        """Accept the candidate: write params, promote candidate to baseline."""
        if self._candidate_run is None or self._baseline_params is None:
            return

        strategy_name = self.strategy_combo.currentText().strip()
        if not strategy_name or strategy_name.startswith("("):
            return

        try:
            self._improve_service.accept_candidate(strategy_name, self._candidate_config)
        except OSError as e:
            QMessageBox.critical(self, "Accept Failed", str(e))
            return

        # Update all state atomically before any UI refresh
        self._baseline_history.append(copy.deepcopy(self._baseline_params))
        self._baseline_params = copy.deepcopy(self._candidate_config)
        self._baseline_run = self._candidate_run
        self._candidate_run = None
        self._candidate_config = copy.deepcopy(self._baseline_params)

        # Single UI refresh after all state is updated
        self._update_comparison_view()
        self.status_label.setText("Candidate accepted — strategy parameters updated")
        _log.info("Candidate accepted for strategy '%s'", strategy_name)

    def _on_reject(self) -> None:
        """Reject the candidate: clean up sandbox, reset candidate config."""
        if self._sandbox_dir is not None:
            self._improve_service.reject_candidate(self._sandbox_dir)
            self._sandbox_dir = None

        self._candidate_run = None
        self._candidate_config = copy.deepcopy(self._baseline_params) if self._baseline_params else {}

        self._update_comparison_view()
        self._update_candidate_preview()
        _log.info("Candidate rejected")

    def _on_rollback(self) -> None:
        """Rollback to the previous baseline params."""
        if not self._baseline_history:
            return

        strategy_name = self.strategy_combo.currentText().strip()
        if not strategy_name or strategy_name.startswith("("):
            return

        try:
            self._improve_service.rollback(strategy_name, self._baseline_history[-1])
        except OSError as e:
            QMessageBox.critical(self, "Rollback Failed", str(e))
            return

        # Pop snapshot and restore
        popped = self._baseline_history.pop()
        self._baseline_params = popped
        self._candidate_run = None
        self._candidate_config = copy.deepcopy(self._baseline_params)

        self._update_comparison_view()
        self._update_candidate_preview()
        self.status_label.setText("Rolled back to previous baseline parameters")
        _log.info("Rolled back to previous baseline for strategy '%s'", strategy_name)
