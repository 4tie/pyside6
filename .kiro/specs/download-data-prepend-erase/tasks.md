# Implementation Plan: download-data-prepend-erase

## Overview

Four targeted edits to existing files, following the layered architecture bottom-up (model → runner → service → UI). No new files are created. Property-based tests use Hypothesis and cover the three correctness properties defined in the design.

## Tasks

- [x] 1. Add `prepend` and `erase` fields to `DownloadPreferences`
  - Open `app/core/models/settings_models.py`
  - Add `prepend: bool = Field(False, description="Include --prepend flag in download command")` to `DownloadPreferences`
  - Add `erase: bool = Field(False, description="Include --erase flag in download command")` to `DownloadPreferences`
  - Both fields must follow the existing `Field(default, description="...")` convention
  - No migration needed — Pydantic's default handling covers existing `settings.json` files that lack these keys
  - _Requirements: 6.1, 6.2_

  - [x] 1.1 Write property test for `DownloadPreferences` round-trip serialization
    - **Property 3: Preferences round-trip**
    - Use `@given(prepend=st.booleans(), erase=st.booleans())` with `@settings(max_examples=100)`
    - Construct `DownloadPreferences(prepend=prepend, erase=erase)`, call `.model_dump()`, reconstruct, assert both fields match
    - Place test in `tests/test_download_data_prepend_erase.py`
    - **Validates: Requirements 6.3, 6.4, 6.5**

- [x] 2. Update `create_download_data_command` in the runner
  - Open `app/core/freqtrade/runners/download_data_runner.py`
  - Add `prepend: bool = False` and `erase: bool = False` parameters to `create_download_data_command`
  - Remove the hardcoded `"--prepend"` entry from `ft_args`
  - Add `if prepend: ft_args.append("--prepend")` immediately after the fixed positional args and before `--timerange`/`-p`
  - Add `if erase: ft_args.append("--erase")` on the next line, same position
  - Update the docstring to document the two new parameters
  - _Requirements: 2.1, 2.2, 2.3, 4.1, 4.2, 4.3_

  - [x] 2.1 Write property test for prepend flag presence
    - **Property 1: Prepend flag presence matches parameter**
    - Use `@given(timeframe=st.sampled_from(["1m","5m","1h","1d"]), timerange=st.one_of(st.none(), st.text(min_size=1, max_size=20)), pairs=st.lists(st.text(min_size=3, max_size=10), max_size=5), erase=st.booleans(), prepend=st.booleans())` with `@settings(max_examples=100)`
    - Build a minimal `AppSettings` mock (valid-looking `python_executable` and `user_data_path`) to avoid filesystem access
    - Assert `("--prepend" in cmd.args) == prepend`
    - Place test in `tests/test_download_data_prepend_erase.py`
    - **Validates: Requirements 2.1, 2.2**

  - [x] 2.2 Write property test for erase flag presence
    - **Property 2: Erase flag presence matches parameter**
    - Same generators as Property 1
    - Assert `("--erase" in cmd.args) == erase`
    - Place test in `tests/test_download_data_prepend_erase.py`
    - **Validates: Requirements 4.2, 4.3**

- [x] 3. Checkpoint — ensure runner tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Update `DownloadDataService.build_command` in the service layer
  - Open `app/core/services/download_data_service.py`
  - Add `prepend: bool = False` and `erase: bool = False` keyword parameters to `build_command`
  - Forward both values to `create_download_data_command(... prepend=prepend, erase=erase)`
  - Update the docstring to document the two new parameters
  - The service must not interpret the booleans — pure pass-through only
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 4.1 Write unit tests for `DownloadDataService.build_command`
    - Test that calling `build_command` without `prepend`/`erase` kwargs succeeds and produces neither flag (Requirements 3.1, 3.2)
    - Test that `prepend=True` is forwarded and produces `--prepend` in the command args
    - Test that `erase=True` is forwarded and produces `--erase` in the command args
    - Use a mock `SettingsService` that returns a minimal valid `AppSettings`
    - Place tests in `tests/test_download_data_prepend_erase.py`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 5. Add checkboxes and wire preferences in `DownloadPage`
  - Open `app/ui/pages/download_data_page.py`
  - Import `QCheckBox` from `PySide6.QtWidgets` (add to existing import if not present)
  - In `_build()` (or equivalent UI construction method), create `self._prepend_cb = QCheckBox("Prepend data")` and `self._erase_cb = QCheckBox("Erase existing data")`
  - Insert both checkboxes into the Configuration section layout, below the Timerange row and above the Pairs section header
  - In `_run()` (or equivalent run handler), read `self._prepend_cb.isChecked()` and `self._erase_cb.isChecked()` and pass them to `self._download_svc.build_command(..., prepend=..., erase=...)`
  - Add `_save_preferences()` helper: load settings, set `settings.download_preferences.prepend` and `.erase` from checkbox states, save settings; call it at the end of `_run()` after a successful `build_command`
  - Add `_restore_preferences()` helper: load settings, call `self._prepend_cb.setChecked(prefs.prepend)` and `self._erase_cb.setChecked(prefs.erase)`; call it at the end of `_build()`
  - `blockSignals` is not required — the checkboxes have no connected signals with side effects
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3, 5.4, 6.3, 6.4, 6.5_

  - [x] 5.1 Write unit tests for `DownloadPage` checkbox initialisation and preferences
    - Test that `DownloadPage` initialises with both checkboxes unchecked when preferences are default (Requirements 1.4, 1.5)
    - Test that `_restore_preferences()` sets "Prepend data" checked when `DownloadPreferences.prepend=True` (Requirement 6.4)
    - Test that `_restore_preferences()` sets "Erase existing data" checked when `DownloadPreferences.erase=True` (Requirement 6.5)
    - Test that both unchecked → command contains neither flag (Requirement 5.3)
    - Test that both checked → command contains both flags (Requirement 5.4)
    - Place tests in `tests/test_download_data_prepend_erase.py`
    - _Requirements: 1.4, 1.5, 5.3, 5.4, 6.4, 6.5_

- [x] 6. Final checkpoint — ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- All four changes are in existing files — no new modules or abstractions are introduced
- The runner is the single source of truth for CLI flag construction; every layer above it is a pure pass-through
- Property tests (Properties 1–3) use Hypothesis with `max_examples=100`; place all tests in `tests/test_download_data_prepend_erase.py`
- The `AppSettings` mock for runner property tests needs only `python_executable` and `user_data_path` set to valid-looking paths to avoid filesystem access
