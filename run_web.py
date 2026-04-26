#!/usr/bin/env python3
"""Web server launcher — FastAPI + uvicorn with unified logging.

Usage
-----
    python run_web.py                        # defaults: 0.0.0.0:8000, no reload
    python run_web.py --port 9000
    python run_web.py --host 127.0.0.1 --port 8080
    python run_web.py --reload               # auto-reload on code changes (dev)
    python run_web.py --log-level debug
    python run_web.py --no-open              # skip browser auto-open

The server is available at:
    http://127.0.0.1:<port>          (local)
    http://<host>:<port>/docs        (Swagger UI)
    http://<host>:<port>/app         (React SPA)

Logs are written to  data/log/web.log  (rotating, 5 MB × 3 backups)
and also streamed to the console with ANSI colours.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ── Make sure the project root is on sys.path ─────────────────────────────────
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Load .env early so settings / AI keys are available ──────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass  # python-dotenv not installed — skip silently


# ─────────────────────────────────────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────────────────────────────────────

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_CYAN   = "\033[36m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_RED    = "\033[31m"
_WHITE  = "\033[37m"

_LEVEL_COLORS = {
    "DEBUG":    _DIM + _WHITE,
    "INFO":     _CYAN,
    "WARNING":  _YELLOW,
    "ERROR":    _BOLD + _RED,
    "CRITICAL": _BOLD + _RED,
    "ACCESS":   _BOLD + _GREEN,
}

_FILE_FMT = logging.Formatter(
    "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-35s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class _ColorFormatter(logging.Formatter):
    _FMT = "%(asctime)s {color}[%(levelname)-8s]{reset} {dim}%(name)s{reset}: %(message)s"

    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLORS.get(record.levelname, _WHITE)
        fmt = self._FMT.format(color=color, reset=_RESET, dim=_DIM)
        return logging.Formatter(fmt, datefmt="%H:%M:%S").format(record)


def _setup_logging(log_level: str) -> tuple[logging.Logger, Path]:
    """Configure root + app loggers and return (app_logger, log_file_path)."""
    numeric = getattr(logging, log_level.upper(), logging.INFO)

    # ── Log directory ─────────────────────────────────────────────────────────
    log_dir = _ROOT / "data" / "log"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        # Quick write-test
        probe = log_dir / ".write_test"
        probe.write_text("", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError:
        import tempfile
        log_dir = Path(tempfile.gettempdir()) / "freqtrade_gui_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "web.log"

    # ── Handlers ──────────────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric)
    console_handler.setFormatter(_ColorFormatter())

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # always capture everything to file
    file_handler.setFormatter(_FILE_FMT)

    # ── Root logger ───────────────────────────────────────────────────────────
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # ── App logger (freqtrade_gui) ─────────────────────────────────────────────
    # Also initialise the project's own logging system so all internal
    # get_logger() calls write to the same file.
    try:
        from app.core.utils.app_logger import configure_logging
        configure_logging(str(log_dir))
    except Exception:
        pass  # not critical — root logger already covers everything

    # ── Silence noisy third-party loggers ─────────────────────────────────────
    for noisy in ("watchfiles", "watchgod"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logging.getLogger("web"), log_file


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Freqtrade GUI — web server launcher",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--host",      default="0.0.0.0",  help="Bind address")
    p.add_argument("--port",      default=8000, type=int, help="TCP port")
    p.add_argument("--reload",    action="store_true",  help="Auto-reload on code changes (dev)")
    p.add_argument("--log-level", default="info",
                   choices=["debug", "info", "warning", "error", "critical"],
                   help="Console log level")
    p.add_argument("--no-open",   action="store_true",  help="Do not open browser on start")
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────────────────────

def _banner(host: str, port: int, log_file: Path, reload: bool) -> None:
    local = f"http://127.0.0.1:{port}"
    bound = f"http://{host}:{port}" if host not in ("0.0.0.0", "::") else local
    lines = [
        "",
        f"  {_BOLD}{_CYAN}Freqtrade GUI — Web Server{_RESET}",
        "",
        f"  {'Local':12s}  {_BOLD}{local}{_RESET}",
        f"  {'API docs':12s}  {_BOLD}{local}/docs{_RESET}",
        f"  {'React app':12s}  {_BOLD}{local}/app{_RESET}",
        f"  {'Log file':12s}  {_DIM}{log_file}{_RESET}",
        f"  {'Reload':12s}  {'on' if reload else 'off'}",
        "",
    ]
    sep = "  " + "─" * 52
    print(sep)
    for line in lines:
        print(line)
    print(sep)
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()
    log, log_file = _setup_logging(args.log_level)

    _banner(args.host, args.port, log_file, args.reload)

    log.info(
        "Starting uvicorn  host=%s  port=%d  reload=%s  log_level=%s",
        args.host, args.port, args.reload, args.log_level,
    )

    # Open browser after a short delay (only when binding to localhost)
    if not args.no_open:
        local_url = f"http://127.0.0.1:{args.port}/app"
        try:
            import threading
            def _open():
                import time
                time.sleep(1.4)
                webbrowser.open(local_url)
            threading.Thread(target=_open, daemon=True).start()
        except Exception:
            pass

    import uvicorn

    # Build uvicorn log config that routes its output through our handlers
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": True,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
                "use_colors": True,
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["default"],
                "level": args.log_level.upper(),
                "propagate": True,   # propagate → root → our file handler
            },
            "uvicorn.error": {
                "level": args.log_level.upper(),
                "propagate": True,
            },
            "uvicorn.access": {
                "handlers": ["access"],
                "level": "INFO",
                "propagate": True,
            },
        },
    }

    try:
        uvicorn.run(
            "app.web.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
            log_config=log_config,
        )
    except KeyboardInterrupt:
        log.info("Server stopped by user (KeyboardInterrupt)")
    except Exception as exc:
        log.exception("Server crashed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
