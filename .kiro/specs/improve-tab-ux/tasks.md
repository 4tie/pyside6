# Implementation Plan: Improve Tab UX

## Overview

All changes are confined to `app/ui/pages/improve_page.py`. The plan adds three new module-level widget classes (`StepIndicator`, `ContextBanner`, `EmptyStatePanel`), two new pure helper functions (`_build_banner_message`, `_build_status_message`), modifies `ImprovePage` to track workflow step state, updates all button/label/group-box text, adds tooltips and subtitle labels, wires empty-state panels, and guards controls when `user_data_path` is unconfigured. Property-based tests use `hypothesis` and live in `tests/ui/pages/test_improve_page_ux.py`.

## Tasks

- [x] 1. Add pure helper functions `_build_banner_message` and `_build_status_message`
  - Add `_build_banner_message(step: int) -> str` at module level (below `_fade_in_widget`), returning the message string for each step 1–5 from `BANNER_MESSAGES`
  - Add `_build_status_message(trigger: str, n_issues: int = 0) -> tuple[str, str]` at module level, returning `(message, color)` for each trigger key defined in the Status Message Mapping table in the design
  - Both functions must be pure (no side effects, no widget access) so they are testable without instantiating `ImprovePage`
  - _Requirements: 2.2, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9_

  - [x] 1.1 Write property test for `_build_banner_message` — Property 2
    - **Property 2: Banner message matches active step**
    - For any step in `st.integers(min_value=1, max_value=5)`, assert `_build_banner_message(step)` equals `BANNER_MESSAGES[step]`
    - **Validates: Requirements 2.2, 2.3**

  - [x] 1.2 Write property test for `_build_status_message` — Property 4
    - **Property 4: Status message includes issue count**
    - For any `n_issues` in `st.integers(min_value=1, max_value=10000)`, assert `str(n_issues)` appears in `_build_status_message("analysis_complete_issues", n_issues)[0]`
    - **Validates: Requirements 7.2**

- [x] 2. Implement `StepIndicator` widget class
  - Add `StepIndicator(QWidget)` as a new module-level class in `improve_page.py`, following the pattern of `AnimatedMetricCard` and `IssueBadge`
  - `STEPS` class attribute: `[(1, "Select"), (2, "Analyze"), (3, "Apply"), (4, "Backtest"), (5, "Decide")]`
  - `__init__`: build a horizontal layout with five `QLabel` step nodes connected by `QFrame` line separators; store node labels in `self._node_labels`; call `set_active_step(1)`
  - `set_active_step(step: int) -> None`: iterate nodes — step < active → dimmed + "✓ " prefix; step == active → `_C_GREEN` + bold; step > active → dimmed, no prefix; update connector line colors (accent for completed segments, `_C_BORDER` for pending)
  - Fixed height ~48px; stretches horizontally
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9_

  - [x] 2.1 Write unit tests for `StepIndicator.set_active_step`
    - For each step value 1–5, assert the correct node labels carry the expected prefix ("✓ " or none) and the active node has bold styling
    - Test that calling `set_active_step(1)` after `set_active_step(5)` resets all nodes to pending except node 1
    - _Requirements: 1.3, 1.4, 1.8_

  - [x] 2.2 Write property test for `StepIndicator` — Property 1
    - **Property 1: Step indicator resets after accept or reject**
    - For any `initial_step` in `st.integers(min_value=1, max_value=5)`, call `set_active_step(initial_step)` then `set_active_step(1)`; assert active step is 1 and all other nodes are in pending state
    - **Validates: Requirements 1.8**

