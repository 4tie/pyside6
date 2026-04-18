# Implementation Plan

---

## Bug 1 — Improve Page: Partial/Stale Analyze Results

- [-] 1. Write bug condition exploration test for Bug 1 (stale/partial analyze results)
  - **Property 1: Bug Condition** - Stale Layout Children After Consecutive Analyze Calls
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior — it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate stale `_empty_*` placeholder widgets remain in the layout after `deleteLater()` is used
  - **Scoped PBT Approach**: Scope the property to `n >= 1` consecutive analyze calls; for each call assert that the simulated layout has zero stale children after the clear operation
  - In `tests/ui/test_ui_rendering_bugs.py`, write a property-based test using `hypothesis` that:
    - Simulates a layout with one placeholder child widget
    - Calls the unfixed clear logic (`deleteLater()` pattern) and checks the child count
    - Asserts `stale_child_count == 0` after the clear — this FAILS on unfixed code because `deleteLater()` is asynchronous and the widget remains in the layout
  - Also write a test that calls `_fade_in_widget()` on a mock widget, fires the animation's `finished` signal, and asserts `widget.graphicsEffect() is None` — this FAILS on unfixed code because the effect is never removed
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (proves the bug exists — stale child count > 0 and/or effect not removed)
  - Document counterexamples found (e.g., `layout.count() == 2` after second analyze call instead of 1)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 2. Write preservation property tests for Bug 1 (BEFORE implementing fix)
  - **Property 2: Preservation** - Analyze Results Correctness Unchanged
  - **IMPORTANT**: Follow observation-first methodology — observe behavior on UNFIXED code for non-buggy inputs
  - Observe: on a first analyze call with no prior stale state and no tab switch, `_display_baseline_summary()` populates form rows correctly
  - Observe: `_build_status_message()` returns the correct `(message, color)` tuple for each trigger key
  - Observe: `compute_highlight()` returns `"green"` / `"red"` / `None` correctly for each metric direction
  - In `tests/ui/test_ui_rendering_bugs.py`, write property-based tests using `hypothesis` that:
    - For any `BacktestSummary`-like dict with valid metric values, `compute_highlight(metric, baseline, candidate)` returns the correct direction string (pure-logic, no Qt needed)
    - For any trigger key string, `_build_status_message(trigger, n_issues)` returns a non-empty message string and a non-empty color hex string
    - For any integer `n_issues >= 0`, `_build_status_message("analysis_complete_issues", n_issues)` includes the issue count in the message
  - Verify tests PASS on UNFIXED code (confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.9_

- [ ] 3. Fix Bug 1 — Improve Page stale/partial analyze results

  - [ ] 3.1 Replace `deleteLater()` with `setParent(None)` in `_display_baseline_summary()`
    - In `app/ui/pages/improve_page.py`, locate `_display_baseline_summary()`
    - Replace:
      ```python
      if self._empty_baseline is not None:
          self._empty_baseline.deleteLater()
          self._empty_baseline = None
      ```
      With:
      ```python
      if self._empty_baseline is not None:
          self._empty_baseline.setParent(None)
          self._empty_baseline = None
      ```
    - Add `self._cards_widget.setVisible(False)` at the very start of `_display_baseline_summary()`, before any layout clearing
    - The existing `self._cards_widget.setVisible(True)` call at the end of the method remains unchanged
    - _Bug_Condition: `isBugCondition_Bug1(X)` where `X.analyze_call_count >= 1` and `empty_panel_still_in_layout(X)` is true_
    - _Expected_Behavior: `layout_stale_child_count(result) == 0` and `cards_widget_initially_hidden(result) == True`_
    - _Preservation: `_on_analyze()` continues to populate baseline summary form rows with correct strategy metrics_
    - _Requirements: 2.1, 2.2, 2.4, 3.1_

  - [ ] 3.2 Replace `deleteLater()` with `setParent(None)` in `_display_issues_and_suggestions()`
    - In `app/ui/pages/improve_page.py`, locate `_display_issues_and_suggestions()`
    - Replace `self._empty_issues.deleteLater()` with `self._empty_issues.setParent(None)`
    - Replace `self._empty_suggestions.deleteLater()` with `self._empty_suggestions.setParent(None)`
    - Ensure both `_empty_issues` and `_empty_suggestions` are set to `None` immediately after `setParent(None)`
    - _Bug_Condition: `isBugCondition_Bug1(X)` where second analyze call encounters stale `_empty_issues` at layout index 1_
    - _Expected_Behavior: layout-clearing loop sees correct child count on every call_
    - _Preservation: issue badge count and suggestion row count remain correct after fix_
    - _Requirements: 2.2, 3.2, 3.3_

  - [ ] 3.3 Remove `QGraphicsOpacityEffect` after fade-in animation completes in `_fade_in_widget()`
    - In `app/ui/pages/improve_page.py`, locate `_fade_in_widget()`
    - After `anim.start()`, add:
      ```python
      anim.finished.connect(lambda: widget.setGraphicsEffect(None))
      ```
    - The `widget._fade_anim = anim` reference line remains unchanged
    - _Bug_Condition: `isBugCondition_Bug1(X)` where `X.tab_was_hidden_and_reshown == True` and `X.fade_effects_still_attached == True`_
    - _Expected_Behavior: `widget.graphicsEffect() is None` after animation `finished` signal fires_
    - _Preservation: `QPropertyAnimation` fade-in visual behavior is unchanged; only the cleanup after completion is added_
    - _Requirements: 2.3, 3.9_

  - [ ] 3.4 Verify bug condition exploration test (Property 1) now passes
    - **Property 1: Expected Behavior** - Stale Layout Children After Consecutive Analyze Calls
    - **IMPORTANT**: Re-run the SAME test from task 1 — do NOT write a new test
    - The test from task 1 encodes the expected behavior (zero stale children, effect removed after animation)
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms Bug 1 is fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ] 3.5 Verify preservation tests still pass
    - **Property 2: Preservation** - Analyze Results Correctness Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions in analyze results logic)
    - Confirm `compute_highlight()` and `_build_status_message()` behavior is unchanged

