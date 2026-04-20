# Implementation Plan

## Overview

This task list implements fixes for five critical bugs in the Strategy Lab / Loop feature using the bug condition methodology. Tasks are ordered to minimize risk and enable incremental testing.

---

## Phase 1: Exploratory Bug Condition Testing (BEFORE Fix)

### 1. Write bug condition exploration tests

- [x] 1.1 **Property 1: Bug Condition** - Fake Baseline Seed Detection
  - **CRITICAL**: Write this property-based test BEFORE implementing the fix
  - **GOAL**: Surface counterexamples that demonstrate Bug 1 exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - Test that starting a loop with no previous diagnosis input returns a dummy BacktestSummary with hardcoded values (50 trades, 50% win rate, 0% profit)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found (e.g., "Loop start returns dummy baseline instead of running real backtest")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 2.1, 2.2_

- [x] 1.2 **Property 1: Bug Condition** - Hardcoded Timeframe Detection
  - **CRITICAL**: Write this property-based test BEFORE implementing the fix
  - **GOAL**: Surface counterexamples that demonstrate Bug 2 exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - Test that gate backtests use "5m" timeframe when strategy has "1h" native timeframe
  - Verify `LoopConfig.timeframe` defaults to "5m" and is never populated from strategy
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found (e.g., "Strategy with 1h timeframe uses 5m in all gates")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.2, 1.3, 2.3, 2.4_

- [x] 1.3 **Property 1: Bug Condition** - IS/OOS Split Verification
  - **CRITICAL**: Write this property-based test BEFORE implementing the fix
  - **GOAL**: Verify current IS/OOS split behavior (may already be correct)
  - Test that `compute_in_sample_timerange()` ends at `oos_start - 1 day`
  - Test that `compute_oos_timerange()` starts at `oos_start`
  - Verify boundary day is included in OOS and excluded from IS
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test may PASS (current implementation appears correct)
  - Document findings - if test passes, Bug 3 may not exist
  - Mark task complete when test is written, run, and results are documented
  - _Requirements: 1.4, 1.5, 1.6, 2.5, 2.6, 2.7_

- [x] 1.4 **Property 1: Bug Condition** - Hard Filter Wiring Gap
  - **CRITICAL**: Write this property-based test BEFORE implementing the fix
  - **GOAL**: Surface counterexamples that demonstrate Bug 4 exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - Test that `LoopPage._on_gate1_finished()` calls `evaluate_gate1_hard_filters()` without trades parameter
  - Verify filters 3, 6, 7 are silently skipped when trades=None
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found (e.g., "Profit concentration filter skipped despite trades data existing")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.7, 1.8, 1.9, 1.10, 2.8, 2.9, 2.10_

- [x] 1.5 **Property 1: Bug Condition** - Duplicate Method Search
  - **CRITICAL**: Search for duplicate methods BEFORE implementing cleanup
  - **GOAL**: Identify all duplicate method definitions and compatibility wrappers
  - Search `loop_page.py` for methods with similar names or functionality
  - Search `loop_service.py` for methods with similar names or functionality
  - Document all duplicates found with line numbers and method signatures
  - Mark task complete when all duplicates are identified and documented
  - _Requirements: 1.11, 1.12, 2.11, 2.12_

### 2. Write preservation property tests (BEFORE implementing fixes)

- [x] 2.1 **Property 2: Preservation** - Loop Behavior with Existing Baseline
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: Loop starts normally when baseline exists (no duplicate baseline run)
  - Write property-based test: for all loop starts with existing baseline, verify loop proceeds to first iteration without running baseline again
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test PASSES (confirms baseline behavior to preserve)
  - Mark task complete when test is written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 2.2 **Property 2: Preservation** - Gate Execution with 5m Timeframe
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: Strategies with "5m" native timeframe use "5m" in all gates
  - Write property-based test: for all strategies with "5m" timeframe, verify gates use "5m"
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test PASSES (confirms baseline behavior to preserve)
  - Mark task complete when test is written, run, and passing on unfixed code
  - _Requirements: 3.4, 3.5, 3.6_

