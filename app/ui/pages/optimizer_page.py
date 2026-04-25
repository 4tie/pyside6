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

import json
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
from PySide6.QtGui import QAction, QDesktopServices, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QCheckBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
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
    QToolButton,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from app.app_state.settings_state import SettingsState
from app.core.models.settings_models import AppSettings
from app.core.models.optimizer_models import (
    OptimizerSession,
    ParamDef,
    ParamType,
    SessionConfig,
    TrialRecord,
    TrialStatus,
)
from app.core.services.backtest_service import BacktestService
from app.core.services.optimizer_search_space_service import OptimizerSearchSpaceService
from app.core.services.optimizer_session_service import StrategyOptimizerService
from app.core.services.optimizer_store import OptimizerStore
from app.core.services.process_run_manager import ProcessRunManager
from app.core.services.rollback_service import RollbackService
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger
from app.ui import theme
from app.ui.dialogs.export_confirm_dialog import ExportConfirmDialog
from app.ui.dialogs.rollback_dialog import RollbackDialog
from app.ui.widgets.trial_table_model import TRIAL_RATING_COLUMN, TrialTableModel

_log = get_logger("ui.pages.optimizer_page")

# Score options
SCORE_OPTIONS = [
    ("composite", "Composite Score"),
    ("total_profit_pct", "Total Profit %"),
    ("total_profit_abs", "Total Profit (abs)"),
    ("sharpe_ratio", "Sharpe Ratio"),
    ("profit_factor", "Profit Factor"),
    ("win_rate", "Win Rate"),
]

TIMEFRAME_OPTIONS = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"]

# Param table column indices
_PCOL_ENABLED  = 0
_PCOL_NAME     = 1
_PCOL_TYPE     = 2
_PCOL_SPACE    = 3
_PCOL_DEFAULT  = 4
_PCOL_MIN      = 5
_PCOL_MAX      = 6
_PCOL_COUNT    = 7

