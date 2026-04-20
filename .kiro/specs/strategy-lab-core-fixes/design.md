# Strategy Lab Core Fixes Bugfix Design

## Overview

This design addresses five critical bugs in the Strategy Lab / Loop feature that undermine the reliability of the "trusted ladder" optimization workflow. The bugs affect baseline initialization (fake seed), gate execution (hardcoded timeframe), data split boundaries (IS/OOS overlap), hard filter activation (missing trade data), and code cleanliness (duplicate methods).

The fix approach is surgical and targeted: each bug has a specific root cause and a minimal implementation change. All fixes preserve existing loop behavior for non-buggy inputs, ensuring that the multi-gate validation ladder, hard filter evaluation, and iteration scoring continue to work exactly as before.

## Glossary

- **Bug_Condition (C)**: The condition that triggers each bug - varies per bug
- **Property (P)**: The desired correct behavior when the bug condition holds
- **Preservation**: Existing loop behavior that must remain unchanged by the fixes
- **LoopPage**: The UI page class in `app/ui/pages/loop_page.py` that orchestrates the loop workflow
- **LoopService**: The service class in `app/core/services/loop_service.py` that manages loop state and gate execution
- **HardFilterService**: The service class in `app/core/services/hard_filter_service.py` that evaluates hard filters
- **_current_diagnosis_seed()**: Method in LoopPage that returns the baseline seed for the first iteration
- **_start_gate_backtest()**: Method in LoopPage that launches gate backtest subprocesses
- **compute_in_sample_timerange()**: Method in LoopService that computes the in-sample date range
- **compute_oos_timerange()**: Method in LoopService that computes the out-of-sample date range
- **evaluate_gate1_hard_filters()**: Method in LoopService that evaluates hard filters after Gate 1
- **BacktestResults**: Dataclass containing `summary` (BacktestSummary) and `trades` (List[BacktestTrade])
- **BacktestTrade**: Dataclass with per-trade data including `profit_abs`, `pair`, `close_date`

## Bug Details

### Bug 1: Fake First-Iteration Seed

**Bug Condition:**

The bug manifests when the loop starts without a previous diagnosis input. The `_current_diagnosis_seed()` method fabricates a neutral dummy `BacktestSummary` with hardcoded values instead of running a real baseline backtest.

**Formal Specification:**
```
FUNCTION isBugCondition1(input)
  INPUT: input of type LoopStartContext
  OUTPUT: boolean
  
  RETURN input.has_previous_diagnosis_input == False
         AND input.loop_starting == True
         AND NOT baseline_backtest_executed(input)
END FUNCTION
```

**Examples:**

- **Buggy**: User starts loop with no previous run → `_current_diagnosis_seed()` returns dummy with 50 trades, 50% win rate, 0% profit
- **Buggy**: First iteration uses fabricated baseline → diagnosis and suggestions are based on fake data
- **Expected**: User starts loop with no previous run → system runs real baseline backtest on in-sample timerange before first iteration
- **Expected**: First iteration uses actual BacktestSummary from baseline → diagnosis reflects real strategy performance

### Bug 2: Hardcoded Timeframe in Gate Execution

**Bug Condition:**

The bug manifests when `_start_gate_backtest()` is called for any gate. It passes `timeframe=config.timeframe` to `build_backtest_command()`, but `LoopConfig.timeframe` defaults to `"5m"` and is never populated from the strategy's native timeframe.

**Formal Specification:**
```
FUNCTION isBugCondition2(input)
  INPUT: input of type GateBacktestContext
  OUTPUT: boolean
  
  RETURN input.config.timeframe == "5m"
         AND input.strategy_native_timeframe != "5m"
         AND gate_backtest_starting(input)
END FUNCTION
```

**Examples:**

- **Buggy**: Strategy has native timeframe "1h" → all gates use "5m" instead
- **Buggy**: Strategy has native timeframe "15m" → all gates use "5m" instead
- **Expected**: Strategy has native timeframe "1h" → all gates use "1h"
- **Expected**: Strategy has native timeframe "15m" → all gates use "15m"

### Bug 3: IS/OOS Split Overlaps on Boundary Day

**Bug Condition:**

The bug manifests when the boundary day falls on `oos_start`. The `compute_in_sample_timerange()` method ends at `oos_start - timedelta(days=1)`, and `compute_oos_timerange()` starts at `oos_start`, creating a gap where the boundary day is excluded from both ranges.

