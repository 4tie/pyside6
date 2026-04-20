"""SettingsPage for the v2 UI layer.

Category sidebar (QListWidget) + QStackedWidget for category panels:
Paths, Execution, Terminal, AI, Appearance, About.

Reuses all existing SettingsService / SettingsState logic.
Search QLineEdit at top filters visible fields via textChanged.
Real-time validation with inline error labels per field.

Requirements: 12.1, 12.2, 12.3, 1.2
"""
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor

from app.app_state.settings_state import SettingsState
from app.core.models.settings_models import AISettings, AppSettings, TerminalPreferences
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger

_log = get_logger("ui_v2.pages.settings_page")

# ---------------------------------------------------------------------------
# Category index constants
# ---------------------------------------------------------------------------
_CAT_PATHS = 0
_CAT_EXECUTION = 1
_CAT_TERMINAL = 2
_CAT_AI = 3
_CAT_APPEARANCE = 4
_CAT_ABOUT = 5

_CATEGORIES = ["Paths", "Execution", "Terminal", "AI", "Appearance", "About"]


# ---------------------------------------------------------------------------
# Helper: inline error label
# ---------------------------------------------------------------------------

def _make_error_label() -> QLabel:
    """Create a small red error label for inline validation feedback."""
    lbl = QLabel()
    lbl.setStyleSheet("color: #e05252; font-size: 11px;")
    lbl.setVisible(False)
    return lbl


def _set_error(label: QLabel, message: str) -> None:
    """Show an error message on an inline label."""
    if message:
        label.setText(message)
        label.setVisible(True)
    else:
        label.setText("")
        label.setVisible(False)


# ---------------------------------------------------------------------------
# Individual category panel builders
# ---------------------------------------------------------------------------

