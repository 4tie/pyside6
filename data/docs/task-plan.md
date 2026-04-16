# Project Plan: Clean up the codebase: remove all backward-compat shims and dead files, update all remaining imports to point directly to the new module locations, leaving no extra files.

## Tasks Overview
- [ ] Fix widgets: update imports in backtest_summary_widget.py and backtest_trades_widget.py
- [ ] Fix download_data_page.py: switch from BacktestService.build_download_command to DownloadDataService
- [ ] Fix main_window.py: rename dd_page attribute and fix terminal reference
- [ ] Delete all shim files and dead files
- [ ] Verify: run import check and CI checks

## Detailed Tasks

### 1. Fix widgets: update imports in backtest_summary_widget.py and backtest_trades_widget.py
**Description:** Both widgets import from the old shim `app.core.services.backtest_results_service`. Update them to import `BacktestSummary` and `BacktestTrade` directly from `app.core.backtests.results_models`.

### 2. Fix download_data_page.py: switch from BacktestService.build_download_command to DownloadDataService
**Description:** download_data_page.py uses `BacktestService.build_download_command()` which no longer exists on BacktestService. Replace with `DownloadDataService` from `app.core.services.download_data_service`.

### 3. Fix main_window.py: rename dd_page attribute and fix terminal reference
**Description:** main_window.py imports `DownloadDataPage` (correct) but stores it as `self.dd_page` and references `self.dd_page.terminal` in `_all_terminals`. Rename attribute to `self.download_data_page` for consistency.

### 4. Delete all shim files and dead files
**Description:** Delete the following files that are now pure shims or fully replaced:
- app/core/services/backtest_results_service.py (shim)
- app/core/services/run_store.py (shim)
- app/core/services/dd_service.py (shim)
- app/core/freqtrade/command_runner.py (replaced by runners/)
- app/ui/pages/dd_page.py (replaced by download_data_page.py)

### 5. Verify: run import check and CI checks
**Description:** Run `python -c 'import app'` with the venv Python to confirm no broken imports, then run `python data/tools/run_checks.py` to confirm all CI checks pass.

## Progress Tracking

| Task | Status | Completion Date |
|------|--------|----------------|
| Fix widgets: update imports in backtest_summary_widget.py and backtest_trades_widget.py | 🔄 In Progress |  |
| Fix download_data_page.py: switch from BacktestService.build_download_command to DownloadDataService | 🔄 In Progress |  |
| Fix main_window.py: rename dd_page attribute and fix terminal reference | 🔄 In Progress |  |
| Delete all shim files and dead files | 🔄 In Progress |  |
| Verify: run import check and CI checks | 🔄 In Progress |  |