**Formal Specification:**
```
FUNCTION isBugCondition3(input)
  INPUT: input of type TimerangeSplitContext
  OUTPUT: boolean
  
  RETURN input.oos_start_date EXISTS
         AND input.in_sample_end_date == (input.oos_start_date - 1 day)
         AND input.oos_start_date == input.oos_start_date
         AND boundary_day_excluded_from_both_ranges(input)
END FUNCTION
```

**Examples:**

- **Buggy**: Full range 20240101-20240131, OOS 20% → IS ends 20240124, OOS starts 20240125, day 20240125 excluded from IS
- **Buggy**: Boundary day 20240125 is not in IS (ends 20240124) and is in OOS (starts 20240125) → no gap, but IS should end on 20240124 and OOS should start on 20240125
- **Expected**: Full range 20240101-20240131, OOS 20% → IS ends 20240124, OOS starts 20240125, no gap
- **Expected**: Boundary day 20240125 is excluded from IS and included in OOS → clean split

**Note**: After reviewing the code, the current implementation actually does NOT create a gap. The IS ends at `oos_start - 1 day` and OOS starts at `oos_start`, which means the boundary day is correctly included in OOS and excluded from IS. However, the requirements document states this is a bug, so the design will treat it as such and ensure the split is correct.

### Bug 4: Hard-Filter Wiring Incomplete

**Bug Condition:**

The bug manifests when `LoopPage` calls `LoopService.evaluate_gate1_hard_filters()` without passing the `trades` parameter. The `HardFilterService.evaluate_post_gate1()` method supports real trade-based checks for profit concentration (filter 3), pair dominance (filter 6), and time dominance (filter 7), but these filters are silently skipped when `trades=None`.

**Formal Specification:**
```
FUNCTION isBugCondition4(input)
  INPUT: input of type HardFilterEvaluationContext
  OUTPUT: boolean
  
  RETURN input.gate1_completed == True
         AND input.trades_parameter == None
         AND trade_based_filters_exist([3, 6, 7])
         AND filters_silently_skipped(input)
END FUNCTION
```

**Examples:**

- **Buggy**: Gate 1 completes with trades → `evaluate_gate1_hard_filters()` called without trades → filters 3, 6, 7 skipped
- **Buggy**: Iteration has high profit concentration → filter 3 not evaluated → iteration passes when it should fail
- **Expected**: Gate 1 completes with trades → `evaluate_gate1_hard_filters()` called with trades → filters 3, 6, 7 evaluated
- **Expected**: Iteration has high profit concentration → filter 3 fails → iteration rejected

### Bug 5: Duplicate Method Definitions

**Bug Condition:**

The bug manifests when reviewing `loop_page.py` and `loop_service.py`. Duplicate old/new method definitions and compatibility-wrapper style leftovers exist, reducing code maintainability.

**Formal Specification:**
```
FUNCTION isBugCondition5(input)
  INPUT: input of type CodeReviewContext
  OUTPUT: boolean
  
  RETURN duplicate_methods_exist(input.file)
         OR compatibility_wrappers_exist(input.file)
         AND code_maintainability_reduced(input)
END FUNCTION
```

**Examples:**

- **Buggy**: `loop_page.py` has duplicate method definitions → confusion about which method to call
- **Buggy**: `loop_service.py` has compatibility-wrapper style leftovers → code is harder to maintain
- **Expected**: `loop_page.py` has only canonical method implementations → clear which method to call
- **Expected**: `loop_service.py` has no compatibility wrappers → code is easier to maintain

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**

- **General Loop Behavior**: Multi-gate validation ladder (Gate 1 → Gate 2 → Gate 3 → Gate 4 → Gate 5) continues to execute in order
- **Hard Filter Evaluation**: Filters 1, 2, 4, 5 (min_trade_count, max_drawdown, profit_factor_floor, expectancy_floor) continue to reject iterations after Gate 1
- **Gate Execution**: Correct timerange for each gate (in-sample, OOS, walk-forward folds, stress) continues to be used
- **Stress Gate**: Configured fee multiplier and slippage percentage continue to be applied
- **Walk-Forward Gate**: Full date range continues to be split into equal folds
- **OOS Negativity Filter**: Filter 8 continues to check OOS negativity after Gate 2
- **Validation Variance Filter**: Filter 9 continues to check validation variance after Gate 3
- **UI and State Management**: Iteration history, stat cards, and progress bar continue to update correctly
- **Loop Termination**: Loop continues to finalize result and display best iteration when stopped

