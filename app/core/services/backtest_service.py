from pathlib import Path
from typing import List, Optional

from app.core.backtests.results_index import IndexStore
from app.core.parsing.backtest_parser import parse_backtest_results_from_zip as parse_backtest_zip
from app.core.backtests.results_store import RunStore
from app.core.freqtrade import (
    BacktestRunCommand,
    create_backtest_command,
    list_strategies,
    find_config_file_safe,
)
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
        return create_backtest_command(
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

        imported = skipped = 0
        settings = self.settings_service.load_settings()
        user_data_dir = (
            Path(settings.user_data_path).expanduser().resolve()
            if settings.user_data_path
            else None
        )

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
                config_path = None
                if user_data_dir:
                    try:
                        config_path = str(
                            find_config_file_safe(user_data_dir, strategy_name=strategy)
                        )
                    except FileNotFoundError:
                        config_path = None
                RunStore.save(
                    results,
                    str(results_dir / strategy),
                    config_path=config_path,
                )
                imported += 1
            except Exception as e:
                _log.warning("Failed to import zip %s: %s", zip_path.name, e)

        _log.info("Index rebuild: imported=%d skipped=%d", imported, skipped)

    def parse_and_save_latest_results(
        self,
        export_dir: Path,
        strategy_name: Optional[str] = None,
    ) -> Optional[str]:
        """Parse the newest backtest result zip and save it to the index.

        Args:
            export_dir: Directory containing backtest result zip files.
            strategy_name: Optional strategy name hint for directory naming.

        Returns:
            Run ID string if successful, None otherwise.
        """
        settings = self.settings_service.load_settings()
        if not settings or not settings.user_data_path:
            _log.warning("No user_data_path configured — cannot save results")
            return None

        try:
            zips = sorted(
                export_dir.glob("*.zip"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not zips:
                _log.warning("No zip files found in %s", export_dir)
                return None

            newest_zip = zips[0]
            results = parse_backtest_zip(str(newest_zip))

            # Resolve config path for the strategy
            config_path = None
            strategy = strategy_name or results.summary.strategy
            user_data_dir = Path(settings.user_data_path)
            try:
                config_path = str(find_config_file_safe(user_data_dir, strategy_name=strategy))
            except FileNotFoundError:
                pass

            backtest_results_dir = user_data_dir / "backtest_results"
            strategy_dir = backtest_results_dir / strategy
            run_dir = RunStore.save(results, str(strategy_dir), config_path=config_path)

            run_id = run_dir.name
            _log.info("Backtest results saved: strategy=%s run_id=%s", strategy, run_id)
            return run_id

        except Exception as e:
            _log.error("Failed to parse and save backtest results: %s", e)
            return None
