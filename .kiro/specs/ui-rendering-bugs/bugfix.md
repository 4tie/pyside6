# Bugfix Requirements Document

## Introduction

Four UI rendering bugs affect the Freqtrade GUI PySide6 desktop application on Windows.

**Bug 1 — Improve Page: Partial/Stale Analyze Results on Tab Switch**
When the user clicks "Analyze Run" on the Improve tab, the results area (metric cards, baseline summary, issues, suggestions) renders incompletely or with visual glitches. Switching away to another tab and returning causes the previously loaded results to appear stale or partially rendered. The root cause is deferred widget deletion (`deleteLater()`) leaving stale layout references, `_empty_*` panel references being set to `None` before Qt has processed the deletion, `_cards_widget` visibility/layout state not being fully reset between calls, and `QGraphicsOpacityEffect` fade animations leaving ghost effects when the page is hidden and reshown.

**Bug 2 — Pairs Selector Dialog: Heart and Lock Icons Not Rendering**
In the pairs selector dialog, the favorite heart buttons (♥/♡) and lock buttons (🔒/🔓) display as empty squares on Windows. The buttons use Unicode emoji characters set via `QPushButton.setText()`, which do not render in the default Qt button font on Windows.

**Bug 3 — Time Range Preset Buttons: Text Getting Cut Off**
In the Backtest and Download Data pages, the timerange preset buttons ("7d", "14d", "30d", "90d", "120d", "360d") have `setMaximumWidth(50)` applied, which is too narrow. Longer labels such as "120d" and "360d" are visually clipped.

**Bug 4 — General Layout/Text Clipping Across the App**
Various labels and text elements across the app are cut off because widgets lack sufficient minimum sizes or word wrap. This includes group box subtitles in `improve_page.py` and labels in the pairs selector dialog.

---

## Bug Analysis

### Current Behavior (Defect)

**Bug 1 — Improve Page stale/partial results:**

1.1 WHEN the user clicks "Analyze Run" on the Improve page for the first time THEN the system renders metric cards, baseline summary, issues, and suggestions incompletely or with visual glitches due to stale layout children from deferred `deleteLater()` calls

1.2 WHEN the user clicks "Analyze Run" a second time (re-analyze) THEN the system may show a mix of old and new widgets because `_empty_baseline`, `_empty_issues`, and `_empty_suggestions` references are set to `None` immediately after `deleteLater()` while Qt has not yet removed them from the layout

1.3 WHEN the user switches away from the Improve tab and returns after an analyze THEN the system displays stale or ghost-rendered results because `QGraphicsOpacityEffect` instances attached to widgets during fade-in animations are not cleaned up when the page is hidden

1.4 WHEN `_display_baseline_summary()` is called while `_cards_widget` is already visible from a prior analyze THEN the system does not reset the cards widget visibility or layout state, causing layout count mismatches

**Bug 2 — Pairs selector icon rendering:**

1.5 WHEN the pairs selector dialog is opened on Windows THEN the system renders the favorite heart buttons (♥/♡) and lock buttons (🔒/🔓) as empty squares because the default Qt button font does not support these Unicode emoji/symbol characters on Windows

1.6 WHEN a user toggles a favorite or lock state in the pairs selector dialog on Windows THEN the system updates the button text to the toggled Unicode character but the button continues to display as an empty square

**Bug 3 — Timerange preset button text clipping:**

1.7 WHEN the Backtest page or Download Data page is displayed THEN the system clips the text of timerange preset buttons ("120d", "360d", and others) because `setMaximumWidth(50)` is too narrow to accommodate the full label text

1.8 WHEN the application window is resized THEN the system keeps the preset buttons at the fixed maximum width of 50px, preventing the text from ever being fully visible regardless of available space

**Bug 4 — General text clipping:**

1.9 WHEN the Improve page is displayed THEN the system clips the subtitle labels inside the "Detected Issues" and "Suggested Actions" group boxes because `setWordWrap(False)` is set on labels that may exceed the available width

1.10 WHEN the pairs selector dialog is displayed at its default size THEN the system may clip label text that lacks a minimum width or word wrap setting

---

### Expected Behavior (Correct)

**Bug 1 — Improve Page stale/partial results:**

2.1 WHEN the user clicks "Analyze Run" on the Improve page for the first time THEN the system SHALL render all metric cards, baseline summary rows, issue badges, and suggestion rows completely and without visual glitches

2.2 WHEN the user clicks "Analyze Run" a second time THEN the system SHALL fully clear all previously rendered widgets synchronously before populating new content, ensuring no mix of old and new widgets appears

2.3 WHEN the user switches away from the Improve tab and returns after an analyze THEN the system SHALL display the previously loaded results correctly without ghost rendering or opacity artifacts from prior fade-in animations

2.4 WHEN `_display_baseline_summary()` is called while `_cards_widget` is already visible THEN the system SHALL reset the cards widget and layout state cleanly so that subsequent analyze calls produce a consistent layout

**Bug 2 — Pairs selector icon rendering:**

2.5 WHEN the pairs selector dialog is opened on Windows THEN the system SHALL render the favorite heart buttons and lock buttons with clearly visible icons using a font that supports the required characters (e.g., "Segoe UI Emoji" on Windows with a cross-platform fallback)

2.6 WHEN a user toggles a favorite or lock state in the pairs selector dialog on Windows THEN the system SHALL update the button to display the correct toggled icon visibly

