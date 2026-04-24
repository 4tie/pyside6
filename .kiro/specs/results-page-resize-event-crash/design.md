# Results Page Resize Event Crash — Bugfix Design

## Overview

The `_reflow` closure inside `ResultsPage._build_pairs_widget` crashes with an
`AttributeError` whenever the pairs-badge container widget is resized. The broken
line used `super(type(container), container).resizeEvent(event)` to forward the
resize event to the base class. Because `container` is a plain `QWidget` instance
(not an instance of a subclass), `type(container)` is `QWidget` itself, so
`super(QWidget, container)` resolves to `QObject` — which has no `resizeEvent`
method — causing the crash.

The fix replaces that call with the direct unbound-method form
`QWidget.resizeEvent(container, event)`, which always resolves to the correct
base-class implementation regardless of the runtime type of `container`.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the crash — `_reflow` is
  called with a non-`None` `QResizeEvent` argument while `container` is a plain
  `QWidget` instance (not a subclass).
- **Property (P)**: The desired behavior when the bug condition holds — the resize
  event is forwarded to `QWidget.resizeEvent` without raising any exception, and
  badge labels are subsequently reflowed.
- **Preservation**: All behavior that must remain unchanged — initial layout pass
  (`event=None`), empty-pairs path, and the badge reflow geometry logic itself.
- **`_reflow`**: The closure defined inside `_build_pairs_widget` that both
  forwards the resize event and repositions badge labels in a flow-wrap pattern.
- **`container`**: The plain `QWidget` instance created inside
  `_build_pairs_widget` whose `resizeEvent` slot is monkey-patched to `_reflow`.
- **`super(type(container), container)`**: The broken super-proxy. When
  `type(container) is QWidget`, this resolves to `QObject`, which lacks
  `resizeEvent`.
- **`QWidget.resizeEvent(container, event)`**: The fixed unbound-method call.
  Explicitly names `QWidget` as the class, so MRO resolution is bypassed and the
  correct implementation is always called.

## Bug Details

### Bug Condition

The bug manifests when `_reflow` is invoked with a non-`None` `QResizeEvent`
(i.e., when Qt delivers a resize event to the container widget). The closure
attempts to forward the event to the parent class via
`super(type(container), container).resizeEvent(event)`. Because `container` is a
plain `QWidget` — not a subclass — `type(container)` is `QWidget`, and
`super(QWidget, container)` yields a proxy for `QObject`. `QObject` does not
define `resizeEvent`, so Python raises `AttributeError: 'super' object has no
attribute 'resizeEvent'`.

**Formal Specification:**

```
FUNCTION isBugCondition(container, event)
  INPUT: container — a QWidget instance
         event    — the argument passed to _reflow (QResizeEvent or None)
  OUTPUT: boolean

  RETURN event IS NOT None
         AND type(container) IS QWidget   -- not a subclass
         -- equivalently: super(type(container), container) resolves to QObject
END FUNCTION
```

### Examples

- **Resize while pairs are displayed**: User resizes the Results Browser window
  while a run with pairs is selected. Qt fires a `QResizeEvent` on `container`.
  `_reflow(event)` is called, hits `super(type(container), container).resizeEvent(event)`,
  and raises `AttributeError`. **Expected**: event forwarded cleanly, badges
  reflowed.
- **Initial layout pass** (`event=None`): `_reflow()` is called immediately after
  construction. The `if event is not None` guard is `False`, so the broken line is
  never reached. **No crash** — this path is unaffected.
- **Empty pairs list**: `_build_pairs_widget([])` returns a plain `QLabel("—")`
  and never creates `container` or `_reflow`. **No crash** — this path is
  unaffected.
- **Subclass scenario** (hypothetical): If `container` were an instance of a
  `QWidget` subclass `MyWidget`, `super(MyWidget, container)` would resolve to
  `QWidget`, which *does* have `resizeEvent`. The bug would not manifest — but
  this is not the actual code path.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**

