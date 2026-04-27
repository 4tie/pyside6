# Implementation Plan: Shared Inputs

## Overview

Consolidate six common trading input fields into a single `shared_inputs` preference section. Backend changes land in `app/core/` and `leave/web/`; frontend changes land in `app/re_web/src/`. The `app/ui/` and `app/web/` directories are frozen and must not be touched.

## Tasks

- [x] 1. Add `SharedInputsPreferences` model and `AppSettings` migration validator
  - Add `SharedInputsPreferences` Pydantic model to `app/core/models/settings_models.py` with exactly six fields: `default_timeframe`, `default_timerange`, `last_timerange_preset`, `default_pairs`, `dry_run_wallet`, `max_open_trades` and their defaults
  - Add `shared_inputs: SharedInputsPreferences` field to `AppSettings`
  - Add `migrate_shared_inputs` `model_validator(mode="before")` to `AppSettings` that, when `shared_inputs` is absent from the raw dict, merges values from `download_preferences` → `backtest_preferences` → `optimizer_preferences` (last-write-wins, so optimizer wins)
  - Add `"shared_inputs"` to `SettingsService._PREFERENCE_SECTIONS` frozenset in `app/core/services/settings_service.py`
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.1 Write property test for migration priority (Property 1)
    - **Property 1: Migration priority is respected**
    - Generate arbitrary combinations of `optimizer_preferences`, `backtest_preferences`, and `download_preferences` dicts each containing a subset of the six shared fields; assert that `AppSettings` without a `shared_inputs` key produces `shared_inputs` values matching optimizer > backtest > download priority
    - **Validates: Requirements 1.3**

  - [x] 1.2 Write unit tests for `SharedInputsPreferences` defaults and field count
    - `test_shared_inputs_defaults` — `AppSettings()` has correct default values for all six fields
    - `test_shared_inputs_fields_only` — `SharedInputsPreferences` has exactly six fields
    - `test_legacy_fields_retained` — `BacktestPreferences`, `DownloadPreferences`, `OptimizerPreferences` still carry the shared fields (backward compat)
    - _Requirements: 1.1, 1.2, 1.4_

- [x] 2. Create `SharedInputsService`
  - Create `app/core/services/shared_inputs_service.py`
  - Define `SharedInputsUpdate` Pydantic model with all six fields as `Optional[T] = None`
  - Implement `SharedInputsService.__init__(self, settings_service: SettingsService)`
  - Implement `read_config()` → returns `SharedInputsPreferences` from `settings_service.load_settings().shared_inputs`
  - Implement `write_config(update: SharedInputsUpdate)` → validates constraints, resolves preset via `InputHolderService.resolve_preset`, deduplicates pairs via `InputHolderService.deduplicate_pairs`, persists via `settings_service.update_preferences("shared_inputs", ...)`, returns updated `SharedInputsPreferences`
  - Raise `ValueError` when `dry_run_wallet <= 0` or `max_open_trades < 1`
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 2.1 Write property test for write/read round-trip (Property 2)
    - **Property 2: Write/read round-trip preserves values**
    - Generate valid `SharedInputsUpdate` instances (wallet > 0, trades >= 1); call `write_config` then `read_config` against a temp-file-backed `SettingsService`; assert returned fields match written values after preset resolution and deduplication
    - **Validates: Requirements 2.1, 2.2, 9.1**

  - [x] 2.2 Write property test for numeric validation (Property 3)
    - **Property 3: Numeric validation rejects invalid inputs**
    - Generate `dry_run_wallet <= 0` and `max_open_trades < 1` values; assert `write_config` raises `ValueError` and that `read_config` returns unchanged state
    - **Validates: Requirements 2.3, 2.4**

  - [x] 2.3 Write property test for preset resolution format (Property 4)
    - **Property 4: Preset resolution produces valid YYYYMMDD-YYYYMMDD timerange**
    - Parametrize over all known preset keys with arbitrary reference dates; assert `default_timerange` matches `YYYYMMDD-YYYYMMDD` pattern with correct end date
    - **Validates: Requirements 2.5**

  - [x] 2.4 Write property test for pair deduplication (Property 5)
    - **Property 5: Pair deduplication preserves insertion order and removes duplicates**
    - Generate comma-separated strings with repeated entries; assert persisted `default_pairs` has each pair at most once and first-occurrence order is preserved
    - **Validates: Requirements 2.6**

