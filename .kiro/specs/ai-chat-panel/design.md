# Design Document: AI Chat Panel

## Overview

The AI Chat Panel is an embedded AI platform for the Freqtrade GUI desktop application. It is implemented as a `QDockWidget` that provides a dockable, floating-capable panel giving users access to an AI assistant with plain conversation, app-aware context delivery, and tool-driven actions.

The platform is provider-agnostic (Ollama local-first, OpenRouter optional), supports streaming responses, and is designed for incremental delivery across five phases — from a basic chat UI through to autonomous strategy-analysis loops.

**Core design principle:** The AI is a read-and-advise layer only. It never directly mutates application state, executes trades, or writes files without explicit user confirmation. All real business logic remains in existing services.

### Phased Delivery

| Phase | Scope |
|-------|-------|
| Phase 1 | Foundation — AISettings model, SettingsState signal, AIState QObject |
| Phase 2 | Providers — AIProvider ABC, OllamaProvider, OpenRouterProvider, ProviderFactory, ConversationRuntime, AIWorker threading |
| Phase 3 | Tools — ToolRegistry, ToolExecutor, basic app tools (get_app_status, read_recent_logs, get_last_error, list_recent_events) |
| Phase 4 | Context + Journal — AppContextProvider hierarchy, EventJournal, EventJournal adapters for existing services |
| Phase 5 | Backtest/Strategy tools — get_latest_backtest_result, load_run_history, compare_runs, list_strategies, read_strategy_code, read_strategy_params |

Phases 3–5 are fully designed here but not implemented until their phase is reached.

---

## Architecture

### Layered Architecture

The AI Chat Panel follows the existing project layering with no upward imports:

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: AI UI                                             │
│  app/ui/widgets/ai_chat_dock.py                             │
│  app/ui/widgets/ai_message_widget.py                        │
│  app/ui/widgets/tool_call_card.py                           │
└──────────────────────┬──────────────────────────────────────┘
                       │ signals only (no direct calls up)
┌──────────────────────▼──────────────────────────────────────┐
│  Layer 2: AI State                                          │
│  app/app_state/ai_state.py  (QObject + signals)             │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Layer 3: Model Runtime                                     │
│  app/core/ai/runtime/conversation_runtime.py                │
│  app/core/ai/runtime/agent_policy.py                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Layer 4: Tools                                             │
│  app/core/ai/tools/tool_registry.py                         │
│  app/core/ai/tools/tool_executor.py                         │
│  app/core/ai/tools/app_tools.py                             │
│  app/core/ai/tools/log_path_resolver.py                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Layer 5: App Context                                       │
│  app/core/ai/context/context_provider.py                    │
│  app/core/ai/context/app_state_context.py                   │
│  app/core/ai/context/backtest_context.py                    │
│  app/core/ai/context/strategy_context.py                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Layer 6: Event Journal                                     │
│  app/core/ai/journal/event_journal.py                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Layer 7: Agent Policy + Provider                           │
│  app/core/ai/providers/provider_base.py                     │
│  app/core/ai/providers/ollama_provider.py                   │
│  app/core/ai/providers/openrouter_provider.py               │
│  app/core/ai/providers/provider_factory.py                  │
│  app/core/models/settings_models.py  (AISettings)           │
└─────────────────────────────────────────────────────────────┘
```

**Invariant:** No module in a lower layer imports from a higher layer. Services never import UI code.

### Threading Model

All provider calls run in a `QThread` worker using the `AIWorker(QObject)` pattern — consistent with the existing `ProcessService` approach:

```
Main Thread                    Worker Thread (QThread)
──────────                     ──────────────────────
AIChatDock                     AIWorker (moved to QThread)
  │                              │
  ├─ send_message() ────────────►│ provider.stream_chat()
  │                              │   ├─ token_received(StreamToken) ──► main thread
  │                              │   └─ response_complete(AIResponse) ► main thread
  │                              │
  ├─ cancel_current_request() ──►│ cancel_flag.set()
  │                              │ http_session.close()
  │                              │
  └─ health_check() ────────────►│ provider.health_check()
                                 │   └─ health_checked(ProviderHealth) ► main thread
