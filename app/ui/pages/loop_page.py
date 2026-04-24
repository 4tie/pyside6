"""
loop_page.py — Enhanced Strategy Lab UI page.

Full-featured optimization workbench: multi-gate validation, hyperopt mode,
AI advisor, transparent iteration history, and accept/discard/rollback controls.
"""
from __future__ import annotations

import copy
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSpinBox, QSplitter, QVBoxLayout, QWidget, QLineEdit,
)

from app.app_state.settings_state import SettingsState
from app.core.backtests.results_models import BacktestResults, BacktestSummary
from app.core.freqtrade.resolvers.strategy_resolver import detect_strategy_timeframe
from app.core.models.loop_models import LoopConfig, LoopIteration, LoopResult
from app.core.models.settings_models import AppSettings
from app.core.services.ai_advisor_service import AIAdvisorService
from app.core.services.backtest_service import BacktestService
from app.core.services.improve_service import ImproveService
from app.core.services.loop_service import (
    LoopService,
    build_diagnosis_input,
    build_score_input,
)
from app.core.services.process_service import ProcessService
from app.core.utils.app_logger import get_logger
from app.ui.theme import PALETTE as _THEME_PALETTE
from app.ui.widgets.iteration_history_row import IterationHistoryRow
from app.ui.widgets.terminal_widget import TerminalWidget

_log = get_logger("ui.loop_page")

# ---------------------------------------------------------------------------
# Color palette — sourced from the centralised theme (dark palette)
# ---------------------------------------------------------------------------
_C_GREEN       = _THEME_PALETTE["success"]
_C_RED         = _THEME_PALETTE["danger"]
_C_ORANGE      = _THEME_PALETTE["warning"]
_C_YELLOW      = "#dcdcaa"   # VS Code yellow — no direct theme key, kept as-is
_C_AMBER       = "#e5a000"   # amber accent — no direct theme key, kept as-is
_C_DARK_BG     = _THEME_PALETTE["bg_base"]
_C_CARD_BG     = _THEME_PALETTE["bg_surface"]
_C_ELEVATED    = _THEME_PALETTE["bg_elevated"]
_C_BORDER      = _THEME_PALETTE["border"]
_C_TEXT        = _THEME_PALETTE["text_primary"]
_C_TEXT_DIM    = _THEME_PALETTE["text_secondary"]

_TIMERANGE_PRESETS = ["7d", "14d", "30d", "90d", "120d", "360d"]
_HYPEROPT_SPACES   = ["buy", "sell", "roi", "stoploss", "trailing"]
_HYPEROPT_LOSSES   = [
    "SharpeHyperOptLoss", "CalmarHyperOptLoss", "SortinoHyperOptLoss",
    "OnlyProfitHyperOptLoss", "MaxDrawDownHyperOptLoss",
    "ProfitDrawDownHyperOptLoss",
]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _btn(label: str, bg: str, fg: str = "white", min_w: int = 120) -> QPushButton:
    b = QPushButton(label)
    b.setMinimumWidth(min_w)
    b.setStyleSheet(f"""
        QPushButton {{
            background:{bg}; color:{fg};
            border:1px solid {bg}; border-radius:4px;
            padding:6px 14px; font-size:12px; font-weight:bold;
        }}
        QPushButton:hover {{ border-color:{_C_GREEN}; }}
        QPushButton:disabled {{
            background:{_C_BORDER}; color:{_C_TEXT_DIM}; border-color:{_C_BORDER};
        }}
    """)
    return b


