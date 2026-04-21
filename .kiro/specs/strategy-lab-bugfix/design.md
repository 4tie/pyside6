# Strategy Lab Bugfix Design

## Overview

Five bugs in `loop_page.py` and `loop_service.py` prevent the Strategy Lab from completing
a single optimization cycle. Three bugs cause immediate `AttributeError` / `TypeError`
crashes in the baseline backtest flow; one bug silently routes Freqtrade output to the
wrong directory so the result parser always raises `FileNotFoundError`; and two dead-code
problems (duplicate helpers in `loop_page.py`, duplicate `run_gate_sequence` in
`loop_service.py`) create maintenance hazards and Python name-resolution ambiguity.

All fixes are surgical: change only the broken call sites and delete the unreachable
dead code. No new abstractions, no behaviour changes outside the bug conditions.

---

## Glossary

- **Bug_Condition (C)**: The set of runtime inputs / call paths that trigger a crash or
  silent data-routing error.
- **Property (P)**: The correct observable outcome when the fixed code handles a buggy
  input — no exception, correct data written to the expected location.
- **Preservation**: All call paths that do NOT involve the five bug conditions must
  produce identical results before and after the fix.
- **`prepare_sandbox(strategy_name, candidate_config)`**: `ImproveService` method that
  creates an isolated sandbox directory. First arg is `str`, second is `dict`.
- **`parse_candidate_run(export_dir, started_at)`**: `ImproveService` method that locates
  and parses the Freqtrade result zip from `export_dir`.
- **`_start_gate_backtest()`**: The canonical gate-backtest launcher in `LoopPage` that
  correctly passes `self._terminal.append_output` / `self._terminal.append_error` as
  subprocess callbacks and includes `--strategy-path` / `--backtest-directory` flags.
- **Stale `run_gate_sequence`**: The first definition of `run_gate_sequence` in
  `LoopService` (lines 1001–1097) that lacks hard-filter evaluation and is superseded by
  the canonical second definition (lines 1914+).
- **Dead `_build_config_panel`**: The first `_build_config_panel` method in `LoopPage`
  (lines 359–551) that is never called; `_init_ui` calls `_build_config_group` instead.

---

## Bug Details

### Bug 1 — `prepare_sandbox()` contract mismatch (`loop_page.py`)

**File**: `app/ui/pages/loop_page.py`  
**Method**: `_run_baseline_backtest` (line ~1862)

The call site passes an `AppSettings` object as the first argument and a strategy name
string as the second:

```python
# BUGGY
sandbox_dir = self._improve_service.prepare_sandbox(settings, strategy)
```

`ImproveService.prepare_sandbox(strategy_name: str, candidate_config: dict)` expects the
strategy name string first and a parameter dict second. Passing `AppSettings` as
`strategy_name` causes the method to attempt `strategies_dir / f"{settings}.py"`, which
produces a nonsensical path and raises `FileNotFoundError` or `AttributeError` immediately.

**Formal Specification:**
```
FUNCTION isBugCondition_1(call)
  INPUT: call to _run_baseline_backtest
  OUTPUT: boolean

  RETURN call.prepare_sandbox.arg0 IS AppSettings   -- wrong type
         AND call.prepare_sandbox.arg1 IS str        -- wrong position
END FUNCTION
```

**Examples:**
- `prepare_sandbox(AppSettings(...), "MyStrategy")` → `FileNotFoundError: Strategy file not found: .../AppSettings object.py`
- `prepare_sandbox("MyStrategy", {})` → sandbox created correctly ✓

---

### Bug 2 — Missing `--strategy-path` / `--backtest-directory` flags in baseline command (`loop_page.py`)

**File**: `app/ui/pages/loop_page.py`  
**Method**: `_run_baseline_backtest` (line ~1893)

The baseline `build_backtest_command` call omits `extra_flags`:

```python
# BUGGY
cmd = build_backtest_command(
    settings=settings,
    strategy_name=strategy,
    timeframe=config.timeframe,
    timerange=in_sample_timerange,
    pairs=list(config.pairs) if config.pairs else None,
    # extra_flags absent
)
```

