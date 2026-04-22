"""Abstract base for async AI operations.

Defines the interface for framework-agnostic async operations,
allowing implementations for Qt (desktop UI) and asyncio (web UI).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional

from app.core.ai.providers.provider_base import AIResponse, StreamToken
from app.core.models.settings_models import AISettings


class AsyncRuntimeBase(ABC):
    """Abstract base for async AI conversation runtime.

    Implementations can use Qt signals (for desktop UI) or asyncio/futures
    (for web UI) to handle async operations.
    """

    @abstractmethod
    def send_message(self, text: str) -> None:
        """Append a user message and dispatch a chat request asynchronously.

        Args:
            text: The user's message text.
        """
        pass

    @abstractmethod
    def run_task(self, text: str) -> None:
        """Append a user message and dispatch a task run asynchronously.

        Args:
            text: The user's task description text.
        """
        pass

    @abstractmethod
    def cancel_current_request(self) -> None:
        """Cancel the in-progress request."""
        pass

    @abstractmethod
    def clear_history(self) -> None:
        """Remove all messages except the system prompt."""
        pass

    @abstractmethod
    def set_system_prompt(self, prompt: str) -> None:
        """Set or replace the system message at index 0 of history.

        Args:
            prompt: The new system prompt text.
        """
        pass


class AsyncWorkerBase(ABC):
    """Abstract base for async worker that executes AI requests.

    Implementations handle the actual execution in a background thread
    or async context.
    """

    @abstractmethod
    def run_chat(self, messages: list, model: str) -> None:
        """Execute a chat request and emit results via signals/callbacks.

        Args:
            messages: Conversation history as a list of role/content dicts.
            model: Model identifier to use.
        """
        pass

    @abstractmethod
    def run_task_loop(
        self,
        messages: list,
        model: str,
        tool_registry,
        max_steps: int,
        tool_schemas: list = None,
    ) -> None:
        """Execute a multi-step task run with tool calling support.

        Args:
            messages: Conversation history as a list of role/content dicts.
            model: Model identifier to use.
            tool_registry: ToolRegistry instance for tool lookup and execution.
            max_steps: Maximum number of tool call iterations allowed.
            tool_schemas: Optional list of OpenAI-format tool schema dicts.
        """
        pass
