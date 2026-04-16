# Requirements Document

## Introduction

The AI Chat Panel is an embedded AI platform for the Freqtrade GUI desktop application. It provides a dockable panel (QDockWidget) that gives users access to an AI assistant capable of plain conversation, app-aware context delivery, and tool-driven actions such as reading logs, inspecting backtest results, and analyzing strategies. The platform is provider-agnostic (Ollama local-first, OpenRouter optional), supports streaming responses, and is designed to be extended incrementally across five phases — from a basic chat UI through to autonomous strategy-analysis loops.

The five phases are:
- Phase 1: Foundation — AISettings model, SettingsState signal, AIState QObject, dock placeholder
- Phase 2: Providers — AIProvider ABC, OllamaProvider, OpenRouterProvider, ProviderFactory, ConversationRuntime, AIWorker threading
- Phase 3: Tools — ToolRegistry, ToolExecutor, basic app tools (get_app_status, read_recent_logs, get_last_error, list_recent_events)
- Phase 4: Context + Journal — AppContextProvider hierarchy, EventJournal, EventJournal adapters for existing services
- Phase 5: Backtest/Strategy tools — get_latest_backtest_result, load_run_history, compare_runs, list_strategies, read_strategy_code, read_strategy_params

The AI is a read-and-advise layer only. It never directly mutates application state, executes trades, or writes files without explicit user confirmation. All real business logic remains in existing services.

---

## Glossary

- **AI_Panel**: The QDockWidget that hosts the entire AI chat interface, dockable on the right side of MainWindow by default.
- **AIProvider**: The abstract interface that all LLM backend implementations must satisfy (`chat`, `stream_chat`, `list_models`, `health_check`).
- **OllamaProvider**: Concrete AIProvider implementation that communicates with a locally running Ollama server.
- **OpenRouterProvider**: Concrete AIProvider implementation that communicates with the OpenRouter cloud API.
- **ConversationRuntime**: The component that manages conversation history, system prompt, tool schema injection, response parsing, and mode switching.
- **ToolRegistry**: The registry that stores all available tool definitions (schemas + callables).
- **ToolExecutor**: The component that validates tool call requests from the AI and dispatches them to registered tools.
- **AppContextProvider**: The abstract interface for components that collect and deliver structured context packets to the AI.
- **EventJournal**: The append-only in-memory log of timestamped application events (user actions, command starts/ends, validation results, etc.).
- **AISettings**: The Pydantic model nested inside AppSettings that stores all AI-related configuration (provider, models, endpoint, API key, timeouts, feature flags, routing mode).
- **TaskRunResult**: A dataclass returned by `run_task()` containing the full message history, tool steps, final response text, cancellation flag, and error string.
- **ToolResult**: A dataclass returned by ToolExecutor containing the tool name, output (Any), display text, and optional error string.
- **routing_mode**: An AISettings field controlling whether a single model handles both chat and task calls (`"single_model"`) or separate models are used (`"dual_model"`).
- **Level_A**: A model capable only of plain text conversation.
- **Level_B**: A model capable of producing structured JSON responses.
- **Level_C**: A model with native tool/function-calling support.
- **Chat_Mode**: ConversationRuntime mode for plain conversation without tool calls.
- **Task_Mode**: ConversationRuntime mode where the AI may emit tool calls and receive tool results in a multi-step loop.
- **ToolCard**: A collapsible UI widget inside the chat body that displays a single tool call and its result.
- **StreamToken**: A single incremental text chunk emitted by a streaming AIProvider response.
- **HealthCheck**: A lightweight probe sent to an AIProvider to verify connectivity and model availability.
- **AgentPolicy**: The system prompt, app rules, tool usage policy, task routing policy, and safety rules that govern AI behaviour.

---

## Requirements

### Requirement 1: AI Settings Model

**User Story:** As a developer, I want AI configuration stored in AppSettings, so that provider credentials, model selection, and feature flags persist across sessions.

