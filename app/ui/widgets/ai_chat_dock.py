"""AIChatDock — dockable AI Chat panel wired to ConversationRuntime."""

from typing import Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.app_state.settings_state import SettingsState
from app.core.ai.providers.provider_base import AIResponse, ProviderHealth, StreamToken
from app.core.ai.providers.provider_factory import ProviderFactory
from app.core.ai.runtime.agent_policy import default_policy
from app.core.ai.runtime.conversation_runtime import ConversationRuntime
from app.core.models.settings_models import AISettings
from app.core.utils.app_logger import get_logger
from app.ui.widgets.ai_message_widget import AssistantMessageWidget, UserMessageWidget

_log = get_logger("ui.ai_chat_dock")

_NARROW_THRESHOLD = 280  # px — layout switch point


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------


class _HealthWorker(QObject):
    """Runs a provider health check on a background thread."""

    health_ready = Signal(object)  # ProviderHealth

    def __init__(self, ai_settings: AISettings) -> None:
        super().__init__()
        self._ai_settings = ai_settings

    def run(self) -> None:
        """Execute health check and emit result."""
        try:
            provider = ProviderFactory.create(self._ai_settings)
            health = provider.health_check()
        except Exception as exc:  # noqa: BLE001
            health = ProviderHealth(ok=False, message=str(exc))
        self.health_ready.emit(health)


class _ModelListWorker(QObject):
    """Fetches the model list from the provider on a background thread."""

    models_ready = Signal(list)  # list[str]

    def __init__(self, ai_settings: AISettings) -> None:
        super().__init__()
        self._ai_settings = ai_settings

    def run(self) -> None:
        """Fetch models and emit result."""
        try:
            provider = ProviderFactory.create(self._ai_settings)
            models = provider.list_models()
        except Exception as exc:  # noqa: BLE001
            _log.warning("Failed to list models: %s", exc)
            models = []
        self.models_ready.emit(models)


# ---------------------------------------------------------------------------
# AIChatDock
# ---------------------------------------------------------------------------


