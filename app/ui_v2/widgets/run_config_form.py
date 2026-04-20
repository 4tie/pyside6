"""RunConfigForm widget for the v2 UI layer.

Shared strategy / timeframe / pairs configuration form used by
``BacktestPage``, ``OptimizePage``, and ``DownloadPage``.

Requirements: 4.1, 4.2, 4.3, 7.3, 7.4
"""
import re
from typing import Dict, List

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.app_state.settings_state import SettingsState
from app.core.utils.app_logger import get_logger
from app.ui.dialogs.pairs_selector_dialog import PairsSelectorDialog

_log = get_logger("ui_v2.run_config_form")

# Timerange pattern: YYYYMMDD-YYYYMMDD  or  YYYYMMDD-  or  -YYYYMMDD
_TIMERANGE_RE = re.compile(
    r"^(\d{8}-\d{8}|\d{8}-|-\d{8})$"
)

_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w"]


class RunConfigForm(QWidget):
    """Shared strategy / timeframe / pairs configuration form.

    Emits ``config_changed(dict)`` whenever any field changes.

    Args:
        settings_state:  Application settings state (for pairs dialog).
        show_strategy:   Show the strategy selector row (default ``True``).
        show_timeframe:  Show the timeframe selector row (default ``True``).
        show_timerange:  Show the timerange input row (default ``True``).
        show_pairs:      Show the pairs selector row (default ``True``).
        parent:          Optional parent widget.

    Signals:
        config_changed(dict): Emitted when any field value changes.
    """

    config_changed = Signal(dict)

    def __init__(
        self,
        settings_state: SettingsState,
        show_strategy: bool = True,
        show_timeframe: bool = True,
        show_timerange: bool = True,
        show_pairs: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._settings_state = settings_state
        self._show_strategy = show_strategy
        self._show_timeframe = show_timeframe
        self._show_timerange = show_timerange
        self._show_pairs = show_pairs

        self._selected_pairs: List[str] = []

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the form layout."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)

        # ── Strategy ──────────────────────────────────────────────────
        if self._show_strategy:
            self._strategy_combo = QComboBox()
            self._strategy_combo.setEditable(True)
            self._strategy_combo.setPlaceholderText("Select or type strategy…")
            self._strategy_combo.setAccessibleName("Strategy")
            self._strategy_combo.setToolTip("Freqtrade strategy class name")
            self._strategy_error = QLabel()
            self._strategy_error.setStyleSheet("color: #f44336; font-size: 11px;")
            self._strategy_error.hide()
            strategy_col = QVBoxLayout()
            strategy_col.setSpacing(2)
            strategy_col.addWidget(self._strategy_combo)
            strategy_col.addWidget(self._strategy_error)
            form.addRow("Strategy:", strategy_col)

        # ── Timeframe ─────────────────────────────────────────────────
        if self._show_timeframe:
            self._timeframe_combo = QComboBox()
            self._timeframe_combo.addItems(_TIMEFRAMES)
            self._timeframe_combo.setCurrentText("5m")
            self._timeframe_combo.setAccessibleName("Timeframe")
            self._timeframe_combo.setToolTip("Candle timeframe for the run")
            self._timeframe_error = QLabel()
            self._timeframe_error.setStyleSheet("color: #f44336; font-size: 11px;")
            self._timeframe_error.hide()
            tf_col = QVBoxLayout()
            tf_col.setSpacing(2)
            tf_col.addWidget(self._timeframe_combo)
            tf_col.addWidget(self._timeframe_error)
            form.addRow("Timeframe:", tf_col)

        # ── Timerange ─────────────────────────────────────────────────
        if self._show_timerange:
            self._timerange_edit = QLineEdit()
            self._timerange_edit.setPlaceholderText("e.g. 20230101-20231231")
            self._timerange_edit.setAccessibleName("Timerange")
            self._timerange_edit.setToolTip(
                "Date range in YYYYMMDD-YYYYMMDD format (or open-ended)"
            )
            self._timerange_edit.setWhatsThis(
                "Enter a date range as YYYYMMDD-YYYYMMDD.  "
                "You may omit either end: '20230101-' means from that date to now."
            )
            self._timerange_error = QLabel()
            self._timerange_error.setStyleSheet("color: #f44336; font-size: 11px;")
            self._timerange_error.hide()
            tr_col = QVBoxLayout()
            tr_col.setSpacing(2)
            tr_col.addWidget(self._timerange_edit)
            tr_col.addWidget(self._timerange_error)
            form.addRow("Timerange:", tr_col)

        # ── Pairs ─────────────────────────────────────────────────────
        if self._show_pairs:
            pairs_row = QHBoxLayout()
            pairs_row.setSpacing(6)
            self._pairs_btn = QPushButton("Select Pairs…")
            self._pairs_btn.setAccessibleName("Select trading pairs")
            self._pairs_btn.setToolTip("Open the pairs selector dialog")
            self._pairs_btn.clicked.connect(self._open_pairs_dialog)
            self._pairs_label = QLabel("No pairs selected")
            self._pairs_label.setStyleSheet("color: #888; font-size: 11px;")
            pairs_row.addWidget(self._pairs_btn)
            pairs_row.addWidget(self._pairs_label)
            pairs_row.addStretch()
            form.addRow("Pairs:", pairs_row)

        outer.addLayout(form)
        outer.addStretch()

    def _connect_signals(self) -> None:
        """Wire internal widget signals to ``_on_field_changed``."""
        if self._show_strategy:
            self._strategy_combo.currentTextChanged.connect(self._on_field_changed)
        if self._show_timeframe:
            self._timeframe_combo.currentTextChanged.connect(self._on_field_changed)
        if self._show_timerange:
            self._timerange_edit.textChanged.connect(self._on_field_changed)

    def _on_field_changed(self, _value=None) -> None:
        """Validate and emit ``config_changed`` with the current config dict."""
        self._validate()
        self.config_changed.emit(self.get_config())

    def _validate(self) -> bool:
        """Run inline validation; show/hide error labels.

        Returns:
            ``True`` when all visible fields are valid.
        """
        valid = True

        if self._show_strategy:
            strategy = self._strategy_combo.currentText().strip()
            if not strategy:
                self._strategy_error.setText("Strategy is required.")
                self._strategy_error.show()
                valid = False
            else:
                self._strategy_error.hide()

        if self._show_timeframe:
            tf = self._timeframe_combo.currentText().strip()
            if not tf:
                self._timeframe_error.setText("Timeframe is required.")
                self._timeframe_error.show()
                valid = False
            else:
                self._timeframe_error.hide()

        if self._show_timerange:
            tr = self._timerange_edit.text().strip()
            if tr and not _TIMERANGE_RE.match(tr):
                self._timerange_error.setText(
                    "Format: YYYYMMDD-YYYYMMDD (or open-ended)"
                )
                self._timerange_error.show()
                valid = False
            else:
                self._timerange_error.hide()

        return valid

    def _open_pairs_dialog(self) -> None:
        """Open ``PairsSelectorDialog`` and update the selected pairs."""
        settings = self._settings_state.current_settings
        favorites: List[str] = []
        if settings:
            favorites = list(settings.favorite_pairs)

        max_trades = 1
        if settings and settings.backtest_preferences:
            max_trades = settings.backtest_preferences.max_open_trades

        dlg = PairsSelectorDialog(
            favorites=favorites,
            selected=list(self._selected_pairs),
            settings_state=self._settings_state,
            max_open_trades=max_trades,
            parent=self,
        )
        if dlg.exec():
            self._selected_pairs = dlg.get_selected_pairs()
            self._update_pairs_label()
            self._on_field_changed()
            _log.debug("Pairs updated: %s", self._selected_pairs)

    def _update_pairs_label(self) -> None:
        """Refresh the pairs count label."""
        if not self._show_pairs:
            return
        count = len(self._selected_pairs)
        if count == 0:
            self._pairs_label.setText("No pairs selected")
        elif count == 1:
            self._pairs_label.setText(self._selected_pairs[0])
        else:
            self._pairs_label.setText(f"{count} pairs selected")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self) -> Dict:
        """Return current form values as a plain dict.

        Returns:
            Dict with keys: ``strategy``, ``timeframe``, ``timerange``,
            ``pairs`` — only keys for visible fields are included.
        """
        config: Dict = {}
        if self._show_strategy:
            config["strategy"] = self._strategy_combo.currentText().strip()
        if self._show_timeframe:
            config["timeframe"] = self._timeframe_combo.currentText().strip()
        if self._show_timerange:
            config["timerange"] = self._timerange_edit.text().strip()
        if self._show_pairs:
            config["pairs"] = list(self._selected_pairs)
        return config

    def set_config(self, config: Dict) -> None:
        """Populate form fields from a dict.

        Args:
            config: Dict with optional keys ``strategy``, ``timeframe``,
                    ``timerange``, ``pairs``.
        """
        # Block signals during bulk load to avoid spurious config_changed
        if self._show_strategy and "strategy" in config:
            self._strategy_combo.blockSignals(True)
            text = config["strategy"]
            idx = self._strategy_combo.findText(text)
            if idx >= 0:
                self._strategy_combo.setCurrentIndex(idx)
            else:
                self._strategy_combo.setCurrentText(text)
            self._strategy_combo.blockSignals(False)

        if self._show_timeframe and "timeframe" in config:
            self._timeframe_combo.blockSignals(True)
            idx = self._timeframe_combo.findText(config["timeframe"])
            if idx >= 0:
                self._timeframe_combo.setCurrentIndex(idx)
            else:
                self._timeframe_combo.setCurrentText(config["timeframe"])
            self._timeframe_combo.blockSignals(False)

        if self._show_timerange and "timerange" in config:
            self._timerange_edit.blockSignals(True)
            self._timerange_edit.setText(config["timerange"])
            self._timerange_edit.blockSignals(False)

        if self._show_pairs and "pairs" in config:
            self._selected_pairs = list(config["pairs"])
            self._update_pairs_label()

        self._validate()
        _log.debug("RunConfigForm.set_config: %s", config)

    def is_valid(self) -> bool:
        """Return ``True`` when all visible required fields pass validation.

        Returns:
            ``True`` if the form is currently valid.
        """
        return self._validate()

    def set_strategy_choices(self, strategies: List[str]) -> None:
        """Populate the strategy combo box with the given list.

        Args:
            strategies: List of strategy class name strings.
        """
        if not self._show_strategy:
            return
        current = self._strategy_combo.currentText()
        self._strategy_combo.blockSignals(True)
        self._strategy_combo.clear()
        self._strategy_combo.addItems(strategies)
        # Restore previous selection if still present
        idx = self._strategy_combo.findText(current)
        if idx >= 0:
            self._strategy_combo.setCurrentIndex(idx)
        elif current:
            self._strategy_combo.setCurrentText(current)
        self._strategy_combo.blockSignals(False)