#### Acceptance Criteria

1. THE AISettings SHALL be a Pydantic BaseModel with fields: `provider` (str, default `"ollama"`), `ollama_base_url` (str, default `"http://localhost:11434"`), `openrouter_api_key` (Optional[str], default `None`), `chat_model` (str, default `""`), `task_model` (str, default `""`), `routing_mode` (str, default `"single_model"`), `cloud_fallback_enabled` (bool, default `False`), `openrouter_free_only` (bool, default `True`), `timeout_seconds` (int, default `60`), `stream_enabled` (bool, default `True`), `tools_enabled` (bool, default `False`), `max_history_messages` (int, default `50`), `max_tool_steps` (int, default `8`).
2. THE `routing_mode` field SHALL accept only the values `"single_model"` or `"dual_model"`; any other value SHALL cause a Pydantic validation error.
3. THE AppSettings SHALL contain an `ai` field of type AISettings with `default_factory=AISettings`.
4. WHEN AISettings is serialized to JSON, THE AISettings SHALL round-trip through `model_dump()` and `model_validate()` without data loss.
5. WHEN a field in AISettings is missing from a loaded JSON file, THE AISettings SHALL substitute the declared default value without raising an error.
6. WHEN a legacy settings file containing a `selected_model` key is loaded, THE AISettings SHALL map the value to `chat_model` and leave `task_model` as the default empty string, without raising an error.

> **Note:** `cloud_fallback_enabled` is reserved for a future release. In this version it is persisted as a setting only and has no enforced runtime behaviour — no fallback logic is triggered based on its value.

> **Note:** `selected_model` is deprecated. Use `chat_model` for plain conversation and `task_model` for tool-using task runs. Deep configuration fields (`ollama_base_url`, `openrouter_api_key`, `timeout_seconds`, `stream_enabled`, `tools_enabled`, `routing_mode`, `openrouter_free_only`, `cloud_fallback_enabled`, `max_tool_steps`) are managed in SettingsPage, not the AI Panel header.

---

### Requirement 2: AIProvider Abstract Interface

**User Story:** As a developer, I want a provider-agnostic interface, so that chat logic, tools, and the runtime never depend on a specific LLM backend.

#### Acceptance Criteria

1. THE AIProvider SHALL declare abstract methods: `chat(messages, model, **kwargs) -> AIResponse`, `stream_chat(messages, model, **kwargs) -> Iterator[StreamToken]`, `list_models() -> list[str]`, `health_check() -> ProviderHealth`.
2. THE AIProvider SHALL define a `provider_name` abstract property returning a str identifier.
3. WHEN a concrete provider class omits any abstract method, THE Python runtime SHALL raise `TypeError` on instantiation.
4. THE AIResponse SHALL be a dataclass with fields: `content` (str), `model` (str), `tool_calls` (list, default empty), `finish_reason` (str), `usage` (Optional[dict]).
5. THE ProviderHealth SHALL be a dataclass with fields: `ok` (bool), `message` (str), `latency_ms` (Optional[float]).
6. THE StreamToken SHALL be a dataclass with fields: `delta` (str), `finish_reason` (Optional[str]).

---

### Requirement 3: OllamaProvider Implementation

**User Story:** As a user, I want to use a locally running Ollama server as the AI backend, so that the AI works without internet access or API keys.

#### Acceptance Criteria

1. WHEN `chat()` is called, THE OllamaProvider SHALL send a POST request to `{base_url}/api/chat` with the message list and model name, and return an AIResponse.
2. WHEN `stream_chat()` is called, THE OllamaProvider SHALL send a streaming POST request to `{base_url}/api/chat` and yield one StreamToken per newline-delimited JSON chunk.
3. WHEN `list_models()` is called, THE OllamaProvider SHALL send a GET request to `{base_url}/api/tags` and return a list of model name strings.
4. WHEN `health_check()` is called, THE OllamaProvider SHALL send a GET request to `{base_url}/api/tags` and return a ProviderHealth with `ok=True` and measured latency if the request succeeds within `timeout_seconds`.
5. IF the HTTP request raises a connection error or times out, THEN THE OllamaProvider SHALL return a ProviderHealth with `ok=False` and a descriptive message, without raising an exception to the caller.
6. WHEN the Ollama server returns a non-200 HTTP status, THE OllamaProvider SHALL raise a `ValueError` with the status code and response body included in the message.

