# UI Rendering Bugs — Bugfix Design

## Overview

This document formalises the fix design for four UI rendering bugs in the Freqtrade GUI PySide6 desktop application.
All four bugs are independent and affect different pages/dialogs, but share a common theme: Qt widget lifecycle
mismanagement and platform-specific font rendering gaps.

| Bug | File(s) | Root Cause Category |
|-----|---------|---------------------|
| Bug 1 — Improve Page stale/partial results | `app/ui/pages/improve_page.py` | Deferred `deleteLater()`, ghost `QGraphicsOpacityEffect` |
| Bug 2 — Pairs Selector icons not rendering | `app/ui/dialogs/pairs_selector_dialog.py` | Default font lacks emoji/symbol glyphs on Windows |
| Bug 3 — Timerange preset text clipping | `app/ui/pages/backtest_page.py`, `app/ui/pages/download_data_page.py` | `setMaximumWidth(50)` too narrow |
| Bug 4 — General label text clipping | `app/ui/pages/improve_page.py`, `app/ui/dialogs/pairs_selector_dialog.py` | `setWordWrap(False)` on subtitle labels |

The fix strategy for each bug is minimal and targeted: change only the lines that cause the defect,
preserve all surrounding behaviour, and add tests that would have caught the regression.

---

## Glossary

- **Bug_Condition (C)**: The condition that identifies inputs that trigger a specific bug.
- **Property (P)**: The desired correct behaviour when the bug condition holds.
- **Preservation**: Existing behaviour that must remain unchanged after the fix is applied.
- **`deleteLater()`**: Qt's asynchronous widget destruction — schedules deletion for the next event-loop iteration, leaving the widget in its parent layout until then.
- **`setParent(None)`**: Synchronous reparenting that immediately removes a widget from its parent layout and schedules it for deletion without a deferred-deletion race condition.
- **`QGraphicsOpacityEffect`**: A Qt graphics effect that modifies a widget's rendered opacity. If not removed after animation, it persists and can cause ghost rendering artefacts when the widget is hidden and reshown.
- **`_empty_baseline` / `_empty_issues` / `_empty_suggestions`**: `EmptyStatePanel` placeholder widgets in `ImprovePage` that are shown before data is loaded and must be removed synchronously before new content is inserted.
- **`_cards_widget`**: The `QWidget` row containing the five `AnimatedMetricCard` instances in `ImprovePage`. Its visibility and layout state must be reset at the start of each analyze call.
- **`_emoji_font()`**: A helper function (to be added) that returns a `QFont` with a platform-appropriate emoji family so that Unicode symbol characters render correctly on Windows.
- **`isBugCondition`**: Pseudocode function that returns `True` when a given input triggers the bug.
- **`F`**: The original (unfixed) function.
- **`F'`**: The fixed function.

---

## Bug Details

### Bug 1 — Improve Page: Partial/Stale Analyze Results on Tab Switch

#### Bug Condition

The bug manifests when `_on_analyze()` is called on `ImprovePage`. The `_display_baseline_summary()` and
`_display_issues_and_suggestions()` methods use `deleteLater()` to remove the `_empty_*` placeholder panels,
but `deleteLater()` is asynchronous — the widget remains in the layout until the Qt event loop processes the
deferred deletion. On a second analyze call the layout still holds the old placeholder as a child, producing
duplicate or stale content. Additionally, `_fade_in_widget()` attaches a `QGraphicsOpacityEffect` to each
widget; when the page is hidden (tab switch) and reshown, these effects leave ghost rendering artefacts.
Finally, `_cards_widget` is never hidden at the start of a new analyze call, so its layout state can be
inconsistent between calls.

**Formal Specification:**

```
FUNCTION isBugCondition_Bug1(X)
  INPUT: X of type ImprovePageAnalyzeCall
  OUTPUT: boolean

  RETURN (X.analyze_call_count >= 1
          AND (empty_panel_still_in_layout(X) OR cards_widget_not_reset(X)))
      OR (X.tab_was_hidden_and_reshown = true
          AND X.fade_effects_still_attached = true)
END FUNCTION
```

#### Examples

