"""
Validate that BacktestPage wires output_tabs correctly and switches to Results tab.
"""
import sys
sys.path.insert(0, "T:/ae/pyside6")

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from unittest.mock import MagicMock
from app.core.services.backtest_results_service import BacktestResultsService
from app.ui.pages.backtest_page import BacktestPage

# Mock SettingsState minimally
settings_state = MagicMock()
settings_state.current_settings = MagicMock()
settings_state.current_settings.backtest_preferences = MagicMock()
settings_state.current_settings.backtest_preferences.last_strategy = ""
settings_state.current_settings.backtest_preferences.default_timeframe = "5m"
settings_state.current_settings.backtest_preferences.default_timerange = ""
settings_state.current_settings.backtest_preferences.default_pairs = ""
settings_state.current_settings.backtest_preferences.paired_favorites = []
settings_state.current_settings.backtest_preferences.dry_run_wallet = 80.0
settings_state.current_settings.backtest_preferences.max_open_trades = 2
settings_state.current_settings.user_data_path = r"T:\ae\pyside6\user_data"
settings_state.settings_changed = MagicMock()
settings_state.settings_changed.connect = MagicMock()

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

# ── Structure checks ──────────────────────────────────────────────────────
check("output_tabs exists as attribute",    hasattr(page, "output_tabs"))
check("output_tabs has 2 tabs",             page.output_tabs.count() == 2)
check("tab 0 is Terminal Output",           page.output_tabs.tabText(0) == "Terminal Output")
check("tab 1 is Results",                   page.output_tabs.tabText(1) == "Results")
check("terminal is tab 0 widget",           page.output_tabs.widget(0) is page.terminal)
check("results_widget is tab 1 widget",     page.output_tabs.widget(1) is page.results_widget)
check("starts on Terminal tab (index 0)",   page.output_tabs.currentIndex() == 0)

# ── Simulate display_results + tab switch ────────────────────────────────
ZIP = r"T:\ae\pyside6\user_data\backtest_results\backtest-result-2026-04-16_02-52-06.zip"
results = BacktestResultsService.parse_backtest_zip(ZIP)

page.results_widget.display_results(results)
page.output_tabs.setCurrentIndex(1)

check("after setCurrentIndex(1), current tab is Results",
      page.output_tabs.currentIndex() == 1)
check("results_widget has data after display_results",
      page.results_widget.results is not None)
check("results_widget trades table populated",
      page.results_widget.trades_table.rowCount() == len(results.trades))
check("results_widget summary header updated",
      "MultiMeee" in page.results_widget._summary_header.text())

# ── Confirm terminal still accessible for preferences ────────────────────
check("page.terminal is a TerminalWidget",
      page.terminal is not None)
check("page.terminal is same object as output_tabs widget 0",
      page.output_tabs.widget(0) is page.terminal)

print()
if ok:
    print("All checks passed.")
else:
    print("VALIDATION FAILED:")
    for e in errors:
        print(e)
    sys.exit(1)
