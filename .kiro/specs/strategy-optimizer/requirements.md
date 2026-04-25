# Requirements Document

## Introduction

The Strategy Optimizer is a new tab in the Freqtrade GUI desktop application that runs repeated real Freqtrade backtests with systematically varied parameter values, records every attempt, tracks the best accepted result, and lets the user safely export or roll back the optimized JSON and `.py` file.

It reuses the same backtest configuration already entered in the Backtesting tab (pairs, timeframe, timerange, wallet, max open trades, config path, strategy name) so the user never has to re-enter settings they have already provided.

The optimizer loop is driven by Optuna (already a project dependency) and operates on a temporary per-trial JSON profile — it never modifies the live strategy file or its JSON directly until the user explicitly confirms an export.

The feature follows the existing project architecture: all core logic lives in `app/core/` with no PySide6 imports, the PySide6 page lives in `app/ui/pages/`, and all data models are Pydantic v2 `BaseModel` subclasses.

---

## Glossary

- **Strategy_Optimizer**: The new PySide6 page (`app/ui/pages/optimizer_page.py`) and its backing service layer (`app/core/services/optimizer_session_service.py`) that orchestrate the parameter search loop.
- **Optimizer_Session**: One complete run of the optimizer loop for a given strategy, from start to stop or completion. Identified by a unique `session_id` (UUID4).
- **Trial**: A single backtest execution within an `Optimizer_Session`, identified by a sequential `trial_number` (1-based). Each trial uses one candidate parameter set.
- **Trial_Record**: The persisted artefact for one `Trial`: candidate parameters, backtest result metrics, raw result file path, log excerpt, and acceptance status.
- **Accepted_Best**: The `Trial_Record` with the highest score that has been promoted as the current best checkpoint. There is at most one `Accepted_Best` per `Optimizer_Session`. Tracked via a lightweight `best.json` pointer file — no file duplication.
- **Candidate_Params**: The full parameter dict (buy params, sell params, stoploss, ROI, trailing settings) written to a temporary JSON file before each trial backtest.
- **Backtest_Config**: The shared configuration snapshot (pairs, timeframe, timerange, wallet, max open trades, config file path) read from `BacktestPreferences` at session start.
- **Trial_Strategy_Dir**: A temporary directory created per trial containing a symlink or copy of the strategy `.py` file and a `{StrategyName}.json` file with the trial's `Candidate_Params`. Passed to Freqtrade via `--strategy-path`.
- **Strategy_Parser**: The component that reads a `.py` strategy file using Python's `ast` module (AST traversal, not regex) and extracts the class name, timeframe, ROI table, stoploss, trailing settings, and buy/sell parameter definitions with their ranges and defaults from `IntParameter`, `DecimalParameter`, `CategoricalParameter`, and `BooleanParameter` declarations. Implemented in `app/core/parsing/strategy_py_parser.py` (distinct from the existing `app/core/parsing/strategy_parser.py` which handles JSON config files).
- **Optimizer_Score**: A finite `float` scalar computed from a trial's backtest metrics used to rank trials and decide acceptance. Higher is better. Always sanitized to a finite value — never `NaN`, `+Inf`, or `-Inf`.
- **Session_Store**: The filesystem layout under `{user_data}/optimizer/sessions/` that persists all session and trial artefacts, including a per-session SQLite file (`study.db`) for Optuna's RDB storage backend. Implemented in `app/core/services/optimizer_store.py`.
- **Export**: The user-confirmed action of writing the `Accepted_Best` parameters to the live strategy JSON file, with a timestamped backup created first via atomic `os.replace`.
- **Rollback**: The user-confirmed action of restoring a previous checkpoint from a backup file, undoing a prior export, using the existing `RollbackService`.
- **Optuna_Ask_Tell**: The decoupled Optuna interface (`study.ask()` / `study.tell()`) used instead of `study.optimize()` to keep the main thread non-blocking during trial execution.
- **ProcessService**: The existing `app.core.services.process_service.ProcessService` used to launch Freqtrade backtest subprocesses with streaming stdout/stderr callbacks.
- **BacktestPreferences**: The `app.core.models.settings_models.BacktestPreferences` Pydantic model that stores the user's last-used backtest settings.
- **RollbackService**: The existing `app.core.services.rollback_service.RollbackService` that provides atomic backup, restore, and pruning logic reused by the export and rollback flows.
- **StrategyParams**: A Pydantic `BaseModel` representing the parsed parameter metadata extracted from a strategy `.py` file, including per-parameter type, default, minimum, maximum, and space.
- **TrialTableModel**: A `QAbstractTableModel` subclass that backs the trial list in the UI, enabling virtual rendering of large trial sets.

