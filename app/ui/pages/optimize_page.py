"""optimize_page.py — Hyperparameter optimisation (hyperopt) page.

Provides a two-panel layout: left panel for run configuration and hyperopt
options, right panel for live terminal output.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QSettings

from app.app_state.settings_state import SettingsState
from app.core.services.optimize_service import OptimizeService
from app.core.utils.app_logger import get_logger
from app.ui.dialogs.pairs_selector_dialog import PairsSelectorDialog
from app.ui.widgets.run_config_form import RunConfigForm
from app.ui.widgets.terminal_widget import TerminalWidget

_log = get_logger("ui.optimize_page")

_QSETTINGS_ORG = "FreqtradeGUI"
_QSETTINGS_APP = "ModernUI"
_SPLITTER_KEY = "splitter/optimize"

_LOSS_FUNCTIONS = [
    "SharpeHyperOptLoss",
    "CalmarHyperOptLoss",
    "SortinoHyperOptLoss",
    "OnlyProfitHyperOptLoss",
    "MaxDrawDownHyperOptLoss",
    "ProfitDrawDownHyperOptLoss",
]


class OptimizePage(QWidget):
    """Hyperopt configuration and execution page.

    Args:
        settings_state: Application settings state.
        parent: Optional parent widget.
    """

    def __init__(self, settings_state: SettingsState, parent=None) -> None:
        super().__init__(parent)
        self._settings_state = settings_state
        self._optimize_service = OptimizeService(settings_state.settings_service)
        self._restoring: bool = False  # guard against save-during-restore
        self._build_ui()
        self._connect_signals()
        self._restore_state()
        self._restore_preferences()  # load saved strategy/timeframe/pairs/timerange

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
        title_label = QLabel("Optimize")
        title_label.setObjectName("page_title")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        root.addWidget(title_bar)

        # Main splitter
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(4)
        root.addWidget(self._splitter, 1)

        # ── Left panel ─────────────────────────────────────────────────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(240)
        left_scroll.setMaximumWidth(360)

        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        # Run config form
        self.run_config_form = RunConfigForm(self._settings_state)
        left_layout.addWidget(self.run_config_form)

        # Hyperopt options group
        hyperopt_group = QGroupBox("Hyperopt Options")
        hyperopt_form = QFormLayout(hyperopt_group)
        hyperopt_form.setContentsMargins(8, 8, 8, 8)
        hyperopt_form.setSpacing(6)

        self._epochs_spin = QSpinBox()
        self._epochs_spin.setRange(1, 10000)
        self._epochs_spin.setValue(100)
        self._epochs_spin.setAccessibleName("Number of hyperopt epochs")
        self._epochs_spin.setToolTip("Number of hyperopt iterations to run")
        hyperopt_form.addRow("Epochs:", self._epochs_spin)

        self._loss_combo = QComboBox()
        self._loss_combo.addItems(_LOSS_FUNCTIONS)
        self._loss_combo.setAccessibleName("Hyperopt loss function")
        self._loss_combo.setToolTip("Loss function used to evaluate hyperopt results")
        hyperopt_form.addRow("Loss Function:", self._loss_combo)

        # Spaces checkboxes
        spaces_label = QLabel("Spaces:")
        hyperopt_form.addRow(spaces_label)

        self._space_buy = QCheckBox("buy")
        self._space_buy.setChecked(True)
        self._space_buy.setAccessibleName("Optimize buy space")
        hyperopt_form.addRow("", self._space_buy)

        self._space_sell = QCheckBox("sell")
        self._space_sell.setChecked(True)
        self._space_sell.setAccessibleName("Optimize sell space")
        hyperopt_form.addRow("", self._space_sell)

        self._space_roi = QCheckBox("roi")
        self._space_roi.setChecked(True)
        self._space_roi.setAccessibleName("Optimize ROI space")
        hyperopt_form.addRow("", self._space_roi)

        self._space_stoploss = QCheckBox("stoploss")
        self._space_stoploss.setChecked(True)
        self._space_stoploss.setAccessibleName("Optimize stoploss space")
        hyperopt_form.addRow("", self._space_stoploss)

        self._space_trailing = QCheckBox("trailing")
        self._space_trailing.setChecked(True)
        self._space_trailing.setAccessibleName("Optimize trailing stop space")
        hyperopt_form.addRow("", self._space_trailing)

        left_layout.addWidget(hyperopt_group)

        # Run / Stop buttons
        btn_row = QHBoxLayout()
        self._run_btn = QPushButton("Run Optimize")
        self._run_btn.setObjectName("success")
        self._run_btn.setAccessibleName("Run hyperopt optimization")
        self._run_btn.setToolTip("Validate configuration and start hyperopt")

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("danger")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setAccessibleName("Stop optimization")
        self._stop_btn.setToolTip("Terminate the running hyperopt process")

        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        left_layout.addLayout(btn_row)
        left_layout.addStretch()

        left_scroll.setWidget(left_content)
        self._splitter.addWidget(left_scroll)

        # ── Right panel ────────────────────────────────────────────────
        self._terminal = TerminalWidget()
        self._splitter.addWidget(self._terminal)

        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 3)
        self._splitter.setSizes([300, 900])

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Wire all internal signals."""
        self._run_btn.clicked.connect(self._on_run_clicked)
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        self._terminal.process_finished.connect(self._on_process_finished)
        self.run_config_form.config_changed.connect(self._on_config_changed)
        self._epochs_spin.valueChanged.connect(self._on_hyperopt_options_changed)
        self._loss_combo.currentIndexChanged.connect(self._on_hyperopt_options_changed)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_run_clicked(self) -> None:
        """Validate form and start hyperopt."""
        errors = self.run_config_form.validate()
        if errors:
            QMessageBox.warning(self, "Configuration Error", "\n".join(errors))
            return

        cfg = self.run_config_form.get_config()
        strategy = cfg["strategy"]
        timeframe = cfg["timeframe"]
        timerange = cfg.get("timerange") or None
        pairs = cfg.get("pairs") or []
        epochs = self._epochs_spin.value()
        loss_fn = self._loss_combo.currentText()

        spaces = []
        for chk, name in [
            (self._space_buy, "buy"),
            (self._space_sell, "sell"),
            (self._space_roi, "roi"),
            (self._space_stoploss, "stoploss"),
            (self._space_trailing, "trailing"),
        ]:
            if chk.isChecked():
                spaces.append(name)

        try:
            cmd = self._optimize_service.build_command(
                strategy_name=strategy,
                timeframe=timeframe,
                epochs=epochs,
                timerange=timerange,
                pairs=pairs,
                spaces=spaces,
                hyperopt_loss=loss_fn,
            )
        except Exception as e:
            QMessageBox.critical(self, "Command Build Error", str(e))
            _log.error("Failed to build optimize command: %s", e)
            return

        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._terminal.run_command(cmd.as_list())
        _log.info("Hyperopt started: strategy=%s epochs=%d", strategy, epochs)

    def _on_stop_clicked(self) -> None:
        """Stop the running hyperopt."""
        self._terminal.stop_process()
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        _log.info("Hyperopt stopped by user")

    def _on_process_finished(self, exit_code: int) -> None:
        """Re-enable Run button when process finishes."""
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        if exit_code == 0:
            _log.info("Hyperopt completed successfully")
        else:
            _log.warning("Hyperopt exited with code %d", exit_code)

    def _on_config_changed(self, _cfg: dict) -> None:
        """Persist preferences when form config changes."""
        if not self._restoring:
            self._save_preferences()

    def _on_hyperopt_options_changed(self, _=None) -> None:
        """Persist preferences when hyperopt options change."""
        if not self._restoring:
            self._save_preferences()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_strategy(self, strategy_name: str) -> None:
        """Pre-select a strategy (called from StrategyPage).

        Args:
            strategy_name: The strategy name to pre-select.
        """
        self.run_config_form.set_config({"strategy": strategy_name})
        _log.debug("Strategy pre-selected: %s", strategy_name)

    def _on_select_pairs(self) -> None:
        """Open PairsSelectorDialog directly (compatibility method for tests).

        Delegates to the RunConfigForm's pairs button handler.
        """
        settings = self._settings_state.current_settings
        favorites: list = []
        if settings is not None:
            favorites = list(settings.favorite_pairs or [])

        selected = self.run_config_form.get_config().get("pairs", [])
        dlg = PairsSelectorDialog(
            favorites=favorites,
            selected=list(selected),
            settings_state=self._settings_state,
            parent=self,
        )
        if dlg.exec():
            new_pairs = dlg.get_selected_pairs()
            self.run_config_form.set_config({"pairs": new_pairs})

    def _save_preferences(self) -> None:
        """Persist current form values to AppSettings.optimize_preferences."""
        if self._restoring:
            return
        settings = self._settings_state.current_settings
        if settings is None:
            return
        cfg = self.run_config_form.get_config()
        spaces = []
        for chk, name in [
            (self._space_buy, "buy"),
            (self._space_sell, "sell"),
            (self._space_roi, "roi"),
            (self._space_stoploss, "stoploss"),
            (self._space_trailing, "trailing"),
        ]:
            if chk.isChecked():
                spaces.append(name)
        prefs = settings.optimize_preferences.model_copy(update={
            "last_strategy": cfg.get("strategy", ""),
            "default_timeframe": cfg.get("timeframe", ""),
            "default_timerange": cfg.get("timerange", ""),
            "default_pairs": ",".join(cfg.get("pairs", [])),
            "epochs": self._epochs_spin.value(),
            "hyperopt_loss": self._loss_combo.currentText(),
            "spaces": ",".join(spaces),
        })
        updated = settings.model_copy(update={"optimize_preferences": prefs})
        self._restoring = True
        try:
            self._settings_state.save_settings(updated)
        finally:
            self._restoring = False
        _log.debug("Optimize preferences saved")

    def _restore_preferences(self) -> None:
        """Restore form values from AppSettings.optimize_preferences."""
        settings = self._settings_state.current_settings
        if settings is None:
            return
        self._restoring = True
        try:
            prefs = settings.optimize_preferences
            pairs = [p.strip() for p in prefs.default_pairs.split(",") if p.strip()]
            self.run_config_form.set_config({
                "strategy": prefs.last_strategy,
                "timeframe": prefs.default_timeframe,
                "timerange": prefs.default_timerange,
                "pairs": pairs,
            })
            self._epochs_spin.setValue(prefs.epochs)
            idx = self._loss_combo.findText(prefs.hyperopt_loss)
            if idx >= 0:
                self._loss_combo.setCurrentIndex(idx)
            # Restore spaces checkboxes
            saved_spaces = {s.strip() for s in prefs.spaces.split(",") if s.strip()}
            if saved_spaces:
                self._space_buy.setChecked("buy" in saved_spaces)
                self._space_sell.setChecked("sell" in saved_spaces)
                self._space_roi.setChecked("roi" in saved_spaces)
                self._space_stoploss.setChecked("stoploss" in saved_spaces)
                self._space_trailing.setChecked("trailing" in saved_spaces)
            _log.debug("Optimize preferences restored: strategy=%s timeframe=%s",
                       prefs.last_strategy, prefs.default_timeframe)
        finally:
            self._restoring = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _restore_state(self) -> None:
        """Restore splitter state from QSettings, falling back to default sizes."""
        qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        state = qs.value(_SPLITTER_KEY)
        if state is not None:
            restored = self._splitter.restoreState(state)
            sizes = self._splitter.sizes()
            if not restored or not sizes or sizes[0] < 100:
                self._splitter.setSizes([300, 900])

    def _save_state(self) -> None:
        """Persist splitter state to QSettings."""
        qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        qs.setValue(_SPLITTER_KEY, self._splitter.saveState())

    def hideEvent(self, event) -> None:  # noqa: N802
        """Save splitter state when page is hidden."""
        self._save_state()
        super().hideEvent(event)
