# Requirements Document

## Introduction

The current `ProcessService` is a singleton-style object that holds a single `subprocess.Popen`
reference. Every page (backtest, optimize, download, loop) instantiates its own copy, so there is
no shared registry of what is running, no way to look up a past run's output, and no clean path
for the FastAPI web layer to observe or control runs.

This feature replaces that pattern with a **ProcessRunManager** — a pure-Python, framework-agnostic
run registry. Each invocation of a freqtrade command produces a `ProcessRun` record with a unique
`run_id`, full lifecycle metadata, and per-run stdout/stderr queues. The PySide6 desktop UI and the
FastAPI web API both consume the same manager; neither layer embeds subprocess or business logic
directly.

---

## Glossary

- **ProcessRunManager**: The central service that creates, tracks, and terminates `ProcessRun`
  instances. Lives in `app/core/services/`.
- **ProcessRun**: An immutable-identity record representing one subprocess invocation. Holds all
  metadata and I/O queues for that run.
- **run_id**: A UUID4 string that uniquely identifies a single `ProcessRun` within the manager.
- **RunStatus**: An enumeration of the lifecycle states a `ProcessRun` can occupy:
  `PENDING`, `RUNNING`, `FINISHED`, `FAILED`, `CANCELLED`.
- **stdout_queue / stderr_queue**: Thread-safe `queue.Queue[str]` instances attached to a
  `ProcessRun` that receive line-by-line output from the subprocess.
- **Desktop Adapter**: A thin PySide6 wrapper (`ProcessRunAdapter`) that bridges a `ProcessRun`'s
  queues to Qt signals so UI pages can consume output without touching subprocess logic.
- **Web Adapter**: A thin FastAPI wrapper (route handlers + SSE/polling endpoint) that exposes
  `ProcessRunManager` over HTTP without embedding subprocess logic.
- **RunCommand**: The existing dataclass (`app/core/models/command_models.py`) that carries a
  tokenised command list, `cwd`, and optional environment overrides.

---

## Requirements

### Requirement 1: ProcessRun Data Model

**User Story:** As a developer, I want a structured record for each subprocess invocation, so that
I can inspect its status, output, and metadata at any point during or after execution.

#### Acceptance Criteria

1. THE `ProcessRun` SHALL expose the following fields: `run_id` (str, UUID4), `status`
   (RunStatus), `command` (list[str]), `cwd` (Optional[str]), `started_at` (Optional[datetime]),
   `finished_at` (Optional[datetime]), `exit_code` (Optional[int]), `stdout_queue`
   (queue.Queue[str]), `stderr_queue` (queue.Queue[str]).
2. WHEN a `ProcessRun` is created, THE `ProcessRun` SHALL assign a unique `run_id` via
   `uuid.uuid4()` and set `status` to `RunStatus.PENDING`.
3. THE `ProcessRun` SHALL be constructable with only `command` and optional `cwd`; all other
   fields SHALL default to `None` or their zero value.
4. THE `RunStatus` enumeration SHALL define exactly the values: `PENDING`, `RUNNING`, `FINISHED`,
   `FAILED`, `CANCELLED`.
5. THE `ProcessRun` SHALL NOT expose the raw `subprocess.Popen` object as part of its public
   interface.

---

### Requirement 2: ProcessRunManager Lifecycle

**User Story:** As a developer, I want a single manager that starts, tracks, and stops runs, so
that all subprocess activity is visible from one place regardless of which UI or API layer
initiated it.

#### Acceptance Criteria

1. THE `ProcessRunManager` SHALL provide a `start_run(command: RunCommand) -> ProcessRun` method
   that creates a `ProcessRun`, registers it internally, launches the subprocess, and returns the
   `ProcessRun` to the caller.
2. WHEN `start_run` is called, THE `ProcessRunManager` SHALL set `ProcessRun.status` to
   `RunStatus.RUNNING` and record `started_at` as the current UTC datetime before the subprocess
   first produces output.
3. THE `ProcessRunManager` SHALL provide a `stop_run(run_id: str) -> None` method that terminates
   the subprocess associated with the given `run_id`.
