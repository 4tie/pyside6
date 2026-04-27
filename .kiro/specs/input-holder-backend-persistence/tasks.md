# Implementation Plan: Input Holder Backend Persistence

## Overview

Move the source of truth for the seven Configure-section fields (Strategy, Timeframe, Preset, Timerange, Wallet, Max Trades, Pairs) from ephemeral UI state to the Python backend. The implementation adds validators to `OptimizerPreferences`, two new DTOs, `InputHolderService`, `InputHolderRouter`, router registration in `app/web/main.py`, and wires the PySide6 `OptimizerPage` to call the backend on load and on every input change.

## Tasks

- [x] 1. Extend `OptimizerPreferences` with validators
  - [x] 1.1 Add `@field_validator` for `dry_run_wallet` in `app/core/models/optimizer_models.py`
    - Reject values `<= 0` with a descriptive `ValueError`
    - _Requirements: 1.1, 1.4, 3.6_

  - [x] 1.2 Add `@field_validator` for `max_open_trades` in `app/core/models/optimizer_models.py`
    - Reject values `< 1` with a descriptive `ValueError`
    - _Requirements: 1.1, 1.4, 3.7_

  - [x] 1.3 Write property test for `OptimizerPreferences` JSON round-trip
    - **Property 1: OptimizerPreferences JSON round-trip**
    - **Validates: Requirements 1.3**
    - Place in `tests/property/test_input_holder_properties.py`
    - Use `@given(st.builds(OptimizerPreferences, ...))` with bounded strategies for each field
    - `# Feature: input-holder-backend-persistence, Property 1: OptimizerPreferences JSON round-trip`

  - [x] 1.4 Write property test for type constraint violations
    - **Property 2: Type constraint violations raise ValidationError**
    - **Validates: Requirements 1.4**
    - Place in `tests/property/test_input_holder_properties.py`
    - Use `@given` with invalid type values (non-numeric strings, floats for int fields)
    - `# Feature: input-holder-backend-persistence, Property 2: Type constraint violations raise ValidationError`

- [x] 2. Add `OptimizerConfigUpdate` and `OptimizerConfigResponse` DTOs
  - [x] 2.1 Create `OptimizerConfigUpdate` in `app/core/models/optimizer_models.py`
    - All seven fields optional (`str | None`, `float | None`, `int | None`)
    - `model_config = ConfigDict(extra="forbid")` to reject unknown fields with HTTP 422
    - _Requirements: 3.1, 3.4_

  - [x] 2.2 Create `OptimizerConfigResponse` in `app/core/models/optimizer_models.py`
    - All seven fields required (non-optional)
    - Add computed `pairs_list: list[str]` field (split `default_pairs` on commas, strip whitespace)
    - _Requirements: 2.1, 2.4, 5.2, 6.3_