- **First analyze call**: `_empty_baseline` is removed via `deleteLater()`. Before the event loop runs, `_display_baseline_summary()` sets `self._empty_baseline = None` and starts adding form rows. The old placeholder widget is still a layout child — the form rows appear below it, producing a duplicate/stale layout.
- **Second analyze call**: `_empty_issues` was already set to `None` after the first call. The second call skips the removal guard (`if self._empty_issues is not None`) and proceeds to clear the layout from index 1, but the deferred-deleted widget from the first call may still be present at index 1, causing an off-by-one removal.
- **Tab switch and return**: After `_fade_in_widget()` attaches a `QGraphicsOpacityEffect` to an `IssueBadge`, the user switches tabs. On return, the effect is still attached and the widget renders with incorrect opacity or as a ghost.
- **Re-analyze with `_cards_widget` already visible**: `_cards_widget.setVisible(True)` is called at the end of `_display_baseline_summary()` but never reset to `False` at the start. On re-analyze the cards widget is already visible with stale card values while new values are being written, causing a visible flash of old data.

---

### Bug 2 — Pairs Selector Dialog: Heart and Lock Icons Not Rendering

#### Bug Condition

The bug manifests on Windows when `PairsSelectorDialog` creates favorite and lock toggle buttons via
`_make_favorite_button()` and `_make_lock_button()`. Both methods call `btn.setText("♥")` / `btn.setText("♡")`
/ `btn.setText("🔒")` / `btn.setText("🔓")`. The default Qt button font on Windows (`MS Shell Dlg 2` or
`Segoe UI`) does not include glyphs for these Unicode characters, so they render as empty squares (tofu).

**Formal Specification:**

```
FUNCTION isBugCondition_Bug2(X)
  INPUT: X of type ButtonCreationContext
  OUTPUT: boolean

  RETURN X.platform = "nt"
      AND font_supports_codepoint(X.button_font, X.unicode_char) = false
END FUNCTION
```

#### Examples

- **Windows, heart button**: `btn.setText("♥")` — renders as `□` because `Segoe UI` does not include U+2665.
- **Windows, lock button**: `btn.setText("🔒")` — renders as `□` because the default font does not include U+1F512.
- **Windows, toggle after click**: `_on_favorite_clicked()` calls `btn.setText("♡")` — still renders as `□`.
- **macOS / Linux**: Default system fonts (`Apple Color Emoji`, `Noto Color Emoji`) include these glyphs — no bug.

---

### Bug 3 — Timerange Preset Buttons: Text Getting Cut Off

#### Bug Condition

The bug manifests in `BacktestPage.init_ui()` and `DownloadDataPage.init_ui()` where each preset button is
created with `btn.setMaximumWidth(50)`. The labels `"120d"` and `"360d"` require more than 50 px to render
fully at the default system font size on Windows (typically ~52–58 px depending on DPI).

**Formal Specification:**

```
FUNCTION isBugCondition_Bug3(X)
  INPUT: X of type PresetButtonConfig
  OUTPUT: boolean

  RETURN X.maximum_width = 50
      AND rendered_text_width(X.label, X.font) > 50
END FUNCTION
```

#### Examples

- **`"120d"` button**: At 96 DPI with default font, the label requires ~54 px. With `setMaximumWidth(50)` the last character is clipped.
- **`"360d"` button**: Same issue — ~54 px required, 50 px allowed.
- **`"7d"` button**: ~28 px required — not clipped, but still constrained unnecessarily.
- **Window resize**: The `QHBoxLayout` with `addStretch()` would allow buttons to stay at natural size, but `setMaximumWidth(50)` overrides this regardless of available space.

---

### Bug 4 — General Label Text Clipping

#### Bug Condition

The bug manifests in `ImprovePage._init_ui()` where four subtitle labels (`_issues_subtitle`,
`_suggestions_subtitle`, `_candidate_subtitle`, `_comparison_subtitle`) are created with
`setWordWrap(False)`. At narrow window widths the labels are clipped rather than wrapping.

**Formal Specification:**

```
FUNCTION isBugCondition_Bug4(X)
  INPUT: X of type SubtitleLabelConfig
  OUTPUT: boolean

  RETURN X.word_wrap = false
      AND X.text_pixel_width > X.available_container_width
END FUNCTION
```

#### Examples

