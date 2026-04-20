# Strategy Lab Cleanup and Baseline Fixes - Bugfix Design

## Overview

This bugfix addresses five critical issues left from the previous Strategy Lab refactoring that will cause runtime failures when the baseline backtest flow is triggered. The issues stem from incomplete cleanup during refactoring:

1. **Duplicate method definitions** in `loop_page.py` and `loop_service.py` that create dead code and maintenance burden
2. **Parameter mismatches** in `build_backtest_command()` calls using unsupported kwargs
3. **Parameter name mismatches** in `ProcessService.execute_command()` calls
4. **Callback signature mismatch** in baseline backtest completion handler

The fix strategy is straightforward: remove duplicate method definitions (keeping the canonical second definitions), correct parameter names to match actual function signatures, and align callback signatures with the calling convention. All fixes are localized to two files (`loop_page.py` and `loop_service.py`) and preserve existing functionality.

## Glossary

- **Bug_Condition (C)**: The condition that triggers each bug - duplicate methods, wrong parameter names, or signature mismatches
- **Property (P)**: The desired behavior - single method definitions, correct parameter names, matching signatures
- **Preservation**: Existing non-baseline backtest flows and all other Strategy Lab functionality that must remain unchanged
- **loop_page.py**: The UI page at `app/ui/pages/loop_page.py` containing the Strategy Lab interface
- **loop_service.py**: The service at `app/core/services/loop_service.py` containing validation gate logic
- **ProcessService**: The service at `app/core/services/process_service.py` that wraps QProcess for command execution
- **build_backtest_command()**: Function in `app/core/freqtrade/runners/backtest_runner.py` that builds backtest commands
- **Canonical definition**: The second (later) definition of a duplicate method, which is the one actually used by Python

## Bug Details

### Bug Condition 1: Duplicate _update_state_machine() in loop_page.py

The bug manifests when the code contains two definitions of `_update_state_machine()` at lines 695 and 1343 in `loop_page.py`. Python uses only the second definition, making the first definition dead code.

**Formal Specification:**
```
FUNCTION isBugCondition1(file)
  INPUT: file of type PythonSourceFile
  OUTPUT: boolean
  
  RETURN file.path == "app/ui/pages/loop_page.py"
         AND count(file.methods WHERE name == "_update_state_machine") > 1
         AND first_definition.line_number == 695
         AND second_definition.line_number == 1343
END FUNCTION
```

### Bug Condition 2: Duplicate Gate Methods in loop_service.py

The bug manifests when the code contains duplicate gate runner method definitions in `loop_service.py`:
- `_run_oos_gate()` at lines 791 and 1874
- `_run_walk_forward_gate()` at lines 875 and 1912
- `_run_stress_gate()` at lines 964 and 1948
- `_run_consistency_gate()` at lines 1020 and 1972

Python uses only the second definitions, making the first definitions dead code.

**Formal Specification:**
```
FUNCTION isBugCondition2(file)
  INPUT: file of type PythonSourceFile
  OUTPUT: boolean
  
  RETURN file.path == "app/core/services/loop_service.py"
         AND (
           count(file.methods WHERE name == "_run_oos_gate") > 1
           OR count(file.methods WHERE name == "_run_walk_forward_gate") > 1
           OR count(file.methods WHERE name == "_run_stress_gate") > 1
           OR count(file.methods WHERE name == "_run_consistency_gate") > 1
         )
END FUNCTION
```

### Bug Condition 3: build_backtest_command() Parameter Mismatch

The bug manifests when `_run_baseline_backtest()` in `loop_page.py` (around line 1910) calls `build_backtest_command()` with unsupported kwargs: `export_dir`, `config_file`, `strategy_file`. These parameters are not in the function signature and will cause a TypeError at runtime.

**Formal Specification:**
```
FUNCTION isBugCondition3(call_site)
  INPUT: call_site of type FunctionCall
  OUTPUT: boolean
  
  LET actual_params = ["settings", "strategy_name", "timeframe", "timerange", 
                       "pairs", "max_open_trades", "dry_run_wallet", "extra_flags"]
  LET invalid_params = ["export_dir", "config_file", "strategy_file"]
  
  RETURN call_site.function_name == "build_backtest_command"
         AND call_site.location.file == "app/ui/pages/loop_page.py"
         AND call_site.location.function == "_run_baseline_backtest"
         AND EXISTS param IN call_site.kwargs WHERE param IN invalid_params
END FUNCTION
```

### Bug Condition 4: ProcessService.execute_command() Parameter Mismatch

The bug manifests when `_run_baseline_backtest()` calls `ProcessService.execute_command()` with wrong parameter names:
- Uses `cwd` instead of `working_directory`
- Uses `on_stdout` instead of `on_output`
- Uses `on_stderr` instead of `on_error`

