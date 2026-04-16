import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_root_logger: Optional[logging.Logger] = None

# Log format: timestamp | level | module | message
_FILE_FMT = logging.Formatter(
    "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-30s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_CONSOLE_FMT = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def setup_logging(user_data_path: Optional[str] = None) -> logging.Logger:
    """Configure application logging.

    File handler  : user_data/logs/app.log  (DEBUG+, 5 MB rotating, 3 backups)
    Console handler: stdout  (INFO+)

    Args:
        user_data_path: Path to the freqtrade user_data directory.

    Returns:
        Root logger instance.
    """
    global _root_logger

    logger = logging.getLogger("freqtrade_gui")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    # Console — INFO and above
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(_CONSOLE_FMT)
    logger.addHandler(console)

    # File — DEBUG and above, rotating
    if user_data_path:
        log_dir = Path(user_data_path) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"
        fh = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(_FILE_FMT)
        logger.addHandler(fh)
        logger.info("Log file: %s", log_file)

    _root_logger = logger
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a child logger under freqtrade_gui.<name>, or the root logger.

    Args:
        name: Sub-module name, e.g. "backtest", "settings", "process".
              If None, returns the root freqtrade_gui logger.

    Returns:
        Logger instance.
    """
    global _root_logger
    if _root_logger is None:
        _root_logger = setup_logging()
    if name:
        return _root_logger.getChild(name)
    return _root_logger
