"""
hard_filter_service.py — Stateless hard-filter evaluation for loop iterations.

Evaluates nine hard filters at three interleaved points in the validation ladder:
  - Filters 1–7: after Gate 1 (in-sample), before Gate 2
  - Filter 8 (oos_negativity): after Gate 2, before Gate 3
  - Filter 9 (validation_variance): after Gate 3, before Gate 4
"""
from __future__ import annotations

import statistics
from datetime import datetime
from typing import Dict, List, Optional

from app.core.models.backtest_models import BacktestTrade
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
        trades: Optional[List[BacktestTrade]] = None,
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
        # Compute actual top-3 trade profit share using per-trade data
        if trades and len(trades) > 0:
            total_profit_abs = sum(abs(t.profit_abs) for t in trades)
            
            if total_profit_abs > 0:
                # Sort trades by absolute profit descending
                sorted_trades = sorted(trades, key=lambda t: abs(t.profit_abs), reverse=True)
                
                # Sum top 3 trades' absolute profit
                top_3_profit = sum(abs(t.profit_abs) for t in sorted_trades[:3])
                concentration_ratio = top_3_profit / total_profit_abs
                
                if concentration_ratio > config.profit_concentration_threshold:
                    failures.append(HardFilterFailure(
                        filter_name="profit_concentration",
                        reason=(
                            f"Top-3 profit share {concentration_ratio * 100:.1f}% exceeds "
                            f"threshold {config.profit_concentration_threshold * 100:.0f}%"
                        ),
                        evidence=f"{concentration_ratio:.4f}",
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
        # Compute single-pair profit share using per-pair profit data
        if trades and len(trades) > 0:
            total_profit_abs = sum(abs(t.profit_abs) for t in trades)
            
            if total_profit_abs > 0:
                # Group trades by pair and sum profit_abs per pair
                pair_profits: Dict[str, float] = {}
                for t in trades:
                    pair_profits[t.pair] = pair_profits.get(t.pair, 0.0) + abs(t.profit_abs)
                
                # Find max pair profit share
                max_pair_profit = max(pair_profits.values())
                max_pair_share = max_pair_profit / total_profit_abs
                
                if max_pair_share > config.pair_dominance_threshold:
                    # Find which pair(s) have the max profit
                    dominant_pairs = [p for p, profit in pair_profits.items() if profit == max_pair_profit]
                    failures.append(HardFilterFailure(
                        filter_name="pair_dominance",
                        reason=(
                            f"Single-pair profit share {max_pair_share * 100:.1f}% "
                            f"(pair: {dominant_pairs[0]}) exceeds threshold "
                            f"{config.pair_dominance_threshold * 100:.0f}%"
                        ),
                        evidence=f"{max_pair_share:.4f}",
                    ))

        # Filter 7: time_dominance
        # Compute single-period profit share using per-period profit data
        if trades and len(trades) > 0:
            total_profit_abs = sum(abs(t.profit_abs) for t in trades)
            
            if total_profit_abs > 0:
                # Parse close_date from trades and bucket by hour-of-day (0-23)
                hour_profits: Dict[int, float] = {}
                for t in trades:
                    if t.close_date:
                        try:
                            # Parse close_date - try common formats
                            # Freqtrade typically uses ISO format: "2024-01-15 14:30:00"
                            close_dt = datetime.fromisoformat(t.close_date.replace('Z', '+00:00'))
                            hour = close_dt.hour
                            hour_profits[hour] = hour_profits.get(hour, 0.0) + abs(t.profit_abs)
                        except (ValueError, AttributeError):
                            # Skip trades with unparseable dates
                            _log.warning("Could not parse close_date: %s", t.close_date)
                            continue
                
                if hour_profits:
                    # Find max hour profit share
                    max_hour_profit = max(hour_profits.values())
                    max_hour_share = max_hour_profit / total_profit_abs
                    
                    if max_hour_share > config.time_dominance_threshold:
                        # Find which hour(s) have the max profit
                        dominant_hours = [h for h, profit in hour_profits.items() if profit == max_hour_profit]
                        failures.append(HardFilterFailure(
                            filter_name="time_dominance",
                            reason=(
                                f"Single-hour profit share {max_hour_share * 100:.1f}% "
                                f"(hour: {dominant_hours[0]:02d}:00) exceeds threshold "
                                f"{config.time_dominance_threshold * 100:.0f}%"
                            ),
                            evidence=f"{max_hour_share:.4f}",
                        ))

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
