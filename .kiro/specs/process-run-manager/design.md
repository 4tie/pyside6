# Design Document: ProcessRunManager

## Overview

The current `ProcessService` is a per-page singleton that holds a single `subprocess.Popen`
reference. Each page (`BacktestPage`, `OptimizePage`, `DownloadPage`) instantiates its own copy,
so there is no shared registry of running processes, no way to look up a past run's output, and
no clean path for a FastAPI web layer to observe or control runs.

This design replaces that pattern with a **ProcessRunManager** — a pure-Python,
framework-agnostic run registry. Each invocation of a freqtrade command produces a `ProcessRun`
record with a unique `run_id`, full lifecycle metadata, and per-run stdout/stderr queues. The
PySide6 desktop UI and the FastAPI web API both consume the same manager; neither layer embeds
subprocess or business logic directly.

The migration is incremental: a backward-compatibility shim keeps `ProcessService` working
throughout the transition so pages can be migrated one at a time.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          UI / API Layer                             │
│                                                                     │
│  ┌──────────────────────┐        ┌──────────────────────────────┐  │
│  │  PySide6 Desktop UI  │        │     FastAPI Web API          │  │
│  │                      │        │                              │  │
│  │  BacktestPage        │        │  POST   /runs                │  │
│  │  OptimizePage        │        │  GET    /runs/{id}           │  │
│  │  DownloadPage        │        │  DELETE /runs/{id}           │  │
│  │        │             │        │  GET    /runs/{id}/output    │  │
│  │  ProcessRunAdapter   │        │        │                     │  │
│  │  (QObject + QTimer)  │        │  RunRouter (FastAPI)         │  │
│  └──────────┬───────────┘        └──────────────┬───────────────┘  │
└─────────────┼────────────────────────────────────┼─────────────────┘
              │  observes                           │  delegates
              ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Core Layer (no framework imports)               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    ProcessRunManager                         │  │
│  │                                                              │  │
│  │  start_run(cmd) → ProcessRun                                 │  │
│  │  stop_run(run_id)                                            │  │
│  │  get_run(run_id) → ProcessRun                                │  │
│  │  list_runs(status?) → list[ProcessRun]                       │  │
│  │                                                              │  │
│  │  _runs: dict[str, ProcessRun]   (insertion-ordered)          │  │
│  │  _on_run_finished: Callable[[ProcessRun], None] | None       │  │
│  └──────────────────────────────┬───────────────────────────────┘  │
│                                 │ creates / manages                 │
│  ┌──────────────────────────────▼───────────────────────────────┐  │
│  │                       ProcessRun                             │  │
│  │                                                              │  │
│  │  run_id: str          status: RunStatus                      │  │
│  │  command: list[str]   cwd: str | None                        │  │
│  │  started_at: datetime finished_at: datetime | None           │  │
│  │  exit_code: int | None                                       │  │
│  │  stdout_queue: Queue[str]   stderr_queue: Queue[str]         │  │
│  │  stdout_buffer: list[str]   stderr_buffer: list[str]         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  ProcessService (backward-compat shim)                       │  │
│  │  Delegates to ProcessRunManager internally                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

**Framework independence via adapters.** `ProcessRunManager` and `ProcessRun` live in
`app/core/services/` with zero imports from PySide6 or FastAPI. Each surface (desktop, web)
provides a thin adapter that translates the manager's queue-based output into its native
notification mechanism (Qt signals vs. HTTP responses).

**Queue + buffer dual output model.** Each run maintains both a `queue.Queue[str]` (for live
streaming to active consumers) and a `list[str]` buffer (for late consumers who need the full
history). This avoids the need for consumers to replay a queue they weren't subscribed to from
the start.

**Insertion-ordered dict for run registry.** Python 3.7+ dicts preserve insertion order, so
`_runs: dict[str, ProcessRun]` gives O(1) lookup by `run_id` and O(n) ordered iteration for
`list_runs()` without a separate ordering structure.

**Graceful shutdown sequence.** `stop_run` sends SIGTERM, waits 3 seconds, then SIGKILL. This
matches the existing `ProcessService.stop_process` behavior but makes the timeout explicit and
sets the `CANCELLED` status atomically after the process exits.

**Backward-compat shim.** `ProcessService` is updated to hold a `ProcessRunManager` instance
and delegate all subprocess work to it. Its public API (`execute_command`, `stop_process`,
`get_full_output`, `is_running`, `build_environment`) is preserved unchanged so existing pages
continue to work without modification during the migration.

---

## Components and Interfaces

### `ProcessRun` (dataclass)

**Location:** `app/core/models/run_models.py`

