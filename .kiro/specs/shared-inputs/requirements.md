# Requirements Document

## Introduction

The Freqtrade GUI currently stores six common trading input fields — `default_timeframe`, `default_timerange`, `last_timerange_preset`, `default_pairs`, `dry_run_wallet`, and `max_open_trades` — independently in three separate preference sections (`backtest_preferences`, `download_preferences`, `optimizer_preferences`). This causes the values to diverge across pages and forces users to update the same fields in multiple places.

This feature introduces a single shared preference section (`shared_inputs`) as the canonical source of truth for these six fields. All three pages (BacktestPage, DownloadPage, OptimizerPage) will read from and write to this shared section. The Settings page will no longer expose these fields, since they are managed inline on each page. The result is zero code duplication, last-write-wins synchronisation across pages, and a cleaner Settings tab.

## Glossary

- **Shared_Inputs**: The new unified preference section (`shared_inputs`) in `AppSettings` that owns the six common fields.
- **SharedInputs_Service**: The backend service (`SharedInputsService`) responsible for reading and writing `Shared_Inputs` via `SettingsService`.
- **Settings_Service**: The existing `SettingsService` that persists `AppSettings` to `settings.json`.
- **BacktestPage**: The React page at `app/re_web/src/pages/BacktestPage.tsx`.
- **DownloadPage**: The React page at `app/re_web/src/pages/DownloadPage.tsx`.
- **OptimizerPage**: The React page at `app/re_web/src/pages/OptimizerPage.tsx`.
- **SettingsPage**: The React page at `app/re_web/src/pages/SettingsPage.tsx`.
- **Shared_Fields**: The six fields: `default_timeframe`, `default_timerange`, `last_timerange_preset`, `default_pairs`, `dry_run_wallet`, `max_open_trades`.
- **API_Client**: The TypeScript module at `app/re_web/src/api/client.ts`.
- **AppSettings**: The Pydantic model in `app/core/models/settings_models.py` that holds all application preferences.

---

## Requirements

### Requirement 1: Unified Shared Inputs Model

**User Story:** As a developer, I want a single backend model for the six shared fields, so that there is one source of truth and no duplication across preference sections.

#### Acceptance Criteria

1. THE `AppSettings` SHALL contain a `shared_inputs` field of type `SharedInputsPreferences` with default values: `default_timeframe="5m"`, `default_timerange=""`, `last_timerange_preset="30d"`, `default_pairs=""`, `dry_run_wallet=80.0`, `max_open_trades=2`.
2. THE `SharedInputsPreferences` model SHALL define exactly the six Shared_Fields and no others.
3. WHEN `AppSettings` is loaded from a `settings.json` that contains values in `backtest_preferences`, `download_preferences`, or `optimizer_preferences` for any of the Shared_Fields but has no `shared_inputs` section, THE `AppSettings` model validator SHALL migrate those values into `shared_inputs` using last-write-wins priority order: `optimizer_preferences` > `backtest_preferences` > `download_preferences`.
4. THE `BacktestPreferences`, `DownloadPreferences`, and `OptimizerPreferences` models SHALL retain their existing Shared_Fields for backward compatibility with existing `settings.json` files, but those fields SHALL NOT be used as the authoritative source at runtime after migration.

---

### Requirement 2: SharedInputs Backend Service

**User Story:** As a developer, I want a dedicated service for reading and writing shared inputs, so that all pages use the same persistence path without duplicating logic.

#### Acceptance Criteria

1. THE `SharedInputs_Service` SHALL expose a `read_config()` method that returns the current `SharedInputsPreferences` from `Settings_Service`.
2. THE `SharedInputs_Service` SHALL expose a `write_config(update)` method that accepts a partial update, validates it, persists it via `Settings_Service.update_preferences("shared_inputs", ...)`, and returns the updated `SharedInputsPreferences`.
3. WHEN `write_config` is called with `dry_run_wallet <= 0`, THE `SharedInputs_Service` SHALL raise a `ValueError`.
4. WHEN `write_config` is called with `max_open_trades < 1`, THE `SharedInputs_Service` SHALL raise a `ValueError`.
5. WHEN `write_config` is called with a `last_timerange_preset` matching a known preset key (e.g. `"30d"`), THE `SharedInputs_Service` SHALL resolve and overwrite `default_timerange` with the computed `YYYYMMDD-YYYYMMDD` string before persisting.
6. WHEN `write_config` is called with `default_pairs`, THE `SharedInputs_Service` SHALL deduplicate the comma-separated list (preserving insertion order) before persisting.

---

### Requirement 3: REST API Endpoints for Shared Inputs

**User Story:** As a frontend developer, I want REST endpoints to get and update shared inputs, so that all pages can read and write the shared state over HTTP.

#### Acceptance Criteria

1. THE API SHALL expose a `GET /api/shared-inputs` endpoint that returns the current `SharedInputsPreferences` as JSON.
2. THE API SHALL expose a `PUT /api/shared-inputs` endpoint that accepts a partial JSON body, delegates to `SharedInputs_Service.write_config()`, and returns the updated `SharedInputsPreferences` as JSON.
3. WHEN `PUT /api/shared-inputs` receives an invalid value (e.g. `dry_run_wallet <= 0`), THE API SHALL return HTTP 422 with a descriptive error message.
4. THE `GET /api/settings` response SHALL include the `shared_inputs` section so that pages that load settings on mount receive the shared values in a single request.

