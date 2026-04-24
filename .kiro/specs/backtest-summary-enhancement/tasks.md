# Implementation Plan: Backtest Summary Enhancement

## Overview

All changes are confined to `app/ui/pages/results_page.py`. The implementation proceeds in layers: pure color functions first (testable in isolation), then the helper widgets, then the section builder, then the KPI row, and finally the orchestrating `_build_summary` replacement. Tests are written close to the code they validate so failures surface early.

## Tasks

- [x] 1. Add module-level color-coding pure functions
  - Add six functions at module level in `results_page.py`, outside the `ResultsPage` class, immediately after the existing module-level helpers (`_run_dir_path`, `_trade_profit`, etc.)
  - Implement `_profit_color(value: float) -> str` — returns `theme.GREEN` when `value > 0`, `theme.RED` when `value < 0`, `theme.TEXT_PRIMARY` when `value == 0`
  - Implement `_win_rate_color(value: float) -> str` — returns `theme.GREEN` when `value >= 50.0`, `theme.RED` otherwise
  - Implement `_sharpe_color(value: float) -> str` — returns `theme.GREEN` when `value >= 1.0`, `theme.YELLOW` when `0.0 < value < 1.0`, `theme.RED` when `value <= 0.0`
  - Implement `_profit_factor_color(value: float) -> str` — returns `theme.GREEN` when `value >= 1.0`, `theme.RED` otherwise
  - Implement `_profit_accent_color(value: float) -> str` — returns `theme.GREEN` when `value >= 0`, `theme.RED` when `value < 0`
  - Implement `_drawdown_accent_color(value: float) -> str` — returns `theme.RED` when `value > 20.0`, `theme.YELLOW` otherwise
  - Each function must have a one-line docstring
  - No Qt imports required — these are pure Python functions
  - _Requirements: 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_

  - [x] 1.1 Write property tests for all six color functions (`tests/ui/test_summary_color_functions.py`)
    - Create `tests/ui/test_summary_color_functions.py`; add `tests/ui/__init__.py` if it does not exist
    - Import the six functions directly from `app.ui.pages.results_page`
    - Use `@settings(max_examples=200)` on every `@given` test
    - **Property 1: Profit color partitions the real line correctly** — three `@given` tests covering `v > 0` → GREEN, `v < 0` → RED, `v == 0` → TEXT_PRIMARY; **Validates: Requirements 3.1, 3.2, 3.3**
    - **Property 2: Win rate color threshold is monotone at 50.0** — two `@given` tests covering `v >= 50.0` → GREEN, `v in [0.0, 50.0)` → RED; **Validates: Requirements 3.4, 3.5**
    - **Property 3: Sharpe color partitions into three zones** — three `@given` tests covering `v >= 1.0` → GREEN, `v in (0.0, 1.0)` → YELLOW, `v <= 0.0` → RED; **Validates: Requirements 3.6, 3.7, 3.8**
    - **Property 4: Profit factor color threshold is monotone at 1.0** — two `@given` tests covering `v >= 1.0` → GREEN, `v in [0.0, 1.0)` → RED; **Validates: Requirements 3.9, 3.10**
    - **Property 5: KPI accent colors are consistent with profit color rules** — two `@given` tests covering `v >= 0` → GREEN, `v < 0` → RED; **Validates: Requirements 2.3, 2.4**
    - **Property 6: Drawdown accent color threshold is monotone at 20.0** — two `@given` tests covering `v > 20.0` → RED, `v in [0.0, 20.0]` → YELLOW; **Validates: Requirements 2.5, 2.6**
    - Use `st.floats(allow_nan=False, allow_infinity=False)` with appropriate `min_value`/`max_value` bounds per zone
    - Tag each test with `# Feature: backtest-summary-enhancement, Property {N}: {property_text}`

- [x] 2. Checkpoint — run the property tests
  - Ensure all tests in `tests/ui/test_summary_color_functions.py` pass. Ask the user if questions arise.

- [x] 3. Implement `_balance_delta_widget` private method
  - Add `_balance_delta_widget(self, starting: float, final: float) -> QLabel | None` to `ResultsPage`
  - When `final > starting`: return a `QLabel` with text `f"+{final - starting:.2f} USDT"` and stylesheet color `theme.GREEN`
  - When `final < starting`: return a `QLabel` with text `f"−{final - starting:.2f} USDT"` (Unicode minus U+2212) and stylesheet color `theme.RED`
  - When `final == starting`: return `None`
  - Font size 12px, font weight 600 on the returned label
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 3.1 Write property tests for `_balance_delta_widget` (append to `tests/ui/test_summary_color_functions.py`)
    - Requires a `QApplication` fixture (session-scoped); add one if not already present in the file or a shared conftest
    - **Property 7: Balance delta sign and color are consistent** — `@given` tests for `final > starting` (text starts with `"+"`, color is GREEN) and `final < starting` (text starts with `"−"`, color is RED); **Validates: Requirements 6.1, 6.2**
    - **Property 8: Balance delta formatting precision** — `@given` test for `final != starting` asserting the label text contains a value formatted to exactly two decimal places followed by `" USDT"`; **Validates: Requirement 6.4**
    - Tag each test with `# Feature: backtest-summary-enhancement, Property {N}: {property_text}`