- [x] 3. Implement `InputHolderService`
  - [x] 3.1 Create `app/core/services/input_holder_service.py` with class skeleton and `__init__`
    - Accept `settings_service: SettingsService` in constructor
    - Import `SettingsService`, `OptimizerPreferences`, `OptimizerConfigUpdate`, `OptimizerConfigResponse`
    - _Requirements: 2.2, 3.2_

  - [x] 3.2 Implement `InputHolderService.read_config`
    - Call `settings_service.load_settings()`, extract `optimizer_preferences`
    - Build and return `OptimizerConfigResponse` from the preferences
    - _Requirements: 2.2, 2.3, 6.2, 6.3_

  - [x] 3.3 Implement `InputHolderService.resolve_preset` static method
    - Support keys: `"7d"`, `"14d"`, `"30d"`, `"60d"`, `"90d"`, `"180d"`, `"1y"`
    - Return `YYYYMMDD-YYYYMMDD` string using `today - timedelta(days=N)`; return `None` for unknown keys
    - Accept optional `today: date | None = None` parameter (defaults to `date.today()`)
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 3.4 Implement `InputHolderService.deduplicate_pairs` static method
    - Parse comma-separated string, remove duplicates preserving insertion order, rejoin with `","`
    - Handle empty string input gracefully (return `""`)
    - _Requirements: 5.3_

  - [x] 3.5 Implement `InputHolderService.write_config`
    - Validate `dry_run_wallet > 0` and `max_open_trades >= 1`; raise `ValueError` on violation
    - Call `resolve_preset` when `last_timerange_preset` is a known key; update `default_timerange`
    - Call `deduplicate_pairs` on `default_pairs` before persisting
    - Call `settings_service.update_preferences("optimizer_preferences", **fields)` for atomic write
    - Return `OptimizerConfigResponse` of the updated state
    - _Requirements: 3.2, 3.3, 4.2, 4.3, 5.1, 5.3, 7.1_

  - [x] 3.6 Write unit tests for `InputHolderService` in `tests/unit/test_input_holder_service.py`
    - `test_read_config_returns_defaults` — mock `SettingsService`, assert defaults returned
    - `test_resolve_preset_all_known_keys` — call for each of the 7 keys, assert valid `YYYYMMDD-YYYYMMDD`
    - `test_resolve_preset_unknown_key_returns_none` — assert `None` for unknown key
    - `test_deduplicate_pairs_empty_string` — assert `""` returned
    - `test_deduplicate_pairs_preserves_order` — assert first-occurrence order
    - `test_write_config_invalid_wallet_raises` — assert `ValueError` for `dry_run_wallet <= 0`
    - `test_write_config_invalid_trades_raises` — assert `ValueError` for `max_open_trades < 1`
    - `test_disk_write_failure_propagates_runtime_error` — mock `update_preferences` to raise `RuntimeError`
    - _Requirements: 3.6, 3.7, 4.1, 4.3, 5.3_

  - [x] 3.7 Write property test for preset resolution format
    - **Property 6: Known preset resolution produces valid YYYYMMDD-YYYYMMDD**
    - **Validates: Requirements 4.2**
    - Place in `tests/property/test_input_holder_properties.py`
    - Use `@given(st.sampled_from(KNOWN_PRESETS), st.dates())`
    - `# Feature: input-holder-backend-persistence, Property 6: Known preset resolution produces valid YYYYMMDD-YYYYMMDD`

  - [x] 3.8 Write property test for preset idempotence
    - **Property 7: Preset resolution idempotence**
    - **Validates: Requirements 4.4**
    - Place in `tests/property/test_input_holder_properties.py`
    - Use `@given(st.sampled_from(KNOWN_PRESETS), st.dates())`, resolve twice, assert equal
    - `# Feature: input-holder-backend-persistence, Property 7: Preset resolution idempotence`

  - [x] 3.9 Write property test for pairs deduplication order
    - **Property 9: Pairs deduplication preserves insertion order**
    - **Validates: Requirements 5.3**
    - Place in `tests/property/test_input_holder_properties.py`
    - Use `@given(st.lists(st.text(min_size=1, max_size=10)))` with duplicates injected
    - `# Feature: input-holder-backend-persistence, Property 9: Pairs deduplication preserves insertion order`

- [x] 4. Checkpoint — Ensure all unit and property tests for the service pass
  - Ensure all tests pass, ask the user if questions arise.

