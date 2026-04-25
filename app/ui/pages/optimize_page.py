"""Optimize (Hyperopt) page."""
from __future__ import annotations
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QFormLayout, QFrame, QCheckBox, QSplitter
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot

from app.app_state.settings_state import SettingsState
from app.core.models.settings_models import AppSettings
from app.core.services.optimize_service import OptimizeService
from app.core.services.process_run_manager import ProcessRunManager
from app.core.services.settings_service import SettingsService
from app.ui.adapters.process_run_adapter import ProcessRunAdapter
from app.ui import theme
from app.ui.widgets.terminal_widget import TerminalWidget
from app.core.utils.app_logger import get_logger

_log = get_logger("ui.optimize")

SPACES = ["buy", "sell", "roi", "stoploss", "trailing"]
LOSS_FUNCTIONS = [
    "SharpeHyperOptLoss", "SortinoHyperOptLoss", "CalmarHyperOptLoss",
    "MaxDrawDownHyperOptLoss", "ProfitDrawDownHyperOptLoss",
    "OnlyProfitHyperOptLoss", "ShortTradeDurHyperOptLoss",
]
TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"]


class OptimizePage(QWidget):
    # Thread-safe bridge signals
    _sig_stdout   = Signal(str)
    _sig_stderr   = Signal(str)
    _sig_finished = Signal(int)

    def __init__(self, settings_state: SettingsState, process_manager: ProcessRunManager, parent: QWidget | None = None):
        super().__init__(parent)
        self._state = settings_state
        self._settings_svc = getattr(settings_state, "settings_service", SettingsService())
        self._optimize_svc = OptimizeService(self._settings_svc)
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
        self._sig_stdout.connect(self._terminal.append_output)
        self._sig_stderr.connect(self._terminal.append_error)
        self._sig_finished.connect(self._handle_finished)
        self._load_strategies()
        self._restore_preferences()
        self._connect_preferences_autosave()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("Optimize (Hyperopt)")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {theme.TEXT_PRIMARY};"
        )
        hdr.addWidget(title)
        hdr.addStretch()

        self._run_btn = QPushButton("▶  Run Hyperopt")
        self._run_btn.setObjectName("primary")
        self._run_btn.setFixedSize(150, 36)
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

        config = QFrame()
        config.setStyleSheet(f"""
            QFrame {{
                background: {theme.BG_SURFACE};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 10px;
            }}
        """)
        config.setMinimumWidth(280)
        config.setMaximumWidth(360)
        cl = QVBoxLayout(config)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(14)

        cl.addWidget(self._section("Configuration"))

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self._strategy_combo = QComboBox()
        form.addRow(self._lbl("Strategy"), self._strategy_combo)

        self._tf_combo = QComboBox()
        self._tf_combo.addItems(TIMEFRAMES)
        self._tf_combo.setCurrentText("5m")
        form.addRow(self._lbl("Timeframe"), self._tf_combo)

        self._timerange_edit = QComboBox()
        self._timerange_edit.setEditable(True)
        self._timerange_edit.addItems(["", "20240101-20241231", "20230101-20231231"])
        form.addRow(self._lbl("Timerange"), self._timerange_edit)

        self._epochs_spin = QSpinBox()
        self._epochs_spin.setRange(10, 10000)
        self._epochs_spin.setValue(100)
        form.addRow(self._lbl("Epochs"), self._epochs_spin)

        self._loss_combo = QComboBox()
        self._loss_combo.addItems(LOSS_FUNCTIONS)
        form.addRow(self._lbl("Loss Function"), self._loss_combo)

        cl.addLayout(form)

        cl.addWidget(self._section("Search Spaces"))
        self._space_checks: dict[str, QCheckBox] = {}
        for space in SPACES:
            cb = QCheckBox(space.capitalize())
            cb.setChecked(True)
            self._space_checks[space] = cb
            cl.addWidget(cb)

        cl.addStretch()
        splitter.addWidget(config)

        self._terminal = TerminalWidget()
        splitter.addWidget(self._terminal)
        splitter.setSizes([300, 700])
        root.addWidget(splitter, 1)

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {theme.TEXT_PRIMARY};"
        )
        return lbl

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
        return lbl

    def _load_strategies(self):
        try:
            strategies = self._optimize_svc.get_available_strategies()
            self._strategy_combo.clear()
            self._strategy_combo.addItems(strategies)
        except Exception as e:
            _log.warning("Could not load strategies: %s", e)

    def _restore_preferences(self) -> None:
        current = getattr(self._state, "current_settings", None)
        settings = current if isinstance(current, AppSettings) else self._settings_svc.load_settings()
        self._state.current_settings = settings
        prefs = settings.optimize_preferences
        self._loading_preferences = True
        if prefs.last_strategy:
            idx = self._strategy_combo.findText(prefs.last_strategy)
            if idx >= 0:
                self._strategy_combo.setCurrentIndex(idx)
        self._tf_combo.setCurrentText(prefs.default_timeframe or "5m")
        self._timerange_edit.setCurrentText(prefs.default_timerange or "")
        self._epochs_spin.setValue(prefs.epochs)
        self._loss_combo.setCurrentText(prefs.hyperopt_loss)
        spaces = {s.strip() for s in prefs.spaces.split(",") if s.strip()}
        for name, checkbox in self._space_checks.items():
            checkbox.setChecked(not spaces or prefs.spaces == "all" or name in spaces)
        self._loading_preferences = False

    def _connect_preferences_autosave(self) -> None:
        self._strategy_combo.currentTextChanged.connect(self._schedule_preferences_save)
        self._tf_combo.currentTextChanged.connect(self._schedule_preferences_save)
        self._timerange_edit.currentTextChanged.connect(self._schedule_preferences_save)
        self._epochs_spin.valueChanged.connect(self._schedule_preferences_save)
        self._loss_combo.currentTextChanged.connect(self._schedule_preferences_save)
        for checkbox in self._space_checks.values():
            checkbox.toggled.connect(self._schedule_preferences_save)

    def _schedule_preferences_save(self, *_args) -> None:
        if self._loading_preferences:
            return
        self._prefs_save_timer.start()

    def _save_preferences(self) -> None:
        spaces = [s for s, cb in self._space_checks.items() if cb.isChecked()]
        try:
            self._state.update_preferences(
                "optimize_preferences",
                last_strategy=self._strategy_combo.currentText().strip(),
                default_timeframe=self._tf_combo.currentText().strip(),
                default_timerange=self._timerange_edit.currentText().strip(),
                epochs=self._epochs_spin.value(),
                spaces="all" if set(spaces) == set(SPACES) else ",".join(spaces),
                hyperopt_loss=self._loss_combo.currentText().strip(),
            )
        except Exception as exc:
            _log.warning("Could not save optimize preferences: %s", exc)

    def _run(self):
        if self._running:
            return
        strategy = self._strategy_combo.currentText()
        if not strategy:
            return
        settings = self._state.current_settings
        if not settings or not settings.python_executable:
            self._terminal.append_info("⚠ Settings not configured.", theme.RED)
            return

        spaces    = [s for s, cb in self._space_checks.items() if cb.isChecked()]
        timerange = self._timerange_edit.currentText().strip() or None

        try:
            cmd = self._optimize_svc.build_command(
                strategy_name=strategy,
                timeframe=self._tf_combo.currentText(),
                epochs=self._epochs_spin.value(),
                timerange=timerange,
                spaces=spaces,
                hyperopt_loss=self._loss_combo.currentText(),
            )
        except Exception as e:
            self._terminal.append_info(f"⚠ {e}", theme.RED)
            return

        self._running = True
        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._terminal.clear()
        self._terminal.set_status("running", theme.PURPLE)
        self._terminal.append_info(f"$ {cmd.to_display_string()}\n\n", theme.ACCENT)

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
        self._terminal.append_info("\n■ Stopped.", theme.YELLOW)
        self._set_idle()

    @Slot(int)
    def _handle_finished(self, exit_code: int):
        if exit_code == 0:
            self._terminal.append_info("\n✓ Hyperopt completed.", theme.GREEN)
            self._terminal.set_status("done", theme.GREEN)
        else:
            self._terminal.append_info(
                f"\n✗ Failed (exit {exit_code}).", theme.RED
            )
            self._terminal.set_status("failed", theme.RED)
        self._set_idle()

    def _set_idle(self):
        self._running = False
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
