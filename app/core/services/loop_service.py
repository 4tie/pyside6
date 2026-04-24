"""
loop_service.py — Orchestration service for the auto-optimization loop.

Drives the iterative backtest → diagnose → suggest → apply → repeat cycle.
All heavy lifting (subprocess execution) is delegated to ImproveService and
ProcessService; this service manages state transitions and suggestion rotation.
"""
from __future__ import annotations

import copy
import math
import statistics
from typing import Callable, Dict, List, Optional, Tuple

from app.core.backtests.results_models import BacktestResults, BacktestSummary, BacktestTrade
from app.core.models.diagnosis_models import DiagnosisInput
from app.core.models.improve_models import DiagnosedIssue, ParameterSuggestion
from app.core.models.loop_models import (
    GateResult,
    HardFilterFailure,
    LoopConfig,
    LoopIteration,
    LoopResult,
    RobustScore,
    RobustScoreInput,
)
from app.core.services.hard_filter_service import HardFilterService
from app.core.services.improve_service import ImproveService
from app.core.services.results_diagnosis_service import ResultsDiagnosisService
from app.core.services.rule_suggestion_service import RuleSuggestionService
from app.core.utils.app_logger import get_logger

# 4-Layer Diagnostic Architecture imports
from app.core.models.pattern_models import Action, LoopState4L
from app.core.services.pattern_database import PatternDatabase
from app.core.services.pattern_engine import PatternEngine
from app.core.services.decision_engine import DecisionEngine
from app.core.services.execution_engine import ExecutionEngine
from app.core.services.evaluation_engine import EvaluationEngine

_log = get_logger("services.loop")

# ---------------------------------------------------------------------------
# 4-Layer Diagnostic Architecture fallback actions (emergency only)
# ---------------------------------------------------------------------------
_FALLBACK_ACTIONS = [
    Action(id="reduce_trades", pattern_id="fallback", parameter="max_open_trades", type="set", value=3),
    Action(id="tighten_stoploss", pattern_id="fallback", parameter="stoploss", type="set", value=-0.15),
]

# ---------------------------------------------------------------------------
# Fixed reference ranges for norm() — set once, never change during a session.
# These guarantee RobustScore.total values are directly comparable across all
# iterations regardless of computation order.
# ---------------------------------------------------------------------------
_NORM_NET_PROFIT_MIN: float = -100.0
_NORM_NET_PROFIT_MAX: float = 200.0
_NORM_EXPECTANCY_MIN: float = -1.0
_NORM_EXPECTANCY_MAX: float = 5.0
_NORM_PROFIT_FACTOR_MIN: float = 0.0
_NORM_PROFIT_FACTOR_MAX: float = 3.0
_NORM_MAX_DRAWDOWN_MIN: float = 0.0
_NORM_MAX_DRAWDOWN_MAX: float = 100.0


def _normalize_value(value: float, lo: float, hi: float) -> float:
    """Linearly normalize value to [0, 1] using fixed reference range [lo, hi].

    Args:
        value: Raw metric value.
        lo: Lower bound of the reference range.
        hi: Upper bound of the reference range.

    Returns:
        Clamped normalized value in [0, 1].
    """
    if hi == lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _is_invalid_value(v) -> bool:
    """Return True if v is None or a float NaN."""
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False


def _normalize_backtest_summary(summary: BacktestSummary) -> BacktestSummary:
    """Return a copy of summary with None/NaN fields replaced by neutral values.

    Substitutions applied:
    - sharpe_ratio  → 0.0
    - profit_factor → 0.0
    - win_rate      → 0.0
    - max_drawdown  → 100.0

    A WARNING is logged for each substitution made.

    Args:
        summary: BacktestSummary that may contain None or NaN fields.

    Returns:
        A new BacktestSummary with all four guarded fields guaranteed non-None/NaN.
    """
    # Use copy to avoid mutating the original
    result = copy.copy(summary)

    if _is_invalid_value(result.sharpe_ratio):
        _log.warning(
            "_normalize_backtest_summary: sharpe_ratio is None/NaN for strategy '%s' — substituting 0.0",
            summary.strategy,
        )
        result.sharpe_ratio = 0.0

    if _is_invalid_value(result.profit_factor):
        _log.warning(
            "_normalize_backtest_summary: profit_factor is None/NaN for strategy '%s' — substituting 0.0",
            summary.strategy,
        )
        result.profit_factor = 0.0

    if _is_invalid_value(result.win_rate):
        _log.warning(
            "_normalize_backtest_summary: win_rate is None/NaN for strategy '%s' — substituting 0.0",
            summary.strategy,
        )
        result.win_rate = 0.0

    if _is_invalid_value(result.max_drawdown):
        _log.warning(
            "_normalize_backtest_summary: max_drawdown is None/NaN for strategy '%s' — substituting 100.0",
            summary.strategy,
        )
        result.max_drawdown = 100.0

    return result


def calculate_robust_score(input: RobustScoreInput) -> RobustScore:
    """Compute a multi-dimensional RobustScore for a backtest result bundle.

    Formula:
        robust_score = profitability_score + consistency_score + stability_score
                       - fragility_score

    Each component is a normalized value in [0, 1] (fragility is subtracted).

    Args:
        input: RobustScoreInput bundling in-sample summary, optional fold
            summaries, optional stress summary, and optional pair profit
            distribution.

    Returns:
        RobustScore with total and four component scores.
    """
    s = _normalize_backtest_summary(input.in_sample)

    # ------------------------------------------------------------------
    # Profitability component (weight 0.35)
    # ------------------------------------------------------------------
    norm_profit = _normalize_value(s.total_profit, _NORM_NET_PROFIT_MIN, _NORM_NET_PROFIT_MAX)
    norm_expectancy = _normalize_value(s.expectancy, _NORM_EXPECTANCY_MIN, _NORM_EXPECTANCY_MAX)
    norm_pf = _normalize_value(min(s.profit_factor, 3.0), _NORM_PROFIT_FACTOR_MIN, _NORM_PROFIT_FACTOR_MAX)
    profitability = 0.35 * (norm_profit + norm_expectancy + norm_pf) / 3.0

    # ------------------------------------------------------------------
    # Consistency component (weight 0.30)
    # ------------------------------------------------------------------
    # equity_r2: placeholder — use 0.5 as neutral when not computable
    equity_r2 = 0.5

    if input.fold_summaries and len(input.fold_summaries) > 0:
        profitable_folds = sum(
            1 for fs in input.fold_summaries if fs.total_profit > 0
        )
        pct_profitable_folds = profitable_folds / len(input.fold_summaries)
        consistency = 0.30 * (pct_profitable_folds + equity_r2) / 2.0
    else:
        # Quick mode: use only equity_r2 with full weight
        consistency = 0.30 * equity_r2

    # ------------------------------------------------------------------
    # Stability component (weight 0.20)
    # ------------------------------------------------------------------
    # pair_dominance_ratio: fraction of profit from the single most dominant pair
    pair_dominance_ratio = 0.0
    if input.pair_profit_distribution:
        pair_dominance_ratio = max(input.pair_profit_distribution.values(), default=0.0)
        pair_dominance_ratio = max(0.0, min(1.0, pair_dominance_ratio))

    if input.fold_summaries and len(input.fold_summaries) > 1:
        fold_profits = [fs.total_profit for fs in input.fold_summaries]
        mean_fp = statistics.mean(fold_profits)
        std_fp = statistics.stdev(fold_profits)
        cv_fold_profits = (std_fp / abs(mean_fp)) if mean_fp != 0 else 1.0
        cv_fold_profits = max(0.0, min(1.0, cv_fold_profits))
        stability = 0.20 * ((1.0 - cv_fold_profits) + (1.0 - pair_dominance_ratio)) / 2.0
    else:
        # Quick mode: use only pair stability with full weight
        stability = 0.20 * (1.0 - pair_dominance_ratio)

    # ------------------------------------------------------------------
    # Fragility component (weight 0.15, subtracted)
    # ------------------------------------------------------------------
    norm_dd = _normalize_value(s.max_drawdown, _NORM_MAX_DRAWDOWN_MIN, _NORM_MAX_DRAWDOWN_MAX)

    # slippage_sensitivity: ratio of stress-test profit drop to baseline profit
    slippage_sensitivity = 0.0
    if input.stress_summary is not None:
        stress_s = _normalize_backtest_summary(input.stress_summary)
        if s.total_profit != 0:
            drop = s.total_profit - stress_s.total_profit
            slippage_sensitivity = max(0.0, min(1.0, drop / abs(s.total_profit)))

    if input.stress_summary is not None:
        fragility = 0.15 * (norm_dd + slippage_sensitivity + pair_dominance_ratio) / 3.0
    else:
        # Quick mode: use only drawdown and pair dependence
        fragility = 0.15 * (norm_dd + pair_dominance_ratio) / 2.0

    # ------------------------------------------------------------------
    # Total
    # ------------------------------------------------------------------
    total = profitability + consistency + stability - fragility

    return RobustScore(
        total=total,
        profitability=profitability,
        consistency=consistency,
        stability=stability,
        fragility=fragility,
    )


