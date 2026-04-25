"""Confirmation dialog for exporting Accepted_Best parameters to the live strategy JSON."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from app.core.utils.app_logger import get_logger
from app.ui import theme

_log = get_logger("ui.dialogs.export_confirm_dialog")


class ExportConfirmDialog(QDialog):
    """Modal confirmation dialog for exporting Accepted_Best parameters.

    Reads the current parameter values directly from ``live_json_path`` on
    disk (handles file-not-found gracefully by treating current params as an
    empty dict).  Displays the target JSON file path, the current parameter
    values that will be overwritten, the new parameter values from
    ``Accepted_Best``, and a diff-style view of changed keys.

    An optional "Patch .py file" checkbox triggers a second confirmation
    dialog before proceeding.

    Usage::

        dlg = ExportConfirmDialog(
            live_json_path="/user_data/strategies/MyStrategy.json",
            new_params={"buy_rsi": 18, "sell_rsi": 70},
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted:
            patch_py = dlg.patch_py_file
    """

    def __init__(
        self,
        live_json_path: str,
        new_params: Dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm Export")
        self.setMinimumWidth(560)
        self.setMinimumHeight(400)
        self.setModal(True)

        self._live_json_path = live_json_path
        self._new_params = new_params
        self._current_params = self._load_current_params(live_json_path)

        self._build()

        _log.debug(
            "ExportConfirmDialog created for path=%s changed_keys=%d",
            live_json_path,
            len(self._changed_keys()),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_current_params(live_json_path: str) -> Dict[str, Any]:
        """Read and return the current params from the live JSON file.

        Returns an empty dict if the file does not exist or cannot be parsed,
        so the dialog can still be shown with a graceful fallback.
        """
        path = Path(live_json_path)
        if not path.exists():
            _log.warning(
                "ExportConfirmDialog: live JSON not found at %s — treating current params as empty",
                live_json_path,
            )
            return {}
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                _log.warning(
                    "ExportConfirmDialog: live JSON at %s is not a dict — treating current params as empty",
                    live_json_path,
                )
                return {}
            return data
        except (OSError, json.JSONDecodeError) as exc:
            _log.warning(
                "ExportConfirmDialog: failed to read live JSON at %s: %s — treating current params as empty",
                live_json_path,
                exc,
            )
            return {}

    def _changed_keys(self) -> set[str]:
        """Return the set of keys that differ between current and new params."""
        all_keys = set(self._current_params) | set(self._new_params)
        return {
            k for k in all_keys
            if self._current_params.get(k) != self._new_params.get(k)
        }

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Construct the dialog layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── Title ─────────────────────────────────────────────────────
        title_lbl = QLabel("📤  Export Best Parameters")
        title_lbl.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {theme.TEXT_PRIMARY};"
        )
        root.addWidget(title_lbl)

        # ── Target file path ──────────────────────────────────────────
        path_header = QLabel("Target file:")
        path_header.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600;"
        )
        root.addWidget(path_header)

        path_frame = QFrame()
        path_frame.setStyleSheet(
            f"QFrame {{ background: {theme.BG_SURFACE};"
            f" border: 1px solid {theme.BG_BORDER};"
            f" border-radius: 6px; }}"
        )
        path_lay = QVBoxLayout(path_frame)
        path_lay.setContentsMargins(12, 10, 12, 10)

        path_lbl = QLabel(self._live_json_path)
        path_lbl.setStyleSheet(
            f"color: {theme.YELLOW}; font-size: 11px; font-family: {theme.FONT_MONO};"
        )
        path_lbl.setWordWrap(True)
        path_lay.addWidget(path_lbl)

        # Show a warning if the file was not found on disk
        if not Path(self._live_json_path).exists():
            missing_lbl = QLabel("⚠  File not found — current values shown as absent")
            missing_lbl.setStyleSheet(
                f"color: {theme.YELLOW}; font-size: 11px;"
            )
            path_lay.addWidget(missing_lbl)

        root.addWidget(path_frame)

        # ── Diff view ─────────────────────────────────────────────────
        diff_header = QLabel("Parameter changes:")
        diff_header.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600;"
        )
        root.addWidget(diff_header)

        diff_scroll = QScrollArea()
        diff_scroll.setWidgetResizable(True)
        diff_scroll.setMaximumHeight(220)
        diff_scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {theme.BG_BORDER};"
            f" border-radius: 6px; background: {theme.BG_SURFACE}; }}"
        )

        diff_container = QWidget()
        diff_container.setStyleSheet(f"background: {theme.BG_SURFACE};")
        diff_lay = QVBoxLayout(diff_container)
        diff_lay.setContentsMargins(12, 10, 12, 10)
        diff_lay.setSpacing(4)

        changed = self._changed_keys()
        all_keys = sorted(set(self._current_params) | set(self._new_params))

        if not all_keys:
            empty_lbl = QLabel("No parameters to display.")
            empty_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 12px;")
            diff_lay.addWidget(empty_lbl)
        else:
            # Column header
            header_lbl = QLabel(
                f"{'Key':<30}  {'Current':<20}  {'New':<20}"
            )
            header_lbl.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; font-size: 11px;"
                f" font-family: {theme.FONT_MONO}; font-weight: 600;"
            )
            diff_lay.addWidget(header_lbl)

            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet(f"color: {theme.BG_BORDER};")
            diff_lay.addWidget(sep)

            for key in all_keys:
                cur_val = self._current_params.get(key, "<absent>")
                new_val = self._new_params.get(key, "<absent>")
                is_changed = key in changed

                row_text = (
                    f"{str(key):<30}  {str(cur_val):<20}  {str(new_val):<20}"
                )
                row_lbl = QLabel(row_text)
                row_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)

                if is_changed:
                    row_lbl.setStyleSheet(
                        f"color: {theme.GREEN}; font-size: 11px;"
                        f" font-family: {theme.FONT_MONO};"
                        f" background: {theme.GREEN_DIM};"
                        f" border-radius: 3px; padding: 1px 4px;"
                    )
                else:
                    row_lbl.setStyleSheet(
                        f"color: {theme.TEXT_SECONDARY}; font-size: 11px;"
                        f" font-family: {theme.FONT_MONO};"
                    )
                diff_lay.addWidget(row_lbl)

        diff_lay.addStretch()
        diff_scroll.setWidget(diff_container)
        root.addWidget(diff_scroll)

        # ── Changed keys summary ──────────────────────────────────────
        n_changed = len(changed)
        n_total = len(all_keys)
        summary_lbl = QLabel(
            f"{n_changed} of {n_total} parameter(s) will change."
            if n_total > 0
            else "No parameters found."
        )
        summary_lbl.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 12px;"
        )
        root.addWidget(summary_lbl)

        # ── Patch .py file checkbox ───────────────────────────────────
        self._patch_py_cb = QCheckBox("Patch .py file (update parameter defaults in source)")
        self._patch_py_cb.setChecked(False)
        self._patch_py_cb.setStyleSheet(
            f"color: {theme.TEXT_PRIMARY}; font-size: 13px;"
        )
        root.addWidget(self._patch_py_cb)

        patch_note = QLabel(
            "⚠  Patching the .py file will modify your strategy source code. "
            "A second confirmation will be required."
        )
        patch_note.setStyleSheet(
            f"color: {theme.YELLOW}; font-size: 11px;"
        )
        patch_note.setWordWrap(True)
        root.addWidget(patch_note)

        # ── Button box ────────────────────────────────────────────────
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)

        ok_btn = self._button_box.button(QDialogButtonBox.Ok)
        if ok_btn:
            ok_btn.setObjectName("primary")
            ok_btn.setText("Export")

        root.addWidget(self._button_box)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_accept(self) -> None:
        """Handle OK click — show second confirmation if patch .py is checked."""
        if self._patch_py_cb.isChecked():
            confirm = QMessageBox(self)
            confirm.setWindowTitle("Confirm .py Patch")
            confirm.setIcon(QMessageBox.Warning)
            confirm.setText(
                "<b>You are about to modify the strategy .py source file.</b>"
            )
            confirm.setInformativeText(
                "This will overwrite the parameter default values in the source code. "
                "This action cannot be automatically undone.\n\n"
                "Are you sure you want to proceed?"
            )
            confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
            confirm.setDefaultButton(QMessageBox.Cancel)

            result = confirm.exec()
            if result != QMessageBox.Yes:
                _log.debug("ExportConfirmDialog: .py patch second confirmation cancelled")
                return

            _log.debug("ExportConfirmDialog: .py patch second confirmation accepted")

        self.accept()

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def patch_py_file(self) -> bool:
        """True if the user checked 'Patch .py file' and confirmed."""
        return self._patch_py_cb.isChecked()
