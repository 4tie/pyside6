# Implementation Plan: ProcessRunManager

## Overview

Introduce a `ProcessRunManager` — a pure-Python, framework-agnostic run registry — to replace
the per-page `ProcessService` singleton pattern. The migration is incremental: a backward-compat
shim keeps `ProcessService` working throughout so pages can be migrated one at a time.

Implementation order follows the property-based testing methodology: exploration/construction
property tests first, then core implementation, then fix-checking and preservation tests, then
page migrations.

---

## Tasks

- [x] 1. Define `RunStatus` enum and `ProcessRun` dataclass in `app/core/models/run_models.py`
  - Create `app/core/models/run_models.py` with `RunStatus(str, Enum)` defining exactly:
    `PENDING`, `RUNNING`, `FINISHED`, `FAILED`, `CANCELLED`
  - Define `ProcessRun` as a `@dataclass` with fields: `command: list[str]`, `cwd: Optional[str]`,
    `run_id: str` (default `uuid4()`), `status: RunStatus` (default `PENDING`),
    `started_at: Optional[datetime]`, `finished_at: Optional[datetime]`,
    `exit_code: Optional[int]`, `stdout_queue: queue.Queue`, `stderr_queue: queue.Queue`,
    `stdout_buffer: list[str]`, `stderr_buffer: list[str]`
  - Use `field(default_factory=...)` for mutable defaults; annotate queues as `queue.Queue`
    (not `queue.Queue[str]`) for Python 3.9 compatibility
  - Add module-level `_log = get_logger("core.run_models")`
  - Do NOT import PySide6, fastapi, or starlette
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 1.1 Write property test for `ProcessRun` construction invariants (Property 1)
    - **Property 1: ProcessRun construction invariants**
    - Use `@given(command=st.lists(st.text(min_size=1), min_size=1), cwd=st.one_of(st.none(), st.text(min_size=1)))`
    - Assert: `run_id` is a non-empty string matching UUID4 format, `status == RunStatus.PENDING`,
      `started_at is None`, `finished_at is None`, `exit_code is None`,
      `stdout_buffer == []`, `stderr_buffer == []`
    - File: `tests/core/models/test_run_models_properties.py`
    - **Validates: Requirements 1.2, 1.3**

  - [x] 1.2 Write property test for `run_id` uniqueness (Property 2)
    - **Property 2: run_id uniqueness**
    - Use `@given(st.lists(st.lists(st.text(min_size=1), min_size=1), min_size=2, max_size=20))`
    - Construct N independent `ProcessRun` instances; assert all `run_id` values are distinct
    - File: `tests/core/models/test_run_models_properties.py`
    - **Validates: Requirements 1.2**