4. WHEN `stop_run` is called on a `RUNNING` run, THE `ProcessRunManager` SHALL attempt a graceful
   `SIGTERM` first, wait up to 3 seconds, then send `SIGKILL` if the process has not exited, and
   set `ProcessRun.status` to `RunStatus.CANCELLED`.
5. WHEN `stop_run` is called on a run that is not in `RUNNING` status, THE `ProcessRunManager`
   SHALL raise `ValueError` with a descriptive message.
6. WHEN a subprocess exits with return code 0, THE `ProcessRunManager` SHALL set
   `ProcessRun.status` to `RunStatus.FINISHED`, record `finished_at`, and set `exit_code` to 0.
7. WHEN a subprocess exits with a non-zero return code, THE `ProcessRunManager` SHALL set
   `ProcessRun.status` to `RunStatus.FAILED`, record `finished_at`, and set `exit_code` to the
   actual return code.
8. THE `ProcessRunManager` SHALL provide a `get_run(run_id: str) -> ProcessRun` method that
   returns the `ProcessRun` for the given `run_id`.
9. WHEN `get_run` is called with an unknown `run_id`, THE `ProcessRunManager` SHALL raise
   `KeyError`.
10. THE `ProcessRunManager` SHALL provide a `list_runs() -> list[ProcessRun]` method that returns
    all registered runs in creation order.

---

### Requirement 3: Per-Run Output Streaming

**User Story:** As a developer, I want each run's stdout and stderr delivered to its own queues,
so that multiple concurrent runs do not mix their output.

#### Acceptance Criteria

1. WHEN a subprocess produces a line on stdout, THE `ProcessRunManager` SHALL place that line into
   the corresponding `ProcessRun.stdout_queue` without blocking the subprocess.
2. WHEN a subprocess produces a line on stderr, THE `ProcessRunManager` SHALL place that line into
   the corresponding `ProcessRun.stderr_queue` without blocking the subprocess.
3. THE `ProcessRunManager` SHALL read stdout and stderr on separate daemon threads so that a slow
   consumer on one stream does not stall the other.
4. WHEN a subprocess exits, THE `ProcessRunManager` SHALL drain any remaining buffered output into
   the queues before marking the run as `FINISHED` or `FAILED`.
5. THE `ProcessRunManager` SHALL also accumulate all stdout lines into `ProcessRun.stdout_buffer`
   (list[str]) and all stderr lines into `ProcessRun.stderr_buffer` (list[str]) so that late
   consumers can read the full history without replaying the queue.

---

### Requirement 4: Desktop Adapter (PySide6)

**User Story:** As a desktop UI developer, I want a thin Qt adapter that bridges a `ProcessRun`'s
queues to Qt signals, so that UI pages receive live output on the main thread without embedding
subprocess logic.

#### Acceptance Criteria

1. THE `ProcessRunAdapter` SHALL be a `QObject` subclass that accepts a `ProcessRun` at
   construction time.
2. THE `ProcessRunAdapter` SHALL declare Qt signals: `stdout_received(str)`,
   `stderr_received(str)`, `run_finished(int)`.
3. WHEN the `ProcessRunAdapter` is started, THE `ProcessRunAdapter` SHALL poll
   `ProcessRun.stdout_queue` and `ProcessRun.stderr_queue` using a `QTimer` and emit the
   corresponding signals on the Qt main thread.
4. WHEN `ProcessRun.status` transitions to `FINISHED`, `FAILED`, or `CANCELLED`, THE
   `ProcessRunAdapter` SHALL emit `run_finished` with the `exit_code` (or `-1` for `CANCELLED`)
   and stop its internal timer.
5. THE `ProcessRunAdapter` SHALL NOT start or stop the subprocess itself; it SHALL only observe
   the `ProcessRun`.
6. WHERE a UI page previously instantiated `ProcessService` directly, THE page SHALL instead
   receive a `ProcessRunManager` via constructor injection and use `ProcessRunAdapter` for output
   bridging.

---

