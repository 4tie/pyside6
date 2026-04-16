import subprocess
import json
import zipfile
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("Freqtrade")

_ROOT = Path(__file__).parent.parent


def _settings() -> dict:
    p = Path.home() / ".freqtrade_gui" / "settings.json"
    return json.loads(p.read_text(encoding="utf8")) if p.exists() else {}


def _python() -> str:
    return _settings().get("python_executable") or "python"


def _user_data() -> Path:
    s = _settings()
    return Path(s.get("user_data_path", str(_ROOT / "user_data")))


@mcp.tool()
def run_backtest(strategy: str, timeframe: str, timerange: str = "") -> str:
    """Run a freqtrade backtest for a given strategy.

    Args:
        strategy: Strategy filename without .py (e.g. 'MyStrategy')
        timeframe: Candle timeframe (e.g. '5m', '1h')
        timerange: Optional timerange (e.g. '20240101-20241231')
    """
    ud = _user_data()
    args = [
        _python(), "-m", "freqtrade", "backtesting",
        "--strategy", strategy,
        "--timeframe", timeframe,
        "--user-data-dir", str(ud),
        "--config", str(ud / "config.json"),
        "--export", "trades",
        "--export-filename", str(ud / "backtest_results" / strategy / "latest.json"),
    ]
    if timerange:
        args += ["--timerange", timerange]
    result = subprocess.run(args, capture_output=True, text=True, cwd=str(_ROOT))
    return result.stdout + result.stderr


@mcp.tool()
def read_backtest_results(strategy: str) -> dict:
    """Read the latest backtest result JSON for a strategy.

    Args:
        strategy: Strategy name (e.g. 'MyStrategy')
    """
    results_dir = _user_data() / "backtest_results" / strategy
    zips = sorted(results_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if zips:
        with zipfile.ZipFile(zips[0]) as zf:
            json_files = [n for n in zf.namelist() if n.endswith(".json")]
            if json_files:
                return json.loads(zf.read(json_files[0]))
    json_file = results_dir / "latest.json"
    if json_file.exists():
        return json.loads(json_file.read_text(encoding="utf8"))
    return {"error": f"No results found for {strategy}"}


@mcp.tool()
def analyze_strategy_path(strategy: str) -> dict:
    """Return file path, size, and first 30 lines of a strategy file.

    Args:
        strategy: Strategy filename without .py (e.g. 'MyStrategy')
    """
    p = _user_data() / "strategies" / f"{strategy}.py"
    if not p.exists():
        return {"error": f"Not found: {p}"}
    lines = p.read_text(encoding="utf8").splitlines()
    return {
        "path": str(p),
        "size_bytes": p.stat().st_size,
        "preview": "\n".join(lines[:30]),
    }


@mcp.tool()
def read_config() -> dict:
    """Read user_data/config.json."""
    cfg = _user_data() / "config.json"
    if cfg.exists():
        return json.loads(cfg.read_text(encoding="utf8"))
    return {"error": "config.json not found"}


@mcp.tool()
def export_results_summary(strategy: str) -> str:
    """Return a plain-text summary of the latest backtest results for a strategy.

    Args:
        strategy: Strategy name (e.g. 'MyStrategy')
    """
    data = read_backtest_results(strategy)
    if "error" in data:
        return data["error"]
    try:
        strat_data = list(data.get("strategy", {}).values())[0]
        sd = strat_data.get("results_per_pair", [{}])[0] if strat_data.get("results_per_pair") else {}
        lines = [
            f"Strategy : {strategy}",
            f"Trades   : {strat_data.get('total_trades', 'N/A')}",
            f"Win rate : {strat_data.get('wins', 'N/A')} / {strat_data.get('total_trades', 'N/A')}",
            f"Profit % : {strat_data.get('profit_total_abs', 'N/A')}",
            f"Drawdown : {strat_data.get('max_drawdown', 'N/A')}",
            f"Sharpe   : {strat_data.get('sharpe', 'N/A')}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Could not parse results: {e}"


if __name__ == "__main__":
    mcp.run()
