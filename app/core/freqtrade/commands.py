"""Central freqtrade command builders with proper wrappers."""
from app.core.freqtrade.runners.backtest_runner import create_backtest_command as _create_backtest
from app.core.freqtrade.runners.optimize_runner import create_optimize_command as _create_optimize
from app.core.freqtrade.runners.download_data_runner import create_download_data_command as _create_download
from app.core.utils.app_logger import get_logger

_log = get_logger("freqtrade.commands")

def create_backtest_command(
    settings,
    strategy_name: str,
    timeframe: str,
    timerange: str,
    pairs: list[str] | None,
    extra_flags: list[str],
    max_open_trades: int | None = None,
    dry_run_wallet: float | None = None,
):
    """Build backtest command with explicit parameters, logging and validation."""
    _log.debug("Building backtest command: %s", strategy_name)
    try:
        return _create_backtest(
            settings=settings,
            strategy_name=strategy_name,
            timeframe=timeframe,
            timerange=timerange,
            pairs=pairs,
            extra_flags=extra_flags,
            max_open_trades=max_open_trades,
            dry_run_wallet=dry_run_wallet,
        )
    except Exception as e:
        _log.error("Failed to build backtest command: %s", e)
        raise

def create_optimize_command(
    settings,
    strategy_name: str,
    timeframe: str,
    timerange: str,
    pairs: list[str] | None,
    extra_flags: list[str],
):
    """Build optimize command with explicit parameters, logging and validation."""
    _log.debug("Building optimize command: %s", strategy_name)
    try:
        return _create_optimize(
            settings=settings,
            strategy_name=strategy_name,
            timeframe=timeframe,
            timerange=timerange,
            pairs=pairs,
            extra_flags=extra_flags,
        )
    except Exception as e:
        _log.error("Failed to build optimize command: %s", e)
        raise

def create_download_data_command(
    settings,
    timerange: str,
    pairs: list[str],
    extra_flags: list[str],
):
    """Build download data command with explicit parameters, logging and validation."""
    _log.debug("Building download data command")
    try:
        return _create_download(
            settings=settings,
            timerange=timerange,
            pairs=pairs,
            extra_flags=extra_flags,
        )
    except Exception as e:
        _log.error("Failed to build download data command: %s", e)
        raise
