"""BacktestPage for the v2 UI layer.

Two-panel layout: ``RunConfigForm`` on the left, tabbed output (Results +
Terminal) on the right, separated by a ``QSplitter``.  Wired to
``BacktestService`` and ``ProcessService`` for live command execution.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.6
"""
import time
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.app_state.settings_state import SettingsState
from app.core.backtests.results_index import IndexStore
from app.core.backtests.results_models import BacktestResults
from app.core.backtests.results_parser import parse_backtest_zip
from app.core.backtests.results_store import RunStore
from app.core.services.backtest_service import BacktestService
from app.core.services.comparison_service import ComparisonService
from app.core.services.pair_analysis_service import PairAnalysisService
from app.core.services.process_service import ProcessService
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger
from app.ui.widgets.backtest_results_widget import BacktestResultsWidget
from app.ui.widgets.terminal_widget import TerminalWidget
from app.ui_v2.widgets.compare_widget import CompareWidget
from app.ui_v2.widgets.pair_results_widget import PairResultsWidget
from app.ui_v2.widgets.run_config_form import RunConfigForm
from app.ui_v2.widgets.section_header import SectionHeader

_log = get_logger("ui_v2.pages.backtest_page")

_SETTINGS_KEY = "splitter/backtest"


class BacktestPage(QWidget):
    """Redesigned backtest page using a ``QSplitter`` layout.

    Left panel holds a ``RunConfigForm`` (strategy / timeframe / timerange /
    pairs) plus an advanced options group and Run/Stop buttons.  Right panel
    holds a ``QTabWidget`` with a "Results" tab (``BacktestResultsWidget``)
    and a "Terminal" tab (``TerminalWidget``), preceded by a run-picker
    toolbar.

    Args:
        settings_state: Application settings state.
        parent: Optional parent widget.

    Signals:
        loop_completed(): Emitted when a backtest process finishes.
    """

    loop_completed = Signal()

    def __init__(self, settings_state: SettingsState, parent=None) -> None:
        super().__init__(parent)

        self.settings_state = settings_state
        self._settings_service = SettingsService()
        self._backtest_service = BacktestService(self._settings_service)
        self._process_service = ProcessService()

        self._last_run_config_path: Optional[str] = None
        self._run_started_at: float = 0.0
        self._initializing: bool = True

        self._build_ui()
        self._connect_signals()
        self._refresh_strategies()
        self._load_preferences()
        self._initializing = False
        self._update_command_preview()
        self._rebuild_index_from_zips()
        self._refresh_run_picker()

        # Keep command preview timestamp current
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(1000)
        self._preview_timer.timeout.connect(self._update_command_preview)
        self._preview_timer.start()

        # Restore splitter state
        self._restore_splitter()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the splitter-based layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(4)
        self._splitter.setChildrenCollapsible(False)

        # ── Left panel ────────────────────────────────────────────────
        left_widget = self._build_left_panel()
        self._splitter.addWidget(left_widget)

        # ── Right panel ───────────────────────────────────────────────
        right_widget = self._build_right_panel()
        self._splitter.addWidget(right_widget)

        # Default proportions: 35% left, 65% right
        self._splitter.setStretchFactor(0, 35)
        self._splitter.setStretchFactor(1, 65)

        root.addWidget(self._splitter)

    def _build_left_panel(self) -> QWidget:
        """Build the left configuration panel.

        Returns:
            Scroll-wrapped widget containing ``RunConfigForm``, advanced
            options, and Run/Stop buttons.
        """
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Page title
        title = QLabel("Backtest")
        title.setObjectName("page_title")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # RunConfigForm (strategy / timeframe / timerange / pairs)
        self.run_config_form = RunConfigForm(
            settings_state=self.settings_state,
            show_strategy=True,
            show_timeframe=True,
            show_timerange=True,
            show_pairs=True,
        )
        layout.addWidget(self.run_config_form)

        # Advanced options (collapsible via SectionHeader)
        advanced_body = self._build_advanced_body()
        self._advanced_section = SectionHeader(
            title="Advanced Options",
            body=advanced_body,
            collapsed=True,
        )
        layout.addWidget(self._advanced_section)

        # Command preview (collapsible via SectionHeader)
        self._preview_label = QLabel()
        self._preview_label.setWordWrap(True)
        self._preview_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._preview_label.setStyleSheet(
            "font-family: monospace; font-size: 11px; color: #aaa;"
        )
        self._preview_label.setAccessibleName("Command preview")
        preview_section = SectionHeader(
            title="Command Preview",
            body=self._preview_label,
            collapsed=True,
        )
        layout.addWidget(preview_section)

        # Run / Stop buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._run_btn = QPushButton("Run")
        self._run_btn.setAccessibleName("Run backtest")
        self._run_btn.setToolTip("Start the backtest with the current configuration")
        self._run_btn.clicked.connect(self._run_backtest)
        btn_layout.addWidget(self._run_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setAccessibleName("Stop backtest")
        self._stop_btn.setToolTip("Stop the running backtest process")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._process_service.stop_process)
        btn_layout.addWidget(self._stop_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()

        # Wrap in scroll area so the form is usable on small screens
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        scroll.setMinimumWidth(300)
        scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        return scroll

    def _build_advanced_body(self) -> QWidget:
        """Build the advanced options form body.

        Returns:
            Widget containing dry-run wallet and max-open-trades spinboxes.
        """
        body = QWidget()
        form = QFormLayout(body)
        form.setContentsMargins(8, 4, 8, 4)
        form.setSpacing(6)

        self._dry_run_wallet = QDoubleSpinBox()
        self._dry_run_wallet.setMinimum(0.0)
        self._dry_run_wallet.setMaximum(999_999.0)
        self._dry_run_wallet.setValue(80.0)
        self._dry_run_wallet.setAccessibleName("Dry run wallet size")
        self._dry_run_wallet.setToolTip(
            "Saved as a preference only. The strategy's own parameters control "
            "the wallet size during backtesting."
        )
        self._dry_run_wallet.setWhatsThis(
            "The simulated wallet size used when the strategy is run in dry-run mode."
        )
        form.addRow("Dry Run Wallet:", self._dry_run_wallet)

        self._max_open_trades = QSpinBox()
        self._max_open_trades.setMinimum(1)
        self._max_open_trades.setMaximum(999)
        self._max_open_trades.setValue(2)
        self._max_open_trades.setAccessibleName("Max open trades")
        self._max_open_trades.setToolTip(
            "Used when opening the Pairs Selector dialog. "
            "The strategy's own parameters control max open trades during backtesting."
        )
        form.addRow("Max Open Trades:", self._max_open_trades)

        return body

    def _build_right_panel(self) -> QWidget:
        """Build the right output panel.

        Returns:
            Widget containing the run-picker toolbar and tabbed output.
        """
        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Run picker toolbar
        picker_layout = QHBoxLayout()
        picker_layout.setSpacing(6)
        picker_layout.addWidget(QLabel("Run:"))

        self._run_combo = QComboBox()
        self._run_combo.setMinimumWidth(260)
        self._run_combo.setToolTip("Select a previous run to load")
        self._run_combo.setAccessibleName("Previous runs")
        picker_layout.addWidget(self._run_combo, 1)

        self._load_run_btn = QPushButton("Load")
        self._load_run_btn.setToolTip("Load the selected run into the Results tab")
        self._load_run_btn.setAccessibleName("Load selected run")
        self._load_run_btn.clicked.connect(self._on_load_run)
        picker_layout.addWidget(self._load_run_btn)

        layout.addLayout(picker_layout)

        # Tabbed output
        self._output_tabs = QTabWidget()

        self._results_widget = BacktestResultsWidget()
        self._output_tabs.addTab(self._results_widget, "Results")

        self._terminal = TerminalWidget()
        self._output_tabs.addTab(self._terminal, "Terminal")

        layout.addWidget(self._output_tabs)

        return right

    # ------------------------------------------------------------------
    # Signal Wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Wire internal signals for live updates."""
        self.settings_state.settings_changed.connect(self._on_settings_changed)
        self.run_config_form.config_changed.connect(self._on_config_changed)

    def _on_settings_changed(self, _settings) -> None:
        """Refresh strategies and run picker when settings change."""
        self._refresh_strategies()
        self._refresh_run_picker()

    def _on_config_changed(self, _config: dict) -> None:
        """Update command preview when form values change."""
        if not self._initializing:
            self._update_command_preview()

    # ------------------------------------------------------------------
    # Strategy / Run Picker
    # ------------------------------------------------------------------

    def _refresh_strategies(self) -> None:
        """Reload available strategies into the RunConfigForm combo."""
        strategies = self._backtest_service.get_available_strategies()
        self.run_config_form.set_strategy_choices(strategies)

    def _rebuild_index_from_zips(self) -> None:
        """Delegate index rebuild to BacktestService."""
        settings = self.settings_state.current_settings
        if not settings or not settings.user_data_path:
            return
        backtest_results_dir = str(
            Path(settings.user_data_path).expanduser().resolve() / "backtest_results"
        )
        self._backtest_service.rebuild_index(backtest_results_dir)

    def _refresh_run_picker(self, _=None) -> None:
        """Populate the run combo with existing runs for the selected strategy."""
        self._run_combo.blockSignals(True)
        self._run_combo.clear()

        settings = self.settings_state.current_settings
        if not settings or not settings.user_data_path:
            self._run_combo.blockSignals(False)
            return

        strategy = self.run_config_form.get_config().get("strategy", "").strip()
        if not strategy:
            self._run_combo.blockSignals(False)
            return

        backtest_results_dir = str(Path(settings.user_data_path) / "backtest_results")
        runs = IndexStore.get_strategy_runs(backtest_results_dir, strategy)

        for run in runs:
            run_id = run.get("run_id", "")
            profit = run.get("profit_total_pct", 0)
            trades = run.get("trades_count", 0)
            saved_at = run.get("saved_at", "")[:16]
            label = f"{run_id}  |  {profit:+.2f}%  |  {trades} trades  |  {saved_at}"
            self._run_combo.addItem(label, userData=run)

        if self._run_combo.count() == 0:
            self._run_combo.addItem("No saved runs found", userData=None)

        self._run_combo.blockSignals(False)

    def _on_load_run(self) -> None:
        """Load the selected run from the index into the results widget."""
        run_meta = self._run_combo.currentData()
        if not run_meta:
            return

        _log.info(
            "Loading run | id=%s | strategy=%s | profit=%.4f%%",
            run_meta.get("run_id"),
            run_meta.get("strategy"),
            run_meta.get("profit_total_pct", 0),
        )

        settings = self.settings_state.current_settings
        if not settings or not settings.user_data_path:
            return

        run_dir = (
            Path(settings.user_data_path) / "backtest_results" / run_meta["run_dir"]
        )

        try:
            results = RunStore.load_run(run_dir)
            _log.info(
                "Run loaded | strategy=%s | trades=%d",
                results.summary.strategy,
                len(results.trades),
            )
            self._results_widget.display_results(results, export_dir=str(run_dir))
            self._output_tabs.setCurrentIndex(0)  # Results tab
        except (FileNotFoundError, ValueError) as e:
            _log.error("Failed to load run %s: %s", run_meta.get("run_id"), e)
            QMessageBox.critical(self, "Load Failed", str(e))

    # ------------------------------------------------------------------
    # Command Preview
    # ------------------------------------------------------------------

    def _update_command_preview(self) -> None:
        """Rebuild the command preview label from current form values."""
        try:
            cfg = self.run_config_form.get_config()
            strategy = cfg.get("strategy", "").strip()
            timeframe = cfg.get("timeframe", "").strip()
            timerange = cfg.get("timerange", "").strip() or None
            pairs: List[str] = cfg.get("pairs", [])

            if not strategy or not timeframe:
                self._preview_label.setText("[Configure strategy and timeframe]")
                return

            cmd = self._backtest_service.build_command(
                strategy_name=strategy,
                timeframe=timeframe,
                timerange=timerange,
                pairs=pairs,
            )
            self._preview_label.setText(" ".join(cmd.as_list()))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Run / Stop
    # ------------------------------------------------------------------

    def _run_backtest(self) -> None:
        """Validate form and start the backtest process."""
        cfg = self.run_config_form.get_config()
        strategy = cfg.get("strategy", "").strip()
        timeframe = cfg.get("timeframe", "").strip()
        timerange = cfg.get("timerange", "").strip() or None
        pairs: List[str] = cfg.get("pairs", [])

        if not strategy:
            QMessageBox.warning(self, "Missing Input", "Please enter a strategy name.")
            return
        if not timeframe:
            QMessageBox.warning(self, "Missing Input", "Please enter a timeframe.")
            return
        if not pairs:
            QMessageBox.warning(self, "Missing Input", "Please select at least one pair.")
            return

        _log.info(
            "Backtest requested | strategy=%s | timeframe=%s | timerange=%s | pairs=%s",
            strategy,
            timeframe,
            timerange or "(all)",
            pairs,
        )

        self._save_preferences()

        try:
            cmd = self._backtest_service.build_command(
                strategy_name=strategy,
                timeframe=timeframe,
                timerange=timerange,
                pairs=pairs,
            )
            self._last_run_config_path = cmd.config_file
        except (ValueError, FileNotFoundError) as e:
            QMessageBox.critical(self, "Backtest Setup Failed", str(e))
            return

        # Prepare terminal
        self._terminal.clear_output()
        self._terminal.append_output(f"$ {cmd.to_display_string()}\n")
        self._terminal.append_output(
            f"Config: {cmd.config_file}\nStrategy: {cmd.strategy_file}\n\n"
        )

        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._preview_timer.stop()
        self._terminal.append_output("[Process started]\n\n")
        self._run_started_at = time.time()
        self._output_tabs.setCurrentIndex(1)  # Terminal tab

        try:
            self._process_service.execute_command(
                command=cmd.as_list(),
                on_output=self._terminal.append_output,
                on_error=self._terminal.append_error,
                on_finished=self._on_process_finished,
                working_directory=cmd.cwd,
            )
        except Exception as e:
            QMessageBox.critical(self, "Process Error", str(e))
            self._run_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)

    def _on_process_finished(self, exit_code: int) -> None:
        """Handle process completion.

        Args:
            exit_code: Process exit code.
        """
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._preview_timer.start()
        self._terminal.append_output(f"\n[Process finished] exit_code={exit_code}\n")
        _log.info("Backtest process finished | exit_code=%d", exit_code)

        if exit_code == 0:
            self._try_load_results()

        self.loop_completed.emit()

    def _try_load_results(self) -> None:
        """Find the zip written during this run and load it into the results widget."""
        settings = self.settings_state.current_settings
        if not settings or not settings.user_data_path:
            self._terminal.append_error("\nWarning: user_data_path not configured.\n")
            return

        backtest_results_dir = (
            Path(settings.user_data_path).expanduser().resolve() / "backtest_results"
        )

        zips = sorted(
            [
                p
                for p in backtest_results_dir.glob("*.zip")
                if p.stat().st_mtime >= self._run_started_at
            ],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not zips:
            self._terminal.append_error("\nWarning: No new zip found in backtest_results/.\n")
            return

        zip_path = zips[0]
        self._terminal.append_output(f"\nFound result: {zip_path.name}\n")
        _log.info("Loading result zip: %s", zip_path.name)

        try:
            self._terminal.append_output("Parsing backtest results...\n")
            results = parse_backtest_zip(str(zip_path))

            if results:
                s = results.summary
                _log.info(
                    "Parsed | strategy=%s | trades=%d | profit=%.4f%% | win_rate=%.1f%%",
                    s.strategy,
                    s.total_trades,
                    s.total_profit,
                    s.win_rate,
                )
                strategy_results_dir = str(backtest_results_dir / s.strategy)
                run_dir = RunStore.save(
                    results=results,
                    strategy_results_dir=strategy_results_dir,
                    config_path=self._last_run_config_path,
                )
                self._terminal.append_output(f"✓ Run saved → {run_dir}\n")
                self._results_widget.display_results(results, export_dir=str(run_dir))
                self._terminal.append_output("✓ Results loaded successfully!\n")
                self._refresh_run_picker()
                self._output_tabs.setCurrentIndex(0)  # Results tab

        except Exception as e:
            _log.error("Failed to load results from %s: %s", zip_path.name, e)
            self._terminal.append_error(f"Failed to parse backtest results: {e}\n")

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------

    def _load_preferences(self) -> None:
        """Populate form from saved backtest preferences."""
        settings = self.settings_state.current_settings
        if not settings or not settings.backtest_preferences:
            return

        prefs = settings.backtest_preferences
        cfg: dict = {}

        if prefs.last_strategy:
            cfg["strategy"] = prefs.last_strategy
        if prefs.default_timeframe:
            cfg["timeframe"] = prefs.default_timeframe
        if prefs.default_timerange:
            cfg["timerange"] = prefs.default_timerange
        if prefs.default_pairs:
            cfg["pairs"] = [
                p.strip() for p in prefs.default_pairs.split(",") if p.strip()
            ]

        if cfg:
            self.run_config_form.set_config(cfg)

        # Advanced options
        self._dry_run_wallet.setValue(prefs.dry_run_wallet or 80.0)
        self._max_open_trades.setValue(prefs.max_open_trades or 2)

    def _save_preferences(self) -> None:
        """Persist current form values to backtest preferences."""
        settings = self.settings_state.current_settings
        if not settings or not settings.backtest_preferences:
            return

        prefs = settings.backtest_preferences
        cfg = self.run_config_form.get_config()

        prefs.last_strategy = cfg.get("strategy", "")
        prefs.default_timeframe = cfg.get("timeframe", "")
        prefs.default_timerange = cfg.get("timerange", "")
        pairs: List[str] = cfg.get("pairs", [])
        prefs.default_pairs = ",".join(pairs) if pairs else ""
        prefs.dry_run_wallet = self._dry_run_wallet.value()
        prefs.max_open_trades = self._max_open_trades.value()

        self.settings_state.save_settings(settings)

    # ------------------------------------------------------------------
    # Splitter Persistence
    # ------------------------------------------------------------------

    def _restore_splitter(self) -> None:
        """Restore splitter state from QSettings."""
        qs = QSettings("FreqtradeGUI", "ModernUI")
        state = qs.value(_SETTINGS_KEY)
        if state:
            self._splitter.restoreState(state)
            _log.debug("Splitter state restored")

    def _save_splitter(self) -> None:
        """Persist splitter state to QSettings."""
        qs = QSettings("FreqtradeGUI", "ModernUI")
        qs.setValue(_SETTINGS_KEY, self._splitter.saveState())
        _log.debug("Splitter state saved")

    def closeEvent(self, event) -> None:  # noqa: N802
        """Save splitter state on close."""
        self._save_splitter()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_current_config(self) -> dict:
        """Return the current backtest configuration as a plain dict.

        Returns:
            Dict with strategy, timeframe, timerange, pairs,
            dry_run_wallet, max_open_trades.
        """
        cfg = self.run_config_form.get_config()
        cfg["dry_run_wallet"] = self._dry_run_wallet.value()
        cfg["max_open_trades"] = self._max_open_trades.value()
        return cfg

    def run_with_config(self, config: dict) -> None:
        """Populate the form from a config dict and run the backtest.

        Args:
            config: Dict with optional keys: strategy, timeframe, timerange,
                pairs, dry_run_wallet, max_open_trades.
        """
        self.run_config_form.set_config(config)

        if "dry_run_wallet" in config:
            self._dry_run_wallet.setValue(float(config["dry_run_wallet"]))
        if "max_open_trades" in config:
            self._max_open_trades.setValue(int(config["max_open_trades"]))

        self._update_command_preview()
        self._run_backtest()

    def refresh(self) -> None:
        """Refresh strategies and run picker (called by ModernMainWindow)."""
        _log.info("BacktestPage.refresh called")
        self._refresh_strategies()
        self._refresh_run_picker()
