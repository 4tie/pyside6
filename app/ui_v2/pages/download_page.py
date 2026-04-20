"""DownloadPage for the v2 UI layer.

Two-panel QSplitter layout: RunConfigForm (timeframe + timerange + pairs only)
on the left; tabbed output (Data Status + Terminal) on the right.

Requirements: 13.1, 13.3, 13.4, 8.6
"""
from datetime import datetime
from typing import List

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.app_state.settings_state import SettingsState
from app.core.services.download_data_service import DownloadDataService
from app.core.services.process_service import ProcessService
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger
from app.ui.widgets.data_status_widget import DataStatusWidget
from app.ui.widgets.terminal_widget import TerminalWidget
from app.ui_v2.widgets.run_config_form import RunConfigForm

_log = get_logger("ui_v2.pages.download_page")

_SETTINGS_KEY = "splitter/download"


class DownloadPage(QWidget):
    """Redesigned download data page using a QSplitter layout.

    Left panel holds a RunConfigForm (timeframe + timerange + pairs only)
    with inline validation warnings.  Right panel holds a QTabWidget with
    "Data Status" tab (DataStatusWidget) and "Terminal" tab (TerminalWidget).

    Args:
        settings_state: Application settings state.
        parent: Optional parent widget.
    """

    def __init__(self, settings_state: SettingsState, parent=None) -> None:
        super().__init__(parent)

        self.settings_state = settings_state
        self._settings_service = SettingsService()
        self._download_service = DownloadDataService(self._settings_service)
        self._process_service = ProcessService()

        self._initializing: bool = True

        self._build_ui()
        self._connect_signals()
        self._load_preferences()
        self._initializing = False
        self._update_command_preview()
        self._validate_inputs()

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
            Scroll-wrapped widget containing RunConfigForm (timeframe +
            timerange + pairs only), inline validation warnings, and
            Run/Stop buttons.
        """
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Page title
        title = QLabel("Download Data")
        title.setObjectName("page_title")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # RunConfigForm (timeframe + timerange + pairs only, no strategy)
        self.run_config_form = RunConfigForm(
            settings_state=self.settings_state,
            show_strategy=False,
            show_timeframe=True,
            show_timerange=True,
            show_pairs=True,
        )
        layout.addWidget(self.run_config_form)

        # Inline validation warnings
        self._validation_label = QLabel()
        self._validation_label.setWordWrap(True)
        self._validation_label.setObjectName("warning_banner")
        self._validation_label.setStyleSheet(
            "background-color: #3a2a1a; color: #ce9178; "
            "padding: 8px; border-radius: 4px; font-size: 11px;"
        )
        self._validation_label.hide()
        layout.addWidget(self._validation_label)

        # Run / Stop buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._run_btn = QPushButton("Download")
        self._run_btn.setAccessibleName("Download data")
        self._run_btn.setToolTip("Start downloading data with the current configuration")
        self._run_btn.clicked.connect(self._run_download)
        btn_layout.addWidget(self._run_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setAccessibleName("Stop download")
        self._stop_btn.setToolTip("Stop the running download process")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._process_service.stop_process)
        btn_layout.addWidget(self._stop_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()

        # Wrap in scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        scroll.setMinimumWidth(300)
        scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        return scroll

    def _build_right_panel(self) -> QWidget:
        """Build the right output panel.

        Returns:
            Widget containing tabbed output (Data Status + Terminal).
        """
        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Tabbed output
        self._output_tabs = QTabWidget()

        self._data_status_widget = DataStatusWidget()
        self._output_tabs.addTab(self._data_status_widget, "Data Status")

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

    def _on_settings_changed(self, settings) -> None:
        """Update data status widget and command preview when settings change."""
        self._data_status_widget.set_user_data_path(
            settings.user_data_path if settings else None
        )
        self._update_command_preview()

    def _on_config_changed(self, _config: dict) -> None:
        """Update command preview and validation when form values change."""
        if not self._initializing:
            self._update_command_preview()
            self._validate_inputs()

    # ------------------------------------------------------------------
    # Command Preview
    # ------------------------------------------------------------------

    def _update_command_preview(self) -> None:
        """Rebuild the command preview in the terminal from current form values."""
        try:
            cfg = self.run_config_form.get_config()
            timeframe = cfg.get("timeframe", "").strip()
            timerange = cfg.get("timerange", "").strip() or None
            pairs: List[str] = cfg.get("pairs", [])

            if not timeframe:
                self._terminal.set_command("[Configure timeframe]")
                return
            if not pairs:
                self._terminal.set_command("[Select pairs to download]")
                return

            cmd = self._download_service.build_command(
                timeframe=timeframe,
                timerange=timerange,
                pairs=pairs,
            )
            self._terminal.set_command_list(cmd.as_list())
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Inline Validation
    # ------------------------------------------------------------------

    def _validate_inputs(self) -> None:
        """Show inline warnings for short timeranges or missing data context."""
        warnings = []
        cfg = self.run_config_form.get_config()
        raw = cfg.get("timerange", "").strip()

        if raw and "-" in raw:
            parts = raw.split("-")
            if len(parts) == 2 and len(parts[0]) == 8 and len(parts[1]) == 8:
                try:
                    start = datetime.strptime(parts[0], "%Y%m%d")
                    end = datetime.strptime(parts[1], "%Y%m%d")
                    days = (end - start).days

                    if days < 7:
                        warnings.append(
                            f"⚠ Timerange is only {days} day(s). "
                            "For backtesting you need at least 30 days; "
                            "for hyperopt at least 90 days."
                        )
                    elif days < 30:
                        warnings.append(
                            f"⚠ {days} days is enough for basic backtesting but "
                            "too short for reliable hyperopt (need 90+ days)."
                        )

                    tf = cfg.get("timeframe", "").strip()
                    if tf in ("1d", "3d", "1w") and days < 365:
                        warnings.append(
                            "⚠ Daily/weekly timeframes need at least 1 year of data "
                            "for meaningful results."
                        )
                except ValueError:
                    warnings.append("⚠ Invalid timerange format. Use YYYYMMDD-YYYYMMDD.")

        if warnings:
            self._validation_label.setText("\n\n".join(warnings))
            self._validation_label.show()
        else:
            self._validation_label.hide()

    # ------------------------------------------------------------------
    # Run / Stop
    # ------------------------------------------------------------------

    def _run_download(self) -> None:
        """Validate form and start the download process."""
        cfg = self.run_config_form.get_config()
        timeframe = cfg.get("timeframe", "").strip()
        timerange = cfg.get("timerange", "").strip() or None
        pairs: List[str] = cfg.get("pairs", [])

        if not timeframe:
            QMessageBox.warning(self, "Missing Input", "Please enter a timeframe.")
            return
        if not pairs:
            QMessageBox.warning(
                self, "Missing Input", "Please select at least one pair."
            )
            return

        _log.info(
            "Download requested | timeframe=%s | timerange=%s | pairs=%s",
            timeframe,
            timerange or "(all)",
            pairs,
        )

        self._save_preferences()

        try:
            cmd = self._download_service.build_command(
                timeframe=timeframe,
                timerange=timerange,
                pairs=pairs,
            )
        except (ValueError, FileNotFoundError) as exc:
            QMessageBox.critical(self, "Download Setup Failed", str(exc))
            return

        # Prepare terminal
        self._terminal.clear_output()
        self._terminal.append_output(f"$ {cmd.to_display_string()}\n")
        self._terminal.append_output(
            f"Timeframe: {timeframe}\n"
            f"Timerange: {timerange or 'default'}\n"
            f"Pairs: {', '.join(pairs)}\n\n"
        )

        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._terminal.append_output("[Download started]\n\n")
        self._output_tabs.setCurrentIndex(1)  # Terminal tab

        try:
            self._process_service.execute_command(
                command=cmd.as_list(),
                on_output=self._terminal.append_output,
                on_error=self._terminal.append_error,
                on_finished=self._on_process_finished,
                working_directory=cmd.cwd,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Process Error", str(exc))
            self._run_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)

    def _on_process_finished(self, exit_code: int) -> None:
        """Handle process completion.

        Args:
            exit_code: Process exit code.
        """
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._terminal.append_output(f"\n[Download finished] exit_code={exit_code}\n")
        _log.info("Download process finished | exit_code=%d", exit_code)

        if exit_code == 0:
            self._data_status_widget.refresh()
            self._output_tabs.setCurrentIndex(0)  # Data Status tab

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------

    def _load_preferences(self) -> None:
        """Populate form from saved download preferences."""
        settings = self.settings_state.current_settings
        if not settings or not settings.download_preferences:
            return

        prefs = settings.download_preferences
        cfg: dict = {}

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

        # Set user_data_path for data status widget
        self._data_status_widget.set_user_data_path(
            settings.user_data_path if settings else None
        )

    def _save_preferences(self) -> None:
        """Persist current form values to download preferences."""
        settings = self.settings_state.current_settings
        if not settings or not settings.download_preferences:
            return

        prefs = settings.download_preferences
        cfg = self.run_config_form.get_config()

        prefs.default_timeframe = cfg.get("timeframe", "")
        prefs.default_timerange = cfg.get("timerange", "")
        pairs: List[str] = cfg.get("pairs", [])
        prefs.default_pairs = ",".join(pairs) if pairs else ""

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
        """Return the current download configuration as a plain dict.

        Returns:
            Dict with timeframe, timerange, pairs.
        """
        return self.run_config_form.get_config()

    def refresh(self) -> None:
        """Refresh data status widget (called by ModernMainWindow)."""
        _log.info("DownloadPage.refresh called")
        self._data_status_widget.refresh()
