from pathlib import Path
from typing import List, Optional

from app.core.freqtrade.runners.backtest_runner import BacktestRunCommand, build_backtest_command
from app.core.freqtrade.resolvers.strategy_resolver import list_strategies
from app.core.backtests.results_index import IndexStore
from app.core.backtests.results_parser import parse_backtest_zip
from app.core.backtests.results_store import RunStore
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger

_log = get_logger("services.backtest")


class BacktestService:
    """Service for building backtest commands, listing strategies, and rebuilding indexes."""

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

    def build_command(
        self,
        strategy_name: str,
        timeframe: str,
        timerange: Optional[str] = None,
        pairs: Optional[List[str]] = None,
        max_open_trades: Optional[int] = None,
        dry_run_wallet: Optional[float] = None,
        extra_flags: Optional[List[str]] = None,
    ) -> BacktestRunCommand:
        """Build a backtest command."""
        settings = self.settings_service.load_settings()
        return build_backtest_command(
            settings=settings,
            strategy_name=strategy_name,
            timeframe=timeframe,
            timerange=timerange,
            pairs=pairs or [],
            max_open_trades=max_open_trades,
            dry_run_wallet=dry_run_wallet,
            extra_flags=extra_flags or [],
        )

    def get_available_strategies(self) -> List[str]:
        """List available strategy names from user_data/strategies/."""
        settings = self.settings_service.load_settings()
        if not settings.user_data_path:
            return []
        return list_strategies(Path(settings.user_data_path).expanduser().resolve())

    def rebuild_index(self, backtest_results_dir: str) -> None:
        """Parse any root-level zips not yet in the index and save them as runs."""
        from pathlib import Path as _Path
        results_dir = _Path(backtest_results_dir)
        if not results_dir.exists():
            return

        index = IndexStore.load(backtest_results_dir)
        imported = skipped = 0

        for zip_path in sorted(results_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime):
            try:
                results = parse_backtest_zip(str(zip_path))
                if not results:
                    continue
                strategy = results.summary.strategy
                existing = IndexStore.get_strategy_runs(backtest_results_dir, strategy)
                already = any(
                    r.get("trades_count") == results.summary.total_trades
                    and r.get("backtest_start") == results.summary.backtest_start
                    and r.get("backtest_end") == results.summary.backtest_end
                    for r in existing
                )
                if already:
                    skipped += 1
                    continue
                RunStore.save(results, str(results_dir / strategy))
                imported += 1
            except Exception as e:
                _log.warning("Failed to import zip %s: %s", zip_path.name, e)

        _log.info("Index rebuild: imported=%d skipped=%d", imported, skipped)
