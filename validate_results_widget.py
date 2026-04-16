"""
Headless validation: BacktestResultsWidget renders correctly with real data.
Checks every UI element without showing a window.
"""
import sys
sys.path.insert(0, "T:/ae/pyside6")

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from app.core.services.backtest_results_service import BacktestResultsService
from app.ui.widgets.backtest_results_widget import BacktestResultsWidget

ZIP = r"T:\ae\pyside6\user_data\backtest_results\backtest-result-2026-04-16_02-52-06.zip"
RUN_DIR = r"T:\ae\pyside6\user_data\backtest_results\MultiMeee\run_2026-04-16_04-20-04_969ea9"

results = BacktestResultsService.parse_backtest_zip(ZIP)
widget = BacktestResultsWidget()
widget.display_results(results, export_dir=RUN_DIR)

ok = True
errors = []

def check(name, condition):
    global ok
    if not condition:
        ok = False
        errors.append(f"  FAIL  {name}")
    else:
        print(f"  OK    {name}")

# ── Toolbar ──────────────────────────────────────────────────────────────
check("export_btn enabled after display_results",
      widget._export_btn.isEnabled())
check("export_path_label shows run dir",
      RUN_DIR in widget._export_path_label.text())

# ── Summary tab ──────────────────────────────────────────────────────────
header = widget._summary_header.text()
check("summary header contains strategy name",
      "MultiMeee" in header)
check("summary header contains timeframe",
      "5m" in header)
check("summary header contains backtest dates",
      "2025-04-21" in header and "2026-04-11" in header)

perf_count = widget._perf_grid.rowCount()
trade_count = widget._trade_grid.rowCount()
check("performance grid has rows",  perf_count > 0)
check("trade stats grid has rows",  trade_count > 0)

# Collect all label texts from both grids
def grid_texts(grid):
    texts = []
    for i in range(grid.count()):
        item = grid.itemAt(i)
        if item and item.widget():
            texts.append(item.widget().text())
    return texts

perf_texts  = grid_texts(widget._perf_grid)
trade_texts = grid_texts(widget._trade_grid)

check("Starting Balance shown",   any("Starting Balance" in t for t in perf_texts))
check("Final Balance shown",      any("Final Balance" in t for t in perf_texts))
check("Total Profit % shown",     any("Total Profit %" in t for t in perf_texts))
check("Total Profit Abs shown",   any("Total Profit Abs" in t for t in perf_texts))
check("Max Drawdown shown",       any("Max Drawdown" in t for t in perf_texts))
check("Sharpe shown",             any("Sharpe" in t for t in perf_texts))
check("Sortino shown",            any("Sortino" in t for t in perf_texts))
check("Profit Factor shown",      any("Profit Factor" in t for t in perf_texts))
check("Expectancy shown",         any("Expectancy" in t for t in perf_texts))

check("Total Trades shown",       any("Total Trades" in t for t in trade_texts))
check("Wins shown",               any("Wins" in t for t in trade_texts))
check("Losses shown",             any("Losses" in t for t in trade_texts))
check("Win Rate shown",           any("Win Rate" in t for t in trade_texts))
check("Avg Duration shown",       any("Avg Duration" in t for t in trade_texts))
check("Pairs shown",              any("Pairs" in t for t in trade_texts))
check("Timerange shown",          any("Timerange" in t for t in trade_texts))

# Spot-check actual values
s = results.summary
check("Starting balance value correct",
      any(f"{s.starting_balance:.3f}" in t for t in perf_texts))
check("Final balance value correct",
      any(f"{s.final_balance:.3f}" in t for t in perf_texts))
check("Total trades value correct",
      any(str(s.total_trades) in t for t in trade_texts))
check("Wins value correct",
      any(str(s.wins) in t for t in trade_texts))
check("Losses value correct",
      any(str(s.losses) in t for t in trade_texts))

# ── Trades tab ───────────────────────────────────────────────────────────
table = widget.trades_table
check("trades label shows count",
      str(len(results.trades)) in widget._trades_label.text())
check("trades table row count matches",
      table.rowCount() == len(results.trades))
check("trades table has 9 columns",
      table.columnCount() == 9)

# Check first row has data
check("row 0 pair not empty",       bool(table.item(0, 0) and table.item(0, 0).text()))
check("row 0 open date not empty",  bool(table.item(0, 1) and table.item(0, 1).text()))
check("row 0 close date not empty", bool(table.item(0, 2) and table.item(0, 2).text()))
check("row 0 profit % not empty",   bool(table.item(0, 5) and table.item(0, 5).text()))
check("row 0 exit reason not empty",bool(table.item(0, 8) and table.item(0, 8).text()))

# Check profit coloring on a known losing trade
for row in range(table.rowCount()):
    profit_item = table.item(row, 5)
    if profit_item and profit_item.text().startswith("-"):
        fg = profit_item.foreground().color().name()
        check(f"row {row} negative profit is red", fg == "#cf222e")
        break

for row in range(table.rowCount()):
    profit_item = table.item(row, 5)
    if profit_item and profit_item.text().startswith("+"):
        fg = profit_item.foreground().color().name()
        check(f"row {row} positive profit is green", fg == "#1a7f37")
        break

# ── Tabs ─────────────────────────────────────────────────────────────────
check("tabs count is 2 (Summary + Trades)",
      widget.tabs.count() == 2)
check("tab 0 label is Summary",
      widget.tabs.tabText(0) == "Summary")
check("tab 1 label is Trades",
      widget.tabs.tabText(1) == "Trades")

# ── Final ─────────────────────────────────────────────────────────────────
print()
if ok:
    print("All checks passed.")
else:
    print("VALIDATION FAILED:")
    for e in errors:
        print(e)
    sys.exit(1)