- [x] 4. Implement `_build_pairs_widget` private method
  - Add `_build_pairs_widget(self, pairs: list[str]) -> QWidget` to `ResultsPage`
  - Empty list: return a plain `QLabel("—")` with color `theme.TEXT_PRIMARY`
  - Non-empty list: return a `QWidget` that holds badge `QLabel` widgets and overrides `resizeEvent` to reposition them using `setGeometry` (flow-wrap pattern — no third-party layout managers)
  - Each badge `QLabel` styled with: `background: {theme.ACCENT_DIM}; color: {theme.ACCENT}; border-radius: 10px; padding: 2px 8px; font-size: 11px; font-weight: 600;`
  - The `resizeEvent` override must call `super().resizeEvent(event)` and reposition all child badge labels with a horizontal gap of 6px and vertical gap of 4px
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 5. Implement `_summary_section` private method
  - Add `_summary_section(self, title: str, fields: list[tuple[str, str, str]]) -> QFrame` to `ResultsPage`
  - Returns a `QFrame` with a `QVBoxLayout` containing:
    - A section header `QLabel` (text: `title.upper()`, color: `theme.TEXT_SECONDARY`, font-size: 11px, font-weight: 600)
    - A card body `QFrame` (background: `theme.BG_SURFACE`, border: `1px solid {theme.BG_BORDER}`, border-radius: 8px)
  - Inside the card body: a `QGridLayout` with fields arranged in two columns (column 0 = label, column 1 = value, then column 2 = label, column 3 = value for the second column)
  - Each field tuple `(label_text, value_text, color_hex)`: label `QLabel` styled at 11px `theme.TEXT_SECONDARY`; value `QLabel` styled at 13px font-weight 500 with the provided `color_hex`
  - Set `setColumnMinimumWidth(1, 200)` and `setColumnMinimumWidth(3, 200)` on the grid
  - Odd-count field lists: leave the last grid cell empty (do not stretch the final field)
  - Grid layout margins: 12px all sides, spacing 8px
  - _Requirements: 1.1, 1.2, 1.3, 4.1, 4.2, 4.3, 4.4_

- [x] 6. Implement `_build_kpi_row` private method
  - Add `_build_kpi_row(self, run: dict) -> QWidget` to `ResultsPage`
  - Returns a `QWidget` containing a `QHBoxLayout` of exactly six `StatCard` instances
  - Card definitions (label, field key, default, accent logic):
    1. `"Total Profit %"` — `profit_total_pct`, default `0.0`, accent: `_profit_accent_color(v)`
    2. `"Win Rate"` — `win_rate_pct`, default `0.0`, accent: `theme.ACCENT` (fixed)
    3. `"Total Trades"` — `trades_count`, default `0`, accent: `theme.PURPLE` (fixed)
    4. `"Max Drawdown %"` — `max_drawdown_pct`, default `0.0`, accent: `_drawdown_accent_color(v)`
    5. `"Sharpe Ratio"` — `sharpe`, default `None`, accent: `theme.ACCENT` (fixed)
    6. `"Profit Factor"` — `profit_factor`, default `0.0`, accent: `theme.GREEN` (fixed)
  - Missing / `None` values display `"—"` in the card
  - Format non-None values: profit `f"{v:+.2f}%"`, win rate `f"{v:.1f}%"`, trades `str(v)`, drawdown `f"{v:.2f}%"`, sharpe `f"{v:.3f}"`, profit factor `f"{v:.3f}"`
  - Each card: `setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)`, `setFixedHeight(100)`
  - HBoxLayout spacing: 10px, no margins
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

- [x] 7. Checkpoint — verify helpers compile and are importable
  - Ensure all five new methods and six module-level functions are importable without errors. Ask the user if questions arise.

