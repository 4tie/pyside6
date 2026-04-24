# Design Document: Web Layer Architecture

## Overview

This design enforces a clean layered architecture across the Freqtrade GUI codebase and
completes the `app/web/` FastAPI layer so it is fully functional and correctly wired to the
existing service layer.

The work falls into four concrete deliverables:

1. **Architecture Linter** — a `pytest` module that statically scans `app/` for forbidden
   cross-layer imports and fails CI when violations are found.
2. **RollbackService** — a new `app/core/services/rollback_service.py` that restores a
   strategy's params and config from a saved run directory.
3. **Rollback API endpoint** — `POST /api/runs/{strategy}/{run_id}/rollback` wired to
   `RollbackService`.
4. **SSE Process Output Bus** — a thread-safe bridge (`ProcessOutputBus`) that connects
   `ProcessService` callbacks to the `GET /api/process/stream` SSE endpoint, replacing the
   current no-op lambdas.

The `AsyncConversationRuntime` already exists and is PySide6-free; the legacy
`conversation_runtime.py` (if it still exists) must be removed or confirmed absent.

---

## Architecture

### Layer Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser / Web Client                                           │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼────────────────────────────────────┐
│  app/web/  (FastAPI — Web Layer)                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ main.py      │  │ dependencies │  │ models.py            │  │
│  │ (app, CORS,  │  │ .py          │  │ (Pydantic req/resp)  │  │
│  │  routers)    │  │ (@lru_cache  │  └──────────────────────┘  │
│  └──────────────┘  │  singletons) │                            │
│                    └──────────────┘                            │
│  api/routes/                                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │backtest  │ │optimize  │ │runs      │ │process (SSE)     │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
│  ┌──────────┐ ┌──────────┐                                     │
│  │settings  │ │strategies│                                     │
│  └──────────┘ └──────────┘                                     │
│                                                                 │
│  process_output_bus.py  ← NEW (thread-safe asyncio bridge)     │
└────────────────────────────┬────────────────────────────────────┘
                             │ Python function calls only
┌────────────────────────────▼────────────────────────────────────┐
│  app/core/services/  (Service Layer)                            │
│  BacktestService  OptimizeService  DownloadDataService          │
│  SettingsService  ProcessService   RollbackService ← NEW        │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  app/core/  (Core Layer — models, runners, resolvers, utils)    │
│  backtests/  freqtrade/  models/  parsing/  utils/  ai/         │
└─────────────────────────────────────────────────────────────────┘
```

### Invariants

- `app/core/` has **zero** `PySide6` imports.
- `app/core/services/` has **zero** `app.ui` or `app.app_state` imports.
- `app/web/` has **zero** `app.ui` imports.
- Route handlers contain **no business logic** — they call a service method and return a
  Pydantic model.
- `ProcessService` is the **only** place subprocesses are spawned.

---

## Components and Interfaces

### 1. Architecture Linter (`tests/test_architecture.py`)

A single pytest module that encodes the three layer boundary rules as data and scans all
Python files under `app/` using the `ast` module (or simple regex for speed).

```python
# Rule definition structure
@dataclass
class ArchRule:
    name: str
    scan_dir: str          # directory to scan (relative to repo root)
    forbidden_patterns: list[str]  # regex patterns to match against each line

RULES: list[ArchRule] = [
    ArchRule(
        name="No PySide6 in app/core/",
        scan_dir="app/core",
        forbidden_patterns=[r"^\s*(import|from)\s+PySide6"],
    ),
    ArchRule(
        name="No app.ui or app.app_state in app/core/services/",
        scan_dir="app/core/services",
        forbidden_patterns=[
            r"^\s*(import|from)\s+app\.ui",
            r"^\s*(import|from)\s+app\.app_state",
        ],
    ),
    ArchRule(
        name="No app.ui in app/web/",
        scan_dir="app/web",
        forbidden_patterns=[r"^\s*(import|from)\s+app\.ui"],
    ),
]
```

**Violation dataclass:**

```python
@dataclass
class Violation:
    rule_name: str
    file_path: str   # relative to repo root
    line_number: int
    line_text: str   # the offending line, stripped
```

**Public API:**

```python
def scan_for_violations(rules: list[ArchRule], repo_root: Path) -> list[Violation]:
    """Scan all .py files under each rule's scan_dir and return all violations."""
    ...

def test_architecture_boundaries():
    """pytest test — fails with all violations in a single assertion message."""
    violations = scan_for_violations(RULES, Path(__file__).parent.parent)
    assert violations == [], format_violations(violations)