```

The `AIWorker` holds a `threading.Event cancel_flag`. The provider checks it between chunks during streaming. On `cancel_current_request()`, the flag is set AND the HTTP session is closed to unblock any blocking read.

### Dual-Model Routing

`ConversationRuntime` reads `routing_mode` from `AISettings` at call time:

```
routing_mode = "single_model"  →  chat_model used for both send_message() and run_task()
routing_mode = "dual_model"    →  chat_model for send_message(), task_model for run_task()
```

`ProviderFactory.create()` is called once per routing decision, not cached globally, so model switches take effect immediately.

### Model Capability Classification

A `ModelCapabilityRegistry` maps known model name patterns to capability levels:

| Level | Capability | Tool Strategy |
|-------|-----------|---------------|
| Level_A | Plain text only | Warn user, disable tool injection |
| Level_B | Structured JSON | Prompt-based action extraction |
| Level_C | Native tool calling | Inject tool schemas natively |

Unknown models default to Level_B. Providers can supply metadata to override.

---

## Components and Interfaces

### Phase 1: Foundation

#### `app/core/models/settings_models.py` — AISettings

`AISettings` is a new Pydantic `BaseModel` nested inside the existing `AppSettings`:

```python
class AISettings(BaseModel):
    provider: str = Field("ollama", description="Active provider: 'ollama' or 'openrouter'")
    ollama_base_url: str = Field("http://localhost:11434", description="Ollama server base URL")
    openrouter_api_key: Optional[str] = Field(None, description="OpenRouter API key")
    chat_model: str = Field("", description="Model for plain conversation")
    task_model: str = Field("", description="Model for tool-using task runs")
    routing_mode: str = Field("single_model", description="'single_model' or 'dual_model'")
    cloud_fallback_enabled: bool = Field(False, description="Reserved — no runtime effect in this version")
    openrouter_free_only: bool = Field(True, description="Filter OpenRouter to free models only")
    timeout_seconds: int = Field(60, description="HTTP request timeout in seconds")
    stream_enabled: bool = Field(True, description="Use streaming responses")
    tools_enabled: bool = Field(False, description="Enable tool calling")
    max_history_messages: int = Field(50, description="Max messages retained in history")
    max_tool_steps: int = Field(8, description="Max tool call iterations per run_task()")

    @field_validator("routing_mode")
    @classmethod
    def validate_routing_mode(cls, v: str) -> str:
        if v not in ("single_model", "dual_model"):
            raise ValueError(f"routing_mode must be 'single_model' or 'dual_model', got: {v!r}")
        return v
```

`AppSettings` gains:
```python
ai: AISettings = Field(default_factory=AISettings, description="AI panel configuration")
```

Legacy migration: if a loaded JSON contains `selected_model`, it is mapped to `chat_model` via a `model_validator(mode="before")`.

#### `app/app_state/ai_state.py` — AIState

```python
class AIState(QObject):
    # Emitted when provider health changes
    health_changed = Signal(object)          # ProviderHealth
    # Emitted when model list is refreshed
    models_refreshed = Signal(list)          # list[str]
    # Emitted when AI settings change (provider/model switch in header)
    ai_settings_changed = Signal(object)     # AISettings
    # Emitted when a streaming token arrives
    token_received = Signal(object)          # StreamToken
    # Emitted when a full response is ready
    response_complete = Signal(object)       # AIResponse
    # Emitted on any error
    error_occurred = Signal(str)
    # Emitted when a task run completes
    task_complete = Signal(object)           # TaskRunResult
```

`SettingsState` gains an `ai_settings_changed = Signal(AISettings)` signal emitted whenever `save_settings()` is called with changed AI fields.

---

### Phase 2: Providers and Runtime

#### `app/core/ai/providers/provider_base.py`

```python
@dataclass
class AIResponse:
    content: str
    model: str
    tool_calls: list = field(default_factory=list)
    finish_reason: str = ""
    usage: Optional[dict] = None

@dataclass
class ProviderHealth:
    ok: bool
    message: str
    latency_ms: Optional[float] = None

@dataclass
class StreamToken:
    delta: str
    finish_reason: Optional[str] = None

class AIProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    def chat(self, messages: list[dict], model: str, **kwargs) -> AIResponse: ...

    @abstractmethod
    def stream_chat(self, messages: list[dict], model: str, **kwargs) -> Iterator[StreamToken]: ...

    @abstractmethod
    def list_models(self) -> list[str]: ...

    @abstractmethod
    def health_check(self) -> ProviderHealth: ...

    @abstractmethod
    def cancel_current_request(self) -> None:
        """Close the active HTTP session/connection to abort any in-progress request."""
        ...

    def get_model_capability(self, model: str) -> str:
        """Return Level_A, Level_B, or Level_C. Default implementation returns Level_B."""
        return "Level_B"
