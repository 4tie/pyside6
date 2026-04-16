"""
Full validation: paths, config resolution, command building, export paths.
"""
import sys, json
sys.path.insert(0, "T:/ae/pyside6")

from pathlib import Path
from app.core.utils.app_logger import setup_logging, get_logger
setup_logging(r"T:\ae\pyside6\user_data")
log = get_logger("validate")

from app.core.models.settings_models import AppSettings
from app.core.freqtrade.command_runner import CommandRunner
from app.core.services.settings_service import SettingsService
from app.core.services.backtest_service import BacktestService
from app.core.services.dd_service import DownloadDataService

ok = True
errors = []

def check(name, condition, detail=""):
    global ok
    if not condition:
        ok = False
        msg = f"  FAIL  {name}" + (f" — {detail}" if detail else "")
        errors.append(msg)
        print(msg)
    else:
        print(f"  OK    {name}")

# ── Load real settings ────────────────────────────────────────────────────
svc = SettingsService()
settings = svc.load_settings()

print("\n=== Settings ===")
check("python_executable set",      bool(settings.python_executable))
check("python_executable exists",   Path(settings.python_executable).exists() if settings.python_executable else False,
      settings.python_executable)
check("user_data_path set",         bool(settings.user_data_path))
check("user_data_path exists",      Path(settings.user_data_path).exists() if settings.user_data_path else False,
      settings.user_data_path)
check("venv_path set",              bool(settings.venv_path))
check("venv_path exists",           Path(settings.venv_path).exists() if settings.venv_path else False,
      settings.venv_path)

user_data = Path(settings.user_data_path).expanduser().resolve() if settings.user_data_path else None

# ── user_data subdirs ─────────────────────────────────────────────────────
print("\n=== user_data structure ===")
if user_data:
    for sub in ["strategies", "backtest_results", "data", "logs", "config"]:
        p = user_data / sub
        check(f"user_data/{sub}/ exists", p.exists(), str(p))

# ── Strategies ────────────────────────────────────────────────────────────
print("\n=== Strategies ===")
if user_data:
    strategies_dir = user_data / "strategies"
    py_files = sorted(strategies_dir.glob("*.py")) if strategies_dir.exists() else []
    check("at least one strategy .py", len(py_files) > 0)
    for py in py_files:
        print(f"  strategy: {py.stem}")

# ── Config resolution per strategy ───────────────────────────────────────
print("\n=== Config resolution ===")
if user_data and py_files:
    strategies_dir = user_data / "strategies"
    for py in py_files:
        name = py.stem
        sidecar   = strategies_dir / f"{name}.json"
        proj_cfg  = Path(settings.project_path) / "config.json" if settings.project_path else None
        root_cfg  = user_data / "config.json"

        if sidecar.exists():
            resolved = sidecar
            source = "sidecar"
        elif proj_cfg and proj_cfg.exists():
            resolved = proj_cfg
            source = "project"
        elif root_cfg.exists():
            resolved = root_cfg
            source = "user_data root"
        else:
            resolved = None
            source = "NONE"

        check(f"{name}: config resolved ({source})", resolved is not None, str(resolved))

# ── Backtest command building ─────────────────────────────────────────────
print("\n=== Backtest command building ===")
bt_svc = BacktestService(svc)
strategies = bt_svc.get_available_strategies()
check("get_available_strategies returns list", isinstance(strategies, list))
check("strategies not empty", len(strategies) > 0)

test_strategy = "MultiMeee" if "MultiMeee" in strategies else (strategies[0] if strategies else None)
if test_strategy:
    try:
        cmd = bt_svc.build_command(
            strategy_name=test_strategy,
            timeframe="5m",
            pairs=["ADA/USDT", "ETH/USDT"],
            max_open_trades=2,
            dry_run_wallet=80.0,
        )
        check("program is python_executable",   cmd.program == settings.python_executable)
        check("program file exists",            Path(cmd.program).exists())
        check("strategy_file ends with .py",    cmd.strategy_file.endswith(".py"))
        check("strategy_file exists",           Path(cmd.strategy_file).exists(), cmd.strategy_file)
        check("export_dir is under backtest_results", "backtest_results" in cmd.export_dir)
        check("export_zip contains strategy name",    test_strategy in cmd.export_zip)
        check("export_zip ends with .backtest.zip",   cmd.export_zip.endswith(".backtest.zip"))
        check("cwd exists",                     Path(cmd.cwd).exists(), cmd.cwd)
        check("--user-data-dir in args",        "--user-data-dir" in cmd.args)
        check("--strategy-path in args",        "--strategy-path" in cmd.args)
        check("--strategy in args",             "--strategy" in cmd.args)
        check("--timeframe in args",            "--timeframe" in cmd.args)
        check("--export trades in args",        "trades" in cmd.args)
        check("--export-filename in args",      "--export-filename" in cmd.args)
        check("-p pairs in args",               "-p" in cmd.args)
        check("--max-open-trades in args",      "--max-open-trades" in cmd.args)
        check("--dry-run-wallet in args",       "--dry-run-wallet" in cmd.args)
        check("no -m freqtrade duplicate",
              cmd.args.count("freqtrade") == 1,
              f"freqtrade appears {cmd.args.count('freqtrade')} times")

        # Validate all path args point to existing locations
        for flag in ["--user-data-dir", "--strategy-path"]:
            idx = cmd.args.index(flag)
            path_val = cmd.args[idx + 1]
            check(f"{flag} path exists", Path(path_val).exists(), path_val)

        print(f"\n  Full command preview:")
        print(f"  {cmd.program} {' '.join(cmd.args[:8])} ...")

    except Exception as e:
        check(f"build_command({test_strategy}) no exception", False, str(e))