- [x] 2.3 **Property 2: Preservation** - Hard Filter Evaluation for Filters 1, 2, 4, 5
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: Filters 1, 2, 4, 5 (min_trade_count, max_drawdown, profit_factor_floor, expectancy_floor) work correctly
  - Write property-based test: for all Gate 1 completions, verify filters 1, 2, 4, 5 are evaluated correctly
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test PASSES (confirms baseline behavior to preserve)
  - Mark task complete when test is written, run, and passing on unfixed code
  - _Requirements: 3.2, 3.7, 3.8_

- [x] 2.4 **Property 2: Preservation** - UI State Management
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: Iteration history, stat cards, and progress bar update correctly
  - Write property-based test: for all iteration completions, verify UI updates correctly
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test PASSES (confirms baseline behavior to preserve)
  - Mark task complete when test is written, run, and passing on unfixed code
  - _Requirements: 3.9, 3.10_

---

## Phase 2: Implementation (Surgical Fixes)

### 3. Fix Bug 2: Strategy-Native Timeframe (Simplest, No Dependencies)

- [x] 3.1 Detect and populate strategy native timeframe
  - Open `app/ui/pages/loop_page.py`
  - Locate `_on_start()` method (around line 1800)
  - After creating `LoopConfig`, add timeframe detection:
    ```python
    from app.core.freqtrade.resolvers.strategy_resolver import detect_strategy_timeframe
    settings = self._settings_state.settings_service.load_settings()
    native_timeframe = detect_strategy_timeframe(settings, strategy_name)
    if native_timeframe:
        config.timeframe = native_timeframe
        _log.info("Detected strategy native timeframe: %s", native_timeframe)
    ```
  - _Bug_Condition: isBugCondition2(input) where strategy_native_timeframe != "5m"_
  - _Expected_Behavior: All gates use strategy's native timeframe_
  - _Preservation: Strategies with "5m" timeframe continue to use "5m"_
  - _Requirements: 2.3, 2.4, 3.4_

  - [x] 3.1.1 Verify Bug 2 exploration test now passes
    - **Property 1: Expected Behavior** - Strategy-Native Timeframe
    - **IMPORTANT**: Re-run the SAME test from task 1.2 - do NOT write a new test
    - Run test from step 1.2
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.3, 2.4_

  - [x] 3.1.2 Verify preservation tests still pass
    - **Property 2: Preservation** - Gate Execution with 5m Timeframe
    - **IMPORTANT**: Re-run the SAME test from task 2.2 - do NOT write a new test
    - Run test from step 2.2
    - **EXPECTED OUTCOME**: Test PASSES (confirms no regressions)

### 4. Fix Bug 3: IS/OOS Split Verification (Document if Correct)

- [x] 4.1 Verify and document IS/OOS split behavior
  - Open `app/core/services/loop_service.py`
  - Locate `compute_in_sample_timerange()` and `compute_oos_timerange()` methods
  - Review implementation:
    - IS ends at `oos_start - timedelta(days=1)`
    - OOS starts at `oos_start`
  - Add docstring comments to clarify split logic:
    ```python
    def compute_in_sample_timerange(self, config: LoopConfig) -> str:
        """Return the in-sample timerange used for Gate 1 and stress testing.
        
        The in-sample range ends one day before the OOS start date, ensuring
        the boundary day is excluded from in-sample and included in OOS.
        """
    ```
  - If test 1.3 passed, document that Bug 3 does not exist
  - If test 1.3 failed, implement fix to ensure boundary day is in OOS only
  - _Bug_Condition: isBugCondition3(input) where boundary_day_excluded_from_both_ranges_
  - _Expected_Behavior: Boundary day in OOS, not in IS, no gap_
  - _Preservation: All other timerange splits continue to work correctly_
  - _Requirements: 2.5, 2.6, 2.7, 3.4_

  - [x] 4.1.1 Verify Bug 3 exploration test passes (or documents correct behavior)
    - **Property 1: Expected Behavior** - Non-Overlapping IS/OOS Split
    - **IMPORTANT**: Re-run the SAME test from task 1.3 - do NOT write a new test
    - Run test from step 1.3
    - **EXPECTED OUTCOME**: Test PASSES (confirms split is correct)
    - _Requirements: 2.5, 2.6, 2.7_

### 5. Fix Bug 4: Hard-Filter Trade Data Wiring (Straightforward Parameter Passing)

