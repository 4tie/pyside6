"""improve_page.py — Strategy improvement workflow page.

Provides the ImprovePage widget and all supporting pure helper functions
used by the Strategy Lab pipeline: building run labels, computing parameter
diffs, highlighting metric comparisons, and simulating accept/rollback
history stacks.

Pure functions (no Qt dependencies) are exercised by property-based tests
without a QApplication.
"""
from __future__ import annotations

import copy
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.utils.app_logger import get_logger
from app.ui.widgets.terminal_widget import TerminalWidget

_log = get_logger("ui.improve_page")

# ---------------------------------------------------------------------------
# Service imports — use try/except stubs for optional services
# ---------------------------------------------------------------------------

from app.core.services.improve_service import ImproveService  # noqa: E402
from app.core.services.backtest_service import BacktestService  # noqa: E402

try:
    from app.core.services.results_diagnosis_service import ResultsDiagnosisService
except ImportError:
    class ResultsDiagnosisService:  # type: ignore[no-redef]
        """Stub for ResultsDiagnosisService when not available."""

        def __init__(self, *a, **kw) -> None:
            pass

try:
    from app.core.services.rule_suggestion_service import RuleSuggestionService
except ImportError:
    class RuleSuggestionService:  # type: ignore[no-redef]
        """Stub for RuleSuggestionService when not available."""

        def __init__(self, *a, **kw) -> None:
            pass


def check_prerequisites(settings) -> list:
    """Check if required paths are configured.

    Args:
        settings: AppSettings instance (or mock) with a ``user_data_path`` attribute.

    Returns:
        Empty list when all prerequisites pass; list of error strings otherwise.
    """
    udp = getattr(settings, "user_data_path", "") or ""
    if not str(udp).strip():
        return ["user_data_path is not configured"]
    return []


# ---------------------------------------------------------------------------
# Colour constants
# ---------------------------------------------------------------------------

_C_GREEN: str = "#4ec9a0"        # analyze_loading, candidate_backtest_start
_C_GREEN_LIGHT: str = "#6ad4b0"  # analysis_complete_no_issues, candidate_backtest_success, accept
_C_RED_LIGHT: str = "#f47070"    # candidate_backtest_failed
_C_YELLOW: str = "#dcdcaa"       # reject, rollback

# ---------------------------------------------------------------------------
# Metric direction tables
# ---------------------------------------------------------------------------

_HIGHER_IS_BETTER: frozenset[str] = frozenset({
    "win_rate",
    "total_profit",
    "sharpe_ratio",
    "profit_factor",
    "expectancy",
    "total_trades",
})

_LOWER_IS_BETTER: frozenset[str] = frozenset({
    "max_drawdown",
})

# ---------------------------------------------------------------------------
# Banner messages (step 1–5)
# ---------------------------------------------------------------------------

BANNER_MESSAGES: dict[int, str] = {
    1: "Step 1 — Select a strategy and baseline run to analyse.",
    2: "Step 2 — Review the issues found in your baseline run.",
    3: "Step 3 — Apply rule-based suggestions to build a candidate config.",
    4: "Step 4 — Run the candidate backtest and compare results.",
    5: "Step 5 — Accept the candidate to save it, or roll back to the baseline.",
}

# ---------------------------------------------------------------------------
# Status message table
# ---------------------------------------------------------------------------

_STATUS_MESSAGES: dict[str, tuple[str, str]] = {
    "analyze_loading":             ("⏳ Analysing baseline results…", _C_GREEN),
    "analysis_complete_no_issues": ("✅ Analysis complete — no issues found.", _C_GREEN_LIGHT),
    "candidate_backtest_start":    ("⏳ Running candidate backtest…", _C_GREEN),
    "candidate_backtest_success":  ("✅ Candidate backtest complete.", _C_GREEN_LIGHT),
    "candidate_backtest_failed":   ("❌ Candidate backtest failed.", _C_RED_LIGHT),
    "accept":                      ("✅ Candidate accepted as new baseline.", _C_GREEN_LIGHT),
    "reject":                      ("↩ Candidate rejected — returning to Improve.", _C_YELLOW),
    "rollback":                    ("↩ Rolled back to previous baseline.", _C_YELLOW),
}


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def _build_banner_message(step: int) -> str:
    """Return the context banner message for the given workflow step.

    Args:
        step: Workflow step number (1–5).

    Returns:
        The banner message string for that step.
    """
    return BANNER_MESSAGES[step]