**Bug 3 — Timerange preset button text clipping:**

2.7 WHEN the Backtest page or Download Data page is displayed THEN the system SHALL render all timerange preset button labels ("7d", "14d", "30d", "90d", "120d", "360d") fully without clipping by using a minimum width instead of a restrictive maximum width

2.8 WHEN the application window is resized THEN the system SHALL allow the preset buttons to expand naturally within their layout so that all label text remains fully visible

**Bug 4 — General text clipping:**

2.9 WHEN the Improve page is displayed THEN the system SHALL render all group box subtitle labels with word wrap enabled so that long text wraps rather than being clipped

2.10 WHEN the pairs selector dialog is displayed THEN the system SHALL render all labels with sufficient minimum sizing or word wrap so that no text is clipped at the default dialog size

---

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the user clicks "Analyze Run" and the run loads successfully THEN the system SHALL CONTINUE TO populate the baseline summary form with the correct strategy metrics from the loaded run

3.2 WHEN the user clicks "Analyze Run" and issues are detected THEN the system SHALL CONTINUE TO display the correct number of issue badges and update the "Detected Issues" group box title with the count

3.3 WHEN the user clicks "Analyze Run" and suggestions are generated THEN the system SHALL CONTINUE TO display the correct suggestion rows with Apply buttons and update the "Suggested Actions" group box title with the count

3.4 WHEN the user clicks "Analyze Run" and no issues are detected THEN the system SHALL CONTINUE TO display the "no issues detected" message and the healthy status label

3.5 WHEN the user toggles a favorite in the pairs selector dialog THEN the system SHALL CONTINUE TO persist the favorite state via `settings_state.toggle_favorite_pair()` and re-sort the rows with favorites first

3.6 WHEN the user toggles a lock in the pairs selector dialog THEN the system SHALL CONTINUE TO maintain the locked pair in the selection and prevent it from being deselected by randomize

3.7 WHEN the user clicks a timerange preset button on the Backtest page THEN the system SHALL CONTINUE TO populate the timerange input field with the correct calculated date range string

3.8 WHEN the user clicks a timerange preset button on the Download Data page THEN the system SHALL CONTINUE TO populate the timerange input field with the correct calculated date range string and save the preference

3.9 WHEN the Improve page metric cards are populated THEN the system SHALL CONTINUE TO animate the progress bar from its current value to the new target value using the existing `QPropertyAnimation`

3.10 WHEN the user applies a suggestion and runs a candidate backtest THEN the system SHALL CONTINUE TO display the results comparison table and Accept/Reject/Rollback buttons correctly

---

## Bug Condition Pseudocode

### Bug 1 — Improve Page Stale/Partial Results

```pascal
FUNCTION isBugCondition_Bug1(X)
  INPUT: X of type ImprovePageAnalyzeCall
  OUTPUT: boolean

  // Bug triggers when analyze is called and any of the following hold:
  RETURN (X.analyze_call_count >= 1)
      OR (X.tab_was_hidden_and_reshown = true AND X.fade_effects_attached = true)
END FUNCTION

// Property: Fix Checking
FOR ALL X WHERE isBugCondition_Bug1(X) DO
  result ← _on_analyze'(X)
  ASSERT all_layout_children_are_current(result)
      AND no_ghost_opacity_effects(result)
      AND cards_widget_state_is_reset(result)
END FOR

// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition_Bug1(X) DO
  ASSERT _on_analyze(X) = _on_analyze'(X)
END FOR
```

### Bug 2 — Pairs Selector Icon Rendering

```pascal
FUNCTION isBugCondition_Bug2(X)
  INPUT: X of type ButtonCreationContext
  OUTPUT: boolean

  RETURN X.platform = "Windows"
      AND X.font_supports_emoji = false
END FUNCTION

// Property: Fix Checking
FOR ALL X WHERE isBugCondition_Bug2(X) DO
  result ← _make_favorite_button'(X)
  ASSERT button_icon_is_visible(result) = true
END FOR

// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition_Bug2(X) DO
  ASSERT _make_favorite_button(X) = _make_favorite_button'(X)
END FOR
```

### Bug 3 — Timerange Preset Button Text Clipping

```pascal
FUNCTION isBugCondition_Bug3(X)
  INPUT: X of type PresetButton
  OUTPUT: boolean

  // Bug triggers for any preset label that exceeds 50px rendered width
  RETURN X.maximum_width = 50
      AND rendered_text_width(X.label) > 50
END FUNCTION

// Property: Fix Checking
FOR ALL X WHERE isBugCondition_Bug3(X) DO
  result ← create_preset_button'(X)
  ASSERT text_is_fully_visible(result) = true
      AND result.maximum_width = UNSET
END FOR

// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition_Bug3(X) DO
  ASSERT preset_button_click_behavior(X) = preset_button_click_behavior'(X)
END FOR
```

### Bug 4 — General Text Clipping

```pascal
FUNCTION isBugCondition_Bug4(X)
  INPUT: X of type LabelWidget
  OUTPUT: boolean

  RETURN X.word_wrap = false
      AND X.text_pixel_width > X.available_width
END FUNCTION

// Property: Fix Checking
FOR ALL X WHERE isBugCondition_Bug4(X) DO
  result ← create_label'(X)
  ASSERT text_is_fully_visible(result) = true
END FOR

// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition_Bug4(X) DO
  ASSERT label_display(X) = label_display'(X)
END FOR
```