---

### Requirement 4: OpenRouterProvider Implementation

**User Story:** As a user, I want to optionally use OpenRouter as a cloud AI backend, so that I can access more powerful models when local resources are insufficient.

#### Acceptance Criteria

1. WHEN `chat()` is called, THE OpenRouterProvider SHALL send a POST request to `https://openrouter.ai/api/v1/chat/completions` with an `Authorization: Bearer {api_key}` header and return an AIResponse.
2. WHEN `stream_chat()` is called, THE OpenRouterProvider SHALL send a streaming POST request using Server-Sent Events format and yield one StreamToken per `data:` line.
3. WHEN `list_models()` is called, THE OpenRouterProvider SHALL send a GET request to `https://openrouter.ai/api/v1/models` and return a list of model id strings.
4. WHEN `health_check()` is called and `api_key` is None or empty, THE OpenRouterProvider SHALL return a ProviderHealth with `ok=False` and message `"API key not configured"` without making a network request.
5. IF the HTTP request raises a connection error or times out, THEN THE OpenRouterProvider SHALL return a ProviderHealth with `ok=False` and a descriptive message, without raising an exception to the caller.
6. THE OpenRouterProvider SHALL never log the raw API key value; it SHALL log only the first 8 characters followed by `"..."`.

---

### Requirement 5: Provider Factory

**User Story:** As a developer, I want a single factory function to instantiate the correct provider, so that the rest of the system never constructs providers directly.

#### Acceptance Criteria

1. THE ProviderFactory SHALL expose a `create(ai_settings: AISettings) -> AIProvider` static method.
2. WHEN `ai_settings.provider` is `"ollama"`, THE ProviderFactory SHALL return an OllamaProvider configured with `ai_settings.ollama_base_url` and `ai_settings.timeout_seconds`.
3. WHEN `ai_settings.provider` is `"openrouter"`, THE ProviderFactory SHALL return an OpenRouterProvider configured with `ai_settings.openrouter_api_key` and `ai_settings.timeout_seconds`.
4. IF `ai_settings.provider` is an unrecognised string, THEN THE ProviderFactory SHALL raise a `ValueError` naming the unsupported provider.

---

### Requirement 6: ConversationRuntime

**User Story:** As a developer, I want a runtime component that manages conversation state, so that the UI and tools never manipulate message history directly.

#### Acceptance Criteria

1. THE ConversationRuntime SHALL maintain an ordered list of messages, each with `role` (`"system"`, `"user"`, `"assistant"`, `"tool"`) and `content`.
2. WHEN a new user message is added, THE ConversationRuntime SHALL append it to history and enforce the `max_history_messages` limit by removing the oldest non-system messages first.
3. THE ConversationRuntime SHALL expose `send_message(text: str) -> None` for Chat_Mode and `run_task(text: str) -> None` for Task_Mode; both methods are asynchronous and deliver results via Qt signals.
4. WHEN `send_message` is called in Chat_Mode, THE ConversationRuntime SHALL dispatch the request to an AIWorker on a background QThread and emit `response_complete(AIResponse)` on the main thread when the provider responds.
5. WHEN `stream_send_message` is called, THE ConversationRuntime SHALL call `AIProvider.stream_chat()` and emit each StreamToken via a Qt signal `token_received(StreamToken)`. This is the streaming variant of `send_message`.
6. THE `TaskRunResult` SHALL be a dataclass with fields: `messages` (list[dict]), `tool_steps` (list[ToolResult]), `final_response` (Optional[str]), `cancelled` (bool), `error` (Optional[str]).
7. WHEN `run_task` completes, THE ConversationRuntime SHALL emit `task_complete(TaskRunResult)` on the main thread.
8. WHEN `run_task` is called in Task_Mode, THE ConversationRuntime SHALL select the provider model using `task_model` when `routing_mode` is `"dual_model"`, or `chat_model` when `routing_mode` is `"single_model"`.
9. THE ConversationRuntime SHALL expose `clear_history()` which removes all messages except the system prompt.
10. WHEN the system prompt is set, THE ConversationRuntime SHALL always place it as the first message with `role="system"`.
11. IF the provider raises an exception during `send_message`, THEN THE ConversationRuntime SHALL emit an `error_occurred(str)` signal and not append a partial assistant message to history.

