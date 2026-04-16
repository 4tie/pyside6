from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QGroupBox, QFormLayout, QDoubleSpinBox, QSpinBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QSizePolicy,
)

from app.app_state.settings_state import SettingsState
from app.core.services.strategy_config_service import StrategyConfigService
from app.core.utils.app_logger import get_logger

_log = get_logger("strategy_config_page")


class StrategyConfigPage(QWidget):
    """Page for viewing and editing strategy parameter JSON files."""

    def __init__(self, settings_state: SettingsState, parent=None):
        super().__init__(parent)
        self.settings_state = settings_state
        self._current_path: Optional[Path] = None
        self._loaded_data: dict = {}
        self._buy_widgets: Dict[str, QWidget] = {}
        self._sell_widgets: Dict[str, QWidget] = {}

        self._build_ui()
        self._connect_signals()
        self._refresh_combo()

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Top toolbar
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Strategy:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.setMinimumWidth(200)
        toolbar.addWidget(self.strategy_combo, 1)

        self.reload_btn = QPushButton("Reload")
        self.reload_btn.clicked.connect(self._load)
        toolbar.addWidget(self.reload_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        toolbar.addWidget(self.save_btn)

        self.status_label = QLabel("")
        self.status_label.setMinimumWidth(120)
        toolbar.addWidget(self.status_label)
        root.addLayout(toolbar)

        # Main area: left scroll | right panel
        main = QHBoxLayout()

        # Left scroll area
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_content = QWidget()
        self._left_layout = QVBoxLayout(left_content)
        self._left_layout.setAlignment(Qt.AlignTop)

        # Parameters group
        params_group = QGroupBox("Parameters")
        params_form = QFormLayout(params_group)

        self.stoploss_spin = QDoubleSpinBox()
        self.stoploss_spin.setRange(-1.0, 0.0)
        self.stoploss_spin.setSingleStep(0.001)
        self.stoploss_spin.setDecimals(3)
        params_form.addRow("Stoploss:", self.stoploss_spin)

        self.max_open_trades_spin = QSpinBox()
        self.max_open_trades_spin.setRange(-1, 999)
        self.max_open_trades_spin.setValue(-1)
        params_form.addRow("Max Open Trades:", self.max_open_trades_spin)

        self._left_layout.addWidget(params_group)

        # Trailing stop group
        trailing_group = QGroupBox("Trailing Stop")
        trailing_form = QFormLayout(trailing_group)

        self.trailing_stop_chk = QCheckBox()
        trailing_form.addRow("Trailing Stop:", self.trailing_stop_chk)

        self.trailing_positive_spin = QDoubleSpinBox()
        self.trailing_positive_spin.setRange(0.0, 1.0)
        self.trailing_positive_spin.setSingleStep(0.001)
        self.trailing_positive_spin.setDecimals(3)
        trailing_form.addRow("Trailing Positive:", self.trailing_positive_spin)

        self.trailing_positive_offset_spin = QDoubleSpinBox()
        self.trailing_positive_offset_spin.setRange(0.0, 1.0)
        self.trailing_positive_offset_spin.setSingleStep(0.001)
        self.trailing_positive_offset_spin.setDecimals(3)
        trailing_form.addRow("Positive Offset:", self.trailing_positive_offset_spin)

        self.trailing_only_offset_chk = QCheckBox()
        trailing_form.addRow("Only Offset:", self.trailing_only_offset_chk)

        self._left_layout.addWidget(trailing_group)

        # Dynamic buy/sell groups (rebuilt on each load)
        self._buy_group = QGroupBox("Buy Params")
        self._buy_form = QFormLayout(self._buy_group)
        self._left_layout.addWidget(self._buy_group)

        self._sell_group = QGroupBox("Sell Params")
        self._sell_form = QFormLayout(self._sell_group)
        self._left_layout.addWidget(self._sell_group)

        left_scroll.setWidget(left_content)
        main.addWidget(left_scroll, 1)

        # Right panel — ROI table
        right_panel = QVBoxLayout()
        roi_group = QGroupBox("ROI Table")
        roi_layout = QVBoxLayout(roi_group)

        self.roi_table = QTableWidget(0, 2)
        self.roi_table.setHorizontalHeaderLabels(["Minutes", "ROI %"])
        self.roi_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.roi_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.roi_table.verticalHeader().setVisible(False)
        roi_layout.addWidget(self.roi_table)

        roi_btn_row = QHBoxLayout()
        add_row_btn = QPushButton("Add Row")
        add_row_btn.clicked.connect(self._add_roi_row)
        roi_btn_row.addWidget(add_row_btn)
        remove_row_btn = QPushButton("Remove Row")
        remove_row_btn.clicked.connect(self._remove_roi_row)
        roi_btn_row.addWidget(remove_row_btn)
        roi_btn_row.addStretch()
        roi_layout.addLayout(roi_btn_row)

        right_panel.addWidget(roi_group)
        right_panel.addStretch()

        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        main.addWidget(right_widget, 1)

        root.addLayout(main)

        # Bottom path label
        self._path_label = QLabel("")
        self._path_label.setStyleSheet("color: #666; font-size: 9pt;")
        root.addWidget(self._path_label)

    # ------------------------------------------------------------------ #
    # Signals                                                              #
    # ------------------------------------------------------------------ #

    def _connect_signals(self):
        self.strategy_combo.currentIndexChanged.connect(self._on_combo_changed)
        self.settings_state.settings_changed.connect(self._on_settings_changed)

    def _on_settings_changed(self, _=None):
        self._refresh_combo()

    def _on_combo_changed(self, _=None):
        self._load()

    # ------------------------------------------------------------------ #
    # Combo population                                                     #
    # ------------------------------------------------------------------ #

    def _refresh_combo(self):
        """Repopulate strategy combo from disk, preserving current selection."""
        settings = self.settings_state.current_settings
        if not settings or not settings.user_data_path:
            self.strategy_combo.blockSignals(True)
            self.strategy_combo.clear()
            self.strategy_combo.blockSignals(False)
            return

        strategies_dir = str(Path(settings.user_data_path) / "strategies")
        files = StrategyConfigService.get_strategy_json_files(strategies_dir)

        current = self.strategy_combo.currentText()
        self.strategy_combo.blockSignals(True)
        self.strategy_combo.clear()
        for f in files:
            self.strategy_combo.addItem(f.stem, userData=f)
        # Restore previous selection
        idx = self.strategy_combo.findText(current)
        if idx >= 0:
            self.strategy_combo.setCurrentIndex(idx)
        self.strategy_combo.blockSignals(False)

        if self.strategy_combo.count() > 0:
            self._load()

    # ------------------------------------------------------------------ #
    # Load                                                                 #
    # ------------------------------------------------------------------ #

    def _load(self):
        """Load the currently selected strategy JSON into all widgets."""
        json_path: Optional[Path] = self.strategy_combo.currentData()
        if not json_path:
            return

        try:
            data = StrategyConfigService.load(json_path)
        except (FileNotFoundError, ValueError) as e:
            self._set_status(str(e), error=True)
            _log.error("Load failed: %s", e)
            return

        self._current_path = json_path
        self._loaded_data = data
        params = data.get("params", {})

        # stoploss
        stoploss_val = params.get("stoploss", {}).get("stoploss", -0.1)
        self.stoploss_spin.setValue(float(stoploss_val))

        # max_open_trades
        mot = params.get("max_open_trades", {}).get("max_open_trades", -1)
        self.max_open_trades_spin.setValue(int(mot))

        # trailing
        t = params.get("trailing", {})
        self.trailing_stop_chk.setChecked(bool(t.get("trailing_stop", False)))
        self.trailing_positive_spin.setValue(float(t.get("trailing_stop_positive") or 0.0))
        self.trailing_positive_offset_spin.setValue(float(t.get("trailing_stop_positive_offset", 0.0)))
        self.trailing_only_offset_chk.setChecked(bool(t.get("trailing_only_offset_is_reached", False)))

        # ROI table
        roi = params.get("roi", {})
        self._populate_roi(roi)

        # Dynamic buy/sell
        self._populate_dynamic_group(self._buy_group, self._buy_form, params.get("buy", {}), self._buy_widgets)
        self._populate_dynamic_group(self._sell_group, self._sell_form, params.get("sell", {}), self._sell_widgets)

        self._path_label.setText(str(json_path))
        self._set_status("Loaded", error=False)
        _log.info("Loaded: %s", json_path.name)

    def _populate_roi(self, roi: dict):
        """Fill ROI table sorted by minutes ascending."""
        self.roi_table.setRowCount(0)
        for minutes, ratio in sorted(roi.items(), key=lambda x: int(x[0])):
            row = self.roi_table.rowCount()
            self.roi_table.insertRow(row)
            self.roi_table.setItem(row, 0, QTableWidgetItem(str(minutes)))
            self.roi_table.setItem(row, 1, QTableWidgetItem(f"{float(ratio) * 100:.4f}"))

    def _populate_dynamic_group(self, group: QGroupBox, form: QFormLayout, section: dict, store: dict):
        """Rebuild a dynamic form layout for buy or sell params."""
        # Clear existing widgets
        while form.rowCount():
            form.removeRow(0)
        store.clear()

        for key, val in section.items():
            if isinstance(val, bool):
                widget = QCheckBox()
                widget.setChecked(bool(val))
            elif isinstance(val, int):
                widget = QSpinBox()
                widget.setRange(-999999, 999999)
                widget.setValue(int(val))
            else:
                widget = QDoubleSpinBox()
                widget.setRange(-999999.0, 999999.0)
                widget.setDecimals(4)
                widget.setSingleStep(0.001)
                widget.setValue(float(val))
            form.addRow(f"{key}:", widget)
            store[key] = widget

        group.setVisible(bool(section))

    # ------------------------------------------------------------------ #
    # Save                                                                 #
    # ------------------------------------------------------------------ #

    def _save(self):
        """Collect all widgets and write back to the strategy JSON."""
        if not self._current_path or not self._loaded_data:
            self._set_status("Nothing loaded", error=True)
            return

        data = self._loaded_data.copy()
        params = dict(data.get("params", {}))

        # stoploss
        params["stoploss"] = {"stoploss": self.stoploss_spin.value()}

        # max_open_trades — only write if key existed or value != -1
        mot_val = self.max_open_trades_spin.value()
        if "max_open_trades" in params or mot_val != -1:
            params["max_open_trades"] = {"max_open_trades": mot_val}

        # trailing
        params["trailing"] = {
            "trailing_stop": self.trailing_stop_chk.isChecked(),
            "trailing_stop_positive": self.trailing_positive_spin.value() or None,
            "trailing_stop_positive_offset": self.trailing_positive_offset_spin.value(),
            "trailing_only_offset_is_reached": self.trailing_only_offset_chk.isChecked(),
        }

        # ROI
        roi = {}
        for row in range(self.roi_table.rowCount()):
            min_item = self.roi_table.item(row, 0)
            roi_item = self.roi_table.item(row, 1)
            if min_item and roi_item:
                try:
                    roi[min_item.text().strip()] = round(float(roi_item.text()) / 100, 6)
                except ValueError:
                    pass
        params["roi"] = roi

        # Dynamic buy/sell
        if self._buy_widgets:
            params["buy"] = self._collect_dynamic(self._buy_widgets)
        if self._sell_widgets:
            params["sell"] = self._collect_dynamic(self._sell_widgets)

        data["params"] = params

        try:
            StrategyConfigService.save(self._current_path, data)
            self._loaded_data = data
            self._set_status("Saved ✓", error=False)
        except ValueError as e:
            self._set_status(str(e), error=True)

    def _collect_dynamic(self, store: Dict[str, QWidget]) -> dict:
        """Read values from a dynamic widget store."""
        result = {}
        for key, widget in store.items():
            if isinstance(widget, QCheckBox):
                result[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                result[key] = widget.value()
            else:
                result[key] = widget.value()
        return result

    # ------------------------------------------------------------------ #
    # ROI table helpers                                                    #
    # ------------------------------------------------------------------ #

    def _add_roi_row(self):
        row = self.roi_table.rowCount()
        self.roi_table.insertRow(row)
        self.roi_table.setItem(row, 0, QTableWidgetItem("0"))
        self.roi_table.setItem(row, 1, QTableWidgetItem("0.0000"))

    def _remove_roi_row(self):
        rows = {idx.row() for idx in self.roi_table.selectedIndexes()}
        for row in sorted(rows, reverse=True):
            self.roi_table.removeRow(row)

    # ------------------------------------------------------------------ #
    # Status                                                               #
    # ------------------------------------------------------------------ #

    def _set_status(self, msg: str, error: bool):
        self.status_label.setText(msg)
        color = "#cc0000" if error else "#1a7f37"
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
