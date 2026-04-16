from typing import List, Optional
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.app_state.settings_state import SettingsState
from app.core.services.optimize_service import OptimizeService
from app.core.services.process_service import ProcessService
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger
from app.ui.dialogs.pairs_selector_dialog import PairsSelectorDialog
from app.ui.widgets.terminal_widget import TerminalWidget

_log = get_logger("optimize")


class OptimizePage(QWidget):
    """Page for running freqtrade hyperopt jobs."""

    def __init__(self, settings_state: SettingsState, parent=None):
        super().__init__(parent)
        self.settings_state = settings_state
        self.settings_service = SettingsService()
        self.optimize_service = OptimizeService(self.settings_service)
        self.process_service = ProcessService()
        self.selected_pairs: List[str] = []
        self._initializing = True

        self._build_ui()
        self._connect_signals()
        self._refresh_strategies()
        self._load_preferences()
        self._initializing = False
        self._update_command_preview()

    def _build_ui(self):
        root = QVBoxLayout(self)

        params_layout = QVBoxLayout()

        strategy_layout = QHBoxLayout()
        strategy_layout.addWidget(QLabel("Strategy:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.setEditable(True)
        strategy_layout.addWidget(self.strategy_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_strategies)
        strategy_layout.addWidget(refresh_btn)
        params_layout.addLayout(strategy_layout)

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
            btn.setMaximumWidth(50)
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
        self.pairs_display_label.setStyleSheet("color: #666; font-size: 9pt; padding-left: 4px;")
        pairs_layout.addWidget(self.pairs_display_label)
        params_layout.addLayout(pairs_layout)

        advanced_group = QGroupBox("Hyperopt Options")
        advanced_form = QFormLayout()

        self.epochs_spin = QSpinBox()
        self.epochs_spin.setRange(1, 100000)
        self.epochs_spin.setValue(100)
        advanced_form.addRow("Epochs:", self.epochs_spin)

        self.spaces_input = QLineEdit()
        self.spaces_input.setPlaceholderText("buy sell roi stoploss trailing")
        self.spaces_input.setText("buy sell roi stoploss trailing")
        advanced_form.addRow("Spaces:", self.spaces_input)

        self.loss_combo = QComboBox()
        self.loss_combo.setEditable(True)
        self.loss_combo.addItems(
            [
                "SharpeHyperOptLoss",
                "SortinoHyperOptLoss",
                "CalmarHyperOptLoss",
                "OnlyProfitHyperOptLoss",
                "MaxDrawDownHyperOptLoss",
                "MultiMetricHyperOptLoss",
            ]
        )
        advanced_form.addRow("Loss:", self.loss_combo)

        advanced_group.setLayout(advanced_form)
        params_layout.addWidget(advanced_group)

        button_layout = QHBoxLayout()
        self.run_button = QPushButton("Optimize")
        self.run_button.clicked.connect(self._run_optimize)
        button_layout.addWidget(self.run_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.process_service.stop_process)
        button_layout.addWidget(self.stop_button)
        button_layout.addStretch()
        params_layout.addLayout(button_layout)
        params_layout.addStretch()

        output_layout = QVBoxLayout()
        self.terminal = TerminalWidget()
        output_layout.addWidget(self.terminal)

        h_layout = QHBoxLayout()
        h_layout.addLayout(params_layout, 1)
        h_layout.addLayout(output_layout, 2)
        root.addLayout(h_layout)

    def _connect_signals(self):
        self.settings_state.settings_changed.connect(self._on_settings_changed)
        self.strategy_combo.currentTextChanged.connect(self._update_command_preview)
        self.timeframe_input.textChanged.connect(self._update_command_preview)
        self.timerange_input.textChanged.connect(self._update_command_preview)
        self.epochs_spin.valueChanged.connect(self._update_command_preview)
        self.spaces_input.textChanged.connect(self._update_command_preview)
        self.loss_combo.currentTextChanged.connect(self._update_command_preview)

    def _on_settings_changed(self, _settings):
        self._refresh_strategies()
        self._update_command_preview()

    def _refresh_strategies(self):
        strategies = self.optimize_service.get_available_strategies()
        current = self.strategy_combo.currentText()
        self.strategy_combo.blockSignals(True)
        self.strategy_combo.clear()
        self.strategy_combo.addItems(strategies)
        if current:
            idx = self.strategy_combo.findText(current)
            if idx >= 0:
                self.strategy_combo.setCurrentIndex(idx)
        self.strategy_combo.blockSignals(False)

    def _parse_spaces(self) -> List[str]:
        raw = self.spaces_input.text().replace(",", " ").strip()
        return [space for space in raw.split() if space]

    def _update_command_preview(self):
        if self._initializing:
            return

        try:
            strategy = self.strategy_combo.currentText().strip()
            timeframe = self.timeframe_input.text().strip()
            timerange = self.timerange_input.text().strip() or None
            epochs = self.epochs_spin.value()
            spaces = self._parse_spaces()
            hyperopt_loss = self.loss_combo.currentText().strip() or None

            if not strategy or not timeframe:
                self.terminal.set_command("[Configure strategy and timeframe]")
                return
            if not self.selected_pairs:
                self.terminal.set_command("[Select pairs to optimize]")
                return

            cmd = self.optimize_service.build_command(
                strategy_name=strategy,
                timeframe=timeframe,
                epochs=epochs,
                timerange=timerange,
                pairs=self.selected_pairs,
                spaces=spaces,
                hyperopt_loss=hyperopt_loss,
            )
            self.terminal.set_command_list(cmd.as_list())
        except Exception:
            pass

    def _run_optimize(self):
        strategy = self.strategy_combo.currentText().strip()
        timeframe = self.timeframe_input.text().strip()
        timerange = self.timerange_input.text().strip() or None
        epochs = self.epochs_spin.value()
        spaces = self._parse_spaces()
        hyperopt_loss = self.loss_combo.currentText().strip() or None

        if not strategy:
            QMessageBox.warning(self, "Missing Input", "Please enter a strategy name.")
            return
        if not timeframe:
            QMessageBox.warning(self, "Missing Input", "Please enter a timeframe.")
            return
        if not self.selected_pairs:
            QMessageBox.warning(self, "Missing Input", "Please select at least one pair.")
            return
        if not spaces:
            QMessageBox.warning(self, "Missing Input", "Please enter at least one hyperopt space.")
            return

        _log.info(
            "Hyperopt requested | strategy=%s | timeframe=%s | timerange=%s | epochs=%d | spaces=%s | pairs=%s",
            strategy,
            timeframe,
            timerange or "(all)",
            epochs,
            spaces,
            self.selected_pairs,
        )

        self._save_preferences()

        try:
            cmd = self.optimize_service.build_command(
                strategy_name=strategy,
                timeframe=timeframe,
                epochs=epochs,
                timerange=timerange,
                pairs=self.selected_pairs,
                spaces=spaces,
                hyperopt_loss=hyperopt_loss,
            )
        except (ValueError, FileNotFoundError) as exc:
            QMessageBox.critical(self, "Optimize Setup Failed", str(exc))
            return

        self.terminal.clear_output()
        self.terminal.append_output(f"$ {cmd.to_display_string()}\n")
        self.terminal.append_output(
            f"Config: {cmd.config_file}\n"
            f"Strategy: {cmd.strategy_file}\n"
            f"Pairs: {', '.join(self.selected_pairs)}\n"
            f"Spaces: {', '.join(spaces)}\n"
            f"Loss: {hyperopt_loss or 'default'}\n\n"
        )

        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.terminal.append_output("[Optimize started]\n\n")

        try:
            self.process_service.execute_command(
                command=cmd.as_list(),
                on_output=self.terminal.append_output,
                on_error=self.terminal.append_error,
                on_finished=self._on_process_finished,
                working_directory=cmd.cwd,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Process Error", str(exc))
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    def _on_process_finished(self, exit_code: int):
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.terminal.append_output(f"\n[Optimize finished] exit_code={exit_code}\n")

    def _load_preferences(self):
        settings = self.settings_state.current_settings
        if not settings or not settings.optimize_preferences:
            return

        prefs = settings.optimize_preferences
        self.strategy_combo.blockSignals(True)
        self.timeframe_input.blockSignals(True)
        self.timerange_input.blockSignals(True)
        self.epochs_spin.blockSignals(True)
        self.spaces_input.blockSignals(True)
        self.loss_combo.blockSignals(True)

        if prefs.last_strategy:
            idx = self.strategy_combo.findText(prefs.last_strategy)
            if idx >= 0:
                self.strategy_combo.setCurrentIndex(idx)
        if prefs.default_timeframe:
            self.timeframe_input.setText(prefs.default_timeframe)
        if prefs.default_timerange:
            self.timerange_input.setText(prefs.default_timerange)
        self.selected_pairs = (
            [pair.strip() for pair in prefs.default_pairs.split(",") if pair.strip()]
            if prefs.default_pairs
            else []
        )
        self.epochs_spin.setValue(prefs.epochs or 100)
        self.spaces_input.setText(prefs.spaces or "buy sell roi stoploss trailing")
        if prefs.hyperopt_loss:
            idx = self.loss_combo.findText(prefs.hyperopt_loss)
            if idx >= 0:
                self.loss_combo.setCurrentIndex(idx)
            else:
                self.loss_combo.setEditText(prefs.hyperopt_loss)

        self._update_pairs_display()

        self.strategy_combo.blockSignals(False)
        self.timeframe_input.blockSignals(False)
        self.timerange_input.blockSignals(False)
        self.epochs_spin.blockSignals(False)
        self.spaces_input.blockSignals(False)
        self.loss_combo.blockSignals(False)

    def _save_preferences(self):
        settings = self.settings_state.current_settings
        if not settings or not settings.optimize_preferences:
            return

        prefs = settings.optimize_preferences
        prefs.last_strategy = self.strategy_combo.currentText().strip()
        prefs.default_timeframe = self.timeframe_input.text().strip()
        prefs.default_timerange = self.timerange_input.text().strip()
        prefs.default_pairs = ",".join(self.selected_pairs) if self.selected_pairs else ""
        prefs.epochs = self.epochs_spin.value()
        prefs.spaces = self.spaces_input.text().strip()
        prefs.hyperopt_loss = self.loss_combo.currentText().strip()

        for pair in self.selected_pairs:
            if pair not in prefs.paired_favorites and len(prefs.paired_favorites) < 20:
                prefs.paired_favorites.append(pair)

        self.settings_state.save_settings(settings)

    def _on_timerange_preset(self, preset: str):
        from app.core.utils.date_utils import calculate_timerange_preset

        self.timerange_input.setText(calculate_timerange_preset(preset))
        settings = self.settings_state.current_settings
        if settings and settings.optimize_preferences:
            settings.optimize_preferences.last_timerange_preset = preset
            self.settings_state.save_settings(settings)

    def _on_select_pairs(self):
        settings = self.settings_state.current_settings
        favorites = settings.optimize_preferences.paired_favorites if settings else []

        dialog = PairsSelectorDialog(favorites, self.selected_pairs, self)
        if dialog.exec() == QDialog.Accepted:
            self.selected_pairs = dialog.get_selected_pairs()
            self._update_pairs_display()
            self._update_command_preview()

    def _update_pairs_display(self):
        count = len(self.selected_pairs)
        self.pairs_button.setText(f"Select Pairs... ({count})")
        if self.selected_pairs:
            self.pairs_display_label.setText(f"Selected: {', '.join(self.selected_pairs)}")
        else:
            self.pairs_display_label.setText("Selected: None")
