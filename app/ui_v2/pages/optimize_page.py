"""OptimizePage for the v2 UI layer.

Two-panel QSplitter layout: RunConfigForm + hyperopt options + collapsible
advisor on the left; TerminalWidget with revert toolbar on the right.

Requirements: 14.1, 14.5, 8.6
"""
from typing import List, Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.app_state.settings_state import SettingsState
from app.core.services.hyperopt_advisor import analyse as advise_hyperopt
from app.core.services.optimize_service import OptimizeService
from app.core.services.process_service import ProcessService
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger
from app.ui.widgets.terminal_widget import TerminalWidget
from app.ui_v2.widgets.run_config_form import RunConfigForm
from app.ui_v2.widgets.section_header import SectionHeader

_log = get_logger("ui_v2.pages.optimize_page")

_SETTINGS_KEY = "splitter/optimize"

_HYPEROPT_LOSS_FUNCTIONS = [
    "SharpeHyperOptLoss",
    "SortinoHyperOptLoss",
    "CalmarHyperOptLoss",
    "OnlyProfitHyperOptLoss",
    "MaxDrawDownHyperOptLoss",
    "MultiMetricHyperOptLoss",
]

_SPACES_OPTIONS = [
    "buy sell roi stoploss trailing",
    "buy sell",
    "roi stoploss trailing",
    "stoploss trailing",
    "roi",
]