```

#### `app/core/ai/providers/ollama_provider.py` — OllamaProvider

- Uses `requests.Session` for connection reuse and cancellation support. Each provider instance owns a single `requests.Session` that is created in `__init__` and reused across calls for connection pooling. `cancel_current_request()` closes this session, which aborts any in-progress request. A new session is created automatically on the next call after cancellation.
- `stream_chat()` reads newline-delimited JSON chunks; checks `cancel_flag` between each chunk.
- `health_check()` GETs `/api/tags`, measures latency, returns `ProviderHealth`.
- On connection error/timeout: returns `ProviderHealth(ok=False, message=...)` — never raises.
- On non-200 HTTP: raises `ValueError(f"Ollama returned {status}: {body}")`.
- Cancellation: `cancel_current_request()` calls `self._session.close()`.

#### `app/core/ai/providers/openrouter_provider.py` — OpenRouterProvider

- Uses `requests.Session` with `Authorization: Bearer {api_key}` header. Each provider instance owns a single `requests.Session` that is created in `__init__` and reused across calls for connection pooling. `cancel_current_request()` closes this session, which aborts any in-progress request. A new session is created automatically on the next call after cancellation.
- `stream_chat()` reads SSE `data:` lines; checks `cancel_flag` between each.
- `list_models()` filters by `openrouter_free_only` and text-capable model types.
- `health_check()` returns `ProviderHealth(ok=False, message="API key not configured")` if key is absent — no network call.
- API key logged as `key[:8] + "..."` only.
- Cancellation: `cancel_current_request()` calls `self._session.close()`.

#### `app/core/ai/providers/provider_factory.py` — ProviderFactory

```python
class ProviderFactory:
    @staticmethod
    def create(ai_settings: AISettings) -> AIProvider:
        if ai_settings.provider == "ollama":
            return OllamaProvider(base_url=ai_settings.ollama_base_url,
                                  timeout=ai_settings.timeout_seconds)
        elif ai_settings.provider == "openrouter":
            return OpenRouterProvider(api_key=ai_settings.openrouter_api_key,
                                      timeout=ai_settings.timeout_seconds,
                                      free_only=ai_settings.openrouter_free_only)
        else:
            raise ValueError(f"Unsupported provider: {ai_settings.provider!r}")
```

#### `app/core/ai/runtime/agent_policy.py` — AgentPolicy

```python
@dataclass
class AgentPolicy:
    system_prompt: str
    tool_usage_policy: str
    safety_rules: list[str]
```

Default `system_prompt` instructs the AI that it is a read-and-advise assistant, must not claim to execute trades or write files without user confirmation, and must use tools only when necessary.

Default `safety_rules` includes a rule preventing the AI from returning raw API keys or credentials. `ConversationRuntime` strips strings matching known secret patterns before emitting tokens to the UI.

#### `app/core/ai/runtime/conversation_runtime.py` — ConversationRuntime

```python
@dataclass
class TaskRunResult:
    messages: list[dict]
    tool_steps: list  # list[ToolResult]
    final_response: Optional[str]
    cancelled: bool
    error: Optional[str]

class ConversationRuntime(QObject):
    token_received = Signal(object)    # StreamToken
    response_complete = Signal(object) # AIResponse
    error_occurred = Signal(str)
    task_complete = Signal(object)     # TaskRunResult

    def __init__(self, ai_settings: AISettings, agent_policy: AgentPolicy,
                 tool_registry=None, context_providers=None): ...

    def send_message(self, text: str) -> None: ...          # async via AIWorker; results delivered via response_complete signal
    def run_task(self, text: str) -> None: ...              # async via AIWorker; results delivered via task_complete signal
    def cancel_current_request(self) -> None: ...
    def clear_history(self) -> None: ...
    def set_system_prompt(self, prompt: str) -> None: ...