def calculate_trade_profit_contributions(
    results: Optional[BacktestResults],
) -> Optional[List[float]]:
    """Return per-trade profit contributions as fractions of total positive profit."""
    if results is None or not results.trades:
        return None

    positive_trades = [trade for trade in results.trades if trade.profit_abs > 0]
    total_positive_profit = sum(trade.profit_abs for trade in positive_trades)
    if total_positive_profit <= 0:
        return None

    return [
        round(trade.profit_abs / total_positive_profit, 6)
        for trade in positive_trades
    ]


def calculate_pair_profit_distribution(
    results: Optional[BacktestResults],
) -> Optional[Dict[str, float]]:
    """Return pair -> positive profit share distribution for stability scoring."""
    if results is None or not results.trades:
        return None

    totals: Dict[str, float] = {}
    for trade in results.trades:
        if trade.profit_abs <= 0:
            continue
        totals[trade.pair] = totals.get(trade.pair, 0.0) + trade.profit_abs

    total_positive_profit = sum(totals.values())
    if total_positive_profit <= 0:
        return None

    return {
        pair: round(value / total_positive_profit, 6)
        for pair, value in totals.items()
    }


def create_diagnosis_input(
    in_sample_results: BacktestResults,
    oos_results: Optional[BacktestResults] = None,
    fold_results: Optional[List[BacktestResults]] = None,
) -> DiagnosisInput:
    """Build a DiagnosisInput bundle from parsed backtest results."""
    from app.core.services.exit_reason_analysis_service import ExitReasonAnalysisService

    exit_reason_analysis = ExitReasonAnalysisService.analyze(in_sample_results.trades)

    return DiagnosisInput(
        in_sample=in_sample_results.summary,
        oos_summary=oos_results.summary if oos_results is not None else None,
        fold_summaries=[
            result.summary for result in (fold_results or [])
        ] or None,
        trade_profit_contributions=calculate_trade_profit_contributions(in_sample_results),
        exit_reason_analysis=exit_reason_analysis,
    )


def create_score_input(
    in_sample_results: BacktestResults,
    fold_results: Optional[List[BacktestResults]] = None,
    stress_results: Optional[BacktestResults] = None,
) -> RobustScoreInput:
    """Build a RobustScoreInput bundle from parsed backtest results."""
    return RobustScoreInput(
        in_sample=in_sample_results.summary,
        fold_summaries=[result.summary for result in (fold_results or [])] or None,
        stress_summary=stress_results.summary if stress_results is not None else None,
        pair_profit_distribution=calculate_pair_profit_distribution(in_sample_results),
    )


def check_targets_met(summary: BacktestSummary, config: LoopConfig) -> bool:
    """Return True if all profitability targets in config are satisfied.

    All four conditions must be simultaneously satisfied.

    Args:
        summary: Backtest summary to evaluate.
        config: Loop configuration containing target thresholds.

    Returns:
        True if every target is met simultaneously.
    """
    return (
        summary.total_profit >= config.target_profit_pct
        and summary.win_rate >= config.target_win_rate
        and summary.max_drawdown <= config.target_max_drawdown
        and summary.total_trades >= config.target_min_trades
    )