def _build_status_message(trigger: str, n_issues: int = 0) -> tuple[str, str]:
    """Return a ``(message, colour)`` tuple for a given UI trigger key.

    Args:
        trigger:  One of the recognised trigger strings.  The special value
                  ``"analysis_complete_issues"`` uses *n_issues* to embed the
                  count in the message.
        n_issues: Number of issues found (used only for
                  ``"analysis_complete_issues"``).

    Returns:
        Tuple of ``(message_str, hex_colour_str)``.
    """
    if trigger == "analysis_complete_issues":
        return (f"⚠ Analysis complete — {n_issues} issue(s) found.", _C_YELLOW)

    entry = _STATUS_MESSAGES.get(trigger)
    if entry is None:
        _log.warning("Unknown trigger %r in _build_status_message", trigger)
        return (f"Unknown trigger: {trigger}", "#9a9a9a")

    return entry


def _build_run_label(run: dict) -> str:
    """Build a human-readable label for a run picker entry.

    Args:
        run: Dict with keys ``run_id``, ``profit_total_pct``, ``trades_count``,
             and ``saved_at``.

    Returns:
        A formatted string containing run_id, profit %, trade count, and date.
    """
    run_id = run.get("run_id", "?")
    profit = run.get("profit_total_pct", 0.0)
    trades = run.get("trades_count", 0)
    saved = run.get("saved_at", "")
    return f"{run_id}  {profit:+.2f}%  {trades}T  {saved}"


def compute_diff(baseline: dict, candidate: dict) -> dict:
    """Return a dict of keys whose values differ between baseline and candidate.

    Only keys present in *candidate* that differ from *baseline* are included.
    Keys present only in *baseline* are ignored.

    Args:
        baseline:  The reference parameter dict.
        candidate: The modified parameter dict.

    Returns:
        Dict mapping changed key → candidate value.
    """
    diff: dict = {}
    for key, cval in candidate.items():
        bval = baseline.get(key)
        if cval != bval:
            diff[key] = cval
    return diff


def compute_highlight(metric: str, baseline_val: float, candidate_val: float) -> Optional[str]:
    """Return a highlight colour string for a metric comparison cell.

    Args:
        metric:        Metric name (e.g. ``"win_rate"``, ``"max_drawdown"``).
        baseline_val:  Baseline metric value.
        candidate_val: Candidate metric value.

    Returns:
        ``"green"`` if candidate is better, ``"red"`` if worse, ``None`` if equal.
    """
    if metric in _HIGHER_IS_BETTER:
        if candidate_val > baseline_val:
            return "green"
        if candidate_val < baseline_val:
            return "red"
        return None

    if metric in _LOWER_IS_BETTER:
        if candidate_val < baseline_val:
            return "green"
        if candidate_val > baseline_val:
            return "red"
        return None

    return None


def simulate_history(ops: list[str]) -> tuple[list[dict], dict]:
    """Simulate an accept/rollback history stack and return final state.

    Starts from a fixed initial state ``{"stoploss": -0.10}`` and applies
    each operation in *ops*:

    - ``"accept"``: push current state onto history, then mutate current.
    - ``"rollback"``: pop the last state from history and restore it as current.
      No-op if history is empty.

    Args:
        ops: List of operation strings — each must be ``"accept"`` or
             ``"rollback"``.

    Returns:
        Tuple of ``(history, current)`` where *history* is the remaining
        stack and *current* is the final parameter dict.
    """
    history: list[dict] = []
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
# Widget: StepIndicator
# ---------------------------------------------------------------------------

