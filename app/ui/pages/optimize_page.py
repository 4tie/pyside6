"""Optimize (Hyperopt) page."""
from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QFormLayout, QFrame, QCheckBox, QSplitter
)
from PySide6.QtCore import Qt, Signal, Slot

from app.app_state.settings_state import SettingsState
from app.core.services.optimize_service import OptimizeService
from app.core.services.settings_service import SettingsService
from app.core.services.process_service import ProcessService
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

    def __init__(self, settings_state: SettingsState, parent: QWidget | None = None):
        super().__init__(parent)
        self._state = settings_state
        self._settings_svc = SettingsService()
        self._optimize_svc = OptimizeService(self._settings_svc)
        self._process_svc  = ProcessService()
        self._running = False
        self._build()
        self._sig_stdout.connect(self._terminal.append_output)
        self._sig_stderr.connect(self._terminal.append_error)
        self._sig_finished.connect(self._handle_finished)
        self._load_strategies()

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

        env = (
            ProcessService.build_environment(settings.venv_path)
            if settings.venv_path else None
        )
        self._process_svc.execute_command(
            cmd.as_list(),
            on_output=self._sig_stdout.emit,
            on_error=self._sig_stderr.emit,
            on_finished=self._sig_finished.emit,
            working_directory=cmd.cwd,
            env=env,
        )

    def _stop(self):
        self._process_svc.stop_process()
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