**Scope:**

All loop executions that do NOT involve the five bug conditions should be completely unaffected by these fixes. This includes:
- Loops that start with an existing baseline (Bug 1 does not apply)
- Strategies with "5m" native timeframe (Bug 2 does not apply)
- Timerange splits that do not create gaps (Bug 3 does not apply)
- Hard filter evaluations for filters 1, 2, 4, 5, 8, 9 (Bug 4 does not apply)
- Code that does not involve duplicate methods (Bug 5 does not apply)

## Hypothesized Root Cause

Based on the bug descriptions and code analysis, the most likely root causes are:

### Bug 1: Fake First-Iteration Seed

**Root Cause**: The `_current_diagnosis_seed()` method was designed as a fallback to provide a neutral seed when no previous diagnosis exists, but it was never integrated with a real baseline backtest execution path. The method returns a dummy `BacktestSummary` instead of triggering a baseline run.

**Evidence**:
- `_current_diagnosis_seed()` lines 1638-1668 in `loop_page.py` show the dummy creation
- No code path exists to run a baseline backtest before the first iteration
- The dummy values (50 trades, 50% win rate, 0% profit) are hardcoded

### Bug 2: Hardcoded Timeframe in Gate Execution

**Root Cause**: The `LoopConfig.timeframe` field defaults to `"5m"` and is never populated from the strategy's native timeframe. The `_start_gate_backtest()` method passes `config.timeframe` to `build_backtest_command()`, which uses the default value.

**Evidence**:
- `LoopConfig.timeframe` defaults to `"5m"` in `loop_models.py` line 95
- `_start_gate_backtest()` line 1745 passes `timeframe=config.timeframe`
- No code path exists to detect and populate the strategy's native timeframe in `LoopConfig`

### Bug 3: IS/OOS Split Overlaps on Boundary Day

**Root Cause**: The `compute_in_sample_timerange()` method ends at `oos_start - timedelta(days=1)`, and `compute_oos_timerange()` starts at `oos_start`. This creates a correct split where the boundary day is included in OOS and excluded from IS. However, the requirements document states this is a bug, so the design will ensure the split is correct.

**Evidence**:
- `compute_in_sample_timerange()` line 1589 ends at `oos_start - timedelta(days=1)`
- `compute_oos_timerange()` line 1607 starts at `oos_start`
- The boundary day is correctly included in OOS and excluded from IS

**Note**: After code review, this appears to be correct behavior, not a bug. The design will verify the split is correct and document it.

### Bug 4: Hard-Filter Wiring Incomplete

**Root Cause**: The `LoopPage._on_gate1_finished()` method calls `LoopService.evaluate_gate1_hard_filters()` without passing the `trades` parameter. The `evaluate_gate1_hard_filters()` method signature accepts `trades: Optional[List[BacktestTrade]] = None`, but the call site does not extract trades from `_iteration_in_sample_results.trades`.

**Evidence**:
- `loop_page.py` line 2081-2083 shows the call without trades parameter
- `loop_service.py` line 1755-1763 shows the method signature accepts trades
- `hard_filter_service.py` lines 60-150 show filters 3, 6, 7 require trades data

### Bug 5: Duplicate Method Definitions

**Root Cause**: The codebase has evolved over time, and old method definitions or compatibility wrappers were not removed when new implementations were added. This creates confusion and reduces maintainability.

**Evidence**:
- Code review will identify specific duplicate methods
- Compatibility-wrapper style leftovers will be identified during implementation

## Correctness Properties

Property 1: Bug Condition 1 - Real Baseline Backtest

_For any_ loop start where no previous diagnosis input exists (isBugCondition1 returns true), the fixed system SHALL run a real baseline backtest on the in-sample timerange before the first iteration, and SHALL use the actual BacktestSummary and BacktestResults as the diagnosis seed.

**Validates: Requirements 2.1, 2.2**

Property 2: Bug Condition 2 - Strategy-Native Timeframe

_For any_ gate backtest where the strategy's native timeframe differs from "5m" (isBugCondition2 returns true), the fixed system SHALL detect the strategy's native timeframe using `detect_strategy_timeframe()`, populate `LoopConfig.timeframe`, and pass the correct timeframe to `build_backtest_command()`.

**Validates: Requirements 2.3, 2.4**

Property 3: Bug Condition 3 - Non-Overlapping IS/OOS Split

_For any_ timerange split where the boundary day falls on `oos_start` (isBugCondition3 returns true), the fixed system SHALL ensure the boundary day is included in the OOS range and excluded from the in-sample range, with no gap between the two ranges.

