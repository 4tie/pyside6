"""Backtest page — configure and run backtests with live terminal output."""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox,
    QSplitter, QFrame, QFormLayout
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot

from app.app_state.settings_state import SettingsState
from app.core.models.settings_models import AppSettings
from app.core.services.backtest_service import BacktestService
from app.core.services.process_run_manager import ProcessRunManager
from app.core.services.settings_service import SettingsService
from app.ui.adapters.process_run_adapter import ProcessRunAdapter
from app.ui import theme
from app.ui.widgets.terminal_widget import TerminalWidget
from app.core.utils.app_logger import get_logger

_log = get_logger("ui.backtest")

TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"]
PRESETS = {"7d": 7, "14d": 14, "30d": 30, "90d": 90, "180d": 180, "360d": 360, "Custom": 0}


class BacktestPage(QWidget):
    run_completed = Signal(str)   # emits run_id on success

    # Thread-safe bridge signals (background thread → Qt main thread)
    _sig_stdout   = Signal(str)
    _sig_stderr   = Signal(str)
    _sig_finished = Signal(int)

    def __init__(self, settings_state: SettingsState, process_manager: ProcessRunManager, parent: QWidget | None = None):
        super().__init__(parent)
        self._state = settings_state
        self._settings_svc = getattr(settings_state, "settings_service", SettingsService())
        self._backtest_svc = BacktestService(self._settings_svc)
        self._process_manager = process_manager
        self._current_run_id: Optional[str] = None
        self._adapter: Optional[ProcessRunAdapter] = None
        self._running = False
        self._loading_preferences = False
        self._prefs_save_timer = QTimer(self)
        self._prefs_save_timer.setSingleShot(True)
        self._prefs_save_timer.setInterval(500)
        self._prefs_save_timer.timeout.connect(self._save_preferences)
        self._build()
        # Wire bridge signals to slots (always runs on main thread)
        self._sig_stdout.connect(self._terminal.append_output)
        self._sig_stderr.connect(self._terminal.append_error)
        self._sig_finished.connect(self._handle_finished)
        self._load_strategies()
        self._restore_preferences()
        self._connect_preferences_autosave()

    # ── UI construction ───────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("Backtest")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {theme.TEXT_PRIMARY};"
        )
        hdr.addWidget(title)
        hdr.addStretch()

        self._run_btn = QPushButton("▶  Run Backtest")
        self._run_btn.setObjectName("primary")
        self._run_btn.setFixedSize(140, 36)
        self._run_btn.clicked.connect(self._run)
        hdr.addWidget(self._run_btn)

        self._stop_btn = QPushButton("■  Stop")
        self._stop_btn.setObjectName("danger")
        self._stop_btn.setFixedSize(80, 36)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)
        hdr.addWidget(self._stop_btn)
        root.addLayout(hdr)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {theme.BG_BORDER}; }}"
        )

        # Config panel
        config_panel = QFrame()
        config_panel.setStyleSheet(f"""
            QFrame {{
                background: {theme.BG_SURFACE};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 10px;
            }}
        """)
        config_panel.setMinimumWidth(280)
        config_panel.setMaximumWidth(360)
        cl = QVBoxLayout(config_panel)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(14)

        sec = QLabel("Configuration")
        sec.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {theme.TEXT_PRIMARY};"
        )
        cl.addWidget(sec)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self._strategy_combo = QComboBox()
        form.addRow(self._lbl("Strategy"), self._strategy_combo)

        self._tf_combo = QComboBox()
        self._tf_combo.addItems(TIMEFRAMES)
        self._tf_combo.setCurrentText("5m")
        form.addRow(self._lbl("Timeframe"), self._tf_combo)

        self._preset_combo = QComboBox()
        self._preset_combo.addItems(list(PRESETS.keys()))
        self._preset_combo.setCurrentText("30d")
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)
        form.addRow(self._lbl("Preset"), self._preset_combo)

        self._timerange_edit = QLineEdit()
        self._timerange_edit.setPlaceholderText("e.g. 20240101-20241231")
        form.addRow(self._lbl("Timerange"), self._timerange_edit)

        self._pairs_edit = QLineEdit()
        self._pairs_edit.setPlaceholderText("BTC/USDT,ETH/USDT")
        form.addRow(self._lbl("Pairs"), self._pairs_edit)

        self._wallet_spin = QDoubleSpinBox()
        self._wallet_spin.setRange(1, 1_000_000)
        self._wallet_spin.setValue(80)
        self._wallet_spin.setSuffix(" USDT")
        form.addRow(self._lbl("Wallet"), self._wallet_spin)

        self._trades_spin = QSpinBox()
        self._trades_spin.setRange(1, 100)
        self._trades_spin.setValue(2)
        form.addRow(self._lbl("Max Trades"), self._trades_spin)

        cl.addLayout(form)

        cl.addStretch()

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
        )
        cl.addWidget(self._status_lbl)

        splitter.addWidget(config_panel)

        self._terminal = TerminalWidget()
        splitter.addWidget(self._terminal)
        splitter.setSizes([300, 700])
        root.addWidget(splitter, 1)

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
        return lbl

    def get_run_config(self) -> dict:
        """Return the current Backtest form values as a reusable run config."""
        pairs_text = self._pairs_edit.text().strip()
        pairs = [p.strip() for p in pairs_text.split(",") if p.strip()] if pairs_text else []
        return {
            "strategy": self._strategy_combo.currentText().strip(),
            "timeframe": self._tf_combo.currentText().strip(),
            "timerange": self._timerange_edit.text().strip(),
            "pairs": pairs,
            "dry_run_wallet": self._wallet_spin.value(),
            "max_open_trades": self._trades_spin.value(),
        }

    # ── Helpers ───────────────────────────────────────────────────────
    def _load_strategies(self):
        try:
            strategies = self._backtest_svc.get_available_strategies()
            self._strategy_combo.clear()
            self._strategy_combo.addItems(strategies)
            settings = self._state.current_settings
            if settings and settings.backtest_preferences.last_strategy:
                idx = self._strategy_combo.findText(
                    settings.backtest_preferences.last_strategy
                )
                if idx >= 0:
                    self._strategy_combo.setCurrentIndex(idx)
        except Exception as e:
            _log.warning("Could not load strategies: %s", e)

    def _restore_preferences(self):
        current = getattr(self._state, "current_settings", None)
        settings = current if isinstance(current, AppSettings) else self._settings_svc.load_settings()
        self._state.current_settings = settings
        if not settings:
            return
        p = settings.backtest_preferences
        self._loading_preferences = True
        if p.last_strategy:
            idx = self._strategy_combo.findText(p.last_strategy)
            if idx >= 0:
                self._strategy_combo.setCurrentIndex(idx)
        if p.default_timeframe:
            self._tf_combo.setCurrentText(p.default_timeframe)
        if p.last_timerange_preset:
            self._preset_combo.setCurrentText(p.last_timerange_preset)
        if p.default_pairs:
            self._pairs_edit.setText(p.default_pairs)
        if p.default_timerange:
            self._timerange_edit.setText(p.default_timerange)
        self._wallet_spin.setValue(p.dry_run_wallet)
        self._trades_spin.setValue(p.max_open_trades)
        self._loading_preferences = False

    def _connect_preferences_autosave(self) -> None:
        self._strategy_combo.currentTextChanged.connect(self._schedule_preferences_save)
        self._tf_combo.currentTextChanged.connect(self._schedule_preferences_save)
        self._preset_combo.currentTextChanged.connect(self._schedule_preferences_save)
        self._timerange_edit.textChanged.connect(self._schedule_preferences_save)
        self._pairs_edit.textChanged.connect(self._schedule_preferences_save)
        self._wallet_spin.valueChanged.connect(self._schedule_preferences_save)
        self._trades_spin.valueChanged.connect(self._schedule_preferences_save)

    def _schedule_preferences_save(self, *_args) -> None:
        if self._loading_preferences:
            return
        self._status_lbl.setText("Saving preferences...")
        self._prefs_save_timer.start()

    def _save_preferences(self) -> None:
        try:
            self._state.update_preferences(
                "backtest_preferences",
                last_strategy=self._strategy_combo.currentText().strip(),
                default_timeframe=self._tf_combo.currentText().strip(),
                default_timerange=self._timerange_edit.text().strip(),
                default_pairs=self._pairs_edit.text().strip(),
                last_timerange_preset=self._preset_combo.currentText().strip(),
                dry_run_wallet=self._wallet_spin.value(),
                max_open_trades=self._trades_spin.value(),
            )
            self._status_lbl.setText("Preferences saved")
        except Exception as exc:
            _log.warning("Could not save backtest preferences: %s", exc)
            self._status_lbl.setText("Preference save failed")

    def _on_preset_changed(self, preset: str):
        if preset == "Custom":
            self._timerange_edit.setEnabled(True)
            return
        self._timerange_edit.setEnabled(False)
        from datetime import datetime, timedelta
        days = PRESETS.get(preset, 30)
        end   = datetime.now()
        start = end - timedelta(days=days)
        self._timerange_edit.setText(
            f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"
        )

    # ── Run / Stop ────────────────────────────────────────────────────
    def _run(self):
        if self._running:
            return
        strategy = self._strategy_combo.currentText()
        if not strategy:
            self._terminal.append_info("⚠ No strategy selected.", theme.YELLOW)
            return

        settings = self._state.current_settings
        if not settings or not settings.python_executable:
            self._terminal.append_info("⚠ Settings not configured.", theme.RED)
            return

        timeframe  = self._tf_combo.currentText()
        timerange  = self._timerange_edit.text().strip() or None
        pairs_text = self._pairs_edit.text().strip()
        pairs      = [p.strip() for p in pairs_text.split(",") if p.strip()] \
                     if pairs_text else []
        wallet     = self._wallet_spin.value()
        max_trades = self._trades_spin.value()

        try:
            cmd = self._backtest_svc.build_command(
                strategy_name=strategy,
                timeframe=timeframe,
                timerange=timerange,
                pairs=pairs,
                max_open_trades=max_trades,
                dry_run_wallet=wallet,
            )
        except Exception as e:
            self._terminal.append_info(f"⚠ Command build failed: {e}", theme.RED)
            return

        self._running = True
        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._terminal.clear()
        self._terminal.set_status("running", theme.GREEN)
        self._terminal.append_info(f"$ {cmd.to_display_string()}\n\n", theme.ACCENT)
        self._status_lbl.setText("Running…")

        run = self._process_manager.start_run(cmd)
        self._current_run_id = run.run_id
        self._adapter = ProcessRunAdapter(run, parent=self)
        self._adapter.stdout_received.connect(self._sig_stdout.emit)
        self._adapter.stderr_received.connect(self._sig_stderr.emit)
        self._adapter.run_finished.connect(self._sig_finished.emit)
        self._adapter.start()

    def _stop(self):
        if self._current_run_id:
            try:
                self._process_manager.stop_run(self._current_run_id)
            except (KeyError, ValueError):
                pass
        if self._adapter:
            self._adapter.stop()
            self._adapter = None
        self._terminal.append_info("\n■ Stopped by user.", theme.YELLOW)
        self._set_idle()

    # ── Slots (always on main thread via signal) ──────────────────────
    @Slot(int)
    def _handle_finished(self, exit_code: int):
        if exit_code == 0:
            self._terminal.append_info("\n✓ Backtest completed.", theme.GREEN)
            self._terminal.set_status("done", theme.GREEN)
            self._status_lbl.setText("Completed ✓")
            try:
                settings   = self._state.current_settings
                strategy   = self._strategy_combo.currentText()
                export_dir = Path(settings.user_data_path) / "backtest_results"
                run_id     = self._backtest_svc.parse_and_save_latest_results(
                    export_dir, strategy
                )
                if run_id:
                    self._terminal.append_info(
                        f"✓ Results saved: {run_id}", theme.GREEN
                    )
                    self.run_completed.emit(run_id)
            except Exception as e:
                _log.warning("Could not save results: %s", e)
        else:
            self._terminal.append_info(
                f"\n✗ Backtest failed (exit {exit_code}).", theme.RED
            )
            self._terminal.set_status("failed", theme.RED)
            self._status_lbl.setText(f"Failed (exit {exit_code})")
        self._set_idle()

    def _set_idle(self):
        self._running = False
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