---

### Requirement 7: ToolRegistry and ToolExecutor

**User Story:** As a developer, I want a registry of callable tools with schemas, so that the AI can discover and invoke app capabilities in a structured way.

#### Acceptance Criteria

1. THE ToolRegistry SHALL store tool definitions as a dict mapping tool name (str) to a ToolDefinition containing: `name`, `description`, `parameters_schema` (JSON Schema dict), and `callable`.
2. WHEN a tool is registered, THE ToolRegistry SHALL validate that `name` is a non-empty string and `callable` is callable, raising `ValueError` if either condition fails.
3. THE ToolRegistry SHALL expose `get_schema_list() -> list[dict]` returning all tool definitions in the format expected by the AIProvider's tool-calling API.
4. THE ToolExecutor SHALL expose `execute(tool_name: str, arguments: dict) -> ToolResult`.
5. WHEN `execute` is called, THE ToolExecutor SHALL look up the tool in ToolRegistry, call its callable with the provided arguments, and return a ToolResult with `tool_name` (str), `output` (Any — supports `dict | list | str`), `display_text` (str, default `""`), and `error` (Optional[str]).
6. IF the tool callable raises an exception, THEN THE ToolExecutor SHALL catch it, log the error, and return a ToolResult with `error` set to the exception message, `output` set to `""`, and `display_text` set to `""`.
7. IF `tool_name` is not found in ToolRegistry, THEN THE ToolExecutor SHALL return a ToolResult with `error="Tool not found: {tool_name}"`.

---

### Requirement 8: AI Dock Panel (UI Shell)

**User Story:** As a user, I want a dockable AI panel accessible from any tab, so that I can interact with the AI without leaving my current workflow.

#### Acceptance Criteria

1. THE AI_Panel SHALL be implemented as a QDockWidget added to MainWindow with `Qt.RightDockWidgetArea` as the default area.
2. THE AI_Panel SHALL be toggleable via a toolbar button or menu action in MainWindow, showing or hiding the dock without destroying its state.
3. THE AI_Panel SHALL support floating (detached) mode via standard QDockWidget behaviour.
4. THE AI_Panel header SHALL contain: current provider name, a quick-access provider selector (QComboBox), a quick-access model selector reflecting `chat_model` when `routing_mode` is `"single_model"` or both `chat_model` and `task_model` selectors when `routing_mode` is `"dual_model"`, a connection status indicator, and a tools on/off toggle button.

> **Note:** Deep configuration (`ollama_base_url`, `openrouter_api_key`, `timeout_seconds`, `stream_enabled`, `tools_enabled`, `routing_mode`, `openrouter_free_only`, `cloud_fallback_enabled`) lives in SettingsPage, not the panel header.
5. THE AI_Panel body SHALL contain a scrollable message list area where user and assistant messages are rendered.
6. THE AI_Panel input area SHALL contain a multi-line text input, a Send button, and a Stop button.
7. WHEN the Stop button is clicked during a streaming response, THE AI_Panel SHALL signal the ConversationRuntime to cancel the in-progress stream.
8. WHEN the AI_Panel is first shown and no model is selected, THE AI_Panel SHALL display a prompt instructing the user to select a model in settings.