---

## Requirements

### Requirement 1: Backtest Configuration Reuse

**User Story:** As a user, I want the Strategy Optimizer to automatically inherit the same pairs, timeframe, timerange, wallet, max open trades, and config file that I already configured in the Backtesting tab, so that I do not have to re-enter settings I have already provided.

#### Acceptance Criteria

1. WHEN the Strategy Optimizer page is opened, THE `Strategy_Optimizer` SHALL read `BacktestPreferences` from `SettingsService` and pre-populate all shared fields (pairs, timeframe, timerange, wallet size, max open trades, config file path) with the stored values.
2. THE `Strategy_Optimizer` SHALL display the inherited configuration values in a read-only summary panel so the user can confirm what settings will be used.
3. WHERE the user has not yet saved any `BacktestPreferences`, THE `Strategy_Optimizer` SHALL display a warning message directing the user to configure the Backtesting tab first.
4. WHEN the user modifies a shared field on the Strategy Optimizer page, THE `Strategy_Optimizer` SHALL persist the updated value back to `BacktestPreferences` via `SettingsService` so the Backtesting tab also reflects the change.
5. THE `Strategy_Optimizer` SHALL expose a "Sync from Backtest" button that re-reads `BacktestPreferences` and refreshes all shared fields without restarting an active session.

### Requirement 2: Strategy Selection and Parsing

**User Story:** As a user, I want to select a strategy `.py` file and have the app automatically detect its parameters, ranges, and defaults, so that I do not have to manually configure what to optimize.

#### Acceptance Criteria

1. THE `Strategy_Optimizer` SHALL list all `.py` files found in `{user_data}/strategies/` in a strategy selector dropdown, using the same discovery logic as `BacktestService.get_available_strategies()`.
2. WHEN a strategy is selected, THE `Strategy_Parser` SHALL read the `.py` file and extract: the strategy class name, the declared `timeframe`, the `minimal_roi` table, the `stoploss` value, the `trailing_stop` flag, `trailing_stop_positive`, `trailing_stop_positive_offset`, and all numeric parameters declared in `buy_params` and `sell_params` dicts.
3. WHEN a strategy is selected, THE `Strategy_Optimizer` SHALL search for a matching JSON file (same stem as the `.py` file) in `{user_data}/strategies/` and load it as the baseline `Candidate_Params` if found.
4. IF no matching JSON file is found, THEN THE `Strategy_Optimizer` SHALL construct a baseline `Candidate_Params` dict from the values extracted by `Strategy_Parser` and notify the user that no JSON was found.
5. THE `Strategy_Parser` SHALL extract parameter range metadata (minimum, maximum, default) from Freqtrade `IntParameter`, `DecimalParameter`, `CategoricalParameter`, and `BooleanParameter` declarations found in the strategy source using Python's `ast` module (`ast.NodeVisitor`) — NOT regular expressions. The AST visitor SHALL locate these declarations by matching `ast.Call` nodes whose function name is one of the four parameter class names and SHALL map their keyword arguments (`low`, `high`, `default`, `space`) directly into the `StrategyParams` model.
6. WHEN parameter extraction completes, THE `Strategy_Optimizer` SHALL display a parameter table showing each detected parameter, its type, its default value, and its declared range so the user can review before starting.
7. IF the `Strategy_Parser` cannot parse the strategy file, THEN THE `Strategy_Optimizer` SHALL display a descriptive error message and prevent the session from starting.

