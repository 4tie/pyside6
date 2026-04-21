# Strategy Lab Bugfix Design

## Overview

Five bugs in `loop_page.py` and `loop_service.py` were identified and partially fixed in
the previous pass. Two critical regressions were introduced during that fix: the baseline
result is immediately wiped when `_on_start()` restarts after baseline completion (causing
an infinite baseline loop), and the UI state machine does not account for the
`_baseline_in_progress` flag (leaving Start/config widgets enabled while the baseline
subprocess is running).

All fixes are surgical: change only the broken call sites. No new abstractions, no
behaviour changes outside the bug conditions.

---

## Glossary

- **Bug_Condition (C)**: The set of runtime inputs / call paths that trigger a crash or
  silent data-routing error.
- **Property (P)**: The correct observable outcome when the fixed code handles a buggy
  input — no exception, correct data written to the expected location.
- **Preservation**: All call paths that do NOT involve the bug conditions must produce
  identical results before and after the fix.
- **`_baseline_in_progress`**: Boolean flag on `LoopPage` that is `True` from the moment
  `_run_baseline_backtest()` is called until `_on_baseline_backtest_finished()` clears it.
- **Baseline-completion restart**: The call to `_on_start()` triggered by
  `QTimer.singleShot(100, self._on_start)` inside `_on_baseline_backtest_finished()`.
- **User-initiated start**: The call to `_on_start()` triggered directly by the user
  clicking the Start button (i.e., `_baseline_in_progress` is `False`).

---

## Bug Details (New — Regressions from Previous Fix Pass)

### Bug 6 — `_on_start()` unconditionally wipes `_latest_diagnosis_input` (`loop_page.py`)

**File**: `app/ui/pages/loop_page.py`  
**Method**: `_on_start` (line ~1450)

The fix for Bug 1.5 (stale session data) added `self._latest_diagnosis_input = None` as
the very first line of `_on_start()`. This correctly clears stale data when the user
clicks Start for a new session. However, `_on_baseline_backtest_finished()` also calls
`_on_start()` via `QTimer.singleShot(100, self._on_start)` after setting
`_latest_diagnosis_input` to the freshly-parsed baseline result. When `_on_start()` fires,
it immediately resets `_latest_diagnosis_input = None`, so `needs_baseline` is `True`
again, `_run_baseline_backtest()` is called again, and the cycle repeats indefinitely.

```python
# CURRENT (BUGGY) — top of _on_start()
def _on_start(self) -> None:
    self._latest_diagnosis_input = None  # wipes baseline result on restart too
    ...
    needs_baseline = self._latest_diagnosis_input is None  # always True
    if needs_baseline:
        self._run_baseline_backtest(...)  # infinite loop
```

**Formal Specification:**
```
FUNCTION isBugCondition_6(call)
  INPUT: call to _on_start
  OUTPUT: boolean

  RETURN call._latest_diagnosis_input IS NOT None   -- baseline just set
         AND call resets _latest_diagnosis_input = None unconditionally
END FUNCTION
```

**Fix**: Guard the reset with `_baseline_in_progress`. Only reset
`_latest_diagnosis_input` when this is a fresh user-initiated start (i.e.,
`_baseline_in_progress` is `False`):

```python
# AFTER
def _on_start(self) -> None:
    # Only reset stale session data on a fresh user-initiated start.
    # When called as a baseline-completion restart (_baseline_in_progress is True),
    # _latest_diagnosis_input has just been populated — do NOT wipe it.
    if not getattr(self, '_baseline_in_progress', False):
        self._latest_diagnosis_input = None
    ...
```

---

### Bug 7 — `_update_state_machine()` ignores `_baseline_in_progress` (`loop_page.py`)

**File**: `app/ui/pages/loop_page.py`  
**Method**: `_update_state_machine` (line ~990)

`_update_state_machine()` computes `is_running = self._loop_service.is_running`. During
the baseline phase, `LoopService.start()` has not yet been called, so `is_running` is
`False`. All config widgets and the Start button are therefore re-enabled while the
baseline subprocess is still running, allowing the user to click Start again and launch
a second overlapping baseline run.

```python
# CURRENT (BUGGY)
is_running = self._loop_service.is_running  # False during baseline phase
# Start button enabled, config widgets enabled while baseline subprocess runs
```

**Formal Specification:**
```
FUNCTION isBugCondition_7(state)
  INPUT: LoopPage state
  OUTPUT: boolean

  RETURN state._baseline_in_progress == True
         AND state._loop_service.is_running == False
         AND _update_state_machine treats page as NOT busy
END FUNCTION
```

**Fix**: Include `_baseline_in_progress` in the busy check:

```python
# AFTER
is_running = self._loop_service.is_running or getattr(self, '_baseline_in_progress', False)
```

---

## Bug Details (Previous Pass — Already Fixed)