```python
@dataclass
class ProcessRun:
    command: list[str]
    cwd: Optional[str] = None
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: RunStatus = RunStatus.PENDING
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    stdout_queue: queue.Queue = field(default_factory=queue.Queue)
    stderr_queue: queue.Queue = field(default_factory=queue.Queue)
    stdout_buffer: list[str] = field(default_factory=list)
    stderr_buffer: list[str] = field(default_factory=list)
```

The `subprocess.Popen` handle is stored on the manager, not on `ProcessRun`, keeping the
public model clean. `stdout_queue` and `stderr_queue` are typed as `queue.Queue[str]` at
runtime; the generic annotation is `queue.Queue` for Python 3.9 compatibility.

### `RunStatus` (enum)

**Location:** `app/core/models/run_models.py`

```python
class RunStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    FINISHED  = "finished"
    FAILED    = "failed"
    CANCELLED = "cancelled"
```

Using `str` as a mixin makes the enum JSON-serializable without a custom encoder, which
simplifies the FastAPI response models.

### `ProcessRunManager`

**Location:** `app/core/services/process_run_manager.py`

```python
class ProcessRunManager:
    def __init__(
        self,
        on_run_finished: Optional[Callable[[ProcessRun], None]] = None,
    ) -> None: ...

    def start_run(self, command: RunCommand) -> ProcessRun: ...
    def stop_run(self, run_id: str) -> None: ...
    def get_run(self, run_id: str) -> ProcessRun: ...
    def list_runs(
        self, status: Optional[RunStatus] = None
    ) -> list[ProcessRun]: ...
```

Internal state:
- `_runs: dict[str, ProcessRun]` — insertion-ordered registry
- `_processes: dict[str, subprocess.Popen]` — Popen handles keyed by run_id (not exposed)
- `_lock: threading.Lock` — guards mutations to `_runs` and `_processes`
- `_on_run_finished: Optional[Callable[[ProcessRun], None]]`

### `ProcessRunAdapter` (Desktop Adapter)

**Location:** `app/ui/adapters/process_run_adapter.py`

```python
class ProcessRunAdapter(QObject):
    stdout_received = Signal(str)
    stderr_received = Signal(str)
    run_finished    = Signal(int)

    def __init__(self, run: ProcessRun, parent: QObject | None = None) -> None: ...
    def start(self) -> None: ...   # starts QTimer polling
    def stop(self) -> None: ...    # stops QTimer, cleans up
```

The adapter holds a reference to the `ProcessRun` and polls its queues via a `QTimer` (default
interval: 50 ms). It does not start or stop the subprocess. When the run reaches a terminal
status and both queues are drained, it emits `run_finished` and stops the timer.

### Web API Router

**Location:** `app/api/routers/runs_router.py`

```python
router = APIRouter(prefix="/runs", tags=["runs"])

@router.post("", response_model=RunResponse, status_code=201)
async def create_run(body: RunRequest, manager: ProcessRunManager = Depends(...)): ...

@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, manager: ProcessRunManager = Depends(...)): ...

@router.delete("/{run_id}", response_model=RunResponse)
async def stop_run(run_id: str, manager: ProcessRunManager = Depends(...)): ...

@router.get("/{run_id}/output", response_model=RunOutputResponse)
async def get_output(run_id: str, manager: ProcessRunManager = Depends(...)): ...
```

Pydantic request/response models:

```python
class RunRequest(BaseModel):
    command: list[str]
    cwd: Optional[str] = None

class RunResponse(BaseModel):
    run_id: str
    status: RunStatus
    command: list[str]
    cwd: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    exit_code: Optional[int]

class RunOutputResponse(BaseModel):
    run_id: str
    stdout: list[str]
    stderr: list[str]
```

### `ProcessService` (Backward-Compat Shim)

**Location:** `app/core/services/process_service.py` (updated in-place)

The class gains a `_manager: ProcessRunManager` instance attribute and a `_current_run_id:
Optional[str]` to track the most recent run. All subprocess logic is removed; `execute_command`
builds a `RunCommand`, calls `_manager.start_run()`, and wires the callbacks via a
`_ShimAdapter` helper (a lightweight non-Qt version of `ProcessRunAdapter` that calls the
callbacks directly from the reader threads). `build_environment` is unchanged.

---

## Data Models

### `ProcessRun` field summary

| Field | Type | Default | Notes |
|---|---|---|---|
| `run_id` | `str` | `uuid4()` | UUID4 string, immutable after creation |
| `status` | `RunStatus` | `PENDING` | Mutated by manager only |
| `command` | `list[str]` | required | Tokenized command |
| `cwd` | `Optional[str]` | `None` | Working directory |
| `started_at` | `Optional[datetime]` | `None` | UTC, set on `start_run` |
| `finished_at` | `Optional[datetime]` | `None` | UTC, set on exit |
| `exit_code` | `Optional[int]` | `None` | Set on exit |
| `stdout_queue` | `queue.Queue[str]` | `Queue()` | Live streaming |
| `stderr_queue` | `queue.Queue[str]` | `Queue()` | Live streaming |
| `stdout_buffer` | `list[str]` | `[]` | Full history |
| `stderr_buffer` | `list[str]` | `[]` | Full history |