### Requirement 3: Parameter Range Configuration

**User Story:** As a user, I want to review and optionally override the parameter ranges that the optimizer will search, so that I can constrain the search space to values that make sense for my strategy.

#### Acceptance Criteria

1. THE `Strategy_Optimizer` SHALL display an editable parameter table with one row per detected parameter, showing: parameter name, type, current default value, minimum bound, and maximum bound.
2. WHEN the user edits a minimum or maximum bound in the parameter table, THE `Strategy_Optimizer` SHALL validate that minimum is less than maximum and that both values are within the type's valid domain, and SHALL display an inline error if validation fails.
3. THE `Strategy_Optimizer` SHALL allow the user to enable or disable individual parameters via a checkbox per row; disabled parameters SHALL be held at their default value and excluded from the Optuna search space.
4. THE `Strategy_Optimizer` SHALL allow the user to configure the total number of trials (minimum 1, maximum 1000, default 50) before starting a session.
5. THE `Strategy_Optimizer` SHALL allow the user to select the `Optimizer_Score` metric from: `total_profit_pct` (profit %), `total_profit_abs` (absolute profit), `sharpe_ratio`, `profit_factor`, and `win_rate` (default: `total_profit_pct`).
6. WHEN the user saves a parameter configuration, THE `Strategy_Optimizer` SHALL persist it to `{user_data}/optimizer/sessions/{session_id}/session_config.json` so it can be reviewed after the session.

### Requirement 4: Optimizer Session Lifecycle

**User Story:** As a user, I want to start, pause, and stop an optimizer session, so that I have control over how long the search runs and can inspect results at any time.

#### Acceptance Criteria

1. WHEN the user clicks "Start Optimizer", THE `Strategy_Optimizer` SHALL create a new `Optimizer_Session` with a unique `session_id` (UUID4), record the `Backtest_Config` snapshot and parameter configuration, and begin executing trials sequentially.
2. THE `Strategy_Optimizer` SHALL execute trials one at a time in sequence; concurrent trial execution is out of scope.
3. WHEN a session is running, THE `Strategy_Optimizer` SHALL display a progress indicator showing: current trial number, total trials configured, elapsed time, and estimated remaining time.
4. WHEN the user clicks "Stop", THE `Strategy_Optimizer` SHALL stop launching new trials after the current trial completes, set the session status to `stopped`, and preserve all completed `Trial_Record` artefacts.
5. WHEN all configured trials have completed, THE `Strategy_Optimizer` SHALL set the session status to `completed` and display a summary of the best result found.
6. THE `Strategy_Optimizer` SHALL prevent starting a new session while another session is running; the "Start Optimizer" button SHALL be disabled during an active session.
7. WHEN a session is stopped or completed, THE `Strategy_Optimizer` SHALL re-enable the "Start Optimizer" button and allow a new session to be configured.

### Requirement 5: Trial Execution

**User Story:** As a user, I want each trial to run a real Freqtrade backtest with a candidate parameter set and record the outcome, so that the optimizer has accurate performance data to guide the search.

#### Acceptance Criteria

