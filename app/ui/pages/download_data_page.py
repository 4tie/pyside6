from typing import List, Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QGroupBox,
    QScrollArea,
    QTabWidget,
)
from PySide6.QtCore import Qt
from app.app_state.settings_state import SettingsState
from app.ui.theme import SPACING
from app.core.services.download_data_service import DownloadDataService
from app.core.services.process_service import ProcessService
from app.core.services.settings_service import SettingsService
from app.ui.dialogs.pairs_selector_dialog import PairsSelectorDialog
from app.ui.widgets.data_status_widget import DataStatusWidget
from app.ui.widgets.terminal_widget import TerminalWidget


class DownloadDataPage(QWidget):
    """Page for downloading and validating OHLCV market data."""

    def __init__(self, settings_state: SettingsState, parent=None):
        super().__init__(parent)
        self.settings_state = settings_state
        self.settings_service = SettingsService()
        self.download_data_service = DownloadDataService(self.settings_service)
        self.process_service = ProcessService()
        self.selected_pairs: List[str] = []
        self._initializing: bool = True

        self.init_ui()
        self._connect_signals()
        self._load_preferences()
        self._initializing = False
        self._update_command_preview()
        self._validate_inputs()

    def init_ui(self):
        """Initialize UI components."""
        main_layout = QVBoxLayout()

        params_layout = QVBoxLayout()
        params_layout.setContentsMargins(SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"])
        params_layout.setSpacing(SPACING["sm"])

        timeframe_layout = QHBoxLayout()
        timeframe_layout.addWidget(QLabel("Timeframe:"))
        self.timeframe_input = QLineEdit()
        self.timeframe_input.setPlaceholderText("5m, 1h, 4h, 1d, etc.")
        self.timeframe_input.setText("5m")
        timeframe_layout.addWidget(self.timeframe_input)
        params_layout.addLayout(timeframe_layout)

        presets_layout = QHBoxLayout()
        presets_layout.addWidget(QLabel("Timerange Presets:"))
        for preset in ["7d", "14d", "30d", "90d", "120d", "360d"]:
            btn = QPushButton(preset)
            btn.setMinimumWidth(48)
            btn.clicked.connect(lambda checked, p=preset: self._on_timerange_preset(p))
            presets_layout.addWidget(btn)
        presets_layout.addStretch()
        params_layout.addLayout(presets_layout)

        timerange_group = QGroupBox("Custom Timerange (Optional)")
        timerange_layout = QHBoxLayout()
        timerange_layout.addWidget(QLabel("Format: YYYYMMDD-YYYYMMDD"))
        self.timerange_input = QLineEdit()
        self.timerange_input.setPlaceholderText("e.g., 20240101-20241231")
        timerange_layout.addWidget(self.timerange_input)
        timerange_group.setLayout(timerange_layout)
        params_layout.addWidget(timerange_group)

        pairs_layout = QVBoxLayout()
        pairs_button_layout = QHBoxLayout()
        pairs_button_layout.addWidget(QLabel("Pairs:"))
        self.pairs_button = QPushButton("Select Pairs... (0)")
        self.pairs_button.clicked.connect(self._on_select_pairs)
        pairs_button_layout.addWidget(self.pairs_button)
        pairs_button_layout.addStretch()
        pairs_layout.addLayout(pairs_button_layout)

        self.pairs_display_label = QLabel("Selected: None")
        self.pairs_display_label.setObjectName("hint_label")
        pairs_layout.addWidget(self.pairs_display_label)
        params_layout.addLayout(pairs_layout)

        button_layout = QHBoxLayout()
        self.run_button = QPushButton("Download")
        self.run_button.clicked.connect(self._run_download)
        button_layout.addWidget(self.run_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.process_service.stop_process)
        button_layout.addWidget(self.stop_button)

        button_layout.addStretch()
        params_layout.addLayout(button_layout)

        # Validation warning
        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        self.validation_label.setObjectName("warning_banner")
        self.validation_label.setVisible(False)
        params_layout.addWidget(self.validation_label)

        params_layout.addStretch()

        # Wrap params in scroll area
        params_content = QWidget()
        params_content.setLayout(params_layout)

        params_scroll = QScrollArea()
        params_scroll.setWidgetResizable(True)
        params_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        params_scroll.setWidget(params_content)
        params_scroll.setMinimumWidth(380)
        params_scroll.setMaximumWidth(500)

        output_layout = QVBoxLayout()
        output_layout.setContentsMargins(SPACING["sm"], SPACING["sm"], SPACING["sm"], SPACING["sm"])

        self.output_tabs = QTabWidget()

        self.status_widget = DataStatusWidget()
        self.output_tabs.addTab(self.status_widget, "Data Status")

        self.terminal = TerminalWidget()
        self.output_tabs.addTab(self.terminal, "Terminal")

        output_layout.addWidget(self.output_tabs)

        output_widget = QWidget()
        output_widget.setLayout(output_layout)

        h_layout = QHBoxLayout()
        h_layout.addWidget(params_scroll, 1)
        h_layout.addWidget(output_widget, 2)

        main_layout.addLayout(h_layout)
        self.setLayout(main_layout)

    def _connect_signals(self):
        """Connect signals for live command preview updates."""
        self.settings_state.settings_changed.connect(self._on_settings_changed)
        self.timeframe_input.textChanged.connect(self._update_command_preview)
        self.timeframe_input.textChanged.connect(self._validate_inputs)
        self.timerange_input.textChanged.connect(self._update_command_preview)
        self.timerange_input.textChanged.connect(self._validate_inputs)
        self.settings_state.settings_changed.connect(self._update_command_preview)

    def _on_settings_changed(self, settings):
        """Called when settings change."""
        self._update_command_preview()
        self.status_widget.set_user_data_path(
            settings.user_data_path if settings else None
        )

    def _update_command_preview(self):
        """Update the command preview based on current UI values."""
        if self._initializing:
            return
        try:
            timeframe = self.timeframe_input.text().strip()
            timerange = self.timerange_input.text().strip() or None
            pairs = self.selected_pairs

            if not timeframe:
                self.terminal.set_command("[Configure timeframe]")
                return
            if not pairs:
                self.terminal.set_command("[Select pairs to download]")
                return

            cmd = self.download_data_service.build_command(
                timeframe=timeframe,
                timerange=timerange,
                pairs=pairs,
            )
            self.terminal.set_command_list(cmd.as_list())
        except Exception:
            pass

    def _run_download(self):
        """Run download-data with current parameters."""
        timeframe = self.timeframe_input.text().strip()
        timerange = self.timerange_input.text().strip() or None
        pairs = self.selected_pairs

        if not timeframe:
            QMessageBox.warning(self, "Missing Input", "Please enter a timeframe.")
            return
        if not pairs:
            QMessageBox.warning(self, "Missing Input", "Please select at least one pair.")
            return

        self._save_preferences()

        try:
            cmd = self.download_data_service.build_command(
                timeframe=timeframe,
                timerange=timerange,
                pairs=pairs,
            )
        except (ValueError, FileNotFoundError) as e:
            QMessageBox.critical(self, "Download Setup Failed", str(e))
            return

        command_string = cmd.to_display_string()

        self.terminal.clear_output()
        self.terminal.append_output(f"$ {command_string}\n")
        self.terminal.append_output(
            f"Timeframe: {timeframe}\n"
            f"Timerange: {timerange or 'default'}\n"
            f"Pairs: {', '.join(pairs)}\n\n"
        )

        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.terminal.append_output("[Download started]\n\n")
        self.output_tabs.setCurrentIndex(1)  # switch to Terminal tab

        try:
            self.process_service.execute_command(
                command=cmd.as_list(),
                on_output=self.terminal.append_output,
                on_error=self.terminal.append_error,
                on_finished=self._on_process_finished,
                working_directory=cmd.cwd,
            )
        except Exception as e:
            QMessageBox.critical(self, "Process Error", str(e))
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    def _validate_inputs(self):
        """Show warnings for short timeranges or missing data context."""
        warnings = []
        raw = self.timerange_input.text().strip()
        if raw and "-" in raw:
            parts = raw.split("-")
            if len(parts) == 2 and len(parts[0]) == 8 and len(parts[1]) == 8:
                try:
                    start = datetime.strptime(parts[0], "%Y%m%d")
                    end   = datetime.strptime(parts[1], "%Y%m%d")
                    days  = (end - start).days
                    if days < 7:
                        warnings.append(
                            f"⚠ Timerange is only {days} day(s). "
                            "For backtesting you need at least 30 days; for hyperopt at least 90 days."
                        )
                    elif days < 30:
                        warnings.append(
                            f"⚠ {days} days is enough for basic backtesting but too short for reliable hyperopt (need 90+ days)."
                        )
                    tf = self.timeframe_input.text().strip()
                    if tf in ("1d", "3d", "1w") and days < 365:
                        warnings.append(
                            f"⚠ Daily/weekly timeframes need at least 1 year of data for meaningful results."
                        )
                except ValueError:
                    warnings.append("⚠ Invalid timerange format. Use YYYYMMDD-YYYYMMDD.")

        if warnings:
            self.validation_label.setText("\n\n".join(warnings))
            self.validation_label.setVisible(True)
        else:
            self.validation_label.setVisible(False)

    def _on_process_finished(self, exit_code: int):
        """Called when download process finishes."""
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.terminal.append_output(f"\n[Download finished] exit_code={exit_code}\n")
        if exit_code == 0:
            self.status_widget.refresh()
            self.output_tabs.setCurrentIndex(0)  # switch to Data Status tab

    def _load_preferences(self):
        """Load saved preferences from settings."""
        settings = self.settings_state.current_settings
        if not settings or not settings.download_preferences:
            return

        prefs = settings.download_preferences

        self.timeframe_input.blockSignals(True)
        self.timerange_input.blockSignals(True)

        if prefs.default_timeframe:
            self.timeframe_input.setText(prefs.default_timeframe)
        if prefs.default_timerange:
            self.timerange_input.setText(prefs.default_timerange)
        self.selected_pairs = (
            [p.strip() for p in prefs.default_pairs.split(",") if p.strip()]
            if prefs.default_pairs else []
        )
        self._update_pairs_display()

        self.timeframe_input.blockSignals(False)
        self.timerange_input.blockSignals(False)

        self.status_widget.set_user_data_path(
            settings.user_data_path if settings else None
        )

    def _save_preferences(self):
        """Save current input values to settings."""
        settings = self.settings_state.current_settings
        if not settings or not settings.download_preferences:
            return

        prefs = settings.download_preferences
        prefs.default_timeframe = self.timeframe_input.text()
        prefs.default_timerange = self.timerange_input.text().strip()
        prefs.default_pairs = ",".join(self.selected_pairs) if self.selected_pairs else ""

        self.settings_state.save_settings(settings)

    def _on_timerange_preset(self, preset: str):
        """Handle timerange preset button click."""
        from app.core.utils.date_utils import calculate_timerange_preset

        self.timerange_input.setText(calculate_timerange_preset(preset))

        settings = self.settings_state.current_settings
        if settings and settings.download_preferences:
            settings.download_preferences.last_timerange_preset = preset
            self.settings_state.save_settings(settings)

    def _on_select_pairs(self):
        """Open pairs selector dialog."""
        settings = self.settings_state.current_settings
        favorites = settings.favorite_pairs if settings else []

        dialog = PairsSelectorDialog(
            favorites=favorites,
            selected=self.selected_pairs,
            settings_state=self.settings_state,
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            self.selected_pairs = dialog.get_selected_pairs()
            self._update_pairs_display()
            self._update_command_preview()

    def _update_pairs_display(self):
        """Update pairs button and display label."""
        count = len(self.selected_pairs)
        self.pairs_button.setText(f"Select Pairs... ({count})")
        if self.selected_pairs:
            self.pairs_display_label.setText(f"Selected: {', '.join(self.selected_pairs)}")
        else:
            self.pairs_display_label.setText("Selected: None")