class _PathsPanel(QWidget):
    """Paths category panel: venv, user_data, python, freqtrade fields."""

    def __init__(self, settings_service: SettingsService, parent=None) -> None:
        super().__init__(parent)
        self._settings_service = settings_service
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Paths")
        title.setObjectName("page_title")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(8)

        # Venv path
        venv_row = QHBoxLayout()
        self.venv_path_input = QLineEdit()
        self.venv_path_input.setPlaceholderText("/path/to/.venv")
        self.venv_path_input.setAccessibleName("Virtual environment path")
        self.venv_path_input.setToolTip("Path to the Python virtual environment containing freqtrade")
        venv_row.addWidget(self.venv_path_input)
        browse_venv = QPushButton("Browse...")
        browse_venv.setAccessibleName("Browse for virtual environment")
        browse_venv.clicked.connect(self._browse_venv)
        venv_row.addWidget(browse_venv)
        self.venv_error = _make_error_label()
        form.addRow("Venv Path:", venv_row)
        form.addRow("", self.venv_error)

        # User data path
        user_data_row = QHBoxLayout()
        self.user_data_input = QLineEdit()
        self.user_data_input.setPlaceholderText("/path/to/user_data")
        self.user_data_input.setAccessibleName("User data directory")
        self.user_data_input.setToolTip("Path to the freqtrade user_data directory")
        user_data_row.addWidget(self.user_data_input)
        browse_ud = QPushButton("Browse...")
        browse_ud.setAccessibleName("Browse for user data directory")
        browse_ud.clicked.connect(self._browse_user_data)
        user_data_row.addWidget(browse_ud)
        self.user_data_error = _make_error_label()
        form.addRow("User Data Dir:", user_data_row)
        form.addRow("", self.user_data_error)

        # Python executable (read-only, derived from venv)
        self.python_display = QLineEdit()
        self.python_display.setReadOnly(True)
        self.python_display.setObjectName("hint_label")
        self.python_display.setAccessibleName("Python executable path (derived)")
        self.python_display.setToolTip("Derived from the venv path — not editable directly")
        self.python_error = _make_error_label()
        form.addRow("Python Executable:", self.python_display)
        form.addRow("", self.python_error)

        # Freqtrade executable (read-only, derived from venv)
        self.freqtrade_display = QLineEdit()
        self.freqtrade_display.setReadOnly(True)
        self.freqtrade_display.setObjectName("hint_label")
        self.freqtrade_display.setAccessibleName("Freqtrade executable path (derived)")
        self.freqtrade_display.setToolTip("Derived from the venv path — not editable directly")
        self.freqtrade_error = _make_error_label()
        form.addRow("Freqtrade Executable:", self.freqtrade_display)
        form.addRow("", self.freqtrade_error)

        layout.addLayout(form)
        layout.addStretch()

        # Wire real-time validation
        self.venv_path_input.textChanged.connect(self._on_venv_changed)
        self.user_data_input.textChanged.connect(self._validate_user_data)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _on_venv_changed(self, text: str) -> None:
        """Update derived paths and validate when venv path changes."""
        if text:
            python_exe = self._settings_service._resolve_python_from_venv(text)
            freqtrade_exe = self._settings_service._resolve_freqtrade_from_venv(text)
            self.python_display.setText(python_exe or "")
            self.freqtrade_display.setText(freqtrade_exe or "(not found)")

            venv_p = Path(text).expanduser()
            if not venv_p.exists():
                _set_error(self.venv_error, "Path does not exist")
            elif not venv_p.is_dir():
                _set_error(self.venv_error, "Path is not a directory")
            else:
                _set_error(self.venv_error, "")

            if python_exe and not Path(python_exe).exists():
                _set_error(self.python_error, "Python executable not found in venv")
            else:
                _set_error(self.python_error, "")

            if freqtrade_exe is None:
                _set_error(self.freqtrade_error, "freqtrade executable not found in venv")
            else:
                _set_error(self.freqtrade_error, "")
        else:
            self.python_display.clear()
            self.freqtrade_display.clear()
            _set_error(self.venv_error, "")
            _set_error(self.python_error, "")
            _set_error(self.freqtrade_error, "")

    def _validate_user_data(self, text: str) -> None:
        """Validate user data path in real time."""
        if text:
            p = Path(text).expanduser()
            if not p.exists():
                _set_error(self.user_data_error, "Path does not exist")
            elif not p.is_dir():
                _set_error(self.user_data_error, "Path is not a directory")
            else:
                _set_error(self.user_data_error, "")
        else:
            _set_error(self.user_data_error, "")

    # ------------------------------------------------------------------
    # Browse helpers
    # ------------------------------------------------------------------

    def _browse_venv(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select Virtual Environment Directory", str(Path.home())
        )
        if directory:
            self.venv_path_input.setText(directory)

    def _browse_user_data(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select User Data Directory", str(Path.home())
        )
        if directory:
            self.user_data_input.setText(directory)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, settings: AppSettings) -> None:
        """Populate fields from an AppSettings instance."""
        self.venv_path_input.setText((settings.venv_path or "").strip())
        self.user_data_input.setText((settings.user_data_path or "").strip())

    def collect(self, settings: AppSettings) -> None:
        """Write field values back into an AppSettings instance."""
        venv = self.venv_path_input.text().strip() or None
        settings.venv_path = venv
        settings.user_data_path = self.user_data_input.text().strip() or None
        if venv:
            settings.python_executable = (
                self._settings_service._resolve_python_from_venv(venv)
            )
            settings.freqtrade_executable = (
                self._settings_service._resolve_freqtrade_from_venv(venv)
            )

    def field_rows(self) -> List[tuple]:
        """Return (label_text, widget) pairs for search filtering."""
        return [
            ("Venv Path", self.venv_path_input),
            ("User Data Dir", self.user_data_input),
            ("Python Executable", self.python_display),
            ("Freqtrade Executable", self.freqtrade_display),
        ]