- [-] 5. Implement `InputHolderRouter`
  - [x] 5.1 Create `app/web/api/routes/input_holder.py` with `GET /optimizer/config`
    - Use `SettingsServiceDep` from `app/web/dependencies.py`
    - Instantiate `InputHolderService(settings)` per-request
    - Return `OptimizerConfigResponse`; propagate `RuntimeError` as HTTP 500
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 8.2_

  - [x] 5.2 Add `PUT /optimizer/config` endpoint to `InputHolderRouter`
    - Accept `OptimizerConfigUpdate` body
    - Catch `ValueError` → HTTP 422; catch `RuntimeError` → HTTP 500
    - Return full `OptimizerConfigResponse` on success
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 5.3 Register `InputHolderRouter` in `app/web/main.py`
    - Import `input_holder` from `app.web.api.routes`
    - `app.include_router(input_holder.router, prefix="/api", tags=["optimizer-config"])`
    - _Requirements: 8.1, 8.3_

  - [x] 5.4 Write unit tests for the router in `tests/unit/test_input_holder_router.py`
    - Use `fastapi.testclient.TestClient`
    - `test_get_returns_200_with_defaults` — mock service, assert HTTP 200 and all fields present
    - `test_put_valid_payload_returns_200` — assert HTTP 200 and updated fields in response
    - `test_put_unknown_field_returns_422` — assert HTTP 422 and state unchanged
    - `test_put_invalid_wallet_returns_422` — `dry_run_wallet=0`, assert HTTP 422
    - `test_put_invalid_trades_returns_422` — `max_open_trades=0`, assert HTTP 422
    - `test_disk_write_failure_returns_500` — mock service to raise `RuntimeError`, assert HTTP 500
    - `test_last_strategy_empty_string_not_null` — PUT `last_strategy=""`, GET returns `""`
    - _Requirements: 2.1, 3.1, 3.3, 3.4, 3.5, 3.6, 3.7, 6.3_

  - [x] 5.5 Write property test for read-your-writes consistency
    - **Property 3: Read-your-writes consistency**
    - **Validates: Requirements 2.2, 3.2, 3.3, 7.3**
    - Place in `tests/property/test_input_holder_properties.py`
    - Use `@given` random `OptimizerConfigUpdate` payloads, PUT then GET via `TestClient`, assert fields match
    - `# Feature: input-holder-backend-persistence, Property 3: Read-your-writes consistency`

  - [x] 5.6 Write property test for unknown fields rejected with HTTP 422
    - **Property 4: Unknown fields rejected with HTTP 422**
    - **Validates: Requirements 3.4**
    - Place in `tests/property/test_input_holder_properties.py`
    - Use `@given(st.text().filter(lambda s: s not in KNOWN_FIELDS))` for field names
    - Assert HTTP 422 and persisted state unchanged
    - `# Feature: input-holder-backend-persistence, Property 4: Unknown fields rejected with HTTP 422`

  - [x] 5.7 Write property test for wallet and trades boundary validation
    - **Property 5: Wallet and trades boundary validation**
    - **Validates: Requirements 3.6, 3.7**
    - Place in `tests/property/test_input_holder_properties.py`
    - Use `@given(st.floats(max_value=0.0))` and `@given(st.integers(max_value=0))`
    - Assert HTTP 422 and state unchanged
    - `# Feature: input-holder-backend-persistence, Property 5: Wallet and trades boundary validation`

  - [x] 5.8 Write property test for unknown preset preserving existing timerange
    - **Property 8: Unknown preset does not overwrite existing timerange**
    - **Validates: Requirements 4.3**
    - Place in `tests/property/test_input_holder_properties.py`
    - Use `@given(st.text().filter(lambda s: s not in KNOWN_PRESETS), st.text())`
    - Assert `default_timerange` unchanged after PUT with unknown preset
    - `# Feature: input-holder-backend-persistence, Property 8: Unknown preset does not overwrite existing timerange`

  - [x] 5.9 Write property test for pairs response consistency
    - **Property 10: Pairs response includes both raw string and parsed list**
    - **Validates: Requirements 5.2**
    - Place in `tests/property/test_input_holder_properties.py`
    - Use `@given(st.text())` for pairs strings, GET, assert `",".join(pairs_list) == default_pairs`
    - `# Feature: input-holder-backend-persistence, Property 10: Pairs response includes both raw string and parsed list`

- [x] 6. Checkpoint — Ensure all router unit tests and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Wire `OptimizerPage` UI to the backend
  - [x] 7.1 Add `InputHolderService` import and instantiation to `OptimizerPage.__init__`
    - Import `InputHolderService` from `app.core.services.input_holder_service`
    - Instantiate with the existing `self._settings_svc`
    - _Requirements: 2.1, 2.2_

  - [x] 7.2 Replace `_restore_preferences` with a backend-driven load in `OptimizerPage`
    - Call `self._input_holder_svc.read_config()` to get `OptimizerConfigResponse`
    - Populate all seven Configure-section widgets from the response fields
    - Keep `_loading_preferences = True` guard to suppress autosave during population
    - _Requirements: 2.2, 2.3, 2.4, 6.2_

  - [x] 7.3 Replace `_save_preferences` with a backend PUT call in `OptimizerPage`
    - Build `OptimizerConfigUpdate` from current widget values
    - Call `self._input_holder_svc.write_config(update)` (or equivalent HTTP call if using the REST layer)
    - Log errors via `_log`; do not crash the UI on failure
    - _Requirements: 3.1, 3.2, 3.3, 5.1, 6.1_

  - [x] 7.4 Ensure `_connect_preferences_autosave` triggers the new backend save on every widget change
    - All seven Configure-section widgets must connect to `_prefs_save_timer.start()` (debounced 500 ms)
    - Verify `_pairs_edit`, `_wallet_spin`, `_trades_spin`, `_timeframe_combo`, `_strategy_combo`, `_timerange_edit` are all wired
    - _Requirements: 3.1, 5.1, 6.1_

- [x] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Unit tests live in `tests/unit/`; property tests live in `tests/property/test_input_holder_properties.py`
- All property tests use Hypothesis (`@given`) with `max_examples=100` minimum
- Each property test comment cites `# Feature: input-holder-backend-persistence, Property N: <title>`
- `InputHolderService` is instantiated per-request in the router (stateless — no shared mutable state)
- The `SettingsServiceDep` from `app/web/dependencies.py` must be used in the router (not a direct instantiation)
- Atomic writes are guaranteed by delegating to `SettingsService.update_preferences` (uses `write_json_file_atomic`)
