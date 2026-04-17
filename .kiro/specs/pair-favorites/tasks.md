# Implementation Plan: Pair Favorites

## Overview

Implement a persistent favorites system for the `PairsSelectorDialog`. The work proceeds bottom-up: model → state → dialog → caller pages. Each layer is independently testable before the next is wired in.

## Tasks

- [x] 1. Update `AppSettings` model with `favorite_pairs` field and migration validator
  - Add `favorite_pairs: list[str] = Field(default_factory=list, ...)` to `AppSettings` in `app/core/models/settings_models.py`
  - Add `@model_validator(mode="before")` `migrate_legacy_favorites` that collects `paired_favorites` from `backtest_preferences`, `optimize_preferences`, and `download_preferences` raw dicts, deduplicates (preserving order), and writes into `favorite_pairs` only when the top-level field is absent or empty
  - _Requirements: 3.1, 3.5, 5.1, 5.4_

  - [x] 1.1 Write property test for legacy migration deduplication
    - **Property 6: Legacy migration produces deduplicated union**
    - Generate three random lists of pair strings (possibly overlapping), build a raw dict with per-section `paired_favorites` and no top-level `favorite_pairs`, load `AppSettings`, assert `favorite_pairs` equals the deduplicated union with no duplicates
    - **Validates: Requirements 5.4**

  - [x] 1.2 Write unit tests for `AppSettings.favorite_pairs`
    - `AppSettings()` defaults `favorite_pairs` to `[]`
    - `AppSettings(**data_without_favorite_pairs)` does not raise
    - `AppSettings` exposes `favorite_pairs` at top level (not nested inside any preferences sub-model)
    - _Requirements: 3.1, 3.5, 5.1_

- [x] 2. Add `toggle_favorite_pair` method and `favorites_changed` signal to `SettingsState`
  - Add `favorites_changed = Signal(list)` class attribute to `SettingsState` in `app/app_state/settings_state.py`
  - Implement `toggle_favorite_pair(self, pair: str) -> None`: guard on `self.current_settings`, copy the list, add or remove `pair`, assign back, call `self.save_settings(self.current_settings)`, emit `favorites_changed` with the new list
  - _Requirements: 3.2, 3.3_

  - [x] 2.1 Write property test for `toggle_favorite_pair` mutation and persistence
    - **Property 5: `toggle_favorite_pair` mutates and persists**
    - Generate a random `AppSettings` instance and a random pair string, mock `SettingsService.save_settings`, call `toggle_favorite_pair`, assert membership flipped and `save_settings` called exactly once; repeat for the reverse direction
    - **Validates: Requirements 3.2, 3.3**

- [x] 3. Refactor `PairsSelectorDialog` to support favorites
  - Update constructor signature to `__init__(self, favorites: list[str], selected: list[str], settings_state: SettingsState, parent=None)` in `app/ui/dialogs/pairs_selector_dialog.py`
  - Add instance attributes: `self.favorites: set[str]`, `self.fav_buttons: dict[str, QPushButton]`, `self.row_widgets: dict[str, QWidget]`
  - Replace the checkbox-only loop in `init_ui` with `_build_rows()` that creates a `QHBoxLayout` per pair containing a `FavoriteButton` (via `_make_favorite_button`) and the existing `QCheckBox`; store the row container in `self.row_widgets`
  - Implement `_make_favorite_button(self, pair: str) -> QPushButton`: flat button, `setFixedWidth(28)`, `setFlat(True)`, text `"♥"` if pair in favorites else `"♡"`, no border stylesheet
  - Implement `_on_favorite_clicked(self, pair: str)`: toggle `self.favorites`, update button text, call `self.settings_state.toggle_favorite_pair(pair)`, call `_sort_rows()`
  - Implement `_sort_rows(self)`: collect visible pairs, compute `sorted(visible ∩ favorites) + sorted(visible − favorites)`, remove all row widgets from layout, re-insert in computed order, append stretch
  - Update `_filter_pairs(self, text: str)` to show/hide `self.row_widgets[pair]` (not individual checkboxes) and call `_sort_rows()` after updating visibility
  - Update `_on_add_custom` to also create a `FavoriteButton` for each new pair and add it to `self.fav_buttons` and `self.row_widgets`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 3.1 Write property test for every pair having a FavoriteButton
    - **Property 1: Every pair has a FavoriteButton**
    - Generate a random list of pair strings, construct the dialog (with a mock `SettingsState`), assert `len(dialog.fav_buttons) == len(dialog.all_pairs)`
    - **Validates: Requirements 1.1, 1.5**

  - [x] 3.2 Write property test for FavoriteButton text reflecting favorites state
    - **Property 2: FavoriteButton text reflects favorites state**
    - Generate a random pairs list and a random favorites subset, construct the dialog, assert each button text is `"♥"` iff the pair is in favorites
    - **Validates: Requirements 1.2, 1.3**

  - [x] 3.3 Write property test for toggle round-trip
    - **Property 3: Toggle adds then removes (round-trip)**
    - Generate a random pairs list and a non-favorited pair, click its button, assert added; click again, assert removed and state equals original; mock `SettingsState.toggle_favorite_pair` to avoid disk I/O
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [x] 3.4 Write property test for favorites-first ordering
    - **Property 4: Displayed order is favorites-first, alphabetical within groups**
    - Generate a random pairs list, a random favorites subset, and an optional search text, construct the dialog, apply filter, collect visible row order from layout, assert equals `sorted(visible ∩ fav) + sorted(visible − fav)`
    - **Validates: Requirements 2.4, 2.5, 4.1, 4.2, 4.3, 4.4**

- [x] 4. Checkpoint — ensure model, state, and dialog tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Update caller pages to use the new `PairsSelectorDialog` signature
  - In `BacktestPage._on_select_pairs` (`app/ui/pages/backtest_page.py`): replace `favorites = settings.backtest_preferences.paired_favorites` with `settings.favorite_pairs`; pass `settings_state=self.settings_state` to the dialog constructor; remove the post-close favorites persistence block
  - In `BacktestPage._save_preferences_to_settings`: remove the loop that appends to `prefs.paired_favorites`
  - In `OptimizePage._on_select_pairs` (`app/ui/pages/optimize_page.py`): same pattern — use `settings.favorite_pairs` and pass `settings_state`
  - In `OptimizePage._save_preferences`: remove the loop that appends to `prefs.paired_favorites`
  - In `DownloadDataPage._on_select_pairs` (`app/ui/pages/download_data_page.py`): same pattern
  - In `DownloadDataPage._save_preferences`: remove the loop that appends to `prefs.paired_favorites`
  - _Requirements: 5.2, 5.3, 3.4_

  - [x] 5.1 Write unit tests for caller page integration
    - For each page, assert that `_on_select_pairs` passes `settings.favorite_pairs` (not a per-section field) to the dialog constructor
    - Assert that `settings_state` is forwarded correctly
    - _Requirements: 5.2, 5.3_

- [x] 6. Final checkpoint — ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Property tests use `@settings(max_examples=100)` and tag each test with `# Feature: pair-favorites, Property N: <text>`
- Mock `SettingsService.save_settings` in all state/dialog tests to avoid disk I/O
- The `QApplication` instance required for Qt widget tests can be shared via a `pytest` session-scoped fixture
- `paired_favorites` on the three `*Preferences` models is intentionally left in place (not removed) to preserve backward-compatible JSON loading; the migration validator handles the transition