class _ExecutionPanel(QWidget):
    """Execution category panel: use_module_execution toggle."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Execution")
        title.setObjectName("page_title")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        group = QGroupBox("Execution Mode")
        group_layout = QVBoxLayout(group)

        self.module_exec_checkbox = QCheckBox("Use 'python -m freqtrade' (preferred)")
        self.module_exec_checkbox.setAccessibleName("Use module execution")
        self.module_exec_checkbox.setToolTip(
            "When checked, freqtrade is invoked as 'python -m freqtrade'. "
            "Uncheck to use the freqtrade executable directly."
        )
        self.module_exec_checkbox.setWhatsThis(
            "Module execution is the recommended way to run freqtrade inside a venv. "
            "Disable only if you have a standalone freqtrade executable."
        )
        group_layout.addWidget(self.module_exec_checkbox)

        self.module_exec_error = _make_error_label()
        group_layout.addWidget(self.module_exec_error)

        layout.addWidget(group)
        layout.addStretch()

    def load(self, settings: AppSettings) -> None:
        self.module_exec_checkbox.setChecked(settings.use_module_execution)

    def collect(self, settings: AppSettings) -> None:
        settings.use_module_execution = self.module_exec_checkbox.isChecked()

    def field_rows(self) -> List[tuple]:
        return [
            ("Use Module Execution", self.module_exec_checkbox),
        ]


class _TerminalPanel(QWidget):
    """Terminal category panel: font, colors."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Terminal")
        title.setObjectName("page_title")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        group = QGroupBox("Terminal Appearance")
        form = QFormLayout(group)
        form.setSpacing(8)

        # Font family
        self.font_combo = QComboBox()
        self.font_combo.addItems([
            "Courier", "Courier New", "Consolas", "Lucida Console",
            "Monospace", "DejaVu Sans Mono",
        ])
        self.font_combo.setEditable(True)
        self.font_combo.setAccessibleName("Terminal font family")
        self.font_combo.setToolTip("Font family used in the terminal output widget")
        self.font_error = _make_error_label()
        form.addRow("Font Family:", self.font_combo)
        form.addRow("", self.font_error)

        # Font size
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 32)
        self.font_size.setValue(10)
        self.font_size.setAccessibleName("Terminal font size")
        self.font_size.setToolTip("Font size in points for the terminal output widget")
        form.addRow("Font Size:", self.font_size)

        # Background color
        bg_row = QHBoxLayout()
        self.bg_btn = QPushButton()
        self.bg_btn.setFixedWidth(80)
        self.bg_btn.setAccessibleName("Terminal background color")
        self.bg_btn.setToolTip("Click to choose the terminal background color")
        self.bg_btn.clicked.connect(self._pick_bg)
        bg_row.addWidget(self.bg_btn)
        bg_row.addStretch()
        self.bg_error = _make_error_label()
        form.addRow("Background Color:", bg_row)
        form.addRow("", self.bg_error)

        # Text color
        text_row = QHBoxLayout()
        self.text_btn = QPushButton()
        self.text_btn.setFixedWidth(80)
        self.text_btn.setAccessibleName("Terminal text color")
        self.text_btn.setToolTip("Click to choose the terminal text color")
        self.text_btn.clicked.connect(self._pick_text)
        text_row.addWidget(self.text_btn)
        text_row.addStretch()
        self.text_error = _make_error_label()
        form.addRow("Text Color:", text_row)
        form.addRow("", self.text_error)

        layout.addWidget(group)
        layout.addStretch()

        # Set defaults
        self._set_color_btn(self.bg_btn, "#1e1e1e")
        self._set_color_btn(self.text_btn, "#d4d4d4")

    # ------------------------------------------------------------------
    # Color helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_dark(hex_color: str) -> bool:
        c = hex_color.lstrip("#")
        if len(c) != 6:
            return True
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        return (r * 299 + g * 587 + b * 114) / 1000 < 128

    def _set_color_btn(self, btn: QPushButton, color: str) -> None:
        btn.setText(color)
        fg = "#ffffff" if self._is_dark(color) else "#000000"
        btn.setStyleSheet(f"background-color: {color}; color: {fg};")

    def _pick_bg(self) -> None:
        color = QColorDialog.getColor(QColor(self.bg_btn.text() or "#1e1e1e"), self)
        if color.isValid():
            self._set_color_btn(self.bg_btn, color.name())

    def _pick_text(self) -> None:
        color = QColorDialog.getColor(QColor(self.text_btn.text() or "#d4d4d4"), self)
        if color.isValid():
            self._set_color_btn(self.text_btn, color.name())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, settings: AppSettings) -> None:
        prefs = settings.terminal_preferences
        idx = self.font_combo.findText(prefs.font_family)
        if idx >= 0:
            self.font_combo.setCurrentIndex(idx)
        else:
            self.font_combo.setCurrentText(prefs.font_family)
        self.font_size.setValue(prefs.font_size)
        self._set_color_btn(self.bg_btn, prefs.background_color)
        self._set_color_btn(self.text_btn, prefs.text_color)

    def collect(self, settings: AppSettings) -> None:
        settings.terminal_preferences = TerminalPreferences(
            font_family=self.font_combo.currentText(),
            font_size=self.font_size.value(),
            background_color=self.bg_btn.text() or "#1e1e1e",
            text_color=self.text_btn.text() or "#d4d4d4",
        )

    def field_rows(self) -> List[tuple]:
        return [
            ("Font Family", self.font_combo),
            ("Font Size", self.font_size),
            ("Background Color", self.bg_btn),
            ("Text Color", self.text_btn),
        ]