- **`_issues_subtitle`** at 800 px window width: `"Issues found in the baseline run that may be limiting strategy performance."` — 72 characters, ~520 px at 12 px font. Clipped when the scroll area is narrower than the text.
- **`_suggestions_subtitle`** at 800 px: Two-sentence label — even more likely to clip.
- **`_candidate_subtitle`** and **`_comparison_subtitle`**: Same pattern.
- **`pairs_selector_dialog.py` "Add Custom Pairs:" label**: No `setWordWrap` set; at minimum dialog width the label may be clipped.

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**

- `ImprovePage._on_analyze()` SHALL continue to populate the baseline summary form with the correct strategy metrics from the loaded run (Requirements 3.1, 3.2, 3.3, 3.4).
- `ImprovePage` metric cards SHALL continue to animate their progress bars using `QPropertyAnimation` (Requirement 3.9).
- `ImprovePage` Accept / Reject / Rollback flow SHALL continue to work correctly after the fix (Requirement 3.10).
- `PairsSelectorDialog` favorite toggle SHALL continue to persist state via `settings_state.toggle_favorite_pair()` and re-sort rows (Requirement 3.5).
- `PairsSelectorDialog` lock toggle SHALL continue to keep locked pairs selected and protected from randomize (Requirement 3.6).
- Timerange preset buttons SHALL continue to populate the timerange input field with the correct calculated date range string on both pages (Requirements 3.7, 3.8).
- All non-subtitle labels, non-preset buttons, and non-icon buttons are completely unaffected by these fixes.

**Scope:**

All inputs that do NOT trigger the specific bug conditions above are completely unaffected. This includes:
- Mouse clicks on action buttons in `ImprovePage` (Apply, Run Candidate Backtest, Accept, Reject, Rollback).
- Keyboard and mouse interactions in `PairsSelectorDialog` other than icon rendering.
- Timerange preset button click callbacks — only the width constraint changes, not the click handler.
- All other labels in the application that already have correct word-wrap settings.

---

## Hypothesized Root Cause

### Bug 1

1. **Asynchronous `deleteLater()` race**: `_display_baseline_summary()` calls `self._empty_baseline.deleteLater()` then immediately sets `self._empty_baseline = None`. The widget is still a layout child when the method continues, so subsequent layout operations see a stale child count.

2. **Same pattern in `_display_issues_and_suggestions()`**: `_empty_issues` and `_empty_suggestions` are set to `None` after `deleteLater()`. The layout-clearing loop (`while count > 1`) may encounter the not-yet-deleted widget at index 1 on a second call.

3. **`QGraphicsOpacityEffect` not cleaned up**: `_fade_in_widget()` attaches an effect to every faded widget but never removes it. When the page is hidden and reshown, Qt re-renders the effect, producing ghost opacity artefacts.

4. **`_cards_widget` not reset between calls**: `_display_baseline_summary()` calls `self._cards_widget.setVisible(True)` but never calls `setVisible(False)` at the start of the method. On re-analyze, the cards widget is already visible with stale values while new values are being written.

### Bug 2

1. **Missing emoji font on Windows**: The default `QPushButton` font (`Segoe UI` or `MS Shell Dlg 2`) does not include glyphs for U+2665 (♥), U+2661 (♡), U+1F512 (🔒), U+1F513 (🔓) on Windows. No explicit font is set on the buttons, so Qt falls back to the default and renders missing glyphs as empty squares.

### Bug 3

1. **`setMaximumWidth(50)` too narrow**: The constraint was likely set to keep buttons visually compact, but 50 px is insufficient for 4-character labels like `"120d"` and `"360d"` at standard DPI. The `QHBoxLayout` with `addStretch()` already handles spacing — the maximum width constraint is unnecessary.

### Bug 4

1. **`setWordWrap(False)` on subtitle labels**: All four subtitle labels in `ImprovePage._init_ui()` explicitly call `setWordWrap(False)`. This prevents Qt from wrapping the text when the container is narrower than the label's natural width, causing clipping instead of wrapping.

---

## Correctness Properties

Property 1: Bug Condition — Synchronous Empty-Panel Removal

_For any_ `ImprovePageAnalyzeCall` where `isBugCondition_Bug1` returns true (i.e., analyze is called one or more times, or the page has been hidden and reshown with fade effects attached), the fixed `_display_baseline_summary()` and `_display_issues_and_suggestions()` SHALL remove all `_empty_*` placeholder widgets synchronously (zero stale layout children after the call), remove all `QGraphicsOpacityEffect` instances after their animations complete, and reset `_cards_widget` visibility at the start of each call.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Bug Condition — Emoji Font Applied on Windows