### Bug 1 — `prepare_sandbox()` contract mismatch — **FIXED**
### Bug 2 — Missing `--strategy-path` / `--backtest-directory` flags — **FIXED**
### Bug 3 — Non-existent `parse_backtest_results()` method — **FIXED**
### Bug 4 — Dead duplicate code in `loop_page.py` — **FIXED**
### Bug 5 — Duplicate `run_gate_sequence()` in `loop_service.py` — **FIXED**

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- `_start_gate_backtest()` continues to pass `self._terminal.append_output` and
  `self._terminal.append_error` as subprocess callbacks — no change.
- `ImproveService.prepare_sandbox()` called from `_run_next_iteration()` continues to
  receive `(config.strategy, iteration.params_after)` — no change.
- `ImproveService.parse_candidate_run()` called from `_parse_current_gate_results()`
  continues to receive `(self._current_gate_export_dir, self._gate_run_started_at)` — no change.
- When `_on_start()` is called by the user (not as a baseline-completion restart),
  `_latest_diagnosis_input` is still reset to `None` — stale-session protection preserved.
- All gate backtest output routing, gate result recording, and loop finalization logic
  remain identical.

**Scope:**
Fixes 6 and 7 touch only two lines in `_on_start()` and one line in
`_update_state_machine()`. No other methods are modified.

---

## Correctness Properties

Property 1: Bug Condition — Baseline Completion Triggers Loop Start (Not Infinite Loop)

_For any_ call to `_on_baseline_backtest_finished()` that successfully sets
`_latest_diagnosis_input` and then calls `QTimer.singleShot(100, self._on_start)`,
the subsequent `_on_start()` call SHALL NOT reset `_latest_diagnosis_input` to `None`,
SHALL evaluate `needs_baseline = False`, and SHALL proceed to `LoopService.start()` and
`_run_next_iteration()` without calling `_run_baseline_backtest()` again.

**Validates: Requirements 2.6**

Property 2: Bug Condition — UI Busy During Baseline Phase

_For any_ state where `_baseline_in_progress` is `True`, `_update_state_machine()` SHALL
disable the Start button and all config widgets, and SHALL show the Stop button as enabled,
regardless of the value of `self._loop_service.is_running`.

**Validates: Requirements 2.7**

Property 3: Preservation — Fresh User Session Still Resets Baseline

_For any_ call to `_on_start()` where `_baseline_in_progress` is `False` (user-initiated
start), `_latest_diagnosis_input` SHALL be reset to `None` before the baseline check,
ensuring every new user session runs a fresh baseline backtest.

**Validates: Requirements 2.5, 3.1**

---

## Fix Implementation

### Fix 6 — Guard `_latest_diagnosis_input` reset in `_on_start()`

**File**: `app/ui/pages/loop_page.py`  
**Method**: `_on_start`

```python
# BEFORE (line ~1451)
def _on_start(self) -> None:
    """Validate config and kick off the first ladder iteration."""
    self._latest_diagnosis_input = None  # Reset stale state from any prior session

# AFTER
def _on_start(self) -> None:
    """Validate config and kick off the first ladder iteration."""
    # Only reset stale session data on a fresh user-initiated start.
    # When called as a baseline-completion restart (_baseline_in_progress is True),
    # _latest_diagnosis_input has just been populated — do NOT wipe it.
    if not getattr(self, '_baseline_in_progress', False):
        self._latest_diagnosis_input = None
```

---

### Fix 7 — Include `_baseline_in_progress` in `_update_state_machine()` busy check

**File**: `app/ui/pages/loop_page.py`  
**Method**: `_update_state_machine`

```python
# BEFORE (line ~993)
is_running = self._loop_service.is_running

# AFTER
is_running = self._loop_service.is_running or getattr(self, '_baseline_in_progress', False)
```

---

## Testing Strategy

### Fix Checking

**Test Cases**:

1. **Baseline-completion restart does not wipe `_latest_diagnosis_input`**: Simulate
   `_on_baseline_backtest_finished()` setting `_latest_diagnosis_input` and then calling
   `_on_start()` with `_baseline_in_progress = True`. Assert `_latest_diagnosis_input`
   is still set after the reset guard line executes.

2. **Fresh user start still resets `_latest_diagnosis_input`**: Call `_on_start()` with
   `_baseline_in_progress = False` and a non-None `_latest_diagnosis_input`. Assert
   `_latest_diagnosis_input` is `None` after the reset line.

3. **UI busy during baseline**: Set `_baseline_in_progress = True` and call
   `_update_state_machine()`. Assert Start button is disabled and Stop button is enabled.

4. **UI not busy after baseline clears**: Set `_baseline_in_progress = False` and
   `_loop_service.is_running = False`. Assert Start button is enabled (given valid config).

### Preservation Checking

1. **Gate backtest callbacks unchanged**: `_start_gate_backtest()` still passes
   `self._terminal.append_output` / `self._terminal.append_error`.

2. **Iteration flow unchanged**: `_run_next_iteration()` still calls
   `prepare_sandbox(config.strategy, iteration.params_after)`.

3. **Stale-session protection preserved**: A second user-initiated start (after a
   completed session) still resets `_latest_diagnosis_input` to `None`.