class _AIPanel(QWidget):
    """AI category panel: provider, models, keys, timeouts."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("AI")
        title.setObjectName("page_title")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        scroll_content = QWidget()
        form = QFormLayout(scroll_content)
        form.setSpacing(8)

        # Provider
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["ollama", "openrouter"])
        self.provider_combo.setAccessibleName("AI provider")
        self.provider_combo.setToolTip("Select the AI backend provider")
        form.addRow("Provider:", self.provider_combo)

        # Ollama base URL
        self.ollama_url_input = QLineEdit()
        self.ollama_url_input.setPlaceholderText("http://localhost:11434")
        self.ollama_url_input.setAccessibleName("Ollama base URL")
        self.ollama_url_input.setToolTip("Base URL for the local Ollama server")
        self.ollama_url_error = _make_error_label()
        form.addRow("Ollama Base URL:", self.ollama_url_input)
        form.addRow("", self.ollama_url_error)

        # OpenRouter API keys list
        keys_widget = QWidget()
        keys_layout = QVBoxLayout(keys_widget)
        keys_layout.setContentsMargins(0, 0, 0, 0)
        self.openrouter_keys_list = QListWidget()
        self.openrouter_keys_list.setFixedHeight(90)
        self.openrouter_keys_list.setAccessibleName("OpenRouter API keys")
        self.openrouter_keys_list.setToolTip("API keys for OpenRouter (supports rotation)")
        keys_layout.addWidget(self.openrouter_keys_list)
        keys_btn_row = QHBoxLayout()
        add_key_btn = QPushButton("Add Key")
        add_key_btn.setAccessibleName("Add OpenRouter API key")
        add_key_btn.clicked.connect(self._add_key)
        keys_btn_row.addWidget(add_key_btn)
        remove_key_btn = QPushButton("Remove Selected")
        remove_key_btn.setAccessibleName("Remove selected OpenRouter API key")
        remove_key_btn.clicked.connect(self._remove_key)
        keys_btn_row.addWidget(remove_key_btn)
        keys_btn_row.addStretch()
        keys_layout.addLayout(keys_btn_row)
        form.addRow("OpenRouter API Keys:", keys_widget)

        # Chat model
        self.chat_model_input = QLineEdit()
        self.chat_model_input.setPlaceholderText("e.g. llama3")
        self.chat_model_input.setAccessibleName("Chat model name")
        self.chat_model_input.setToolTip("Model used for plain conversation")
        form.addRow("Chat Model:", self.chat_model_input)

        # Task model
        self.task_model_input = QLineEdit()
        self.task_model_input.setPlaceholderText("e.g. llama3")
        self.task_model_input.setAccessibleName("Task model name")
        self.task_model_input.setToolTip("Model used for tool-using task runs")
        form.addRow("Task Model:", self.task_model_input)

        # Routing mode
        self.routing_mode_combo = QComboBox()
        self.routing_mode_combo.addItems(["single_model", "dual_model"])
        self.routing_mode_combo.setAccessibleName("AI routing mode")
        self.routing_mode_combo.setToolTip(
            "single_model: use one model for all tasks; "
            "dual_model: use separate chat and task models"
        )
        form.addRow("Routing Mode:", self.routing_mode_combo)

        # Timeout
        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setRange(1, 300)
        self.timeout_spinbox.setValue(60)
        self.timeout_spinbox.setAccessibleName("AI request timeout in seconds")
        self.timeout_spinbox.setToolTip("HTTP request timeout in seconds")
        form.addRow("Timeout (seconds):", self.timeout_spinbox)

        # Stream enabled
        self.stream_checkbox = QCheckBox()
        self.stream_checkbox.setAccessibleName("Enable streaming responses")
        self.stream_checkbox.setToolTip("Use streaming responses from the AI provider")
        form.addRow("Stream Enabled:", self.stream_checkbox)

        # Tools enabled
        self.tools_checkbox = QCheckBox()
        self.tools_checkbox.setAccessibleName("Enable tool calling")
        self.tools_checkbox.setToolTip("Allow the AI to call tools (function calling)")
        form.addRow("Tools Enabled:", self.tools_checkbox)

        # Max history
        self.max_history_spinbox = QSpinBox()
        self.max_history_spinbox.setRange(1, 500)
        self.max_history_spinbox.setValue(50)
        self.max_history_spinbox.setAccessibleName("Max history messages")
        self.max_history_spinbox.setToolTip("Maximum number of messages retained in conversation history")
        form.addRow("Max History Messages:", self.max_history_spinbox)

        # Max tool steps
        self.max_tool_steps_spinbox = QSpinBox()
        self.max_tool_steps_spinbox.setRange(1, 50)
        self.max_tool_steps_spinbox.setValue(8)
        self.max_tool_steps_spinbox.setAccessibleName("Max tool steps per run")
        self.max_tool_steps_spinbox.setToolTip("Maximum tool call iterations per task run")
        form.addRow("Max Tool Steps:", self.max_tool_steps_spinbox)

        # OpenRouter free only
        self.free_only_checkbox = QCheckBox()
        self.free_only_checkbox.setAccessibleName("OpenRouter free models only")
        self.free_only_checkbox.setToolTip("Filter OpenRouter model list to free models only")
        form.addRow("OpenRouter Free Only:", self.free_only_checkbox)

        # Cloud fallback
        self.cloud_fallback_checkbox = QCheckBox()
        self.cloud_fallback_checkbox.setAccessibleName("Cloud fallback enabled")
        self.cloud_fallback_checkbox.setToolTip("Reserved — no runtime effect in this version")
        form.addRow("Cloud Fallback Enabled:", self.cloud_fallback_checkbox)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Real-time validation
        self.ollama_url_input.textChanged.connect(self._validate_ollama_url)

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    @staticmethod
    def _mask_key(key: str) -> str:
        if len(key) <= 12:
            return key[:8] + "****"
        return key[:8] + "****" + key[-4:]

    def _add_key_item(self, key: str) -> None:
        item = QListWidgetItem(self._mask_key(key))
        item.setData(Qt.ItemDataRole.UserRole, key)
        self.openrouter_keys_list.addItem(item)

    def _add_key(self) -> None:
        key, ok = QInputDialog.getText(
            self, "Add OpenRouter API Key", "Enter API key (sk-or-...):",
            QLineEdit.EchoMode.Password,
        )
        if ok and key.strip():
            existing = [
                self.openrouter_keys_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.openrouter_keys_list.count())
            ]
            if key.strip() in existing:
                QMessageBox.information(self, "Duplicate Key", "That key is already in the list.")
                return
            self._add_key_item(key.strip())

    def _remove_key(self) -> None:
        row = self.openrouter_keys_list.currentRow()
        if row >= 0:
            self.openrouter_keys_list.takeItem(row)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_ollama_url(self, text: str) -> None:
        if text and not (text.startswith("http://") or text.startswith("https://")):
            _set_error(self.ollama_url_error, "URL must start with http:// or https://")
        else:
            _set_error(self.ollama_url_error, "")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, settings: AppSettings) -> None:
        ai = settings.ai
        self.provider_combo.setCurrentText(ai.provider)
        self.ollama_url_input.setText(ai.ollama_base_url)
        self.openrouter_keys_list.clear()
        keys = list(ai.openrouter_api_keys)
        if not keys and ai.openrouter_api_key:
            keys = [ai.openrouter_api_key]
        for key in keys:
            self._add_key_item(key)
        self.chat_model_input.setText(ai.chat_model)
        self.task_model_input.setText(ai.task_model)
        self.routing_mode_combo.setCurrentText(ai.routing_mode)
        self.timeout_spinbox.setValue(ai.timeout_seconds)
        self.stream_checkbox.setChecked(ai.stream_enabled)
        self.tools_checkbox.setChecked(ai.tools_enabled)
        self.max_history_spinbox.setValue(ai.max_history_messages)
        self.max_tool_steps_spinbox.setValue(ai.max_tool_steps)
        self.free_only_checkbox.setChecked(ai.openrouter_free_only)
        self.cloud_fallback_checkbox.setChecked(ai.cloud_fallback_enabled)

    def collect(self, settings: AppSettings) -> None:
        keys = [
            self.openrouter_keys_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.openrouter_keys_list.count())
        ]
        settings.ai = AISettings(
            provider=self.provider_combo.currentText(),
            ollama_base_url=self.ollama_url_input.text() or "http://localhost:11434",
            openrouter_api_key=keys[0] if keys else None,
            openrouter_api_keys=keys,
            chat_model=self.chat_model_input.text(),
            task_model=self.task_model_input.text(),
            routing_mode=self.routing_mode_combo.currentText(),
            timeout_seconds=self.timeout_spinbox.value(),
            stream_enabled=self.stream_checkbox.isChecked(),
            tools_enabled=self.tools_checkbox.isChecked(),
            max_history_messages=self.max_history_spinbox.value(),
            max_tool_steps=self.max_tool_steps_spinbox.value(),
            openrouter_free_only=self.free_only_checkbox.isChecked(),
            cloud_fallback_enabled=self.cloud_fallback_checkbox.isChecked(),
        )

    def field_rows(self) -> List[tuple]:
        return [
            ("Provider", self.provider_combo),
            ("Ollama Base URL", self.ollama_url_input),
            ("OpenRouter API Keys", self.openrouter_keys_list),
            ("Chat Model", self.chat_model_input),
            ("Task Model", self.task_model_input),
            ("Routing Mode", self.routing_mode_combo),
            ("Timeout (seconds)", self.timeout_spinbox),
            ("Stream Enabled", self.stream_checkbox),
            ("Tools Enabled", self.tools_checkbox),
            ("Max History Messages", self.max_history_spinbox),
            ("Max Tool Steps", self.max_tool_steps_spinbox),
            ("OpenRouter Free Only", self.free_only_checkbox),
            ("Cloud Fallback Enabled", self.cloud_fallback_checkbox),
        ]


class _AppearancePanel(QWidget):
    """Appearance category panel: theme mode."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Appearance")
        title.setObjectName("page_title")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        group = QGroupBox("Theme")
        form = QFormLayout(group)
        form.setSpacing(8)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        self.theme_combo.setAccessibleName("Theme mode")
        self.theme_combo.setToolTip("Switch between dark and light colour themes")
        self.theme_error = _make_error_label()
        form.addRow("Theme Mode:", self.theme_combo)
        form.addRow("", self.theme_error)

        layout.addWidget(group)
        layout.addStretch()

    def load(self, settings: AppSettings) -> None:
        theme = getattr(settings, "theme_mode", "dark")
        self.theme_combo.setCurrentText("Light" if theme == "light" else "Dark")

    def collect(self, settings: AppSettings) -> None:
        settings.theme_mode = (
            "light" if self.theme_combo.currentText() == "Light" else "dark"
        )

    def field_rows(self) -> List[tuple]:
        return [
            ("Theme Mode", self.theme_combo),
        ]