```

**History management:** `max_history_messages` is enforced by removing the oldest non-system messages first when the limit is exceeded.

**Model routing:**
- `send_message` → `chat_model` always (regardless of `routing_mode`)
- `run_task` → `task_model` if `routing_mode == "dual_model"`, else `chat_model`

**Tool injection:** Only when `tools_enabled=True` AND model is Level_B or Level_C. Level_A emits `error_occurred` warning and skips injection.

**Cancellation:** `cancel_current_request()` sets `cancel_flag` AND calls `provider.cancel_current_request()` (closes HTTP session). If worker thread does not finish within 2 seconds, a warning is logged and the thread is detached safely.

**Streaming cancellation:** Partial tokens received before cancellation are appended to history with `finish_reason="cancelled"`.

**Secret scrubbing:** Before emitting any token, `ConversationRuntime` applies a regex pass to strip strings matching known secret patterns (e.g. `sk-...`, bearer tokens).

#### `app/core/ai/runtime/conversation_runtime.py` — AIWorker

```python
class AIWorker(QObject):
    token_received = Signal(object)
    response_complete = Signal(object)
    error_occurred = Signal(str)
    task_complete = Signal(object)

    def __init__(self, provider: AIProvider, cancel_flag: threading.Event): ...

    def run_chat(self, messages: list[dict], model: str, stream: bool) -> None: ...
    def run_task_loop(self, messages: list[dict], model: str,
                     tool_registry, max_steps: int) -> None: ...
```

`AIWorker` uses a **per-request** lifecycle: a new `AIWorker` instance is created and moved to a new `QThread` for each request. The thread is started, runs to completion (or cancellation), and is then cleaned up. This is the simplest and safest approach for Phase 1–2 and avoids thread-reuse race conditions. A persistent-thread optimization may be introduced in a later phase if profiling shows startup overhead is significant. Signals carry results back to the main thread.

---

### Phase 3: Tools

#### `app/core/ai/tools/tool_registry.py`

```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters_schema: dict   # JSON Schema
    callable: Callable

class ToolRegistry:
    def register(self, definition: ToolDefinition) -> None: ...
    def get_schema_list(self) -> list[dict]: ...
    def get(self, name: str) -> Optional[ToolDefinition]: ...
```

Validation on `register()`: `name` must be non-empty string, `callable` must be callable — raises `ValueError` otherwise.

#### `app/core/ai/tools/tool_executor.py`

```python
@dataclass
class ToolResult:
    tool_name: str
    output: Any          # dict | list | str
    display_text: str = ""
    error: Optional[str] = None

class ToolExecutor:
    def __init__(self, registry: ToolRegistry): ...
    def execute(self, tool_name: str, arguments: dict) -> ToolResult: ...
```

On exception: catches, logs, returns `ToolResult(tool_name=..., output="", display_text="", error=str(e))`.
On missing tool: returns `ToolResult(tool_name=tool_name, output="", error=f"Tool not found: {tool_name}")`.

#### `app/core/ai/tools/app_tools.py` — Phase 3 tools

| Tool | Parameters | Returns |
|------|-----------|---------|
| `get_app_status` | none | provider name, model name, tools enabled, active tab |
| `read_recent_logs` | `lines: int = 50` (max 200) | last N lines from app log file; clamps >200 with note |
| `get_last_error` | none | most recent ERROR-level entry from EventJournal or log file |
| `list_recent_events` | `n: int = 20` | last N EventRecord entries as JSON array |

Log file path is resolved via a `LogPathResolver` utility that reads the configured log directory from `AppSettings` or the logger service's public API — never from a private attribute or hardcoded path. `LogPathResolver.get_log_path(log_name: str) -> Path` is the single point of resolution.

All tools complete within 2 seconds. `read_recent_logs` with `lines > 200` clamps to 200 and appends a truncation note.

---

### Phase 4: Context and Journal

#### `app/core/ai/context/context_provider.py`

```python
class AppContextProvider(ABC):
    @abstractmethod
    def get_context(self) -> dict: ...
```

All implementations return within 100ms with no blocking I/O.

#### Context Provider Implementations

| Class | File | Returns |
|-------|------|---------|
| `AppStateContextProvider` | `app_state_context.py` | provider name, selected model, tools enabled, active tab name |
| `BacktestContextProvider` | `backtest_context.py` | last strategy, timeframe, timerange, exit code, last result summary |
| `StrategyContextProvider` | `strategy_context.py` | last open strategy name and file path |

`ConversationRuntime` accepts a `list[AppContextProvider]` and includes their combined output in the system prompt.

#### `app/core/ai/journal/event_journal.py`

```python
@dataclass
class EventRecord:
    timestamp: datetime
    event_type: str
    source: str
    payload: dict

