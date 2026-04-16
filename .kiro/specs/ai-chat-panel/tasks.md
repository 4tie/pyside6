# Implementation Plan: AI Chat Panel

## Overview

Implement the AI Chat Panel as a dockable QDockWidget embedded in the Freqtrade GUI desktop app. Delivery is split into five incremental phases: Foundation → Providers & Runtime → Tools → Context & Journal → Backtest & Strategy Tools. Each phase builds on the previous and ends with all components wired together and tested.

All code follows project conventions: `get_logger("section.module")`, `@dataclass` for DTOs, `pydantic.BaseModel` for settings, services never import UI.

## Tasks

- [ ] 1. Phase 1 — Foundation
  - [~] 1.1 Extend `AppSettings` with `AISettings` Pydantic model
    - Add `AISettings` class to `app/core/models/settings_models.py` with all fields from the design: `provider`, `ollama_base_url`, `openrouter_api_key`, `chat_model`, `task_model`, `routing_mode`, `cloud_fallback_enabled`, `openrouter_free_only`, `timeout_seconds`, `stream_enabled`, `tools_enabled`, `max_history_messages`, `max_tool_steps`
    - Add `@field_validator("routing_mode")` that rejects any value other than `"single_model"` or `"dual_model"`
    - Add `model_validator(mode="before")` to map legacy `selected_model` key to `chat_model`
    - Add `ai: AISettings = Field(default_factory=AISettings)` to `AppSettings`
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6, 20.1, 20.3_

  - [~] 1.2 Write property test: AISettings serialization round-trip
    - **Property 1: AISettings serialization round-trip**
    - Use `st.builds(AISettings, ...)` with random valid field values; assert `model_validate(model_dump(mode="json"))` equals original
    - **Validates: Requirements 1.4, 20.1**

  - [~] 1.3 Write property test: routing_mode validation rejects invalid values
    - **Property 2: routing_mode validation rejects invalid values**
    - Use `st.text()` filtered to exclude `"single_model"` and `"dual_model"`; assert `ValidationError` is raised; assert valid values are always accepted
    - **Validates: Requirements 1.2**

  - [~] 1.4 Write property test: AISettings partial JSON loading uses defaults
    - **Property 3: AISettings partial JSON loading uses defaults**
    - Use `st.fixed_dictionaries` with a random non-empty subset of AISettings fields; assert `model_validate()` succeeds and omitted fields equal declared defaults
    - **Validates: Requirements 1.5**

  - [~] 1.5 Write unit test: legacy selected_model migration
    - Load a dict containing `selected_model` but no `chat_model`; assert `chat_model` equals the legacy value and `task_model` equals `""`
    - _Requirements: 1.6_

  - [~] 1.6 Add `ai_settings_changed` signal to `SettingsState`
    - Add `ai_settings_changed = Signal(object)` to `app/app_state/settings_state.py`
    - Emit it from `save_settings()` when the `ai` field has changed
    - _Requirements: 11.3_

  - [~] 1.7 Create `AIState(QObject)` with all signals
    - Create `app/app_state/ai_state.py` with `AIState(QObject)` declaring signals: `health_changed`, `models_refreshed`, `ai_settings_changed`, `token_received`, `response_complete`, `error_occurred`, `task_complete`
    - Add module-level `_log = get_logger("ui.ai_state")`
    - _Requirements: 8.1, 8.2, 12.2_

  - [~] 1.8 Create `AIChatDock` placeholder QDockWidget
    - Create `app/ui/widgets/ai_chat_dock.py` with `AIChatDock(QDockWidget)`
    - Dock area: `Qt.RightDockWidgetArea`; toggleable (show/hide without destroying state)
    - Body: placeholder `QLabel("AI Chat — coming soon")`
    - Add module-level `_log = get_logger("ui.ai_chat_dock")`
    - _Requirements: 8.1, 8.2, 8.3_

  - [~] 1.9 Wire `AIChatDock` into `MainWindow`
    - Instantiate `AIChatDock` in `MainWindow.__init__` and call `addDockWidget(Qt.RightDockWidgetArea, self.ai_chat_dock)`
    - Add a toolbar button or `View` menu action that calls `self.ai_chat_dock.toggleViewAction()`
    - _Requirements: 8.1, 8.2_

  - [~] 1.10 Add AI section to `SettingsPage`
    - Add a `QGroupBox("AI")` section to `app/ui/pages/settings_page.py` with fields for all `AISettings` attributes
    - Render `openrouter_api_key` as `QLineEdit.Password` echo mode
    - Render `routing_mode` as a `QComboBox` with options `"single_model"` and `"dual_model"`
    - Load from and save to `AISettings` via `SettingsState`
    - _Requirements: 21.1, 21.2, 21.3, 21.4_

  - [~] 1.11 Phase 1 checkpoint — ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