_PARAM_TABLE_TOOLTIP = (
    "Buy/sell parameters come from declarations in the strategy class body. "
    "ROI, stoploss, and trailing spaces are generated from strategy metadata "
    "and live JSON when available."
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
        self._settings_svc = getattr(settings_state, "settings_service", SettingsService())
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
        self._loading_preferences = False

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

        self._prefs_save_timer = QTimer(self)
        self._prefs_save_timer.setSingleShot(True)
        self._prefs_save_timer.setInterval(500)
        self._prefs_save_timer.timeout.connect(self._save_preferences)

        # Load initial data
        self._load_strategies()
        self._restore_preferences()
        self._connect_preferences_autosave()
        self._load_history()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 10)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Strategy Optimizer")
        title.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()

        self._left_panel_toggle = self._panel_toggle(
            "Config",
            "Show or hide optimizer configuration",
        )
        self._left_panel_toggle.toggled.connect(
            lambda checked: self._set_side_panel_visible("left", checked)
        )
        header.addWidget(self._left_panel_toggle)

        self._right_panel_toggle = self._panel_toggle(
            "Details",
            "Show or hide best and selected trial details",
        )
        self._right_panel_toggle.toggled.connect(
            lambda checked: self._set_side_panel_visible("right", checked)
        )
        header.addWidget(self._right_panel_toggle)

        self._start_btn = QPushButton("Start Optimizer")
        self._start_btn.setObjectName("primary")
        self._start_btn.clicked.connect(self._start_optimizer)
        header.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("danger")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_optimizer)
        header.addWidget(self._stop_btn)
        root.addLayout(header)

        self._warning_lbl = QLabel("")
        self._warning_lbl.setVisible(False)
        self._warning_lbl.setWordWrap(True)
        self._warning_lbl.setStyleSheet(
            f"color: {theme.YELLOW}; background: {theme.BG_ELEVATED}; "
            f"border: 1px solid {theme.YELLOW}; border-radius: 6px; padding: 8px;"
        )
        root.addWidget(self._warning_lbl)

        self._main_splitter = QSplitter(Qt.Horizontal)
        self._main_splitter.setHandleWidth(1)
        self._main_splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {theme.BG_BORDER}; }}"
        )

        self._left_sidebar = self._build_left_sidebar()
        self._center_pane = self._build_center_pane()
        self._right_sidebar = self._build_right_sidebar()
        self._main_splitter.addWidget(self._left_sidebar)
        self._main_splitter.addWidget(self._center_pane)
        self._main_splitter.addWidget(self._right_sidebar)
        self._main_splitter.setCollapsible(0, True)
        self._main_splitter.setCollapsible(1, False)
        self._main_splitter.setCollapsible(2, True)
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setStretchFactor(2, 0)
        self._main_splitter.setSizes([410, 980, 360])
        self._expanded_splitter_sizes = [410, 980, 360]
        root.addWidget(self._main_splitter, 1)

    def _panel_toggle(self, text: str, tooltip: str) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setCheckable(True)
        btn.setChecked(True)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(
            f"QToolButton {{ color: {theme.TEXT_SECONDARY}; background: {theme.BG_ELEVATED}; "
            f"border: 1px solid {theme.BG_BORDER}; border-radius: 6px; padding: 5px 9px; }}"
            f"QToolButton:checked {{ color: {theme.TEXT_PRIMARY}; border-color: {theme.ACCENT}; }}"
        )
        return btn

    def _set_side_panel_visible(self, side: str, visible: bool) -> None:
        if not hasattr(self, "_main_splitter"):
            return

        sizes = self._main_splitter.sizes()
        if any(sizes):
            self._expanded_splitter_sizes = sizes

        panel_index = 0 if side == "left" else 2
        panel = self._left_sidebar if side == "left" else self._right_sidebar
        panel.setVisible(visible)

        if visible:
            restored = list(self._expanded_splitter_sizes)
            if restored[panel_index] <= 0:
                restored[panel_index] = 410 if side == "left" else 360
            if restored[1] <= 0:
                restored[1] = 680
            self._main_splitter.setSizes(restored)
            return

        collapsed = self._main_splitter.sizes()
        reclaimed = collapsed[panel_index]
        collapsed[1] = max(collapsed[1] + reclaimed, 360)
        collapsed[panel_index] = 0
        self._main_splitter.setSizes(collapsed)

    def _panel(self, min_width: int = 260, max_width: int | None = None) -> QFrame:
        panel = QFrame()
        panel.setObjectName("optimizerPanel")
        panel.setStyleSheet(
            f"QFrame#optimizerPanel {{ background: {theme.BG_SURFACE}; border: 1px solid {theme.BG_BORDER}; "
            "border-radius: 8px; }"
        )
        panel.setMinimumWidth(min_width)
        if max_width:
            panel.setMaximumWidth(max_width)
        return panel

    def _scroll_panel(self, panel: QFrame, *, min_width: int, max_width: int | None = None) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(min_width)
        if max_width:
            scroll.setMaximumWidth(max_width)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        return scroll

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
        return lbl

    def _build_left_sidebar(self) -> QWidget:
        panel = self._panel(390)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(_section_label("Configuration"))
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(7)

        self._strategy_combo = QComboBox()
        self._strategy_combo.currentTextChanged.connect(self._on_strategy_changed)
        form.addRow(self._label("Strategy"), self._strategy_combo)

        self._timeframe_combo = QComboBox()
        self._timeframe_combo.setEditable(True)
        self._timeframe_combo.addItems(TIMEFRAME_OPTIONS)
        self._timeframe_combo.setCurrentText("5m")
        form.addRow(self._label("Timeframe"), self._timeframe_combo)

        self._timerange_edit = QLineEdit()
        self._timerange_edit.setReadOnly(True)
        form.addRow(self._label("Timerange"), self._timerange_edit)

        self._pairs_edit = QLineEdit()
        self._pairs_edit.setPlaceholderText("BTC/USDT,ETH/USDT")
        pairs_row = QWidget()
        pairs_layout = QHBoxLayout(pairs_row)
        pairs_layout.setContentsMargins(0, 0, 0, 0)
        pairs_layout.setSpacing(6)
        pairs_layout.addWidget(self._pairs_edit, 1)
        self._select_pairs_btn = QPushButton("Select")
        self._select_pairs_btn.setToolTip("Edit optimizer pairs")
        self._select_pairs_btn.setFixedWidth(68)
        self._select_pairs_btn.clicked.connect(self._select_pairs)
        pairs_layout.addWidget(self._select_pairs_btn)
        form.addRow(self._label("Pairs"), pairs_row)

        self._wallet_spin = QDoubleSpinBox()
        self._wallet_spin.setRange(1, 1_000_000)
        self._wallet_spin.setSuffix(" USDT")
        form.addRow(self._label("Wallet"), self._wallet_spin)

        self._trades_spin = QSpinBox()
        self._trades_spin.setRange(1, 100)
        form.addRow(self._label("Max Trades"), self._trades_spin)

        self._trials_spin = QSpinBox()
        self._trials_spin.setRange(1, 1000)
        self._trials_spin.setValue(50)
        form.addRow(self._label("Trials"), self._trials_spin)

        self._score_combo = QComboBox()
        for key, label in SCORE_OPTIONS:
            self._score_combo.addItem(label, key)
        form.addRow(self._label("Score"), self._score_combo)

        self._target_trades_spin = QSpinBox()
        self._target_trades_spin.setRange(1, 100_000)
        self._target_trades_spin.setValue(100)
        form.addRow(self._label("Target Trades"), self._target_trades_spin)

        self._target_profit_spin = QDoubleSpinBox()
        self._target_profit_spin.setRange(0.01, 10_000.0)
        self._target_profit_spin.setDecimals(2)
        self._target_profit_spin.setSuffix("%")
        self._target_profit_spin.setValue(50.0)
        form.addRow(self._label("Target Profit"), self._target_profit_spin)

        self._max_drawdown_spin = QDoubleSpinBox()
        self._max_drawdown_spin.setRange(0.01, 100.0)
        self._max_drawdown_spin.setDecimals(2)
        self._max_drawdown_spin.setSuffix("%")
        self._max_drawdown_spin.setValue(25.0)
        form.addRow(self._label("Max Drawdown"), self._max_drawdown_spin)

        self._target_romad_spin = QDoubleSpinBox()
        self._target_romad_spin.setRange(0.01, 100.0)
        self._target_romad_spin.setDecimals(2)
        self._target_romad_spin.setValue(2.0)
        form.addRow(self._label("Target RoMAD"), self._target_romad_spin)
        layout.addLayout(form)
        for widget in (
            self._strategy_combo,
            self._timeframe_combo,
            self._timerange_edit,
            self._pairs_edit,
            self._select_pairs_btn,
            self._wallet_spin,
            self._trades_spin,
            self._trials_spin,
            self._score_combo,
            self._target_trades_spin,
            self._target_profit_spin,
            self._max_drawdown_spin,
            self._target_romad_spin,
        ):
            widget.setMinimumWidth(0)
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout.addWidget(_section_label("Parameters"))
        self._param_model = QStandardItemModel(0, _PCOL_COUNT, self)
        self._param_model.setHorizontalHeaderLabels(["On", "Name", "Type", "Space", "Default", "Min", "Max"])
        self._param_model.itemChanged.connect(self._on_param_item_changed)
        self._param_table = QTableView()
        self._param_table.setToolTip(_PARAM_TABLE_TOOLTIP)
        self._param_table.setModel(self._param_model)
        param_header = self._param_table.horizontalHeader()
        param_header.setMinimumSectionSize(24)
        param_header.setSectionResizeMode(QHeaderView.Fixed)
        param_header.resizeSection(_PCOL_ENABLED, 36)
        param_header.resizeSection(_PCOL_NAME, 55)
        param_header.resizeSection(_PCOL_TYPE, 44)
        param_header.resizeSection(_PCOL_SPACE, 58)
        param_header.resizeSection(_PCOL_DEFAULT, 70)
        param_header.resizeSection(_PCOL_MIN, 44)
        param_header.resizeSection(_PCOL_MAX, 48)
        self._param_table.verticalHeader().setVisible(False)
        self._param_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._param_table.setWordWrap(False)
        self._param_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._param_table.setFixedHeight(165)
        layout.addWidget(self._param_table, 1)

        layout.addWidget(_section_label("History"))
        self._history_table = QTableWidget(0, 5)
        self._history_table.setHorizontalHeaderLabels(["Strategy", "Started", "Trials", "Best", "Status"])
        history_header = self._history_table.horizontalHeader()
        history_header.setMinimumSectionSize(36)
        history_header.setSectionResizeMode(QHeaderView.Fixed)
        history_header.resizeSection(0, 82)
        history_header.resizeSection(1, 88)
        history_header.resizeSection(2, 52)
        history_header.resizeSection(3, 58)
        history_header.resizeSection(4, 84)
        self._history_table.verticalHeader().setVisible(False)
        self._history_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._history_table.setWordWrap(False)
        self._history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._history_table.cellDoubleClicked.connect(self._load_history_session)
        self._history_table.setFixedHeight(112)
        layout.addWidget(self._history_table)

        delete_btn = QPushButton("Delete Session")
        delete_btn.clicked.connect(self._delete_selected_history)
        layout.addWidget(delete_btn)
        return self._scroll_panel(panel, min_width=390, max_width=440)

    def _build_center_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        top.addWidget(self._progress, 1)
        self._elapsed_lbl = QLabel("Elapsed: 00:00")
        self._eta_lbl = QLabel("ETA: --:--")
        for lbl in (self._elapsed_lbl, self._eta_lbl):
            lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
            top.addWidget(lbl)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(1)
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(5000)
        self._log_view.setStyleSheet(f"font-family: {theme.FONT_MONO}; font-size: 11px;")
        splitter.addWidget(self._log_view)

        self._trial_model = TrialTableModel(self)
        self._trial_proxy = QSortFilterProxyModel(self)
        self._trial_proxy.setSourceModel(self._trial_model)
        self._trial_table = QTableView()
        self._trial_table.setModel(self._trial_proxy)
        self._trial_table.setSortingEnabled(True)
        self._trial_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._trial_table.horizontalHeader().setSectionResizeMode(
            TRIAL_RATING_COLUMN,
            QHeaderView.ResizeToContents,
        )
        self._trial_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._trial_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._trial_table.clicked.connect(self._on_trial_clicked)
        splitter.addWidget(self._trial_table)
        splitter.setSizes([360, 300])
        layout.addWidget(splitter, 1)
        return pane

    def _build_right_sidebar(self) -> QWidget:
        panel = self._panel(340)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(_section_label("Best Result"))
        self._best_labels = self._metric_group(layout)
        self._export_btn = QPushButton("Export Best")
        self._export_btn.clicked.connect(self._export_best)
        self._rollback_btn = QPushButton("Rollback")
        self._rollback_btn.clicked.connect(self._rollback)
        best_actions = QHBoxLayout()
        best_actions.setSpacing(8)
        best_actions.addWidget(self._export_btn)
        best_actions.addWidget(self._rollback_btn)
        layout.addLayout(best_actions)

        layout.addWidget(_section_label("Selected Trial"))
        self._selected_labels = self._metric_group(layout)
        layout.addWidget(_section_label("Score Breakdown"))
        self._score_breakdown_view = QPlainTextEdit()
        self._score_breakdown_view.setReadOnly(True)
        self._score_breakdown_view.setFixedHeight(78)
        self._score_breakdown_view.setStyleSheet(
            f"font-family: {theme.FONT_MONO}; font-size: 10px;"
        )
        layout.addWidget(self._score_breakdown_view)

        self._set_best_btn = QPushButton("Set as Best")
        self._set_best_btn.clicked.connect(self._set_selected_as_best)
        self._open_log_btn = QPushButton("Open Log")
        self._open_log_btn.clicked.connect(self._open_selected_log)
        self._open_result_btn = QPushButton("Open Result File")
        self._open_result_btn.clicked.connect(self._open_selected_result)
        self._compare_btn = QPushButton("Compare")
        self._compare_btn.clicked.connect(self._compare_selected)

        self._apply_btn = QPushButton("Apply")
        apply_menu = QMenu(self._apply_btn)
        self._apply_existing_action = QAction("Apply to strategy", self)
        self._apply_existing_action.triggered.connect(self._apply_selected_to_strategy)
        self._apply_new_action = QAction("Apply new-strategy", self)
        self._apply_new_action.triggered.connect(self._apply_selected_as_new_strategy)
        apply_menu.addAction(self._apply_existing_action)
        apply_menu.addAction(self._apply_new_action)
        self._apply_btn.setMenu(apply_menu)

        primary_actions = QHBoxLayout()
        primary_actions.setSpacing(8)
        primary_actions.addWidget(self._set_best_btn)
        primary_actions.addWidget(self._compare_btn)
        layout.addLayout(primary_actions)

        file_actions = QHBoxLayout()
        file_actions.setSpacing(8)
        file_actions.addWidget(self._open_log_btn)
        file_actions.addWidget(self._open_result_btn)
        layout.addLayout(file_actions)
        layout.addWidget(self._apply_btn)

        layout.addWidget(_section_label("Selected Trial Changes"))
        self._diff_status_lbl = QLabel("Select a successful trial to preview changes.")
        self._diff_status_lbl.setWordWrap(True)
        self._diff_status_lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(self._diff_status_lbl)

        self._param_diff_table = QTableWidget(0, 3)
        self._param_diff_table.setHorizontalHeaderLabels(["Key", "Current", "Selected"])
        self._param_diff_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._param_diff_table.verticalHeader().setVisible(False)
        self._param_diff_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._param_diff_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._param_diff_table.setFixedHeight(120)
        layout.addWidget(self._param_diff_table)

        self._strategy_diff_view = QPlainTextEdit()
        self._strategy_diff_view.setReadOnly(True)
        self._strategy_diff_view.setFixedHeight(135)
        self._strategy_diff_view.setStyleSheet(
            f"font-family: {theme.FONT_MONO}; font-size: 10px;"
        )
        layout.addWidget(self._strategy_diff_view)

        return self._scroll_panel(panel, min_width=340, max_width=390)

    def _metric_group(self, parent_layout: QVBoxLayout) -> dict[str, QLabel]:
        labels: dict[str, QLabel] = {}
        for key, label in [
            ("profit", "Profit %"),
            ("abs", "Profit abs"),
            ("win", "Win rate"),
            ("dd", "Max DD %"),
            ("trades", "Trades"),
            ("pf", "Profit factor"),
            ("sharpe", "Sharpe"),
            ("score", "Score"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(8)
            left, right = _metric_row(label)
            left.setMinimumWidth(100)
            right.setMinimumWidth(74)
            right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(left)
            row.addStretch()
            row.addWidget(right)
            parent_layout.addLayout(row)
            labels[key] = right
        return labels

    def _load_strategies(self) -> None:
        try:
            strategies = self._backtest_svc.get_available_strategies()
            self._strategy_combo.blockSignals(True)
            self._strategy_combo.clear()
            self._strategy_combo.addItems(strategies)
            settings = self._settings_svc.load_settings()
            preferred = (
                settings.optimizer_preferences.last_strategy
                or settings.backtest_preferences.last_strategy
            )
            if preferred:
                idx = self._strategy_combo.findText(preferred)
                if idx >= 0:
                    self._strategy_combo.setCurrentIndex(idx)
            self._strategy_combo.blockSignals(False)
            self._on_strategy_changed(self._strategy_combo.currentText())
        except Exception as exc:
            _log.warning("Could not load optimizer strategies: %s", exc)

    def _restore_preferences(self) -> None:
        current = getattr(self._state, "current_settings", None)
        settings = current if isinstance(current, AppSettings) else self._settings_svc.load_settings()
        self._state.current_settings = settings
        optimizer_prefs = settings.optimizer_preferences
        self._loading_preferences = True
        if optimizer_prefs.last_strategy:
            idx = self._strategy_combo.findText(optimizer_prefs.last_strategy)
            if idx >= 0:
                self._strategy_combo.setCurrentIndex(idx)
        self._timeframe_combo.setCurrentText(optimizer_prefs.default_timeframe or "5m")
        self._timerange_edit.setText(optimizer_prefs.default_timerange or "")
        self._pairs_edit.setText(optimizer_prefs.default_pairs or "")
        self._wallet_spin.setValue(optimizer_prefs.dry_run_wallet)
        self._trades_spin.setValue(optimizer_prefs.max_open_trades)
        self._trials_spin.setValue(optimizer_prefs.total_trials)
        score_key = optimizer_prefs.score_metric or "composite"
        score_idx = self._score_combo.findData(score_key)
        self._score_combo.setCurrentIndex(max(0, score_idx))
        self._target_trades_spin.setValue(optimizer_prefs.target_min_trades)
        self._target_profit_spin.setValue(optimizer_prefs.target_profit_pct)
        self._max_drawdown_spin.setValue(optimizer_prefs.max_drawdown_limit)
        self._target_romad_spin.setValue(optimizer_prefs.target_romad)
        self._loading_preferences = False
        has_config = bool(optimizer_prefs.last_strategy or optimizer_prefs.default_pairs or settings.user_data_path)
        self._warning_lbl.setVisible(not has_config)
        self._warning_lbl.setText("Optimizer preferences look empty. Configure this tab before starting.")

    def _connect_preferences_autosave(self) -> None:
        self._strategy_combo.currentTextChanged.connect(self._schedule_preferences_save)
        self._timeframe_combo.currentTextChanged.connect(self._schedule_preferences_save)
        self._timerange_edit.textChanged.connect(self._schedule_preferences_save)
        self._pairs_edit.textChanged.connect(self._schedule_preferences_save)
        self._wallet_spin.valueChanged.connect(self._schedule_preferences_save)
        self._trades_spin.valueChanged.connect(self._schedule_preferences_save)
        self._trials_spin.valueChanged.connect(self._schedule_preferences_save)
        self._score_combo.currentIndexChanged.connect(self._schedule_preferences_save)
        self._target_trades_spin.valueChanged.connect(self._schedule_preferences_save)
        self._target_profit_spin.valueChanged.connect(self._schedule_preferences_save)
        self._max_drawdown_spin.valueChanged.connect(self._schedule_preferences_save)
        self._target_romad_spin.valueChanged.connect(self._schedule_preferences_save)

    def _schedule_preferences_save(self, *_args) -> None:
        if self._loading_preferences:
            return
        self._prefs_save_timer.start()

    def _save_preferences(self) -> None:
        score_key = self._score_combo.currentData() or "composite"
        try:
            self._state.update_preferences(
                "optimizer_preferences",
                last_strategy=self._strategy_combo.currentText().strip(),
                default_timeframe=self._timeframe_combo.currentText().strip(),
                default_timerange=self._timerange_edit.text().strip(),
                default_pairs=self._pairs_edit.text().strip(),
                dry_run_wallet=self._wallet_spin.value(),
                max_open_trades=self._trades_spin.value(),
                total_trials=self._trials_spin.value(),
                score_metric=score_key,
                score_mode="composite" if score_key == "composite" else "single_metric",
                target_min_trades=self._target_trades_spin.value(),
                target_profit_pct=self._target_profit_spin.value(),
                max_drawdown_limit=self._max_drawdown_spin.value(),
                target_romad=self._target_romad_spin.value(),
            )
        except Exception as exc:
            _log.warning("Could not save optimizer preferences: %s", exc)

    def _select_pairs(self) -> None:
        current = self._pairs_edit.text().strip()
        try:
            settings = self._settings_svc.load_settings()
            favorites = list(getattr(settings, "favorite_pairs", []) or [])
            if not favorites:
                favorites = list(getattr(settings.backtest_preferences, "paired_favorites", []) or [])
        except Exception as exc:
            _log.warning("Could not load optimizer pair favorites: %s", exc)
            favorites = []

        seed_pairs = current or ",".join(favorites)
        text, accepted = QInputDialog.getText(
            self,
            "Select Optimizer Pairs",
            "Pairs, comma-separated:",
            QLineEdit.Normal,
            seed_pairs,
        )
        if not accepted:
            return
        pairs = [pair.strip() for pair in text.split(",") if pair.strip()]
        self._pairs_edit.setText(",".join(dict.fromkeys(pairs)))

    def _on_strategy_changed(self, strategy_name: str) -> None:
        self._param_defs = []
        self._param_model.blockSignals(True)
        self._param_model.removeRows(0, self._param_model.rowCount())
        self._param_model.blockSignals(False)
        if not strategy_name:
            return
        settings = self._settings_svc.load_settings()
        if not settings.user_data_path:
            return
        strategies_dir = Path(settings.user_data_path).expanduser() / "strategies"
        path = strategies_dir / f"{strategy_name}.py"
        json_path = strategies_dir / f"{strategy_name}.json"
        params, defs = OptimizerSearchSpaceService.build_search_space_from_files(path, json_path)
        self._param_defs = defs
        self._strategy_class = params.strategy_class
        if params.timeframe:
            self._timeframe_combo.setCurrentText(params.timeframe)
        self._populate_param_table(defs)

    def _populate_param_table(self, defs: list[ParamDef]) -> None:
        self._param_model.blockSignals(True)
        self._param_model.removeRows(0, self._param_model.rowCount())
        for param in defs:
            enabled = QStandardItem()
            enabled.setCheckable(True)
            enabled.setCheckState(Qt.Checked if param.enabled else Qt.Unchecked)
            row = [
                enabled,
                QStandardItem(param.name),
                QStandardItem(param.param_type.value),
                QStandardItem(param.space),
                QStandardItem(str(param.default)),
                QStandardItem("" if param.low is None else str(param.low)),
                QStandardItem("" if param.high is None else str(param.high)),
            ]
            for idx, item in enumerate(row):
                if idx not in (_PCOL_ENABLED, _PCOL_MIN, _PCOL_MAX):
                    item.setEditable(False)
            self._param_model.appendRow(row)
        self._param_model.blockSignals(False)

    def _on_param_item_changed(self, item: QStandardItem) -> None:
        if item.column() not in (_PCOL_ENABLED, _PCOL_MIN, _PCOL_MAX):
            return
        row = item.row()
        if not (0 <= row < len(self._param_defs)):
            return
        param = self._param_defs[row]
        enabled_item = self._param_model.item(row, _PCOL_ENABLED)
        low_text = self._param_model.item(row, _PCOL_MIN).text().strip()
        high_text = self._param_model.item(row, _PCOL_MAX).text().strip()
        low = self._to_float(low_text)
        high = self._to_float(high_text)
        if low is not None and high is not None and low >= high:
            item.setBackground(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor(theme.RED))
            return
        item.setBackground(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor("transparent"))
        self._param_defs[row] = param.model_copy(
            update={
                "enabled": enabled_item.checkState() == Qt.Checked,
                "low": low,
                "high": high,
            }
        )

    @staticmethod
    def _to_float(text: str) -> Optional[float]:
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _build_config(self) -> SessionConfig:
        strategy = self._strategy_combo.currentText().strip()
        if not strategy:
            raise ValueError("Select a strategy before starting.")
        pairs = [p.strip() for p in self._pairs_edit.text().split(",") if p.strip()]
        score_key = self._score_combo.currentData() or "composite"
        score_mode = "composite" if score_key == "composite" else "single_metric"
        param_errors = OptimizerSearchSpaceService.validate_param_defs(self._param_defs)
        if param_errors:
            shown = "\n".join(param_errors[:8])
            if len(param_errors) > 8:
                shown += f"\n... and {len(param_errors) - 8} more."
            raise ValueError(f"Invalid optimizer parameters:\n{shown}")
        return SessionConfig(
            strategy_name=strategy,
            strategy_class=getattr(self, "_strategy_class", strategy),
            pairs=pairs,
            timeframe=self._timeframe_combo.currentText().strip() or "5m",
            timerange=self._timerange_edit.text().strip() or None,
            dry_run_wallet=self._wallet_spin.value(),
            max_open_trades=self._trades_spin.value(),
            total_trials=self._trials_spin.value(),
            score_metric=score_key,
            score_mode=score_mode,
            target_min_trades=self._target_trades_spin.value(),
            target_profit_pct=self._target_profit_spin.value(),
            max_drawdown_limit=self._max_drawdown_spin.value(),
            target_romad=self._target_romad_spin.value(),
            param_defs=self._param_defs,
        )

    def _start_optimizer(self) -> None:
        if self._running:
            return
        try:
            config = self._build_config()
            session = self._service.create_session(config)
            self._save_optimizer_preferences(config)
        except Exception as exc:
            QMessageBox.warning(self, "Optimizer", str(exc))
            return
        self._active_session = session
        self._session_start_time = time.monotonic()
        self._running = True
        self._current_best_trial_number = 0
        self._selected_trial = None
        self._trial_model.clear()
        self._log_view.clear()
        self._clear_selected_trial_diff("Select a successful trial to preview changes.")
        self._progress.setRange(0, config.total_trials)
        self._progress.setValue(0)
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._elapsed_timer.start()
        self._service.run_session_async(
            session,
            on_trial_start=lambda n, p: self._sig_trial_start.emit(n, p),
            on_trial_complete=lambda r: self._sig_trial_done.emit(r),
            on_session_complete=lambda s: self._sig_session_done.emit(s),
            on_log_line=lambda line: self._sig_log_line.emit(line),
        )

    def _stop_optimizer(self) -> None:
        self._service.stop_session()
        self._stop_btn.setEnabled(False)
        self._append_log("Stop requested.")

    @Slot(str)
    def _on_log_line(self, line: str) -> None:
        self._pending_log_lines.append(line)

    @Slot(object)
    def _on_trial_done(self, record: TrialRecord) -> None:
        self._pending_trials.append(record)

    @Slot(object)
    def _on_session_done(self, session: OptimizerSession) -> None:
        self._active_session = session
        self._running = False
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._elapsed_timer.stop()
        self._append_log(f"Session {session.status.value}: {session.trials_completed} trial(s).")
        self._load_history()

    @Slot(int, dict)
    def _on_trial_start(self, trial_number: int, params: dict) -> None:
        self._append_log(f"\n=== Trial #{trial_number}: {params} ===")

    def _flush_pending_updates(self) -> None:
        if self._pending_log_lines:
            lines = self._pending_log_lines[:]
            self._pending_log_lines.clear()
            self._append_log("\n".join(lines))
        if self._pending_trials:
            trials = self._pending_trials[:]
            self._pending_trials.clear()
            for record in trials:
                old_best = self._current_best_trial_number
                self._trial_model.append_trial(record)
                if record.is_best:
                    self._current_best_trial_number = record.trial_number
                    self._trial_model.update_best(old_best, record.trial_number)
                    self._update_metric_labels(self._best_labels, record)
                if self._active_session:
                    self._progress.setValue(min(self._progress.maximum(), self._progress.value() + 1))
                self._append_log(self._trial_summary(record))

    def _append_log(self, text: str) -> None:
        if not text:
            return
        self._log_view.appendPlainText(text)
        self._log_view.verticalScrollBar().setValue(self._log_view.verticalScrollBar().maximum())

    def _trial_summary(self, record: TrialRecord) -> str:
        if record.status == TrialStatus.SUCCESS and record.metrics:
            return (
                f"Trial #{record.trial_number} done: profit={record.metrics.total_profit_pct:.2f}% "
                f"dd={record.metrics.max_drawdown_pct:.2f}% trades={record.metrics.total_trades} "
                f"score={record.score or 0.0:.4g}"
            )
        return f"Trial #{record.trial_number} failed."

    def _update_elapsed(self) -> None:
        if not self._session_start_time:
            return
        elapsed = int(time.monotonic() - self._session_start_time)
        self._elapsed_lbl.setText(f"Elapsed: {elapsed // 60:02d}:{elapsed % 60:02d}")
        done = max(1, self._progress.value())
        total = self._progress.maximum()
        if self._running and done and total > done:
            eta = int((elapsed / done) * (total - done))
            self._eta_lbl.setText(f"ETA: {eta // 60:02d}:{eta % 60:02d}")
        else:
            self._eta_lbl.setText("ETA: --:--")

    def _on_trial_clicked(self, index: QModelIndex) -> None:
        source_index = self._trial_proxy.mapToSource(index)
        record = self._trial_model.data(source_index, Qt.UserRole)
        if isinstance(record, TrialRecord):
            self._selected_trial = record
            self._update_metric_labels(self._selected_labels, record)
            self._update_score_breakdown(record)
            self._refresh_selected_trial_diff()

    def _update_metric_labels(self, labels: dict[str, QLabel], record: Optional[TrialRecord]) -> None:
        if not record or not record.metrics:
            for lbl in labels.values():
                lbl.setText("—")
            if record:
                labels["score"].setText(_fmt_float(record.score, 4))
            return
        m = record.metrics
        labels["profit"].setText(_fmt_pct(m.total_profit_pct))
        labels["abs"].setText(_fmt_float(m.total_profit_abs))
        labels["win"].setText(_fmt_pct(m.win_rate * 100 if m.win_rate <= 1 else m.win_rate))
        labels["dd"].setText(_fmt_pct(m.max_drawdown_pct))
        labels["trades"].setText(_fmt_int(m.total_trades))
        labels["pf"].setText(_fmt_float(m.profit_factor))
        labels["sharpe"].setText(_fmt_float(m.sharpe_ratio))
        labels["score"].setText(_fmt_float(record.score, 4))

    def _update_score_breakdown(self, record: Optional[TrialRecord]) -> None:
        if not hasattr(self, "_score_breakdown_view"):
            return
        if not record or not record.score_breakdown:
            self._score_breakdown_view.setPlainText("—")
            return
        lines = [
            f"{key}: {value:.4f}"
            for key, value in record.score_breakdown.items()
        ]
        self._score_breakdown_view.setPlainText("\n".join(lines))

    def _save_optimizer_preferences(self, config: SessionConfig) -> None:
        try:
            self._state.update_preferences(
                "optimizer_preferences",
                last_strategy=config.strategy_name,
                default_timeframe=config.timeframe,
                default_timerange=config.timerange or "",
                default_pairs=",".join(config.pairs),
                dry_run_wallet=config.dry_run_wallet,
                max_open_trades=config.max_open_trades,
                total_trials=config.total_trials,
                score_metric=config.score_metric,
                score_mode=config.score_mode,
                target_min_trades=config.target_min_trades,
                target_profit_pct=config.target_profit_pct,
                max_drawdown_limit=config.max_drawdown_limit,
                target_romad=config.target_romad,
            )
        except Exception as exc:
            _log.warning("Could not save optimizer preferences: %s", exc)

    def _set_selected_as_best(self) -> None:
        if not self._active_session or not self._selected_trial:
            return
        if self._selected_trial.status != TrialStatus.SUCCESS:
            QMessageBox.information(self, "Optimizer", "Only successful trials can be set as best.")
            return
        old_best = self._current_best_trial_number
        self._service.set_best(self._active_session.session_id, self._selected_trial.trial_number)
        self._current_best_trial_number = self._selected_trial.trial_number
        self._trial_model.update_best(old_best, self._selected_trial.trial_number)
        self._update_metric_labels(self._best_labels, self._selected_trial)

    def _refresh_selected_trial_diff(self) -> None:
        if not self._active_session or not self._selected_trial:
            self._clear_selected_trial_diff("Select a successful trial to preview changes.")
            return
        if self._selected_trial.status != TrialStatus.SUCCESS:
            self._clear_selected_trial_diff("Only successful trials can be previewed or applied.")
            return

        diff = self._service.build_trial_diff(
            self._active_session.session_id,
            self._selected_trial.trial_number,
        )
        if not diff.success:
            self._clear_selected_trial_diff(diff.error_message or "Could not build diff.")
            return

        self._param_diff_table.setRowCount(0)
        for change in diff.param_changes:
            row = self._param_diff_table.rowCount()
            self._param_diff_table.insertRow(row)
            self._param_diff_table.setItem(row, 0, QTableWidgetItem(change.key))
            self._param_diff_table.setItem(
                row,
                1,
                QTableWidgetItem(self._format_diff_value(change.current_value)),
            )
            self._param_diff_table.setItem(
                row,
                2,
                QTableWidgetItem(self._format_diff_value(change.trial_value)),
            )

        param_count = len(diff.param_changes)
        code_changed = bool(diff.strategy_diff)
        if param_count or code_changed:
            self._diff_status_lbl.setText(
                f"{param_count} parameter change(s), "
                f"{'code changes found' if code_changed else 'no code changes'}."
            )
        else:
            self._diff_status_lbl.setText("No changes detected for the selected trial.")
        self._strategy_diff_view.setPlainText(diff.strategy_diff or "No code changes.")

    def _clear_selected_trial_diff(self, message: str) -> None:
        if hasattr(self, "_diff_status_lbl"):
            self._diff_status_lbl.setText(message)
            self._param_diff_table.setRowCount(0)
            self._strategy_diff_view.setPlainText("")

    @staticmethod
    def _format_diff_value(value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except TypeError:
            return str(value)

    def _apply_selected_to_strategy(self) -> None:
        if not self._active_session or not self._selected_trial:
            QMessageBox.information(self, "Optimizer", "Select a successful trial first.")
            return
        if self._selected_trial.status != TrialStatus.SUCCESS:
            QMessageBox.information(self, "Optimizer", "Only successful trials can be applied.")
            return
        if QMessageBox.question(
            self,
            "Apply Selected Trial",
            "Apply the selected trial to the existing strategy .py and .json files?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return

        result = self._service.apply_trial_to_strategy(
            self._active_session.session_id,
            self._selected_trial.trial_number,
        )
        if result.success:
            QMessageBox.information(
                self,
                "Apply Selected Trial",
                f"Applied to:\n{result.strategy_py_path}\n{result.strategy_json_path}",
            )
            self._refresh_selected_trial_diff()
        else:
            QMessageBox.warning(self, "Apply Selected Trial", result.error_message)

    def _apply_selected_as_new_strategy(self) -> None:
        if not self._active_session or not self._selected_trial:
            QMessageBox.information(self, "Optimizer", "Select a successful trial first.")
            return
        if self._selected_trial.status != TrialStatus.SUCCESS:
            QMessageBox.information(self, "Optimizer", "Only successful trials can be applied.")
            return

        default_name = (
            f"{self._active_session.config.strategy_name}"
            f"_trial_{self._selected_trial.trial_number:03d}"
        )
        text, accepted = QInputDialog.getText(
            self,
            "Apply New Strategy",
            "New strategy name:",
            QLineEdit.Normal,
            default_name,
        )
        if not accepted:
            return
        strategy_name = text.strip()
        if strategy_name.endswith(".py"):
            strategy_name = strategy_name[:-3]

        result = self._service.apply_trial_as_new_strategy(
            self._active_session.session_id,
            self._selected_trial.trial_number,
            strategy_name,
        )
        if result.success:
            if self._strategy_combo.findText(strategy_name) < 0:
                self._strategy_combo.addItem(strategy_name)
            QMessageBox.information(
                self,
                "Apply New Strategy",
                f"Created:\n{result.strategy_py_path}\n{result.strategy_json_path}",
            )
        else:
            QMessageBox.warning(self, "Apply New Strategy", result.error_message)

    def _export_best(self) -> None:
        if not self._active_session:
            return
        pointer = self._store.load_best_pointer(self._active_session.session_id)
        if not pointer:
            QMessageBox.information(self, "Optimizer", "No best trial is available yet.")
            return
        record = self._store.load_trial_record(self._active_session.session_id, pointer.trial_number)
        settings = self._settings_svc.load_settings()
        live_json = Path(settings.user_data_path or "user_data") / "strategies" / f"{self._active_session.config.strategy_name}.json"
        dlg = ExportConfirmDialog(str(live_json), record.candidate_params if record else {}, self)
        if dlg.exec() != QDialog.Accepted:
            return
        result = self._service.export_best(self._active_session.session_id)
        if result.success:
            QMessageBox.information(self, "Export Best", f"Exported to:\n{result.live_json_path}\n\nBackup:\n{result.backup_path}")
        else:
            QMessageBox.warning(self, "Export Best", result.error_message)

    def _rollback(self) -> None:
        strategy = self._strategy_combo.currentText().strip()
        settings = self._settings_svc.load_settings()
        if not strategy or not settings.user_data_path:
            return
        live_json = Path(settings.user_data_path) / "strategies" / f"{strategy}.json"
        backups = sorted(live_json.parent.glob(f"{live_json.name}.bak_*"), key=lambda p: p.name, reverse=True)
        if not backups:
            QMessageBox.information(self, "Rollback", "No backups found for this strategy JSON.")
            return
        backup = backups[0]
        dlg = RollbackDialog(strategy, backup.name, True, False, live_json, Path(settings.user_data_path) / "config.json", self)
        if dlg.exec() != QDialog.Accepted or not dlg.restore_params:
            return
        try:
            rollback = RollbackService()
            rollback._backup_file(live_json)
            rollback._atomic_restore(backup, live_json)
            QMessageBox.information(self, "Rollback", f"Restored:\n{backup}")
        except Exception as exc:
            QMessageBox.warning(self, "Rollback", str(exc))

    def _trial_path(self, filename: str) -> Optional[Path]:
        if not self._active_session or not self._selected_trial:
            return None
        return self._store.trial_dir(self._active_session.session_id, self._selected_trial.trial_number) / filename

    def _open_selected_log(self) -> None:
        path = self._trial_path("trial.log")
        if path and path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_selected_result(self) -> None:
        path = self._trial_path("backtest_result.json")
        if path and path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _compare_selected(self) -> None:
        rows = self._trial_table.selectionModel().selectedRows()
        records: list[TrialRecord] = []
        for proxy_idx in rows[:2]:
            source_idx = self._trial_proxy.mapToSource(proxy_idx)
            record = self._trial_model.data(source_idx, Qt.UserRole)
            if isinstance(record, TrialRecord):
                records.append(record)
        if len(records) != 2:
            QMessageBox.information(self, "Compare", "Select exactly two trials to compare.")
            return
        _CompareDialog(records[0], records[1], self).exec()

    def _load_history(self) -> None:
        sessions = self._store.list_sessions()
        self._history_sessions = sessions
        self._history_table.setRowCount(0)
        for session in sessions:
            row = self._history_table.rowCount()
            self._history_table.insertRow(row)
            best = session.best_pointer.score if session.best_pointer else None
            values = [
                session.config.strategy_name,
                session.started_at or "",
                str(session.trials_completed),
                "—" if best is None else f"{best:.4g}",
                session.status.value,
            ]
            for col, value in enumerate(values):
                self._history_table.setItem(row, col, QTableWidgetItem(value))

    def _load_history_session(self, row: int, _col: int) -> None:
        if not hasattr(self, "_history_sessions") or row >= len(self._history_sessions):
            return
        session = self._history_sessions[row]
        self._active_session = session
        self._trial_model.clear()
        self._current_best_trial_number = session.best_pointer.trial_number if session.best_pointer else 0
        for record in self._store.load_all_trial_records(session.session_id):
            self._trial_model.append_trial(record)
        if session.best_pointer:
            self._trial_model.update_best(0, session.best_pointer.trial_number)
            record = self._store.load_trial_record(session.session_id, session.best_pointer.trial_number)
            self._update_metric_labels(self._best_labels, record)
        self._progress.setRange(0, max(session.config.total_trials, 1))
        self._progress.setValue(session.trials_completed)

    def _delete_selected_history(self) -> None:
        row = self._history_table.currentRow()
        if row < 0 or not hasattr(self, "_history_sessions") or row >= len(self._history_sessions):
            return
        session = self._history_sessions[row]
        result = QMessageBox.question(self, "Delete Session", f"Delete optimizer session {session.session_id}?")
        if result != QMessageBox.Yes:
            return
        self._store.delete_session(session.session_id)
        self._load_history()