**Formal Specification:**
```
FUNCTION isBugCondition4(call_site)
  INPUT: call_site of type FunctionCall
  OUTPUT: boolean
  
  LET actual_params = ["command", "on_output", "on_error", "on_finished", 
                       "working_directory", "env"]
  LET invalid_params = ["cwd", "on_stdout", "on_stderr"]
  
  RETURN call_site.function_name == "execute_command"
         AND call_site.object_type == "ProcessService"
         AND call_site.location.file == "app/ui/pages/loop_page.py"
         AND call_site.location.function == "_run_baseline_backtest"
         AND EXISTS param IN call_site.kwargs WHERE param IN invalid_params
END FUNCTION
```

### Bug Condition 5: Callback Signature Mismatch

The bug manifests when `_on_baseline_backtest_finished()` is defined with signature `(self, exit_code: int, exit_status: str)` but `ProcessService.execute_command()` on_finished callback only passes one argument `(exit_code)`. This causes a TypeError at runtime due to argument count mismatch.

**Formal Specification:**
```
FUNCTION isBugCondition5(callback_def, callback_call)
  INPUT: callback_def of type FunctionDefinition
  INPUT: callback_call of type CallbackRegistration
  OUTPUT: boolean
  
  RETURN callback_def.name == "_on_baseline_backtest_finished"
         AND callback_def.location.file == "app/ui/pages/loop_page.py"
         AND callback_def.parameter_count == 3  // self, exit_code, exit_status
         AND callback_call.callback_name == callback_def.name
         AND callback_call.actual_argument_count == 1  // only exit_code
END FUNCTION
```

### Examples

**Bug 1 Example:**
- **Current**: Two `_update_state_machine()` methods exist at lines 695 and 1343
- **Expected**: Only one `_update_state_machine()` method exists (the one at line 1343)
- **Impact**: Dead code, confusion during maintenance, potential for divergent implementations

**Bug 2 Example:**
- **Current**: `_run_oos_gate()` defined twice at lines 791 and 1874
- **Expected**: Only one `_run_oos_gate()` method exists (the one at line 1874)
- **Impact**: Dead code, confusion during maintenance, wasted file space

**Bug 3 Example:**
- **Current**: `build_backtest_command(settings, strategy, timeframe, timerange, pairs, export_dir=str(export_dir), config_file=str(sandbox_dir / "config.json"), strategy_file=str(sandbox_dir / f"{strategy}.py"))`
- **Expected**: `build_backtest_command(settings, strategy, timeframe, timerange, pairs)`
- **Impact**: TypeError: build_backtest_command() got unexpected keyword argument 'export_dir'

**Bug 4 Example:**
- **Current**: `process_service.execute_command(cmd.as_list(), cwd=str(cmd.cwd), on_stdout=self._on_process_stdout, on_stderr=self._on_process_stderr, on_finished=self._on_baseline_backtest_finished)`
- **Expected**: `process_service.execute_command(cmd.as_list(), working_directory=str(cmd.cwd), on_output=self._on_process_stdout, on_error=self._on_process_stderr, on_finished=self._on_baseline_backtest_finished)`
- **Impact**: TypeError: execute_command() got unexpected keyword argument 'cwd'

**Bug 5 Example:**
- **Current**: `def _on_baseline_backtest_finished(self, exit_code: int, exit_status: str) -> None:`
- **Expected**: `def _on_baseline_backtest_finished(self, exit_code: int) -> None:`
- **Impact**: TypeError: _on_baseline_backtest_finished() takes 3 positional arguments but 2 were given

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- All non-baseline backtest flows must continue to work exactly as before
- Strategy Lab UI state management must remain unchanged
- Validation gate logic must remain unchanged
- All other ProcessService command executions must remain unchanged
- All other backtest command building must remain unchanged

**Scope:**
All code paths that do NOT involve the baseline backtest flow should be completely unaffected by this fix. This includes:
- Regular loop iterations (non-baseline)
- Manual backtest runs from the Backtest page
- Optimize page functionality
- Download data functionality
- All other Strategy Lab features (apply best, discard, rollback)

## Hypothesized Root Cause

Based on the bug description and code analysis, the root causes are:

1. **Incomplete Refactoring Cleanup**: During the previous Strategy Lab refactoring, new method implementations were added but the old implementations were not removed, resulting in duplicate definitions. Python's method resolution uses the last definition, making earlier definitions dead code.

2. **API Mismatch from Refactoring**: The baseline backtest code was written against an older or assumed API for `build_backtest_command()` that included `export_dir`, `config_file`, and `strategy_file` parameters. The actual implementation returns a `BacktestRunCommand` dataclass that contains these as attributes, not parameters.

