import logging
import sys
from pathlib import Path
from typing import Optional


_logger: Optional[logging.Logger] = None


def setup_logging(user_data_path: Optional[str] = None) -> logging.Logger:
    """Configure application logging to user_data/logs/app.log and stdout.

    Args:
        user_data_path: Path to the freqtrade user_data directory. If None,
            logs only to stdout.

    Returns:
        Configured logger instance.
    """
    global _logger

    logger = logging.getLogger("freqtrade_gui")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # stdout handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # file handler
    if user_data_path:
        log_dir = Path(user_data_path) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """Return the application logger, initializing with defaults if needed."""
    global _logger
    if _logger is None:
        _logger = setup_logging()
    return _logger
