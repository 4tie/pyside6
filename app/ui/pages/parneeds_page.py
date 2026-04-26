"""ParNeeds page — Walk-Forward, Monte Carlo, Parameter Sensitivity, and Timerange workflows."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.app_state.settings_state import SettingsState
from app.core.models.parneeds_models import (
    CandleCoverageReport,
    MCPercentiles,
    MonteCarloConfig,
    ParNeedsConfig,
    ParNeedsRunResult,
    ParNeedsWindow,
    SweepParameterDef,
    SweepParamType,
    SweepPoint,
    WalkForwardConfig,
    WalkForwardFold,
    WalkForwardFoldResult,
    WalkForwardMode,
)
from app.core.services.backtest_service import BacktestService
from app.core.services.download_data_service import DownloadDataService
from app.core.services.parneeds_service import ParNeedsService
from app.core.services.process_run_manager import ProcessRunManager
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger
from app.ui import theme
from app.ui.adapters.process_run_adapter import ProcessRunAdapter
from app.ui.pages.backtest_page import TIMEFRAMES
from app.ui.widgets.terminal_widget import TerminalWidget

_log = get_logger("ui.parneeds")

# Workflow combo indices
_WF_TIMERANGE = 0
_WF_WALK_FORWARD = 1
_WF_MONTE_CARLO = 2
_WF_PARAM_SENSITIVITY = 3

# Results table column indices
_COL_RUN_TRIAL = 0
_COL_WORKFLOW = 1
_COL_STRATEGY = 2
_COL_PAIRS = 3
_COL_TIMEFRAME = 4
_COL_TIMERANGE = 5
_COL_PROFIT_PCT = 6
_COL_TOTAL_PROFIT = 7
_COL_WIN_RATE = 8
_COL_MAX_DD = 9
_COL_TRADES = 10
_COL_PROFIT_FACTOR = 11
_COL_SHARPE = 12
_COL_SCORE = 13
_COL_STATUS = 14
_COL_RESULT_PATH = 15
_COL_LOG_PATH = 16

_RESULT_HEADERS = [
    "Run/Trial", "Workflow", "Strategy", "Pair(s)", "Timeframe", "Timerange",
    "Profit %", "Total Profit", "Win Rate", "Max DD %", "Trades",
    "Profit Factor", "Sharpe Ratio", "Score", "Status", "Result Path", "Log Path",
]


class ParNeedsPage(QWidget):
    """Run validation workflows against editable backtest configuration."""

    run_completed = Signal(str)

    # Bridge signals (background thread → Qt main thread)
    _sig_stdout   = Signal(str)
    _sig_stderr   = Signal(str)
    _sig_finished = Signal(int)
    _sig_result   = Signal(object)   # ParNeedsRunResult — batched table updates

    def __init__(
        self,
        settings_state: SettingsState,
        process_manager: ProcessRunManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = settings_state
        self._settings_svc = SettingsService()
        self._backtest_svc = BacktestService(self._settings_svc)
        self._download_svc = DownloadDataService(self._settings_svc)
        self._parneeds_svc = ParNeedsService()
        self._process_manager = process_manager
        self._adapter: Optional[ProcessRunAdapter] = None
        self._current_run_id: Optional[str] = None
        self._running = False
        self._phase = "idle"

        # Timerange workflow state
        self._active_config: Optional[ParNeedsConfig] = None
        self._active_window: Optional[ParNeedsWindow] = None
        self._pending_windows: list[ParNeedsWindow] = []
        self._download_queue: list[tuple[bool, list[str], str]] = []

        # Walk-Forward workflow state
        self._wf_config: Optional[WalkForwardConfig] = None
        self._wf_folds: list[WalkForwardFold] = []
        self._wf_fold_results: list[WalkForwardFoldResult] = []
        self._pending_wf_items: list[tuple[WalkForwardFold, str]] = []  # (fold, "IS"|"OOS")

        # Monte Carlo workflow state
        self._mc_config: Optional[MonteCarloConfig] = None
        self._mc_iteration_index: int = 0
        self._mc_profits: list[float] = []
        self._mc_failed_count: int = 0

        # Parameter Sensitivity workflow state
        self._ps_params: list[SweepParameterDef] = []
        self._pending_sweep_points: list[SweepPoint] = []
        self._ps_results: list[ParNeedsRunResult] = []

        # Batched update buffers (matching OptimizerPage pattern)
        self._pending_results: list[ParNeedsRunResult] = []

        # All stored results for export
        self._all_results: list[ParNeedsRunResult] = []

        self._build()

        # Wire bridge signals
        self._sig_stdout.connect(self._terminal.append_output)
        self._sig_stderr.connect(self._terminal.append_error)
        self._sig_finished.connect(self._handle_finished)
        self._sig_result.connect(self._on_result_received)

        # Flush timer (500 ms, matching OptimizerPage)
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(500)
        self._flush_timer.timeout.connect(self._flush_pending_updates)
        self._flush_timer.start()

        self._load_strategies()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("ParNeeds")
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()

        self._sync_btn = QPushButton("Sync Backtest")
        self._sync_btn.clicked.connect(self._request_sync)
        header.addWidget(self._sync_btn)

        self._start_btn = QPushButton("Start")
        self._start_btn.setObjectName("primary")
        self._start_btn.clicked.connect(self._on_start_clicked)
        header.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("danger")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)
        header.addWidget(self._stop_btn)
        root.addLayout(header)

        # Three-pane splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {theme.BG_BORDER}; }}")

        splitter.addWidget(self._build_left_sidebar())
        splitter.addWidget(self._build_center_pane())
        splitter.addWidget(self._build_right_sidebar())
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, False)
        splitter.setSizes([340, 820, 300])
        root.addWidget(splitter, 1)

    def _build_left_sidebar(self) -> QFrame:
        panel = QFrame()
        panel.setMinimumWidth(280)
        panel.setMaximumWidth(400)
        panel.setStyleSheet(
            f"QFrame {{ background: {theme.BG_SURFACE}; border: 1px solid {theme.BG_BORDER}; border-radius: 10px; }}"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Workflow selector
        layout.addWidget(self._section("Workflow"))
        self._workflow_combo = QComboBox()
        self._workflow_combo.addItem("Timerange workflow")
        self._workflow_combo.addItem("Walk-Forward workflow")
        self._workflow_combo.addItem("Monte Carlo workflow")
        self._workflow_combo.addItem("Parameter Sensitivity workflow")
        self._workflow_combo.currentIndexChanged.connect(self._on_workflow_changed)
        layout.addWidget(self._workflow_combo)

        # Shared run config
        layout.addWidget(self._section("Run Config"))
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self._strategy_combo = QComboBox()
        self._strategy_combo.setEditable(True)
        self._strategy_combo.currentTextChanged.connect(self._update_plan_label)
        form.addRow(self._label("Strategy"), self._strategy_combo)

        self._timeframe_combo = QComboBox()
        self._timeframe_combo.setEditable(True)
        self._timeframe_combo.addItems(TIMEFRAMES)
        self._timeframe_combo.setCurrentText("5m")
        self._timeframe_combo.currentTextChanged.connect(self._update_plan_label)
        form.addRow(self._label("Timeframe"), self._timeframe_combo)

        self._timerange_edit = QLineEdit()
        self._timerange_edit.setPlaceholderText("Defaults to 20240101-yesterday")
        self._timerange_edit.textChanged.connect(self._update_plan_label)
        form.addRow(self._label("Timerange"), self._timerange_edit)

        self._pairs_edit = QLineEdit()
        self._pairs_edit.setPlaceholderText("BTC/USDT,ETH/USDT")
        self._pairs_edit.textChanged.connect(self._update_plan_label)
        form.addRow(self._label("Pairs"), self._pairs_edit)

        self._wallet_spin = QDoubleSpinBox()
        self._wallet_spin.setRange(1, 1_000_000)
        self._wallet_spin.setValue(80)
        self._wallet_spin.setSuffix(" USDT")
        form.addRow(self._label("Wallet"), self._wallet_spin)

        self._trades_spin = QSpinBox()
        self._trades_spin.setRange(1, 100)
        self._trades_spin.setValue(2)
        form.addRow(self._label("Max Trades"), self._trades_spin)

        self._seed_spin = QSpinBox()
        self._seed_spin.setRange(1, 2_147_483_647)
        self._seed_spin.setValue(20240101)
        form.addRow(self._label("Seed"), self._seed_spin)
        layout.addLayout(form)

        # Workflow-specific config panels (QStackedWidget)
        self._workflow_stack = QStackedWidget()

        # Index 0: no extra panel (Timerange)
        self._workflow_stack.addWidget(QWidget())

        # Index 1: Walk-Forward panel
        self._workflow_stack.addWidget(self._build_wf_panel())

        # Index 2: Monte Carlo panel
        self._workflow_stack.addWidget(self._build_mc_panel())

        # Index 3: Parameter Sensitivity panel
        self._workflow_stack.addWidget(self._build_ps_panel())

        layout.addWidget(self._workflow_stack)

        self._plan_lbl = QLabel("Select a workflow, sync config, then start.")
        self._plan_lbl.setWordWrap(True)
        self._plan_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self._plan_lbl)
        layout.addStretch()
        return panel

    def _build_wf_panel(self) -> QFrame:
        """Walk-Forward config panel (Task 8.1)."""
        frame = QFrame()
        form = QFormLayout(frame)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self._wf_folds_spin = QSpinBox()
        self._wf_folds_spin.setRange(2, 20)
        self._wf_folds_spin.setValue(5)
        self._wf_folds_spin.valueChanged.connect(self._update_plan_label)
        form.addRow(self._label("Folds"), self._wf_folds_spin)

        self._wf_split_spin = QSpinBox()
        self._wf_split_spin.setRange(50, 95)
        self._wf_split_spin.setValue(80)
        self._wf_split_spin.setSuffix(" %")
        self._wf_split_spin.valueChanged.connect(self._update_plan_label)
        form.addRow(self._label("IS Split"), self._wf_split_spin)

        self._wf_mode_combo = QComboBox()
        self._wf_mode_combo.addItems(["anchored", "rolling"])
        self._wf_mode_combo.currentIndexChanged.connect(self._update_plan_label)
        form.addRow(self._label("Mode"), self._wf_mode_combo)

        return frame

    def _build_mc_panel(self) -> QFrame:
        """Monte Carlo config panel (Task 8.2)."""
        frame = QFrame()
        form = QFormLayout(frame)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self._mc_iterations_spin = QSpinBox()
        self._mc_iterations_spin.setRange(10, 5000)
        self._mc_iterations_spin.setValue(500)
        self._mc_iterations_spin.valueChanged.connect(self._update_plan_label)
        form.addRow(self._label("Iterations"), self._mc_iterations_spin)

        self._mc_randomise_chk = QCheckBox("Randomise trade order")
        self._mc_randomise_chk.setChecked(True)
        form.addRow(self._mc_randomise_chk)

        self._mc_noise_chk = QCheckBox("Profit noise (±2%)")
        self._mc_noise_chk.setChecked(True)
        form.addRow(self._mc_noise_chk)

        self._mc_max_dd_spin = QDoubleSpinBox()
        self._mc_max_dd_spin.setRange(1.0, 100.0)
        self._mc_max_dd_spin.setValue(20.0)
        self._mc_max_dd_spin.setSuffix(" %")
        form.addRow(self._label("Max DD Threshold"), self._mc_max_dd_spin)

        return frame

    def _build_ps_panel(self) -> QFrame:
        """Parameter Sensitivity config panel (Task 8.3)."""
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self._ps_mode_combo = QComboBox()
        self._ps_mode_combo.addItems(["One-at-a-time", "Grid"])
        self._ps_mode_combo.currentIndexChanged.connect(self._update_plan_label)
        form.addRow(self._label("Mode"), self._ps_mode_combo)
        layout.addLayout(form)

        self._ps_discover_btn = QPushButton("Discover Parameters")
        self._ps_discover_btn.clicked.connect(self._discover_ps_parameters)
        layout.addWidget(self._ps_discover_btn)

        self._ps_param_table = QTableWidget(0, 6)
        self._ps_param_table.setHorizontalHeaderLabels(
            ["✓", "Name", "Type", "Min", "Max", "Step/Values"]
        )
        self._ps_param_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._ps_param_table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self._ps_param_table.setMaximumHeight(200)
        layout.addWidget(self._ps_param_table)

        return frame

    def _build_center_pane(self) -> QWidget:
        """Center pane: terminal (top) + shared results table (bottom)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._terminal = TerminalWidget()
        layout.addWidget(self._terminal, 2)

        # 17-column shared results table (Task 9)
        self._results = QTableWidget(0, len(_RESULT_HEADERS))
        self._results.setHorizontalHeaderLabels(_RESULT_HEADERS)
        self._results.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._results.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._results.setAlternatingRowColors(True)
        self._results.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._results.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._results, 1)

        return widget

    def _build_right_sidebar(self) -> QFrame:
        """Right sidebar: summary, chart placeholder, export button."""
        panel = QFrame()
        panel.setMinimumWidth(220)
        panel.setMaximumWidth(380)
        panel.setStyleSheet(
            f"QFrame {{ background: {theme.BG_SURFACE}; border: 1px solid {theme.BG_BORDER}; border-radius: 10px; }}"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(self._section("Summary"))

        self._summary_lbl = QLabel("No results yet.")
        self._summary_lbl.setWordWrap(True)
        self._summary_lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self._summary_lbl)

        layout.addWidget(self._section("Chart"))

        # Try to embed matplotlib; fall back to a QLabel placeholder
        self._chart_widget = self._build_chart_widget()
        layout.addWidget(self._chart_widget, 1)

        layout.addStretch()

        self._export_btn = QPushButton("Export Results")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_results)
        layout.addWidget(self._export_btn)

        return panel

    def _build_chart_widget(self) -> QWidget:
        """Return a matplotlib FigureCanvasQTAgg or a QLabel fallback."""
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure

            fig = Figure(figsize=(3, 2), tight_layout=True)
            self._mpl_figure = fig
            self._mpl_axes = fig.add_subplot(111)
            canvas = FigureCanvasQTAgg(fig)
            self._mpl_canvas = canvas
            return canvas
        except Exception:
            lbl = QLabel("Chart unavailable\n(install matplotlib)")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
            self._mpl_figure = None
            self._mpl_axes = None
            self._mpl_canvas = None
            return lbl


    # ------------------------------------------------------------------
    # Workflow selector
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_workflow_changed(self, index: int) -> None:
        """Show the correct config panel; ignore changes while running (Req 14.3)."""
        if self._running:
            # Revert silently
            self._workflow_combo.blockSignals(True)
            self._workflow_combo.setCurrentIndex(self._workflow_stack.currentIndex())
            self._workflow_combo.blockSignals(False)
            return
        self._workflow_stack.setCurrentIndex(index)
        self._update_plan_label()

    # ------------------------------------------------------------------
    # Sync from Backtest page
    # ------------------------------------------------------------------

    def sync_from_backtest(self, config: dict) -> None:
        """Load Backtest page values into the editable ParNeeds form."""
        strategy = str(config.get("strategy") or "")
        if strategy and self._strategy_combo.findText(strategy) < 0:
            self._strategy_combo.addItem(strategy)
        self._strategy_combo.setCurrentText(strategy)
        self._timeframe_combo.setCurrentText(str(config.get("timeframe") or "5m"))
        self._timerange_edit.setText(str(config.get("timerange") or ""))
        pairs = config.get("pairs") or []
        if isinstance(pairs, str):
            pairs_text = pairs
        else:
            pairs_text = ",".join(str(pair) for pair in pairs)
        self._pairs_edit.setText(pairs_text)
        self._wallet_spin.setValue(float(config.get("dry_run_wallet") or 80.0))
        self._trades_spin.setValue(int(config.get("max_open_trades") or 2))
        self._update_plan_label()

    # ------------------------------------------------------------------
    # Config builders
    # ------------------------------------------------------------------

    def build_config(self) -> ParNeedsConfig:
        """Build a typed ParNeeds config from the current form values."""
        pairs = [p.strip() for p in self._pairs_edit.text().split(",") if p.strip()]
        timerange = self._timerange_edit.text().strip() or None
        normalized_timerange = self._parneeds_svc.normalize_timerange(timerange)
        return ParNeedsConfig(
            strategy=self._strategy_combo.currentText().strip(),
            timeframe=self._timeframe_combo.currentText().strip() or "5m",
            timerange=normalized_timerange,
            pairs=pairs,
            dry_run_wallet=self._wallet_spin.value(),
            max_open_trades=self._trades_spin.value(),
            seed=self._seed_spin.value(),
        )

    def _build_wf_config(self) -> WalkForwardConfig:
        """Build WalkForwardConfig from current form values (Task 10.1)."""
        cfg = self.build_config()
        mode = WalkForwardMode.ANCHORED if self._wf_mode_combo.currentIndex() == 0 else WalkForwardMode.ROLLING
        return WalkForwardConfig(
            strategy=cfg.strategy,
            timeframe=cfg.timeframe,
            timerange=cfg.timerange,
            pairs=cfg.pairs,
            dry_run_wallet=cfg.dry_run_wallet,
            max_open_trades=cfg.max_open_trades,
            n_folds=self._wf_folds_spin.value(),
            split_ratio=self._wf_split_spin.value() / 100.0,
            mode=mode,
        )

    def _build_mc_config(self) -> MonteCarloConfig:
        """Build MonteCarloConfig from current form values (Task 11.1)."""
        cfg = self.build_config()
        return MonteCarloConfig(
            strategy=cfg.strategy,
            timeframe=cfg.timeframe,
            timerange=cfg.timerange,
            pairs=cfg.pairs,
            dry_run_wallet=cfg.dry_run_wallet,
            max_open_trades=cfg.max_open_trades,
            n_iterations=self._mc_iterations_spin.value(),
            randomise_trade_order=self._mc_randomise_chk.isChecked(),
            profit_noise=self._mc_noise_chk.isChecked(),
            max_drawdown_threshold_pct=self._mc_max_dd_spin.value(),
            base_seed=self._seed_spin.value(),
        )

    # ------------------------------------------------------------------
    # Start button routing (Task 14)
    # ------------------------------------------------------------------

    @Slot()
    def _on_start_clicked(self) -> None:
        """Route Start button to the active workflow."""
        idx = self._workflow_combo.currentIndex()
        if idx == _WF_TIMERANGE:
            self.start_timerange_workflow()
        elif idx == _WF_WALK_FORWARD:
            self.start_walk_forward_workflow()
        elif idx == _WF_MONTE_CARLO:
            self.start_monte_carlo_workflow()
        elif idx == _WF_PARAM_SENSITIVITY:
            self.start_param_sensitivity_workflow()

    # ------------------------------------------------------------------
    # Timerange workflow (existing, preserved)
    # ------------------------------------------------------------------

    def start_timerange_workflow(self) -> None:
        """Start the v1 ParNeeds timerange workflow."""
        if self._running:
            return
        try:
            config = self.build_config()
            self._validate_config(config)
            windows = self._parneeds_svc.generate_timerange_windows(config)
        except Exception as exc:
            self._terminal.append_info(f"Cannot start: {exc}", theme.RED)
            return

        self._active_config = config
        self._pending_windows = list(windows)
        self._active_window = None
        self._terminal.clear()
        self._terminal.set_status("checking", theme.ACCENT)
        self._timerange_edit.setText(config.timerange or "")
        self._plan_lbl.setText(
            f"{len(windows)} windows planned across {config.timerange}. "
            "Checking candle coverage."
        )
        self._set_running(True)

        try:
            reports = self._parneeds_svc.validate_candle_coverage(
                self._require_settings(), config
            )
        except Exception as exc:
            self._terminal.append_info(f"Coverage check failed: {exc}", theme.RED)
            self._terminal.set_status("failed", theme.RED)
            self._set_running(False)
            return

        self._append_coverage(reports)
        if self._coverage_has_blocking_gaps(reports):
            self._queue_downloads(config, reports)
            self._start_next_download()
            return
        self._start_next_backtest()

    # ------------------------------------------------------------------
    # Walk-Forward workflow (Task 10)
    # ------------------------------------------------------------------

    def start_walk_forward_workflow(self) -> None:
        """Entry point for Walk-Forward workflow (Task 10.2)."""
        if self._running:
            return
        try:
            wf_cfg = self._build_wf_config()
            self._validate_config_base(wf_cfg)
        except Exception as exc:
            self._terminal.append_info(f"Cannot start: {exc}", theme.RED)
            return

        # Generate folds — may raise ValueError
        try:
            folds = self._parneeds_svc.generate_walk_forward_folds(wf_cfg)
        except ValueError as exc:
            self._terminal.append_info(f"Fold generation failed: {exc}", theme.RED)
            return

        self._wf_config = wf_cfg
        self._wf_folds = folds
        self._wf_fold_results = []
        self._pending_wf_items = []
        for fold in folds:
            self._pending_wf_items.append((fold, "IS"))
            self._pending_wf_items.append((fold, "OOS"))

        self._terminal.clear()
        self._terminal.set_status("checking", theme.ACCENT)
        self._set_running(True)

        # Display fold schedule (Req 1.6)
        self._terminal.append_info("Walk-Forward fold schedule:", theme.ACCENT)
        for fold in folds:
            self._terminal.append_info(
                f"  Fold {fold.fold_index}: IS {fold.is_timerange}  OOS {fold.oos_timerange}",
                theme.TEXT_SECONDARY,
            )

        # Candle coverage validation (Req 15.1)
        base_cfg = self.build_config()
        try:
            reports = self._parneeds_svc.validate_candle_coverage(
                self._require_settings(), base_cfg
            )
        except Exception as exc:
            self._terminal.append_info(f"Coverage check failed: {exc}", theme.RED)
            self._terminal.set_status("failed", theme.RED)
            self._set_running(False)
            return

        self._append_coverage(reports)
        if self._coverage_has_blocking_gaps(reports):
            self._active_config = base_cfg
            self._queue_downloads(base_cfg, reports)
            self._phase = "wf_download"
            self._start_next_download()
            return

        self._phase = "wf_backtest"
        self._start_next_wf_backtest()

    def _start_next_wf_backtest(self) -> None:
        """Sequential IS-then-OOS execution per fold (Task 10.3)."""
        if not self._pending_wf_items:
            self._finish_walk_forward()
            return

        fold, window_type = self._pending_wf_items.pop(0)
        timerange = fold.is_timerange if window_type == "IS" else fold.oos_timerange
        cfg = self._wf_config
        if not cfg:
            self._set_running(False)
            return

        self._plan_lbl.setText(
            f"Fold {fold.fold_index} / {len(self._wf_folds)} — {window_type}"
        )
        self._terminal.append_info(
            f"\n[WF Fold {fold.fold_index} {window_type}] {timerange}\n", theme.ACCENT
        )

        try:
            cmd = self._backtest_svc.build_command(
                strategy_name=cfg.strategy,
                timeframe=cfg.timeframe,
                timerange=timerange,
                pairs=cfg.pairs,
                max_open_trades=cfg.max_open_trades,
                dry_run_wallet=cfg.dry_run_wallet,
            )
        except Exception as exc:
            self._terminal.append_info(f"Command failed: {exc}", theme.RED)
            self._start_next_wf_backtest()
            return

        # Track which fold/window we're running
        self._wf_active_fold = fold
        self._wf_active_window_type = window_type
        self._phase = "wf_backtest"
        self._terminal.set_status("running", theme.GREEN)
        self._start_process(cmd)

    def _handle_wf_backtest_finished(self, exit_code: int) -> None:
        """Result parsing and fold result update (Task 10.4)."""
        fold = getattr(self, "_wf_active_fold", None)
        window_type = getattr(self, "_wf_active_window_type", "IS")
        cfg = self._wf_config

        if not fold or not cfg:
            self._start_next_wf_backtest()
            return

        # Find or create fold result
        fold_result = next(
            (r for r in self._wf_fold_results if r.fold.fold_index == fold.fold_index),
            None,
        )
        if fold_result is None:
            from app.core.models.parneeds_models import WalkForwardFoldResult
            fold_result = WalkForwardFoldResult(fold=fold)
            self._wf_fold_results.append(fold_result)

        if exit_code == 0:
            run_id = ""
            entry: dict = {}
            try:
                settings = self._require_settings()
                export_dir = Path(settings.user_data_path) / "backtest_results"
                run_id = self._backtest_svc.parse_and_save_latest_results(
                    export_dir, cfg.strategy
                ) or ""
                entry = self._find_run_entry(run_id, cfg.strategy)
            except Exception as exc:
                _log.warning("Could not save WF backtest result: %s", exc)

            profit = self._safe_float(entry.get("profit_total_pct"))
            win_rate = self._safe_float(entry.get("win_rate_pct"))
            max_dd = self._safe_float(entry.get("max_drawdown_pct"))
            trades = self._safe_int(entry.get("trades_count"))

            if window_type == "IS":
                fold_result.is_run_id = run_id
                fold_result.is_profit_pct = profit
            else:
                fold_result.oos_run_id = run_id
                fold_result.oos_profit_pct = profit
                fold_result.win_rate_pct = win_rate
                fold_result.max_drawdown_pct = max_dd
                fold_result.trades_count = trades
                fold_result.status = "completed"

            timerange = fold.is_timerange if window_type == "IS" else fold.oos_timerange
            result = ParNeedsRunResult(
                run_trial=f"Fold {fold.fold_index} {window_type}",
                workflow="walk_forward",
                strategy=cfg.strategy,
                pairs=", ".join(cfg.pairs),
                timeframe=cfg.timeframe,
                timerange=timerange,
                profit_pct=profit,
                win_rate=win_rate,
                max_dd_pct=max_dd,
                trades=trades,
                status="completed",
                result_path=str(entry.get("result_path", "")),
                log_path=str(entry.get("log_path", "")),
            )
            self._sig_result.emit(result)
            if run_id:
                self.run_completed.emit(run_id)
        else:
            fold_result.status = "failed"
            self._terminal.append_info(
                f"Fold {fold.fold_index} {window_type} failed (exit {exit_code})", theme.RED
            )
            result = ParNeedsRunResult(
                run_trial=f"Fold {fold.fold_index} {window_type}",
                workflow="walk_forward",
                strategy=cfg.strategy,
                timerange=fold.is_timerange if window_type == "IS" else fold.oos_timerange,
                status=f"failed ({exit_code})",
            )
            self._sig_result.emit(result)

        self._start_next_wf_backtest()

    def _finish_walk_forward(self) -> None:
        """Stability score and summary display (Task 10.5)."""
        cfg = self._wf_config
        if not cfg:
            self._set_running(False)
            return

        oos_profits = [
            r.oos_profit_pct
            for r in self._wf_fold_results
            if r.oos_profit_pct is not None
        ]
        score = self._parneeds_svc.compute_stability_score(oos_profits)

        pass_count = sum(1 for p in oos_profits if p is not None and p > 0)
        fail_count = len(self._wf_fold_results) - pass_count
        avg_profit = sum(oos_profits) / len(oos_profits) if oos_profits else 0.0

        oos_dds = [
            r.max_drawdown_pct
            for r in self._wf_fold_results
            if r.max_drawdown_pct is not None
        ]
        avg_dd = sum(oos_dds) / len(oos_dds) if oos_dds else 0.0

        summary = (
            f"Walk-Forward complete\n"
            f"Stability score: {score:.1f}/100\n"
            f"Avg OOS profit: {avg_profit:.2f}%\n"
            f"Avg OOS DD: {avg_dd:.2f}%\n"
            f"Pass: {pass_count}  Fail: {fail_count}"
        )
        self._summary_lbl.setText(summary)
        self._terminal.append_info(f"\n{summary}", theme.GREEN)
        self._terminal.set_status("done", theme.GREEN)

        # Colour-code fold rows (Req 3.4)
        self._colour_wf_rows()

        # Render chart
        self._render_wf_chart(oos_profits)

        self._phase = "idle"
        self._set_running(False)

    def _colour_wf_rows(self) -> None:
        """Green for positive OOS profit, red for negative/failed (Req 3.4)."""
        for row in range(self._results.rowCount()):
            trial_item = self._results.item(row, _COL_RUN_TRIAL)
            if trial_item is None:
                continue
            trial_text = trial_item.text()
            if "OOS" not in trial_text:
                continue
            profit_item = self._results.item(row, _COL_PROFIT_PCT)
            status_item = self._results.item(row, _COL_STATUS)
            is_failed = status_item and "failed" in status_item.text().lower()
            try:
                profit_val = float(profit_item.text()) if profit_item else None
            except (ValueError, AttributeError):
                profit_val = None

            if is_failed or profit_val is None or profit_val <= 0:
                color = theme.RED
            else:
                color = theme.GREEN

            for col in range(self._results.columnCount()):
                item = self._results.item(row, col)
                if item:
                    item.setForeground(
                        __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(color)
                    )

    def _render_wf_chart(self, oos_profits: list[float]) -> None:
        """Render OOS profit bar chart in right sidebar."""
        if self._mpl_axes is None or self._mpl_canvas is None:
            return
        try:
            ax = self._mpl_axes
            ax.clear()
            x = list(range(1, len(oos_profits) + 1))
            colors = [theme.GREEN if p > 0 else theme.RED for p in oos_profits]
            ax.bar(x, oos_profits, color=colors)
            ax.set_xlabel("Fold")
            ax.set_ylabel("OOS Profit %")
            ax.set_title("Walk-Forward OOS Profits")
            self._mpl_canvas.draw()
        except Exception as exc:
            _log.warning("Chart render failed: %s", exc)


    # ------------------------------------------------------------------
    # Monte Carlo workflow (Task 11)
    # ------------------------------------------------------------------

    def start_monte_carlo_workflow(self) -> None:
        """Entry point for Monte Carlo workflow (Task 11.2)."""
        if self._running:
            return
        try:
            mc_cfg = self._build_mc_config()
            self._validate_config_base(mc_cfg)
        except Exception as exc:
            self._terminal.append_info(f"Cannot start: {exc}", theme.RED)
            return

        self._mc_config = mc_cfg
        self._mc_iteration_index = 0
        self._mc_profits = []
        self._mc_failed_count = 0

        self._terminal.clear()
        self._terminal.set_status("checking", theme.ACCENT)
        self._set_running(True)

        # Validate coverage once (Req 15.3)
        base_cfg = self.build_config()
        try:
            reports = self._parneeds_svc.validate_candle_coverage(
                self._require_settings(), base_cfg
            )
        except Exception as exc:
            self._terminal.append_info(f"Coverage check failed: {exc}", theme.RED)
            self._terminal.set_status("failed", theme.RED)
            self._set_running(False)
            return

        self._append_coverage(reports)
        if self._coverage_has_blocking_gaps(reports):
            self._active_config = base_cfg
            self._queue_downloads(base_cfg, reports)
            self._phase = "mc_download"
            self._start_next_download()
            return

        self._phase = "mc_backtest"
        self._start_next_mc_iteration()

    def _start_next_mc_iteration(self) -> None:
        """Sequential iteration execution (Task 11.3)."""
        cfg = self._mc_config
        if not cfg:
            self._set_running(False)
            return

        i = self._mc_iteration_index
        if i >= cfg.n_iterations:
            self._finish_monte_carlo()
            return

        seed_i = self._parneeds_svc.generate_mc_seed(cfg.base_seed, i)
        self._mc_active_seed = seed_i

        self._plan_lbl.setText(f"Iteration {i + 1} / {cfg.n_iterations}")
        self._terminal.append_info(
            f"\n[MC Iteration {i + 1}/{cfg.n_iterations}] seed={seed_i}\n", theme.ACCENT
        )

        extra_flags: list[str] = []
        if cfg.randomise_trade_order:
            extra_flags = ["--random-state", str(seed_i)]

        try:
            cmd = self._backtest_svc.build_command(
                strategy_name=cfg.strategy,
                timeframe=cfg.timeframe,
                timerange=cfg.timerange,
                pairs=cfg.pairs,
                max_open_trades=cfg.max_open_trades,
                dry_run_wallet=cfg.dry_run_wallet,
                extra_flags=extra_flags,
            )
        except Exception as exc:
            self._terminal.append_info(f"Command failed: {exc}", theme.RED)
            self._mc_iteration_index += 1
            self._start_next_mc_iteration()
            return

        self._phase = "mc_backtest"
        self._terminal.set_status("running", theme.GREEN)
        self._start_process(cmd)

    def _handle_mc_iteration_finished(self, exit_code: int) -> None:
        """Result parsing and noise application (Task 11.4)."""
        cfg = self._mc_config
        i = self._mc_iteration_index
        seed_i = getattr(self, "_mc_active_seed", 0)

        if not cfg:
            self._set_running(False)
            return

        if exit_code == 0:
            run_id = ""
            entry: dict = {}
            try:
                settings = self._require_settings()
                export_dir = Path(settings.user_data_path) / "backtest_results"
                run_id = self._backtest_svc.parse_and_save_latest_results(
                    export_dir, cfg.strategy
                ) or ""
                entry = self._find_run_entry(run_id, cfg.strategy)
            except Exception as exc:
                _log.warning("Could not save MC iteration result: %s", exc)

            profit = self._safe_float(entry.get("profit_total_pct"))
            if profit is not None and cfg.profit_noise:
                profit = self._parneeds_svc.apply_profit_noise(profit, seed_i)

            if profit is not None:
                self._mc_profits.append(profit)

            result = ParNeedsRunResult(
                run_trial=f"Iter {i + 1}",
                workflow="monte_carlo",
                strategy=cfg.strategy,
                pairs=", ".join(cfg.pairs),
                timeframe=cfg.timeframe,
                timerange=cfg.timerange,
                profit_pct=profit,
                win_rate=self._safe_float(entry.get("win_rate_pct")),
                max_dd_pct=self._safe_float(entry.get("max_drawdown_pct")),
                trades=self._safe_int(entry.get("trades_count")),
                status="completed",
                result_path=str(entry.get("result_path", "")),
                log_path=str(entry.get("log_path", "")),
            )
            self._sig_result.emit(result)
            if run_id:
                self.run_completed.emit(run_id)
        else:
            self._mc_failed_count += 1
            self._terminal.append_info(
                f"Iteration {i + 1} failed (exit {exit_code})", theme.RED
            )
            result = ParNeedsRunResult(
                run_trial=f"Iter {i + 1}",
                workflow="monte_carlo",
                strategy=cfg.strategy if cfg else "",
                status=f"failed ({exit_code})",
            )
            self._sig_result.emit(result)

        self._mc_iteration_index += 1
        self._start_next_mc_iteration()

    def _finish_monte_carlo(self) -> None:
        """Percentile table and distribution chart (Task 11.5)."""
        cfg = self._mc_config
        if not cfg:
            self._set_running(False)
            return

        profits = self._mc_profits
        summary_lines = [f"Monte Carlo complete ({len(profits)} successful iterations)"]

        if profits:
            try:
                pct = self._parneeds_svc.compute_mc_percentiles(profits)
                prob_profit = sum(1 for p in profits if p > 0) / len(profits)
                prob_exceed_dd = 0.0  # placeholder — DD data not aggregated here

                summary_lines += [
                    f"P5 profit: {pct.p5:.2f}%",
                    f"P50 profit: {pct.p50:.2f}%",
                    f"P95 profit: {pct.p95:.2f}%",
                    f"Prob. profitable: {prob_profit:.1%}",
                ]
                self._render_mc_chart(profits)
            except Exception as exc:
                _log.warning("MC percentile computation failed: %s", exc)

        if self._mc_failed_count:
            summary_lines.append(f"Failed iterations: {self._mc_failed_count}")

        summary = "\n".join(summary_lines)
        self._summary_lbl.setText(summary)
        self._terminal.append_info(f"\n{summary}", theme.GREEN)
        self._terminal.set_status("done", theme.GREEN)
        self._phase = "idle"
        self._set_running(False)

    def _render_mc_chart(self, profits: list[float]) -> None:
        """Render profit distribution histogram."""
        if self._mpl_axes is None or self._mpl_canvas is None:
            return
        try:
            ax = self._mpl_axes
            ax.clear()
            ax.hist(profits, bins=min(30, len(profits)), color=theme.ACCENT, edgecolor="none")
            ax.set_xlabel("Profit %")
            ax.set_ylabel("Count")
            ax.set_title("MC Profit Distribution")
            self._mpl_canvas.draw()
        except Exception as exc:
            _log.warning("MC chart render failed: %s", exc)


    # ------------------------------------------------------------------
    # Parameter Sensitivity workflow (Task 12)
    # ------------------------------------------------------------------

    def _discover_ps_parameters(self) -> None:
        """Triggered by 'Discover Parameters' button (Task 12.1)."""
        strategy_name = self._strategy_combo.currentText().strip()
        if not strategy_name:
            self._terminal.append_info("Select a strategy first.", theme.YELLOW)
            return

        try:
            settings = self._require_settings()
            strategy_path = Path(settings.user_data_path) / "strategies" / f"{strategy_name}.py"
            params = self._parneeds_svc.discover_strategy_parameters(strategy_path)
        except Exception as exc:
            self._terminal.append_info(f"Parameter discovery failed: {exc}", theme.RED)
            return

        self._ps_params = params
        self._ps_param_table.setRowCount(0)

        if not params:
            self._terminal.append_info(
                "No sweepable parameters found for this strategy.", theme.YELLOW
            )
            self._start_btn.setEnabled(False)
            return

        self._start_btn.setEnabled(True)
        for param in params:
            row = self._ps_param_table.rowCount()
            self._ps_param_table.insertRow(row)

            chk = QTableWidgetItem()
            chk.setCheckState(Qt.Unchecked)
            self._ps_param_table.setItem(row, 0, chk)
            self._ps_param_table.setItem(row, 1, QTableWidgetItem(param.name))
            self._ps_param_table.setItem(row, 2, QTableWidgetItem(param.param_type.value))

            if param.param_type in (SweepParamType.INT, SweepParamType.DECIMAL):
                self._ps_param_table.setItem(row, 3, QTableWidgetItem(str(param.min_value or "")))
                self._ps_param_table.setItem(row, 4, QTableWidgetItem(str(param.max_value or "")))
                self._ps_param_table.setItem(row, 5, QTableWidgetItem(str(param.step or "")))
            elif param.param_type in (SweepParamType.CATEGORICAL, SweepParamType.BOOLEAN):
                self._ps_param_table.setItem(row, 5, QTableWidgetItem(",".join(str(v) for v in param.values)))

        self._terminal.append_info(
            f"Discovered {len(params)} parameter(s). Enable and configure ranges, then Start.",
            theme.GREEN,
        )
        self._update_plan_label()

    def _read_ps_params_from_table(self) -> list[SweepParameterDef]:
        """Read enabled parameters and ranges from the PS param table."""
        params: list[SweepParameterDef] = []
        for row in range(self._ps_param_table.rowCount()):
            chk_item = self._ps_param_table.item(row, 0)
            if chk_item is None or chk_item.checkState() != Qt.Checked:
                continue

            name_item = self._ps_param_table.item(row, 1)
            type_item = self._ps_param_table.item(row, 2)
            if not name_item or not type_item:
                continue

            name = name_item.text().strip()
            type_str = type_item.text().strip()

            try:
                param_type = SweepParamType(type_str)
            except ValueError:
                continue

            min_item = self._ps_param_table.item(row, 3)
            max_item = self._ps_param_table.item(row, 4)
            step_item = self._ps_param_table.item(row, 5)

            min_val = self._safe_float(min_item.text() if min_item else None)
            max_val = self._safe_float(max_item.text() if max_item else None)
            step_val = self._safe_float(step_item.text() if step_item else None)

            values: list[Any] = []
            if param_type in (SweepParamType.CATEGORICAL, SweepParamType.BOOLEAN):
                raw = step_item.text() if step_item else ""
                values = [v.strip() for v in raw.split(",") if v.strip()]

            params.append(SweepParameterDef(
                name=name,
                param_type=param_type,
                default_value=None,
                min_value=min_val,
                max_value=max_val,
                step=step_val,
                values=values,
                enabled=True,
            ))
        return params

    def start_param_sensitivity_workflow(self) -> None:
        """Entry point for Parameter Sensitivity workflow (Task 12.2)."""
        if self._running:
            return

        enabled_params = self._read_ps_params_from_table()
        if not enabled_params:
            self._terminal.append_info(
                "No parameters enabled. Use 'Discover Parameters' and enable at least one.",
                theme.YELLOW,
            )
            return

        try:
            cfg = self.build_config()
            self._validate_config(cfg)
        except Exception as exc:
            self._terminal.append_info(f"Cannot start: {exc}", theme.RED)
            return

        baseline: dict[str, Any] = {}
        mode = self._ps_mode_combo.currentText()

        if mode == "Grid":
            sweep_points = self._parneeds_svc.generate_grid_sweep_points(enabled_params, baseline)
            if len(sweep_points) > 200:
                reply = QMessageBox.question(
                    self,
                    "Large Grid Sweep",
                    f"Grid sweep will run {len(sweep_points)} backtests. Continue?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return
        else:
            sweep_points = self._parneeds_svc.generate_oat_sweep_points(enabled_params, baseline)

        if not sweep_points:
            self._terminal.append_info("No sweep points generated. Check parameter ranges.", theme.YELLOW)
            return

        self._active_config = cfg
        self._pending_sweep_points = list(sweep_points)
        self._ps_results = []

        self._terminal.clear()
        self._terminal.set_status("checking", theme.ACCENT)
        self._set_running(True)
        self._plan_lbl.setText(f"Sweep point 0 / {len(sweep_points)}")

        # Candle coverage validation (Req 15.1)
        try:
            reports = self._parneeds_svc.validate_candle_coverage(
                self._require_settings(), cfg
            )
        except Exception as exc:
            self._terminal.append_info(f"Coverage check failed: {exc}", theme.RED)
            self._terminal.set_status("failed", theme.RED)
            self._set_running(False)
            return

        self._append_coverage(reports)
        if self._coverage_has_blocking_gaps(reports):
            self._queue_downloads(cfg, reports)
            self._phase = "ps_download"
            self._start_next_download()
            return

        self._phase = "ps_backtest"
        self._start_next_sweep_point()

    def _start_next_sweep_point(self) -> None:
        """Sequential sweep execution (Task 12.3)."""
        cfg = self._active_config
        if not cfg:
            self._set_running(False)
            return

        if not self._pending_sweep_points:
            self._finish_param_sensitivity()
            return

        point = self._pending_sweep_points.pop(0)
        self._ps_active_point = point
        total = point.index + 1 + len(self._pending_sweep_points)
        done = point.index
        self._plan_lbl.setText(f"Sweep point {done + 1} / {total}")
        self._terminal.append_info(
            f"\n[PS Sweep {done + 1}] {point.label}\n", theme.ACCENT
        )

        # Build extra flags for parameter overrides
        extra_flags: list[str] = []
        for param_name, val in point.param_overrides.items():
            extra_flags += [f"--{param_name}", str(val)]

        try:
            cmd = self._backtest_svc.build_command(
                strategy_name=cfg.strategy,
                timeframe=cfg.timeframe,
                timerange=cfg.timerange,
                pairs=cfg.pairs,
                max_open_trades=cfg.max_open_trades,
                dry_run_wallet=cfg.dry_run_wallet,
                extra_flags=extra_flags,
            )
        except Exception as exc:
            self._terminal.append_info(f"Command failed: {exc}", theme.RED)
            self._start_next_sweep_point()
            return

        self._phase = "ps_backtest"
        self._terminal.set_status("running", theme.GREEN)
        self._start_process(cmd)

    def _handle_sweep_point_finished(self, exit_code: int) -> None:
        """Result parsing and sweep result update (Task 12.4)."""
        point = getattr(self, "_ps_active_point", None)
        cfg = self._active_config

        if not point or not cfg:
            self._start_next_sweep_point()
            return

        if exit_code == 0:
            run_id = ""
            entry: dict = {}
            try:
                settings = self._require_settings()
                export_dir = Path(settings.user_data_path) / "backtest_results"
                run_id = self._backtest_svc.parse_and_save_latest_results(
                    export_dir, cfg.strategy
                ) or ""
                entry = self._find_run_entry(run_id, cfg.strategy)
            except Exception as exc:
                _log.warning("Could not save PS sweep result: %s", exc)

            profit = self._safe_float(entry.get("profit_total_pct"))
            result = ParNeedsRunResult(
                run_trial=f"Sweep {point.index + 1}",
                workflow="param_sensitivity",
                strategy=cfg.strategy,
                pairs=", ".join(cfg.pairs),
                timeframe=cfg.timeframe,
                timerange=cfg.timerange,
                profit_pct=profit,
                win_rate=self._safe_float(entry.get("win_rate_pct")),
                max_dd_pct=self._safe_float(entry.get("max_drawdown_pct")),
                trades=self._safe_int(entry.get("trades_count")),
                status="completed",
                result_path=str(entry.get("result_path", "")),
                log_path=str(entry.get("log_path", "")),
            )
            self._ps_results.append(result)
            self._sig_result.emit(result)
            if run_id:
                self.run_completed.emit(run_id)
        else:
            self._terminal.append_info(
                f"Sweep {point.index + 1} failed (exit {exit_code})", theme.RED
            )
            result = ParNeedsRunResult(
                run_trial=f"Sweep {point.index + 1}",
                workflow="param_sensitivity",
                strategy=cfg.strategy if cfg else "",
                status=f"failed ({exit_code})",
            )
            self._ps_results.append(result)
            self._sig_result.emit(result)

        self._start_next_sweep_point()

    def _finish_param_sensitivity(self) -> None:
        """Chart and best-row highlight (Task 12.5)."""
        results = self._ps_results
        if not results:
            self._terminal.append_info("\nParameter Sensitivity complete (no results).", theme.YELLOW)
            self._terminal.set_status("done", theme.YELLOW)
            self._phase = "idle"
            self._set_running(False)
            return

        # Find best result
        best = max(
            (r for r in results if r.profit_pct is not None),
            key=lambda r: r.profit_pct,  # type: ignore[arg-type]
            default=None,
        )

        summary_lines = [f"Parameter Sensitivity complete ({len(results)} sweep points)"]
        if best:
            summary_lines.append(f"Best: {best.run_trial} — {best.profit_pct:.2f}%")

        summary = "\n".join(summary_lines)
        self._summary_lbl.setText(summary)
        self._terminal.append_info(f"\n{summary}", theme.GREEN)
        self._terminal.set_status("done", theme.GREEN)

        # Highlight best row (Req 10.4)
        if best:
            self._highlight_best_ps_row(best.run_trial)

        # Render chart
        self._render_ps_chart(results)

        self._phase = "idle"
        self._set_running(False)

    def _highlight_best_ps_row(self, run_trial: str) -> None:
        """Highlight the row with the highest Profit % (Req 10.4)."""
        from PySide6.QtGui import QColor
        for row in range(self._results.rowCount()):
            item = self._results.item(row, _COL_RUN_TRIAL)
            if item and item.text() == run_trial:
                for col in range(self._results.columnCount()):
                    cell = self._results.item(row, col)
                    if cell:
                        cell.setBackground(QColor(theme.ACCENT).darker(150))
                break

    def _render_ps_chart(self, results: list[ParNeedsRunResult]) -> None:
        """Render line chart or heatmap for parameter sensitivity."""
        if self._mpl_axes is None or self._mpl_canvas is None:
            return
        try:
            profits = [r.profit_pct for r in results if r.profit_pct is not None]
            labels = [r.run_trial for r in results if r.profit_pct is not None]
            ax = self._mpl_axes
            ax.clear()
            ax.plot(range(len(profits)), profits, marker="o", color=theme.ACCENT)
            ax.set_xlabel("Sweep Point")
            ax.set_ylabel("Profit %")
            ax.set_title("Parameter Sensitivity")
            self._mpl_canvas.draw()
        except Exception as exc:
            _log.warning("PS chart render failed: %s", exc)


    # ------------------------------------------------------------------
    # Export (Task 13)
    # ------------------------------------------------------------------

    @Slot()
    def _export_results(self) -> None:
        """Export all results to JSON and CSV (Task 13)."""
        if not self._all_results:
            self._terminal.append_info("No results to export.", theme.YELLOW)
            return

        workflow_idx = self._workflow_combo.currentIndex()
        workflow_labels = ["timerange", "walk_forward", "monte_carlo", "param_sensitivity"]
        workflow = workflow_labels[workflow_idx] if workflow_idx < len(workflow_labels) else "unknown"

        try:
            settings = self._require_settings()
            export_dir = Path(settings.user_data_path) / "backtest_results" / "parneeds_exports"
        except Exception:
            export_dir = Path.home() / "parneeds_exports"

        try:
            json_path, csv_path = self._parneeds_svc.export_results(
                self._all_results, workflow, export_dir
            )
            self._terminal.append_info(f"Exported JSON: {json_path}", theme.GREEN)
            self._terminal.append_info(f"Exported CSV:  {csv_path}", theme.GREEN)
        except Exception as exc:
            _log.error("Export failed: %s", exc)
            self._terminal.append_info(f"Export failed: {exc}", theme.RED)

    # ------------------------------------------------------------------
    # Shared result row handling
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_result_received(self, result: ParNeedsRunResult) -> None:
        """Buffer incoming results for batched flush."""
        self._pending_results.append(result)

    def _flush_pending_updates(self) -> None:
        """Batch-write pending result rows to the table (500 ms timer)."""
        if not self._pending_results:
            return
        for result in self._pending_results:
            self._append_result_row(result)
        self._pending_results.clear()

    def _append_result_row(self, result: ParNeedsRunResult) -> None:
        """Append one ParNeedsRunResult to the shared 17-column table."""
        self._all_results.append(result)
        row = self._results.rowCount()
        self._results.insertRow(row)

        values = [
            result.run_trial,
            result.workflow,
            result.strategy,
            result.pairs,
            result.timeframe,
            result.timerange,
            self._fmt_float(result.profit_pct),
            self._fmt_float(result.total_profit),
            self._fmt_float(result.win_rate),
            self._fmt_float(result.max_dd_pct),
            self._fmt_int(result.trades),
            self._fmt_float(result.profit_factor),
            self._fmt_float(result.sharpe_ratio),
            self._fmt_float(result.score),
            result.status,
            result.result_path,
            result.log_path,
        ]
        for col, value in enumerate(values):
            self._results.setItem(row, col, QTableWidgetItem(str(value) if value is not None else "-"))

        # Enable export button when table has rows
        self._export_btn.setEnabled(self._results.rowCount() > 0)

    # ------------------------------------------------------------------
    # Timerange workflow helpers (preserved)
    # ------------------------------------------------------------------

    def _start_next_backtest(self) -> None:
        if not self._active_config:
            self._set_running(False)
            return
        if not self._pending_windows:
            self._terminal.append_info("\nParNeeds timerange workflow completed.", theme.GREEN)
            self._terminal.set_status("done", theme.GREEN)
            self._phase = "idle"
            self._set_running(False)
            return

        self._active_window = self._pending_windows.pop(0)
        window = self._active_window
        cfg = self._active_config
        try:
            cmd = self._backtest_svc.build_command(
                strategy_name=cfg.strategy,
                timeframe=cfg.timeframe,
                timerange=window.timerange,
                pairs=cfg.pairs,
                max_open_trades=cfg.max_open_trades,
                dry_run_wallet=cfg.dry_run_wallet,
            )
        except Exception as exc:
            self._terminal.append_info(f"Backtest command failed: {exc}", theme.RED)
            self._start_next_backtest()
            return

        done = self._results.rowCount()
        total = done + 1 + len(self._pending_windows)
        self._plan_lbl.setText(f"Running window {done + 1} of {total}: {window.timerange}")
        self._phase = "backtest"
        self._terminal.set_status("running", theme.GREEN)
        self._terminal.append_info(f"\n[{window.label}] {window.timerange}\n", theme.ACCENT)
        self._start_process(cmd)

    def _handle_backtest_finished(self, exit_code: int) -> None:
        window = self._active_window
        cfg = self._active_config
        if not window or not cfg:
            self._set_running(False)
            return

        if exit_code == 0:
            run_id = ""
            entry: dict = {}
            try:
                settings = self._require_settings()
                export_dir = Path(settings.user_data_path) / "backtest_results"
                run_id = self._backtest_svc.parse_and_save_latest_results(
                    export_dir, cfg.strategy
                ) or ""
                entry = self._find_run_entry(run_id, cfg.strategy)
            except Exception as exc:
                _log.warning("Could not save ParNeeds backtest result: %s", exc)

            result = ParNeedsRunResult(
                run_trial=window.label,
                workflow="timerange",
                strategy=cfg.strategy,
                pairs=", ".join(cfg.pairs),
                timeframe=cfg.timeframe,
                timerange=window.timerange,
                profit_pct=self._safe_float(entry.get("profit_total_pct")),
                win_rate=self._safe_float(entry.get("win_rate_pct")),
                max_dd_pct=self._safe_float(entry.get("max_drawdown_pct")),
                trades=self._safe_int(entry.get("trades_count")),
                status="completed",
                result_path=str(entry.get("result_path", "")),
                log_path=str(entry.get("log_path", "")),
            )
            self._sig_result.emit(result)
            if run_id:
                self.run_completed.emit(run_id)
        else:
            result = ParNeedsRunResult(
                run_trial=window.label,
                workflow="timerange",
                strategy=cfg.strategy,
                timerange=window.timerange,
                status=f"failed ({exit_code})",
            )
            self._sig_result.emit(result)

        self._active_window = None
        self._start_next_backtest()

    # ------------------------------------------------------------------
    # Download helpers (preserved)
    # ------------------------------------------------------------------

    def _queue_downloads(
        self,
        config: ParNeedsConfig,
        reports: list[CandleCoverageReport],
    ) -> None:
        append_pairs: list[str] = []
        prepend_pairs: list[str] = []
        for report in reports:
            if report.is_complete:
                continue
            reasons = " ".join(report.missing_reasons)
            if "no candles found" in reasons or "missing end" in reasons:
                append_pairs.append(report.pair)
            if "missing start" in reasons:
                prepend_pairs.append(report.pair)

        self._download_queue = []
        if append_pairs:
            self._download_queue.append((False, self._dedupe(append_pairs), "append missing end candles"))
        if prepend_pairs:
            self._download_queue.append((True, self._dedupe(prepend_pairs), "prepend missing start candles"))

        if not self._download_queue:
            self._download_queue.append((False, list(config.pairs), "refresh missing candles"))

    def _start_next_download(self) -> None:
        if not self._active_config:
            self._set_running(False)
            return
        if not self._download_queue:
            self._recheck_coverage_after_downloads()
            return

        prepend, pairs, label = self._download_queue.pop(0)
        self._start_download(self._active_config, prepend=prepend, pairs=pairs, label=label)

    def _start_download(
        self,
        config: ParNeedsConfig,
        *,
        prepend: bool,
        pairs: list[str],
        label: str,
    ) -> None:
        try:
            cmd = self._download_svc.build_command(
                timeframe=config.timeframe,
                timerange=config.timerange,
                pairs=pairs,
                prepend=prepend,
                erase=False,
            )
        except Exception as exc:
            self._terminal.append_info(f"Download command failed: {exc}", theme.RED)
            self._terminal.set_status("failed", theme.RED)
            self._set_running(False)
            return

        # Preserve the current phase prefix so _handle_finished routes correctly.
        # For the timerange workflow the phase is plain "download"; for the new
        # workflows it is already set to "wf_download", "mc_download", etc.
        if self._phase not in ("wf_download", "mc_download", "ps_download"):
            self._phase = "download"

        self._terminal.set_status("downloading", theme.ACCENT)
        mode = "--prepend" if prepend else "append"
        self._terminal.append_info(
            f"\nMissing candles found. Auto-download started ({label}, {mode}: {', '.join(pairs)}).\n",
            theme.YELLOW,
        )
        self._start_process(cmd)

    def _handle_download_finished(self, exit_code: int) -> None:
        if exit_code != 0:
            self._terminal.append_info(f"\nDownload failed (exit {exit_code}).", theme.RED)
            self._terminal.set_status("failed", theme.RED)
            self._set_running(False)
            return

        if self._download_queue:
            self._terminal.append_info("\nDownload step completed. Continuing queued downloads.\n", theme.GREEN)
            self._start_next_download()
            return

        self._terminal.append_info("\nDownload completed. Rechecking coverage.\n", theme.GREEN)
        self._recheck_coverage_after_downloads()

    def _recheck_coverage_after_downloads(self) -> None:
        cfg = self._active_config
        if not cfg:
            self._set_running(False)
            return
        try:
            reports = self._parneeds_svc.validate_candle_coverage(
                self._require_settings(), cfg
            )
        except Exception as exc:
            self._terminal.append_info(f"Coverage recheck failed: {exc}", theme.RED)
            self._terminal.set_status("failed", theme.RED)
            self._set_running(False)
            return

        self._append_coverage(reports)
        if self._coverage_has_blocking_gaps(reports, allow_late_start=True):
            self._terminal.append_info(
                "\nCoverage still has gaps after download. Backtests were not started.",
                theme.RED,
            )
            self._terminal.set_status("failed", theme.RED)
            self._set_running(False)
            return

        # Route back to the correct workflow
        if self._phase == "wf_download":
            self._phase = "wf_backtest"
            self._start_next_wf_backtest()
        elif self._phase == "mc_download":
            self._phase = "mc_backtest"
            self._start_next_mc_iteration()
        elif self._phase == "ps_download":
            self._phase = "ps_backtest"
            self._start_next_sweep_point()
        else:
            self._start_next_backtest()

    # ------------------------------------------------------------------
    # Process management
    # ------------------------------------------------------------------

    def _start_process(self, cmd) -> None:
        self._terminal.append_info(f"$ {cmd.to_display_string()}\n\n", theme.ACCENT)
        run = self._process_manager.start_run(cmd)
        self._current_run_id = run.run_id
        self._adapter = ProcessRunAdapter(run, parent=self)
        self._adapter.stdout_received.connect(self._sig_stdout.emit)
        self._adapter.stderr_received.connect(self._sig_stderr.emit)
        self._adapter.run_finished.connect(self._sig_finished.emit)
        self._adapter.start()

    def _stop(self) -> None:
        """Cancel active subprocess and halt all pending work (Task 14)."""
        if self._current_run_id:
            try:
                self._process_manager.stop_run(self._current_run_id)
            except (KeyError, ValueError):
                pass
        if self._adapter:
            self._adapter.stop()
            self._adapter = None

        self._terminal.append_info("\nStopped by user.", theme.YELLOW)
        self._terminal.set_status("stopped", theme.YELLOW)

        # Clear all pending queues
        self._pending_windows.clear()
        self._download_queue.clear()
        self._pending_wf_items.clear()
        self._mc_iteration_index = self._mc_config.n_iterations if self._mc_config else 0
        self._pending_sweep_points.clear()

        self._phase = "idle"
        self._set_running(False)

    @Slot(int)
    def _handle_finished(self, exit_code: int) -> None:
        if self._phase == "download":
            self._handle_download_finished(exit_code)
        elif self._phase in ("wf_download", "mc_download", "ps_download"):
            self._handle_download_finished(exit_code)
        elif self._phase == "backtest":
            self._handle_backtest_finished(exit_code)
        elif self._phase == "wf_backtest":
            self._handle_wf_backtest_finished(exit_code)
        elif self._phase == "mc_backtest":
            self._handle_mc_iteration_finished(exit_code)
        elif self._phase == "ps_backtest":
            self._handle_sweep_point_finished(exit_code)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_config(self, config: ParNeedsConfig) -> None:
        if not config.strategy:
            raise ValueError("strategy is required")
        if not config.timeframe:
            raise ValueError("timeframe is required")
        if not config.pairs:
            raise ValueError("at least one pair is required for candle validation")

    def _validate_config_base(self, config) -> None:
        """Validate any config object that has strategy/timeframe/pairs."""
        if not getattr(config, "strategy", ""):
            raise ValueError("strategy is required")
        if not getattr(config, "timeframe", ""):
            raise ValueError("timeframe is required")
        if not getattr(config, "pairs", []):
            raise ValueError("at least one pair is required")

    def _require_settings(self):
        settings = self._state.current_settings
        if not settings or not settings.python_executable:
            raise ValueError("settings are not configured")
        return settings

    # ------------------------------------------------------------------
    # Coverage helpers (preserved)
    # ------------------------------------------------------------------

    def _append_coverage(self, reports: list[CandleCoverageReport]) -> None:
        for report in reports:
            if report.is_complete:
                self._terminal.append_info(
                    f"Coverage OK: {report.pair} {report.timeframe} "
                    f"{report.first_candle} -> {report.last_candle} "
                    f"({report.actual_candles}/{report.expected_candles})",
                    theme.GREEN,
                )
            elif self._is_late_start_only(report):
                self._terminal.append_info(
                    f"Coverage usable: {report.pair} {report.timeframe} starts at "
                    f"{report.first_candle}; treating requested earlier candles as unavailable.",
                    theme.YELLOW,
                )
            else:
                self._terminal.append_info(
                    f"Coverage missing: {report.pair} {report.timeframe} "
                    f"{'; '.join(report.missing_reasons)} "
                    f"({report.actual_candles}/{report.expected_candles})",
                    theme.YELLOW,
                )

    def _coverage_has_blocking_gaps(
        self,
        reports: list[CandleCoverageReport],
        *,
        allow_late_start: bool = False,
    ) -> bool:
        for report in reports:
            if report.is_complete:
                continue
            if allow_late_start and self._is_late_start_only(report):
                continue
            return True
        return False

    def _is_late_start_only(self, report: CandleCoverageReport) -> bool:
        reasons = set(report.missing_reasons)
        return (
            bool(report.first_candle)
            and report.actual_candles > 0
            and report.gap_count == 0
            and reasons.issubset({"missing start candles", "candle count below expected"})
        )

    def _dedupe(self, pairs: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for pair in pairs:
            if pair not in seen:
                seen.add(pair)
                unique.append(pair)
        return unique

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    def _request_sync(self) -> None:
        parent = self.window()
        backtest_page = getattr(parent, "backtest_page", None)
        if backtest_page and hasattr(backtest_page, "get_run_config"):
            self.sync_from_backtest(backtest_page.get_run_config())

    def _find_run_entry(self, run_id: str, strategy: str) -> dict:
        if not run_id:
            return {}
        settings = self._require_settings()
        results_dir = str(Path(settings.user_data_path) / "backtest_results")
        for entry in self._backtest_svc.get_strategy_runs(results_dir, strategy):
            if entry.get("run_id") == run_id:
                return entry
        return {}

    def _set_running(self, running: bool) -> None:
        self._running = running
        self._start_btn.setEnabled(not running)
        self._sync_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        if not running:
            self._current_run_id = None
            self._adapter = None

    def _load_strategies(self) -> None:
        try:
            strategies = self._backtest_svc.get_available_strategies()
            self._strategy_combo.clear()
            self._strategy_combo.addItems(strategies)
        except Exception as exc:
            _log.warning("Could not load ParNeeds strategies: %s", exc)

    def _update_plan_label(self) -> None:
        idx = self._workflow_combo.currentIndex()
        try:
            if idx == _WF_TIMERANGE:
                cfg = self.build_config()
                windows = self._parneeds_svc.generate_timerange_windows(cfg)
                self._plan_lbl.setText(f"{len(windows)} windows planned across {cfg.timerange}.")
            elif idx == _WF_WALK_FORWARD:
                wf_cfg = self._build_wf_config()
                folds = self._parneeds_svc.generate_walk_forward_folds(wf_cfg)
                self._plan_lbl.setText(
                    f"{len(folds)} folds planned ({self._wf_mode_combo.currentText()})."
                )
            elif idx == _WF_MONTE_CARLO:
                n = self._mc_iterations_spin.value()
                self._plan_lbl.setText(f"{n} Monte Carlo iterations planned.")
            elif idx == _WF_PARAM_SENSITIVITY:
                mode = self._ps_mode_combo.currentText()
                self._plan_lbl.setText(f"Parameter Sensitivity ({mode}) — discover parameters to plan.")
        except Exception:
            self._plan_lbl.setText("Config is incomplete.")

    def _section(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {theme.TEXT_SECONDARY};"
            " margin-top: 4px;"
        )
        return label

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
        return label

    def _fmt_float(self, value) -> str:
        if value is None or value == "":
            return "-"
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "-"

    def _fmt_int(self, value) -> str:
        if value is None or value == "":
            return "-"
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return "-"

    def _safe_float(self, value) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _safe_int(self, value) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