_For any_ `ButtonCreationContext` where `isBugCondition_Bug2` returns true (platform is Windows and the default font lacks the required glyph), the fixed `_make_favorite_button()` and `_make_lock_button()` SHALL set a font on the button whose family is one of `{"Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"}` (or the system default as final fallback), ensuring the Unicode character renders as a visible glyph rather than an empty square.

**Validates: Requirements 2.5, 2.6**

Property 3: Bug Condition — Preset Button Has No Maximum Width of 50

_For any_ preset label string from `["7d", "14d", "30d", "90d", "120d", "360d"]`, the fixed button creation code SHALL NOT call `setMaximumWidth(50)` on the button, and SHALL call `setMinimumWidth(48)` instead, allowing the button to grow to fit its label.

**Validates: Requirements 2.7, 2.8**

Property 4: Bug Condition — Subtitle Labels Have Word Wrap Enabled

_For any_ subtitle label created by the fixed `ImprovePage._init_ui()` (issues, suggestions, candidate, comparison subtitles), the label SHALL have `wordWrap() == True`, ensuring long text wraps rather than being clipped at narrow window widths.

**Validates: Requirements 2.9, 2.10**

Property 5: Preservation — Analyze Results Correctness Unchanged

_For any_ `ImprovePageAnalyzeCall` where `isBugCondition_Bug1` does NOT hold (first analyze call with no prior stale state and no tab switch), the fixed `_on_analyze()` SHALL produce the same baseline summary form rows, issue badge count, and suggestion row count as the original function.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

Property 6: Preservation — Preset Button Click Behavior Unchanged

_For any_ preset label string, clicking the fixed preset button SHALL populate the timerange input with the same date range string as the original button, with no change to the click handler logic.

**Validates: Requirements 3.7, 3.8**

---

## Fix Implementation

### Bug 1 — `app/ui/pages/improve_page.py`

**Changes Required:**

1. **`_display_baseline_summary()` — replace `deleteLater()` with `setParent(None)`**

   Current code:
   ```python
   if self._empty_baseline is not None:
       self._empty_baseline.deleteLater()
       self._empty_baseline = None
   ```
   Fixed code:
   ```python
   if self._empty_baseline is not None:
       self._empty_baseline.setParent(None)
       self._empty_baseline = None
   ```
   `setParent(None)` immediately removes the widget from its parent layout and schedules it for deletion synchronously, eliminating the deferred-deletion race.

2. **`_display_baseline_summary()` — hide and re-show `_cards_widget`**

   At the very start of the method, before clearing the form, add:
   ```python
   self._cards_widget.setVisible(False)
   ```
   At the end of the method (after populating all cards), the existing `self._cards_widget.setVisible(True)` call remains. This forces a clean layout recalculation on every analyze call.

3. **`_display_issues_and_suggestions()` — replace `deleteLater()` with `setParent(None)` for `_empty_issues` and `_empty_suggestions`**

   Ensure the pattern is:
   ```python
   if self._empty_issues is not None:
       self._empty_issues.setParent(None)
       self._empty_issues = None
   # ... then clear layout from index 1
   ```
   Same pattern for `_empty_suggestions`.

4. **`_fade_in_widget()` — remove `QGraphicsOpacityEffect` after animation completes**

   Current code:
   ```python
   anim.start()
   widget._fade_anim = anim
   ```
   Fixed code:
   ```python
   anim.finished.connect(lambda: widget.setGraphicsEffect(None))
   anim.start()
   widget._fade_anim = anim
   ```
   This removes the opacity effect from the widget once the fade-in is complete, preventing ghost rendering artefacts when the page is hidden and reshown.

---

### Bug 2 — `app/ui/dialogs/pairs_selector_dialog.py`

**Changes Required:**

1. **Add `_emoji_font()` helper at module level**

   ```python
   import os
   import sys
   from PySide6.QtGui import QFont

   def _emoji_font() -> QFont:
       """Return a QFont with an emoji-capable family for the current platform."""
       if os.name == "nt":
           family = "Segoe UI Emoji"
       elif sys.platform == "darwin":
           family = "Apple Color Emoji"
       else:
           family = "Noto Color Emoji"
       font = QFont(family, 14)
       return font
   ```

   Font size 14 pt matches the `font-size: 14px` style used on icon labels elsewhere in the dialog.

