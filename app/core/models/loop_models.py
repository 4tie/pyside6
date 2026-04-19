"""
loop_models.py — Data transfer objects for the auto-optimization loop.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.core.backtests.results_models import BacktestResults
from app.core.models.improve_models import DiagnosedIssue, ParameterSuggestion


@dataclass
class LoopConfig:
    """Configuration for a single auto-optimization loop run.

    Attributes:
        strategy: Strategy class name to optimize.
        max_iterations: Maximum number of backtest iterations to run.
        target_profit_pct: Stop when total profit exceeds this value (%).
        target_win_rate: Stop when win rate exceeds this value (%).
        target_max_drawdown: Stop when max drawdown is below this value (%).
        target_min_trades: Stop when total trades exceeds this value.
        stop_on_first_profitable: Stop as soon as all targets are met.
    """

    strategy: str
    max_iterations: int = 10
    target_profit_pct: float = 5.0
    target_win_rate: float = 55.0
    target_max_drawdown: float = 20.0
    target_min_trades: int = 30
    stop_on_first_profitable: bool = True


@dataclass
class LoopIteration:
    """Record of a single iteration within the auto-optimization loop.

    Attributes:
        iteration_num: 1-based iteration counter.
        params_before: Strategy parameters at the start of this iteration.
        params_after: Strategy parameters after applying suggestions.
        changes: Dict of {param: (old_value, new_value)} for changed params.
        issues: Diagnosed issues found in this iteration's backtest.
        suggestions_applied: Suggestions that were applied to produce params_after.
        results: BacktestResults from running the candidate backtest.
        is_improvement: True if this iteration improved over the previous best.
        score: Composite score used to rank iterations (higher is better).
        error: Error message if the iteration failed, otherwise None.
    """

    iteration_num: int
    params_before: dict
    params_after: dict
    changes: dict
    issues: List[DiagnosedIssue]
    suggestions_applied: List[ParameterSuggestion]
    results: Optional[BacktestResults] = None
    is_improvement: bool = False
    score: float = 0.0
    error: Optional[str] = None

    @property
    def profit_pct(self) -> float:
        """Total profit percentage from this iteration's results."""
        if self.results is None:
            return 0.0
        return self.results.summary.total_profit

    @property
    def win_rate(self) -> float:
        """Win rate percentage from this iteration's results."""
        if self.results is None:
            return 0.0
        return self.results.summary.win_rate

    @property
    def max_drawdown(self) -> float:
        """Max drawdown percentage from this iteration's results."""
        if self.results is None:
            return 0.0
        return self.results.summary.max_drawdown

    @property
    def total_trades(self) -> int:
        """Total trades from this iteration's results."""
        if self.results is None:
            return 0
        return self.results.summary.total_trades

    @property
    def sharpe_ratio(self) -> float:
        """Sharpe ratio from this iteration's results."""
        if self.results is None:
            return 0.0
        return self.results.summary.sharpe_ratio or 0.0

    @property
    def changes_summary(self) -> str:
        """Human-readable summary of parameter changes."""
        if not self.changes:
            return "No changes"
        parts = []
        for param, (old_val, new_val) in self.changes.items():
            parts.append(f"{param}: {old_val} → {new_val}")
        return ", ".join(parts)

    @property
    def succeeded(self) -> bool:
        """True if the iteration completed without error and has results."""
        return self.error is None and self.results is not None


@dataclass
class LoopResult:
    """Final result of a completed auto-optimization loop run.

    Attributes:
        iterations: All completed iterations, in order.
        best_iteration: The iteration with the highest composite score.
        stop_reason: Human-readable explanation of why the loop stopped.
        target_reached: True if all profitability targets were met.
    """

    iterations: List[LoopIteration] = field(default_factory=list)
    best_iteration: Optional[LoopIteration] = None
    stop_reason: str = ""
    target_reached: bool = False

    @property
    def best_params(self) -> dict:
        """Parameters from the best iteration, or empty dict if no iterations."""
        if self.best_iteration is None:
            return {}
        return self.best_iteration.params_after

    @property
    def total_iterations(self) -> int:
        """Number of completed iterations."""
        return len(self.iterations)

    @property
    def successful_iterations(self) -> int:
        """Number of iterations that completed without error."""
        return sum(1 for it in self.iterations if it.succeeded)
