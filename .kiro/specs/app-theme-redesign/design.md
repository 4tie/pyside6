# Design Document: App Theme Redesign

## Overview

The app-theme-redesign feature centralises the Freqtrade GUI's visual theme into a dedicated `app/ui/theme.py` module, eliminates scattered inline `setStyleSheet` calls across pages and widgets, enforces consistent spacing and typography, and adds a dark/light mode toggle that persists across sessions.

The current application already has a coherent dark VS Code-inspired look defined as a large `_STYLESHEET` string inside `main_window.py`. The problem is that individual pages and widgets override or supplement that stylesheet with ad-hoc inline calls, making the theme fragile and hard to evolve. This redesign extracts the stylesheet into a proper module, parameterises it with named constants, and wires the mode preference into `AppSettings`.

No new runtime behaviour is introduced — the feature is purely a UI/styling refactor with a settings extension.

---

## Architecture

### Current State

```
main_window.py
  └── _STYLESHEET (large hardcoded string)
  └── MainWindow.__init__ → self.setStyleSheet(_STYLESHEET)

pages/backtest_page.py       → inline setStyleSheet calls (export_label, pairs_display_label)
pages/optimize_page.py       → inline setStyleSheet calls (advisor panels, warning labels)
pages/download_data_page.py  → inline setStyleSheet calls (validation_label, pairs_display_label)
pages/strategy_config_page.py → inline setStyleSheet calls (status_label, path_label)
pages/settings_page.py       → inline setStyleSheet calls (python_path_display, validation_result)
widgets/terminal_widget.py   → apply_preferences() (intentional user-configurable override)
widgets/backtest_results_widget.py → inline setStyleSheet (export_path_label)
widgets/ai_chat_dock.py      → many inline setStyleSheet calls
widgets/data_status_widget.py → inline setStyleSheet (legend labels, summary_label)
```

### Target State

```
app/ui/theme.py
  ├── PALETTE: dict[str, str]       — named colour constants
  ├── SPACING: dict[str, int]       — named spacing constants
  ├── FONT: dict[str, str | int]    — named font constants
  ├── ThemeMode (enum)              — DARK | LIGHT
  └── build_stylesheet(mode) -> str — assembles QSS from constants

main_window.py
  └── MainWindow.__init__ → QApplication.instance().setStyleSheet(build_stylesheet(mode))
  └── _on_settings_saved  → re-applies stylesheet on theme_mode change

core/models/settings_models.py
  └── AppSettings.theme_mode: str   — "dark" | "light", default "dark"

All pages / widgets
  └── zero inline setStyleSheet calls (except TerminalWidget.apply_preferences)
  └── semantic variants applied via widget.setObjectName("warning_banner") etc.
```

### Dependency Flow

```
theme.py  ←  main_window.py  ←  pages/*  ←  widgets/*
              ↑
         settings_models.py (theme_mode field)
```

`theme.py` has no imports from the rest of the application — it is a pure data/string module. This keeps the dependency graph clean and makes the module trivially testable.

---

## Components and Interfaces

### `app/ui/theme.py`

The single new file introduced by this feature.

```python
from enum import Enum
from typing import Final

class ThemeMode(Enum):
    DARK = "dark"
    LIGHT = "light"

PALETTE: Final[dict] = { ... }   # dark palette (default)
_LIGHT_PALETTE: Final[dict] = { ... }

SPACING: Final[dict[str, int]] = {
    "xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24
}

FONT: Final[dict] = {
    "family": "...",
    "size_sm": 11,
    "size_base": 13,
    "size_lg": 15,
    "mono_family": "...",
}

def build_stylesheet(mode: ThemeMode = ThemeMode.DARK) -> str:
    """Return the complete application QSS string for the given mode."""
    ...
```

