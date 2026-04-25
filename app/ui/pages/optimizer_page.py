"""Strategy Optimizer page — configure, run, and inspect optimizer sessions.

Three-pane layout:
  Left sidebar  — config panel, parameter table, action buttons, session history
  Center pane   — progress bar, live log (top), trial table (bottom)
  Right sidebar — best result metrics, selected trial metrics, per-trial actions

Thread safety: all UI updates from the background trial loop are marshalled
through bridge signals (never touching Qt widgets directly from a non-main thread).
Pending log lines and trial records are batched and flushed every 500 ms via QTimer.

Architecture boundary: PySide6 imports are allowed here (UI layer).
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import (
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from app.app_state.settings_state import SettingsState
from app.core.models.optimizer_models import (
    OptimizerSession,
    ParamDef,
    ParamType,
    SessionConfig,
    TrialRecord,
    TrialStatus,
)
from app.core.services.backtest_service import BacktestService
from app.core.services.optimizer_session_service import StrategyOptimizerService
from app.core.services.optimizer_store import OptimizerStore
from app.core.services.process_run_manager import ProcessRunManager
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger
from app.ui import theme
from app.ui.dialogs.export_confirm_dialog import ExportConfirmDialog
from app.ui.dialogs.rollback_dialog import RollbackDialog
from app.ui.widgets.trial_table_model import TrialTableModel

_log = get_logger("ui.pages.optimizer_page")

# Score metric options
SCORE_METRICS = [
    ("total_profit_pct", "Total Profit %"),
    ("total_profit_abs", "Total Profit (abs)"),
    ("sharpe_ratio", "Sharpe Ratio"),
    ("profit_factor", "Profit Factor"),
    ("win_rate", "Win Rate"),
]

# Param table column indices
_PCOL_ENABLED  = 0
_PCOL_NAME     = 1
_PCOL_TYPE     = 2
_PCOL_DEFAULT  = 3
_PCOL_MIN      = 4
_PCOL_MAX      = 5
_PCOL_COUNT    = 6

_PARAM_TABLE_TOOLTIP = (
    "Only parameters declared directly in the strategy class body are detected. "
    "Inherited parameters from base classes are not shown."
)


def _section_label(text: str) -> QLabel:
    """Return a styled section header label."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-size: 12px; font-weight: 700; color: {theme.TEXT_SECONDARY};"
        f" text-transform: uppercase; letter-spacing: 0.5px;"
    )
    return lbl


def _metric_row(label: str) -> tuple[QLabel, QLabel]:
    """Return a (label, value) pair for a metric display row."""
    lbl = QLabel(label)
    lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
    val = QLabel("—")
    val.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 600;")
    return lbl, val


def _fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return f"{v:.2f}%"


def _fmt_float(v: Optional[float], decimals: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:.{decimals}f}"


def _fmt_int(v: Optional[int]) -> str:
    if v is None:
        return "—"
    return str(v)

class _CompareDialog(QDialog):
    """Side-by-side metric comparison for two trials."""

    def __init__(self, trial_a: TrialRecord, trial_b: TrialRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Compare Trial #{trial_a.trial_number} vs #{trial_b.trial_number}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.setModal(True)
        self._build(trial_a, trial_b)

    def _build(self, a: TrialRecord, b: TrialRecord) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        title = QLabel(f"Trial #{a.trial_number}  vs  Trial #{b.trial_number}")
        title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        root.addWidget(title)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Metric", f"Trial #{a.trial_number}", f"Trial #{b.trial_number}", "Delta"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)

        rows = []
        if a.metrics and b.metrics:
            am, bm = a.metrics, b.metrics
            rows = [
                ("Profit %",       am.total_profit_pct,  bm.total_profit_pct,  True),
                ("Profit (abs)",   am.total_profit_abs,  bm.total_profit_abs,  True),
                ("Win Rate",       am.win_rate,           bm.win_rate,           True),
                ("Max DD %",       am.max_drawdown_pct,  bm.max_drawdown_pct,  False),
                ("Total Trades",   am.total_trades,       bm.total_trades,       None),
                ("Profit Factor",  am.profit_factor,      bm.profit_factor,      True),
                ("Sharpe Ratio",   am.sharpe_ratio,       bm.sharpe_ratio,       True),
                ("Final Balance",  am.final_balance,      bm.final_balance,      True),
            ]
        rows.append(("Score", a.score, b.score, True))

        for metric, va, vb, higher_is_better in rows:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(metric))

            def _fmt(v: Any) -> str:
                if v is None:
                    return "—"
                if isinstance(v, int):
                    return str(v)
                return f"{v:.4g}"

            item_a = QTableWidgetItem(_fmt(va))
            item_b = QTableWidgetItem(_fmt(vb))

            # Delta
            delta_text = "—"
            delta_color = theme.TEXT_PRIMARY
            if va is not None and vb is not None:
                try:
                    delta = float(vb) - float(va)
                    delta_text = f"{delta:+.4g}"
                    if higher_is_better is True:
                        delta_color = theme.GREEN if delta > 0 else (theme.RED if delta < 0 else theme.TEXT_PRIMARY)
                    elif higher_is_better is False:
                        delta_color = theme.RED if delta > 0 else (theme.GREEN if delta < 0 else theme.TEXT_PRIMARY)
                except (TypeError, ValueError):
                    pass

            item_delta = QTableWidgetItem(delta_text)
            item_delta.setForeground(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor(delta_color))

            table.setItem(row, 1, item_a)
            table.setItem(row, 2, item_b)
            table.setItem(row, 3, item_delta)

        root.addWidget(table)

        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)


class OptimizerPage(QWidget):
    """Strategy Optimizer page — three-pane layout with live trial updates."""

    # ── Bridge signals (background thread → Qt main thread) ──────────────────
    _sig_log_line    = Signal(str)
    _sig_trial_done  = Signal(object)   # TrialRecord
    _sig_session_done = Signal(object)  # OptimizerSession
    _sig_trial_start = Signal(int, dict)

    def __init__(
        self,
        settings_state: SettingsState,
        process_manager: ProcessRunManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = settings_state
        self._process_manager = process_manager

        # Services
        self._settings_svc = settings_state.settings_service
        self._backtest_svc = BacktestService(self._settings_svc)
        self._service = StrategyOptimizerService(
            settings_service=self._settings_svc,
            backtest_service=self._backtest_svc,
        )
        self._store = OptimizerStore(self._settings_svc)

        # Session state
        self._active_session: Optional[OptimizerSession] = None
        self._session_start_time: Optional[float] = None
        self._running = False
        self._param_defs: List[ParamDef] = []

        # Batched update buffers (9.9)
        self._pending_log_lines: list[str] = []
        self._pending_trials: list[TrialRecord] = []
        self._current_best_trial_number: int = 0

        # Selected trial for right sidebar
        self._selected_trial: Optional[TrialRecord] = None

        # Build UI
        self._build()

        # Wire bridge signals to slots (always runs on main thread)
        self._sig_log_line.connect(self._on_log_line)
        self._sig_trial_done.connect(self._on_trial_done)
        self._sig_session_done.connect(self._on_session_done)
        self._sig_trial_start.connect(self._on_trial_start)

        # Flush timer (9.9)
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(500)
        self._flush_timer.timeout.connect(self._flush_pending_updates)
        self._flush_timer.start()

        # Elapsed timer
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._update_elapsed)

        # Load initial data
        self._load_strategies()
        self._sync_from_backtest()
        self._load_history()