### Requirement 5: Web API Adapter (FastAPI)

**User Story:** As a web API developer, I want FastAPI route handlers that delegate to
`ProcessRunManager`, so that the web layer can start, monitor, and stop runs without duplicating
subprocess logic.

#### Acceptance Criteria

1. THE Web_API SHALL expose a `POST /runs` endpoint that accepts a `RunRequest` JSON body
   (containing `command` list and optional `cwd`), calls `ProcessRunManager.start_run()`, and
   returns the `run_id` and initial status.
2. THE Web_API SHALL expose a `GET /runs/{run_id}` endpoint that returns the current `status`,
   `exit_code`, `started_at`, `finished_at`, `command`, and `cwd` for the given run.
3. THE Web_API SHALL expose a `DELETE /runs/{run_id}` endpoint that calls
   `ProcessRunManager.stop_run()` and returns the updated status.
4. THE Web_API SHALL expose a `GET /runs/{run_id}/output` endpoint that returns all accumulated
   stdout and stderr lines from `ProcessRun.stdout_buffer` and `ProcessRun.stderr_buffer`.
5. WHEN a `run_id` is not found, THE Web_API SHALL return HTTP 404 with a descriptive error body.
6. THE Web_API route handlers SHALL NOT create or manage `subprocess.Popen` objects directly;
   all subprocess interaction SHALL be delegated to `ProcessRunManager`.

---

### Requirement 6: Framework Independence of Core

**User Story:** As a developer, I want the `ProcessRunManager` and `ProcessRun` to have zero
imports from PySide6 or FastAPI, so that the core logic can be tested in isolation and reused
across both surfaces.

#### Acceptance Criteria

1. THE `ProcessRunManager` module SHALL NOT import any symbol from `PySide6`, `fastapi`, or
   `starlette`.
2. THE `ProcessRun` model SHALL NOT import any symbol from `PySide6`, `fastapi`, or `starlette`.
3. THE `ProcessRunManager` SHALL be fully exercisable by plain `pytest` tests without a Qt
   application instance or a running HTTP server.
4. WHEN the `ProcessRunManager` is instantiated, THE `ProcessRunManager` SHALL accept an optional
   `on_run_finished` callback (`Callable[[ProcessRun], None]`) so that adapters can register
   lifecycle hooks without subclassing.

---

### Requirement 7: Backward Compatibility Shim

**User Story:** As a developer, I want existing callers of `ProcessService.execute_command` to
continue working during the migration, so that I can migrate pages incrementally without breaking
the running application.

#### Acceptance Criteria

1. THE existing `ProcessService` class SHALL remain importable from
   `app.core.services.process_service` throughout the migration period.
2. THE `ProcessService` SHALL be updated internally to delegate to `ProcessRunManager` rather than
   managing `subprocess.Popen` directly, while preserving its existing public method signatures:
   `execute_command`, `stop_process`, `get_full_output`, `is_running`, and `build_environment`.
3. WHEN `ProcessService.execute_command` is called, THE `ProcessService` SHALL create a
   `RunCommand` from the supplied arguments, call `ProcessRunManager.start_run()`, and wire the
   `on_output`, `on_error`, and `on_finished` callbacks to the new run's queues.
4. THE `ProcessService.build_environment` static method SHALL remain unchanged.

---

### Requirement 8: Run History and Lookup

**User Story:** As a developer, I want to retrieve any past run by its `run_id`, so that results
pages and API clients can display logs and outcomes without re-running the command.

#### Acceptance Criteria

1. THE `ProcessRunManager` SHALL retain all `ProcessRun` records in memory for the lifetime of the
   application process.
2. WHEN `list_runs()` is called with an optional `status` filter, THE `ProcessRunManager` SHALL
   return only runs whose `status` matches the filter.
3. THE `ProcessRunManager` SHALL provide a `get_run(run_id: str) -> ProcessRun` method that
   returns the run regardless of its current status (including completed runs).
4. WHEN the application process exits, THE `ProcessRunManager` SHALL NOT persist run history to
   disk (persistence is out of scope for this feature).
