# Tasks: Strategy Optimizer

## Task List

- [x] 1. Data Models (`app/core/models/optimizer_models.py`)
  - [x] 1.1 Create `app/core/models/optimizer_models.py` with `SessionStatus`, `TrialStatus`, `ParamType` enums and `ParamDef`, `StrategyParams`, `TrialMetrics`, `TrialRecord`, `BestPointer`, `SessionConfig`, `OptimizerSession`, `OptimizerPreferences` Pydantic v2 models
  - [x] 1.2 Add `OptimizerPreferences` field to `AppSettings` in `app/core/models/settings_models.py` following the same pattern as `backtest_preferences`
  - [x] 1.3 Verify no PySide6 imports in the new models file (architecture boundary)

- [x] 2. Strategy `.py` Parser (`app/core/parsing/strategy_py_parser.py`)
  - [x] 2.1 Create `app/core/parsing/strategy_py_parser.py` with `_ParamVisitor(ast.NodeVisitor)` that extracts `IntParameter`, `DecimalParameter`, `CategoricalParameter`, `BooleanParameter` declarations using `ast.NodeVisitor` — no regex
  - [x] 2.2 Implement `parse_strategy_py(path: Path) -> StrategyParams` that reads the `.py` file, runs the AST visitor, and returns a `StrategyParams` object; returns empty `buy_params`/`sell_params` dicts (never raises) when no parameters are found
  - [x] 2.3 Implement `_eval_constant()` helper to safely evaluate `ast.Constant`, `ast.UnaryOp` (negative numbers), and `ast.List`/`ast.Tuple` nodes without `eval()`
  - [x] 2.4 Document V1 scope limitation in the parser module docstring: only parameters declared directly in the strategy class body are extracted; inherited parameters from base classes are not traversed. The UI must surface this as a tooltip on the parameter table.
  - [x] 2.5 Write unit tests in `tests/core/test_strategy_py_parser.py` covering: parameter extraction, missing params (empty result), parse error handling, all four parameter types, and a strategy that inherits from a base class (verify empty result, no exception)

- [x] 3. Optimizer Score Function
  - [x] 3.1 Implement `compute_optimizer_score(metrics: dict, score_metric: str) -> float` as a pure function in `app/core/services/optimizer_session_service.py`; handles `None`, `NaN`, `+Inf`, `-Inf`, missing keys, and unknown metric names — always returns a finite `float`
  - [x] 3.2 Write unit tests in `tests/core/test_optimizer_score.py` for all five named metrics, missing key, unknown metric, and zero-trades case
  - [x] 3.3 Write Hypothesis property test in `tests/property/test_optimizer_properties.py`: `test_score_always_finite` — for all metric names and all value types (None, NaN, Inf, int, str), score is always a finite float

- [x] 4. Session Store (`app/core/services/optimizer_store.py`)
  - [x] 4.1 Create `app/core/services/optimizer_store.py` with `OptimizerStore` class; implement `sessions_root()`, `session_dir()`, `trial_dir()` path helpers that resolve `{user_data}/optimizer/sessions/`
  - [x] 4.2 Implement `save_session()` / `load_session()` / `list_sessions()` / `delete_session()` using `write_json_file_atomic` from `app/core/parsing/json_parser.py`
  - [x] 4.3 Implement `save_trial_record()` / `load_trial_record()` / `load_all_trial_records()` — each trial's artefacts written to `trial_{n:03d}/` subdirectory
  - [x] 4.4 Implement `save_best_pointer()` / `load_best_pointer()` for `best.json`
  - [x] 4.5 Write unit tests in `tests/core/test_optimizer_session_service.py` for store operations using `tmp_path`

- [x] 5. Strategy Parameter Round-Trip Property Test
  - [x] 5.1 Write Hypothesis property test `test_strategy_params_round_trip` in `tests/property/test_optimizer_properties.py`: for all valid `StrategyParams` objects, `StrategyParams.from_dict(params.to_dict()) == params`