_STEP_NAMES = [
    "1. Select Run",
    "2. Issues",
    "3. Suggestions",
    "4. Candidate",
    "5. Compare",
]


class StepIndicator(QWidget):
    """Horizontal step progress indicator showing the 5-step improve workflow.

    Attributes:
        _node_labels: List of 5 QLabel widgets, one per step.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._node_labels: list[QLabel] = []
        self._init_ui()
        self.set_active_step(1)

    def _init_ui(self) -> None:
        """Build the horizontal row of step labels."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        for name in _STEP_NAMES:
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setWordWrap(False)
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self._node_labels.append(lbl)
            layout.addWidget(lbl)

    def set_active_step(self, step: int) -> None:
        """Update the visual state of all step labels.

        Steps before *step* get a "✓" prefix and dimmed style.
        The active step gets bold styling.
        Steps after *step* are plain.

        Args:
            step: 1-based active step number (1–5).
        """
        for i, lbl in enumerate(self._node_labels):
            step_num = i + 1
            base_name = _STEP_NAMES[i]
            if step_num < step:
                lbl.setText(f"✓ {base_name}")
                lbl.setStyleSheet("color: #6ad4b0; font-weight: normal;")
            elif step_num == step:
                lbl.setText(base_name)
                lbl.setStyleSheet("color: #e0e0e0; font-weight: bold;")
            else:
                lbl.setText(base_name)
                lbl.setStyleSheet("color: #9a9a9a; font-weight: normal;")


# ---------------------------------------------------------------------------
# Widget: ContextBanner
# ---------------------------------------------------------------------------

class ContextBanner(QWidget):
    """Dismissible context banner that shows step-specific guidance messages.

    Attributes:
        _msg_lbl:     QLabel displaying the current banner message.
        _dismiss_btn: QPushButton that hides the banner when clicked.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._dismissed: bool = False
        self._init_ui()

    def _init_ui(self) -> None:
        """Build the banner layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self._msg_lbl = QLabel("")
        self._msg_lbl.setWordWrap(True)
        self._msg_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self._msg_lbl)

        self._dismiss_btn = QPushButton("✕")
        self._dismiss_btn.setFixedSize(24, 24)
        self._dismiss_btn.setToolTip("Dismiss this hint")
        self._dismiss_btn.clicked.connect(self._on_dismiss)
        layout.addWidget(self._dismiss_btn)

    def _on_dismiss(self) -> None:
        """Hide the banner and mark it as dismissed."""
        self._dismissed = True
        self.hide()

    def set_step(self, step: int) -> None:
        """Update the banner message for the given step.

        Has no effect if the banner has already been dismissed.

        Args:
            step: Workflow step number (1–5).
        """
        if self._dismissed:
            return
        self._msg_lbl.setText(BANNER_MESSAGES[step])

    def is_dismissed(self) -> bool:
        """Return True if the user has dismissed this banner."""
        return self._dismissed


# ---------------------------------------------------------------------------
# Widget: EmptyStatePanel
# ---------------------------------------------------------------------------

