"""run_config_form.py — Shared strategy/timeframe/pairs/timerange configuration form.

Used by BacktestPage, OptimizePage, and DownloadPage to provide a consistent
configuration UI. Emits config_changed(dict) whenever any field changes.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

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
from app.ui.theme import SPACING

_log = get_logger("ui.run_config_form")

# Ordered list of standard Freqtrade timeframes
_TIMEFRAMES = [
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
]

# Timerange preset labels and their day offsets (None = clear field)
_TIMERANGE_PRESETS: list[tuple[str, Optional[int]]] = [
    ("1M", 30),
    ("3M", 90),
    ("6M", 180),
    ("1Y", 365),
    ("YTD", None),   # handled specially
    ("All", -1),     # -1 = clear
]


def _compute_timerange(label: str) -> str:
    """Compute a YYYYMMDD-YYYYMMDD string for a preset label.

    Args:
        label: One of "1M", "3M", "6M", "1Y", "YTD", "All".

    Returns:
        Formatted timerange string, or "" for "All".
    """
    today = date.today()
    fmt = "%Y%m%d"

    if label == "All":
        return ""
    if label == "YTD":
        start = date(today.year, 1, 1)
        return f"{start.strftime(fmt)}-{today.strftime(fmt)}"

    days_map = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}
    days = days_map.get(label, 30)
    start = today - timedelta(days=days)
    return f"{start.strftime(fmt)}-{today.strftime(fmt)}"


class RunConfigForm(QWidget):
    """Shared strategy/timeframe/pairs/timerange configuration form.

    Args:
        settings_state: Application settings state providing strategy paths and favorites.
        show_strategy: Whether to show the strategy selector row.
        show_timeframe: Whether to show the timeframe selector row.
        show_timerange: Whether to show the timerange input row.
        show_pairs: Whether to show the pairs selector row.
        parent: Optional parent widget.

    Signals:
        config_changed(dict): Emitted whenever any field value changes.
            Dict keys: strategy, timeframe, timerange, pairs.
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
        self._selected_pairs: list[str] = []

        self._build_ui()
        self._connect_signals()
        self._refresh_strategies()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the form layout with conditional rows."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])

        form = QFormLayout()
        form.setSpacing(SPACING["sm"])
        form.setContentsMargins(0, 0, 0, 0)

        # ── Strategy ──────────────────────────────────────────────────
        if self._show_strategy:
            self._strategy_combo = QComboBox()
            self._strategy_combo.setObjectName("strategy_combo")
            self._strategy_combo.setAccessibleName("Strategy selector")
            self._strategy_combo.setToolTip("Select a strategy .py file from your strategies folder")
            form.addRow("Strategy:", self._strategy_combo)
        else:
            self._strategy_combo = None  # type: ignore[assignment]

        # ── Timeframe ─────────────────────────────────────────────────
        if self._show_timeframe:
            self._timeframe_combo = QComboBox()
            self._timeframe_combo.setObjectName("timeframe_combo")
            self._timeframe_combo.setAccessibleName("Timeframe selector")
            self._timeframe_combo.setToolTip("Select the candle timeframe for the run")
            self._timeframe_combo.addItems(_TIMEFRAMES)
            form.addRow("Timeframe:", self._timeframe_combo)
        else:
            self._timeframe_combo = None  # type: ignore[assignment]

        layout.addLayout(form)

        # ── Timerange ─────────────────────────────────────────────────
        if self._show_timerange:
            self._timerange_edit = QLineEdit()
            self._timerange_edit.setObjectName("timerange_edit")
            self._timerange_edit.setPlaceholderText("YYYYMMDD-YYYYMMDD")
            self._timerange_edit.setAccessibleName("Timerange input")
            self._timerange_edit.setToolTip(
                "Date range in YYYYMMDD-YYYYMMDD format, or use a preset button"
            )

            preset_row = QHBoxLayout()
            preset_row.setSpacing(SPACING["xs"])
            preset_row.setContentsMargins(0, 0, 0, 0)
            for label, _ in _TIMERANGE_PRESETS:
                btn = QPushButton(label)
                btn.setFixedWidth(40)
                btn.setToolTip(f"Set timerange to {label}")
                btn.setAccessibleName(f"Timerange preset {label}")
                btn.clicked.connect(lambda checked, lbl=label: self._on_preset_clicked(lbl))
                preset_row.addWidget(btn)
            preset_row.addStretch()

            tr_layout = QVBoxLayout()
            tr_layout.setSpacing(SPACING["xs"])
            tr_layout.setContentsMargins(0, 0, 0, 0)
            tr_label = QLabel("Timerange:")
            tr_layout.addWidget(tr_label)
            tr_layout.addWidget(self._timerange_edit)
            tr_layout.addLayout(preset_row)
            layout.addLayout(tr_layout)
        else:
            self._timerange_edit = None  # type: ignore[assignment]

        # ── Pairs ─────────────────────────────────────────────────────
        if self._show_pairs:
            self._pairs_btn = QPushButton("Select Pairs (0)")
            self._pairs_btn.setObjectName("pairs_btn")
            self._pairs_btn.setAccessibleName("Pairs selector")
            self._pairs_btn.setToolTip("Open the pairs selector dialog")
            self._pairs_btn.clicked.connect(self._on_pairs_clicked)

            pairs_layout = QVBoxLayout()
            pairs_layout.setSpacing(SPACING["xs"])
            pairs_layout.setContentsMargins(0, 0, 0, 0)
            pairs_label = QLabel("Pairs:")
            pairs_layout.addWidget(pairs_label)
            pairs_layout.addWidget(self._pairs_btn)
            layout.addLayout(pairs_layout)
        else:
            self._pairs_btn = None  # type: ignore[assignment]

        layout.addStretch()

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Wire internal widget signals to emit config_changed."""
        if self._strategy_combo is not None:
            self._strategy_combo.currentIndexChanged.connect(self._on_field_changed)
        if self._timeframe_combo is not None:
            self._timeframe_combo.currentIndexChanged.connect(self._on_field_changed)
        if self._timerange_edit is not None:
            self._timerange_edit.textChanged.connect(self._on_field_changed)

        # Refresh strategy list when settings change
        self._settings_state.settings_changed.connect(self._on_settings_changed)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_field_changed(self) -> None:
        """Emit config_changed with the current config dict."""
        self.config_changed.emit(self.get_config())

    def _on_preset_clicked(self, label: str) -> None:
        """Fill the timerange field with the computed preset value.

        Args:
            label: Preset label (e.g. "1M", "YTD", "All").
        """
        if self._timerange_edit is None:
            return
        value = _compute_timerange(label)
        self._timerange_edit.setText(value)
        # config_changed is emitted via textChanged → _on_field_changed

    def _on_pairs_clicked(self) -> None:
        """Open PairsSelectorDialog and update selected pairs."""
        from app.ui.dialogs.pairs_selector_dialog import PairsSelectorDialog

        settings = self._settings_state.current_settings
        favorites: list[str] = []
        if settings is not None:
            favorites = list(settings.favorite_pairs or [])

        dlg = PairsSelectorDialog(
            favorites=favorites,
            selected=list(self._selected_pairs),
            settings_state=self._settings_state,
            parent=self,
        )
        if dlg.exec():
            self._selected_pairs = dlg.get_selected_pairs()
            self._update_pairs_button()
            self.config_changed.emit(self.get_config())

    def _on_settings_changed(self) -> None:
        """Refresh strategy list when settings change."""
        self._refresh_strategies()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh_strategies(self) -> None:
        """Scan the strategies directory and populate the strategy combo."""
        if self._strategy_combo is None:
            return

        settings = self._settings_state.current_settings
        strategies: list[str] = []

        if settings is not None and settings.user_data_path:
            strategies_dir = Path(settings.user_data_path) / "strategies"
            if strategies_dir.is_dir():
                strategies = sorted(
                    p.stem
                    for p in strategies_dir.iterdir()
                    if p.suffix == ".py" and not p.name.startswith("_")
                )

        current = self._strategy_combo.currentText()
        self._strategy_combo.blockSignals(True)
        self._strategy_combo.clear()
        self._strategy_combo.addItems(strategies)
        # Restore previous selection if still available
        idx = self._strategy_combo.findText(current)
        if idx >= 0:
            self._strategy_combo.setCurrentIndex(idx)
        self._strategy_combo.blockSignals(False)

        _log.debug("Refreshed strategy list: %d strategies found", len(strategies))

    def _update_pairs_button(self) -> None:
        """Update the pairs button label to reflect the current selection count."""
        if self._pairs_btn is None:
            return
        n = len(self._selected_pairs)
        self._pairs_btn.setText(f"Select Pairs ({n})")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self) -> dict:
        """Return current form values as a plain dict.

        Returns:
            Dict with keys: strategy, timeframe, timerange, pairs.
        """
        return {
            "strategy": self._strategy_combo.currentText() if self._strategy_combo is not None else "",
            "timeframe": self._timeframe_combo.currentText() if self._timeframe_combo is not None else "",
            "timerange": self._timerange_edit.text() if self._timerange_edit is not None else "",
            "pairs": list(self._selected_pairs),
        }

    def set_config(self, config: dict) -> None:
        """Populate form from a dict.

        Args:
            config: Dict with optional keys: strategy, timeframe, timerange, pairs.
        """
        # Block signals during bulk update to avoid multiple config_changed emissions
        if self._strategy_combo is not None:
            self._strategy_combo.blockSignals(True)
        if self._timeframe_combo is not None:
            self._timeframe_combo.blockSignals(True)
        if self._timerange_edit is not None:
            self._timerange_edit.blockSignals(True)

        try:
            if self._strategy_combo is not None and "strategy" in config:
                idx = self._strategy_combo.findText(config["strategy"])
                if idx >= 0:
                    self._strategy_combo.setCurrentIndex(idx)

            if self._timeframe_combo is not None and "timeframe" in config:
                idx = self._timeframe_combo.findText(config["timeframe"])
                if idx >= 0:
                    self._timeframe_combo.setCurrentIndex(idx)

            if self._timerange_edit is not None and "timerange" in config:
                self._timerange_edit.setText(config.get("timerange", ""))

            if "pairs" in config:
                self._selected_pairs = list(config["pairs"])
                self._update_pairs_button()
        finally:
            if self._strategy_combo is not None:
                self._strategy_combo.blockSignals(False)
            if self._timeframe_combo is not None:
                self._timeframe_combo.blockSignals(False)
            if self._timerange_edit is not None:
                self._timerange_edit.blockSignals(False)

        _log.debug("RunConfigForm.set_config applied: %r", config)

    def validate(self) -> list[str]:
        """Return a list of validation error strings (empty list = valid).

        Returns:
            List of human-readable error messages. Empty if all fields are valid.
        """
        errors: list[str] = []

        if self._show_strategy:
            if self._strategy_combo is None or not self._strategy_combo.currentText().strip():
                errors.append("Strategy is required.")

        if self._show_timeframe:
            if self._timeframe_combo is None or not self._timeframe_combo.currentText().strip():
                errors.append("Timeframe is required.")

        if self._show_timerange and self._timerange_edit is not None:
            tr = self._timerange_edit.text().strip()
            if tr:
                # Validate YYYYMMDD-YYYYMMDD format
                parts = tr.split("-")
                if len(parts) != 2 or not all(len(p) == 8 and p.isdigit() for p in parts):
                    errors.append(
                        "Timerange must be in YYYYMMDD-YYYYMMDD format or left empty."
                    )

        if self._show_pairs and not self._selected_pairs:
            errors.append("At least one pair must be selected.")

        return errors
