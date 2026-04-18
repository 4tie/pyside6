# Improve Tab GUI Update Bug — Bugfix Design

## Overview

Two independent Qt object-lifetime bugs in `app/ui/pages/improve_page.py` cause the Improve tab
to stop updating after the first candidate backtest cycle completes.

**Bug 1** — `_update_candidate_preview()` contains a layout-clearing loop that iterates over every
widget added after the subtitle label and calls `deleteLater()` on each. On the first call the
terminal (`self._terminal`) is not yet in the layout, so it survives. On the second call the
terminal — added at the end of the first call — is encountered by the loop and scheduled for
deletion. `self._terminal` becomes a dangling reference; subsequent `clear_output()` /
`append_output()` calls silently fail and the terminal produces no output.

**Bug 2** — `accept_btn`, `reject_btn`, and `rollback_btn` are pre-created in `__init__` and
added as children of a transient `arb_widget` inside `_update_comparison_view()`. When
`_update_comparison_view()` is called again (e.g. after Accept sets `_candidate_run = None`),
the clearing loop calls `arb_widget.deleteLater()`, which also destroys all its children —
including the three pre-created buttons. The next call to `_update_comparison_view()` calls
`.setVisible()` and `.setStyleSheet()` on deleted C++ objects; those calls silently fail and
the buttons never appear.

The fix strategy is minimal and targeted:

- **Fix 1**: Detach `self._terminal` from the layout with `removeWidget()` *before* the clearing
  loop runs, so it is never passed to `deleteLater()`. Re-add it at the end as before.
- **Fix 2**: Remove the pre-creation of the three buttons from `__init__` and `_init_ui()`.
  Create fresh local button instances inside `_update_comparison_view()` on every call.

---

## Glossary

- **Bug_Condition (C)**: The condition that triggers a bug — either `callCount >= 2` for
  `_update_candidate_preview()` (Bug 1) or `comparisonViewCallCount >= 2` for
  `_update_comparison_view()` (Bug 2).
- **Property (P)**: The desired correct behavior when the bug condition holds — the terminal
  remains a valid Qt object (Bug 1) and the Accept/Reject/Rollback buttons are valid and visible
  (Bug 2).
- **Preservation**: Existing first-call behavior, terminal streaming, comparison table rendering,
  and accept/reject/rollback signal connections that must remain unchanged by the fix.
- **`_update_candidate_preview()`**: The method in `app/ui/pages/improve_page.py` that rebuilds
  the "Candidate Changes" group box, including the parameter diff table, the Run Candidate
  Backtest button, and the terminal widget.
- **`_update_comparison_view()`**: The method in `app/ui/pages/improve_page.py` that rebuilds
  the "Results Comparison" group box, including delta cards, the comparison table, and the
  Accept/Reject/Rollback action buttons.
- **`self._terminal`**: The `TerminalWidget` instance created once in `__init__` and re-added to
  `_candidate_layout` on every call to `_update_candidate_preview()`.
- **`arb_widget`**: The transient `QWidget` created inside `_update_comparison_view()` to hold
  the action buttons row. It is added to `_comparison_layout` and destroyed by the clearing loop
  on the next call.
- **`deleteLater()`**: Qt method that schedules a C++ object for deletion on the next event-loop
  iteration. After this call the Python wrapper becomes a dangling reference.
- **`removeWidget()`**: Qt layout method that detaches a widget from a layout without deleting it.

---

## Bug Details

### Bug Condition

**Bug 1 — Terminal widget deleted on second call to `_update_candidate_preview()`**

The clearing loop in `_update_candidate_preview()` iterates over every item at index > 0 in
`_candidate_layout` and calls `deleteLater()` on any widget it finds. On the first call the
terminal has not yet been added to the layout, so it is not encountered. On the second call the
terminal is at the last position in the layout (added at the end of the first call) and is
therefore passed to `deleteLater()`. `self._terminal` becomes a dangling reference.

**Formal Specification:**
```
FUNCTION isBugCondition_Terminal(callCount)
  INPUT: callCount — number of times _update_candidate_preview() has been called
  OUTPUT: boolean

  RETURN callCount >= 2
END FUNCTION
```

**Bug 2 — Accept/Reject/Rollback buttons deleted when `_update_comparison_view()` clears its layout**