- [x] 2. Implement `ProcessRunManager` in `app/core/services/process_run_manager.py`
  - Create `app/core/services/process_run_manager.py`
  - Implement `ProcessRunManager.__init__(self, on_run_finished: Optional[Callable[[ProcessRun], None]] = None)`
    with `_runs: dict[str, ProcessRun]`, `_processes: dict[str, subprocess.Popen]`,
    `_lock: threading.Lock`, `_on_run_finished` attribute
  - Implement `start_run(command: RunCommand) -> ProcessRun`:
    - Raise `ValueError` if `command.as_list()` is empty
    - Create `ProcessRun`, set `status = RUNNING`, `started_at = datetime.utcnow()`
    - Register in `_runs` and `_processes` under `_lock`
    - Launch `subprocess.Popen` with `stdout=PIPE`, `stderr=PIPE`, `stdin=PIPE`, `text=True`, `bufsize=1`
    - On `FileNotFoundError` or `OSError`: set run to `FAILED`, `exit_code = -1`, re-raise as `ValueError`
    - Start two daemon reader threads (stdout, stderr) that append to queue + buffer
    - Start a daemon waiter thread that sets `FINISHED`/`FAILED` status and calls `_on_run_finished`
  - Implement `stop_run(run_id: str) -> None`:
    - Raise `KeyError` if not registered; raise `ValueError` if status is not `RUNNING`
    - `SIGTERM` → wait 3 s → `SIGKILL`; set `status = CANCELLED` under `_lock`
    - Call `_on_run_finished` if set
  - Implement `get_run(run_id: str) -> ProcessRun`: raise `KeyError` if not found
  - Implement `list_runs(status: Optional[RunStatus] = None) -> list[ProcessRun]`:
    return all runs in insertion order, optionally filtered by status
  - Add `_log = get_logger("services.process_run_manager")`
  - Do NOT import PySide6, fastapi, or starlette
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 3.1, 3.2, 3.3, 3.4, 3.5, 6.1, 6.2, 6.3, 6.4, 8.1, 8.2, 8.3, 8.4_

  - [x] 2.1 Write property test for `stop_run` on non-RUNNING run raises `ValueError` (Property 4)
    - **Property 4: stop_run on non-RUNNING run raises ValueError**
    - Use `@given(st.sampled_from([RunStatus.PENDING, RunStatus.FINISHED, RunStatus.FAILED, RunStatus.CANCELLED]))`
    - Construct a `ProcessRun` and manually set its status to the sampled non-RUNNING value;
      register it in a manager; assert `stop_run` raises `ValueError`
    - File: `tests/core/services/test_process_run_manager_properties.py`
    - **Validates: Requirements 2.5**

  - [x] 2.2 Write property test for `get_run` with unknown id raises `KeyError` (Property 7)
    - **Property 7: get_run with unknown id raises KeyError**
    - Use `@given(st.text(min_size=1))` for arbitrary strings not returned by `start_run`
    - Assert `manager.get_run(arbitrary_id)` raises `KeyError`
    - File: `tests/core/services/test_process_run_manager_properties.py`
    - **Validates: Requirements 2.9**

  - [x] 2.3 Write property test for `list_runs` ordering and status filtering (Property 8)
    - **Property 8: list_runs preserves creation order and supports status filtering**
    - Use `@given(st.lists(st.sampled_from(list(RunStatus)), min_size=1, max_size=10))`
    - Construct N `ProcessRun` instances with varying statuses, register them in a manager
      (without launching real subprocesses — inject directly into `_runs`);
      assert `list_runs()` returns them in insertion order;
      assert `list_runs(status=S)` returns exactly the subset with `status == S`
    - File: `tests/core/services/test_process_run_manager_properties.py`
    - **Validates: Requirements 2.10, 8.1, 8.2**

  - [x] 2.4 Write unit tests for `ProcessRunManager` lifecycle with real subprocesses
    - Test `start_run` → status is `RUNNING`, `started_at` is set, run retrievable via `get_run`
      (Property 3 — validates Requirements 2.1, 2.2, 2.8)
    - Test exit code 0 → status becomes `FINISHED`, `exit_code == 0`, `finished_at` set
      (Property 5 — validates Requirements 2.6)
    - Test non-zero exit → status becomes `FAILED`, `exit_code` matches
      (Property 5 — validates Requirements 2.7)
    - Test `stop_run` on running process → status becomes `CANCELLED`
      (validates Requirements 2.3, 2.4)
    - Test `get_run` round-trip after terminal state (Property 6 — validates Requirements 2.8, 8.3)
    - Test `on_run_finished` callback invoked exactly once per terminal transition
      (Property 10 — validates Requirements 6.4)
    - Use short-lived `python -c "..."` subprocesses; wait with `time.sleep` + polling
    - File: `tests/core/services/test_process_run_manager.py`

  - [x] 2.5 Write unit test for stdout/stderr buffer accumulation (Property 9)
    - Launch a subprocess that prints N known lines to stdout and M to stderr
    - After run reaches terminal state, assert `stdout_buffer` contains exactly those N lines
      and `stderr_buffer` contains exactly those M lines in order
    - **Property 9: stdout/stderr output accumulates in buffer**
    - **Validates: Requirements 3.1, 3.2, 3.4, 3.5**
    - File: `tests/core/services/test_process_run_manager.py`

- [x] 3. Checkpoint — core model and manager tests pass
  - Ensure all tests in `tests/core/models/` and `tests/core/services/` pass, ask the user if questions arise.

- [x] 4. Update `ProcessService` backward-compat shim in `app/core/services/process_service.py`
  - Add `_manager: ProcessRunManager` instance attribute (created in `__init__`)
  - Add `_current_run_id: Optional[str]` instance attribute
  - Implement a private `_ShimAdapter` helper class (inner class or module-level) that reads
    from a `ProcessRun`'s queues on daemon threads and calls `on_output`, `on_error`,
    `on_finished` callbacks directly — no Qt dependency
  - Replace `execute_command` body: build a `RunCommand` from `command` + `working_directory`,
    call `_manager.start_run()`, store `_current_run_id`, wire callbacks via `_ShimAdapter`
  - Replace `stop_process` body: call `_manager.stop_run(_current_run_id)` if set and running
  - Replace `get_full_output` body: return buffers from `_manager.get_run(_current_run_id)`
  - Replace `is_running` body: check `_manager.get_run(_current_run_id).status == RUNNING`
  - Keep `build_environment` static method completely unchanged
  - Keep all existing public method signatures unchanged (same parameters, same return types)
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 4.1 Write property test for `ProcessService.execute_command` delegation round-trip (Property 11)
    - **Property 11: ProcessService.execute_command delegation round-trip**
    - Use `@given(st.lists(st.text(min_size=1), min_size=1, max_size=5))` for command args
    - Call `ProcessService.execute_command` with a short-lived `python -c "print('x')"` command
      and capture callbacks; assert the manager registered a new run and callbacks received
      the same data as `stdout_buffer`/`stderr_buffer`/`exit_code`
    - File: `tests/core/services/test_process_service_shim.py`
    - **Validates: Requirements 7.2, 7.3**

  - [x] 4.2 Write smoke tests for framework independence
    - Import `ProcessRunManager` and `ProcessRun`; assert `"PySide6"`, `"fastapi"`, `"starlette"`
      are NOT in `sys.modules` after import
    - Import `ProcessService`; verify importable without Qt application
    - Instantiate `ProcessRunManager()` without a Qt application; assert no exception
    - File: `tests/core/services/test_smoke.py`
    - **Validates: Requirements 6.1, 6.2, 6.3**

