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
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.app_state.settings_state import SettingsState
from app.ui.theme import SPACING
from app.core.services.hyperopt_advisor import analyse as advise_hyperopt
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
        self._last_json_backup: Optional[dict] = None  # backup before hyperopt overwrites it
        self._last_json_path: Optional[str] = None

        self._build_ui()
        self._connect_signals()
        self._refresh_strategies()
        self._load_preferences()
        self._initializing = False
        self._update_command_preview()
        self._validate_data_window()
        self._refresh_advisor()

    def _build_ui(self):
        root = QVBoxLayout(self)

        params_layout = QVBoxLayout()
        params_layout.setContentsMargins(SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"])
        params_layout.setSpacing(SPACING["sm"])

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
        self.pairs_display_label.setObjectName("hint_label")
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

        self.revert_button = QPushButton("\u21a9 Revert Parameters")
        self.revert_button.setEnabled(False)
        self.revert_button.setToolTip("Restore strategy parameters to values before this optimization run")
        self.revert_button.setObjectName("secondary")
        self.revert_button.clicked.connect(self._revert_parameters)
        button_layout.addWidget(self.revert_button)

        button_layout.addStretch()
        params_layout.addLayout(button_layout)

        # Data quality warning
        self.data_warning_label = QLabel("")
        self.data_warning_label.setWordWrap(True)
        self.data_warning_label.setObjectName("warning_banner")
        self.data_warning_label.setVisible(False)
        params_layout.addWidget(self.data_warning_label)

        # Result quality warning
        self.result_warning_label = QLabel("")
        self.result_warning_label.setWordWrap(True)
        self.result_warning_label.setObjectName("warning_banner")
        self.result_warning_label.setVisible(False)
        params_layout.addWidget(self.result_warning_label)

        params_layout.addStretch()

        # ── Advisor panel ──────────────────────────────────────────────
        advisor_group = QGroupBox("💡 Hyperopt Advisor")
        advisor_group.setCheckable(True)
        advisor_group.setChecked(False)  # collapsed by default
        advisor_vbox = QVBoxLayout(advisor_group)

        advisor_header = QHBoxLayout()
        self._advisor_status = QLabel("Select a strategy to see recommendations.")
        self._advisor_status.setObjectName("hint_label")
        self._advisor_status.setWordWrap(True)
        advisor_header.addWidget(self._advisor_status, 1)

        self._auto_configure_btn = QPushButton("⚡ Auto-Configure")
        self._auto_configure_btn.setToolTip(
            "Apply recommended epochs, spaces and loss function based on last run analysis"
        )
        self._auto_configure_btn.setEnabled(False)
        self._auto_configure_btn.clicked.connect(self._apply_advisor_suggestion)
        advisor_header.addWidget(self._auto_configure_btn)
        advisor_vbox.addLayout(advisor_header)

        self._advisor_tips = QLabel("")
        self._advisor_tips.setWordWrap(True)
        self._advisor_tips.setObjectName("success_banner")
        self._advisor_tips.setVisible(False)
        advisor_vbox.addWidget(self._advisor_tips)

        self._advisor_warnings = QLabel("")
        self._advisor_warnings.setWordWrap(True)
        self._advisor_warnings.setObjectName("warning_banner")
        self._advisor_warnings.setVisible(False)
        advisor_vbox.addWidget(self._advisor_warnings)

        params_layout.addWidget(advisor_group)

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
        self.terminal = TerminalWidget()
        output_layout.addWidget(self.terminal)

        output_widget = QWidget()
        output_widget.setLayout(output_layout)

        h_layout = QHBoxLayout()
        h_layout.addWidget(params_scroll, 1)
        h_layout.addWidget(output_widget, 2)
        root.addLayout(h_layout)

    def _connect_signals(self):
        self.settings_state.settings_changed.connect(self._on_settings_changed)
        self.strategy_combo.currentTextChanged.connect(self._update_command_preview)
        self.strategy_combo.currentTextChanged.connect(self._refresh_advisor)
        self.timeframe_input.textChanged.connect(self._update_command_preview)
        self.timerange_input.textChanged.connect(self._update_command_preview)
        self.timerange_input.textChanged.connect(self._validate_data_window)
        self.epochs_spin.valueChanged.connect(self._update_command_preview)
        self.epochs_spin.valueChanged.connect(self._validate_data_window)
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
        self.revert_button.setEnabled(False)
        self.result_warning_label.setVisible(False)
        self.terminal.append_output("[Optimize started]\n\n")

        # Backup current strategy JSON before freqtrade overwrites it
        self._last_json_backup = None
        self._last_json_path = cmd.strategy_file.replace(".py", ".json")
        try:
            import json
            from pathlib import Path
            p = Path(self._last_json_path)
            if p.exists():
                self._last_json_backup = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass

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
        if exit_code == 0:
            self._check_result_quality()
            self._refresh_advisor()  # re-analyse with new results

    def _refresh_advisor(self, _=None):
        """Run the hyperopt advisor for the selected strategy and update the panel."""
        strategy = self.strategy_combo.currentText().strip()
        settings = self.settings_state.current_settings
        if not strategy or not settings or not settings.user_data_path:
            self._advisor_status.setText("Select a strategy to see recommendations.")
            self._advisor_tips.setVisible(False)
            self._advisor_warnings.setVisible(False)
            self._auto_configure_btn.setEnabled(False)
            self._current_suggestion = None
            return

        try:
            suggestion = advise_hyperopt(strategy, settings.user_data_path)
            self._current_suggestion = suggestion

            if suggestion.source == "last_run":
                self._advisor_status.setText(
                    f"Analysis based on last run for {strategy}. "
                    f"Recommended: {suggestion.epochs} epochs · "
                    f"spaces: {' '.join(suggestion.spaces)} · "
                    f"loss: {suggestion.loss_function}"
                )
            else:
                self._advisor_status.setText(
                    f"No previous runs found for {strategy}. Showing general recommendations."
                )

            if suggestion.tips:
                self._advisor_tips.setText("\n\n".join(f"• {t}" for t in suggestion.tips))
                self._advisor_tips.setVisible(True)
            else:
                self._advisor_tips.setVisible(False)

            if suggestion.warnings:
                self._advisor_warnings.setText("\n\n".join(f"⚠ {w}" for w in suggestion.warnings))
                self._advisor_warnings.setVisible(True)
            else:
                self._advisor_warnings.setVisible(False)

            self._auto_configure_btn.setEnabled(True)

        except Exception as e:
            _log.warning("Advisor failed for %s: %s", strategy, e)
            self._advisor_status.setText("Could not load advisor recommendations.")
            self._auto_configure_btn.setEnabled(False)
            self._current_suggestion = None

    def _apply_advisor_suggestion(self):
        """Apply the current advisor suggestion to the UI fields."""
        s = getattr(self, "_current_suggestion", None)
        if not s:
            return

        self.epochs_spin.blockSignals(True)
        self.spaces_input.blockSignals(True)

        self.epochs_spin.setValue(s.epochs)
        self.spaces_input.setText(" ".join(s.spaces))

        idx = self.loss_combo.findText(s.loss_function)
        if idx >= 0:
            self.loss_combo.setCurrentIndex(idx)
        else:
            self.loss_combo.setEditText(s.loss_function)

        self.epochs_spin.blockSignals(False)
        self.spaces_input.blockSignals(False)

        self._update_command_preview()
        self._validate_data_window()
        _log.info(
            "Auto-configured | epochs=%d | spaces=%s | loss=%s",
            s.epochs, s.spaces, s.loss_function,
        )

    def _validate_data_window(self):
        """Show a warning if the timerange is too short for reliable optimization."""
        warnings = []
        raw = self.timerange_input.text().strip()
        if raw and "-" in raw:
            parts = raw.split("-")
            if len(parts) == 2 and len(parts[0]) == 8 and len(parts[1]) == 8:
                try:
                    start = datetime.strptime(parts[0], "%Y%m%d")
                    end = datetime.strptime(parts[1], "%Y%m%d")
                    days = (end - start).days
                    if days < 30:
                        warnings.append(
                            f"⚠ Timerange is only {days} day(s). "
                            "Hyperopt needs at least 30 days of data to find reliable parameters. "
                            "Results on short windows are likely to overfit and perform worse on new data."
                        )
                except ValueError:
                    pass

        epochs = self.epochs_spin.value()
        if epochs < 50:
            warnings.append(
                f"⚠ {epochs} epochs is very low. Use at least 100–500 epochs for meaningful results."
            )

        if warnings:
            self.data_warning_label.setText("\n\n".join(warnings))
            self.data_warning_label.setVisible(True)
        else:
            self.data_warning_label.setVisible(False)

    def _check_result_quality(self):
        """Parse terminal output after optimization and warn if result is bad."""
        output = self.terminal.get_output() if hasattr(self.terminal, "get_output") else ""
        issues = []

        # Detect all-loss result
        import re
        m = re.search(r"\|\s*\*?\s*Best\s*\|[^|]+\|\s*(\d+)\s*\|\s*(\d+)\s+(\d+)\s+(\d+)", output)
        if m:
            trades, wins, draws, losses = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            if trades > 0 and wins == 0:
                issues.append(f"⚠ Best result had 0 wins out of {trades} trades — all losses.")

        # Detect negative total profit
        if re.search(r"Total profit\s+-", output) or re.search(r"\(-\d+\.\d+%\)", output):
            issues.append("⚠ Best result has negative total profit — the optimized parameters are worse than doing nothing.")

        # Detect very short data window from freqtrade's own log
        m2 = re.search(r"Hyperopting with data from .+ \((\d+) days?\)", output)
        if m2 and int(m2.group(1)) < 7:
            issues.append(
                f"⚠ Freqtrade only had {m2.group(1)} day(s) of actual data. "
                "Download more historical data before optimizing."
            )

        if issues:
            msg = "\n".join(issues)
            if self._last_json_backup:
                msg += "\n\nParameters were overwritten. Use ↩ Revert Parameters to restore the previous values."
                self.revert_button.setEnabled(True)
            self.result_warning_label.setText(msg)
            self.result_warning_label.setVisible(True)
        else:
            self.result_warning_label.setVisible(False)

    def _revert_parameters(self):
        """Restore strategy JSON to the backup taken before this optimization run."""
        if not self._last_json_backup or not self._last_json_path:
            return
        import json, os
        from pathlib import Path
        tmp = Path(self._last_json_path).with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(self._last_json_backup, indent=2), encoding="utf-8")
            os.replace(tmp, self._last_json_path)
            self.revert_button.setEnabled(False)
            self.result_warning_label.setVisible(False)
            self.terminal.append_output("\n[Parameters reverted to pre-optimization values]\n")
            _log.info("Reverted strategy JSON: %s", self._last_json_path)
        except Exception as e:
            QMessageBox.critical(self, "Revert Failed", str(e))

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
        favorites = settings.favorite_pairs if settings else []
        max_open_trades = settings.backtest_preferences.max_open_trades if settings else 1

        dialog = PairsSelectorDialog(
            favorites=favorites,
            selected=self.selected_pairs,
            settings_state=self.settings_state,
            max_open_trades=max_open_trades,
            parent=self,
        )
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
