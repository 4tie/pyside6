"""
improve_page.py — ImprovePage: strategy improvement workflow UI.

Enhanced with animated metric cards, color-coded severity indicators,
progress bar gauges, and animated comparison deltas.
"""
import copy
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QScrollArea, QFormLayout, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
    QProgressBar, QFrame, QGraphicsOpacityEffect, QGridLayout,
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QSequentialAnimationGroup
from PySide6.QtGui import QColor, QFont, QPalette

from app.app_state.settings_state import SettingsState
from app.core.backtests.results_models import BacktestResults, BacktestSummary
from app.core.models.diagnosis_models import DiagnosisInput
from app.core.models.improve_models import DiagnosedIssue, ParameterSuggestion, SessionBaseline, SessionRound
from app.core.services.backtest_service import BacktestService
from app.core.services.improve_service import ImproveService
from app.core.services.results_diagnosis_service import ResultsDiagnosisService
from app.core.services.rule_suggestion_service import RuleSuggestionService
from app.core.utils.app_logger import get_logger
from app.ui.widgets.animated_metric_card import AnimatedMetricCard
from app.ui.widgets.issue_badge import IssueBadge
from app.ui.widgets.suggestion_row import SuggestionRow
from app.ui.widgets.terminal_widget import TerminalWidget

_log = get_logger("ui.improve_page")

# ---------------------------------------------------------------------------
# Color palette — mirrors app/ui/theme.py PALETTE exactly
# ---------------------------------------------------------------------------
_C_GREEN = "#4ec9a0"          # success / profit positive (mint-green = theme accent)
_C_GREEN_LIGHT = "#6ad4b0"    # lighter mint for highlights
_C_RED = "#f44747"            # danger / loss (VS Code red)
_C_RED_LIGHT = "#f47070"      # softer red for text
_C_ORANGE = "#ce9178"         # warning (VS Code orange-brown)
_C_YELLOW = "#dcdcaa"         # VS Code yellow — advisory labels
_C_TEAL = "#4ec9a0"           # accent (same as _C_GREEN — mint)
_C_TEAL_HOVER = "#6ad4b0"
_C_DARK_BG = "#1e1e1e"        # bg_base
_C_CARD_BG = "#252526"        # bg_surface
_C_ELEVATED = "#2d2d30"       # bg_elevated
_C_CARD_HIGH = "#333337"      # bg_card
_C_BORDER = "#3e3e42"         # border
_C_TEXT = "#d4d4d4"           # text_primary
_C_TEXT_DIM = "#9d9d9d"       # text_secondary


# ---------------------------------------------------------------------------
# Helper widgets (imported from app.ui.widgets.*)
# ---------------------------------------------------------------------------
# AnimatedMetricCard, IssueBadge, SuggestionRow are imported at the top of
# this file from their respective widget modules. The inline definitions have
# been removed.


