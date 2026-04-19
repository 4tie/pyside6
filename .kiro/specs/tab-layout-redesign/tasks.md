# Implementation Plan: Tab Layout Redesign

## Overview

Purely structural UI changes to fix content overflow and clipping across all Tab_Pages. The work is: (1) create a reusable `CollapsibleTerminal` widget, (2) wire it into each page that has a terminal, (3) fix scroll areas on `StrategyConfigPage` and `SettingsPage`, (4) reorganise `OptimizePage` controls into sub-sections, and (5) tighten the minimum window size in `MainWindow`.

No service, model, or state classes are modified.

## Tasks

- [x] 1. Create `CollapsibleTerminal` widget
  - Create `app/ui/widgets/collapsible_terminal.py`
  - Implement `CollapsibleTerminal(QWidget)` with:
    - `LABEL_COLLAPSED = "Terminal Output ▶"` and `LABEL_EXPANDED = "Terminal Output ▼"` class constants
    - A `QPushButton` toggle header and an inner `TerminalWidget`
    - `self._expanded: bool = False` — hidden by default
    - `toggle()`, `show_terminal()`, `hide_terminal()` methods
    - `is_expanded() -> bool` property
    - `terminal` property returning the inner `TerminalWidget`
    - `apply_preferences(prefs: TerminalPreferences)` delegating to inner terminal
  - The inner `TerminalWidget` starts hidden (`setVisible(False)`)
  - Clicking the toggle button calls `toggle()`
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 1.1 Write unit tests for `CollapsibleTerminal`
    - Test initial state: `is_expanded() == False`, label == `"Terminal Output ▶"`
    - Test `show_terminal()`: `is_expanded() == True`, label == `"Terminal Output ▼"`
    - Test `hide_terminal()`: `is_expanded() == False`, label == `"Terminal Output ▶"`
    - Test `toggle()` on collapsed → expanded; on expanded → collapsed
    - Test `terminal` property returns the inner `TerminalWidget` instance
    - Test `apply_preferences()` does not raise
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 1.2 Write property test for toggle round-trip (Property 1)
    - **Property 1: Toggle round-trip restores original state**
    - `@given(st.booleans())` — set initial state; call `toggle()` twice; assert `is_expanded()` equals initial state and label is consistent
    - Tag: `# Feature: tab-layout-redesign, Property 1: Toggle round-trip restores original state`
    - **Validates: Requirements 2.2, 2.3**

  - [x] 1.3 Write property test for show_terminal idempotency (Property 2)
    - **Property 2: show_terminal always results in expanded state**
    - `@given(st.booleans())` — set initial state; call `show_terminal()`; assert `is_expanded() == True` and label == `"Terminal Output ▼"`
    - Tag: `# Feature: tab-layout-redesign, Property 2: show_terminal always results in expanded state`
    - **Validates: Requirements 2.4, 7.3**

  - [x] 1.4 Write property test for instance independence (Property 3)
    - **Property 3: Independent toggle state per page**
    - `@given(st.booleans(), st.booleans())` — create two instances with independent initial states; toggle the first; assert the second is unchanged
    - Tag: `# Feature: tab-layout-redesign, Property 3: Independent toggle state per page`
    - **Validates: Requirements 2.5**

  - [x] 1.5 Write property test for label/state consistency (Property 4)
    - **Property 4: Label always reflects expanded state**
    - `@given(st.lists(st.sampled_from(["toggle", "show", "hide"]), min_size=1, max_size=20))` — apply a random sequence of operations; after each step assert label matches `is_expanded()`
    - Tag: `# Feature: tab-layout-redesign, Property 4: Label always reflects expanded state`
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [x] 2. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Update `BacktestPage` to use `CollapsibleTerminal`
  - In `backtest_page.py` `init_ui()`: replace `self.terminal = TerminalWidget()` with `self.collapsible_terminal = CollapsibleTerminal()`
  - Add the `collapsible_terminal` widget to the output layout above the existing `QTabWidget`
  - Add a `terminal` property alias: `@property def terminal(self): return self.collapsible_terminal.terminal`
  - In `_run_backtest()`: call `self.collapsible_terminal.show_terminal()` before starting the process
  - In `_on_process_finished_internal()`: do NOT force-expand or collapse the terminal after a successful run (keep current toggle state); only switch to Results tab on success
  - _Requirements: 7.1, 7.2, 7.3_

- [x] 4. Update `OptimizePage` to use `CollapsibleTerminal` and add sub-sections
  - In `optimize_page.py` `_build_ui()`:
    - Replace `self.terminal = TerminalWidget()` with `self.collapsible_terminal = CollapsibleTerminal()`
    - Add `@property def terminal(self): return self.collapsible_terminal.terminal`
    - Wrap strategy combo, timeframe input, timerange presets, and custom timerange `QGroupBox` inside a new `QGroupBox("Run Configuration")`
    - Wrap pairs selection controls inside a new `QGroupBox("Pairs")`
    - Retain existing `QGroupBox("Hyperopt Options")` and `QGroupBox("💡 Hyperopt Advisor")` unchanged
    - Place `collapsible_terminal` in the output layout
  - In `_run_optimize()`: call `self.collapsible_terminal.show_terminal()` before starting the process
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 2.4_

- [x] 5. Update `DownloadDataPage` to use `CollapsibleTerminal`
  - In `download_data_page.py` `init_ui()`: replace `self.terminal = TerminalWidget()` with `self.collapsible_terminal = CollapsibleTerminal()`
  - Add `@property def terminal(self): return self.collapsible_terminal.terminal`
  - Place `collapsible_terminal` in the output layout (above or alongside the existing `QTabWidget` for Data Status)
  - In `_run_download()`: call `self.collapsible_terminal.show_terminal()` before starting the process
  - _Requirements: 6.2, 2.4_

- [x] 6. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Fix `StrategyConfigPage` scroll areas
  - In `strategy_config_page.py` `_build_ui()`:
    - Confirm `left_scroll` has `setWidgetResizable(True)` and `setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)`; add `left_scroll.setMinimumWidth(320)` if not present
    - Wrap the right ROI panel widget in a new `QScrollArea` with `setWidgetResizable(True)`, `setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)`, and `setMinimumWidth(320)`
    - Replace the direct `main.addWidget(right_widget, 1)` call with `main.addWidget(right_scroll, 1)`
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 8. Fix `SettingsPage` to be fully scrollable
  - In `settings_page.py` `init_ui()`:
    - Collect all existing group boxes and the button row into a content `QWidget` with the current `QVBoxLayout`
    - Wrap that content widget in a `QScrollArea` with `setWidgetResizable(True)` and `setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)`
    - Set the page's own layout to a single `QVBoxLayout` containing only the scroll area
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 9. Update `MainWindow` minimum size
  - In `main_window.py`: change `self.setMinimumSize(1200, 800)` to `self.setMinimumSize(800, 600)`
  - Verify `_all_terminals` still works — each page now exposes `.terminal` as a property alias, so no changes needed there
  - _Requirements: 8.1, 8.2_

- [x] 10. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes


- Property tests use [Hypothesis](https://hypothesis.readthedocs.io/) with `@given` — minimum 100 iterations per property
- All changes are confined to the UI layer; no services, models, or state classes are touched
- The `.terminal` property alias on each page keeps `MainWindow._all_terminals` working without modification
- `CollapsibleTerminal` toggle state is per-instance (in-memory only) — not persisted to `AppSettings`