2. **Apply `_emoji_font()` in `_make_favorite_button()`**

   ```python
   btn.setFont(_emoji_font())
   ```
   Added after `btn.setStyleSheet(...)`.

3. **Apply `_emoji_font()` in `_make_lock_button()`**

   ```python
   btn.setFont(_emoji_font())
   ```
   Added after `btn.setStyleSheet(...)`.

4. **Verify font persistence through `setText()` calls**

   Qt's `setText()` does not reset the font set via `setFont()`, so no re-application is needed in `_on_favorite_clicked()` or `_on_lock_clicked()`. The existing `setText()` calls are unchanged.

---

### Bug 3 — `app/ui/pages/backtest_page.py` and `app/ui/pages/download_data_page.py`

**Changes Required (identical in both files):**

1. **Remove `btn.setMaximumWidth(50)`**

2. **Add `btn.setMinimumWidth(48)`**

   The `QHBoxLayout` with `addStretch()` at the end of the presets row already handles spacing correctly. The minimum width of 48 px ensures a consistent baseline size while allowing the button to grow to fit its label.

   Before:
   ```python
   btn = QPushButton(preset)
   btn.setMaximumWidth(50)
   btn.clicked.connect(...)
   ```
   After:
   ```python
   btn = QPushButton(preset)
   btn.setMinimumWidth(48)
   btn.clicked.connect(...)
   ```

---

### Bug 4 — `app/ui/pages/improve_page.py`

**Changes Required:**

Change `setWordWrap(False)` to `setWordWrap(True)` on all four subtitle labels in `_init_ui()`:

- `_issues_subtitle`
- `_suggestions_subtitle`
- `_candidate_subtitle`
- `_comparison_subtitle`

Before:
```python
_issues_subtitle.setWordWrap(False)
```
After:
```python
_issues_subtitle.setWordWrap(True)
```

No other changes to these labels are required.

---

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on
unfixed code (exploratory checking), then verify the fix works correctly (fix checking) and that existing
behaviour is unchanged (preservation checking).

Because these are Qt widget bugs, the property-based tests are written as pure-logic tests that verify the
fix conditions without instantiating Qt widgets. This makes them fast, deterministic, and runnable in CI
without a display server.

---

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each bug on the unfixed code. Confirm or refute the root
cause analysis.

**Test Plan**: Write tests that inspect the widget configuration produced by the unfixed factory functions
and assert the buggy condition. Run on unfixed code to observe failures.

**Test Cases:**

1. **Bug 1 — `deleteLater()` leaves stale child** (will fail on unfixed code): Simulate two consecutive
   analyze calls and assert that the layout child count after the second call equals the expected count
   (no stale placeholder children).

2. **Bug 1 — `QGraphicsOpacityEffect` not removed** (will fail on unfixed code): Call `_fade_in_widget()`
   on a mock widget and assert that `widget.graphicsEffect()` is `None` after the animation's `finished`
   signal fires.

3. **Bug 2 — Default font lacks emoji glyph** (will fail on unfixed code): Create a `QPushButton` without
   setting a font and assert that `QFontMetrics(btn.font()).inFont(QChar('♥'))` returns `True` — this will
   fail on Windows with the default font.

4. **Bug 3 — `setMaximumWidth(50)` present** (will fail on unfixed code): Inspect the `maximumWidth()`
   of a preset button created by the unfixed code and assert it is not 50.

5. **Bug 4 — `wordWrap()` is False** (will fail on unfixed code): Inspect `wordWrap()` on a subtitle label
   created by the unfixed code and assert it is `True`.

**Expected Counterexamples:**

- Layout child count exceeds expected after second analyze call.
- `graphicsEffect()` is not `None` after animation completes.
- `maximumWidth()` equals 50 for preset buttons.
- `wordWrap()` is `False` for subtitle labels.

---

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed code produces the expected behaviour.

**Bug 1 pseudocode:**
```
FOR ALL X WHERE isBugCondition_Bug1(X) DO
  result := _display_baseline_summary_fixed(X)
  ASSERT layout_stale_child_count(result) = 0
      AND cards_widget_initially_hidden(result) = true
      AND graphics_effect_removed_after_animation(result) = true
END FOR
```