The three buttons are pre-created in `__init__` and added as children of `arb_widget` inside
`_update_comparison_view()`. When `_update_comparison_view()` is called again, the clearing loop
calls `arb_widget.deleteLater()`, which also destroys all its children — including the three
pre-created buttons. Subsequent calls to `.setVisible(True)` and `.setStyleSheet()` on the
deleted objects silently fail.

**Formal Specification:**
```
FUNCTION isBugCondition_Buttons(comparisonViewCallCount)
  INPUT: comparisonViewCallCount — number of times _update_comparison_view() has been called
  OUTPUT: boolean

  RETURN comparisonViewCallCount >= 2
END FUNCTION
```

### Examples

**Bug 1 examples:**
- User applies a suggestion (call 1): terminal is added to layout, output streams correctly.
  User applies a second suggestion (call 2): terminal is deleted by the clearing loop.
  `self._terminal.clear_output()` silently fails — no output appears during the second backtest.
- User clicks "Reset to Baseline" (call 2): same deletion occurs; terminal is gone.
- User clicks "Reject & Discard" which calls `_update_candidate_preview()` (call 2): terminal
  is deleted; the next candidate backtest produces no terminal output.

**Bug 2 examples:**
- User runs a candidate backtest (call 1): Accept/Reject/Rollback buttons appear correctly.
  User clicks Accept (sets `_candidate_run = None`, calls `_update_comparison_view()` — call 2):
  `arb_widget.deleteLater()` destroys the three buttons. User runs another candidate backtest
  (call 3): `_update_comparison_view()` calls `.setVisible(True)` on deleted objects — buttons
  never appear.
- User clicks Reject (same sequence): identical outcome — buttons missing on the next cycle.

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- On the first call to `_update_candidate_preview()`, the parameter diff table and the
  Run Candidate Backtest button must render exactly as before the fix.
- Terminal streaming (`append_output`, `append_error`) must continue to work after any number
  of calls to `_update_candidate_preview()`.
- On the first call to `_update_comparison_view()` with both `_baseline_run` and
  `_candidate_run` set, the delta cards and comparison table must render identically to
  pre-fix behavior.
- The Accept button's `clicked` signal must remain connected to `_on_accept`.
- The Reject button's `clicked` signal must remain connected to `_on_reject`.
- The Rollback button's `clicked` signal must remain connected to `_on_rollback`.
- The Rollback button must be hidden when `_baseline_history` is empty and visible when it
  is non-empty.
- `_update_comparison_view()` called with `_candidate_run = None` must clear the layout
  without rendering the table or action buttons.

**Scope:**
All inputs that do NOT involve a second (or later) call to `_update_candidate_preview()` or
`_update_comparison_view()` should be completely unaffected by this fix. This includes:
- First-call rendering of the candidate preview and comparison view.
- Mouse clicks on any button (Apply, Run Candidate Backtest, Stop, Reset to Baseline).
- Strategy and run combo-box selection.
- Settings changes and strategy refresh.

---

## Hypothesized Root Cause

### Bug 1 — Terminal widget deletion

1. **Layout clearing loop does not exclude the terminal**: The loop at the top of
   `_update_candidate_preview()` removes and deletes every widget at index > 0 in
   `_candidate_layout`. There is no guard to skip `self._terminal`. On the first call the
   terminal is not yet in the layout (it is added at the end of the method), so it survives.
   On the second call it is at the last position and is deleted.

2. **`self._terminal` is a long-lived singleton**: The terminal is created once in `__init__`
   and is intended to persist for the lifetime of the page. The clearing loop was written to
   remove dynamically-created widgets but inadvertently treats the terminal as one of them.

3. **Qt's `deleteLater()` is deferred but irreversible**: The Python wrapper object remains
   alive but the underlying C++ object is destroyed on the next event-loop iteration. Any
   subsequent method call on the wrapper silently fails without raising a Python exception,
   making the bug hard to detect at runtime.

### Bug 2 — Accept/Reject/Rollback button deletion

1. **Pre-created buttons become children of a transient container**: `arb_widget` is a
   `QWidget` created locally inside `_update_comparison_view()` and added to
   `_comparison_layout`. When a widget is added to a layout, Qt reparents it to the layout's
   parent widget. The three pre-created buttons are added to `arb_widget`'s layout, making
   `arb_widget` their parent. When `arb_widget.deleteLater()` is called by the clearing loop,
   Qt's parent-child ownership model destroys all children along with it.