- [x] 8. Replace `_build_summary` with the new orchestrating implementation
  - Replace the existing `_build_summary(self, run: dict) -> None` method entirely
  - Clear step (before try block): call `_clear_summary_layout()` — implement this as a private helper that removes all widgets from `_summary_layout` using `takeAt` + `deleteLater`; if a `_clear_summary_layout` helper already exists reuse it, otherwise add it
  - Wrap the build logic in `try/except Exception as exc` — on failure call `_log.warning("_build_summary failed: %s", exc)` and return (layout already cleared)
  - Inside the try block, in order:
    1. Build and add the KPI row widget via `_build_kpi_row(run)` — add to `_summary_layout`
    2. Build and add the Overview section via `_summary_section("Overview", fields)` where fields cover: Strategy, Timeframe, Timerange, Backtest Start, Backtest End, Pairs (use `_build_pairs_widget`), Run ID, Saved At — all with color `theme.TEXT_PRIMARY`
    3. Build and add the Performance section via `_summary_section("Performance", fields)` where fields cover: Starting Balance, Final Balance (with `_balance_delta_widget` result placed inline), Total Profit % (color from `_profit_color`), Total Profit Abs (color from `_profit_color`), Profit Factor (color from `_profit_factor_color`), Expectancy (color from `_profit_color`)
    4. Build and add the Trade Statistics section via `_summary_section("Trade Statistics", fields)` where fields cover: Total Trades, Wins, Losses, Win Rate (color from `_win_rate_color`) — all others `theme.TEXT_PRIMARY`
    5. Build and add the Risk Metrics section via `_summary_section("Risk Metrics", fields)` where fields cover: Max Drawdown % (`theme.RED`), Max Drawdown Abs (`theme.RED`), Sharpe Ratio (color from `_sharpe_color`), Sortino Ratio (color from `_sharpe_color`), Calmar Ratio (`theme.TEXT_PRIMARY`)
    6. Call `_summary_layout.addStretch()`
  - For the Final Balance field: when `_balance_delta_widget` returns a non-None label, embed both the balance value label and the delta label in a `QHBoxLayout` inside a container `QWidget`, and pass that widget as the value cell in the grid (adjust `_summary_section` to accept `QWidget` as value if needed, or handle inline)
  - All `run.get(key, default)` calls use safe defaults per the design data model table
  - _Requirements: 1.1, 1.4, 1.5, 1.6, 1.7, 2.1, 3.1–3.11, 4.1–4.4, 5.1–5.4, 6.1–6.4, 7.1, 7.2, 7.3, 7.4_

- [x] 9. Write unit and structural tests (`tests/ui/test_build_summary.py`)
  - Create `tests/ui/test_build_summary.py`
  - Add a session-scoped `QApplication` fixture (or import from a shared conftest if one exists)
  - Add a `results_page` fixture that instantiates `ResultsPage` with a minimal mock `SettingsState` (use `unittest.mock.MagicMock`)
  - [x] 9.1 Write unit tests for KPI row structure
    - Test that `_build_kpi_row({})` returns a widget containing exactly 6 `StatCard` children
    - Test that all 6 cards display `"—"` when the run dict is empty
    - _Requirements: 2.1, 2.2, 2.8_
  - [x] 9.2 Write unit tests for section structure
    - Test that `_build_summary` produces widgets for all four section headers: "OVERVIEW", "PERFORMANCE", "TRADE STATISTICS", "RISK METRICS"
    - Test field-to-section placement: `strategy` appears in Overview, `profit_total_pct` in Performance, `trades_count` in Trade Statistics, `sharpe` in Risk Metrics
    - _Requirements: 1.1, 1.4, 1.5, 1.6, 1.7_
  - [x] 9.3 Write unit tests for pairs display
    - Test that `_build_pairs_widget(["BTC/USDT", "ETH/USDT"])` returns a widget with 2 badge child labels
    - Test that `_build_pairs_widget([])` returns a `QLabel` with text `"—"`
    - _Requirements: 5.1, 5.3_
  - [x] 9.4 Write unit tests for balance delta
    - Test that equal balances produce `None` from `_balance_delta_widget`
    - _Requirements: 6.3_
  - [x] 9.5 Write property-style unit tests for idempotency and robustness (Properties 9–10)
    - **Property 9: `_build_summary` is idempotent on widget count** — call `_build_summary` twice with the same run dict and assert the top-level widget count in `_summary_layout` is identical after both calls; **Validates: Requirement 7.2**
    - **Property 10: `_build_summary` is robust to missing fields** — call `_build_summary({})` and assert it completes without raising an exception; **Validates: Requirement 7.3**
  - [x] 9.6 Write unit test for exception handling
    - Patch one of the helper methods to raise an exception, call `_build_summary`, and assert `_log.warning` was called and the layout is in a cleared state
    - _Requirements: 7.4_

- [x] 10. Final checkpoint — ensure all tests pass
  - Run `pytest tests/ui/ --tb=short` and confirm all tests pass. Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The clear-before-try pattern in task 8 is intentional: stale content is worse than an empty state on failure
- `_summary_section` receives plain `(label, value, color)` tuples; the Final Balance delta requires special handling — either extend the tuple to accept a `QWidget` as the value, or build that row manually outside `_summary_section`
- Property tests (Properties 1–8) live in `test_summary_color_functions.py`; structural/behavioral tests (Properties 9–10 + examples) live in `test_build_summary.py`
- Each property test must be tagged with `# Feature: backtest-summary-enhancement, Property {N}: {property_text}` for traceability
