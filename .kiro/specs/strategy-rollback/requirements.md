# Requirements Document

## Introduction

The Strategy Rollback feature adds a "Rollback" button next to each run entry in the Backtest Results Browser. When clicked, it restores the strategy parameters (from `params.json`) and optionally the Freqtrade config (from `config.snapshot.json`) back to the state they were in when that backtest run was executed. This lets users quickly revert a strategy to a known-good configuration without manually hunting through run folders.

The feature builds on the existing `RollbackService` (which already handles the file-copy logic) and the `ResultsPage` run table. The primary work is wiring a per-row rollback button into the UI, adding a confirmation dialog, surfacing success/error feedback, and optionally backing up the current params before overwriting.

## Glossary

- **Backtest_Results_Browser**: The `ResultsPage` widget that lists historical backtest runs and shows their metrics.
- **Run**: A single backtest execution stored under `{user_data}/backtest_results/{strategy}/run_{ts}_{hash}/`.
- **Run_Dir**: The folder for a specific run, containing `params.json`, `config.snapshot.json`, `trades.json`, `results.json`, and `meta.json`.
- **params.json**: File inside a Run_Dir that stores the strategy's buy/sell parameters and ROI table at the time of the run.
- **config.snapshot.json**: File inside a Run_Dir that stores a copy of the Freqtrade config used during the run.
- **Active_Params**: The live strategy parameter file at `{user_data}/strategies/{strategy_name}.json`.
- **Active_Config**: The live Freqtrade config file at `{user_data}/config.json`.
- **Rollback_Service**: The existing `app.core.services.rollback_service.RollbackService` that copies `params.json` and `config.snapshot.json` from a Run_Dir to their active locations.
- **Rollback_Button**: A per-row button rendered in the run list table of the Backtest_Results_Browser.
- **Confirmation_Dialog**: A modal `QDialog` that presents the rollback scope and asks the user to confirm before any files are modified.
- **Backup**: An automatic copy of the current Active_Params (and optionally Active_Config) written to a timestamped file before overwriting, so the user can recover if needed.

---

## Requirements

### Requirement 1: Rollback Action Button on Row Selection

**User Story:** As a strategy developer, I want a rollback action button that appears when I select a run in the Results Browser, so that I can restore a strategy to a previous state without leaving the UI.

#### Acceptance Criteria

1. WHEN the user selects a run row in the run list table, THE Backtest_Results_Browser SHALL display a "Rollback" action button in the toolbar or action area above the table.
2. WHILE no run row is selected, THE Rollback_Button SHALL NOT be visible or SHALL be hidden from the action area.
3. WHILE no `user_data_path` is configured in settings, THE Rollback_Button SHALL be disabled even when a row is selected.
4. WHEN a run row is selected and the Run_Dir does not contain `params.json` AND does not contain `config.snapshot.json`, THE Rollback_Button SHALL be disabled with a tooltip explaining that no restorable files were found.

---

### Requirement 2: Confirmation Dialog Before Rollback

**User Story:** As a strategy developer, I want a confirmation dialog before any files are overwritten, so that I do not accidentally lose my current strategy parameters.

#### Acceptance Criteria

1. WHEN the user clicks a Rollback_Button, THE Backtest_Results_Browser SHALL display a Confirmation_Dialog before modifying any files.
2. THE Confirmation_Dialog SHALL display the strategy name, the run ID being restored, and the list of files that will be overwritten (Active_Params and/or Active_Config).
3. WHEN the user dismisses the Confirmation_Dialog without confirming, THE Rollback_Service SHALL NOT modify any files.
4. WHERE `params.json` is present in the Run_Dir, THE Confirmation_Dialog SHALL indicate that Active_Params will be overwritten.
5. WHERE `config.snapshot.json` is present in the Run_Dir, THE Confirmation_Dialog SHALL indicate that Active_Config will be overwritten.

---

### Requirement 3: Backup Before Overwrite

**User Story:** As a strategy developer, I want my current parameters automatically backed up before a rollback overwrites them, so that I can recover if I rolled back by mistake.

#### Acceptance Criteria

1. WHEN the user confirms a rollback and Active_Params exists at `{user_data}/strategies/{strategy_name}.json`, THE Rollback_Service SHALL write a backup copy to `{user_data}/strategies/{strategy_name}.json.bak_{timestamp}` before overwriting.
2. WHEN the user confirms a rollback and Active_Config exists at `{user_data}/config.json`, THE Rollback_Service SHALL write a backup copy to `{user_data}/config.json.bak_{timestamp}` before overwriting.
3. IF writing the backup file fails, THEN THE Rollback_Service SHALL log the error and abort the rollback without modifying any active files.
4. THE Rollback_Service SHALL use an ISO-8601 timestamp (format `YYYYMMDDTHHMMSS`) as the `{timestamp}` suffix in backup file names.

---

### Requirement 4: Execute Rollback and Restore Files

