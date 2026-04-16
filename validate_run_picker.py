import sys
sys.path.insert(0, "T:/ae/pyside6")

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from unittest.mock import MagicMock
from app.ui.pages.backtest_page import BacktestPage
from app.core.services.run_store import IndexStore
from pathlib import Path

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

# Run picker exists
check("run_combo exists",       hasattr(page, "run_combo"))
check("load_run_btn exists",    hasattr(page, "load_run_btn"))

# Index has runs for MultiMeee
backtest_results_dir = r"T:\ae\pyside6\user_data\backtest_results"
runs = IndexStore.get_strategy_runs(backtest_results_dir, "MultiMeee")
check("index has MultiMeee runs", len(runs) > 0)

# Run combo is populated
page.strategy_combo.setCurrentText("MultiMeee")
page._refresh_run_picker()
check("run_combo populated with runs", page.run_combo.count() > 0)
check("first item is not placeholder",
      "No saved runs" not in page.run_combo.itemText(0))
check("first item has run_id in label",
      "run_" in page.run_combo.itemText(0))
check("first item userData is dict",
      isinstance(page.run_combo.itemData(0), dict))
check("first item userData has run_id key",
      "run_id" in (page.run_combo.itemData(0) or {}))

# Load the first run
page.run_combo.setCurrentIndex(0)
page._on_load_run()
check("results_widget populated after load",
      page.results_widget.results is not None)
check("output_tabs switched to Results (index 1)",
      page.output_tabs.currentIndex() == 1)
check("summary header shows MultiMeee",
      "MultiMeee" in page.results_widget._summary_header.text())
check("trades table has rows",
      page.results_widget.trades_table.rowCount() > 0)

print()
if ok:
    print("All checks passed.")
else:
    print("VALIDATION FAILED:")
    for e in errors:
        print(e)
    sys.exit(1)