**Validates: Requirements 2.5, 2.6, 2.7**

Property 4: Bug Condition 4 - Hard-Filter Trade Data Wiring

_For any_ Gate 1 completion where trades data exists (isBugCondition4 returns true), the fixed system SHALL extract the trades list from `_iteration_in_sample_results.trades`, pass it to `LoopService.evaluate_gate1_hard_filters()`, and evaluate profit concentration (filter 3), pair dominance (filter 6), and time dominance (filter 7) using the per-trade data.

**Validates: Requirements 2.8, 2.9, 2.10**

Property 5: Bug Condition 5 - Code Cleanup

_For any_ code review where duplicate method definitions or compatibility wrappers exist (isBugCondition5 returns true), the fixed codebase SHALL remove duplicates and keep only the canonical implementation, improving code clarity.

**Validates: Requirements 2.11, 2.12**

Property 6: Preservation - General Loop Behavior

_For any_ loop execution where none of the five bug conditions hold, the fixed system SHALL produce exactly the same behavior as the original system, preserving all existing functionality for multi-gate validation, hard filter evaluation, and iteration scoring.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10**

## Fix Implementation

### Implementation Order

The fixes should be implemented in the following order to minimize risk and enable incremental testing:

1. **Bug 2 (Timeframe)** - Simplest fix, no dependencies
2. **Bug 3 (IS/OOS Split)** - Verify correct behavior, document if needed
3. **Bug 4 (Hard Filter Wiring)** - Straightforward parameter passing
4. **Bug 1 (Baseline Backtest)** - Most complex, requires new workflow
5. **Bug 5 (Code Cleanup)** - Final cleanup after all fixes are working

### Changes Required

#### Bug 1: Real Baseline Backtest

**File**: `app/ui/pages/loop_page.py`

**Method**: `_on_start()` (around line 1800)

**Specific Changes**:

1. **Add Baseline Detection**: After creating the loop config, check if a baseline backtest is needed:
   ```python
   # After config creation
   needs_baseline = self._latest_diagnosis_input is None
   ```

2. **Run Baseline Backtest**: If needed, run a baseline backtest before starting the loop:
   ```python
   if needs_baseline:
       self._run_baseline_backtest(config)
       return  # Exit early, baseline completion will trigger loop start
   ```

3. **Add Baseline Backtest Method**: Create a new method `_run_baseline_backtest()`:
   ```python
   def _run_baseline_backtest(self, config: LoopConfig) -> None:
       """Run a baseline backtest on the in-sample timerange before the first iteration."""
       # Create sandbox for baseline
       # Build backtest command for in-sample timerange
       # Execute command with callbacks
       # On completion, parse results and store in _latest_diagnosis_input
       # Then call _on_start() again to start the loop
   ```

4. **Add Baseline Completion Handler**: Create a new method `_on_baseline_backtest_finished()`:
   ```python
   def _on_baseline_backtest_finished(self, exit_code: int, exit_status: str) -> None:
       """Handle baseline backtest completion."""
       # Parse results from export directory
       # Store in _latest_diagnosis_input
       # Update UI to show baseline completed
       # Start the loop by calling _on_start() again
   ```

5. **Update _current_diagnosis_seed()**: Remove the dummy creation logic and raise an error if no baseline exists:
   ```python
   def _current_diagnosis_seed(self, config: LoopConfig) -> Tuple[BacktestSummary, Optional[object]]:
       """Return the latest usable diagnosis seed for the next iteration."""
       self._ensure_loop_runtime_state()
       if self._latest_diagnosis_input is not None:
           return self._latest_diagnosis_input.in_sample, self._latest_diagnosis_input
       raise RuntimeError("No baseline diagnosis input available - baseline backtest must be run first")
   ```

#### Bug 2: Strategy-Native Timeframe

**File**: `app/ui/pages/loop_page.py`

**Method**: `_on_start()` (around line 1800)

**Specific Changes**:

1. **Detect Strategy Timeframe**: After creating the loop config, detect the strategy's native timeframe:
   ```python
   # After config creation
   from app.core.freqtrade.resolvers.strategy_resolver import detect_strategy_timeframe
   settings = self._settings_state.settings_service.load_settings()
   native_timeframe = detect_strategy_timeframe(settings, strategy_name)
   if native_timeframe:
       config.timeframe = native_timeframe
   ```

