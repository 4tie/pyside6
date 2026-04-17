# Design Document: Pair Favorites

## Overview

This feature adds a persistent favorites system to the `PairsSelectorDialog`. Each pair row gains a heart toggle button (♥/♡) that marks the pair as a favorite. Favorited pairs sort to the top of the list and are persisted in a single shared `AppSettings.favorite_pairs` field, replacing the per-section `paired_favorites` lists that currently live on `BacktestPreferences`, `OptimizePreferences`, and `DownloadPreferences`.

The change touches three layers in the existing architecture:

- **Model layer** — add `favorite_pairs: list[str]` to `AppSettings`; add a `model_validator` to migrate legacy per-section favorites on first load
- **State layer** — add `toggle_favorite_pair(pair)` and a `favorites_changed` signal to `SettingsState`
- **UI layer** — refactor `PairsSelectorDialog` to render a `FavoriteButton` per row, re-sort on toggle, and call `SettingsState.toggle_favorite_pair`; update the three caller pages to pass `settings.favorite_pairs`

---

## Architecture

```
BacktestPage / OptimizePage / DownloadDataPage
        │  passes settings.favorite_pairs
        ▼
PairsSelectorDialog
  ├── _build_rows()          builds PairRow widgets (FavoriteButton + QCheckBox)
  ├── _on_favorite_clicked() toggles favorite, calls SettingsState, re-sorts
  ├── _sort_rows()           reorders widgets: sorted(fav) + sorted(non-fav)
  └── _filter_pairs()        hides/shows rows; sort order preserved
        │  calls toggle_favorite_pair(pair)
        ▼
SettingsState
  ├── toggle_favorite_pair(pair)  mutates AppSettings.favorite_pairs, saves
  └── Signal: favorites_changed(list[str])
        │
        ▼
SettingsService.save_settings()  → ~/.freqtrade_gui/settings.json
        │
        ▼
AppSettings.favorite_pairs: list[str]   (top-level field)
  └── model_validator migrates legacy BacktestPreferences / OptimizePreferences
      / DownloadPreferences .paired_favorites on first load
```

---

## Components and Interfaces

### 1. `AppSettings` (model layer)

Add one field and one migration validator:

```python
favorite_pairs: list[str] = Field(
    default_factory=list,
    description="Shared favorite trading pairs across all sections",
)

@model_validator(mode="before")
@classmethod
def migrate_legacy_favorites(cls, data: Any) -> Any:
    """Merge per-section paired_favorites into top-level favorite_pairs."""
    ...
```

The validator collects `paired_favorites` from `backtest_preferences`, `optimize_preferences`, and `download_preferences` (if present in the raw dict), deduplicates them, and writes the result into `favorite_pairs` only when `favorite_pairs` is absent or empty in the raw data.

### 2. `SettingsState` (state layer)

Add one signal and one method:

```python
favorites_changed = Signal(list)   # emits updated list[str]

def toggle_favorite_pair(self, pair: str) -> None:
    """Add pair to favorites if absent, remove if present; save and emit."""
    ...
```

The method mutates `self.current_settings.favorite_pairs` in-place, calls `save_settings`, and emits `favorites_changed` with the new list.

### 3. `PairsSelectorDialog` (UI layer)

**Constructor signature change:**

```python
def __init__(
    self,
    favorites: list[str],
    selected: list[str],
    settings_state: SettingsState,   # NEW — replaces implicit favorites management
    parent=None,
):
```

**New internal structures:**

```python
self.favorites: set[str]                    # mutable during dialog lifetime
self.fav_buttons: dict[str, QPushButton]    # pair → FavoriteButton widget
self.row_widgets: dict[str, QWidget]        # pair → full row widget
```

**Key new/changed methods:**

| Method | Responsibility |
|---|---|
| `_build_rows()` | Replaces the old checkbox-only loop; creates `PairRow` (FavoriteButton + QCheckBox) per pair |
| `_make_favorite_button(pair)` | Returns a flat `QPushButton` with fixed width 28, text ♥ or ♡ |
| `_on_favorite_clicked(pair)` | Toggles `self.favorites`, updates button text, calls `settings_state.toggle_favorite_pair`, calls `_sort_rows()` |
| `_sort_rows()` | Removes all row widgets from layout, re-inserts in order: `sorted(fav ∩ visible)` + `sorted(non-fav ∩ visible)` |
| `_filter_pairs(text)` | Shows/hides rows by search text; calls `_sort_rows()` after visibility update |
| `_on_add_custom(pair)` | Unchanged logic, but now also creates a FavoriteButton for the new row |

### 4. Caller pages (`BacktestPage`, `OptimizePage`, `DownloadDataPage`)

Each page's `_on_select_pairs` method changes from:

```python
# Before
favorites = settings.backtest_preferences.paired_favorites
dialog = PairsSelectorDialog(favorites, self.selected_pairs, self)
```

to:

```python
# After
dialog = PairsSelectorDialog(
    favorites=settings.favorite_pairs,
    selected=self.selected_pairs,
    settings_state=self.settings_state,
    parent=self,
)
```

The pages no longer need to manually persist favorites after dialog close — `PairsSelectorDialog` calls `settings_state.toggle_favorite_pair` on each toggle in real time.

The `_save_preferences` / `_save_preferences_to_settings` methods in each page should stop appending to `prefs.paired_favorites` (that field becomes deprecated).

---

## Data Models

### `AppSettings` (updated)

