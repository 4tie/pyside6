# Design Document: Strategy Rollback

## Overview

The Strategy Rollback feature lets users restore a strategy's parameters (and optionally the Freqtrade config) to the exact state captured during a previous backtest run — directly from the Results Browser, without leaving the UI.

When a run row is selected in `ResultsPage`, a **Rollback** button appears in the toolbar. Clicking it opens a `RollbackDialog` (a `QDialog`) that shows what will be overwritten and lets the user choose scope (params only, config only, or both). On confirmation, `RollbackService` backs up the current active files, then atomically restores the chosen files from the run directory. The result is surfaced as a non-blocking `QMessageBox` or status-bar message.

The existing `RollbackService` skeleton at `app/core/services/rollback_service.py` is present but incomplete — it lacks backup creation, backup pruning, scope selection, and the full `RollbackResult` contract. This design replaces it entirely.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  UI Layer                                                       │
│                                                                 │
│  ResultsPage (app/ui/pages/results_page.py)                     │
│    • Adds "Rollback" QPushButton to toolbar                     │
│    • Shows/hides button on row selection                        │
│    • Opens RollbackDialog on click                              │
│    • Calls RollbackService on confirmation                      │
│    • Shows QMessageBox / status-bar feedback                    │
│                                                                 │
│  RollbackDialog (app/ui/dialogs/rollback_dialog.py)             │
│    • QDialog — modal confirmation                               │
│    • Displays strategy name, run ID, files to overwrite         │
│    • Two checkboxes: params (checked) / config (unchecked)      │
│    • Disables OK when both unchecked                            │
│    • Returns (restore_params: bool, restore_config: bool)       │
└────────────────────────┬────────────────────────────────────────┘
                         │ calls
┌────────────────────────▼────────────────────────────────────────┐
│  Service Layer                                                  │
│                                                                 │
│  RollbackService (app/core/services/rollback_service.py)        │
│    • rollback(run_dir, user_data_path, strategy_name,           │
│               restore_params, restore_config) → RollbackResult  │
│    • _backup_file(src) → Path  (write + prune)                  │
│    • _prune_backups(active_file)                                 │
│    • _atomic_restore(src, dest)                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │ uses
┌────────────────────────▼────────────────────────────────────────┐
│  Infrastructure Layer                                           │
│                                                                 │
│  app/core/parsing/json_parser.py                                │
│    • parse_json_file()                                          │
│    • write_json_file_atomic()                                   │
│                                                                 │
│  app/core/utils/app_logger.py                                   │
│    • get_logger("services.rollback")                            │
│    • get_logger("ui.rollback_dialog")                           │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

**Services never import UI code.** `RollbackService` is a pure service — it takes `Path` arguments and returns a `RollbackResult` dataclass. All Qt interaction lives in `ResultsPage` and `RollbackDialog`.

**Scope is decided in the dialog, not the service.** `RollbackDialog` returns two booleans (`restore_params`, `restore_config`). `RollbackService.rollback()` accepts these as parameters and skips the corresponding file if `False`. This keeps the service testable without a UI.

**Backup-then-restore ordering.** For each file to be restored, the service writes the backup first. If the backup write fails, the rollback aborts immediately — the active file is never touched. This satisfies the "never leave active files in a partially-written state" requirement.

**Atomic writes via temp+rename.** All file writes (backup and restore) use `write_json_file_atomic()` from `json_parser.py`, which writes to a `.tmp` sibling then calls `os.replace()`. This is atomic on POSIX and near-atomic on Windows (same volume).

---

## Components and Interfaces

### `RollbackResult` (dataclass)

```python
@dataclass
class RollbackResult:
    """Outcome of a rollback operation."""
    params_restored: bool
    config_restored: bool
    rolled_back_to: str          # run_id (e.g. "run_20240315T143022_abc123")
    strategy_name: str
    params_path: Optional[Path]  # absolute path of restored params file, or None
    config_path: Optional[Path]  # absolute path of restored config file, or None
```

### `RollbackService`

