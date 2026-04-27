#!/usr/bin/env python3
"""Web server launcher — starts FastAPI backend (uvicorn) + React dev server (vite).

Usage
-----
    python run_web.py                        # backend :8000, React dev :5173
    python run_web.py --port 9000            # backend on custom port
    python run_web.py --no-react             # backend only (use built dist)
    python run_web.py --log-level debug
    python run_web.py --no-open              # skip browser auto-open

URLs
----
    http://127.0.0.1:5173/app    React dev server (proxies /api → :8000)
    http://127.0.0.1:8000/docs   FastAPI Swagger UI
    http://127.0.0.1:8000/api    REST API

Logs are written to  data/log/web.log  (rotating, 5 MB × 3 backups).
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
import threading
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ── Project root on sys.path ──────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_RE_WEB = _ROOT / "app" / "re_web"

# ── Load .env ─────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Logging
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
    numeric = getattr(logging, log_level.upper(), logging.INFO)

    log_dir = _ROOT / "data" / "log"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        probe = log_dir / ".write_test"
        probe.write_text("", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError:
        import tempfile
        log_dir = Path(tempfile.gettempdir()) / "freqtrade_gui_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "web.log"

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric)
    console.setFormatter(_ColorFormatter())

    fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_FILE_FMT)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(fh)

    for noisy in ("watchfiles", "watchgod"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    try:
        from app.core.utils.app_logger import configure_logging
        configure_logging(str(log_dir))
    except Exception:
        pass

    return logging.getLogger("web"), log_file


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    _env_port = os.environ.get("WEB_PORT")
    _default_port = 8000
    if _env_port:
        try:
            _default_port = int(_env_port)
            if not (1 <= _default_port <= 65535):
                raise ValueError
        except ValueError:
            print(f"ERROR: WEB_PORT={_env_port!r} is not a valid port", file=sys.stderr)
            sys.exit(1)

    p = argparse.ArgumentParser(
        description="Freqtrade GUI — backend + React dev server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--host",       default=os.environ.get("WEB_HOST", "127.0.0.1"), help="Backend bind address")
    p.add_argument("--port",       default=_default_port, type=int, help="Backend TCP port")
    p.add_argument("--react-port", default=5173, type=int, help="React dev server port")
    p.add_argument("--no-react",   action="store_true", help="Skip React dev server (serve built dist)")
    p.add_argument("--reload",     action="store_true", help="Auto-reload backend on code changes")
    p.add_argument("--log-level",  default="info",
                   choices=["debug", "info", "warning", "error", "critical"])
    p.add_argument("--no-open",    action="store_true", help="Do not open browser on start")
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────────────────────

def _banner(host: str, port: int, react_port: int, no_react: bool, log_file: Path) -> None:
    app_url = (
        f"http://127.0.0.1:{react_port}/app"
        if not no_react
        else f"http://127.0.0.1:{port}/app"
    )
    lines = [
        "",
        f"  {_BOLD}{_CYAN}Freqtrade GUI{_RESET}",
        "",
        f"  {'React app':14s}  {_BOLD}{app_url}{_RESET}",
        f"  {'API':14s}  {_BOLD}http://127.0.0.1:{port}/api{_RESET}",
        f"  {'API docs':14s}  {_BOLD}http://127.0.0.1:{port}/docs{_RESET}",
        f"  {'Log file':14s}  {_DIM}{log_file}{_RESET}",
        "",
    ]
    sep = "  " + "─" * 54
    print(sep)
    for line in lines:
        print(line)
    print(sep)
    print()


# ─────────────────────────────────────────────────────────────────────────────
# React dev server
# ─────────────────────────────────────────────────────────────────────────────

def _start_react(react_port: int, backend_port: int, log: logging.Logger) -> subprocess.Popen | None:
    """Start `npm run dev` inside app/re_web/ and stream its output."""
    if not (_RE_WEB / "node_modules").exists():
        log.warning("app/re_web/node_modules not found — run `npm install` inside app/re_web/ first")
        return None

    env = {**os.environ, "VITE_BACKEND_PORT": str(backend_port)}
    try:
        proc = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(react_port)],
            cwd=str(_RE_WEB),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        log.warning("npm not found — React dev server not started. Install Node.js to enable it.")
        return None

    def _stream() -> None:
        assert proc.stdout
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                log.info("[react] %s", line)

    threading.Thread(target=_stream, daemon=True).start()
    log.info("React dev server started  pid=%d  port=%d", proc.pid, react_port)
    return proc


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()
    log, log_file = _setup_logging(args.log_level)

    _banner(args.host, args.port, args.react_port, args.no_react, log_file)

    react_proc: subprocess.Popen | None = None

    if not args.no_react:
        react_proc = _start_react(args.react_port, args.port, log)

    # Open browser after a short delay
    if not args.no_open:
        url = (
            f"http://127.0.0.1:{args.react_port}/app"
            if (not args.no_react and react_proc)
            else f"http://127.0.0.1:{args.port}/app"
        )
        def _open() -> None:
            import time
            time.sleep(1.8)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    def _shutdown(signum: int, frame: object) -> None:
        log.info("Shutting down…")
        if react_proc and react_proc.poll() is None:
            react_proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    log.info(
        "Starting backend  host=%s  port=%d  reload=%s  log_level=%s",
        args.host, args.port, args.reload, args.log_level,
    )

    import uvicorn

    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {"()": "uvicorn.logging.DefaultFormatter", "fmt": "%(levelprefix)s %(message)s", "use_colors": True},
            "access":  {"()": "uvicorn.logging.AccessFormatter",  "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s', "use_colors": True},
        },
        "handlers": {
            "default": {"formatter": "default", "class": "logging.StreamHandler", "stream": "ext://sys.stdout"},
            "access":  {"formatter": "access",  "class": "logging.StreamHandler", "stream": "ext://sys.stdout"},
        },
        "loggers": {
            "uvicorn":        {"handlers": ["default"], "level": args.log_level.upper(), "propagate": True},
            "uvicorn.error":  {"level": args.log_level.upper(), "propagate": True},
            "uvicorn.access": {"handlers": ["access"],  "level": "INFO", "propagate": True},
        },
    }

    try:
        uvicorn.run(
            "leave.web.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
            log_config=log_config,
        )
    except KeyboardInterrupt:
        log.info("Backend stopped.")
    except Exception as exc:
        log.exception("Backend crashed: %s", exc)
        sys.exit(1)
    finally:
        if react_proc and react_proc.poll() is None:
            react_proc.terminate()


if __name__ == "__main__":
    main()