---

### Requirement 4: Frontend API Client Methods

**User Story:** As a frontend developer, I want typed API client methods for shared inputs, so that pages can call them without duplicating fetch logic.

#### Acceptance Criteria

1. THE `API_Client` SHALL expose a `getSharedInputs()` method that calls `GET /api/shared-inputs` and returns a `SharedInputsConfig` TypeScript type.
2. THE `API_Client` SHALL expose an `updateSharedInputs(payload)` method that calls `PUT /api/shared-inputs` with a partial `SharedInputsConfig` payload and returns the updated `SharedInputsConfig`.
3. THE `SharedInputsConfig` TypeScript interface SHALL define exactly the six Shared_Fields with appropriate types: `default_timeframe: string`, `default_timerange: string`, `last_timerange_preset: string`, `default_pairs: string`, `dry_run_wallet: number`, `max_open_trades: number`.
4. THE `SettingsResponse` TypeScript interface SHALL include a `shared_inputs: SharedInputsConfig` field so that the existing `api.settings()` call returns shared inputs alongside path settings.

---

### Requirement 5: BacktestPage Uses Shared Inputs

**User Story:** As a user, I want changes I make on the Backtest page to be reflected on other pages, so that I don't have to re-enter the same values.

#### Acceptance Criteria

1. WHEN `BacktestPage` mounts, THE `BacktestPage` SHALL load Shared_Fields from `settings.shared_inputs` (via the existing `api.settings()` call) instead of `settings.backtest_preferences`.
2. WHEN a user changes any Shared_Field on `BacktestPage`, THE `BacktestPage` SHALL autosave the change by calling `api.updateSharedInputs(...)` instead of `api.updateSettings({ backtest_preferences: ... })`.
3. THE `BacktestPage` SHALL NOT read from or write to `backtest_preferences` for any of the six Shared_Fields.

---

### Requirement 6: DownloadPage Uses Shared Inputs

**User Story:** As a user, I want the Download page to always show the same timeframe, timerange, and pairs I last used on any page, so that downloads are consistent with my current setup.

#### Acceptance Criteria

1. WHEN `DownloadPage` mounts, THE `DownloadPage` SHALL load `default_timeframe`, `default_timerange`, and `default_pairs` from `settings.shared_inputs` instead of `settings.download_preferences`.
2. WHEN a user changes `default_timeframe`, `default_timerange`, or `default_pairs` on `DownloadPage`, THE `DownloadPage` SHALL autosave the change by calling `api.updateSharedInputs(...)` instead of `api.updateSettings({ download_preferences: ... })`.
3. THE `DownloadPage` SHALL NOT read from or write to `download_preferences` for any of the six Shared_Fields.

---

### Requirement 7: OptimizerPage Uses Shared Inputs

**User Story:** As a user, I want the Optimizer page to share the same inputs as Backtest and Download, so that I can switch between pages without losing my configuration.

#### Acceptance Criteria

1. WHEN `OptimizerPage` mounts, THE `OptimizerPage` SHALL load Shared_Fields from `api.getSharedInputs()` (or `settings.shared_inputs`) instead of `api.getOptimizerConfig()` for those fields.
2. WHEN a user changes any Shared_Field on `OptimizerPage`, THE `OptimizerPage` SHALL autosave the change by calling `api.updateSharedInputs(...)` instead of `api.updateOptimizerConfig(...)` for those fields.
3. THE `OptimizerPage` SHALL continue to read and write `last_strategy` via `api.updateOptimizerConfig(...)` since `last_strategy` is not a Shared_Field.
4. THE `OptimizerPage` SHALL NOT read from or write to `optimizer_preferences` for any of the six Shared_Fields.

---

### Requirement 8: Remove Shared Fields from SettingsPage

**User Story:** As a user, I want the Settings page to be focused on paths and executables, so that I'm not confused by duplicate input fields that are already managed on each page.

#### Acceptance Criteria

1. THE `SettingsPage` SHALL NOT render `PrefsSection` components for `backtest_preferences`, `optimizer_preferences`, or `download_preferences`.
2. THE `SettingsPage` SHALL continue to render the "Paths & Executables" section unchanged.
3. WHEN `SettingsPage` autosaves, THE `SettingsPage` SHALL only persist path and executable fields, not any Shared_Fields.

---

### Requirement 9: Last-Write-Wins Synchronisation

**User Story:** As a user, I want the last value I typed on any page to be the one that persists, so that switching between pages never silently reverts my input.

#### Acceptance Criteria

1. WHEN a user updates a Shared_Field on any page and then navigates to another page, THE second page SHALL display the value that was last written to `shared_inputs`.
2. WHEN two pages are open simultaneously and both write to the same Shared_Field within the autosave debounce window, THE `Settings_Service` SHALL persist the last received write (last-write-wins) without error.
3. IF a write to `shared_inputs` fails due to a disk error, THEN THE `API_Client` SHALL surface the error to the calling page so the user is informed.
