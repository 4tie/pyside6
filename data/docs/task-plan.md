# Project Plan: Clean up the codebase: remove all backward-compat shims and dead files, update all remaining imports to point directly to the new module locations, leaving no extra files.

## Tasks Overview
- [ ] Fix backtest_results_widget.py imports
- [ ] Fix terminal_widget.py imports
- [ ] Fix download_data_page.py imports
- [ ] Fix main_window.py: rename dd_page and add strategy_config_page
- [ ] Delete all shim and dead files
- [ ] Verify: import check + CI checks

## Detailed Tasks

### 1. Fix backtest_results_widget.py imports
**Description:** File imports from both shims:
- `from app.core.services.backtest_results_service import BacktestResults` → `from app.core.backtests.results_models import BacktestResults`
- `from app.core.services.run_store import RunStore` → `from app.core.backtests.results_store import RunStore`

### 2. Fix terminal_widget.py imports
**Description:** File imports from the dead file:
- `from app.core.freqtrade.command_runner import CommandRunner` → `from app.core.freqtrade.runners.base_runner import build_command` (and update the one call site that uses CommandRunner inside the widget)

### 3. Fix download_data_page.py imports
**Description:** File uses `BacktestService.build_download_command()` which no longer exists on BacktestService. Replace:
- `from app.core.services.backtest_service import BacktestService` → `from app.core.services.download_data_service import DownloadDataService`
- Replace `self.backtest_service = BacktestService(...)` with `self.download_service = DownloadDataService(...)`
- Replace all `self.backtest_service.build_download_command(...)` calls with `self.download_service.build_command(...)`

### 4. Fix main_window.py: rename dd_page and add strategy_config_page
**Description:** Two issues:
1. `self.dd_page = DownloadDataPage(...)` → rename to `self.download_data_page` and fix `_all_terminals` reference from `self.dd_page.terminal` to `self.download_data_page.terminal`
2. `main_window.py` already imports `StrategyConfigPage` — verify it is wired up correctly in tabs

### 5. Delete all shim and dead files
**Description:** Delete these 5 files — no remaining references after tasks 1–4:
- `app/core/services/backtest_results_service.py` (shim)
- `app/core/services/run_store.py` (shim)
- `app/core/services/dd_service.py` (shim)
- `app/core/freqtrade/command_runner.py` (replaced by runners/)
- `app/ui/pages/dd_page.py` (replaced by download_data_page.py)

### 6. Verify: import check + CI checks
**Description:** Run:
1. `.venv\Scripts\python.exe -c "import app.ui.main_window; import app.ui.pages.backtest_page; import app.ui.pages.download_data_page; import app.ui.widgets.backtest_results_widget; import app.ui.widgets.terminal_widget; print('OK')"`
2. `python data/tools/run_checks.py`

Both must pass with zero errors.

## Progress Tracking

| Task | Status | Completion Date |
|------|--------|----------------|
| Fix backtest_results_widget.py imports | 🔄 In Progress |  |
| Fix terminal_widget.py imports | 🔄 In Progress |  |
| Fix download_data_page.py imports | 🔄 In Progress |  |
| Fix main_window.py: rename dd_page and add strategy_config_page | 🔄 In Progress |  |
| Delete all shim and dead files | 🔄 In Progress |  |
| Verify: import check + CI checks | 🔄 In Progress |  |
