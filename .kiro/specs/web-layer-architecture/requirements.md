# Requirements Document

## Introduction

This feature enforces a clean layered architecture across the Freqtrade GUI codebase and adds a
fully functional web layer (`app/web/`) that delegates to the existing service layer. The goals are:

1. **Architectural purity** — no PySide6 symbols may appear in `app/core/` or `app/core/services/`;
   the one known violation (`app/core/ai/runtime/conversation_runtime.py`) must be resolved.
2. **Web layer completion** — `app/web/` exposes a FastAPI REST API that delegates every
   operation to the existing service layer; no business logic lives in route handlers.
3. **Architecture validation** — layer boundary rules are enforced automatically in CI so future
   changes cannot re-introduce cross-layer import violations.

The web layer is already partially scaffolded (`app/web/main.py`, `app/web/dependencies.py`,
`app/web/api/routes/`). `ProcessService` is already framework-agnostic (uses `subprocess`,
not `QProcess`). The primary remaining work is the architectural audit, the AI-runtime leak fix,
and ensuring every web route delegates cleanly to services.

---

## Glossary

- **Architecture_Linter**: The automated check (Ruff rule or CI script) that enforces layer
  boundaries by detecting forbidden cross-layer imports.
- **Core_Layer**: Modules under `app/core/` — models, runners, resolvers, utils, and services.
  Must have zero PySide6 dependencies.
- **Service_Layer**: Modules under `app/core/services/` — stateless or lightly stateful
  business-logic classes. Must have zero PySide6 or UI dependencies.
- **Web_Layer**: Modules under `app/web/` — FastAPI application, route handlers, Pydantic
  request/response models, and dependency injection. May import from Service_Layer and
  Core_Layer.
- **ProcessService**: `app/core/services/process_service.py` — framework-agnostic subprocess
  wrapper using Python's `subprocess.Popen` and threading.
- **ConversationRuntime**: `app/core/ai/runtime/conversation_runtime.py` — the single known
  PySide6 leak in Core_Layer that must be resolved.
- **Route_Handler**: A FastAPI async function decorated with `@router.get/post/...` inside
  `app/web/api/routes/`.
- **Dependency_Injector**: `app/web/dependencies.py` — provides singleton service instances
  to Route_Handlers via FastAPI's `Depends()` mechanism.
- **SSE**: Server-Sent Events — HTTP streaming mechanism used to push live subprocess output
  from the web server to the browser.
- **Rollback**: The operation of restoring a strategy's configuration and parameter state to match a previously saved backtest run, using the `config.snapshot.json` and `params.json` stored in that run's directory.

---

## Requirements

### Requirement 1: Layer Boundary Enforcement — No PySide6 in Core

**User Story:** As a developer, I want the Core_Layer and Service_Layer to be free of PySide6
imports, so that services can be used by both the desktop UI and the web layer without pulling
in Qt dependencies.

#### Acceptance Criteria

1. THE Architecture_Linter SHALL detect any `import PySide6` or `from PySide6` statement in
   any Python file under `app/core/`.
2. WHEN the Architecture_Linter detects a forbidden import, THE Architecture_Linter SHALL
   report the file path, line number, and the offending import statement.
3. THE ConversationRuntime SHALL be refactored to remove its dependency on
   `PySide6.QtCore.QObject`, `QThread`, and `Signal`.
4. WHEN ConversationRuntime requires asynchronous execution, THE ConversationRuntime SHALL use
   Python's `threading.Thread` or `asyncio` instead of `QThread`.
5. WHEN ConversationRuntime requires observable state, THE ConversationRuntime SHALL use
   callback functions or `asyncio` coroutines instead of Qt `Signal`.
6. THE Architecture_Linter SHALL be executable as a standalone script and as part of the
   `pytest` test suite.
7. IF the Architecture_Linter finds zero violations, THEN THE Architecture_Linter SHALL exit
   with code 0.
8. IF the Architecture_Linter finds one or more violations, THEN THE Architecture_Linter SHALL
   exit with a non-zero code.

---

### Requirement 2: Layer Boundary Enforcement — No UI Imports in Service Layer

**User Story:** As a developer, I want the Service_Layer to be free of UI imports, so that
services remain independently testable and reusable across front-ends.

#### Acceptance Criteria

1. THE Architecture_Linter SHALL detect any `import app.ui`, `from app.ui`, `import app.app_state`,
   or `from app.app_state` statement in any Python file under `app/core/services/`.
2. WHEN the Architecture_Linter detects a forbidden import in the Service_Layer, THE
   Architecture_Linter SHALL report the file path, line number, and the offending import.
3. THE Service_Layer SHALL contain zero imports from `app.ui` or `app.app_state`.
4. WHEN a service requires reactive notification, THE Service_Layer SHALL accept a callback
   function as a constructor or method parameter instead of importing a Qt signal class.

---

### Requirement 3: Web Layer — Shared Service Delegation

**User Story:** As a developer, I want every web API route handler to delegate to the same
service functions used by the desktop UI, so that there is a single source of truth for
business logic.

#### Acceptance Criteria

1. THE Web_Layer SHALL contain zero business logic that is not already present in the
   Service_Layer.
2. WHEN a Route_Handler receives a valid request, THE Route_Handler SHALL call the
   corresponding Service_Layer function and return its result as a Pydantic response model.
3. THE Dependency_Injector SHALL provide singleton instances of `BacktestService`,
   `OptimizeService`, `DownloadDataService`, `SettingsService`, and `ProcessService` to
   Route_Handlers via FastAPI's `Depends()` mechanism.
4. THE Web_Layer SHALL expose a `POST /api/backtest/run` endpoint that accepts a
   `BacktestRequest` body and delegates to `BacktestService.build_command`.