1. BEFORE each trial, THE `Strategy_Optimizer` SHALL write the `Candidate_Params` to a temporary file at `{user_data}/optimizer/sessions/{session_id}/trial_{n:03d}/params.json` without modifying the live strategy JSON file.
2. THE `Strategy_Optimizer` SHALL create a `Trial_Strategy_Dir` containing: a copy or symlink of the selected strategy `.py` file, and a strategy parameter JSON file named exactly after the strategy class (e.g. `MohsBaseline_v2.json`) containing the `Candidate_Params` for that trial. THE `Strategy_Optimizer` SHALL pass that directory via `--strategy-path` so Freqtrade loads the trial-specific JSON without modifying the live strategy JSON file.
3. THE `Strategy_Optimizer` SHALL execute the backtest subprocess via `ProcessService`, capturing stdout and stderr line by line.
4. WHEN the backtest subprocess exits with code 0, THE `Strategy_Optimizer` SHALL parse the backtest result JSON from the Freqtrade output directory and extract: total profit %, total profit absolute, win rate, max drawdown %, total trades, profit factor, Sharpe ratio, best pair, worst pair, final balance, best trade profit %, worst trade profit %.
5. WHEN the backtest subprocess exits with a non-zero code, THE `Strategy_Optimizer` SHALL mark the trial as `failed`, record the stderr output, and continue to the next trial without stopping the session.
6. THE `Strategy_Optimizer` SHALL compute the `Optimizer_Score` for each successful trial using the metric selected by the user in Requirement 3.5.
7. AFTER each trial, THE `Strategy_Optimizer` SHALL persist a `Trial_Record` to `{user_data}/optimizer/sessions/{session_id}/trial_{n:03d}/` containing: `params.json`, `metrics.json` (extracted metrics), `score.json` (score value and metric used), `backtest_result.json` (full parsed result), and `trial.log` (captured stdout/stderr).
8. THE `Strategy_Optimizer` SHALL use Optuna's ask-and-tell interface (`study.ask()` / `study.tell()`) — NOT `study.optimize()` — to propose `Candidate_Params` for each trial.
9. THE `Session_Store` SHALL persist the Optuna study to a SQLite database at `{user_data}/optimizer/sessions/{session_id}/study.db` using Optuna's RDB storage backend.

### Requirement 6: Accepted Best Tracking

**User Story:** As a user, I want the optimizer to automatically track the best result found so far and let me accept it as a checkpoint, so that I always have a safe known-good state to export or roll back to.

#### Acceptance Criteria

1. AFTER each successful trial, THE `Strategy_Optimizer` SHALL compare the trial's `Optimizer_Score` against the current `Accepted_Best` score and automatically promote the trial to `Accepted_Best` if its score is strictly higher.
2. WHEN a trial is promoted to `Accepted_Best`, THE `Strategy_Optimizer` SHALL write a `best.json` pointer file to `{user_data}/optimizer/sessions/{session_id}/best.json` containing the `trial_number` and `session_id` of the new best.
3. THE `Strategy_Optimizer` SHALL display the current `Accepted_Best` metrics in a dedicated "Best Result" panel that updates after each trial.
4. THE `Strategy_Optimizer` SHALL allow the user to manually override the automatic `Accepted_Best` by selecting any successful trial from the trial list and clicking "Set as Best".
5. WHEN the user clicks "Set as Best" on a trial, THE `Strategy_Optimizer` SHALL update `best.json` and the "Best Result" panel to reflect the manually selected trial.
6. THE `Strategy_Optimizer` SHALL display a visual indicator (★ badge) on the trial row that currently holds `Accepted_Best` status in the trial list.

### Requirement 7: Live Progress Display

**User Story:** As a user, I want to see live log output and per-trial status updates while the optimizer is running, so that I can monitor progress without waiting for the session to finish.

#### Acceptance Criteria

1. WHILE a session is running, THE `Strategy_Optimizer` SHALL display a live log panel that streams stdout and stderr from the current trial's backtest subprocess line by line.
2. THE `Strategy_Optimizer` SHALL prepend each trial's log section with a header line showing: trial number, candidate parameter values being tested, and start timestamp.
3. WHEN a trial completes, THE `Strategy_Optimizer` SHALL append a summary line to the log panel showing: profit %, max drawdown %, total trades, `Optimizer_Score`, and whether the trial was accepted as the new best.
4. THE `Strategy_Optimizer` SHALL maintain a trial list panel that shows one row per completed trial with: trial number, key parameter values, profit %, drawdown %, score, and accepted-best indicator.
5. THE `Strategy_Optimizer` SHALL update the trial list panel after each trial completes without requiring the user to refresh.
6. WHEN the user clicks a row in the trial list, THE `Strategy_Optimizer` SHALL display the full metrics for that trial in a detail panel.