2. **The clearing loop does not distinguish pre-created from dynamically-created widgets**:
   The loop removes and deletes every widget at index > 0 in `_comparison_layout`. It has no
   knowledge that `arb_widget` holds pre-created buttons that must survive.

3. **Silent failure of calls on deleted objects**: As with Bug 1, `.setVisible()` and
   `.setStyleSheet()` on deleted C++ objects silently fail, so the buttons simply never appear
   rather than raising an exception.

---

## Correctness Properties

Property 1: Bug Condition — Terminal Survives Repeated Calls

_For any_ `callCount >= 2`, after calling `_update_candidate_preview()` `callCount` times, the
fixed method SHALL preserve `self._terminal` as a valid (non-deleted) Qt object such that
`self._terminal.clear_output()` executes without error and `self._terminal.append_output(text)`
appends `text` to the terminal output display.

**Validates: Requirements 2.1, 2.2**

Property 2: Bug Condition — Action Buttons Valid After Repeated Comparison View Calls

_For any_ `comparisonViewCallCount >= 2`, after calling `_update_comparison_view()`
`comparisonViewCallCount` times with `_candidate_run` set on each call, the fixed method SHALL
render Accept and Reject buttons that are valid (non-deleted) Qt objects with
`isVisible() == True` and correct signal connections to `_on_accept` and `_on_reject`
respectively.

**Validates: Requirements 2.3, 2.4**

Property 3: Preservation — First-Call Candidate Preview Unchanged

_For any_ single call to `_update_candidate_preview()` (i.e. `callCount == 1`), the fixed
method SHALL produce the same parameter diff table and Run Candidate Backtest button as the
original unfixed method, preserving all first-call rendering behavior.

**Validates: Requirements 3.1**

Property 4: Preservation — Terminal Streaming Unchanged

_For any_ number of calls to `_update_candidate_preview()`, the fixed method SHALL leave
`self._terminal` in a state where `append_output(text)` appends `text` to the terminal output
display, preserving real-time streaming behavior for all subsequent candidate backtests.

**Validates: Requirements 3.2**

Property 5: Preservation — Comparison Table Unchanged

_For any_ `comparisonViewCallCount >= 1` with both `_baseline_run` and `_candidate_run` set,
the fixed `_update_comparison_view()` SHALL render the delta cards and comparison table
identically to the pre-fix behavior, preserving all metric display and color-coding logic.

**Validates: Requirements 3.3**

---

## Fix Implementation

### Changes Required

**File**: `app/ui/pages/improve_page.py`

#### Fix 1 — Protect terminal widget from deletion in `_update_candidate_preview()`

**Function**: `_update_candidate_preview()`

**Specific Changes**:

1. **Detach terminal before the clearing loop**: Add a `removeWidget()` call immediately before
   the `while` loop. This detaches `self._terminal` from `_candidate_layout` without scheduling
   it for deletion. The loop then never encounters it.

   ```python
   # Detach terminal before clearing so it is never passed to deleteLater()
   self._candidate_layout.removeWidget(self._terminal)
   ```

2. **Clearing loop and re-add remain unchanged**: The existing loop body and the final
   `self._candidate_layout.addWidget(self._terminal)` at the end of the method are kept as-is.

#### Fix 2 — Create Accept/Reject/Rollback buttons locally in `_update_comparison_view()`

**Functions**: `__init__()`, `_init_ui()`, `_update_comparison_view()`

**Specific Changes**:

1. **Remove pre-creation from `__init__`**: Delete the six lines that create `accept_btn`,
   `reject_btn`, `rollback_btn` and connect their `clicked` signals.

   ```python
   # DELETE:
   self.accept_btn = QPushButton("✅ Accept & Save")
   self.accept_btn.clicked.connect(self._on_accept)
   self.reject_btn = QPushButton("✕ Reject & Discard")
   self.reject_btn.clicked.connect(self._on_reject)
   self.rollback_btn = QPushButton("↩ Rollback to Previous")
   self.rollback_btn.clicked.connect(self._on_rollback)
   ```

