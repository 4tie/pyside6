# Implementation Plan: Strategy Rollback

## Overview

Rewrite `RollbackService` with backup/prune/atomic-restore logic, add `RollbackDialog`, wire a Rollback button into `ResultsPage`, and cover everything with unit and property-based tests using Hypothesis.

The existing `rollback_service.py` skeleton is replaced entirely. `json_parser.write_json_file_atomic` is already available and will be used for all atomic writes. The correct UI file to modify is `app/ui/pages/results_page.py`.

## Tasks

- [x] 1. Rewrite `RollbackService` with `RollbackResult`, backup, prune, and scope support
  - [x] 1.1 Replace `RollbackResult` dataclass in `app/core/services/rollback_service.py`
    - Remove the existing `success` and `error` fields
    - Add fields: `params_restored: bool`, `config_restored: bool`, `rolled_back_to: str`, `strategy_name: str`, `params_path: Optional[Path]`, `config_path: Optional[Path]`
    - Keep `@dataclass` decorator; import `Optional` from `typing`
    - _Requirements: 4.5_

  - [x] 1.2 Implement `RollbackService._backup_file(active_path) -> Path`
    - Generate ISO-8601 UTC timestamp with `datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")`
    - Compute backup path as `active_path.parent / f"{active_path.name}.bak_{timestamp}"`
    - Read source with `parse_json_file(active_path)`, write backup with `write_json_file_atomic`
    - Wrap any write failure in `ValueError`; log `debug` with source and backup paths
    - Call `self._prune_backups(active_path)` after writing
    - Return the backup `Path`
    - _Requirements: 3.1, 3.2, 3.4, 7.2_

  - [x] 1.3 Implement `RollbackService._prune_backups(active_path)`
    - Glob `active_path.parent.glob(f"{active_path.name}.bak_*")` to find existing backups
    - Sort descending by name (ISO-8601 lexicographic = chronological)
    - Delete all files beyond index `MAX_BACKUPS - 1` (keep 5 most recent)
    - On deletion failure: log `warning` with path and error, continue — do not abort
    - When no excess files exist, do nothing and do not log a warning
    - `MAX_BACKUPS: int = 5` as class attribute
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 1.4 Implement `RollbackService._atomic_restore(src, dest)`
    - Read source JSON with `parse_json_file(src)`; raise `ValueError` on failure
    - Ensure `dest.parent` exists with `mkdir(parents=True, exist_ok=True)`
    - Write with `write_json_file_atomic(dest, data)`; wrap failure in `ValueError`
    - Log `info` with source and destination paths
    - _Requirements: 4.1, 4.2, 4.4, 7.3_

  - [x] 1.5 Implement `RollbackService.rollback(run_dir, user_data_path, strategy_name, restore_params=True, restore_config=False) -> RollbackResult`
    - Raise `FileNotFoundError` immediately if `run_dir` does not exist
    - Raise `ValueError("No restorable files found in run directory: ...")` if neither source file is present
    - Log `info` with strategy name and run ID at start of operation
    - For params: if `restore_params=True` and `params.json` exists, call `_backup_file(params_dest)` then `_atomic_restore(params_src, params_dest)`; set `params_restored=True` and `params_path=params_dest`
    - For config: if `restore_config=True` and `config.snapshot.json` exists, call `_backup_file(config_dest)` then `_atomic_restore(config_src, config_dest)`; set `config_restored=True` and `config_path=config_dest`
    - If backup write fails, raise `ValueError` without touching the active file
    - Return `RollbackResult` with all fields populated; `params_path`/`config_path` are `None` when not restored
    - _Requirements: 3.3, 4.1, 4.2, 4.3, 4.5, 7.1, 7.4_

  - [x] 1.6 Write unit tests for `RollbackService` in `tests/core/services/test_rollback_service.py`
    - Test `rollback()` with both files present and both flags `True`
    - Test `rollback()` with only `params.json` present (`restore_params=True`)
    - Test `rollback()` with only `config.snapshot.json` present (`restore_config=True`)
    - Test `rollback()` raises `FileNotFoundError` for missing `run_dir`
    - Test `rollback()` raises `ValueError` when neither source file is present
    - Test `_backup_file()` creates a backup with the correct `.bak_YYYYMMDDTHHMMSS` name format
    - Test `_prune_backups()` with exactly 5 existing backups — no deletion occurs
    - Test `_prune_backups()` with 0 existing backups — no deletion, no warning logged
    - Test backup write failure aborts rollback without touching the active file
    - _Requirements: 3.1, 3.3, 4.1, 4.3, 8.1_