**Public surface:**
- `ThemeMode` — enum consumed by `MainWindow` and `SettingsPage`
- `PALETTE` — dict of named colour strings (dark palette, exported for any widget that needs a colour at runtime, e.g. `DataStatusWidget` legend)
- `SPACING` — dict of named spacing ints
- `FONT` — dict of named font values
- `build_stylesheet(mode)` — the only function; returns a `str`

### `app/ui/main_window.py` changes

- Remove `_STYLESHEET` module-level constant.
- In `__init__`: read `settings.theme_mode`, convert to `ThemeMode`, call `build_stylesheet(mode)`, pass to `QApplication.instance().setStyleSheet(...)`.
- In `_on_settings_saved`: compare old vs new `theme_mode`; if changed, re-apply stylesheet.
- Toolbar `setFixedHeight(40)`.

### `app/core/models/settings_models.py` changes

Add one field to `AppSettings`:

```python
theme_mode: str = Field("dark", description="UI colour mode: dark or light")
```

### Page and Widget changes (inline style removal)

Each file listed below has its inline `setStyleSheet` calls replaced with `widget.setObjectName("semantic_name")` calls. The QSS rules for those object names live in `theme.py`.

| File | Widgets to convert |
|------|--------------------|
| `backtest_page.py` | `export_label`, `pairs_display_label` |
| `optimize_page.py` | `data_warning_label`, `result_warning_label`, `_advisor_tips`, `_advisor_warnings`, `_advisor_status` |
| `download_data_page.py` | `validation_label`, `pairs_display_label` |
| `strategy_config_page.py` | `status_label` (ok/error states set via `setObjectName`), `_path_label` |
| `settings_page.py` | `python_path_display`, `freqtrade_path_display`, `validation_result` |
| `backtest_results_widget.py` | `_export_path_label` |
| `ai_chat_dock.py` | header background, scroll area, input area, `_provider_label`, `_no_model_label`, `_tools_btn`, `_input_edit`, error message labels |
| `data_status_widget.py` | legend colour labels, `_summary_label` |

`TerminalWidget.apply_preferences` is explicitly **excluded** — it applies user-configurable colours and must remain as an inline call.

### `app/ui/pages/settings_page.py` — theme mode selector

A `QComboBox` (or two `QRadioButton`s) is added to the Settings page under a new "Appearance" group, allowing the user to select Dark or Light mode. On save, `AppSettings.theme_mode` is updated and `MainWindow._on_settings_saved` re-applies the stylesheet.

### Layout changes — Params/Output split

`BacktestPage`, `OptimizePage`, and `DownloadDataPage` each receive:
- `Params_Panel` wrapped in a `QScrollArea`
- `Params_Panel` minimum width 260 px, maximum width 360 px
- Outer content margin `SPACING["lg"]` (16 px), row spacing `SPACING["sm"]` (8 px)
- `Output_Panel` outer margin `SPACING["sm"]` (8 px)
- Horizontal stretch ratio 1:2 (already present in all three pages — preserved)

---

## Data Models

### `AppSettings` extension

```python
class AppSettings(BaseModel):
    # ... existing fields ...
    theme_mode: str = Field(
        "dark",
        description="UI colour mode: dark or light"
    )
```

Validation: `theme_mode` is stored as a plain string (`"dark"` / `"light"`) to keep JSON serialisation simple and avoid an enum dependency in the model layer. `MainWindow` converts it to `ThemeMode` at read time.

### `PALETTE` structure (dark mode)

```python
PALETTE = {
    # Backgrounds
    "bg_base":      "#1e1e1e",   # main window / page background
    "bg_surface":   "#2d2d2d",   # panels, toolbar, dock title
    "bg_elevated":  "#3c3c3c",   # inputs, list items, disabled buttons

    # Borders
    "border":       "#3c3c3c",
    "border_focus": "#007acc",

    # Text
    "text_primary":   "#d4d4d4",
    "text_secondary": "#aaaaaa",
    "text_disabled":  "#666666",

    # Accent (VS Code blue)
    "accent":         "#0e639c",
    "accent_hover":   "#1177bb",
    "accent_pressed": "#0a4f7e",

    # Semantic
    "success": "#1a7a3c",
    "danger":  "#c72e2e",
    "warning": "#856404",
}
```

