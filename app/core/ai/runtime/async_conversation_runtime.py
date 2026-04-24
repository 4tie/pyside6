"""Asyncio-based ConversationRuntime for framework-agnostic AI operations.

This module provides a pure asyncio implementation without Qt dependencies,
designed to be used by both web and desktop UIs through appropriate adapters.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Callable, List

from app.core.parsing.json_parser import parse_json_string, json_dumps
from app.core.ai.providers.provider_base import AIProvider, AIResponse, StreamToken
from app.core.ai.providers.provider_factory import ProviderFactory
from app.core.ai.runtime.agent_policy import AgentPolicy, default_policy
from app.core.ai.runtime.async_base import AsyncRuntimeBase
from app.core.models.settings_models import AISettings
from app.core.utils.app_logger import get_logger

_log = get_logger("services.async_conversation_runtime")

# ---------------------------------------------------------------------------
# Secret scrubbing
# ---------------------------------------------------------------------------

_SECRET_PATTERN = re.compile(r"(sk-[A-Za-z0-9\-_]{8,}|Bearer\s+[A-Za-z0-9\-_\.]{8,})")


def _scrub_secrets(text: str) -> str:
    """Replace known secret patterns with a redaction placeholder."""
    return _SECRET_PATTERN.sub("[REDACTED]", text)


# ---------------------------------------------------------------------------
# Model capability registry
# ---------------------------------------------------------------------------

_MODEL_CAPABILITY_REGISTRY: dict[str, str] = {
    "llama2": "Level_A",
    "mistral": "Level_B",
    "llama3": "Level_B",
    "qwen": "Level_B",
    "gpt-4": "Level_C",
    "claude": "Level_C",
    "mistral-nemo": "Level_C",
}
_DEFAULT_CAPABILITY = "Level_B"


def _get_model_capability(model: str, provider: AIProvider) -> str:
    """Return the capability level for a model.

    First tries the provider's own metadata. If the provider returns the
    default Level_B, falls back to prefix-matching against the registry.

    Args:
        model: Model identifier string.
        provider: The active AIProvider instance.

    Returns:
        Capability level string: 'Level_A', 'Level_B', or 'Level_C'.
    """
    provider_level = provider.get_model_capability(model)
    if provider_level != "Level_B":
        return provider_level

    model_lower = model.lower()
    for pattern, level in _MODEL_CAPABILITY_REGISTRY.items():
        if model_lower.startswith(pattern):
            return level

    return _DEFAULT_CAPABILITY


# ---------------------------------------------------------------------------
# TaskRunResult
# ---------------------------------------------------------------------------


@dataclass
class TaskRunResult:
    """Result returned by ConversationRuntime.run_task().

    Attributes:
        messages: Full message history at the time the task completed.
        tool_steps: List of ToolResult objects from each tool call iteration.
        final_response: The last assistant response text, or None if cancelled/errored.
        cancelled: True if the task was cancelled before completion.
        error: Error message string if the task failed, else None.
    """

    messages: list = field(default_factory=list)
    tool_steps: list = field(default_factory=list)
    final_response: Optional[str] = None
    cancelled: bool = False
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# AsyncConversationRuntime
# ---------------------------------------------------------------------------


class AsyncConversationRuntime(AsyncRuntimeBase):
    """Framework-agnostic asyncio-based AI conversation runtime.

    Manages conversation history, model routing, and async provider calls
    using pure asyncio without Qt dependencies.

    Callbacks can be registered for:
    - on_token: Called for each streaming token
    - on_response: Called when response is complete
    - on_error: Called on errors
    - on_task_complete: Called when task execution completes
    """

    def __init__(
        self,
        ai_settings: AISettings,
        agent_policy: Optional[AgentPolicy] = None,
        tool_registry=None,
        context_providers=None,
    ) -> None:
        """Initialize the runtime.

        Args:
            ai_settings: AI configuration (provider, models, flags).
            agent_policy: Governs system prompt and safety rules. Defaults to
                default_policy() if None.
            tool_registry: Optional ToolRegistry for task mode (Phase 3).
            context_providers: Optional list of AppContextProvider instances
                whose output is injected into the system prompt.
        """
        self._ai_settings = ai_settings
        self._policy = agent_policy if agent_policy is not None else default_policy()
        self._tool_registry = tool_registry
        self._context_providers: list = context_providers or []

        self._history: List[dict] = []
        self._cancel_flag = asyncio.Event()
        self._current_task: Optional[asyncio.Task] = None
        self._current_provider: Optional[AIProvider] = None

        # Callbacks
        self._on_token_callback: Optional[Callable[[StreamToken], None]] = None
        self._on_response_callback: Optional[Callable[[AIResponse], None]] = None
        self._on_error_callback: Optional[Callable[[str], None]] = None
        self._on_task_complete_callback: Optional[Callable[[TaskRunResult], None]] = None

        self.set_system_prompt(self._policy.system_prompt)

    def set_callbacks(
        self,
        on_token: Optional[Callable[[StreamToken], None]] = None,
        on_response: Optional[Callable[[AIResponse], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_task_complete: Optional[Callable[[TaskRunResult], None]] = None,
    ) -> None:
        """Register callbacks for async events.

        Args:
            on_token: Called for each streaming token.
            on_response: Called when response is complete.
            on_error: Called on errors.
            on_task_complete: Called when task execution completes.
        """
        self._on_token_callback = on_token
        self._on_response_callback = on_response
        self._on_error_callback = on_error
        self._on_task_complete_callback = on_task_complete

    # ------------------------------------------------------------------
    # Public API (matches AsyncRuntimeBase)
    # ------------------------------------------------------------------

    def send_message(self, text: str) -> None:
        """Append a user message and dispatch a chat request asynchronously.

        Always uses chat_model regardless of routing_mode. Results are
        delivered via callbacks.

        Args:
            text: The user's message text.
        """
        self._history.append({"role": "user", "content": text})
        self._trim_history()

        model = self._ai_settings.chat_model
        provider = ProviderFactory.create(self._ai_settings)
        self._current_provider = provider

        self._check_tool_capability(model, provider)

        messages = self._build_messages()
        self._start_task(self._run_chat_async(provider, messages, model))

    def run_task(self, text: str) -> None:
        """Append a user message and dispatch a task run asynchronously.

        Uses task_model when routing_mode is "dual_model", else chat_model.
        Results are delivered via callbacks.

        Args:
            text: The user's task description text.
        """
        self._history.append({"role": "user", "content": text})
        self._trim_history()

        if self._ai_settings.routing_mode == "dual_model":
            model = self._ai_settings.task_model
        else:
            model = self._ai_settings.chat_model

        provider = ProviderFactory.create(self._ai_settings)
        self._current_provider = provider

        self._check_tool_capability(model, provider)

        messages = self._build_messages()
        max_steps = self._ai_settings.max_tool_steps

        # Compute tool schemas if tools are enabled and model supports it
        tool_schemas: list = []
        if self._ai_settings.tools_enabled and self._tool_registry is not None:
            capability = _get_model_capability(model, provider)
            if capability in ("Level_B", "Level_C"):
                tool_schemas = self._tool_registry.get_schema_list()

        self._start_task(
            self._run_task_loop_async(
                provider, messages, model, self._tool_registry, max_steps, tool_schemas
            )
        )

    def cancel_current_request(self) -> None:
        """Cancel the in-progress request.

        Sets the cancel flag and closes the HTTP session via the provider.
        """
        _log.info("Cancellation requested")
        self._cancel_flag.set()

        if self._current_provider is not None:
            try:
                self._current_provider.cancel_current_request()
            except Exception as exc:
                _log.warning("Error cancelling provider request: %s", exc)

        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

    # ------------------------------------------------------------------
    # Private async methods
    # ------------------------------------------------------------------

    async def _run_chat_async(
        self, provider: AIProvider, messages: list, model: str
    ) -> None:
        """Execute a chat request asynchronously.

        If streaming is enabled, calls on_token for each StreamToken
        and on_response with the assembled AIResponse when done.
        If streaming is disabled, calls on_response directly.
        On any exception, calls on_error.

        Args:
            provider: The AIProvider instance to use for requests.
            messages: Conversation history as a list of role/content dicts.
            model: Model identifier to use.
        """
        try:
            if self._ai_settings.stream_enabled:
                accumulated = ""
                finish_reason = ""
                async for token in provider.stream_chat_async(messages, model):
                    if self._cancel_flag.is_set():
                        finish_reason = "cancelled"
                        break
                    accumulated += token.delta
                    if token.finish_reason:
                        finish_reason = token.finish_reason
                    scrubbed_token = StreamToken(
                        delta=_scrub_secrets(token.delta), finish_reason=token.finish_reason
                    )
                    if self._on_token_callback:
                        self._on_token_callback(scrubbed_token)

                response = AIResponse(
                    content=accumulated,
                    model=model,
                    finish_reason=finish_reason,
                )
                if self._on_response_callback:
                    self._on_response_callback(response)
            else:
                response = await provider.chat_async(messages, model)
                if self._on_response_callback:
                    self._on_response_callback(response)
        except Exception as exc:
            _log.error("Async chat error: %s", exc, exc_info=True)
            if self._on_error_callback:
                self._on_error_callback(str(exc))

    async def _run_task_loop_async(
        self,
        provider: AIProvider,
        messages: list,
        model: str,
        tool_registry,
        max_steps: int,
        tool_schemas: list = None,
    ) -> None:
        """Execute a multi-step task run with tool calling support.

        Iterates up to ``max_steps`` times, routing tool calls through
        ``ToolExecutor`` and appending results to the message history.
        Calls ``on_task_complete`` with a :class:`TaskRunResult` when done.

        Args:
            provider: The AIProvider instance to use for requests.
            messages: Conversation history as a list of role/content dicts.
            model: Model identifier to use.
            tool_registry: ToolRegistry instance for tool lookup and execution.
            max_steps: Maximum number of tool call iterations allowed.
            tool_schemas: Optional list of OpenAI-format tool schema dicts to
                inject into the provider request.
        """
        import json

        from app.core.ai.tools.tool_executor import ToolExecutor

        tool_steps = []
        current_messages = list(messages)

        try:
            for step in range(max_steps + 1):
                if self._cancel_flag.is_set():
                    result = TaskRunResult(
                        messages=current_messages,
                        tool_steps=tool_steps,
                        final_response=None,
                        cancelled=True,
                        error=None,
                    )
                    if self._on_task_complete_callback:
                        self._on_task_complete_callback(result)
                    return

                # Build kwargs — inject tool schemas when available
                kwargs = {}
                if tool_schemas:
                    kwargs["tools"] = tool_schemas

                response = await provider.chat_async(current_messages, model, **kwargs)

                # If the response contains tool calls, execute them
                if response.tool_calls and tool_registry is not None:
                    executor = ToolExecutor(tool_registry)
                    for tool_call in response.tool_calls:
                        tool_name = tool_call.get("function", {}).get("name", "")
                        arguments = tool_call.get("function", {}).get("arguments", {})
                        if isinstance(arguments, str):
                            try:
                                arguments = parse_json_string(arguments)
                            except Exception:
                                arguments = {}

                        tool_result = executor.execute(tool_name, arguments)
                        tool_steps.append(tool_result)

                        # Append assistant message with tool call
                        current_messages.append(
                            {
                                "role": "assistant",
                                "content": response.content,
                                "tool_calls": response.tool_calls,
                            }
                        )
                        # Append tool result message
                        current_messages.append(
                            {
                                "role": "tool",
                                "content": str(tool_result.output)
                                if not tool_result.error
                                else tool_result.error,
                                "tool_call_id": tool_call.get("id", ""),
                            }
                        )

                    # Check if we've hit the step limit
                    if step >= max_steps - 1:
                        _log.warning("Max tool steps (%d) reached", max_steps)
                        result = TaskRunResult(
                            messages=current_messages,
                            tool_steps=tool_steps,
                            final_response=None,
                            cancelled=False,
                            error="Max tool steps reached",
                        )
                        if self._on_task_complete_callback:
                            self._on_task_complete_callback(result)
                        return

                    # Continue to next iteration
                    continue

                # No tool calls — this is the final response
                result = TaskRunResult(
                    messages=current_messages,
                    tool_steps=tool_steps,
                    final_response=response.content,
                    cancelled=False,
                    error=None,
                )
                if self._on_task_complete_callback:
                    self._on_task_complete_callback(result)
                return

            # Fell through all steps without a final response
            _log.warning("Max tool steps (%d) reached", max_steps)
            result = TaskRunResult(
                messages=current_messages,
                tool_steps=tool_steps,
                final_response=None,
                cancelled=False,
                error="Max tool steps reached",
            )
            if self._on_task_complete_callback:
                self._on_task_complete_callback(result)

        except Exception as exc:
            _log.error("Async task loop error: %s", exc, exc_info=True)
            result = TaskRunResult(
                messages=current_messages,
                tool_steps=tool_steps,
                final_response=None,
                cancelled=False,
                error=str(exc),
            )
            if self._on_task_complete_callback:
                self._on_task_complete_callback(result)

    def _start_task(self, coro) -> None:
        """Start an async task and track it for cancellation.

        Args:
            coro: The coroutine to execute.
        """
        self._cancel_flag.clear()
        self._current_task = asyncio.create_task(coro)

    # ------------------------------------------------------------------
    # Private helpers (same as original)
    # ------------------------------------------------------------------

    def set_system_prompt(self, prompt: str) -> None:
        """Set or replace the system message at index 0 of history.

        Args:
            prompt: The new system prompt text.
        """
        system_msg = {"role": "system", "content": prompt}
        if self._history and self._history[0]["role"] == "system":
            self._history[0] = system_msg
        else:
            self._history.insert(0, system_msg)

    def clear_history(self) -> None:
        """Remove all messages except the system prompt."""
        if self._history and self._history[0]["role"] == "system":
            self._history = [self._history[0]]
        else:
            self._history = []

    def _trim_history(self) -> None:
        """Enforce max_history_messages by removing oldest non-system messages."""
        limit = self._ai_settings.max_history_messages
        if limit <= 0:
            return

        while len(self._history) > limit:
            # Find the first non-system message and remove it
            for i, msg in enumerate(self._history):
                if msg["role"] != "system":
                    self._history.pop(i)
                    break
            else:
                # Only system messages remain — nothing to trim
                break

    def _build_messages(self) -> list:
        """Build the message list to send to the provider.

        Injects context provider output into the system prompt if any
        context providers are configured.

        Returns:
            A copy of the history list, with an enriched system prompt if
            context providers are present.
        """
        if not self._context_providers:
            return list(self._history)

        context_parts: list[str] = []
        for cp in self._context_providers:
            try:
                ctx = cp.get_context()
                if ctx:
                    context_parts.append(json_dumps(ctx, default=str))
            except Exception as exc:
                _log.warning("Context provider error: %s", exc)

        if not context_parts:
            return list(self._history)

        messages = list(self._history)
        if messages and messages[0]["role"] == "system":
            enriched_prompt = (
                messages[0]["content"] + "\n\n## App Context\n" + "\n".join(context_parts)
            )
            messages = [{"role": "system", "content": enriched_prompt}] + messages[1:]

        return messages

    def _check_tool_capability(self, model: str, provider: AIProvider) -> None:
        """Emit a warning if tools are enabled but the model is Level_A.

        Args:
            model: The model identifier being used.
            provider: The active AIProvider instance.
        """
        if not self._ai_settings.tools_enabled:
            return

        capability = _get_model_capability(model, provider)
        if capability == "Level_A":
            msg = (
                f"Model '{model}' is Level_A (plain text only) and does not support "
                "tool calling. Tool injection has been skipped for this request."
            )
            _log.warning(msg)
            if self._on_error_callback:
                self._on_error_callback(msg)
