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
    epochs: int,
    timerange: str | None = None,
    pairs: list[str] | None = None,
    spaces: list[str] | None = None,
    hyperopt_loss: str | None = None,
    extra_flags: list[str] | None = None,
):
    """Build optimize command with explicit parameters, logging and validation.

    Args:
        settings: AppSettings with paths configured.
        strategy_name: Name of the strategy class to optimise.
        timeframe: Candle timeframe e.g. '5m', '1h'.
        epochs: Number of hyperopt epochs to run.
        timerange: Optional timerange e.g. '20240101-20241231'.
        pairs: Optional list of trading pairs.
        spaces: Optional list of hyperopt spaces e.g. ['roi', 'stoploss'].
        hyperopt_loss: Optional hyperopt loss function name
            e.g. 'SharpeHyperOptLoss'.
        extra_flags: Optional additional freqtrade CLI flags.
    """
    _log.debug("Building optimize command: %s", strategy_name)
    try:
        return _create_optimize(
            settings=settings,
            strategy_name=strategy_name,
            timeframe=timeframe,
            epochs=epochs,
            timerange=timerange,
            pairs=pairs,
            spaces=spaces,
            hyperopt_loss=hyperopt_loss,
            extra_flags=extra_flags,
        )
    except Exception as e:
        _log.error("Failed to build optimize command: %s", e)
        raise

def create_download_data_command(
    settings,
    timeframe: str,
    timerange: str | None = None,
    pairs: list[str] | None = None,
    extra_flags: list[str] | None = None,
    prepend: bool = False,
    erase: bool = False,
):
    """Build download data command with explicit parameters, logging and validation.

    Args:
        settings: AppSettings with paths configured.
        timeframe: Candle timeframe e.g. '5m', '1h'.
        timerange: Optional timerange e.g. '20240101-20241231'.
        pairs: Optional list of trading pairs.
        extra_flags: Unused; reserved for future extension.
        prepend: When True, include --prepend flag in the command.
        erase: When True, include --erase flag in the command.
    """
    _log.debug("Building download data command")
    try:
        return _create_download(
            settings=settings,
            timeframe=timeframe,
            timerange=timerange,
            pairs=pairs,
            prepend=prepend,
            erase=erase,
        )
    except Exception as e:
        _log.error("Failed to build download data command: %s", e)
        raise