5. THE Web_Layer SHALL expose a `POST /api/optimize/run` endpoint that accepts an
   `OptimizeRequest` body and delegates to `OptimizeService.build_command`.
6. THE Web_Layer SHALL expose a `POST /api/download/run` endpoint that accepts a
   `DownloadDataRequest` body and delegates to `DownloadDataService.build_command`.
7. THE Web_Layer SHALL expose a `GET /api/strategies` endpoint that delegates to
   `BacktestService.get_available_strategies`.
8. THE Web_Layer SHALL expose a `GET /api/settings` endpoint that delegates to
   `SettingsService.load_settings`.
9. THE Web_Layer SHALL expose a `PUT /api/settings` endpoint that accepts a
   `SettingsUpdate` body and delegates to `SettingsService.save_settings`.

---

### Requirement 4: Web Layer — Live Process Output via SSE

**User Story:** As a web UI user, I want to see live subprocess output (backtest, optimize,
download) streamed to the browser, so that I have the same real-time feedback as the desktop
terminal widget.

#### Acceptance Criteria

1. THE Web_Layer SHALL expose a `GET /api/process/stream` SSE endpoint that streams
   stdout and stderr lines from the currently running subprocess.
2. WHEN a subprocess is started via a web API endpoint, THE Web_Layer SHALL stream each
   output line as an SSE `data:` event within 500 ms of the line being written by the
   subprocess.
3. WHEN the subprocess exits, THE Web_Layer SHALL send a final SSE event containing the
   exit code and then close the stream.
4. THE Web_Layer SHALL use `ProcessService.execute_command` with callback parameters to
   receive subprocess output — it SHALL NOT spawn a second subprocess independently.
5. IF no subprocess is running when a client connects to the SSE endpoint, THEN THE
   Web_Layer SHALL send a single SSE event indicating idle status and keep the connection
   open until a process starts or the client disconnects.

---

### Requirement 5: Web Layer — Backtest Results API

**User Story:** As a web UI user, I want to browse and load saved backtest runs through the
web API, so that I can view historical results in a browser without running the desktop app.

#### Acceptance Criteria

1. THE Web_Layer SHALL expose a `GET /api/runs` endpoint that returns a list of all saved
   backtest runs across all strategies, delegating to `IndexStore.get_all_runs`.
2. THE Web_Layer SHALL expose a `GET /api/runs/{strategy}` endpoint that returns runs for
   a specific strategy, delegating to `IndexStore.get_strategy_runs`.
3. THE Web_Layer SHALL expose a `GET /api/runs/{strategy}/{run_id}` endpoint that returns
   full run details including trades, delegating to `RunStore.load_run`.
4. WHEN a run is not found, THE Web_Layer SHALL return HTTP 404 with a descriptive error
   message.
5. THE Web_Layer SHALL expose a `GET /api/health` endpoint that returns HTTP 200 with
   `{"status": "ok"}` when the service is running.
6. THE Web_Layer SHALL expose a `POST /api/runs/{strategy}/{run_id}/rollback` endpoint that
   restores the strategy file and config snapshot from the selected run, delegating to a
   `RollbackService` or equivalent service method.
7. WHEN a rollback is requested, THE Web_Layer SHALL copy the `config.snapshot.json` and
   strategy params from the selected run directory back to the active strategy location.
8. WHEN a rollback succeeds, THE Web_Layer SHALL return HTTP 200 with
   `{"success": true, "rolled_back_to": run_id}`.
9. WHEN a rollback fails because the run does not exist, THE Web_Layer SHALL return HTTP 404
   with a descriptive error message.
10. WHEN a rollback fails due to a file system error, THE Web_Layer SHALL return HTTP 500
    with a descriptive error message.

---

### Requirement 6: Web Layer — Settings Persistence

**User Story:** As a web UI user, I want to read and update application settings through the
web API, so that I can configure paths and preferences without the desktop app.

#### Acceptance Criteria

1. THE Web_Layer SHALL expose a `GET /api/settings` endpoint that returns the current
   `AppSettings` as a JSON object.
2. THE Web_Layer SHALL expose a `PUT /api/settings` endpoint that accepts a partial
   `SettingsUpdate` body, merges it with the current settings, and persists the result via
   `SettingsService.save_settings`.
3. WHEN a `PUT /api/settings` request contains an invalid path value, THE Web_Layer SHALL
   return HTTP 422 with a descriptive validation error.
4. WHEN settings are saved via the web API, THE Web_Layer SHALL persist them to the same
   `~/.freqtrade_gui/settings.json` file used by the desktop app.
5. FOR ALL valid `AppSettings` objects, serializing to JSON and deserializing back SHALL
   produce an equivalent object (round-trip property).

---

### Requirement 7: Architecture Validation in CI

**User Story:** As a developer, I want the layer boundary rules enforced automatically in the
test suite, so that future changes cannot accidentally re-introduce cross-layer import
violations.

#### Acceptance Criteria

1. THE Architecture_Linter SHALL be implemented as a `pytest` test module at
   `tests/test_architecture.py`.
2. WHEN `pytest` is run, THE Architecture_Linter SHALL scan all Python files under `app/`
   and fail the test if any forbidden import is detected.
3. THE Architecture_Linter SHALL enforce the following rules:
   - No `PySide6` imports in `app/core/`
   - No `app.ui` or `app.app_state` imports in `app/core/services/`
   - No `app.ui` imports in `app/web/`
4. THE Architecture_Linter SHALL report all violations in a single test failure message
   rather than stopping at the first violation.
5. WHEN zero violations are found, THE Architecture_Linter test SHALL pass without output.
