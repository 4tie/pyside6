"""
loop_models.py — Data transfer objects for the auto-optimization loop.

Covers LoopConfig, LoopIteration, LoopResult, GateResult, HardFilterFailure,
RobustScoreInput, and RobustScore used by LoopService and LoopPage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.core.backtests.results_models import BacktestSummary


# ---------------------------------------------------------------------------
# Scoring dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RobustScoreInput:
    """Input bundle for the multi-dimensional robust scoring function.

    Attributes:
        in_sample: In-sample backtest summary (Gate 1 result).
        fold_summaries: Per-fold summaries from walk-forward gate; None in Quick mode.
        stress_summary: Stress-test gate summary; None in Quick mode.
        pair_profit_distribution: Mapping of pair → profit contribution ratio; optional.
    """

    in_sample: BacktestSummary
    fold_summaries: Optional[List[BacktestSummary]] = None
    stress_summary: Optional[BacktestSummary] = None
    pair_profit_distribution: Optional[Dict[str, float]] = None


@dataclass
class RobustScore:
    """Multi-dimensional score for a single loop iteration.

    Attributes:
        total: Composite score (profitability + consistency + stability - fragility).
        profitability: Profitability component (weight 0.35).
        consistency: Consistency component (weight 0.30).
        stability: Stability component (weight 0.20).
        fragility: Fragility penalty (weight 0.15, subtracted from total).
    """

    total: float
    profitability: float
    consistency: float
    stability: float
    fragility: float


# ---------------------------------------------------------------------------
# Hard-filter dataclasses
# ---------------------------------------------------------------------------

@dataclass
class HardFilterFailure:
    """Record of a single hard-filter rejection.

    Attributes:
        filter_name: Machine-readable filter identifier.
        reason: Human-readable explanation of why the filter failed.
        evidence: Numeric or textual evidence supporting the failure.
    """

    filter_name: str
    reason: str
    evidence: str


# ---------------------------------------------------------------------------
# Gate result
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    """Record of a single validation gate execution within one iteration.

    Attributes:
        gate_name: Identifier for the gate (e.g. "in_sample", "out_of_sample",
            "walk_forward", "stress_test", "consistency").
        passed: True if the gate passed.
        metrics: Aggregate BacktestSummary for this gate; None for pure-computation gates.
        fold_summaries: Per-fold summaries for walk-forward gate; None otherwise.
        failure_reason: Human-readable reason for failure; None when passed.
    """

    gate_name: str
    passed: bool
    metrics: Optional[BacktestSummary] = None
    fold_summaries: Optional[List[BacktestSummary]] = None
    failure_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Loop configuration
# ---------------------------------------------------------------------------

@dataclass
class LoopConfig:
    """Configuration for a single auto-optimization loop run.

    Attributes:
        strategy: Strategy class name to optimize.
        timeframe: Timeframe for backtests (e.g. "5m", "1h").
        max_iterations: Maximum number of backtest iterations to run.
        target_profit_pct: Stop when total profit exceeds this value (%).
        target_win_rate: Stop when win rate exceeds this value (%).
        target_max_drawdown: Stop when max drawdown is below this value (%).
        target_min_trades: Stop when total trades exceeds this value.
        stop_on_first_profitable: Stop as soon as all targets are met.
        date_from: Start date for the full configured date range (ISO string).
        date_to: End date for the full configured date range (ISO string).
        oos_split_pct: Percentage of the total date range held out for OOS gate.
        walk_forward_folds: Number of folds for walk-forward validation gate.
        stress_fee_multiplier: Fee multiplier applied during stress-test gate.
        stress_slippage_pct: Per-trade slippage added during stress-test gate (%).
        stress_profit_target_pct: Minimum profit required during stress-test gate
            as a percentage of the main profit target.
        consistency_threshold_pct: Maximum allowed std-dev of per-fold profit as
            a percentage of mean fold profit.
        validation_mode: "full" for all five gates; "quick" for gates 1–2 only.
        profit_concentration_threshold: Max fraction of profit from top 3 trades.
        profit_factor_floor: Minimum acceptable profit factor.
        pair_dominance_threshold: Max profit share from a single pair.
        time_dominance_threshold: Max profit share from a single time period.
        validation_variance_ceiling: Max walk-forward coefficient of variation.
    """

    strategy: str
    timeframe: str = "5m"
    max_iterations: int = 10
    target_profit_pct: float = 5.0
    target_win_rate: float = 55.0
    target_max_drawdown: float = 20.0
    target_min_trades: int = 30
    stop_on_first_profitable: bool = True
    date_from: str = ""
    date_to: str = ""
    oos_split_pct: float = 20.0
    walk_forward_folds: int = 5
    stress_fee_multiplier: float = 2.0
    stress_slippage_pct: float = 0.1
    stress_profit_target_pct: float = 50.0
    consistency_threshold_pct: float = 30.0
    validation_mode: str = "full"
    profit_concentration_threshold: float = 0.50
    profit_factor_floor: float = 1.1
    pair_dominance_threshold: float = 0.60
    time_dominance_threshold: float = 0.40
    validation_variance_ceiling: float = 1.0
    # Extended fields for full parameter surface and new modes
    iteration_mode: str = "rule_based"
    hyperopt_epochs: int = 200
    hyperopt_spaces: List[str] = field(default_factory=list)
    hyperopt_loss_function: str = "SharpeHyperOptLoss"
    pairs: List[str] = field(default_factory=list)
    ai_advisor_enabled: bool = False


# ---------------------------------------------------------------------------
# Loop iteration
# ---------------------------------------------------------------------------

@dataclass
class LoopIteration:
    """Record of a single iteration within the auto-optimization loop.

    Attributes:
        iteration_number: 1-based iteration counter.
        params_before: Strategy parameters at the start of this iteration.
        params_after: Strategy parameters after applying suggestions.
        changes_summary: List of human-readable change descriptions.
        summary: In-sample BacktestSummary for this iteration; None on error.
        score: RobustScore for this iteration; None on error or pre-scoring.
        is_improvement: True if this iteration improved over the previous best.
        status: One of "success", "error", "hard_filter_rejected", "gate_failed".
        error_message: Error message if the iteration failed; None otherwise.
        below_min_trades: True if trade count is below target_min_trades.
        sandbox_path: Path to the sandbox directory used for this iteration.
        validation_gate_reached: Name of the last gate attempted.
        validation_gate_passed: True if all attempted gates passed.
        gate_results: Ordered list of GateResult objects for each gate run.
        hard_filter_failures: List of HardFilterFailure objects if rejected.
        version_id: ID of the version snapshot created for this iteration.
    """

    iteration_number: int
    params_before: dict
    params_after: dict
    changes_summary: List[str]
    summary: Optional[BacktestSummary] = None
    score: Optional[RobustScore] = None
    is_improvement: bool = False
    status: str = "success"
    error_message: Optional[str] = None
    below_min_trades: bool = False
    sandbox_path: Path = field(default_factory=lambda: Path("."))
    validation_gate_reached: str = ""
    validation_gate_passed: bool = False
    gate_results: List[GateResult] = field(default_factory=list)
    hard_filter_failures: List[HardFilterFailure] = field(default_factory=list)
    # AI advisor fields
    ai_suggested: bool = False
    ai_suggestion_reason: Optional[str] = None
    # Structural diagnosis patterns that triggered changes
    diagnosed_structural: List = field(default_factory=list)
    # Version tracking
    version_id: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        """True if the iteration completed without error and has a summary."""
        return self.error_message is None and self.summary is not None

    @property
    def profit_pct(self) -> float:
        """Total profit percentage from this iteration's in-sample summary."""
        if self.summary is None:
            return 0.0
        return self.summary.total_profit

    @property
    def win_rate(self) -> float:
        """Win rate percentage from this iteration's in-sample summary."""
        if self.summary is None:
            return 0.0
        return self.summary.win_rate

    @property
    def max_drawdown(self) -> float:
        """Max drawdown percentage from this iteration's in-sample summary."""
        if self.summary is None:
            return 0.0
        return self.summary.max_drawdown

    @property
    def total_trades(self) -> int:
        """Total trades from this iteration's in-sample summary."""
        if self.summary is None:
            return 0
        return self.summary.total_trades

    @property
    def sharpe_ratio(self) -> float:
        """Sharpe ratio from this iteration's in-sample summary."""
        if self.summary is None:
            return 0.0
        return self.summary.sharpe_ratio or 0.0


# ---------------------------------------------------------------------------
# Loop result
# ---------------------------------------------------------------------------

@dataclass
class LoopResult:
    """Final result of a completed auto-optimization loop run.

    Attributes:
        iterations: All completed iterations, in order.
        best_iteration: The iteration with the highest RobustScore.
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
