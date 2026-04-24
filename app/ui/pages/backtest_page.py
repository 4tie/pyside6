"""backtest_page.py — Backtest configuration and execution page.

Provides a two-panel layout: left panel for run configuration, right panel
for tabbed results and terminal output. Supports run picker for loading
saved runs and live command preview.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.app_state.settings_state import SettingsState
from app.core.backtests.results_store import RunStore
from app.core.services.backtest_service import BacktestService
from app.core.utils.app_logger import get_logger
from app.ui.dialogs.pairs_selector_dialog import PairsSelectorDialog
from app.ui.utils import SplitterStateMixin
from app.ui.widgets.backtest_results_widget import BacktestResultsWidget
from app.ui.widgets.run_config_form import RunConfigForm
from app.ui.widgets.section_header import SectionHeader
from app.ui.widgets.terminal_widget import TerminalWidget

_log = get_logger("ui.backtest_page")

_SPLITTER_KEY = "splitter/backtest"


class BacktestPage(QWidget, SplitterStateMixin):
    """Backtest configuration and execution page.

    Args:
        settings_state: Application settings state.
        parent: Optional parent widget.

    Signals:
        loop_completed: Emitted when a backtest finishes successfully.
    """

    loop_completed = Signal()

    def __init__(self, settings_state: SettingsState, parent=None) -> None:
        super().__init__(parent)
        self._settings_state = settings_state
        self._backtest_service = BacktestService(settings_state.settings_service)
        self._run_start_time: Optional[float] = None
        self._restoring: bool = False  # guard against save-during-restore
        self._build_ui()
        self._connect_signals()
        self._restore_state()
        self._restore_preferences()  # load saved strategy/timeframe/pairs/timerange

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the two-panel splitter layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Page title
        title_bar = QWidget()
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 12, 16, 8)
        title_label = QLabel("Backtest")
        title_label.setObjectName("page_title")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        root.addWidget(title_bar)

        # Main splitter
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(4)
        self._splitter_key = _SPLITTER_KEY
        self._splitter_default_sizes = [300, 900]
        root.addWidget(self._splitter, 1)

        # ── Left panel ─────────────────────────────────────────────────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(240)
        left_scroll.setMaximumWidth(360)
        left_scroll.setObjectName("left_panel_scroll")

        left_content = QWidget()
        left_content.setObjectName("left_panel_content")
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        # Run config form
        self.run_config_form = RunConfigForm(self._settings_state)
        left_layout.addWidget(self.run_config_form)

        # Advanced options (collapsible)
        advanced_widget = QWidget()
        advanced_form = QFormLayout(advanced_widget)
        advanced_form.setContentsMargins(8, 4, 8, 4)

        self._wallet_spin = QDoubleSpinBox()
        self._wallet_spin.setRange(0.0, 1_000_000.0)
        self._wallet_spin.setValue(1000.0)
        self._wallet_spin.setDecimals(2)
        self._wallet_spin.setAccessibleName("Dry-run wallet size")
        self._wallet_spin.setToolTip("Starting wallet balance for the dry-run simulation")
        self._wallet_spin.setWhatsThis(
            "The starting balance for the simulated dry-run. "
            "Freqtrade uses this to calculate position sizes."
        )
        advanced_form.addRow("Wallet:", self._wallet_spin)

        self._max_trades_spin = QSpinBox()
        self._max_trades_spin.setRange(1, 999)
        self._max_trades_spin.setValue(3)
        self._max_trades_spin.setAccessibleName("Max open trades")
        self._max_trades_spin.setToolTip("Maximum number of simultaneously open trades")
        self._max_trades_spin.setWhatsThis(
            "Maximum number of trades that can be open simultaneously during the backtest."
        )
        advanced_form.addRow("Max Trades:", self._max_trades_spin)

        self._advanced_section = SectionHeader(
            "Advanced Options", advanced_widget, collapsed=True
        )
        left_layout.addWidget(self._advanced_section)

        # Command preview (collapsible)
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(8, 4, 8, 4)

        self._cmd_preview_label = QLabel("")
        mono_font = QFont("Consolas, Menlo, Courier New, monospace")
        mono_font.setPointSize(9)
        self._cmd_preview_label.setFont(mono_font)
        self._cmd_preview_label.setWordWrap(True)
        self._cmd_preview_label.setObjectName("hint_label")
        preview_layout.addWidget(self._cmd_preview_label)

        self._preview_section = SectionHeader(
            "Command Preview", preview_widget, collapsed=True
        )
        left_layout.addWidget(self._preview_section)

        # Run / Stop buttons
        btn_row = QHBoxLayout()
        self._run_btn = QPushButton("Run")
        self._run_btn.setObjectName("success")
        self._run_btn.setAccessibleName("Run backtest")
        self._run_btn.setToolTip("Validate configuration and start the backtest")
        self._run_btn.setWhatsThis(
            "Validates the configuration and starts the backtest. "
            "Results appear in the Results tab when complete."
        )

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("danger")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setAccessibleName("Stop backtest")
        self._stop_btn.setToolTip("Terminate the running backtest process")

        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        left_layout.addLayout(btn_row)
        left_layout.addStretch()

        # Tab order for keyboard navigation
        QWidget.setTabOrder(self._wallet_spin, self._max_trades_spin)
        QWidget.setTabOrder(self._max_trades_spin, self._run_btn)
        QWidget.setTabOrder(self._run_btn, self._stop_btn)

        left_scroll.setWidget(left_content)
        self._splitter.addWidget(left_scroll)

        # ── Right panel ────────────────────────────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        # Run picker toolbar
        picker_bar = QHBoxLayout()
        picker_bar.setContentsMargins(8, 8, 8, 4)
        picker_label = QLabel("Load run:")
        picker_bar.addWidget(picker_label)

        self._run_picker = QComboBox()
        self._run_picker.setAccessibleName("Saved runs picker")
        self._run_picker.setToolTip("Select a previously saved backtest run to load")
        picker_bar.addWidget(self._run_picker, 1)

        self._load_btn = QPushButton("Load")
        self._load_btn.setAccessibleName("Load selected run")
        self._load_btn.setToolTip("Load the selected run into the Results tab")
        picker_bar.addWidget(self._load_btn)
        right_layout.addLayout(picker_bar)

        # Tab widget
        self._tabs = QTabWidget()
        self._results_widget = BacktestResultsWidget()
        self._terminal = TerminalWidget()

        self._tabs.addTab(self._results_widget, "Results")
        self._tabs.addTab(self._terminal, "Terminal")
        right_layout.addWidget(self._tabs)

        self._splitter.addWidget(right_widget)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 3)
        self._splitter.setSizes([300, 900])

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Wire all internal signals."""
        self._run_btn.clicked.connect(self._on_run_clicked)
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        self._load_btn.clicked.connect(self._on_load_clicked)
        self._terminal.process_finished.connect(self._on_process_finished)
        self.run_config_form.config_changed.connect(self._on_config_changed)
        self._wallet_spin.valueChanged.connect(self._on_advanced_changed)
        self._max_trades_spin.valueChanged.connect(self._on_advanced_changed)
        self._settings_state.settings_changed.connect(self._on_settings_changed)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_run_clicked(self) -> None:
        """Validate form and start backtest."""
        errors = self.run_config_form.validate()
        if errors:
            QMessageBox.warning(self, "Configuration Error", "\n".join(errors))
            return

        cfg = self.run_config_form.get_config()
        strategy = cfg["strategy"]
        timeframe = cfg["timeframe"]
        timerange = cfg.get("timerange") or None
        pairs = cfg.get("pairs") or []
        wallet = self._wallet_spin.value()
        max_trades = self._max_trades_spin.value()

        try:
            cmd = self._backtest_service.build_command(
                strategy_name=strategy,
                timeframe=timeframe,
                timerange=timerange,
                pairs=pairs,
                max_open_trades=max_trades,
                dry_run_wallet=wallet,
            )
        except Exception as e:
            QMessageBox.critical(self, "Command Build Error", str(e))
            _log.error("Failed to build backtest command: %s", e)
            return

        import time
        self._run_start_time = time.time()

        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._tabs.setCurrentWidget(self._terminal)

        settings = self._settings_state.current_settings
        env = None
        if settings and settings.venv_path:
            from app.core.services.process_service import ProcessService
            env = ProcessService.build_environment(settings.venv_path)

        self._terminal.run_command(cmd.as_list(), env=env)
        _log.info("Backtest started: strategy=%s timeframe=%s", strategy, timeframe)

    def _on_stop_clicked(self) -> None:
        """Stop the running backtest."""
        self._terminal.stop_process()
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        _log.info("Backtest stopped by user")

    def _on_process_finished(self, exit_code: int) -> None:
        """Handle backtest process completion."""
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

        if exit_code != 0:
            _log.warning("Backtest exited with code %d", exit_code)
            return

        # Use shared service method to parse and save results
        cfg = self.run_config_form.get_config()
        strategy = cfg.get("strategy", "")
        
        run_id = self._backtest_service.parse_and_save_latest_results(
            export_dir=Path(self._settings_state.current_settings.user_data_path) / "backtest_results",
            strategy_name=strategy,
        )
        
        if run_id:
            # Load and display the saved results
            try:
                results_dir = Path(self._settings_state.current_settings.user_data_path) / "backtest_results"
                run_dir = results_dir / strategy / run_id
                results = RunStore.load_run(run_dir)
                self._results_widget.display_results(results, export_dir=str(run_dir))
                self._tabs.setCurrentWidget(self._results_widget)
                self._refresh_run_picker()
                _log.info("Backtest results loaded: strategy=%s run_id=%s", strategy, run_id)
            except Exception as e:
                _log.error("Failed to load saved backtest results: %s", e)
        else:
            _log.warning("Failed to parse or save backtest results")
        
        self.loop_completed.emit()

    def _on_load_clicked(self) -> None:
        """Load the selected run from the run picker."""
        run_dir_str: Optional[str] = self._run_picker.currentData()
        if not run_dir_str:
            return
        try:
            run_dir = Path(run_dir_str)
            results = RunStore.load_run(run_dir)
            self._results_widget.display_results(results, export_dir=str(run_dir))
            self._tabs.setCurrentWidget(self._results_widget)
            _log.info("Loaded run from %s", run_dir)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load run:\n{e}")
            _log.error("Failed to load run: %s", e)

    def _on_config_changed(self, cfg: dict) -> None:
        """Update command preview when config changes and persist preferences."""
        self._update_command_preview(cfg)
        self._refresh_run_picker()
        if not self._restoring:
            self._save_preferences()

    def _on_advanced_changed(self, _=None) -> None:
        """Update command preview and persist preferences when wallet or max-trades changes."""
        self._update_command_preview()
        if not self._restoring:
            self._save_preferences()

    def _on_settings_changed(self, _=None) -> None:
        """Refresh run picker when settings change (skip if we triggered the save)."""
        if not self._restoring:
            self._refresh_run_picker()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_current_config(self) -> dict:
        """Return the current run configuration including wallet and max trades."""
        cfg = self.run_config_form.get_config()
        cfg["dry_run_wallet"] = self._wallet_spin.value()
        cfg["max_open_trades"] = self._max_trades_spin.value()
        return cfg

    def set_strategy(self, strategy_name: str) -> None:
        """Pre-select a strategy (called from StrategyPage).

        Args:
            strategy_name: The strategy name to pre-select.
        """
        self.run_config_form.set_config({"strategy": strategy_name})
        self._refresh_run_picker()
        _log.debug("Strategy pre-selected: %s", strategy_name)

    def _on_select_pairs(self) -> None:
        """Open PairsSelectorDialog directly (compatibility method for tests).

        Delegates to the RunConfigForm's pairs button handler.
        """
        settings = self._settings_state.current_settings
        favorites: list = []
        if settings is not None:
            favorites = list(settings.favorite_pairs or [])

        selected = self.run_config_form.get_config().get("pairs", [])
        dlg = PairsSelectorDialog(
            favorites=favorites,
            selected=list(selected),
            settings_state=self._settings_state,
            parent=self,
        )
        if dlg.exec():
            new_pairs = dlg.get_selected_pairs()
            self.run_config_form.set_config({"pairs": new_pairs})

    def _save_preferences(self) -> None:
        """Persist current form values to AppSettings.backtest_preferences."""
        if self._restoring:
            return
        settings = self._settings_state.current_settings
        if settings is None:
            return
        cfg = self.run_config_form.get_config()
        prefs = settings.backtest_preferences.model_copy(update={
            "last_strategy": cfg.get("strategy", ""),
            "default_timeframe": cfg.get("timeframe", ""),
            "default_timerange": cfg.get("timerange", ""),
            "default_pairs": ",".join(cfg.get("pairs", [])),
            "dry_run_wallet": self._wallet_spin.value(),
            "max_open_trades": self._max_trades_spin.value(),
        })
        updated = settings.model_copy(update={"backtest_preferences": prefs})
        # Block settings_changed from triggering another save cycle
        self._restoring = True
        try:
            self._settings_state.save_settings(updated)
        finally:
            self._restoring = False
        _log.debug("Backtest preferences saved")

    # Backward-compatibility alias used by tests
    _save_preferences_to_settings = _save_preferences

    def _restore_preferences(self) -> None:
        """Restore form values from AppSettings.backtest_preferences."""
        settings = self._settings_state.current_settings
        if settings is None:
            return
        self._restoring = True
        try:
            prefs = settings.backtest_preferences
            pairs = [p.strip() for p in prefs.default_pairs.split(",") if p.strip()]
            self.run_config_form.set_config({
                "strategy": prefs.last_strategy,
                "timeframe": prefs.default_timeframe,
                "timerange": prefs.default_timerange,
                "pairs": pairs,
            })
            self._wallet_spin.setValue(prefs.dry_run_wallet)
            self._max_trades_spin.setValue(prefs.max_open_trades)
            self._refresh_run_picker()
            _log.debug("Backtest preferences restored: strategy=%s timeframe=%s",
                       prefs.last_strategy, prefs.default_timeframe)
        finally:
            self._restoring = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _update_command_preview(self, cfg: Optional[dict] = None) -> None:
        """Rebuild and display the CLI command preview."""
        if cfg is None:
            cfg = self.run_config_form.get_config()

        strategy = cfg.get("strategy", "")
        timeframe = cfg.get("timeframe", "")
        if not strategy or not timeframe:
            self._cmd_preview_label.setText("(fill in strategy and timeframe)")
            return

        try:
            cmd = self._backtest_service.build_command(
                strategy_name=strategy,
                timeframe=timeframe,
                timerange=cfg.get("timerange") or None,
                pairs=cfg.get("pairs") or [],
                max_open_trades=self._max_trades_spin.value(),
                dry_run_wallet=self._wallet_spin.value(),
            )
            self._cmd_preview_label.setText(" ".join(cmd.as_list()))
        except Exception as e:
            _log.debug("Command preview unavailable: %s", e)
            self._cmd_preview_label.setText("(unable to build preview)")

    def _refresh_run_picker(self) -> None:
        """Repopulate the run picker for the currently selected strategy."""
        settings = self._settings_state.current_settings
        if not settings or not settings.user_data_path:
            self._run_picker.clear()
            return

        cfg = self.run_config_form.get_config()
        strategy = cfg.get("strategy", "")
        backtest_results_dir = str(Path(settings.user_data_path) / "backtest_results")

        self._run_picker.blockSignals(True)
        self._run_picker.clear()

        try:
            runs = self._backtest_service.get_strategy_runs(backtest_results_dir, strategy)
            for run in runs:
                run_id = run.get("run_id", "?")
                profit = run.get("profit_total_pct", 0.0)
                trades = run.get("trades_count", 0)
                saved = run.get("saved_at", "")[:16].replace("T", " ")
                label = f"{run_id}  {profit:+.2f}%  {trades}T  {saved}"
                run_dir = str(
                    Path(backtest_results_dir) / run.get("run_dir", run_id)
                )
                self._run_picker.addItem(label, userData=run_dir)
        except Exception as e:
            _log.warning("Failed to refresh run picker: %s", e)

        self._run_picker.blockSignals(False)