### `RunStatus` state machine

```
PENDING ──start_run()──► RUNNING ──exit 0──► FINISHED
                              │
                              ├──exit ≠ 0──► FAILED
                              │
                              └──stop_run()──► CANCELLED
```

`FINISHED`, `FAILED`, and `CANCELLED` are terminal states. No transitions out of them.

### Thread-safety model

`ProcessRun` fields that are mutated after construction (`status`, `started_at`, `finished_at`,
`exit_code`) are mutated only by the manager under `_lock`. The `stdout_buffer` and
`stderr_buffer` lists are appended to by the reader threads; since CPython's GIL makes list
`append` atomic, no additional lock is needed for the buffer. The queues are inherently
thread-safe.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of
a system — essentially, a formal statement about what the system should do. Properties serve as
the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: ProcessRun construction invariants

*For any* non-empty command list and optional cwd string, a newly constructed `ProcessRun` SHALL
have a non-empty UUID4 `run_id`, `status == RunStatus.PENDING`, and all optional fields set to
`None` or their zero value.

**Validates: Requirements 1.2, 1.3**

### Property 2: run_id uniqueness

*For any* collection of `ProcessRun` instances constructed independently, all `run_id` values
SHALL be distinct.

**Validates: Requirements 1.2**

### Property 3: start_run returns a registered RUNNING run

*For any* valid `RunCommand`, calling `start_run` SHALL return a `ProcessRun` whose `run_id` is
retrievable via `get_run`, whose `status` is `RunStatus.RUNNING`, and whose `started_at` is not
`None`.

**Validates: Requirements 2.1, 2.2, 2.8**

### Property 4: stop_run on non-RUNNING run raises ValueError

*For any* `ProcessRun` whose `status` is not `RunStatus.RUNNING` (i.e., `PENDING`, `FINISHED`,
`FAILED`, or `CANCELLED`), calling `stop_run` with that run's `run_id` SHALL raise `ValueError`.

**Validates: Requirements 2.5**

### Property 5: exit code determines terminal status

*For any* subprocess that exits with return code 0, the corresponding `ProcessRun.status` SHALL
become `RunStatus.FINISHED` and `exit_code` SHALL be 0. *For any* subprocess that exits with a
non-zero return code N, `status` SHALL become `RunStatus.FAILED` and `exit_code` SHALL equal N.

**Validates: Requirements 2.6, 2.7**

### Property 6: get_run round-trip

*For any* `run_id` returned by `start_run`, calling `get_run(run_id)` SHALL return the same
`ProcessRun` object regardless of the run's current status (including after it has reached a
terminal state).

**Validates: Requirements 2.8, 8.3**

### Property 7: get_run with unknown id raises KeyError

*For any* string that was not returned by `start_run`, calling `get_run` with that string SHALL
raise `KeyError`.

**Validates: Requirements 2.9**

### Property 8: list_runs preserves creation order and supports status filtering

*For any* sequence of `start_run` calls, `list_runs()` SHALL return all runs in the order they
were created. *For any* `RunStatus` value S, `list_runs(status=S)` SHALL return exactly the
subset of runs whose `status == S`, in creation order.

**Validates: Requirements 2.10, 8.1, 8.2**

### Property 9: stdout/stderr output accumulates in buffer

*For any* subprocess that produces N lines on stdout and M lines on stderr, after the run
reaches a terminal state, `ProcessRun.stdout_buffer` SHALL contain exactly those N lines and
`ProcessRun.stderr_buffer` SHALL contain exactly those M lines, in the order they were produced.

**Validates: Requirements 3.1, 3.2, 3.4, 3.5**

### Property 10: on_run_finished callback is invoked for every terminal transition

*For any* `ProcessRunManager` constructed with an `on_run_finished` callback, and *for any* run
that reaches a terminal state (`FINISHED`, `FAILED`, or `CANCELLED`), the callback SHALL be
called exactly once with the corresponding `ProcessRun`.

**Validates: Requirements 6.4**

### Property 11: ProcessService.execute_command delegation round-trip

*For any* command sequence and callbacks passed to `ProcessService.execute_command`, the
underlying `ProcessRunManager` SHALL register a new run, and the `on_output`, `on_error`, and
`on_finished` callbacks SHALL be invoked with the same data that appears in the run's
`stdout_buffer`, `stderr_buffer`, and `exit_code`.

**Validates: Requirements 7.2, 7.3**

### Property 12: Web API 404 for unknown run_id

*For any* string that is not a registered `run_id`, all four web endpoints (`GET /runs/{id}`,
`DELETE /runs/{id}`, `GET /runs/{id}/output`) SHALL return HTTP 404.