- [x] 3. Checkpoint — Ensure all backend service tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Add REST endpoints `GET /api/shared-inputs` and `PUT /api/shared-inputs`
  - Create `leave/web/api/routes/shared_inputs.py` with a FastAPI `APIRouter`
  - Implement `GET /api/shared-inputs` → delegates to `SharedInputsService.read_config()`, returns `SharedInputsPreferences` as JSON
  - Implement `PUT /api/shared-inputs` → accepts `SharedInputsUpdate` body, delegates to `SharedInputsService.write_config()`, returns updated `SharedInputsPreferences`; map `ValueError` → HTTP 422, `RuntimeError` → HTTP 500
  - Wire `SharedInputsService` via a new dependency (mirror the pattern in `leave/web/api/routes/input_holder.py`)
  - Register the new router in `leave/web/main.py` with `prefix="/api"` and `tags=["shared-inputs"]`
  - _Requirements: 3.1, 3.2, 3.3_

  - [x] 4.1 Write unit tests for `GET /api/shared-inputs` and `PUT /api/shared-inputs`
    - `test_get_shared_inputs_endpoint` — returns 200 with correct six-field shape
    - `test_put_shared_inputs_endpoint` — partial body returns updated state
    - `test_api_422_on_invalid_wallet` — `PUT` with `dry_run_wallet=0` returns 422
    - `test_api_422_on_invalid_trades` — `PUT` with `max_open_trades=0` returns 422
    - `test_disk_write_failure_returns_500` — mock `RuntimeError` from service returns 500
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 5. Update `GET /api/settings` to include `shared_inputs`
  - In `leave/web/models.py`, add `shared_inputs: Dict[str, Any] = Field(default_factory=dict)` to `SettingsResponse`
  - In `leave/web/api/routes/settings.py`, update `_settings_response()` to include `shared_inputs=app_settings.shared_inputs.model_dump(mode="json")`
  - _Requirements: 3.4_

  - [x] 5.1 Write unit test for settings response shape
    - `test_settings_response_includes_shared_inputs` — `GET /api/settings` response JSON contains a `shared_inputs` key with all six fields
    - _Requirements: 3.4_

- [x] 6. Add `SharedInputsConfig` type and API client methods (frontend)
  - In `app/re_web/src/types/api.ts`, add `SharedInputsConfig` interface with exactly six fields: `default_timeframe: string`, `default_timerange: string`, `last_timerange_preset: string`, `default_pairs: string`, `dry_run_wallet: number`, `max_open_trades: number`
  - Add `shared_inputs: SharedInputsConfig` field to `SettingsResponse` interface
  - In `app/re_web/src/api/client.ts`, add `getSharedInputs()` method calling `GET /api/shared-inputs` returning `SharedInputsConfig`
  - Add `updateSharedInputs(payload: Partial<SharedInputsConfig>)` method calling `PUT /api/shared-inputs` returning `SharedInputsConfig`
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 7. Migrate `BacktestPage` to shared inputs
  - In `app/re_web/src/pages/BacktestPage.tsx`, change the `useEffect` load to read shared fields from `settings.shared_inputs` instead of `settings.backtest_preferences`
  - Split state: keep `last_strategy` in a separate state variable backed by `api.updateSettings({ backtest_preferences: { last_strategy } })`; move the six shared fields into a `sharedPrefs` state backed by `api.updateSharedInputs(...)`
  - Replace the single `useAutosave` with two: one for `last_strategy` → `api.updateSettings(...)`, one for shared fields → `api.updateSharedInputs(...)`
  - Remove all reads/writes to `backtest_preferences` for the six shared fields
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 8. Migrate `DownloadPage` to shared inputs
  - In `app/re_web/src/pages/DownloadPage.tsx`, change the `useEffect` load to read `default_timeframe`, `default_timerange`, `default_pairs` from `settings.shared_inputs` instead of `settings.download_preferences`
  - Keep `prepend` and `erase` in a separate state backed by `api.updateSettings({ download_preferences: { prepend, erase } })`
  - Replace the single `useAutosave` with two: one for download-only fields (`prepend`, `erase`) → `api.updateSettings(...)`, one for shared fields → `api.updateSharedInputs(...)`
  - Remove all reads/writes to `download_preferences` for the three shared fields
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 9. Migrate `OptimizerPage` to shared inputs
  - In `app/re_web/src/pages/OptimizerPage.tsx`, change `loadAll()` to call `api.getSharedInputs()` (or read from `settings.shared_inputs`) for the six shared fields; keep `last_strategy` from `api.getOptimizerConfig()`
  - Split the single `useAutosave` into two: shared fields → `api.updateSharedInputs(...)`, `last_strategy` → `api.updateOptimizerConfig({ last_strategy })`
  - Remove all reads/writes to `optimizer_preferences` for the six shared fields
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 10. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Remove shared-field `PrefsSection` blocks from `SettingsPage`
  - In `app/re_web/src/pages/SettingsPage.tsx`, remove the three `<PrefsSection>` calls for `backtest_preferences`, `optimizer_preferences`, and `download_preferences`
  - Remove the `setPrefs` helper and any state/autosave logic that was only used for those three sections
  - Keep the "Paths & Executables" section and its autosave unchanged
  - Update `emptySettings` initial state to remove the three preference keys if they are no longer referenced
  - _Requirements: 8.1, 8.2, 8.3_

  - [x] 11.1 Write unit test for `SettingsPage` cleanup
    - Assert `SettingsPage` renders without `PrefsSection` components for `backtest_preferences`, `optimizer_preferences`, `download_preferences`
    - Assert the "Paths & Executables" section is still present
    - _Requirements: 8.1, 8.2_

- [x] 12. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Property tests use Hypothesis (Python) following the pattern in `tests/property/test_input_holder_properties.py`
- Frontend unit tests use vitest following the pattern in `app/re_web/tests/`
- Route files live in `leave/web/api/routes/` — `app/web/` is frozen and must not be modified
- `app/ui/` is also frozen — no changes there
- `InputHolderService.resolve_preset` and `InputHolderService.deduplicate_pairs` are reused as static helpers; do not duplicate that logic
- The `SettingsService._PREFERENCE_SECTIONS` guard must include `"shared_inputs"` before any `update_preferences("shared_inputs", ...)` call will succeed
