from pathlib import Path

from app.core.utils import app_logger


class LogPathResolver:
    """Resolves log file paths using the configured log directory."""

    @staticmethod
    def get_log_path(log_name: str) -> Path:
        """Return the full path for a log file by name.

        Args:
            log_name: Log filename, e.g. 'app.log'.

        Returns:
            Path to the log file under the configured log directory.
            Falls back to Path('data/log') if logging has not been set up yet.
        """
        log_dir: Path = app_logger._log_dir if app_logger._log_dir is not None else Path("data/log")
        return log_dir / log_name