- [x] 6. Session Service (`app/core/services/optimizer_session_service.py`)
  - [x] 6.1 Implement `StrategyOptimizerService.__init__()` with constructor injection of `SettingsService`, `BacktestService`, optional `ProcessService`, optional `RollbackService`; instantiate `OptimizerStore` internally; add `_active_subprocess: Optional[subprocess.Popen] = None` instance variable
  - [x] 6.2 Implement `create_session(config: SessionConfig) -> OptimizerSession` — generates UUID4 session_id, creates session directory, initialises Optuna study with SQLite RDB storage at `study.db` with WAL mode enabled via SQLAlchemy `connect` event (`PRAGMA journal_mode=WAL`) and `check_same_thread=False`
  - [x] 6.3 Implement `_sample_params(optuna_trial, param_defs) -> dict` — maps enabled `ParamDef` entries to Optuna `suggest_int` / `suggest_float` / `suggest_categorical` calls; holds disabled params at their default value
  - [x] 6.4 Implement `_execute_trial()` — creates `Trial_Strategy_Dir`, **copies** (never symlinks) the strategy `.py` file into it for cross-platform compatibility, writes `{StrategyClass}.json` with `Candidate_Params`, builds backtest command via `BacktestService.build_command()` with `--strategy-path` extra flag, runs via `ProcessService`, stores the `Popen` handle in `self._active_subprocess`, captures stdout/stderr
  - [x] 6.5 Implement `_parse_trial_result()` — finds newest backtest result zip in export dir, calls `parse_backtest_results_from_zip`, maps `BacktestSummary` fields to `TrialMetrics`, sanitizes all numeric fields to finite floats
  - [x] 6.6 Implement `_maybe_update_best()` — compares trial score against current `BestPointer`; updates `best.json` via store if strictly higher
  - [x] 6.7 Implement `run_session_async(session, callbacks)` — runs the trial loop on a background thread; accepts `on_trial_start`, `on_trial_complete`, `on_session_complete`, `on_log_line` callbacks
  - [x] 6.8 Implement `stop_session()` — sets `_stop_requested = True`; retrieves `self._active_subprocess` and sends SIGTERM, waits up to 10 seconds, then sends SIGKILL if the process has not exited; prevents orphaned Freqtrade processes
  - [x] 6.9 Implement `export_best(session_id) -> ExportResult` — delegates backup to `RollbackService._backup_file()`, writes params atomically via `write_json_file_atomic` (temp file created in `live_json.parent` to guarantee same-filesystem atomic rename), prunes old backups via `RollbackService._prune_backups()`
  - [x] 6.10 Implement `set_best(session_id, trial_number)` — manual override of `Accepted_Best`; updates `best.json`
  - [x] 6.11 Verify no PySide6 imports in the service module (architecture boundary)

- [x] 7. TrialTableModel (`app/ui/widgets/trial_table_model.py`)
  - [x] 7.1 Create `app/ui/widgets/trial_table_model.py` with `TrialTableModel(QAbstractTableModel)` — columns: `#`, `Params`, `Profit %`, `DD %`, `Score`, `★`
  - [x] 7.2 Implement `append_trial(record: TrialRecord)` using `beginInsertRows` / `endInsertRows` — no full model reset
  - [x] 7.3 Implement `update_best(old_best_trial_number, new_best_trial_number)` — emits `dataChanged` only for the two affected rows' `★` column
  - [x] 7.4 Implement `sort()` override to support sorting by any numeric column without reloading from disk
  - [x] 7.5 Implement `data()` for `Qt.DisplayRole`, `Qt.BackgroundRole` (semantic row colors: green for best, red for failed, blue for running), and `Qt.UserRole` (returns full `TrialRecord` for detail panel)

- [x] 8. Export Confirmation Dialog (`app/ui/dialogs/export_confirm_dialog.py`)
  - [x] 8.1 Create `ExportConfirmDialog(QDialog)` that displays: target JSON file path, current parameter values (read from live JSON), new parameter values from `Accepted_Best`, and a diff-style view of changed keys
  - [x] 8.2 Add optional "Patch .py file" checkbox that triggers a second confirmation dialog before proceeding

