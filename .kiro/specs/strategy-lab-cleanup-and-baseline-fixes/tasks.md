# Implementation Plan

## Phase 1: Exploratory Bug Condition Testing (BEFORE Fix)

### 1.1 Static Analysis - Duplicate Methods Detection

- [ ] 1.1.1 Write bug condition exploration test for duplicate methods
  - **Property 1: Bug Condition** - Duplicate Method Definitions Exist
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bugs exist
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate duplicate method definitions exist
  - **Scoped PBT Approach**: Use AST parsing to scope the property to concrete duplicate method locations
  - Test implementation details from Bug Conditions 1 and 2 in design:
    - Parse `app/ui/pages/loop_page.py` and count definitions of `_update_state_machine`
    - Parse `app/core/services/loop_service.py` and count definitions of gate runner methods
    - Assert: `_update_state_machine` appears at lines 695 and 1343 in loop_page.py
    - Assert: `_run_oos_gate` appears at lines 791 and 1874 in loop_service.py
    - Assert: `_run_walk_forward_gate` appears at lines 875 and 1912 in loop_service.py
    - Assert: `_run_stress_gate` appears at lines 964 and 1948 in loop_service.py
    - Assert: `_run_consistency_gate` appears at lines 1020 and 1972 in loop_service.py
  - The test assertions should match the Expected Behavior Properties from design (Property 1)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the duplicate methods exist)
  - Document counterexamples found: specific line numbers and method names
  - Mark task complete when test is written, run, and failures are documented
  - _Requirements: 2.1, 2.2_

### 1.2 Runtime Analysis - Parameter Mismatch Detection

- [ ] 1.2.1 Write bug condition exploration test for build_backtest_command() parameter mismatch
  - **Property 1: Bug Condition** - Invalid Parameters Passed to build_backtest_command
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate parameter mismatch
  - **Scoped PBT Approach**: Scope the property to the concrete failing case in `_run_baseline_backtest()`
  - Test implementation details from Bug Condition 3 in design:
    - Mock or inspect the call to `build_backtest_command()` in `loop_page.py` line ~1910
    - Assert: Call includes unsupported kwargs `export_dir`, `config_file`, `strategy_file`
    - Attempt to invoke `build_backtest_command()` with these kwargs
    - Assert: Raises TypeError about unexpected keyword arguments
  - The test assertions should match the Expected Behavior Properties from design (Property 2)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS with TypeError (this is correct - it proves the bug exists)
  - Document counterexamples found: specific TypeError message and parameter names
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 2.3_

- [ ] 1.2.2 Write bug condition exploration test for execute_command() parameter mismatch
  - **Property 1: Bug Condition** - Invalid Parameters Passed to execute_command
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate parameter name mismatch
  - **Scoped PBT Approach**: Scope the property to the concrete failing case in `_run_baseline_backtest()`
  - Test implementation details from Bug Condition 4 in design:
    - Mock or inspect the call to `ProcessService.execute_command()` in `loop_page.py` line ~1910
    - Assert: Call includes wrong parameter names `cwd`, `on_stdout`, `on_stderr`
    - Attempt to invoke `execute_command()` with these parameter names
    - Assert: Raises TypeError about unexpected keyword arguments
  - The test assertions should match the Expected Behavior Properties from design (Property 2)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS with TypeError (this is correct - it proves the bug exists)
  - Document counterexamples found: specific TypeError message and parameter names
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 2.4_

- [ ] 1.2.3 Write bug condition exploration test for callback signature mismatch
  - **Property 1: Bug Condition** - Callback Signature Mismatch
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate callback signature mismatch
  - **Scoped PBT Approach**: Scope the property to the concrete failing case with callback invocation
  - Test implementation details from Bug Condition 5 in design:
    - Inspect `_on_baseline_backtest_finished()` signature in `loop_page.py`
    - Assert: Method signature is `(self, exit_code: int, exit_status: str)`
    - Mock ProcessService to invoke callback with only one argument (exit_code)
    - Assert: Raises TypeError about argument count mismatch
  - The test assertions should match the Expected Behavior Properties from design (Property 3)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS with TypeError (this is correct - it proves the bug exists)
  - Document counterexamples found: specific TypeError message about argument count
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 2.5_

## Phase 2: Preservation Property Tests (BEFORE Fix)