- [x] 3. Implement `ContextBanner` widget class
  - Add `ContextBanner(QWidget)` as a new module-level class in `improve_page.py`
  - `__init__`: build a styled `QHBoxLayout` with a `QLabel` for the message (`self._msg_lbl`, `setTextFormat(Qt.RichText)`) and a dismiss `QPushButton("✕")` right-aligned; apply left-border accent styling (`_C_GREEN`, 3px), background `_C_ELEVATED`, text `_C_TEXT` at 12px; set `self._dismissed = False`
  - `set_step(step: int) -> None`: if `self._dismissed`, return immediately; set `self._msg_lbl.setText(_build_banner_message(step))`; ensure widget is visible
  - Dismiss button `clicked` handler: set `self._dismissed = True`; call `self.hide()`
  - `is_dismissed(self) -> bool`: return `self._dismissed`
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 3.1 Write unit tests for `ContextBanner`
    - Assert `set_step(n)` sets the label text to `_build_banner_message(n)` for each n in 1–5
    - Assert clicking the dismiss button hides the widget and sets `is_dismissed()` to `True`
    - Assert `set_step` after dismiss does not change the label text or make the widget visible
    - _Requirements: 2.2, 2.3, 2.4, 2.5_

  - [x] 3.2 Write property test for `ContextBanner` — Property 3
    - **Property 3: Dismissed banner stays hidden across all step changes**
    - For any sequence of steps in `st.lists(st.integers(min_value=1, max_value=5), min_size=1, max_size=20)`, dismiss the banner then call `set_step` for each step in the sequence; assert `banner.isVisible()` is `False` after every call
    - **Validates: Requirements 2.5**

- [x] 4. Implement `EmptyStatePanel` widget class
  - Add `EmptyStatePanel(QWidget)` as a new module-level class in `improve_page.py`
  - `__init__(self, icon: str, text: str, hint: str, parent=None)`: build a vertically centered `QVBoxLayout` — icon `QLabel` at 28px font size, main text `QLabel` at 13px in `_C_TEXT_DIM`, hint `QLabel` at 11px italic in `_C_TEXT_DIM`; all center-aligned; minimum height 80px
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 4.1 Write unit tests for `EmptyStatePanel`
    - Assert the icon, text, and hint labels contain the strings passed to `__init__`
    - Assert minimum height is ≥ 80px
    - _Requirements: 3.6_

- [x] 5. Add `_workflow_step`, `_banner_dismissed`, `_step_indicator`, `_context_banner` to `ImprovePage` and implement `_set_workflow_step`
  - In `ImprovePage.__init__`, add instance variables: `self._workflow_step: int = 1` and `self._banner_dismissed: bool = False` (before `_init_ui`)
  - Add `_set_workflow_step(self, step: int) -> None`: set `self._workflow_step = step`; call `self._step_indicator.set_active_step(step)`; call `self._context_banner.set_step(step)`
  - _Requirements: 1.4, 1.5, 1.6, 1.7, 1.8, 2.3_

- [x] 6. Insert `StepIndicator` and `ContextBanner` into `_init_ui` layout
  - In `_init_ui`, before the top controls row, instantiate `self._step_indicator = StepIndicator()` and `self._context_banner = ContextBanner()`; add both to `main_layout` as the first two items
  - Call `self._step_indicator.set_active_step(1)` and `self._context_banner.set_step(1)` after construction
  - _Requirements: 1.1, 2.1_

- [x] 7. Rename buttons, group box titles, and update tooltips in `_init_ui`
  - Rename buttons per the Button/Label Text Mapping in the design:
    - `"⚡ Analyze"` → `"⚡ Analyze Run"`
    - `"Load Latest"` → `"↓ Load Latest Run"`
    - `"▶  Run Backtest on Candidate"` → `"▶ Run Candidate Backtest"` (also update in `_update_candidate_preview`)
    - `"↺  Reset Candidate"` → `"↺ Reset to Baseline"` (also update in `_update_candidate_preview`)
    - `"Accept"` → `"✅ Accept & Save"`
    - `"Reject"` → `"✕ Reject & Discard"`
    - `"Rollback"` → `"↩ Rollback to Previous"`
  - Rename group box titles: `"Candidate Preview"` → `"Candidate Changes"`; `"Comparison"` → `"Results Comparison"`
  - Add `setToolTip` calls per Requirements 5.1–5.9 to: `strategy_combo`, `run_combo`, `analyze_btn`, `load_latest_btn`, `run_backtest_btn`, `accept_btn`, `reject_btn`, `rollback_btn`, `reset_candidate_btn`
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.10, 4.11, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_

  - [x] 7.1 Write unit tests for button text and tooltip values
    - Instantiate `ImprovePage` with a mock `SettingsState`; assert each button's `.text()` matches the new label; assert each widget's `.toolTip()` matches the spec text
    - _Requirements: 4.1–4.7, 5.1–5.9_