- `_reflow(event=None)` (initial layout pass) SHALL continue to position all
  badge labels in a flow-wrap pattern without calling any resize-event forwarding.
- When the pairs list is empty, `_build_pairs_widget` SHALL continue to return a
  plain `QLabel("—")` without constructing a container or `_reflow` closure.
- When the container is resized, badge labels SHALL continue to be repositioned to
  fit within the container width, wrapping to new rows as needed.
- The container's minimum height SHALL continue to be updated after each reflow to
  reflect the total height of all badge rows.

**Scope:**

All inputs that do NOT involve a non-`None` resize event being delivered to a
plain `QWidget` container are completely unaffected by this fix. This includes:

- The initial `_reflow()` call with `event=None`
- Mouse interaction with the Results Browser (run selection, tab switching)
- All other pages and widgets in the application

## Hypothesized Root Cause

The root cause is a misuse of `super()` with a dynamically-resolved type on a
non-subclassed instance:

1. **`super()` MRO resolution on a plain `QWidget`**: `super(type(container), container)`
   is intended to call the parent class's `resizeEvent`. When `container` is a
   plain `QWidget`, `type(container)` is `QWidget`, so `super(QWidget, container)`
   walks up the MRO to `QObject`. `QObject` does not expose `resizeEvent` in its
   Python binding, causing the `AttributeError`.

2. **Monkey-patching instead of subclassing**: The code assigns `_reflow` directly
   to `container.resizeEvent` rather than creating a `QWidget` subclass that
   overrides `resizeEvent`. Inside a monkey-patched function, `super()` has no
   implicit `__class__` cell (it is not defined inside a class body), so the
   two-argument form `super(type(container), container)` was used as a workaround
   — but it resolves incorrectly for plain instances.

3. **Correct fix — direct unbound call**: `QWidget.resizeEvent(container, event)`
   bypasses MRO entirely and calls the known correct implementation directly. This
   is the standard pattern for forwarding events in monkey-patched Qt handlers.

## Correctness Properties

Property 1: Bug Condition — Resize Event Forwarded Without Exception

_For any_ `QResizeEvent` delivered to the pairs-badge container widget (i.e.,
`isBugCondition(container, event)` is `True`), the fixed `_reflow` closure SHALL
call `QWidget.resizeEvent(container, event)` successfully without raising any
exception, and SHALL then reposition all badge labels in the flow-wrap layout.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation — Non-Resize-Event Paths Unchanged

_For any_ invocation of `_reflow` where `event is None` (initial layout pass),
the fixed closure SHALL produce exactly the same badge positioning and container
minimum-height result as the original closure, with no call to any resize-event
forwarding method.

**Validates: Requirements 3.1, 3.2, 3.3**

## Fix Implementation

### Changes Required

**File**: `app/ui/pages/results_page.py`

**Function**: `_reflow` closure inside `ResultsPage._build_pairs_widget`

**Specific Changes:**

1. **Replace broken super-proxy call with direct unbound-method call**:

   Before (broken):
   ```python
   if event is not None:
       super(type(container), container).resizeEvent(event)
   ```

   After (fixed):
   ```python
   if event is not None:
       QWidget.resizeEvent(container, event)
   ```

2. **No other changes required**: The reflow geometry logic, the
   `container.resizeEvent = _reflow` assignment, the initial `_reflow()` call,
   and the empty-pairs guard are all correct and must not be modified.

### Why This Fix Is Correct

`QWidget.resizeEvent` is an unbound method. Calling it as
`QWidget.resizeEvent(container, event)` is equivalent to
`container.__class__.__mro__[<QWidget index>].resizeEvent(container, event)` but
without the fragility of dynamic MRO lookup. It always resolves to `QWidget`'s
implementation, which is the intended base-class call regardless of what
`type(container)` happens to be at runtime.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples
that demonstrate the crash on the unfixed code, then verify the fix works
correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the `AttributeError` crash
BEFORE the fix is applied. Confirm the root cause analysis.

