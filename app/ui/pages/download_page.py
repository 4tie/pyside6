"""Download Data page."""
from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QFormLayout, QFrame, QSplitter, QListWidget
)
from PySide6.QtCore import Qt, Signal, Slot

from app.app_state.settings_state import SettingsState
from app.core.services.download_data_service import DownloadDataService
from app.core.services.settings_service import SettingsService
from app.core.services.process_service import ProcessService
from app.ui import theme
from app.ui.widgets.terminal_widget import TerminalWidget
from app.core.utils.app_logger import get_logger

_log = get_logger("ui.download")

TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"]
COMMON_PAIRS = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT",
    "SOL/USDT", "DOGE/USDT", "DOT/USDT", "MATIC/USDT", "AVAX/USDT",
    "LINK/USDT", "UNI/USDT", "LTC/USDT", "ATOM/USDT", "NEAR/USDT",
]


class DownloadPage(QWidget):
    # Thread-safe bridge signals
    _sig_stdout   = Signal(str)
    _sig_stderr   = Signal(str)
    _sig_finished = Signal(int)

    def __init__(self, settings_state: SettingsState, parent: QWidget | None = None):
        super().__init__(parent)
        self._state = settings_state
        self._settings_svc = SettingsService()
        self._download_svc = DownloadDataService(self._settings_svc)
        self._process_svc  = ProcessService()
        self._running = False
        self._build()
        self._sig_stdout.connect(self._terminal.append_output)
        self._sig_stderr.connect(self._terminal.append_error)
        self._sig_finished.connect(self._handle_finished)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("Download Data")
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {theme.TEXT_PRIMARY};"
        )
        hdr.addWidget(title)
        hdr.addStretch()

        self._run_btn = QPushButton("↓  Download")
        self._run_btn.setObjectName("primary")
        self._run_btn.setFixedSize(120, 36)
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
        config.setMaximumWidth(380)
        cl = QVBoxLayout(config)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(14)

        cl.addWidget(self._section("Configuration"))

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self._tf_combo = QComboBox()
        self._tf_combo.addItems(TIMEFRAMES)
        self._tf_combo.setCurrentText("5m")
        form.addRow(self._lbl("Timeframe"), self._tf_combo)

        self._timerange_edit = QLineEdit()
        self._timerange_edit.setPlaceholderText("e.g. 20240101-20241231")
        form.addRow(self._lbl("Timerange"), self._timerange_edit)

        cl.addLayout(form)

        cl.addWidget(self._section("Pairs"))

        pair_row = QHBoxLayout()
        self._pair_input = QLineEdit()
        self._pair_input.setPlaceholderText("BTC/USDT")
        self._pair_input.returnPressed.connect(self._add_pair)
        pair_row.addWidget(self._pair_input)
        add_btn = QPushButton("+")
        add_btn.setFixedSize(32, 32)
        add_btn.clicked.connect(self._add_pair)
        pair_row.addWidget(add_btn)
        cl.addLayout(pair_row)

        self._pairs_list = QListWidget()
        self._pairs_list.setMaximumHeight(160)
        self._pairs_list.setStyleSheet(f"""
            QListWidget {{
                background: {theme.BG_INPUT};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 6px;
                font-size: 12px;
                color: {theme.TEXT_PRIMARY};
            }}
            QListWidget::item {{ padding: 4px 8px; }}
            QListWidget::item:selected {{ background: {theme.ACCENT_DIM}; }}
        """)
        cl.addWidget(self._pairs_list)

        cl.addWidget(self._section("Quick Add"))
        for pair in COMMON_PAIRS[:8]:
            btn = QPushButton(pair)
            btn.setFixedHeight(26)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {theme.BG_ELEVATED};
                    color: {theme.TEXT_SECONDARY};
                    border: 1px solid {theme.BG_BORDER};
                    border-radius: 4px;
                    font-size: 11px;
                    padding: 0 8px;
                }}
                QPushButton:hover {{
                    background: {theme.ACCENT_DIM};
                    color: {theme.ACCENT};
                }}
            """)
            btn.clicked.connect(lambda checked, p=pair: self._quick_add(p))
            cl.addWidget(btn)

        remove_btn = QPushButton("✕  Remove Selected")
        remove_btn.clicked.connect(self._remove_pair)
        cl.addWidget(remove_btn)

        cl.addStretch()
        splitter.addWidget(config)

        self._terminal = TerminalWidget()
        splitter.addWidget(self._terminal)
        splitter.setSizes([320, 680])
        root.addWidget(splitter, 1)

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {theme.TEXT_SECONDARY};"
            " margin-top: 4px;"
        )
        return lbl

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
        return lbl

    def _add_pair(self):
        pair = self._pair_input.text().strip().upper()
        if pair and not self._pair_exists(pair):
            self._pairs_list.addItem(pair)
        self._pair_input.clear()

    def _quick_add(self, pair: str):
        if not self._pair_exists(pair):
            self._pairs_list.addItem(pair)

    def _pair_exists(self, pair: str) -> bool:
        return any(
            self._pairs_list.item(i).text() == pair
            for i in range(self._pairs_list.count())
        )

    def _remove_pair(self):
        for item in self._pairs_list.selectedItems():
            self._pairs_list.takeItem(self._pairs_list.row(item))

    def _get_pairs(self) -> list[str]:
        return [self._pairs_list.item(i).text()
                for i in range(self._pairs_list.count())]

    def _run(self):
        if self._running:
            return
        pairs = self._get_pairs()
        if not pairs:
            self._terminal.append_info("⚠ No pairs selected.", theme.YELLOW)
            return
        settings = self._state.current_settings
        if not settings or not settings.python_executable:
            self._terminal.append_info("⚠ Settings not configured.", theme.RED)
            return

        timerange = self._timerange_edit.text().strip() or None
        try:
            cmd = self._download_svc.build_command(
                timeframe=self._tf_combo.currentText(),
                timerange=timerange,
                pairs=pairs,
            )
        except Exception as e:
            self._terminal.append_info(f"⚠ {e}", theme.RED)
            return

        self._running = True
        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._terminal.clear()
        self._terminal.set_status("downloading", theme.ACCENT)
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
            self._terminal.append_info("\n✓ Download completed.", theme.GREEN)
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
