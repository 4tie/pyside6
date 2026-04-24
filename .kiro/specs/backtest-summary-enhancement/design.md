# Design Document: Backtest Summary Enhancement

## Overview

The current `_build_summary()` method in `ResultsPage` renders all ~23 fields as a flat, unstyled label/value list with no visual hierarchy. This design replaces it with a structured, color-coded, sectioned layout that makes backtest results immediately scannable.

The enhancement is entirely self-contained within `app/ui/pages/results_page.py`. It introduces:

- A **KPI row** of `StatCard` widgets at the top with dynamic accent colors
- Four **section cards** below, each with a titled header and a two-column `QGridLayout`
- **Color-coding pure functions** that map numeric values to theme color tokens
- A **pairs badge widget** built from PySide6 primitives using a wrapping `QWidget` + `QFlowLayout`-style approach
- A **balance delta label** inline with the Final Balance value

No new files, no new dependencies. All logic stays in `ResultsPage`.

---

## Architecture

The redesigned `_build_summary()` follows a clear construction sequence:

```
_build_summary(run)
  │
  ├── _clear_summary_layout()          # remove all existing widgets
  │
  ├── _build_kpi_row(run)              # returns QHBoxLayout of StatCards
  │   ├── _profit_accent_color(value)  # GREEN / RED
  │   └── _drawdown_accent_color(value)# RED / YELLOW
  │
  ├── _summary_section("Overview", fields)
  ├── _summary_section("Performance", fields)
  │   └── _balance_delta_widget(start, final)
  ├── _summary_section("Trade Statistics", fields)
  ├── _summary_section("Risk Metrics", fields)
  │
  └── addStretch()
```

Color-coding for field values is handled by three pure functions:

```
_profit_color(value: float) -> str        # GREEN / RED / TEXT_PRIMARY
_win_rate_color(value: float) -> str      # GREEN / RED
_sharpe_color(value: float) -> str        # GREEN / YELLOW / RED
_profit_factor_color(value: float) -> str # GREEN / RED
```

These functions are pure (no side effects, no Qt dependencies) and are the primary targets for property-based testing.

---

## Components and Interfaces

### `_build_summary(run: dict) -> None`

Replaces the existing method entirely. Orchestrates the full rebuild:

1. Clears the existing `_summary_layout`
2. Builds and adds the KPI row
3. Builds and adds each of the four section cards
4. Appends a stretch

**Error handling**: wrapped in `try/except Exception` — on failure, logs via `_log.warning` and leaves the layout in a cleared state.

---

### `_build_kpi_row(run: dict) -> QWidget`

Returns a `QWidget` containing a `QHBoxLayout` of six `StatCard` instances:

| Card | Field | Accent Logic |
|------|-------|-------------|
| Total Profit % | `profit_total_pct` | `_profit_accent_color(v)` |
| Win Rate | `win_rate_pct` | `theme.ACCENT` (fixed) |
| Total Trades | `trades_count` | `theme.PURPLE` (fixed) |
| Max Drawdown % | `max_drawdown_pct` | `_drawdown_accent_color(v)` |
| Sharpe Ratio | `sharpe` | `theme.ACCENT` (fixed) |
| Profit Factor | `profit_factor` | `theme.GREEN` (fixed) |

Each `StatCard` is constructed with `accent_color=<computed>` at build time. Missing values display `"—"`. All cards use `QSizePolicy.Expanding` horizontally.

---

### `_summary_section(title: str, fields: list[tuple[str, str, str]]) -> QFrame`

Private helper that builds a titled, bordered section card.

**Parameters:**
- `title` — section header text (e.g. `"OVERVIEW"`)
- `fields` — list of `(label, value, color)` tuples

**Returns:** A `QFrame` with:
- A `QVBoxLayout` containing:
  - A `QLabel` section header (11px, weight 600, `theme.TEXT_SECONDARY`, uppercase)
  - A `QFrame` card body (`theme.BG_SURFACE` background, `theme.BG_BORDER` border, 8px radius)
    - Inside: a `QGridLayout` with fields arranged in two columns
    - Each field: label `QLabel` (11px, `theme.TEXT_SECONDARY`) + value `QLabel` (13px, weight 500, color from tuple)
    - Minimum column width: 200px via `setColumnMinimumWidth`
    - Odd-count sections: last grid cell left empty

