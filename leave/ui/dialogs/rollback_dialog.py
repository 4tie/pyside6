"""Confirmation dialog for strategy rollback operations."""
from __future__ import annotations
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QDialogButtonBox, QFrame, QWidget
)
from PySide6.QtCore import Qt

from app.core.utils.app_logger import get_logger
from app.ui import theme

_log = get_logger("ui.rollback_dialog")


class RollbackDialog(QDialog):
    """Modal confirmation dialog for strategy rollback.

    Displays the strategy name, run ID, and files that will be overwritten.
    Presents two checkboxes for scope selection. Disables the OK button when
    both checkboxes are unchecked.

    Usage::

        dlg = RollbackDialog(
            strategy_name="MyStrategy",
            run_id="run_20240315T143022_abc123",
            has_params=True,
            has_config=True,
            params_path=Path("/user_data/strategies/MyStrategy.json"),
            config_path=Path("/user_data/config.json"),
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted:
            restore_params = dlg.restore_params
            restore_config = dlg.restore_config
    """

    def __init__(
        self,
        strategy_name: str,
        run_id: str,
        has_params: bool,
        has_config: bool,
        params_path: Path,
        config_path: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm Rollback")
        self.setMinimumWidth(480)
        self.setModal(True)

        self._strategy_name = strategy_name
        self._run_id = run_id
        self._has_params = has_params
        self._has_config = has_config
        self._params_path = params_path
        self._config_path = config_path

        self._build()
        self._on_checkbox_changed()

        _log.debug(
            "RollbackDialog created for strategy=%s run=%s",
            strategy_name,
            run_id,
        )

    # ------------------------------------------------------------------
    def _build(self) -> None:
        """Construct the dialog layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── Title ─────────────────────────────────────────────────────
        title_lbl = QLabel("⏪  Rollback Strategy")
        title_lbl.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {theme.TEXT_PRIMARY};"
        )
        root.addWidget(title_lbl)

        # ── Info card ─────────────────────────────────────────────────
        info_frame = QFrame()
        info_frame.setStyleSheet(
            f"QFrame {{ background: {theme.BG_ELEVATED};"
            f" border: 1px solid {theme.BG_BORDER};"
            f" border-radius: 8px; }}"
        )
        info_lay = QVBoxLayout(info_frame)
        info_lay.setContentsMargins(14, 12, 14, 12)
        info_lay.setSpacing(6)

        strategy_lbl = QLabel(f"Strategy:  <b>{self._strategy_name}</b>")
        strategy_lbl.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: 13px;")
        info_lay.addWidget(strategy_lbl)

        run_lbl = QLabel(f"Run:  <b>{self._run_id}</b>")
        run_lbl.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: 13px;")
        info_lay.addWidget(run_lbl)

        root.addWidget(info_frame)

        # ── Files that will be overwritten ────────────────────────────
        overwrite_header = QLabel("Files that will be overwritten:")
        overwrite_header.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600;"
        )
        root.addWidget(overwrite_header)

        files_frame = QFrame()
        files_frame.setStyleSheet(
            f"QFrame {{ background: {theme.BG_SURFACE};"
            f" border: 1px solid {theme.BG_BORDER};"
            f" border-radius: 6px; }}"
        )
        files_lay = QVBoxLayout(files_frame)
        files_lay.setContentsMargins(12, 10, 12, 10)
        files_lay.setSpacing(4)

        if self._has_params:
            params_file_lbl = QLabel(str(self._params_path.resolve()))
            params_file_lbl.setStyleSheet(
                f"color: {theme.YELLOW}; font-size: 11px; font-family: {theme.FONT_MONO};"
            )
            params_file_lbl.setWordWrap(True)
            files_lay.addWidget(params_file_lbl)

        if self._has_config:
            config_file_lbl = QLabel(str(self._config_path.resolve()))
            config_file_lbl.setStyleSheet(
                f"color: {theme.YELLOW}; font-size: 11px; font-family: {theme.FONT_MONO};"
            )
            config_file_lbl.setWordWrap(True)
            files_lay.addWidget(config_file_lbl)

        if not self._has_params and not self._has_config:
            no_files_lbl = QLabel("No restorable files found in run directory.")
            no_files_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 12px;")
            files_lay.addWidget(no_files_lbl)

        root.addWidget(files_frame)

        # ── Scope checkboxes ──────────────────────────────────────────
        scope_header = QLabel("Select files to restore:")
        scope_header.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600;"
        )
        root.addWidget(scope_header)

        self._params_cb = QCheckBox("Restore strategy parameters (params.json)")
        self._params_cb.setChecked(self._has_params)
        self._params_cb.setEnabled(self._has_params)
        self._params_cb.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: 13px;")
        self._params_cb.stateChanged.connect(self._on_checkbox_changed)
        root.addWidget(self._params_cb)

        self._config_cb = QCheckBox("Restore Freqtrade config (config.snapshot.json)")
        self._config_cb.setChecked(False)
        self._config_cb.setEnabled(self._has_config)
        self._config_cb.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: 13px;")
        self._config_cb.stateChanged.connect(self._on_checkbox_changed)
        root.addWidget(self._config_cb)

        # ── Validation message ────────────────────────────────────────
        self._validation_lbl = QLabel("Select at least one file to restore")
        self._validation_lbl.setStyleSheet(
            f"color: {theme.RED}; font-size: 12px;"
        )
        self._validation_lbl.setVisible(False)
        root.addWidget(self._validation_lbl)

        # ── Button box ────────────────────────────────────────────────
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)

        ok_btn = self._button_box.button(QDialogButtonBox.Ok)
        if ok_btn:
            ok_btn.setObjectName("primary")
            ok_btn.setText("Rollback")

        root.addWidget(self._button_box)

    # ------------------------------------------------------------------
    def _on_checkbox_changed(self) -> None:
        """Enable/disable OK button and show/hide validation message."""
        either_checked = self._params_cb.isChecked() or self._config_cb.isChecked()
        ok_btn = self._button_box.button(QDialogButtonBox.Ok)
        if ok_btn:
            ok_btn.setEnabled(either_checked)
        self._validation_lbl.setVisible(not either_checked)

    # ------------------------------------------------------------------
    @property
    def restore_params(self) -> bool:
        """True if the params checkbox is checked."""
        return self._params_cb.isChecked()

    @property
    def restore_config(self) -> bool:
        """True if the config checkbox is checked."""
        return self._config_cb.isChecked()
