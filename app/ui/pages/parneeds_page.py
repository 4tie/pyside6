"""ParNeeds page - validation workflows for backtest configurations."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.app_state.settings_state import SettingsState
from app.core.models.parneeds_models import (
    CandleCoverageReport,
    ParNeedsConfig,
    ParNeedsWindow,
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


class ParNeedsPage(QWidget):
    """Run validation workflows against editable backtest configuration."""

    run_completed = Signal(str)

    _sig_stdout = Signal(str)
    _sig_stderr = Signal(str)
    _sig_finished = Signal(int)

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
        self._active_config: Optional[ParNeedsConfig] = None
        self._active_window: Optional[ParNeedsWindow] = None
        self._pending_windows: list[ParNeedsWindow] = []
        self._download_queue: list[tuple[bool, list[str], str]] = []
        self._build()
        self._sig_stdout.connect(self._terminal.append_output)
        self._sig_stderr.connect(self._terminal.append_error)
        self._sig_finished.connect(self._handle_finished)
        self._load_strategies()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

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
        self._start_btn.clicked.connect(self.start_timerange_workflow)
        header.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("danger")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)
        header.addWidget(self._stop_btn)
        root.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {theme.BG_BORDER}; }}")

        config_panel = QFrame()
        config_panel.setMinimumWidth(300)
        config_panel.setMaximumWidth(390)
        config_panel.setStyleSheet(
            f"QFrame {{ background: {theme.BG_SURFACE}; border: 1px solid {theme.BG_BORDER}; border-radius: 10px; }}"
        )
        cfg_layout = QVBoxLayout(config_panel)
        cfg_layout.setContentsMargins(16, 16, 16, 16)
        cfg_layout.setSpacing(14)
        cfg_layout.addWidget(self._section("Workflow"))

        self._workflow_combo = QComboBox()
        self._workflow_combo.addItem("Timerange workflow")
        cfg_layout.addWidget(self._workflow_combo)

        cfg_layout.addWidget(self._section("Run Config"))
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self._strategy_combo = QComboBox()
        self._strategy_combo.setEditable(True)
        form.addRow(self._label("Strategy"), self._strategy_combo)

        self._timeframe_combo = QComboBox()
        self._timeframe_combo.setEditable(True)
        self._timeframe_combo.addItems(TIMEFRAMES)
        self._timeframe_combo.setCurrentText("5m")
        form.addRow(self._label("Timeframe"), self._timeframe_combo)

        self._timerange_edit = QLineEdit()
        self._timerange_edit.setPlaceholderText("Defaults to 20240101-yesterday")
        form.addRow(self._label("Timerange"), self._timerange_edit)

        self._pairs_edit = QLineEdit()
        self._pairs_edit.setPlaceholderText("BTC/USDT,ETH/USDT")
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
        cfg_layout.addLayout(form)

        self._plan_lbl = QLabel("Select a workflow, sync config, then start.")
        self._plan_lbl.setWordWrap(True)
        self._plan_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        cfg_layout.addWidget(self._plan_lbl)
        cfg_layout.addStretch()
        splitter.addWidget(config_panel)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        self._terminal = TerminalWidget()
        right_layout.addWidget(self._terminal, 2)

        self._results = QTableWidget(0, 7)
        self._results.setHorizontalHeaderLabels(
            ["Timerange", "Profit %", "Win %", "DD %", "Trades", "Status", "Run ID"]
        )
        self._results.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._results.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._results.setAlternatingRowColors(True)
        self._results.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self._results, 1)

        splitter.addWidget(right)
        splitter.setSizes([330, 820])
        root.addWidget(splitter, 1)

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

    def build_config(self) -> ParNeedsConfig:
        """Build a typed ParNeeds config from the current form values."""
        pairs = [
            pair.strip()
            for pair in self._pairs_edit.text().split(",")
            if pair.strip()
        ]
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
        self._results.setRowCount(0)
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

    def _request_sync(self) -> None:
        parent = self.window()
        backtest_page = getattr(parent, "backtest_page", None)
        if backtest_page and hasattr(backtest_page, "get_run_config"):
            self.sync_from_backtest(backtest_page.get_run_config())

    def _validate_config(self, config: ParNeedsConfig) -> None:
        if not config.strategy:
            raise ValueError("strategy is required")
        if not config.timeframe:
            raise ValueError("timeframe is required")
        if not config.pairs:
            raise ValueError("at least one pair is required for candle validation")

    def _require_settings(self):
        settings = self._state.current_settings
        if not settings or not settings.python_executable:
            raise ValueError("settings are not configured")
        return settings

    def _queue_downloads(
        self,
        config: ParNeedsConfig,
        reports: list[CandleCoverageReport],
    ) -> None:
        """Queue append and prepend downloads for the gaps reported by coverage."""
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

        self._phase = "download"
        self._terminal.set_status("downloading", theme.ACCENT)
        mode = "--prepend" if prepend else "append"
        self._terminal.append_info(
            f"\nMissing candles found. Auto-download started ({label}, {mode}: {', '.join(pairs)}).\n",
            theme.YELLOW,
        )
        self._start_process(cmd)

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
            self._append_result(window.timerange, "command failed", run_id=str(exc))
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
        self._phase = "idle"
        self._pending_windows.clear()
        self._download_queue.clear()
        self._set_running(False)

    @Slot(int)
    def _handle_finished(self, exit_code: int) -> None:
        if self._phase == "download":
            self._handle_download_finished(exit_code)
        elif self._phase == "backtest":
            self._handle_backtest_finished(exit_code)

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
        self._start_next_backtest()

    def _handle_backtest_finished(self, exit_code: int) -> None:
        window = self._active_window
        cfg = self._active_config
        if not window or not cfg:
            self._set_running(False)
            return

        if exit_code == 0:
            run_id = ""
            entry = {}
            try:
                settings = self._require_settings()
                export_dir = Path(settings.user_data_path) / "backtest_results"
                run_id = self._backtest_svc.parse_and_save_latest_results(
                    export_dir, cfg.strategy
                ) or ""
                entry = self._find_run_entry(run_id, cfg.strategy)
            except Exception as exc:
                _log.warning("Could not save ParNeeds backtest result: %s", exc)
            self._append_result(window.timerange, "completed", run_id=run_id, entry=entry)
            if run_id:
                self.run_completed.emit(run_id)
        else:
            self._append_result(window.timerange, f"failed ({exit_code})")

        self._active_window = None
        self._start_next_backtest()

    def _find_run_entry(self, run_id: str, strategy: str) -> dict:
        if not run_id:
            return {}
        settings = self._require_settings()
        results_dir = str(Path(settings.user_data_path) / "backtest_results")
        for entry in self._backtest_svc.get_strategy_runs(results_dir, strategy):
            if entry.get("run_id") == run_id:
                return entry
        return {}

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

    def _append_result(
        self,
        timerange: str,
        status: str,
        *,
        run_id: str = "",
        entry: Optional[dict] = None,
    ) -> None:
        entry = entry or {}
        row = self._results.rowCount()
        self._results.insertRow(row)
        values = [
            timerange,
            self._fmt_float(entry.get("profit_total_pct")),
            self._fmt_float(entry.get("win_rate_pct")),
            self._fmt_float(entry.get("max_drawdown_pct")),
            self._fmt_int(entry.get("trades_count")),
            status,
            run_id,
        ]
        for col, value in enumerate(values):
            self._results.setItem(row, col, QTableWidgetItem(value))

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
        try:
            cfg = self.build_config()
            windows = self._parneeds_svc.generate_timerange_windows(cfg)
            self._plan_lbl.setText(f"{len(windows)} windows planned across {cfg.timerange}.")
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
