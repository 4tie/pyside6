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

from app.core.backtests.results_models import BacktestSummary
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
from app.core.services.improve_service import ImproveService
from app.core.services.results_diagnosis_service import ResultsDiagnosisService
from app.core.services.rule_suggestion_service import RuleSuggestionService
from app.core.utils.app_logger import get_logger

_log = get_logger("services.loop")

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


def _norm(value: float, lo: float, hi: float) -> float:
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


def _is_nan_or_none(v) -> bool:
    """Return True if v is None or a float NaN."""
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False


def _normalize_summary(summary: BacktestSummary) -> BacktestSummary:
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

    if _is_nan_or_none(result.sharpe_ratio):
        _log.warning(
            "_normalize_summary: sharpe_ratio is None/NaN for strategy '%s' — substituting 0.0",
            summary.strategy,
        )
        result.sharpe_ratio = 0.0

    if _is_nan_or_none(result.profit_factor):
        _log.warning(
            "_normalize_summary: profit_factor is None/NaN for strategy '%s' — substituting 0.0",
            summary.strategy,
        )
        result.profit_factor = 0.0

    if _is_nan_or_none(result.win_rate):
        _log.warning(
            "_normalize_summary: win_rate is None/NaN for strategy '%s' — substituting 0.0",
            summary.strategy,
        )
        result.win_rate = 0.0

    if _is_nan_or_none(result.max_drawdown):
        _log.warning(
            "_normalize_summary: max_drawdown is None/NaN for strategy '%s' — substituting 100.0",
            summary.strategy,
        )
        result.max_drawdown = 100.0

    return result


def compute_score(input: RobustScoreInput) -> RobustScore:
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
    s = _normalize_summary(input.in_sample)

    # ------------------------------------------------------------------
    # Profitability component (weight 0.35)
    # ------------------------------------------------------------------
    norm_profit = _norm(s.total_profit, _NORM_NET_PROFIT_MIN, _NORM_NET_PROFIT_MAX)
    norm_expectancy = _norm(s.expectancy, _NORM_EXPECTANCY_MIN, _NORM_EXPECTANCY_MAX)
    norm_pf = _norm(min(s.profit_factor, 3.0), _NORM_PROFIT_FACTOR_MIN, _NORM_PROFIT_FACTOR_MAX)
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
    norm_dd = _norm(s.max_drawdown, _NORM_MAX_DRAWDOWN_MIN, _NORM_MAX_DRAWDOWN_MAX)

    # slippage_sensitivity: ratio of stress-test profit drop to baseline profit
    slippage_sensitivity = 0.0
    if input.stress_summary is not None:
        stress_s = _normalize_summary(input.stress_summary)
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