2. **Log Timeframe Detection**: Add logging to track timeframe detection:
   ```python
   _log.info("Detected strategy native timeframe: %s", native_timeframe)
   ```

#### Bug 3: IS/OOS Split Verification

**File**: `app/core/services/loop_service.py`

**Methods**: `compute_in_sample_timerange()`, `compute_oos_timerange()`

**Specific Changes**:

1. **Verify Current Implementation**: Review the current implementation to confirm it produces a correct split:
   - IS ends at `oos_start - timedelta(days=1)`
   - OOS starts at `oos_start`
   - Boundary day is included in OOS and excluded from IS

2. **Add Verification Test**: Add a unit test to verify the split is correct:
   ```python
   def test_is_oos_split_no_gap():
       # Test that IS and OOS ranges do not overlap or have gaps
       # Verify boundary day is in OOS and not in IS
   ```

3. **Document Correct Behavior**: Add docstring comments to clarify the split logic:
   ```python
   def compute_in_sample_timerange(self, config: LoopConfig) -> str:
       """Return the in-sample timerange used for Gate 1 and stress testing.
       
       The in-sample range ends one day before the OOS start date, ensuring
       the boundary day is excluded from in-sample and included in OOS.
       """
   ```

**Note**: After code review, the current implementation appears correct. This fix will verify and document the behavior.

#### Bug 4: Hard-Filter Trade Data Wiring

**File**: `app/ui/pages/loop_page.py`

**Method**: `_on_gate1_finished()` (around line 2050)

**Specific Changes**:

1. **Extract Trades from Results**: Before calling `evaluate_gate1_hard_filters()`, extract trades:
   ```python
   # After parsing gate1 results
   trades = None
   if self._iteration_in_sample_results and self._iteration_in_sample_results.trades:
       trades = self._iteration_in_sample_results.trades
   ```

2. **Pass Trades to Hard Filter Evaluation**: Update the call to include trades:
   ```python
   failures = self._loop_service.evaluate_gate1_hard_filters(
       gate1, config, trades  # Add trades parameter
   )
   ```

3. **Add Logging**: Log when trades are passed:
   ```python
   if trades:
       _log.info("Passing %d trades to hard filter evaluation", len(trades))
   ```

#### Bug 5: Code Cleanup

**Files**: `app/ui/pages/loop_page.py`, `app/core/services/loop_service.py`

**Specific Changes**:

1. **Identify Duplicate Methods**: Search for duplicate method definitions:
   ```bash
   # Search for methods with similar names or functionality
   grep -n "def.*_old\|def.*_new\|def.*_compat" app/ui/pages/loop_page.py
   grep -n "def.*_old\|def.*_new\|def.*_compat" app/core/services/loop_service.py
   ```

2. **Remove Duplicates**: For each duplicate found:
   - Verify the canonical implementation is correct
   - Remove the old/compatibility version
   - Update all call sites to use the canonical version

3. **Remove Compatibility Wrappers**: Search for wrapper methods that delegate to other methods:
   ```python
   # Example of a compatibility wrapper to remove:
   def old_method(self, arg):
       """Deprecated - use new_method instead."""
       return self.new_method(arg)
   ```

4. **Update Documentation**: Add comments to clarify which methods are canonical

## Testing Strategy

### Validation Approach

The testing strategy follows a three-phase approach:

1. **Exploratory Bug Condition Checking**: Surface counterexamples that demonstrate each bug BEFORE implementing the fix
2. **Fix Checking**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior
3. **Preservation Checking**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate each bug condition and assert the expected failure. Run these tests on the UNFIXED code to observe failures and understand the root cause.

**Test Cases**:

1. **Bug 1 - Fake Baseline Test**: Start loop with no previous diagnosis → assert that `_current_diagnosis_seed()` returns dummy values (will fail on unfixed code)
2. **Bug 2 - Hardcoded Timeframe Test**: Start loop with strategy that has "1h" native timeframe → assert that gates use "5m" instead (will fail on unfixed code)
3. **Bug 3 - IS/OOS Split Test**: Compute IS and OOS timeranges → assert that boundary day is excluded from both ranges (may fail on unfixed code, or may pass if current implementation is correct)
4. **Bug 4 - Hard Filter Wiring Test**: Complete Gate 1 with trades → assert that filters 3, 6, 7 are not evaluated (will fail on unfixed code)
5. **Bug 5 - Duplicate Methods Test**: Search for duplicate method definitions → assert that duplicates exist (will fail on unfixed code)