2. **Remove tooltip setup from `_init_ui()`**: Delete the three `setToolTip()` calls for the
   pre-created buttons in `_init_ui()`.

   ```python
   # DELETE:
   self.accept_btn.setToolTip("Write the candidate parameters to the strategy file. ...")
   self.reject_btn.setToolTip("Discard the candidate parameters. ...")
   self.rollback_btn.setToolTip("Restore the strategy parameters to the state before the last Accept.")
   ```

3. **Replace the button section in `_update_comparison_view()`**: Remove the block that calls
   `.setVisible()`, `.setStyleSheet()`, and adds the pre-created buttons to `arb_row`. Replace
   it with local variable creation, style/tooltip/signal setup, and layout construction:

   ```python
   # Create fresh button instances — never reuse pre-created ones
   accept_btn = QPushButton("✅ Accept & Save")
   accept_btn.setStyleSheet(self._btn_style(_C_GREEN, "white"))
   accept_btn.setToolTip(
       "Write the candidate parameters to the strategy file. "
       "This replaces the current parameters permanently."
   )
   accept_btn.clicked.connect(self._on_accept)

   reject_btn = QPushButton("✕ Reject & Discard")
   reject_btn.setStyleSheet(self._btn_style(_C_RED, "white"))
   reject_btn.setToolTip("Discard the candidate parameters. The strategy file is not modified.")
   reject_btn.clicked.connect(self._on_reject)

   rollback_btn = QPushButton("↩ Rollback to Previous")
   rollback_btn.setStyleSheet(self._btn_style(_C_ORANGE, "white"))
   rollback_btn.setToolTip(
       "Restore the strategy parameters to the state before the last Accept."
   )
   rollback_btn.setVisible(len(self._baseline_history) > 0)
   rollback_btn.clicked.connect(self._on_rollback)

   arb_row = QHBoxLayout()
   arb_row.addWidget(accept_btn)
   arb_row.addWidget(reject_btn)
   arb_row.addWidget(rollback_btn)
   arb_row.addStretch()
   arb_widget = QWidget()
   arb_widget.setStyleSheet("background: transparent;")
   arb_widget.setLayout(arb_row)
   self._comparison_layout.addWidget(arb_widget)
   ```

4. **No changes to `_on_accept`, `_on_reject`, `_on_rollback`**: These handlers do not
   reference `self.accept_btn`, `self.reject_btn`, or `self.rollback_btn`, so they require no
   modification.

---

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that
demonstrate each bug on the unfixed code to confirm the root cause analysis; then verify the
fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bugs BEFORE implementing the fix.
Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that instantiate `ImprovePage` with a minimal mock `SettingsState`,
call `_update_candidate_preview()` and `_update_comparison_view()` the required number of times
with appropriate state set, and assert on widget validity and visibility. Run these tests on the
UNFIXED code to observe failures and understand the root cause.

**Test Cases**:

1. **Terminal deletion on second preview call** (will fail on unfixed code): Call
   `_update_candidate_preview()` twice. Assert `self._terminal` is a valid Qt object and that
   `append_output("x")` appends text. On unfixed code the terminal is deleted after the second
   call and the assertion fails.

2. **Button deletion on second comparison view call** (will fail on unfixed code): Set
   `_candidate_run` to a mock `BacktestResults`, call `_update_comparison_view()` twice. Assert
   that the Accept and Reject buttons found in the layout are valid Qt objects with
   `isVisible() == True`. On unfixed code the buttons are deleted after the first call and the
   assertion fails.

3. **Terminal deletion after reject** (will fail on unfixed code): Call
   `_update_candidate_preview()` once, then simulate `_on_reject()` (which calls
   `_update_candidate_preview()` again). Assert terminal validity. On unfixed code the terminal
   is deleted.

4. **Button deletion after accept** (will fail on unfixed code): Call
   `_update_comparison_view()` once with `_candidate_run` set, then simulate `_on_accept()`
   (which calls `_update_comparison_view()` with `_candidate_run = None`), then set
   `_candidate_run` again and call `_update_comparison_view()` a third time. Assert button
   validity. On unfixed code the buttons are deleted.

**Expected Counterexamples**:
- `self._terminal` is a deleted C++ object after the second call to `_update_candidate_preview()`.
- Accept/Reject buttons are deleted C++ objects after the second call to
  `_update_comparison_view()`.
- Possible causes: clearing loop does not skip the terminal; pre-created buttons become children
  of a transient container that is deleted by the clearing loop.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed functions produce
the expected behavior.

