"""Settings page — configure venv, paths, and preferences."""
from __future__ import annotations
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFormLayout, QFrame, QFileDialog, QCheckBox,
    QScrollArea, QGroupBox, QComboBox
)
from PySide6.QtCore import Qt, Signal

from app.app_state.settings_state import SettingsState
from app.core.models.settings_models import AppSettings
from app.ui import theme
from app.core.utils.app_logger import get_logger

_log = get_logger("ui.settings")


class SettingsPage(QWidget):
    settings_saved = Signal()

    def __init__(self, settings_state: SettingsState, parent: QWidget | None = None):
        super().__init__(parent)
        self._state = settings_state
        self._build()
        self._load()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Settings")
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        hdr.addWidget(title)
        hdr.addStretch()
        self._save_btn = QPushButton("✓  Save Settings")
        self._save_btn.setObjectName("primary")
        self._save_btn.setFixedSize(140, 36)
        self._save_btn.clicked.connect(self._save)
        hdr.addWidget(self._save_btn)
        validate_btn = QPushButton("⚡  Validate")
        validate_btn.setFixedSize(100, 36)
        validate_btn.clicked.connect(self._validate)
        hdr.addWidget(validate_btn)
        root.addLayout(hdr)

        # Status bar
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 12px;")
        root.addWidget(self._status_lbl)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(16)
        scroll.setWidget(content)

        # ── Paths section ─────────────────────────────────────────────
        paths_group = self._group("Paths & Executables")
        pf = QFormLayout()
        pf.setSpacing(10)
        pf.setLabelAlignment(Qt.AlignRight)

        self._venv_edit = self._path_row(pf, "Venv Path", "Path to Python virtual environment", dir=True)
        self._python_edit = self._path_row(pf, "Python Executable", "Full path to python binary")
        self._freqtrade_edit = self._path_row(pf, "Freqtrade Executable", "Full path to freqtrade binary")
        self._userdata_edit = self._path_row(pf, "User Data Path", "Path to freqtrade user_data directory", dir=True)

        self._use_module_cb = QCheckBox("Use 'python -m freqtrade' (recommended)")
        self._use_module_cb.setChecked(True)
        pf.addRow("", self._use_module_cb)

        paths_group.layout().addLayout(pf)
        cl.addWidget(paths_group)

        # ── Auto-resolve button ───────────────────────────────────────
        resolve_btn = QPushButton("⚡  Auto-resolve from Venv Path")
        resolve_btn.clicked.connect(self._auto_resolve)
        cl.addWidget(resolve_btn)

        # ── Appearance ────────────────────────────────────────────────
        appear_group = self._group("Appearance")
        af = QFormLayout()
        af.setSpacing(10)
        af.setLabelAlignment(Qt.AlignRight)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["dark", "light"])
        af.addRow(self._lbl("Theme"), self._theme_combo)

        appear_group.layout().addLayout(af)
        cl.addWidget(appear_group)

        # ── Validation result ─────────────────────────────────────────
        self._validation_frame = QFrame()
        self._validation_frame.setStyleSheet(f"""
            QFrame {{
                background: {theme.BG_SURFACE};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 10px;
            }}
        """)
        vl = QVBoxLayout(self._validation_frame)
        vl.setContentsMargins(16, 12, 16, 12)
        self._validation_lbl = QLabel("Click Validate to check settings.")
        self._validation_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 12px;")
        self._validation_lbl.setWordWrap(True)
        vl.addWidget(self._validation_lbl)
        cl.addWidget(self._validation_frame)

        cl.addStretch()
        root.addWidget(scroll, 1)

    def _group(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet(f"""
            QGroupBox {{
                background: {theme.BG_SURFACE};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 10px;
                margin-top: 10px;
                padding: 12px;
                font-size: 13px;
                font-weight: 700;
                color: {theme.TEXT_PRIMARY};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                background: {theme.BG_SURFACE};
                color: {theme.TEXT_SECONDARY};
            }}
        """)
        QVBoxLayout(g)
        return g

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
        return lbl

    def _path_row(self, form: QFormLayout, label: str, placeholder: str, dir: bool = False) -> QLineEdit:
        row = QHBoxLayout()
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        row.addWidget(edit)
        browse_btn = QPushButton("…")
        browse_btn.setFixedSize(32, 32)
        if dir:
            browse_btn.clicked.connect(lambda: self._browse_dir(edit))
        else:
            browse_btn.clicked.connect(lambda: self._browse_file(edit))
        row.addWidget(browse_btn)
        form.addRow(self._lbl(label), row)
        return edit

    def _browse_dir(self, edit: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "Select Directory", edit.text() or str(Path.home()))
        if path:
            edit.setText(path)

    def _browse_file(self, edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(self, "Select File", edit.text() or str(Path.home()))
        if path:
            edit.setText(path)

    def _auto_resolve(self):
        venv = self._venv_edit.text().strip()
        if not venv:
            self._status("Enter venv path first.", theme.YELLOW)
            return
        from app.core.services.settings_service import SettingsService
        svc = SettingsService()
        python = svc._resolve_python_from_venv(venv)
        freqtrade = svc._resolve_freqtrade_from_venv(venv)
        self._python_edit.setText(python or "")
        self._freqtrade_edit.setText(freqtrade or "")
        self._status("Paths resolved from venv.", theme.GREEN)

    def _load(self):
        settings = self._state.current_settings
        if not settings:
            return
        self._venv_edit.setText(settings.venv_path or "")
        self._python_edit.setText(settings.python_executable or "")
        self._freqtrade_edit.setText(settings.freqtrade_executable or "")
        self._userdata_edit.setText(settings.user_data_path or "")
        self._use_module_cb.setChecked(settings.use_module_execution)
        self._theme_combo.setCurrentText(settings.theme_mode or "dark")

    def _save(self):
        settings = self._state.current_settings or AppSettings()
        settings.venv_path = self._venv_edit.text().strip() or None
        settings.python_executable = self._python_edit.text().strip() or None
        settings.freqtrade_executable = self._freqtrade_edit.text().strip() or None
        settings.user_data_path = self._userdata_edit.text().strip() or None
        settings.use_module_execution = self._use_module_cb.isChecked()
        settings.theme_mode = self._theme_combo.currentText()

        if self._state.save_settings(settings):
            self._status("✓ Settings saved.", theme.GREEN)
            self.settings_saved.emit()
        else:
            self._status("✗ Failed to save settings.", theme.RED)

    def _validate(self):
        self._save()
        result = self._state.validate_current_settings()
        lines = [
            f"{'✓' if result.python_ok else '✗'} Python: {'OK' if result.python_ok else 'NOT FOUND'}",
            f"{'✓' if result.freqtrade_ok else '✗'} Freqtrade: {'OK' if result.freqtrade_ok else 'NOT FOUND'}",
            f"{'✓' if result.user_data_ok else '✗'} User Data: {'OK' if result.user_data_ok else 'NOT FOUND'}",
        ]
        if result.details.get("python_version"):
            lines.append(f"  → {result.details['python_version']}")
        if result.details.get("freqtrade_version"):
            lines.append(f"  → {result.details['freqtrade_version'][:80]}")

        color = theme.GREEN if result.valid else theme.RED
        self._validation_lbl.setText("\n".join(lines))
        self._validation_lbl.setStyleSheet(f"color: {color}; font-size: 12px; font-family: {theme.FONT_MONO};")
        self._validation_frame.setStyleSheet(f"""
            QFrame {{
                background: {theme.BG_SURFACE};
                border: 1px solid {color}55;
                border-radius: 10px;
            }}
        """)

    def _status(self, msg: str, color: str = theme.TEXT_MUTED):
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 12px;")