- [x] 5.1 Extract and pass trades to hard filter evaluation
  - Open `app/ui/pages/loop_page.py`
  - Locate `_on_gate1_finished()` method (around line 2050)
  - Before calling `evaluate_gate1_hard_filters()`, extract trades:
    ```python
    trades = None
    if self._iteration_in_sample_results and self._iteration_in_sample_results.trades:
        trades = self._iteration_in_sample_results.trades
        _log.info("Passing %d trades to hard filter evaluation", len(trades))
    ```
  - Update the call to include trades parameter:
    ```python
    failures = self._loop_service.evaluate_gate1_hard_filters(
        gate1, config, trades  # Add trades parameter
    )
    ```
  - _Bug_Condition: isBugCondition4(input) where trades_parameter == None_
  - _Expected_Behavior: Filters 3, 6, 7 evaluated using per-trade data_
  - _Preservation: Filters 1, 2, 4, 5, 8, 9 continue to work as before_
  - _Requirements: 2.8, 2.9, 2.10, 3.2, 3.7_

  - [x] 5.1.1 Verify Bug 4 exploration test now passes
    - **Property 1: Expected Behavior** - Hard-Filter Trade Data Wiring
    - **IMPORTANT**: Re-run the SAME test from task 1.4 - do NOT write a new test
    - Run test from step 1.4
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.8, 2.9, 2.10_

  - [x] 5.1.2 Verify preservation tests still pass
    - **Property 2: Preservation** - Hard Filter Evaluation for Filters 1, 2, 4, 5
    - **IMPORTANT**: Re-run the SAME test from task 2.3 - do NOT write a new test
    - Run test from step 2.3
    - **EXPECTED OUTCOME**: Test PASSES (confirms no regressions)

### 6. Fix Bug 1: Real Baseline Backtest (Most Complex, Requires New Workflow)

- [x] 6.1 Add baseline detection logic
  - Open `app/ui/pages/loop_page.py`
  - Locate `_on_start()` method (around line 1800)
  - After creating loop config, add baseline detection:
    ```python
    needs_baseline = self._latest_diagnosis_input is None
    if needs_baseline:
        _log.info("No previous diagnosis input - running baseline backtest")
        self._run_baseline_backtest(config)
        return  # Exit early, baseline completion will trigger loop start
    ```
  - _Bug_Condition: isBugCondition1(input) where has_previous_diagnosis_input == False_
  - _Expected_Behavior: Real baseline backtest executed before first iteration_
  - _Preservation: Loops with existing baseline continue to start normally_
  - _Requirements: 2.1, 2.2, 3.1_

- [x] 6.2 Implement baseline backtest execution method
  - Add new method `_run_baseline_backtest()` to `LoopPage`:
    ```python
    def _run_baseline_backtest(self, config: LoopConfig) -> None:
        """Run a baseline backtest on the in-sample timerange before the first iteration."""
        # Create sandbox for baseline
        # Compute in-sample timerange using LoopService
        # Build backtest command for in-sample timerange
        # Execute command with callbacks
        # Store process handle for output streaming
    ```
  - Use `self._loop_service.compute_in_sample_timerange(config)` to get timerange
  - Use `self._improve_service.build_backtest_command()` to build command
  - Use `self._process_service.execute_command()` to run backtest
  - Connect stdout/stderr to terminal widget
  - Connect finished signal to `_on_baseline_backtest_finished()`
  - _Requirements: 2.1, 2.2_

- [x] 6.3 Implement baseline completion handler
  - Add new method `_on_baseline_backtest_finished()` to `LoopPage`:
    ```python
    def _on_baseline_backtest_finished(self, exit_code: int, exit_status: str) -> None:
        """Handle baseline backtest completion."""
        # Parse results from export directory
        # Store in _latest_diagnosis_input
        # Update UI to show baseline completed
        # Start the loop by calling _on_start() again
    ```
  - Use `self._improve_service.parse_backtest_results()` to parse results
  - Create `DiagnosisInput` from parsed results
  - Store in `self._latest_diagnosis_input`
  - Update status label: "Baseline backtest completed - starting loop"
  - Call `self._on_start()` again to start the loop
  - _Requirements: 2.1, 2.2_