Without `--backtest-directory str(export_dir)`, Freqtrade writes its result zip to its
default location (`user_data/backtest_results/`), not to `sandbox_dir / "baseline_export"`.
When `_on_baseline_backtest_finished` then calls `parse_candidate_run(export_dir, ...)`,
the `baseline_export` directory is empty and `FileNotFoundError` is raised.

Without `--strategy-path str(sandbox_dir)`, Freqtrade cannot find the strategy file
copied into the sandbox, so the subprocess itself exits non-zero.

**Formal Specification:**
```
FUNCTION isBugCondition_2(cmd)
  INPUT: BacktestRunCommand built for baseline
  OUTPUT: boolean

  RETURN "--backtest-directory" NOT IN cmd.as_list()
         OR "--strategy-path" NOT IN cmd.as_list()
END FUNCTION
```

**Examples:**
- Baseline command without flags → Freqtrade writes zip to default dir → parser finds empty `baseline_export` → `FileNotFoundError`
- Baseline command with `--strategy-path sandbox_dir --backtest-directory export_dir` → zip written to `export_dir` → parser succeeds ✓

---

### Bug 3 — Non-existent `parse_backtest_results()` method (`loop_page.py`)

**File**: `app/ui/pages/loop_page.py`  
**Method**: `_on_baseline_backtest_finished` (line ~1930)

```python
# BUGGY
results = self._improve_service.parse_backtest_results(export_dir)
```

`ImproveService` has no `parse_backtest_results` method. The correct method is
`parse_candidate_run(export_dir: Path, started_at: float = 0.0)`. The call also omits
the `started_at` timestamp, which is needed for the legacy mtime fallback.

**Formal Specification:**
```
FUNCTION isBugCondition_3(call)
  INPUT: call in _on_baseline_backtest_finished
  OUTPUT: boolean

  RETURN call.method_name == "parse_backtest_results"
         AND "parse_backtest_results" NOT IN dir(ImproveService)
END FUNCTION
```

**Examples:**
- `self._improve_service.parse_backtest_results(export_dir)` → `AttributeError: 'ImproveService' object has no attribute 'parse_backtest_results'`
- `self._improve_service.parse_candidate_run(export_dir, self._baseline_run_started_at)` → returns `BacktestResults` ✓

---

### Bug 4 — Dead duplicate code in `loop_page.py`

**File**: `app/ui/pages/loop_page.py`

Two categories of dead code exist:

**4a — Unreachable `_build_config_panel` (lines 359–551)**  
`_init_ui` calls `self._build_config_group()` (line 316). `_build_config_panel` is never
called anywhere. It instantiates the same widget attributes (`_strategy_combo`,
`_max_iter_spin`, etc.) as `_build_config_group`, so if it were ever accidentally called
it would silently overwrite the live widgets. It also references `self._timerange_edit`
without the `_date_from_edit` / `_date_to_edit` fields that `_build_config_group` adds,
making it incompatible with the canonical `_restore_preferences` / `_save_preferences`.

**4b — Duplicate helper methods (lines 714–822)**  
The following methods appear twice in `LoopPage`:

| Method | Old (stale) location | Canonical location |
|--------|---------------------|--------------------|
| `_restore_preferences` | lines 714–752 | lines 1352–1410 |
| `_save_preferences` | lines 753–792 | lines 1411–1445 |
| `_on_timerange_preset` | lines 793–800 | lines 1446–1462 |
| `_on_iteration_mode_changed` | lines 822–823 | lines 1463–1468 |
| `_update_stat_cards` | lines 943–964 | lines 1478–1504 |
| `_clear_history_ui` | lines 911–924 | lines 1570–1585 |

Python resolves method names to the **last** definition in the class body, so the stale
definitions at lines 714–964 are silently shadowed. They are dead code that creates
confusion and risks accidental reactivation during future edits.

**Formal Specification:**
```
FUNCTION isBugCondition_4(class_body)
  INPUT: LoopPage class body
  OUTPUT: boolean

  RETURN "_build_config_panel" IN class_body.methods
         AND "_build_config_panel" NOT IN callers(class_body)
         OR count(method_name, class_body) > 1 FOR method_name IN duplicate_list
END FUNCTION
```