```python
class RollbackService:
    """Restores strategy params and/or config from a saved backtest run.

    All public methods are instance methods (stateless logic, but kept as
    instance methods for testability via dependency injection).
    """

    MAX_BACKUPS: int = 5  # maximum .bak_* files retained per active file

    def rollback(
        self,
        run_dir: Path,
        user_data_path: Path,
        strategy_name: str,
        restore_params: bool = True,
        restore_config: bool = False,
    ) -> RollbackResult:
        """Restore files from run_dir to their active locations.

        Args:
            run_dir: Absolute path to the run folder.
            user_data_path: Absolute path to freqtrade user_data directory.
            strategy_name: Strategy name without .py extension.
            restore_params: If True, restore params.json → active params.
            restore_config: If True, restore config.snapshot.json → active config.

        Returns:
            RollbackResult describing what was restored.

        Raises:
            FileNotFoundError: If run_dir does not exist.
            ValueError: If a source file cannot be read, or if backup write fails.
        """

    def _backup_file(self, active_path: Path) -> Path:
        """Write a timestamped backup of active_path, then prune old backups.

        Args:
            active_path: The active file to back up (must exist).

        Returns:
            Path of the newly written backup file.

        Raises:
            ValueError: If the backup write fails (wraps underlying IOError).
        """

    def _prune_backups(self, active_path: Path) -> None:
        """Delete excess .bak_* files for active_path, keeping MAX_BACKUPS most recent.

        Sorts by ISO-8601 timestamp suffix (descending). Logs a warning for
        any deletion failure but does not abort.

        Args:
            active_path: The active file whose backups should be pruned.
        """

    def _atomic_restore(self, src: Path, dest: Path) -> None:
        """Copy src JSON content to dest atomically.

        Args:
            src: Source JSON file (inside run_dir).
            dest: Destination active file.

        Raises:
            ValueError: If src cannot be read or dest cannot be written.
        """
```

### `RollbackDialog`

```python
class RollbackDialog(QDialog):
    """Modal confirmation dialog for strategy rollback.

    Displays the strategy name, run ID, and files that will be overwritten.
    Presents two checkboxes for scope selection. Disables the OK button when
    both checkboxes are unchecked.

    Usage:
        dlg = RollbackDialog(
            strategy_name="MyStrategy",
            run_id="run_20240315T143022_abc123",
            has_params=True,
            has_config=True,
            params_path=Path("/user_data/strategies/MyStrategy.json"),
            config_path=Path("/user_data/config.json"),
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted:
            restore_params = dlg.restore_params
            restore_config = dlg.restore_config
    """

    def __init__(
        self,
        strategy_name: str,
        run_id: str,
        has_params: bool,
        has_config: bool,
        params_path: Path,
        config_path: Path,
        parent: QWidget | None = None,
    ) -> None: ...

    @property
    def restore_params(self) -> bool:
        """True if the params checkbox is checked."""

    @property
    def restore_config(self) -> bool:
        """True if the config checkbox is checked."""
```

### `ResultsPage` changes

The following additions are made to the existing `ResultsPage` class:

| Addition | Description |
|---|---|
| `self._rollback_btn: QPushButton` | "⏪  Rollback" button added to the header `hdr` layout, hidden by default |
| `self._rollback_service: RollbackService` | Instantiated in `__init__` |
| `_on_run_selected(row)` | Extended to show/hide/enable/disable `_rollback_btn` |
| `_on_rollback_clicked()` | New slot — opens `RollbackDialog`, calls service, shows feedback |
| `_update_rollback_button(run)` | Helper — checks `user_data_path`, `params.json`, `config.snapshot.json` presence |

---

## Data Models

### Backup file naming

```
{active_file}.bak_{YYYYMMDDTHHMMSS}

Examples:
  /user_data/strategies/MyStrategy.json.bak_20240315T143022
  /user_data/config.json.bak_20240315T143022
```

The timestamp is generated with:
```python
from datetime import datetime, timezone
datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
```

### Backup glob pattern (for pruning)

```python
active_path.parent.glob(f"{active_path.name}.bak_*")
```

Sorted descending by name (ISO-8601 lexicographic order = chronological order), keep first 5, delete the rest.

### `RollbackResult` field summary

| Field | Type | Description |
|---|---|---|
| `params_restored` | `bool` | True if params.json was successfully written to active params |
| `config_restored` | `bool` | True if config.snapshot.json was successfully written to active config |
| `rolled_back_to` | `str` | The `run_id` (folder name) that was restored from |
| `strategy_name` | `str` | Strategy name used for the restore |
| `params_path` | `Optional[Path]` | Absolute path of the restored active params file, or `None` |
| `config_path` | `Optional[Path]` | Absolute path of the restored active config file, or `None` |