- [x] 8. Add subtitle labels to group boxes in `_init_ui`
  - For each of the four group boxes that require subtitles, insert a `QLabel` as the first widget in the group's layout immediately after construction:
    - "Detected Issues" group: `"Issues found in the baseline run that may be limiting strategy performance."`
    - "Suggested Actions" group: `"Rule-based parameter changes that address the detected issues. Apply one or more, then run the candidate backtest."`
    - "Candidate Changes" group: `"Parameters that will be changed from the baseline when the candidate backtest runs."`
    - "Results Comparison" group: `"Side-by-side metrics for the baseline and candidate runs. Green = improvement, red = regression."`
  - Style each subtitle label: `_C_TEXT_DIM`, 11px, single line (no word wrap), 10px left padding
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 8.1 Write unit tests for subtitle label text
    - Assert each group box layout's first widget is a `QLabel` whose text matches the spec subtitle string
    - _Requirements: 6.1–6.5_

- [x] 9. Add `EmptyStatePanel` instances to group boxes and wire fade-in replacement
  - In `_init_ui`, after creating each group box layout, add an `EmptyStatePanel` as the initial content for the five group boxes that start empty:
    - "Baseline Summary": icon `"📊"`, text `"No run loaded yet"`, hint `"Select a strategy and run above, then click Analyze."`
    - "Detected Issues": icon `"🔍"`, text `"Issues will appear here after analysis"`, hint `"Click Analyze to scan your backtest results."`
    - "Suggested Actions": icon `"💡"`, text `"Suggestions will appear here after analysis"`, hint `"Each suggestion targets a specific performance issue."`
    - "Candidate Changes": icon `"⚙️"`, text `"No changes applied yet"`, hint `"Click Apply on a suggestion above to start building your candidate."`
    - "Results Comparison": icon `"⚖️"`, text `"Comparison will appear after the candidate backtest"`, hint `"Apply suggestions and run the candidate backtest to see results here."`
  - Store references: `self._empty_baseline`, `self._empty_issues`, `self._empty_suggestions`, `self._empty_candidate`, `self._empty_comparison`
  - Make all five group boxes visible by default (remove `setVisible(False)` calls); the `EmptyStatePanel` provides the placeholder content
  - In `_display_baseline_summary`, `_display_issues_and_suggestions`, `_update_candidate_preview`, and `_update_comparison_view`: remove the `EmptyStatePanel` (call `deleteLater`) before adding real content; use `_fade_in_widget` on the first real content widget
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.7_

- [x] 10. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Wire `_set_workflow_step` calls into existing event handlers
  - In `_on_analyze` success branch: call `self._set_workflow_step(3)` after `_display_issues_and_suggestions`
  - In `_on_apply_suggestion`: call `self._set_workflow_step(4)` on the first non-advisory apply (guard with `if self._workflow_step < 4`)
  - In `_on_candidate_finished` success branch: call `self._set_workflow_step(5)` after `_update_comparison_view`
  - In `_on_accept` after state update: call `self._set_workflow_step(1)`
  - In `_on_reject`: call `self._set_workflow_step(1)`
  - _Requirements: 1.5, 1.6, 1.7, 1.8_

