from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QGroupBox, QCheckBox, QMessageBox, QSpinBox, QComboBox,
    QColorDialog
)
from PySide6.QtGui import QColor, QFont

from app.core.models.settings_models import AppSettings, TerminalPreferences
from app.app_state.settings_state import SettingsState
from app.core.services.settings_service import SettingsService


class SettingsPage(QWidget):
    """Settings page for environment configuration."""

    def __init__(self, settings_state: SettingsState, parent=None):
        super().__init__(parent)
        self.settings_state = settings_state
        self.settings_service = SettingsService()
        self.current_settings: AppSettings = None
        self.init_ui()
        self._connect_signals()
        self._load_current_settings()

    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()

        # Venv selection group
        venv_group = QGroupBox("Virtual Environment")
        venv_layout = QVBoxLayout()

        # Venv path
        venv_path_layout = QHBoxLayout()
        venv_path_layout.addWidget(QLabel("Venv Path:"))
        self.venv_path_input = QLineEdit()
        self.venv_path_input.setPlaceholderText("/path/to/.venv")
        venv_path_layout.addWidget(self.venv_path_input)
        self.venv_browse_btn = QPushButton("Browse...")
        self.venv_browse_btn.clicked.connect(self._browse_venv)
        venv_path_layout.addWidget(self.venv_browse_btn)
        venv_layout.addLayout(venv_path_layout)

        # Python path preview
        python_layout = QHBoxLayout()
        python_layout.addWidget(QLabel("Python:"))
        self.python_path_display = QLineEdit()
        self.python_path_display.setReadOnly(True)
        self.python_path_display.setStyleSheet("color: gray;")
        python_layout.addWidget(self.python_path_display)
        venv_layout.addLayout(python_layout)

        # Freqtrade path preview
        freqtrade_layout = QHBoxLayout()
        freqtrade_layout.addWidget(QLabel("Freqtrade:"))
        self.freqtrade_path_display = QLineEdit()
        self.freqtrade_path_display.setReadOnly(True)
        self.freqtrade_path_display.setStyleSheet("color: gray;")
        freqtrade_layout.addWidget(self.freqtrade_path_display)
        venv_layout.addLayout(freqtrade_layout)

        venv_group.setLayout(venv_layout)
        layout.addWidget(venv_group)

        # Data and project paths
        paths_group = QGroupBox("Paths")
        paths_layout = QVBoxLayout()

        # User data path
        user_data_layout = QHBoxLayout()
        user_data_layout.addWidget(QLabel("User Data:"))
        self.user_data_input = QLineEdit()
        self.user_data_input.setPlaceholderText("/path/to/user_data")
        user_data_layout.addWidget(self.user_data_input)
        self.user_data_browse_btn = QPushButton("Browse...")
        self.user_data_browse_btn.clicked.connect(self._browse_user_data)
        user_data_layout.addWidget(self.user_data_browse_btn)
        paths_layout.addLayout(user_data_layout)

        # Project path
        project_layout = QHBoxLayout()
        project_layout.addWidget(QLabel("Project:"))
        self.project_input = QLineEdit()
        self.project_input.setPlaceholderText("/path/to/project")
        project_layout.addWidget(self.project_input)
        self.project_browse_btn = QPushButton("Browse...")
        self.project_browse_btn.clicked.connect(self._browse_project)
        project_layout.addWidget(self.project_browse_btn)
        paths_layout.addLayout(project_layout)

        paths_group.setLayout(paths_layout)
        layout.addWidget(paths_group)

        # Execution mode
        mode_group = QGroupBox("Execution Mode")
        mode_layout = QVBoxLayout()
        self.module_exec_checkbox = QCheckBox("Use 'python -m freqtrade' (preferred)")
        self.module_exec_checkbox.setChecked(True)
        mode_layout.addWidget(self.module_exec_checkbox)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Terminal appearance
        terminal_group = QGroupBox("Terminal Appearance")
        terminal_layout = QVBoxLayout()

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Font Family:"))
        self.terminal_font_combo = QComboBox()
        self.terminal_font_combo.addItems(["Courier", "Courier New", "Consolas", "Lucida Console", "Monospace", "DejaVu Sans Mono"])
        self.terminal_font_combo.setEditable(True)
        font_row.addWidget(self.terminal_font_combo)
        font_row.addWidget(QLabel("Size:"))
        self.terminal_font_size = QSpinBox()
        self.terminal_font_size.setRange(6, 32)
        self.terminal_font_size.setValue(10)
        font_row.addWidget(self.terminal_font_size)
        terminal_layout.addLayout(font_row)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Background:"))
        self.terminal_bg_btn = QPushButton()
        self.terminal_bg_btn.setFixedWidth(80)
        self.terminal_bg_btn.clicked.connect(self._pick_terminal_bg)
        color_row.addWidget(self.terminal_bg_btn)
        color_row.addWidget(QLabel("Text:"))
        self.terminal_text_btn = QPushButton()
        self.terminal_text_btn.setFixedWidth(80)
        self.terminal_text_btn.clicked.connect(self._pick_terminal_text)
        color_row.addWidget(self.terminal_text_btn)
        color_row.addStretch()
        terminal_layout.addLayout(color_row)

        terminal_group.setLayout(terminal_layout)
        layout.addWidget(terminal_group)

        # Validation result
        self.validation_result = QLabel("Not validated")
        self.validation_result.setStyleSheet("padding: 10px; background-color: #f0f0f0;")
        layout.addWidget(self.validation_result)

        # Action buttons
        button_layout = QHBoxLayout()

        self.validate_btn = QPushButton("Validate Settings")
        self.validate_btn.clicked.connect(self._validate)
        button_layout.addWidget(self.validate_btn)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self._save)
        button_layout.addWidget(self.save_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        layout.addStretch()
        self.setLayout(layout)

    def _connect_signals(self):
        """Connect UI signals."""
        self.venv_path_input.textChanged.connect(self._on_venv_changed)
        self.module_exec_checkbox.stateChanged.connect(self._on_settings_changed)
        self.terminal_font_combo.currentTextChanged.connect(self._on_settings_changed)
        self.terminal_font_size.valueChanged.connect(self._on_settings_changed)

    def _set_color_button(self, btn: QPushButton, color: str):
        """Set button background to reflect chosen color."""
        btn.setText(color)
        btn.setStyleSheet(f"background-color: {color}; color: {'#ffffff' if self._is_dark(color) else '#000000'};")

    @staticmethod
    def _is_dark(hex_color: str) -> bool:
        """Return True if hex color is dark (for contrast)."""
        c = hex_color.lstrip("#")
        if len(c) != 6:
            return True
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        return (r * 299 + g * 587 + b * 114) / 1000 < 128

    def _pick_terminal_bg(self):
        """Open color picker for terminal background."""
        color = QColorDialog.getColor(QColor(self.terminal_bg_btn.text() or "#1e1e1e"), self)
        if color.isValid():
            self._set_color_button(self.terminal_bg_btn, color.name())
            self._on_settings_changed()

    def _pick_terminal_text(self):
        """Open color picker for terminal text."""
        color = QColorDialog.getColor(QColor(self.terminal_text_btn.text() or "#d4d4d4"), self)
        if color.isValid():
            self._set_color_button(self.terminal_text_btn, color.name())
            self._on_settings_changed()

    def _load_current_settings(self):
        """Load current settings into UI."""
        if not self.current_settings:
            self.current_settings = self.settings_state.current_settings or AppSettings()

        self.venv_path_input.setText(self.current_settings.venv_path or "")
        self.user_data_input.setText(self.current_settings.user_data_path or "")
        self.project_input.setText(self.current_settings.project_path or "")
        self.module_exec_checkbox.setChecked(self.current_settings.use_module_execution)

        prefs = self.current_settings.terminal_preferences
        idx = self.terminal_font_combo.findText(prefs.font_family)
        if idx >= 0:
            self.terminal_font_combo.setCurrentIndex(idx)
        else:
            self.terminal_font_combo.setCurrentText(prefs.font_family)
        self.terminal_font_size.setValue(prefs.font_size)
        self._set_color_button(self.terminal_bg_btn, prefs.background_color)
        self._set_color_button(self.terminal_text_btn, prefs.text_color)

    def _on_venv_changed(self):
        """Update paths when venv changes."""
        venv_path = self.venv_path_input.text()
        if venv_path:
            python_exe = self.settings_service._resolve_python_from_venv(venv_path)
            freqtrade_exe = self.settings_service._resolve_freqtrade_from_venv(venv_path)

            self.python_path_display.setText(python_exe)
            self.freqtrade_path_display.setText(freqtrade_exe or "(not found)")
        else:
            self.python_path_display.clear()
            self.freqtrade_path_display.clear()

        self._on_settings_changed()

    def _on_settings_changed(self):
        """Handle settings change."""
        self.validation_result.setText("Not validated - settings changed")
        self.validation_result.setStyleSheet("padding: 10px; background-color: #ffffcc;")

    def _browse_venv(self):
        """Browse for venv directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Virtual Environment Directory",
            str(Path.home())
        )
        if directory:
            self.venv_path_input.setText(directory)

    def _browse_user_data(self):
        """Browse for user_data directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select User Data Directory",
            str(Path.home())
        )
        if directory:
            self.user_data_input.setText(directory)

    def _browse_project(self):
        """Browse for project directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Project Directory",
            str(Path.home())
        )
        if directory:
            self.project_input.setText(directory)

    def _validate(self):
        """Validate settings."""
        self._collect_settings()

        result = self.settings_state.validate_current_settings()

        # Update UI
        if result.valid:
            self.validation_result.setStyleSheet("padding: 10px; background-color: #00ff00; color: darkgreen;")
            self.validation_result.setText(f"✓ {result.message}")
        else:
            self.validation_result.setStyleSheet("padding: 10px; background-color: #ff6666; color: darkred;")
            details = "\n".join(f"  {k}: {v}" for k, v in result.details.items())
            msg = f"✗ {result.message}\n{details}"
            self.validation_result.setText(msg)

        # Show detailed message
        detail_text = self._format_validation_details(result)
        QMessageBox.information(self, "Validation Result", detail_text)

    def _validate_async(self):
        """Validate settings asynchronously."""
        self._collect_settings()
        result = self.settings_state.validate_current_settings()
        return result

    def _save(self):
        """Save settings."""
        self._collect_settings()
        success = self.settings_state.save_settings(self.current_settings)

        if success:
            QMessageBox.information(self, "Success", "Settings saved successfully")
        else:
            QMessageBox.warning(self, "Error", "Failed to save settings")

    def _collect_settings(self):
        """Collect settings from UI."""
        self.current_settings = AppSettings(
            venv_path=self.venv_path_input.text() or None,
            user_data_path=self.user_data_input.text() or None,
            project_path=self.project_input.text() or None,
            use_module_execution=self.module_exec_checkbox.isChecked(),
            terminal_preferences=TerminalPreferences(
                font_family=self.terminal_font_combo.currentText(),
                font_size=self.terminal_font_size.value(),
                background_color=self.terminal_bg_btn.text() or "#1e1e1e",
                text_color=self.terminal_text_btn.text() or "#d4d4d4",
            ),
        )

        # Resolve paths
        venv_path = self.current_settings.venv_path
        if venv_path:
            self.current_settings.python_executable = (
                self.settings_service._resolve_python_from_venv(venv_path)
            )
            self.current_settings.freqtrade_executable = (
                self.settings_service._resolve_freqtrade_from_venv(venv_path)
            )

    def _format_validation_details(self, result) -> str:
        """Format validation result for display."""
        lines = [result.message]
        lines.append("")
        lines.append("Details:")
        lines.append(f"  Python: {'✓' if result.python_ok else '✗'}")
        lines.append(f"  Freqtrade: {'✓' if result.freqtrade_ok else '✗'}")
        lines.append(f"  User Data: {'✓' if result.user_data_ok else '✗'}")

        if result.details:
            lines.append("")
            for key, value in result.details.items():
                if key not in ["python_ok", "freqtrade_ok", "user_data_ok"]:
                    lines.append(f"  {key}: {value}")

        return "\n".join(lines)
