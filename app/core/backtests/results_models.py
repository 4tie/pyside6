from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PairMetrics:
    """Per-pair computed statistics for one backtest run.

    Attributes:
        pair: Trading pair symbol (e.g. "ETH/USDT").
        total_profit_pct: Sum of BacktestTrade.profit for all trades on this pair.
        win_rate: Wins divided by total trades, expressed as a percentage (0–100).
        trade_count: Total number of trades on this pair.
        max_drawdown_pct: Absolute value of the most negative single-trade profit
            for this pair; 0.0 if no losing trades exist.
        profit_share: This pair's total_profit_pct divided by the absolute sum of
            all pairs' total_profit_pct; 0.0 when total absolute profit is zero.
    """

    pair: str
    total_profit_pct: float
    win_rate: float
    trade_count: int
    max_drawdown_pct: float
    profit_share: float


@dataclass
class PairAnalysis:
    """Full output of PairAnalysisService for one backtest run.

    Attributes:
        pair_metrics: One PairMetrics entry per distinct pair in the run.
        best_pairs: Up to three PairMetrics with the highest total_profit_pct,
            ordered descending.
        worst_pairs: Up to three PairMetrics with the lowest total_profit_pct,
            ordered ascending.
        dominance_flags: List of flag strings; contains "profit_concentration"
            when a single pair's profit_share exceeds 0.60.
    """

    pair_metrics: List[PairMetrics]
    best_pairs: List[PairMetrics]
    worst_pairs: List[PairMetrics]
    dominance_flags: List[str]


@dataclass
class RunComparison:
    """Diff between two backtest runs (run_b relative to run_a).

    Attributes:
        profit_diff: run_b.total_profit - run_a.total_profit.
        winrate_diff: run_b.win_rate - run_a.win_rate.
        drawdown_diff: run_b.max_drawdown - run_a.max_drawdown; positive means
            run_b has higher drawdown (worse).
        verdict: "improved" | "degraded" | "neutral".

        # Multi-objective scores
        score_a: 4-layer multi-objective score for run A.
        score_b: 4-layer multi-objective score for run B.
        score_diff: Positive = improvement.

        # Risk-adjusted metrics
        sharpe_diff: Sharpe ratio difference.
        sortino_diff: Sortino ratio difference.
        calmar_diff: Calmar ratio difference.
        profit_factor_diff: Profit factor difference.

        # Trade quality
        trade_frequency_diff: Trades per day difference.
        avg_duration_diff: Average trade duration difference (minutes).
        expectancy_diff: Expectancy difference.

        # Pattern detection
        patterns_a: Pattern IDs affecting run A.
        patterns_b: Pattern IDs affecting run B.

        # Confidence scoring
        confidence_score: 0.0 to 1.0 confidence in verdict.
        confidence_reason: Explanation of confidence score.
        is_statistically_significant: Whether improvement is meaningful.

        # Detailed breakdown
        metric_scores: Per-metric improvement scores (-1 to 1).
        recommendations: Actionable recommendations.
    """

    profit_diff: float
    winrate_diff: float
    drawdown_diff: float
    verdict: str

    # Multi-objective scores
    score_a: float = 0.0
    score_b: float = 0.0
    score_diff: float = 0.0

    # Risk-adjusted metrics
    sharpe_diff: float = 0.0
    sortino_diff: float = 0.0
    calmar_diff: float = 0.0
    profit_factor_diff: float = 0.0

    # Trade quality
    trade_frequency_diff: float = 0.0
    avg_duration_diff: float = 0.0
    expectancy_diff: float = 0.0

    # Pattern detection
    patterns_a: List[str] = None
    patterns_b: List[str] = None

    # Confidence scoring
    confidence_score: float = 0.5
    confidence_reason: str = ""
    is_statistically_significant: bool = False

    # Detailed breakdown
    metric_scores: Dict[str, float] = None
    recommendations: List[str] = None

    def __post_init__(self):
        """Initialize default values for mutable fields."""
        if self.patterns_a is None:
            self.patterns_a = []
        if self.patterns_b is None:
            self.patterns_b = []
        if self.metric_scores is None:
            self.metric_scores = {}
        if self.recommendations is None:
            self.recommendations = []


@dataclass
class BacktestTrade:
    """A single trade from backtest results."""
    pair: str
    stake_amount: float
    amount: float
    open_date: str
    close_date: Optional[str]
    open_rate: float
    close_rate: Optional[float]
    profit: float        # percent
    profit_abs: float
    duration: int        # minutes
    is_open: bool
    exit_reason: str = ""


@dataclass
class BacktestSummary:
    """Aggregate statistics from a backtest run."""
    strategy: str
    timeframe: str
    total_trades: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    avg_profit: float
    total_profit: float
    total_profit_abs: float
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    calmar_ratio: Optional[float]
    max_drawdown: float
    max_drawdown_abs: float
    trade_duration_avg: int
    starting_balance: float = 0.0
    final_balance: float = 0.0
    timerange: str = ""
    pairlist: List[str] = field(default_factory=list)
    backtest_start: str = ""
    backtest_end: str = ""
    expectancy: float = 0.0
    profit_factor: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    def format_for_display(self) -> Dict[str, str]:
        """Return a flat dict of formatted strings for UI display."""
        return {
            "Strategy":            self.strategy,
            "Timeframe":           self.timeframe,
            "Total Trades":        str(self.total_trades),
            "Wins":                f"{self.wins} ({self.win_rate:.2f}%)" if self.total_trades else "0",
            "Losses":              str(self.losses),
            "Draws":               str(self.draws),
            "Avg Profit":          f"{self.avg_profit:.4f}%",
            "Total Profit":        f"{self.total_profit:.4f}%",
            "Total Profit (Abs)":  f"{self.total_profit_abs:.8f}",
            "Sharpe Ratio":        f"{self.sharpe_ratio:.4f}" if self.sharpe_ratio is not None else "N/A",
            "Sortino Ratio":       f"{self.sortino_ratio:.4f}" if self.sortino_ratio is not None else "N/A",
            "Calmar Ratio":        f"{self.calmar_ratio:.4f}" if self.calmar_ratio is not None else "N/A",
            "Max Drawdown":        f"{self.max_drawdown:.2f}%",
            "Max Drawdown (Abs)":  f"{self.max_drawdown_abs:.8f}",
            "Avg Trade Duration":  f"{self.trade_duration_avg} min",
        }


@dataclass
class BacktestResults:
    """Complete results from one backtest run."""
    summary: BacktestSummary
    trades: List[BacktestTrade] = field(default_factory=list)
    raw_data: Dict = field(default_factory=dict)
