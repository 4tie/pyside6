"""pair_analysis_service.py — Stateless service for per-pair backtest analysis.

Derives PairAnalysis (with PairMetrics per pair, best/worst pairs, and dominance
flags) from a BacktestResults object.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from app.core.backtests.results_models import (
    BacktestResults,
    BacktestTrade,
    PairAnalysis,
    PairMetrics,
)
from app.core.utils.app_logger import get_logger

_log = get_logger("services.pair_analysis")


class PairAnalysisService:
    """Stateless service that derives PairAnalysis from BacktestResults.

    All methods are static — no instance state is held.
    """

    @staticmethod
    def analyse(results: BacktestResults) -> PairAnalysis:
        """Derive PairAnalysis from a BacktestResults object.

        Implements the 8-step algorithm:
        1. Return empty PairAnalysis when trades list is empty.
        2. Group trades by pair.
        3. Compute PairMetrics for each group (profit_share deferred).
        4. Compute abs_total across all pairs.
        5. Set profit_share for each PairMetrics entry.
        6. Derive best_pairs (top 3 descending by total_profit_pct).
        7. Derive worst_pairs (bottom 3 ascending by total_profit_pct).
        8. Set dominance_flags when any single profit_share > 0.60.

        Args:
            results: BacktestResults containing a trades list and summary.

        Returns:
            PairAnalysis with per-pair metrics, best/worst pairs, and
            dominance flags.
        """
        # Step 1 — empty trades guard
        if not results.trades:
            _log.debug("analyse called with empty trades list — returning empty PairAnalysis")
            return PairAnalysis([], [], [], [])

        # Step 2 — group trades by pair
        groups: Dict[str, List[BacktestTrade]] = defaultdict(list)
        for trade in results.trades:
            groups[trade.pair].append(trade)

        _log.debug("analyse: %d distinct pairs from %d trades", len(groups), len(results.trades))

        # Step 3 — compute PairMetrics for each group (profit_share=0.0 placeholder)
        all_metrics: List[PairMetrics] = []
        for pair, trades in groups.items():
            total_profit_pct = sum(t.profit for t in trades)
            wins = len([t for t in trades if t.profit > 0])
            trade_count = len(trades)
            win_rate = wins / trade_count * 100
            max_drawdown_pct = abs(
                min((t.profit for t in trades if t.profit < 0), default=0.0)
            )
            all_metrics.append(
                PairMetrics(
                    pair=pair,
                    total_profit_pct=total_profit_pct,
                    win_rate=win_rate,
                    trade_count=trade_count,
                    max_drawdown_pct=max_drawdown_pct,
                    profit_share=0.0,  # filled in step 5
                )
            )

        # Step 4 — compute abs_total
        abs_total = sum(abs(pm.total_profit_pct) for pm in all_metrics)

        # Step 5 — set profit_share (guard against zero division)
        for pm in all_metrics:
            pm.profit_share = pm.total_profit_pct / abs_total if abs_total != 0.0 else 0.0

        # Step 6 — best_pairs: top 3 descending by total_profit_pct
        best_pairs = sorted(all_metrics, key=lambda pm: pm.total_profit_pct, reverse=True)[:3]

        # Step 7 — worst_pairs: bottom 3 ascending by total_profit_pct
        worst_pairs = sorted(all_metrics, key=lambda pm: pm.total_profit_pct)[:3]

        # Step 8 — dominance_flags
        dominance_flags: List[str] = []
        if any(pm.profit_share > 0.60 for pm in all_metrics):
            dominance_flags.append("profit_concentration")

        _log.debug(
            "analyse complete: %d pairs, best=%s, worst=%s, flags=%s",
            len(all_metrics),
            [pm.pair for pm in best_pairs],
            [pm.pair for pm in worst_pairs],
            dominance_flags,
        )

        return PairAnalysis(
            pair_metrics=all_metrics,
            best_pairs=best_pairs,
            worst_pairs=worst_pairs,
            dominance_flags=dominance_flags,
        )
