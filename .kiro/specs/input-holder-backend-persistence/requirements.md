# Requirements Document

## Introduction

The Configure section of the Optimizer page (and related pages) exposes several input fields — Strategy, Timeframe, Preset, Timerange, Wallet, Max Trades, and Pairs — whose values are currently held only in frontend/UI state. This feature moves the source of truth for all those inputs to the Python backend: values are read from, updated in, and written to `OptimizerPreferences` (and the shared `AppSettings`) via the existing `SettingsService` / `settings.json` persistence layer and a new dedicated REST API. The UI becomes a thin view that reads initial values from the backend on load and pushes changes back on every user edit.

## Glossary

- **InputHolder**: The collective name for the seven Configure-section fields: Strategy, Timeframe, Preset, Timerange, Wallet, Max Trades, and Pairs.
- **InputHolderService**: The new Python backend service responsible for reading and writing InputHolder values through `SettingsService`.
- **InputHolderRouter**: The new FastAPI router that exposes InputHolder read/write endpoints under `/api/optimizer/config`.
- **OptimizerPreferences**: The existing Pydantic model (`app.core.models.optimizer_models.OptimizerPreferences`) that stores optimizer-specific user preferences inside `AppSettings`.
- **SettingsService**: The existing service (`app.core.services.settings_service.SettingsService`) that loads and atomically saves `AppSettings` to `data/settings.json`.
- **AppSettings**: The root Pydantic model (`app.core.models.settings_models.AppSettings`) that owns `optimizer_preferences`.
- **Preset**: A named shorthand for a timerange (e.g. "30d", "90d", "1y") that the backend resolves to a concrete `YYYYMMDD-YYYYMMDD` timerange string.
- **Timerange**: A date-range string in `YYYYMMDD-YYYYMMDD` format used by freqtrade commands.
- **Pairs**: A comma-separated list of trading pair strings (e.g. `BTC/USDT,ETH/USDT`).

---

## Requirements

### Requirement 1: Backend Model for InputHolder State

**User Story:** As a backend developer, I want a well-typed Pydantic model that captures all seven Configure-section fields, so that the data contract between the API and the persistence layer is explicit and validated.

#### Acceptance Criteria

1. THE `OptimizerPreferences` model SHALL include fields for `last_strategy` (str), `default_timeframe` (str), `last_timerange_preset` (str), `default_timerange` (str), `default_pairs` (str), `dry_run_wallet` (float), and `max_open_trades` (int).
2. WHEN an `OptimizerPreferences` instance is constructed with no arguments, THE model SHALL supply non-empty default values for every field so that the UI can render without a prior save.
3. THE `OptimizerPreferences` model SHALL be serialisable to and deserialisable from JSON without data loss (round-trip property).
4. IF a field value violates its type constraint (e.g. a non-numeric string for `dry_run_wallet`), THEN THE `OptimizerPreferences` model SHALL raise a `ValidationError` with a descriptive message identifying the offending field.

---

### Requirement 2: InputHolder Read Endpoint

**User Story:** As a frontend developer, I want a GET endpoint that returns the current InputHolder values from the backend, so that the Configure section always reflects the last-saved state when the page loads.

#### Acceptance Criteria

1. THE `InputHolderRouter` SHALL expose a `GET /api/optimizer/config` endpoint that returns all seven InputHolder fields as a JSON object.
2. WHEN `GET /api/optimizer/config` is called and `data/settings.json` exists, THE `InputHolderRouter` SHALL return the values stored in `AppSettings.optimizer_preferences`.
3. WHEN `GET /api/optimizer/config` is called and no `data/settings.json` exists, THE `InputHolderRouter` SHALL return the default values defined by `OptimizerPreferences`.
4. THE `GET /api/optimizer/config` response SHALL include the resolved `timerange` string alongside the `last_timerange_preset` so the UI can populate both the Preset dropdown and the Timerange text field from a single call.

---

### Requirement 3: InputHolder Write Endpoint

**User Story:** As a frontend developer, I want a PUT endpoint that persists updated InputHolder values to the backend, so that user edits survive page reloads and browser restarts.

#### Acceptance Criteria

1. THE `InputHolderRouter` SHALL expose a `PUT /api/optimizer/config` endpoint that accepts a partial or full set of InputHolder fields and persists them via `SettingsService.update_preferences`.
2. WHEN a valid `PUT /api/optimizer/config` request is received, THE `InputHolderService` SHALL call `SettingsService.update_preferences("optimizer_preferences", **fields)` to atomically write the changes to `data/settings.json`.
3. WHEN a valid `PUT /api/optimizer/config` request is received, THE `InputHolderRouter` SHALL return the full updated `OptimizerPreferences` state (not just the changed fields) with HTTP 200.
4. IF the request body contains an unknown field name, THEN THE `InputHolderRouter` SHALL return HTTP 422 with a descriptive validation error.
5. IF `SettingsService.update_preferences` raises a `RuntimeError` (disk write failure), THEN THE `InputHolderRouter` SHALL return HTTP 500 with an error message and SHALL NOT return a partial success response.
6. WHEN `dry_run_wallet` is provided in the request, THE `InputHolderService` SHALL reject values less than or equal to zero with HTTP 422.
7. WHEN `max_open_trades` is provided in the request, THE `InputHolderService` SHALL reject values less than 1 with HTTP 422.