- [x] 12. Update status messages to use `_build_status_message` in all event handlers
  - Replace all inline `status_label.setText` / `setStyleSheet` calls in `_on_analyze`, `_on_run_candidate`, `_on_candidate_finished`, `_on_accept`, `_on_reject`, `_on_rollback` with calls to `_build_status_message(trigger, n_issues)` and unpack `(msg, color)` to set the label
  - Update `_on_analyze` loading message to `"⏳ Loading run — please wait…"` in `_C_GREEN`
  - Update `_on_analyze` success message to `"✅ Analysis complete — {N} issue(s) found. Review suggestions below and click Apply."` (N > 0) or `"✅ Analysis complete — no issues detected. Your strategy looks healthy!"` (N == 0)
  - Update `_on_run_candidate` start message to `"⏳ Running candidate backtest — see terminal output below…"` in `_C_GREEN`
  - Update `_on_candidate_finished` success message to `"✅ Candidate backtest complete — review the comparison below and click Accept or Reject."` in `_C_GREEN_LIGHT`
  - Update `_on_candidate_finished` failure message to `"❌ Candidate backtest failed — check the terminal output above for errors."` in `_C_RED_LIGHT`
  - Update `_on_accept` message to `"✅ Accepted — strategy parameters saved. You can run another iteration or switch to a different run."` in `_C_GREEN_LIGHT`
  - Update `_on_reject` message to `"↩ Rejected — candidate discarded. Apply different suggestions or select a new run."` in `_C_YELLOW`
  - Update `_on_rollback` message to `"↩ Rolled back — parameters restored to the previous accepted state."` in `_C_YELLOW`
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10_

- [x] 13. Update "Detected Issues" and "Suggested Actions" group box titles with count suffix
  - In `_display_issues_and_suggestions`, after computing `issues` and `suggestions`, call `self.issues_group.setTitle(f"Detected Issues ({len(issues)})")` when `len(issues) > 0`, else `"Detected Issues"`
  - Similarly set `self.suggestions_group.setTitle(f"Suggested Actions ({len(suggestions)})")` when `len(suggestions) > 0`, else `"Suggested Actions"`
  - _Requirements: 4.8, 4.9_

- [x] 14. Implement no-configuration guard
  - Add a `_no_config_banner: QLabel` instance variable; in `_init_ui`, create it as a full-width `QLabel` with the warning text `"⚠️ User data path is not configured. Go to Settings and set your Freqtrade user_data directory to use this tab."`, styled with left border `_C_ORANGE` (3px), background `_C_ELEVATED`, text `_C_TEXT` at 12px; insert it as the first item in `main_layout`; hide it initially
  - Extract a helper `_check_config_guard(self) -> None`: read `user_data_path` from `SettingsState`; if empty/unset, show `_no_config_banner` and disable `strategy_combo`, `run_combo`, `load_latest_btn`, `analyze_btn`; otherwise hide banner and re-enable those controls
  - Call `_check_config_guard()` at the end of `_refresh_strategies` and connect `settings_state.settings_changed` to `_check_config_guard`
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 14.1 Write property test for no-config guard — Property 5
    - **Property 5: Controls disabled when user_data_path is unconfigured**
    - For any `user_data_path` value in `st.one_of(st.just(""), st.just(None), st.text(max_size=0))`, mock `SettingsState` to return that value; call `_check_config_guard()`; assert `strategy_combo`, `run_combo`, `load_latest_btn`, and `analyze_btn` are all disabled
    - **Validates: Requirements 8.3**

  - [x] 14.2 Write unit tests for no-config guard
    - Assert warning banner is visible when `user_data_path` is empty and hidden when it is a non-empty path
    - Assert controls re-enable when `settings_changed` fires with a valid path
    - _Requirements: 8.1, 8.4, 8.5_

- [x] 15. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All changes are confined to `app/ui/pages/improve_page.py` and `tests/ui/pages/test_improve_page_ux.py`
- Property tests require `hypothesis`; run with `pytest tests/ui/pages/test_improve_page_ux.py --tb=short`
- Each property test must be tagged with `# Feature: improve-tab-ux, Property {N}: {property_text}`
- `_build_banner_message` and `_build_status_message` are pure functions — test them without any Qt widget setup
- For widget tests that need a `QApplication`, use a session-scoped `pytest` fixture