### Run directory layout (reference)

```
{user_data}/backtest_results/{strategy}/run_{ts}_{hash}/
    params.json              ← source for params restore
    config.snapshot.json     ← source for config restore
    trades.json
    results.json
    meta.json
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Params restore round-trip

*For any* valid `params.json` content in a run directory, after a successful rollback with `restore_params=True`, the active params file should contain exactly the same data as the source `params.json`.

**Validates: Requirements 4.1**

---

### Property 2: Config restore round-trip

*For any* valid `config.snapshot.json` content in a run directory, after a successful rollback with `restore_config=True`, the active config file should contain exactly the same data as the source `config.snapshot.json`.

**Validates: Requirements 4.2**

---

### Property 3: Backup is created before overwrite

*For any* existing active params file content, when a rollback with `restore_params=True` is confirmed, a `.bak_*` file containing the original content must exist before the active file is overwritten.

**Validates: Requirements 3.1, 3.2**

---

### Property 4: Backup filename matches ISO-8601 format

*For any* rollback operation that creates a backup, the backup filename suffix must match the pattern `bak_YYYYMMDDTHHMMSS` (exactly 15 digits with a `T` separator at position 8).

**Validates: Requirements 3.4**

---

### Property 5: Backup pruning keeps at most 5 files per active file

*For any* number N of pre-existing `.bak_*` files for a given active file, after writing a new backup, the total count of `.bak_*` files for that active file must be at most 5, and the retained files must be the N+1 most recent (or all of them if N+1 ≤ 5).

**Validates: Requirements 8.1, 8.2**

---

### Property 6: Backup pruning is independent per active file

*For any* combination of params backup count and config backup count, pruning params backups must not affect the count of config backups, and vice versa.

**Validates: Requirements 8.4**

---

### Property 7: Unchecked params scope leaves active params unchanged

*For any* existing active params file content and any run directory, when a rollback is executed with `restore_params=False`, the active params file must be byte-for-byte identical after the rollback as it was before.

**Validates: Requirements 6.3**

---

### Property 8: Unchecked config scope leaves active config unchanged

*For any* existing active config file content and any run directory, when a rollback is executed with `restore_config=False`, the active config file must be byte-for-byte identical after the rollback as it was before.

**Validates: Requirements 6.4**

---

### Property 9: RollbackResult accurately reflects what was restored

*For any* rollback invocation with known `restore_params` and `restore_config` flags and a run directory containing the corresponding source files, the returned `RollbackResult` must have `params_restored` equal to `restore_params` (when the source file exists) and `config_restored` equal to `restore_config` (when the source file exists), and `rolled_back_to` equal to the run directory's folder name.

**Validates: Requirements 4.5**

---

### Property 10: Rollback info log contains strategy name and run ID

*For any* strategy name and run ID, initiating a rollback must produce at least one `INFO`-level log entry that contains both the strategy name and the run ID as substrings.

**Validates: Requirements 7.1**

---

### Property 11: Restore log contains source and destination paths

*For any* successful file restore, the service must emit at least one `INFO`-level log entry that contains both the source path and the destination path as substrings.

**Validates: Requirements 7.3**

---

**Property Reflection — redundancy check:**

- Properties 1 and 2 are both round-trip properties but for different files (params vs config). They cannot be merged because the source filenames, destination paths, and backup logic differ. Both are retained.
- Properties 3 (backup before overwrite) and 5 (pruning keeps ≤ 5) are distinct: Property 3 tests ordering (backup happens before overwrite), Property 5 tests count invariant. Not redundant.
- Properties 7 and 8 (scope selection) are symmetric but for different files. Both retained.
- Properties 10 and 11 are both logging properties but test different log levels and different content (strategy+run_id vs source+dest paths). Both retained.
- Property 5 subsumes Property 6's sorting concern (correct sort order is implied by "most recent 5"), so Property 6 focuses only on independence. Both retained as they test different invariants.

---

## Error Handling

### Service layer

| Condition | Behaviour |
|---|---|
| `run_dir` does not exist | Raise `FileNotFoundError` immediately; no files touched |
| `params.json` present but unreadable | Raise `ValueError` with descriptive message; active params unchanged |
| Backup write fails | Raise `ValueError`; active file never touched; backup `.tmp` cleaned up |
| Atomic restore write fails | Raise `ValueError`; backup already written and intact for manual recovery |
| Neither `params.json` nor `config.snapshot.json` present | Raise `ValueError("No restorable files found in run directory: ...")` |
| Excess backup deletion fails | Log `WARNING` with path and error; continue — rollback is not aborted |

### UI layer

| Condition | Behaviour |
|---|---|
| `FileNotFoundError` from service | `QMessageBox.critical` — "Run directory not found: {path}" |
| `ValueError` from service | `QMessageBox.critical` — error message from exception |
| Unexpected `Exception` | `QMessageBox.critical` — "Unexpected error: {e}" |
| Rollback succeeds | `QMessageBox.information` (non-blocking) listing restored files and run ID |

### Button state rules

The `_rollback_btn` is:
- **Hidden** when no row is selected
- **Visible + Enabled** when a row is selected, `user_data_path` is configured, and at least one of `params.json` / `config.snapshot.json` exists in the run directory
- **Visible + Disabled** (with tooltip) when `user_data_path` is not configured
- **Visible + Disabled** (with tooltip "No restorable files found") when neither source file exists in the run directory

---

## Testing Strategy

### Unit tests (example-based)

Located in `tests/unit/services/test_rollback_service.py` and `tests/unit/ui/test_rollback_dialog.py`.

Focus areas:
- `RollbackService.rollback()` with both files present
- `RollbackService.rollback()` with only params present
- `RollbackService.rollback()` with only config present
- `RollbackService.rollback()` raises `FileNotFoundError` for missing run_dir
- `RollbackService.rollback()` raises `ValueError` when neither file present
- `RollbackService._backup_file()` creates backup with correct name format
- `RollbackService._prune_backups()` with exactly 5 existing backups (no deletion)
- `RollbackService._prune_backups()` with 0 existing backups (no deletion, no warning)
- Backup write failure aborts rollback without touching active file
- `RollbackDialog` — confirm button disabled when both checkboxes unchecked
- `RollbackDialog` — `restore_params` / `restore_config` properties reflect checkbox state

### Property-based tests (Hypothesis)

Located in `tests/property/test_rollback_properties.py`.

Uses [Hypothesis](https://hypothesis.readthedocs.io/) (`pip install hypothesis`). Each test runs a minimum of 100 iterations.

```python
# Tag format: Feature: strategy-rollback, Property {N}: {property_text}
```

| Test | Property | Hypothesis strategy |
|---|---|---|
| `test_params_restore_round_trip` | Property 1 | `st.dictionaries(st.text(), st.text())` for params content |
| `test_config_restore_round_trip` | Property 2 | `st.dictionaries(st.text(), st.text())` for config content |
| `test_backup_created_before_overwrite` | Property 3 | `st.binary()` for file content |
| `test_backup_filename_iso8601_format` | Property 4 | `st.just(None)` (timestamp from real clock) |
| `test_backup_pruning_keeps_at_most_5` | Property 5 | `st.integers(min_value=0, max_value=20)` for N existing backups |
| `test_backup_pruning_independence` | Property 6 | `st.integers(0, 10)` × 2 for params and config backup counts |
| `test_unchecked_params_leaves_active_unchanged` | Property 7 | `st.dictionaries(...)` for active params content |
| `test_unchecked_config_leaves_active_unchanged` | Property 8 | `st.dictionaries(...)` for active config content |
| `test_rollback_result_accuracy` | Property 9 | `st.booleans()` × 2 for restore flags, `st.text()` for run_id |
| `test_rollback_log_contains_strategy_and_run_id` | Property 10 | `st.text(min_size=1)` × 2 for strategy name and run ID |
| `test_restore_log_contains_paths` | Property 11 | `st.text(min_size=1)` for strategy name |

All property tests use `tmp_path` (pytest fixture) for file system isolation. No real `user_data` directories are touched.

### Integration tests

Not required for this feature — all logic operates on local files with no external services.

### Manual smoke tests

- Run the app, open Results Browser, select a run → Rollback button appears
- Click Rollback → dialog shows correct strategy name, run ID, file paths
- Uncheck both checkboxes → OK button disables
- Cancel → no files changed
- Confirm (params only) → active params updated, backup created, success message shown
- Confirm (both) → both files updated, two backups created
- Run rollback 7 times → only 5 `.bak_*` files remain per active file
