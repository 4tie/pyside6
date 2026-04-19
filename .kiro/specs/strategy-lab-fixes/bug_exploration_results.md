# Bug Exploration Test Results

**Test File**: `tests/core/services/test_strategy_lab_bug_exploration.py`

**Test Date**: Task 1 Execution

**Status**: ✅ ALL BUGS CONFIRMED - 8 tests failed as expected

## Summary

All five bugs have been successfully detected and documented through property-based exploration tests. The tests are designed to FAIL on unfixed code, confirming the bugs exist. After the fix is implemented, these same tests will PASS, validating the expected behavior.

## Bug 1: Fabricated First Iteration Seed

**Test**: `test_first_iteration_should_run_real_baseline_backtest`

**Status**: ✅ BUG CONFIRMED

**Counterexample**:
- First iteration uses fabricated BacktestSummary
- Fabricated seed values:
  - `total_trades`: 50 (hardcoded)
  - `total_profit`: 0.0% (neutral)
  - `timeframe`: "5m" (hardcoded)

**Expected Behavior**: Real baseline backtest should be executed with actual metrics

**Root Cause**: In `loop_page.py`, when `_run_next_iteration()` is called and iterations list is empty, the system creates a dummy seed instead of launching a real baseline backtest.

---

## Bug 2: Hardcoded 5m Timeframe

**Test**: `test_gates_should_use_config_timeframe_not_hardcoded_5m`

**Status**: ✅ BUG CONFIRMED

**Counterexample**:
- `LoopConfig` has no `timeframe` field
- All gate backtests use hardcoded "5m" regardless of strategy timeframe

**Expected Behavior**: 
- `LoopConfig` should have a `timeframe` field
- All gates should use `config.timeframe` from strategy detection or user selection

**Root Cause**: `LoopConfig` dataclass was created before timeframe selection was added. The hardcoded "5m" was never replaced with a configurable field.

---

## Bug 3: Placeholder Hard Filters (3, 6, 7)

### Filter 3: profit_concentration

**Test**: `test_filter3_profit_concentration_should_fail_when_threshold_exceeded`

**Status**: ✅ BUG CONFIRMED

**Counterexample**:
- Created 100 trades where top 3 contribute 75% of profit
- Threshold: 50%
- **Result**: Filter PASSED (should have FAILED)

**Expected Behavior**: Filter should fail when top-3 share (75%) exceeds threshold (50%)

**Root Cause**: Filter is skipped when `total_trades > 3` because per-trade data is not available in the filter evaluation.

---

### Filter 6: pair_dominance

**Test**: `test_filter6_pair_dominance_should_fail_when_threshold_exceeded`

**Status**: ✅ BUG CONFIRMED

**Counterexample**:
- Created 100 trades where BTC/USDT contributes 70% of profit
- Threshold: 60%
- **Result**: Filter PASSED (should have FAILED)

**Expected Behavior**: Filter should fail when single-pair share (70%) exceeds threshold (60%)

**Root Cause**: Filter has comment-only implementation, no actual computation.

---

### Filter 7: time_dominance

**Test**: `test_filter7_time_dominance_should_fail_when_threshold_exceeded`

**Status**: ✅ BUG CONFIRMED

**Counterexample**:
- Created 100 trades where hour 10 contributes 50% of profit
- Threshold: 40%
- **Result**: Filter PASSED (should have FAILED)

**Expected Behavior**: Filter should fail when single-hour share (50%) exceeds threshold (40%)

**Root Cause**: Filter has comment-only implementation, no actual computation.

---

## Bug 4: Duplicate Method Definitions

### loop_page.py

**Test**: `test_loop_page_should_have_no_duplicate_methods`

**Status**: ✅ BUG CONFIRMED

**Counterexamples**:
- `_on_start`: Found 2 times (lines 858, 2047)
- `_on_stop`: Found 2 times (lines 949, 2096)
- `_run_next_iteration`: Found 2 times (lines 1009, 2103)
- `_on_backtest_finished`: Found 2 times (lines 1109, 2338)

**Expected Behavior**: Only one definition per method

**Root Cause**: Refactoring from old single-gate loop to new multi-gate ladder left compatibility wrappers and old method definitions. Python silently uses the later definition while earlier dead code remains.

---

### loop_service.py

**Test**: `test_loop_service_should_have_no_duplicate_methods`

**Status**: ✅ BUG CONFIRMED

**Counterexample**:
- `_suggestions_from_structural`: Found 2 times (lines 590, 961)

**Expected Behavior**: Only one definition

**Root Cause**: Earlier definition is dead code from refactoring.

---

## Bug 5: Timerange Boundary Overlap

**Test**: `test_timeranges_should_not_overlap_at_oos_start_boundary`

**Status**: ✅ BUG CONFIRMED

**Counterexample**:
- Config: `date_from="20240101"`, `date_to="20240131"`, `oos_split_pct=20.0`
- In-sample range: `20240101-20240125` (ends on Jan 25)
- OOS range: `20240125-20240131` (starts on Jan 25)
- **Result**: Both ranges include Jan 25 (boundary overlap)

**Expected Behavior**: 
- In-sample should end on `20240124` (day before oos_start)
- OOS should start on `20240125`
- No date should appear in both ranges

**Root Cause**: `compute_in_sample_timerange()` uses inclusive string formatting without considering that Freqtrade interprets both boundaries as inclusive.

---

## Next Steps

1. ✅ Task 1 Complete: Bug exploration tests written and run on unfixed code
2. ⏭️ Task 2: Write preservation property tests (BEFORE implementing fix)
3. ⏭️ Task 3: Implement all five fixes following 7-phase implementation order
4. ⏭️ Task 3.8: Re-run bug exploration tests (should PASS after fix)
5. ⏭️ Task 3.9: Re-run preservation tests (should still PASS after fix)

---

## Test Execution Summary

```
================================ test session starts =================================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
collected 8 items

tests\core\services\test_strategy_lab_bug_exploration.py FFFFFFFF               [100%]

====================================== FAILURES ======================================
FAILED test_first_iteration_should_run_real_baseline_backtest - BUG CONFIRMED
FAILED test_gates_should_use_config_timeframe_not_hardcoded_5m - BUG CONFIRMED
FAILED test_filter3_profit_concentration_should_fail_when_threshold_exceeded - BUG CONFIRMED
FAILED test_filter6_pair_dominance_should_fail_when_threshold_exceeded - BUG CONFIRMED
FAILED test_filter7_time_dominance_should_fail_when_threshold_exceeded - BUG CONFIRMED
FAILED test_loop_page_should_have_no_duplicate_methods - BUG CONFIRMED
FAILED test_loop_service_should_have_no_duplicate_methods - BUG CONFIRMED
FAILED test_timeranges_should_not_overlap_at_oos_start_boundary - BUG CONFIRMED

================================= 8 failed in 0.31s ==================================
```

**All tests failed as expected, confirming all five bugs exist in the unfixed code.**
