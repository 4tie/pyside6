import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class BacktestTrade:
    """Represents a single trade from backtest results."""
    pair: str
    stake_amount: float
    amount: float
    open_date: str
    close_date: Optional[str]
    open_rate: float
    close_rate: Optional[float]
    profit: float
    profit_abs: float
    duration: int  # minutes
    is_open: bool


@dataclass
class BacktestSummary:
    """Summary statistics from a backtest."""
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


@dataclass
class BacktestResults:
    """Complete backtest results."""
    summary: BacktestSummary
    trades: List[BacktestTrade] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)


class BacktestResultsService:
    """Service for parsing and extracting backtest results."""

    @staticmethod
    def parse_backtest_zip(zip_path: str) -> Optional[BacktestResults]:
        """Parse a backtest zip file and extract results.

        Args:
            zip_path: Path to the .backtest.zip file

        Returns:
            BacktestResults object or None if parsing fails
        """
        zip_file = Path(zip_path)
        if not zip_file.exists():
            raise FileNotFoundError(f"Backtest zip not found: {zip_path}")

        try:
            with zipfile.ZipFile(zip_file, 'r') as zf:
                # Find the backtest result JSON file
                json_files = [f for f in zf.namelist() if f.endswith('.json')]
                if not json_files:
                    raise ValueError("No JSON files found in backtest zip")

                # Usually it's backtest-result_*.json
                result_file = None
                for f in json_files:
                    if 'backtest-result' in f:
                        result_file = f
                        break

                if not result_file:
                    result_file = json_files[0]  # Fallback to first JSON

                # Extract and parse the JSON
                json_data = json.loads(zf.read(result_file).decode('utf-8'))
                return BacktestResultsService._parse_result_json(json_data)

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse backtest JSON: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse backtest zip: {e}")

    @staticmethod
    def _parse_result_json(data: Dict[str, Any]) -> BacktestResults:
        """Parse the backtest result JSON format.

        Args:
            data: Parsed JSON data from backtest result

        Returns:
            BacktestResults object
        """
        # Actual freqtrade bt-*.result.json structure:
        # { "strategy": "...", "result": { "trades": [...] }, ... }
        strategy = data.get('strategy', 'Unknown')
        trades_data = data.get('result', {}).get('trades', [])

        trades = []
        for trade in trades_data:
            try:
                trades.append(BacktestTrade(
                    pair=trade.get('pair', ''),
                    stake_amount=float(trade.get('stake_amount', 0)),
                    amount=float(trade.get('amount', 0)),
                    open_date=str(trade.get('open_date', '')),
                    close_date=str(trade.get('close_date', '')) or None,
                    open_rate=float(trade.get('open_rate', 0)),
                    close_rate=float(trade.get('close_rate', 0)) if trade.get('close_rate') else None,
                    profit=float(trade.get('profit_ratio', 0)) * 100,
                    profit_abs=float(trade.get('profit_abs', 0)),
                    duration=int(trade.get('trade_duration', 0)),
                    is_open=bool(trade.get('is_open', False)),
                ))
            except (ValueError, KeyError):
                continue

        wins = sum(1 for t in trades if t.profit > 0)
        losses = sum(1 for t in trades if t.profit < 0)
        draws = sum(1 for t in trades if t.profit == 0)
        total = len(trades)
        win_rate = (wins / total * 100) if total else 0.0
        avg_profit = (sum(t.profit for t in trades) / total) if total else 0.0
        total_profit_abs = sum(t.profit_abs for t in trades)
        avg_duration = int(sum(t.duration for t in trades) / total) if total else 0

        summary = BacktestSummary(
            strategy=strategy,
            timeframe='',
            total_trades=total,
            wins=wins,
            losses=losses,
            draws=draws,
            win_rate=win_rate,
            avg_profit=avg_profit,
            total_profit=float(data.get('profit_total_pct', avg_profit * total / 100 if total else 0)),
            total_profit_abs=total_profit_abs,
            sharpe_ratio=None,
            sortino_ratio=None,
            calmar_ratio=None,
            max_drawdown=0.0,
            max_drawdown_abs=0.0,
            trade_duration_avg=avg_duration,
        )

        return BacktestResults(
            summary=summary,
            trades=trades,
            raw_data=data,
        )

    @staticmethod
    def format_summary_for_display(summary: BacktestSummary) -> Dict[str, str]:
        """Format summary statistics for UI display.

        Args:
            summary: BacktestSummary object

        Returns:
            Dictionary of formatted display strings
        """
        return {
            'Strategy': summary.strategy,
            'Timeframe': summary.timeframe,
            'Total Trades': str(summary.total_trades),
            'Wins': f"{summary.wins} ({summary.win_rate:.2f}%)" if summary.total_trades > 0 else "0",
            'Losses': str(summary.losses),
            'Draws': str(summary.draws),
            'Avg Profit': f"{summary.avg_profit:.4f}%",
            'Total Profit': f"{summary.total_profit:.4f}%",
            'Total Profit (Abs)': f"{summary.total_profit_abs:.8f}",
            'Sharpe Ratio': f"{summary.sharpe_ratio:.4f}" if summary.sharpe_ratio else "N/A",
            'Sortino Ratio': f"{summary.sortino_ratio:.4f}" if summary.sortino_ratio else "N/A",
            'Calmar Ratio': f"{summary.calmar_ratio:.4f}" if summary.calmar_ratio else "N/A",
            'Max Drawdown': f"{summary.max_drawdown:.2f}%",
            'Max Drawdown (Abs)': f"{summary.max_drawdown_abs:.8f}",
            'Avg Trade Duration': f"{summary.trade_duration_avg} min",
        }
