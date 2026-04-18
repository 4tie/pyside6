# Bugfix Requirements Document

## Introduction

The Improve tab GUI stops updating correctly after the first candidate backtest cycle completes. Two independent object-lifetime bugs in `app/ui/pages/improve_page.py` cause Qt C++ objects to be deleted while Python still holds references to them. Any subsequent call that touches those references silently fails, leaving the UI frozen: the terminal produces no output, and the Accept / Reject / Rollback buttons never appear after a second candidate run.

**Bug 1 — Terminal widget deleted on second call to `_update_candidate_preview()`.**
The layout-clearing loop in `_update_candidate_preview()` iterates over every widget added since the subtitle label and calls `deleteLater()` on each. On the first call the terminal is not yet in the layout, so it survives. On the second call the terminal (added at the end of the first call) is encountered by the loop and scheduled for deletion. `self._terminal` becomes a dangling reference; subsequent calls to `clear_output()` or `append_output()` silently fail.

**Bug 2 — Accept / Reject / Rollback buttons deleted when `_update_comparison_view()` clears its layout.**
The three buttons are pre-created in `__init__` and added as children of `arb_widget` inside `_update_comparison_view()`. When `_update_comparison_view()` is called again (e.g. after Accept sets `_candidate_run = None`), the clearing loop calls `arb_widget.deleteLater()`, which also destroys all its children — including the three pre-created buttons. The next call to `_update_comparison_view()` calls `.setVisible()` and `.setStyleSheet()` on deleted objects; those calls silently fail and the buttons never appear.

---

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `_update_candidate_preview()` is called a second time (e.g. after applying a second suggestion or after accept/reject) THEN the system calls `deleteLater()` on `self._terminal` because it was added to the layout during the first call and is encountered by the clearing loop

1.2 WHEN `self._terminal.clear_output()` or `self._terminal.append_output()` is called after the second invocation of `_update_candidate_preview()` THEN the system silently fails to update the terminal because the underlying C++ Qt object has been deleted

1.3 WHEN `_update_comparison_view()` is called a second time (e.g. after Accept or Reject sets `_candidate_run = None`) THEN the system calls `deleteLater()` on `arb_widget`, which also destroys `accept_btn`, `reject_btn`, and `rollback_btn` as child widgets

1.4 WHEN `_update_comparison_view()` is called again after a new candidate backtest completes THEN the system silently fails to show the Accept / Reject / Rollback buttons because `.setVisible(True)` and `.setStyleSheet()` are called on deleted C++ objects

### Expected Behavior (Correct)

2.1 WHEN `_update_candidate_preview()` is called any number of times THEN the system SHALL preserve `self._terminal` as a live Qt object by removing it from the layout before the clearing loop runs, so it is never passed to `deleteLater()`

2.2 WHEN `self._terminal.clear_output()` or `self._terminal.append_output()` is called after any invocation of `_update_candidate_preview()` THEN the system SHALL successfully update the terminal output because the widget remains a valid Qt object

2.3 WHEN `_update_comparison_view()` is called any number of times THEN the system SHALL create fresh Accept / Reject / Rollback button instances locally within the method so they are never pre-existing children of a widget that gets deleted by the clearing loop

2.4 WHEN `_update_comparison_view()` is called after a new candidate backtest completes THEN the system SHALL display the Accept / Reject / Rollback buttons with correct visibility, style, and signal connections

### Unchanged Behavior (Regression Prevention)

3.1 WHEN `_update_candidate_preview()` is called for the first time after applying a suggestion THEN the system SHALL CONTINUE TO display the parameter diff table and the Run Candidate Backtest button correctly

3.2 WHEN the candidate backtest process produces stdout or stderr output THEN the system SHALL CONTINUE TO stream that output to the terminal widget in real time

3.3 WHEN `_update_comparison_view()` is called with both `_baseline_run` and `_candidate_run` set THEN the system SHALL CONTINUE TO render the delta cards, the comparison table, and the action buttons

3.4 WHEN the Accept button is clicked THEN the system SHALL CONTINUE TO write candidate parameters to the strategy file, promote the candidate to baseline, and reset `_candidate_run` to `None`

3.5 WHEN the Reject button is clicked THEN the system SHALL CONTINUE TO discard the candidate sandbox, reset `_candidate_run` to `None`, and restore the candidate config to the current baseline params

3.6 WHEN the Rollback button is clicked THEN the system SHALL CONTINUE TO restore strategy parameters to the previous accepted state from `_baseline_history`

3.7 WHEN `_update_comparison_view()` is called with `_candidate_run` equal to `None` THEN the system SHALL CONTINUE TO clear the comparison layout without rendering the table or action buttons

---

## Bug Condition Pseudocode

### Bug 1 — Terminal Widget Deletion

```pascal
FUNCTION isBugCondition_Terminal(callCount)
  INPUT: callCount — number of times _update_candidate_preview() has been called
  OUTPUT: boolean

  RETURN callCount >= 2
END FUNCTION

// Property: Fix Checking — Terminal survives repeated calls
FOR ALL callCount WHERE isBugCondition_Terminal(callCount) DO
  invoke _update_candidate_preview() callCount times
  ASSERT self._terminal is a valid (non-deleted) Qt object
  ASSERT self._terminal.clear_output() executes without error
  ASSERT self._terminal.append_output("x") appends text to the widget
END FOR

// Property: Preservation Checking
FOR ALL callCount WHERE NOT isBugCondition_Terminal(callCount) DO
  ASSERT F(callCount) = F'(callCount)   // first call behavior unchanged
END FOR
```

### Bug 2 — Accept/Reject/Rollback Button Deletion

```pascal
FUNCTION isBugCondition_Buttons(comparisonViewCallCount)
  INPUT: comparisonViewCallCount — number of times _update_comparison_view() has been called
  OUTPUT: boolean

  RETURN comparisonViewCallCount >= 2
END FUNCTION

// Property: Fix Checking — Buttons are valid and visible after repeated calls
FOR ALL comparisonViewCallCount WHERE isBugCondition_Buttons(comparisonViewCallCount) DO
  invoke _update_comparison_view() comparisonViewCallCount times with _candidate_run set
  ASSERT accept_btn is a valid (non-deleted) Qt object AND accept_btn.isVisible() = True
  ASSERT reject_btn is a valid (non-deleted) Qt object AND reject_btn.isVisible() = True
END FOR

// Property: Preservation Checking
FOR ALL comparisonViewCallCount WHERE NOT isBugCondition_Buttons(comparisonViewCallCount) DO
  ASSERT F(comparisonViewCallCount) = F'(comparisonViewCallCount)
END FOR
```
