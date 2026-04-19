# Strategy Lab Fixes Bugfix Design

## Overview

Five correctness bugs undermine the Strategy Lab's "trusted ladder" optimization workflow. This design addresses all five bugs through targeted fixes that preserve existing behavior while enforcing correct data flow, timeframe handling, filter validation, code deduplication, and timerange boundary separation.

**Bug Summary:**
1. **Fabricated First Iteration Seed** — bypasses real baseline backtest
2. **Hardcoded 5m Timeframe** — ignores strategy/user timeframe selection
3. **Placeholder Hard Filters (3/6/7)** — profit_concentration, pair_dominance, time_dominance pass by default
4. **Duplicate Method Definitions** — stale code paths in loop_page.py and loop_service.py
5. **Timerange Boundary Overlap** — in-sample and OOS windows share split day

**Fix Strategy:**
- Add real baseline backtest execution before first iteration
- Add `timeframe` field to `LoopConfig` and wire it through all gate launches
- Extend `HardFilterService.evaluate_post_gate1()` to receive `BacktestResults.trades` and compute actual filter metrics
- Delete superseded method definitions, keeping only canonical implementations
- Adjust `compute_in_sample_timerange()` to exclude `oos_start` from upper bound

## Glossary

- **Bug_Condition (C)**: The condition that triggers each bug — fabricated seed on first iteration, hardcoded "5m" in gate launches, placeholder filter logic, duplicate method definitions, overlapping timerange boundaries
- **Property (P)**: The desired behavior when bugs are fixed — real baseline backtest, correct timeframe propagation, enforced filter thresholds, single canonical method per operation, non-overlapping timeranges
- **Preservation**: Existing behavior that must remain unchanged — subsequent iterations use cached diagnosis input, all gates use same timeframe, filters 1/2/4/5/8/9 unchanged, Quick mode skips gates 3-4, walk-forward fold count unchanged
- **LoopConfig**: Configuration dataclass in `app/core/models/loop_models.py` that holds all loop parameters
- **BacktestResults**: Dataclass in `app/core/backtests/results_models.py` containing `summary: BacktestSummary` and `trades: List[BacktestTrade]`
- **HardFilterService**: Stateless service in `app/core/services/hard_filter_service.py` that evaluates nine hard filters at three interleaved points
- **_latest_diagnosis_input**: Instance variable in `LoopPage` that caches the most recent multi-gate diagnosis input for subsequent iterations
- **oos_start**: The boundary date computed as `date_to - timedelta(days=oos_days)` that separates in-sample from out-of-sample windows

## Bug Details

### Bug Condition

The bugs manifest in five distinct scenarios:

**Bug 1: Fabricated First Iteration Seed**
When `_run_next_iteration()` is called and `self._loop_service._result.iterations` is empty (first iteration), the system fabricates a neutral `BacktestSummary` with hardcoded values (50 trades, 0% profit, timeframe="5m") and passes it to `prepare_next_iteration()` instead of running a real baseline backtest.

**Bug 2: Hardcoded 5m Timeframe**
When `_start_gate_backtest()` is called for any gate (in-sample, OOS, walk-forward, stress), the system passes `timeframe="5m"` hardcoded to `build_backtest_command()` regardless of the strategy's native timeframe or user selection, because `LoopConfig` has no `timeframe` field.

**Bug 3: Placeholder Hard Filters**
When `HardFilterService.evaluate_post_gate1()` evaluates filters 3, 6, and 7:
- Filter 3 (profit_concentration): skips when `total_trades > 3` because per-trade data is unavailable
- Filter 6 (pair_dominance): always passes (comment-only implementation)
- Filter 7 (time_dominance): always passes (comment-only implementation)