- [ ] 2.1 Write preservation property tests for non-baseline flows
  - **Property 2: Preservation** - Non-Baseline Flows Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-baseline flows:
    - Regular loop iterations (non-baseline)
    - Manual backtest runs from Backtest page
    - Optimize page functionality
    - Download data functionality
    - Strategy Lab UI state management
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements:
    - Test that regular loop iterations execute gate sequence correctly
    - Test that manual backtests build commands correctly
    - Test that UI state machine transitions work correctly
    - Test that ProcessService executes non-baseline commands correctly
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

## Phase 3: Implementation (Surgical Fixes)

### 3.1 Fix Duplicate Methods in loop_page.py

- [ ] 3.1.1 Remove duplicate _update_state_machine() method
  - Delete the first definition at line 695 (approximately lines 695-733)
  - Keep the second definition at line 1343 (the canonical implementation)
  - Verify no references to the deleted method exist
  - _Bug_Condition: isBugCondition1(file) where file contains duplicate _update_state_machine definitions_
  - _Expected_Behavior: Only one _update_state_machine method exists (Property 1 from design)_
  - _Preservation: Non-baseline flows continue to use the same state machine logic (Preservation Requirements from design)_
  - _Requirements: 2.1, 3.1_

### 3.2 Fix Duplicate Methods in loop_service.py

- [ ] 3.2.1 Remove duplicate _run_oos_gate() method
  - Delete the first definition at line 791 (approximately lines 791-873)
  - Keep the second definition at line 1874 (the canonical implementation)
  - Verify no references to the deleted method exist
  - _Bug_Condition: isBugCondition2(file) where file contains duplicate _run_oos_gate definitions_
  - _Expected_Behavior: Only one _run_oos_gate method exists (Property 1 from design)_
  - _Preservation: Gate validation logic unchanged (Preservation Requirements from design)_
  - _Requirements: 2.2, 3.1_

- [ ] 3.2.2 Remove duplicate _run_walk_forward_gate() method
  - Delete the first definition at line 875 (approximately lines 875-962)
  - Keep the second definition at line 1912 (the canonical implementation)
  - Verify no references to the deleted method exist
  - _Bug_Condition: isBugCondition2(file) where file contains duplicate _run_walk_forward_gate definitions_
  - _Expected_Behavior: Only one _run_walk_forward_gate method exists (Property 1 from design)_
  - _Preservation: Gate validation logic unchanged (Preservation Requirements from design)_
  - _Requirements: 2.2, 3.1_

- [ ] 3.2.3 Remove duplicate _run_stress_gate() method
  - Delete the first definition at line 964 (approximately lines 964-1018)
  - Keep the second definition at line 1948 (the canonical implementation)
  - Verify no references to the deleted method exist
  - _Bug_Condition: isBugCondition2(file) where file contains duplicate _run_stress_gate definitions_
  - _Expected_Behavior: Only one _run_stress_gate method exists (Property 1 from design)_
  - _Preservation: Gate validation logic unchanged (Preservation Requirements from design)_
  - _Requirements: 2.2, 3.1_

- [ ] 3.2.4 Remove duplicate _run_consistency_gate() method
  - Delete the first definition at line 1020 (approximately lines 1020-1050)
  - Keep the second definition at line 1972 (the canonical implementation)
  - Verify no references to the deleted method exist
  - _Bug_Condition: isBugCondition2(file) where file contains duplicate _run_consistency_gate definitions_
  - _Expected_Behavior: Only one _run_consistency_gate method exists (Property 1 from design)_
  - _Preservation: Gate validation logic unchanged (Preservation Requirements from design)_
  - _Requirements: 2.2, 3.1_

### 3.3 Fix Parameter Mismatches in _run_baseline_backtest()

- [ ] 3.3.1 Fix build_backtest_command() call parameters
  - Locate the call to `build_backtest_command()` in `_run_baseline_backtest()` (around line 1910)
  - Remove unsupported kwargs: `export_dir`, `config_file`, `strategy_file`
  - Change from: `build_backtest_command(settings, strategy, timeframe, timerange, pairs, export_dir=..., config_file=..., strategy_file=...)`
  - Change to: `build_backtest_command(settings, strategy, timeframe, timerange, pairs)`
  - Note: These removed parameters are attributes of the returned `BacktestRunCommand`, not function parameters
  - _Bug_Condition: isBugCondition3(call_site) where call uses unsupported kwargs_
  - _Expected_Behavior: Call uses only supported parameters (Property 2 from design)_
  - _Preservation: Backtest command building unchanged for non-baseline calls (Preservation Requirements from design)_
  - _Requirements: 2.3, 3.4_

