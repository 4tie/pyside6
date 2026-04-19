from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QGroupBox, QCheckBox, QMessageBox, QSpinBox, QComboBox,
    QColorDialog, QFormLayout, QListWidget, QListWidgetItem, QInputDialog,
    QScrollArea,
)
from PySide6.QtGui import QColor, QFont

from app.core.models.settings_models import AppSettings, TerminalPreferences, AISettings
from app.app_state.settings_state import SettingsState
from app.core.services.settings_service import SettingsService
from app.core.ai.providers.provider_factory import ProviderFactory


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
        self.python_path_display.setObjectName("hint_label")
        python_layout.addWidget(self.python_path_display)
        venv_layout.addLayout(python_layout)

        # Freqtrade path preview
        freqtrade_layout = QHBoxLayout()
        freqtrade_layout.addWidget(QLabel("Freqtrade:"))
        self.freqtrade_path_display = QLineEdit()
        self.freqtrade_path_display.setReadOnly(True)
        self.freqtrade_path_display.setObjectName("hint_label")
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

        # AI settings
        ai_group = QGroupBox("AI")
        ai_form = QFormLayout()

        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItems(["ollama", "openrouter"])
        ai_form.addRow("Provider:", self.ai_provider_combo)

        self.ai_ollama_base_url_input = QLineEdit()
        self.ai_ollama_base_url_input.setPlaceholderText("http://localhost:11434")
        ai_form.addRow("Ollama Base URL:", self.ai_ollama_base_url_input)

        # Multi-key widget for OpenRouter key rotation
        keys_widget = QWidget()
        keys_layout = QVBoxLayout(keys_widget)
        keys_layout.setContentsMargins(0, 0, 0, 0)

        self.ai_openrouter_keys_list = QListWidget()
        self.ai_openrouter_keys_list.setFixedHeight(90)
        keys_layout.addWidget(self.ai_openrouter_keys_list)

        keys_btn_layout = QHBoxLayout()
        self.ai_openrouter_add_key_btn = QPushButton("Add Key")
        self.ai_openrouter_add_key_btn.clicked.connect(self._add_openrouter_key)
        keys_btn_layout.addWidget(self.ai_openrouter_add_key_btn)
        self.ai_openrouter_remove_key_btn = QPushButton("Remove Selected")
        self.ai_openrouter_remove_key_btn.clicked.connect(self._remove_openrouter_key)
        keys_btn_layout.addWidget(self.ai_openrouter_remove_key_btn)
        keys_btn_layout.addStretch()
        keys_layout.addLayout(keys_btn_layout)

        ai_form.addRow("OpenRouter API Keys:", keys_widget)

        self.ai_chat_model_input = QLineEdit()
        self.ai_chat_model_input.setPlaceholderText("e.g. llama3")
        ai_form.addRow("Chat Model:", self.ai_chat_model_input)

        self.ai_task_model_input = QLineEdit()
        self.ai_task_model_input.setPlaceholderText("e.g. llama3")
        ai_form.addRow("Task Model:", self.ai_task_model_input)

        self.ai_routing_mode_combo = QComboBox()
        self.ai_routing_mode_combo.addItems(["single_model", "dual_model"])
        ai_form.addRow("Routing Mode:", self.ai_routing_mode_combo)

        self.ai_timeout_spinbox = QSpinBox()
        self.ai_timeout_spinbox.setRange(1, 300)
        self.ai_timeout_spinbox.setValue(60)
        ai_form.addRow("Timeout (seconds):", self.ai_timeout_spinbox)

        self.ai_stream_enabled_checkbox = QCheckBox()
        ai_form.addRow("Stream Enabled:", self.ai_stream_enabled_checkbox)

        self.ai_tools_enabled_checkbox = QCheckBox()
        ai_form.addRow("Tools Enabled:", self.ai_tools_enabled_checkbox)

        self.ai_max_history_spinbox = QSpinBox()
        self.ai_max_history_spinbox.setRange(1, 500)
        self.ai_max_history_spinbox.setValue(50)
        ai_form.addRow("Max History Messages:", self.ai_max_history_spinbox)

        self.ai_max_tool_steps_spinbox = QSpinBox()
        self.ai_max_tool_steps_spinbox.setRange(1, 50)
        self.ai_max_tool_steps_spinbox.setValue(8)
        ai_form.addRow("Max Tool Steps:", self.ai_max_tool_steps_spinbox)

        self.ai_openrouter_free_only_checkbox = QCheckBox()
        ai_form.addRow("OpenRouter Free Only:", self.ai_openrouter_free_only_checkbox)

        self.ai_cloud_fallback_checkbox = QCheckBox()
        ai_form.addRow("Cloud Fallback Enabled:", self.ai_cloud_fallback_checkbox)

        ai_group.setLayout(ai_form)
        layout.addWidget(ai_group)

        # Appearance
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout()

        self.theme_mode_combo = QComboBox()
        self.theme_mode_combo.addItems(["Dark", "Light"])
        appearance_layout.addRow("Theme Mode:", self.theme_mode_combo)

        appearance_group.setLayout(appearance_layout)
        layout.addWidget(appearance_group)

        # Validation result
        self.validation_result = QLabel("Not validated")
        self.validation_result.setObjectName("hint_label")
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

        content_widget = QWidget()
        content_widget.setLayout(layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content_widget)

        page_layout = QVBoxLayout()
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        self.setLayout(page_layout)

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

    # ------------------------------------------------------------------
    # OpenRouter key management
    # ------------------------------------------------------------------

    @staticmethod
    def _mask_key(key: str) -> str:
        """Return a masked display string for an API key."""
        if len(key) <= 12:
            return key[:8] + "****"
        return key[:8] + "****" + key[-4:]

    def _append_key_item(self, key: str) -> None:
        """Add a key entry to the list widget, storing the real key as UserRole data."""
        item = QListWidgetItem(self._mask_key(key))
        item.setData(Qt.ItemDataRole.UserRole, key)
        self.ai_openrouter_keys_list.addItem(item)

    def _add_openrouter_key(self) -> None:
        """Prompt the user for a new API key and add it to the list."""
        key, ok = QInputDialog.getText(
            self,
            "Add OpenRouter API Key",
            "Enter API key (sk-or-...):",
            QLineEdit.EchoMode.Password,
        )
        if ok and key.strip():
            # Avoid duplicates
            existing = [
                self.ai_openrouter_keys_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.ai_openrouter_keys_list.count())
            ]
            if key.strip() in existing:
                QMessageBox.information(self, "Duplicate Key", "That key is already in the list.")
                return
            self._append_key_item(key.strip())
            self._on_settings_changed()

    def _remove_openrouter_key(self) -> None:
        """Remove the currently selected key from the list."""
        row = self.ai_openrouter_keys_list.currentRow()
        if row >= 0:
            self.ai_openrouter_keys_list.takeItem(row)
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

        ai = self.current_settings.ai
        self.ai_provider_combo.setCurrentText(ai.provider)
        self.ai_ollama_base_url_input.setText(ai.ollama_base_url)
        # Populate multi-key list
        self.ai_openrouter_keys_list.clear()
        keys = list(ai.openrouter_api_keys)
        if not keys and ai.openrouter_api_key:
            keys = [ai.openrouter_api_key]
        for key in keys:
            self._append_key_item(key)
        self.ai_chat_model_input.setText(ai.chat_model)
        self.ai_task_model_input.setText(ai.task_model)
        self.ai_routing_mode_combo.setCurrentText(ai.routing_mode)
        self.ai_timeout_spinbox.setValue(ai.timeout_seconds)
        self.ai_stream_enabled_checkbox.setChecked(ai.stream_enabled)
        self.ai_tools_enabled_checkbox.setChecked(ai.tools_enabled)
        self.ai_max_history_spinbox.setValue(ai.max_history_messages)
        self.ai_max_tool_steps_spinbox.setValue(ai.max_tool_steps)
        self.ai_openrouter_free_only_checkbox.setChecked(ai.openrouter_free_only)
        self.ai_cloud_fallback_checkbox.setChecked(ai.cloud_fallback_enabled)

        # Load theme mode
        theme_mode = self.current_settings.theme_mode if hasattr(self.current_settings, 'theme_mode') else "dark"
        self.theme_mode_combo.setCurrentText("Light" if theme_mode == "light" else "Dark")

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

        # Test each OpenRouter key individually
        key_results = self._check_all_openrouter_keys()

        # Single Ollama/OpenRouter health (for the status label)
        ai_health = self._check_ai_provider()

        ai_ok = ai_health is None or ai_health.ok
        overall_ok = result.valid and ai_ok
        if overall_ok:
            self.validation_result.setObjectName("status_ok")
            self.validation_result.style().unpolish(self.validation_result)
            self.validation_result.style().polish(self.validation_result)
            self.validation_result.setText(f"✓ {result.message}")
        else:
            self.validation_result.setObjectName("status_error")
            self.validation_result.style().unpolish(self.validation_result)
            self.validation_result.style().polish(self.validation_result)
            self.validation_result.setText(f"✗ {result.message}")

        detail_text = self._format_validation_details(result, ai_health, key_results)
        QMessageBox.information(self, "Validation Result", detail_text)

    def _check_ai_provider(self):
        """Run a health check on the configured AI provider."""
        try:
            provider = ProviderFactory.create(self.current_settings.ai)
            return provider.health_check()
        except Exception as exc:
            from app.core.ai.providers.provider_base import ProviderHealth
            return ProviderHealth(ok=False, message=str(exc))

    def _check_all_openrouter_keys(self) -> list:
        """Test every OpenRouter key individually. Returns list of (masked_key, ok, message)."""
        from app.core.ai.providers.openrouter_provider import OpenRouterProvider
        keys = [
            self.ai_openrouter_keys_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.ai_openrouter_keys_list.count())
        ]
        if not keys:
            return []

        results = []
        timeout = self.ai_timeout_spinbox.value()
        for key in keys:
            masked = self._mask_key(key)
            try:
                provider = OpenRouterProvider(api_key=key, timeout=timeout)
                health = provider.health_check()
                results.append((masked, health.ok, health.message, health.latency_ms))
            except Exception as exc:
                results.append((masked, False, str(exc), None))
        return results

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
        keys = [
            self.ai_openrouter_keys_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.ai_openrouter_keys_list.count())
        ]
        ai_settings = AISettings(
            provider=self.ai_provider_combo.currentText(),
            ollama_base_url=self.ai_ollama_base_url_input.text() or "http://localhost:11434",
            openrouter_api_key=keys[0] if keys else None,
            openrouter_api_keys=keys,
            chat_model=self.ai_chat_model_input.text(),
            task_model=self.ai_task_model_input.text(),
            routing_mode=self.ai_routing_mode_combo.currentText(),
            timeout_seconds=self.ai_timeout_spinbox.value(),
            stream_enabled=self.ai_stream_enabled_checkbox.isChecked(),
            tools_enabled=self.ai_tools_enabled_checkbox.isChecked(),
            max_history_messages=self.ai_max_history_spinbox.value(),
            max_tool_steps=self.ai_max_tool_steps_spinbox.value(),
            openrouter_free_only=self.ai_openrouter_free_only_checkbox.isChecked(),
            cloud_fallback_enabled=self.ai_cloud_fallback_checkbox.isChecked(),
        )

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
            ai=ai_settings,
            theme_mode="light" if self.theme_mode_combo.currentText() == "Light" else "dark",
        )
        venv_path = self.current_settings.venv_path
        if venv_path:
            self.current_settings.python_executable = (
                self.settings_service._resolve_python_from_venv(venv_path)
            )
            self.current_settings.freqtrade_executable = (
                self.settings_service._resolve_freqtrade_from_venv(venv_path)
            )

    def _format_validation_details(self, result, ai_health=None, key_results=None) -> str:
        """Format validation result for display."""
        lines = [result.message, ""]
        lines.append("── Environment ──────────────────────")
        lines.append(f"  Python:     {'✓' if result.python_ok else '✗'}")
        lines.append(f"  Freqtrade:  {'✓' if result.freqtrade_ok else '✗'}")
        lines.append(f"  User Data:  {'✓' if result.user_data_ok else '✗'}")

        # Clean up the raw details (strip the noisy freqtrade --version output)
        if result.details:
            for k, v in result.details.items():
                if k in ("python_ok", "freqtrade_ok", "user_data_ok"):
                    continue
                if k == "freqtrade_version":
                    # Keep only the first line (e.g. "freqtrade 2026.3")
                    v = str(v).splitlines()[0].strip()
                if k == "python_version":
                    v = str(v).strip()
                lines.append(f"  {k}: {v}")

        # AI provider (Ollama or single-key OpenRouter)
        if ai_health is not None:
            provider_name = (
                self.current_settings.ai.provider.capitalize()
                if self.current_settings else "AI"
            )
            status = "✓" if ai_health.ok else "✗"
            latency = f" ({ai_health.latency_ms:.0f} ms)" if ai_health.latency_ms is not None else ""
            lines.append("")
            lines.append("── AI Provider ──────────────────────")
            lines.append(f"  {provider_name}: {status} {ai_health.message}{latency}")

        # Per-key OpenRouter results
        if key_results:
            lines.append("")
            lines.append("── OpenRouter API Keys ──────────────")
            for i, (masked, ok, message, latency_ms) in enumerate(key_results, 1):
                status = "✓" if ok else "✗"
                latency = f" ({latency_ms:.0f} ms)" if latency_ms is not None else ""
                lines.append(f"  Key {i} ({masked}): {status} {message}{latency}")

        return "\n".join(lines)
