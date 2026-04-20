# Bugfix Requirements Document

## Introduction

This document specifies the requirements for fixing five critical bugs in the Strategy Lab / Loop feature that undermine the reliability of the "trusted ladder" optimization workflow. These bugs affect baseline initialization, gate execution, data split boundaries, hard filter activation, and code cleanliness.

## Bug Analysis

### Current Behavior (Defect)

**Bug 1: Fake First-Iteration Seed**

1.1 WHEN there is no previous diagnosis input THEN `LoopPage._current_diagnosis_seed()` fabricates a neutral dummy `BacktestSummary` with hardcoded values (50 trades, 50% win rate, 0% profit) instead of running a real baseline backtest

**Bug 2: Hardcoded Timeframe in Gate Execution**

1.2 WHEN `_start_gate_backtest()` is called THEN it passes `timeframe=config.timeframe` to `build_backtest_command()`, but `LoopConfig.timeframe` defaults to `"5m"` and is never populated from the strategy's native timeframe

1.3 WHEN a strategy has a native timeframe other than "5m" THEN all gate backtests ignore the strategy's actual timeframe and use "5m" instead

**Bug 3: IS/OOS Split Overlaps on Boundary Day**

1.4 WHEN `compute_in_sample_timerange()` computes the in-sample end date THEN it ends at `oos_start - timedelta(days=1)`, which is one day before the OOS start

1.5 WHEN `compute_oos_timerange()` computes the OOS start date THEN it starts at `oos_start`, which is the same day that was excluded from in-sample

1.6 WHEN the boundary day falls on `oos_start` THEN the day is excluded from both in-sample and OOS ranges, creating a gap in the data

**Bug 4: Hard-Filter Wiring Incomplete**

1.7 WHEN `HardFilterService.evaluate_post_gate1()` is called THEN it supports real trade-based checks for profit concentration (filter 3), pair dominance (filter 6), and time dominance (filter 7) using the `trades` parameter

1.8 WHEN `LoopPage` calls `LoopService.evaluate_gate1_hard_filters()` THEN it does not pass the `trades` parameter, so the method receives `None`

1.9 WHEN `LoopService.evaluate_gate1_hard_filters()` receives `None` for trades THEN filters 3, 6, and 7 are silently skipped because they cannot compute without per-trade data

1.10 WHEN the hard filters are evaluated without trades THEN profit concentration, pair dominance, and time dominance checks are never activated in the live loop path

**Bug 5: Duplicate Method Definitions**

1.11 WHEN reviewing `loop_page.py` and `loop_service.py` THEN duplicate old/new method definitions and compatibility-wrapper style leftovers exist

1.12 WHEN duplicate methods exist THEN code maintainability is reduced and confusion about which method to call increases

### Expected Behavior (Correct)

**Bug 1: Real Baseline Backtest**

2.1 WHEN the loop starts and there is no previous diagnosis input THEN the system SHALL run a real baseline backtest on the in-sample timerange before the first iteration

2.2 WHEN the baseline backtest completes THEN the system SHALL use the actual `BacktestSummary` and `BacktestResults` as the diagnosis seed for the first iteration

**Bug 2: Strategy-Native Timeframe**

2.3 WHEN the loop starts THEN the system SHALL detect the strategy's native timeframe using `detect_strategy_timeframe()` and populate `LoopConfig.timeframe`

2.4 WHEN `_start_gate_backtest()` is called THEN it SHALL pass the strategy's native timeframe to `build_backtest_command()` so all gates use the correct timeframe

**Bug 3: Non-Overlapping IS/OOS Split**

2.5 WHEN `compute_in_sample_timerange()` computes the in-sample end date THEN it SHALL end at `oos_start - timedelta(days=1)` to exclude the OOS start day

2.6 WHEN `compute_oos_timerange()` computes the OOS start date THEN it SHALL start at `oos_start` to include the OOS start day

2.7 WHEN the boundary day falls on `oos_start` THEN the day SHALL be included in the OOS range and excluded from the in-sample range, with no gap

**Bug 4: Hard-Filter Trade Data Wiring**

2.8 WHEN `LoopPage` evaluates Gate 1 hard filters THEN it SHALL extract the trades list from `_iteration_in_sample_results.trades` and pass it to `LoopService.evaluate_gate1_hard_filters()`

2.9 WHEN `LoopService.evaluate_gate1_hard_filters()` is called THEN it SHALL accept a `trades` parameter and forward it to `HardFilterService.evaluate_post_gate1()`

2.10 WHEN `HardFilterService.evaluate_post_gate1()` receives trades THEN it SHALL compute profit concentration (filter 3), pair dominance (filter 6), and time dominance (filter 7) using the per-trade data

**Bug 5: Code Cleanup**

2.11 WHEN duplicate method definitions exist in `loop_page.py` and `loop_service.py` THEN they SHALL be removed, keeping only the canonical implementation

2.12 WHEN compatibility-wrapper style leftovers exist THEN they SHALL be removed to improve code clarity

### Unchanged Behavior (Regression Prevention)

**General Loop Behavior**

3.1 WHEN the loop runs with a valid baseline THEN the system SHALL CONTINUE TO execute the multi-gate validation ladder (Gate 1 → Gate 2 → Gate 3 → Gate 4 → Gate 5)

3.2 WHEN hard filters are evaluated after Gate 1 THEN the system SHALL CONTINUE TO reject iterations that fail filters 1, 2, 4, and 5 (min_trade_count, max_drawdown, profit_factor_floor, expectancy_floor)

3.3 WHEN the loop completes THEN the system SHALL CONTINUE TO return the best validated iteration based on `RobustScore.total`

**Gate Execution**

3.4 WHEN gates are executed THEN the system SHALL CONTINUE TO use the correct timerange for each gate (in-sample, OOS, walk-forward folds, stress)

3.5 WHEN the stress gate runs THEN the system SHALL CONTINUE TO apply the configured fee multiplier and slippage percentage

3.6 WHEN the walk-forward gate runs THEN the system SHALL CONTINUE TO split the full date range into equal folds

**Hard Filter Evaluation**

3.7 WHEN hard filters 8 and 9 are evaluated THEN the system SHALL CONTINUE TO check OOS negativity (filter 8) after Gate 2 and validation variance (filter 9) after Gate 3

3.8 WHEN a hard filter fails THEN the system SHALL CONTINUE TO mark the iteration as "hard_filter_rejected" and record the failure reasons

**UI and State Management**

3.9 WHEN an iteration completes THEN the system SHALL CONTINUE TO update the iteration history, stat cards, and progress bar

3.10 WHEN the loop is stopped THEN the system SHALL CONTINUE TO finalize the result and display the best iteration found