- [x] 2. Add property-based tests for `RollbackService` in `tests/property/test_rollback_properties.py`
  - [x] 2.1 Write property test for params restore round-trip
    - **Property 1: Params restore round-trip**
    - **Validates: Requirements 4.1**
    - Use `st.dictionaries(st.text(), st.text())` for params content; assert active file content equals source after rollback

  - [x] 2.2 Write property test for config restore round-trip
    - **Property 2: Config restore round-trip**
    - **Validates: Requirements 4.2**
    - Use `st.dictionaries(st.text(), st.text())` for config content; assert active file content equals source after rollback

  - [x] 2.3 Write property test for backup created before overwrite
    - **Property 3: Backup is created before overwrite**
    - **Validates: Requirements 3.1, 3.2**
    - Use `st.binary()` for file content; assert at least one `.bak_*` file exists after rollback

  - [x] 2.4 Write property test for backup filename ISO-8601 format
    - **Property 4: Backup filename matches ISO-8601 format**
    - **Validates: Requirements 3.4**
    - Assert backup filename suffix matches `bak_\d{8}T\d{6}` regex

  - [x] 2.5 Write property test for backup pruning keeps at most 5 files
    - **Property 5: Backup pruning keeps at most 5 files per active file**
    - **Validates: Requirements 8.1, 8.2**
    - Use `st.integers(min_value=0, max_value=20)` for N pre-existing backups; assert total `.bak_*` count ≤ 5 after rollback

  - [x] 2.6 Write property test for backup pruning independence
    - **Property 6: Backup pruning is independent per active file**
    - **Validates: Requirements 8.4**
    - Use `st.integers(0, 10)` × 2 for params and config backup counts; assert pruning one does not affect the other

  - [x] 2.7 Write property test for unchecked params scope leaves active params unchanged
    - **Property 7: Unchecked params scope leaves active params unchanged**
    - **Validates: Requirements 6.3**
    - Use `st.dictionaries(...)` for active params content; assert byte-for-byte identity after `restore_params=False`

  - [x] 2.8 Write property test for unchecked config scope leaves active config unchanged
    - **Property 8: Unchecked config scope leaves active config unchanged**
    - **Validates: Requirements 6.4**
    - Use `st.dictionaries(...)` for active config content; assert byte-for-byte identity after `restore_config=False`

  - [x] 2.9 Write property test for RollbackResult accuracy
    - **Property 9: RollbackResult accurately reflects what was restored**
    - **Validates: Requirements 4.5**
    - Use `st.booleans()` × 2 for restore flags and `st.text(min_size=1)` for run_id; assert result fields match inputs

  - [x] 2.10 Write property test for rollback info log contains strategy name and run ID
    - **Property 10: Rollback info log contains strategy name and run ID**
    - **Validates: Requirements 7.1**
    - Use `st.text(min_size=1)` × 2 for strategy name and run ID; capture log output and assert both substrings present

  - [x] 2.11 Write property test for restore log contains source and destination paths
    - **Property 11: Restore log contains source and destination paths**
    - **Validates: Requirements 7.3**
    - Use `st.text(min_size=1)` for strategy name; capture log output and assert source and dest path strings present

- [x] 3. Checkpoint — service layer complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement `RollbackDialog` in `app/ui/dialogs/rollback_dialog.py`
  - [x] 4.1 Create `RollbackDialog(QDialog)` with constructor and layout
    - Constructor params: `strategy_name: str`, `run_id: str`, `has_params: bool`, `has_config: bool`, `params_path: Path`, `config_path: Path`, `parent: QWidget | None = None`
    - Module-level logger: `_log = get_logger("ui.rollback_dialog")`
    - Display strategy name and run ID in the dialog body
    - List the files that will be overwritten (active params path and/or active config path)
    - _Requirements: 2.1, 2.2, 2.4, 2.5_

  - [x] 4.2 Add scope checkboxes and OK/Cancel buttons
    - Params checkbox: label `"Restore strategy parameters (params.json)"`, checked by default when `has_params=True`, disabled when `has_params=False`
    - Config checkbox: label `"Restore Freqtrade config (config.snapshot.json)"`, unchecked by default even when `has_config=True`, disabled when `has_config=False`
    - Connect both checkboxes to a `_on_checkbox_changed()` slot that enables/disables the OK button
    - OK button disabled when both checkboxes are unchecked; display a validation message in that state
    - Standard `QDialogButtonBox` with `Ok | Cancel`
    - _Requirements: 6.1, 6.2, 6.5_

  - [x] 4.3 Add `restore_params` and `restore_config` properties
    - `restore_params` returns `self._params_cb.isChecked()`
    - `restore_config` returns `self._config_cb.isChecked()`
    - _Requirements: 6.3, 6.4_

  - [x] 4.4 Write unit tests for `RollbackDialog` in `tests/ui/test_rollback_dialog.py`
    - Test OK button is disabled when both checkboxes are unchecked
    - Test OK button is enabled when at least one checkbox is checked
    - Test `restore_params` property reflects params checkbox state
    - Test `restore_config` property reflects config checkbox state
    - Test params checkbox is checked by default when `has_params=True`
    - Test config checkbox is unchecked by default even when `has_config=True`
    - _Requirements: 6.1, 6.2, 6.5_

