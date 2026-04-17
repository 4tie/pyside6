# Requirements Document

## Introduction

This feature adds a favorite-pair system to the Pairs Selector dialog in the Freqtrade GUI desktop app. Each pair in the list will display a heart icon button that users can click to toggle the pair as a favorite. Favorited pairs are sorted to the top of the list and persisted across sessions via the existing `AppSettings` / `SettingsState` infrastructure.

The feature touches three layers:
- **Model layer** — a single shared `favorite_pairs` list on `AppSettings` (replacing the per-section `paired_favorites` fields, or supplementing them)
- **State layer** — `SettingsState` exposes a signal and mutation method for toggling favorites
- **UI layer** — `PairsSelectorDialog` renders a heart button per row and re-orders the list when favorites change

---

## Glossary

- **Dialog**: `PairsSelectorDialog` — the Qt `QDialog` used to select trading pairs
- **FavoriteButton**: A `QPushButton` (or `QToolButton`) rendered per pair row that displays a filled heart (♥) when the pair is favorited and an outline heart (♡) when it is not
- **FavoritePairs**: The ordered list of pair strings that the user has marked as favorites; stored in `AppSettings`
- **PairRow**: A single horizontal layout within the Dialog's scroll area containing a `FavoriteButton` and a `QCheckBox` for one pair
- **SettingsState**: The `QObject` subclass in `app/app_state/settings_state.py` that owns `AppSettings` and emits Qt signals on change
- **AppSettings**: The top-level Pydantic model in `app/core/models/settings_models.py` persisted at `~/.freqtrade_gui/settings.json`
- **Section**: One of `BacktestPreferences`, `OptimizePreferences`, or `DownloadPreferences` — each currently holds its own `paired_favorites` list

---

## Requirements

### Requirement 1: Heart Icon Per Pair Row

**User Story:** As a trader, I want to see a heart icon next to every pair in the selector dialog, so that I can visually identify and toggle favorites at a glance.

#### Acceptance Criteria

1. THE Dialog SHALL render a FavoriteButton to the left of the pair checkbox for every pair displayed in the scroll area.
2. WHEN a pair is in FavoritePairs, THE FavoriteButton SHALL display a filled heart character (♥).
3. WHEN a pair is not in FavoritePairs, THE FavoriteButton SHALL display an outline heart character (♡).
4. THE FavoriteButton SHALL have a fixed width of 28 pixels and no visible border so it does not disrupt the row layout.
5. WHEN a custom pair is added via the "Add Custom Pairs" input, THE Dialog SHALL render a FavoriteButton for that pair using the same rules as Acceptance Criteria 1–4.

---

### Requirement 2: Toggle Favorite on Click

**User Story:** As a trader, I want to click the heart icon to add or remove a pair from my favorites, so that I can manage my favorites without leaving the dialog.

#### Acceptance Criteria

1. WHEN the FavoriteButton for a non-favorited pair is clicked, THE Dialog SHALL add that pair to FavoritePairs.
2. WHEN the FavoriteButton for a favorited pair is clicked, THE Dialog SHALL remove that pair from FavoritePairs.
3. WHEN FavoritePairs changes, THE FavoriteButton icon SHALL update immediately to reflect the new state (filled ↔ outline) without requiring a dialog restart.
4. WHEN FavoritePairs changes, THE Dialog SHALL re-sort the visible pair list so that all favorited pairs appear before all non-favorited pairs, preserving alphabetical order within each group.
5. IF a pair appears in the search filter results, THEN THE Dialog SHALL apply the favorite-first ordering only within the visible (filtered) rows.

---

### Requirement 3: Favorites Persisted Across Sessions

**User Story:** As a trader, I want my favorite pairs to be saved automatically, so that my favorites are still present the next time I open the application.

#### Acceptance Criteria

1. THE AppSettings SHALL contain a `favorite_pairs` field of type `list[str]` with an empty list as the default value.
2. WHEN FavoritePairs changes in the Dialog, THE Dialog SHALL call `SettingsState.toggle_favorite_pair(pair: str)` to persist the change.
3. WHEN `SettingsState.toggle_favorite_pair` is called, THE SettingsState SHALL update `AppSettings.favorite_pairs` and call `save_settings` so the change is written to `~/.freqtrade_gui/settings.json`.
4. WHEN the Dialog is opened, THE Dialog SHALL initialise FavoritePairs from `AppSettings.favorite_pairs` passed in by the caller.
5. WHEN `AppSettings` is loaded from disk and the `favorite_pairs` field is absent, THE AppSettings SHALL default `favorite_pairs` to an empty list without raising a validation error.

---

### Requirement 4: Favorites Shown First in the List

**User Story:** As a trader, I want my favorite pairs to appear at the top of the pair list, so that I can quickly find and select the pairs I use most often.

#### Acceptance Criteria

1. WHEN the Dialog is initialised, THE Dialog SHALL display all pairs in FavoritePairs before all non-favorited pairs.
2. WITHIN the favorited group, THE Dialog SHALL sort pairs alphabetically by pair string.
3. WITHIN the non-favorited group, THE Dialog SHALL sort pairs alphabetically by pair string.
4. WHEN the search filter is active, THE Dialog SHALL maintain the favorite-first ordering among the visible rows.
5. WHEN a pair is toggled as a favorite, THE Dialog SHALL move that pair's row to the correct position in the sorted order within 100 ms of the button click.

---

### Requirement 5: Shared Favorites Across All Sections

**User Story:** As a trader, I want my favorite pairs to be shared across the Backtest, Optimize, and Download sections, so that I only need to manage one favorites list.

#### Acceptance Criteria

1. THE AppSettings SHALL expose `favorite_pairs` as a top-level field, not nested inside `BacktestPreferences`, `OptimizePreferences`, or `DownloadPreferences`.
2. WHEN any page (Backtest, Optimize, Download) opens the Dialog, THE page SHALL pass `settings.favorite_pairs` as the `favorites` argument.
3. WHEN the Dialog closes and favorites have changed, THE page SHALL persist the updated favorites via `SettingsState.toggle_favorite_pair` or an equivalent bulk-update method.
4. IF `BacktestPreferences.paired_favorites`, `OptimizePreferences.paired_favorites`, or `DownloadPreferences.paired_favorites` exist in a saved `settings.json`, THEN THE AppSettings loader SHALL migrate those values into `AppSettings.favorite_pairs` on first load, deduplicating entries.