---

## Bug 2 — Pairs Selector Dialog: Heart and Lock Icons Not Rendering

- [ ] 4. Write bug condition exploration test for Bug 2 (icons not rendering on Windows)
  - **Property 1: Bug Condition** - Default Button Font Lacks Emoji Glyphs on Windows
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **GOAL**: Surface counterexamples showing that `_make_favorite_button()` and `_make_lock_button()` produce buttons whose font does not support the required Unicode characters on Windows
  - **Scoped PBT Approach**: Scope the property to the concrete failing case — a button created without an explicit font on a Windows-like platform
  - In `tests/ui/test_ui_rendering_bugs.py`, write a property-based test using `hypothesis` that:
    - Creates a `QPushButton` without setting an explicit font (simulating the unfixed code)
    - Asserts that `btn.font().family()` is one of `{"Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"}` — this FAILS on unfixed code because no emoji font is set
  - Also write a unit test that directly inspects the font family on a button created by the unfixed `_make_favorite_button()` and `_make_lock_button()` methods
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (proves the bug exists — default font family is not an emoji font)
  - Document counterexamples found (e.g., `btn.font().family() == "Segoe UI"` instead of `"Segoe UI Emoji"`)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.5, 1.6_

- [ ] 5. Write preservation property tests for Bug 2 (BEFORE implementing fix)
  - **Property 2: Preservation** - Favorite and Lock Toggle Behavior Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: `_on_favorite_clicked(pair)` toggles `pair` in `self.favorites`, updates button text to `"♥"` or `"♡"`, and calls `settings_state.toggle_favorite_pair(pair)`
  - Observe: `_on_lock_clicked(pair)` toggles `pair` in `self.locked_pairs`, updates button text to `"🔒"` or `"🔓"`, and checks the pair's checkbox when locked
  - In `tests/ui/test_ui_rendering_bugs.py`, write property-based tests using `hypothesis` that:
    - For any pair name string, toggling favorite twice returns the button text to its original state (`"♡"`)
    - For any pair name string, toggling lock sets the expected text (`"🔒"` when locked, `"🔓"` when unlocked)
    - These are pure-logic tests on the text values — no Qt widget instantiation required
  - Verify tests PASS on UNFIXED code
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.5, 3.6_