3. **Parameter Name Inconsistency**: The baseline backtest code uses parameter names (`cwd`, `on_stdout`, `on_stderr`) that don't match the actual `ProcessService.execute_command()` signature (`working_directory`, `on_output`, `on_error`). This suggests the code was written against a different or assumed API.

4. **Callback Convention Mismatch**: The baseline backtest completion handler was written with a two-parameter signature `(exit_code, exit_status)` but the actual `ProcessService` on_finished callback only passes `exit_code`. The `exit_status` string would need to be derived from the exit code if needed.

## Correctness Properties

Property 1: Bug Condition - Duplicate Methods Removed

_For any_ Python source file in the codebase, the fixed code SHALL contain at most one definition of each method name within a class, eliminating all duplicate method definitions identified in bugs 1 and 2.

**Validates: Requirements 2.1, 2.2**

Property 2: Bug Condition - Correct Function Parameters

_For any_ function call to `build_backtest_command()` or `ProcessService.execute_command()`, the fixed code SHALL use only parameters that exist in the actual function signature, eliminating parameter mismatches identified in bugs 3 and 4.

**Validates: Requirements 2.3, 2.4**

Property 3: Bug Condition - Matching Callback Signatures

_For any_ callback function registered with `ProcessService.execute_command()`, the fixed code SHALL define the callback with a signature that matches the number and types of arguments actually passed by the ProcessService, eliminating signature mismatches identified in bug 5.

**Validates: Requirements 2.5**

Property 4: Preservation - Non-Baseline Flows Unchanged

_For any_ code path that does NOT involve the baseline backtest flow (regular loop iterations, manual backtests, optimize, download data), the fixed code SHALL produce exactly the same behavior as the original code, preserving all existing functionality.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

All changes are localized to two files: `app/ui/pages/loop_page.py` and `app/core/services/loop_service.py`.

**File**: `app/ui/pages/loop_page.py`

**Function**: `_run_baseline_backtest()` (around line 1867)

**Specific Changes**:

1. **Remove Duplicate _update_state_machine() Method**:
   - Delete the first definition at line 695 (approximately lines 695-733)
   - Keep the second definition at line 1343 (the canonical implementation)
   - Rationale: Python uses the last definition; the first is dead code

2. **Fix build_backtest_command() Call**:
   - Remove unsupported kwargs: `export_dir`, `config_file`, `strategy_file`
   - These are attributes of the returned `BacktestRunCommand`, not parameters
   - Before: `build_backtest_command(settings, strategy, timeframe, timerange, pairs, export_dir=..., config_file=..., strategy_file=...)`
   - After: `build_backtest_command(settings, strategy, timeframe, timerange, pairs)`

3. **Fix ProcessService.execute_command() Call**:
   - Rename `cwd` → `working_directory`
   - Rename `on_stdout` → `on_output`
   - Rename `on_stderr` → `on_error`
   - Before: `execute_command(cmd.as_list(), cwd=..., on_stdout=..., on_stderr=..., on_finished=...)`
   - After: `execute_command(cmd.as_list(), working_directory=..., on_output=..., on_error=..., on_finished=...)`

4. **Fix _on_baseline_backtest_finished() Signature**:
   - Remove `exit_status: str` parameter (not passed by ProcessService)
   - Before: `def _on_baseline_backtest_finished(self, exit_code: int, exit_status: str) -> None:`
   - After: `def _on_baseline_backtest_finished(self, exit_code: int) -> None:`
   - Update any references to `exit_status` inside the function to derive it from `exit_code` if needed

**File**: `app/core/services/loop_service.py`

**Functions**: Gate runner methods

**Specific Changes**:

1. **Remove Duplicate _run_oos_gate() Method**:
   - Delete the first definition at line 791 (approximately lines 791-873)
   - Keep the second definition at line 1874 (the canonical implementation)

2. **Remove Duplicate _run_walk_forward_gate() Method**:
   - Delete the first definition at line 875 (approximately lines 875-962)
   - Keep the second definition at line 1912 (the canonical implementation)

3. **Remove Duplicate _run_stress_gate() Method**:
   - Delete the first definition at line 964 (approximately lines 964-1018)
   - Keep the second definition at line 1948 (the canonical implementation)

4. **Remove Duplicate _run_consistency_gate() Method**:
   - Delete the first definition at line 1020 (approximately lines 1020-1050)
   - Keep the second definition at line 1972 (the canonical implementation)

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, demonstrate that the bugs exist in the unfixed code (exploratory testing), then verify the fixes work correctly and preserve existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bugs BEFORE implementing the fix. Confirm the root cause analysis.

**Test Plan**: Write tests that attempt to trigger the baseline backtest flow and observe the failures. Inspect the code to confirm duplicate methods exist.

**Test Cases**:

1. **Static Analysis - Duplicate Methods**: Parse `loop_page.py` and `loop_service.py` to count method definitions
   - Expected: Multiple definitions of `_update_state_machine`, `_run_oos_gate`, etc.
   - Will fail on unfixed code: Finds 2 definitions of each method

2. **Runtime Test - build_backtest_command() Call**: Mock the baseline backtest flow and call `build_backtest_command()` with the unsupported kwargs
   - Expected: TypeError about unexpected keyword arguments
   - Will fail on unfixed code: Raises TypeError for 'export_dir'

3. **Runtime Test - execute_command() Call**: Mock the baseline backtest flow and call `execute_command()` with wrong parameter names
   - Expected: TypeError about unexpected keyword arguments
   - Will fail on unfixed code: Raises TypeError for 'cwd'

4. **Runtime Test - Callback Invocation**: Mock ProcessService to invoke the callback with only one argument
   - Expected: TypeError about argument count mismatch
   - Will fail on unfixed code: Raises TypeError (takes 3 positional arguments but 2 were given)

**Expected Counterexamples**:
- Duplicate method definitions found via AST parsing
- TypeError exceptions when calling functions with wrong parameters
- TypeError exceptions when invoking callbacks with wrong argument counts

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed code produces the expected behavior.

**Pseudocode:**
```
FOR ALL bug_condition IN [duplicate_methods, wrong_params, wrong_callback_sig] DO
  result := check_bug_condition_fixed(bug_condition)
  ASSERT result == "bug_eliminated"
END FOR
```

**Test Cases**:

1. **Static Analysis - No Duplicate Methods**: Parse fixed code and verify only one definition of each method
   - Assert: count(methods named "_update_state_machine") == 1
   - Assert: count(methods named "_run_oos_gate") == 1
   - Assert: count(methods named "_run_walk_forward_gate") == 1
   - Assert: count(methods named "_run_stress_gate") == 1
   - Assert: count(methods named "_run_consistency_gate") == 1

2. **Runtime Test - build_backtest_command() Succeeds**: Call with only supported parameters
   - Assert: Returns BacktestRunCommand without TypeError
   - Assert: Returned object has export_dir, config_file, strategy_file attributes

3. **Runtime Test - execute_command() Succeeds**: Call with correct parameter names
   - Assert: QProcess starts without TypeError
   - Assert: Callbacks are registered correctly

4. **Runtime Test - Callback Invocation Succeeds**: Invoke callback with one argument
   - Assert: Callback executes without TypeError
   - Assert: Callback logic handles exit_code correctly

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold (non-baseline flows), the fixed code produces the same result as the original code.

**Pseudocode:**
```
FOR ALL code_path WHERE NOT involves_baseline_backtest(code_path) DO
  ASSERT behavior_after_fix(code_path) == behavior_before_fix(code_path)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across different Strategy Lab configurations
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-baseline flows

**Test Plan**: Observe behavior on UNFIXED code first for non-baseline flows, then write property-based tests capturing that behavior.

**Test Cases**:

1. **Regular Loop Iteration Preservation**: Run a regular loop iteration (not baseline) and verify identical behavior
   - Observe: Gate sequence, validation logic, result handling on unfixed code
   - Test: Property-based test generates random loop configs and verifies same behavior after fix

2. **UI State Management Preservation**: Interact with Strategy Lab UI and verify state transitions unchanged
   - Observe: Button enable/disable logic, widget state on unfixed code
   - Test: Property-based test generates random UI states and verifies same state machine behavior

3. **Manual Backtest Preservation**: Run manual backtest from Backtest page and verify unchanged
   - Observe: Command building, execution, result parsing on unfixed code
   - Test: Unit test verifies manual backtest flow unchanged

4. **Other ProcessService Calls Preservation**: Execute other commands via ProcessService and verify unchanged
   - Observe: Download data, optimize commands on unfixed code
   - Test: Property-based test generates random commands and verifies same execution behavior

### Unit Tests

- Test that duplicate methods are removed (static analysis)
- Test that `build_backtest_command()` is called with correct parameters
- Test that `execute_command()` is called with correct parameter names
- Test that callback signature matches ProcessService convention
- Test that baseline backtest flow completes successfully with fixes
- Test that non-baseline flows continue to work (regression tests)

### Property-Based Tests

- Generate random loop configurations and verify non-baseline iterations work identically before/after fix
- Generate random UI interactions and verify state machine behavior unchanged
- Generate random command executions and verify ProcessService behavior unchanged for non-baseline commands
- Generate random strategy/timeframe/pair combinations and verify backtest command building unchanged for non-baseline calls

### Integration Tests

- Test full baseline backtest flow from UI button click through completion
- Test that baseline results are correctly stored and used as seed for first iteration
- Test that loop continues correctly after baseline completes
- Test that error handling works correctly if baseline fails
- Test that non-baseline flows (regular iterations, manual backtests) continue to work end-to-end