- [ ] 2. Phase 2 — Providers and Runtime
  - [~] 2.1 Create `provider_base.py` with `AIProvider` ABC and DTOs
    - Create `app/core/ai/providers/provider_base.py`
    - Define `@dataclass AIResponse`, `@dataclass ProviderHealth`, `@dataclass StreamToken` with all fields from the design
    - Define `AIProvider(ABC)` with abstract methods: `provider_name` property, `chat`, `stream_chat`, `list_models`, `health_check`, `cancel_current_request`; default `get_model_capability` returning `"Level_B"`
    - Add module-level `_log = get_logger("services.ai_provider")`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [~] 2.2 Create `OllamaProvider`
    - Create `app/core/ai/providers/ollama_provider.py`
    - Use `requests.Session` owned per instance; `cancel_current_request()` closes the session and resets it so the next call creates a fresh one
    - Implement `chat()` → POST `{base_url}/api/chat`; `stream_chat()` → streaming POST with newline-delimited JSON chunks, checking `cancel_flag` between each; `list_models()` → GET `{base_url}/api/tags`; `health_check()` → GET `/api/tags` with latency measurement
    - Connection errors/timeouts return `ProviderHealth(ok=False, ...)`; non-200 raises `ValueError`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 12.6_

  - [~] 2.3 Write unit tests for `OllamaProvider`
    - Mock HTTP responses with `unittest.mock`; test `chat()` 200 success, `health_check()` success and failure, non-200 raises `ValueError`, `cancel_current_request()` closes session
    - _Requirements: 3.1, 3.4, 3.5, 3.6_

  - [~] 2.4 Create `OpenRouterProvider`
    - Create `app/core/ai/providers/openrouter_provider.py`
    - Use `requests.Session` with `Authorization: Bearer {api_key}` header; `cancel_current_request()` closes the session
    - Implement `chat()` → POST `https://openrouter.ai/api/v1/chat/completions`; `stream_chat()` → SSE `data:` lines with `cancel_flag` check; `list_models()` → GET `/api/v1/models` filtered by `openrouter_free_only` and text-capable types; `health_check()` returns `ProviderHealth(ok=False, message="API key not configured")` if key absent
    - Log API key as `key[:8] + "..."` only
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 12.6, 22.1, 22.2, 22.3_

  - [~] 2.5 Write unit tests for `OpenRouterProvider`
    - Test `health_check()` with no API key, mock 200 `chat()`, API key never logged in full, `cancel_current_request()` closes session
    - _Requirements: 4.4, 4.6_

  - [~] 2.6 Create `ProviderFactory`
    - Create `app/core/ai/providers/provider_factory.py` with `ProviderFactory.create(ai_settings) -> AIProvider`
    - Return `OllamaProvider` for `"ollama"`, `OpenRouterProvider` for `"openrouter"`, raise `ValueError` for unknown providers
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [~] 2.7 Write property test: ProviderFactory raises ValueError for unknown providers
    - **Property 4: ProviderFactory raises ValueError for unknown providers**
    - Use `st.text()` filtered to exclude `"ollama"` and `"openrouter"`; assert `ValueError` raised; assert valid strings produce correct types
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

  - [~] 2.8 Create `AgentPolicy` dataclass
    - Create `app/core/ai/runtime/agent_policy.py` with `@dataclass AgentPolicy` fields: `system_prompt`, `tool_usage_policy`, `safety_rules: list[str]`
    - Provide a `default_policy()` factory with the read-and-advise system prompt and a safety rule preventing raw credential output
    - _Requirements: 18.1, 18.2, 18.3, 18.5_

  - [~] 2.9 Create `ConversationRuntime` and `AIWorker`
    - Create `app/core/ai/runtime/conversation_runtime.py`
    - Define `@dataclass TaskRunResult` with fields: `messages`, `tool_steps`, `final_response`, `cancelled`, `error`
    - Implement `ConversationRuntime(QObject)` with signals `token_received`, `response_complete`, `error_occurred`, `task_complete`; methods `send_message`, `run_task`, `cancel_current_request`, `clear_history`, `set_system_prompt`
    - Implement `AIWorker(QObject)` with `run_chat` and `run_task_loop`; per-request QThread lifecycle (new worker + thread per request, cleaned up on completion)
    - History management: enforce `max_history_messages` by removing oldest non-system messages; system prompt always first
    - Model routing: `send_message` always uses `chat_model`; `run_task` uses `task_model` when `routing_mode == "dual_model"`, else `chat_model`
    - Tool injection: only when `tools_enabled=True` and model is Level_B or Level_C; emit `error_occurred` warning for Level_A
    - Cancellation: set `cancel_flag` AND call `provider.cancel_current_request()`; if worker thread does not finish within 2s, log warning and detach
    - Secret scrubbing: strip known secret patterns (e.g. `sk-...`, bearer tokens) before emitting tokens
    - Add module-level `_log = get_logger("services.conversation_runtime")`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11, 12.1, 12.3, 12.4, 12.5, 12.7, 18.2, 18.4, 18.5, 19.1, 19.2, 19.5, 23.2, 23.3, 24.1, 24.2, 24.3, 24.4_

  - [~] 2.10 Write property test: ConversationRuntime model routing is correct
    - **Property 5: ConversationRuntime model routing is correct for all routing modes**
    - Generate all combinations of `routing_mode` and call type; assert correct model is passed to provider
    - **Validates: Requirements 6.3, 6.4, 6.8**

  - [~] 2.11 Write property test: history trimming preserves system message
    - **Property 6: History trimming preserves system message and respects limit**
    - Use `st.lists(st.fixed_dictionaries(...))` to generate message sequences exceeding `max_history_messages`; assert system message always first, total count never exceeds limit, most recent messages retained
    - **Validates: Requirements 6.2**

  - [~] 2.12 Write property test: clear_history leaves only the system message
    - **Property 7: clear_history leaves only the system message**
    - For any history state, call `clear_history()`; assert exactly one message with `role="system"` remains
    - **Validates: Requirements 6.9**

  - [~] 2.13 Write unit tests for `AIWorker` signals
    - Use `QSignalSpy` to verify `token_received`, `response_complete`, and `error_occurred` signals are emitted on the main thread with correct payloads
    - _Requirements: 19.1, 19.2_

  - [~] 2.14 Wire `ConversationRuntime` into `AIChatDock`
    - Replace the placeholder body in `AIChatDock` with the full UI shell:
      - Header: provider `QComboBox`, model selector(s) (single or dual based on `routing_mode`), connection status indicator, tools toggle button; layout switches at 280px dock width via `resizeEvent`
      - Body: `QScrollArea` with `AIMessageWidget` instances; auto-scroll unless user has scrolled up
      - Input area: `QPlainTextEdit`, Send button, Stop button (enabled only during streaming)
      - No-model state: `QLabel("Select a model in Settings → AI to get started.")` when `chat_model` is empty
    - Create `app/ui/widgets/ai_message_widget.py` with `UserMessageWidget` (right-aligned) and `AssistantMessageWidget` (left-aligned, incremental token appending, fenced code block rendering)
    - Connect Send → `runtime.send_message`, Stop → `runtime.cancel_current_request`
    - Connect `runtime.token_received` → incremental message update; `runtime.response_complete` → finalize message; `runtime.error_occurred` → display error
    - Health check on first show and on `ai_settings_changed`; model list populated asynchronously
    - _Requirements: 8.4, 8.5, 8.6, 8.7, 8.8, 9.1, 9.2, 9.3, 9.5, 9.6, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 11.1, 11.2, 11.3, 11.4, 11.5, 12.2, 12.8, 19.3, 19.4_

  - [~] 2.15 Phase 2 checkpoint — ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Phase 3 — Tools
  - [~] 3.1 Create `ToolRegistry` and `ToolDefinition`
    - Create `app/core/ai/tools/tool_registry.py`
    - Define `@dataclass ToolDefinition` with fields: `name`, `description`, `parameters_schema`, `callable`
    - Implement `ToolRegistry` with `register(definition)` (validates non-empty name and callable, raises `ValueError` otherwise), `get_schema_list() -> list[dict]`, `get(name) -> Optional[ToolDefinition]`
    - Add module-level `_log = get_logger("services.tool_registry")`
    - _Requirements: 7.1, 7.2, 7.3_

  - [~] 3.2 Write property test: ToolRegistry registration validates name and callable
    - **Property 8: ToolRegistry registration validates name and callable**
    - For any `ToolDefinition` with empty name or non-callable; assert `ValueError` raised; for valid definitions assert registration succeeds
    - **Validates: Requirements 7.2**

  - [~] 3.3 Create `ToolExecutor` and `ToolResult`
    - Create `app/core/ai/tools/tool_executor.py`
    - Define `@dataclass ToolResult` with fields: `tool_name`, `output`, `display_text`, `error`
    - Implement `ToolExecutor.execute(tool_name, arguments) -> ToolResult`; catch all exceptions and return `ToolResult` with `error` set; return `error="Tool not found: {tool_name}"` for missing tools
    - Add module-level `_log = get_logger("services.tool_executor")`
    - _Requirements: 7.4, 7.5, 7.6, 7.7_

  - [~] 3.4 Write property test: ToolExecutor returns ToolResult for any input
    - **Property 9: ToolExecutor returns ToolResult for any input**
    - For any tool name (registered or not) and any arguments dict, assert `execute()` never raises and always returns a `ToolResult`; assert correct `error` values for missing and failing tools
    - **Validates: Requirements 7.4, 7.5, 7.6, 7.7**

  - [~] 3.5 Create `LogPathResolver`
    - Create `app/core/ai/tools/log_path_resolver.py` with `LogPathResolver.get_log_path(log_name: str) -> Path`
    - Resolve log directory from `AppSettings` or the logger service's public API — never from a private attribute or hardcoded path
    - _Requirements: 15.2_

  - [~] 3.6 Implement Phase 3 app tools
    - Create `app/core/ai/tools/app_tools.py` with functions: `get_app_status`, `read_recent_logs`, `get_last_error`, `list_recent_events`
    - `read_recent_logs`: accepts `lines: int = 50` (max 200), clamps >200 with note in output, resolves path via `LogPathResolver`
    - `list_recent_events`: accepts `n: int = 20`, returns last N `EventRecord` entries as JSON array
    - All tools complete within 2 seconds
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_

  - [~] 3.7 Write unit tests for Phase 3 app tools
    - Test `get_app_status` returns expected keys; `read_recent_logs` clamps lines > 200 and includes note; `list_recent_events` returns correct JSON array
    - _Requirements: 15.1, 15.2, 15.4, 15.6_

  - [~] 3.8 Create `ToolCard` widget
    - Create `app/ui/widgets/tool_call_card.py` with `ToolCard(QWidget)`
    - Collapsible widget: tool name always visible in header; input arguments and result output in collapsible body toggled by a `QToolButton(setCheckable(True))`
    - _Requirements: 9.4_

  - [~] 3.9 Write UI test for `ToolCard`
    - Test expand/collapse toggle changes body visibility
    - _Requirements: 9.4_

  - [~] 3.10 Wire tools into `ConversationRuntime`
    - Accept `tool_registry: ToolRegistry` in `ConversationRuntime.__init__`
    - Inject tool schemas into message list when `tools_enabled=True` and model is Level_B or Level_C
    - Route tool calls through `ToolExecutor` in `run_task_loop`; enforce `max_tool_steps` limit; set `TaskRunResult.error = "Max tool steps reached"` and log warning when limit hit
    - Render `ToolCard` in `AIChatDock` for each tool step in the response
    - _Requirements: 7.3, 15.5, 18.4, 23.1, 23.2, 23.3, 24.3, 24.4_

  - [~] 3.11 Phase 3 checkpoint — ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Phase 4 — Context and Journal
  - [~] 4.1 Create `EventJournal` and `EventRecord`
    - Create `app/core/ai/journal/event_journal.py`
    - Define `@dataclass EventRecord` with fields: `timestamp: datetime`, `event_type: str`, `source: str`, `payload: dict`
    - Implement `EventJournal` with `MAX_CAPACITY = 200`; `record(event_type, source, payload)` appends and discards oldest when over capacity; `get_recent(n=50)` returns last N in chronological order
    - Add module-level `_log = get_logger("services.event_journal")`
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [~] 4.2 Write property test: EventJournal never exceeds capacity
    - **Property 10: EventJournal never exceeds capacity**
    - Record any number of events; assert journal never contains more than 200 entries and retained entries are the most recently recorded
    - **Validates: Requirements 13.2**

  - [~] 4.3 Write property test: EventJournal get_recent returns chronological order
    - **Property 11: EventJournal get_recent returns chronological order**
    - For any journal state and any `n`, assert `get_recent(n)` returns at most `n` events in ascending timestamp order
    - **Validates: Requirements 13.4**

  - [~] 4.4 Create `AppContextProvider` ABC
    - Create `app/core/ai/context/context_provider.py` with `AppContextProvider(ABC)` declaring abstract method `get_context() -> dict`
    - _Requirements: 14.1_

  - [~] 4.5 Implement context provider classes
    - Create `app/core/ai/context/app_state_context.py` with `AppStateContextProvider` returning: provider name, selected model, tools enabled, active tab name
    - Create `app/core/ai/context/backtest_context.py` with `BacktestContextProvider` returning: last strategy, timeframe, timerange, exit code, last result summary
    - Create `app/core/ai/context/strategy_context.py` with `StrategyContextProvider` returning: last open strategy name and file path
    - All `get_context()` implementations return within 100ms with no blocking I/O
    - _Requirements: 14.2, 14.3, 14.4, 14.5_

  - [~] 4.6 Write unit tests for context providers
    - Test each provider's `get_context()` returns a dict with expected keys within 100ms
    - _Requirements: 14.2, 14.3, 14.4, 14.5_

  - [~] 4.7 Create EventJournal adapters
    - Create `app/core/ai/journal/backtest_adapter.py`: register callbacks on `BacktestService` to record `backtest_started` (strategy name, timeframe) and `backtest_finished` (exit code, result summary) events
    - Create `app/core/ai/journal/settings_adapter.py`: connect `SettingsState.settings_saved` signal to record `settings_saved` event
    - Adapters import from services — services never import from journal
    - _Requirements: 13.5, 13.6, 13.7_

  - [~] 4.8 Write integration tests for EventJournal adapters
    - Test that `backtest_started`, `backtest_finished`, and `settings_saved` events are recorded in the journal when the corresponding service actions occur
    - _Requirements: 13.5, 13.6, 13.7_

  - [~] 4.9 Wire context providers into `ConversationRuntime`
    - Accept `context_providers: list[AppContextProvider]` in `ConversationRuntime.__init__`
    - Include combined `get_context()` output in the system prompt when building the message list
    - _Requirements: 14.6_

  - [~] 4.10 Phase 4 checkpoint — ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Phase 5 — Backtest and Strategy Tools
  - [~] 5.1 Implement backtest tools
    - Create `app/core/ai/tools/backtest_tools.py` with functions: `get_latest_backtest_result`, `load_run_history`, `compare_runs`
    - `get_latest_backtest_result`: returns most recent `BacktestResults` summary for current strategy; returns `ToolResult(error="user_data_path not configured")` if path absent
    - `load_run_history(strategy)`: returns list of run summaries (date, profit factor, win rate, total trades); returns `ToolResult(output="No results found for strategy: {strategy}", error=None)` if none exist
    - `compare_runs(run_id_a, run_id_b)`: returns side-by-side metric comparison
    - Register all three tools in `ToolRegistry`
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

  - [~] 5.2 Write unit tests for backtest tools
    - Test `get_latest_backtest_result` with no `user_data_path` returns error; `load_run_history` with no results returns correct output; `compare_runs` with valid run IDs returns comparison dict
    - _Requirements: 16.4, 16.5_

  - [~] 5.3 Implement strategy tools
    - Create `app/core/ai/tools/strategy_tools.py` with functions: `list_strategies`, `read_strategy_code`, `read_strategy_params`
    - `list_strategies`: returns names of all `.py` files in `{user_data_path}/strategies/`
    - `read_strategy_code(strategy_name)`: returns full source (first 50 KB + truncation notice if larger); returns `ToolResult(error="Strategy file not found: {strategy_name}")` if missing
    - `read_strategy_params(strategy_name)`: returns buy/sell params and ROI table from JSON params file if it exists
    - Register all three tools in `ToolRegistry`
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

  - [~] 5.4 Write unit tests for strategy tools
    - Test `read_strategy_code` with missing file returns error; `read_strategy_code` with file > 50 KB returns truncated content with notice; `list_strategies` returns only `.py` filenames
    - _Requirements: 17.4, 17.5_

  - [~] 5.5 Write property test: AppSettings file persistence round-trip
    - **Property 12: AppSettings round-trip through file persistence**
    - For any valid `AppSettings` containing `AISettings`, save to a temp file and reload; assert `ai` field equals original including `chat_model`, `task_model`, and `routing_mode`
    - **Validates: Requirements 20.2**

  - [~] 5.6 Write property test: OpenRouter free model filtering
    - **Property 13: OpenRouter free model filtering**
    - Generate lists of model objects with varying pricing fields; assert `list_models()` with `free_only=True` returns only zero-priced models; with `free_only=False` returns all text-capable models
    - **Validates: Requirements 22.1, 22.2**

  - [ ] 5.7 Write property test: tool loop terminates at max_tool_steps
    - **Property 14: Tool loop terminates at max_tool_steps**
    - For any `max_tool_steps` value and AI responses that always request tool calls, assert `run_task()` terminates after at most `max_tool_steps` iterations with `error = "Max tool steps reached"` and `cancelled = False`
    - **Validates: Requirements 23.1, 23.2**

  - [ ] 5.8 Write property test: model capability classification is consistent
    - **Property 15: Model capability classification is consistent**
    - For any model name string, assert `ModelCapabilityRegistry` lookup returns a deterministic level; unknown names always return `"Level_B"`; same name always returns same level
    - **Validates: Requirements 24.1**

  - [ ] 5.9 Final checkpoint — ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at the end of each phase
- Property tests use Hypothesis (`@settings(max_examples=100)`) and are tagged with `# Feature: ai-chat-panel, Property N: <property_text>`
- Unit tests complement property tests by covering specific examples, integration points, and error conditions
- Phase 5 depends on Phase 4 completion (EventJournal and context providers must be wired before backtest/strategy tools are registered)
- Services never import UI code — `AIChatDock` wires signals to `ConversationRuntime`, not the other way around