class _AboutPanel(QWidget):
    """About category panel: version info and links."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("About")
        title.setObjectName("page_title")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        app_name = QLabel("<b>Freqtrade GUI</b>")
        app_name.setStyleSheet("font-size: 16px;")
        layout.addWidget(app_name)

        desc = QLabel(
            "A graphical interface for the Freqtrade cryptocurrency trading bot framework."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        links_group = QGroupBox("Links")
        links_layout = QVBoxLayout(links_group)

        freqtrade_link = QLabel(
            '<a href="https://www.freqtrade.io/">Freqtrade Documentation</a>'
        )
        freqtrade_link.setOpenExternalLinks(True)
        freqtrade_link.setAccessibleName("Freqtrade documentation link")
        links_layout.addWidget(freqtrade_link)

        github_link = QLabel(
            '<a href="https://github.com/freqtrade/freqtrade">Freqtrade on GitHub</a>'
        )
        github_link.setOpenExternalLinks(True)
        github_link.setAccessibleName("Freqtrade GitHub link")
        links_layout.addWidget(github_link)

        layout.addWidget(links_group)

        settings_path_group = QGroupBox("Settings File")
        settings_path_layout = QVBoxLayout(settings_path_group)
        settings_path = str(Path.home() / ".freqtrade_gui" / "settings.json")
        path_label = QLabel(f"<code>{settings_path}</code>")
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        settings_path_layout.addWidget(path_label)
        layout.addWidget(settings_path_group)

        layout.addStretch()

    def load(self, settings: AppSettings) -> None:
        pass  # Static content only

    def collect(self, settings: AppSettings) -> None:
        pass  # Nothing to collect

    def field_rows(self) -> List[tuple]:
        return []  # No filterable fields


# ---------------------------------------------------------------------------
# Main SettingsPage
# ---------------------------------------------------------------------------

class SettingsPage(QWidget):
    """Categorised settings page for the v2 UI layer.

    Layout: search bar at top, then a horizontal split between a
    ``QListWidget`` category sidebar on the left and a ``QStackedWidget``
    of category panels on the right.

    Categories: Paths, Execution, Terminal, AI, Appearance, About.

    The search bar filters visible form rows across all panels by matching
    the field label text.  Real-time validation is handled inside each
    panel via inline error labels.

    Args:
        settings_state: Application settings state.
        parent: Optional parent widget.
    """

    def __init__(self, settings_state: SettingsState, parent=None) -> None:
        super().__init__(parent)

        self.settings_state = settings_state
        self._settings_service = SettingsService()
        self._current_settings: Optional[AppSettings] = None

        self._build_ui()
        self._connect_signals()
        self._load_settings()

        _log.info("SettingsPage initialised")

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the full settings page layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Search bar ────────────────────────────────────────────────
        search_bar = QWidget()
        search_bar.setObjectName("settings_search_bar")
        search_layout = QHBoxLayout(search_bar)
        search_layout.setContentsMargins(12, 8, 12, 8)
        search_layout.setSpacing(8)

        search_icon = QLabel("Search:")
        search_layout.addWidget(search_icon)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search settings...")
        self._search_input.setAccessibleName("Search settings fields")
        self._search_input.setToolTip("Filter settings fields by label text")
        self._search_input.setClearButtonEnabled(True)
        search_layout.addWidget(self._search_input)

        root.addWidget(search_bar)

        # ── Body: sidebar + stacked panels ───────────────────────────
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Category sidebar
        self._category_list = QListWidget()
        self._category_list.setFixedWidth(160)
        self._category_list.setAccessibleName("Settings categories")
        self._category_list.setToolTip("Select a settings category")
        for cat in _CATEGORIES:
            item = QListWidgetItem(cat)
            self._category_list.addItem(item)
        self._category_list.setCurrentRow(0)
        body_layout.addWidget(self._category_list)

        # Stacked panels
        self._stack = QStackedWidget()

        self._paths_panel = _PathsPanel(self._settings_service)
        self._execution_panel = _ExecutionPanel()
        self._terminal_panel = _TerminalPanel()
        self._ai_panel = _AIPanel()
        self._appearance_panel = _AppearancePanel()
        self._about_panel = _AboutPanel()

        self._panels = [
            self._paths_panel,
            self._execution_panel,
            self._terminal_panel,
            self._ai_panel,
            self._appearance_panel,
            self._about_panel,
        ]

        for panel in self._panels:
            # Wrap each panel in a scroll area
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setWidget(panel)
            self._stack.addWidget(scroll)

        body_layout.addWidget(self._stack, 1)

        root.addWidget(body, 1)

        # ── Save / Validate buttons ───────────────────────────────────
        btn_bar = QWidget()
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(12, 8, 12, 8)
        btn_layout.setSpacing(8)

        self._validate_btn = QPushButton("Validate Settings")
        self._validate_btn.setAccessibleName("Validate current settings")
        self._validate_btn.setToolTip("Run validation checks on the current settings")
        self._validate_btn.clicked.connect(self._validate)
        btn_layout.addWidget(self._validate_btn)

        self._save_btn = QPushButton("Save Settings")
        self._save_btn.setAccessibleName("Save settings")
        self._save_btn.setToolTip("Persist the current settings to disk")
        self._save_btn.clicked.connect(self._save)
        btn_layout.addWidget(self._save_btn)

        self._status_label = QLabel()
        self._status_label.setObjectName("hint_label")
        btn_layout.addWidget(self._status_label)

        btn_layout.addStretch()

        root.addWidget(btn_bar)

    # ------------------------------------------------------------------
    # Signal Wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Wire internal signals."""
        self._category_list.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._search_input.textChanged.connect(self._on_search_changed)
        self.settings_state.settings_changed.connect(self._on_settings_changed)

    def _on_settings_changed(self, settings: AppSettings) -> None:
        """Reload UI when settings change externally."""
        _log.debug("SettingsPage: external settings_changed received")
        self._current_settings = settings
        self._populate_panels(settings)

    # ------------------------------------------------------------------
    # Search Filtering
    # ------------------------------------------------------------------

    def _on_search_changed(self, text: str) -> None:
        """Filter visible fields across all panels by label text.

        When the search text is non-empty, switch to the first panel that
        has a matching field.  Rows whose label does not match are hidden.

        Args:
            text: Current search query.
        """
        query = text.strip().lower()

        if not query:
            # Restore all rows in all panels
            for panel in self._panels:
                for _label, widget in panel.field_rows():
                    widget.setVisible(True)
                    # Also show parent row containers
                    if widget.parent():
                        widget.parent().setVisible(True)
            return

        first_match_cat: Optional[int] = None

        for cat_idx, panel in enumerate(self._panels):
            panel_has_match = False
            for label_text, widget in panel.field_rows():
                matches = query in label_text.lower()
                widget.setVisible(matches)
                if widget.parent() and widget.parent() is not panel:
                    widget.parent().setVisible(matches)
                if matches:
                    panel_has_match = True
                    if first_match_cat is None:
                        first_match_cat = cat_idx

            # Show/hide the category in the sidebar
            self._category_list.item(cat_idx).setHidden(not panel_has_match)

        if first_match_cat is not None:
            self._category_list.setCurrentRow(first_match_cat)
            self._stack.setCurrentIndex(first_match_cat)

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        """Load current settings from state and populate all panels."""
        settings = self.settings_state.current_settings or AppSettings()
        self._current_settings = settings
        self._populate_panels(settings)

    def _populate_panels(self, settings: AppSettings) -> None:
        """Push settings values into all category panels.

        Args:
            settings: The AppSettings instance to display.
        """
        for panel in self._panels:
            panel.load(settings)
        _log.debug("SettingsPage panels populated")

    def _collect_settings(self) -> AppSettings:
        """Gather values from all panels into a new AppSettings instance.

        Returns:
            A fresh AppSettings populated from the current form values.
        """
        # Start from a copy of current settings to preserve fields not shown
        import copy
        settings = copy.deepcopy(self._current_settings or AppSettings())
        for panel in self._panels:
            panel.collect(settings)
        return settings

    def _validate(self) -> None:
        """Collect settings and run validation, showing a result dialog."""
        settings = self._collect_settings()
        self._current_settings = settings

        result = self._settings_service.validate_settings(settings)

        if result.valid:
            self._status_label.setStyleSheet("color: #4caf50;")
            self._status_label.setText("✓ Settings are valid")
        else:
            self._status_label.setStyleSheet("color: #e05252;")
            self._status_label.setText("✗ Validation failed")

        lines = [result.message, ""]
        lines.append("Python:    " + ("✓" if result.python_ok else "✗"))
        lines.append("Freqtrade: " + ("✓" if result.freqtrade_ok else "✗"))
        lines.append("User Data: " + ("✓" if result.user_data_ok else "✗"))
        if result.details.get("python_version"):
            lines.append("  " + str(result.details["python_version"]).strip())
        if result.details.get("freqtrade_version"):
            lines.append("  " + str(result.details["freqtrade_version"]).splitlines()[0].strip())

        QMessageBox.information(self, "Validation Result", "\n".join(lines))
        _log.info(
            "Settings validated: valid=%s python=%s freqtrade=%s user_data=%s",
            result.valid, result.python_ok, result.freqtrade_ok, result.user_data_ok,
        )

    def _save(self) -> None:
        """Collect settings from all panels and persist via SettingsState."""
        settings = self._collect_settings()
        self._current_settings = settings

        success = self.settings_state.save_settings(settings)
        if success:
            self._status_label.setStyleSheet("color: #4caf50;")
            self._status_label.setText("✓ Settings saved")
            _log.info("Settings saved successfully")
        else:
            self._status_label.setStyleSheet("color: #e05252;")
            self._status_label.setText("✗ Failed to save settings")
            QMessageBox.warning(self, "Save Failed", "Failed to save settings to disk.")
            _log.error("Failed to save settings")