class SuggestionRotator:
    """Manages suggestion variation across loop iterations.

    Tracks which parameter values have already been tried and generates
    progressively different suggestions to avoid repeating the same config.
    When structured suggestions are exhausted, falls back to random
    perturbations so the loop can keep exploring without stopping early.

    Args:
        base_params: The initial strategy parameters before any loop changes.
    """

    # How many times to try tightening/loosening each parameter before giving up.
    # Set high so the rotator doesn't exhaust its budget before the loop's
    # max_iterations is reached.
    _MAX_STEPS_PER_PARAM = 20

    # Random perturbation parameters used when structured suggestions run dry
    _RANDOM_STOPLOSS_RANGE = (-0.30, -0.01)
    _RANDOM_MOT_RANGE = (1, 20)
    _RANDOM_ROI_DELTA_RANGE = (-0.02, 0.02)
    _RANDOM_PARAM_SCALE = 0.10  # ±10% of current value for buy/sell params

    def __init__(self, base_params: dict) -> None:
        self._base_params = copy.deepcopy(base_params)
        # {param_name: step_count} — how many times we've adjusted each param
        self._step_counts: Dict[str, int] = {}
        # Set of frozensets of (param, value) tuples — configs already tried
        self._tried_configs: set = set()

    def _config_key(self, params: dict) -> frozenset:
        """Return a hashable key for a params dict (top-level scalar values only)."""
        items = []
        for k, v in params.items():
            if isinstance(v, (int, float, str, bool)):
                items.append((k, v))
            elif isinstance(v, dict):
                items.append((k, str(sorted(v.items()))))
        return frozenset(items)

    def already_tried(self, params: dict) -> bool:
        """Return True if this exact parameter configuration has been tried before."""
        return self._config_key(params) in self._tried_configs

    def mark_tried(self, params: dict) -> None:
        """Record that this parameter configuration has been tried."""
        self._tried_configs.add(self._config_key(params))

    def get_step(self, param: str) -> int:
        """Return the current step count for a parameter (0-based)."""
        return self._step_counts.get(param, 0)

    def increment_step(self, param: str) -> None:
        """Increment the step count for a parameter."""
        self._step_counts[param] = self._step_counts.get(param, 0) + 1

    def exhausted(self, param: str) -> bool:
        """Return True if we've tried the maximum number of steps for a parameter."""
        return self._step_counts.get(param, 0) >= self._MAX_STEPS_PER_PARAM

    def generate_suggestions(
        self,
        issues: List[DiagnosedIssue],
        current_params: dict,
        prev_iteration: Optional[LoopIteration],
        structural: Optional[List] = None,
        exit_reason_suggestions: Optional[List] = None,
    ) -> List[ParameterSuggestion]:
        """Generate a varied set of suggestions for this iteration.

        Applies step-based variation: each successive call for the same issue
        produces a more aggressive or differently-directed change. If a previous
        iteration made things worse, the direction is reversed.

        Args:
            issues: Diagnosed issues from the latest backtest.
            current_params: Current strategy parameters.
            prev_iteration: The previous loop iteration, or None for the first.
            structural: Optional structural diagnosis patterns from DiagnosisBundle.
            exit_reason_suggestions: Optional exit reason suggestions from DiagnosisBundle.

        Returns:
            List of non-advisory ParameterSuggestion objects to apply.
        """
        actionable = RuleSuggestionService.suggest(
            issues, current_params, structural, exit_reason_suggestions
        )

        # Inject trailing-stop proposal when high-drawdown structural pattern is present
        # and trailing_stop is currently disabled
        if structural:
            high_drawdown_patterns = {"losers_lasting_too_long", "drawdown_after_volatility"}
            has_drawdown_pattern = any(
                getattr(sd, "failure_pattern", "") in high_drawdown_patterns
                for sd in structural
            )
            if has_drawdown_pattern and not current_params.get("trailing_stop", False):
                actionable.append(ParameterSuggestion(
                    parameter="trailing_stop",
                    proposed_value=True,
                    reason="High-drawdown structural pattern detected — proposing trailing stop",
                    expected_effect="Trailing stop protects profits and limits drawdown",
                ))

        if not actionable:
            # No structured suggestions — go straight to random perturbations
            return self._random_perturbations(current_params)

        varied: List[ParameterSuggestion] = []

        for suggestion in actionable:
            param = suggestion.parameter
            step = self.get_step(param)

            if self.exhausted(param):
                _log.debug("Skipping exhausted param '%s' (step=%d)", param, step)
                continue

            # Determine if the previous iteration's change for this param was beneficial
            prev_was_worse = False
            if prev_iteration is not None and not prev_iteration.is_improvement:
                # Check if this param was changed in the previous iteration
                if prev_iteration.params_before.get(param) != prev_iteration.params_after.get(param):
                    prev_was_worse = True

            varied_suggestion = self._vary_suggestion(
                suggestion, current_params, step, prev_was_worse
            )
            if varied_suggestion is not None:
                varied.append(varied_suggestion)
                self.increment_step(param)

        # If structured suggestions produced nothing, fall back to random perturbations
        # so the loop keeps exploring rather than stopping prematurely.
        if not varied:
            varied = self._random_perturbations(current_params)

        return varied

    def _random_perturbations(self, current_params: dict) -> List[ParameterSuggestion]:
        """Generate random parameter perturbations as a fallback when structured
        suggestions are exhausted.

        Picks one or two parameters from the current param set and nudges them
        by a small random amount so the loop can keep exploring without stopping.
        Uses a seeded approach based on the number of tried configs to ensure
        deterministic variation across calls.

        Args:
            current_params: Current strategy parameters.

        Returns:
            List of 1–2 ParameterSuggestion objects, or empty list if no
            perturbable parameters exist.
        """
        import random as _random

        # Seed from the number of tried configs for reproducible-but-varied exploration
        rng = _random.Random(len(self._tried_configs))
        suggestions: List[ParameterSuggestion] = []

        # Build a list of perturbable parameters in priority order
        candidates: List[str] = []
        if "stoploss" in current_params:
            candidates.append("stoploss")
        if "minimal_roi" in current_params and current_params["minimal_roi"]:
            candidates.append("minimal_roi")
        if "max_open_trades" in current_params:
            candidates.append("max_open_trades")
        if "buy_params" in current_params and current_params["buy_params"]:
            candidates.append("buy_params")
        if "sell_params" in current_params and current_params["sell_params"]:
            candidates.append("sell_params")

        if not candidates:
            _log.warning("_random_perturbations: no perturbable parameters found")
            return []

        # Shuffle and pick up to 2 to avoid always mutating the same param
        rng.shuffle(candidates)
        for param in candidates[:2]:
            suggestion = self._random_perturb_param(param, current_params, rng)
            if suggestion is not None:
                suggestions.append(suggestion)

        if suggestions:
            _log.info(
                "_random_perturbations: generated %d fallback suggestion(s): %s",
                len(suggestions),
                [s.parameter for s in suggestions],
            )
        return suggestions

    def _random_perturb_param(
        self,
        param: str,
        current_params: dict,
        rng,
    ) -> Optional[ParameterSuggestion]:
        """Randomly perturb a single parameter.

        Args:
            param: Parameter name to perturb.
            current_params: Current strategy parameters.
            rng: Random instance for reproducibility.

        Returns:
            A ParameterSuggestion, or None if no valid perturbation is possible.
        """
        if param == "stoploss":
            current = current_params.get("stoploss", -0.10)
            lo, hi = self._RANDOM_STOPLOSS_RANGE
            # Pick a random value in the valid range, biased toward current ±0.05
            delta = rng.uniform(-0.05, 0.05)
            proposed = round(max(lo, min(hi, current + delta)), 4)
            if proposed == current:
                return None
            return ParameterSuggestion(
                parameter="stoploss",
                proposed_value=proposed,
                reason=f"Random exploration: stoploss {current} → {proposed}",
                expected_effect="Exploring stoploss parameter space",
            )

        elif param == "minimal_roi":
            minimal_roi: dict = current_params.get("minimal_roi", {})
            if not minimal_roi:
                return None
            lo, hi = self._RANDOM_ROI_DELTA_RANGE
            delta = rng.uniform(lo, hi)
            proposed_roi = {k: round(v + delta, 6) for k, v in minimal_roi.items()}
            if proposed_roi == minimal_roi:
                return None
            direction = "up" if delta > 0 else "down"
            return ParameterSuggestion(
                parameter="minimal_roi",
                proposed_value=proposed_roi,
                reason=f"Random exploration: ROI targets shifted {direction} by {abs(delta):.4f}",
                expected_effect="Exploring ROI parameter space",
            )

        elif param == "max_open_trades":
            current = current_params.get("max_open_trades", 3)
            lo, hi = self._RANDOM_MOT_RANGE
            delta = rng.choice([-1, 1])
            proposed = max(lo, min(hi, current + delta))
            if proposed == current:
                return None
            return ParameterSuggestion(
                parameter="max_open_trades",
                proposed_value=proposed,
                reason=f"Random exploration: max_open_trades {current} → {proposed}",
                expected_effect="Exploring trade concurrency parameter space",
            )

        elif param in ("buy_params", "sell_params"):
            group: dict = current_params.get(param, {})
            if not group:
                return None
            numeric_keys = [k for k, v in group.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if not numeric_keys:
                return None
            target_key = rng.choice(numeric_keys)
            current_val = group[target_key]
            scale = self._RANDOM_PARAM_SCALE
            delta = current_val * rng.uniform(-scale, scale) if current_val != 0 else rng.uniform(-0.01, 0.01)
            proposed_val = round(current_val + delta, 6) if isinstance(current_val, float) else int(round(current_val + delta))
            if proposed_val == current_val:
                return None
            proposed_group = dict(group)
            proposed_group[target_key] = proposed_val
            return ParameterSuggestion(
                parameter=param,
                proposed_value=proposed_group,
                reason=f"Random exploration: {param}.{target_key} {current_val} → {proposed_val}",
                expected_effect=f"Exploring {param} parameter space",
            )

        return None

    def _vary_suggestion(
        self,
        suggestion: ParameterSuggestion,
        current_params: dict,
        step: int,
        reverse: bool,
    ) -> Optional[ParameterSuggestion]:
        """Apply step-based variation to a single suggestion.

        Args:
            suggestion: Base suggestion from RuleSuggestionService.
            current_params: Current strategy parameters.
            step: How many times this parameter has been adjusted.
            reverse: If True, try the opposite direction from the base suggestion.

        Returns:
            A modified ParameterSuggestion, or None if no valid variation exists.
        """
        param = suggestion.parameter
        multiplier = 1.0 + step * 0.5  # step 0→1x, step 1→1.5x, step 2→2x, ...

        if param == "stoploss":
            current = current_params.get("stoploss", -0.10)
            base_delta = 0.02  # tighten by 0.02 per step
            if reverse:
                # Previous tightening made things worse → try loosening instead
                delta = -base_delta * multiplier
            else:
                delta = base_delta * multiplier
            proposed = round(current + delta, 4)
            # Keep stoploss in a sane range: -0.30 to -0.01
            proposed = max(-0.30, min(-0.01, proposed))
            if proposed == current:
                return None
            direction = "Loosening" if delta < 0 else "Tightening"
            return ParameterSuggestion(
                parameter="stoploss",
                proposed_value=proposed,
                reason=f"{direction} stoploss (step {step + 1}, multiplier {multiplier:.1f}x)",
                expected_effect="Adjusted per-trade loss exposure",
            )

        elif param == "max_open_trades":
            current = current_params.get("max_open_trades", 3)
            base_delta = 1
            if reverse:
                delta = -base_delta
            else:
                delta = base_delta
            proposed = max(1, min(20, current + delta))
            if proposed == current:
                return None
            direction = "Decreasing" if delta < 0 else "Increasing"
            return ParameterSuggestion(
                parameter="max_open_trades",
                proposed_value=proposed,
                reason=f"{direction} max_open_trades (step {step + 1})",
                expected_effect="Adjusted concurrent trade exposure",
            )

        elif param == "minimal_roi":
            minimal_roi: dict = current_params.get("minimal_roi", {})
            if not minimal_roi:
                return None
            proposed_roi = dict(minimal_roi)
            # Adjust all ROI values by a step-scaled amount
            base_delta = 0.005
            if reverse:
                delta = base_delta * multiplier  # raise ROI (harder to hit)
            else:
                delta = -base_delta * multiplier  # lower ROI (easier to hit)
            for key in proposed_roi:
                proposed_roi[key] = round(proposed_roi[key] + delta, 6)
            if proposed_roi == minimal_roi:
                return None
            direction = "Raising" if delta > 0 else "Lowering"
            return ParameterSuggestion(
                parameter="minimal_roi",
                proposed_value=proposed_roi,
                reason=f"{direction} ROI targets (step {step + 1}, Δ{delta:+.4f})",
                expected_effect="Adjusted take-profit thresholds",
            )

        elif param == "trailing_stop":
            # Propose enabling trailing_stop with a conservative positive value
            current_trailing = current_params.get("trailing_stop", False)
            if current_trailing:
                # Already enabled → nothing to do
                return None
            return ParameterSuggestion(
                parameter="trailing_stop",
                proposed_value=True,
                reason=(
                    f"Enabling trailing_stop (step {step + 1}) — "
                    "high-drawdown pattern detected"
                ),
                expected_effect="Trailing stop protects profits and limits drawdown",
            )

        elif param in ("buy_params", "sell_params"):
            # Delegate to the buy/sell param variation helper
            return self._vary_buy_sell_param(suggestion, current_params, step, reverse)

        # Unknown parameter → return the base suggestion as-is on step 0 only
        if step == 0:
            return suggestion
        return None

    def _vary_buy_sell_param(
        self,
        suggestion: ParameterSuggestion,
        current_params: dict,
        step: int,
        reverse: bool,
    ) -> Optional[ParameterSuggestion]:
        """Apply step-based variation to a buy_params or sell_params suggestion.

        For numeric values, applies a step-scaled delta respecting the observed
        range from the strategy JSON. For boolean values, proposes a toggle.
        Clamps all proposed values to the valid observed range.

        Args:
            suggestion: Base suggestion targeting buy_params or sell_params.
            current_params: Current strategy parameters.
            step: How many times this parameter group has been adjusted.
            reverse: If True, try the opposite direction.

        Returns:
            A modified ParameterSuggestion, or None if no valid variation exists.
        """
        param = suggestion.parameter  # "buy_params" or "sell_params"
        current_group: dict = current_params.get(param, {})
        if not current_group:
            return None

        proposed_group = dict(current_group)
        multiplier = 1.0 + step * 0.3  # gentler scaling for indicator params
        changed_keys = []

        # Use proposed_value from the base suggestion if it's a dict with a target key
        target_key: Optional[str] = None
        if isinstance(suggestion.proposed_value, dict):
            # The suggestion may specify which sub-key to mutate
            for k in suggestion.proposed_value:
                if k in current_group:
                    target_key = k
                    break

        # If no specific key, pick the first numeric or boolean key
        if target_key is None:
            for k, v in current_group.items():
                if isinstance(v, (int, float, bool)):
                    target_key = k
                    break

        if target_key is None:
            return None

        current_val = current_group[target_key]

        if isinstance(current_val, bool):
            # Boolean toggle
            proposed_group[target_key] = not current_val
            changed_keys.append(f"{target_key}: {current_val} → {proposed_group[target_key]}")
        elif isinstance(current_val, (int, float)):
            # Numeric delta — use 5% of the current value as base step
            base_delta = abs(current_val) * 0.05 if current_val != 0 else 0.01
            delta = base_delta * multiplier * (-1 if reverse else 1)

            # Determine observed range from all values in the group for this key type
            all_vals = [v for v in current_group.values() if isinstance(v, type(current_val))]
            lo = min(all_vals) * 0.5 if all_vals else current_val * 0.5
            hi = max(all_vals) * 2.0 if all_vals else current_val * 2.0
            # Ensure lo < hi
            if lo >= hi:
                lo, hi = hi * 0.5, hi * 1.5

            proposed_val = current_val + delta
            # Clamp to observed range
            if proposed_val < lo or proposed_val > hi:
                _log.warning(
                    "_vary_buy_sell_param: clamping %s.%s from %.4f to [%.4f, %.4f]",
                    param, target_key, proposed_val, lo, hi,
                )
                proposed_val = max(lo, min(hi, proposed_val))

            if isinstance(current_val, int):
                proposed_val = int(round(proposed_val))
            else:
                proposed_val = round(proposed_val, 6)

            if proposed_val == current_val:
                return None

            proposed_group[target_key] = proposed_val
            changed_keys.append(f"{target_key}: {current_val} → {proposed_val}")
        else:
            return None

        direction = "Reversed" if reverse else "Adjusted"
        return ParameterSuggestion(
            parameter=param,
            proposed_value=proposed_group,
            reason=(
                f"{direction} {param}.{target_key} (step {step + 1}, "
                f"multiplier {multiplier:.1f}x): {', '.join(changed_keys)}"
            ),
            expected_effect=f"Adjusted indicator parameter {target_key}",
        )

    def _suggestions_from_structural(
        self,
        structural: List,
        current_params: dict,
        exit_reason_suggestions: Optional[List] = None,
    ) -> List[ParameterSuggestion]:
        """Compatibility wrapper around RuleSuggestionService structural mapping."""
        return RuleSuggestionService.suggest(
            [], current_params, structural, exit_reason_suggestions
        )


class LoopService:
    """Orchestrates the auto-optimization loop.

    Manages the state machine that drives iterative backtest → diagnose →
    suggest → apply → compare cycles. Delegates subprocess execution to
    ImproveService and reports progress via callbacks.

    Args:
        improve_service: Provides sandbox, command building, and result parsing.
    """

    def __init__(self, improve_service: ImproveService) -> None:
        self._improve_service = improve_service
        self._config: Optional[LoopConfig] = None
        self._result: Optional[LoopResult] = None
        self._rotator: Optional[SuggestionRotator] = None
        self._current_params: dict = {}
        self._current_iteration: int = 0
        self._best_score: float = float("-inf")
        self._running: bool = False
        self._ai_advisor = None  # Set via set_ai_advisor()
        self._version_manager = None  # Set via set_version_manager()
        self._last_version_id: Optional[str] = None  # Track version lineage

        # 4-Layer Diagnostic Architecture state
        self._state_4l: Optional[LoopState4L] = None
        self._pattern_knowledge = None  # Set via set_pattern_knowledge()

        # Callbacks set by the UI layer
        self._on_iteration_complete: Optional[Callable[[LoopIteration], None]] = None
        self._on_loop_complete: Optional[Callable[[LoopResult], None]] = None
        self._on_status: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """True while the loop is actively running."""
        return self._running

    @property
    def current_result(self) -> Optional[LoopResult]:
        """The in-progress or completed LoopResult, or None if not started."""
        return self._result

    def set_ai_advisor(self, ai_advisor) -> None:
        """Register an AIAdvisorService instance for AI-assisted suggestions.

        Args:
            ai_advisor: AIAdvisorService instance, or None to disable.
        """
        self._ai_advisor = ai_advisor

    def set_version_manager(self, version_manager) -> None:
        """Register a VersionManagerService for version tracking.

        Args:
            version_manager: VersionManagerService instance, or None to disable.
        """
        self._version_manager = version_manager

    def set_pattern_knowledge(self, pattern_knowledge) -> None:
        """Register a PatternKnowledgeService for 4-layer architecture.

        Args:
            pattern_knowledge: PatternKnowledgeService instance, or None to disable.
        """
        self._pattern_knowledge = pattern_knowledge

    def set_callbacks(
        self,
        on_iteration_complete: Callable[[LoopIteration], None],
        on_loop_complete: Callable[[LoopResult], None],
        on_status: Callable[[str], None],
    ) -> None:
        """Register UI callbacks for loop progress events.

        Args:
            on_iteration_complete: Called after each iteration finishes.
            on_loop_complete: Called when the loop terminates for any reason.
            on_status: Called with a status string for display in the UI.
        """
        self._on_iteration_complete = on_iteration_complete
        self._on_loop_complete = on_loop_complete
        self._on_status = on_status

    def start(
        self,
        config: LoopConfig,
        initial_params: dict,
        initial_results=None,
    ) -> None:
        """Initialise loop state. Does NOT start the first backtest.

        The UI layer calls ``next_iteration()`` to kick off the first run
        after wiring up the process callbacks.

        Args:
            config: Loop configuration (targets, max iterations, strategy).
            initial_params: Starting strategy parameters.
            initial_results: Optional pre-existing baseline BacktestResults. If
                provided, the first iteration skips the initial backtest and goes
                straight to diagnosis.
        """
        self._config = config
        self._current_params = copy.deepcopy(initial_params)
        self._rotator = SuggestionRotator(initial_params)
        self._result = LoopResult()
        self._current_iteration = 0
        self._best_score = float("-inf")
        self._running = True

        if initial_results is not None:
            # Seed the best score from the existing baseline (Training Range only)
            score = calculate_robust_score(RobustScoreInput(in_sample=initial_results.summary))
            self._best_score = score.total
            _log.info(
                "Loop started with existing baseline; score=%.4f", self._best_score
            )
        _log.info(
            "LoopService.start: strategy=%s, max_iter=%d",
            config.strategy,
            config.max_iterations,
        )

    def stop(self) -> None:
        """Request the loop to stop after the current iteration completes."""
        self._running = False
        _log.info("LoopService.stop requested")

    def should_continue(self) -> bool:
        """Return True if the loop should proceed to the next iteration.

        Checks: running flag, iteration limit, and whether the rotator has
        any remaining suggestions to try.
        """
        if not self._running:
            return False
        if self._config is None:
            return False
        if self._current_iteration >= self._config.max_iterations:
            return False
        return True



    def record_hyperopt_candidate(
        self,
        iteration: LoopIteration,
        hyperopt_results_dir,
        exit_code: int,
    ) -> Optional[dict]:
        """Process a completed hyperopt run and extract the best candidate params.

        Called by the UI layer after the hyperopt subprocess completes.

        Args:
            iteration: The iteration object to update.
            hyperopt_results_dir: Directory containing the .fthypt file.
            exit_code: Exit code from the hyperopt subprocess.

        Returns:
            Best params dict if successful, None on error.
        """
        if exit_code != 0:
            iteration.status = "error"
            iteration.error_message = f"Hyperopt exited with code {exit_code}"
            self._record_iteration(iteration)
            _log.warning(
                "Loop iter %d: hyperopt non-zero exit code %d",
                iteration.iteration_number, exit_code,
            )
            return None

        try:
            best_params = self._parse_hyperopt_result(hyperopt_results_dir)
        except (FileNotFoundError, ValueError) as exc:
            iteration.status = "error"
            iteration.error_message = str(exc)
            self._record_iteration(iteration)
            _log.warning("Loop iter %d: hyperopt parse error: %s", iteration.iteration_number, exc)
            return None

        # Update iteration with hyperopt candidate params
        iteration.params_after = {**copy.deepcopy(self._current_params), **best_params}
        iteration.changes_summary = [
            f"{k}: {self._current_params.get(k)} → {v}"
            for k, v in best_params.items()
            if self._current_params.get(k) != v
        ]
        _log.info(
            "Loop iter %d: hyperopt candidate extracted, %d param(s) changed",
            iteration.iteration_number, len(iteration.changes_summary),
        )
        return iteration.params_after



    def record_iteration_error(self, iteration: LoopIteration, error: str) -> None:
        """Record a failed iteration (backtest process error).

        Args:
            iteration: The iteration object (mutated in place with error).
            error: Error message describing the failure.
        """
        iteration.error_message = error
        iteration.status = "error"
        self._record_iteration(iteration)
        _log.warning("Loop iter %d failed: %s", iteration.iteration_number, error)

    def _build_hyperopt_command(
        self,
        config: LoopConfig,
        sandbox_dir,
        settings,
        timeframe: str = "5m",
    ):
        """Build a freqtrade hyperopt command for the current loop config.

        Args:
            config: Loop configuration with hyperopt_spaces, hyperopt_epochs,
                hyperopt_loss_function, and pairs.
            sandbox_dir: Path to the sandbox directory containing the strategy.
            settings: AppSettings instance.
            timeframe: Candle timeframe to use.

        Returns:
            OptimizeRunCommand ready for ProcessService.
        """
        from app.core.freqtrade.runners.optimize_runner import create_optimize_command

        timerange = None
        if config.date_from and config.date_to:
            timerange = f"{config.date_from}-{config.date_to}"

        extra_flags = [
            "--strategy-path", str(sandbox_dir),
        ]

        return create_optimize_command(
            settings=settings,
            strategy_name=config.strategy,
            timeframe=timeframe,
            epochs=config.hyperopt_epochs,
            timerange=timerange,
            pairs=config.pairs if config.pairs else None,
            spaces=config.hyperopt_spaces if config.hyperopt_spaces else None,
            hyperopt_loss=config.hyperopt_loss_function or None,
            extra_flags=extra_flags,
        )

    def _parse_hyperopt_result(self, hyperopt_results_dir) -> dict:
        """Parse the best parameter set from a freqtrade hyperopt results file.

        Locates the ``.fthypt`` file written by freqtrade in hyperopt_results_dir
        and extracts the best parameter set from the JSON-lines file.

        Args:
            hyperopt_results_dir: Path to the directory containing ``.fthypt`` files.

        Returns:
            Dict of best parameters from the hyperopt run.

        Raises:
            FileNotFoundError: If no ``.fthypt`` file is found.
            ValueError: If the file cannot be parsed.
        """
        import json as _json
        from pathlib import Path as _Path

        results_dir = _Path(hyperopt_results_dir)
        fthypt_files = list(results_dir.glob("*.fthypt"))
        if not fthypt_files:
            raise FileNotFoundError(
                f"No .fthypt file found in hyperopt results dir: {results_dir}"
            )

        # Use the most recently modified file
        fthypt_path = max(fthypt_files, key=lambda p: p.stat().st_mtime)

        best_params: Optional[dict] = None
        best_loss: Optional[float] = None

        try:
            lines = fthypt_path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = parse_json_string(line)
                except Exception:
                    continue
                # Each line is a hyperopt result; find the one with the best (lowest) loss
                loss = entry.get("loss")
                params = entry.get("params_dict") or entry.get("params") or {}
                if loss is not None and params:
                    if best_loss is None or loss < best_loss:
                        best_loss = loss
                        best_params = params
        except OSError as exc:
            raise ValueError(f"Failed to read .fthypt file {fthypt_path}: {exc}") from exc

        if best_params is None:
            raise ValueError(
                f"No valid parameter entries found in .fthypt file: {fthypt_path}"
            )

        _log.info(
            "_parse_hyperopt_result: best_loss=%.4f, params=%s",
            best_loss or 0.0,
            list(best_params.keys()),
        )
        return best_params

    def _record_iteration(self, iteration: LoopIteration) -> None:
        """Append iteration to result, create version, and fire the callback."""
        self._result.iterations.append(iteration)

        # Create version snapshot if version manager is available
        if self._version_manager is not None and iteration.summary is not None:
            try:
                from app.core.models.exit_reason_models import ExitReasonAnalysis

                exit_reason_analysis = None
                if iteration.summary and hasattr(iteration, 'diagnosed_structural'):
                    # Extract exit reason analysis if available
                    for diag in iteration.diagnosed_structural or []:
                        if isinstance(diag, ExitReasonAnalysis):
                            exit_reason_analysis = diag.to_dict() if hasattr(diag, 'to_dict') else None

                version = self._version_manager.create_version(
                    strategy_name=self._config.strategy,
                    params=iteration.params_after,
                    summary=iteration.summary,
                    iteration_number=iteration.iteration_number,
                    changes_summary=iteration.changes_summary,
                    parent_version_id=self._last_version_id,
                    score=iteration.score.total if iteration.score else 0.0,
                    exit_reason_analysis=exit_reason_analysis,
                )
                self._last_version_id = version.version_id
                iteration.version_id = version.version_id  # Store in iteration for reference

                _log.debug(
                    "Created version %s for iteration %d",
                    version.version_id,
                    iteration.iteration_number,
                )
            except Exception as e:
                _log.warning("Failed to create version for iteration %d: %s", iteration.iteration_number, e)

        if self._on_iteration_complete is not None:
            self._on_iteration_complete(iteration)

    def _emit_status(self, message: str) -> None:
        """Fire the status callback if registered."""
        if self._on_status is not None:
            self._on_status(message)

    def _parse_config_dates(self, config: LoopConfig):
        """Return parsed (date_from, date_to) datetimes, or None when invalid."""
        if not config.date_from or not config.date_to:
            return None

        from datetime import datetime

        fmt = "%Y%m%d"
        try:
            date_from = datetime.strptime(config.date_from, fmt)
            date_to = datetime.strptime(config.date_to, fmt)
        except ValueError:
            return None

        if date_to <= date_from:
            return None
        return date_from, date_to

    def compute_full_timerange(self, config: LoopConfig) -> str:
        """Return the full configured timerange, or an empty string when unset."""
        if not config.date_from or not config.date_to:
            return ""
        return f"{config.date_from}-{config.date_to}"

    def compute_in_sample_timerange(self, config: LoopConfig) -> str:
        """Return the in-sample timerange used for Gate 1 and stress testing.
        
        The in-sample range ends one day before the OOS start date, ensuring
        the boundary day is excluded from in-sample and included in OOS.
        This creates a clean split with no gap or overlap between the two ranges.
        """
        parsed = self._parse_config_dates(config)
        if parsed is None:
            return self.compute_full_timerange(config)

        from datetime import timedelta

        date_from, date_to = parsed
        total_days = (date_to - date_from).days
        if total_days <= 1:
            return self.compute_full_timerange(config)

        oos_days = max(1, int(total_days * config.oos_split_pct / 100.0))
        if oos_days >= total_days:
            oos_days = total_days - 1
        oos_start = date_to - timedelta(days=oos_days)
        return f"{date_from.strftime('%Y%m%d')}-{(oos_start - timedelta(days=1)).strftime('%Y%m%d')}"

    def compute_oos_timerange(self, config: LoopConfig) -> str:
        """Return the held-out out-of-sample timerange.
        
        The OOS range starts at the OOS start date, which is one day after
        the in-sample end date. This ensures the boundary day is included in
        OOS only, creating a clean split with no gap or overlap.
        """
        parsed = self._parse_config_dates(config)
        if parsed is None:
            return ""

        from datetime import timedelta

        date_from, date_to = parsed
        total_days = (date_to - date_from).days
        if total_days <= 0:
            return ""

        oos_days = max(1, int(total_days * config.oos_split_pct / 100.0))
        oos_start = date_to - timedelta(days=oos_days)
        return f"{oos_start.strftime('%Y%m%d')}-{date_to.strftime('%Y%m%d')}"

    def compute_walk_forward_timeranges(self, config: LoopConfig) -> List[str]:
        """Return per-fold timeranges for the walk-forward gate."""
        parsed = self._parse_config_dates(config)
        if parsed is None:
            return []

        from datetime import timedelta

        date_from, date_to = parsed
        total_days = (date_to - date_from).days
        k = max(2, config.walk_forward_folds)
        fold_days = total_days // k
        if total_days <= 0 or fold_days < 1:
            return []

        timeranges: List[str] = []
        for i in range(k):
            fold_start = date_from + timedelta(days=i * fold_days)
            fold_end = date_from + timedelta(days=(i + 1) * fold_days)
            if i == k - 1:
                fold_end = date_to
            timeranges.append(
                f"{fold_start.strftime('%Y%m%d')}-{fold_end.strftime('%Y%m%d')}"
            )
        return timeranges

    def build_in_sample_gate_result(self, summary: BacktestSummary) -> GateResult:
        """Wrap the Gate 1 summary as a GateResult."""
        return GateResult(
            gate_name="in_sample",
            passed=True,
            metrics=summary,
        )

    def build_oos_gate_result(
        self,
        in_sample_summary: BacktestSummary,
        oos_summary: Optional[BacktestSummary],
    ) -> GateResult:
        """Build the out-of-sample gate result from parsed summaries."""
        if oos_summary is None:
            return GateResult(
                gate_name="out_of_sample",
                passed=False,
                failure_reason="OOS backtest failed",
            )

        threshold = in_sample_summary.total_profit * 0.5
        passed = oos_summary.total_profit >= threshold
        reason = None if passed else (
            f"OOS profit {oos_summary.total_profit:.2f}% < 50% of "
            f"in-sample profit {in_sample_summary.total_profit:.2f}%"
        )
        return GateResult(
            gate_name="out_of_sample",
            passed=passed,
            metrics=oos_summary,
            failure_reason=reason,
        )

    def build_walk_forward_gate_result(
        self,
        config: LoopConfig,
        fold_summaries: List[BacktestSummary],
    ) -> GateResult:
        """Build the walk-forward gate result from per-fold summaries."""
        if not fold_summaries:
            return GateResult(
                gate_name="walk_forward",
                passed=False,
                failure_reason="All walk-forward folds failed",
            )

        profitable_folds = sum(1 for fs in fold_summaries if fs.total_profit > 0)
        pct_profitable = profitable_folds / len(fold_summaries)
        passed = pct_profitable >= 0.60
        reason = None if passed else (
            f"Only {profitable_folds}/{len(fold_summaries)} folds profitable "
            f"({pct_profitable * 100:.0f}% < 60%)"
        )
        return GateResult(
            gate_name="walk_forward",
            passed=passed,
            fold_summaries=fold_summaries,
            failure_reason=reason,
        )

    def build_stress_gate_result(
        self,
        config: LoopConfig,
        stress_summary: Optional[BacktestSummary],
    ) -> GateResult:
        """Build the stress-test gate result from a parsed summary."""
        if stress_summary is None:
            return GateResult(
                gate_name="stress_test",
                passed=False,
                failure_reason="Stress backtest failed",
            )

        threshold = config.target_profit_pct * config.stress_profit_target_pct / 100.0
        passed = stress_summary.total_profit >= threshold
        reason = None if passed else (
            f"Stress profit {stress_summary.total_profit:.2f}% < "
            f"{config.stress_profit_target_pct:.0f}% of target "
            f"({threshold:.2f}%)"
        )
        return GateResult(
            gate_name="stress_test",
            passed=passed,
            metrics=stress_summary,
            failure_reason=reason,
        )

    def build_consistency_gate_result(
        self,
        config: LoopConfig,
        fold_summaries: List[BacktestSummary],
    ) -> GateResult:
        """Build the consistency gate result from walk-forward fold profits."""
        if not fold_summaries or len(fold_summaries) < 2:
            return GateResult(
                gate_name="consistency",
                passed=True,
            )

        try:
            fold_profits = [fs.total_profit for fs in fold_summaries]
            mean_profit = statistics.mean(fold_profits)
            std_profit = statistics.stdev(fold_profits)
            cv = (std_profit / abs(mean_profit) * 100.0) if mean_profit != 0 else float("inf")
            passed = cv <= config.consistency_threshold_pct
            reason = None if passed else (
                f"Profit CV {cv:.1f}% exceeds threshold "
                f"{config.consistency_threshold_pct:.0f}%"
            )
            return GateResult(
                gate_name="consistency",
                passed=passed,
                failure_reason=reason,
            )
        except Exception as exc:
            return GateResult(
                gate_name="consistency",
                passed=False,
                failure_reason=f"Consistency gate error: {exc}",
            )

    def evaluate_gate1_hard_filters(
        self,
        gate1_result: GateResult,
        config: LoopConfig,
        trades: Optional[List[BacktestTrade]] = None,
    ) -> List[HardFilterFailure]:
        """Evaluate post-Gate1 hard filters."""
        return HardFilterService.evaluate_post_gate1(gate1_result, config, trades)

    def evaluate_post_gate_hard_filters(
        self,
        gate_result: GateResult,
        config: LoopConfig,
    ) -> List[HardFilterFailure]:
        """Evaluate gate-specific post-gate hard filters."""
        return HardFilterService.evaluate_post_gate(gate_result.gate_name, gate_result, config)

    def _mark_hard_filter_rejection(
        self,
        iteration: LoopIteration,
        gate_name: str,
        failures: List[HardFilterFailure],
    ) -> None:
        """Mutate iteration to represent a hard-filter rejection."""
        iteration.status = "hard_filter_rejected"
        iteration.is_improvement = False
        iteration.validation_gate_reached = gate_name
        iteration.validation_gate_passed = False
        iteration.hard_filter_failures = list(failures)

    def record_hard_filter_rejection(
        self,
        iteration: LoopIteration,
        gate_name: str,
        failures: List[HardFilterFailure],
    ) -> None:
        """Record a hard-filter rejection as a completed iteration."""
        self._mark_hard_filter_rejection(iteration, gate_name, failures)
        self._record_iteration(iteration)

    def _mark_gate_failure(
        self,
        iteration: LoopIteration,
        gate_result: GateResult,
    ) -> None:
        """Mutate iteration to represent a validation gate failure."""
        iteration.status = "gate_failed"
        iteration.is_improvement = False
        iteration.validation_gate_reached = gate_result.gate_name
        iteration.validation_gate_passed = False

    def record_gate_failure(
        self,
        iteration: LoopIteration,
        gate_result: GateResult,
    ) -> None:
        """Record a validation gate failure as a completed iteration."""
        self._mark_gate_failure(iteration, gate_result)
        self._record_iteration(iteration)

    def _eligible_best_iterations(self) -> List[LoopIteration]:
        """Return iterations eligible to be considered the best result."""
        return [
            iteration
            for iteration in (self._result.iterations if self._result is not None else [])
            if iteration.validation_gate_passed
            and iteration.status == "success"
            and iteration.score is not None
            and not iteration.below_min_trades
        ]

    def prepare_next_iteration(
        self,
        latest_summary: BacktestSummary,
        diagnosis_input: Optional[DiagnosisInput] = None,
    ) -> Optional[Tuple[LoopIteration, List[ParameterSuggestion]]]:
        """Analyse the latest validated results and prepare the next iteration.
        
        This is the CANONICAL method for preparing loop iterations. It handles:
        - Target checking and early termination
        - Hyperopt mode sentinel iteration creation
        - Rule-based diagnosis and suggestion generation
        - Duplicate configuration detection with fallback logic
        - AI Advisor integration
        
        For rule_based mode: runs diagnosis and suggestion rotation to produce
        the candidate params for the next backtest.
        For hyperopt mode: returns a sentinel iteration with empty suggestions;
        the UI layer is responsible for running hyperopt and calling
        record_hyperopt_candidate() with the result.

        Args:
            latest_summary: BacktestSummary from the most recent backtest.
            diagnosis_input: Optional DiagnosisInput for more comprehensive diagnosis.
                If None, a minimal input using only in_sample is constructed.

        Returns:
            Tuple of (LoopIteration, suggestions) ready to execute, or None if
            the loop should terminate.
        """
        if self._config is None or self._rotator is None or self._result is None:
            return None

        prev_iteration = self._result.iterations[-1] if self._result.iterations else None
        self._current_iteration += 1

        if (
            prev_iteration is not None
            and prev_iteration.validation_gate_passed
            and self._config.stop_on_first_profitable
            and check_targets_met(latest_summary, self._config)
        ):
            from pathlib import Path

            iteration = LoopIteration(
                iteration_number=self._current_iteration,
                params_before=copy.deepcopy(self._current_params),
                params_after=copy.deepcopy(self._current_params),
                changes_summary=[],
                summary=latest_summary,
                is_improvement=True,
                status="success",
                sandbox_path=Path("."),
                validation_gate_reached=prev_iteration.validation_gate_reached or "in_sample",
                validation_gate_passed=True,
            )
            self._record_iteration(iteration)
            self._result.target_reached = True
            self._result.stop_reason = "All profitability targets met"
            self._running = False
            _log.info("Loop: targets met at iteration %d", self._current_iteration)
            return None

        if self._config.iteration_mode == "hyperopt":
            from pathlib import Path

            iteration = LoopIteration(
                iteration_number=self._current_iteration,
                params_before=copy.deepcopy(self._current_params),
                params_after=copy.deepcopy(self._current_params),
                changes_summary=["[hyperopt mode - awaiting hyperopt result]"],
                sandbox_path=Path("."),
            )
            self._emit_status(
                f"Iteration {self._current_iteration}/{self._config.max_iterations} - "
                "running hyperopt..."
            )
            return iteration, []

        diagnosis_input = diagnosis_input or DiagnosisInput(in_sample=latest_summary)
        bundle = ResultsDiagnosisService.diagnose(diagnosis_input)
        issues = bundle.issues
        structural = bundle.structural

        _log.debug(
            "Loop iter %d: %d issue(s), %d structural pattern(s), %d exit suggestions diagnosed",
            self._current_iteration,
            len(issues),
            len(structural),
            len(bundle.exit_reason_suggestions),
        )

        suggestions = self._rotator.generate_suggestions(
            issues,
            self._current_params,
            prev_iteration,
            structural,
            bundle.exit_reason_suggestions,
        )
        if not suggestions:
            self._result.stop_reason = "Optimization complete: No further improvements suggested"
            self._running = False
            _log.info("Loop: no more suggestions at iteration %d", self._current_iteration)
            return None

        candidate_params = copy.deepcopy(self._current_params)
        actionable_suggestions: List[ParameterSuggestion] = []
        for suggestion in suggestions:
            if candidate_params.get(suggestion.parameter) == suggestion.proposed_value:
                _log.debug(
                    "Loop iter %d: skipping no-op suggestion for %s",
                    self._current_iteration,
                    suggestion.parameter,
                )
                continue
            candidate_params[suggestion.parameter] = copy.deepcopy(suggestion.proposed_value)
            actionable_suggestions.append(suggestion)

        ai_changes: dict = {}
        if self._config.ai_advisor_enabled and self._ai_advisor is not None:
            try:
                self._emit_status("Waiting for AI Advisor...")
                prompt = self._ai_advisor.build_prompt(
                    self._config.strategy,
                    self._current_params,
                    latest_summary,
                    bundle.issues + bundle.structural,
                )
                ai_suggestion = self._ai_advisor.request_suggestion(prompt)
                if ai_suggestion:
                    ai_changes = {
                        key: value
                        for key, value in ai_suggestion.items()
                        if candidate_params.get(key) != value
                    }
                    for key, value in ai_changes.items():
                        candidate_params[key] = copy.deepcopy(value)
                    if ai_changes:
                        _log.info(
                            "Loop iter %d: AI Advisor suggested %d changed param(s)",
                            self._current_iteration,
                            len(ai_changes),
                        )
            except Exception as exc:
                _log.warning("Loop iter %d: AI Advisor failed: %s", self._current_iteration, exc)

        changes_summary = [
            f"{param}: {self._current_params.get(param)} -> {new_value}"
            for param, new_value in candidate_params.items()
            if self._current_params.get(param) != new_value
        ]

        if not changes_summary:
            self._result.stop_reason = "Optimization complete: All parameters already at optimal values"
            self._running = False
            _log.info("Loop: no-op candidate avoided at iteration %d", self._current_iteration)
            return None

        if self._rotator.already_tried(candidate_params):
            if actionable_suggestions:
                fallback = actionable_suggestions[0]
                fallback_params = copy.deepcopy(self._current_params)
                fallback_params[fallback.parameter] = copy.deepcopy(fallback.proposed_value)
                fallback_changes = [
                    f"{param}: {self._current_params.get(param)} -> {new_value}"
                    for param, new_value in fallback_params.items()
                    if self._current_params.get(param) != new_value
                ]
                if fallback_changes and not self._rotator.already_tried(fallback_params):
                    candidate_params = fallback_params
                    actionable_suggestions = [fallback]
                    changes_summary = fallback_changes

            if self._rotator.already_tried(candidate_params):
                self._result.stop_reason = "Optimization complete: All parameter variations have been tested"
                self._running = False
                _log.info("Loop: duplicate candidate exhausted at iteration %d", self._current_iteration)
                return None

        self._rotator.mark_tried(candidate_params)

        from pathlib import Path

        iteration = LoopIteration(
            iteration_number=self._current_iteration,
            params_before=copy.deepcopy(self._current_params),
            params_after=candidate_params,
            changes_summary=changes_summary,
            sandbox_path=Path("."),
            ai_suggested=bool(ai_changes),
            ai_suggestion_reason=(
                "AI Advisor changed: " + ", ".join(sorted(ai_changes.keys()))
                if ai_changes else None
            ),
            diagnosed_structural=[sd.failure_pattern for sd in structural],
        )

        self._emit_status(
            f"Iteration {self._current_iteration}/{self._config.max_iterations} - "
            f"applying {len(actionable_suggestions)} suggestion(s): "
            + ", ".join(changes_summary)
        )

        return iteration, actionable_suggestions

    def record_iteration_result(
        self,
        iteration: LoopIteration,
        summary: BacktestSummary,
        score_input: Optional[RobustScoreInput] = None,
    ) -> bool:
        """Record the backtest result for a fully-evaluated iteration.
        
        This is the CANONICAL method for recording iteration results. It:
        - Guards against zero trades and below-minimum trades
        - Computes robust score from multi-gate validation results
        - Checks if iteration is an improvement (requires validation_gate_passed AND status=="success")
        - Updates best iteration tracking
        - Records iteration to result history
        
        Args:
            iteration: The iteration object (mutated in place with results/score).
            summary: BacktestSummary from the candidate backtest (Gate 1).
            score_input: Optional full RobustScoreInput for multi-gate scoring.
                If None, a minimal input using only in_sample is constructed.

        Returns:
            True if this iteration improved over the previous best.
        """
        iteration.summary = summary

        if summary.total_trades == 0:
            iteration.status = "zero_trades"
            iteration.is_improvement = False
            self._record_iteration(iteration)
            _log.info("Loop iter %d: zero trades - not eligible for best", iteration.iteration_number)
            return False

        if self._config and summary.total_trades < self._config.target_min_trades:
            iteration.below_min_trades = True

        if score_input is None:
            score_input = RobustScoreInput(in_sample=summary)
        robust_score = calculate_robust_score(score_input)
        iteration.score = robust_score

        is_improvement = (
            iteration.validation_gate_passed
            and iteration.status == "success"
            and not iteration.below_min_trades
            and robust_score.total > self._best_score
        )
        iteration.is_improvement = is_improvement

        if is_improvement:
            self._best_score = robust_score.total
            self._current_params = copy.deepcopy(iteration.params_after)
            self._result.best_iteration = iteration
            _log.info(
                "Loop iter %d: improvement! score=%.4f profit=%.2f%%",
                iteration.iteration_number,
                robust_score.total,
                summary.total_profit,
            )
        else:
            _log.info(
                "Loop iter %d: no improvement. score=%.4f (best=%.4f)",
                iteration.iteration_number,
                robust_score.total,
                self._best_score,
            )

        self._record_iteration(iteration)
        return is_improvement

    def finalize(self, stop_reason: str = "") -> LoopResult:
        """Finalize the loop and choose the best validated successful iteration.
        
        This is the CANONICAL method for finalizing the loop. It:
        - Stops the running flag
        - Sets the stop reason if not already set
        - Selects the best iteration from eligible candidates using _eligible_best_iterations()
        - Logs final loop statistics
        
        Args:
            stop_reason: Human-readable reason the loop stopped (if not already set).

        Returns:
            The completed LoopResult with best_iteration selected.
        """
        self._running = False
        if stop_reason and not self._result.stop_reason:
            self._result.stop_reason = stop_reason

        eligible = self._eligible_best_iterations()
        self._result.best_iteration = (
            max(eligible, key=lambda iteration: iteration.score.total)
            if eligible else None
        )

        _log.info(
            "Loop finalized: %d iterations, best_score=%.4f, reason=%s",
            len(self._result.iterations),
            self._best_score,
            self._result.stop_reason,
        )
        return self._result

    def _run_oos_gate(
        self,
        config: LoopConfig,
        sandbox_dir,
        run_backtest_fn: Callable,
        in_sample_summary: Optional[BacktestSummary] = None,
    ) -> GateResult:
        """Run the out-of-sample validation gate."""
        in_sample_timerange = self.compute_in_sample_timerange(config)
        oos_timerange = self.compute_oos_timerange(config)
        if not in_sample_timerange or not oos_timerange:
            return GateResult(
                gate_name="out_of_sample",
                passed=False,
                failure_reason="No valid date range configured for OOS gate",
            )

        try:
            reference_summary = in_sample_summary
            if reference_summary is None:
                reference_summary = run_backtest_fn(in_sample_timerange, sandbox_dir)
            if reference_summary is None:
                return GateResult(
                    gate_name="out_of_sample",
                    passed=False,
                    failure_reason="In-sample backtest failed during OOS gate",
                )

            oos_summary = run_backtest_fn(oos_timerange, sandbox_dir)
            return self.build_oos_gate_result(reference_summary, oos_summary)
        except Exception as exc:
            _log.warning("OOS gate error: %s", exc)
            return GateResult(
                gate_name="out_of_sample",
                passed=False,
                failure_reason=f"OOS gate error: {exc}",
            )

    def _run_walk_forward_gate(
        self,
        config: LoopConfig,
        sandbox_dir,
        run_backtest_fn: Callable,
    ) -> GateResult:
        """Run the walk-forward validation gate."""
        timeranges = self.compute_walk_forward_timeranges(config)
        if not timeranges:
            return GateResult(
                gate_name="walk_forward",
                passed=False,
                failure_reason="No valid date range configured for walk-forward gate",
            )

        try:
            fold_summaries: List[BacktestSummary] = []
            for fold_index, timerange in enumerate(timeranges, start=1):
                summary = run_backtest_fn(timerange, sandbox_dir)
                if summary is not None:
                    fold_summaries.append(summary)
                else:
                    _log.warning(
                        "Walk-forward fold %d/%d failed",
                        fold_index,
                        len(timeranges),
                    )
            return self.build_walk_forward_gate_result(config, fold_summaries)
        except Exception as exc:
            _log.warning("Walk-forward gate error: %s", exc)
            return GateResult(
                gate_name="walk_forward",
                passed=False,
                failure_reason=f"Walk-forward gate error: {exc}",
            )

    def _run_stress_gate(
        self,
        config: LoopConfig,
        sandbox_dir,
        run_backtest_fn: Callable,
        in_sample_timerange: str,
    ) -> GateResult:
        """Run the stress-test validation gate."""
        try:
            stress_summary = run_backtest_fn(
                in_sample_timerange,
                sandbox_dir,
                fee_multiplier=config.stress_fee_multiplier,
                slippage_pct=config.stress_slippage_pct,
            )
            return self.build_stress_gate_result(config, stress_summary)
        except Exception as exc:
            _log.warning("Stress gate error: %s", exc)
            return GateResult(
                gate_name="stress_test",
                passed=False,
                failure_reason=f"Stress gate error: {exc}",
            )

    def _run_consistency_gate(
        self,
        config: LoopConfig,
        fold_summaries: List[BacktestSummary],
    ) -> GateResult:
        """Run the consistency validation gate."""
        return self.build_consistency_gate_result(config, fold_summaries)

    def run_gate_sequence(
        self,
        iteration: LoopIteration,
        in_sample_summary,
        config: LoopConfig,
        sandbox_dir,
        run_backtest_fn: Optional[Callable] = None,
    ) -> bool:
        """Run the full validation ladder with interleaved hard filters."""
        gate1 = self.build_in_sample_gate_result(in_sample_summary)
        iteration.gate_results.append(gate1)
        iteration.validation_gate_reached = "in_sample"

        gate1_failures = self.evaluate_gate1_hard_filters(gate1, config)
        if gate1_failures:
            self._mark_hard_filter_rejection(iteration, "in_sample", gate1_failures)
            return False

        if run_backtest_fn is None:
            iteration.status = "success"
            iteration.validation_gate_passed = True
            return True

        gate2 = self._run_oos_gate(
            config,
            sandbox_dir,
            run_backtest_fn,
            in_sample_summary=in_sample_summary,
        )
        iteration.gate_results.append(gate2)
        iteration.validation_gate_reached = "out_of_sample"
        if not gate2.passed:
            self._mark_gate_failure(iteration, gate2)
            return False

        gate2_failures = self.evaluate_post_gate_hard_filters(gate2, config)
        if gate2_failures:
            self._mark_hard_filter_rejection(iteration, "out_of_sample", gate2_failures)
            return False

        if config.validation_mode == "quick":
            iteration.status = "success"
            iteration.validation_gate_passed = True
            return True

        gate3 = self._run_walk_forward_gate(config, sandbox_dir, run_backtest_fn)
        iteration.gate_results.append(gate3)
        iteration.validation_gate_reached = "walk_forward"
        if not gate3.passed:
            self._mark_gate_failure(iteration, gate3)
            return False

        gate3_failures = self.evaluate_post_gate_hard_filters(gate3, config)
        if gate3_failures:
            self._mark_hard_filter_rejection(iteration, "walk_forward", gate3_failures)
            return False

        def _stress_run(timerange, sdir, fee_multiplier=1.0, slippage_pct=0.0):
            return run_backtest_fn(
                timerange,
                sdir,
                fee_multiplier=fee_multiplier,
                slippage_pct=slippage_pct,
            )

        gate4 = self._run_stress_gate(
            config,
            sandbox_dir,
            _stress_run,
            self.compute_in_sample_timerange(config),
        )
        iteration.gate_results.append(gate4)
        iteration.validation_gate_reached = "stress_test"
        if not gate4.passed:
            self._mark_gate_failure(iteration, gate4)
            return False

        gate5 = self._run_consistency_gate(config, gate3.fold_summaries or [])
        iteration.gate_results.append(gate5)
        iteration.validation_gate_reached = "consistency"
        if not gate5.passed:
            self._mark_gate_failure(iteration, gate5)
            return False

        iteration.status = "success"
        iteration.validation_gate_passed = True
        return True

    # ------------------------------------------------------------------
    # 4-Layer Diagnostic Architecture Methods
    # ------------------------------------------------------------------

    def prepare_next_iteration_4l(
        self,
        latest_summary: BacktestSummary,
    ) -> Optional[Tuple[LoopIteration, List[ParameterSuggestion]]]:
        """Prepare next iteration using 4-layer diagnostic architecture.
        
        This is an alternative to prepare_next_iteration() that uses the
        4-layer architecture: PatternEngine → DecisionEngine → ExecutionEngine → EvaluationEngine.
        
        Args:
            latest_summary: BacktestSummary from the most recent backtest.
            
        Returns:
            Tuple of (LoopIteration, suggestions) ready to execute, or None if
            the loop should terminate.
        """
        if self._config is None or self._result is None:
            return None
        
        # Initialize 4-layer state if not already done
        if self._state_4l is None:
            self._state_4l = LoopState4L(
                params=copy.deepcopy(self._current_params),
                last_summary=None,
                candidate_actions=[],
                fallback_index=0,
                tried_actions=set(),
                iteration=self._current_iteration,
            )
        
        prev_iteration = self._result.iterations[-1] if self._result.iterations else None
        self._current_iteration += 1
        self._state_4l.iteration = self._current_iteration
        
        # Check targets
        if (
            prev_iteration is not None
            and prev_iteration.validation_gate_passed
            and self._config.stop_on_first_profitable
            and check_targets_met(latest_summary, self._config)
        ):
            self._result.target_reached = True
            self._result.stop_reason = "All profitability targets met"
            self._running = False
            return None
        
        # 1-2. Detect patterns using PatternEngine (pure function)
        patterns = PatternDatabase.get_all()
        diagnoses = PatternEngine.detect(latest_summary, patterns)
        
        # 3. Select action: try candidate queue first, then DecisionEngine
        action = None
        if self._state_4l.candidate_actions:
            action = self._state_4l.candidate_actions.pop(0)  # FIFO exploration
        else:
            # Get knowledge for DecisionEngine
            knowledge = {}
            if self._pattern_knowledge:
                knowledge = self._pattern_knowledge.get_data()
            
            action = DecisionEngine.select(
                diagnoses,
                patterns,
                knowledge,
                self._state_4l.iteration
            )
        
        # 4. Fallback if no action or low confidence (emergency only)
        avg_confidence = sum(d.confidence for d in diagnoses) / len(diagnoses) if diagnoses else 0
        if not action or (diagnoses and avg_confidence < 0.3):
            action = self._get_fallback_action_4l()
        
        if not action:
            self._result.stop_reason = "Optimization complete: No further improvements suggested"
            self._running = False
            return None
        
        # 5. Track tried action with iteration (allows learning in different contexts)
        self._state_4l.tried_actions.add((action.id, self._state_4l.iteration))
        
        # 6. Apply action using ExecutionEngine (deterministic)
        new_params = ExecutionEngine.apply(action, self._current_params)
        
        # Build changes summary
        changes_summary = [
            f"{param}: {self._current_params.get(param)} -> {new_value}"
            for param, new_value in new_params.items()
            if self._current_params.get(param) != new_value
        ]
        
        if not changes_summary:
            self._result.stop_reason = "Optimization complete: All parameters already at optimal values"
            self._running = False
            return None
        
        # Check if already tried
        if self._rotator and self._rotator.already_tried(new_params):
            # Try fallback
            fallback_action = self._get_fallback_action_4l()
            if fallback_action:
                new_params = ExecutionEngine.apply(fallback_action, self._current_params)
                changes_summary = [
                    f"{param}: {self._current_params.get(param)} -> {new_value}"
                    for param, new_value in new_params.items()
                    if self._current_params.get(param) != new_value
                ]
                action = fallback_action
            
            if self._rotator and self._rotator.already_tried(new_params):
                self._result.stop_reason = "Optimization complete: All parameter variations have been tested"
                self._running = False
                return None
        
        if self._rotator:
            self._rotator.mark_tried(new_params)
        
        # Create suggestions for compatibility
        suggestions = [
            ParameterSuggestion(
                parameter=action.parameter,
                current_value=self._current_params.get(action.parameter),
                proposed_value=new_params.get(action.parameter),
                reason=f"4L pattern: {action.pattern_id}",
            )
        ]
        
        # Create iteration
        from pathlib import Path
        
        iteration = LoopIteration(
            iteration_number=self._current_iteration,
            params_before=copy.deepcopy(self._current_params),
            params_after=new_params,
            changes_summary=changes_summary,
            sandbox_path=Path("."),
            ai_suggested=False,
            ai_suggestion_reason=None,
            diagnosed_structural=[action.pattern_id] if action.pattern_id != "fallback" else [],
        )
        
        self._emit_status(
            f"Iteration {self._current_iteration}/{self._config.max_iterations} - "
            f"applying 4L action: {action.id} ({action.pattern_id})"
        )
        
        # Store action in iteration for later knowledge update
        iteration._4l_action = action
        
        return iteration, suggestions

    def record_iteration_result_4l(
        self,
        iteration: LoopIteration,
        old_summary: BacktestSummary,
        new_summary: BacktestSummary,
    ) -> bool:
        """Record iteration result using 4-layer evaluation.
        
        Args:
            iteration: The iteration object.
            old_summary: Previous backtest summary.
            new_summary: New backtest summary.
            
        Returns:
            True if this iteration improved over the previous best.
        """
        # Get the action from the iteration
        action = getattr(iteration, '_4l_action', None)
        if not action:
            # Fallback to regular evaluation
            return self.record_iteration_result(iteration, new_summary)
        
        # Evaluate using EvaluationEngine
        result = EvaluationEngine.evaluate(old_summary, new_summary)
        
        # Update knowledge
        if self._pattern_knowledge:
            self._pattern_knowledge.update(
                action.pattern_id,
                action.id,
                result["improved"]
            )
        
        # Build debug log
        log_data = {
            "pattern_id": action.pattern_id,
            "action": action.id,
            "metrics_before": {
                "profit": old_summary.profit_pct if old_summary else None,
                "drawdown": old_summary.max_drawdown if old_summary else None,
                "sharpe": old_summary.sharpe_ratio if old_summary else None,
                "win_rate": old_summary.win_rate if old_summary else None,
                "trades": old_summary.total_trades if old_summary else None,
            },
            "metrics_after": {
                "profit": new_summary.profit_pct,
                "drawdown": new_summary.max_drawdown,
                "sharpe": new_summary.sharpe_ratio,
                "win_rate": new_summary.win_rate,
                "trades": new_summary.total_trades,
            },
            "improved": result["improved"],
            "score_diff": result["score_diff"],
        }
        
        _log.debug("4L iteration %d: %s", iteration.iteration_number, log_data)
        
        # Record as regular iteration
        return self.record_iteration_result(iteration, new_summary)

    def _get_fallback_action_4l(self) -> Optional[Action]:
        """Get fallback action for 4-layer architecture (emergency only).
        
        Returns:
            Fallback Action or None if exhausted.
        """
        if self._state_4l is None:
            return None
        
        while self._state_4l.fallback_index < len(_FALLBACK_ACTIONS):
            fallback = _FALLBACK_ACTIONS[self._state_4l.fallback_index]
            self._state_4l.fallback_index += 1
            if (fallback.id, self._state_4l.iteration) not in self._state_4l.tried_actions:
                return fallback
        
        return None

    def reset_4l_state(self) -> None:
        """Reset the 4-layer architecture state."""
        self._state_4l = None
        _log.info("Reset 4-layer architecture state")
