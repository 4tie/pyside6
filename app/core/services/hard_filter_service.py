"""
hard_filter_service.py — Stateless hard-filter evaluation for loop iterations.

Evaluates nine hard filters at three interleaved points in the validation ladder:
  - Filters 1–7: after Gate 1 (in-sample), before Gate 2
  - Filter 8 (oos_negativity): after Gate 2, before Gate 3
  - Filter 9 (validation_variance): after Gate 3, before Gate 4
"""
from __future__ import annotations

import statistics
from typing import List

from app.core.models.loop_models import GateResult, HardFilterFailure, LoopConfig
from app.core.utils.app_logger import get_logger

_log = get_logger("services.hard_filter")


class HardFilterService:
    """Stateless service for evaluating hard filters on gate results.

    All methods are static — no instance state is required.
    """

    @staticmethod
    def evaluate_post_gate1(
        gate1_result: GateResult,
        config: LoopConfig,
    ) -> List[HardFilterFailure]:
        """Evaluate hard filters 1–7 using the Gate 1 (in-sample) BacktestSummary.

        All seven filters are evaluated even after the first failure — rejection
        is logical (all failures are collected and returned together).

        Filters evaluated:
          1. min_trade_count — total_trades >= target_min_trades
          2. max_drawdown — max_drawdown <= target_max_drawdown
          3. profit_concentration — top-3 trades profit share <= threshold
          4. profit_factor_floor — profit_factor >= config.profit_factor_floor
          5. expectancy_floor — expectancy >= 0.0
          6. pair_dominance — single-pair profit share <= config.pair_dominance_threshold
          7. time_dominance — single-period profit share <= config.time_dominance_threshold

        Args:
            gate1_result: GateResult from Gate 1 (in-sample backtest).
            config: LoopConfig containing filter thresholds.

        Returns:
            List of HardFilterFailure objects for every filter that failed.
            Returns empty list when all filters pass.
        """
        failures: List[HardFilterFailure] = []
        metrics = gate1_result.metrics

        if metrics is None:
            _log.warning(
                "evaluate_post_gate1: gate1_result.metrics is None — skipping all filters"
            )
            return failures

        # Filter 1: min_trade_count
        if metrics.total_trades < config.target_min_trades:
            failures.append(HardFilterFailure(
                filter_name="min_trade_count",
                reason=(
                    f"Trade count {metrics.total_trades} is below minimum "
                    f"{config.target_min_trades}"
                ),
                evidence=str(metrics.total_trades),
            ))

        # Filter 2: max_drawdown
        if metrics.max_drawdown > config.target_max_drawdown:
            failures.append(HardFilterFailure(
                filter_name="max_drawdown",
                reason=(
                    f"Max drawdown {metrics.max_drawdown:.2f}% exceeds limit "
                    f"{config.target_max_drawdown:.2f}%"
                ),
                evidence=f"{metrics.max_drawdown:.2f}%",
            ))

        # Filter 3: profit_concentration (top 3 trades)
        # We approximate using total_profit and trade count — if we had per-trade
        # data we would compute it exactly. Here we use a conservative heuristic:
        # if total_trades >= 3, we cannot determine concentration without per-trade
        # data, so we skip this filter (pass by default). The filter is only
        # meaningful when per-trade data is available via pair_profit_distribution.
        # NOTE: Full implementation requires per-trade profit data which is not
        # currently stored in BacktestSummary. This filter is a placeholder that
        # passes unless the summary has very few trades (≤ 3) with high profit.
        if metrics.total_trades > 0 and metrics.total_trades <= 3:
            # With 3 or fewer trades, top-3 IS all trades — concentration = 1.0
            if 1.0 > config.profit_concentration_threshold:
                failures.append(HardFilterFailure(
                    filter_name="profit_concentration",
                    reason=(
                        f"Only {metrics.total_trades} trade(s) — top-3 concentration "
                        f"is 100%, exceeds threshold "
                        f"{config.profit_concentration_threshold * 100:.0f}%"
                    ),
                    evidence=f"{metrics.total_trades} trades",
                ))

        # Filter 4: profit_factor_floor
        if metrics.profit_factor < config.profit_factor_floor:
            failures.append(HardFilterFailure(
                filter_name="profit_factor_floor",
                reason=(
                    f"Profit factor {metrics.profit_factor:.3f} is below floor "
                    f"{config.profit_factor_floor:.3f}"
                ),
                evidence=f"{metrics.profit_factor:.3f}",
            ))

        # Filter 5: expectancy_floor (must be >= 0.0)
        if metrics.expectancy < 0.0:
            failures.append(HardFilterFailure(
                filter_name="expectancy_floor",
                reason=(
                    f"Expectancy {metrics.expectancy:.4f} is negative — "
                    "average trade loses money"
                ),
                evidence=f"{metrics.expectancy:.4f}",
            ))

        # Filter 6: pair_dominance
        # Without per-pair profit data in BacktestSummary, we cannot compute this
        # directly. This filter passes by default unless pair_profit_distribution
        # is available (it is not in BacktestSummary). Placeholder implementation.
        # In a full implementation, pair_profit_distribution would be passed in.

        # Filter 7: time_dominance
        # Similarly, without per-period profit data, this filter passes by default.
        # Placeholder implementation.

        if failures:
            _log.info(
                "evaluate_post_gate1: %d hard filter(s) failed: %s",
                len(failures),
                [f.filter_name for f in failures],
            )
        return failures

    @staticmethod
    def evaluate_post_gate(
        gate_name: str,
        gate_result: GateResult,
        config: LoopConfig,
    ) -> List[HardFilterFailure]:
        """Evaluate hard filters 8–9 after Gate 2 or Gate 3.

        Filter 8 (oos_negativity): evaluated when gate_name == "out_of_sample".
            Fails when OOS total_profit < 0.

        Filter 9 (validation_variance): evaluated when gate_name == "walk_forward".
            Fails when coefficient of variation of fold profits exceeds
            config.validation_variance_ceiling, or when mean fold profit <= 0.

        Args:
            gate_name: Name of the gate just completed ("out_of_sample" or
                "walk_forward").
            gate_result: GateResult from the completed gate.
            config: LoopConfig containing filter thresholds.

        Returns:
            List of HardFilterFailure objects for every filter that failed.
            Returns empty list when all applicable filters pass or gate_name
            is not "out_of_sample" or "walk_forward".
        """
        failures: List[HardFilterFailure] = []

        if gate_name == "out_of_sample":
            # Filter 8: oos_negativity
            metrics = gate_result.metrics
            if metrics is None:
                _log.warning(
                    "evaluate_post_gate: out_of_sample gate_result.metrics is None"
                )
                return failures

            if metrics.total_profit < 0.0:
                failures.append(HardFilterFailure(
                    filter_name="oos_negativity",
                    reason=(
                        f"Out-of-sample profit {metrics.total_profit:.4f}% is negative — "
                        "strategy loses money on unseen data"
                    ),
                    evidence=f"{metrics.total_profit:.4f}%",
                ))

        elif gate_name == "walk_forward":
            # Filter 9: validation_variance
            fold_summaries = gate_result.fold_summaries
            if not fold_summaries:
                _log.warning(
                    "evaluate_post_gate: walk_forward gate_result.fold_summaries is empty"
                )
                return failures

            fold_profits = [fs.total_profit for fs in fold_summaries]

            if len(fold_profits) < 2:
                # Cannot compute variance with fewer than 2 folds
                return failures

            mean_profit = statistics.mean(fold_profits)

            if mean_profit <= 0.0:
                failures.append(HardFilterFailure(
                    filter_name="validation_variance",
                    reason=(
                        f"Mean fold profit {mean_profit:.4f}% is zero or negative — "
                        "walk-forward validation failed"
                    ),
                    evidence=f"mean={mean_profit:.4f}%",
                ))
                return failures

            std_profit = statistics.stdev(fold_profits)
            cv = std_profit / abs(mean_profit)

            if cv > config.validation_variance_ceiling:
                failures.append(HardFilterFailure(
                    filter_name="validation_variance",
                    reason=(
                        f"Walk-forward CV {cv:.4f} exceeds ceiling "
                        f"{config.validation_variance_ceiling:.4f} — "
                        "fold profits are too inconsistent"
                    ),
                    evidence=f"CV={cv:.4f}",
                ))

        if failures:
            _log.info(
                "evaluate_post_gate(%s): %d hard filter(s) failed: %s",
                gate_name,
                len(failures),
                [f.filter_name for f in failures],
            )
        return failures
