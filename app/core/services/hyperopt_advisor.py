"""
hyperopt_advisor.py — Analyses past hyperopt/backtest runs for a strategy
and recommends better hyperopt settings for the next run.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.core.utils.app_logger import get_logger

_log = get_logger("services.hyperopt_advisor")


@dataclass
class HyperoptSuggestion:
    """Recommended hyperopt settings derived from past run analysis."""
    epochs: int = 200
    spaces: List[str] = field(default_factory=lambda: ["buy", "sell", "roi", "stoploss", "trailing"])
    loss_function: str = "SharpeHyperOptLoss"
    min_timerange_days: int = 90
    tips: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source: str = "default"  # "last_run" | "default"


def _load_last_hyperopt_result(hyperopt_results_dir: Path, strategy: str) -> Optional[dict]:
    """Find the most recent .fthypt file for a strategy and read its summary."""
    if not hyperopt_results_dir.exists():
        return None
    pattern = f"strategy_{strategy}_*.fthypt"
    files = sorted(hyperopt_results_dir.glob(pattern), reverse=True)
    if not files:
        return None
    # .fthypt files are JSON lines — read the last line which is the best result
    try:
        lines = files[0].read_text(encoding="utf-8", errors="ignore").strip().splitlines()
        for line in reversed(lines):
            line = line.strip()
            if line.startswith("{"):
                return json.loads(line)
    except Exception as e:
        _log.warning("Could not read hyperopt result %s: %s", files[0].name, e)
    return None


def _load_last_backtest_meta(backtest_results_dir: Path, strategy: str) -> Optional[dict]:
    """Load the most recent backtest meta.json for a strategy."""
    strategy_dir = backtest_results_dir / strategy
    if not strategy_dir.exists():
        return None
    run_dirs = sorted(
        [d for d in strategy_dir.iterdir() if d.is_dir() and (d / "meta.json").exists()],
        key=lambda d: d.name,
        reverse=True,
    )
    if not run_dirs:
        return None
    try:
        return json.loads((run_dirs[0] / "meta.json").read_text(encoding="utf-8"))
    except Exception:
        return None


def analyse(
    strategy: str,
    user_data_path: str,
) -> HyperoptSuggestion:
    """
    Analyse past runs for a strategy and return recommended hyperopt settings.

    Args:
        strategy: Strategy name (e.g. "MultiMeee")
        user_data_path: Path to user_data directory

    Returns:
        HyperoptSuggestion with recommended settings and human-readable tips
    """
    root = Path(user_data_path).expanduser().resolve()
    backtest_dir = root / "backtest_results"
    hyperopt_dir = root / "hyperopt_results"

    suggestion = HyperoptSuggestion()
    meta = _load_last_backtest_meta(backtest_dir, strategy)

    # ── No history at all ──────────────────────────────────────────────
    if meta is None:
        suggestion.tips = [
            "No previous backtest found for this strategy.",
            "Run a backtest first to understand baseline performance before optimizing.",
            "Start with spaces: buy sell — optimizing entry/exit signals first gives the most signal.",
            "Use at least 90 days of data and 200+ epochs for reliable results.",
        ]
        suggestion.warnings = [
            "Optimizing without a baseline makes it hard to know if results improved.",
        ]
        suggestion.source = "default"
        return suggestion

    suggestion.source = "last_run"
    win_rate   = meta.get("win_rate_pct", 0.0)
    profit_pct = meta.get("profit_total_pct", 0.0)
    drawdown   = meta.get("max_drawdown_pct", 0.0)
    trades     = meta.get("trades_count", 0)
    sharpe     = meta.get("sharpe")
    timerange  = meta.get("timerange", "")

    tips: List[str] = []
    warnings: List[str] = []
    spaces: List[str] = []

    # ── Diagnose and recommend spaces ─────────────────────────────────
    if profit_pct < 0:
        tips.append(
            f"Last run was unprofitable ({profit_pct:.2f}%). "
            "Focus on buy/sell signal quality first — optimize 'buy sell' spaces only."
        )
        spaces = ["buy", "sell"]
    elif win_rate < 45:
        tips.append(
            f"Win rate is low ({win_rate:.1f}%). "
            "Optimize 'buy sell' to improve entry/exit signal accuracy."
        )
        spaces = ["buy", "sell"]
    elif drawdown > 30:
        tips.append(
            f"Max drawdown is high ({drawdown:.1f}%). "
            "Optimize 'stoploss trailing' to protect capital."
        )
        spaces = ["stoploss", "trailing"]
    elif profit_pct > 0 and win_rate >= 50 and drawdown < 20:
        tips.append(
            f"Strategy is profitable ({profit_pct:.2f}%, {win_rate:.1f}% win rate). "
            "Fine-tune ROI and trailing stop to squeeze more profit."
        )
        spaces = ["roi", "stoploss", "trailing"]
    else:
        spaces = ["buy", "sell", "roi", "stoploss", "trailing"]

    # ── Recommend loss function ────────────────────────────────────────
    if drawdown > 25:
        suggestion.loss_function = "MaxDrawDownHyperOptLoss"
        tips.append("Using MaxDrawDownHyperOptLoss to prioritize capital protection.")
    elif sharpe is not None and sharpe < 0.5:
        suggestion.loss_function = "SharpeHyperOptLoss"
        tips.append("Using SharpeHyperOptLoss to improve risk-adjusted returns.")
    elif trades < 20:
        suggestion.loss_function = "OnlyProfitHyperOptLoss"
        tips.append(
            f"Only {trades} trades in last run — using OnlyProfitHyperOptLoss "
            "to avoid over-penalizing low-trade strategies."
        )
    else:
        suggestion.loss_function = "SharpeHyperOptLoss"

    # ── Recommend epochs ──────────────────────────────────────────────
    n_spaces = len(spaces)
    if n_spaces <= 2:
        suggestion.epochs = 150
        tips.append("Optimizing 2 spaces — 150 epochs is sufficient.")
    elif n_spaces <= 3:
        suggestion.epochs = 300
        tips.append("Optimizing 3 spaces — 300 epochs recommended.")
    else:
        suggestion.epochs = 500
        tips.append("Optimizing 5 spaces — use 500+ epochs for thorough search.")

    # ── Timerange advice ──────────────────────────────────────────────
    if timerange:
        parts = timerange.split("-")
        if len(parts) == 2:
            try:
                from datetime import datetime
                start = datetime.strptime(parts[0], "%Y%m%d")
                end   = datetime.strptime(parts[1], "%Y%m%d")
                days  = (end - start).days
                if days < 30:
                    warnings.append(
                        f"Last backtest used only {days} days of data. "
                        "Use at least 90 days for hyperopt — short windows cause overfitting."
                    )
                    suggestion.min_timerange_days = 90
                elif days < 90:
                    warnings.append(
                        f"Last backtest used {days} days. "
                        "90+ days is recommended for hyperopt."
                    )
                    suggestion.min_timerange_days = 90
                else:
                    suggestion.min_timerange_days = days
                    tips.append(f"Use the same {days}-day timerange as your last backtest for consistency.")
            except ValueError:
                pass

    # ── General tips always shown ─────────────────────────────────────
    tips.append(
        "Always backtest the optimized parameters on a different (out-of-sample) "
        "timerange to check for overfitting before using live."
    )
    if trades > 0 and trades < 30:
        warnings.append(
            f"Only {trades} trades in last run. More trades = more reliable optimization. "
            "Consider adding more pairs or a longer timerange."
        )

    suggestion.spaces   = spaces
    suggestion.tips     = tips
    suggestion.warnings = warnings
    return suggestion