**Test Plan**: Construct a minimal `_reflow`-style closure that uses the broken
`super(type(container), container).resizeEvent(event)` pattern, fire a synthetic
resize event at it, and assert that `AttributeError` is raised. This confirms the
root cause without requiring a full Qt application.

**Test Cases:**

1. **Plain QWidget resize — broken pattern** (will raise `AttributeError` on
   unfixed code): Create a plain `QWidget` container, assign a `_reflow`-style
   closure using the broken super call, and invoke it with a mock `QResizeEvent`.
   Assert `AttributeError` is raised.
2. **Plain QWidget resize — fixed pattern** (must NOT raise on fixed code):
   Same setup but using `QWidget.resizeEvent(container, event)`. Assert no
   exception is raised.
3. **`event=None` path — both patterns** (must never raise): Invoke `_reflow()`
   with `event=None` using both the broken and fixed patterns. Assert no exception
   is raised in either case (the guard prevents the broken line from executing).

**Expected Counterexamples:**

- `AttributeError: 'super' object has no attribute 'resizeEvent'` when the broken
  pattern is used with a plain `QWidget` instance and a non-`None` event.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed
`_reflow` closure produces the expected behavior (no exception, badges reflowed).

**Pseudocode:**

```
FOR ALL (container, event) WHERE isBugCondition(container, event) DO
  result := _reflow_fixed(event)
  ASSERT no AttributeError raised
  ASSERT all badges have been repositioned (geometry updated)
  ASSERT container.minimumHeight() >= 28
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the
fixed `_reflow` produces the same result as the original.

**Pseudocode:**

```
FOR ALL (container, event) WHERE NOT isBugCondition(container, event) DO
  ASSERT _reflow_original(event) produces same badge layout as _reflow_fixed(event)
END FOR
```

**Testing Approach**: Property-based testing is well-suited here because:

- The reflow geometry depends on container width, badge sizes, and the number of
  pairs — a large combinatorial space.
- Hypothesis can generate many `(pairs_list, container_width)` combinations and
  verify that badge positions are identical between the original and fixed closures
  for the `event=None` path (which is unaffected by the fix).
- It catches any accidental regression in the geometry logic.

**Test Cases:**

1. **`event=None` reflow preservation**: For many randomly-generated pairs lists
   and container widths, assert that badge `geometry()` values produced by the
   fixed closure match those produced by the original closure.
2. **Empty pairs preservation**: Assert that `_build_pairs_widget([])` continues
   to return a `QLabel` with text `"—"` and no container is created.
3. **Minimum height preservation**: For any non-empty pairs list, assert that
   `container.minimumHeight()` is at least 28 after `_reflow()`.

### Unit Tests

- Test that `_reflow(event=<QResizeEvent>)` does not raise when using the fixed
  call on a plain `QWidget` container.
- Test that `_reflow(event=None)` positions badges correctly for a single pair,
  multiple pairs that fit on one row, and multiple pairs that wrap to a second row.
- Test that `_build_pairs_widget([])` returns a `QLabel` with text `"—"`.
- Test that `container.minimumHeight()` is updated correctly after reflow.

### Property-Based Tests

- Generate random lists of pair strings (1–20 pairs, each 3–12 characters) and
  random container widths (100–1200 px). For each, verify that all badges are
  positioned within `[0, container_width]` horizontally after `_reflow(None)`.
- Generate random pairs lists and verify that no two badges overlap after reflow.
- Verify that `container.minimumHeight()` equals the total height of all badge
  rows plus spacing for any generated input.

### Integration Tests

- Load the Results Browser with a run that has a non-empty pairs list. Resize the
  main window and assert no exception is raised and badges remain visible.
- Switch between runs with different numbers of pairs while resizing; assert
  stable layout throughout.
