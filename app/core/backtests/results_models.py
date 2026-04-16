from dataclasses import dataclass, field
from typing import Dict, List, Optional


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