**Bug 4: Duplicate Method Definitions**
When reading or modifying `loop_page.py` and `loop_service.py`, Python silently uses the later definition while earlier dead code remains:
- `loop_page.py`: `_on_start` (lines 858, 2047), `_on_stop` (lines 949, 2096), `_run_next_iteration` (lines 1009, 2103), `_on_backtest_finished` (lines 1109, 2338)
- `loop_service.py`: `_suggestions_from_structural` (lines 590, 961)

**Bug 5: Timerange Boundary Overlap**
When `compute_in_sample_timerange()` and `compute_oos_timerange()` are called for the same `LoopConfig`, both return ranges that include `oos_start`:
- In-sample: `f"{date_from}-{oos_start}"` (inclusive upper bound)
- OOS: `f"{oos_start}-{date_to}"` (inclusive lower bound)

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type (IterationContext | GateLaunchContext | FilterEvalContext | CodebaseState | TimerangeComputeContext)
  OUTPUT: boolean
  
  RETURN (
    (input.type == "IterationContext" AND input.iterations.isEmpty() AND input.uses_fabricated_seed)
    OR (input.type == "GateLaunchContext" AND input.timeframe == "5m" AND input.config.timeframe != "5m")
    OR (input.type == "FilterEvalContext" AND input.filter_name IN ["profit_concentration", "pair_dominance", "time_dominance"] AND input.passes_by_default)
    OR (input.type == "CodebaseState" AND input.has_duplicate_method_definitions)
    OR (input.type == "TimerangeComputeContext" AND input.in_sample_end == input.oos_start)
  )