**Field tuple format:** `(label_text, value_text, color_hex)` where `color_hex` is one of the theme constants.

---

### `_build_pairs_widget(pairs: list[str]) -> QWidget`

Builds the pairs display for the Overview section.

- **Empty list**: returns a single `QLabel("—")` with `theme.TEXT_PRIMARY`
- **Non-empty list**: returns a `QWidget` with a custom wrapping layout

**Wrapping layout approach** (pure PySide6, no third-party layout managers):

A `QWidget` subclass is not needed. Instead, use a `QWidget` with a `QVBoxLayout` containing rows of `QHBoxLayout`, where each row is filled with badge `QLabel` widgets. Since we cannot know the container width at build time, we use a `FlowLayout`-compatible approach: override `resizeEvent` on the container widget to re-flow badges when width changes.

**Simpler alternative** (chosen for implementation): Use a fixed-width-aware approach — render badges in a `QWidget` with a custom `paintEvent`-free layout. Concretely, use a `QWidget` that holds all badge `QLabel`s and overrides `resizeEvent` to reposition them manually using `setGeometry`. This is the standard PySide6 pattern for flow layouts without third-party dependencies.

Each badge `QLabel`:
- Text: pair name (e.g. `"BTC/USDT"`)
- StyleSheet: `background: {theme.ACCENT_DIM}; color: {theme.ACCENT}; border-radius: 10px; padding: 2px 8px; font-size: 11px; font-weight: 600;`

---

### `_balance_delta_widget(starting: float, final: float) -> QWidget | None`

Returns a `QLabel` delta indicator, or `None` if balances are equal.

- `final > starting`: `QLabel(f"+{final - starting:.2f} USDT")`, color `theme.GREEN`
- `final < starting`: `QLabel(f"−{final - starting:.2f} USDT")` (note: Unicode minus `−`), color `theme.RED`
- `final == starting`: returns `None`

The Final Balance field in the Performance section is rendered as a `QHBoxLayout` containing the value `QLabel` and (if non-None) the delta `QLabel` side by side.

---

### Color-Coding Pure Functions

These are module-level (or static) pure functions with no Qt imports required:

```python
def _profit_color(value: float) -> str:
    """Map profit/return value to theme color."""
    if value > 0:   return theme.GREEN
    if value < 0:   return theme.RED
    return theme.TEXT_PRIMARY

def _win_rate_color(value: float) -> str:
    """Map win rate percentage to theme color."""
    return theme.GREEN if value >= 50.0 else theme.RED

def _sharpe_color(value: float) -> str:
    """Map Sharpe ratio to theme color."""
    if value >= 1.0:  return theme.GREEN
    if value > 0.0:   return theme.YELLOW
    return theme.RED

def _profit_factor_color(value: float) -> str:
    """Map profit factor to theme color."""
    return theme.GREEN if value >= 1.0 else theme.RED

def _profit_accent_color(value: float) -> str:
    """Map profit % to StatCard accent color."""
    return theme.GREEN if value >= 0 else theme.RED

def _drawdown_accent_color(value: float) -> str:
    """Map drawdown % to StatCard accent color."""
    return theme.RED if value > 20.0 else theme.YELLOW
```

These functions are defined at module level (outside the class) so they can be imported and tested independently without instantiating any Qt widgets.

---

## Data Models

No new data models are introduced. The `run: dict` passed to `_build_summary` is the same index entry dict already used throughout `ResultsPage`. Expected keys and their types:

