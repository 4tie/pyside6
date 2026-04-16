import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.core.utils.app_logger import get_logger

_log = get_logger("results")


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
    starting_balance: float = 0.0
    final_balance: float = 0.0
    timerange: str = ''
    pairlist: List[str] = field(default_factory=list)
    backtest_start: str = ''
    backtest_end: str = ''
    expectancy: float = 0.0
    profit_factor: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0


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
                json_files = [f for f in zf.namelist()
                              if f.endswith('.json') and '_config' not in f]
                if not json_files:
                    raise ValueError("No JSON files found in backtest zip")
                _log.debug("Parsing zip: %s | json_file=%s", zip_file.name, json_files[0])
                json_data = json.loads(zf.read(json_files[0]).decode('utf-8'))
                result = BacktestResultsService._parse_result_json(json_data)
                _log.info("Zip parsed | strategy=%s | trades=%d | profit=%.4f%%",
                          result.summary.strategy, result.summary.total_trades,
                          result.summary.total_profit)
                return result

        except json.JSONDecodeError as e:
            _log.error("JSON decode error in %s: %s", zip_file.name, e)
            raise ValueError(f"Failed to parse backtest JSON: {e}")
        except Exception as e:
            _log.error("Failed to parse zip %s: %s", zip_file.name, e)
            raise ValueError(f"Failed to parse backtest zip: {e}")

    @staticmethod
    def parse_result_json_file(json_path: str) -> Optional[BacktestResults]:
        """Parse a bt-*.result.json file directly.

        Args:
            json_path: Path to the result JSON file

        Returns:
            BacktestResults object or None if parsing fails
        """
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"Result file not found: {json_path}")
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return BacktestResultsService._parse_result_json(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse result JSON: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse result file: {e}")

    @staticmethod
    def _parse_result_json(data: Dict[str, Any]) -> BacktestResults:
        """Parse either a backtest zip JSON or a bt-*.result.json file.

        Zip format:  { "strategy": { "<Name>": { "trades": [...], "total_trades": N, ... } } }
        File format: { "strategy": "<Name>", "result": { "trades": [...] }, ... }

        Args:
            data: Parsed JSON data

        Returns:
            BacktestResults object
        """
        # --- detect format ---
        strategy_block = data.get('strategy', {})

        if isinstance(strategy_block, dict):
            # ZIP format: strategy block is a dict keyed by strategy name
            strategy_name = next(iter(strategy_block), 'Unknown')
            sd = strategy_block[strategy_name]          # full summary dict
            trades_data = sd.get('trades', [])
        else:
            # bt-*.result.json format
            strategy_name = str(strategy_block)
            sd = {}                                     # no pre-computed summary
            trades_data = data.get('result', {}).get('trades', [])

        # --- parse trades ---
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

        total = len(trades)

        # prefer pre-computed values from zip summary, fall back to computing from trades
        wins   = int(sd.get('wins',   sum(1 for t in trades if t.profit > 0)))
        losses = int(sd.get('losses', sum(1 for t in trades if t.profit < 0)))
        draws  = int(sd.get('draws',  sum(1 for t in trades if t.profit == 0)))
        win_rate         = float(sd.get('winrate', wins / total if total else 0.0)) * 100
        avg_profit       = float(sd.get('profit_mean', sum(t.profit for t in trades) / total if total else 0.0)) * 100
        total_profit     = float(sd.get('profit_total', 0.0)) * 100
        total_profit_abs = float(sd.get('profit_total_abs', sum(t.profit_abs for t in trades)))
        max_drawdown     = float(sd.get('max_relative_drawdown', sd.get('max_drawdown_account', 0.0))) * 100
        max_drawdown_abs = float(sd.get('max_drawdown_abs', 0.0))
        sharpe           = sd.get('sharpe')
        sortino          = sd.get('sortino')
        calmar           = sd.get('calmar')
        timeframe        = str(sd.get('timeframe', ''))
        starting_balance = float(sd.get('starting_balance', sd.get('dry_run_wallet', 0.0)))
        final_balance    = float(sd.get('final_balance', 0.0))
        avg_duration_s   = float(sd.get('holding_avg_s', 0.0))
        avg_duration_min = int(avg_duration_s / 60) if avg_duration_s else (
            int(sum(t.duration for t in trades) / total) if total else 0
        )

        summary = BacktestSummary(
            strategy=strategy_name,
            timeframe=timeframe,
            total_trades=int(sd.get('total_trades', total)),
            wins=wins,
            losses=losses,
            draws=draws,
            win_rate=win_rate,
            avg_profit=avg_profit,
            total_profit=total_profit,
            total_profit_abs=total_profit_abs,
            sharpe_ratio=float(sharpe) if sharpe is not None else None,
            sortino_ratio=float(sortino) if sortino is not None else None,
            calmar_ratio=float(calmar) if calmar is not None else None,
            max_drawdown=max_drawdown,
            max_drawdown_abs=max_drawdown_abs,
            trade_duration_avg=avg_duration_min,
            starting_balance=starting_balance,
            final_balance=final_balance,
            timerange=str(sd.get('timerange', '')),
            pairlist=list(sd.get('pairlist', [])),
            backtest_start=str(sd.get('backtest_start', '')),
            backtest_end=str(sd.get('backtest_end', '')),
            expectancy=float(sd.get('expectancy', 0.0)),
            profit_factor=float(sd.get('profit_factor', 0.0)),
            max_consecutive_wins=int(sd.get('max_consecutive_wins', 0)),
            max_consecutive_losses=int(sd.get('max_consecutive_losses', 0)),
        )

        return BacktestResults(summary=summary, trades=trades, raw_data=data)

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