```

The linter is also runnable as a standalone script:

```bash
python tests/test_architecture.py
```

### 2. RollbackService (`app/core/services/rollback_service.py`)

A stateless service that copies `params.json` and `config.snapshot.json` from a saved run
directory back to the active strategy locations.

```python
@dataclass
class RollbackResult:
    success: bool
    rolled_back_to: str      # run_id
    strategy_name: str
    params_restored: bool
    config_restored: bool
    error: Optional[str] = None
```

```python
class RollbackService:
    """Restores strategy params and config from a saved backtest run."""

    def rollback(
        self,
        run_dir: Path,
        user_data_path: Path,
        strategy_name: str,
    ) -> RollbackResult:
        """
        Copy params.json → {user_data}/strategies/{strategy_name}.json
        Copy config.snapshot.json → active config location

        Args:
            run_dir: Absolute path to the run folder (contains params.json,
                     config.snapshot.json).
            user_data_path: Absolute path to the freqtrade user_data directory.
            strategy_name: Name of the strategy (without .py extension).

        Returns:
            RollbackResult with success flag and details.

        Raises:
            FileNotFoundError: If run_dir does not exist.
            ValueError: If neither params.json nor config.snapshot.json exists
                        in the run directory.
        """
```

**Rollback logic:**

1. Validate `run_dir` exists — raise `FileNotFoundError` if not.
2. Copy `params.json` → `{user_data}/strategies/{strategy_name}.json` (hyperopt params file).
   - If `params.json` is absent, set `params_restored = False` and log a warning.
3. Copy `config.snapshot.json` → `{user_data}/config.json` (active config).
   - If `config.snapshot.json` is absent, set `config_restored = False` and log a warning.
4. If neither file was restored, raise `ValueError`.
5. Return `RollbackResult(success=True, ...)`.

All file writes use `write_json_file_atomic` to prevent partial writes.

### 3. Rollback API Endpoint (`app/web/api/routes/runs.py`)

Add to the existing `runs.py` router:

```python
@router.post("/runs/{strategy}/{run_id}/rollback", response_model=RollbackResponse)
async def rollback_run(
    strategy: str,
    run_id: str,
    settings: SettingsServiceDep,
    rollback_service: RollbackServiceDep,
) -> RollbackResponse:
    """Restore strategy params and config from a saved run."""
```

**Error mapping:**

| Exception | HTTP status |
|-----------|-------------|
| `FileNotFoundError` | 404 |
| `ValueError` | 422 |
| Any other `Exception` | 500 |

`RollbackServiceDep` is added to `dependencies.py`:

```python
@lru_cache
def get_rollback_service() -> RollbackService:
    return RollbackService()