END FUNCTION
```

### Examples

**Bug 1 Example:**
- **Input**: First iteration start, no previous diagnosis input
- **Current**: System creates `BacktestSummary(total_trades=50, total_profit=0.0, timeframe="5m")` and uses it as seed
- **Expected**: System runs real baseline backtest of current strategy over in-sample timerange, uses actual results as seed

**Bug 2 Example:**
- **Input**: Strategy with native timeframe "1h", user selects "15m" in UI
- **Current**: All gate backtests run with `timeframe="5m"` hardcoded
- **Expected**: All gate backtests run with `timeframe="15m"` from `LoopConfig.timeframe`

**Bug 3 Example:**
- **Input**: Backtest with 100 trades where top 3 trades contribute 75% of profit
- **Current**: Filter 3 passes by default (skipped when `total_trades > 3`)
- **Expected**: Filter 3 fails with reason "Top-3 profit share 75.0% exceeds threshold 50.0%"

**Bug 4 Example:**
- **Input**: Developer modifies `_on_start()` at line 858 in `loop_page.py`
- **Current**: Changes have no effect because line 2047 definition overrides it
- **Expected**: Only one `_on_start()` definition exists (line 2047), changes take effect immediately

**Bug 5 Example:**
- **Input**: `LoopConfig(date_from="20240101", date_to="20240131", oos_split_pct=20.0)`
- **Current**: In-sample="20240101-20240125", OOS="20240125-20240131" (Jan 25 counted twice)
- **Expected**: In-sample="20240101-20240124", OOS="20240125-20240131" (Jan 25 only in OOS)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Subsequent iterations (after first) continue to use cached `_latest_diagnosis_input` without additional baseline backtests
- All gates within one iteration continue to use the same timeframe without alteration
- Filters 1, 2, 4, 5 (min_trade_count, max_drawdown, profit_factor_floor, expectancy_floor) continue to enforce thresholds exactly as implemented
- Filters 8, 9 (oos_negativity, validation_variance) continue to enforce thresholds after Gates 2 and 3
- Quick validation mode continues to skip walk-forward and stress gates
- Walk-forward fold count continues to match `config.walk_forward_folds`
- Loop stop/max_iterations behavior continues to surface best iteration for user acceptance

**Scope:**
All inputs that do NOT involve the five bug conditions should be completely unaffected by this fix. This includes:
- Non-first iterations (already have diagnosis input)
- Strategies where timeframe happens to be "5m" (no observable change)
- Backtests that pass filters 3/6/7 under correct implementation
- Code paths that don't involve duplicate methods
- Timeranges where boundary overlap doesn't affect results

## Hypothesized Root Cause

Based on the bug descriptions, the most likely issues are:

1. **Fabricated Seed**: The first-iteration logic was designed to avoid a cold-start problem but never implemented the actual baseline backtest execution. The dummy seed was intended as a temporary placeholder.

2. **Hardcoded Timeframe**: `LoopConfig` was created before timeframe selection was added to the UI. The hardcoded "5m" was a default that was never replaced with a configurable field.

3. **Placeholder Filters**: Filters 3, 6, 7 were designed before `BacktestResults.trades` was available in the data flow. The placeholder logic was added with TODO comments but never completed.

4. **Duplicate Methods**: Refactoring from the old single-gate loop to the new multi-gate ladder left compatibility wrappers and old method definitions in place. The later definitions override earlier ones, but the dead code was never deleted.

5. **Timerange Overlap**: The boundary calculation uses inclusive string formatting (`f"{date_from}-{oos_start}"`) without considering that Freqtrade interprets both boundaries as inclusive. The fix requires making the in-sample upper bound exclusive by subtracting one day.

## Correctness Properties

Property 1: Bug Condition - Real Baseline Backtest on First Iteration

_For any_ loop start where no previous diagnosis input exists (first iteration), the fixed system SHALL execute a real baseline backtest of the current strategy over the in-sample timerange and use the resulting `BacktestSummary` as the mutation seed before generating parameter suggestions.

**Validates: Requirements 2.1**

Property 2: Bug Condition - Correct Timeframe Propagation

_For any_ gate backtest launch, the fixed system SHALL pass the timeframe stored in `LoopConfig.timeframe` (populated from strategy detection or user selection) to `build_backtest_command()`, ensuring all gates use a consistent, correct timeframe.

**Validates: Requirements 2.2**

Property 3: Bug Condition - Enforced Hard Filters 3/6/7

_For any_ post-Gate-1 filter evaluation, the fixed system SHALL compute actual filter metrics using per-trade and per-pair data from `BacktestResults.trades`, and SHALL fail filters 3, 6, 7 when their respective thresholds are exceeded.

**Validates: Requirements 2.3, 2.4, 2.5**

Property 4: Bug Condition - Single Canonical Method Definitions

_For any_ method in `loop_page.py` or `loop_service.py`, the fixed codebase SHALL contain only one active implementation, with all superseded compatibility wrappers and duplicate definitions removed.

**Validates: Requirements 2.6**

Property 5: Bug Condition - Non-Overlapping Timeranges

_For any_ `LoopConfig` with configured date range, the fixed system SHALL return non-overlapping in-sample and OOS timeranges such that the in-sample range ends on the day before `oos_start` and the OOS range starts on `oos_start`.

**Validates: Requirements 2.7**

Property 6: Preservation - Cached Diagnosis Input for Subsequent Iterations

_For any_ loop iteration after the first where `_latest_diagnosis_input` is not None, the fixed system SHALL produce exactly the same behavior as the original system, using the cached diagnosis input without running additional baseline backtests.

**Validates: Requirements 3.1**

Property 7: Preservation - Consistent Timeframe Across Gates

_For any_ loop iteration where `LoopConfig.timeframe` is correctly populated, the fixed system SHALL produce exactly the same behavior as the original system, passing the same timeframe to every gate without alteration.

**Validates: Requirements 3.2**

Property 8: Preservation - Unchanged Filter Logic for Filters 1/2/4/5/8/9

_For any_ filter evaluation that does NOT involve filters 3, 6, or 7, the fixed system SHALL produce exactly the same pass/fail result as the original system, with no change to thresholds or logic.

**Validates: Requirements 3.3, 3.4**

Property 9: Preservation - Quick Mode Gate Skipping

_For any_ loop run in Quick validation mode, the fixed system SHALL produce exactly the same behavior as the original system, skipping walk-forward and stress gates and producing a result using only in-sample and OOS gates.

**Validates: Requirements 3.5**

Property 10: Preservation - Walk-Forward Fold Count

_For any_ `LoopConfig` with configured walk-forward folds, the fixed system SHALL produce exactly the same number of fold timeranges as the original system, matching `config.walk_forward_folds`.

**Validates: Requirements 3.6**

## Fix Implementation

### Changes Required

The fix requires changes to five files in a specific order to maintain data flow integrity:

#### File 1: `app/core/models/loop_models.py`

**Function**: Add `timeframe` field to `LoopConfig`

**Specific Changes**:
1. **Add timeframe field**: Insert `timeframe: str = "5m"` after line 95 (after `strategy: str`)
   - Default value "5m" preserves backward compatibility
   - Field will be populated from strategy detection or UI selection

**Rationale**: This is the foundation change — all other fixes depend on `LoopConfig` carrying the timeframe.

#### File 2: `app/ui/pages/loop_page.py`

**Function**: Populate `LoopConfig.timeframe`, execute real baseline backtest on first iteration, delete duplicate methods

**Specific Changes**:
1. **Populate timeframe in `_build_loop_config()`** (around line 800):
   - Detect strategy timeframe using `StrategyResolver.detect_strategy_timeframe(strategy_py)`
   - Add `timeframe=detected_timeframe` to `LoopConfig` constructor
   - Fallback to "5m" if detection fails

2. **Add baseline backtest execution in `_run_next_iteration()`** (around line 1009):
   - Replace fabricated dummy seed logic with real backtest execution
   - Check if `self._loop_service._result.iterations` is empty (first iteration)
   - If first iteration: call `_start_baseline_backtest()` instead of `prepare_next_iteration(dummy)`
   - Add new method `_start_baseline_backtest()` that launches a backtest over in-sample timerange
   - Add new callback `_on_baseline_backtest_finished()` that parses results and calls `prepare_next_iteration(real_summary)`

3. **Wire timeframe through gate launches** (lines 1028, 1083, 1887, 1984):
   - Replace all `timeframe="5m"` with `timeframe=config.timeframe`
   - Affects: dummy seed creation (line 1028), `build_backtest_command` (line 1083), `_current_diagnosis_seed` (line 1887), `_start_gate_backtest` (line 1984)

4. **Delete duplicate method definitions**:
   - Delete `_on_start` at line 858 (keep line 2047 version)
   - Delete `_on_stop` at line 949 (keep line 2096 version)
   - Delete `_run_next_iteration` at line 1009 (keep line 2103 version)
   - Delete `_on_backtest_finished` at line 1109 (keep line 2338 version)
   - Verify no references to deleted methods exist

**Rationale**: LoopPage orchestrates the loop execution and is responsible for launching backtests and wiring callbacks.

#### File 3: `app/core/services/loop_service.py`

**Function**: Fix timerange boundary overlap, delete duplicate method

**Specific Changes**:
1. **Fix `compute_in_sample_timerange()`** (line 1942):
   - Change return statement from `f"{date_from}-{oos_start}"` to `f"{date_from}-{(oos_start - timedelta(days=1)).strftime('%Y%m%d')}"`
   - This makes the in-sample upper bound exclusive (ends day before oos_start)

2. **Delete duplicate `_suggestions_from_structural`**:
   - Delete method at line 590 (keep line 961 version which has full structural pattern mapping)
   - Verify no references to deleted method exist

**Rationale**: LoopService computes timeranges and must ensure non-overlapping boundaries.

#### File 4: `app/core/services/hard_filter_service.py`

**Function**: Implement filters 3, 6, 7 with real data

**Specific Changes**:
1. **Extend `evaluate_post_gate1()` signature** (line 28):
   - Add parameter `trades: Optional[List[BacktestTrade]] = None` after `config: LoopConfig`
   - Import `BacktestTrade` from `app.core.backtests.results_models`

2. **Implement Filter 3: profit_concentration** (around line 85):
   - Replace placeholder logic with real computation
   - If `trades` is None or empty, skip filter (pass by default)
   - Sort trades by `profit_abs` descending
   - Sum top 3 trades' `profit_abs`, divide by total profit_abs across all trades
   - Fail if ratio > `config.profit_concentration_threshold`

3. **Implement Filter 6: pair_dominance** (around line 100):
   - Replace comment-only implementation with real computation
   - If `trades` is None or empty, skip filter (pass by default)
   - Group trades by `pair`, sum `profit_abs` per pair
   - Find max pair profit share (max_pair_profit / total_profit)
   - Fail if share > `config.pair_dominance_threshold`

4. **Implement Filter 7: time_dominance** (around line 110):
   - Replace comment-only implementation with real computation
   - If `trades` is None or empty, skip filter (pass by default)
   - Parse `close_date` from trades, bucket by hour-of-day (0-23)
   - Sum `profit_abs` per hour bucket
   - Find max hour profit share (max_hour_profit / total_profit)
   - Fail if share > `config.time_dominance_threshold`

**Rationale**: HardFilterService must receive per-trade data to compute actual filter metrics.

#### File 5: `app/ui/pages/loop_page.py` (second pass)

**Function**: Wire `BacktestResults.trades` into `HardFilterService.evaluate_post_gate1()` call

**Specific Changes**:
1. **Locate call to `HardFilterService.evaluate_post_gate1()`** (search for "evaluate_post_gate1"):
   - Add `trades=self._iteration_in_sample_results.trades` parameter
   - Ensure `self._iteration_in_sample_results` is a `BacktestResults` object (not just `BacktestSummary`)

**Rationale**: This completes the data flow from parsed backtest results through to filter evaluation.

### Implementation Order

The changes must be applied in this strict sequence to avoid breaking intermediate states:

1. **Phase 1: Foundation** — Add `timeframe` field to `LoopConfig` (File 1)
2. **Phase 2: Timeframe Wiring** — Populate and propagate timeframe in LoopPage (File 2, changes 1 and 3)
3. **Phase 3: Baseline Backtest** — Add real baseline execution on first iteration (File 2, change 2)
4. **Phase 4: Timerange Fix** — Fix boundary overlap in LoopService (File 3, change 1)
5. **Phase 5: Filter Implementation** — Implement filters 3/6/7 in HardFilterService (File 4)
6. **Phase 6: Filter Data Flow** — Wire trades into filter evaluation (File 5)
7. **Phase 7: Code Cleanup** — Delete duplicate methods (File 2, change 4; File 3, change 2)

## Testing Strategy

### Validation Approach

The testing strategy follows a three-phase approach: first, surface counterexamples that demonstrate each bug on unfixed code; second, verify the fix works correctly for all bug conditions; third, verify preservation of existing behavior for all non-buggy inputs.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate all five bugs BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate each bug condition and assert the defective behavior. Run these tests on the UNFIXED code to observe failures and understand the root causes.

**Test Cases**:
1. **Fabricated Seed Test**: Start a loop with no previous diagnosis input, capture the seed passed to `prepare_next_iteration()` (will show fabricated dummy on unfixed code)
2. **Hardcoded Timeframe Test**: Start a loop with strategy timeframe "1h", capture the timeframe passed to `build_backtest_command()` (will show "5m" on unfixed code)
3. **Placeholder Filter Test**: Run a backtest with 100 trades where top 3 contribute 75% of profit, evaluate filter 3 (will pass on unfixed code)
4. **Duplicate Method Test**: Modify `_on_start()` at line 858, verify which definition is active (will show line 2047 overrides on unfixed code)
5. **Timerange Overlap Test**: Compute in-sample and OOS ranges for same config, check if boundaries overlap (will show overlap on unfixed code)

**Expected Counterexamples**:
- First iteration uses `BacktestSummary(total_trades=50, total_profit=0.0, timeframe="5m")` instead of real baseline
- All gate backtests use `timeframe="5m"` regardless of strategy/config
- Filters 3, 6, 7 pass by default even when thresholds are exceeded
- Earlier method definitions are dead code, later definitions override
- In-sample and OOS ranges both include `oos_start` date

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed system produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := fixed_system(input)
  ASSERT expectedBehavior(result)
END FOR
```