**Validates: Requirements 5.5**

---

## Error Handling

### `ProcessRunManager.start_run`

- Raises `ValueError` if `command.as_list()` is empty.
- If `subprocess.Popen` raises `FileNotFoundError` (executable not found), the run is
  immediately set to `FAILED` with `exit_code = -1` and the exception is re-raised as
  `ValueError` with a descriptive message.
- If `Popen` raises any other `OSError`, same treatment.

### `ProcessRunManager.stop_run`

- Raises `KeyError` if `run_id` is not registered.
- Raises `ValueError` if the run is not in `RUNNING` state (message includes current status).
- If `SIGTERM` + 3-second wait + `SIGKILL` all fail (e.g., permission error), logs the error
  and sets status to `FAILED` rather than leaving it in `RUNNING`.

### `ProcessRunManager.get_run`

- Raises `KeyError` if `run_id` is not registered.

### Web API error responses

All `KeyError` from the manager are caught by the router and converted to HTTP 404:

```json
{"detail": "Run '<run_id>' not found"}
```

`ValueError` from `stop_run` (wrong status) is converted to HTTP 409 Conflict:

```json
{"detail": "Run '<run_id>' is not running (status: finished)"}
```

### Reader thread errors

If a reader thread encounters an unexpected exception while reading from a pipe, it logs the
error at `ERROR` level and puts a sentinel line `"[output reader error: <msg>]"` into the
queue/buffer so the consumer is aware something went wrong. The run is then marked `FAILED`.

---

## Testing Strategy

### Unit tests (pytest, no Qt, no HTTP server)

These tests exercise `ProcessRunManager` and `ProcessRun` in isolation using real subprocesses
(short-lived `python -c "..."` commands) or mocked `Popen` objects.

- Construction invariants: verify `run_id` format, initial `status`, default field values.
- Lifecycle: `start_run` → `RUNNING`, exit 0 → `FINISHED`, exit 1 → `FAILED`.
- `stop_run` on running process → `CANCELLED`.
- `stop_run` on non-running process → `ValueError`.
- `get_run` round-trip; `get_run` with unknown id → `KeyError`.
- `list_runs` ordering; `list_runs(status=...)` filtering.
- Buffer accumulation: verify all lines appear in `stdout_buffer`/`stderr_buffer` after exit.
- `on_run_finished` callback invocation.
- `ProcessService` shim: verify callbacks fire and a run appears in the manager.

### Property-based tests (Hypothesis, minimum 100 iterations each)

The project already uses Hypothesis (`.hypothesis/` directory present). Each property test is
tagged with a comment referencing the design property.

```python
# Feature: process-run-manager, Property 1: ProcessRun construction invariants
@given(
    command=st.lists(st.text(min_size=1), min_size=1, max_size=10),
    cwd=st.one_of(st.none(), st.text(min_size=1)),
)
@settings(max_examples=100)
def test_process_run_construction_invariants(command, cwd): ...
```

Properties covered by Hypothesis tests:
- **Property 1** — construction invariants (UUID4 format, PENDING status, None defaults)
- **Property 2** — run_id uniqueness across independently constructed instances
- **Property 4** — `stop_run` raises `ValueError` for non-RUNNING statuses
- **Property 7** — `get_run` raises `KeyError` for unregistered ids
- **Property 8** — `list_runs` ordering and status filtering
- **Property 12** — Web API 404 for unknown run_ids (via FastAPI `TestClient`)

Properties 3, 5, 6, 9, 10, 11 involve real subprocess execution and are covered by
example-based unit tests (subprocess execution is too slow for 100-iteration property tests;
mocked Popen is used where iteration count matters).

### Integration tests (Qt adapter)

Require a `QApplication` instance (use `pytest-qt` or a session-scoped fixture):

- `ProcessRunAdapter` emits `stdout_received` / `stderr_received` signals when queue has data.
- `ProcessRunAdapter` emits `run_finished` and stops timer when run reaches terminal state.
- Verify adapter does not expose any subprocess management methods.

### Integration tests (Web API)

Use FastAPI `TestClient` (synchronous, no running server needed):

- `POST /runs` with valid body → 201, `run_id` returned.
- `GET /runs/{run_id}` → 200, all fields present.
- `DELETE /runs/{run_id}` on running run → 200, status `cancelled`.
- `GET /runs/{run_id}/output` → 200, stdout/stderr lists.
- All endpoints with unknown `run_id` → 404.
- `DELETE /runs/{run_id}` on finished run → 409.

### Smoke tests

- Import `ProcessRunManager` and `ProcessRun`; assert no PySide6/fastapi/starlette in
  `sys.modules` after import.
- Import `ProcessService` from `app.core.services.process_service`; verify it is importable.
- Instantiate `ProcessRunManager` without a Qt application; verify no exception.