- [x] 5. Checkpoint — shim tests and smoke tests pass
  - Ensure all tests in `tests/core/services/` pass, ask the user if questions arise.

- [x] 6. Implement `ProcessRunAdapter` (Qt desktop adapter) in `app/ui/adapters/process_run_adapter.py`
  - Create `app/ui/adapters/` directory and `app/ui/adapters/process_run_adapter.py`
  - Implement `ProcessRunAdapter(QObject)` with:
    - Signals: `stdout_received = Signal(str)`, `stderr_received = Signal(str)`, `run_finished = Signal(int)`
    - `__init__(self, run: ProcessRun, parent: QObject | None = None)` — store run reference,
      create `QTimer(self)` with 50 ms interval
    - `start(self) -> None` — connect timer to `_poll` slot, start timer
    - `stop(self) -> None` — stop timer, disconnect
    - `_poll(self)` slot — drain `stdout_queue` emitting `stdout_received`, drain `stderr_queue`
      emitting `stderr_received`; if run status is terminal and both queues empty, emit
      `run_finished(exit_code or -1)` and call `self.stop()`
  - Do NOT add `start_run` / `stop_run` / any subprocess management methods
  - Add `_log = get_logger("ui.adapters.process_run_adapter")`
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 6.1 Write integration tests for `ProcessRunAdapter` signals
    - Requires `QApplication` fixture (session-scoped `pytest-qt` or manual `QApplication`)
    - Test: adapter emits `stdout_received` / `stderr_received` when queue has data
    - Test: adapter emits `run_finished` and stops timer when run reaches terminal state
    - Test: adapter has no `start_run`, `stop_run`, or `execute_command` attributes
    - File: `tests/ui/adapters/test_process_run_adapter.py`
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5**

- [x] 7. Implement Web API router in `app/api/routers/runs_router.py`
  - Create `app/api/` and `app/api/routers/` directories with empty `__init__.py` files
  - Create `app/api/routers/runs_router.py` with:
    - Pydantic models: `RunRequest(BaseModel)` with `command: list[str]`, `cwd: Optional[str]`;
      `RunResponse(BaseModel)` with all `ProcessRun` metadata fields (no queues/buffers);
      `RunOutputResponse(BaseModel)` with `run_id`, `stdout: list[str]`, `stderr: list[str]`
    - `router = APIRouter(prefix="/runs", tags=["runs"])`
    - `POST /runs` → 201, calls `manager.start_run()`, returns `RunResponse`
    - `GET /runs/{run_id}` → 200, returns `RunResponse`; 404 on `KeyError`
    - `DELETE /runs/{run_id}` → 200, calls `manager.stop_run()`, returns `RunResponse`;
      404 on `KeyError`; 409 on `ValueError` (wrong status)
    - `GET /runs/{run_id}/output` → 200, returns `RunOutputResponse` from buffers; 404 on `KeyError`
    - Use `Depends(...)` for manager injection (accept manager as a parameter)
    - Catch `KeyError` → HTTP 404 `{"detail": "Run '<id>' not found"}`
    - Catch `ValueError` from `stop_run` → HTTP 409 `{"detail": "..."}`
  - Add `_log = get_logger("api.runs_router")`
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 7.1 Write property test for Web API 404 on unknown run_id (Property 12)
    - **Property 12: Web API 404 for unknown run_id**
    - Use `@given(st.text(min_size=1).filter(lambda s: s not in registered_ids))`
    - Use FastAPI `TestClient` (no running server needed)
    - Assert `GET /runs/{id}`, `DELETE /runs/{id}`, `GET /runs/{id}/output` all return 404
    - File: `tests/api/test_runs_router_properties.py`
    - **Validates: Requirements 5.5**

  - [x] 7.2 Write integration tests for Web API endpoints
    - `POST /runs` with valid body → 201, `run_id` in response
    - `GET /runs/{run_id}` → 200, all fields present
    - `DELETE /runs/{run_id}` on running run → 200, status `cancelled`
    - `GET /runs/{run_id}/output` → 200, stdout/stderr lists present
    - `DELETE /runs/{run_id}` on finished run → 409
    - Use FastAPI `TestClient`
    - File: `tests/api/test_runs_router.py`
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