**Test Cases**:
1. **Real Baseline Test**: Start loop with no diagnosis input, verify real backtest is executed and results are used as seed
2. **Correct Timeframe Test**: Start loop with strategy timeframe "1h", verify all gates use "1h"
3. **Enforced Filter 3 Test**: Run backtest with top-3 profit share 75%, verify filter 3 fails
4. **Enforced Filter 6 Test**: Run backtest with single pair contributing 70% of profit, verify filter 6 fails
5. **Enforced Filter 7 Test**: Run backtest with single hour contributing 50% of profit, verify filter 7 fails
6. **Single Method Test**: Verify only one definition exists per method in loop_page.py and loop_service.py
7. **Non-Overlapping Timerange Test**: Compute in-sample and OOS ranges, verify no date appears in both

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed system produces the same result as the original system.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT original_system(input) = fixed_system(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for non-bug inputs, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Subsequent Iteration Preservation**: Run loop for 3 iterations, verify iterations 2-3 use cached diagnosis input (not baseline backtest)
2. **Correct Timeframe Preservation**: Run loop with strategy timeframe "5m", verify no observable change in behavior
3. **Passing Filter Preservation**: Run backtest with top-3 profit share 30%, verify filter 3 passes on both systems
4. **Filter 1/2/4/5 Preservation**: Run backtests that trigger filters 1, 2, 4, 5, verify identical pass/fail results
5. **Filter 8/9 Preservation**: Run backtests that trigger filters 8, 9, verify identical pass/fail results
6. **Quick Mode Preservation**: Run loop in Quick mode, verify gates 3-4 are skipped on both systems
7. **Walk-Forward Fold Preservation**: Compute walk-forward timeranges, verify identical fold count and boundaries

### Unit Tests

- Test `LoopConfig` serialization with new `timeframe` field
- Test `_start_baseline_backtest()` launches correct backtest command
- Test `_on_baseline_backtest_finished()` parses results and calls `prepare_next_iteration()`
- Test `compute_in_sample_timerange()` excludes `oos_start` from upper bound
- Test filter 3 computation with various trade profit distributions
- Test filter 6 computation with various pair profit distributions
- Test filter 7 computation with various time-bucket profit distributions
- Test that only one method definition exists per method name in loop_page.py and loop_service.py

### Property-Based Tests

- Generate random `LoopConfig` instances with various timeframes, verify all gates use config timeframe
- Generate random trade lists with varying profit distributions, verify filters 3/6/7 enforce thresholds correctly
- Generate random date ranges and OOS split percentages, verify in-sample and OOS ranges never overlap
- Generate random iteration counts, verify only first iteration runs baseline backtest
- Generate random backtest results, verify filters 1/2/4/5/8/9 produce identical results on both systems

### Integration Tests

- Test full loop execution from start to finish with real baseline backtest on first iteration
- Test loop execution with strategy timeframe "1h", verify all gates use "1h" consistently
- Test loop execution with backtest that fails filter 3, verify iteration is rejected with correct reason
- Test loop execution with backtest that fails filter 6, verify iteration is rejected with correct reason
- Test loop execution with backtest that fails filter 7, verify iteration is rejected with correct reason
- Test loop execution in Quick mode, verify gates 3-4 are skipped and result is produced
- Test loop execution with 5 walk-forward folds, verify 5 fold backtests are executed with non-overlapping ranges
