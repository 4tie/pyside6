# Bugfix Requirements Document

## Introduction

Five correctness bugs in the Strategy Lab / Loop feature undermine the reliability of the
"trusted ladder" optimization workflow. The issues span: a fabricated first-iteration seed
that bypasses real baseline data, a hardcoded `5m` timeframe that ignores user or strategy
selection, three placeholder hard filters that do not enforce their stated constraints,
stale duplicate code paths in `loop_page.py` and `loop_service.py` that create maintenance
risk, and a timerange boundary overlap that causes the in-sample and out-of-sample windows
to share the same split day.

---

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the first Strategy Lab iteration starts and no previous diagnosis input exists
    THEN the system fabricates a neutral `BacktestSummary` (50 trades, 0 % profit,
    `timeframe="5m"`) and uses it as the mutation seed instead of running a real baseline
    backtest of the current strategy.

1.2 WHEN any gate backtest is launched via `_start_gate_backtest()`
    THEN the system passes `timeframe="5m"` hardcoded to the backtest runner regardless of
    the strategy's native timeframe or any user-selected timeframe, because `LoopConfig`
    carries no `timeframe` field.

1.3 WHEN `HardFilterService.evaluate_post_gate1()` evaluates the `profit_concentration`
    filter for a result with more than three trades
    THEN the system skips the filter entirely (passes by default) because per-trade profit
    data is not available in `BacktestSummary`, leaving the filter unenforced.

1.4 WHEN `HardFilterService.evaluate_post_gate1()` evaluates the `pair_dominance` filter
    THEN the system always passes the filter because per-pair profit data is not present in
    `BacktestSummary` and the filter body contains only a comment with no enforcement logic.

1.5 WHEN `HardFilterService.evaluate_post_gate1()` evaluates the `time_dominance` filter
    THEN the system always passes the filter because per-period profit data is not present
    in `BacktestSummary` and the filter body contains only a comment with no enforcement
    logic.

1.6 WHEN `loop_page.py` and `loop_service.py` are read or modified
    THEN the system contains old and new implementations of the same methods side by side
    (compatibility wrappers, repeated method names), so Python silently uses the later
    definition while the earlier dead code remains, increasing maintenance risk and the
    chance of future regressions.

1.7 WHEN `compute_in_sample_timerange()` and `compute_oos_timerange()` are called for the
    same `LoopConfig`
    THEN both functions return a timerange string that includes `oos_start` as a boundary
    date — the in-sample range ends on `oos_start` and the OOS range starts on `oos_start`
    — so the split day is counted in both windows simultaneously.

---

### Expected Behavior (Correct)

2.1 WHEN the first Strategy Lab iteration starts and no previous diagnosis input exists
    THEN the system SHALL run a real baseline backtest of the current strategy over the
    configured in-sample timerange and use the resulting `BacktestSummary` as the mutation
    seed before generating the first set of parameter suggestions.

2.2 WHEN any gate backtest is launched via `_start_gate_backtest()`
    THEN the system SHALL pass the timeframe stored in `LoopConfig` (populated from the
    strategy's detected timeframe or the user's explicit selection) to the backtest runner,
    so every gate uses a consistent, correct timeframe end-to-end.

2.3 WHEN `HardFilterService.evaluate_post_gate1()` evaluates the `profit_concentration`
    filter
    THEN the system SHALL compute the actual top-3 trade profit share using per-trade data
    (available via `BacktestResults.trades`) and SHALL fail the filter when that share
    exceeds `config.profit_concentration_threshold`.

2.4 WHEN `HardFilterService.evaluate_post_gate1()` evaluates the `pair_dominance` filter
    THEN the system SHALL compute the single-pair profit share using per-pair profit data
    (available via `compute_pair_profit_distribution()`) and SHALL fail the filter when
    that share exceeds `config.pair_dominance_threshold`.

2.5 WHEN `HardFilterService.evaluate_post_gate1()` evaluates the `time_dominance` filter
    THEN the system SHALL compute the single-period profit share using per-period profit
    data derived from trade timestamps and SHALL fail the filter when that share exceeds
    `config.time_dominance_threshold`.

2.6 WHEN `loop_page.py` and `loop_service.py` are read or modified
    THEN each class SHALL contain only one active implementation per method — all
    superseded compatibility wrappers and duplicate method definitions SHALL be removed,
    leaving a single, authoritative code path for each operation.

2.7 WHEN `compute_in_sample_timerange()` and `compute_oos_timerange()` are called for the
    same `LoopConfig`
    THEN the system SHALL return non-overlapping ranges such that the in-sample range ends
    on the day before `oos_start` (exclusive upper bound) and the OOS range starts on
    `oos_start` (inclusive lower bound), ensuring no calendar day is counted in both
    windows.

---

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a Strategy Lab iteration is not the first iteration and a previous diagnosis input
    already exists
    THEN the system SHALL CONTINUE TO use the stored `_latest_diagnosis_input` as the
    mutation seed without running an additional baseline backtest.

3.2 WHEN a strategy's timeframe is correctly stored in `LoopConfig` and all gate backtests
    are launched
    THEN the system SHALL CONTINUE TO pass the same timeframe to every gate (in-sample,
    OOS, walk-forward, stress) without alteration.

3.3 WHEN `HardFilterService.evaluate_post_gate1()` evaluates filters 1, 2, 4, and 5
    (`min_trade_count`, `max_drawdown`, `profit_factor_floor`, `expectancy_floor`)
    THEN the system SHALL CONTINUE TO enforce those filters exactly as currently
    implemented, with no change to their thresholds or logic.

3.4 WHEN `HardFilterService.evaluate_post_gate()` evaluates filters 8 and 9
    (`oos_negativity`, `validation_variance`) after Gate 2 and Gate 3 respectively
    THEN the system SHALL CONTINUE TO enforce those filters exactly as currently
    implemented.

3.5 WHEN the Strategy Lab loop runs in Quick validation mode (gates 1–2 only)
    THEN the system SHALL CONTINUE TO skip walk-forward and stress gates and produce a
    result using only the in-sample and OOS gates.

3.6 WHEN `compute_walk_forward_timeranges()` is called for the same `LoopConfig`
    THEN the system SHALL CONTINUE TO return the same number of fold timeranges as
    `config.walk_forward_folds`, with each fold covering a non-overlapping sub-range of
    the full configured date window.

3.7 WHEN the loop is stopped mid-run or reaches `max_iterations`
    THEN the system SHALL CONTINUE TO surface the best iteration found so far and allow
    the user to accept, discard, or rollback as before.