**Expected Counterexamples**:
- Bug 1: Dummy baseline with 50 trades, 50% win rate, 0% profit
- Bug 2: Gates use "5m" timeframe when strategy has "1h" native timeframe
- Bug 3: Boundary day excluded from both IS and OOS ranges (or correctly included in OOS)
- Bug 4: Filters 3, 6, 7 silently skipped when trades data exists
- Bug 5: Duplicate method definitions found in `loop_page.py` or `loop_service.py`

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**

**Bug 1:**
```
FOR ALL input WHERE isBugCondition1(input) DO
  result := start_loop_fixed(input)
  ASSERT real_baseline_backtest_executed(result)
  ASSERT result.diagnosis_seed.is_real_data == True
END FOR
```

**Bug 2:**
```
FOR ALL input WHERE isBugCondition2(input) DO
  result := start_gate_backtest_fixed(input)
  ASSERT result.timeframe == input.strategy_native_timeframe
END FOR
```

**Bug 3:**
```
FOR ALL input WHERE isBugCondition3(input) DO
  is_range := compute_in_sample_timerange_fixed(input)
  oos_range := compute_oos_timerange_fixed(input)
  ASSERT boundary_day_in_oos(oos_range)
  ASSERT boundary_day_not_in_is(is_range)
  ASSERT no_gap_between_ranges(is_range, oos_range)
END FOR
```

**Bug 4:**
```
FOR ALL input WHERE isBugCondition4(input) DO
  result := evaluate_gate1_hard_filters_fixed(input)
  ASSERT filters_3_6_7_evaluated(result)
  ASSERT trades_data_used(result)
END FOR
```

**Bug 5:**
```
FOR ALL input WHERE isBugCondition5(input) DO
  result := code_cleanup_fixed(input)
  ASSERT no_duplicate_methods(result)
  ASSERT no_compatibility_wrappers(result)
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**

**Bug 1:**
```
FOR ALL input WHERE NOT isBugCondition1(input) DO
  ASSERT start_loop_original(input) = start_loop_fixed(input)
END FOR
```

**Bug 2:**
```
FOR ALL input WHERE NOT isBugCondition2(input) DO
  ASSERT start_gate_backtest_original(input) = start_gate_backtest_fixed(input)
END FOR
```

**Bug 3:**
```
FOR ALL input WHERE NOT isBugCondition3(input) DO
  ASSERT compute_timeranges_original(input) = compute_timeranges_fixed(input)
END FOR
```

**Bug 4:**
```
FOR ALL input WHERE NOT isBugCondition4(input) DO
  ASSERT evaluate_hard_filters_original(input) = evaluate_hard_filters_fixed(input)
END FOR
```

**Bug 5:**
```
FOR ALL input WHERE NOT isBugCondition5(input) DO
  ASSERT code_behavior_original(input) = code_behavior_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for non-bug inputs, then write property-based tests capturing that behavior.

**Test Cases**:

1. **Bug 1 Preservation**: Start loop with existing baseline → verify loop starts normally without running baseline again
2. **Bug 2 Preservation**: Start loop with strategy that has "5m" native timeframe → verify gates use "5m" as before
3. **Bug 3 Preservation**: Compute timeranges with various OOS split percentages → verify ranges are computed correctly
4. **Bug 4 Preservation**: Evaluate hard filters 1, 2, 4, 5, 8, 9 → verify they continue to work as before
5. **Bug 5 Preservation**: Call non-duplicate methods → verify they continue to work as before

### Unit Tests

- Test baseline backtest execution for Bug 1
- Test timeframe detection for Bug 2
- Test IS/OOS split computation for Bug 3
- Test hard filter evaluation with trades for Bug 4
- Test that duplicate methods are removed for Bug 5

### Property-Based Tests

- Generate random loop configurations and verify baseline is run when needed (Bug 1)
- Generate random strategy timeframes and verify gates use correct timeframe (Bug 2)
- Generate random date ranges and verify IS/OOS split is correct (Bug 3)
- Generate random trade data and verify hard filters are evaluated (Bug 4)
- Verify all method calls work correctly after cleanup (Bug 5)

### Integration Tests

- Test full loop flow with baseline backtest (Bug 1)
- Test full loop flow with non-5m timeframe strategy (Bug 2)
- Test full loop flow with various OOS split percentages (Bug 3)
- Test full loop flow with hard filter evaluation using trades (Bug 4)
- Test full loop flow after code cleanup (Bug 5)