- [x] 6.4 Update _current_diagnosis_seed() to require baseline
  - Locate `_current_diagnosis_seed()` method in `LoopPage`
  - Remove dummy creation logic
  - Raise error if no baseline exists:
    ```python
    def _current_diagnosis_seed(self, config: LoopConfig) -> Tuple[BacktestSummary, Optional[object]]:
        """Return the latest usable diagnosis seed for the next iteration."""
        self._ensure_loop_runtime_state()
        if self._latest_diagnosis_input is not None:
            return self._latest_diagnosis_input.in_sample, self._latest_diagnosis_input
        raise RuntimeError("No baseline diagnosis input available - baseline backtest must be run first")
    ```
  - _Requirements: 2.1, 2.2_

  - [x] 6.4.1 Verify Bug 1 exploration test now passes
    - **Property 1: Expected Behavior** - Real Baseline Backtest
    - **IMPORTANT**: Re-run the SAME test from task 1.1 - do NOT write a new test
    - Run test from step 1.1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2_

  - [x] 6.4.2 Verify preservation tests still pass
    - **Property 2: Preservation** - Loop Behavior with Existing Baseline
    - **IMPORTANT**: Re-run the SAME test from task 2.1 - do NOT write a new test
    - Run test from step 2.1
    - **EXPECTED OUTCOME**: Test PASSES (confirms no regressions)

### 7. Fix Bug 5: Code Cleanup (Final Cleanup After All Fixes Working)

- [x] 7.1 Remove duplicate methods from loop_page.py
  - Review duplicates identified in task 1.5
  - For each duplicate:
    - Verify canonical implementation is correct
    - Remove old/compatibility version
    - Update all call sites to use canonical version
  - Search for methods with `_old`, `_new`, `_compat` suffixes
  - Remove compatibility wrappers that delegate to other methods
  - _Bug_Condition: isBugCondition5(input) where duplicate_methods_exist_
  - _Expected_Behavior: Only canonical implementations remain_
  - _Preservation: All method calls continue to work correctly_
  - _Requirements: 2.11, 2.12_

- [x] 7.2 Remove duplicate methods from loop_service.py
  - Review duplicates identified in task 1.5
  - For each duplicate:
    - Verify canonical implementation is correct
    - Remove old/compatibility version
    - Update all call sites to use canonical version
  - Search for methods with `_old`, `_new`, `_compat` suffixes
  - Remove compatibility wrappers that delegate to other methods
  - _Requirements: 2.11, 2.12_

- [x] 7.3 Add documentation comments for canonical methods
  - Add docstring comments to clarify which methods are canonical
  - Document any method naming conventions
  - Update module-level docstrings if needed
  - _Requirements: 2.11, 2.12_

  - [x] 7.3.1 Verify all method calls work after cleanup
    - **Property 2: Preservation** - Method Call Behavior
    - Run all preservation tests from Phase 1
    - **EXPECTED OUTCOME**: All tests PASS (confirms no regressions)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_

---

## Phase 3: Integration Testing

### 8. Checkpoint - Ensure all tests pass

- [x] 8.1 Run all exploration tests (should now pass)
  - Re-run tests from tasks 1.1, 1.2, 1.3, 1.4
  - Verify all tests pass (confirming bugs are fixed)
  - Document any remaining failures

- [x] 8.2 Run all preservation tests (should still pass)
  - Re-run tests from tasks 2.1, 2.2, 2.3, 2.4
  - Verify all tests pass (confirming no regressions)
  - Document any failures

- [x] 8.3 Run full loop integration test
  - Start loop with no previous baseline
  - Verify baseline backtest runs automatically
  - Verify first iteration uses real baseline data
  - Verify all gates use correct timeframe
  - Verify hard filters 3, 6, 7 are evaluated
  - Verify loop completes successfully

- [x] 8.4 Ask user for confirmation
  - Present test results to user
  - Ask if any issues need to be addressed
  - Confirm all fixes are working as expected

---

## Notes

- **Test Execution Order**: Exploration tests (Phase 1) MUST be run BEFORE implementing fixes (Phase 2)
- **Property-Based Testing**: Use Hypothesis library for property-based tests where applicable
- **Preservation Testing**: Follow observation-first methodology - observe unfixed behavior first, then write tests
- **Bug Condition Methodology**: Each fix validates against bug condition (C), expected behavior (P), and preservation (¬C)
- **Implementation Order**: Fixes are ordered by complexity and dependencies (Bug 2 → Bug 3 → Bug 4 → Bug 1 → Bug 5)