---

### Bug 5 — Duplicate `run_gate_sequence()` in `loop_service.py`

**File**: `app/core/services/loop_service.py`

`LoopService` contains two definitions of `run_gate_sequence`:

| Definition | Lines | Status |
|-----------|-------|--------|
| First (stale) | 1001–1097 | Missing hard-filter evaluation; uses `GateResult(gate_name=..., passed=True, metrics=...)` constructor directly; does not call `build_in_sample_gate_result`; does not call `_mark_gate_failure` or `_mark_hard_filter_rejection` |
| Second (canonical) | 1914–end | Calls `build_in_sample_gate_result`, `evaluate_gate1_hard_filters`, `_mark_hard_filter_rejection`, `_mark_gate_failure`, `evaluate_post_gate_hard_filters`; sets `iteration.status = "success"` on pass |

Python resolves `self.run_gate_sequence(...)` to the **last** definition (canonical), so
the stale definition at lines 1001–1097 is dead. However, it occupies ~97 lines between
`record_iteration_error` and `_build_hyperopt_command`, making the file harder to read
and risking accidental edits to the wrong copy.

**Formal Specification:**
```
FUNCTION isBugCondition_5(class_body)
  INPUT: LoopService class body
  OUTPUT: boolean

  RETURN count("run_gate_sequence", class_body.methods) == 2
END FUNCTION
```

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
- The canonical `run_gate_sequence` (lines 1914+) is not modified in any way.
- All gate backtest output routing, gate result recording, and loop finalization logic
  remain identical.
- `_build_config_group()` and all widgets it creates are untouched.
- The canonical `_restore_preferences`, `_save_preferences`, `_on_timerange_preset`,
  `_on_iteration_mode_changed`, `_update_stat_cards`, and `_clear_history_ui`
  implementations (the later definitions) are untouched.

**Scope:**
All call paths that do NOT involve `_run_baseline_backtest` or
`_on_baseline_backtest_finished` are completely unaffected by fixes 1–3. Fixes 4 and 5
are pure deletions of unreachable code; they cannot change runtime behaviour.

---

## Hypothesized Root Cause

1. **Copy-paste from gate flow without adapting the API** (Bugs 1, 2, 3): The baseline
   backtest was added by copying the structure of `_start_gate_backtest` but the author
   used the old `prepare_sandbox(settings, strategy)` signature (from an earlier version
   of `ImproveService`), forgot to add `extra_flags` to `build_backtest_command`, and
   referenced a method name (`parse_backtest_results`) that was either renamed or never
   existed in the current `ImproveService`.

2. **Incremental refactoring left stale copies** (Bugs 4, 5): `_build_config_group` was
   written as a replacement for `_build_config_panel` but the old method was not deleted.
   Similarly, `run_gate_sequence` was rewritten with hard-filter support but the original
   definition was not removed. Python's last-definition-wins semantics masked both issues
   at runtime.

---

## Correctness Properties

Property 1: Bug Condition — Baseline Backtest Completes Without Crash

_For any_ call to `_on_start()` where `_latest_diagnosis_input is None` (baseline needed),
the fixed `_run_baseline_backtest` SHALL call `prepare_sandbox(strategy, {})` with correct
argument types, build a backtest command that includes `--strategy-path` and
`--backtest-directory` flags pointing to the sandbox and export directories respectively,
route subprocess output to `self._terminal.append_output` / `self._terminal.append_error`,
and upon successful completion call `parse_candidate_run(export_dir, started_at)` to
obtain a `BacktestResults` object without raising any exception.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Preservation — Gate Backtests and Non-Baseline Paths Unchanged

_For any_ call path that does NOT involve `_run_baseline_backtest` or
`_on_baseline_backtest_finished` (i.e., gate backtests, loop finalization, apply/discard/
rollback, preferences persistence), the fixed code SHALL produce exactly the same
observable behaviour as the original code, with no change to subprocess callbacks,
export directory routing, result parsing, or UI state transitions.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

