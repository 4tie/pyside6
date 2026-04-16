"""AIChatDock — dockable AI Chat panel wired to ConversationRuntime."""

from typing import Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
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


# ---------------------------------------------------------------------------
# Background worker — health check only
# ---------------------------------------------------------------------------


class _HealthWorker(QObject):
    """Runs a provider health check on a background thread."""

    health_ready = Signal(object)  # ProviderHealth

    def __init__(self, ai_settings: AISettings) -> None:
        super().__init__()
        self._ai_settings = ai_settings

    def run(self) -> None:
        try:
            provider = ProviderFactory.create(self._ai_settings)
            health = provider.health_check()
        except Exception as exc:  # noqa: BLE001
            health = ProviderHealth(ok=False, message=str(exc))
        self.health_ready.emit(health)


# ---------------------------------------------------------------------------
# AIChatDock
# ---------------------------------------------------------------------------


class AIChatDock(QDockWidget):
    """Dockable AI Chat panel backed by ConversationRuntime.

    Model and provider selection live exclusively in Settings → AI.
    """

    def __init__(self, settings_state: SettingsState, parent=None):
        super().__init__("AI Chat", parent)
        self.setObjectName("AIChatDock")
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)

        self._settings_state = settings_state
        self._runtime: Optional[ConversationRuntime] = None
        self._current_assistant_widget: Optional[AssistantMessageWidget] = None
        self._user_scrolled_up = False
        self._first_show = True

        self._health_thread: Optional[QThread] = None
        self._health_worker: Optional[_HealthWorker] = None

        self._build_ui()
        self._init_runtime()

        self._settings_state.ai_settings_changed.connect(self._on_ai_settings_changed)
        _log.debug("AIChatDock initialised")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(4)

        # --- Header: status dot + provider label + tools toggle ---
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self._status_label = QLabel("●")
        self._status_label.setToolTip("Provider connection status")
        self._set_status_color("yellow")
        header_layout.addWidget(self._status_label)

        self._provider_label = QLabel()
        self._provider_label.setStyleSheet("color: gray; font-size: 11px;")
        header_layout.addWidget(self._provider_label)

        header_layout.addStretch()

        self._tools_btn = QToolButton()
        self._tools_btn.setText("Tools")
        self._tools_btn.setCheckable(True)
        self._tools_btn.setToolTip("Toggle tool calling (configure in Settings → AI)")
        self._tools_btn.setEnabled(False)  # read-only indicator; change via Settings
        header_layout.addWidget(self._tools_btn)

        root_layout.addWidget(header)

        # --- Message area ---
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._messages_widget = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_widget)
        self._messages_layout.setContentsMargins(0, 0, 0, 0)
        self._messages_layout.setSpacing(2)
        self._messages_layout.addStretch()

        self._scroll_area.setWidget(self._messages_widget)
        self._scroll_area.verticalScrollBar().valueChanged.connect(
            self._on_scroll_value_changed
        )
        root_layout.addWidget(self._scroll_area, stretch=1)

        # --- Input area / no-model placeholder ---
        self._no_model_label = QLabel("Select a model in Settings → AI to get started.")
        self._no_model_label.setAlignment(Qt.AlignCenter)
        self._no_model_label.setWordWrap(True)
        self._no_model_label.setVisible(False)
        root_layout.addWidget(self._no_model_label)

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
        root_layout.addWidget(self._input_widget)

        self.setWidget(root)
        self._sync_input_visibility()

    # ------------------------------------------------------------------
    # Runtime
    # ------------------------------------------------------------------

    def _init_runtime(self) -> None:
        settings = self._settings_state.current_settings
        ai_settings = settings.ai if settings else AISettings()
        self._runtime = ConversationRuntime(ai_settings=ai_settings, agent_policy=default_policy())
        self._connect_runtime_signals()
        self._sync_header_to_settings(ai_settings)

    def _connect_runtime_signals(self) -> None:
        if self._runtime is None:
            return
        self._runtime.token_received.connect(self._on_token_received)
        self._runtime.response_complete.connect(self._on_response_complete)
        self._runtime.error_occurred.connect(self._on_error_occurred)
        self._runtime.task_complete.connect(self._on_task_complete)

    def _disconnect_runtime_signals(self) -> None:
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
    # Header helpers
    # ------------------------------------------------------------------

    def _sync_header_to_settings(self, ai_settings: AISettings) -> None:
        """Reflect current settings in the header (read-only display)."""
        provider = ai_settings.provider
        model = ai_settings.chat_model or "—"
        self._provider_label.setText(f"{provider} · {model}")

        self._tools_btn.blockSignals(True)
        self._tools_btn.setChecked(ai_settings.tools_enabled)
        self._tools_btn.blockSignals(False)

        self._sync_input_visibility()

    def _sync_input_visibility(self) -> None:
        settings = self._settings_state.current_settings
        has_model = bool(settings.ai.chat_model if settings else "")
        self._input_widget.setVisible(has_model)
        self._no_model_label.setVisible(not has_model)

    # ------------------------------------------------------------------
    # Status indicator
    # ------------------------------------------------------------------

    def _set_status_color(self, color: str) -> None:
        colors = {"green": "#22c55e", "red": "#ef4444", "yellow": "#eab308"}
        self._status_label.setStyleSheet(
            f"color: {colors.get(color, '#eab308')}; font-size: 14px;"
        )

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def _run_health_check(self) -> None:
        settings = self._settings_state.current_settings
        ai_settings = settings.ai if settings else AISettings()
        self._set_status_color("yellow")

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
        self._set_status_color("green" if health.ok else "red")
        tooltip = health.message
        if health.latency_ms is not None:
            tooltip += f" ({health.latency_ms:.0f} ms)"
        self._status_label.setToolTip(tooltip)

    # ------------------------------------------------------------------
    # Qt events
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self._run_health_check()

    # ------------------------------------------------------------------
    # Message area
    # ------------------------------------------------------------------

    def _append_user_message(self, text: str) -> None:
        widget = UserMessageWidget(text)
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, widget)
        self._scroll_to_bottom()

    def _append_assistant_message(self) -> AssistantMessageWidget:
        widget = AssistantMessageWidget()
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, widget)
        self._scroll_to_bottom()
        return widget

    def _append_error_message(self, error: str) -> None:
        label = QLabel(f"⚠ {error}")
        label.setWordWrap(True)
        label.setStyleSheet(
            "color: #ef4444; background-color: #fef2f2; border-radius: 6px; padding: 6px;"
        )
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, label)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        if not self._user_scrolled_up:
            sb = self._scroll_area.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _on_scroll_value_changed(self, value: int) -> None:
        sb = self._scroll_area.verticalScrollBar()
        self._user_scrolled_up = value < sb.maximum()

    # ------------------------------------------------------------------
    # Send / Stop
    # ------------------------------------------------------------------

    def _send_message(self) -> None:
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
        if self._runtime is not None:
            self._runtime.cancel_current_request()
        self._send_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Runtime signal slots
    # ------------------------------------------------------------------

    def _on_token_received(self, token: StreamToken) -> None:
        if self._current_assistant_widget is not None:
            self._current_assistant_widget.append_token(token.delta)
            self._scroll_to_bottom()

    def _on_response_complete(self, response: AIResponse) -> None:
        if self._current_assistant_widget is not None:
            if not self._current_assistant_widget._text:
                self._current_assistant_widget.set_text(response.content)
        self._current_assistant_widget = None
        self._send_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._scroll_to_bottom()

    def _on_error_occurred(self, error: str) -> None:
        if self._current_assistant_widget is not None:
            self._current_assistant_widget.setParent(None)
            self._current_assistant_widget = None
        self._append_error_message(error)
        self._send_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def _on_task_complete(self, result) -> None:
        from app.ui.widgets.tool_call_card import ToolCard
        for tool_step in result.tool_steps:
            card = ToolCard(
                tool_name=tool_step.tool_name,
                arguments={},
                result=str(tool_step.output) if not tool_step.error else "",
                error=tool_step.error or "",
            )
            self._messages_layout.insertWidget(self._messages_layout.count() - 1, card)

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
    # Settings change
    # ------------------------------------------------------------------

    def _on_ai_settings_changed(self, ai_settings: AISettings) -> None:
        _log.info("AI settings changed — recreating runtime")
        self._disconnect_runtime_signals()
        self._runtime = ConversationRuntime(ai_settings=ai_settings, agent_policy=default_policy())
        self._connect_runtime_signals()
        self._sync_header_to_settings(ai_settings)
        self._run_health_check()