def _fade_in_widget(widget: QWidget, duration: int = 350) -> None:
    """Animate a widget fading in from transparent to opaque."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start()
    # Keep reference alive
    widget._fade_anim = anim


class StepIndicator(QWidget):
    """Horizontal workflow step indicator showing five named stages."""

    STEPS = [
        (1, "Select"),
        (2, "Analyze"),
        (3, "Apply"),
        (4, "Backtest"),
        (5, "Decide"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._node_labels: List[QLabel] = []
        self._connector_lines: List[QFrame] = []
        self._build_ui()
        self.set_active_step(1)

    def _build_ui(self) -> None:
        """Build the horizontal step node layout."""
        self.setFixedHeight(48)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(f"background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(0)

        for i, (num, label) in enumerate(self.STEPS):
            node_lbl = QLabel(f"{num} · {label}")
            node_lbl.setAlignment(Qt.AlignCenter)
            node_lbl.setMinimumWidth(80)
            self._node_labels.append(node_lbl)
            layout.addWidget(node_lbl)

            if i < len(self.STEPS) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.HLine)
                line.setFixedHeight(2)
                line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self._connector_lines.append(line)
                layout.addWidget(line, 1)

    def set_active_step(self, step: int) -> None:
        """Set the currently active step (1–5). Steps < active are complete.

        Args:
            step: The active workflow step number (1–5).
        """
        for i, (num, label) in enumerate(self.STEPS):
            lbl = self._node_labels[i]
            if num < step:
                # Complete
                lbl.setText(f"✓ {num} · {label}")
                lbl.setStyleSheet(
                    f"color: {_C_TEXT_DIM}; font-size: 11px; font-weight: normal;"
                )
            elif num == step:
                # Active
                lbl.setText(f"{num} · {label}")
                lbl.setStyleSheet(
                    f"color: {_C_GREEN}; font-size: 11px; font-weight: bold;"
                )
            else:
                # Pending
                lbl.setText(f"{num} · {label}")
                lbl.setStyleSheet(
                    f"color: {_C_TEXT_DIM}; font-size: 11px; font-weight: normal;"
                )

        # Update connector line colors
        for i, line in enumerate(self._connector_lines):
            # Connector i connects step (i+1) to step (i+2)
            if i + 2 <= step:
                # Completed segment
                line.setStyleSheet(f"background: {_C_GREEN}; border: none;")
            else:
                # Pending segment
                line.setStyleSheet(f"background: {_C_BORDER}; border: none;")


class ContextBanner(QWidget):
    """Dismissible instruction banner showing per-step guidance text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dismissed = False
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the banner layout."""
        self.setStyleSheet(f"""
            ContextBanner {{
                background: {_C_ELEVATED};
                border-left: 3px solid {_C_GREEN};
                border-radius: 4px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)
        layout.setSpacing(8)

        self._msg_lbl = QLabel("")
        self._msg_lbl.setTextFormat(Qt.RichText)
        self._msg_lbl.setWordWrap(True)
        self._msg_lbl.setStyleSheet(
            f"color: {_C_TEXT}; font-size: 12px; background: transparent; border: none;"
        )
        layout.addWidget(self._msg_lbl, 1)

        self._dismiss_btn = QPushButton("✕")
        self._dismiss_btn.setFixedSize(20, 20)
        self._dismiss_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {_C_TEXT_DIM};
                border: none;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {_C_TEXT};
            }}
        """)
        self._dismiss_btn.clicked.connect(self._on_dismiss)
        layout.addWidget(self._dismiss_btn)

    def _on_dismiss(self) -> None:
        """Handle dismiss button click."""
        self._dismissed = True
        self.hide()

    def set_step(self, step: int) -> None:
        """Update the displayed message for the given step. No-op if dismissed.

        Args:
            step: Workflow step number (1–5).
        """
        if self._dismissed:
            return
        self._msg_lbl.setText(_build_banner_message(step))
        self.setVisible(True)

    def is_dismissed(self) -> bool:
        """Return True if the user has dismissed the banner this session."""
        return self._dismissed


class EmptyStatePanel(QWidget):
    """Placeholder shown inside a group box when it has no data yet."""

    def __init__(self, icon: str, text: str, hint: str, parent=None):
        super().__init__(parent)
        self._build_ui(icon, text, hint)

    def _build_ui(self, icon: str, text: str, hint: str) -> None:
        """Build the vertically centered placeholder layout."""
        self.setMinimumHeight(80)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignCenter)

        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setAlignment(Qt.AlignCenter)
        self._icon_lbl.setStyleSheet(
            f"color: {_C_TEXT_DIM}; font-size: 28px; background: transparent; border: none;"
        )
        layout.addWidget(self._icon_lbl)

        self._text_lbl = QLabel(text)
        self._text_lbl.setAlignment(Qt.AlignCenter)
        self._text_lbl.setStyleSheet(
            f"color: {_C_TEXT_DIM}; font-size: 13px; background: transparent; border: none;"
        )
        layout.addWidget(self._text_lbl)

        self._hint_lbl = QLabel(hint)
        self._hint_lbl.setAlignment(Qt.AlignCenter)
        self._hint_lbl.setStyleSheet(
            f"color: {_C_TEXT_DIM}; font-size: 11px; font-style: italic; background: transparent; border: none;"
        )
        layout.addWidget(self._hint_lbl)


# ---------------------------------------------------------------------------
# Banner messages per workflow step
# ---------------------------------------------------------------------------

BANNER_MESSAGES: Dict[int, str] = {
    1: "Choose a strategy and a saved backtest run, then click <b>Analyze Run</b> to detect performance issues.",
    2: "Review the detected issues and suggested parameter changes below.",
    3: "Click <b>Apply</b> on one or more suggestions to build your candidate configuration, then click <b>Run Candidate Backtest</b>.",
    4: "The candidate backtest is running. Wait for it to finish, then review the comparison.",
    5: "Compare the results. Click <b>Accept &amp; Save</b> to save the improvements, or <b>Reject &amp; Discard</b> to discard them.",
}

# ---------------------------------------------------------------------------
# Module-level pure functions (testable without instantiating ImprovePage)
# ---------------------------------------------------------------------------


def _build_banner_message(step: int) -> str:
    """Return the instruction banner message for the given workflow step (1–5).

    Args:
        step: Workflow step number, must be in range 1–5.

    Returns:
        HTML-formatted instruction string for the step.
    """
    return BANNER_MESSAGES[step]


def _build_status_message(trigger: str, n_issues: int = 0) -> Tuple[str, str]:
    """Return (message, color) for the given status trigger key.

    Args:
        trigger: One of the trigger keys defined in the Status Message Mapping.
        n_issues: Number of detected issues (used for analysis_complete_issues).

    Returns:
        Tuple of (message_text, color_hex_string).
    """
    _STATUS_MAP: Dict[str, Tuple[str, str]] = {
        "analyze_loading": (
            "⏳ Loading run — please wait…",
            _C_GREEN,
        ),
        "analysis_complete_issues": (
            f"✅ Analysis complete — {n_issues} issue(s) found. Review suggestions below and click Apply.",
            _C_GREEN_LIGHT,
        ),
        "analysis_complete_no_issues": (
            "✅ Analysis complete — no issues detected. Your strategy looks healthy!",
            _C_GREEN_LIGHT,
        ),
        "candidate_backtest_start": (
            "⏳ Running candidate backtest — see terminal output below…",
            _C_GREEN,
        ),
        "candidate_backtest_success": (
            "✅ Candidate backtest complete — review the comparison below and click Accept or Reject.",
            _C_GREEN_LIGHT,
        ),
        "candidate_backtest_failed": (
            "❌ Candidate backtest failed — check the terminal output above for errors.",
            _C_RED_LIGHT,
        ),
        "accept": (
            "✅ Accepted — strategy parameters saved. You can run another iteration or switch to a different run.",
            _C_GREEN_LIGHT,
        ),
        "reject": (
            "↩ Rejected — candidate discarded. Apply different suggestions or select a new run.",
            _C_YELLOW,
        ),
        "rollback": (
            "↩ Rolled back — parameters restored to the previous accepted state.",
            _C_YELLOW,
        ),
    }
    return _STATUS_MAP[trigger]


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


def check_prerequisites(settings) -> list:
    """Return a list of human-readable failure messages for missing prerequisites.

    Returns an empty list when all prerequisites are satisfied.

    Checks:
      1. user_data_path is set and the directory exists on disk.
      2. python_executable (or freqtrade_executable when use_module_execution=False)
         exists on disk and is executable.
      3. At least one .py strategy file exists under {user_data_path}/strategies/.

    Args:
        settings: AppSettings instance.

    Returns:
        List of failure message strings. Empty list means all prerequisites pass.
    """
    import os
    failures = []

    user_data_path = getattr(settings, "user_data_path", "") or ""
    if not str(user_data_path).strip():
        failures.append("user_data_path is not configured")
    else:
        udp = Path(str(user_data_path))
        if not udp.exists():
            failures.append(f"user_data_path directory does not exist: {udp}")
        else:
            # Check for at least one strategy file
            strategies_dir = udp / "strategies"
            if not strategies_dir.exists() or not any(strategies_dir.glob("*.py")):
                failures.append(
                    f"No strategy .py files found under {strategies_dir}"
                )

    # Check executable
    use_module = getattr(settings, "use_module_execution", True)
    if use_module:
        exe = getattr(settings, "python_executable", "") or ""
    else:
        exe = getattr(settings, "freqtrade_executable", "") or ""

    if not str(exe).strip():
        exe_name = "python_executable" if use_module else "freqtrade_executable"
        failures.append(f"{exe_name} is not configured")
    else:
        exe_path = Path(str(exe))
        if not exe_path.exists():
            failures.append(f"Executable not found at {exe_path}")
        elif not os.access(str(exe_path), os.X_OK):
            failures.append(f"Executable is not executable: {exe_path}")

    return failures


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

        # Workflow step state (1–5)
        self._workflow_step: int = 1
        self._banner_dismissed: bool = False

        # Internal state
        self._baseline_run: Optional[BacktestResults] = None
        self._baseline_params: Optional[dict] = None
        self._candidate_config: dict = {}
        self._candidate_run: Optional[BacktestResults] = None
        self._baseline_history: List[dict] = []
        self._sandbox_dir: Optional[Path] = None
        self._export_dir: Optional[Path] = None
        self._run_started_at: float = 0.0

        # Session tracking (task 9)
        self._session_baseline: Optional[SessionBaseline] = None
        self._session_history: List[SessionRound] = []

        # Subprocess running flag (task 10) — disables strategy combo while running
        self._subprocess_running: bool = False

        # Run data parallel to run_combo items
        self._run_data: List[dict] = []

        # Terminal (created early so it's always available)
        self._terminal = TerminalWidget()

        # Connect settings signal
        settings_state.settings_changed.connect(self._refresh_strategies)
        settings_state.settings_changed.connect(self._check_config_guard)

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
        # Page-level dark background
        self.setStyleSheet(f"""
            QWidget {{
                background: {_C_DARK_BG};
                color: {_C_TEXT};
            }}
            QGroupBox {{
                background: {_C_CARD_BG};
                border: 1px solid {_C_BORDER};
                border-radius: 8px;
                margin-top: 10px;
                font-weight: bold;
                font-size: 12px;
                color: {_C_TEXT};
                padding-top: 6px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: {_C_TEXT_DIM};
                font-size: 11px;
                letter-spacing: 1px;
                text-transform: uppercase;
            }}
            QComboBox {{
                background: {_C_CARD_BG};
                border: 1px solid {_C_BORDER};
                border-radius: 4px;
                padding: 4px 8px;
                color: {_C_TEXT};
            }}
            QComboBox:hover {{
                border-color: {_C_TEAL};
            }}
            QComboBox QAbstractItemView {{
                background: {_C_CARD_BG};
                border: 1px solid {_C_BORDER};
                selection-background-color: {_C_TEAL};
            }}
            QScrollArea {{
                border: none;
                background: {_C_DARK_BG};
            }}
            QScrollBar:vertical {{
                background: {_C_CARD_BG};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {_C_BORDER};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {_C_TEAL};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # ---- No-configuration warning banner ----
        self._no_config_banner = QLabel(
            "⚠️ User data path is not configured. "
            "Go to Settings and set your Freqtrade user_data directory to use this tab."
        )
        self._no_config_banner.setWordWrap(True)
        self._no_config_banner.setStyleSheet(f"""
            QLabel {{
                background: {_C_ELEVATED};
                border-left: 3px solid {_C_ORANGE};
                border-radius: 4px;
                color: {_C_TEXT};
                font-size: 12px;
                padding: 8px 12px;
            }}
        """)
        self._no_config_banner.setVisible(False)
        main_layout.addWidget(self._no_config_banner)

        # ---- Step indicator ----
        self._step_indicator = StepIndicator()
        main_layout.addWidget(self._step_indicator)

        # ---- Context banner ----
        self._context_banner = ContextBanner()
        self._context_banner.set_step(1)
        main_layout.addWidget(self._context_banner)

        # ---- Top controls row ----
        top_controls = QHBoxLayout()
        top_controls.setSpacing(6)

        strategy_lbl = QLabel("Strategy:")
        strategy_lbl.setStyleSheet(f"color: {_C_TEXT_DIM}; font-size: 11px;")
        top_controls.addWidget(strategy_lbl)
        self.strategy_combo = QComboBox()
        self.strategy_combo.setMinimumWidth(180)
        self.strategy_combo.setToolTip(
            "Select the strategy whose backtest results you want to improve."
        )
        top_controls.addWidget(self.strategy_combo)

        run_lbl = QLabel("Run:")
        run_lbl.setStyleSheet(f"color: {_C_TEXT_DIM}; font-size: 11px;")
        top_controls.addWidget(run_lbl)
        self.run_combo = QComboBox()
        self.run_combo.setMinimumWidth(320)
        self.run_combo.setToolTip(
            "Select a saved backtest run to use as the baseline for comparison."
        )
        top_controls.addWidget(self.run_combo, 1)

        self.load_latest_btn = QPushButton("↓ Load Latest Run")
        self.load_latest_btn.setStyleSheet(self._btn_style(_C_BORDER, _C_TEXT))
        self.load_latest_btn.setToolTip(
            "Automatically select the most recently saved run for this strategy."
        )
        self.load_latest_btn.clicked.connect(self._on_load_latest)
        top_controls.addWidget(self.load_latest_btn)

        self.analyze_btn = QPushButton("⚡ Analyze Run")
        self.analyze_btn.setStyleSheet(self._btn_style(_C_TEAL, "white"))
        self.analyze_btn.setToolTip(
            "Load the selected run, detect performance issues, and generate parameter suggestions."
        )
        self.analyze_btn.clicked.connect(self._on_analyze)
        top_controls.addWidget(self.analyze_btn)

        top_controls.addStretch()
        main_layout.addLayout(top_controls)

        # ---- Scrollable results area ----
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background: {_C_DARK_BG};")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(4, 4, 4, 4)
        scroll_layout.setSpacing(10)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {_C_TEXT_DIM}; font-size: 11px; padding: 2px 4px;")
        scroll_layout.addWidget(self.status_label)

        # Metric cards row (hidden until data loaded)
        self._cards_widget = QWidget()
        self._cards_widget.setVisible(False)
        cards_layout = QHBoxLayout(self._cards_widget)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)

        self._card_profit = AnimatedMetricCard("TOTAL PROFIT")
        self._card_winrate = AnimatedMetricCard("WIN RATE")
        self._card_drawdown = AnimatedMetricCard("MAX DRAWDOWN")
        self._card_sharpe = AnimatedMetricCard("SHARPE RATIO")
        self._card_trades = AnimatedMetricCard("TOTAL TRADES")

        for card in (self._card_profit, self._card_winrate, self._card_drawdown,
                     self._card_sharpe, self._card_trades):
            cards_layout.addWidget(card)
        cards_layout.addStretch()
        scroll_layout.addWidget(self._cards_widget)

        # Baseline Summary group
        self.baseline_group = QGroupBox("Baseline Summary")
        self._baseline_form = QFormLayout()
        self._baseline_form.setSpacing(6)
        self._baseline_form.setContentsMargins(10, 8, 10, 8)
        baseline_container = QVBoxLayout()
        baseline_container.setContentsMargins(0, 0, 0, 0)
        baseline_container.setSpacing(0)
        self._empty_baseline = EmptyStatePanel(
            "📊",
            "No run loaded yet",
            "Select a strategy and run above, then click Analyze.",
        )
        baseline_container.addWidget(self._empty_baseline)
        baseline_container.addLayout(self._baseline_form)
        self.baseline_group.setLayout(baseline_container)
        scroll_layout.addWidget(self.baseline_group)

        # Detected Issues group
        self.issues_group = QGroupBox("Detected Issues")
        self._issues_layout = QVBoxLayout()
        self._issues_layout.setSpacing(6)
        self._issues_layout.setContentsMargins(10, 8, 10, 8)
        # Subtitle label
        _issues_subtitle = QLabel(
            "Issues found in the baseline run that may be limiting strategy performance."
        )
        _issues_subtitle.setStyleSheet(
            f"color: {_C_TEXT_DIM}; font-size: 11px; padding-left: 10px;"
        )
        _issues_subtitle.setWordWrap(True)
        self._issues_layout.addWidget(_issues_subtitle)
        self._empty_issues = EmptyStatePanel(
            "🔍",
            "Issues will appear here after analysis",
            "Click Analyze to scan your backtest results.",
        )
        self._issues_layout.addWidget(self._empty_issues)
        self.issues_group.setLayout(self._issues_layout)
        scroll_layout.addWidget(self.issues_group)

        # Suggested Actions group
        self.suggestions_group = QGroupBox("Suggested Actions")
        self._suggestions_layout = QVBoxLayout()
        self._suggestions_layout.setSpacing(6)
        self._suggestions_layout.setContentsMargins(10, 8, 10, 8)
        # Subtitle label
        _suggestions_subtitle = QLabel(
            "Rule-based parameter changes that address the detected issues. "
            "Apply one or more, then run the candidate backtest."
        )
        _suggestions_subtitle.setStyleSheet(
            f"color: {_C_TEXT_DIM}; font-size: 11px; padding-left: 10px;"
        )
        _suggestions_subtitle.setWordWrap(True)
        self._suggestions_layout.addWidget(_suggestions_subtitle)
        self._empty_suggestions = EmptyStatePanel(
            "💡",
            "Suggestions will appear here after analysis",
            "Each suggestion targets a specific performance issue.",
        )
        self._suggestions_layout.addWidget(self._empty_suggestions)
        self.suggestions_group.setLayout(self._suggestions_layout)
        scroll_layout.addWidget(self.suggestions_group)

        # Candidate Changes group (was "Candidate Preview")
        self.candidate_group = QGroupBox("Candidate Changes")
        self._candidate_layout = QVBoxLayout()
        self._candidate_layout.setContentsMargins(10, 8, 10, 8)
        # Subtitle label
        _candidate_subtitle = QLabel(
            "Parameters that will be changed from the baseline when the candidate backtest runs."
        )
        _candidate_subtitle.setStyleSheet(
            f"color: {_C_TEXT_DIM}; font-size: 11px; padding-left: 10px;"
        )
        _candidate_subtitle.setWordWrap(True)
        self._candidate_layout.addWidget(_candidate_subtitle)
        self._empty_candidate = EmptyStatePanel(
            "⚙️",
            "No changes applied yet",
            "Click Apply on a suggestion above to start building your candidate.",
        )
        self._candidate_layout.addWidget(self._empty_candidate)
        self.candidate_group.setLayout(self._candidate_layout)
        scroll_layout.addWidget(self.candidate_group)

        # Results Comparison group (was "Comparison")
        self.comparison_group = QGroupBox("Results Comparison")
        self._comparison_layout = QVBoxLayout()
        self._comparison_layout.setContentsMargins(10, 8, 10, 8)
        # Subtitle label
        _comparison_subtitle = QLabel(
            "Side-by-side metrics for the baseline and candidate runs. "
            "Green = improvement, red = regression."
        )
        _comparison_subtitle.setStyleSheet(
            f"color: {_C_TEXT_DIM}; font-size: 11px; padding-left: 10px;"
        )
        _comparison_subtitle.setWordWrap(True)
        self._comparison_layout.addWidget(_comparison_subtitle)
        self._empty_comparison = EmptyStatePanel(
            "⚖️",
            "Comparison will appear after the candidate backtest",
            "Apply suggestions and run the candidate backtest to see results here.",
        )
        self._comparison_layout.addWidget(self._empty_comparison)
        self.comparison_group.setLayout(self._comparison_layout)
        scroll_layout.addWidget(self.comparison_group)

        # Session History group (task 9) — scrollable panel showing accepted rounds
        self.session_history_group = QGroupBox("Session History")
        self._session_history_layout = QVBoxLayout()
        self._session_history_layout.setSpacing(4)
        self._session_history_layout.setContentsMargins(10, 8, 10, 8)
        _session_history_subtitle = QLabel(
            "Accepted improvement rounds this session. Each entry shows the metrics of the accepted candidate."
        )
        _session_history_subtitle.setStyleSheet(
            f"color: {_C_TEXT_DIM}; font-size: 11px; padding-left: 10px;"
        )
        _session_history_subtitle.setWordWrap(True)
        self._session_history_layout.addWidget(_session_history_subtitle)
        self._empty_session_history = EmptyStatePanel(
            "📋",
            "No rounds accepted yet",
            "Accept a candidate to start tracking session history.",
        )
        self._session_history_layout.addWidget(self._empty_session_history)
        self.session_history_group.setLayout(self._session_history_layout)
        scroll_layout.addWidget(self.session_history_group)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area, 1)

        self.setLayout(main_layout)

        # Connect combo signals
        self.strategy_combo.currentTextChanged.connect(self._refresh_runs)

    @staticmethod
    def _btn_style(bg: str, fg: str) -> str:
        """Return a QPushButton stylesheet for the given background/foreground."""
        return f"""
            QPushButton {{
                background: {bg};
                color: {fg};
                border: 1px solid {bg};
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                opacity: 0.85;
                border-color: {_C_TEAL};
            }}
            QPushButton:disabled {{
                background: {_C_BORDER};
                color: {_C_TEXT_DIM};
                border-color: {_C_BORDER};
            }}
        """

    # ------------------------------------------------------------------
    # Workflow step management
    # ------------------------------------------------------------------

    def _set_workflow_step(self, step: int) -> None:
        """Advance the workflow to the given step and sync all guidance widgets.

        Args:
            step: The new active workflow step (1–5).
        """
        self._workflow_step = step
        self._step_indicator.set_active_step(step)
        self._context_banner.set_step(step)

    # ------------------------------------------------------------------
    # No-configuration guard
    # ------------------------------------------------------------------

    def _check_config_guard(self) -> None:
        """Show/hide the no-config banner and enable/disable controls based on prerequisites."""
        settings = self._settings_state.settings_service.load_settings()
        failures = check_prerequisites(settings)
        unconfigured = len(failures) > 0

        if unconfigured:
            failure_text = "\n".join(f"• {f}" for f in failures)
            self._no_config_banner.setText(
                f"⚠️ Configuration issues detected:\n{failure_text}"
            )
        else:
            self._no_config_banner.setText("")

        self._no_config_banner.setVisible(unconfigured)
        # Only enable controls when configured AND no subprocess is running
        subprocess_running = getattr(self, "_subprocess_running", False)
        controls_enabled = not unconfigured and not subprocess_running
        self.strategy_combo.setEnabled(controls_enabled)
        self.run_combo.setEnabled(not unconfigured)
        self.load_latest_btn.setEnabled(not unconfigured)
        self.analyze_btn.setEnabled(not unconfigured)

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
        self._check_config_guard()

    def _refresh_runs(self) -> None:
        """Populate run_combo for the currently selected strategy."""
        strategy = self.strategy_combo.currentText().strip()

        self.run_combo.blockSignals(True)
        self.run_combo.clear()
        self._run_data = []

        # Clear session history whenever the strategy changes (task 9)
        self._session_history = []
        self._session_baseline = None

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
            # Populate session baseline from the most recent run (task 9)
            self._load_session_baseline(strategy, runs[0])
        else:
            self.run_combo.addItem("(No saved runs found for this strategy)")
            self.analyze_btn.setEnabled(False)
            # No runs — session baseline stays None; a fresh baseline backtest would be needed

        self.run_combo.blockSignals(False)

    def _load_session_baseline(self, strategy: str, run: dict) -> None:
        """Load the most recent run as the session baseline (task 9).

        Args:
            strategy: Strategy class name.
            run: Run metadata dict from the index (most recent run).
        """
        try:
            settings = self._settings_state.settings_service.load_settings()
            backtest_results_dir = Path(settings.user_data_path) / "backtest_results"
            run_dir = backtest_results_dir / run.get("run_dir", "")
            baseline_results = self._improve_service.load_baseline(run_dir)
            params = self._improve_service.load_baseline_params(run_dir, strategy)
            self._session_baseline = SessionBaseline(
                params=params,
                summary=baseline_results.summary,
            )
            _log.info(
                "Session baseline loaded for strategy '%s' from run '%s'",
                strategy,
                run.get("run_id", ""),
            )
        except (FileNotFoundError, ValueError, OSError) as e:
            _log.warning("Could not load session baseline for '%s': %s", strategy, e)
            self._session_baseline = None

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
        msg, color = _build_status_message("analyze_loading")
        self.status_label.setText(msg)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px; padding: 2px 4px;")

        try:
            baseline = self._improve_service.load_baseline(run_dir)
            strategy_name = self.strategy_combo.currentText().strip()
            params = self._improve_service.load_baseline_params(run_dir, strategy_name)
            self._baseline_run = baseline
            self._baseline_params = params
            self._candidate_config = copy.deepcopy(params)
            self._display_baseline_summary(baseline.summary)
            issues = self._display_issues_and_suggestions(baseline.summary, params)
            n_issues = len(issues)
            if n_issues > 0:
                msg, color = _build_status_message("analysis_complete_issues", n_issues)
            else:
                msg, color = _build_status_message("analysis_complete_no_issues")
            self.status_label.setText(msg)
            self.status_label.setStyleSheet(f"color: {color}; font-size: 11px; padding: 2px 4px;")
            self._set_workflow_step(3)
        except (FileNotFoundError, ValueError) as e:
            self.status_label.setText(f"❌  Error: {e}")
            self.status_label.setStyleSheet(f"color: {_C_RED_LIGHT}; font-size: 11px; padding: 2px 4px;")
        finally:
            self.analyze_btn.setEnabled(True)

    def _display_baseline_summary(self, summary: BacktestSummary) -> None:
        """Clear and repopulate the baseline summary form and metric cards."""
        # Hide cards widget at the start so layout is clean during repopulation
        self._cards_widget.setVisible(False)

        # Remove empty state panel synchronously (setParent(None) avoids deleteLater() race)
        if self._empty_baseline is not None:
            self._empty_baseline.setParent(None)
            self._empty_baseline = None

        while self._baseline_form.rowCount() > 0:
            self._baseline_form.removeRow(0)

        def _lbl(text: str, color: str = _C_TEXT) -> QLabel:
            l = QLabel(text)
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        def _key(text: str) -> QLabel:
            l = QLabel(text)
            l.setStyleSheet(f"color: {_C_TEXT_DIM}; font-size: 11px; background: transparent;")
            return l

        profit_color = _C_GREEN_LIGHT if summary.total_profit >= 0 else _C_RED_LIGHT
        sharpe_color = _C_GREEN_LIGHT if (summary.sharpe_ratio or 0) >= 0 else _C_RED_LIGHT
        wr_color = _C_GREEN_LIGHT if summary.win_rate >= 50 else _C_RED_LIGHT
        dd_color = _C_RED_LIGHT if summary.max_drawdown > 20 else (_C_YELLOW if summary.max_drawdown > 10 else _C_GREEN_LIGHT)

        self._baseline_form.addRow(_key("Strategy:"), _lbl(summary.strategy))
        self._baseline_form.addRow(_key("Timeframe:"), _lbl(summary.timeframe))
        self._baseline_form.addRow(_key("Total Trades:"), _lbl(str(summary.total_trades)))
        self._baseline_form.addRow(_key("Win Rate:"), _lbl(f"{summary.win_rate:.2f}%", wr_color))
        self._baseline_form.addRow(_key("Total Profit:"), _lbl(f"{summary.total_profit:.4f}%", profit_color))
        self._baseline_form.addRow(_key("Max Drawdown:"), _lbl(f"{summary.max_drawdown:.2f}%", dd_color))
        sharpe = f"{summary.sharpe_ratio:.4f}" if summary.sharpe_ratio is not None else "N/A"
        self._baseline_form.addRow(_key("Sharpe Ratio:"), _lbl(sharpe, sharpe_color))
        self._baseline_form.addRow(
            _key("Date Range:"), _lbl(f"{summary.backtest_start} → {summary.backtest_end}")
        )

        self.baseline_group.setVisible(True)
        self._cards_widget.setVisible(True)

        # Profit card
        profit_bar = min(abs(summary.total_profit) / 100 * 100, 100)
        self._card_profit.set_value(
            f"{summary.total_profit:.2f}%",
            color=profit_color,
            bar_pct=profit_bar,
            bar_color=profit_color,
            sub_text="vs 0% target",
        )

        # Win rate card
        self._card_winrate.set_value(
            f"{summary.win_rate:.1f}%",
            color=wr_color,
            bar_pct=summary.win_rate,
            bar_color=wr_color,
            sub_text="50% threshold",
        )

        # Drawdown card
        dd_bar = min(summary.max_drawdown / 60 * 100, 100)
        self._card_drawdown.set_value(
            f"{summary.max_drawdown:.1f}%",
            color=dd_color,
            bar_pct=dd_bar,
            bar_color=dd_color,
            sub_text="lower is better",
        )

        # Sharpe card
        sharpe_val = summary.sharpe_ratio or 0.0
        sharpe_bar = min(max((sharpe_val + 3) / 6 * 100, 0), 100)
        self._card_sharpe.set_value(
            f"{sharpe_val:.2f}" if summary.sharpe_ratio is not None else "N/A",
            color=sharpe_color,
            bar_pct=sharpe_bar,
            bar_color=sharpe_color,
            sub_text=">1.0 is good",
        )

        # Trades card
        trades_bar = min(summary.total_trades / 500 * 100, 100)
        self._card_trades.set_value(
            str(summary.total_trades),
            color=_C_TEXT,
            bar_pct=trades_bar,
            bar_color=_C_TEAL,
            sub_text="30 min threshold",
        )

    def _display_issues_and_suggestions(self, summary: BacktestSummary, params: dict) -> list:
        """Run diagnosis and suggestion services, then populate the UI groups.

        Returns:
            List of diagnosed issues (for status message count).
        """
        # Clear issues layout (preserves subtitle label at index 0)
        while self._issues_layout.count() > 1:
            item = self._issues_layout.takeAt(1)
            if item.widget():
                item.widget().setParent(None)

        # Remove empty state panel reference (already cleared above)
        self._empty_issues = None

        bundle = ResultsDiagnosisService.diagnose(DiagnosisInput(in_sample=summary))
        issues = bundle.issues

        if not issues:
            ok_lbl = QLabel("✅  No issues detected — results look healthy")
            ok_lbl.setStyleSheet(f"color: {_C_GREEN_LIGHT}; font-size: 12px; padding: 4px;")
            self._issues_layout.addWidget(ok_lbl)
            _fade_in_widget(ok_lbl)
        else:
            for i, issue in enumerate(issues):
                badge = IssueBadge(issue)
                self._issues_layout.addWidget(badge)
                # Stagger fade-in
                QTimer.singleShot(i * 80, lambda w=badge: _fade_in_widget(w, 300))

        # Render structural diagnoses (task 11)
        structural = bundle.structural
        if structural:
            struct_header = QLabel("Structural Patterns:")
            struct_header.setStyleSheet(
                f"color: {_C_TEXT_DIM}; font-size: 10px; font-weight: bold; "
                f"letter-spacing: 1px; padding-top: 6px;"
            )
            self._issues_layout.addWidget(struct_header)
            for i, sd in enumerate(structural):
                sd_badge = self._make_structural_badge(sd)
                self._issues_layout.addWidget(sd_badge)
                QTimer.singleShot((len(issues) + i) * 80, lambda w=sd_badge: _fade_in_widget(w, 300))

        self.issues_group.setVisible(True)

        # Update group box title with count
        total_count = len(issues) + len(structural)
        if total_count > 0:
            self.issues_group.setTitle(f"Detected Issues ({total_count})")
        else:
            self.issues_group.setTitle("Detected Issues")
        # Clear suggestions layout (preserves subtitle label at index 0)
        while self._suggestions_layout.count() > 1:
            item = self._suggestions_layout.takeAt(1)
            if item.widget():
                item.widget().setParent(None)

        self._empty_suggestions = None

        suggestions = RuleSuggestionService.suggest(issues, params, structural)

        if not suggestions:
            no_lbl = QLabel("No suggestions available")
            no_lbl.setStyleSheet(f"color: {_C_TEXT_DIM}; font-size: 12px; padding: 4px;")
            self._suggestions_layout.addWidget(no_lbl)
        else:
            for i, suggestion in enumerate(suggestions):
                row = SuggestionRow(suggestion, self._on_apply_suggestion)
                self._suggestions_layout.addWidget(row)
                QTimer.singleShot(i * 80, lambda w=row: _fade_in_widget(w, 300))

        # Update group box title with count
        if suggestions:
            self.suggestions_group.setTitle(f"Suggested Actions ({len(suggestions)})")
        else:
            self.suggestions_group.setTitle("Suggested Actions")

        self.suggestions_group.setVisible(True)

        return issues

    @staticmethod
    def _make_structural_badge(sd) -> QFrame:
        """Build a colored badge widget for a StructuralDiagnosis.

        Badge color: critical → red, moderate → orange, advisory → yellow.

        Args:
            sd: StructuralDiagnosis object.

        Returns:
            A styled QFrame badge widget.
        """
        severity_colors = {
            "critical": (_C_RED, "🔴"),
            "moderate": (_C_ORANGE, "🟠"),
            "advisory": (_C_YELLOW, "🟡"),
        }
        color, icon = severity_colors.get(sd.severity, (_C_TEXT_DIM, "⚪"))

        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {color}22;
                border: 1px solid {color}66;
                border-left: 3px solid {color};
                border-radius: 4px;
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Header row: icon + pattern label
        header_row = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(18)
        header_row.addWidget(icon_lbl)

        pattern_lbl = QLabel(f"<b>{sd.failure_pattern}</b>")
        pattern_lbl.setStyleSheet(
            f"color: {color}; font-size: 12px; background: transparent; border: none;"
        )
        header_row.addWidget(pattern_lbl, 1)
        layout.addLayout(header_row)

        # Evidence
        evidence_lbl = QLabel(f"Evidence: {sd.evidence}")
        evidence_lbl.setWordWrap(True)
        evidence_lbl.setStyleSheet(
            f"color: {_C_TEXT}; font-size: 11px; background: transparent; border: none;"
        )
        layout.addWidget(evidence_lbl)

        # Root cause
        cause_lbl = QLabel(f"Root cause: {sd.root_cause}")
        cause_lbl.setWordWrap(True)
        cause_lbl.setStyleSheet(
            f"color: {_C_TEXT_DIM}; font-size: 11px; background: transparent; border: none;"
        )
        layout.addWidget(cause_lbl)

        # Mutation direction
        direction_lbl = QLabel(f"Direction: {sd.mutation_direction}")
        direction_lbl.setWordWrap(True)
        direction_lbl.setStyleSheet(
            f"color: {_C_TEAL}; font-size: 11px; background: transparent; border: none;"
        )
        layout.addWidget(direction_lbl)

        # Confidence bar
        conf_row = QHBoxLayout()
        conf_label = QLabel("Confidence:")
        conf_label.setStyleSheet(
            f"color: {_C_TEXT_DIM}; font-size: 10px; background: transparent; border: none;"
        )
        conf_label.setFixedWidth(70)
        conf_row.addWidget(conf_label)

        conf_bar = QProgressBar()
        conf_bar.setRange(0, 100)
        conf_bar.setValue(int(sd.confidence * 100))
        conf_bar.setTextVisible(True)
        conf_bar.setFormat(f"{sd.confidence * 100:.0f}%")
        conf_bar.setFixedHeight(12)
        conf_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {_C_BORDER};
                border-radius: 6px;
                border: none;
                font-size: 9px;
                color: {_C_TEXT};
            }}
            QProgressBar::chunk {{
                background: {color};
                border-radius: 6px;
            }}
        """)
        conf_row.addWidget(conf_bar, 1)
        layout.addLayout(conf_row)

        return frame

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
        # Advance to Backtest step on first non-advisory apply
        if self._workflow_step < 4:
            self._set_workflow_step(4)
        self._update_candidate_preview()

    def _update_candidate_preview(self) -> None:
        """Recompute and display the diff between baseline and candidate config."""
        # Detach terminal before clearing so it is never passed to deleteLater()
        self._candidate_layout.removeWidget(self._terminal)
        # Clear existing widgets (preserves subtitle label at index 0)
        while self._candidate_layout.count() > 1:
            item = self._candidate_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                sub = item.layout()
                while sub.count():
                    sub_item = sub.takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().deleteLater()

        # Remove empty state panel reference
        self._empty_candidate = None

        diff = compute_diff(self._baseline_params or {}, self._candidate_config)

        if not diff:
            no_lbl = QLabel("No changes applied yet")
            no_lbl.setStyleSheet(f"color: {_C_TEXT_DIM}; font-size: 12px; padding: 4px;")
            self._candidate_layout.addWidget(no_lbl)
        else:
            diff_frame = QFrame()
            diff_frame.setStyleSheet(f"""
                QFrame {{
                    background: {_C_DARK_BG};
                    border: 1px solid {_C_BORDER};
                    border-radius: 6px;
                }}
            """)
            diff_layout = QVBoxLayout(diff_frame)
            diff_layout.setContentsMargins(10, 8, 10, 8)
            diff_layout.setSpacing(4)

            header = QLabel("Parameter Changes")
            header.setStyleSheet(f"color: {_C_TEXT_DIM}; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
            diff_layout.addWidget(header)

            for key, value in diff.items():
                old_val = (self._baseline_params or {}).get(key, "—")
                row = QHBoxLayout()
                key_lbl = QLabel(f"  {key}")
                key_lbl.setStyleSheet(f"color: {_C_TEXT}; font-size: 12px; font-weight: bold;")
                key_lbl.setFixedWidth(160)
                row.addWidget(key_lbl)

                old_lbl = QLabel(str(old_val))
                old_lbl.setStyleSheet(f"color: {_C_RED_LIGHT}; font-size: 12px; text-decoration: line-through;")
                row.addWidget(old_lbl)

                arrow = QLabel("  →  ")
                arrow.setStyleSheet(f"color: {_C_TEXT_DIM}; font-size: 12px;")
                row.addWidget(arrow)

                new_lbl = QLabel(str(value))
                new_lbl.setStyleSheet(f"color: {_C_GREEN_LIGHT}; font-size: 12px; font-weight: bold;")
                row.addWidget(new_lbl)
                row.addStretch()

                diff_layout.addLayout(row)

            self._candidate_layout.addWidget(diff_frame)
            _fade_in_widget(diff_frame)

        # Buttons row
        btn_row = QHBoxLayout()
        self.run_backtest_btn = QPushButton("▶ Run Candidate Backtest")
        self.run_backtest_btn.setEnabled(bool(diff))
        self.run_backtest_btn.setStyleSheet(self._btn_style(_C_GREEN, "white"))
        self.run_backtest_btn.setToolTip(
            "Run a backtest using the candidate parameters. Results will be compared to the baseline."
        )
        self.run_backtest_btn.clicked.connect(self._on_run_candidate)
        btn_row.addWidget(self.run_backtest_btn)

        self.stop_btn = QPushButton("⏹  Stop")
        self.stop_btn.setVisible(False)
        self.stop_btn.setStyleSheet(self._btn_style(_C_RED, "white"))
        self.stop_btn.clicked.connect(self._on_stop_candidate)
        btn_row.addWidget(self.stop_btn)

        self.reset_candidate_btn = QPushButton("↺ Reset to Baseline")
        self.reset_candidate_btn.setStyleSheet(self._btn_style(_C_BORDER, _C_TEXT))
        self.reset_candidate_btn.setToolTip(
            "Clear all applied suggestions and reset the candidate to match the current baseline parameters."
        )
        self.reset_candidate_btn.clicked.connect(self._on_reset_candidate)
        btn_row.addWidget(self.reset_candidate_btn)
        btn_row.addStretch()

        btn_widget = QWidget()
        btn_widget.setStyleSheet(f"background: transparent;")
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

        # Disable run button, show stop button; lock strategy combo (task 10)
        self.run_backtest_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self._subprocess_running = True
        self.strategy_combo.setEnabled(False)

        # Update status message
        msg, color = _build_status_message("candidate_backtest_start")
        self.status_label.setText(msg)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px; padding: 2px 4px;")

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
            self.status_label.setText(f"❌  Process error: {e}")
            self.status_label.setStyleSheet(f"color: {_C_RED_LIGHT}; font-size: 11px; padding: 2px 4px;")
            self.run_backtest_btn.setEnabled(True)
            self.stop_btn.setVisible(False)

    def _on_stop_candidate(self) -> None:
        """Stop the running candidate backtest."""
        self._terminal.process_service.stop_process()
        self.run_backtest_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self._subprocess_running = False
        self._check_config_guard()

    def _on_candidate_finished(self, exit_code: int) -> None:
        """Handle candidate backtest process completion."""
        self.run_backtest_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        # Re-enable strategy combo when no subprocess is running (task 10)
        self._subprocess_running = False
        self._check_config_guard()

        self._terminal.append_output(f"\n[Process finished] exit_code={exit_code}\n")

        if exit_code == 0:
            try:
                candidate_run = self._improve_service.parse_candidate_run(
                    self._export_dir, self._run_started_at
                )
                self._candidate_run = candidate_run
                self._update_comparison_view()
                msg, color = _build_status_message("candidate_backtest_success")
                self.status_label.setText(msg)
                self.status_label.setStyleSheet(f"color: {color}; font-size: 11px; padding: 2px 4px;")
                self._set_workflow_step(5)
            except (FileNotFoundError, ValueError) as e:
                self.status_label.setText(f"❌  Error loading candidate results: {e}")
                self.status_label.setStyleSheet(f"color: {_C_RED_LIGHT}; font-size: 11px; padding: 2px 4px;")
        else:
            terminal_text = self._terminal.get_output()
            known_phrases = [
                "Invalid parameter file",
                "Strategy not found",
                "No data found",
                "Configuration error",
                "No pairs defined",
            ]
            matched_phrase = next(
                (phrase for phrase in known_phrases if phrase in terminal_text), None
            )
            if matched_phrase:
                base_msg, color = _build_status_message("candidate_backtest_failed")
                msg = base_msg.replace(
                    "check the terminal output above for errors",
                    f"check the terminal output above for errors ({matched_phrase})",
                )
            else:
                msg, color = _build_status_message("candidate_backtest_failed")
            self.status_label.setText(msg)
            self.status_label.setStyleSheet(f"color: {color}; font-size: 11px; padding: 2px 4px;")

    def _update_comparison_view(self) -> None:
        """Build or rebuild the comparison table when both runs are available."""
        # Clear all items from comparison layout (preserves subtitle label at index 0)
        while self._comparison_layout.count() > 1:
            item = self._comparison_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        # Remove empty state panel reference
        self._empty_comparison = None

        if self._baseline_run is None or self._candidate_run is None:
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

        baseline_summary = self._baseline_run.summary
        candidate_summary = self._candidate_run.summary

        # Summary delta cards at the top
        delta_widget = QWidget()
        delta_widget.setStyleSheet(f"background: transparent;")
        delta_layout = QHBoxLayout(delta_widget)
        delta_layout.setContentsMargins(0, 0, 0, 8)
        delta_layout.setSpacing(8)

        for metric_key, display_name, getter in METRICS[:4]:
            b_val = getter(baseline_summary)
            c_val = getter(candidate_summary)
            delta = c_val - b_val
            color = compute_highlight(metric_key, b_val, c_val)
            card_color = _C_GREEN_LIGHT if color == "green" else (_C_RED_LIGHT if color == "red" else _C_TEXT_DIM)
            sign = "+" if delta > 0 else ""
            delta_card = QFrame()
            delta_card.setStyleSheet(f"""
                QFrame {{
                    background: {card_color}18;
                    border: 1px solid {card_color}55;
                    border-radius: 6px;
                }}
            """)
            dc_layout = QVBoxLayout(delta_card)
            dc_layout.setContentsMargins(8, 6, 8, 6)
            dc_layout.setSpacing(2)

            name_lbl = QLabel(display_name)
            name_lbl.setStyleSheet(f"color: {_C_TEXT_DIM}; font-size: 9px; font-weight: bold; letter-spacing: 1px; background: transparent; border: none;")
            name_lbl.setAlignment(Qt.AlignCenter)
            dc_layout.addWidget(name_lbl)

            if metric_key in ("win_rate", "total_profit", "max_drawdown"):
                delta_str = f"{sign}{delta:.2f}%"
            elif metric_key == "total_trades":
                delta_str = f"{sign}{int(delta)}"
            else:
                delta_str = f"{sign}{delta:.4f}"

            delta_lbl = QLabel(delta_str)
            delta_lbl.setStyleSheet(f"color: {card_color}; font-size: 16px; font-weight: bold; background: transparent; border: none;")
            delta_lbl.setAlignment(Qt.AlignCenter)
            dc_layout.addWidget(delta_lbl)

            delta_layout.addWidget(delta_card)
            _fade_in_widget(delta_card, 400)

        delta_layout.addStretch()
        self._comparison_layout.addWidget(delta_widget)

        # Full comparison table
        table = QTableWidget(len(METRICS), 4)
        table.setHorizontalHeaderLabels(["Metric", "Baseline", "Candidate", "Δ Change"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(f"""
            QTableWidget {{
                background: {_C_CARD_BG};
                alternate-background-color: {_C_DARK_BG};
                gridline-color: {_C_BORDER};
                border: 1px solid {_C_BORDER};
                border-radius: 6px;
                color: {_C_TEXT};
                font-size: 12px;
            }}
            QHeaderView::section {{
                background: {_C_DARK_BG};
                color: {_C_TEXT_DIM};
                border: none;
                border-bottom: 1px solid {_C_BORDER};
                padding: 6px 8px;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            QTableWidget::item {{
                padding: 6px 8px;
            }}
        """)

        for row, (metric_key, display_name, getter) in enumerate(METRICS):
            baseline_val = getter(baseline_summary)
            candidate_val = getter(candidate_summary)
            delta = candidate_val - baseline_val

            if metric_key == "total_trades":
                b_str = str(int(baseline_val))
                c_str = str(int(candidate_val))
                d_str = f"{'+' if delta >= 0 else ''}{int(delta)}"
            elif metric_key in ("win_rate", "total_profit", "max_drawdown"):
                b_str = f"{baseline_val:.2f}%"
                c_str = f"{candidate_val:.2f}%"
                d_str = f"{'+' if delta >= 0 else ''}{delta:.2f}%"
            else:
                b_str = f"{baseline_val:.4f}"
                c_str = f"{candidate_val:.4f}"
                d_str = f"{'+' if delta >= 0 else ''}{delta:.4f}"

            metric_item = QTableWidgetItem(display_name)
            metric_item.setForeground(QColor(_C_TEXT_DIM))
            table.setItem(row, 0, metric_item)
            table.setItem(row, 1, QTableWidgetItem(b_str))

            candidate_item = QTableWidgetItem(c_str)
            color = compute_highlight(metric_key, baseline_val, candidate_val)
            if color == "green":
                candidate_item.setForeground(QColor(_C_GREEN_LIGHT))
                candidate_item.setFont(QFont("", -1, QFont.Bold))
            elif color == "red":
                candidate_item.setForeground(QColor(_C_RED_LIGHT))
                candidate_item.setFont(QFont("", -1, QFont.Bold))
            table.setItem(row, 2, candidate_item)

            delta_item = QTableWidgetItem(d_str)
            if color == "green":
                delta_item.setForeground(QColor(_C_GREEN_LIGHT))
                delta_item.setBackground(QColor(_C_GREEN + "22"))
            elif color == "red":
                delta_item.setForeground(QColor(_C_RED_LIGHT))
                delta_item.setBackground(QColor(_C_RED + "22"))
            else:
                delta_item.setForeground(QColor(_C_TEXT_DIM))
            table.setItem(row, 3, delta_item)

        self._comparison_layout.addWidget(table)
        _fade_in_widget(table)

        # Accept / Reject / Rollback buttons — create fresh instances on every call
        accept_btn = QPushButton("✅ Accept & Save")
        accept_btn.setStyleSheet(self._btn_style(_C_GREEN, "white"))
        accept_btn.setToolTip(
            "Write the candidate parameters to the strategy file. "
            "This replaces the current parameters permanently."
        )
        accept_btn.clicked.connect(self._on_accept)

        reject_btn = QPushButton("✕ Reject & Discard")
        reject_btn.setStyleSheet(self._btn_style(_C_RED, "white"))
        reject_btn.setToolTip("Discard the candidate parameters. The strategy file is not modified.")
        reject_btn.clicked.connect(self._on_reject)

        rollback_btn = QPushButton("↩ Rollback to Previous")
        rollback_btn.setStyleSheet(self._btn_style(_C_ORANGE, "white"))
        rollback_btn.setToolTip(
            "Restore the strategy parameters to the state before the last Accept."
        )
        # Hidden until at least one round is accepted (task 9)
        rollback_btn.setVisible(len(self._session_history) > 0 or len(self._baseline_history) > 0)
        rollback_btn.clicked.connect(self._on_rollback)

        run_another_btn = QPushButton("🔄 Run Another Round")
        run_another_btn.setStyleSheet(self._btn_style(_C_TEAL, "white"))
        run_another_btn.setToolTip(
            "Use the current accepted parameters as the starting point for the next suggestion cycle."
        )
        # Hidden until at least one round is accepted (task 9)
        run_another_btn.setVisible(len(self._session_history) > 0)
        run_another_btn.clicked.connect(self._on_run_another_round)

        arb_row = QHBoxLayout()
        arb_row.addWidget(accept_btn)
        arb_row.addWidget(reject_btn)
        arb_row.addWidget(rollback_btn)
        arb_row.addWidget(run_another_btn)
        arb_row.addStretch()
        arb_widget = QWidget()
        arb_widget.setStyleSheet("background: transparent;")
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

        # Clean up sandbox directory after successful accept
        if self._sandbox_dir is not None:
            self._improve_service.reject_candidate(self._sandbox_dir)
            self._sandbox_dir = None

        # Build SessionRound and update session tracking (task 9)
        params_before = copy.deepcopy(self._baseline_params)
        params_after = copy.deepcopy(self._candidate_config)
        candidate_summary = self._candidate_run.summary
        round_number = len(self._session_history) + 1
        session_round = SessionRound(
            round_number=round_number,
            params_before=params_before,
            params_after=params_after,
            summary=candidate_summary,
            timestamp=datetime.now(timezone.utc),
        )
        self._session_history.append(session_round)

        # Update session baseline to the accepted candidate values (task 9)
        self._session_baseline = SessionBaseline(
            params=params_after,
            summary=candidate_summary,
        )

        # Update all state atomically before any UI refresh
        self._baseline_history.append(copy.deepcopy(self._baseline_params))
        self._baseline_params = copy.deepcopy(self._candidate_config)
        self._baseline_run = self._candidate_run
        self._candidate_run = None
        self._candidate_config = copy.deepcopy(self._baseline_params)

        # Single UI refresh after all state is updated
        self._update_comparison_view()
        self._update_session_history_panel()
        msg, color = _build_status_message("accept")
        self.status_label.setText(msg)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px; padding: 2px 4px;")
        self._set_workflow_step(1)
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
        msg, color = _build_status_message("reject")
        self.status_label.setText(msg)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px; padding: 2px 4px;")
        self._set_workflow_step(1)
        _log.info("Candidate rejected")

    def _on_rollback(self) -> None:
        """Rollback to the previous baseline params using session history (task 9)."""
        if not self._session_history:
            return

        strategy_name = self.strategy_combo.currentText().strip()
        if not strategy_name or strategy_name.startswith("("):
            return

        # Pop the last session round
        last_round = self._session_history.pop()

        try:
            self._improve_service.rollback(strategy_name, last_round.params_before)
        except OSError as e:
            # Re-push the round since rollback failed
            self._session_history.append(last_round)
            QMessageBox.critical(self, "Rollback Failed", str(e))
            return

        # Restore session baseline to params_before — no disk read (task 9)
        self._session_baseline = SessionBaseline(
            params=last_round.params_before,
            summary=last_round.summary,  # keep the summary from that round for reference
        )

        # Also keep _baseline_history in sync for backward compat
        if self._baseline_history:
            self._baseline_history.pop()

        self._baseline_params = copy.deepcopy(last_round.params_before)
        # Restore _baseline_run.summary from the popped round (task 3.3)
        if self._baseline_run is not None:
            self._baseline_run.summary = last_round.summary
        self._candidate_run = None
        self._candidate_config = copy.deepcopy(self._baseline_params)

        self._update_comparison_view()
        self._update_candidate_preview()
        self._update_session_history_panel()
        msg, color = _build_status_message("rollback")
        self.status_label.setText(msg)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px; padding: 2px 4px;")
        _log.info("Rolled back to previous baseline for strategy '%s'", strategy_name)

    def _on_run_another_round(self) -> None:
        """Start the next suggestion cycle using the current session baseline (task 9).

        Uses ``_session_baseline.params`` as the starting point without re-reading
        the strategy JSON from disk.
        """
        if self._session_baseline is None:
            _log.warning("_on_run_another_round called but _session_baseline is None")
            return

        # Use session baseline params as the new starting point — no disk read
        self._baseline_params = copy.deepcopy(self._session_baseline.params)
        self._candidate_config = copy.deepcopy(self._session_baseline.params)
        self._candidate_run = None

        # Re-run diagnosis and suggestions from the current baseline summary
        if self._baseline_run is not None:
            self._display_issues_and_suggestions(
                self._baseline_run.summary, self._baseline_params
            )
        self._update_candidate_preview()
        self._set_workflow_step(3)
        _log.info("Run Another Round started from session baseline")

    def _update_session_history_panel(self) -> None:
        """Rebuild the session history panel from ``_session_history`` (task 9).

        Displays a scrollable list of accepted rounds with round number,
        profit %, win rate, max drawdown, and trade count.
        """
        # Clear existing content (preserves subtitle label at index 0)
        while self._session_history_layout.count() > 1:
            item = self._session_history_layout.takeAt(1)
            if item.widget():
                item.widget().setParent(None)

        # Remove empty state panel reference
        self._empty_session_history = None

        if not self._session_history:
            empty = EmptyStatePanel(
                "📋",
                "No rounds accepted yet",
                "Accept a candidate to start tracking session history.",
            )
            self._session_history_layout.addWidget(empty)
            self._empty_session_history = empty
            self.session_history_group.setTitle("Session History")
            return

        # Build a table for the session rounds
        table = QTableWidget(len(self._session_history), 5)
        table.setHorizontalHeaderLabels([
            "Round", "Profit %", "Win Rate %", "Max Drawdown %", "Trades",
        ])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(f"""
            QTableWidget {{
                background: {_C_CARD_BG};
                alternate-background-color: {_C_DARK_BG};
                gridline-color: {_C_BORDER};
                border: 1px solid {_C_BORDER};
                border-radius: 6px;
                color: {_C_TEXT};
                font-size: 12px;
            }}
            QHeaderView::section {{
                background: {_C_DARK_BG};
                color: {_C_TEXT_DIM};
                border: none;
                border-bottom: 1px solid {_C_BORDER};
                padding: 6px 8px;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            QTableWidget::item {{
                padding: 6px 8px;
            }}
        """)

        for row_idx, session_round in enumerate(self._session_history):
            summary = session_round.summary

            # Round number
            round_item = QTableWidgetItem(f"Round {session_round.round_number}")
            round_item.setForeground(QColor(_C_TEXT_DIM))
            table.setItem(row_idx, 0, round_item)

            # Profit %
            profit = getattr(summary, "total_profit", 0.0) or 0.0
            profit_color = _C_GREEN_LIGHT if profit >= 0 else _C_RED_LIGHT
            profit_item = QTableWidgetItem(f"{profit:.2f}%")
            profit_item.setForeground(QColor(profit_color))
            table.setItem(row_idx, 1, profit_item)

            # Win rate %
            win_rate = getattr(summary, "win_rate", 0.0) or 0.0
            wr_color = _C_GREEN_LIGHT if win_rate >= 50 else _C_RED_LIGHT
            wr_item = QTableWidgetItem(f"{win_rate:.2f}%")
            wr_item.setForeground(QColor(wr_color))
            table.setItem(row_idx, 2, wr_item)

            # Max drawdown %
            max_dd = getattr(summary, "max_drawdown", 0.0) or 0.0
            dd_color = (
                _C_RED_LIGHT if max_dd > 20
                else (_C_YELLOW if max_dd > 10 else _C_GREEN_LIGHT)
            )
            dd_item = QTableWidgetItem(f"{max_dd:.2f}%")
            dd_item.setForeground(QColor(dd_color))
            table.setItem(row_idx, 3, dd_item)

            # Trade count
            trades = getattr(summary, "total_trades", 0) or 0
            trades_item = QTableWidgetItem(str(trades))
            trades_item.setForeground(QColor(_C_TEXT))
            table.setItem(row_idx, 4, trades_item)

        self._session_history_layout.addWidget(table)
        _fade_in_widget(table)

        self.session_history_group.setTitle(
            f"Session History ({len(self._session_history)} round(s))"
        )