**Bug 2 pseudocode:**
```
FOR ALL X WHERE isBugCondition_Bug2(X) DO
  btn := _make_favorite_button_fixed(X)
  ASSERT btn.font().family() IN {"Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"}
      AND btn.font().pointSize() = 14
END FOR
```

**Bug 3 pseudocode:**
```
FOR ALL label IN ["7d", "14d", "30d", "90d", "120d", "360d"] DO
  btn := create_preset_button_fixed(label)
  ASSERT btn.maximumWidth() != 50
      AND btn.minimumWidth() = 48
END FOR
```

**Bug 4 pseudocode:**
```
FOR ALL subtitle_label IN [issues, suggestions, candidate, comparison] DO
  lbl := create_subtitle_label_fixed(subtitle_label)
  ASSERT lbl.wordWrap() = true
END FOR
```

---

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed code produces the same
result as the original code.

**Pseudocode (general form):**
```
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT original_function(X) = fixed_function(X)
END FOR
```

**Testing Approach**: Property-based testing with `hypothesis` is used for preservation checking because:
- It generates many test cases automatically across the input domain.
- It catches edge cases that manual unit tests might miss.
- It provides strong guarantees that behaviour is unchanged for all non-buggy inputs.

**Test Cases:**

1. **Bug 1 — Analyze results correctness preserved**: For any `BacktestSummary` with valid metric values,
   the fixed `_display_baseline_summary()` SHALL produce the same form row count and card values as the
   original. Verified by extracting the pure-logic parts (color selection, bar percentage calculation) into
   testable functions.

2. **Bug 2 — Favorite toggle persistence preserved**: For any pair name string, `_on_favorite_clicked()`
   SHALL still call `settings_state.toggle_favorite_pair()` and update the button text correctly.

3. **Bug 3 — Preset click handler preserved**: For any preset label string, the click handler SHALL still
   call `_on_timerange_preset(preset)` with the correct preset value.

4. **Bug 4 — Label text content preserved**: For any subtitle text string, the fixed label SHALL have the
   same text content as the original — only `wordWrap()` changes.

---

### Unit Tests

- Test that `_emoji_font()` returns a `QFont` with a non-empty family for each platform string (`"nt"`, `"darwin"`, `"linux"`).
- Test that `_emoji_font()` returns font size 14.
- Test that a preset button created by the fixed code has `minimumWidth() == 48` and `maximumWidth() != 50`.
- Test that all four subtitle labels in `ImprovePage` have `wordWrap() == True` after construction.
- Test that `_fade_in_widget()` connects `anim.finished` to a slot that calls `widget.setGraphicsEffect(None)`.

### Property-Based Tests

All four properties below are implemented in `tests/ui/test_ui_rendering_bugs.py` using `hypothesis`.
They are pure-logic tests that do not instantiate Qt widgets.

- **Property 1** (Bug 1 fix check): For any integer `n >= 1` representing the number of consecutive analyze
  calls, a `_clear_layout_synchronously()` helper (extracted from the fix) leaves zero stale children in a
  simulated layout.
- **Property 2** (Bug 2 fix check): For any platform string from `["nt", "darwin", "linux", "posix"]`,
  `_emoji_font(platform)` returns a `QFont` whose `family()` is non-empty and is one of the known emoji
  font families.
- **Property 3** (Bug 3 fix check): For any preset label string from
  `["7d", "14d", "30d", "90d", "120d", "360d"]`, the button configuration produced by the fixed creation
  logic does NOT include `maximum_width == 50`.
- **Property 4** (Bug 4 fix check): For any subtitle text string (generated by `hypothesis.strategies.text()`),
  the label configuration produced by the fixed creation logic has `word_wrap == True`.

### Integration Tests

- Test the full `ImprovePage` analyze flow twice in sequence (simulated with mocked services) and assert
  that the baseline summary group contains exactly the expected number of form rows after each call.
- Test that switching the active tab away from `ImprovePage` and back does not leave `QGraphicsOpacityEffect`
  instances on any child widget.
- Test that the `PairsSelectorDialog` renders correctly on a simulated Windows platform by verifying the
  font family on the favorite and lock buttons.
- Test that clicking a timerange preset button on `BacktestPage` and `DownloadDataPage` populates the
  timerange input with the correct value (regression test for the click handler after the width fix).
