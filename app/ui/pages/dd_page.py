from pathlib import Path
from typing import Optional, List

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
    QTabWidget,
    QTreeWidget,
    QHeaderView,
)
from app.app_state.settings_state import SettingsState
from app.core.services.download_data_service import DownloadDataService
from app.core.services.settings_service import SettingsService
from app.core.services.process_service import ProcessService
from app.ui.widgets.terminal_widget import TerminalWidget
from app.ui.widgets.data_status_widget import DataStatusWidget
from app.ui.dialogs.pairs_selector_dialog import PairsSelectorDialog


class DDPage(QWidget):
    """Page for downloading and validating OHLCV market data."""

    def __init__(self, settings_state: SettingsState, parent=None):
        super().__init__(parent)
        self.settings_state = settings_state
        self.settings_service = SettingsService()
        self.download_service = DownloadDataService(self.settings_service)
        self.process_service = ProcessService()
        self.selected_pairs: List[str] = []
        self._initializing: bool = True

        self.init_ui()
        self._connect_signals()
        self._load_preferences()
        self._initializing = False
        self._update_command_preview()

    def init_ui(self):
        """Initialize UI components."""
        main_layout = QVBoxLayout()

        # Left panel: Parameters
        params_layout = QVBoxLayout()

        # Timeframe
        timeframe_layout = QHBoxLayout()
        timeframe_layout.addWidget(QLabel("Timeframe:"))
        self.timeframe_input = QLineEdit()
        self.timeframe_input.setPlaceholderText("5m, 1h, 4h, 1d, etc.")
        self.timeframe_input.setText("5m")
        timeframe_layout.addWidget(self.timeframe_input)
        params_layout.addLayout(timeframe_layout)

        # Timerange presets
        presets_layout = QHBoxLayout()
        presets_layout.addWidget(QLabel("Timerange Presets:"))
        for preset in ["7d", "14d", "30d", "90d", "120d", "360d"]:
            btn = QPushButton(preset)
            btn.setMaximumWidth(50)
            btn.clicked.connect(lambda checked, p=preset: self._on_timerange_preset(p))
            presets_layout.addWidget(btn)
        presets_layout.addStretch()
        params_layout.addLayout(presets_layout)

        # Custom timerange
        timerange_group = QGroupBox("Custom Timerange (Optional)")
        timerange_layout = QHBoxLayout()
        timerange_layout.addWidget(QLabel("Format: YYYYMMDD-YYYYMMDD"))
        self.timerange_input = QLineEdit()
        self.timerange_input.setPlaceholderText("e.g., 20240101-20241231")
        timerange_layout.addWidget(self.timerange_input)
        timerange_group.setLayout(timerange_layout)
        params_layout.addWidget(timerange_group)

        # Pairs selection
        pairs_layout = QVBoxLayout()
        pairs_button_layout = QHBoxLayout()
        pairs_button_layout.addWidget(QLabel("Pairs:"))
        self.pairs_button = QPushButton("Select Pairs... (0)")
        self.pairs_button.clicked.connect(self._on_select_pairs)
        pairs_button_layout.addWidget(self.pairs_button)
        pairs_button_layout.addStretch()
        pairs_layout.addLayout(pairs_button_layout)

        self.pairs_display_label = QLabel("Selected: None")
        self.pairs_display_label.setStyleSheet(
            "color: #666; font-size: 9pt; padding-left: 4px;"
        )
        pairs_layout.addWidget(self.pairs_display_label)
        params_layout.addLayout(pairs_layout)

        params_layout.addStretch()

        # Run / Stop buttons
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

        # Right panel: Terminal + Data Status
        output_layout = QVBoxLayout()
        self.output_tabs = QTabWidget()

        self.terminal = TerminalWidget()
        self.output_tabs.addTab(self.terminal, "Terminal Output")

        self.status_widget = DataStatusWidget()
        self.output_tabs.addTab(self.status_widget, "Data Status")

        output_layout.addWidget(self.output_tabs)

        # Main horizontal layout
        h_layout = QHBoxLayout()
        h_layout.addLayout(params_layout, 1)
        h_layout.addLayout(output_layout, 2)

        main_layout.addLayout(h_layout)
        self.setLayout(main_layout)

    def _build_status_widget(self) -> QWidget:
        """Build the data status panel showing downloaded files."""
        widget = QWidget()
        layout = QVBoxLayout()

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Downloaded Data Files:"))
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setMaximumWidth(70)
        refresh_btn.clicked.connect(self._refresh_data_status)
        header_layout.addWidget(refresh_btn)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.data_tree = QTreeWidget()
        self.data_tree.setHeaderLabels(["Pair / Exchange", "Timeframe", "Size"])
        self.data_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.data_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.data_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self.data_tree)

        self.status_summary_label = QLabel("")
        self.status_summary_label.setStyleSheet("color: #555; font-size: 9pt;")
        layout.addWidget(self.status_summary_label)

        widget.setLayout(layout)
        return widget

    def _connect_signals(self):
        """Connect signals for live command preview updates."""
        self.settings_state.settings_changed.connect(self._on_settings_changed)
        self.timeframe_input.textChanged.connect(self._update_command_preview)
        self.timerange_input.textChanged.connect(self._update_command_preview)
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

            cmd = self.download_service.build_command(
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
            cmd = self.download_service.build_command(
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

    def _on_process_finished(self, exit_code: int):
        """Called when download process finishes."""
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.terminal.append_output(f"\n[Download finished] exit_code={exit_code}\n")
        if exit_code == 0:
            self.status_widget.refresh()
            self.output_tabs.setCurrentIndex(1)

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

        settings = self.settings_state.current_settings
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

        for pair in self.selected_pairs:
            if pair not in prefs.paired_favorites and len(prefs.paired_favorites) < 20:
                prefs.paired_favorites.append(pair)

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
        favorites = settings.download_preferences.paired_favorites if settings else []

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
            self.pairs_display_label.setText(f"Selected: {', '.join(self.selected_pairs)}")
        else:
            self.pairs_display_label.setText("Selected: None")


from app.ui.pages.download_data_page import DownloadDataPage as DDPage

__all__ = ["DDPage"]