---

### Requirement 4: Preset Resolution

**User Story:** As a user, I want to select a named Preset (e.g. "30d") and have the backend compute the correct Timerange string, so that I do not have to manually type dates.

#### Acceptance Criteria

1. THE `InputHolderService` SHALL support at minimum the following preset keys: `"7d"`, `"14d"`, `"30d"`, `"60d"`, `"90d"`, `"180d"`, `"1y"`.
2. WHEN a `PUT /api/optimizer/config` request includes a `last_timerange_preset` value that matches a known preset key, THE `InputHolderService` SHALL compute the corresponding `default_timerange` as `YYYYMMDD-YYYYMMDD` relative to the current UTC date and persist both fields together.
3. WHEN a `PUT /api/optimizer/config` request includes a `last_timerange_preset` value that does not match any known preset key, THE `InputHolderService` SHALL persist the preset value as-is and SHALL NOT overwrite the existing `default_timerange`.
4. FOR ALL known preset keys, resolving a preset and then re-resolving the same preset on the same UTC day SHALL produce the same `default_timerange` string (idempotence property).

---

### Requirement 5: Pairs Persistence

**User Story:** As a user, I want my selected trading pairs to be saved to the backend, so that the Pairs field is pre-populated with my last selection when I return to the page.

#### Acceptance Criteria

1. WHEN a `PUT /api/optimizer/config` request includes a `default_pairs` value, THE `InputHolderService` SHALL persist the value as a comma-separated string in `OptimizerPreferences.default_pairs`.
2. WHEN `GET /api/optimizer/config` is called, THE `InputHolderRouter` SHALL return `default_pairs` as both a raw comma-separated string and as a parsed `List[str]` field (`pairs_list`) so the UI can populate a multi-select widget without client-side splitting.
3. IF `default_pairs` contains duplicate pair entries, THEN THE `InputHolderService` SHALL deduplicate the list while preserving insertion order before persisting.

---

### Requirement 6: Strategy Field Persistence

**User Story:** As a user, I want the Strategy dropdown to remember my last selection, so that I do not have to re-select the same strategy every time I open the optimizer.

#### Acceptance Criteria

1. WHEN a `PUT /api/optimizer/config` request includes a `last_strategy` value, THE `InputHolderService` SHALL persist it in `OptimizerPreferences.last_strategy`.
2. WHEN `GET /api/optimizer/config` is called and `last_strategy` is a non-empty string, THE `InputHolderRouter` SHALL return the stored strategy name so the UI can pre-select it in the dropdown.
3. IF `last_strategy` is an empty string, THE `InputHolderRouter` SHALL return an empty string (not null) so the UI can treat it as "no selection" without null-checking.

---

### Requirement 7: Atomic Persistence and Consistency

**User Story:** As a developer, I want all InputHolder writes to be atomic, so that a crash or concurrent write never leaves `settings.json` in a partially-written state.

#### Acceptance Criteria

1. THE `InputHolderService` SHALL delegate all file writes to `SettingsService.update_preferences`, which uses `write_json_file_atomic` internally, ensuring writes are atomic at the OS level.
2. WHEN two concurrent `PUT /api/optimizer/config` requests arrive, THE `SettingsService` SHALL serialise the writes so that the final state of `data/settings.json` reflects one complete update and not a merge of partial writes.
3. WHEN `GET /api/optimizer/config` is called immediately after a successful `PUT /api/optimizer/config`, THE returned values SHALL match the values that were written (read-your-writes consistency).

---

### Requirement 8: API Registration and Routing

**User Story:** As a backend developer, I want the InputHolder endpoints registered in the FastAPI application, so that they are reachable under the `/api` prefix alongside existing routes.

#### Acceptance Criteria

1. THE `InputHolderRouter` SHALL be registered in `app/web/main.py` with the `/api` prefix and the `"optimizer-config"` tag.
2. THE `InputHolderRouter` SHALL reuse the `SettingsServiceDep` dependency from `app/web/dependencies.py` rather than instantiating `SettingsService` directly.
3. WHEN the FastAPI application starts, THE `GET /api/optimizer/config` and `PUT /api/optimizer/config` endpoints SHALL appear in the OpenAPI schema at `/docs`.