**Pseudocode:**
```
FOR ALL callCount WHERE isBugCondition_Terminal(callCount) DO
  result := _update_candidate_preview_fixed() called callCount times
  ASSERT self._terminal is a valid Qt object
  ASSERT self._terminal.clear_output() executes without error
  ASSERT self._terminal.append_output("x") appends "x" to the display
END FOR

FOR ALL comparisonViewCallCount WHERE isBugCondition_Buttons(comparisonViewCallCount) DO
  result := _update_comparison_view_fixed() called comparisonViewCallCount times
  ASSERT accept_btn in layout is a valid Qt object AND isVisible() == True
  ASSERT reject_btn in layout is a valid Qt object AND isVisible() == True
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed functions
produce the same result as the original functions.

**Pseudocode:**
```
FOR ALL callCount WHERE NOT isBugCondition_Terminal(callCount) DO
  ASSERT _update_candidate_preview_original(callCount) = _update_candidate_preview_fixed(callCount)
END FOR

FOR ALL comparisonViewCallCount WHERE NOT isBugCondition_Buttons(comparisonViewCallCount) DO
  ASSERT _update_comparison_view_original(comparisonViewCallCount) = _update_comparison_view_fixed(comparisonViewCallCount)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain (varying diff sizes,
  metric values, history depths).
- It catches edge cases that manual unit tests might miss (empty diff, all metrics equal,
  large history stacks).
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs.

**Test Plan**: Observe behavior on UNFIXED code first for first-call rendering and terminal
streaming, then write property-based tests capturing that behavior.

**Test Cases**:

1. **First-call candidate preview preservation**: Observe that `_update_candidate_preview()`
   on the first call renders the diff table and Run Candidate Backtest button correctly on
   unfixed code, then write a test to verify this continues after the fix.

2. **Terminal streaming preservation**: Observe that `append_output(text)` appends `text`
   correctly after the first call on unfixed code, then write a property-based test that
   generates random text strings and verifies streaming works after any number of calls on
   fixed code.

3. **Comparison table preservation**: Observe that `_update_comparison_view()` on the first
   call renders delta cards and the comparison table correctly on unfixed code, then write a
   property-based test that generates random `BacktestSummary` pairs and verifies the table
   renders identically after the fix.

4. **Rollback button visibility preservation**: Verify that the Rollback button is hidden when
   `_baseline_history` is empty and visible when it is non-empty, across multiple calls.

### Unit Tests

- Test that `self._terminal` is a valid Qt object after 1, 2, 3, and 5 calls to
  `_update_candidate_preview()`.
- Test that `append_output(text)` appends `text` after each call to
  `_update_candidate_preview()`.
- Test that Accept and Reject buttons in the layout are valid and visible after 1, 2, and 3
  calls to `_update_comparison_view()` with `_candidate_run` set.
- Test that `_update_comparison_view()` with `_candidate_run = None` clears the layout without
  rendering buttons.
- Test edge case: `_update_candidate_preview()` with an empty diff (no changes applied).
- Test edge case: `_update_comparison_view()` with `_baseline_history` empty (Rollback hidden)
  and non-empty (Rollback visible).

### Property-Based Tests

- Generate random `callCount` values in range [2, 20] and verify `self._terminal` remains a
  valid Qt object after that many calls to `_update_candidate_preview()`.
- Generate random text strings and verify `append_output(text)` appends `text` to the terminal
  display after any number of calls to `_update_candidate_preview()`.
- Generate random pairs of `BacktestSummary` objects and verify that `_update_comparison_view()`
  renders the comparison table with the correct metric values and color-coding after multiple
  calls.
- Generate random `_baseline_history` lengths and verify the Rollback button visibility matches
  `len(_baseline_history) > 0` after each call to `_update_comparison_view()`.

### Integration Tests

- Full accept cycle: apply suggestion → run candidate backtest → accept → apply another
  suggestion → run second candidate backtest → verify terminal streams output and Accept/Reject
  buttons appear.
- Full reject cycle: apply suggestion → run candidate backtest → reject → apply suggestion →
  run second candidate backtest → verify terminal streams output and Accept/Reject buttons appear.
- Rollback cycle: accept twice → rollback → verify Rollback button visibility and parameter
  state are correct.
- Reset to Baseline: apply suggestion → click Reset to Baseline → apply suggestion again →
  verify terminal is still functional.