class OptimizePage(QWidget):
    """Redesigned optimize (hyperopt) page using a QSplitter layout.

    Left panel holds a RunConfigForm (strategy / timeframe / timerange /
    pairs), a hyperopt options group (epochs, spaces, loss function), and a
    collapsible advisor SectionHeader.  Right panel holds a TerminalWidget
    with a revert button in the toolbar above it.

    Args:
        settings_state: Application settings state.
        parent: Optional parent widget.
    """

    def __init__(self, settings_state: SettingsState, parent=None) -> None:
        super().__init__(parent)

        self.settings_state = settings_state
        self._settings_service = SettingsService()
        self._optimize_service = OptimizeService(self._settings_service)
        self._process_service = ProcessService()

        self._initializing: bool = True
        self._last_json_backup: Optional[dict] = None
        self._last_json_path: Optional[str] = None
        self._current_suggestion = None
        self._last_advisor_strategy: str = ""

        self._build_ui()
        self._connect_signals()
        self._refresh_strategies()
        self._load_preferences()
        self._initializing = False
        self._update_command_preview()
        self._refresh_advisor()

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

        self._splitter.addWidget(self._build_left_panel())
        self._splitter.addWidget(self._build_right_panel())

        # Default proportions: 40% left, 60% right
        self._splitter.setStretchFactor(0, 40)
        self._splitter.setStretchFactor(1, 60)

        root.addWidget(self._splitter)

    def _build_left_panel(self) -> QWidget:
        """Build the left configuration panel.

        Returns:
            Scroll-wrapped widget containing RunConfigForm, hyperopt options,
            advisor section, and Run/Stop buttons.
        """
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Page title
        title = QLabel("Optimize")
        title.setObjectName("page_title")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # RunConfigForm (strategy / timeframe / timerange / pairs)
        self.run_config_form = RunConfigForm(
            settings_state=self.settings_state,
            show_strategy=True,
            show_timeframe=True,
            show_timerange=True,
            show_pairs=True,
        )
        layout.addWidget(self.run_config_form)

        # Hyperopt options group
        layout.addWidget(self._build_hyperopt_options())

        # Collapsible advisor section
        advisor_body = self._build_advisor_body()
        self._advisor_section = SectionHeader(
            title="Hyperopt Advisor",
            body=advisor_body,
            collapsed=True,
        )
        layout.addWidget(self._advisor_section)

        # Run / Stop buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._run_btn = QPushButton("Optimize")
        self._run_btn.setAccessibleName("Run hyperopt optimization")
        self._run_btn.setToolTip("Start hyperopt with the current configuration")
        self._run_btn.clicked.connect(self._run_optimize)
        btn_layout.addWidget(self._run_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setAccessibleName("Stop optimization")
        self._stop_btn.setToolTip("Stop the running optimization process")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._process_service.stop_process)
        btn_layout.addWidget(self._stop_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        scroll.setMinimumWidth(300)
        scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        return scroll

    def _build_hyperopt_options(self) -> QWidget:
        """Build the hyperopt-specific options group box.

        Returns:
            QGroupBox with epochs spinbox, spaces combobox, loss combobox,
            and inline warning labels below relevant fields.
        """
        group = QGroupBox("Hyperopt Options")
        form = QFormLayout(group)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(6)

        # Epochs
        self._epochs_spin = QSpinBox()
        self._epochs_spin.setRange(1, 100_000)
        self._epochs_spin.setValue(100)
        self._epochs_spin.setAccessibleName("Epochs")
        self._epochs_spin.setToolTip(
            "Number of hyperopt iterations to run. More epochs = better results but slower."
        )
        self._epochs_spin.setWhatsThis(
            "Each epoch evaluates one parameter combination. "
            "Use at least 100-500 epochs for meaningful results."
        )
        self._epochs_warning = QLabel()
        self._epochs_warning.setStyleSheet("color: #f44336; font-size: 11px;")
        self._epochs_warning.setWordWrap(True)
        self._epochs_warning.hide()
        epochs_col = QVBoxLayout()
        epochs_col.setSpacing(2)
        epochs_col.addWidget(self._epochs_spin)
        epochs_col.addWidget(self._epochs_warning)
        form.addRow("Epochs:", epochs_col)

        # Spaces
        self._spaces_combo = QComboBox()
        self._spaces_combo.setEditable(True)
        self._spaces_combo.addItems(_SPACES_OPTIONS)
        self._spaces_combo.setCurrentIndex(0)
        self._spaces_combo.setAccessibleName("Hyperopt spaces")
        self._spaces_combo.setToolTip(
            "Parameter spaces to search. Separate multiple spaces with spaces."
        )
        self._spaces_combo.setWhatsThis(
            "Hyperopt spaces define which parameters are optimized. "
            "Common choices: 'buy sell' for signal tuning, "
            "'roi stoploss trailing' for risk management."
        )
        self._spaces_warning = QLabel()
        self._spaces_warning.setStyleSheet("color: #f44336; font-size: 11px;")
        self._spaces_warning.setWordWrap(True)
        self._spaces_warning.hide()
        spaces_col = QVBoxLayout()
        spaces_col.setSpacing(2)
        spaces_col.addWidget(self._spaces_combo)
        spaces_col.addWidget(self._spaces_warning)
        form.addRow("Spaces:", spaces_col)

        # Loss function
        self._loss_combo = QComboBox()
        self._loss_combo.setEditable(True)
        self._loss_combo.addItems(_HYPEROPT_LOSS_FUNCTIONS)
        self._loss_combo.setCurrentIndex(0)
        self._loss_combo.setAccessibleName("Loss function")
        self._loss_combo.setToolTip(
            "Objective function used to score each hyperopt epoch."
        )
        self._loss_combo.setWhatsThis(
            "The loss function determines what 'better' means during optimization. "
            "SharpeHyperOptLoss balances profit and risk. "
            "MaxDrawDownHyperOptLoss prioritizes capital protection."
        )
        form.addRow("Loss Function:", self._loss_combo)

        return group

    def _build_advisor_body(self) -> QWidget:
        """Build the advisor panel body widget.

        Returns:
            Widget containing advisor status, tips, warnings, and
            auto-configure button.
        """
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        self._advisor_status = QLabel("Select a strategy to see recommendations.")
        self._advisor_status.setObjectName("hint_label")
        self._advisor_status.setWordWrap(True)
        header_row.addWidget(self._advisor_status, 1)

        self._auto_configure_btn = QPushButton("Auto-Configure")
        self._auto_configure_btn.setToolTip(
            "Apply recommended epochs, spaces and loss function based on last run analysis"
        )
        self._auto_configure_btn.setAccessibleName("Auto-configure hyperopt settings")
        self._auto_configure_btn.setEnabled(False)
        self._auto_configure_btn.clicked.connect(self._apply_advisor_suggestion)
        header_row.addWidget(self._auto_configure_btn)
        layout.addLayout(header_row)

        self._advisor_tips = QLabel()
        self._advisor_tips.setWordWrap(True)
        self._advisor_tips.setObjectName("success_banner")
        self._advisor_tips.hide()
        layout.addWidget(self._advisor_tips)

        self._advisor_warnings = QLabel()
        self._advisor_warnings.setWordWrap(True)
        self._advisor_warnings.setObjectName("warning_banner")
        self._advisor_warnings.hide()
        layout.addWidget(self._advisor_warnings)

        return body

    def _build_right_panel(self) -> QWidget:
        """Build the right terminal panel.

        Returns:
            Widget containing a toolbar (with revert button) above the
            TerminalWidget.
        """
        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Toolbar above terminal
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._revert_btn = QPushButton("Revert Parameters")
        self._revert_btn.setObjectName("secondary")
        self._revert_btn.setToolTip(
            "Restore strategy parameters to values before this optimization run"
        )
        self._revert_btn.setAccessibleName("Revert strategy parameters")
        self._revert_btn.setEnabled(False)
        self._revert_btn.clicked.connect(self._revert_parameters)
        toolbar.addWidget(self._revert_btn)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        self._terminal = TerminalWidget()
        layout.addWidget(self._terminal)

        return right

    # ------------------------------------------------------------------
    # Signal Wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Wire internal signals for live updates."""
        self.settings_state.settings_changed.connect(self._on_settings_changed)
        self.run_config_form.config_changed.connect(self._on_config_changed)
        self._epochs_spin.valueChanged.connect(self._on_hyperopt_option_changed)
        self._spaces_combo.currentTextChanged.connect(self._on_hyperopt_option_changed)
        self._loss_combo.currentTextChanged.connect(self._on_hyperopt_option_changed)

    def _on_settings_changed(self, _settings) -> None:
        """Refresh strategies when settings change."""
        self._refresh_strategies()

    def _on_config_changed(self, config: dict) -> None:
        """Update command preview and advisor when form values change."""
        if not self._initializing:
            self._update_command_preview()
            # Refresh advisor when strategy changes
            strategy = config.get("strategy", "").strip()
            if strategy != self._last_advisor_strategy:
                self._last_advisor_strategy = strategy
                self._refresh_advisor()

    def _on_hyperopt_option_changed(self, _value=None) -> None:
        """Update command preview and inline warnings when hyperopt options change."""
        if not self._initializing:
            self._validate_hyperopt_options()
            self._update_command_preview()

    # ------------------------------------------------------------------
    # Strategy Refresh
    # ------------------------------------------------------------------

    def _refresh_strategies(self) -> None:
        """Reload available strategies into the RunConfigForm combo."""
        strategies = self._optimize_service.get_available_strategies()
        self.run_config_form.set_strategy_choices(strategies)

    # ------------------------------------------------------------------
    # Inline Validation
    # ------------------------------------------------------------------

    def _validate_hyperopt_options(self) -> bool:
        """Validate hyperopt options and show inline warnings.

        Returns:
            True when all options are valid.
        """
        valid = True

        # Epochs warning
        epochs = self._epochs_spin.value()
        if epochs < 50:
            self._epochs_warning.setText(
                f"{epochs} epochs is very low. Use at least 100-500 for meaningful results."
            )
            self._epochs_warning.show()
            valid = False
        else:
            self._epochs_warning.hide()

        # Spaces warning
        spaces = self._parse_spaces()
        if not spaces:
            self._spaces_warning.setText("At least one hyperopt space is required.")
            self._spaces_warning.show()
            valid = False
        else:
            self._spaces_warning.hide()

        return valid

    # ------------------------------------------------------------------
    # Command Preview
    # ------------------------------------------------------------------

    def _update_command_preview(self) -> None:
        """Rebuild the command preview in the terminal from current form values."""
        try:
            cfg = self.run_config_form.get_config()
            strategy = cfg.get("strategy", "").strip()
            timeframe = cfg.get("timeframe", "").strip()
            timerange = cfg.get("timerange", "").strip() or None
            pairs: List[str] = cfg.get("pairs", [])
            epochs = self._epochs_spin.value()
            spaces = self._parse_spaces()
            hyperopt_loss = self._loss_combo.currentText().strip() or None

            if not strategy or not timeframe:
                self._terminal.set_command("[Configure strategy and timeframe]")
                return
            if not pairs:
                self._terminal.set_command("[Select pairs to optimize]")
                return
            if not spaces:
                self._terminal.set_command("[Select at least one hyperopt space]")
                return

            cmd = self._optimize_service.build_command(
                strategy_name=strategy,
                timeframe=timeframe,
                epochs=epochs,
                timerange=timerange,
                pairs=pairs,
                spaces=spaces,
                hyperopt_loss=hyperopt_loss,
            )
            self._terminal.set_command_list(cmd.as_list())
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Advisor
    # ------------------------------------------------------------------

    def _refresh_advisor(self, _=None) -> None:
        """Run the hyperopt advisor for the selected strategy and update the panel."""
        cfg = self.run_config_form.get_config()
        strategy = cfg.get("strategy", "").strip()
        settings = self.settings_state.current_settings

        if not strategy or not settings or not settings.user_data_path:
            self._advisor_status.setText("Select a strategy to see recommendations.")
            self._advisor_tips.hide()
            self._advisor_warnings.hide()
            self._auto_configure_btn.setEnabled(False)
            self._current_suggestion = None
            return

        try:
            suggestion = advise_hyperopt(strategy, settings.user_data_path)
            self._current_suggestion = suggestion

            if suggestion.source == "last_run":
                self._advisor_status.setText(
                    f"Analysis based on last run for {strategy}. "
                    f"Recommended: {suggestion.epochs} epochs, "
                    f"spaces: {' '.join(suggestion.spaces)}, "
                    f"loss: {suggestion.loss_function}"
                )
            else:
                self._advisor_status.setText(
                    f"No previous runs found for {strategy}. Showing general recommendations."
                )

            if suggestion.tips:
                self._advisor_tips.setText("\n".join(f"- {t}" for t in suggestion.tips))
                self._advisor_tips.show()
            else:
                self._advisor_tips.hide()

            if suggestion.warnings:
                self._advisor_warnings.setText("\n".join(f"Warning: {w}" for w in suggestion.warnings))
                self._advisor_warnings.show()
            else:
                self._advisor_warnings.hide()

            self._auto_configure_btn.setEnabled(True)

        except Exception as exc:
            _log.warning("Advisor failed for %s: %s", strategy, exc)
            self._advisor_status.setText("Could not load advisor recommendations.")
            self._auto_configure_btn.setEnabled(False)
            self._current_suggestion = None

    def _apply_advisor_suggestion(self) -> None:
        """Apply the current advisor suggestion to the hyperopt option fields."""
        suggestion = self._current_suggestion
        if not suggestion:
            return

        self._epochs_spin.blockSignals(True)
        self._spaces_combo.blockSignals(True)

        self._epochs_spin.setValue(suggestion.epochs)
        spaces_text = " ".join(suggestion.spaces)
        idx = self._spaces_combo.findText(spaces_text)
        if idx >= 0:
            self._spaces_combo.setCurrentIndex(idx)
        else:
            self._spaces_combo.setCurrentText(spaces_text)

        loss_idx = self._loss_combo.findText(suggestion.loss_function)
        if loss_idx >= 0:
            self._loss_combo.setCurrentIndex(loss_idx)
        else:
            self._loss_combo.setCurrentText(suggestion.loss_function)

        self._epochs_spin.blockSignals(False)
        self._spaces_combo.blockSignals(False)

        self._validate_hyperopt_options()
        self._update_command_preview()
        _log.info(
            "Auto-configured | epochs=%d | spaces=%s | loss=%s",
            suggestion.epochs,
            suggestion.spaces,
            suggestion.loss_function,
        )

    # ------------------------------------------------------------------
    # Run / Stop
    # ------------------------------------------------------------------

    def _parse_spaces(self) -> List[str]:
        """Parse the spaces combo text into a list of space names.

        Returns:
            List of non-empty space name strings.
        """
        raw = self._spaces_combo.currentText().replace(",", " ").strip()
        return [s for s in raw.split() if s]

    def _run_optimize(self) -> None:
        """Validate form and start the hyperopt process."""
        cfg = self.run_config_form.get_config()
        strategy = cfg.get("strategy", "").strip()
        timeframe = cfg.get("timeframe", "").strip()
        timerange = cfg.get("timerange", "").strip() or None
        pairs: List[str] = cfg.get("pairs", [])
        epochs = self._epochs_spin.value()
        spaces = self._parse_spaces()
        hyperopt_loss = self._loss_combo.currentText().strip() or None

        if not strategy:
            QMessageBox.warning(self, "Missing Input", "Please enter a strategy name.")
            return
        if not timeframe:
            QMessageBox.warning(self, "Missing Input", "Please enter a timeframe.")
            return
        if not pairs:
            QMessageBox.warning(self, "Missing Input", "Please select at least one pair.")
            return
        if not spaces:
            QMessageBox.warning(self, "Missing Input", "Please enter at least one hyperopt space.")
            return

        _log.info(
            "Hyperopt requested | strategy=%s | timeframe=%s | timerange=%s | "
            "epochs=%d | spaces=%s | pairs=%s",
            strategy,
            timeframe,
            timerange or "(all)",
            epochs,
            spaces,
            pairs,
        )

        self._save_preferences()

        try:
            cmd = self._optimize_service.build_command(
                strategy_name=strategy,
                timeframe=timeframe,
                epochs=epochs,
                timerange=timerange,
                pairs=pairs,
                spaces=spaces,
                hyperopt_loss=hyperopt_loss,
            )
        except (ValueError, FileNotFoundError) as exc:
            QMessageBox.critical(self, "Optimize Setup Failed", str(exc))
            return

        self._terminal.clear_output()
        self._terminal.append_output(f"$ {cmd.to_display_string()}\n")
        self._terminal.append_output(
            f"Config: {cmd.config_file}\n"
            f"Strategy: {cmd.strategy_file}\n"
            f"Pairs: {', '.join(pairs)}\n"
            f"Spaces: {', '.join(spaces)}\n"
            f"Loss: {hyperopt_loss or 'default'}\n\n"
        )

        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._revert_btn.setEnabled(False)
        self._terminal.append_output("[Optimize started]\n\n")

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
        self._terminal.append_output(f"\n[Optimize finished] exit_code={exit_code}\n")
        _log.info("Optimize process finished | exit_code=%d", exit_code)

        if exit_code == 0:
            self._refresh_advisor()

    # ------------------------------------------------------------------
    # Revert Parameters
    # ------------------------------------------------------------------

    def _revert_parameters(self) -> None:
        """Restore strategy JSON to the backup taken before this optimization run."""
        if not self._last_json_backup or not self._last_json_path:
            return

        import json
        import os
        from pathlib import Path

        tmp = Path(self._last_json_path).with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(self._last_json_backup, indent=2), encoding="utf-8")
            os.replace(tmp, self._last_json_path)
            self._revert_btn.setEnabled(False)
            self._terminal.append_output("\n[Parameters reverted to pre-optimization values]\n")
            _log.info("Reverted strategy JSON: %s", self._last_json_path)
        except Exception as exc:
            QMessageBox.critical(self, "Revert Failed", str(exc))

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------

    def _load_preferences(self) -> None:
        """Populate form from saved optimize preferences."""
        settings = self.settings_state.current_settings
        if not settings or not settings.optimize_preferences:
            return

        prefs = settings.optimize_preferences
        cfg: dict = {}

        if prefs.last_strategy:
            cfg["strategy"] = prefs.last_strategy
        if prefs.default_timeframe:
            cfg["timeframe"] = prefs.default_timeframe
        if prefs.default_timerange:
            cfg["timerange"] = prefs.default_timerange
        if prefs.default_pairs:
            cfg["pairs"] = [p.strip() for p in prefs.default_pairs.split(",") if p.strip()]

        if cfg:
            self.run_config_form.set_config(cfg)

        if prefs.epochs:
            self._epochs_spin.blockSignals(True)
            self._epochs_spin.setValue(prefs.epochs)
            self._epochs_spin.blockSignals(False)

        if prefs.spaces:
            self._spaces_combo.blockSignals(True)
            idx = self._spaces_combo.findText(prefs.spaces)
            if idx >= 0:
                self._spaces_combo.setCurrentIndex(idx)
            else:
                self._spaces_combo.setCurrentText(prefs.spaces)
            self._spaces_combo.blockSignals(False)

        if prefs.hyperopt_loss:
            self._loss_combo.blockSignals(True)
            idx = self._loss_combo.findText(prefs.hyperopt_loss)
            if idx >= 0:
                self._loss_combo.setCurrentIndex(idx)
            else:
                self._loss_combo.setCurrentText(prefs.hyperopt_loss)
            self._loss_combo.blockSignals(False)

    def _save_preferences(self) -> None:
        """Persist current form values to optimize preferences."""
        settings = self.settings_state.current_settings
        if not settings or not settings.optimize_preferences:
            return

        prefs = settings.optimize_preferences
        cfg = self.run_config_form.get_config()

        prefs.last_strategy = cfg.get("strategy", "")
        prefs.default_timeframe = cfg.get("timeframe", "")
        prefs.default_timerange = cfg.get("timerange", "")
        pairs: List[str] = cfg.get("pairs", [])
        prefs.default_pairs = ",".join(pairs) if pairs else ""
        prefs.epochs = self._epochs_spin.value()
        prefs.spaces = self._spaces_combo.currentText().strip()
        prefs.hyperopt_loss = self._loss_combo.currentText().strip()

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
        """Return the current optimize configuration as a plain dict.

        Returns:
            Dict with strategy, timeframe, timerange, pairs, epochs,
            spaces, hyperopt_loss.
        """
        cfg = self.run_config_form.get_config()
        cfg["epochs"] = self._epochs_spin.value()
        cfg["spaces"] = self._parse_spaces()
        cfg["hyperopt_loss"] = self._loss_combo.currentText().strip()
        return cfg