Light mode palette uses inverted backgrounds and adjusted text colours while keeping the same accent blue.

### `SPACING` structure

```python
SPACING = {
    "xs":  4,
    "sm":  8,
    "md": 12,
    "lg": 16,
    "xl": 24,
}
```

### `FONT` structure

```python
FONT = {
    "family":      "Segoe UI, SF Pro Display, Ubuntu, Helvetica Neue, Arial, sans-serif",
    "size_sm":     11,
    "size_base":   13,
    "size_lg":     15,
    "mono_family": "Consolas, Menlo, DejaVu Sans Mono, Courier New, monospace",
}
```

### QSS Object Name Conventions

| Object name | Widget type | Semantic meaning |
|-------------|-------------|-----------------|
| `warning_banner` | `QLabel` | Inline validation warning (yellow tint) |
| `success_banner` | `QLabel` | Inline success feedback (green tint) |
| `path_label` | `QLabel` | Secondary path/hint text |
| `hint_label` | `QLabel` | Small secondary/hint text |
| `status_ok` | `QLabel` | Status indicator — success state |
| `status_error` | `QLabel` | Status indicator — error state |
| `secondary` | `QPushButton` | Ghost/secondary action button |
| `danger` | `QPushButton` | Destructive action button |
| `success` | `QPushButton` | Positive action button |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: PALETTE completeness

*For any* `ThemeMode` value, `build_stylesheet(mode)` SHALL produce a string that contains a non-empty CSS rule for every key in `PALETTE` — i.e., no palette key is silently dropped from the generated QSS.

**Validates: Requirements 1.1, 1.3**

### Property 2: SPACING completeness

*For any* `ThemeMode` value, `build_stylesheet(mode)` SHALL produce a string that embeds every value from `SPACING` at least once — i.e., no spacing constant is defined but never used.

**Validates: Requirements 1.2, 1.3**

### Property 3: No hex literals outside theme module

*For any* Python source file under `app/ui/` that is not `theme.py`, the file SHALL contain zero occurrences of a bare hex colour literal (pattern `#[0-9a-fA-F]{3,6}`) outside of string arguments to `setObjectName` or comments.

**Validates: Requirement 1.5, 2.3**

### Property 4: Stylesheet round-trip stability

*For any* `ThemeMode` value, calling `build_stylesheet(mode)` twice in succession SHALL return identical strings — the function is pure and deterministic.

**Validates: Requirements 1.3, 10.2**

### Property 5: Theme mode serialisation round-trip

*For any* `AppSettings` instance with a valid `theme_mode` value (`"dark"` or `"light"`), serialising to JSON and deserialising SHALL produce an `AppSettings` with the same `theme_mode`.

**Validates: Requirement 10.3**

---

## Error Handling

### `build_stylesheet` — invalid mode

`build_stylesheet` accepts a `ThemeMode` enum value. If an unexpected value is passed (e.g. from a future extension), the function falls back to `ThemeMode.DARK` and logs a warning via `_log.warning`. It never raises — a broken stylesheet call must not crash the application.

### `AppSettings.theme_mode` — unknown value from disk

If `settings.json` contains an unrecognised `theme_mode` string (e.g. `"solarized"`), `MainWindow.__init__` falls back to `ThemeMode.DARK` silently. The field is not validated by Pydantic beyond being a `str`, so no `ValidationError` is raised on load.

### Inline style removal — regression guard

Because inline styles are being removed, any widget that previously relied on an inline style for correct rendering will now depend on the global QSS. The risk is that a widget's object name is not set, leaving it unstyled. This is mitigated by:
1. The `build_stylesheet` tests (Properties 1–2) ensuring all semantic rules are present.
2. A manual smoke-test checklist in the Testing Strategy.

### `TerminalWidget.apply_preferences` — preserved exception

