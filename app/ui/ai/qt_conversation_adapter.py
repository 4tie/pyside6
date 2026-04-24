"""Qt adapter for AsyncConversationRuntime.

Bridges the asyncio-based core runtime to Qt signals for the desktop UI.
This layer belongs in the UI layer and contains the Qt-specific code.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from PySide6.QtCore import QObject, Signal

from app.core.ai.runtime.async_conversation_runtime import (
    AsyncConversationRuntime,
    TaskRunResult,
)
from app.core.ai.providers.provider_base import AIResponse, StreamToken
from app.core.ai.runtime.agent_policy import AgentPolicy
from app.core.models.settings_models import AISettings
from app.core.utils.app_logger import get_logger

_log = get_logger("ui.qt_conversation_adapter")


class QtConversationAdapter(QObject):
    """Qt adapter that bridges AsyncConversationRuntime to Qt signals.

    This class wraps the framework-agnostic AsyncConversationRuntime and
    converts its callback-based API to Qt signals for use in the PySide6 UI.
    """

    token_received = Signal(object)  # StreamToken
    response_complete = Signal(object)  # AIResponse
    error_occurred = Signal(str)
    task_complete = Signal(object)  # TaskRunResult

    def __init__(
        self,
        ai_settings: AISettings,
        agent_policy: Optional[AgentPolicy] = None,
        tool_registry=None,
        context_providers=None,
    ) -> None:
        """Initialize the Qt adapter.

        Args:
            ai_settings: AI configuration (provider, models, flags).
            agent_policy: Governs system prompt and safety rules.
            tool_registry: Optional ToolRegistry for task mode.
            context_providers: Optional list of AppContextProvider instances.
        """
        super().__init__()
        self._runtime = AsyncConversationRuntime(
            ai_settings=ai_settings,
            agent_policy=agent_policy,
            tool_registry=tool_registry,
            context_providers=context_providers,
        )

        # Register callbacks that emit Qt signals
        self._runtime.set_callbacks(
            on_token=self._on_token,
            on_response=self._on_response,
            on_error=self._on_error,
            on_task_complete=self._on_task_complete,
        )

        # Event loop for running async operations
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ------------------------------------------------------------------
    # Public API (delegates to core runtime)
    # ------------------------------------------------------------------

    def set_system_prompt(self, prompt: str) -> None:
        """Set or replace the system message."""
        self._runtime.set_system_prompt(prompt)

    def clear_history(self) -> None:
        """Remove all messages except the system prompt."""
        self._runtime.clear_history()

    def send_message(self, text: str) -> None:
        """Append a user message and dispatch a chat request asynchronously.

        Args:
            text: The user's message text.
        """
        if self._ensure_event_loop():
            self._runtime.send_message(text)

    def run_task(self, text: str) -> None:
        """Append a user message and dispatch a task run asynchronously.

        Args:
            text: The user's task description text.
        """
        if self._ensure_event_loop():
            self._runtime.run_task(text)

    def cancel_current_request(self) -> None:
        """Cancel the in-progress request."""
        self._runtime.cancel_current_request()

    # ------------------------------------------------------------------
    # Qt signal callbacks
    # ------------------------------------------------------------------

    def _on_token(self, token: StreamToken) -> None:
        """Emit Qt signal for streaming token."""
        self.token_received.emit(token)

    def _on_response(self, response: AIResponse) -> None:
        """Emit Qt signal for completed response."""
        self.response_complete.emit(response)

    def _on_error(self, error: str) -> None:
        """Emit Qt signal for error."""
        self.error_occurred.emit(error)

    def _on_task_complete(self, result: TaskRunResult) -> None:
        """Emit Qt signal for task completion."""
        self.task_complete.emit(result)

    # ------------------------------------------------------------------
    # Event loop management
    # ------------------------------------------------------------------

    def _ensure_event_loop(self) -> bool:
        """Ensure an event loop is available for async operations.

        Returns:
            True if event loop is available, False otherwise.
        """
        try:
            # Try to get or create an event loop
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, create one
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
            return True
        except Exception as exc:
            _log.error("Failed to ensure event loop: %s", exc)
            return False
