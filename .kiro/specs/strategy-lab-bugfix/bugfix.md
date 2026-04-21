# Bugfix Requirements Document

## Introduction

The Strategy Lab feature (loop_page.py / loop_service.py) contains bugs that prevent the
baseline backtest flow from completing and the loop from ever reaching iteration 1. The
original five bugs (1.1–1.5) have been partially addressed, but two critical regressions
were introduced during that fix pass (1.6–1.7). Together the remaining bugs mean the
baseline flow still cannot complete end-to-end: the baseline runs but its result is
immediately discarded, and the UI does not correctly reflect the busy state while the
baseline subprocess is running.

---

## Bug Analysis

### Current Behavior (Defect)

> **Bugs 1.1–1.5 are fixed.** The items below document the two new regressions
> introduced during that fix pass.

1.1 ~~WHEN `_run_baseline_backtest()` is called and the baseline subprocess starts~~
    ~~THEN the system crashes with `AttributeError: 'LoopPage' object has no attribute~~
    ~~'_on_process_stdout'`~~ **FIXED**

1.2 ~~WHEN `_run_baseline_backtest()` calls `self._improve_service.prepare_sandbox()`~~
    ~~THEN the system crashes with `TypeError`~~ **FIXED**

1.3 ~~WHEN `_on_baseline_backtest_finished()` tries to parse the results~~
    ~~THEN the system crashes with `AttributeError: 'ImproveService' object has no attribute~~
    ~~'parse_backtest_results'`~~ **FIXED**

1.4 ~~WHEN `_run_baseline_backtest()` builds the backtest command~~
    ~~THEN the system does not pass `--backtest-directory` in `extra_flags`~~ **FIXED**

1.5 ~~WHEN the user starts a new Strategy Lab run after a previous session~~
    ~~THEN `_latest_diagnosis_input` still holds stale data~~ **FIXED** (but see 1.6 below)

1.6 WHEN the baseline backtest completes successfully and
    `_on_baseline_backtest_finished()` sets `self._latest_diagnosis_input` and then
    calls `QTimer.singleShot(100, self._on_start)` to restart the loop
    THEN `_on_start()` immediately executes `self._latest_diagnosis_input = None` at
    its very first line, wiping the just-populated baseline data. The baseline check
    (`needs_baseline = self._latest_diagnosis_input is None`) evaluates to `True`
    again, `_run_baseline_backtest()` is called a second time, and the cycle repeats
    indefinitely — the loop never advances to iteration 1.

    Root cause: the unconditional reset `self._latest_diagnosis_input = None` at the
    top of `_on_start()` was intended to clear stale data from a *previous user
    session*, but it also fires when `_on_start()` is called as a *baseline-completion
    restart*, destroying the freshly-set baseline result.

1.7 WHEN the baseline backtest subprocess is running (between the
    `ProcessService.execute_command()` call and the `_on_baseline_backtest_finished`
    callback)
    THEN `_update_state_machine()` evaluates `is_running = self._loop_service.is_running`,
    which returns `False` because `LoopService.start()` has not yet been called.
    As a result, the Start button and all config widgets are re-enabled while the
    baseline subprocess is still active, allowing the user to click Start again and
    launch a second overlapping baseline run.

    Root cause: `_update_state_machine()` only checks `self._loop_service.is_running`
    and does not account for the `_baseline_in_progress` flag that guards the
    baseline subprocess phase.

---

### Expected Behavior (Correct)

2.1 WHEN `_run_baseline_backtest()` is called
    THEN the system SHALL route baseline subprocess output to the terminal widget by
    passing `self._terminal.append_output` as `on_output` and
    `self._terminal.append_error` as `on_error` to `ProcessService.execute_command()`.
    **[Already correct in current code — preserve as-is.]**

2.2 WHEN `_run_baseline_backtest()` calls `prepare_sandbox()`
    THEN the system SHALL call `self._improve_service.prepare_sandbox(strategy, {})`
    with the strategy name as the first argument and an empty dict as the candidate
    config. **[Already correct in current code — preserve as-is.]**

2.3 WHEN `_on_baseline_backtest_finished()` parses the baseline results
    THEN the system SHALL call `self._improve_service.parse_candidate_run(export_dir,
    self._baseline_run_started_at)`. **[Already correct in current code — preserve as-is.]**

2.4 WHEN `_run_baseline_backtest()` builds the backtest command
    THEN the system SHALL include `"--backtest-directory", str(export_dir)` and
    `"--strategy-path", str(sandbox_dir)` in `extra_flags`.
    **[Already correct in current code — preserve as-is.]**

2.5 WHEN the user clicks "Start Loop" to begin a **new user-initiated** Strategy Lab
    session (i.e., `_baseline_in_progress` is `False` at the time `_on_start()` is
    called)
    THEN the system SHALL reset `_latest_diagnosis_input` to `None`, so every fresh
    user session always runs a new baseline backtest.

2.6 WHEN `_on_start()` is called as a **baseline-completion restart** (i.e.,
    `_baseline_in_progress` is `True` at the time `_on_start()` is called, meaning
    the baseline just finished and set `_latest_diagnosis_input`)
    THEN the system SHALL NOT reset `_latest_diagnosis_input` to `None`, so the
    freshly-populated baseline data is preserved and `needs_baseline` evaluates to
    `False`, allowing the loop to proceed to iteration 1.

2.7 WHEN the baseline backtest subprocess is running (i.e., `_baseline_in_progress`
    is `True`)
    THEN `_update_state_machine()` SHALL treat the page as busy: the Start button and
    all config widgets SHALL be disabled, and the Stop button SHALL be visible and
    enabled, exactly as they are when `self._loop_service.is_running` is `True`.

---

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a Strategy Lab iteration is not the first iteration and
    `_latest_diagnosis_input` has been populated by a completed gate
    THEN the system SHALL CONTINUE TO use the stored `_latest_diagnosis_input` as the
    mutation seed without running an additional baseline backtest.

3.2 WHEN `_start_gate_backtest()` runs any gate (in-sample, OOS, walk-forward, stress)
    THEN the system SHALL CONTINUE TO route subprocess output to
    `self._terminal.append_output` and `self._terminal.append_error` exactly as before,
    with no change to the gate backtest output handling.

3.3 WHEN `ImproveService.prepare_sandbox()` is called from `_run_next_iteration()`
    for a regular iteration
    THEN the system SHALL CONTINUE TO receive `(config.strategy, iteration.params_after)`
    as arguments, with no change to the regular iteration sandbox creation.

3.4 WHEN `ImproveService.parse_candidate_run()` is called from
    `_parse_current_gate_results()` for a regular gate
    THEN the system SHALL CONTINUE TO receive `(self._current_gate_export_dir,
    self._gate_run_started_at)` as arguments, with no change to gate result parsing.

3.5 WHEN the loop is stopped mid-run or reaches `max_iterations`
    THEN the system SHALL CONTINUE TO surface the best iteration found so far and
    allow the user to accept, discard, or rollback as before.

3.6 WHEN the user applies the best result via "Apply Best Result"
    THEN the system SHALL CONTINUE TO write the candidate parameters to the live
    strategy JSON file via `ImproveService.accept_candidate()` exactly as before.