# ── Download command building ─────────────────────────────────────────────
print("\n=== Download command building ===")
dd_svc = DownloadDataService(svc)
try:
    dd_cmd = dd_svc.build_command(
        timeframe="5m",
        pairs=["ADA/USDT", "ETH/USDT"],
    )
    check("dd program is python_executable",  dd_cmd.program == settings.python_executable)
    check("dd program exists",                Path(dd_cmd.program).exists())
    check("dd cwd exists",                    Path(dd_cmd.cwd).exists(), dd_cmd.cwd)
    check("download-data in args",            "download-data" in dd_cmd.args)
    check("--user-data-dir in dd args",       "--user-data-dir" in dd_cmd.args)
    check("--timeframe in dd args",           "--timeframe" in dd_cmd.args)
    check("--prepend in dd args",             "--prepend" in dd_cmd.args)
    check("-p in dd args",                    "-p" in dd_cmd.args)
    check("no -m freqtrade duplicate in dd",
          dd_cmd.args.count("freqtrade") == 1,
          f"freqtrade appears {dd_cmd.args.count('freqtrade')} times")
except Exception as e:
    check("build_download_command no exception", False, str(e))

# ── Dead code check in command_runner ────────────────────────────────────
print("\n=== command_runner.py dead code check ===")
cr_src = Path("T:/ae/pyside6/app/core/freqtrade/command_runner.py").read_text(encoding="utf-8")
check("no orphaned version-check return after build_download_command",
      "Build command to check freqtrade version" not in cr_src or
      cr_src.index("Build command to check freqtrade version") >
      cr_src.index("def build_backtest_command"),
      "Dead code block found after build_download_command")

# ── Export dir creation ───────────────────────────────────────────────────
print("\n=== Export directory ===")
if user_data and test_strategy:
    export_dir = user_data / "backtest_results" / test_strategy
    check("strategy export_dir exists (created by build_command)", export_dir.exists(), str(export_dir))

# ── index.json ───────────────────────────────────────────────────────────
print("\n=== index.json ===")
if user_data:
    idx_path = user_data / "backtest_results" / "index.json"
    check("root index.json exists", idx_path.exists(), str(idx_path))
    if idx_path.exists():
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
        check("index has strategies key", "strategies" in idx)
        check("index has updated_at",     "updated_at" in idx)
        for strat, block in idx.get("strategies", {}).items():
            runs = block.get("runs", [])
            check(f"index[{strat}] has runs", len(runs) > 0)
            check(f"index[{strat}] runs have run_id", all("run_id" in r for r in runs))
            check(f"index[{strat}] runs have run_dir", all("run_dir" in r for r in runs))

# ── Per-strategy index.json ───────────────────────────────────────────────
print("\n=== Per-strategy index.json ===")
if user_data:
    br = user_data / "backtest_results"
    for strat_dir in sorted(br.iterdir()):
        if not strat_dir.is_dir():
            continue
        run_dirs = [d for d in strat_dir.iterdir() if d.is_dir() and d.name.startswith("run_")]
        if not run_dirs:
            continue
        sidx = strat_dir / "index.json"
        check(f"{strat_dir.name}/index.json exists", sidx.exists(), str(sidx))
        if sidx.exists():
            data = json.loads(sidx.read_text(encoding="utf-8"))
            check(f"{strat_dir.name}/index.json has runs", len(data.get("runs", [])) > 0)

# ── Log file ─────────────────────────────────────────────────────────────
print("\n=== Log file ===")
if user_data:
    log_file = user_data / "logs" / "app.log"
    check("app.log exists", log_file.exists(), str(log_file))
    if log_file.exists():
        size_kb = log_file.stat().st_size / 1024
        check("app.log has content", size_kb > 0, f"{size_kb:.1f} KB")

# ── Final ─────────────────────────────────────────────────────────────────
print()
if ok:
    print("All checks passed.")
else:
    print(f"VALIDATION FAILED — {len(errors)} issue(s):")
    for e in errors:
        print(e)
    sys.exit(1)
