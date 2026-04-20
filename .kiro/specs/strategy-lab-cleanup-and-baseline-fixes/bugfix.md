# Bugfix Requirements Document

## Introduction

This bugfix addresses critical issues left from the previous Strategy Lab refactoring that will cause runtime failures when the baseline backtest flow is triggered. The issues include:
- Duplicate method definitions in `loop_page.py` and `loop_service.py` that create ambiguity
- Parameter mismatches in `build_backtest_command()` calls using unsupported kwargs
- Parameter name mismatches in `ProcessService.execute_command()` calls
- Callback signature mismatch in baseline backtest completion handler

These bugs will prevent the baseline backtest feature from functioning and must be fixed to restore proper operation.

## Bug Analysis

### Current Behavior (Defect)

#### Bug 1: Duplicate Methods in loop_page.py

1.1 WHEN the code contains duplicate `_update_state_machine()` method definitions at lines 695 and 1343 in `loop_page.py` THEN the system uses only the second definition, making the first definition dead code that creates confusion and maintenance burden

#### Bug 2: Duplicate Methods in loop_service.py

1.2 WHEN the code contains duplicate gate runner method definitions in `loop_service.py`:
- `_run_oos_gate()` at lines 791 and 1874
- `_run_walk_forward_gate()` at lines 875 and 1912
- `_run_stress_gate()` at lines 964 and 1948
- `_run_consistency_gate()` at lines 1020 and 1972

THEN the system uses only the second definitions, making the first definitions dead code that creates confusion and maintenance burden

#### Bug 3: build_backtest_command() Parameter Mismatch

1.3 WHEN `_run_baseline_backtest()` in `loop_page.py` calls `build_backtest_command()` with unsupported kwargs (`export_dir`, `config_file`, `strategy_file`) THEN the system raises a TypeError at runtime because these parameters are not in the function signature

#### Bug 4: ProcessService.execute_command() Parameter Mismatch

1.4 WHEN `_run_baseline_backtest()` calls `ProcessService.execute_command()` with wrong parameter names (`cwd` instead of `working_directory`, `on_stdout` instead of `on_output`, `on_stderr` instead of `on_error`) THEN the system raises a TypeError at runtime because these parameter names don't match the actual signature

#### Bug 5: Callback Signature Mismatch

1.5 WHEN `_on_baseline_backtest_finished()` is defined with signature `(self, exit_code: int, exit_status: str)` but `ProcessService.execute_command()` on_finished callback only passes one argument `(exit_code)` THEN the system raises a TypeError at runtime due to argument count mismatch

### Expected Behavior (Correct)

#### Bug 1: Single _update_state_machine() Method

2.1 WHEN the code is examined THEN the system SHALL contain only one `_update_state_machine()` method definition in `loop_page.py` with the canonical implementation preserved

#### Bug 2: Single Gate Runner Methods

2.2 WHEN the code is examined THEN the system SHALL contain only one definition of each gate runner method in `loop_service.py`:
- One `_run_oos_gate()` method
- One `_run_walk_forward_gate()` method
- One `_run_stress_gate()` method
- One `_run_consistency_gate()` method

#### Bug 3: Correct build_backtest_command() Call

2.3 WHEN `_run_baseline_backtest()` calls `build_backtest_command()` THEN the system SHALL use only supported parameters from the actual signature: `settings`, `strategy_name`, `timeframe`, `timerange`, `pairs`, `max_open_trades`, `dry_run_wallet`, `extra_flags`

#### Bug 4: Correct ProcessService.execute_command() Call

2.4 WHEN `_run_baseline_backtest()` calls `ProcessService.execute_command()` THEN the system SHALL use correct parameter names: `working_directory` (not `cwd`), `on_output` (not `on_stdout`), `on_error` (not `on_stderr`)

#### Bug 5: Correct Callback Signature

2.5 WHEN `_on_baseline_backtest_finished()` is defined THEN the system SHALL use signature `(self, exit_code: int)` to match the `ProcessService.execute_command()` on_finished callback that passes only one argument

### Unchanged Behavior (Regression Prevention)

#### Existing Functionality Preservation

3.1 WHEN duplicate methods are removed THEN the system SHALL CONTINUE TO execute the same logic as the canonical (second) method definitions

3.2 WHEN parameter names are corrected in `ProcessService.execute_command()` calls THEN the system SHALL CONTINUE TO pass the same values to the same logical parameters (working directory, output callbacks, error callbacks)

3.3 WHEN the callback signature is corrected THEN the system SHALL CONTINUE TO receive the exit code and handle baseline backtest completion with the same logic

3.4 WHEN `build_backtest_command()` is called with only supported parameters THEN the system SHALL CONTINUE TO generate valid backtest commands with the same effective configuration

3.5 WHEN non-baseline backtest flows execute THEN the system SHALL CONTINUE TO function correctly without any changes to their behavior
