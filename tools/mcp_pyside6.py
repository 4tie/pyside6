import subprocess
import os
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("PySide6")

_ROOT = Path(__file__).parent.parent
_SKIP = {".venv", ".git", "__pycache__", ".ruff_cache", "tools", "docs", "logs"}


@mcp.tool()
def run_app() -> str:
    """Launch main.py."""
    subprocess.Popen(["python", str(_ROOT / "main.py")], cwd=str(_ROOT))
    return "App launched"


@mcp.tool()
def run_tests() -> str:
    """Run pytest and return output."""
    result = subprocess.run(["pytest", "--tb=short"], capture_output=True, text=True, cwd=str(_ROOT))
    return result.stdout + result.stderr


@mcp.tool()
def read_logs() -> str:
    """Read logs/app.log."""
    log = _ROOT / "logs" / "app.log"
    if log.exists():
        return log.read_text(encoding="utf8")
    return "No log file found"


@mcp.tool()
def list_ui_files() -> list:
    """List all .py and .ui files under app/ui/."""
    ui_dir = _ROOT / "app" / "ui"
    if not ui_dir.exists():
        return []
    return [str(p.relative_to(_ROOT)) for p in ui_dir.rglob("*.py")]


@mcp.tool()
def read_python_file(relative_path: str) -> str:
    """Read any Python file in the project by relative path (e.g. 'app/ui/pages/backtest_page.py')."""
    p = _ROOT / relative_path
    if not p.exists():
        return f"Not found: {relative_path}"
    if not p.suffix == ".py":
        return "Only .py files are supported"
    return p.read_text(encoding="utf8")


if __name__ == "__main__":
    mcp.run()