def targets_met(summary: BacktestSummary, config: LoopConfig) -> bool:
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

    Args:
        base_params: The initial strategy parameters before any loop changes.
    """

    # How many times to try tightening/loosening each parameter before giving up
    _MAX_STEPS_PER_PARAM = 5

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
    ) -> List[ParameterSuggestion]:
        """Generate a varied set of suggestions for this iteration.

        Applies step-based variation: each successive call for the same issue
        produces a more aggressive or differently-directed change. If a previous
        iteration made things worse, the direction is reversed.

        Args:
            issues: Diagnosed issues from the latest backtest.
            current_params: Current strategy parameters.
            prev_iteration: The previous loop iteration, or None for the first.

        Returns:
            List of non-advisory ParameterSuggestion objects to apply.
        """
        # Start with base suggestions from the rule service
        base_suggestions = RuleSuggestionService.suggest(issues, current_params)
        actionable = [s for s in base_suggestions if not s.is_advisory]

        if not actionable:
            return []

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

        return varied

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

        # Unknown parameter — return the base suggestion as-is on step 0 only
        if step == 0:
            return suggestion
        return None


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
            score = compute_score(RobustScoreInput(in_sample=initial_results.summary))
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

    def prepare_next_iteration(
        self,
        latest_summary: BacktestSummary,
    ) -> Optional[Tuple[LoopIteration, List[ParameterSuggestion]]]:
        """Analyse the latest results and prepare the next iteration.

        Runs diagnosis and suggestion rotation to produce the candidate params
        for the next backtest. Returns None if no actionable suggestions remain
        or the loop should stop.

        Args:
            latest_summary: BacktestSummary from the most recent backtest.

        Returns:
            Tuple of (LoopIteration, suggestions) ready to execute, or None if
            the loop should terminate.
        """
        if self._config is None or self._rotator is None:
            return None

        self._current_iteration += 1

        # Check targets
        if self._config.stop_on_first_profitable and targets_met(latest_summary, self._config):
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
                validation_gate_reached="in_sample",
                validation_gate_passed=True,
            )
            self._record_iteration(iteration)
            self._result.target_reached = True
            self._result.stop_reason = "All profitability targets met"
            self._running = False
            _log.info("Loop: targets met at iteration %d", self._current_iteration)
            return None

        # Diagnose using the new DiagnosisInput/DiagnosisBundle API
        from app.core.models.diagnosis_models import DiagnosisInput
        diagnosis_input = DiagnosisInput(in_sample=latest_summary)
        bundle = ResultsDiagnosisService.diagnose(diagnosis_input)
        issues = bundle.issues
        _log.debug(
            "Loop iter %d: %d issue(s) diagnosed", self._current_iteration, len(issues)
        )

        # Get previous iteration for direction hints
        prev_iteration = self._result.iterations[-1] if self._result.iterations else None

        # Generate varied suggestions
        suggestions = self._rotator.generate_suggestions(
            issues, self._current_params, prev_iteration
        )

        if not suggestions:
            self._result.stop_reason = "No more actionable suggestions to try"
            self._running = False
            _log.info("Loop: no more suggestions at iteration %d", self._current_iteration)
            return None

        # Build candidate params
        candidate_params = copy.deepcopy(self._current_params)
        for s in suggestions:
            candidate_params[s.parameter] = s.proposed_value

        # Skip if we've already tried this exact config
        if self._rotator.already_tried(candidate_params):
            _log.debug("Loop: skipping already-tried config at iteration %d", self._current_iteration)
            # Try to find a different combination by skipping one suggestion
            if len(suggestions) > 1:
                suggestions = suggestions[:1]
                candidate_params = copy.deepcopy(self._current_params)
                for s in suggestions:
                    candidate_params[s.parameter] = s.proposed_value
            if self._rotator.already_tried(candidate_params):
                self._result.stop_reason = "All reachable parameter combinations exhausted"
                self._running = False
                return None

        self._rotator.mark_tried(candidate_params)

        # Build changes_summary list
        changes_summary = []
        for param, new_val in candidate_params.items():
            old_val = self._current_params.get(param)
            if old_val != new_val:
                changes_summary.append(f"{param}: {old_val} → {new_val}")

        from pathlib import Path
        iteration = LoopIteration(
            iteration_number=self._current_iteration,
            params_before=copy.deepcopy(self._current_params),
            params_after=candidate_params,
            changes_summary=changes_summary,
            sandbox_path=Path("."),
        )

        self._emit_status(
            f"Iteration {self._current_iteration}/{self._config.max_iterations} — "
            f"applying {len(suggestions)} suggestion(s): "
            + ", ".join(changes_summary)
        )

        return iteration, suggestions

    def record_iteration_result(
        self,
        iteration: LoopIteration,
        summary: BacktestSummary,
        score_input: Optional[RobustScoreInput] = None,
    ) -> bool:
        """Record the backtest result for an iteration and update best tracking.

        Args:
            iteration: The iteration object (mutated in place with results/score).
            summary: BacktestSummary from the candidate backtest (Gate 1).
            score_input: Optional full RobustScoreInput for multi-gate scoring.
                If None, a minimal input using only in_sample is constructed.

        Returns:
            True if this iteration improved over the previous best.
        """
        iteration.summary = summary

        # Guard: zero trades
        if summary.total_trades == 0:
            iteration.status = "zero_trades"
            iteration.is_improvement = False
            self._record_iteration(iteration)
            _log.info("Loop iter %d: zero trades — not eligible for best", iteration.iteration_number)
            return False

        # Guard: below min trades
        if self._config and summary.total_trades < self._config.target_min_trades:
            iteration.below_min_trades = True

        # Compute score
        if score_input is None:
            score_input = RobustScoreInput(in_sample=summary)
        robust_score = compute_score(score_input)
        iteration.score = robust_score

        # Only fully-validated iterations can become best
        is_improvement = (
            iteration.validation_gate_passed
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

    def finalize(self, stop_reason: str = "") -> LoopResult:
        """Finalize the loop and return the completed LoopResult.

        Args:
            stop_reason: Human-readable reason the loop stopped (if not already set).

        Returns:
            The completed LoopResult.
        """
        self._running = False
        if stop_reason and not self._result.stop_reason:
            self._result.stop_reason = stop_reason

        if self._result.best_iteration is None and self._result.iterations:
            # Pick the best from fully-validated iterations only
            validated = [
                it for it in self._result.iterations
                if it.validation_gate_passed and it.score is not None
            ]
            if validated:
                self._result.best_iteration = max(
                    validated, key=lambda it: it.score.total
                )

        _log.info(
            "Loop finalized: %d iterations, best_score=%.4f, reason=%s",
            len(self._result.iterations),
            self._best_score,
            self._result.stop_reason,
        )
        return self._result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _record_iteration(self, iteration: LoopIteration) -> None:
        """Append iteration to result and fire the callback."""
        self._result.iterations.append(iteration)
        if self._on_iteration_complete is not None:
            self._on_iteration_complete(iteration)

    def _emit_status(self, message: str) -> None:
        """Fire the status callback if registered."""
        if self._on_status is not None:
            self._on_status(message)