class EventJournal:
    MAX_CAPACITY = 200

    def record(self, event_type: str, source: str, payload: dict) -> None: ...
    def get_recent(self, n: int = 50) -> list[EventRecord]: ...
```

Enforces 200-event capacity by discarding the oldest event when exceeded.

**EventJournal adapters** (thin, no direct coupling to services):
- `BacktestService` emits `backtest_started` / `backtest_finished` events via a callback registered at startup.
- `SettingsState.settings_saved` signal is connected to record `settings_saved` events.
- Adapters live in `app/core/ai/journal/` and import from services — services never import from journal.

---

### Phase 5: Backtest and Strategy Tools (designed, not yet implemented)

#### Backtest Tools (`app/core/ai/tools/backtest_tools.py`)

| Tool | Parameters | Returns |
|------|-----------|---------|
| `get_latest_backtest_result` | none | most recent BacktestResults summary for current strategy |
| `load_run_history` | `strategy: str` | list of run summaries (date, profit factor, win rate, total trades) |
| `compare_runs` | `run_id_a: str, run_id_b: str` | side-by-side metric comparison |

When `user_data_path` is not configured: returns `ToolResult(error="user_data_path not configured")`.
When no results exist: returns `ToolResult(output="No results found for strategy: {strategy}", error=None)`.

#### Strategy Tools (`app/core/ai/tools/strategy_tools.py`)

| Tool | Parameters | Returns |
|------|-----------|---------|
| `list_strategies` | none | names of all `.py` files in `{user_data_path}/strategies/` |
| `read_strategy_code` | `strategy_name: str` | full source code (first 50 KB + truncation notice if larger) |
| `read_strategy_params` | `strategy_name: str` | buy/sell params and ROI table from JSON params file |

When strategy file not found: `ToolResult(error="Strategy file not found: {strategy_name}")`.

---

### UI Components

#### `app/ui/widgets/ai_chat_dock.py` — AIChatDock

`AIChatDock(QDockWidget)` is added to `MainWindow` in `__init__` with `Qt.RightDockWidgetArea` as default. It is toggleable via a toolbar button without destroying state.

**Header layout:**

```
Single model mode:
┌─────────────────────────────────────────────────────────┐
│ [Provider ▼]  [Model ▼]  ● connected  [Tools ⚙]        │
└─────────────────────────────────────────────────────────┘

Dual model mode (dock width ≥ 280px):
┌─────────────────────────────────────────────────────────┐
│ [Provider ▼]  Chat: [Model ▼]  ● connected  [Tools ⚙]  │
│               Task: [Model ▼]                           │
└─────────────────────────────────────────────────────────┘

Dual model mode (dock width < 280px):
┌─────────────────────────────────────────────────────────┐
│ [Provider ▼]  Chat: [Model ▼]  [⚙] ● [Tools]           │
└─────────────────────────────────────────────────────────┘
  (Task selector collapses to icon button opening a popup)
```

The dock listens to `resizeEvent` and switches layout at the 280px threshold.

**Body:** Scrollable `QScrollArea` containing `AIMessageWidget` instances. Auto-scrolls to latest message unless user has manually scrolled up (detected via scrollbar position).

**Input area:** `QPlainTextEdit` (multi-line), Send button, Stop button. Stop is enabled only during active streaming.

**No-model state:** When first shown with no model selected, displays a `QLabel` prompt: "Select a model in Settings → AI to get started."

#### `app/ui/widgets/ai_message_widget.py`

Two variants:
- `UserMessageWidget` — right-aligned, distinct background
- `AssistantMessageWidget` — left-aligned, different background; supports incremental token appending during streaming; renders fenced code blocks in monospace with contrasting background

#### `app/ui/widgets/tool_call_card.py` — ToolCard

Collapsible widget showing:
- Tool name (header, always visible)
- Input arguments (collapsible section)
- Result output (collapsible section)

Uses a `QToolButton` with `setCheckable(True)` to toggle the body visibility.

---

## Data Models

### AISettings (Pydantic BaseModel)

```
AISettings
├── provider: str = "ollama"
├── ollama_base_url: str = "http://localhost:11434"
├── openrouter_api_key: Optional[str] = None
├── chat_model: str = ""
├── task_model: str = ""
├── routing_mode: str = "single_model"   # validated: "single_model" | "dual_model"
├── cloud_fallback_enabled: bool = False  # reserved, no runtime effect
├── openrouter_free_only: bool = True
├── timeout_seconds: int = 60
├── stream_enabled: bool = True
├── tools_enabled: bool = False
├── max_history_messages: int = 50
└── max_tool_steps: int = 8
```

### AppSettings (extended)

```
AppSettings
├── ... (existing fields)
└── ai: AISettings = Field(default_factory=AISettings)
```

### Provider DTOs (dataclasses)

```
AIResponse
├── content: str
├── model: str
├── tool_calls: list = []
├── finish_reason: str = ""
└── usage: Optional[dict] = None