---

### Requirement 9: Message Rendering

**User Story:** As a user, I want messages displayed clearly with distinct styles for user, assistant, and tool output, so that I can follow the conversation at a glance.

#### Acceptance Criteria

1. THE AI_Panel SHALL render user messages with a visually distinct background or alignment (right-aligned or highlighted).
2. THE AI_Panel SHALL render assistant messages with a different background or alignment (left-aligned).
3. WHEN an assistant message contains a fenced code block (triple backtick), THE AI_Panel SHALL render it in a monospace font with a contrasting background.
4. WHEN a tool call is present in an assistant message, THE AI_Panel SHALL render a collapsible ToolCard showing the tool name, input arguments, and result.
5. WHEN a streaming response is in progress, THE AI_Panel SHALL update the assistant message bubble incrementally as StreamTokens arrive.
6. THE AI_Panel SHALL auto-scroll to the latest message when a new message is appended, unless the user has manually scrolled up.

---

### Requirement 10: Model and Provider Selection

**User Story:** As a user, I want to select my AI provider and model from within the app, so that I can switch backends without editing config files.

#### Acceptance Criteria

1. THE AI_Panel header SHALL contain a provider selector (QComboBox) listing `"Ollama"` and `"OpenRouter"`.
2. WHEN a provider is selected, THE AI_Panel SHALL trigger a `health_check()` on the new provider and update the status indicator.
3. WHEN `routing_mode` is `"single_model"`, THE AI_Panel header SHALL contain a single model selector (QComboBox) that reads and writes `chat_model` in AISettings.
4. WHEN `routing_mode` is `"dual_model"`, THE AI_Panel header SHALL contain two model selectors: one labelled "Chat" bound to `chat_model` and one labelled "Task" bound to `task_model`.
5. WHEN a model selector is opened, THE AI_Panel SHALL call `list_models()` asynchronously and populate the list without blocking the UI thread.
6. WHEN a model is selected, THE AI_Panel SHALL persist the selection to AISettings via SettingsState.
7. WHEN a provider is selected in the AI_Panel header, THE selection SHALL be persisted to `AISettings.provider` via SettingsState.
8. IF `list_models()` returns an empty list or raises an error, THEN THE AI_Panel SHALL display a `"No models available"` placeholder and log the error.

---

### Requirement 11: Connection Health Check

**User Story:** As a user, I want to see the provider connection status at a glance, so that I know whether the AI is ready before sending a message.

#### Acceptance Criteria

1. THE AI_Panel SHALL display a status indicator with at least three states: `connected` (green), `disconnected` (red), and `checking` (yellow/spinner).
2. WHEN the AI_Panel is first shown, THE AI_Panel SHALL automatically run a health check on the configured provider.
3. WHEN AISettings are saved, THE AI_Panel SHALL re-run the health check on the updated provider configuration.
4. THE AI_Panel SHALL expose a manual "Test Connection" action that triggers a health check and updates the status indicator.
5. WHEN a health check completes, THE AI_Panel SHALL update the status indicator and display the latency in milliseconds if `ok=True`.

---

### Requirement 12: Streaming and Cancellation

**User Story:** As a user, I want responses to stream in token by token and be cancellable, so that I get fast feedback and can stop long responses.

#### Acceptance Criteria

1. WHEN `stream_enabled` is `True` in AISettings, THE ConversationRuntime SHALL use `stream_chat()` instead of `chat()` for all user messages.
2. WHEN streaming is active, THE AI_Panel SHALL display a Stop button in an enabled state.
3. WHEN the Stop button is clicked, THE ConversationRuntime SHALL call `cancel_current_request()`.
4. THE ConversationRuntime SHALL expose a `cancel_current_request()` method that sets the cancellation flag AND closes or aborts the underlying HTTP connection or worker thread, not just abandons the iterator.
5. WHEN `cancel_current_request()` is called, THE ConversationRuntime SHALL request cancellation immediately, close the underlying HTTP connection or session, and return the UI to idle state promptly; IF worker thread termination exceeds 2 seconds, THE runtime SHALL log a warning and detach the request safely without blocking the main thread.
6. THE OllamaProvider and OpenRouterProvider SHALL support request-level cancellation by closing the HTTP session or connection when cancellation is requested.
7. WHEN streaming is cancelled, THE ConversationRuntime SHALL append the partial assistant message (tokens received so far) to history with `finish_reason="cancelled"`.
8. WHEN streaming completes normally, THE AI_Panel SHALL disable the Stop button and re-enable the Send button.