```python
class AppSettings(BaseModel):
    # ... existing fields ...
    favorite_pairs: list[str] = Field(
        default_factory=list,
        description="Shared favorite trading pairs across all sections",
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_favorites(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        # Only migrate when top-level field is absent or empty
        if data.get("favorite_pairs"):
            return data
        collected: list[str] = []
        for section_key in ("backtest_preferences", "optimize_preferences", "download_preferences"):
            section = data.get(section_key)
            if isinstance(section, dict):
                for pair in section.get("paired_favorites", []):
                    if pair not in collected:
                        collected.append(pair)
        if collected:
            data["favorite_pairs"] = collected
        return data
```

### `SettingsState` (updated)

```python
favorites_changed = Signal(list)

def toggle_favorite_pair(self, pair: str) -> None:
    if not self.current_settings:
        return
    favs = list(self.current_settings.favorite_pairs)
    if pair in favs:
        favs.remove(pair)
    else:
        favs.append(pair)
    self.current_settings.favorite_pairs = favs
    self.save_settings(self.current_settings)
    self.favorites_changed.emit(favs)
```

### Row ordering algorithm

```
visible_pairs = [p for p in all_pairs if row_widgets[p].isVisible()]
ordered = sorted(p for p in visible_pairs if p in self.favorites)
        + sorted(p for p in visible_pairs if p not in self.favorites)
```

This runs in O(n log n) and is fast enough for the ~200-pair list.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Every pair has a FavoriteButton

*For any* list of pairs (including custom-added pairs) passed to `PairsSelectorDialog`, every pair in the scroll area SHALL have a corresponding `FavoriteButton` widget.

**Validates: Requirements 1.1, 1.5**

---

### Property 2: FavoriteButton text reflects favorites state

*For any* set of pairs and any favorites list, each pair's `FavoriteButton` text SHALL be `"♥"` if the pair is in favorites and `"♡"` if it is not.

**Validates: Requirements 1.2, 1.3, 3.4**

---

### Property 3: Toggle adds then removes (round-trip)

*For any* pair not currently in favorites, clicking its `FavoriteButton` once SHALL add it to favorites; clicking it again SHALL remove it, restoring the original state.

**Validates: Requirements 2.1, 2.2, 2.3**

---

### Property 4: Displayed order is favorites-first, alphabetical within groups

*For any* pairs list and favorites set, the order of visible rows in the dialog SHALL equal `sorted(visible ∩ favorites) + sorted(visible − favorites)`, both at initialization and after any toggle or search-filter change.

**Validates: Requirements 2.4, 2.5, 4.1, 4.2, 4.3, 4.4**

---

### Property 5: `toggle_favorite_pair` mutates and persists

*For any* pair string, calling `SettingsState.toggle_favorite_pair(pair)` SHALL result in `AppSettings.favorite_pairs` containing the pair (if it was absent) or not containing it (if it was present), and `save_settings` SHALL be called exactly once.

**Validates: Requirements 3.2, 3.3**

---

### Property 6: Legacy migration produces deduplicated union

*For any* combination of `paired_favorites` lists across `BacktestPreferences`, `OptimizePreferences`, and `DownloadPreferences` in a raw settings dict that lacks a top-level `favorite_pairs` key, loading `AppSettings` SHALL produce a `favorite_pairs` list that is the deduplicated union of all three lists, with no duplicates.

**Validates: Requirements 5.4**

---

## Error Handling

| Scenario | Handling |
|---|---|
| `toggle_favorite_pair` called before settings loaded | Guard: `if not self.current_settings: return` |
| `save_settings` fails (disk full, permissions) | `SettingsService` logs the error and returns `False`; `toggle_favorite_pair` does not raise — the in-memory state is still updated |
| Custom pair string is empty or whitespace | `_on_add_custom` already strips and skips empty strings; no change needed |
| `favorite_pairs` field absent in legacy JSON | Pydantic `default_factory=list` handles this; migration validator runs before field validation |
| Duplicate pair in migration sources | The migration validator deduplicates using an ordered `if pair not in collected` check |

---

## Testing Strategy

The project uses **pytest** with **Hypothesis** (already present in `.hypothesis/`) for property-based testing.

### Unit / example tests

- `AppSettings()` defaults `favorite_pairs` to `[]`
- `AppSettings(**data_without_favorite_pairs)` does not raise
- `AppSettings` exposes `favorite_pairs` at top level (not nested)
- `FavoriteButton` has `fixedWidth == 28`
- Row order is correct after a single toggle (timing check: < 100 ms)
- Each page's `_on_select_pairs` passes `settings.favorite_pairs` to the dialog

### Property-based tests (Hypothesis)

Each property test uses `@settings(max_examples=100)` and references its design property via a comment tag:
`# Feature: pair-favorites, Property N: <property text>`

**Property 1 — Every pair has a FavoriteButton**
Generate: random list of pair strings → construct dialog → assert `len(dialog.fav_buttons) == len(all_pairs)`

**Property 2 — Button text reflects state**
Generate: random pairs list + random favorites subset → construct dialog → for each pair assert button text matches membership in favorites

**Property 3 — Toggle round-trip**
Generate: random pairs list + random non-favorited pair → click button → assert added; click again → assert removed and state equals original

**Property 4 — Favorites-first ordering**
Generate: random pairs list + random favorites subset + optional search text → construct dialog, apply filter → collect visible row order → assert equals `sorted(visible ∩ fav) + sorted(visible − fav)`

**Property 5 — `toggle_favorite_pair` mutates and persists**
Generate: random `AppSettings` + random pair string → call `toggle_favorite_pair` → assert membership flipped + `save_settings` called once (mock `SettingsService.save_settings`)

**Property 6 — Migration deduplication**
Generate: three random lists of pair strings (possibly overlapping) → build raw dict with per-section `paired_favorites` and no top-level `favorite_pairs` → load `AppSettings` → assert `favorite_pairs` equals deduplicated union, no duplicates