RollbackServiceDep = Annotated[RollbackService, Depends(get_rollback_service)]
```

### 4. ProcessOutputBus (`app/web/process_output_bus.py`)

A thread-safe bridge between `ProcessService` callbacks (running in a background thread) and
the asyncio event loop that drives the SSE endpoint.

```python
class ProcessOutputBus:
    """
    Thread-safe bridge: background thread → asyncio SSE generator.

    Usage:
        bus = ProcessOutputBus()

        # In route handler (asyncio thread):
        process_service.execute_command(
            command=cmd,
            on_output=bus.push_line,
            on_error=bus.push_line,
            on_finished=bus.push_finished,
        )

        # In SSE generator (asyncio):
        async for event in bus.stream():
            yield event
    """

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue: Optional[asyncio.Queue] = None
        self._finished: bool = False
        self._exit_code: Optional[int] = None
        self._lock = threading.Lock()

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind to the running event loop. Called once from the SSE endpoint."""
        self._loop = loop
        self._queue = asyncio.Queue()
        self._finished = False

    def push_line(self, line: str) -> None:
        """Called from background thread — thread-safe."""
        if self._loop and self._queue:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, ("line", line))

    def push_finished(self, exit_code: int) -> None:
        """Called from background thread when process exits — thread-safe."""
        if self._loop and self._queue:
            self._loop.call_soon_threadsafe(
                self._queue.put_nowait, ("finished", exit_code)
            )

    async def stream(self):
        """Async generator consumed by the SSE endpoint."""
        if self._queue is None:
            yield {"event": "status", "data": '{"status": "idle"}'}
            return
        while True:
            kind, payload = await self._queue.get()
            if kind == "line":
                yield {"event": "output", "data": payload.rstrip("\n")}
            elif kind == "finished":
                yield {
                    "event": "complete",
                    "data": f'{{"exit_code": {payload}}}',
                }
                break
```

**Singleton in `dependencies.py`:**

```python
@lru_cache
def get_process_output_bus() -> ProcessOutputBus:
    return ProcessOutputBus()

ProcessOutputBusDep = Annotated[ProcessOutputBus, Depends(get_process_output_bus)]
```

**Updated `process.py` SSE endpoint:**

```python
@router.get("/process/stream")
async def stream_process_output(bus: ProcessOutputBusDep):
    loop = asyncio.get_event_loop()
    bus.attach(loop)
    return EventSourceResponse(bus.stream())
```

**Updated `backtest.py` and `optimize.py` callbacks:**

```python
# Replace lambda line: None with:
on_output=bus.push_line,
on_error=bus.push_line,
on_finished=bus.push_finished,
```

Both route handlers receive `bus: ProcessOutputBusDep` via dependency injection.

---

## Data Models

### RollbackResult (internal dataclass)

```python
@dataclass
class RollbackResult:
    success: bool
    rolled_back_to: str
    strategy_name: str
    params_restored: bool
    config_restored: bool
    error: Optional[str] = None
```

### RollbackResponse (Pydantic — already in `models.py`)

```python
class RollbackResponse(BaseModel):
    success: bool
    message: str
    rollback_to_run_id: str
    strategy_name: str
```

### ArchRule / Violation (internal dataclasses in `tests/test_architecture.py`)

```python
@dataclass
class ArchRule:
    name: str
    scan_dir: str
    forbidden_patterns: list[str]

@dataclass
class Violation:
    rule_name: str
    file_path: str
    line_number: int
    line_text: str
```

### ProcessOutputBus (no Pydantic — internal state class)

Holds an `asyncio.Queue[tuple[str, Any]]` where the first element is the event kind
(`"line"` or `"finished"`) and the second is the payload.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions
of a system — essentially, a formal statement about what the system should do. Properties
serve as the bridge between human-readable specifications and machine-verifiable correctness
guarantees.*

### Property 1: Linter detects forbidden imports

*For any* Python source string containing a line that matches a forbidden import pattern
(e.g., `import PySide6`, `from app.ui`), the linter's `scan_for_violations` function SHALL
return at least one `Violation` whose `line_text` contains that import.

**Validates: Requirements 1.1, 2.1, 7.3**

---

### Property 2: Linter passes on clean files

*For any* set of Python source files that contain no lines matching any forbidden import
pattern, `scan_for_violations` SHALL return an empty list.

**Validates: Requirements 1.7, 7.5**

---

### Property 3: All violations are reported in a single pass

*For any* set of Python files containing N lines that each match a forbidden import pattern
(N ≥ 1), `scan_for_violations` SHALL return exactly N `Violation` objects — one per
offending line — without stopping at the first match.

**Validates: Requirements 7.4**

---

### Property 4: Violation report contains path, line number, and import text

*For any* Python source file containing a forbidden import at line L, the `Violation`
returned by `scan_for_violations` SHALL have a non-empty `file_path`, a `line_number` equal
to L, and a `line_text` that contains the exact forbidden import string.

**Validates: Requirements 1.2, 2.2**

---

### Property 5: Rollback file fidelity

*For any* run directory containing a `params.json` and/or `config.snapshot.json` with
arbitrary valid JSON content, after calling `RollbackService.rollback`, the content of the
target files SHALL be byte-for-byte identical to the content of the source files in the run
directory.

**Validates: Requirements 5.7**

---

### Property 6: Settings merge preserves unchanged fields

*For any* `AppSettings` object S and any partial `SettingsUpdate` U that sets a non-empty
subset of fields, the merged settings object SHALL have the updated fields equal to U's
values and all other fields equal to S's original values.

**Validates: Requirements 6.2**

---

### Property 7: Settings serialization round-trip

*For any* valid `AppSettings` object, serializing it to a JSON dict via `model_dump()` and
then constructing a new `AppSettings` from that dict SHALL produce an object equal to the
original.

**Validates: Requirements 6.5**

---

### Property 8: SSE delivers correct exit code

*For any* integer exit code E produced by a subprocess, the final SSE event emitted by
`ProcessOutputBus.stream()` SHALL be of kind `"complete"` and its data payload SHALL contain
the integer E.

**Validates: Requirements 4.3**

---

## Error Handling

### Architecture Linter

- File read errors (permissions, encoding) are caught per-file; the file is skipped with a
  warning and scanning continues. This prevents a single unreadable file from masking other
  violations.
- If `scan_dir` does not exist, the rule is skipped with a warning (not a test failure).

### RollbackService

| Condition | Behaviour |
|-----------|-----------|
| `run_dir` does not exist | Raise `FileNotFoundError` |
| `params.json` missing | Log warning, set `params_restored=False`, continue |
| `config.snapshot.json` missing | Log warning, set `config_restored=False`, continue |
| Neither file present | Raise `ValueError("No restorable files found in run directory")` |
| Atomic write fails | Propagate `OSError` to caller |

### Rollback API Endpoint

```python
try:
    result = rollback_service.rollback(run_dir, user_data_path, strategy)
except FileNotFoundError as e:
    raise HTTPException(status_code=404, detail=str(e))
except ValueError as e:
    raise HTTPException(status_code=422, detail=str(e))
except Exception as e:
    _log.error("Rollback failed: %s", e, exc_info=True)
    raise HTTPException(status_code=500, detail=f"Rollback failed: {e}")
```

### ProcessOutputBus

- If `attach()` has not been called before `push_line` / `push_finished`, calls are silently
  dropped (the process is running but no SSE client is connected).
- If the SSE client disconnects mid-stream, `asyncio.CancelledError` propagates out of
  `stream()` naturally; the background thread continues running until the process exits.
- The bus is a singleton per FastAPI app lifetime. A new `attach()` call resets the queue
  for the next process run.

---

## Testing Strategy

### Unit Tests (example-based)

- `tests/test_architecture.py` — the linter itself (doubles as CI enforcement).
- `tests/test_rollback_service.py` — unit tests for `RollbackService.rollback`:
  - Happy path: both files present → both restored.
  - Missing `params.json` → `params_restored=False`, config still restored.
  - Missing `config.snapshot.json` → `config_restored=False`, params still restored.
  - Neither file present → `ValueError`.
  - Non-existent `run_dir` → `FileNotFoundError`.
- `tests/test_process_output_bus.py` — unit tests for `ProcessOutputBus`:
  - Lines pushed from a thread appear in `stream()` in order.
  - `push_finished` terminates the stream with the correct exit code.
  - Calling `push_line` before `attach()` does not raise.
- `tests/test_web_routes.py` — FastAPI `TestClient` tests:
  - `POST /api/runs/{strategy}/{run_id}/rollback` → 200, 404, 500.
  - `GET /api/process/stream` → SSE content-type header.
  - `GET /api/settings` → 200 with `SettingsResponse` shape.
  - `PUT /api/settings` → 200 with merged values.

### Property-Based Tests (Hypothesis)

Property tests use [Hypothesis](https://hypothesis.readthedocs.io/) with `@settings(max_examples=100)`.

Each test is tagged with a comment referencing the design property it validates:
`# Feature: web-layer-architecture, Property N: <property_text>`

**Property 1 — Linter detects forbidden imports:**

```python
@given(
    pattern=st.sampled_from(["import PySide6", "from PySide6 import", "from app.ui import"]),
    prefix=st.text(alphabet=st.characters(whitelist_categories=("Zs",)), max_size=4),
)
def test_linter_detects_forbidden_import(pattern, prefix):
    # Feature: web-layer-architecture, Property 1: linter detects forbidden imports
    source = f"{prefix}{pattern} Something\n"
    violations = _scan_source(source, RULES[0].forbidden_patterns)
    assert len(violations) >= 1
```

**Property 2 — Linter passes on clean files:**

```python
@given(st.lists(st.text(alphabet=st.characters(blacklist_characters="\x00")), max_size=20))
def test_linter_clean_on_safe_lines(lines):
    # Feature: web-layer-architecture, Property 2: linter passes on clean files
    source = "\n".join(l for l in lines if not any(
        re.search(p, l) for p in ALL_FORBIDDEN_PATTERNS
    ))
    violations = _scan_source(source, ALL_FORBIDDEN_PATTERNS)
    assert violations == []
```

**Property 3 — All violations reported:**

```python
@given(st.integers(min_value=1, max_value=10))
def test_linter_reports_all_violations(n):
    # Feature: web-layer-architecture, Property 3: all violations reported in single pass
    lines = [f"import PySide6.module{i}" for i in range(n)]
    source = "\n".join(lines)
    violations = _scan_source(source, [r"^\s*(import|from)\s+PySide6"])
    assert len(violations) == n
```

**Property 4 — Violation report structure:**

```python
@given(
    line_number=st.integers(min_value=1, max_value=500),
    import_text=st.sampled_from(["import PySide6", "from PySide6.QtCore import Signal"]),
)
def test_violation_report_structure(tmp_path, line_number, import_text):
    # Feature: web-layer-architecture, Property 4: violation report contains path, line, text
    lines = ["# safe line\n"] * (line_number - 1) + [import_text + "\n"]
    f = tmp_path / "test_module.py"
    f.write_text("".join(lines))
    violations = scan_for_violations(RULES[:1], tmp_path)
    assert len(violations) == 1
    v = violations[0]
    assert v.file_path != ""
    assert v.line_number == line_number
    assert import_text.strip() in v.line_text
```

**Property 5 — Rollback file fidelity:**

```python
@given(
    params=st.dictionaries(st.text(min_size=1, max_size=20), st.integers()),
    config=st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50)),
)
def test_rollback_file_fidelity(tmp_path, params, config):
    # Feature: web-layer-architecture, Property 5: rollback file fidelity
    run_dir = tmp_path / "run_2024-01-01_abc123"
    run_dir.mkdir()
    write_json_file_atomic(run_dir / "params.json", params)
    write_json_file_atomic(run_dir / "config.snapshot.json", config)

    user_data = tmp_path / "user_data"
    (user_data / "strategies").mkdir(parents=True)

    svc = RollbackService()
    result = svc.rollback(run_dir, user_data, "MyStrategy")

    assert result.success
    restored_params = parse_json_file(user_data / "strategies" / "MyStrategy.json")
    restored_config = parse_json_file(user_data / "config.json")
    assert restored_params == params
    assert restored_config == config
```

**Property 6 — Settings merge preserves unchanged fields:**

```python
@given(
    base=st.builds(AppSettings),
    new_user_data=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
)
def test_settings_merge_preserves_unchanged(base, new_user_data):
    # Feature: web-layer-architecture, Property 6: settings merge preserves unchanged fields
    update = SettingsUpdate(user_data_path=new_user_data)
    merged = _apply_settings_update(base, update)
    if new_user_data is not None:
        assert merged.user_data_path == new_user_data
    else:
        assert merged.user_data_path == base.user_data_path
    # All other fields unchanged
    assert merged.venv_path == base.venv_path
    assert merged.python_executable == base.python_executable
```

**Property 7 — Settings serialization round-trip:**

```python
@given(st.builds(AppSettings))
def test_settings_round_trip(settings):
    # Feature: web-layer-architecture, Property 7: settings serialization round-trip
    data = settings.model_dump()
    restored = AppSettings(**data)
    assert restored == settings
```

**Property 8 — SSE delivers correct exit code:**

```python
@given(st.integers(min_value=-255, max_value=255))
async def test_sse_exit_code(exit_code):
    # Feature: web-layer-architecture, Property 8: SSE delivers correct exit code
    bus = ProcessOutputBus()
    loop = asyncio.get_event_loop()
    bus.attach(loop)
    bus.push_finished(exit_code)

    events = []
    async for event in bus.stream():
        events.append(event)

    assert events[-1]["event"] == "complete"
    assert str(exit_code) in events[-1]["data"]
```

---

## File-Level Change Summary

### New Files

| File | Purpose |
|------|---------|
| `app/core/services/rollback_service.py` | `RollbackService` + `RollbackResult` dataclass |
| `app/web/process_output_bus.py` | `ProcessOutputBus` — thread-safe SSE bridge |
| `tests/test_architecture.py` | Architecture linter + pytest enforcement |

### Modified Files

| File | Change |
|------|--------|
| `app/web/dependencies.py` | Add `get_rollback_service()`, `get_process_output_bus()`, and their `Dep` type aliases |
| `app/web/api/routes/runs.py` | Add `POST /api/runs/{strategy}/{run_id}/rollback` endpoint |
| `app/web/api/routes/process.py` | Replace global queue with `ProcessOutputBus`; wire `attach()` in SSE endpoint |
| `app/web/api/routes/backtest.py` | Replace `lambda line: None` callbacks with `bus.push_line` / `bus.push_finished` |
| `app/web/api/routes/optimize.py` | Replace `lambda line: None` callbacks with `bus.push_line` / `bus.push_finished` |

### Files to Verify / Remove

| File | Action |
|------|--------|
| `app/core/ai/runtime/conversation_runtime.py` | Verify absent or confirm it has no PySide6 imports; remove if it is a stale Qt version |