- [ ] 9. Optimizer Page (`app/ui/pages/optimizer_page.py`)
  - [ ] 9.1 Create `OptimizerPage(QWidget)` with constructor `(settings_state: SettingsState, process_manager: ProcessRunManager)`; instantiate `StrategyOptimizerService` with injected `SettingsService` and `BacktestService`
  - [ ] 9.2 Build three-pane `QSplitter` layout: left sidebar (config + param table + action buttons), center (progress bar + live log top half, trial table bottom half), right sidebar (best result metrics + selected trial metrics + per-trial actions)
  - [ ] 9.3 Build left sidebar config panel: strategy dropdown (populated via `BacktestService.get_available_strategies()`), read-only inherited fields (timeframe, timerange, pairs, wallet, max trades), trials spinbox (1–1000, default 50), score metric dropdown, "Sync from Backtest" button; add tooltip on param table noting V1 limitation (inherited parameters not detected)
  - [ ] 9.4 Build parameter table in left sidebar: editable `QTableView` backed by a `QStandardItemModel` with columns (enabled checkbox, name, type, default, min, max); inline validation on min/max edits
  - [ ] 9.5 Build center pane: progress bar + elapsed/ETA labels at top; `QPlainTextEdit` (read-only, auto-scroll) for live log in upper half; `QTableView` backed by `TrialTableModel` in lower half; `QSplitter` between log and table
  - [ ] 9.6 Build right sidebar: "★ Best Result" section with metric labels; "Selected Trial" section with metric labels; per-trial action buttons ("Set as Best", "Open Log", "Open Result File", "Compare")
  - [ ] 9.7 Wire "Start Optimizer" button: validate config, call `service.create_session()`, start background thread via `run_session_async()`, disable button during run
  - [ ] 9.8 Wire "Stop" button: call `service.stop_session()` (which sends SIGTERM/SIGKILL to active subprocess); re-enable "Start Optimizer" when session finishes
  - [ ] 9.9 Implement batched UI update pattern: `_pending_log_lines` and `_pending_trials` lists flushed every 500 ms via `QTimer`; bridge signal handlers append to pending lists rather than updating UI directly
  - [ ] 9.10 Wire bridge signals (`_sig_log_line`, `_sig_trial_done`, `_sig_session_done`, `_sig_trial_start`) to append to pending lists; `_flush_pending_updates()` drains lists and updates log view + `TrialTableModel` + progress bar + right sidebar
  - [ ] 9.11 Wire trial list row click to populate the "Selected Trial" section in the right sidebar
  - [ ] 9.12 Wire "Set as Best" button to call `service.set_best()`
  - [ ] 9.13 Wire "Export Best" button to open `ExportConfirmDialog`; on confirm call `service.export_best()` and display result/backup path
  - [ ] 9.14 Wire "Rollback" button to open `RollbackDialog` (reuse existing `app/ui/dialogs/rollback_dialog.py`) with backup files for the current strategy
  - [ ] 9.15 Wire "Compare" action to display a side-by-side metric diff for two selected trials
  - [ ] 9.16 Wire "Open Log" and "Open Result File" actions to open files via `QDesktopServices.openUrl()`
  - [ ] 9.17 Implement `_load_history()` — calls `store.list_sessions()` and populates a session history panel (collapsible section at the bottom of the left sidebar or a separate dialog); session rows show strategy name, start time, trial count, best score, status
  - [ ] 9.18 Implement session deletion from history panel with confirmation prompt
  - [ ] 9.19 Display warning banner when `BacktestPreferences` has no strategy configured (Requirement 1.3)

- [ ] 10. Sidebar and Main Window Integration
  - [ ] 10.1 Add `("optimizer", "⚡", "Optimizer")` to `_NAV_ITEMS` in `app/ui/shell/sidebar.py`
  - [ ] 10.2 Import `OptimizerPage` and add it to `self._pages` dict in `app/ui/main_window.py`; wire `Ctrl+N` shortcut (next available after existing pages)

- [ ] 11. Architecture Boundary Verification
  - [ ] 11.1 Run `python tests/test_architecture.py` and confirm zero violations after all new files are created
  - [ ] 11.2 Confirm `app/core/services/optimizer_session_service.py` has no PySide6 imports
  - [ ] 11.3 Confirm `app/core/models/optimizer_models.py` has no PySide6 imports
  - [ ] 11.4 Confirm `app/core/parsing/strategy_py_parser.py` has no PySide6 imports
  - [ ] 11.5 Confirm `app/core/services/optimizer_store.py` has no PySide6 imports

- [ ] 12. Integration and Smoke Tests
  - [ ] 12.1 Write `tests/core/test_optimizer_session_service.py` integration test: create a session, run one mock trial (mock `ProcessService` to return exit code 0 with a fake result), verify `TrialRecord` is persisted and `best.json` is written
  - [ ] 12.2 Write `tests/core/test_optimizer_session_service.py` test: failed trial (exit code 1) does not stop the session and is recorded with `TrialStatus.FAILED`
  - [ ] 12.3 Write `tests/core/test_optimizer_session_service.py` test: `stop_session()` sends SIGTERM to the active subprocess mock, halts the loop after the current trial, and sets session status to `stopped`
  - [ ] 12.4 Write `tests/core/test_optimizer_session_service.py` test: `export_best()` writes the live JSON atomically (temp file created in same directory as target) and creates a backup file
  - [ ] 12.5 Write `tests/core/test_optimizer_session_service.py` test: `set_best()` updates `best.json` to the manually selected trial number
  - [ ] 12.6 Write `tests/core/test_optimizer_session_service.py` test: Optuna study is created with WAL mode — connect to `study.db` after `create_session()` and verify `PRAGMA journal_mode` returns `wal`