---

### Requirement 13: Event Journal

**User Story:** As a developer, I want an in-memory event journal that records application events, so that the AI can understand recent user activity without reading the full log file.

#### Acceptance Criteria

1. THE EventJournal SHALL store events as an ordered list of EventRecord dataclasses with fields: `timestamp` (datetime), `event_type` (str), `source` (str), `payload` (dict).
2. THE EventJournal SHALL enforce a maximum capacity of 200 events, discarding the oldest event when the limit is exceeded.
3. THE EventJournal SHALL expose `record(event_type, source, payload)` to append a new event.
4. THE EventJournal SHALL expose `get_recent(n: int = 50) -> list[EventRecord]` returning the n most recent events in chronological order.
5. WHEN a backtest run starts, THE EventJournal SHALL record an event with `event_type="backtest_started"` and payload containing strategy name and timeframe.
6. WHEN a backtest run finishes, THE EventJournal SHALL record an event with `event_type="backtest_finished"` and payload containing exit code and result summary.
7. WHEN settings are saved, THE EventJournal SHALL record an event with `event_type="settings_saved"`.

---

### Requirement 14: App Context Providers

**User Story:** As a developer, I want structured context providers that package app state for the AI, so that the AI receives relevant, up-to-date information without accessing UI objects directly.

#### Acceptance Criteria

1. THE AppContextProvider SHALL declare an abstract method `get_context() -> dict` returning a JSON-serialisable dict.
2. THE AppStateContextProvider SHALL implement AppContextProvider and return: current provider name, selected model, tools enabled flag, and active tab name.
3. THE BacktestContextProvider SHALL implement AppContextProvider and return: last strategy name, last timeframe, last timerange, last exit code, and a summary of the last backtest result if available.
4. THE StrategyContextProvider SHALL implement AppContextProvider and return: last open strategy name and file path.
5. WHEN `get_context()` is called on any provider, THE provider SHALL return a dict within 100ms without performing any blocking I/O.
6. THE ConversationRuntime SHALL accept a list of AppContextProvider instances and include their combined output in the system prompt when building the message list.

---

### Requirement 15: Basic App Tools (Phase 3)

**User Story:** As a user, I want the AI to be able to query basic app state and recent logs, so that it can give contextually relevant answers about what is happening in the app.

#### Acceptance Criteria

1. THE ToolRegistry SHALL include a `get_app_status` tool that returns: provider name, model name, tools enabled, and active tab.
2. THE ToolRegistry SHALL include a `read_recent_logs` tool that accepts an optional `lines` parameter (default 50, max 200) and returns the last N lines from the application log file; THE tool SHALL resolve the log file path from the application's configured log directory via the logger service or AppSettings, not a hardcoded path.
3. THE ToolRegistry SHALL include a `get_last_error` tool that returns the most recent ERROR-level log entry from the in-memory EventJournal or log file.
4. THE ToolRegistry SHALL include a `list_recent_events` tool that accepts an optional `n` parameter (default 20) and returns the last N EventRecord entries from the EventJournal as a JSON array.
5. WHEN any app tool is called, THE ToolExecutor SHALL complete execution within 2 seconds and return a ToolResult.
6. WHEN `read_recent_logs` is called with `lines` greater than 200, THE tool SHALL clamp the value to 200 and include a note in the output.

---

### Requirement 16: Backtest Tools (Phase 5)