- [x] 8. Checkpoint — adapter and API tests pass
  - Ensure all tests in `tests/ui/adapters/` and `tests/api/` pass, ask the user if questions arise.

- [x] 9. Migrate `BacktestPage` to use `ProcessRunManager` + `ProcessRunAdapter`
  - Update `app/ui/pages/backtest_page.py`:
    - Change constructor signature to accept `process_manager: ProcessRunManager` alongside
      `settings_state: SettingsState`
    - Remove `self._process_svc = ProcessService()` instantiation
    - In `_run()`: call `self._process_manager.start_run(cmd)` to get a `ProcessRun`;
      create `ProcessRunAdapter(run, parent=self)` stored as `self._adapter`;
      connect adapter signals to existing `_sig_stdout`, `_sig_stderr`, `_sig_finished` bridge signals;
      call `self._adapter.start()`
    - In `_stop()`: call `self._process_manager.stop_run(self._current_run_id)` instead of
      `self._process_svc.stop_process()`; call `self._adapter.stop()` if adapter exists
    - Store `run.run_id` as `self._current_run_id` for stop/lookup
    - Keep all existing signal bridge pattern (`_sig_stdout`, `_sig_stderr`, `_sig_finished`)
      and `_handle_finished` slot unchanged
  - _Requirements: 4.6_

  - [x] 9.1 Write smoke test for `BacktestPage` instantiation with injected manager
    - Instantiate `BacktestPage` with a mock `SettingsState` and a real `ProcessRunManager`
    - Assert page has no `_process_svc` attribute
    - Assert page has `_process_manager` attribute
    - File: `tests/ui/pages/test_backtest_page_smoke.py`

- [x] 10. Migrate `OptimizePage` to use `ProcessRunManager` + `ProcessRunAdapter`
  - Update `app/ui/pages/optimize_page.py` following the same pattern as task 9:
    - Accept `process_manager: ProcessRunManager` in constructor
    - Remove `ProcessService()` instantiation
    - Use `start_run` + `ProcessRunAdapter` in `_run()`
    - Use `stop_run` in `_stop()`
  - _Requirements: 4.6_

  - [x] 10.1 Write smoke test for `OptimizePage` instantiation with injected manager
    - File: `tests/ui/pages/test_optimize_page_smoke.py`

- [x] 11. Migrate `DownloadDataPage` to use `ProcessRunManager` + `ProcessRunAdapter`
  - Locate the download data page (likely `app/ui/pages/download_data_page.py` or equivalent)
  - Apply the same migration pattern as tasks 9 and 10
  - _Requirements: 4.6_

  - [x] 11.1 Write smoke test for `DownloadDataPage` instantiation with injected manager
    - File: `tests/ui/pages/test_download_data_page_smoke.py`

- [x] 12. Wire `ProcessRunManager` into `MainWindow` and update page construction
  - Update `app/ui/main_window.py`:
    - Instantiate a single `ProcessRunManager()` at `MainWindow.__init__` level
    - Pass the manager instance to `BacktestPage`, `OptimizePage`, and `DownloadDataPage`
      constructors
    - Ensure the manager instance is stored as `self._process_manager` for potential future use
  - _Requirements: 2.1, 4.6_

- [x] 13. Final checkpoint — full test suite passes
  - Run `pytest --tb=short` and ensure all tests pass
  - Run `ruff check .` and `ruff format .` and fix any issues
  - Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Properties 3, 5, 6, 9, 10, 11 involve real subprocess execution and are covered by
  example-based unit tests (task 2.4, 2.5) rather than property tests — subprocess execution
  is too slow for 100-iteration Hypothesis runs
- Properties 1, 2, 4, 7, 8, 12 are covered by Hypothesis property tests
- The `_ShimAdapter` in `ProcessService` must NOT import PySide6 — it calls callbacks directly
  from reader threads (the existing bridge-signal pattern in pages handles thread safety)
- `ProcessRun.stdout_queue` / `stderr_queue` are typed as `queue.Queue` (not `queue.Queue[str]`)
  for Python 3.9 compatibility; use `# type: ignore[assignment]` if mypy complains
- All new modules must declare `_log = get_logger("section.module")` at module level
- `app/ui/adapters/__init__.py` and `app/api/__init__.py` / `app/api/routers/__init__.py`
  must be empty files (project convention)