`apply_preferences` calls `setStyleSheet` with user-supplied hex colours. These are validated upstream by `QColorDialog` (which only returns valid `QColor` objects), so no additional error handling is needed here.

---

## Testing Strategy

### Unit Tests

Property-based testing is appropriate for this feature because `build_stylesheet` is a pure function with clear input/output behaviour, and the correctness properties (palette completeness, no dropped constants, determinism) are universal across all valid inputs.

**PBT library:** `hypothesis` (already present in the project via `.hypothesis/` directory).

**Property test configuration:** minimum 100 iterations per property test.

#### Property Test 1 — PALETTE completeness
```
# Feature: app-theme-redesign, Property 1: PALETTE completeness
@given(mode=st.sampled_from(ThemeMode))
@settings(max_examples=100)
def test_palette_completeness(mode):
    qss = build_stylesheet(mode)
    for key, value in PALETTE.items():
        assert value in qss or key in qss
```

#### Property Test 2 — SPACING completeness
```
# Feature: app-theme-redesign, Property 2: SPACING completeness
@given(mode=st.sampled_from(ThemeMode))
@settings(max_examples=100)
def test_spacing_completeness(mode):
    qss = build_stylesheet(mode)
    for value in SPACING.values():
        assert str(value) in qss
```

#### Property Test 3 — No hex literals in UI files
This is a static analysis property, best verified by a `pytest` test that walks `app/ui/` and asserts no hex literals appear outside `theme.py`. It runs once (not PBT) but validates the universal property across all files.

#### Property Test 4 — Stylesheet round-trip stability
```
# Feature: app-theme-redesign, Property 4: Stylesheet round-trip stability
@given(mode=st.sampled_from(ThemeMode))
@settings(max_examples=100)
def test_stylesheet_deterministic(mode):
    assert build_stylesheet(mode) == build_stylesheet(mode)
```

#### Property Test 5 — Theme mode serialisation round-trip
```
# Feature: app-theme-redesign, Property 5: Theme mode serialisation round-trip
@given(mode=st.sampled_from(["dark", "light"]))
@settings(max_examples=100)
def test_theme_mode_roundtrip(mode):
    settings = AppSettings(theme_mode=mode)
    json_str = settings.model_dump_json()
    restored = AppSettings.model_validate_json(json_str)
    assert restored.theme_mode == mode
```

### Example-Based Unit Tests

- `test_build_stylesheet_dark_returns_string` — `build_stylesheet(ThemeMode.DARK)` returns a non-empty string.
- `test_build_stylesheet_light_returns_string` — `build_stylesheet(ThemeMode.LIGHT)` returns a non-empty string.
- `test_build_stylesheet_dark_light_differ` — dark and light stylesheets are not identical.
- `test_palette_keys_present` — `PALETTE` contains all 14 required keys from Requirement 1.1.
- `test_spacing_keys_present` — `SPACING` contains all 5 required keys from Requirement 1.2.
- `test_font_keys_present` — `FONT` contains all 5 required keys from Requirement 4.1.
- `test_appsettings_theme_mode_default` — `AppSettings().theme_mode == "dark"`.
- `test_appsettings_theme_mode_light` — `AppSettings(theme_mode="light").theme_mode == "light"`.

### Smoke / Integration Tests (manual checklist)

Because this is a UI-only refactor, the following are verified manually after implementation:

1. Launch app in dark mode — all pages render without unstyled widgets.
2. Launch app in light mode — all pages render with appropriate light colours.
3. Switch theme in Settings, save — stylesheet updates without restart.
4. Resize window below minimum height — Params_Panel scrolls correctly.
5. Params_Panel does not exceed 360 px on a wide monitor.
6. Warning banners (optimize page, download page) display with yellow tint.
7. Success/error status labels display with correct colours.
8. Terminal widget retains user-configured colours after theme switch.
9. AI Chat dock renders correctly in both modes.
10. Settings dialog validation result label shows correct colour states.