ProviderHealth
├── ok: bool
├── message: str
└── latency_ms: Optional[float] = None

StreamToken
├── delta: str
└── finish_reason: Optional[str] = None
```

### Runtime DTOs (dataclasses)

```
TaskRunResult
├── messages: list[dict]
├── tool_steps: list[ToolResult]
├── final_response: Optional[str]
├── cancelled: bool
└── error: Optional[str]

ToolResult
├── tool_name: str
├── output: Any          # dict | list | str
├── display_text: str = ""
└── error: Optional[str] = None

ToolDefinition
├── name: str
├── description: str
├── parameters_schema: dict
└── callable: Callable
```

### Journal DTOs (dataclasses)

```
EventRecord
├── timestamp: datetime
├── event_type: str
├── source: str
└── payload: dict
```

### AgentPolicy (dataclass)

```
AgentPolicy
├── system_prompt: str
├── tool_usage_policy: str
└── safety_rules: list[str]
```

### Message History Format

Messages are plain dicts following the OpenAI/Ollama convention:
```python
{"role": "system",    "content": "..."}
{"role": "user",      "content": "..."}
{"role": "assistant", "content": "..."}
{"role": "tool",      "content": "..."}
```

### ModelCapabilityRegistry

```python
# Maps model name pattern (regex or prefix) → capability level
ModelCapabilityRegistry: dict[str, str] = {
    "llama2":        "Level_A",
    "mistral":       "Level_B",
    "llama3":        "Level_B",
    "qwen":          "Level_B",
    "gpt-4":         "Level_C",
    "claude":        "Level_C",
    "mistral-nemo":  "Level_C",
    # ... extensible
}
DEFAULT_CAPABILITY = "Level_B"
```

Unknown models default to `Level_B`. Providers can supply metadata to override via a `get_model_capability(model: str) -> str` method on `AIProvider`.

When the active provider is `OpenRouterProvider`, `list_models()` also returns model metadata including `supported_parameters`. If a model's metadata includes `tools` or `function_calling` in `supported_parameters`, it is classified as `Level_C` regardless of the name-pattern registry. This makes OpenRouter capability detection data-driven rather than name-pattern-only. For Ollama, name-pattern matching remains the primary mechanism.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

**Property reflection:** After prework analysis, the following redundancies were resolved:
- Requirement 20.1 (AISettings round-trip) is subsumed by Requirement 1.4 — combined into Property 1.
- Requirement 6.4/6.5 (model routing) are combined into a single routing property (Property 5).
- Requirement 22.1/22.2 (free model filtering) are combined into a single filtering property (Property 8).

---

### Property 1: AISettings serialization round-trip

*For any* valid `AISettings` object (with any combination of field values within their declared types), serializing with `model_dump(mode="json")` and then deserializing with `AISettings.model_validate()` SHALL produce an object equal to the original.

**Validates: Requirements 1.4, 20.1**

---

### Property 2: routing_mode validation rejects invalid values

*For any* string that is not `"single_model"` or `"dual_model"`, constructing an `AISettings` with that value for `routing_mode` SHALL raise a Pydantic `ValidationError`. Conversely, `"single_model"` and `"dual_model"` SHALL always be accepted.

**Validates: Requirements 1.2**

---

### Property 3: AISettings partial JSON loading uses defaults

*For any* non-empty subset of `AISettings` fields provided as a dict, `AISettings.model_validate()` SHALL succeed and all omitted fields SHALL equal their declared default values.

**Validates: Requirements 1.5**

---

### Property 4: ProviderFactory raises ValueError for unknown providers

*For any* string that is not `"ollama"` or `"openrouter"`, calling `ProviderFactory.create()` with that provider string SHALL raise a `ValueError`. Conversely, `"ollama"` and `"openrouter"` SHALL always produce the correct provider type.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4**

---

### Property 5: ConversationRuntime model routing is correct for all routing modes

*For any* `routing_mode` value (`"single_model"` or `"dual_model"`) and any call type (`send_message` or `run_task`), the model passed to the provider SHALL be `chat_model` for `send_message` in both modes, `chat_model` for `run_task` in `"single_model"` mode, and `task_model` for `run_task` in `"dual_model"` mode.

**Validates: Requirements 6.3, 6.4, 6.8**

---

### Property 6: History trimming preserves system message and respects limit

*For any* sequence of user/assistant messages added to `ConversationRuntime` that exceeds `max_history_messages`, the system message SHALL always remain as the first message, the total message count SHALL never exceed `max_history_messages`, and the most recently added messages SHALL be retained over older ones.

**Validates: Requirements 6.2**

---

### Property 7: clear_history leaves only the system message

*For any* `ConversationRuntime` with any number of messages in history, calling `clear_history()` SHALL result in a history containing exactly one message with `role="system"`.

**Validates: Requirements 6.9**

---

### Property 8: ToolRegistry registration validates name and callable

*For any* `ToolDefinition`, if `name` is an empty string or `callable` is not callable, `ToolRegistry.register()` SHALL raise `ValueError`. If `name` is a non-empty string and `callable` is callable, registration SHALL succeed.

**Validates: Requirements 7.2**

---

### Property 9: ToolExecutor returns ToolResult for any input

*For any* tool name (registered or not) and any arguments dict, `ToolExecutor.execute()` SHALL return a `ToolResult` without raising an exception. If the tool is not found, `error` SHALL be set to `"Tool not found: {tool_name}"`. If the tool callable raises, `error` SHALL be set to the exception message and `output` SHALL be `""`.

**Validates: Requirements 7.4, 7.5, 7.6, 7.7**

---

### Property 10: EventJournal never exceeds capacity

*For any* sequence of events recorded into `EventJournal` of any length, the journal SHALL never contain more than 200 entries, and the retained entries SHALL always be the most recently recorded ones.

**Validates: Requirements 13.2**

---

### Property 11: EventJournal get_recent returns chronological order

*For any* `EventJournal` state and any value of `n`, `get_recent(n)` SHALL return at most `n` events and the returned events SHALL be in chronological order (ascending by timestamp).

**Validates: Requirements 13.4**

---

### Property 12: AppSettings round-trip through file persistence

*For any* valid `AppSettings` object containing `AISettings`, saving to a temp file and reloading SHALL produce an `AppSettings` whose `ai` field equals the original `ai` field, including `chat_model`, `task_model`, and `routing_mode`.

**Validates: Requirements 20.2**

---

### Property 13: OpenRouter free model filtering

*For any* list of model objects returned by the OpenRouter API (with varying pricing fields), when `openrouter_free_only=True`, `list_models()` SHALL return only models whose prompt and completion pricing are both zero. When `openrouter_free_only=False`, all text-capable models SHALL be returned regardless of pricing.

**Validates: Requirements 22.1, 22.2**

---

### Property 14: Tool loop terminates at max_tool_steps

*For any* `max_tool_steps` value and any sequence of AI responses that always request tool calls, `run_task()` SHALL terminate after at most `max_tool_steps` iterations, setting `TaskRunResult.error = "Max tool steps reached"` and `TaskRunResult.cancelled = False`.

**Validates: Requirements 23.1, 23.2**

---

### Property 15: Model capability classification is consistent

*For any* model name string, `ModelCapabilityRegistry` lookup SHALL return a deterministic capability level (`Level_A`, `Level_B`, or `Level_C`). Unknown model names SHALL always return `Level_B`. The same model name SHALL always return the same level.

**Validates: Requirements 24.1**

---

## Error Handling

### Provider Errors

| Scenario | Behavior |
|----------|----------|
| Connection refused / timeout | `ProviderHealth(ok=False, message=...)` — never raises to caller |
| Non-200 HTTP response | Raises `ValueError(f"Provider returned {status}: {body}")` |
| Streaming interrupted by cancellation | Partial tokens appended to history with `finish_reason="cancelled"` |
| Worker thread exception | `error_occurred(str)` signal emitted; full traceback logged |

### Tool Errors

| Scenario | Behavior |
|----------|----------|
| Tool not found | `ToolResult(error="Tool not found: {name}")` |
| Tool callable raises | `ToolResult(error=str(e), output="", display_text="")` |
| Tool exceeds 2s timeout | Caught by executor; `ToolResult(error="Tool timed out")` |
| `user_data_path` not configured | `ToolResult(error="user_data_path not configured")` |

### Settings Errors

| Scenario | Behavior |
|----------|----------|
| Invalid `routing_mode` | Pydantic `ValidationError` on model construction |
| Missing AI fields in JSON | Default values substituted silently |
| Legacy `selected_model` key | Mapped to `chat_model` via `model_validator(mode="before")` |

### UI Errors

| Scenario | Behavior |
|----------|----------|
| No model selected | Prompt label shown; Send button disabled |
| `list_models()` returns empty | `"No models available"` placeholder; error logged |
| Health check fails | Status indicator → red; latency display cleared |
| Level_A model with tools enabled | `error_occurred` signal emitted with warning; tool injection skipped |

### Cancellation

`cancel_current_request()` is safe to call at any time:
1. Sets `cancel_flag` (threading.Event)
2. Calls `provider.cancel_current_request()` → closes HTTP session
3. If worker thread does not finish within 2 seconds, logs warning and detaches safely — never blocks main thread

---

## Testing Strategy

### Dual Testing Approach

Both unit tests and property-based tests are used for comprehensive coverage:
- **Unit tests** — specific examples, integration points, edge cases, error conditions
- **Property tests** — universal properties across generated inputs (Properties 1–15 above)

### Property-Based Testing

**Library:** [Hypothesis](https://hypothesis.readthedocs.io/) (Python PBT library, consistent with existing `.hypothesis/` directory in the project)

**Configuration:** Each property test runs a minimum of 100 iterations (`@settings(max_examples=100)`).

**Tag format:** Each property test is tagged with a comment:
```python
# Feature: ai-chat-panel, Property N: <property_text>
```

**Strategies (Hypothesis generators) needed:**
- `st.builds(AISettings, ...)` — generate valid AISettings with random field values
- `st.text()` filtered for routing_mode validation tests
- `st.lists(st.fixed_dictionaries({...}))` — generate message sequences
- `st.integers(min_value=1, max_value=500)` — for history limit tests
- `st.lists(st.builds(EventRecord, ...))` — for journal tests
- `st.text()` for model name classification tests

### Unit Test Coverage

**Phase 1 — Settings:**
- `AISettings` default construction and field types
- `AppSettings.ai` field presence
- Legacy `selected_model` migration
- `AppSettings` with missing `ai` key loads defaults

**Phase 2 — Providers:**
- `OllamaProvider.chat()` with mocked HTTP 200 response
- `OllamaProvider.health_check()` with mocked success and failure
- `OllamaProvider` non-200 raises `ValueError`
- `OpenRouterProvider.health_check()` with no API key
- `OpenRouterProvider` never logs full API key
- `ProviderFactory` creates correct types for valid providers
- `ConversationRuntime` system prompt always first message
- `ConversationRuntime` error signal on provider exception
- `AIWorker` signals carry results to main thread (via `QSignalSpy`)

**Phase 3 — Tools:**
- `ToolRegistry.get_schema_list()` format matches provider API expectations
- `ToolExecutor` with registered tool returning dict output
- `get_app_status` returns expected keys
- `read_recent_logs` clamps lines > 200 and includes note
- `list_recent_events` returns correct JSON array

**Phase 4 — Context + Journal:**
- `AppStateContextProvider.get_context()` returns within 100ms
- `EventJournal.record()` appends correct EventRecord
- `EventJournal` adapter records `backtest_started` / `backtest_finished` events
- `settings_saved` event recorded on SettingsState signal

**Phase 5 — Backtest/Strategy Tools:**
- `get_latest_backtest_result` with no `user_data_path` returns error
- `read_strategy_code` with missing file returns error
- `read_strategy_code` with file > 50 KB returns truncated content with notice

### Integration Tests

- `OllamaProvider` against a real local Ollama instance (skipped if not available)
- `OpenRouterProvider` against OpenRouter API (skipped if no API key)
- Full `ConversationRuntime` → `AIWorker` → `OllamaProvider` round-trip with mock HTTP

### UI Tests

- `AIChatDock` header switches layout at 280px threshold
- Stop button enabled during streaming, disabled after completion
- Auto-scroll behavior (scrolls to bottom on new message, stays put if user scrolled up)
- `ToolCard` expand/collapse toggle
- No-model-selected prompt shown when `chat_model` is empty
