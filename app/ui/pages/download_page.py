"""download_page.py — OHLCV market data download page.

Provides a two-panel layout: left panel for download configuration
(timeframe, timerange, pairs), right panel with data status and terminal.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QSettings

from app.app_state.settings_state import SettingsState
from app.core.services.download_data_service import DownloadDataService
from app.core.utils.app_logger import get_logger
from app.ui.widgets.data_status_widget import DataStatusWidget
from app.ui.widgets.run_config_form import RunConfigForm
from app.ui.widgets.terminal_widget import TerminalWidget

_log = get_logger("ui.download_page")

_QSETTINGS_ORG = "FreqtradeGUI"
_QSETTINGS_APP = "ModernUI"
_SPLITTER_KEY = "splitter/download"


class DownloadPage(QWidget):
    """Data download configuration and execution page.

    Args:
        settings_state: Application settings state.
        parent: Optional parent widget.
    """

    def __init__(self, settings_state: SettingsState, parent=None) -> None:
        super().__init__(parent)
        self._settings_state = settings_state
        self._download_service = DownloadDataService(settings_state.settings_service)
        self._build_ui()
        self._connect_signals()
        self._restore_state()

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
        title_label = QLabel("Download Data")
        title_label.setObjectName("page_title")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        root.addWidget(title_bar)

        # Main splitter
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(4)
        root.addWidget(self._splitter)

        # ── Left panel ─────────────────────────────────────────────────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setMaximumWidth(320)

        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        # Run config form — no strategy selector
        self.run_config_form = RunConfigForm(
            self._settings_state,
            show_strategy=False,
        )
        left_layout.addWidget(self.run_config_form)

        # Download / Stop buttons
        btn_row = QHBoxLayout()
        self._download_btn = QPushButton("Download")
        self._download_btn.setObjectName("success")
        self._download_btn.setAccessibleName("Download market data")
        self._download_btn.setToolTip("Validate configuration and start data download")

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("danger")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setAccessibleName("Stop download")
        self._stop_btn.setToolTip("Terminate the running download process")

        btn_row.addWidget(self._download_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        left_layout.addLayout(btn_row)
        left_layout.addStretch()

        left_scroll.setWidget(left_content)
        self._splitter.addWidget(left_scroll)

        # ── Right panel ────────────────────────────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()

        self._data_status_widget = DataStatusWidget()
        self._terminal = TerminalWidget()

        self._tabs.addTab(self._data_status_widget, "Data Status")
        self._tabs.addTab(self._terminal, "Terminal")
        right_layout.addWidget(self._tabs)

        self._splitter.addWidget(right_widget)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

        # Sync data status widget with settings
        self._sync_data_status_path()

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Wire all internal signals."""
        self._download_btn.clicked.connect(self._on_download_clicked)
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        self._terminal.process_finished.connect(self._on_process_finished)
        self._settings_state.settings_changed.connect(self._on_settings_changed)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_download_clicked(self) -> None:
        """Validate form and start data download."""
        errors = self.run_config_form.validate()
        if errors:
            QMessageBox.warning(self, "Configuration Error", "\n".join(errors))
            return

        cfg = self.run_config_form.get_config()
        timeframe = cfg.get("timeframe", "")
        timerange = cfg.get("timerange") or None
        pairs = cfg.get("pairs") or []

        if not pairs:
            QMessageBox.warning(
                self, "Configuration Error", "At least one pair must be selected."
            )
            return
        if not timeframe:
            QMessageBox.warning(
                self, "Configuration Error", "A timeframe must be selected."
            )
            return

        try:
            cmd = self._download_service.build_command(
                timeframe=timeframe,
                timerange=timerange,
                pairs=pairs,
            )
        except Exception as e:
            QMessageBox.critical(self, "Command Build Error", str(e))
            _log.error("Failed to build download command: %s", e)
            return

        self._download_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._tabs.setCurrentWidget(self._terminal)
        self._terminal.run_command(cmd.as_list())
        _log.info("Download started: timeframe=%s pairs=%s", timeframe, pairs)

    def _on_stop_clicked(self) -> None:
        """Stop the running download."""
        self._terminal.stop_process()
        self._download_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        _log.info("Download stopped by user")

    def _on_process_finished(self, exit_code: int) -> None:
        """Handle download process completion."""
        self._download_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

        if exit_code == 0:
            _log.info("Download completed successfully")
            self._data_status_widget.refresh()
        else:
            _log.warning("Download exited with code %d", exit_code)

    def _on_settings_changed(self, _=None) -> None:
        """Sync data status widget path when settings change."""
        self._sync_data_status_path()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _sync_data_status_path(self) -> None:
        """Update DataStatusWidget with the current user_data path."""
        settings = self._settings_state.current_settings
        path = settings.user_data_path if settings else None
        self._data_status_widget.set_user_data_path(path)

    def _restore_state(self) -> None:
        """Restore splitter state from QSettings."""
        qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        state = qs.value(_SPLITTER_KEY)
        if state is not None:
            self._splitter.restoreState(state)

    def _save_state(self) -> None:
        """Persist splitter state to QSettings."""
        qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        qs.setValue(_SPLITTER_KEY, self._splitter.saveState())

    def hideEvent(self, event) -> None:  # noqa: N802
        """Save splitter state when page is hidden."""
        self._save_state()
        super().hideEvent(event)