- [ ] 6. Fix Bug 2 — Pairs selector icon rendering

  - [ ] 6.1 Add `_emoji_font()` helper function to `pairs_selector_dialog.py`
    - In `app/ui/dialogs/pairs_selector_dialog.py`, add the following imports at the top of the file:
      ```python
      import os
      import sys
      from PySide6.QtGui import QFont
      ```
    - Add the `_emoji_font()` module-level helper function before the `PairsSelectorDialog` class:
      ```python
      def _emoji_font() -> QFont:
          """Return a QFont with an emoji-capable family for the current platform."""
          if os.name == "nt":
              family = "Segoe UI Emoji"
          elif sys.platform == "darwin":
              family = "Apple Color Emoji"
          else:
              family = "Noto Color Emoji"
          return QFont(family, 14)
      ```
    - _Bug_Condition: `isBugCondition_Bug2(X)` where `X.platform == "nt"` and `font_supports_codepoint(X.button_font, X.unicode_char) == False`_
    - _Expected_Behavior: `btn.font().family() in {"Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"}` and `btn.font().pointSize() == 14`_
    - _Preservation: `_on_favorite_clicked()` and `_on_lock_clicked()` toggle logic is completely unchanged_
    - _Requirements: 2.5, 2.6_

  - [ ] 6.2 Apply `_emoji_font()` in `_make_favorite_button()` and `_make_lock_button()`
    - In `_make_favorite_button()`, after `btn.setStyleSheet("border: none;")`, add:
      ```python
      btn.setFont(_emoji_font())
      ```
    - In `_make_lock_button()`, after `btn.setStyleSheet("border: none;")`, add:
      ```python
      btn.setFont(_emoji_font())
      ```
    - Do NOT modify `_on_favorite_clicked()` or `_on_lock_clicked()` — `setText()` does not reset the font set via `setFont()`
    - _Requirements: 2.5, 2.6_

  - [ ] 6.3 Verify bug condition exploration test (Property 1) now passes
    - **Property 1: Expected Behavior** - Emoji Font Applied to Icon Buttons
    - **IMPORTANT**: Re-run the SAME test from task 4 — do NOT write a new test
    - Run bug condition exploration test from step 4
    - **EXPECTED OUTCOME**: Test PASSES (confirms Bug 2 is fixed — buttons now have an emoji-capable font)
    - _Requirements: 2.5, 2.6_

  - [ ] 6.4 Verify preservation tests still pass
    - **Property 2: Preservation** - Favorite and Lock Toggle Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 5 — do NOT write new tests
    - Run preservation property tests from step 5
    - **EXPECTED OUTCOME**: Tests PASS (confirms toggle logic and text values are unchanged)

---

## Bug 3 — Timerange Preset Buttons: Text Getting Cut Off

- [ ] 7. Write bug condition exploration test for Bug 3 (preset button text clipping)
  - **Property 1: Bug Condition** - Preset Button Has `maximumWidth == 50`
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **GOAL**: Surface counterexamples showing that preset buttons are created with `setMaximumWidth(50)`, which clips labels like `"120d"` and `"360d"`
  - **Scoped PBT Approach**: For each label in `["7d", "14d", "30d", "90d", "120d", "360d"]`, assert that the button's `maximumWidth()` is NOT 50
  - In `tests/ui/test_ui_rendering_bugs.py`, write a property-based test using `hypothesis` that:
    - Draws a preset label from `sampled_from(["7d", "14d", "30d", "90d", "120d", "360d"])`
    - Creates a `QPushButton(label)` and calls `btn.setMaximumWidth(50)` (simulating unfixed code)
    - Asserts `btn.maximumWidth() != 50` — this FAILS on unfixed code
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (proves the bug exists — `maximumWidth() == 50`)
  - Document counterexamples found (e.g., `QPushButton("120d").maximumWidth() == 50`)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.7, 1.8_

