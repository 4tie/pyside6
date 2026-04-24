# Requirements Document

## Introduction

The Download Data page in the Freqtrade GUI currently builds a `freqtrade download-data` command with a hardcoded `--prepend` flag. This feature exposes both `--prepend` and `--erase` as explicit, user-controlled checkboxes in the UI, removes the hardcoded flag, and threads the user's choices through the service and runner layers so the generated CLI command accurately reflects what the user selected.

## Glossary

- **Download_Page**: The PySide6 `DownloadPage` widget at `app/ui/pages/download_page.py` that provides the Download Data UI.
- **DownloadDataService**: The service at `app/core/services/download_data_service.py` responsible for building `DownloadDataRunCommand` objects.
- **Download_Data_Runner**: The module at `app/core/freqtrade/runners/download_data_runner.py` that constructs the final freqtrade CLI argument list.
- **DownloadDataRunCommand**: The dataclass in `app/core/models/command_models.py` that carries the executable program, argument list, and working directory for a download-data run.
- **Prepend_Flag**: The `--prepend` CLI flag for `freqtrade download-data`, which causes new candles to be prepended to existing data files rather than appended.
- **Erase_Flag**: The `--erase` CLI flag for `freqtrade download-data`, which deletes existing data files for the selected pairs and timeframe before downloading fresh data.
- **DownloadPreferences**: The Pydantic model `DownloadPreferences` inside `app/core/models/settings_models.py` that persists download-related user preferences to `~/.freqtrade_gui/settings.json`.

---

## Requirements

### Requirement 1: Expose Prepend and Erase Checkboxes in the UI

**User Story:** As a Freqtrade GUI user, I want checkboxes for `--prepend` and `--erase` on the Download Data page, so that I can control how existing data files are handled without editing CLI commands manually.

#### Acceptance Criteria

1. THE Download_Page SHALL display a checkbox labelled "Prepend data" that maps to the Prepend_Flag.
2. THE Download_Page SHALL display a checkbox labelled "Erase existing data" that maps to the Erase_Flag.
3. THE Download_Page SHALL render both checkboxes in the Configuration section, below the Timerange field and above the Pairs section.
4. WHEN the Download_Page is first displayed, THE Download_Page SHALL initialise the "Prepend data" checkbox to unchecked.
5. WHEN the Download_Page is first displayed, THE Download_Page SHALL initialise the "Erase existing data" checkbox to unchecked.

---

### Requirement 2: Remove the Hardcoded --prepend Flag

**User Story:** As a Freqtrade GUI user, I want the download command to only include `--prepend` when I have explicitly checked the checkbox, so that the generated command matches my intent.

#### Acceptance Criteria

1. THE Download_Data_Runner SHALL omit the Prepend_Flag from the argument list when the `prepend` parameter is `False`.
2. WHEN the `prepend` parameter is `True`, THE Download_Data_Runner SHALL include `--prepend` in the argument list.
3. THE Download_Data_Runner SHALL accept a `prepend` boolean parameter with a default value of `False`.

---

### Requirement 3: Pass Prepend and Erase Choices Through the Service Layer

**User Story:** As a developer, I want the service layer to accept and forward `prepend` and `erase` options, so that the UI and runner remain decoupled.

#### Acceptance Criteria

1. THE DownloadDataService SHALL accept a `prepend` boolean parameter in its `build_command` method, with a default value of `False`.
2. THE DownloadDataService SHALL accept an `erase` boolean parameter in its `build_command` method, with a default value of `False`.
3. WHEN `build_command` is called, THE DownloadDataService SHALL forward the `prepend` value to the Download_Data_Runner.
4. WHEN `build_command` is called, THE DownloadDataService SHALL forward the `erase` value to the Download_Data_Runner.

---

### Requirement 4: Include --erase in the Generated Command When Selected

**User Story:** As a Freqtrade GUI user, I want the `--erase` flag included in the download command when I check "Erase existing data", so that stale data files are removed before the download starts.

#### Acceptance Criteria

1. THE Download_Data_Runner SHALL accept an `erase` boolean parameter with a default value of `False`.
2. WHEN the `erase` parameter is `True`, THE Download_Data_Runner SHALL include `--erase` in the argument list.
3. THE Download_Data_Runner SHALL omit `--erase` from the argument list when the `erase` parameter is `False`.

---

### Requirement 5: Read Checkbox State When Building the Command

**User Story:** As a Freqtrade GUI user, I want the Download button to use the current checkbox states when building the command, so that the terminal output reflects exactly what I configured.

#### Acceptance Criteria

1. WHEN the user clicks the Download button, THE Download_Page SHALL read the checked state of the "Prepend data" checkbox and pass it to `DownloadDataService.build_command`.
2. WHEN the user clicks the Download button, THE Download_Page SHALL read the checked state of the "Erase existing data" checkbox and pass it to `DownloadDataService.build_command`.
3. WHEN both checkboxes are unchecked and the user clicks Download, THE Download_Page SHALL build a command that contains neither `--prepend` nor `--erase`.
4. WHEN both checkboxes are checked and the user clicks Download, THE Download_Page SHALL build a command that contains both `--prepend` and `--erase`.

---

### Requirement 6: Persist Checkbox Preferences Across Sessions

**User Story:** As a Freqtrade GUI user, I want my last-used prepend and erase selections to be remembered between sessions, so that I do not have to reconfigure them every time I open the app.

#### Acceptance Criteria

1. THE DownloadPreferences SHALL include a `prepend` boolean field with a default value of `False`.
2. THE DownloadPreferences SHALL include an `erase` boolean field with a default value of `False`.
3. WHEN the user clicks the Download button, THE Download_Page SHALL persist the current checkbox states to DownloadPreferences via the settings service.
4. WHEN the Download_Page is initialised, THE Download_Page SHALL restore the "Prepend data" checkbox state from `DownloadPreferences.prepend`.
5. WHEN the Download_Page is initialised, THE Download_Page SHALL restore the "Erase existing data" checkbox state from `DownloadPreferences.erase`.
