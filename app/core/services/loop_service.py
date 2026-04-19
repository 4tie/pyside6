"""
loop_service.py — Orchestration service for the auto-optimization loop.

Drives the iterative backtest → diagnose → suggest → apply → repeat cycle.
All heavy lifting (subprocess execution) is delegated to ImproveService and
ProcessService; this service manages state transitions and suggestion rotation.
"""
from __future__ import annotations

import copy
from typing import Callable, Dict, List, Optional, Tuple

from app.core.backtests.results_models import BacktestResults, BacktestSummary
from app.core.models.improve_models import DiagnosedIssue, ParameterSuggestion
from app.core.models.loop_models import LoopConfig, LoopIteration, LoopResult
from app.core.services.improve_service import ImproveService
from app.core.services.results_diagnosis_service import ResultsDiagnosisService
from app.core.services.rule_suggestion_service import RuleSuggestionService
from app.core.utils.app_logger import get_logger

_log = get_logger("services.loop")

# ---------------------------------------------------------------------------
# Scoring weights — used to rank iterations
# ---------------------------------------------------------------------------
_W_PROFIT = 0.40
_W_WIN_RATE = 0.25
_W_DRAWDOWN = 0.20   # inverted: lower drawdown → higher score
_W_SHARPE = 0.15


def compute_score(summary: BacktestSummary) -> float:
    """Compute a composite profitability score for a backtest summary.

    Higher is better. Profit and win rate contribute positively; drawdown
    contributes negatively (inverted). Sharpe ratio adds a quality bonus.

    Args:
        summary: Aggregate statistics from a completed backtest run.

    Returns:
        Float composite score. Comparable across iterations of the same strategy.
    """
    profit_score = summary.total_profit * _W_PROFIT
    win_score = summary.win_rate * _W_WIN_RATE
    dd_score = -summary.max_drawdown * _W_DRAWDOWN
    sharpe_score = (summary.sharpe_ratio or 0.0) * _W_SHARPE * 10  # scale to ~same range
    return profit_score + win_score + dd_score + sharpe_score


def targets_met(summary: BacktestSummary, config: LoopConfig) -> bool:
    """Return True if all profitability targets in config are satisfied.

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
                if param in prev_iteration.changes:
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
        initial_results: Optional[BacktestResults] = None,
    ) -> None:
        """Initialise loop state. Does NOT start the first backtest.

        The UI layer calls ``next_iteration()`` to kick off the first run
        after wiring up the process callbacks.

        Args:
            config: Loop configuration (targets, max iterations, strategy).
            initial_params: Starting strategy parameters.
            initial_results: Optional pre-existing baseline results. If provided,
                the first iteration skips the initial backtest and goes straight
                to diagnosis.
        """
        self._config = config
        self._current_params = copy.deepcopy(initial_params)
        self._rotator = SuggestionRotator(initial_params)
        self._result = LoopResult()
        self._current_iteration = 0
        self._best_score = float("-inf")
        self._running = True

        if initial_results is not None:
            # Seed the best score from the existing baseline
            self._best_score = compute_score(initial_results.summary)
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
        latest_results: BacktestResults,
    ) -> Optional[Tuple[LoopIteration, List[ParameterSuggestion]]]:
        """Analyse the latest results and prepare the next iteration.

        Runs diagnosis and suggestion rotation to produce the candidate params
        for the next backtest. Returns None if no actionable suggestions remain
        or the loop should stop.

        Args:
            latest_results: BacktestResults from the most recent backtest.

        Returns:
            Tuple of (LoopIteration, suggestions) ready to execute, or None if
            the loop should terminate.
        """
        if self._config is None or self._rotator is None:
            return None

        self._current_iteration += 1
        summary = latest_results.summary

        # Check targets
        if self._config.stop_on_first_profitable and targets_met(summary, self._config):
            score = compute_score(summary)
            iteration = LoopIteration(
                iteration_num=self._current_iteration,
                params_before=copy.deepcopy(self._current_params),
                params_after=copy.deepcopy(self._current_params),
                changes={},
                issues=[],
                suggestions_applied=[],
                results=latest_results,
                is_improvement=True,
                score=score,
            )
            self._record_iteration(iteration)
            self._result.target_reached = True
            self._result.stop_reason = "All profitability targets met"
            self._running = False
            _log.info("Loop: targets met at iteration %d", self._current_iteration)
            return None

        # Diagnose
        issues = ResultsDiagnosisService.diagnose(summary)
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

        # Build changes dict
        changes = {}
        for param, new_val in candidate_params.items():
            old_val = self._current_params.get(param)
            if old_val != new_val:
                changes[param] = (old_val, new_val)

        iteration = LoopIteration(
            iteration_num=self._current_iteration,
            params_before=copy.deepcopy(self._current_params),
            params_after=candidate_params,
            changes=changes,
            issues=issues,
            suggestions_applied=suggestions,
        )

        self._emit_status(
            f"Iteration {self._current_iteration}/{self._config.max_iterations} — "
            f"applying {len(suggestions)} suggestion(s): {iteration.changes_summary}"
        )

        return iteration, suggestions

    def record_iteration_result(
        self,
        iteration: LoopIteration,
        results: BacktestResults,
    ) -> bool:
        """Record the backtest result for an iteration and update best tracking.

        Args:
            iteration: The iteration object (mutated in place with results/score).
            results: BacktestResults from the candidate backtest.

        Returns:
            True if this iteration improved over the previous best.
        """
        score = compute_score(results.summary)
        is_improvement = score > self._best_score

        iteration.results = results
        iteration.score = score
        iteration.is_improvement = is_improvement

        if is_improvement:
            self._best_score = score
            self._current_params = copy.deepcopy(iteration.params_after)
            self._result.best_iteration = iteration
            _log.info(
                "Loop iter %d: improvement! score=%.4f profit=%.2f%%",
                iteration.iteration_num,
                score,
                results.summary.total_profit,
            )
        else:
            _log.info(
                "Loop iter %d: no improvement. score=%.4f (best=%.4f)",
                iteration.iteration_num,
                score,
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
        iteration.error = error
        self._record_iteration(iteration)
        _log.warning("Loop iter %d failed: %s", iteration.iteration_num, error)

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
            # Pick the best from what we have
            successful = [it for it in self._result.iterations if it.succeeded]
            if successful:
                self._result.best_iteration = max(successful, key=lambda it: it.score)

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