### Requirement 8: Results Detail View

**User Story:** As a user, I want to inspect the full backtest metrics for any trial, so that I can make an informed decision about which result to accept or export.

#### Acceptance Criteria

1. WHEN the user selects a trial from the trial list, THE `Strategy_Optimizer` SHALL display the following metrics for that trial: profit %, total profit (absolute), win rate, max drawdown %, total trades, profit factor, Sharpe ratio, best pair, worst pair, final balance, best trade profit %, worst trade profit %, and the full `Candidate_Params` used.
2. THE `Strategy_Optimizer` SHALL display the trial's `Optimizer_Score` and the metric used to compute it alongside the other metrics.
3. THE `Strategy_Optimizer` SHALL provide a "Compare" action that places two selected trials side by side in a comparison view, showing the delta for each numeric metric.
4. THE `Strategy_Optimizer` SHALL provide an "Open Log" action per trial that opens the trial's `trial.log` file in the system default text viewer or in an in-app log viewer.
5. THE `Strategy_Optimizer` SHALL provide an "Open Result File" action per trial that opens the trial's `backtest_result.json` in the system default application.

### Requirement 9: Safe Export

**User Story:** As a user, I want to export the accepted best parameters to the live strategy JSON file safely, so that I can apply the optimized result without risking data loss.

#### Acceptance Criteria

1. WHEN the user clicks "Export Best", THE `Strategy_Optimizer` SHALL display a confirmation dialog showing: the target JSON file path, the current parameter values that will be overwritten, and the new parameter values from `Accepted_Best`.
2. WHEN the user confirms the export, THE `Strategy_Optimizer` SHALL execute the following sequence atomically: (a) read the current live JSON and write a timestamped backup; (b) write the `Accepted_Best` parameters to a hidden temporary file; (c) validate that the temporary file is parseable JSON; (d) invoke `os.replace()` to atomically swap the temporary file into the live JSON path; (e) report success only after the rename completes.
3. IF any step in the export sequence fails, THEN THE `Strategy_Optimizer` SHALL abort the export, restore the backup if the write had already occurred, and display a descriptive error message.
4. THE `Strategy_Optimizer` SHALL retain the five most recent backup files per strategy JSON, pruning older backups automatically using the same logic as `RollbackService`.
5. THE `Strategy_Optimizer` SHALL NOT modify the strategy `.py` source file during export unless the user explicitly enables a "Patch .py file" option and confirms a second confirmation dialog.
6. WHEN export succeeds, THE `Strategy_Optimizer` SHALL display the backup file path so the user knows where the previous version was saved.

### Requirement 10: Rollback

**User Story:** As a user, I want to roll back the strategy JSON to a previous checkpoint, so that I can undo an export that did not perform as expected in live trading.

#### Acceptance Criteria

1. THE `Strategy_Optimizer` SHALL provide a "Rollback" action that lists available backup files for the current strategy JSON, sorted newest-first.
2. WHEN the user selects a backup and confirms, THE `Strategy_Optimizer` SHALL restore that backup to the live strategy JSON path using the same atomic write pattern as the export sequence.
3. THE `Strategy_Optimizer` SHALL delegate rollback execution to `RollbackService` to reuse the existing backup and atomic-restore logic.
4. WHEN rollback succeeds, THE `Strategy_Optimizer` SHALL display a confirmation message showing the restored file path and the backup that was used.
5. IF the selected backup file is missing or corrupt, THEN THE `Strategy_Optimizer` SHALL display a descriptive error and leave the live strategy JSON unchanged.

### Requirement 11: Session Persistence and History

**User Story:** As a user, I want past optimizer sessions to be preserved on disk so that I can review results from previous runs after restarting the application.

#### Acceptance Criteria