---

## Fix Implementation

### Fix 1 — Correct `prepare_sandbox()` call in `_run_baseline_backtest`

**File**: `app/ui/pages/loop_page.py`  
**Method**: `_run_baseline_backtest`

**Change**: Replace the two-argument call with the correct signature.

```python
# BEFORE (line ~1862)
sandbox_dir = self._improve_service.prepare_sandbox(settings, strategy)

# AFTER
sandbox_dir = self._improve_service.prepare_sandbox(strategy, {})
```

`strategy` is already the strategy name string (passed as the `strategy` parameter of
`_run_baseline_backtest`). An empty dict `{}` is the correct `candidate_config` for a
baseline run — it tells `prepare_sandbox` to copy the strategy `.py` file and write a
minimal params file, preserving the strategy's current unmodified parameters.

---

### Fix 2 — Add `--strategy-path` and `--backtest-directory` to baseline command

**File**: `app/ui/pages/loop_page.py`  
**Method**: `_run_baseline_backtest`

**Change**: Build `extra_flags` before calling `build_backtest_command` and pass them in,
mirroring the pattern in `_start_gate_backtest`.

```python
# BEFORE (line ~1893)
cmd = build_backtest_command(
    settings=settings,
    strategy_name=strategy,
    timeframe=config.timeframe,
    timerange=in_sample_timerange,
    pairs=list(config.pairs) if config.pairs else None,
)

# AFTER
extra_flags = [
    "--strategy-path", str(sandbox_dir),
    "--backtest-directory", str(export_dir),
]
cmd = build_backtest_command(
    settings=settings,
    strategy_name=strategy,
    timeframe=config.timeframe,
    timerange=in_sample_timerange,
    pairs=list(config.pairs) if config.pairs else None,
    extra_flags=extra_flags,
)
```

`sandbox_dir` is already computed earlier in the same method (after Fix 1).
`export_dir` is already computed as `sandbox_dir / "baseline_export"` earlier in the
same method.

---

### Fix 3 — Replace `parse_backtest_results()` with `parse_candidate_run()` and record `started_at`

**File**: `app/ui/pages/loop_page.py`  
**Methods**: `_run_baseline_backtest` and `_on_baseline_backtest_finished`

**Change 3a** — Record the start timestamp just before `execute_command` in
`_run_baseline_backtest`:

```python
# Add immediately before self._process_service.execute_command(...)
self._baseline_run_started_at = time.time()
self._process_service.execute_command(
    cmd.as_list(),
    on_output=self._terminal.append_output,
    on_error=self._terminal.append_error,
    on_finished=self._on_baseline_backtest_finished,
    working_directory=cmd.cwd,
)
```

`_baseline_run_started_at` must also be initialised to `0.0` in
`_reset_iteration_runtime()` (or `_ensure_loop_runtime_state()`) alongside the other
`_*_started_at` fields.

**Change 3b** — Fix the parse call in `_on_baseline_backtest_finished`:

```python
# BEFORE (line ~1930)
results = self._improve_service.parse_backtest_results(export_dir)

# AFTER
results = self._improve_service.parse_candidate_run(
    export_dir, self._baseline_run_started_at
)
```

**Change 3c** — Fix the subprocess output callbacks in `_run_baseline_backtest`
(currently `self._on_process_stdout` / `self._on_process_stderr`, which do not exist):

```python
# BEFORE
on_output=self._on_process_stdout,
on_error=self._on_process_stderr,

# AFTER
on_output=self._terminal.append_output,
on_error=self._terminal.append_error,
```

This matches the pattern used by `_start_gate_backtest` and satisfies requirement 2.1.

---

### Fix 4 — Delete dead duplicate code in `loop_page.py`

**File**: `app/ui/pages/loop_page.py`

**4a** — Delete the entire `_build_config_panel` method body (lines 359–551).
The method signature line and all its content through the final `return group` and
closing of the method should be removed. `_init_ui` already calls `_build_config_group`;
`_build_config_panel` has zero callers.

