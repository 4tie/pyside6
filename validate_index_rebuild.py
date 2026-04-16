import sys, json
sys.path.insert(0, "T:/ae/pyside6")

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from unittest.mock import MagicMock
from pathlib import Path
from app.ui.pages.backtest_page import BacktestPage
from app.core.services.run_store import IndexStore

settings_state = MagicMock()
prefs = MagicMock()
prefs.last_strategy = "MultiMeee"
prefs.default_timeframe = "5m"
prefs.default_timerange = ""
prefs.default_pairs = ""
prefs.paired_favorites = []
prefs.dry_run_wallet = 80.0
prefs.max_open_trades = 2
settings_state.current_settings.backtest_preferences = prefs
settings_state.current_settings.user_data_path = r"T:\ae\pyside6\user_data"
settings_state.settings_changed = MagicMock()
settings_state.settings_changed.connect = MagicMock()
settings_state.settings_saved = MagicMock()
settings_state.settings_saved.connect = MagicMock()

page = BacktestPage(settings_state)

ok = True
errors = []

def check(name, condition):
    global ok
    if not condition:
        ok = False
        errors.append(f"  FAIL  {name}")
    else:
        print(f"  OK    {name}")

backtest_results_dir = r"T:\ae\pyside6\user_data\backtest_results"
index = IndexStore.load(backtest_results_dir)
strategies = list(index.get("strategies", {}).keys())
print(f"\nIndexed strategies: {strategies}")

# All zips should now be indexed
import zipfile
root = Path(backtest_results_dir)
zips = list(root.glob("*.zip"))
print(f"Root zips: {len(zips)}")

check("index has strategies", len(strategies) > 0)
check("MultiMeee indexed", "MultiMeee" in strategies)

# Check each strategy has runs
for strat in strategies:
    runs = IndexStore.get_strategy_runs(backtest_results_dir, strat)
    check(f"{strat} has runs in index", len(runs) > 0)
    print(f"  {strat}: {len(runs)} run(s)")

# Check strategy folders were created
for strat in strategies:
    strat_dir = root / strat
    check(f"{strat}/ folder exists", strat_dir.exists())
    run_dirs = [d for d in strat_dir.iterdir() if d.is_dir() and d.name.startswith("run_")]
    check(f"{strat}/ has run subfolders", len(run_dirs) > 0)

# Check run picker shows runs for MultiMeee
page.strategy_combo.setCurrentText("MultiMeee")
page._refresh_run_picker()
check("run_combo not empty for MultiMeee",
      page.run_combo.count() > 0 and "No saved runs" not in page.run_combo.itemText(0))

# Check run picker for other strategies
for strat in strategies:
    if strat == "MultiMeee":
        continue
    page.strategy_combo.setCurrentText(strat)
    page._refresh_run_picker()
    check(f"run_combo not empty for {strat}",
          page.run_combo.count() > 0 and "No saved runs" not in page.run_combo.itemText(0))

print()
if ok:
    print("All checks passed.")
else:
    print("VALIDATION FAILED:")
    for e in errors:
        print(e)
    sys.exit(1)
