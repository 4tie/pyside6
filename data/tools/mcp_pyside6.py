import json
import subprocess
import sys
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("PySide6")

_ROOT = Path(__file__).parents[2]


def _python() -> str:
    """Return the venv python from data/settings.json, fallback to sys.executable."""
    settings_path = _ROOT / "data" / "settings.json"
    if settings_path.exists():
        try:
            s = json.loads(settings_path.read_text(encoding="utf8"))
            exe = s.get("python_executable")
            if exe and Path(exe).exists():
                return exe
        except Exception:
            pass
    return sys.executable


@mcp.tool()
def run_app() -> str:
    """Launch main.py using the project venv Python."""
    subprocess.Popen([_python(), str(_ROOT / "main.py")], cwd=str(_ROOT))
    return "App launched"


@mcp.tool()
def run_tests() -> str:
    """Run pytest and return output."""
    result = subprocess.run(
        [_python(), "-m", "pytest", "--tb=short"],
        capture_output=True, text=True, cwd=str(_ROOT),
    )
    return result.stdout + result.stderr


@mcp.tool()
def read_logs(log_name: str = "app") -> str:
    """Read a log file from data/log/.

    Args:
        log_name: One of 'app', 'ui', 'services', 'process' (default: 'app').
    """
    log = _ROOT / "data" / "log" / f"{log_name}.log"
    return log.read_text(encoding="utf8") if log.exists() else f"No log file found: {log_name}.log"


@mcp.tool()
def list_ui_files() -> list:
    """List all .py files under app/ui/."""
    ui_dir = _ROOT / "app" / "ui"
    return [str(p.relative_to(_ROOT)) for p in ui_dir.rglob("*.py")] if ui_dir.exists() else []


@mcp.tool()
def read_python_file(relative_path: str) -> str:
    """Read any .py file by relative path (e.g. 'app/ui/pages/backtest_page.py').

    Args:
        relative_path: Path relative to project root.
    """
    p = _ROOT / relative_path
    if not p.exists():
        return f"Not found: {relative_path}"
    if p.suffix != ".py":
        return "Only .py files supported"
    return p.read_text(encoding="utf8")


if __name__ == "__main__":
    mcp.run()
