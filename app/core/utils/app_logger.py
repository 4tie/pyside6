import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Custom CMD level — between INFO(20) and WARNING(30)
# Used for: process execution, freqtrade commands, successful calls
# ---------------------------------------------------------------------------
CMD_LEVEL = 25
logging.addLevelName(CMD_LEVEL, "CMD")


def _cmd(self: logging.Logger, message: str, *args, **kwargs) -> None:
    if self.isEnabledFor(CMD_LEVEL):
        self._log(CMD_LEVEL, message, args, **kwargs)


logging.Logger.cmd = _cmd  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# ANSI color codes
# ---------------------------------------------------------------------------
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_RED    = "\033[31m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_WHITE  = "\033[37m"
_DIM    = "\033[2m"

_LEVEL_COLORS = {
    "DEBUG":    _DIM + _WHITE,
    "INFO":     _CYAN,
    "CMD":      _BOLD + _GREEN,
    "WARNING":  _YELLOW,
    "ERROR":    _BOLD + _RED,
    "CRITICAL": _BOLD + _RED,
}

# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------
_FILE_FMT = logging.Formatter(
    "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-30s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class _ColorFormatter(logging.Formatter):
    """Console formatter with ANSI color per log level."""

    _FMT = "%(asctime)s {color}[%(levelname)-8s]{reset} {dim}%(name)s{reset}: %(message)s"

    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLORS.get(record.levelname, _WHITE)
        fmt = self._FMT.format(color=color, reset=_RESET, dim=_DIM)
        formatter = logging.Formatter(fmt, datefmt="%H:%M:%S")
        return formatter.format(record)


# ---------------------------------------------------------------------------
# Section → log file mapping
# name prefix → filename under data/log/
# ---------------------------------------------------------------------------
_SECTION_FILES = {
    "ui":       "ui.log",
    "services": "services.log",
    "process":  "process.log",
    "startup":  "app.log",
    "settings": "services.log",
    "backtest": "services.log",
    "download": "services.log",
}
_DEFAULT_FILE = "app.log"

_root_logger: Optional[logging.Logger] = None
_log_dir: Optional[Path] = None
_file_handlers: dict[str, RotatingFileHandler] = {}


def _get_file_handler(log_dir: Path, filename: str) -> RotatingFileHandler:
    """Return a cached RotatingFileHandler for the given filename."""
    if filename not in _file_handlers:
        fh = RotatingFileHandler(
            log_dir / filename,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(_FILE_FMT)
        _file_handlers[filename] = fh
    return _file_handlers[filename]


def setup_logging(log_dir_path: Optional[str] = None) -> logging.Logger:
    """Configure application logging.

    Args:
        log_dir_path: Path to write log files. Defaults to data/log/ next to main.py.

    Returns:
        Root logger instance.
    """
    global _root_logger, _log_dir

    # Resolve log directory
    if log_dir_path:
        _log_dir = Path(log_dir_path)
    else:
        _log_dir = Path(__file__).parent.parent.parent.parent / "data" / "log"
    _log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("freqtrade_gui")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    # Console — INFO+ with colors
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(_ColorFormatter())
    logger.addHandler(console)

    # Main app.log file — everything
    logger.addHandler(_get_file_handler(_log_dir, "app.log"))

    _root_logger = logger
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a child logger under freqtrade_gui.<name>.

    Automatically attaches a section-specific log file handler based on
    the name prefix (ui.*, services.*, process.*, etc.).

    Args:
        name: Sub-module name e.g. 'ui.backtest_page', 'services.backtest', 'process'.

    Returns:
        Logger instance.
    """
    global _root_logger, _log_dir

    if _root_logger is None:
        _root_logger = setup_logging()

    if not name:
        return _root_logger

    child = _root_logger.getChild(name)

    # Attach section file handler if log_dir is known
    if _log_dir:
        section = name.split(".")[0]
        filename = _SECTION_FILES.get(section, _DEFAULT_FILE)
        # Only add if not already attached (avoid duplicates on re-calls)
        existing_files = {
            getattr(h, "baseFilename", None)
            for h in child.handlers
            if isinstance(h, RotatingFileHandler)
        }
        target = str(_log_dir / filename)
        if target not in existing_files and filename != "app.log":
            child.addHandler(_get_file_handler(_log_dir, filename))

    return child