**User Story:** As a user, I want the AI to be able to read and compare backtest results, so that it can help me understand performance and suggest improvements.

#### Acceptance Criteria

1. THE ToolRegistry SHALL include a `get_latest_backtest_result` tool that returns the most recent BacktestResults summary for the currently selected strategy.
2. THE ToolRegistry SHALL include a `load_run_history` tool that accepts a `strategy` parameter and returns a list of run summaries (date, profit factor, win rate, total trades) for that strategy.
3. THE ToolRegistry SHALL include a `compare_runs` tool that accepts two run IDs and returns a side-by-side comparison of their key metrics.
4. WHEN a backtest tool is called and `user_data_path` is not configured in AppSettings, THE tool SHALL return a ToolResult with `error="user_data_path not configured"`.
5. WHEN a backtest tool is called and no results exist for the requested strategy, THE tool SHALL return a ToolResult with `output="No results found for strategy: {strategy}"` and `error=None`.

---

### Requirement 17: Strategy Tools (Phase 5)

**User Story:** As a user, I want the AI to be able to read strategy code and parameters, so that it can explain, critique, and suggest changes to my strategies.

#### Acceptance Criteria

1. THE ToolRegistry SHALL include a `list_strategies` tool that returns the names of all `.py` files in `{user_data_path}/strategies/`.
2. THE ToolRegistry SHALL include a `read_strategy_code` tool that accepts a `strategy_name` parameter and returns the full source code of the matching strategy file.
3. THE ToolRegistry SHALL include a `read_strategy_params` tool that accepts a `strategy_name` parameter and returns the buy/sell parameters and ROI table from the strategy's JSON params file if it exists.
4. WHEN `read_strategy_code` is called with a strategy name that does not exist, THE tool SHALL return a ToolResult with `error="Strategy file not found: {strategy_name}"`.
5. WHEN `read_strategy_code` is called and the strategy file exceeds 50 KB, THE tool SHALL return the first 50 KB of content and append a truncation notice.

---

### Requirement 18: Agent Policy and Safety Rules

**User Story:** As a developer, I want a configurable agent policy that governs AI behaviour, so that the AI stays within safe, predictable boundaries.

#### Acceptance Criteria

1. THE AgentPolicy SHALL be a dataclass with fields: `system_prompt` (str), `tool_usage_policy` (str), `safety_rules` (list[str]).
2. THE ConversationRuntime SHALL accept an AgentPolicy and prepend its `system_prompt` as the first system message in every conversation.
3. THE AgentPolicy default `system_prompt` SHALL instruct the AI that it is a read-and-advise assistant, that it must not claim to execute trades or write files without user confirmation, and that it must use tools only when necessary.
4. WHEN `tools_enabled` is `False` in AISettings, THE ConversationRuntime SHALL not inject any tool schemas into the message list regardless of AgentPolicy settings.
5. THE AgentPolicy SHALL include a safety rule that prevents the AI from returning raw API keys or credentials in its responses; THE ConversationRuntime SHALL strip any string matching a known secret pattern before emitting a token to the UI.

---

### Requirement 19: Asynchronous Execution (Non-blocking UI)

**User Story:** As a user, I want the UI to remain responsive while the AI is processing, so that I can continue using the app during long AI operations.

#### Acceptance Criteria

1. WHEN `send_message` or `stream_send_message` is called, THE ConversationRuntime SHALL execute the provider call in a QThread or via a worker object moved to a QThread, never on the Qt main thread.
2. WHEN a provider call completes, THE ConversationRuntime SHALL emit results via Qt signals to ensure UI updates happen on the main thread.
3. WHEN a health check is triggered, THE AI_Panel SHALL run it in a background thread and update the status indicator via a Qt signal upon completion.
4. WHEN `list_models()` is called to populate the model selector, THE AI_Panel SHALL run it in a background thread and populate the QComboBox via a Qt signal upon completion.
5. IF a background thread raises an unhandled exception, THEN THE ConversationRuntime SHALL emit `error_occurred(str)` with the exception message and log the full traceback.

