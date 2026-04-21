# Bugfix Requirements Document

## Introduction

The Strategy Lab feature (loop_page.py / loop_service.py) contains four runtime-crash bugs
that prevent the baseline backtest flow from ever completing, plus one stale-state bug that
causes the loop to silently reuse data from a previous session. Together these bugs mean the
Strategy Lab cannot run a single successful optimization cycle: it crashes before the first
iteration starts, and even if the crash were bypassed the loop would mutate the strategy
using wrong baseline data. The fixes must make the loop start cleanly, run the baseline
backtest correctly, parse its results, and reset properly between sessions.

---

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `_run_baseline_backtest()` is called and the baseline subprocess starts
    THEN the system crashes with `AttributeError: 'LoopPage' object has no attribute
    '_on_process_stdout'` because `_run_baseline_backtest()` passes
    `self._on_process_stdout` and `self._on_process_stderr` as the `on_output` /
    `on_error` callbacks to `ProcessService.execute_command()`, but neither method
    is defined anywhere in `LoopPage`.

1.2 WHEN `_run_baseline_backtest()` calls `self._improve_service.prepare_sandbox()`
    THEN the system crashes with `TypeError` because the call passes `(settings, strategy)`
    but `ImproveService.prepare_sandbox()` expects `(strategy_name: str, candidate_config: dict)`.
    The `AppSettings` object is passed as `strategy_name` and the strategy string is passed
    as `candidate_config`, causing the method to fail immediately.

1.3 WHEN the baseline backtest subprocess finishes successfully and
    `_on_baseline_backtest_finished()` tries to parse the results
    THEN the system crashes with `AttributeError: 'ImproveService' object has no attribute
    'parse_backtest_results'` because `_on_baseline_backtest_finished()` calls
    `self._improve_service.parse_backtest_results(export_dir)`, which does not exist.
    The correct method is `parse_candidate_run(export_dir, started_at)`.

1.4 WHEN `_run_baseline_backtest()` builds the backtest command
    THEN the system does not pass the `baseline_export` directory to Freqtrade via
    `--backtest-directory` in `extra_flags`, so Freqtrade writes its result zip to its
    default location rather than `sandbox_dir / "baseline_export"`. When
    `_on_baseline_backtest_finished()` then calls `parse_candidate_run(export_dir)` on
    the empty `baseline_export` directory, it raises `FileNotFoundError: No candidate zip
    found in export_dir`.

1.5 WHEN the user starts a new Strategy Lab run after a previous session has already
    completed or been stopped
    THEN `_latest_diagnosis_input` still holds the previous session's diagnosis data
    because it is never cleared at the start of a new run. The baseline check
    (`needs_baseline = self._latest_diagnosis_input is None`) evaluates to `False`,
    so the baseline backtest is skipped and the new loop uses stale data from the
    prior session as its mutation seed.

---

### Expected Behavior (Correct)

2.1 WHEN `_run_baseline_backtest()` is called
    THEN the system SHALL route baseline subprocess output to the terminal widget by
    passing `self._terminal.append_output` as `on_output` and
    `self._terminal.append_error` as `on_error` to `ProcessService.execute_command()`,
    matching the pattern used by `_start_gate_backtest()`.

2.2 WHEN `_run_baseline_backtest()` calls `prepare_sandbox()`
    THEN the system SHALL call `self._improve_service.prepare_sandbox(strategy, {})`
    with the strategy name as the first argument and an empty dict as the candidate
    config, so the sandbox is created with the strategy's current (unmodified) `.py`
    file and a minimal params file.

2.3 WHEN `_on_baseline_backtest_finished()` parses the baseline results
    THEN the system SHALL call `self._improve_service.parse_candidate_run(export_dir,
    self._baseline_run_started_at)` using the existing `parse_candidate_run()` method,
    where `_baseline_run_started_at` is the Unix timestamp recorded just before
    `ProcessService.execute_command()` is called for the baseline.

2.4 WHEN `_run_baseline_backtest()` builds the backtest command
    THEN the system SHALL include `"--backtest-directory", str(export_dir)` in the
    `extra_flags` list passed to `build_backtest_command()`, so Freqtrade writes its
    result zip into `sandbox_dir / "baseline_export"` where the parser expects it.

2.5 WHEN the user clicks "Start Loop" to begin a new Strategy Lab session
    THEN the system SHALL reset `_latest_diagnosis_input` to `None` at the start of
    `_on_start()` (before the baseline check), so every new session always runs a
    fresh baseline backtest regardless of any previous session's state.

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
