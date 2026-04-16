from pathlib import Path
import time
from typing import Optional, List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QMessageBox,
    QGroupBox,
    QFormLayout,
    QTabWidget,
)

from app.app_state.settings_state import SettingsState
from app.core.services.backtest_service import BacktestService
from app.core.services.backtest_results_service import BacktestResultsService
from app.core.services.run_store import RunStore, IndexStore
from app.core.services.settings_service import SettingsService
from app.core.services.process_service import ProcessService
from app.core.utils.app_logger import get_logger
from app.ui.widgets.terminal_widget import TerminalWidget
from app.ui.widgets.backtest_results_widget import BacktestResultsWidget
from app.ui.dialogs.pairs_selector_dialog import PairsSelectorDialog

_log = get_logger("backtest")


class BacktestPage(QWidget):
    """Page for running backtest jobs."""

    def __init__(self, settings_state: SettingsState, parent=None):
        super().__init__(parent)
        self.settings_state = settings_state
        self.settings_service = SettingsService()
        self.backtest_service = BacktestService(self.settings_service)
        self.process_service = ProcessService()
        self.last_export_path: Optional[str] = None
        self._last_export_dir: Optional[str] = None
        self.selected_pairs: List[str] = []
        self._initializing: bool = True

        self.init_ui()
        self._connect_signals()
        self._refresh_strategies()
        self._load_preferences()
        self._initializing = False
        self._update_command_preview()
        self._rebuild_index_from_zips()
        self._refresh_run_picker()

        # Refresh command preview every second so the timestamp stays current
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(1000)
        self._preview_timer.timeout.connect(self._update_command_preview)
        self._preview_timer.start()

    def init_ui(self):
        """Initialize UI components."""
        main_layout = QVBoxLayout()

        # Left panel: Parameters
        params_layout = QVBoxLayout()

        # Strategy selection
        strategy_layout = QHBoxLayout()
        strategy_layout.addWidget(QLabel("Strategy:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.setEditable(True)
        strategy_layout.addWidget(self.strategy_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_strategies)
        strategy_layout.addWidget(refresh_btn)

        params_layout.addLayout(strategy_layout)

        # Basic parameters
        timeframe_layout = QHBoxLayout()
        timeframe_layout.addWidget(QLabel("Timeframe:"))
        self.timeframe_input = QLineEdit()
        self.timeframe_input.setPlaceholderText("5m, 1h, 4h, 1d, etc.")
        self.timeframe_input.setText("5m")
        timeframe_layout.addWidget(self.timeframe_input)
        params_layout.addLayout(timeframe_layout)

        # Timerange presets
        timerange_presets_layout = QHBoxLayout()
        timerange_presets_layout.addWidget(QLabel("Timerange Presets:"))

        for preset in ["7d", "14d", "30d", "90d", "120d", "360d"]:
            btn = QPushButton(preset)
            btn.setMaximumWidth(50)
            btn.clicked.connect(lambda checked, p=preset: self._on_timerange_preset(p))
            timerange_presets_layout.addWidget(btn)

        timerange_presets_layout.addStretch()
        params_layout.addLayout(timerange_presets_layout)

        # Custom timerange in group box
        custom_timerange_group = QGroupBox("Custom Timerange (Optional)")
        custom_timerange_layout = QHBoxLayout()
        custom_timerange_layout.addWidget(QLabel("Format: YYYYMMDD-YYYYMMDD"))
        self.timerange_input = QLineEdit()
        self.timerange_input.setPlaceholderText("e.g., 20240101-20241231")
        custom_timerange_layout.addWidget(self.timerange_input)
        custom_timerange_group.setLayout(custom_timerange_layout)
        params_layout.addWidget(custom_timerange_group)

        # Pairs selection
        pairs_layout = QVBoxLayout()
        pairs_button_layout = QHBoxLayout()
        pairs_button_layout.addWidget(QLabel("Pairs:"))

        self.pairs_button = QPushButton("Select Pairs... (0)")
        self.pairs_button.clicked.connect(self._on_select_pairs)
        pairs_button_layout.addWidget(self.pairs_button)
        pairs_button_layout.addStretch()

        pairs_layout.addLayout(pairs_button_layout)

        # Display selected pairs
        self.pairs_display_label = QLabel("Selected: None")
        self.pairs_display_label.setStyleSheet(
            "color: #666; font-size: 9pt; padding-left: 4px;"
        )
        pairs_layout.addWidget(self.pairs_display_label)

        params_layout.addLayout(pairs_layout)

        # Advanced options (collapsible)
        advanced_group = QGroupBox("Advanced Options")
        advanced_layout = QFormLayout()

        self.dry_run_wallet = QDoubleSpinBox()
        self.dry_run_wallet.setMinimum(0)
        self.dry_run_wallet.setMaximum(999999)
        self.dry_run_wallet.setValue(80.0)
        self.dry_run_wallet.setToolTip("Dry run starting wallet balance")
        advanced_layout.addRow("Dry Run Wallet:", self.dry_run_wallet)

        self.max_open_trades = QSpinBox()
        self.max_open_trades.setMinimum(1)
        self.max_open_trades.setMaximum(999)
        self.max_open_trades.setValue(2)
        self.max_open_trades.setToolTip("Maximum number of open trades")
        advanced_layout.addRow("Max Open Trades:", self.max_open_trades)

        advanced_group.setLayout(advanced_layout)
        advanced_group.setCheckable(False)
        params_layout.addWidget(advanced_group)

        # Export label
        self.export_label = QLabel("Export: -")
        self.export_label.setStyleSheet(
            "padding: 8px; background-color: #f0f0f0; border-radius: 4px; font-family: Courier;"
        )
        params_layout.addWidget(self.export_label)

        # Run button (context-sensitive based on mode)
        button_layout = QHBoxLayout()
        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self._run_backtest)
        button_layout.addWidget(self.run_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.process_service.stop_process)
        button_layout.addWidget(self.stop_button)

        button_layout.addStretch()
        params_layout.addLayout(button_layout)

        button_layout.addStretch()
        params_layout.addLayout(button_layout)

        params_layout.addStretch()

        # Right panel: Output + Results
        output_layout = QVBoxLayout()

        # Run picker toolbar
        run_picker_layout = QHBoxLayout()
        run_picker_layout.addWidget(QLabel("Run:"))
        self.run_combo = QComboBox()
        self.run_combo.setMinimumWidth(260)
        self.run_combo.setToolTip("Select a previous run to load")
        run_picker_layout.addWidget(self.run_combo, 1)
        self.load_run_btn = QPushButton("Load")
        self.load_run_btn.clicked.connect(self._on_load_run)
        run_picker_layout.addWidget(self.load_run_btn)
        output_layout.addLayout(run_picker_layout)

        self.output_tabs = QTabWidget()

        self.terminal = TerminalWidget()
        self.output_tabs.addTab(self.terminal, "Terminal Output")

        self.results_widget = BacktestResultsWidget()
        self.output_tabs.addTab(self.results_widget, "Results")

        output_layout.addWidget(self.output_tabs)

        # Main horizontal layout
        h_layout = QHBoxLayout()
        h_layout.addLayout(params_layout, 1)
        h_layout.addLayout(output_layout, 2)

        main_layout.addLayout(h_layout)
        self.setLayout(main_layout)

    def _connect_signals(self):
        """Connect settings signals for live command preview updates."""
        self.settings_state.settings_changed.connect(self._on_settings_changed)
        self.strategy_combo.currentTextChanged.connect(self._update_command_preview)
        self.strategy_combo.currentTextChanged.connect(self._refresh_run_picker)
        self.timeframe_input.textChanged.connect(self._update_command_preview)
        self.timerange_input.textChanged.connect(self._update_command_preview)
        self.dry_run_wallet.valueChanged.connect(self._update_command_preview)
        self.max_open_trades.valueChanged.connect(self._update_command_preview)
        self.settings_state.settings_changed.connect(self._update_command_preview)


    def _refresh_strategies(self):
        """Refresh available strategies."""
        strategies = self.backtest_service.get_available_strategies()
        current = self.strategy_combo.currentText()
        self.strategy_combo.blockSignals(True)
        self.strategy_combo.clear()
        self.strategy_combo.addItems(strategies)
        # Restore selection if it exists
        if current:
            idx = self.strategy_combo.findText(current)
            if idx >= 0:
                self.strategy_combo.setCurrentIndex(idx)
        self.strategy_combo.blockSignals(False)

    def _on_settings_changed(self, settings):
        """Called when settings change."""
        self._refresh_strategies()
        self._refresh_run_picker()

    def _rebuild_index_from_zips(self):
        """Parse any root-level zips not yet in the index and save them as runs."""
        settings = self.settings_state.current_settings
        if not settings or not settings.user_data_path:
            return

        backtest_results_dir = (
            Path(settings.user_data_path).expanduser().resolve() / "backtest_results"
        )
        index = IndexStore.load(str(backtest_results_dir))
        zips = list(backtest_results_dir.glob("*.zip"))
        _log.info("Index rebuild: scanning %d zip(s) in %s", len(zips), backtest_results_dir)

        imported = 0
        skipped  = 0
        for zip_path in sorted(zips, key=lambda p: p.stat().st_mtime):
            try:
                results = BacktestResultsService.parse_backtest_zip(str(zip_path))
                if not results:
                    continue
                strategy = results.summary.strategy
                strategy_results_dir = str(backtest_results_dir / strategy)

                existing = IndexStore.get_strategy_runs(str(backtest_results_dir), strategy)
                already = any(
                    r.get("trades_count") == results.summary.total_trades
                    and r.get("backtest_start") == results.summary.backtest_start
                    and r.get("backtest_end") == results.summary.backtest_end
                    for r in existing
                )
                if already:
                    _log.debug("Skipping already-indexed zip: %s", zip_path.name)
                    skipped += 1
                    continue

                RunStore.save(
                    results=results,
                    strategy_results_dir=strategy_results_dir,
                )
                imported += 1
            except Exception as e:
                _log.warning("Failed to import zip %s: %s", zip_path.name, e)
                continue

        _log.info("Index rebuild complete: imported=%d skipped=%d", imported, skipped)

    def _refresh_run_picker(self, _=None):
        """Populate the run combo with existing runs for the selected strategy."""
        self.run_combo.blockSignals(True)
        self.run_combo.clear()

        settings = self.settings_state.current_settings
        if not settings or not settings.user_data_path:
            self.run_combo.blockSignals(False)
            return

        strategy = self.strategy_combo.currentText().strip()
        if not strategy:
            self.run_combo.blockSignals(False)
            return

        backtest_results_dir = str(
            Path(settings.user_data_path) / "backtest_results"
        )
        runs = IndexStore.get_strategy_runs(backtest_results_dir, strategy)

        for run in runs:
            run_id   = run.get("run_id", "")
            profit   = run.get("profit_total_pct", 0)
            trades   = run.get("trades_count", 0)
            saved_at = run.get("saved_at", "")[:16]
            label    = f"{run_id}  |  {profit:+.2f}%  |  {trades} trades  |  {saved_at}"
            self.run_combo.addItem(label, userData=run)

        if self.run_combo.count() == 0:
            self.run_combo.addItem("No saved runs found", userData=None)

        self.run_combo.blockSignals(False)

    def _on_load_run(self):
        """Load the selected run from the index into the results widget."""
        run_meta = self.run_combo.currentData()
        if not run_meta:
            return

        _log.info("Loading run | id=%s | strategy=%s | profit=%.4f%%",
                  run_meta.get("run_id"), run_meta.get("strategy"),
                  run_meta.get("profit_total_pct", 0))

        settings = self.settings_state.current_settings
        if not settings or not settings.user_data_path:
            return

        backtest_results_dir = Path(settings.user_data_path) / "backtest_results"
        run_dir = backtest_results_dir / run_meta["run_dir"]
        results_file = run_dir / "results.json"
        trades_file  = run_dir / "trades.json"

        if not results_file.exists() or not trades_file.exists():
            QMessageBox.warning(self, "Load Failed",
                                f"Run folder incomplete:\n{run_dir}")
            return

        try:
            from app.core.services.backtest_results_service import (
                BacktestResults, BacktestSummary, BacktestTrade
            )
            import json
            from dataclasses import fields

            r_data = json.loads(results_file.read_text(encoding="utf-8"))
            t_data = json.loads(trades_file.read_text(encoding="utf-8"))

            # Rebuild BacktestSummary from results.json
            summary = BacktestSummary(
                strategy=r_data.get("strategy", ""),
                timeframe=r_data.get("timeframe", ""),
                total_trades=r_data.get("total_trades", 0),
                wins=r_data.get("wins", 0),
                losses=r_data.get("losses", 0),
                draws=r_data.get("draws", 0),
                win_rate=r_data.get("win_rate_pct", 0.0),
                avg_profit=r_data.get("avg_profit_pct", 0.0),
                total_profit=r_data.get("total_profit_pct", 0.0),
                total_profit_abs=r_data.get("total_profit_abs", 0.0),
                sharpe_ratio=r_data.get("sharpe_ratio"),
                sortino_ratio=r_data.get("sortino_ratio"),
                calmar_ratio=r_data.get("calmar_ratio"),
                max_drawdown=r_data.get("max_drawdown_pct", 0.0),
                max_drawdown_abs=r_data.get("max_drawdown_abs", 0.0),
                trade_duration_avg=r_data.get("avg_duration_min", 0),
                starting_balance=r_data.get("starting_balance", 0.0),
                final_balance=r_data.get("final_balance", 0.0),
                timerange=r_data.get("timerange", ""),
                pairlist=r_data.get("pairs", []),
                backtest_start=r_data.get("backtest_start", ""),
                backtest_end=r_data.get("backtest_end", ""),
                expectancy=r_data.get("expectancy", 0.0),
                profit_factor=r_data.get("profit_factor", 0.0),
                max_consecutive_wins=r_data.get("max_consecutive_wins", 0),
                max_consecutive_losses=r_data.get("max_consecutive_losses", 0),
            )

            # Rebuild trades from trades.json
            trades = []
            for t in t_data:
                trades.append(BacktestTrade(
                    pair=t.get("pair", ""),
                    stake_amount=float(t.get("stake_amount", 0)),
                    amount=0.0,
                    open_date=t.get("entry", ""),
                    close_date=t.get("exit") or None,
                    open_rate=float(t.get("entry_rate", 0)),
                    close_rate=float(t.get("exit_rate", 0)) if t.get("exit_rate") else None,
                    profit=float(t.get("profit_pct", 0)),
                    profit_abs=float(t.get("profit_abs", 0)),
                    duration=int(t.get("duration_min", 0)),
                    is_open=bool(t.get("is_open", False)),
                ))

            # Inject exit_reason into raw_data so the widget can display it
            raw_trades = [
                {"exit_reason": t.get("reason", "")} for t in t_data
            ]
            raw_data = {"result": {"trades": raw_trades}}

            results = BacktestResults(summary=summary, trades=trades, raw_data=raw_data)
            _log.info("Run loaded from disk | strategy=%s | trades=%d",
                      summary.strategy, len(trades))
            self.results_widget.display_results(results, export_dir=str(run_dir))
            self.output_tabs.setCurrentIndex(1)

        except Exception as e:
            _log.error("Failed to load run %s: %s", run_meta.get("run_id"), e)
            QMessageBox.critical(self, "Load Failed", str(e))

    def _update_command_preview(self):
        """Update the command preview in terminal based on current UI values."""
        try:
            strategy = self.strategy_combo.currentText().strip()
            timeframe = self.timeframe_input.text().strip()
            timerange = self.timerange_input.text().strip() or None
            pairs = self.selected_pairs
            dry_run_wallet = (
                self.dry_run_wallet.value() if self.dry_run_wallet.value() > 0 else None
            )
            max_open_trades = self.max_open_trades.value()

            if not strategy or not timeframe:
                self.terminal.set_command("[Configure strategy and timeframe]")
                return

            cmd = self.backtest_service.build_command(
                strategy_name=strategy,
                timeframe=timeframe,
                timerange=timerange,
                pairs=pairs if pairs else [],
                max_open_trades=max_open_trades,
                dry_run_wallet=dry_run_wallet,
            )

            command_string = f"{cmd.program} {' '.join(cmd.args)}"
            self.terminal.set_command(command_string)
        except Exception:
            pass

    def _run_backtest(self):
        """Run backtest with selected parameters."""
        strategy = self.strategy_combo.currentText().strip()
        timeframe = self.timeframe_input.text().strip()
        timerange = self.timerange_input.text().strip() or None
        pairs = self.selected_pairs

        if not strategy:
            QMessageBox.warning(self, "Missing Input", "Please enter a strategy name.")
            return
        if not timeframe:
            QMessageBox.warning(self, "Missing Input", "Please enter a timeframe.")
            return
        if not pairs:
            QMessageBox.warning(self, "Missing Input", "Please select at least one pair.")
            return

        _log.info("Backtest requested | strategy=%s | timeframe=%s | timerange=%s | pairs=%s",
                  strategy, timeframe, timerange or "(all)", pairs)

        self._save_preferences_to_settings()

        # Build command
        try:
            dry_run_wallet = (
                self.dry_run_wallet.value() if self.dry_run_wallet.value() > 0 else None
            )
            max_open_trades = self.max_open_trades.value()

            cmd = self.backtest_service.build_command(
                strategy_name=strategy,
                timeframe=timeframe,
                timerange=timerange,
                pairs=pairs,
                max_open_trades=max_open_trades,
                dry_run_wallet=dry_run_wallet,
            )

            self.last_export_path = cmd.export_zip
            self._last_export_dir = cmd.export_dir
            command_string = f"{cmd.program} {' '.join(cmd.args)}"
            _log.info("Command built | strategy=%s", strategy)

        except (ValueError, FileNotFoundError) as e:
            QMessageBox.critical(self, "Backtest Setup Failed", str(e))
            return

        # Clear terminal and show command
        self.terminal.clear_output()
        self.terminal.append_output(f"$ {command_string}\n")
        self.terminal.append_output(
            f"Strategy: {cmd.strategy_file}\n\n"
        )

        self.export_label.setText(f"Export dir: {cmd.export_dir}")

        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._preview_timer.stop()
        self.terminal.append_output("[Process started]\n\n")
        self._run_started_at = time.time()

        try:
            self.process_service.execute_command(
                command=[cmd.program] + cmd.args,
                on_output=self.terminal.append_output,
                on_error=self.terminal.append_error,
                on_finished=self._on_process_finished_internal,
                working_directory=cmd.cwd,
            )
        except Exception as e:
            QMessageBox.critical(self, "Process Error", str(e))
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    def _on_process_started(self):
        pass

    def _on_process_finished_internal(self, exit_code: int):
        """Called when process finishes."""
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._preview_timer.start()
        self.terminal.append_output(f"\n[Process finished] exit_code={exit_code}\n")
        _log.info("Backtest process finished | exit_code=%d", exit_code)

        if exit_code == 0:
            self._try_load_results()
        else:
            _log.warning("Backtest exited with non-zero code: %d", exit_code)

    def _try_load_results(self):
        """Find the zip freqtrade wrote during this run and load it."""
        settings = self.settings_state.current_settings
        if not settings or not settings.user_data_path:
            self.terminal.append_error("\nWarning: user_data_path not configured.\n")
            return

        backtest_results_dir = (
            Path(settings.user_data_path).expanduser().resolve() / "backtest_results"
        )

        # Only consider zips written after this run started
        run_started = getattr(self, "_run_started_at", 0.0)
        zips = sorted(
            [
                p for p in backtest_results_dir.glob("*.zip")
                if p.stat().st_mtime >= run_started
            ],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not zips:
            self.terminal.append_error("\nWarning: No new zip found in backtest_results/.\n")
            return

        zip_path = zips[0]
        self.terminal.append_output(f"\nFound result: {zip_path.name}\n")
        _log.info("Loading result zip: %s", zip_path.name)

        try:
            self.terminal.append_output("Parsing backtest results...\n")
            results = BacktestResultsService.parse_backtest_zip(str(zip_path))

            if results:
                s = results.summary
                _log.info("Parsed | strategy=%s | trades=%d | profit=%.4f%% | win_rate=%.1f%%",
                          s.strategy, s.total_trades, s.total_profit, s.win_rate)
                strategy_results_dir = str(backtest_results_dir / s.strategy)
                run_dir = RunStore.save(
                    results=results,
                    strategy_results_dir=strategy_results_dir,
                )
                self.terminal.append_output(f"✓ Run saved → {run_dir}\n")
                self.results_widget.display_results(results, export_dir=str(run_dir))
                self.terminal.append_output("✓ Results loaded successfully!\n")
                self._refresh_run_picker()
                self.output_tabs.setCurrentIndex(1)

        except Exception as e:
            _log.error("Failed to load results from %s: %s", zip_path.name, e)
            self.terminal.append_error(f"Failed to parse backtest results: {e}\n")

    def _load_preferences(self):
        """Load saved preferences from settings."""
        settings = self.settings_state.current_settings
        if not settings or not settings.backtest_preferences:
            return

        prefs = settings.backtest_preferences

        # Block all signals during loading
        self.strategy_combo.blockSignals(True)
        self.timeframe_input.blockSignals(True)
        self.timerange_input.blockSignals(True)
        self.dry_run_wallet.blockSignals(True)
        self.max_open_trades.blockSignals(True)

        # Load strategy
        if prefs.last_strategy:
            idx = self.strategy_combo.findText(prefs.last_strategy)
            if idx >= 0:
                self.strategy_combo.setCurrentIndex(idx)

        # Load timeframe
        if prefs.default_timeframe:
            self.timeframe_input.setText(prefs.default_timeframe)

        # Load timerange from saved config
        if prefs.default_timerange:
            self.timerange_input.setText(prefs.default_timerange)

        # Load pairs from comma-separated string
        if prefs.default_pairs:
            pairs_list = [
                p.strip() for p in prefs.default_pairs.split(",") if p.strip()
            ]
            self.selected_pairs = pairs_list
        else:
            self.selected_pairs = []

        # Load advanced options
        self.dry_run_wallet.setValue(prefs.dry_run_wallet or 80.0)
        self.max_open_trades.setValue(prefs.max_open_trades or 2)

        self._update_pairs_display()

        # Unblock all signals
        self.strategy_combo.blockSignals(False)
        self.timeframe_input.blockSignals(False)
        self.timerange_input.blockSignals(False)
        self.dry_run_wallet.blockSignals(False)
        self.max_open_trades.blockSignals(False)

    def _save_preferences_to_settings(self):
        """Save current input values to settings for next run."""
        settings = self.settings_state.current_settings
        if not settings or not settings.backtest_preferences:
            return

        prefs = settings.backtest_preferences

        prefs.last_strategy = self.strategy_combo.currentText()
        prefs.default_timeframe = self.timeframe_input.text()
        prefs.default_timerange = self.timerange_input.text().strip()
        prefs.default_pairs = (
            ",".join(self.selected_pairs) if self.selected_pairs else ""
        )

        # Save advanced options
        prefs.dry_run_wallet = self.dry_run_wallet.value()
        prefs.max_open_trades = self.max_open_trades.value()

        # Update favorites with selected pairs (auto-grow list)
        for pair in self.selected_pairs:
            if pair not in prefs.paired_favorites and len(prefs.paired_favorites) < 10:
                prefs.paired_favorites.append(pair)

        # Save to disk
        self.settings_state.save_settings(settings)

    def _on_timerange_preset(self, preset: str):
        """Handle timerange preset button click."""
        from app.core.utils.date_utils import calculate_timerange_preset

        timerange = calculate_timerange_preset(preset)
        self.timerange_input.setText(timerange)

        # Save preference
        settings = self.settings_state.current_settings
        if settings and settings.backtest_preferences:
            settings.backtest_preferences.last_timerange_preset = preset
            self.settings_state.save_settings(settings)

    def _on_select_pairs(self):
        """Open pairs selector dialog."""
        settings = self.settings_state.current_settings
        favorites = settings.backtest_preferences.paired_favorites if settings else []

        dialog = PairsSelectorDialog(favorites, self.selected_pairs, self)
        if dialog.exec() == QDialog.Accepted:
            self.selected_pairs = dialog.get_selected_pairs()
            self._update_pairs_display()
            self._update_command_preview()

    def _update_pairs_display(self):
        """Update pairs button and display label."""
        count = len(self.selected_pairs)
        self.pairs_button.setText(f"Select Pairs... ({count})")

        if self.selected_pairs:
            self.pairs_display_label.setText(
                f"Selected: {', '.join(self.selected_pairs)}"
            )
        else:
            self.pairs_display_label.setText("Selected: None")