1. THE `Session_Store` SHALL persist all session artefacts under `{user_data}/optimizer/sessions/{session_id}/` using the directory layout defined in Requirement 5.7, plus the Optuna SQLite database at `{user_data}/optimizer/sessions/{session_id}/study.db`.
2. WHEN the Strategy Optimizer page is opened, THE `Strategy_Optimizer` SHALL load the list of past sessions from `Session_Store` and display them in a session history panel, sorted newest-first.
3. WHEN the user selects a past session from the history panel, THE `Strategy_Optimizer` SHALL restore the trial list and best result panel for that session from the persisted artefacts.
4. THE `Strategy_Optimizer` SHALL display the following per-session summary in the history panel: strategy name, session start time, total trials run, best score achieved, and session status.
5. THE `Strategy_Optimizer` SHALL allow the user to delete a past session from the history panel; deletion SHALL remove the entire session directory after a confirmation prompt.

### Requirement 12: Framework Independence of Core Logic

**User Story:** As a developer, I want the optimizer's core logic (session management, trial execution, scoring, persistence) to have no imports from PySide6, so that the same backend can be consumed by a future web UI without modification.

#### Acceptance Criteria

1. THE `StrategyOptimizerService` module SHALL NOT import any symbol from `PySide6`, `fastapi`, or `starlette`.
2. THE `Trial_Record` and `Optimizer_Session` data models SHALL be `pydantic.BaseModel` subclasses with no UI framework imports.
3. THE `StrategyOptimizerService` SHALL be fully exercisable by plain `pytest` tests without a Qt application instance or a running HTTP server.
4. THE `Strategy_Optimizer` PySide6 page SHALL interact with `StrategyOptimizerService` exclusively through its public Python API; it SHALL NOT embed subprocess management or file I/O logic directly in the page class.
5. WHEN `StrategyOptimizerService` is instantiated, THE service SHALL accept `SettingsService` and `BacktestService` via constructor injection rather than instantiating them internally.

### Requirement 13: Optimizer Score Computation

**User Story:** As a developer, I want the optimizer score to be a deterministic, reproducible function of the backtest metrics, so that trial rankings are consistent and testable.

#### Acceptance Criteria

1. THE `Optimizer_Score` function SHALL accept a metrics dict and a score metric name and SHALL return a single `float` value.
2. WHEN the score metric is `"total_profit_pct"`, THE `Optimizer_Score` function SHALL return `metrics["total_profit_pct"]`.
3. WHEN the score metric is `"total_profit_abs"`, THE `Optimizer_Score` function SHALL return `metrics["total_profit_abs"]`.
4. WHEN the score metric is `"sharpe_ratio"`, THE `Optimizer_Score` function SHALL return `metrics["sharpe_ratio"]`, substituting `0.0` for `None` or `NaN`.
5. WHEN the score metric is `"profit_factor"`, THE `Optimizer_Score` function SHALL return `metrics["profit_factor"]`, substituting `0.0` for `None` or `NaN`.
6. WHEN the score metric is `"win_rate"`, THE `Optimizer_Score` function SHALL return `metrics["win_rate"]`, substituting `0.0` for `None` or `NaN`.
7. IF the metrics dict is missing the requested field, THEN THE `Optimizer_Score` function SHALL return `0.0` and log a warning.
8. FOR ALL valid metrics dicts and score metric names, THE `Optimizer_Score` function SHALL return a finite `float` (never `NaN`, `+Inf`, or `-Inf`).

### Requirement 14: Strategy Parameter Parsing Round-Trip

**User Story:** As a developer, I want the strategy parameter parser to produce output that can be serialized to JSON and deserialized back to an equivalent structure, so that trial parameter files are always valid and recoverable.

#### Acceptance Criteria

1. THE `Strategy_Parser` SHALL parse a strategy `.py` file and return a `StrategyParams` object containing all detected parameters.
2. THE `Strategy_Parser` SHALL serialize a `StrategyParams` object to a JSON-compatible dict via a `to_dict()` method.
3. THE `Strategy_Parser` SHALL deserialize a JSON-compatible dict back to a `StrategyParams` object via a `from_dict()` class method.
4. FOR ALL valid `StrategyParams` objects, serializing then deserializing SHALL produce an object equal to the original (round-trip property).
5. IF the strategy `.py` file contains no `buy_params` or `sell_params` declarations, THEN THE `Strategy_Parser` SHALL return a `StrategyParams` with empty `buy_params` and `sell_params` dicts rather than raising an exception.