**4b** — Delete the stale first definitions of the following methods (the earlier
occurrences in the file, which are shadowed by the later canonical ones):

| Method to delete | Approximate line range |
|-----------------|----------------------|
| `_restore_preferences` (old) | 714–752 |
| `_save_preferences` (old) | 753–792 |
| `_on_timerange_preset` (old) | 793–800 |
| `_on_select_pairs` | 802–818 (only one copy, keep it) |
| `_on_validation_mode_changed` | 819–820 (only one copy, keep it) |
| `_on_iteration_mode_changed` (old) | 822–823 |
| `_update_stat_cards` (old) | 943–964 |
| `_clear_history_ui` (old) | 911–924 |

> **Note**: `_on_select_pairs` and `_on_validation_mode_changed` appear only once — do
> not delete them. Only delete the methods that have a later canonical duplicate.

After deletion, verify that the remaining canonical definitions (at lines 1352+) are
intact and that `_init_ui` / `showEvent` / `_check_config_guard` still reference the
correct method names.

---

### Fix 5 — Delete stale `run_gate_sequence` in `loop_service.py`

**File**: `app/core/services/loop_service.py`

**Change**: Delete the first `run_gate_sequence` definition (lines 1001–1097), which
spans from `def run_gate_sequence(` through the final `return True` and blank lines
before `def _build_hyperopt_command(`.

The canonical second definition (lines 1914+) is the one Python resolves at runtime and
must be kept unchanged.

After deletion, confirm that `_build_hyperopt_command` immediately follows
`record_iteration_error` in the file, and that the canonical `run_gate_sequence` at the
bottom of the class is untouched.

---

## Testing Strategy

### Validation Approach

Two-phase approach: first run exploratory tests against the **unfixed** code to confirm
the crash paths and understand root causes; then run fix-checking and preservation tests
against the **fixed** code.

---

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each crash before the fix is applied.
Confirm or refute the root cause analysis.

**Test Plan**: Write unit tests that call `_run_baseline_backtest` (or its sub-calls)
with a mocked `ImproveService` and `ProcessService`, then assert that the expected
exceptions are raised on unfixed code.

**Test Cases**:

1. **prepare_sandbox type error** (Bug 1): Call `prepare_sandbox(AppSettings(...), "Strat")`
   directly — expect `FileNotFoundError` or `AttributeError` on unfixed code.

2. **Missing export flags** (Bug 2): Capture the command list produced by
   `build_backtest_command` without `extra_flags` — assert `"--backtest-directory"` is
   absent on unfixed code.

3. **parse_backtest_results AttributeError** (Bug 3): Call
   `improve_service.parse_backtest_results(some_dir)` — expect `AttributeError` on
   unfixed code.

4. **Missing on_output callbacks** (Bug 3c): Inspect the `execute_command` call kwargs
   — assert `on_output` is `self._on_process_stdout` (non-existent) on unfixed code.

5. **Duplicate method resolution** (Bugs 4, 5): Use `inspect.getsourcelines` to confirm
   that Python resolves `LoopPage._restore_preferences` to the later definition and
   `LoopService.run_gate_sequence` to the later definition on unfixed code — confirming
   the earlier copies are dead.

**Expected Counterexamples**:
- `TypeError: prepare_sandbox() argument 1 must be str, not AppSettings`
- `FileNotFoundError: Strategy file not found: .../AppSettings object.py`
- `AttributeError: 'ImproveService' object has no attribute 'parse_backtest_results'`
- `AttributeError: 'LoopPage' object has no attribute '_on_process_stdout'`

---

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed code
produces the expected correct behaviour.

**Pseudocode:**
```
FOR ALL call WHERE isBugCondition(call) DO
  result := fixed_code(call)
  ASSERT expectedBehavior(result)   -- no exception, correct data routing
END FOR
```

**Test Cases**:

1. **prepare_sandbox called correctly**: Mock `ImproveService.prepare_sandbox` and assert
   it is called with `(strategy_name: str, {})` — first arg is a string, second is an
   empty dict.