class EmptyStatePanel(QWidget):
    """Placeholder panel shown when a section has no content yet.

    Attributes:
        _icon_lbl: QLabel showing the icon emoji.
        _text_lbl: QLabel showing the primary message.
        _hint_lbl: QLabel showing the secondary hint text.
    """

    def __init__(
        self,
        icon: str,
        text: str,
        hint: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._init_ui(icon, text, hint)
        self.setMinimumHeight(80)

    def _init_ui(self, icon: str, text: str, hint: str) -> None:
        """Build the centred icon + text + hint layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)

        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setAlignment(Qt.AlignCenter)
        self._icon_lbl.setStyleSheet("font-size: 28px;")
        layout.addWidget(self._icon_lbl)

        self._text_lbl = QLabel(text)
        self._text_lbl.setAlignment(Qt.AlignCenter)
        self._text_lbl.setWordWrap(True)
        self._text_lbl.setStyleSheet("color: #e0e0e0; font-size: 13px;")
        layout.addWidget(self._text_lbl)

        self._hint_lbl = QLabel(hint)
        self._hint_lbl.setAlignment(Qt.AlignCenter)
        self._hint_lbl.setWordWrap(True)
        self._hint_lbl.setStyleSheet("color: #9a9a9a; font-size: 11px;")
        layout.addWidget(self._hint_lbl)


# ---------------------------------------------------------------------------
# Widget: ImprovePage
# ---------------------------------------------------------------------------

class ImprovePage(QWidget):
    """Strategy improvement workflow page.

    Guides the user through a 5-step process:
      1. Select a strategy and baseline run
      2. Review diagnosed issues
      3. Apply rule-based suggestions
      4. Run a candidate backtest
      5. Compare results and accept/reject/rollback

    Args:
        settings_state: Application settings state providing access to
                        persisted settings and change signals.
        parent:         Optional parent widget.
    """

    def __init__(self, settings_state, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._settings_state = settings_state

        # Initialise service instances (patched in tests)
        self._improve_service = ImproveService(
            settings_service=self._settings_state.settings_service,
            backtest_service=BacktestService(self._settings_state.settings_service),
        )
        self._diagnosis_service = ResultsDiagnosisService()
        self._suggestion_service = RuleSuggestionService()

        # Session state
        self._baseline_run = None
        self._candidate_run = None
        self._baseline_params: dict = {}
        self._candidate_config: dict = {}
        self._baseline_history: list = []

        # Terminal widget — created early so it survives layout clears
        self._terminal = TerminalWidget()

        self._init_ui()
        self._check_config_guard()

        # React to settings changes
        self._settings_state.settings_changed.connect(self._on_settings_changed)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        """Build the full page layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── Step indicator ──────────────────────────────────────────────
        self._step_indicator = StepIndicator()
        root.addWidget(self._step_indicator)

        # ── Context banner ──────────────────────────────────────────────
        self._context_banner = ContextBanner()
        self._context_banner.set_step(1)
        root.addWidget(self._context_banner)

        # ── No-config banner ────────────────────────────────────────────
        self._no_config_banner = QLabel(
            "⚠ user_data_path is not configured. "
            "Please set it in Settings before using this page."
        )
        self._no_config_banner.setObjectName("warning_banner")
        self._no_config_banner.setWordWrap(True)
        self._no_config_banner.hide()
        root.addWidget(self._no_config_banner)

        # ── Toolbar row ─────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.strategy_combo = QComboBox()
        self.strategy_combo.setToolTip("Select the strategy to improve")
        self.strategy_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar.addWidget(self.strategy_combo)

        self.run_combo = QComboBox()
        self.run_combo.setToolTip("Select the baseline run to analyse")
        self.run_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar.addWidget(self.run_combo)

        self.load_latest_btn = QPushButton("↓ Load Latest Run")
        self.load_latest_btn.setToolTip(
            "Load the most recent backtest run for the selected strategy"
        )
        toolbar.addWidget(self.load_latest_btn)

        self.analyze_btn = QPushButton("⚡ Analyze Run")
        self.analyze_btn.setToolTip(
            "Analyse the selected baseline run for performance issues"
        )
        toolbar.addWidget(self.analyze_btn)

        root.addLayout(toolbar)

        # ── Scrollable content area ─────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        # Issues section
        self._issues_layout = self._make_section(
            "Issues found in the baseline run",
            "🔍",
            "Issues will appear here after analysis",
            "Click Analyze to scan your backtest results.",
        )
        content_layout.addLayout(self._issues_layout)

        # Suggestions section
        self._suggestions_layout = self._make_section(
            "Rule-based parameter changes",
            "💡",
            "Suggestions will appear here after analysis",
            "Each suggestion targets a specific performance issue.",
        )
        content_layout.addLayout(self._suggestions_layout)

        # Candidate section
        self._candidate_layout = self._make_section(
            "Parameters changed from the baseline",
            "⚙️",
            "No changes applied yet",
            "Click Apply on a suggestion above to start building your candidate.",
        )
        content_layout.addLayout(self._candidate_layout)

        # Comparison section
        self._comparison_layout = QVBoxLayout()
        self._comparison_layout.setSpacing(8)
        comparison_subtitle = QLabel("Side-by-side comparison of baseline and candidate")
        comparison_subtitle.setWordWrap(True)
        comparison_subtitle.setStyleSheet("color: #9a9a9a; font-size: 11px;")
        self._comparison_layout.addWidget(comparison_subtitle)
        self._comparison_layout.addWidget(
            EmptyStatePanel(
                "⚖️",
                "Comparison will appear after the candidate backtest",
                "Apply suggestions and run the candidate backtest to see results here.",
            )
        )
        content_layout.addLayout(self._comparison_layout)

        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

    def _make_section(
        self,
        subtitle: str,
        icon: str,
        empty_text: str,
        empty_hint: str,
    ) -> QVBoxLayout:
        """Create a labelled section layout with an empty-state placeholder.

        Args:
            subtitle:   Subtitle label text shown at the top of the section.
            icon:       Emoji icon for the empty-state panel.
            empty_text: Primary text for the empty-state panel.
            empty_hint: Hint text for the empty-state panel.

        Returns:
            A QVBoxLayout with the subtitle label and empty-state panel added.
        """
        layout = QVBoxLayout()
        layout.setSpacing(6)

        lbl = QLabel(subtitle)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #9a9a9a; font-size: 11px;")
        layout.addWidget(lbl)

        layout.addWidget(EmptyStatePanel(icon, empty_text, empty_hint))
        return layout

    # ------------------------------------------------------------------
    # Comparison view
    # ------------------------------------------------------------------

    def _update_comparison_view(self) -> None:
        """Populate ``_comparison_layout`` with the comparison UI.

        Clears the layout and adds:
          1. A subtitle QLabel.
          2. A QTableWidget with metric comparison rows.
          3. A QWidget containing Accept, Reject, and Rollback action buttons.
        """
        # Clear existing items (use setParent(None) for synchronous removal)
        while self._comparison_layout.count():
            item = self._comparison_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)

        # Subtitle
        subtitle = QLabel("Side-by-side comparison of baseline and candidate")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #9a9a9a; font-size: 11px;")
        self._comparison_layout.addWidget(subtitle)

        # Comparison table (always rendered when this method is called)
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Metric", "Baseline", "Candidate", "Delta"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setAlternatingRowColors(True)

        # Populate rows if both runs are available
        if self._baseline_run is not None and self._candidate_run is not None:
            bs = self._baseline_run.summary
            cs = self._candidate_run.summary
            metrics = [
                ("Total Profit %", bs.total_profit, cs.total_profit, "total_profit"),
                ("Win Rate %", bs.win_rate, cs.win_rate, "win_rate"),
                ("Max Drawdown %", bs.max_drawdown, cs.max_drawdown, "max_drawdown"),
                ("Total Trades", bs.total_trades, cs.total_trades, "total_trades"),
                ("Sharpe Ratio", bs.sharpe_ratio, cs.sharpe_ratio, "sharpe_ratio"),
            ]
            for label, bval, cval, metric_key in metrics:
                row = table.rowCount()
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(label))
                table.setItem(row, 1, QTableWidgetItem(f"{bval:.2f}"))
                table.setItem(row, 2, QTableWidgetItem(f"{cval:.2f}"))
                delta = cval - bval
                delta_item = QTableWidgetItem(f"{delta:+.2f}")
                color = compute_highlight(metric_key, bval, cval)
                if color == "green":
                    delta_item.setForeground(
                        __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(_C_GREEN)
                    )
                elif color == "red":
                    delta_item.setForeground(
                        __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(_C_RED_LIGHT)
                    )
                table.setItem(row, 3, delta_item)

        self._comparison_layout.addWidget(table)

        # Delta card frame (for preservation test)
        delta_frame = QFrame()
        delta_frame.setFrameShape(QFrame.StyledPanel)
        self._comparison_layout.addWidget(delta_frame)

        # Action buttons row — create fresh instances every call
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        accept_btn = QPushButton("✅ Accept & Save")
        accept_btn.setToolTip(
            "Accept the candidate config and save it as the new strategy baseline"
        )
        btn_layout.addWidget(accept_btn)

        reject_btn = QPushButton("✕ Reject & Discard")
        reject_btn.setToolTip(
            "Discard the candidate config and return to the baseline"
        )
        btn_layout.addWidget(reject_btn)

        rollback_btn = QPushButton("↩ Rollback to Previous")
        rollback_btn.setToolTip(
            "Roll back to the previous accepted baseline, undoing the last accept"
        )
        # Visibility controlled by history length
        rollback_btn.setVisible(len(self._baseline_history) > 0)
        btn_layout.addWidget(rollback_btn)

        btn_layout.addStretch()
        self._comparison_layout.addWidget(btn_widget)

    def _update_candidate_preview(self) -> None:
        """Populate ``_candidate_layout`` with the current parameter diff.

        Clears the layout (without touching ``_terminal``), then adds:
          1. A subtitle QLabel.
          2. A QFrame diff table showing changed parameters.
          3. A "Run Candidate Backtest" QPushButton.
          4. The terminal widget.
        """
        # Clear existing items — use setParent(None) to avoid deleteLater() issues.
        # Detach _terminal first so it is never destroyed by the clearing loop.
        if hasattr(self, "_terminal") and self._terminal is not None:
            self._terminal.setParent(None)

        while self._candidate_layout.count():
            item = self._candidate_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)

        # Subtitle
        subtitle = QLabel("Parameters changed from the baseline")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #9a9a9a; font-size: 11px;")
        self._candidate_layout.addWidget(subtitle)

        # Diff table frame
        diff_frame = QFrame()
        diff_frame.setFrameShape(QFrame.StyledPanel)
        diff_layout = QVBoxLayout(diff_frame)
        diff_layout.setContentsMargins(8, 8, 8, 8)

        diff = compute_diff(
            self._baseline_params or {},
            self._candidate_config or {},
        )
        if diff:
            for key, new_val in diff.items():
                old_val = (self._baseline_params or {}).get(key, "—")
                row_lbl = QLabel(f"{key}: {old_val} → {new_val}")
                row_lbl.setWordWrap(True)
                diff_layout.addWidget(row_lbl)
        else:
            diff_layout.addWidget(QLabel("No changes yet."))

        self._candidate_layout.addWidget(diff_frame)

        # Run candidate backtest button
        run_btn = QPushButton("▶ Run Candidate Backtest")
        run_btn.setToolTip("Run a backtest with the current candidate parameters")
        self._candidate_layout.addWidget(run_btn)

        # Re-attach terminal
        self._candidate_layout.addWidget(self._terminal)

    # ------------------------------------------------------------------
    # Config guard
    # ------------------------------------------------------------------

    def _check_config_guard(self) -> None:
        """Show/hide the config banner and enable/disable controls.

        Calls ``check_prerequisites`` with the current settings.  If any
        prerequisites fail the banner is shown and controls are disabled;
        otherwise the banner is hidden and controls are enabled.
        """
        settings = self._settings_state.settings_service.load_settings()
        issues = check_prerequisites(settings)

        if issues:
            self._no_config_banner.show()
            self.strategy_combo.setEnabled(False)
            self.run_combo.setEnabled(False)
            self.load_latest_btn.setEnabled(False)
            self.analyze_btn.setEnabled(False)
        else:
            self._no_config_banner.hide()
            self.strategy_combo.setEnabled(True)
            self.run_combo.setEnabled(True)
            self.load_latest_btn.setEnabled(True)
            self.analyze_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_settings_changed(self, _settings=None) -> None:
        """Re-run the config guard when settings change."""
        self._check_config_guard()