class AIChatDock(QDockWidget):
    """Dockable AI Chat panel backed by ConversationRuntime."""

    def __init__(self, settings_state: SettingsState, parent=None):
        super().__init__("AI Chat", parent)
        self.setObjectName("AIChatDock")
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)

        self._settings_state = settings_state
        self._runtime: Optional[ConversationRuntime] = None
        self._current_assistant_widget: Optional[AssistantMessageWidget] = None
        self._user_scrolled_up = False
        self._first_show = True

        # Background thread handles
        self._health_thread: Optional[QThread] = None
        self._health_worker: Optional[_HealthWorker] = None
        self._model_thread: Optional[QThread] = None
        self._model_worker: Optional[_ModelListWorker] = None

        self._build_ui()
        self._init_runtime()

        # React to settings changes
        self._settings_state.ai_settings_changed.connect(self._on_ai_settings_changed)

        _log.debug("AIChatDock initialised")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the full widget hierarchy."""
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(4)

        # --- Header ---
        self._header_widget = QWidget()
        self._header_layout = QHBoxLayout(self._header_widget)
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(4)

        self._provider_combo = QComboBox()
        self._provider_combo.addItems(["ollama", "openrouter"])
        self._provider_combo.setToolTip("AI provider")
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)

        # Chat model combo (always visible)
        self._chat_model_label = QLabel("Chat:")
        self._chat_model_label.setVisible(False)  # hidden in single-model mode
        self._chat_model_combo = QComboBox()
        self._chat_model_combo.setMinimumWidth(80)
        self._chat_model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._chat_model_combo.setToolTip("Chat model")

        # Task model combo (dual-model mode only)
        self._task_model_label = QLabel("Task:")
        self._task_model_combo = QComboBox()
        self._task_model_combo.setMinimumWidth(80)
        self._task_model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._task_model_combo.setToolTip("Task model")
        self._task_model_label.setVisible(False)
        self._task_model_combo.setVisible(False)

        # Status indicator
        self._status_label = QLabel("●")
        self._status_label.setToolTip("Provider connection status")
        self._set_status_color("yellow")

        # Tools toggle
        self._tools_btn = QToolButton()
        self._tools_btn.setText("Tools")
        self._tools_btn.setCheckable(True)
        self._tools_btn.setToolTip("Toggle tool calling")
        self._tools_btn.toggled.connect(self._on_tools_toggled)

        self._header_layout.addWidget(self._provider_combo)
        self._header_layout.addWidget(self._chat_model_label)
        self._header_layout.addWidget(self._chat_model_combo)
        self._header_layout.addWidget(self._task_model_label)
        self._header_layout.addWidget(self._task_model_combo)
        self._header_layout.addWidget(self._status_label)
        self._header_layout.addWidget(self._tools_btn)

        root_layout.addWidget(self._header_widget)

        # --- Message area ---
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._messages_widget = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_widget)
        self._messages_layout.setContentsMargins(0, 0, 0, 0)
        self._messages_layout.setSpacing(2)
        self._messages_layout.addStretch()  # pushes messages to top

        self._scroll_area.setWidget(self._messages_widget)
        self._scroll_area.verticalScrollBar().valueChanged.connect(
            self._on_scroll_value_changed
        )

        root_layout.addWidget(self._scroll_area, stretch=1)

        # --- Input area / no-model placeholder ---
        self._input_stack = QWidget()
        input_stack_layout = QVBoxLayout(self._input_stack)
        input_stack_layout.setContentsMargins(0, 0, 0, 0)
        input_stack_layout.setSpacing(2)

        self._no_model_label = QLabel("Select a model in Settings → AI to get started.")
        self._no_model_label.setAlignment(Qt.AlignCenter)
        self._no_model_label.setWordWrap(True)
        self._no_model_label.setVisible(False)

        self._input_widget = QWidget()
        input_layout = QVBoxLayout(self._input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(2)

        self._input_edit = QPlainTextEdit()
        self._input_edit.setPlaceholderText("Ask anything…")
        self._input_edit.setMaximumHeight(80)
        self._input_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        btn_row = QHBoxLayout()
        self._send_btn = QPushButton("Send")
        self._send_btn.clicked.connect(self._send_message)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_streaming)
        btn_row.addStretch()
        btn_row.addWidget(self._send_btn)
        btn_row.addWidget(self._stop_btn)

        input_layout.addWidget(self._input_edit)
        input_layout.addLayout(btn_row)

        input_stack_layout.addWidget(self._no_model_label)
        input_stack_layout.addWidget(self._input_widget)

        root_layout.addWidget(self._input_stack)

        self.setWidget(root)
        self._sync_input_visibility()

    # ------------------------------------------------------------------
    # Runtime initialisation
    # ------------------------------------------------------------------

    def _init_runtime(self) -> None:
        """Create ConversationRuntime from current AI settings."""
        settings = self._settings_state.current_settings
        ai_settings = settings.ai if settings else AISettings()

        self._runtime = ConversationRuntime(
            ai_settings=ai_settings,
            agent_policy=default_policy(),
        )
        self._connect_runtime_signals()

        # Sync header combos to current settings
        self._sync_header_to_settings(ai_settings)

    def _connect_runtime_signals(self) -> None:
        """Connect runtime signals to UI slots."""
        if self._runtime is None:
            return
        self._runtime.token_received.connect(self._on_token_received)
        self._runtime.response_complete.connect(self._on_response_complete)
        self._runtime.error_occurred.connect(self._on_error_occurred)
        self._runtime.task_complete.connect(self._on_task_complete)

    def _disconnect_runtime_signals(self) -> None:
        """Disconnect runtime signals before replacing the runtime."""
        if self._runtime is None:
            return
        try:
            self._runtime.token_received.disconnect(self._on_token_received)
            self._runtime.response_complete.disconnect(self._on_response_complete)
            self._runtime.error_occurred.disconnect(self._on_error_occurred)
            self._runtime.task_complete.disconnect(self._on_task_complete)
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    # Header sync helpers
    # ------------------------------------------------------------------

    def _sync_header_to_settings(self, ai_settings: AISettings) -> None:
        """Update header combos to reflect ai_settings without triggering saves."""
        # Provider
        idx = self._provider_combo.findText(ai_settings.provider)
        if idx >= 0:
            self._provider_combo.blockSignals(True)
            self._provider_combo.setCurrentIndex(idx)
            self._provider_combo.blockSignals(False)

        # Tools toggle
        self._tools_btn.blockSignals(True)
        self._tools_btn.setChecked(ai_settings.tools_enabled)
        self._tools_btn.blockSignals(False)

        # Dual-model visibility
        dual = ai_settings.routing_mode == "dual_model"
        self._chat_model_label.setVisible(dual)
        self._task_model_label.setVisible(dual)
        self._task_model_combo.setVisible(dual)

        self._sync_input_visibility()

    def _sync_input_visibility(self) -> None:
        """Show input area or no-model placeholder based on chat_model."""
        settings = self._settings_state.current_settings
        chat_model = settings.ai.chat_model if settings else ""
        has_model = bool(chat_model)
        self._input_widget.setVisible(has_model)
        self._no_model_label.setVisible(not has_model)

    # ------------------------------------------------------------------
    # Status indicator
    # ------------------------------------------------------------------

    def _set_status_color(self, color: str) -> None:
        """Update the status dot color.

        Args:
            color: 'green', 'red', or 'yellow'.
        """
        colors = {"green": "#22c55e", "red": "#ef4444", "yellow": "#eab308"}
        hex_color = colors.get(color, "#eab308")
        self._status_label.setStyleSheet(f"color: {hex_color}; font-size: 14px;")

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def _run_health_check(self) -> None:
        """Start a background health check, updating the status indicator."""
        settings = self._settings_state.current_settings
        ai_settings = settings.ai if settings else AISettings()

        self._set_status_color("yellow")

        # Clean up any previous health thread
        if self._health_thread is not None and self._health_thread.isRunning():
            self._health_thread.quit()
            self._health_thread.wait(1000)

        thread = QThread()
        worker = _HealthWorker(ai_settings)
        worker.moveToThread(thread)

        worker.health_ready.connect(self._on_health_ready)
        thread.started.connect(worker.run)
        worker.health_ready.connect(lambda _: thread.quit())
        thread.finished.connect(thread.deleteLater)

        self._health_thread = thread
        self._health_worker = worker
        thread.start()

    def _on_health_ready(self, health: ProviderHealth) -> None:
        """Update status indicator from health check result.

        Args:
            health: The ProviderHealth result from the background check.
        """
        color = "green" if health.ok else "red"
        self._set_status_color(color)
        tooltip = health.message
        if health.latency_ms is not None:
            tooltip += f" ({health.latency_ms:.0f} ms)"
        self._status_label.setToolTip(tooltip)
        _log.debug("Health check: ok=%s message=%s", health.ok, health.message)

    # ------------------------------------------------------------------
    # Model list population
    # ------------------------------------------------------------------

    def _populate_models(self) -> None:
        """Fetch model list asynchronously and populate combos."""
        settings = self._settings_state.current_settings
        ai_settings = settings.ai if settings else AISettings()

        # Clean up any previous model thread
        if self._model_thread is not None and self._model_thread.isRunning():
            self._model_thread.quit()
            self._model_thread.wait(1000)

        thread = QThread()
        worker = _ModelListWorker(ai_settings)
        worker.moveToThread(thread)

        worker.models_ready.connect(self._on_models_ready)
        thread.started.connect(worker.run)
        worker.models_ready.connect(lambda _: thread.quit())
        thread.finished.connect(thread.deleteLater)

        self._model_thread = thread
        self._model_worker = worker
        thread.start()

    def _on_models_ready(self, models: list) -> None:
        """Populate model combos with the fetched list.

        Args:
            models: List of model name strings from the provider.
        """
        settings = self._settings_state.current_settings
        ai_settings = settings.ai if settings else AISettings()

        for combo, current in [
            (self._chat_model_combo, ai_settings.chat_model),
            (self._task_model_combo, ai_settings.task_model),
        ]:
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(models)
            idx = combo.findText(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        self._sync_input_visibility()
        _log.debug("Model list populated: %d models", len(models))

    # ------------------------------------------------------------------
    # Qt event overrides
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        """Run health check and populate models on first show."""
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self._run_health_check()
            self._populate_models()

    def resizeEvent(self, event) -> None:
        """Switch header layout at the 280px threshold."""
        super().resizeEvent(event)
        narrow = self.width() < _NARROW_THRESHOLD
        # In narrow mode, hide task model label/combo to save space
        settings = self._settings_state.current_settings
        dual = settings.ai.routing_mode == "dual_model" if settings else False
        self._task_model_label.setVisible(dual and not narrow)
        self._task_model_combo.setVisible(dual and not narrow)

    # ------------------------------------------------------------------
    # Message area helpers
    # ------------------------------------------------------------------

    def _append_user_message(self, text: str) -> None:
        """Add a user message bubble to the chat area."""
        widget = UserMessageWidget(text)
        # Insert before the trailing stretch
        count = self._messages_layout.count()
        self._messages_layout.insertWidget(count - 1, widget)
        self._scroll_to_bottom()

    def _append_assistant_message(self) -> AssistantMessageWidget:
        """Add an empty assistant message bubble and return it for streaming."""
        widget = AssistantMessageWidget()
        count = self._messages_layout.count()
        self._messages_layout.insertWidget(count - 1, widget)
        self._scroll_to_bottom()
        return widget

    def _append_error_message(self, error: str) -> None:
        """Add an error label to the chat area."""
        label = QLabel(f"⚠ {error}")
        label.setWordWrap(True)
        label.setStyleSheet(
            "color: #ef4444; background-color: #fef2f2; border-radius: 6px; padding: 6px;"
        )
        count = self._messages_layout.count()
        self._messages_layout.insertWidget(count - 1, label)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the message area unless user scrolled up."""
        if not self._user_scrolled_up:
            sb = self._scroll_area.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _on_scroll_value_changed(self, value: int) -> None:
        """Detect whether the user has manually scrolled up."""
        sb = self._scroll_area.verticalScrollBar()
        self._user_scrolled_up = value < sb.maximum()

    # ------------------------------------------------------------------
    # Send / Stop
    # ------------------------------------------------------------------

    def _send_message(self) -> None:
        """Read input, dispatch to runtime, update UI state."""
        text = self._input_edit.toPlainText().strip()
        if not text or self._runtime is None:
            return

        self._input_edit.clear()
        self._send_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._user_scrolled_up = False

        self._append_user_message(text)
        self._current_assistant_widget = self._append_assistant_message()

        self._runtime.send_message(text)

    def _stop_streaming(self) -> None:
        """Cancel the in-progress request and restore UI state."""
        if self._runtime is not None:
            self._runtime.cancel_current_request()
        self._send_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Runtime signal slots
    # ------------------------------------------------------------------

    def _on_token_received(self, token: StreamToken) -> None:
        """Append streaming token delta to the current assistant widget.

        Args:
            token: The StreamToken carrying the incremental text delta.
        """
        if self._current_assistant_widget is not None:
            self._current_assistant_widget.append_token(token.delta)
            self._scroll_to_bottom()

    def _on_response_complete(self, response: AIResponse) -> None:
        """Finalize the current assistant message and restore UI state.

        Args:
            response: The completed AIResponse.
        """
        if self._current_assistant_widget is not None:
            # Ensure the full content is set (non-streaming path)
            if not self._current_assistant_widget._text:
                self._current_assistant_widget.set_text(response.content)
        self._current_assistant_widget = None
        self._send_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._scroll_to_bottom()

    def _on_error_occurred(self, error: str) -> None:
        """Display error in chat and restore UI state.

        Args:
            error: The error message string.
        """
        # Remove the empty assistant bubble if present
        if self._current_assistant_widget is not None:
            self._current_assistant_widget.setParent(None)
            self._current_assistant_widget = None

        self._append_error_message(error)
        self._send_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def _on_task_complete(self, result) -> None:
        """Render tool cards for each tool step and finalize the response.

        Args:
            result: The TaskRunResult from the runtime.
        """
        from app.ui.widgets.tool_call_card import ToolCard

        # Render a ToolCard for each tool step
        for tool_step in result.tool_steps:
            card = ToolCard(
                tool_name=tool_step.tool_name,
                arguments={},
                result=str(tool_step.output) if not tool_step.error else "",
                error=tool_step.error or "",
            )
            count = self._messages_layout.count()
            self._messages_layout.insertWidget(count - 1, card)

        # Set the final response text or show an error
        if result.final_response and self._current_assistant_widget is not None:
            self._current_assistant_widget.set_text(result.final_response)
        elif result.error:
            if self._current_assistant_widget is not None:
                self._current_assistant_widget.setParent(None)
                self._current_assistant_widget = None
            self._append_error_message(result.error)

        self._current_assistant_widget = None
        self._send_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._scroll_to_bottom()

    # ------------------------------------------------------------------
    # Settings change handler
    # ------------------------------------------------------------------

    def _on_ai_settings_changed(self, ai_settings: AISettings) -> None:
        """Recreate runtime, re-run health check, repopulate models.

        Args:
            ai_settings: The updated AISettings from SettingsState.
        """
        _log.info("AI settings changed — recreating runtime")
        self._disconnect_runtime_signals()

        self._runtime = ConversationRuntime(
            ai_settings=ai_settings,
            agent_policy=default_policy(),
        )
        self._connect_runtime_signals()

        self._sync_header_to_settings(ai_settings)
        self._run_health_check()
        self._populate_models()

    # ------------------------------------------------------------------
    # Header interaction handlers
    # ------------------------------------------------------------------

    def _on_provider_changed(self, provider: str) -> None:
        """Repopulate models when the provider combo changes.

        Args:
            provider: The newly selected provider name.
        """
        _log.debug("Provider changed to: %s", provider)
        self._populate_models()
        self._run_health_check()

    def _on_tools_toggled(self, checked: bool) -> None:
        """Log tools toggle state change.

        Args:
            checked: Whether tools are now enabled.
        """
        _log.debug("Tools toggle: %s", checked)