2. **Baseline command includes export flags**: After Fix 2, capture `cmd.as_list()` and
   assert `"--strategy-path"` and `"--backtest-directory"` are present, and that the
   `--backtest-directory` value equals `str(sandbox_dir / "baseline_export")`.

3. **parse_candidate_run called correctly**: Mock `ImproveService.parse_candidate_run`
   and assert it is called with `(export_dir, started_at)` where `started_at` is a
   positive float.

4. **Terminal callbacks used**: Assert `execute_command` is called with
   `on_output=terminal.append_output` and `on_error=terminal.append_error`.

5. **No duplicate methods**: After Fix 4, assert `LoopPage` has exactly one definition
   of each previously-duplicated method name (use `inspect` or count occurrences in
   source).

6. **No duplicate run_gate_sequence**: After Fix 5, assert `LoopService` has exactly one
   `run_gate_sequence` and that it calls `build_in_sample_gate_result` (canonical
   behaviour).

---

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed
code produces the same result as the original code.

**Pseudocode:**
```
FOR ALL call WHERE NOT isBugCondition(call) DO
  ASSERT original_code(call) == fixed_code(call)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking
because it generates many random gate configurations and iteration states automatically,
catching edge cases that manual tests miss.

**Test Cases**:

1. **Gate backtest callbacks unchanged**: Verify `_start_gate_backtest` still passes
   `self._terminal.append_output` / `self._terminal.append_error` — no change from fix.

2. **prepare_sandbox from _run_next_iteration unchanged**: Verify the call in
   `_run_next_iteration` still passes `(config.strategy, iteration.params_after)`.

3. **parse_candidate_run from _parse_current_gate_results unchanged**: Verify the call
   still passes `(self._current_gate_export_dir, self._gate_run_started_at)`.

4. **Canonical run_gate_sequence behaviour preserved**: Run the canonical
   `run_gate_sequence` with a mock `run_backtest_fn` and assert it still evaluates
   hard filters and calls `_mark_hard_filter_rejection` on filter failures.

5. **Preferences round-trip preserved**: Call the canonical `_restore_preferences` and
   `_save_preferences` and assert they read/write the same fields as before.

---

### Unit Tests

- Test `_run_baseline_backtest` with mocked services: assert correct `prepare_sandbox`
  args, correct `extra_flags` in command, correct `execute_command` callbacks.
- Test `_on_baseline_backtest_finished` with a mocked `parse_candidate_run`: assert it
  is called with `(export_dir, baseline_run_started_at)` and that `_latest_diagnosis_input`
  is populated on success.
- Test `_on_baseline_backtest_finished` with `exit_code != 0`: assert no parse call is
  made and `_baseline_in_progress` is reset to `False`.
- Test that `LoopPage` has no `_build_config_panel` method after Fix 4a.
- Test that `LoopService.run_gate_sequence` calls `build_in_sample_gate_result` (not the
  stale direct `GateResult(...)` construction) after Fix 5.

### Property-Based Tests

- Generate random `(strategy_name: str, candidate_config: dict)` pairs and verify
  `prepare_sandbox` always receives a `str` as the first argument from the fixed
  `_run_baseline_backtest`.
- Generate random `LoopConfig` instances and verify the baseline command always contains
  `--backtest-directory` and `--strategy-path` flags after the fix.
- Generate random gate sequences and verify `run_gate_sequence` (canonical) produces
  consistent `iteration.status` and `iteration.validation_gate_passed` values before and
  after Fix 5 (since Fix 5 is a deletion of dead code, behaviour must be identical).

### Integration Tests

- Full baseline → loop start flow: start `LoopPage` with no prior `_latest_diagnosis_input`,
  mock the subprocess to exit 0 and write a valid zip to `baseline_export`, assert the
  loop proceeds to iteration 1 without any exception.
- Gate flow unaffected: run a full gate sequence (in-sample → OOS) with mocked subprocess
  and assert output is routed to the terminal widget, not to any non-existent callback.
- Session reset: start a second loop session after a completed first session and assert
  `_latest_diagnosis_input` is `None` at the start of `_on_start` (requirement 2.5 /
  bug 1.5 from the requirements doc).
