from app.core.ai.journal.event_journal import EventJournal
from app.core.utils.app_logger import get_logger

_log = get_logger("services.backtest_adapter")


class BacktestJournalAdapter:
    """Connects BacktestService signals to EventJournal recording.

    Adapters import from services — services never import from journal.
    """

    def __init__(self, journal: EventJournal, backtest_service=None) -> None:
        self._journal = journal
        if backtest_service is not None:
            self._connect(backtest_service)

    def _connect(self, backtest_service) -> None:
        """Connect to available signals on backtest_service."""
        if hasattr(backtest_service, "process_started"):
            backtest_service.process_started.connect(self._on_backtest_started)
        if hasattr(backtest_service, "process_finished"):
            backtest_service.process_finished.connect(self._on_backtest_finished)

    def on_backtest_started(self, strategy: str = "", timeframe: str = "") -> None:
        """Record a backtest_started event.

        Args:
            strategy: Name of the strategy being backtested.
            timeframe: Timeframe used for the backtest.
        """
        _log.debug("Recording backtest_started: strategy=%s timeframe=%s", strategy, timeframe)
        self._journal.record(
            "backtest_started",
            "backtest_service",
            {"strategy": strategy, "timeframe": timeframe},
        )

    def on_backtest_finished(self, exit_code: int = 0, result_summary: str = "") -> None:
        """Record a backtest_finished event.

        Args:
            exit_code: Process exit code (0 = success).
            result_summary: Short human-readable summary of the result.
        """
        _log.debug(
            "Recording backtest_finished: exit_code=%d result_summary=%s",
            exit_code,
            result_summary,
        )
        self._journal.record(
            "backtest_finished",
            "backtest_service",
            {"exit_code": exit_code, "result_summary": result_summary},
        )

    def _on_backtest_started(self, *args) -> None:
        """Slot forwarded from process_started signal."""
        self.on_backtest_started()

    def _on_backtest_finished(self, *args) -> None:
        """Slot forwarded from process_finished signal."""
        exit_code = args[0] if args else 0
        self.on_backtest_finished(exit_code=exit_code)