**User Story:** As a strategy developer, I want the rollback to atomically restore the strategy parameters and config, so that the active files are never left in a partially-written state.

#### Acceptance Criteria

1. WHEN the user confirms a rollback, THE Rollback_Service SHALL copy `params.json` from the Run_Dir to `{user_data}/strategies/{strategy_name}.json` using an atomic write (write to a temp file, then rename).
2. WHERE `config.snapshot.json` is present in the Run_Dir, THE Rollback_Service SHALL copy it to `{user_data}/config.json` using an atomic write.
3. IF the source `params.json` cannot be read, THEN THE Rollback_Service SHALL raise a `ValueError` with a descriptive message and leave Active_Params unchanged.
4. IF the atomic write fails mid-operation, THEN THE Rollback_Service SHALL leave the previously written backup intact so the user can recover manually.
5. THE Rollback_Service SHALL return a `RollbackResult` dataclass indicating which files were restored (`params_restored`, `config_restored`) and the `rolled_back_to` run ID.

---

### Requirement 5: Success and Error Feedback in the UI

**User Story:** As a strategy developer, I want clear feedback after a rollback attempt, so that I know whether the restore succeeded or failed and what was changed.

#### Acceptance Criteria

1. WHEN a rollback completes successfully, THE Backtest_Results_Browser SHALL display a non-blocking success notification stating which files were restored and the run ID rolled back to.
2. WHEN a rollback fails, THE Backtest_Results_Browser SHALL display an error message describing the failure reason.
3. WHEN a rollback completes successfully and `params_restored` is `True`, THE Backtest_Results_Browser SHALL include the path of the restored Active_Params in the success notification.
4. WHEN a rollback completes successfully and `config_restored` is `True`, THE Backtest_Results_Browser SHALL include the path of the restored Active_Config in the success notification.
5. IF the Run_Dir does not exist at rollback time, THEN THE Backtest_Results_Browser SHALL display an error message stating the run directory was not found.

---

### Requirement 6: Rollback Scope Selection

**User Story:** As a strategy developer, I want to choose whether to restore only the strategy parameters, only the config, or both, so that I have fine-grained control over what gets overwritten.

#### Acceptance Criteria

1. THE Confirmation_Dialog SHALL present a checkbox labelled "Restore strategy parameters (params.json)" that is checked by default when `params.json` is present in the Run_Dir.
2. THE Confirmation_Dialog SHALL present a checkbox labelled "Restore Freqtrade config (config.snapshot.json)" that is unchecked by default, even when `config.snapshot.json` is present in the Run_Dir, because config changes are more disruptive than parameter changes.
3. WHEN the user unchecks "Restore strategy parameters", THE Rollback_Service SHALL NOT overwrite Active_Params.
4. WHEN the user unchecks "Restore Freqtrade config", THE Rollback_Service SHALL NOT overwrite Active_Config.
5. WHEN both checkboxes are unchecked, THE Confirmation_Dialog SHALL disable the confirm button and display a validation message stating that at least one file must be selected.

---

### Requirement 7: Logging

**User Story:** As a developer, I want all rollback operations logged at appropriate levels, so that I can diagnose issues from the log files.

#### Acceptance Criteria

1. WHEN a rollback is initiated, THE Rollback_Service SHALL log an `info`-level message containing the strategy name and run ID.
2. WHEN a backup file is written, THE Rollback_Service SHALL log a `debug`-level message containing the source path and backup destination path.
3. WHEN a file is successfully restored, THE Rollback_Service SHALL log an `info`-level message containing the source path and destination path.
4. IF any step of the rollback fails, THE Rollback_Service SHALL log an `error`-level message containing the exception details before raising or returning the error.
5. WHEN the user cancels the Confirmation_Dialog, THE Backtest_Results_Browser SHALL log a `debug`-level message indicating the rollback was cancelled by the user.

---

### Requirement 8: Backup File Management

**User Story:** As a strategy developer, I want backup files to be automatically pruned so that `.bak_*` files do not accumulate indefinitely in my strategies and config directories.

#### Acceptance Criteria

1. WHEN a new backup file is written for a given active file, THE Rollback_Service SHALL retain only the most recent 5 `.bak_*` files for that active file and delete any older ones.
2. WHEN pruning backup files, THE Rollback_Service SHALL sort existing `.bak_*` files for the active file by their ISO-8601 timestamp suffix in descending order and delete all beyond the 5 most recent.
3. IF deleting an excess backup file fails, THEN THE Rollback_Service SHALL log a `warning`-level message containing the file path and the error, and SHALL continue without aborting the rollback.
4. THE Rollback_Service SHALL apply backup pruning separately for Active_Params backups and Active_Config backups, so the limit of 5 is per active file.
5. WHEN no excess backup files exist for an active file, THE Rollback_Service SHALL perform no deletion and SHALL NOT log a warning.
