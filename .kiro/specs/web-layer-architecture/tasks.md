# Implementation Plan: Web Layer Architecture

## Overview

Implement the four concrete deliverables: architecture linter, RollbackService, rollback API
endpoint, and SSE ProcessOutputBus. Work proceeds bottom-up — core service first, then web
wiring, then the linter that validates the result.

## Tasks

- [x] 1. Implement RollbackService
  - [x] 1.1 Create `app/core/services/rollback_service.py` with `RollbackResult` dataclass and `RollbackService` class
    - Define `RollbackResult` dataclass with fields: `success`, `rolled_back_to`, `strategy_name`, `params_restored`, `config_restored`, `error: Optional[str] = None`
    - Implement `RollbackService.rollback(run_dir, user_data_path, strategy_name)` following the five-step logic in the design
    - Use `write_json_file_atomic` for all file writes; use `pathlib.Path` throughout
    - Raise `FileNotFoundError` when `run_dir` is absent; raise `ValueError` when neither source file exists
    - Add module-level logger: `_log = get_logger("services.rollback")`
    - _Requirements: 5.6, 5.7, 5.8, 5.9, 5.10_

  - [x] 1.2 Write property test for rollback file fidelity
    - **Property 5: Rollback file fidelity**
    - **Validates: Requirements 5.7**
    - Use `@given(st.dictionaries(...), st.dictionaries(...))` with arbitrary JSON-serialisable dicts
    - Assert restored files are byte-for-byte equal to source files

  - [x] 1.3 Write unit tests for RollbackService in `tests/test_rollback_service.py`
    - Happy path: both files present → both restored, `success=True`
    - Missing `params.json` → `params_restored=False`, config still restored
    - Missing `config.snapshot.json` → `config_restored=False`, params still restored
    - Neither file present → `ValueError`
    - Non-existent `run_dir` → `FileNotFoundError`
    - _Requirements: 5.6, 5.7, 5.9, 5.10_

- [x] 2. Implement ProcessOutputBus
  - [x] 2.1 Create `app/web/process_output_bus.py` with the `ProcessOutputBus` class
    - Implement `__init__`, `attach(loop)`, `push_line(line)`, `push_finished(exit_code)`, and `stream()` async generator exactly as specified in the design
    - Use `threading.Lock` for the `_lock` attribute; use `loop.call_soon_threadsafe` for thread-safe queue writes
    - `push_line` / `push_finished` silently drop calls when `attach()` has not been called
    - `stream()` yields `{"event": "status", "data": '{"status": "idle"}'}` when queue is `None`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 2.2 Write property test for SSE exit code delivery
    - **Property 8: SSE delivers correct exit code**
    - **Validates: Requirements 4.3**
    - Use `@given(st.integers(min_value=-255, max_value=255))`
    - Assert final event is `"complete"` and payload contains the integer exit code

  - [x] 2.3 Write unit tests for ProcessOutputBus in `tests/test_process_output_bus.py`
    - Lines pushed from a thread appear in `stream()` in order
    - `push_finished` terminates the stream with the correct exit code
    - Calling `push_line` before `attach()` does not raise
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Wire dependencies and update `app/web/dependencies.py`
  - [x] 4.1 Add `get_rollback_service()` factory and `RollbackServiceDep` type alias
    - Use `@lru_cache` on the factory; `RollbackServiceDep = Annotated[RollbackService, Depends(get_rollback_service)]`
    - _Requirements: 3.3, 5.6_
  - [x] 4.2 Add `get_process_output_bus()` factory and `ProcessOutputBusDep` type alias
    - Use `@lru_cache` on the factory; `ProcessOutputBusDep = Annotated[ProcessOutputBus, Depends(get_process_output_bus)]`
    - _Requirements: 3.3, 4.1_

- [x] 5. Add rollback endpoint to `app/web/api/routes/runs.py`
  - [x] 5.1 Implement `POST /api/runs/{strategy}/{run_id}/rollback` route handler
    - Inject `SettingsServiceDep` and `RollbackServiceDep`; resolve `run_dir` from settings and path params
    - Map exceptions to HTTP status codes: `FileNotFoundError` → 404, `ValueError` → 422, `Exception` → 500
    - Return `RollbackResponse` Pydantic model on success
    - _Requirements: 5.6, 5.7, 5.8, 5.9, 5.10_

  - [x] 5.2 Write route tests for rollback endpoint in `tests/test_web_routes.py`
    - `POST /api/runs/{strategy}/{run_id}/rollback` → 200 with valid run
    - → 404 when run does not exist
    - → 500 on unexpected service error
    - _Requirements: 5.6, 5.8, 5.9, 5.10_

