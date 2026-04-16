import subprocess
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("PySide6")

_ROOT = Path(__file__).parent.parent


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
    """Read data/log/app.log."""
    log = _ROOT / "data" / "log" / "app.log"
    return log.read_text(encoding="utf8") if log.exists() else "No log file found"


@mcp.tool()
def list_ui_files() -> list:
    """List all .py files under app/ui/."""
    ui_dir = _ROOT / "app" / "ui"
    return [str(p.relative_to(_ROOT)) for p in ui_dir.rglob("*.py")] if ui_dir.exists() else []


@mcp.tool()
def read_python_file(relative_path: str) -> str:
    """Read any .py file by relative path (e.g. 'app/ui/pages/backtest_page.py')."""
    p = _ROOT / relative_path
    if not p.exists():
        return f"Not found: {relative_path}"
    if p.suffix != ".py":
        return "Only .py files supported"
    return p.read_text(encoding="utf8")


if __name__ == "__main__":
    mcp.run()