- [x] 5. Wire Rollback button into `ResultsPage` in `app/ui/pages/results_page.py`
  - [x] 5.1 Add `_rollback_btn` and `_rollback_service` to `ResultsPage.__init__` / `_build`
    - Import `RollbackService` from `app.core.services.rollback_service`
    - Instantiate `self._rollback_service = RollbackService()` in `__init__` (before `_build()`)
    - In `_build()`, after the existing `refresh_btn`, add `self._rollback_btn = QPushButton("⏪  Rollback")` to the `hdr` layout
    - Set `self._rollback_btn.setVisible(False)` — hidden by default
    - Connect `self._rollback_btn.clicked.connect(self._on_rollback_clicked)`
    - _Requirements: 1.1, 1.2_

  - [x] 5.2 Implement `_update_rollback_button(run: dict)` helper
    - Resolve `run_dir` using the existing `_run_dir_path()` helper
    - Check `user_data_path` from `self._state.current_settings`
    - Check presence of `params.json` and `config.snapshot.json` in `run_dir`
    - Show button (`setVisible(True)`) whenever a row is selected
    - Enable button when `user_data_path` is configured AND at least one source file exists
    - Disable with tooltip `"user_data path not configured"` when `user_data_path` is missing
    - Disable with tooltip `"No restorable files found"` when neither source file exists
    - _Requirements: 1.1, 1.3, 1.4_

  - [x] 5.3 Extend `_on_run_selected(row)` to call `_update_rollback_button`
    - After the existing `_load_run_detail(run)` call, call `self._update_rollback_button(run)`
    - When `row < 0` or no item found, call `self._rollback_btn.setVisible(False)`
    - _Requirements: 1.1, 1.2_

  - [x] 5.4 Implement `_on_rollback_clicked()` slot
    - Guard: if `self._current_run` is None, return early
    - Resolve `run_dir`, `user_data_path`, `strategy_name` from `self._current_run` and settings
    - Determine `has_params` and `has_config` by checking file existence in `run_dir`
    - Construct `params_path` and `config_path` (active file destinations)
    - Open `RollbackDialog`; if result is not `QDialog.Accepted`, log `debug` "Rollback cancelled by user" and return
    - Call `self._rollback_service.rollback(...)` with `restore_params=dlg.restore_params`, `restore_config=dlg.restore_config`
    - On success: build a message listing restored files and run ID; show `QMessageBox.information`
    - On `FileNotFoundError`: show `QMessageBox.critical` — "Run directory not found: {path}"
    - On `ValueError`: show `QMessageBox.critical` — error message from exception
    - On unexpected `Exception`: show `QMessageBox.critical` — "Unexpected error: {e}"
    - _Requirements: 2.1, 2.3, 5.1, 5.2, 5.3, 5.4, 5.5, 7.5_

- [x] 6. Final checkpoint — full integration
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Sub-tasks marked with `*` are optional and can be skipped for a faster MVP
- `write_json_file_atomic` from `app.core.parsing.json_parser` handles temp+rename — use it for all file writes in `RollbackService`
- The existing `rollback_service.py` skeleton is replaced entirely in task 1; the old `success` and `error` fields are removed
- Property tests go in `tests/property/test_rollback_properties.py` (create the directory if it does not exist); unit tests go in `tests/core/services/test_rollback_service.py` and `tests/ui/test_rollback_dialog.py`
- All property tests use `tmp_path` (pytest fixture) for file system isolation — no real `user_data` directories are touched
- The correct UI file to modify is `app/ui/pages/results_page.py` (not `backtest_results_widget.py`)