- [ ] 8. Write preservation property tests for Bug 3 (BEFORE implementing fix)
  - **Property 2: Preservation** - Preset Button Click Handler Behavior Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: clicking a preset button calls `_on_timerange_preset(preset)` with the correct preset string, which calls `calculate_timerange_preset(preset)` and sets `self.timerange_input.setText(result)`
  - In `tests/ui/test_ui_rendering_bugs.py`, write property-based tests using `hypothesis` that:
    - For any preset string from `["7d", "14d", "30d", "90d", "120d", "360d"]`, the lambda `lambda checked, p=preset: self._on_timerange_preset(p)` captures the correct `p` value (closure correctness)
    - This is a pure-logic test verifying the lambda captures the loop variable correctly — no Qt needed
  - Verify tests PASS on UNFIXED code
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.7, 3.8_

- [ ] 9. Fix Bug 3 — Timerange preset button text clipping

  - [ ] 9.1 Fix preset button width in `backtest_page.py`
    - In `app/ui/pages/backtest_page.py`, locate the preset button creation loop in `init_ui()`:
      ```python
      for preset in ["7d", "14d", "30d", "90d", "120d", "360d"]:
          btn = QPushButton(preset)
          btn.setMaximumWidth(50)
          btn.clicked.connect(lambda checked, p=preset: self._on_timerange_preset(p))
          timerange_presets_layout.addWidget(btn)
      ```
    - Replace `btn.setMaximumWidth(50)` with `btn.setMinimumWidth(48)`
    - Do NOT change the `clicked.connect(...)` line or any other part of the loop
    - _Bug_Condition: `isBugCondition_Bug3(X)` where `X.maximum_width == 50` and `rendered_text_width(X.label, X.font) > 50`_
    - _Expected_Behavior: `btn.maximumWidth() != 50` and `btn.minimumWidth() == 48`_
    - _Preservation: click handler still calls `_on_timerange_preset(preset)` with the correct preset string_
    - _Requirements: 2.7, 2.8, 3.7_

  - [ ] 9.2 Fix preset button width in `download_data_page.py`
    - In `app/ui/pages/download_data_page.py`, locate the preset button creation loop in `init_ui()`:
      ```python
      for preset in ["7d", "14d", "30d", "90d", "120d", "360d"]:
          btn = QPushButton(preset)
          btn.setMaximumWidth(50)
          btn.clicked.connect(lambda checked, p=preset: self._on_timerange_preset(p))
          presets_layout.addWidget(btn)
      ```
    - Replace `btn.setMaximumWidth(50)` with `btn.setMinimumWidth(48)`
    - Do NOT change the `clicked.connect(...)` line or any other part of the loop
    - _Bug_Condition: same as 9.1 — `isBugCondition_Bug3(X)` where `X.maximum_width == 50`_
    - _Expected_Behavior: `btn.maximumWidth() != 50` and `btn.minimumWidth() == 48`_
    - _Preservation: click handler still calls `_on_timerange_preset(preset)` and saves preference_
    - _Requirements: 2.7, 2.8, 3.8_

  - [ ] 9.3 Verify bug condition exploration test (Property 1) now passes
    - **Property 1: Expected Behavior** - Preset Button Has No `maximumWidth == 50`
    - **IMPORTANT**: Re-run the SAME test from task 7 — do NOT write a new test
    - Run bug condition exploration test from step 7
    - **EXPECTED OUTCOME**: Test PASSES (confirms Bug 3 is fixed — `maximumWidth() != 50`, `minimumWidth() == 48`)
    - _Requirements: 2.7, 2.8_

  - [ ] 9.4 Verify preservation tests still pass
    - **Property 2: Preservation** - Preset Button Click Handler Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 8 — do NOT write new tests
    - Run preservation property tests from step 8
    - **EXPECTED OUTCOME**: Tests PASS (confirms click handler closures are correct and unchanged)

---

## Bug 4 — General Label Text Clipping (Word Wrap)