def _lbl(text: str, dim: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{'#9d9d9d' if dim else _C_TEXT};font-size:11px;")
    return lbl


class _StatCard(QFrame):
    """Compact stat card: label + big value."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(110)
        self.setMaximumWidth(160)
        self.setStyleSheet(f"""
            _StatCard {{
                background:{_C_CARD_BG}; border:1px solid {_C_BORDER}; border-radius:8px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{_C_TEXT_DIM};font-size:9px;font-weight:600;letter-spacing:1px;")
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl)
        self._val = QLabel("\u2014")
        self._val.setStyleSheet(f"color:{_C_TEXT};font-size:17px;font-weight:bold;")
        self._val.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._val)

    def set_value(self, text: str, color: str = _C_TEXT) -> None:
        self._val.setText(text)
        self._val.setStyleSheet(f"color:{color};font-size:17px;font-weight:bold;")


class _GateIndicator(QFrame):
    """Five-slot gate progress indicator: ○ pending / ⟳ running / ✓ pass / ✗ fail."""

    _GATE_NAMES = ["in_sample", "out_of_sample", "walk_forward", "stress_test", "consistency"]
    _GATE_LABELS = ["IS", "OOS", "WF", "ST", "CV"]

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(4)
        self._slots: List[QLabel] = []
        for label in self._GATE_LABELS:
            slot = QLabel(f"\u25cb{label}")
            slot.setStyleSheet(f"color:{_C_TEXT_DIM};font-size:9px;font-weight:bold;")
            slot.setAlignment(Qt.AlignCenter)
            slot.setToolTip(label)
            lay.addWidget(slot)
            self._slots.append(slot)

    def reset(self) -> None:
        for i, slot in enumerate(self._slots):
            slot.setText(f"\u25cb{self._GATE_LABELS[i]}")
            slot.setStyleSheet(f"color:{_C_TEXT_DIM};font-size:9px;font-weight:bold;")
            slot.setToolTip(self._GATE_LABELS[i])

    def set_running(self, gate_name: str) -> None:
        idx = self._gate_index(gate_name)
        if idx >= 0:
            self._slots[idx].setText(f"\u27f3{self._GATE_LABELS[idx]}")
            self._slots[idx].setStyleSheet(f"color:{_C_YELLOW};font-size:9px;font-weight:bold;")

    def set_passed(self, gate_name: str) -> None:
        idx = self._gate_index(gate_name)
        if idx >= 0:
            self._slots[idx].setText(f"\u2713{self._GATE_LABELS[idx]}")
            self._slots[idx].setStyleSheet(f"color:{_C_GREEN};font-size:9px;font-weight:bold;")

    def set_failed(self, gate_name: str, reason: str = "") -> None:
        idx = self._gate_index(gate_name)
        if idx >= 0:
            self._slots[idx].setText(f"\u2717{self._GATE_LABELS[idx]}")
            self._slots[idx].setStyleSheet(f"color:{_C_RED};font-size:9px;font-weight:bold;")
            if reason:
                self._slots[idx].setToolTip(reason)

    def _gate_index(self, gate_name: str) -> int:
        try:
            return self._GATE_NAMES.index(gate_name)
        except ValueError:
            return -1


class _WorkflowIndicator(QFrame):
    """Workflow stage indicator: changes → backtest → analyze → changes."""

    _STAGE_NAMES = ["changes", "backtest", "analyze", "apply"]
    _STAGE_LABELS = ["Changes", "Backtest", "Analyze", "Apply"]

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(4)
        self._slots: List[QLabel] = []
        for label in self._STAGE_LABELS:
            slot = QLabel(f"\u25cb{label}")
            slot.setStyleSheet(f"color:{_C_TEXT_DIM};font-size:9px;font-weight:bold;")
            slot.setAlignment(Qt.AlignCenter)
            slot.setToolTip(label)
            lay.addWidget(slot)
            self._slots.append(slot)

    def reset(self) -> None:
        for i, slot in enumerate(self._slots):
            slot.setText(f"\u25cb{self._STAGE_LABELS[i]}")
            slot.setStyleSheet(f"color:{_C_TEXT_DIM};font-size:9px;font-weight:bold;")
            slot.setToolTip(self._STAGE_LABELS[i])

    def set_running(self, stage_name: str) -> None:
        idx = self._stage_index(stage_name)
        if idx >= 0:
            self._slots[idx].setText(f"\u27f3{self._STAGE_LABELS[idx]}")
            self._slots[idx].setStyleSheet(f"color:{_C_YELLOW};font-size:9px;font-weight:bold;")

    def set_completed(self, stage_name: str) -> None:
        idx = self._stage_index(stage_name)
        if idx >= 0:
            self._slots[idx].setText(f"\u2713{self._STAGE_LABELS[idx]}")
            self._slots[idx].setStyleSheet(f"color:{_C_GREEN};font-size:9px;font-weight:bold;")

    def _stage_index(self, stage_name: str) -> int:
        try:
            return self._STAGE_NAMES.index(stage_name)
        except ValueError:
            return -1


# ---------------------------------------------------------------------------
# LoopPage
# ---------------------------------------------------------------------------

class LoopPage(QWidget):
    """Enhanced Strategy Lab — full-featured optimization workbench.

    Runs iterative backtest → diagnose → suggest → apply cycles with
    multi-gate validation, hyperopt mode, AI advisor, and transparent
    iteration history.

    Args:
        settings_state: Application settings state with Qt signals.
        ai_service: Optional AIService instance for AI Advisor.
    """

    loop_completed = Signal(object)  # emits LoopResult

    def __init__(self, settings_state: SettingsState, ai_service=None, parent=None):
        super().__init__(parent)
        self._settings_state = settings_state
        self._ai_service = ai_service

        # Services
        _backtest_svc = BacktestService(settings_state.settings_service)
        self._improve_service = ImproveService(settings_state.settings_service, _backtest_svc)
        self._loop_service = LoopService(self._improve_service)
        self._process_service = ProcessService()

        # AI Advisor
        if ai_service is not None:
            self._ai_advisor = AIAdvisorService(ai_service)
            self._loop_service.set_ai_advisor(self._ai_advisor)
        else:
            self._ai_advisor = None

        # Loop state
        self._loop_result: Optional[LoopResult] = None
        self._current_iteration: Optional[LoopIteration] = None
        self._run_started_at: float = 0.0
        self._sandbox_dir: Optional[Path] = None
        self._export_dir: Optional[Path] = None
        self._initial_params: dict = {}
        self._session_history: List[dict] = []  # accepted param sets for rollback
        
        # Workflow stage tracking
        self._current_stage = "idle"

        # Terminal (created early for MainWindow._all_terminals)
        self._terminal = TerminalWidget()

        settings_state.settings_changed.connect(self._refresh_strategies)
        settings_state.settings_changed.connect(self._check_config_guard)

        self._init_ui()
        self._refresh_strategies()
        self._restore_preferences()
        QTimer.singleShot(0, self._cleanup_stale_sandboxes)

    # ------------------------------------------------------------------
    # terminal property (for MainWindow._all_terminals)
    # ------------------------------------------------------------------

    @property
    def terminal(self) -> TerminalWidget:
        return self._terminal

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        # Note: Most styling is handled by the global QSS from theme.py.
        # Only custom objectName-specific styles are set inline here.

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Config guard banner
        self._no_config_banner = QLabel("")
        self._no_config_banner.setObjectName("warning_banner")
        self._no_config_banner.setWordWrap(True)
        self._no_config_banner.setVisible(False)
        root.addWidget(self._no_config_banner)

        # Title
        title = QLabel("Strategy Lab")
        title.setObjectName("page_title")
        root.addWidget(title)

        # Config panel (scrollable)
        config_scroll = QScrollArea()
        config_scroll.setWidgetResizable(True)
        config_scroll.setMaximumHeight(420)
        config_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        config_inner = QWidget()
        config_vlay = QVBoxLayout(config_inner)
        config_vlay.setContentsMargins(0, 0, 0, 0)
        config_vlay.setSpacing(6)

        config_vlay.addWidget(self._build_config_group())
        config_scroll.setWidget(config_inner)
        root.addWidget(config_scroll)

        # Control row
        root.addLayout(self._build_control_row())

        # Progress bar — use theme accent color
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(14)
        root.addWidget(self._progress_bar)

        # Stat cards
        root.addLayout(self._build_stat_cards())

        # Gate indicator for current iteration
        gate_row = QHBoxLayout()
        gate_row.addWidget(_lbl("Gates:"))
        self._gate_indicator = _GateIndicator()
        gate_row.addWidget(self._gate_indicator)
        gate_row.addStretch()
        root.addLayout(gate_row)

        # Workflow indicator for current iteration
        workflow_row = QHBoxLayout()
        workflow_row.addWidget(_lbl("Workflow:"))
        self._workflow_indicator = _WorkflowIndicator()
        workflow_row.addWidget(self._workflow_indicator)
        workflow_row.addStretch()
        root.addLayout(workflow_row)

        # Splitter: history + terminal
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._build_history_panel())
        splitter.addWidget(self._build_terminal_panel())
        splitter.setSizes([300, 200])
        root.addWidget(splitter, 1)

        # Best result panel
        root.addWidget(self._build_best_result_panel())

    def _build_control_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self._start_btn = _btn("▶  Start Loop", _C_GREEN)
        self._start_btn.clicked.connect(self._on_start)
        row.addWidget(self._start_btn)

        self._stop_btn = _btn("⏹  Stop", _C_RED)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        row.addWidget(self._stop_btn)

        row.addStretch()

        self._status_lbl = QLabel("Idle")
        self._status_lbl.setObjectName("hint_label")
        row.addWidget(self._status_lbl)

        return row

    def _build_stat_cards(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        self._stat_iter   = _StatCard("ITERATION")
        self._stat_profit = _StatCard("BEST PROFIT")
        self._stat_wr     = _StatCard("BEST WIN RATE")
        self._stat_dd     = _StatCard("BEST DRAWDOWN")
        self._stat_sharpe = _StatCard("BEST SHARPE")
        self._stat_score  = _StatCard("BEST SCORE")
        for card in (self._stat_iter, self._stat_profit, self._stat_wr,
                     self._stat_dd, self._stat_sharpe, self._stat_score):
            row.addWidget(card)
        row.addStretch()
        return row

    def _build_history_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        hdr = QHBoxLayout()
        title = QLabel("Iteration History")
        title.setStyleSheet("font-weight:bold;")
        hdr.addWidget(title)
        hdr.addStretch()
        lay.addLayout(hdr)

        self._history_scroll = QScrollArea()
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._history_scroll.setMinimumHeight(180)

        self._history_content = QWidget()
        self._history_vlay = QVBoxLayout(self._history_content)
        self._history_vlay.setContentsMargins(2, 2, 2, 2)
        self._history_vlay.setSpacing(4)

        self._empty_history_lbl = QLabel("No iterations yet \u2014 start the loop to begin.")
        self._empty_history_lbl.setObjectName("hint_label")
        self._empty_history_lbl.setAlignment(Qt.AlignCenter)
        self._history_vlay.addWidget(self._empty_history_lbl)
        self._history_vlay.addStretch()

        self._history_scroll.setWidget(self._history_content)
        lay.addWidget(self._history_scroll, 1)
        return w

    def _build_terminal_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        hdr = QLabel("Live Output")
        hdr.setStyleSheet("font-weight:bold;")
        lay.addWidget(hdr)
        lay.addWidget(self._terminal, 1)
        return w

    def _build_best_result_panel(self) -> QGroupBox:
        self._best_group = QGroupBox("Best Result Found")
        self._best_group.setVisible(False)
        lay = QVBoxLayout()
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        self._best_summary_lbl = QLabel("")
        self._best_summary_lbl.setWordWrap(True)
        lay.addWidget(self._best_summary_lbl)

        self._best_score_lbl = QLabel("")
        self._best_score_lbl.setWordWrap(True)
        self._best_score_lbl.setObjectName("hint_label")
        lay.addWidget(self._best_score_lbl)

        self._best_delta_lbl = QLabel("")
        self._best_delta_lbl.setWordWrap(True)
        self._best_delta_lbl.setObjectName("hint_label")
        lay.addWidget(self._best_delta_lbl)

        btn_row = QHBoxLayout()
        self._apply_best_btn = _btn("Apply Best Result", _C_GREEN)
        self._apply_best_btn.clicked.connect(self._on_apply_best)
        btn_row.addWidget(self._apply_best_btn)

        self._discard_btn = _btn("Discard", _C_BORDER, _C_TEXT, 80)
        self._discard_btn.clicked.connect(self._on_discard)
        btn_row.addWidget(self._discard_btn)

        self._rollback_btn = _btn("Rollback", _C_ELEVATED, _C_TEXT, 80)
        self._rollback_btn.clicked.connect(self._on_rollback)
        self._rollback_btn.setEnabled(False)
        btn_row.addWidget(self._rollback_btn)

        btn_row.addStretch()
        lay.addLayout(btn_row)
        self._best_group.setLayout(lay)
        return self._best_group

    # ------------------------------------------------------------------
    # Config guard + strategy refresh
    # ------------------------------------------------------------------

    def _check_config_guard(self) -> None:
        settings = self._settings_state.current_settings
        if not settings or not settings.user_data_path:
            self._no_config_banner.setText(
                "Warning: User data path is not configured. "
                "Go to Settings and set your Freqtrade user_data directory."
            )
            self._no_config_banner.setVisible(True)
        else:
            self._no_config_banner.setVisible(False)
        self._update_state_machine()

    def _refresh_strategies(self) -> None:
        strategies = self._improve_service.get_available_strategies()
        current = self._strategy_combo.currentText()
        self._strategy_combo.blockSignals(True)
        self._strategy_combo.clear()
        if strategies:
            self._strategy_combo.addItems(strategies)
            idx = self._strategy_combo.findText(current)
            if idx >= 0:
                self._strategy_combo.setCurrentIndex(idx)
        else:
            self._strategy_combo.addItem("(no strategies found)")
        self._strategy_combo.blockSignals(False)
        self._check_config_guard()

    # ------------------------------------------------------------------
    # UI event handlers
    # ------------------------------------------------------------------

    def _on_select_pairs(self) -> None:
        """Open the PairsSelectorDialog to choose pairs."""
        try:
            from app.ui.dialogs.pairs_selector_dialog import PairsSelectorDialog
            settings = self._settings_state.settings_service.load_settings()
            dlg = PairsSelectorDialog(
                favorites=settings.favorite_pairs,
                selected=self._selected_pairs,
                settings_state=self._settings_state,
                parent=self,
            )
            if dlg.exec():
                self._selected_pairs = dlg.get_selected_pairs()
                self._pairs_btn.setText(f"Select Pairs ({len(self._selected_pairs)})")
        except Exception as exc:
            _log.warning("PairsSelectorDialog error: %s", exc)

    def _on_validation_mode_changed(self, index: int) -> None:
        self._quick_mode_warning.setVisible(index == 1)

    def _on_apply_best(self) -> None:
        if self._loop_result is None or self._loop_result.best_iteration is None:
            return
        best = self._loop_result.best_iteration
        strategy = self._strategy_combo.currentText().strip()

        # Show confirmation dialog with parameter diff
        changes = "\n".join(best.changes_summary) if best.changes_summary else "(no changes)"
        reply = QMessageBox.question(
            self, "Apply Best Result",
            f"Apply the following parameter changes to {strategy}?\n\n{changes}",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self._improve_service.accept_candidate(strategy, best.params_after)
            self._session_history.append(copy.deepcopy(best.params_after))
            self._rollback_btn.setEnabled(True)
            QMessageBox.information(self, "Applied", "Best result applied to strategy.")
            self.loop_completed.emit(self._loop_result)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to apply result: {exc}")

    def _on_discard(self) -> None:
        if self._sandbox_dir and self._sandbox_dir.exists():
            self._improve_service.reject_candidate(self._sandbox_dir)
        self._best_group.setVisible(False)
        self._loop_result = None
        self._update_state_machine()

    def _on_rollback(self) -> None:
        if not self._session_history:
            return
        strategy = self._strategy_combo.currentText().strip()
        # Show list of previous states
        items = [f"State {i + 1}" for i in range(len(self._session_history))]
        from PySide6.QtWidgets import QInputDialog
        item, ok = QInputDialog.getItem(
            self, "Rollback", "Select a previous state to restore:", items, 0, False
        )
        if not ok:
            return
        idx = items.index(item)
        try:
            self._improve_service.rollback(strategy, self._session_history[idx])
            QMessageBox.information(self, "Rolled Back", f"Restored to {item}.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Rollback failed: {exc}")

    # ------------------------------------------------------------------
    # Loop iteration execution
    # ------------------------------------------------------------------

    def _on_iteration_complete(self, iteration: LoopIteration) -> None:
        """Callback from LoopService when an iteration completes."""
        pass  # Handled in _on_backtest_finished

    def _on_loop_complete_cb(self, result: LoopResult) -> None:
        """Callback from LoopService when the loop finishes."""
        self._loop_result = result
        self._finalize_loop()

    def _on_status_update(self, message: str) -> None:
        self._set_status(message)
        self._update_workflow_indicator(message)

    def _update_workflow_indicator(self, message: str) -> None:
        """Update workflow indicator based on status message."""
        message_lower = message.lower()
        
        # Detect stage from message
        if "applying" in message_lower or "changes" in message_lower:
            if self._current_stage != "changes":
                self._workflow_indicator.set_running("changes")
                self._current_stage = "changes"
        elif "backtest" in message_lower or "running" in message_lower:
            if self._current_stage != "backtest":
                self._workflow_indicator.set_running("backtest")
                self._current_stage = "backtest"
        elif "analyze" in message_lower or "diagnose" in message_lower:
            if self._current_stage != "analyze":
                self._workflow_indicator.set_running("analyze")
                self._current_stage = "analyze"
        elif "apply" in message_lower or "complete" in message_lower:
            if self._current_stage != "apply":
                self._workflow_indicator.set_running("apply")
                self._current_stage = "apply"
        elif "idle" in message_lower or "stopped" in message_lower:
            self._workflow_indicator.reset()
            self._current_stage = "idle"

    def _finalize_loop(self) -> None:
        """Finalize the loop and update UI."""
        result = self._loop_service.finalize()
        self._loop_result = result
        stop_reason = result.stop_reason or "Complete"
        
        # Reset workflow indicator
        self._workflow_indicator.reset()
        self._current_stage = "idle"
        
        # Add user-friendly guidance based on stop reason
        guidance = self._get_stop_reason_guidance(stop_reason)
        self._set_status(f"{stop_reason} - {guidance}")
        
        self._progress_bar.setValue(100)
        self._update_state_machine()
        self._update_best_result_panel()
        self.loop_completed.emit(result)
        _log.info("Loop finalized: %s", stop_reason)

    def _get_stop_reason_guidance(self, stop_reason: str) -> str:
        """Get user-friendly guidance based on stop reason."""
        if "All profitability targets met" in stop_reason:
            return "Targets achieved! Review the best iteration below."
        elif "No further improvements suggested" in stop_reason:
            return "Review results and try different parameters or strategy."
        elif "All parameters already at optimal values" in stop_reason:
            return "Consider expanding parameter ranges or changing strategy."
        elif "All parameter variations have been tested" in stop_reason:
            return "Try expanding parameter ranges or starting fresh."
        elif "Complete" in stop_reason:
            return "Review the iteration history and best results."
        else:
            return "Review results and adjust strategy as needed."

    # ------------------------------------------------------------------
    # UI update helpers
    # ------------------------------------------------------------------

    def _set_status(self, message: str) -> None:
        self._status_lbl.setText(message)

    def _add_history_row(self, iteration: LoopIteration) -> None:
        """Add an iteration row to the history panel."""
        # Remove empty label and stretch on first row
        if self._empty_history_lbl is not None:
            self._empty_history_lbl.setVisible(False)

        config = self._loop_service._config
        total_gates = 2 if (config and config.validation_mode == "quick") else 5
        row = IterationHistoryRow(iteration, total_gates=total_gates)
        # Insert before the stretch (last item)
        insert_pos = max(0, self._history_vlay.count() - 1)
        self._history_vlay.insertWidget(insert_pos, row)

        # Auto-scroll to bottom
        QTimer.singleShot(50, lambda: self._history_scroll.verticalScrollBar().setValue(
            self._history_scroll.verticalScrollBar().maximum()
        ))

    def _update_best_result_panel(self) -> None:
        """Show the best result panel with metrics and delta."""
        result = self._loop_result
        if result is None or result.best_iteration is None:
            return

        best = result.best_iteration
        s = best.summary
        if s is None:
            return

        self._best_summary_lbl.setText(
            f"Best: Profit {s.total_profit:+.2f}%  |  "
            f"Win Rate {s.win_rate:.1f}%  |  "
            f"Drawdown {s.max_drawdown:.1f}%  |  "
            f"Trades {s.total_trades}"
        )

        if best.score:
            sc = best.score
            self._best_score_lbl.setText(
                f"RobustScore: {sc.total:.3f}  "
                f"(profit={sc.profitability:.3f}, "
                f"consistency={sc.consistency:.3f}, "
                f"stability={sc.stability:.3f}, "
                f"fragility={sc.fragility:.3f})"
            )

        changes = "\n".join(best.changes_summary) if best.changes_summary else "(no changes)"
        self._best_delta_lbl.setText(f"Changes:\n{changes}")

        self._best_group.setVisible(True)
        self._update_state_machine()

    # ------------------------------------------------------------------
    # Stale sandbox cleanup
    # ------------------------------------------------------------------

    def _cleanup_stale_sandboxes(self) -> None:
        """Clean up stale sandbox directories on page init."""
        try:
            self._improve_service.cleanup_stale_sandboxes()
        except Exception as exc:
            _log.warning("Stale sandbox cleanup error: %s", exc)

    # ------------------------------------------------------------------
    # Tab visibility (background running)
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        """Refresh UI when tab regains focus."""
        super().showEvent(event)
        self._update_stat_cards()
        self._update_state_machine()

    def _ensure_loop_runtime_state(self) -> None:
        """Initialize runtime-only attributes used by the async ladder flow."""
        if not hasattr(self, "_syncing_date_fields"):
            self._syncing_date_fields = False
        if not hasattr(self, "_current_gate_name"):
            self._current_gate_name = ""
        if not hasattr(self, "_current_gate_timerange"):
            self._current_gate_timerange = ""
        if not hasattr(self, "_current_gate_export_dir"):
            self._current_gate_export_dir = None
        if not hasattr(self, "_gate_run_started_at"):
            self._gate_run_started_at = 0.0
        if not hasattr(self, "_baseline_run_started_at"):
            self._baseline_run_started_at = 0.0
        if not hasattr(self, "_current_fold_timeranges"):
            self._current_fold_timeranges = []
        if not hasattr(self, "_current_fold_index"):
            self._current_fold_index = 0
        if not hasattr(self, "_iteration_in_sample_results"):
            self._iteration_in_sample_results = None
        if not hasattr(self, "_iteration_oos_results"):
            self._iteration_oos_results = None
        if not hasattr(self, "_iteration_fold_results"):
            self._iteration_fold_results = []
        if not hasattr(self, "_iteration_stress_results"):
            self._iteration_stress_results = None
        if not hasattr(self, "_latest_diagnosis_input"):
            self._latest_diagnosis_input = None

    @staticmethod
    def _parse_timerange_text(timerange: str) -> Optional[Tuple[str, str]]:
        """Return (date_from, date_to) when timerange is complete, else None."""
        if not timerange or "-" not in timerange:
            return None
        parts = timerange.split("-", 1)
        if len(parts) != 2:
            return None
        date_from = parts[0].strip()
        date_to = parts[1].strip()
        if not date_from or not date_to:
            return None
        return date_from, date_to

    @staticmethod
    def _is_valid_date_value(value: str) -> bool:
        """Return True when value matches YYYYMMDD."""
        try:
            datetime.strptime(value, "%Y%m%d")
            return True
        except ValueError:
            return False

    def _sync_timerange_from_dates(self) -> None:
        """Keep the legacy timerange field synchronized with the date inputs."""
        self._ensure_loop_runtime_state()
        if self._syncing_date_fields:
            return

        date_from = self._date_from_edit.text().strip()
        date_to = self._date_to_edit.text().strip()

        self._syncing_date_fields = True
        try:
            if date_from and date_to:
                self._timerange_edit.setText(f"{date_from}-{date_to}")
            else:
                self._timerange_edit.setText("")
        finally:
            self._syncing_date_fields = False

    def _sync_dates_from_timerange(self) -> None:
        """Keep explicit date fields synchronized from the timerange field."""
        self._ensure_loop_runtime_state()
        if self._syncing_date_fields:
            return

        parsed = self._parse_timerange_text(self._timerange_edit.text().strip())
        if parsed is None:
            return

        date_from, date_to = parsed
        self._syncing_date_fields = True
        try:
            self._date_from_edit.setText(date_from)
            self._date_to_edit.setText(date_to)
        finally:
            self._syncing_date_fields = False

    def _build_config_group(self) -> QGroupBox:
        """Build the Strategy Lab configuration form."""
        self._ensure_loop_runtime_state()

        group = QGroupBox("Loop Configuration")
        lay = QGridLayout()
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setHorizontalSpacing(12)
        lay.setVerticalSpacing(8)

        lay.addWidget(_lbl("Strategy:"), 0, 0)
        self._strategy_combo = QComboBox()
        self._strategy_combo.setMinimumWidth(200)
        lay.addWidget(self._strategy_combo, 0, 1)
        lay.addWidget(_lbl("Max Iterations:"), 0, 2)
        self._max_iter_spin = QSpinBox()
        self._max_iter_spin.setRange(1, 100)
        self._max_iter_spin.setValue(10)
        lay.addWidget(self._max_iter_spin, 0, 3)

        lay.addWidget(_lbl("Target Profit (%):"), 1, 0)
        self._target_profit_spin = QDoubleSpinBox()
        self._target_profit_spin.setRange(-100.0, 10000.0)
        self._target_profit_spin.setValue(5.0)
        self._target_profit_spin.setSingleStep(0.5)
        lay.addWidget(self._target_profit_spin, 1, 1)
        lay.addWidget(_lbl("Target Win Rate (%):"), 1, 2)
        self._target_wr_spin = QDoubleSpinBox()
        self._target_wr_spin.setRange(0.0, 100.0)
        self._target_wr_spin.setValue(55.0)
        lay.addWidget(self._target_wr_spin, 1, 3)

        lay.addWidget(_lbl("Max Drawdown (%):"), 2, 0)
        self._target_dd_spin = QDoubleSpinBox()
        self._target_dd_spin.setRange(0.0, 100.0)
        self._target_dd_spin.setValue(20.0)
        lay.addWidget(self._target_dd_spin, 2, 1)
        lay.addWidget(_lbl("Min Trades:"), 2, 2)
        self._target_trades_spin = QSpinBox()
        self._target_trades_spin.setRange(1, 10000)
        self._target_trades_spin.setValue(30)
        lay.addWidget(self._target_trades_spin, 2, 3)

        self._stop_on_target_chk = QCheckBox("Stop as soon as all targets are met")
        self._stop_on_target_chk.setChecked(True)
        lay.addWidget(self._stop_on_target_chk, 3, 0, 1, 4)

        lay.addWidget(_lbl("Date Presets:"), 4, 0)
        timerange_widget = QWidget()
        timerange_widget.setStyleSheet("background:transparent;")
        tr_lay = QHBoxLayout(timerange_widget)
        tr_lay.setContentsMargins(0, 0, 0, 0)
        tr_lay.setSpacing(4)
        for preset in _TIMERANGE_PRESETS:
            pb = QPushButton(preset)
            pb.setFixedWidth(42)
            pb.setStyleSheet(f"""
                QPushButton {{
                    background:{_C_ELEVATED}; color:{_C_TEXT_DIM};
                    border:1px solid {_C_BORDER}; border-radius:3px;
                    padding:2px 4px; font-size:10px;
                }}
                QPushButton:hover {{ border-color:{_C_GREEN}; color:{_C_TEXT}; }}
            """)
            pb.clicked.connect(lambda checked, p=preset: self._on_timerange_preset(p))
            tr_lay.addWidget(pb)
        tr_lay.addStretch()
        lay.addWidget(timerange_widget, 4, 1, 1, 3)

        lay.addWidget(_lbl("Start Date:"), 5, 0)
        self._date_from_edit = QLineEdit()
        self._date_from_edit.setPlaceholderText("YYYYMMDD")
        self._date_from_edit.textChanged.connect(self._sync_timerange_from_dates)
        lay.addWidget(self._date_from_edit, 5, 1)
        lay.addWidget(_lbl("End Date:"), 5, 2)
        self._date_to_edit = QLineEdit()
        self._date_to_edit.setPlaceholderText("YYYYMMDD")
        self._date_to_edit.textChanged.connect(self._sync_timerange_from_dates)
        lay.addWidget(self._date_to_edit, 5, 3)

        lay.addWidget(_lbl("Timerange:"), 6, 0)
        self._timerange_edit = QLineEdit()
        self._timerange_edit.setPlaceholderText("YYYYMMDD-YYYYMMDD")
        self._timerange_edit.textChanged.connect(self._sync_dates_from_timerange)
        lay.addWidget(self._timerange_edit, 6, 1, 1, 3)

        lay.addWidget(_lbl("Pairs:"), 7, 0)
        self._pairs_btn = QPushButton("Select Pairs (0)")
        self._pairs_btn.setStyleSheet(f"""
            QPushButton {{
                background:{_C_ELEVATED}; color:{_C_TEXT};
                border:1px solid {_C_BORDER}; border-radius:4px;
                padding:4px 10px; font-size:11px;
            }}
            QPushButton:hover {{ border-color:{_C_GREEN}; }}
        """)
        self._pairs_btn.clicked.connect(self._on_select_pairs)
        self._selected_pairs = []
        lay.addWidget(self._pairs_btn, 7, 1, 1, 3)

        lay.addWidget(_lbl("OOS Split (%):"), 8, 0)
        self._oos_split_spin = QDoubleSpinBox()
        self._oos_split_spin.setRange(5.0, 50.0)
        self._oos_split_spin.setValue(20.0)
        lay.addWidget(self._oos_split_spin, 8, 1)
        lay.addWidget(_lbl("Walk-Forward Folds:"), 8, 2)
        self._wf_folds_spin = QSpinBox()
        self._wf_folds_spin.setRange(2, 10)
        self._wf_folds_spin.setValue(5)
        lay.addWidget(self._wf_folds_spin, 8, 3)

        lay.addWidget(_lbl("Stress Fee Mult:"), 9, 0)
        self._stress_fee_spin = QDoubleSpinBox()
        self._stress_fee_spin.setRange(1.0, 5.0)
        self._stress_fee_spin.setSingleStep(0.1)
        self._stress_fee_spin.setValue(2.0)
        lay.addWidget(self._stress_fee_spin, 9, 1)
        lay.addWidget(_lbl("Stress Slippage (%):"), 9, 2)
        self._stress_slippage_spin = QDoubleSpinBox()
        self._stress_slippage_spin.setRange(0.0, 2.0)
        self._stress_slippage_spin.setSingleStep(0.01)
        self._stress_slippage_spin.setValue(0.1)
        lay.addWidget(self._stress_slippage_spin, 9, 3)

        lay.addWidget(_lbl("Stress Profit Target (%):"), 10, 0)
        self._stress_profit_spin = QDoubleSpinBox()
        self._stress_profit_spin.setRange(0.0, 100.0)
        self._stress_profit_spin.setValue(50.0)
        lay.addWidget(self._stress_profit_spin, 10, 1)
        lay.addWidget(_lbl("Consistency Threshold (%):"), 10, 2)
        self._consistency_spin = QDoubleSpinBox()
        self._consistency_spin.setRange(0.0, 100.0)
        self._consistency_spin.setValue(30.0)
        lay.addWidget(self._consistency_spin, 10, 3)

        lay.addWidget(_lbl("Validation Mode:"), 11, 0)
        self._validation_mode_combo = QComboBox()
        self._validation_mode_combo.addItems(["Full", "Quick"])
        self._validation_mode_combo.currentIndexChanged.connect(self._on_validation_mode_changed)
        lay.addWidget(self._validation_mode_combo, 11, 1)
        self._quick_mode_warning = QLabel(
            "Quick mode runs Gate 1 + OOS only. Walk-forward, stress, and consistency are skipped."
        )
        self._quick_mode_warning.setStyleSheet(f"color:{_C_AMBER};font-size:10px;")
        self._quick_mode_warning.setVisible(False)
        lay.addWidget(self._quick_mode_warning, 11, 2, 1, 2)

        lay.addWidget(_lbl("Iteration Mode:"), 12, 0)
        self._iteration_mode_combo = QComboBox()
        self._iteration_mode_combo.addItems(["Rule-Based Mutations", "Hyperopt-Guided"])
        self._iteration_mode_combo.currentIndexChanged.connect(self._on_iteration_mode_changed)
        lay.addWidget(self._iteration_mode_combo, 12, 1, 1, 3)

        self._hyperopt_block_lbl = QLabel(
            "Hyperopt-guided runtime is not implemented in this pass. Use rule-based mode to run Strategy Lab."
        )
        self._hyperopt_block_lbl.setStyleSheet(f"color:{_C_AMBER};font-size:10px;")
        self._hyperopt_block_lbl.setVisible(False)
        lay.addWidget(self._hyperopt_block_lbl, 13, 0, 1, 4)

        self._hyperopt_widget = QWidget()
        self._hyperopt_widget.setStyleSheet("background:transparent;")
        ho_lay = QGridLayout(self._hyperopt_widget)
        ho_lay.setContentsMargins(0, 0, 0, 0)
        ho_lay.setSpacing(8)

        ho_lay.addWidget(_lbl("Epochs:"), 0, 0)
        self._hyperopt_epochs_spin = QSpinBox()
        self._hyperopt_epochs_spin.setRange(50, 2000)
        self._hyperopt_epochs_spin.setValue(200)
        ho_lay.addWidget(self._hyperopt_epochs_spin, 0, 1)

        ho_lay.addWidget(_lbl("Loss Function:"), 0, 2)
        self._hyperopt_loss_combo = QComboBox()
        self._hyperopt_loss_combo.addItems(_HYPEROPT_LOSSES)
        ho_lay.addWidget(self._hyperopt_loss_combo, 0, 3)

        ho_lay.addWidget(_lbl("Spaces:"), 1, 0)
        spaces_widget = QWidget()
        spaces_widget.setStyleSheet("background:transparent;")
        spaces_lay = QHBoxLayout(spaces_widget)
        spaces_lay.setContentsMargins(0, 0, 0, 0)
        spaces_lay.setSpacing(4)
        self._hyperopt_space_checks = {}
        for space in _HYPEROPT_SPACES:
            chk = QCheckBox(space)
            chk.setChecked(True)
            spaces_lay.addWidget(chk)
            self._hyperopt_space_checks[space] = chk
        spaces_lay.addStretch()
        ho_lay.addWidget(spaces_widget, 1, 1, 1, 3)

        self._hyperopt_widget.setVisible(False)
        lay.addWidget(self._hyperopt_widget, 14, 0, 1, 4)

        lay.addWidget(_lbl("AI Advisor:"), 15, 0)
        self._ai_advisor_chk = QCheckBox("Enable AI Advisor")
        self._ai_advisor_chk.setChecked(False)
        lay.addWidget(self._ai_advisor_chk, 15, 1, 1, 3)

        group.setLayout(lay)
        return group

    def _update_state_machine(self) -> None:
        """Update enabled/disabled widget state based on config and runtime."""
        settings = self._settings_state.current_settings
        ok = bool(settings and settings.user_data_path)
        is_running = self._loop_service.is_running or getattr(self, '_baseline_in_progress', False)
        strategy = self._strategy_combo.currentText().strip()
        has_strategy = bool(strategy) and not strategy.startswith("(")
        has_result = (
            self._loop_result is not None
            and self._loop_result.best_iteration is not None
        )
        hyperopt_selected = self._iteration_mode_combo.currentIndex() == 1

        config_widgets = [
            self._strategy_combo, self._max_iter_spin, self._target_profit_spin,
            self._target_wr_spin, self._target_dd_spin, self._target_trades_spin,
            self._stop_on_target_chk, self._date_from_edit, self._date_to_edit,
            self._timerange_edit, self._oos_split_spin, self._wf_folds_spin,
            self._stress_fee_spin, self._stress_slippage_spin, self._stress_profit_spin,
            self._consistency_spin, self._validation_mode_combo,
            self._iteration_mode_combo, self._pairs_btn, self._ai_advisor_chk,
            self._hyperopt_epochs_spin, self._hyperopt_loss_combo,
        ]
        for widget in config_widgets:
            widget.setEnabled(ok and not is_running)
        for chk in self._hyperopt_space_checks.values():
            chk.setEnabled(ok and not is_running)

        self._hyperopt_block_lbl.setVisible(hyperopt_selected)

        self._start_btn.setVisible(not is_running)
        self._start_btn.setEnabled(ok and has_strategy and not is_running and not hyperopt_selected)
        self._start_btn.setToolTip(
            "Hyperopt-guided runtime is not implemented in this pass."
            if hyperopt_selected else ""
        )
        self._stop_btn.setVisible(is_running)
        self._stop_btn.setEnabled(is_running)

        self._apply_best_btn.setEnabled(has_result and not is_running)
        self._discard_btn.setEnabled(has_result and not is_running)
        self._rollback_btn.setEnabled(len(self._session_history) > 0 and not is_running)

    def _restore_preferences(self) -> None:
        """Restore saved StrategyLabPreferences from AppSettings."""
        self._ensure_loop_runtime_state()
        try:
            settings = self._settings_state.current_settings
            if not settings:
                return
            prefs = settings.strategy_lab

            if prefs.strategy:
                idx = self._strategy_combo.findText(prefs.strategy)
                if idx >= 0:
                    self._strategy_combo.setCurrentIndex(idx)

            self._max_iter_spin.setValue(prefs.max_iterations)
            self._target_profit_spin.setValue(prefs.target_profit_pct)
            self._target_wr_spin.setValue(prefs.target_win_rate)
            self._target_dd_spin.setValue(prefs.target_max_drawdown)
            self._target_trades_spin.setValue(prefs.target_min_trades)
            self._stop_on_target_chk.setChecked(prefs.stop_on_first_profitable)

            date_from = prefs.date_from
            date_to = prefs.date_to
            if (not date_from or not date_to) and prefs.timerange:
                parsed = self._parse_timerange_text(prefs.timerange)
                if parsed is not None:
                    date_from, date_to = parsed

            self._syncing_date_fields = True
            try:
                self._date_from_edit.setText(date_from or "")
                self._date_to_edit.setText(date_to or "")
                if date_from and date_to:
                    self._timerange_edit.setText(f"{date_from}-{date_to}")
                else:
                    self._timerange_edit.setText(prefs.timerange)
            finally:
                self._syncing_date_fields = False

            self._oos_split_spin.setValue(prefs.oos_split_pct)
            self._wf_folds_spin.setValue(prefs.walk_forward_folds)
            self._stress_fee_spin.setValue(prefs.stress_fee_multiplier)
            self._stress_slippage_spin.setValue(prefs.stress_slippage_pct)
            self._stress_profit_spin.setValue(prefs.stress_profit_target_pct)
            self._consistency_spin.setValue(prefs.consistency_threshold_pct)
            self._validation_mode_combo.setCurrentIndex(0 if prefs.validation_mode == "full" else 1)
            self._iteration_mode_combo.setCurrentIndex(0 if prefs.iteration_mode == "rule_based" else 1)
            self._hyperopt_epochs_spin.setValue(prefs.hyperopt_epochs)
            loss_idx = self._hyperopt_loss_combo.findText(prefs.hyperopt_loss_function)
            if loss_idx >= 0:
                self._hyperopt_loss_combo.setCurrentIndex(loss_idx)
            for space, chk in self._hyperopt_space_checks.items():
                chk.setChecked(space in prefs.hyperopt_spaces if prefs.hyperopt_spaces else True)
            self._ai_advisor_chk.setChecked(prefs.ai_advisor_enabled)
            if prefs.pairs:
                self._selected_pairs = [p.strip() for p in prefs.pairs.split(",") if p.strip()]
                self._pairs_btn.setText(f"Select Pairs ({len(self._selected_pairs)})")
        except Exception as exc:
            _log.warning("Failed to restore StrategyLabPreferences: %s", exc)
        self._on_iteration_mode_changed(self._iteration_mode_combo.currentIndex())

    def _save_preferences(self) -> None:
        """Persist current UI values to AppSettings.strategy_lab."""
        self._ensure_loop_runtime_state()
        try:
            settings = self._settings_state.settings_service.load_settings()
            prefs = settings.strategy_lab
            prefs.strategy = self._strategy_combo.currentText()
            prefs.max_iterations = self._max_iter_spin.value()
            prefs.target_profit_pct = self._target_profit_spin.value()
            prefs.target_win_rate = self._target_wr_spin.value()
            prefs.target_max_drawdown = self._target_dd_spin.value()
            prefs.target_min_trades = self._target_trades_spin.value()
            prefs.stop_on_first_profitable = self._stop_on_target_chk.isChecked()
            prefs.date_from = self._date_from_edit.text().strip()
            prefs.date_to = self._date_to_edit.text().strip()
            prefs.timerange = self._timerange_edit.text().strip()
            prefs.oos_split_pct = self._oos_split_spin.value()
            prefs.walk_forward_folds = self._wf_folds_spin.value()
            prefs.stress_fee_multiplier = self._stress_fee_spin.value()
            prefs.stress_slippage_pct = self._stress_slippage_spin.value()
            prefs.stress_profit_target_pct = self._stress_profit_spin.value()
            prefs.consistency_threshold_pct = self._consistency_spin.value()
            prefs.validation_mode = "full" if self._validation_mode_combo.currentIndex() == 0 else "quick"
            prefs.iteration_mode = "rule_based" if self._iteration_mode_combo.currentIndex() == 0 else "hyperopt"
            prefs.hyperopt_epochs = self._hyperopt_epochs_spin.value()
            prefs.hyperopt_loss_function = self._hyperopt_loss_combo.currentText()
            prefs.hyperopt_spaces = [
                space for space, chk in self._hyperopt_space_checks.items() if chk.isChecked()
            ]
            prefs.ai_advisor_enabled = self._ai_advisor_chk.isChecked()
            prefs.pairs = ",".join(self._selected_pairs)
            self._settings_state.save_settings(settings)
        except Exception as exc:
            _log.warning("Failed to save StrategyLabPreferences: %s", exc)

    def _on_timerange_preset(self, preset: str) -> None:
        """Apply a preset to the explicit date fields and timerange field."""
        self._ensure_loop_runtime_state()
        days = int(preset.replace("d", ""))
        date_to = datetime.now()
        date_from = date_to - timedelta(days=days)

        self._syncing_date_fields = True
        try:
            self._date_from_edit.setText(date_from.strftime("%Y%m%d"))
            self._date_to_edit.setText(date_to.strftime("%Y%m%d"))
            self._timerange_edit.setText(
                f"{date_from.strftime('%Y%m%d')}-{date_to.strftime('%Y%m%d')}"
            )
        finally:
            self._syncing_date_fields = False

    def _on_iteration_mode_changed(self, index: int) -> None:
        """Toggle hyperopt controls and disable runtime launch for that mode."""
        self._hyperopt_widget.setVisible(index == 1)
        self._hyperopt_block_lbl.setVisible(index == 1)
        self._update_state_machine()

    def _reset_stat_cards(self) -> None:
        """Reset all stat cards to empty placeholders."""
        self._stat_iter.set_value("0")
        self._stat_profit.set_value("-")
        self._stat_wr.set_value("-")
        self._stat_dd.set_value("-")
        self._stat_sharpe.set_value("-")
        self._stat_score.set_value("-")

    def _update_stat_cards(self) -> None:
        """Update live stat cards from the current loop result."""
        result = self._loop_service.current_result
        if result is None:
            self._reset_stat_cards()
            return

        self._stat_iter.set_value(str(len(result.iterations)))

        best = result.best_iteration
        if best is None or best.summary is None:
            self._stat_profit.set_value("-")
            self._stat_wr.set_value("-")
            self._stat_dd.set_value("-")
            self._stat_sharpe.set_value("-")
            self._stat_score.set_value("-")
            return

        s = best.summary
        profit_color = _C_GREEN if s.total_profit >= 0 else _C_RED
        self._stat_profit.set_value(f"{s.total_profit:+.1f}%", profit_color)
        self._stat_wr.set_value(f"{s.win_rate:.0f}%")
        dd_color = _C_RED if s.max_drawdown > 20 else _C_TEXT
        self._stat_dd.set_value(f"{s.max_drawdown:.1f}%", dd_color)
        self._stat_sharpe.set_value(f"{s.sharpe_ratio:.2f}" if s.sharpe_ratio is not None else "-")
        self._stat_score.set_value(f"{best.score.total:.3f}" if best.score else "-")

    def _build_loop_config(self, strategy: str) -> LoopConfig:
        """Build a LoopConfig from the current UI state."""
        settings = self._settings_state.current_settings
        if not settings or not settings.user_data_path:
            raise ValueError("user_data_path is not configured")
        strategy_py = Path(settings.user_data_path) / "strategies" / f"{strategy}.py"
        detected_timeframe = "5m"  # fallback default
        if strategy_py.exists():
            detected_timeframe = detect_strategy_timeframe(strategy_py)
        
        return LoopConfig(
            strategy=strategy,
            timeframe=detected_timeframe,
            max_iterations=self._max_iter_spin.value(),
            target_profit_pct=self._target_profit_spin.value(),
            target_win_rate=self._target_wr_spin.value(),
            target_max_drawdown=self._target_dd_spin.value(),
            target_min_trades=self._target_trades_spin.value(),
            stop_on_first_profitable=self._stop_on_target_chk.isChecked(),
            date_from=self._date_from_edit.text().strip(),
            date_to=self._date_to_edit.text().strip(),
            oos_split_pct=self._oos_split_spin.value(),
            walk_forward_folds=self._wf_folds_spin.value(),
            stress_fee_multiplier=self._stress_fee_spin.value(),
            stress_slippage_pct=self._stress_slippage_spin.value(),
            stress_profit_target_pct=self._stress_profit_spin.value(),
            consistency_threshold_pct=self._consistency_spin.value(),
            validation_mode=("full" if self._validation_mode_combo.currentIndex() == 0 else "quick"),
            iteration_mode=("rule_based" if self._iteration_mode_combo.currentIndex() == 0 else "hyperopt"),
            hyperopt_epochs=self._hyperopt_epochs_spin.value(),
            hyperopt_spaces=[
                space for space, chk in self._hyperopt_space_checks.items() if chk.isChecked()
            ],
            hyperopt_loss_function=self._hyperopt_loss_combo.currentText(),
            pairs=list(self._selected_pairs),
            ai_advisor_enabled=self._ai_advisor_chk.isChecked(),
        )

    def _validate_loop_inputs(self, strategy: str) -> Optional[str]:
        """Return an error message if the Strategy Lab config is not runnable."""
        if not strategy or strategy.startswith("("):
            return "Please select a strategy first."

        if self._iteration_mode_combo.currentIndex() == 1:
            return (
                "Hyperopt-guided Strategy Lab runtime is not implemented in this pass. "
                "Switch Iteration Mode back to Rule-Based Mutations."
            )

        date_from = self._date_from_edit.text().strip()
        date_to = self._date_to_edit.text().strip()
        if not date_from or not date_to:
            return "Strategy Lab requires both Start Date and End Date."
        if not self._is_valid_date_value(date_from) or not self._is_valid_date_value(date_to):
            return "Dates must use YYYYMMDD format."

        if datetime.strptime(date_from, "%Y%m%d") >= datetime.strptime(date_to, "%Y%m%d"):
            return "Start Date must be earlier than End Date."

        settings = self._settings_state.current_settings
        if not settings or not settings.user_data_path:
            return "user_data_path is not configured in Settings."
        strategy_py = Path(settings.user_data_path) / "strategies" / f"{strategy}.py"
        if not strategy_py.exists():
            return f"Strategy file not found: {strategy_py}"

        return None

    def _clear_history_ui(self) -> None:
        """Remove all iteration rows and reset visible loop state."""
        while self._history_vlay.count() > 0:
            item = self._history_vlay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._empty_history_lbl = QLabel("No iterations yet - start the loop to begin.")
        self._empty_history_lbl.setStyleSheet(
            f"color:{_C_TEXT_DIM};font-size:12px;font-style:italic;padding:16px;"
        )
        self._empty_history_lbl.setAlignment(Qt.AlignCenter)
        self._history_vlay.addWidget(self._empty_history_lbl)
        self._history_vlay.addStretch()
        self._reset_stat_cards()
        self._progress_bar.setValue(0)

    def _reset_iteration_runtime(self) -> None:
        """Clear per-iteration transient state."""
        self._ensure_loop_runtime_state()
        self._current_gate_name = ""
        self._current_gate_timerange = ""
        self._current_gate_export_dir = None
        self._gate_run_started_at = 0.0
        self._current_fold_timeranges = []
        self._current_fold_index = 0
        self._iteration_in_sample_results = None
        self._iteration_oos_results = None
        self._iteration_fold_results = []
        self._iteration_stress_results = None

    def _current_diagnosis_seed(
        self,
        config: LoopConfig,
    ) -> Tuple[BacktestSummary, Optional[object]]:
        """Return the latest usable diagnosis seed for the next iteration.
        
        The diagnosis seed is the baseline performance data used to generate
        suggestions for the next iteration. This must be real backtest data,
        never fabricated dummy values.
        
        Returns:
            Tuple of (BacktestSummary, Optional diagnosis input object)
            
        Raises:
            RuntimeError: If no baseline diagnosis input is available.
        """
        self._ensure_loop_runtime_state()
        if self._latest_diagnosis_input is not None:
            return self._latest_diagnosis_input.in_sample, self._latest_diagnosis_input

        # No baseline exists - this should not happen if _on_start() is working correctly
        raise RuntimeError(
            "No baseline diagnosis input available. "
            "A baseline backtest must be run before starting iterations. "
            "This should have been triggered automatically by _on_start()."
        )

    def _refresh_latest_diagnosis_input(self) -> None:
        """Persist the latest multi-gate diagnosis input for the next iteration."""
        self._ensure_loop_runtime_state()
        if self._iteration_in_sample_results is None:
            return
        self._latest_diagnosis_input = build_diagnosis_input(
            self._iteration_in_sample_results,
            self._iteration_oos_results,
            self._iteration_fold_results or None,
        )

    def _build_gate_export_dir(self, gate_name: str) -> Path:
        """Create a per-gate export directory under `_loop` results."""
        settings = self._settings_state.current_settings
        if not settings or not settings.user_data_path:
            raise ValueError("user_data_path is not configured")
        config = self._loop_service._config
        iteration = self._current_iteration
        suffix = gate_name
        if gate_name == "walk_forward":
            suffix = f"{gate_name}_{self._current_fold_index + 1}"
        ts = time.strftime("%Y%m%d_%H%M%S")
        export_dir = (
            Path(settings.user_data_path) / "backtest_results" / "_loop"
            / f"{config.strategy}_{ts}_iter{iteration.iteration_number}_{suffix}"
        )
        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir

    def _compute_stress_fee_ratio(self, config_path: Path, config: LoopConfig) -> float:
        """Approximate stress by combining configured fee and slippage into `--fee`."""
        base_fee = 0.001
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            raw_fee = payload.get("fee")
            if raw_fee is None and isinstance(payload.get("exchange"), dict):
                raw_fee = payload["exchange"].get("fee")
            if isinstance(raw_fee, (int, float)) and raw_fee >= 0:
                base_fee = float(raw_fee)
        except Exception as exc:
            _log.warning("Falling back to default base fee for stress gate: %s", exc)

        stress_fee = base_fee * config.stress_fee_multiplier
        stress_fee += config.stress_slippage_pct / 100.0
        return round(stress_fee, 6)

    def _start_gate_backtest(
        self,
        gate_name: str,
        timerange: str,
        phase_label: str,
    ) -> None:
        """Launch one gate backtest subprocess and update the indicator/status."""
        self._ensure_loop_runtime_state()
        config = self._loop_service._config
        iteration = self._current_iteration
        if config is None or iteration is None or self._sandbox_dir is None:
            raise RuntimeError("Cannot start gate without an active iteration sandbox")

        settings = self._settings_state.settings_service.load_settings()
        self._current_gate_name = gate_name
        self._current_gate_timerange = timerange
        self._current_gate_export_dir = self._build_gate_export_dir(gate_name)

        from app.core.freqtrade.resolvers.config_resolver import find_config_file_path
        from app.core.freqtrade.runners.backtest_runner import create_backtest_command

        extra_flags = [
            "--strategy-path", str(self._sandbox_dir),
            "--backtest-directory", str(self._current_gate_export_dir),
        ]
        if gate_name == "stress_test":
            config_path = find_config_file_path(Path(settings.user_data_path), strategy_name=config.strategy)
            extra_flags.extend([
                "--fee",
                str(self._compute_stress_fee_ratio(config_path, config)),
            ])

        cmd = create_backtest_command(
            settings=settings,
            strategy_name=config.strategy,
            timeframe=config.timeframe,
            timerange=timerange,
            pairs=config.pairs if config.pairs else None,
            extra_flags=extra_flags,
        )

        self._gate_indicator.set_running(gate_name)
        self._set_status(phase_label)
        self._gate_run_started_at = time.time()

        env = None
        if settings and settings.venv_path:
            env = ProcessService.build_environment(settings.venv_path)

        self._process_service.execute_command(
            cmd.as_list(),
            on_output=self._terminal.append_output,
            on_error=self._terminal.append_error,
            on_finished=self._on_gate_backtest_finished,
            working_directory=cmd.cwd,
            env=env,
        )

    def _parse_current_gate_results(self) -> BacktestResults:
        """Parse the most recent gate artifact from the current export dir."""
        if self._current_gate_export_dir is None:
            raise FileNotFoundError("No gate export directory recorded for parsing")
        return self._improve_service.parse_candidate_run(
            self._current_gate_export_dir,
            self._gate_run_started_at,
        )

    def _finish_iteration(self, iteration: LoopIteration) -> None:
        """Refresh UI after one iteration reaches a terminal state."""
        self._loop_result = self._loop_service.current_result
        self._add_history_row(iteration)
        self._update_stat_cards()
        config = self._loop_service._config
        if config is not None:
            self._progress_bar.setValue(
                int(iteration.iteration_number / max(config.max_iterations, 1) * 100)
            )
        self._reset_iteration_runtime()
        self._current_iteration = None
        QTimer.singleShot(100, self._run_next_iteration)

    def _finalize_successful_iteration(self, last_gate_name: str) -> None:
        """Score and record a fully validated iteration, then continue."""
        if self._current_iteration is None or self._iteration_in_sample_results is None:
            self._finalize_loop()
            return

        iteration = self._current_iteration
        iteration.status = "success"
        iteration.validation_gate_reached = last_gate_name
        iteration.validation_gate_passed = True
        self._refresh_latest_diagnosis_input()

        self._loop_service.record_iteration_result(
            iteration,
            self._iteration_in_sample_results.summary,
            score_input=build_score_input(
                self._iteration_in_sample_results,
                self._iteration_fold_results or None,
                self._iteration_stress_results,
            ),
        )
        self._finish_iteration(iteration)

    def _on_start(self) -> None:
        """Validate config and kick off the first ladder iteration."""
        # Only reset stale session data on a fresh user-initiated start.
        # When called as a baseline-completion restart (_baseline_in_progress is True),
        # _latest_diagnosis_input has just been populated — do NOT wipe it.
        # We also clear _baseline_in_progress here so the flag is always False
        # by the time the rest of this method runs.
        if not getattr(self, '_baseline_in_progress', False):
            self._latest_diagnosis_input = None
        self._baseline_in_progress = False
        self._ensure_loop_runtime_state()
        strategy = self._strategy_combo.currentText().strip()
        error = self._validate_loop_inputs(strategy)
        if error:
            QMessageBox.warning(self, "Strategy Lab", error)
            return

        self._save_preferences()
        settings = self._settings_state.settings_service.load_settings()

        try:
            self._initial_params = self._improve_service.load_baseline_params(
                Path(settings.user_data_path) / "backtest_results" / "_loop_seed",
                strategy,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Strategy Lab", f"Failed to load baseline params: {exc}")
            return

        config = self._build_loop_config(strategy)

        # Check if we're already running baseline to prevent circular calls
        if hasattr(self, '_baseline_in_progress') and self._baseline_in_progress:
            _log.warning("Baseline already in progress, skipping duplicate start")
            return

        # Check if baseline is needed (no previous diagnosis input)
        needs_baseline = self._latest_diagnosis_input is None
        if needs_baseline:
            _log.info("No previous diagnosis input - running baseline backtest")
            self._baseline_in_progress = True
            self._run_baseline_backtest(config, strategy, settings)
            return  # Exit early, baseline completion will trigger loop start

        self._clear_history_ui()
        self._loop_result = None
        self._best_group.setVisible(False)
        self._gate_indicator.reset()
        self._workflow_indicator.reset()
        self._current_stage = "idle"
        self._reset_iteration_runtime()
        if hasattr(self._terminal, "clear_output"):
            self._terminal.clear_output()

        if config.ai_advisor_enabled and self._ai_advisor is not None:
            self._loop_service.set_ai_advisor(self._ai_advisor)
        else:
            self._loop_service.set_ai_advisor(None)

        self._loop_service.set_callbacks(
            on_iteration_complete=self._on_iteration_complete,
            on_loop_complete=self._on_loop_complete_cb,
            on_status=self._on_status_update,
        )

        self._loop_service.start(config, self._initial_params)
        self._run_started_at = time.time()
        self._update_state_machine()
        self._set_status(f"Preparing iteration 1/{config.max_iterations}")
        QTimer.singleShot(50, self._run_next_iteration)

    def _run_baseline_backtest(
        self, config: LoopConfig, strategy: str, settings: AppSettings
    ) -> None:
        """Run a baseline backtest on the in-sample timerange before the first iteration.
        
        This establishes a real performance baseline for the strategy before any
        parameter modifications are made. The baseline results are stored in
        _latest_diagnosis_input and used as the seed for the first iteration.
        
        Args:
            config: Loop configuration
            strategy: Strategy name
            settings: Application settings
        """
        _log.info("Starting baseline backtest for strategy: %s", strategy)
        
        # Generate version_id for baseline (fallback since no versioning system is active)
        version_id = f"{strategy}_baseline_{int(time.time() * 1000)}"
        
        # Prepare sandbox directory for baseline
        try:
            sandbox_dir = self._improve_service.prepare_sandbox(strategy, {}, version_id)
            self._sandbox_dir = sandbox_dir
        except Exception as exc:
            _log.error("Failed to prepare sandbox for baseline: %s", exc)
            QMessageBox.critical(
                self, "Strategy Lab", f"Failed to prepare sandbox for baseline: {exc}"
            )
            self._baseline_in_progress = False
            self._update_state_machine()
            return
        
        # Compute in-sample timerange for baseline
        in_sample_timerange = self._loop_service.compute_in_sample_timerange(config)
        _log.info("Baseline timerange: %s", in_sample_timerange)
        
        # Build backtest command for baseline
        from app.core.freqtrade.runners.backtest_runner import create_backtest_command
        
        export_dir = sandbox_dir / "baseline_export"
        export_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            extra_flags = [
                "--strategy-path", str(sandbox_dir),
                "--backtest-directory", str(export_dir),
            ]
            cmd = create_backtest_command(
                settings=settings,
                strategy_name=strategy,
                timeframe=config.timeframe,
                timerange=in_sample_timerange,
                pairs=list(config.pairs) if config.pairs else None,
                extra_flags=extra_flags,
            )
        except Exception as exc:
            _log.error("Failed to build baseline backtest command: %s", exc)
            QMessageBox.critical(
                self, "Strategy Lab", f"Failed to build baseline backtest command: {exc}"
            )
            self._baseline_in_progress = False
            self._update_state_machine()
            return
        
        # Update UI
        self._set_status("Running baseline backtest...")
        self._progress_bar.setValue(0)
        self._update_state_machine()
        
        # Execute baseline backtest
        _log.info("Executing baseline backtest command: %s", " ".join(cmd.as_list()))
        self._baseline_run_started_at = time.time()
        self._process_service.execute_command(
            cmd.as_list(),
            working_directory=str(cmd.cwd) if cmd.cwd else None,  # Fixed: cwd -> working_directory
            on_output=self._terminal.append_output,
            on_error=self._terminal.append_error,
            on_finished=self._on_baseline_backtest_finished,
        )

    def _on_baseline_backtest_finished(self, exit_code: int) -> None:  # Fixed: removed exit_status parameter
        """Handle baseline backtest completion.
        
        Parses the baseline backtest results, stores them in _latest_diagnosis_input,
        and starts the loop with the real baseline data.
        
        Args:
            exit_code: Process exit code
        """
        # Derive exit status from exit code if needed
        exit_status = "success" if exit_code == 0 else "failed"
        
        if exit_code != 0:
            _log.error("Baseline backtest failed with exit code: %d", exit_code)
            self._set_status(f"Baseline backtest failed: {exit_status}")
            self._baseline_in_progress = False
            self._update_state_machine()
            QMessageBox.critical(
                self,
                "Strategy Lab",
                f"Baseline backtest failed with exit code {exit_code}.\n\n"
                f"Check the terminal output for details.",
            )
            return
        
        _log.info("Baseline backtest completed successfully")
        
        # Parse baseline results
        export_dir = self._sandbox_dir / "baseline_export"
        try:
            results = self._improve_service.parse_candidate_run(export_dir, self._baseline_run_started_at)
            
            if not results or not results.summary:
                raise ValueError("No baseline results found in export directory")
            
            _log.info(
                "Baseline results: %d trades, %.2f%% win rate, %.2f%% profit",
                results.summary.total_trades,
                results.summary.win_rate,
                results.summary.total_profit,
            )
            
            # Create DiagnosisInput from baseline results
            from app.core.models.diagnosis_models import DiagnosisInput
            
            self._latest_diagnosis_input = DiagnosisInput(
                in_sample=results.summary,
                oos_summary=None,
                fold_summaries=None,
                trade_profit_contributions=None,
                drawdown_periods=None,
                atr_spike_periods=None,
            )
            
            # Update UI
            self._set_status("Baseline backtest completed - starting loop")
            _log.info("Baseline established, restarting loop with real data")

            # Keep _baseline_in_progress = True until _on_start runs.
            # _on_start checks this flag to decide whether to wipe
            # _latest_diagnosis_input; clearing it here (before the timer fires)
            # would cause the guard to miss and destroy the baseline result.
            # _on_start clears the flag itself on the restart path.
            QTimer.singleShot(100, self._on_start)
            
        except Exception as exc:
            _log.error("Failed to parse baseline results: %s", exc, exc_info=True)
            self._set_status(f"Failed to parse baseline results: {exc}")
            self._baseline_in_progress = False
            self._update_state_machine()
            QMessageBox.critical(
                self,
                "Strategy Lab",
                f"Failed to parse baseline results: {exc}\n\n"
                f"The baseline backtest may have completed but results could not be read.",
            )

    def _on_stop(self) -> None:
        """Stop the loop and terminate the active process if one is running."""
        self._loop_service.stop()
        self._process_service.stop_process()
        self._set_status("Stopped by user")
        self._update_state_machine()

    def _run_next_iteration(self) -> None:
        """Prepare the next candidate and start Gate 1."""
        self._ensure_loop_runtime_state()
        if not self._loop_service.should_continue():
            self._finalize_loop()
            return

        config = self._loop_service._config
        if config is None:
            self._finalize_loop()
            return

        # Get the diagnosis seed (baseline must exist at this point)
        latest_summary, diagnosis_input = self._current_diagnosis_seed(config)
        result = self._loop_service.prepare_next_iteration(
            latest_summary,
            diagnosis_input=diagnosis_input,
        )
        if result is None:
            self._finalize_loop()
            return

        iteration, suggestions = result
        self._current_iteration = iteration
        self._gate_indicator.reset()
        self._reset_iteration_runtime()
        self._current_iteration = iteration

        # Generate version_id for this iteration (fallback since no versioning system is active)
        version_id = f"{config.strategy}_iter{iteration.iteration_number}_{int(time.time() * 1000)}"

        try:
            self._sandbox_dir = self._improve_service.prepare_sandbox(
                config.strategy,
                iteration.params_after,
                version_id,
            )
            iteration.sandbox_path = self._sandbox_dir

            gate1_timerange = self._loop_service.compute_in_sample_timerange(config)
            if not gate1_timerange:
                raise ValueError("Strategy Lab requires a valid in-sample timerange")

            n = iteration.iteration_number
            m = max(config.max_iterations, 1)
            self._progress_bar.setValue(int(max(0, (n - 1) / m * 100)))
            self._start_gate_backtest(
                "in_sample",
                gate1_timerange,
                f"Gate 1/5 In-Sample - iteration {n}/{m}",
            )
        except Exception as exc:
            _log.error("Failed to start iteration: %s", exc)
            self._loop_service.record_iteration_error(iteration, str(exc))
            self._gate_indicator.set_failed("in_sample", str(exc))
            self._finish_iteration(iteration)

    def _on_gate_backtest_finished(self, exit_code: int) -> None:
        """Handle completion of the currently running gate subprocess."""
        self._ensure_loop_runtime_state()
        iteration = self._current_iteration
        config = self._loop_service._config
        gate_name = self._current_gate_name

        if iteration is None or config is None or not gate_name:
            self._finalize_loop()
            return

        if exit_code != 0:
            message = f"{gate_name} backtest exited with code {exit_code}"
            self._loop_service.record_iteration_error(iteration, message)
            self._gate_indicator.set_failed(gate_name, message)
            self._finish_iteration(iteration)
            return

        try:
            results = self._parse_current_gate_results()
        except Exception as exc:
            message = f"{gate_name} parse error: {exc}"
            self._loop_service.record_iteration_error(iteration, message)
            self._gate_indicator.set_failed(gate_name, message)
            self._finish_iteration(iteration)
            return

        if gate_name == "in_sample":
            self._iteration_in_sample_results = results
            gate1 = self._loop_service.build_in_sample_gate_result(results.summary)
            iteration.gate_results.append(gate1)
            iteration.validation_gate_reached = "in_sample"
            self._gate_indicator.set_passed("in_sample")
            self._refresh_latest_diagnosis_input()

            failures = self._loop_service.evaluate_gate1_hard_filters(
                gate1, config, self._iteration_in_sample_results.trades
            )
            if failures:
                reason = ", ".join(f.failure_reason if hasattr(f, "failure_reason") else f.reason for f in failures)
                self._gate_indicator.set_failed("in_sample", reason)
                self._set_status("Rejected by hard filters after Gate 1")
                self._loop_service.record_hard_filter_rejection(iteration, "in_sample", failures)
                self._finish_iteration(iteration)
                return

            self._start_gate_backtest(
                "out_of_sample",
                self._loop_service.compute_oos_timerange(config),
                f"Gate 2/5 OOS - iteration {iteration.iteration_number}/{config.max_iterations}",
            )
            return

        if gate_name == "out_of_sample":
            self._iteration_oos_results = results
            gate2 = self._loop_service.build_oos_gate_result(
                self._iteration_in_sample_results.summary,
                results.summary,
            )
            iteration.gate_results.append(gate2)
            iteration.validation_gate_reached = "out_of_sample"
            self._refresh_latest_diagnosis_input()

            if not gate2.passed:
                self._gate_indicator.set_failed("out_of_sample", gate2.failure_reason or "")
                self._set_status(gate2.failure_reason or "Gate 2 failed")
                self._loop_service.record_gate_failure(iteration, gate2)
                self._finish_iteration(iteration)
                return

            self._gate_indicator.set_passed("out_of_sample")
            failures = self._loop_service.evaluate_post_gate_hard_filters(gate2, config)
            if failures:
                reason = ", ".join(f.reason for f in failures)
                self._gate_indicator.set_failed("out_of_sample", reason)
                self._set_status("Rejected by hard filters after Gate 2")
                self._loop_service.record_hard_filter_rejection(iteration, "out_of_sample", failures)
                self._finish_iteration(iteration)
                return

            if config.validation_mode == "quick":
                self._finalize_successful_iteration("out_of_sample")
                return

            self._current_fold_timeranges = self._loop_service.compute_walk_forward_timeranges(config)
            if not self._current_fold_timeranges:
                gate3 = self._loop_service.build_walk_forward_gate_result(config, [])
                iteration.gate_results.append(gate3)
                self._gate_indicator.set_failed("walk_forward", gate3.failure_reason or "")
                self._loop_service.record_gate_failure(iteration, gate3)
                self._finish_iteration(iteration)
                return

            self._current_fold_index = 0
            self._start_gate_backtest(
                "walk_forward",
                self._current_fold_timeranges[self._current_fold_index],
                (
                    f"Gate 3/5 Walk-Forward fold 1/{len(self._current_fold_timeranges)} - "
                    f"iteration {iteration.iteration_number}/{config.max_iterations}"
                ),
            )
            return

        if gate_name == "walk_forward":
            self._iteration_fold_results.append(results)
            self._current_fold_index += 1
            total_folds = len(self._current_fold_timeranges)

            if self._current_fold_index < total_folds:
                self._start_gate_backtest(
                    "walk_forward",
                    self._current_fold_timeranges[self._current_fold_index],
                    (
                        f"Gate 3/5 Walk-Forward fold {self._current_fold_index + 1}/{total_folds} - "
                        f"iteration {iteration.iteration_number}/{config.max_iterations}"
                    ),
                )
                return

            fold_summaries = [item.summary for item in self._iteration_fold_results]
            gate3 = self._loop_service.build_walk_forward_gate_result(config, fold_summaries)
            iteration.gate_results.append(gate3)
            iteration.validation_gate_reached = "walk_forward"
            self._refresh_latest_diagnosis_input()

            if not gate3.passed:
                self._gate_indicator.set_failed("walk_forward", gate3.failure_reason or "")
                self._set_status(gate3.failure_reason or "Gate 3 failed")
                self._loop_service.record_gate_failure(iteration, gate3)
                self._finish_iteration(iteration)
                return

            self._gate_indicator.set_passed("walk_forward")
            failures = self._loop_service.evaluate_post_gate_hard_filters(gate3, config)
            if failures:
                reason = ", ".join(f.reason for f in failures)
                self._gate_indicator.set_failed("walk_forward", reason)
                self._set_status("Rejected by hard filters after Gate 3")
                self._loop_service.record_hard_filter_rejection(iteration, "walk_forward", failures)
                self._finish_iteration(iteration)
                return

            self._start_gate_backtest(
                "stress_test",
                self._loop_service.compute_in_sample_timerange(config),
                f"Gate 4/5 Stress - iteration {iteration.iteration_number}/{config.max_iterations}",
            )
            return

        if gate_name == "stress_test":
            self._iteration_stress_results = results
            gate4 = self._loop_service.build_stress_gate_result(config, results.summary)
            iteration.gate_results.append(gate4)
            iteration.validation_gate_reached = "stress_test"

            if not gate4.passed:
                self._gate_indicator.set_failed("stress_test", gate4.failure_reason or "")
                self._set_status(gate4.failure_reason or "Gate 4 failed")
                self._loop_service.record_gate_failure(iteration, gate4)
                self._finish_iteration(iteration)
                return

            self._gate_indicator.set_passed("stress_test")
            self._gate_indicator.set_running("consistency")
            gate5 = self._loop_service.build_consistency_gate_result(
                config,
                [item.summary for item in self._iteration_fold_results],
            )
            iteration.gate_results.append(gate5)
            iteration.validation_gate_reached = "consistency"
            if not gate5.passed:
                self._gate_indicator.set_failed("consistency", gate5.failure_reason or "")
                self._set_status(gate5.failure_reason or "Gate 5 failed")
                self._loop_service.record_gate_failure(iteration, gate5)
                self._finish_iteration(iteration)
                return

            self._gate_indicator.set_passed("consistency")
            self._finalize_successful_iteration("consistency")
            return

        self._loop_service.record_iteration_error(iteration, f"Unknown gate '{gate_name}'")
        self._finish_iteration(iteration)

    def _on_backtest_finished(self, exit_code: int) -> None:
        """Backward-compatible alias for the new gate callback."""
        self._on_gate_backtest_finished(exit_code)
