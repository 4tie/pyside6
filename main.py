import argparse
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Load .env file early so environment variables are available for settings.
load_dotenv()


ROOT_DIR = Path(__file__).parent.resolve()
RE_WEB_DIR = ROOT_DIR / "re_web"


def run_desktop() -> None:
    """Run the PySide6 desktop application."""
    from PySide6 import __version__ as pyside_version
    from PySide6.QtWidgets import QApplication

    from app.app_state.settings_state import SettingsState
    from app.core.utils.app_logger import configure_logging, get_logger

    app = QApplication(sys.argv)

    settings_state = SettingsState()
    settings = settings_state.load_settings()

    log_dir = ROOT_DIR / "data" / "log"
    configure_logging(str(log_dir))
    log = get_logger("startup")

    log.info("=" * 60)
    log.info("Freqtrade GUI starting")
    log.info("Python     : %s", sys.version.split()[0])
    log.info("Platform   : %s %s", platform.system(), platform.release())
    log.info("PySide6    : %s", pyside_version)
    log.info("user_data  : %s", settings.user_data_path)
    log.info("venv       : %s", settings.venv_path)
    log.info("python_exe : %s", settings.python_executable)
    log.info("freqtrade  : %s", settings.freqtrade_executable)
    log.info("use_module : %s", settings.use_module_execution)
    log.info("=" * 60)

    from app.ui.main_window import ModernMainWindow

    ModernMainWindow(settings_state=settings_state)
    log.info("Main window shown")

    exit_code = app.exec()
    log.info("Application exiting - code=%d", exit_code)
    sys.exit(exit_code)


def _start_process(
    name: str,
    command: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.Popen:
    print(f"Starting {name}: {' '.join(command)}", flush=True)
    return subprocess.Popen(command, cwd=str(cwd), env=env)


def _terminate_process(name: str, proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    print(f"Stopping {name}...", flush=True)
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        print(f"{name} did not exit after SIGTERM; killing.", flush=True)
        proc.kill()
        proc.wait(timeout=5)


def run_web_stack(host: str, backend_port: int, frontend_port: int) -> int:
    """Run FastAPI backend and Next.js frontend as supervised child processes."""
    if not RE_WEB_DIR.exists():
        raise FileNotFoundError(f"Frontend directory not found: {RE_WEB_DIR}")

    backend_url = f"http://{host}:{backend_port}"
    frontend_url = f"http://{host}:{frontend_port}"
    frontend_env = dict(os.environ)
    frontend_env["NEXT_PUBLIC_API_URL"] = f"{backend_url}/api"

    backend = _start_process(
        "backend",
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.web.main:app",
            "--host",
            host,
            "--port",
            str(backend_port),
        ],
        ROOT_DIR,
    )
    frontend = _start_process(
        "frontend",
        [
            "npm",
            "run",
            "dev",
            "--",
            "--hostname",
            host,
            "--port",
            str(frontend_port),
        ],
        RE_WEB_DIR,
        env=frontend_env,
    )

    print(f"API: {backend_url}/api/health", flush=True)
    print(f"UI : {frontend_url}", flush=True)

    processes = {"backend": backend, "frontend": frontend}

    def handle_signal(signum, _frame) -> None:
        print(f"Received signal {signum}; shutting down.", flush=True)
        for proc_name, proc in processes.items():
            _terminate_process(proc_name, proc)
        raise SystemExit(0)

    previous_sigint = signal.signal(signal.SIGINT, handle_signal)
    previous_sigterm = signal.signal(signal.SIGTERM, handle_signal)
    try:
        while True:
            for proc_name, proc in processes.items():
                exit_code = proc.poll()
                if exit_code is not None:
                    print(f"{proc_name} exited with code {exit_code}; shutting down.", flush=True)
                    for other_name, other_proc in processes.items():
                        if other_name != proc_name:
                            _terminate_process(other_name, other_proc)
                    return exit_code
            time.sleep(0.5)
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
        for proc_name, proc in processes.items():
            _terminate_process(proc_name, proc)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Freqtrade GUI app.")
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Run the existing PySide6 desktop app instead of the web stack.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for backend and frontend.")
    parser.add_argument("--backend-port", type=int, default=8000, help="FastAPI backend port.")
    parser.add_argument("--frontend-port", type=int, default=3000, help="Next.js frontend port.")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv[1:])
    if args.desktop:
        run_desktop()
        return
    sys.exit(run_web_stack(args.host, args.backend_port, args.frontend_port))


if __name__ == "__main__":
    main()
