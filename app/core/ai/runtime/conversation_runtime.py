"""ConversationRuntime and AIWorker for managing AI conversation state and threading."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal

from app.core.ai.providers.provider_base import AIProvider, AIResponse, StreamToken
from app.core.ai.providers.provider_factory import ProviderFactory
from app.core.ai.runtime.agent_policy import AgentPolicy, default_policy
from app.core.ai.runtime.async_base import AsyncRuntimeBase
from app.core.models.settings_models import AISettings
from app.core.utils.app_logger import get_logger

_log = get_logger("services.conversation_runtime")

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
# AIWorker
# ---------------------------------------------------------------------------


class AIWorker(QObject):
    """Worker object that runs provider calls on a background QThread.

    A new AIWorker instance is created for each request and moved to a
    dedicated QThread. Signals carry results back to the main thread.
    """

    token_received = Signal(object)     # StreamToken
    response_complete = Signal(object)  # AIResponse
    error_occurred = Signal(str)
    task_complete = Signal(object)      # TaskRunResult

    def __init__(
        self,
        provider: AIProvider,
        cancel_flag: threading.Event,
        ai_settings: AISettings,
    ) -> None:
        """Initialise the worker.

        Args:
            provider: The AIProvider instance to use for requests.
            cancel_flag: Shared threading.Event; set to request cancellation.
            ai_settings: Current AI configuration.
        """
        super().__init__()
        self._provider = provider
        self._cancel_flag = cancel_flag
        self._ai_settings = ai_settings

    def run_chat(self, messages: list, model: str) -> None:
        """Execute a chat request and emit results via signals.

        If streaming is enabled, emits token_received for each StreamToken
        and response_complete with the assembled AIResponse when done.
        If streaming is disabled, emits response_complete directly.
        On any exception, emits error_occurred.

        Args:
            messages: Conversation history as a list of role/content dicts.
            model: Model identifier to use.
        """
        try:
            if self._ai_settings.stream_enabled:
                accumulated = ""
                finish_reason = ""
                for token in self._provider.stream_chat(messages, model):
                    if self._cancel_flag.is_set():
                        finish_reason = "cancelled"
                        break
                    accumulated += token.delta
                    if token.finish_reason:
                        finish_reason = token.finish_reason
                    self.token_received.emit(token)

                response = AIResponse(
                    content=accumulated,
                    model=model,
                    finish_reason=finish_reason,
                )
                self.response_complete.emit(response)
            else:
                response = self._provider.chat(messages, model)
                self.response_complete.emit(response)
        except Exception as exc:  # noqa: BLE001
            _log.error("AIWorker.run_chat error: %s", exc, exc_info=True)
            self.error_occurred.emit(str(exc))

    def run_task_loop(
        self,
        messages: list,
        model: str,
        tool_registry,
        max_steps: int,
        tool_schemas: list = None,
    ) -> None:
        """Execute a multi-step task run with tool calling support.

        Iterates up to ``max_steps`` times, routing tool calls through
        ``ToolExecutor`` and appending results to the message history.
        Emits ``task_complete`` with a :class:`TaskRunResult` when done.

        Args:
            messages: Conversation history as a list of role/content dicts.
            model: Model identifier to use.
            tool_registry: ToolRegistry instance for tool lookup and execution.
            max_steps: Maximum number of tool call iterations allowed.
            tool_schemas: Optional list of OpenAI-format tool schema dicts to
                inject into the provider request.
        """
        import json as _json

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
                    self.task_complete.emit(result)
                    return

                # Build kwargs — inject tool schemas when available
                kwargs = {}
                if tool_schemas:
                    kwargs["tools"] = tool_schemas

                response = self._provider.chat(current_messages, model, **kwargs)

                # If the response contains tool calls, execute them
                if response.tool_calls and tool_registry is not None:
                    executor = ToolExecutor(tool_registry)
                    for tool_call in response.tool_calls:
                        tool_name = tool_call.get("function", {}).get("name", "")
                        arguments = tool_call.get("function", {}).get("arguments", {})
                        if isinstance(arguments, str):
                            try:
                                arguments = _json.loads(arguments)
                            except Exception:  # noqa: BLE001
                                arguments = {}

                        tool_result = executor.execute(tool_name, arguments)
                        tool_steps.append(tool_result)

                        # Append assistant message with tool call
                        current_messages.append({
                            "role": "assistant",
                            "content": response.content,
                            "tool_calls": response.tool_calls,
                        })
                        # Append tool result message
                        current_messages.append({
                            "role": "tool",
                            "content": str(tool_result.output) if not tool_result.error else tool_result.error,
                            "tool_call_id": tool_call.get("id", ""),
                        })

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
                        self.task_complete.emit(result)
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
                self.task_complete.emit(result)
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
            self.task_complete.emit(result)

        except Exception as exc:  # noqa: BLE001
            _log.error("AIWorker.run_task_loop error: %s", exc, exc_info=True)
            result = TaskRunResult(
                messages=current_messages,
                tool_steps=tool_steps,
                final_response=None,
                cancelled=False,
                error=str(exc),
            )
            self.task_complete.emit(result)


# ---------------------------------------------------------------------------
# ConversationRuntime
# ---------------------------------------------------------------------------


class ConversationRuntime(QObject, AsyncRuntimeBase):
    """Manages conversation history, model routing, and async provider calls.

    Dispatches requests to AIWorker on a background QThread and delivers
    results back to the main thread via Qt signals.

    Implements AsyncRuntimeBase for framework-agnostic async operations.
    """

    token_received = Signal(object)     # StreamToken (secret-scrubbed)
    response_complete = Signal(object)  # AIResponse
    error_occurred = Signal(str)
    task_complete = Signal(object)      # TaskRunResult

    def __init__(
        self,
        ai_settings: AISettings,
        agent_policy: Optional[AgentPolicy] = None,
        tool_registry=None,
        context_providers=None,
    ) -> None:
        """Initialise the runtime.

        Args:
            ai_settings: AI configuration (provider, models, flags).
            agent_policy: Governs system prompt and safety rules. Defaults to
                default_policy() if None.
            tool_registry: Optional ToolRegistry for task mode (Phase 3).
            context_providers: Optional list of AppContextProvider instances
                whose output is injected into the system prompt.
        """
        super().__init__()
        self._ai_settings = ai_settings
        self._policy = agent_policy if agent_policy is not None else default_policy()
        self._tool_registry = tool_registry
        self._context_providers: list = context_providers or []

        self._history: List[dict] = []
        self._cancel_flag = threading.Event()
        self._current_thread: Optional[QThread] = None
        self._current_worker: Optional[AIWorker] = None
        self._current_provider: Optional[AIProvider] = None

        self.set_system_prompt(self._policy.system_prompt)

    # ------------------------------------------------------------------
    # Public API
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

    def send_message(self, text: str) -> None:
        """Append a user message and dispatch a chat request asynchronously.

        Always uses chat_model regardless of routing_mode. Results are
        delivered via token_received / response_complete / error_occurred signals.

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
        self._start_worker(provider, lambda w: w.run_chat(messages, model))

    def run_task(self, text: str) -> None:
        """Append a user message and dispatch a task run asynchronously.

        Uses task_model when routing_mode is "dual_model", else chat_model.
        Results are delivered via task_complete / error_occurred signals.

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

        self._start_worker(
            provider,
            lambda w: w.run_task_loop(messages, model, self._tool_registry, max_steps, tool_schemas),
        )

    def cancel_current_request(self) -> None:
        """Cancel the in-progress request.

        Sets the cancel flag, closes the HTTP session via the provider, and
        waits up to 2 seconds for the worker thread to finish. If the thread
        does not finish within 2 seconds, logs a warning and detaches safely.
        """
        _log.info("Cancellation requested")
        self._cancel_flag.set()

        if self._current_provider is not None:
            try:
                self._current_provider.cancel_current_request()
            except Exception as exc:  # noqa: BLE001
                _log.warning("Error cancelling provider request: %s", exc)

        if self._current_thread is not None and self._current_thread.isRunning():
            finished = self._current_thread.wait(2000)  # 2 seconds in ms
            if not finished:
                _log.warning(
                    "Worker thread did not finish within 2 seconds after cancellation; detaching."
                )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
                    import json
                    context_parts.append(json.dumps(ctx, default=str))
            except Exception as exc:  # noqa: BLE001
                _log.warning("Context provider error: %s", exc)

        if not context_parts:
            return list(self._history)

        messages = list(self._history)
        if messages and messages[0]["role"] == "system":
            enriched_prompt = messages[0]["content"] + "\n\n## App Context\n" + "\n".join(context_parts)
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
            self.error_occurred.emit(msg)

    def _start_worker(self, provider: AIProvider, run_fn) -> None:
        """Create an AIWorker + QThread, connect signals, and start the thread.

        Args:
            provider: The AIProvider instance for this request.
            run_fn: Callable that accepts the worker and triggers the desired
                run method (e.g. ``lambda w: w.run_chat(messages, model)``).
        """
        self._cancel_flag.clear()

        thread = QThread()
        worker = AIWorker(provider, self._cancel_flag, self._ai_settings)
        worker.moveToThread(thread)

        # Connect worker signals to runtime slots
        worker.token_received.connect(self._on_token_received)
        worker.response_complete.connect(self._on_response_complete)
        worker.error_occurred.connect(self._on_error_occurred)
        worker.task_complete.connect(self._on_task_complete)

        # Start the work when the thread starts
        thread.started.connect(lambda: run_fn(worker))

        # Clean up when the worker signals completion or error
        worker.response_complete.connect(lambda _: self._cleanup_thread())
        worker.error_occurred.connect(lambda _: self._cleanup_thread())
        worker.task_complete.connect(lambda _: self._cleanup_thread())

        self._current_thread = thread
        self._current_worker = worker

        thread.start()
        _log.debug("Started AIWorker thread for request")

    def _cleanup_thread(self) -> None:
        """Disconnect signals and schedule the thread for deletion."""
        thread = self._current_thread
        worker = self._current_worker

        if worker is not None:
            try:
                worker.token_received.disconnect(self._on_token_received)
                worker.response_complete.disconnect(self._on_response_complete)
                worker.error_occurred.disconnect(self._on_error_occurred)
                worker.task_complete.disconnect(self._on_task_complete)
            except RuntimeError:
                pass  # Already disconnected

        if thread is not None:
            thread.quit()
            thread.deleteLater()

        self._current_thread = None
        self._current_worker = None
        self._current_provider = None

    # ------------------------------------------------------------------
    # Signal slots
    # ------------------------------------------------------------------

    def _on_token_received(self, token: StreamToken) -> None:
        """Scrub secrets from token delta before forwarding to UI.

        Args:
            token: The StreamToken received from the worker.
        """
        scrubbed_delta = _scrub_secrets(token.delta)
        scrubbed_token = StreamToken(delta=scrubbed_delta, finish_reason=token.finish_reason)
        self.token_received.emit(scrubbed_token)

    def _on_response_complete(self, response: AIResponse) -> None:
        """Append the assistant message to history and forward the signal.

        Args:
            response: The completed AIResponse from the worker.
        """
        self._history.append({"role": "assistant", "content": response.content})
        self.response_complete.emit(response)

    def _on_error_occurred(self, error: str) -> None:
        """Forward error signal without appending a partial message to history.

        Args:
            error: The error message string.
        """
        self.error_occurred.emit(error)

    def _on_task_complete(self, result: TaskRunResult) -> None:
        """Forward task_complete signal.

        Args:
            result: The TaskRunResult from the worker.
        """
        self.task_complete.emit(result)