### Requirement 15: Trial List UI Performance

**User Story:** As a user, I want the trial list to remain smooth and responsive even when hundreds of trials have completed, so that the interface never freezes during a long session.

#### Acceptance Criteria

1. THE `Strategy_Optimizer` PySide6 page SHALL back the trial list with a `QAbstractTableModel` subclass (`TrialTableModel`) rather than a `QTableWidget`, so that Qt only renders the rows currently visible on screen.
2. WHEN a new trial completes, THE `TrialTableModel` SHALL append the row by emitting `beginInsertRows` / `endInsertRows` without repainting the entire table.
3. WHEN the `Accepted_Best` pointer changes, THE `TrialTableModel` SHALL emit `dataChanged` only for the affected rows rather than resetting the entire model.
4. THE trial list SHALL display at minimum: trial number, key parameter values (up to 3 params), profit %, max drawdown %, `Optimizer_Score`, and an accepted-best badge (★ for best, blank otherwise).
5. THE `TrialTableModel` SHALL support sorting by any numeric column without reloading data from disk.

### Requirement 16: Metrics Sanitization

**User Story:** As a developer, I want all backtest metrics passed to Optuna to be finite floats, so that the Bayesian sampler never crashes on NaN or infinite values from edge-case backtests.

#### Acceptance Criteria

1. BEFORE calling `study.tell(trial, score)`, THE `Optimizer_Score` function SHALL guarantee the returned value is a finite `float` by replacing `None`, `NaN`, `+Inf`, and `-Inf` with `0.0`.
2. WHEN a backtest produces zero trades, THE `Optimizer_Score` function SHALL return `0.0` for all metrics rather than raising a `ZeroDivisionError` or returning `NaN`.
3. THE metrics extraction step SHALL sanitize every numeric field in the `metrics.json` artefact using the same finite-float guarantee before persisting to disk.
4. FOR ALL combinations of score metric name and metrics dict (including empty dicts and dicts with `None` values), THE `Optimizer_Score` function SHALL return a finite `float` — this SHALL be verified by a property-based test using Hypothesis.

---

## Implementation Guardrail: No Duplicate Architecture

Before implementing, search the repo. If `optimizer_page.py`, `optimizer_session_service.py`, `strategy_py_parser.py`, `optimizer_store.py`, `optimizer_models.py`, or equivalent files already exist, update them instead of creating `strategy_optimizer_*` duplicates. Use existing method names from the repo unless a public wrapper is truly needed. The implementation SHALL NOT duplicate existing services, parsers, stores, runners, UI pages, widgets, or models. If related functionality already exists, it MUST be reused, extended, or refactored in place.

Key reuse points identified in the existing codebase:
- `BacktestService.get_available_strategies()` — reuse for strategy discovery (Requirement 2.1)
- `ProcessService` — reuse for subprocess execution (Requirement 5.3)
- `RollbackService._backup_file()`, `_prune_backups()`, `_atomic_restore()` — reuse for export and rollback (Requirements 9, 10)
- `app/core/parsing/backtest_parser.py` — reuse `parse_backtest_results_from_zip` / `parse_backtest_results_from_json` for trial result parsing (Requirement 5.4)
- `app/core/parsing/json_parser.py` — reuse `write_json_file_atomic` for all JSON writes
- `app/core/freqtrade/runners/backtest_runner.py` — extend or wrap `create_backtest_command` to support `--strategy-path` override (Requirement 5.2)
- `app/core/models/settings_models.BacktestPreferences` — reuse directly; add `OptimizerPreferences` as a new field on `AppSettings` following the same pattern as `backtest_preferences`