---

### Requirement 20: Settings Persistence Round-Trip

**User Story:** As a developer, I want AI settings to survive serialization and deserialization, so that user preferences are never silently lost.

#### Acceptance Criteria

1. FOR ALL valid AISettings objects, serializing with `model_dump(mode="json")` then deserializing with `AISettings.model_validate()` SHALL produce an object equal to the original (round-trip property).
2. WHEN AppSettings containing AISettings is saved to `~/.freqtrade_gui/settings.json` and reloaded, THE loaded AISettings SHALL equal the saved AISettings field-by-field, including `chat_model`, `task_model`, and `routing_mode`.
3. WHEN a legacy settings file without an `ai` key is loaded, THE AppSettings SHALL populate the `ai` field with default AISettings values without raising an error.

---

### Requirement 21: AI Settings UI

**User Story:** As a user, I want to configure AI settings from the Settings page, so that I can set up providers, models, and routing without editing config files.

#### Acceptance Criteria

1. THE SettingsPage SHALL include an "AI" section with editable fields for: `provider`, `ollama_base_url`, `openrouter_api_key`, `timeout_seconds`, `stream_enabled`, `tools_enabled`, `chat_model`, `task_model`, `routing_mode`, `openrouter_free_only`, `cloud_fallback_enabled`.
2. WHEN the AI section is saved, THE SettingsPage SHALL persist changes to AISettings via SettingsState and emit `settings_saved`.
3. THE `openrouter_api_key` field SHALL be rendered as a password field (masked input, `QLineEdit.Password` echo mode).
4. THE `routing_mode` field SHALL be rendered as a QComboBox dropdown with options `"single_model"` and `"dual_model"`.

---

### Requirement 22: OpenRouter Free Model Filtering

**User Story:** As a user, I want to filter OpenRouter models to free-only options, so that I don't accidentally use paid models.

#### Acceptance Criteria

1. WHEN `openrouter_free_only` is `True`, THE OpenRouterProvider `list_models()` SHALL return only models whose prompt and completion pricing are both zero according to the OpenRouter models API response.
2. WHEN `openrouter_free_only` is `False`, THE OpenRouterProvider `list_models()` SHALL return all available text-capable models.
3. THE OpenRouterProvider SHALL filter models to text-capable types only, excluding image-only and audio-only models.

---

### Requirement 23: Tool Loop Limits

**User Story:** As a developer, I want the task mode tool loop to have a maximum step limit, so that runaway tool chains cannot hang the application.

#### Acceptance Criteria

1. THE AISettings SHALL include a `max_tool_steps` field (int, default `8`).
2. WHEN `run_task()` is executing and the number of tool call iterations reaches `max_tool_steps`, THE ConversationRuntime SHALL stop the loop, set `TaskRunResult.cancelled = False` and `TaskRunResult.error = "Max tool steps reached"`, and return the partial result.
3. WHEN the tool step limit is reached, THE ConversationRuntime SHALL log a warning via the module-level logger.

---

### Requirement 24: Model Capability Awareness

**User Story:** As a developer, I want the runtime to adapt its behaviour based on the selected model's capability level, so that tool tasks degrade gracefully on weaker models.

#### Acceptance Criteria

1. THE ConversationRuntime SHALL classify the active model as Level_A (plain text), Level_B (structured JSON), or Level_C (native tool calling) based on a configurable capability registry or provider metadata.
2. WHEN `tools_enabled` is `True` and the active model is Level_A, THE ConversationRuntime SHALL emit a warning to the UI via the `error_occurred` signal and disable tool injection for that session.
3. WHEN the active model is Level_B, THE ConversationRuntime SHALL use prompt-based action extraction instead of native tool schemas.
4. WHEN the active model is Level_C, THE ConversationRuntime SHALL inject tool schemas directly into the message list using the provider's native tool-calling format.