| Key | Type | Default |
|-----|------|---------|
| `strategy` | `str` | `"—"` |
| `timeframe` | `str` | `"—"` |
| `timerange` | `str` | `"—"` |
| `backtest_start` | `str` | `"—"` |
| `backtest_end` | `str` | `"—"` |
| `pairs` | `list[str]` | `[]` |
| `run_id` | `str` | `"—"` |
| `saved_at` | `str` | `"—"` |
| `starting_balance` | `float` | `0.0` |
| `final_balance` | `float` | `0.0` |
| `profit_total_pct` | `float` | `0.0` |
| `profit_total_abs` | `float` | `0.0` |
| `profit_factor` | `float` | `0.0` |
| `expectancy` | `float` | `0.0` |
| `trades_count` | `int` | `0` |
| `wins` | `int` | `0` |
| `losses` | `int` | `0` |
| `win_rate_pct` | `float` | `0.0` |
| `max_drawdown_pct` | `float` | `0.0` |
| `max_drawdown_abs` | `float` | `0.0` |
| `sharpe` | `float \| None` | `None` |
| `sortino` | `float \| None` | `None` |
| `calmar` | `float \| None` | `None` |

All field accesses use `run.get(key, default)` to handle missing keys gracefully.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

The color-coding functions are pure functions with no Qt dependencies, making them ideal candidates for property-based testing with [Hypothesis](https://hypothesis.readthedocs.io/). The balance delta formatter is similarly pure. These are the highest-value targets for PBT in this feature.

**Property reflection**: After reviewing all testable criteria, several color-coding properties share the same structure (threshold → color). Properties 1–4 below consolidate the profit/win-rate/sharpe/profit-factor color rules into comprehensive partition-covering properties rather than listing each threshold separately. Properties 5–6 cover the KPI accent color rules. Properties 7–8 cover the balance delta behavior.

---

### Property 1: Profit color partitions the real line correctly

*For any* float value `v`, `_profit_color(v)` SHALL return exactly `theme.GREEN` when `v > 0`, `theme.RED` when `v < 0`, and `theme.TEXT_PRIMARY` when `v == 0`. The three cases are exhaustive and mutually exclusive.

**Validates: Requirements 3.1, 3.2, 3.3**

---

### Property 2: Win rate color threshold is monotone at 50.0

*For any* float `v >= 50.0`, `_win_rate_color(v)` SHALL return `theme.GREEN`. *For any* float `v` in `[0.0, 50.0)`, `_win_rate_color(v)` SHALL return `theme.RED`. The boundary at 50.0 is inclusive-GREEN.

**Validates: Requirements 3.4, 3.5**

---

### Property 3: Sharpe color partitions into three zones

*For any* float `v >= 1.0`, `_sharpe_color(v)` SHALL return `theme.GREEN`. *For any* float `v` in `(0.0, 1.0)`, `_sharpe_color(v)` SHALL return `theme.YELLOW`. *For any* float `v <= 0.0`, `_sharpe_color(v)` SHALL return `theme.RED`. The three zones are exhaustive and mutually exclusive.

**Validates: Requirements 3.6, 3.7, 3.8**

---

### Property 4: Profit factor color threshold is monotone at 1.0

*For any* float `v >= 1.0`, `_profit_factor_color(v)` SHALL return `theme.GREEN`. *For any* float `v` in `[0.0, 1.0)`, `_profit_factor_color(v)` SHALL return `theme.RED`.

**Validates: Requirements 3.9, 3.10**

---

### Property 5: KPI accent colors are consistent with profit color rules

*For any* float `v >= 0`, `_profit_accent_color(v)` SHALL return `theme.GREEN`. *For any* float `v < 0`, `_profit_accent_color(v)` SHALL return `theme.RED`. The boundary at 0 is inclusive-GREEN (zero profit is not a loss).

**Validates: Requirements 2.3, 2.4**

---

### Property 6: Drawdown accent color threshold is monotone at 20.0

*For any* float `v > 20.0`, `_drawdown_accent_color(v)` SHALL return `theme.RED`. *For any* float `v` in `[0.0, 20.0]`, `_drawdown_accent_color(v)` SHALL return `theme.YELLOW`.

**Validates: Requirements 2.5, 2.6**

---

### Property 7: Balance delta sign and color are consistent

*For any* pair `(starting, final)` where `final > starting`, the delta label text SHALL start with `"+"` and the color SHALL be `theme.GREEN`. *For any* pair where `final < starting`, the delta label text SHALL start with `"−"` and the color SHALL be `theme.RED`.

**Validates: Requirements 6.1, 6.2**

---

### Property 8: Balance delta formatting precision

*For any* pair `(starting, final)` where `final != starting`, the delta label text SHALL contain a value formatted to exactly two decimal places followed by `" USDT"`.

**Validates: Requirement 6.4**

---

### Property 9: _build_summary is idempotent on widget count

*For any* valid run dict, calling `_build_summary` twice in succession SHALL produce the same number of top-level widgets in `_summary_layout` as calling it once. No widget accumulation occurs across rebuilds.

**Validates: Requirement 7.2**

---

### Property 10: _build_summary is robust to missing fields

*For any* subset of the expected run dict keys (including the empty dict), calling `_build_summary` SHALL complete without raising an exception, and every field whose key is absent SHALL display `"—"`.

**Validates: Requirement 7.3**

---

## Error Handling

### `_build_summary` exception guard

```python
def _build_summary(self, run: dict) -> None:
    self._clear_summary_layout()
    try:
        # ... build KPI row and sections ...
    except Exception as exc:
        _log.warning("_build_summary failed: %s", exc)
        # layout is already cleared; leave it empty
```

The clear step happens before the try block so that on failure the tab shows an empty state rather than stale content.

### Missing field defaults

All `run.get(key, default)` calls use safe defaults:
- Numeric fields: `0` or `0.0`
- String fields: `"—"`
- List fields: `[]`
- Optional float fields (`sharpe`, `sortino`, `calmar`): `None`, formatted as `"—"` when `None`

### Pairs badge widget

The `_build_pairs_widget` function handles `pairs=[]` by returning a plain `QLabel("—")` rather than an empty flow container, avoiding any layout edge cases with zero children.

---

## Testing Strategy

### Dual Testing Approach

Unit tests cover specific examples, edge cases, and structural checks. Property-based tests (via **Hypothesis**) cover the pure color-coding and formatting functions across the full input space.

### Property-Based Tests (Hypothesis)

Each property from the Correctness Properties section maps to one `@given`-decorated test. Tests are configured with `settings(max_examples=200)` for thorough coverage.

**Test file:** `tests/ui/test_summary_color_functions.py`

```python
# Feature: backtest-summary-enhancement, Property 1: profit color partitions
@given(st.floats(min_value=0.001, allow_nan=False, allow_infinity=False))
def test_profit_color_positive(v): assert _profit_color(v) == theme.GREEN

@given(st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False))
def test_profit_color_negative(v): assert _profit_color(v) == theme.RED
```

Tag format: `# Feature: backtest-summary-enhancement, Property {N}: {property_text}`

Properties covered by PBT:
- **Property 1** — `_profit_color` partitioning (positive, negative, zero edge case)
- **Property 2** — `_win_rate_color` threshold at 50.0
- **Property 3** — `_sharpe_color` three-zone partitioning
- **Property 4** — `_profit_factor_color` threshold at 1.0
- **Property 5** — `_profit_accent_color` partitioning
- **Property 6** — `_drawdown_accent_color` threshold at 20.0
- **Property 7** — balance delta sign and color consistency
- **Property 8** — balance delta formatting precision

### Unit Tests (pytest, example-based)

**Test file:** `tests/ui/test_build_summary.py`

Requires a `QApplication` fixture (one per session). Tests instantiate `ResultsPage` with a mock `SettingsState` and call `_build_summary` directly.

Key example tests:
- KPI row contains 6 `StatCard` instances with correct labels
- All KPI cards show `"—"` when run dict is empty (Requirement 2.8)
- Section headers exist with correct titles (Requirement 1.1)
- Field-to-section placement for all four sections (Requirements 1.4–1.7)
- Pairs badge count matches pairs list length (Requirement 5.1)
- Empty pairs list shows `"—"` (Requirement 5.3)
- Equal balances produce no delta label (Requirement 6.3)
- `_build_summary` called twice produces same widget count (Property 9)
- Missing fields display `"—"` without exception (Property 10)
- Exception during build triggers `_log.warning` (Requirement 7.4)

### What is NOT unit-tested

- Badge wrapping/reflow behavior (requires rendered geometry — visual/manual verification)
- Exact pixel layout of the two-column grid (layout engine responsibility)