- [x] 6. Fix SSE process output in `app/web/api/routes/process.py`
  - [x] 6.1 Replace global queue skeleton with `ProcessOutputBus`; wire `attach()` in the SSE endpoint
    - Inject `ProcessOutputBusDep`; call `bus.attach(asyncio.get_event_loop())` at the start of the handler
    - Return `EventSourceResponse(bus.stream())`
    - Remove any module-level queue or threading primitives that the skeleton introduced
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 7. Wire `ProcessOutputBus` callbacks in backtest and optimize routes
  - [x] 7.1 Update `app/web/api/routes/backtest.py` — replace `lambda line: None` callbacks
    - Inject `ProcessOutputBusDep`; pass `on_output=bus.push_line`, `on_error=bus.push_line`, `on_finished=bus.push_finished` to `ProcessService.execute_command`
    - _Requirements: 3.1, 3.2, 4.4_
  - [x] 7.2 Update `app/web/api/routes/optimize.py` — same callback fix as backtest
    - Inject `ProcessOutputBusDep`; replace no-op lambdas with `bus.push_line` / `bus.push_finished`
    - _Requirements: 3.1, 3.2, 4.4_

- [x] 8. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement architecture linter in `tests/test_architecture.py`
  - [x] 9.1 Define `ArchRule` and `Violation` dataclasses and the `RULES` list
    - Three rules as specified in the design: no PySide6 in `app/core/`, no `app.ui`/`app.app_state` in `app/core/services/`, no `app.ui` in `app/web/`
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 7.3_
  - [x] 9.2 Implement `scan_for_violations(rules, repo_root)` and `format_violations(violations)`
    - Walk all `.py` files under each rule's `scan_dir` using `pathlib.Path.rglob`
    - Use `re.search` per line; catch file read errors per-file (skip with warning, continue)
    - Skip rule silently if `scan_dir` does not exist
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 7.2, 7.4_
  - [x] 9.3 Implement `test_architecture_boundaries()` pytest test and `__main__` entry point
    - Single assertion: `assert violations == [], format_violations(violations)`
    - `if __name__ == "__main__":` block that exits with code 0 or 1
    - _Requirements: 1.6, 1.7, 1.8, 7.1, 7.2, 7.5_

  - [x] 9.4 Write property test — linter detects forbidden imports (Property 1)
    - **Property 1: Linter detects forbidden imports**
    - **Validates: Requirements 1.1, 2.1, 7.3**
    - Use `@given(pattern=st.sampled_from([...]), prefix=st.text(...))` as shown in the design

  - [x] 9.5 Write property test — linter passes on clean files (Property 2)
    - **Property 2: Linter passes on clean files**
    - **Validates: Requirements 1.7, 7.5**
    - Use `@given(st.lists(st.text(...), max_size=20))` filtering out any accidentally forbidden lines

  - [x] 9.6 Write property test — all violations reported in single pass (Property 3)
    - **Property 3: All violations reported in single pass**
    - **Validates: Requirements 7.4**
    - Use `@given(st.integers(min_value=1, max_value=10))` to generate N offending lines; assert `len(violations) == N`

  - [x] 9.7 Write property test — violation report structure (Property 4)
    - **Property 4: Violation report contains path, line number, and import text**
    - **Validates: Requirements 1.2, 2.2**
    - Use `@given(line_number=st.integers(...), import_text=st.sampled_from([...]))` as shown in the design

- [x] 10. Write property tests for settings in `tests/test_web_layer_properties.py`
  - [x] 10.1 Write property test — settings merge preserves unchanged fields (Property 6)
    - **Property 6: Settings merge preserves unchanged fields**
    - **Validates: Requirements 6.2**
    - Use `@given(st.builds(AppSettings), st.one_of(st.none(), st.text(...)))`

  - [x] 10.2 Write property test — settings serialization round-trip (Property 7)
    - **Property 7: Settings serialization round-trip**
    - **Validates: Requirements 6.5**
    - Use `@given(st.builds(AppSettings))`; assert `AppSettings(**settings.model_dump()) == settings`

- [x] 11. Verify or remove `app/core/ai/runtime/conversation_runtime.py`
  - [x] 11.1 Confirm `conversation_runtime.py` is absent or contains no PySide6 imports
    - If the file exists and imports PySide6, delete it (the async version `async_conversation_runtime.py` is the active file)
    - If absent, no action needed — the architecture linter will enforce this going forward
    - _Requirements: 1.3, 1.4, 1.5_

- [x] 12. Final checkpoint — Ensure all tests pass
  - Run `pytest --tb=short` and confirm zero failures including `test_architecture_boundaries`.
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Property tests use Hypothesis with `@settings(max_examples=100)`; each test carries a comment `# Feature: web-layer-architecture, Property N: <title>`
- All file I/O uses `pathlib.Path`; atomic writes use `write_json_file_atomic`
- Module-level loggers follow the pattern `_log = get_logger("services.rollback")` etc.
- The architecture linter (task 9) validates the work done in tasks 1–8 — run it last