- [ ] 3.3.2 Fix ProcessService.execute_command() call parameters
  - Locate the call to `ProcessService.execute_command()` in `_run_baseline_backtest()` (around line 1910)
  - Rename parameter `cwd` → `working_directory`
  - Rename parameter `on_stdout` → `on_output`
  - Rename parameter `on_stderr` → `on_error`
  - Change from: `execute_command(cmd.as_list(), cwd=..., on_stdout=..., on_stderr=..., on_finished=...)`
  - Change to: `execute_command(cmd.as_list(), working_directory=..., on_output=..., on_error=..., on_finished=...)`
  - _Bug_Condition: isBugCondition4(call_site) where call uses wrong parameter names_
  - _Expected_Behavior: Call uses correct parameter names (Property 2 from design)_
  - _Preservation: ProcessService calls unchanged for non-baseline commands (Preservation Requirements from design)_
  - _Requirements: 2.4, 3.2_

- [ ] 3.3.3 Fix _on_baseline_backtest_finished() callback signature
  - Locate `_on_baseline_backtest_finished()` method definition in `loop_page.py`
  - Remove `exit_status: str` parameter from signature
  - Change from: `def _on_baseline_backtest_finished(self, exit_code: int, exit_status: str) -> None:`
  - Change to: `def _on_baseline_backtest_finished(self, exit_code: int) -> None:`
  - Update any references to `exit_status` inside the function body:
    - If needed, derive exit status from exit_code (e.g., `exit_status = "success" if exit_code == 0 else "failed"`)
  - _Bug_Condition: isBugCondition5(callback_def) where callback expects 2 args but receives 1_
  - _Expected_Behavior: Callback signature matches ProcessService convention (Property 3 from design)_
  - _Preservation: Callback logic handles exit_code correctly (Preservation Requirements from design)_
  - _Requirements: 2.5, 3.3_

### 3.4 Verification - Bug Condition Tests Now Pass

- [ ] 3.4.1 Verify static analysis test now passes
  - **Property 1: Expected Behavior** - Single Method Definitions
  - **IMPORTANT**: Re-run the SAME test from task 1.1.1 - do NOT write a new test
  - The test from task 1.1.1 encodes the expected behavior
  - When this test passes, it confirms duplicate methods are eliminated
  - Run static analysis test from step 1.1.1
  - **EXPECTED OUTCOME**: Test PASSES (confirms duplicate methods removed)
  - Assert: Only one definition of each method exists in fixed code
  - _Requirements: 2.1, 2.2_

- [ ] 3.4.2 Verify runtime parameter tests now pass
  - **Property 1: Expected Behavior** - Correct Function Parameters
  - **IMPORTANT**: Re-run the SAME tests from tasks 1.2.1, 1.2.2, 1.2.3 - do NOT write new tests
  - The tests from task 1.2.x encode the expected behavior
  - When these tests pass, they confirm parameter mismatches are fixed
  - Run runtime tests from steps 1.2.1, 1.2.2, 1.2.3
  - **EXPECTED OUTCOME**: Tests PASS (confirms parameter mismatches fixed)
  - Assert: No TypeError exceptions raised
  - _Requirements: 2.3, 2.4, 2.5_

### 3.5 Verification - Preservation Tests Still Pass

- [ ] 3.5.1 Verify preservation tests still pass
  - **Property 2: Preservation** - Non-Baseline Flows Unchanged
  - **IMPORTANT**: Re-run the SAME tests from task 2.1 - do NOT write new tests
  - Run preservation property tests from step 2.1
  - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
  - Confirm all preservation tests still pass after fix
  - Assert: Non-baseline flows produce identical behavior
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

## Phase 4: Integration Testing

- [ ] 4.1 Integration test - Full baseline backtest flow
  - Test full baseline backtest flow from UI button click through completion
  - Verify baseline results are correctly stored and used as seed for first iteration
  - Verify loop continues correctly after baseline completes
  - Test error handling if baseline fails
  - Verify non-baseline flows (regular iterations, manual backtests) continue to work end-to-end
  - _Requirements: All requirements 2.1-2.5, 3.1-3.5_

- [ ] 4.2 Checkpoint - Ensure all tests pass
  - Run full test suite (exploration tests, preservation tests, integration tests)
  - Verify all tests pass
  - Verify no regressions in non-baseline functionality
  - Ask the user if questions arise