- [ ] 10. Write bug condition exploration test for Bug 4 (word wrap disabled on subtitle labels)
  - **Property 1: Bug Condition** - Subtitle Labels Have `wordWrap() == False`
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **GOAL**: Surface counterexamples showing that subtitle labels in `ImprovePage` are created with `setWordWrap(False)`, causing text clipping at narrow widths
  - **Scoped PBT Approach**: For each of the four subtitle labels (`_issues_subtitle`, `_suggestions_subtitle`, `_candidate_subtitle`, `_comparison_subtitle`), assert `lbl.wordWrap() == True`
  - In `tests/ui/test_ui_rendering_bugs.py`, write a property-based test using `hypothesis` that:
    - Draws a subtitle text string using `hypothesis.strategies.text(min_size=1)`
    - Creates a `QLabel(text)` and calls `lbl.setWordWrap(False)` (simulating unfixed code)
    - Asserts `lbl.wordWrap() == True` — this FAILS on unfixed code
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (proves the bug exists — `wordWrap() == False`)
  - Document counterexamples found (e.g., any `QLabel` with `setWordWrap(False)` fails the assertion)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.9, 1.10_

- [ ] 11. Write preservation property tests for Bug 4 (BEFORE implementing fix)
  - **Property 2: Preservation** - Label Text Content Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: subtitle labels display the same text content regardless of word wrap setting — only the rendering behavior (wrap vs. clip) changes
  - In `tests/ui/test_ui_rendering_bugs.py`, write property-based tests using `hypothesis` that:
    - For any text string, a `QLabel` created with `setWordWrap(True)` has the same `text()` as one created with `setWordWrap(False)` — only `wordWrap()` differs
    - This confirms the fix changes only the wrap behavior, not the text content
  - Verify tests PASS on UNFIXED code
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 2.9, 2.10_

- [ ] 12. Fix Bug 4 — General label text clipping

  - [ ] 12.1 Enable word wrap on all four subtitle labels in `ImprovePage._init_ui()`
    - In `app/ui/pages/improve_page.py`, locate `_init_ui()` and find all four subtitle label definitions
    - For each of `_issues_subtitle`, `_suggestions_subtitle`, `_candidate_subtitle`, `_comparison_subtitle`:
      - Change `setWordWrap(False)` to `setWordWrap(True)`
    - Do NOT change the label text, style, or any other property
    - _Bug_Condition: `isBugCondition_Bug4(X)` where `X.word_wrap == False` and `X.text_pixel_width > X.available_container_width`_
    - _Expected_Behavior: `lbl.wordWrap() == True` for all four subtitle labels_
    - _Preservation: label text content is identical; only rendering behavior changes from clip to wrap_
    - _Requirements: 2.9, 3.1, 3.2, 3.3_

  - [ ] 12.2 Verify bug condition exploration test (Property 1) now passes
    - **Property 1: Expected Behavior** - Subtitle Labels Have Word Wrap Enabled
    - **IMPORTANT**: Re-run the SAME test from task 10 — do NOT write a new test
    - Run bug condition exploration test from step 10
    - **EXPECTED OUTCOME**: Test PASSES (confirms Bug 4 is fixed — `wordWrap() == True`)
    - _Requirements: 2.9, 2.10_

  - [ ] 12.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Label Text Content Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 11 — do NOT write new tests
    - Run preservation property tests from step 11
    - **EXPECTED OUTCOME**: Tests PASS (confirms label text content is unchanged)

---

## Checkpoint

- [ ] 13. Checkpoint — Ensure all tests pass
  - Run the full test suite: `pytest tests/ui/test_ui_rendering_bugs.py --tb=short`
  - All 8 property-based tests (Properties 1 and 2 for each of the 4 bugs) must pass
  - Run `ruff check app/ui/pages/improve_page.py app/ui/dialogs/pairs_selector_dialog.py app/ui/pages/backtest_page.py app/ui/pages/download_data_page.py` and fix any lint errors
  - Confirm no regressions in the broader test suite: `pytest --tb=short`
  - Ask the user if any questions arise
