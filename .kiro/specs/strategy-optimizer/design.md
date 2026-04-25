# Design Document: Strategy Optimizer

## Overview

The Strategy Optimizer adds a new "Optimizer" tab to the Freqtrade GUI desktop application. It runs repeated real Freqtrade backtests with Optuna-guided parameter variation, records every trial, tracks the best result, and provides safe export/rollback of the optimized strategy JSON.

The design follows the existing project architecture strictly:
- All core logic in `app/core/` — no PySide6 imports
- PySide6 page in `app/ui/pages/optimizer_page.py`
- Pydantic v2 `BaseModel` for all data models
- Constructor injection for all service dependencies
- Reuse of existing `ProcessService`, `RollbackService`, `BacktestService`, `SettingsService`, and parsers

---

## Architecture

### Layer Diagram

```
app/ui/pages/optimizer_page.py          ← PySide6 page (UI only)
app/ui/widgets/trial_table_model.py     ← QAbstractTableModel for trial list
app/ui/dialogs/export_confirm_dialog.py ← Export confirmation dialog
        │
        │  public Python API only
        ▼
app/core/services/optimizer_session_service.py  ← orchestrates sessions & trials
app/core/services/optimizer_store.py            ← filesystem persistence
        │
        ├── app/core/parsing/strategy_py_parser.py   ← AST-based .py parser (NEW)
        ├── app/core/parsing/backtest_parser.py       ← reused for result parsing
        ├── app/core/parsing/json_parser.py           ← reused for atomic writes
        ├── app/core/services/process_service.py      ← reused for subprocess
        ├── app/core/services/rollback_service.py     ← reused for export/rollback
        ├── app/core/services/backtest_service.py     ← reused for strategy list
        └── app/core/models/optimizer_models.py       ← Pydantic models (NEW)
```

### New Files

| File | Purpose |
|---|---|
| `app/core/models/optimizer_models.py` | Pydantic models: `OptimizerSession`, `TrialRecord`, `StrategyParams`, `ParamDef`, `TrialMetrics`, `SessionConfig`, `BestPointer` |
| `app/core/parsing/strategy_py_parser.py` | AST-based parser for Freqtrade strategy `.py` files |
| `app/core/services/optimizer_session_service.py` | Session lifecycle, trial execution, scoring, Optuna integration |
| `app/core/services/optimizer_store.py` | Filesystem layout, session/trial persistence, history loading |
| `app/ui/pages/optimizer_page.py` | PySide6 page — the new "Optimizer" tab |
| `app/ui/widgets/trial_table_model.py` | `QAbstractTableModel` subclass for the trial list |
| `app/ui/dialogs/export_confirm_dialog.py` | Export confirmation dialog with diff view |
| `tests/core/test_optimizer_score.py` | Unit + property tests for score computation |
| `tests/core/test_strategy_py_parser.py` | Unit + property tests for AST parser |
| `tests/core/test_optimizer_session_service.py` | Unit tests for session service |
| `tests/property/test_optimizer_properties.py` | Hypothesis property tests (score, round-trip) |

### Modified Files

| File | Change |
|---|---|
| `app/core/models/settings_models.py` | Add `OptimizerPreferences` model and `optimizer_preferences` field to `AppSettings` |
| `app/ui/shell/sidebar.py` | Add `("optimizer", "⚡", "Optimizer")` entry to `_NAV_ITEMS` |
| `app/ui/main_window.py` | Instantiate `OptimizerPage` and add to `self._pages` dict |

---

## Data Models (`app/core/models/optimizer_models.py`)

All models are Pydantic v2 `BaseModel` subclasses. No PySide6 imports.

```python
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid

class SessionStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    STOPPED   = "stopped"
    COMPLETED = "completed"

class TrialStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED  = "failed"

class ParamType(str, Enum):
    INT         = "int"
    DECIMAL     = "decimal"
    CATEGORICAL = "categorical"
    BOOLEAN     = "boolean"

class ParamDef(BaseModel):
    """One parameter definition extracted from a strategy .py file."""
    name: str
    param_type: ParamType
    default: Any
    low: Optional[float] = None       # None for categorical/boolean
    high: Optional[float] = None
    categories: Optional[List[Any]] = None  # for CategoricalParameter
    space: str = "buy"                # "buy" | "sell" | "roi" | "stoploss" | "trailing"
    enabled: bool = True              # user can disable to hold at default

class StrategyParams(BaseModel):
    """Full parameter metadata extracted from a strategy .py file."""
    strategy_class: str
    timeframe: str = "5m"
    minimal_roi: Dict[str, float] = Field(default_factory=dict)
    stoploss: float = -0.10
    trailing_stop: bool = False
    trailing_stop_positive: Optional[float] = None
    trailing_stop_positive_offset: Optional[float] = None
    buy_params: Dict[str, ParamDef] = Field(default_factory=dict)
    sell_params: Dict[str, ParamDef] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyParams":
        return cls.model_validate(data)

class TrialMetrics(BaseModel):
    """Extracted backtest metrics for one trial."""
    total_profit_pct: float = 0.0
    total_profit_abs: float = 0.0
    win_rate: float = 0.0
    max_drawdown_pct: float = 0.0
    total_trades: int = 0
    profit_factor: float = 0.0
    sharpe_ratio: Optional[float] = None
    best_pair: str = ""
    worst_pair: str = ""
    final_balance: float = 0.0
    best_trade_profit_pct: float = 0.0
    worst_trade_profit_pct: float = 0.0

class TrialRecord(BaseModel):
    """Persisted artefact for one trial."""
    session_id: str
    trial_number: int
    status: TrialStatus = TrialStatus.PENDING
    candidate_params: Dict[str, Any] = Field(default_factory=dict)
    metrics: Optional[TrialMetrics] = None
    score: Optional[float] = None
    score_metric: str = "total_profit_pct"
    log_excerpt: str = ""
    is_best: bool = False

class BestPointer(BaseModel):
    """Lightweight pointer to the current Accepted_Best trial."""
    session_id: str
    trial_number: int
    score: float

class SessionConfig(BaseModel):
    """Configuration snapshot saved at session start."""
    strategy_name: str
    strategy_class: str
    pairs: List[str] = Field(default_factory=list)
    timeframe: str = "5m"
    timerange: Optional[str] = None
    dry_run_wallet: float = 80.0
    max_open_trades: int = 2
    config_file_path: str = ""
    total_trials: int = 50
    score_metric: str = "total_profit_pct"
    param_defs: List[ParamDef] = Field(default_factory=list)

class OptimizerSession(BaseModel):
    """One complete optimizer session."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: SessionStatus = SessionStatus.PENDING
    config: SessionConfig
    trials_completed: int = 0
    best_pointer: Optional[BestPointer] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

class OptimizerPreferences(BaseModel):
    """Persisted optimizer UI preferences (added to AppSettings)."""
    last_strategy: str = ""
    total_trials: int = 50
    score_metric: str = "total_profit_pct"
```

---

## Strategy `.py` Parser (`app/core/parsing/strategy_py_parser.py`)

Uses Python's `ast` module exclusively — no regex.

```python
import ast
from pathlib import Path
from typing import Any, Dict, Optional
from app.core.models.optimizer_models import ParamDef, ParamType, StrategyParams

_PARAM_CLASSES = {
    "IntParameter":         ParamType.INT,
    "DecimalParameter":     ParamType.DECIMAL,
    "CategoricalParameter": ParamType.CATEGORICAL,
    "BooleanParameter":     ParamType.BOOLEAN,
}

class _ParamVisitor(ast.NodeVisitor):
    """AST visitor that extracts Freqtrade parameter declarations."""

    def __init__(self):
        self.params: Dict[str, ParamDef] = {}
        self._current_space = "buy"

    def visit_ClassDef(self, node: ast.ClassDef):
        # Detect space from class-level buy_params / sell_params assignments
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Detect space context from assignment targets like `buy_params = {...}`
        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.id in ("buy_params", "sell_params"):
                    self._current_space = "buy" if "buy" in target.id else "sell"
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        func_name = _get_func_name(node)
        if func_name not in _PARAM_CLASSES:
            self.generic_visit(node)
            return
        param_type = _PARAM_CLASSES[func_name]
        kwargs = {kw.arg: _eval_constant(kw.value) for kw in node.keywords if kw.arg}
        # positional args: low, high (for numeric types) or categories (for categorical)
        positional = [_eval_constant(a) for a in node.args]
        # ... build ParamDef from kwargs and positional args
        self.generic_visit(node)
```

Key design decisions:
- `ast.NodeVisitor` traverses the full AST; no `eval()` or `exec()` calls
- `_eval_constant()` handles `ast.Constant`, `ast.UnaryOp` (negative numbers), and `ast.List`/`ast.Tuple` for categorical values
- Parameter names are inferred from the enclosing assignment target (e.g. `buy_rsi = IntParameter(...)`)
- Space is inferred from the enclosing `buy_params`/`sell_params` dict or class attribute context
- Returns `StrategyParams` with empty `buy_params`/`sell_params` if none found (never raises)
- **V1 scope limitation**: Only parameters declared directly in the strategy class body are extracted. Parameters inherited from a base class (e.g. `class MyStrategy(BaseStrategy):`) are not visible to a single-file AST parse. The parser does not traverse the filesystem to locate and parse parent classes. If a strategy relies on inherited parameters, the user will see an empty parameter table and should define the parameters locally or configure them manually. This limitation is documented in the UI via a tooltip on the parameter table.

---

## Optimizer Score Function

Implemented as a pure function in `app/core/services/optimizer_session_service.py`:

```python
import math
from typing import Dict, Any

SCORE_METRICS = frozenset({
    "total_profit_pct", "total_profit_abs", "sharpe_ratio",
    "profit_factor", "win_rate",
})

def compute_optimizer_score(metrics: Dict[str, Any], score_metric: str) -> float:
    """Return a finite float score. Never raises, never returns NaN/Inf."""
    if score_metric not in SCORE_METRICS:
        return 0.0
    raw = metrics.get(score_metric)
    if raw is None:
        return 0.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value):
        return 0.0
    return value
```

This function is the single source of truth for scoring. It is called:
1. After each successful trial to compute the score for `study.tell()`
2. When comparing against `Accepted_Best`
3. When loading historical sessions to reconstruct rankings

---

## Session Service (`app/core/services/optimizer_session_service.py`)

### Responsibilities
- Create and manage `OptimizerSession` lifecycle
- Coordinate trial execution loop (sequential, one at a time)
- Interface with Optuna via ask-and-tell
- Delegate subprocess execution to `ProcessService`
- Delegate persistence to `OptimizerStore`
- Delegate result parsing to `parse_backtest_results_from_zip`/`parse_backtest_results_from_json`

### Constructor

```python
class StrategyOptimizerService:
    def __init__(
        self,
        settings_service: SettingsService,
        backtest_service: BacktestService,
        process_service: Optional[ProcessService] = None,
        rollback_service: Optional[RollbackService] = None,
    ):
        self._settings = settings_service
        self._backtest = backtest_service
        self._process = process_service or ProcessService()
        self._rollback = rollback_service or RollbackService()
        self._store = OptimizerStore(settings_service)
        self._active_session: Optional[OptimizerSession] = None
        self._stop_requested = False
        self._active_subprocess: Optional[subprocess.Popen] = None  # weak ref for SIGTERM
```

### Subprocess Lifecycle and Stop Handling

When `stop_session()` is called, the service must terminate the active Freqtrade subprocess — not just set a flag and wait for the next loop iteration. The active subprocess handle is stored on the service instance and terminated with a two-stage signal:

```python
def stop_session(self) -> None:
    self._stop_requested = True
    proc = self._active_subprocess
    if proc is not None and proc.poll() is None:
        proc.terminate()          # SIGTERM — graceful shutdown
        try:
            proc.wait(timeout=10) # give it 10 seconds
        except subprocess.TimeoutExpired:
            proc.kill()           # SIGKILL — force kill if it hangs
```

`ProcessService` stores the `Popen` handle and exposes it so `StrategyOptimizerService` can retrieve it. This prevents orphaned backtest processes from consuming CPU and memory after the user clicks Stop.

### Trial Loop (runs on a background thread, not the Qt main thread)

```python
def _run_trial_loop(
    self,
    session: OptimizerSession,
    study: optuna.Study,
    on_trial_start: Callable[[int, dict], None],
    on_trial_complete: Callable[[TrialRecord], None],
    on_session_complete: Callable[[OptimizerSession], None],
    on_log_line: Callable[[str], None],
):
    for trial_number in range(1, session.config.total_trials + 1):
        if self._stop_requested:
            break
        # 1. Ask Optuna for candidate params
        optuna_trial = study.ask()
        candidate = self._sample_params(optuna_trial, session.config.param_defs)
        on_trial_start(trial_number, candidate)

        # 2. Write trial dir and run backtest
        trial_dir = self._store.trial_dir(session.session_id, trial_number)
        trial_dir.mkdir(parents=True, exist_ok=True)
        record = self._execute_trial(session, trial_number, candidate, trial_dir, on_log_line)

        # 3. Tell Optuna the result
        score = record.score if record.score is not None else 0.0
        study.tell(optuna_trial, score)

        # 4. Update best
        self._maybe_update_best(session, record)

        # 5. Persist and notify UI
        self._store.save_trial_record(session.session_id, record)
        session.trials_completed += 1
        on_trial_complete(record)

    session.status = SessionStatus.STOPPED if self._stop_requested else SessionStatus.COMPLETED
    self._store.save_session(session)
    on_session_complete(session)
```

### Trial Strategy Directory

For each trial, a temporary directory is created:
```
{user_data}/optimizer/sessions/{session_id}/trial_{n:03d}/strategy_dir/
    {StrategyClass}.py      ← copy of the live .py file (never a symlink)
    {StrategyClass}.json    ← Candidate_Params for this trial
```

The strategy `.py` file is always **copied**, never symlinked. Symlinks on Windows require elevated administrator privileges depending on local security policy, which would crash the application for standard users. Copying a single `.py` file is computationally negligible and guarantees cross-platform compatibility.

The backtest command is built by calling `BacktestService.build_command()` with an extra `--strategy-path` flag pointing to this directory, overriding the default strategies dir.

---

## Session Store (`app/core/services/optimizer_store.py`)

### Directory Layout

```
{user_data}/optimizer/sessions/
    {session_id}/
        session.json          ← OptimizerSession (status, config, metadata)
        session_config.json   ← SessionConfig snapshot
        best.json             ← BestPointer (trial_number, session_id, score)
        study.db              ← Optuna SQLite RDB storage
        trial_001/
            params.json       ← Candidate_Params
            metrics.json      ← TrialMetrics
            score.json        ← {score, score_metric}
            backtest_result.json  ← full parsed BacktestSummary
            trial.log         ← captured stdout+stderr
            strategy_dir/     ← temporary strategy dir (may be cleaned up)
        trial_002/
            ...
```

### Key Methods

```python
class OptimizerStore:
    def __init__(self, settings_service: SettingsService): ...

    def sessions_root(self) -> Path: ...
    def session_dir(self, session_id: str) -> Path: ...
    def trial_dir(self, session_id: str, trial_number: int) -> Path: ...

    def save_session(self, session: OptimizerSession) -> None: ...
    def load_session(self, session_id: str) -> OptimizerSession: ...
    def list_sessions(self) -> List[OptimizerSession]: ...  # sorted newest-first
    def delete_session(self, session_id: str) -> None: ...

    def save_trial_record(self, session_id: str, record: TrialRecord) -> None: ...
    def load_trial_record(self, session_id: str, trial_number: int) -> TrialRecord: ...
    def load_all_trial_records(self, session_id: str) -> List[TrialRecord]: ...

    def save_best_pointer(self, session_id: str, pointer: BestPointer) -> None: ...
    def load_best_pointer(self, session_id: str) -> Optional[BestPointer]: ...
```

All writes use `write_json_file_atomic` from `app/core/parsing/json_parser.py`.

## Optuna SQLite WAL Mode

When `create_session()` initialises the Optuna study, it must enable SQLite Write-Ahead Logging (WAL) mode on the `study.db` database. Without WAL, the default SQLite journal mode serialises all readers and writers, causing the PySide6 UI thread (which reads the study to render progress) to block the optimizer loop thread (which writes trial results), and vice versa.

WAL mode allows simultaneous readers and a single writer, eliminating this contention:

```python
import optuna
from sqlalchemy import event
from sqlalchemy.engine import Engine

def _create_study(db_path: Path, study_name: str) -> optuna.Study:
    storage_url = f"sqlite:///{db_path}"
    engine = create_engine(storage_url)

    @event.listens_for(engine, "connect")
    def set_wal_mode(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")

    storage = optuna.storages.RDBStorage(url=storage_url, engine_kwargs={"connect_args": {"check_same_thread": False}})
    return optuna.create_study(
        study_name=study_name,
        storage=storage,
        direction="maximize",
        load_if_exists=True,
    )
```

This is applied once at study creation time. All subsequent connections to the same `study.db` file inherit WAL mode automatically.

---

## Export Flow

The export is handled by `StrategyOptimizerService.export_best()`, which delegates to `RollbackService` for the atomic write pattern:

```python
def export_best(self, session_id: str) -> ExportResult:
    """Export Accepted_Best params to the live strategy JSON."""
    pointer = self._store.load_best_pointer(session_id)
    record = self._store.load_trial_record(session_id, pointer.trial_number)
    session = self._store.load_session(session_id)

    strategy_name = session.config.strategy_name
    settings = self._settings.load_settings()
    live_json = Path(settings.user_data_path) / "strategies" / f"{strategy_name}.json"

    # (a) Backup current live JSON
    backup_path = self._rollback._backup_file(live_json)

    # (b+c+d) Write candidate params atomically.
    # IMPORTANT: The temp file must be created on the same filesystem as live_json
    # so that os.replace() is a true atomic rename, not a cross-device copy-and-delete.
    # write_json_file_atomic() creates the temp file in live_json.parent for this reason.
    write_json_file_atomic(live_json, record.candidate_params)

    return ExportResult(
        success=True,
        live_json_path=str(live_json),
        backup_path=str(backup_path),
    )
```

`write_json_file_atomic` must create its temporary file in the same directory as the target (`live_json.parent`), not in `/tmp` or any other global temp directory. If the temp file is on a different filesystem, `os.replace()` falls back to a non-atomic copy-and-delete, which introduces a window where a concurrent reader could see a partial write.

---

## UI Page (`app/ui/pages/optimizer_page.py`)

### Layout

The page uses a three-pane layout with `QSplitter` for resizability:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ⚡ Strategy Optimizer                           [Start Optimizer]  [Stop]   │
├─────────────────────┬──────────────────────────────┬────────────────────────┤
│  LEFT SIDEBAR       │  CENTER (live data)           │  RIGHT SIDEBAR         │
│  ─────────────────  │  ─────────────────────────── │  ──────────────────── │
│  Strategy: [▼]      │  Trial 12/50  ETA: 00:14:08  │  ★ Best Result         │
│  Timeframe: [▼]     │  ▓▓▓▓▓▓▓▓░░░░░░░░░░░░ 24%   │  Profit:  5.44%        │
│  Timerange: [     ] │  ─────────────────────────── │  DD:      6.0%         │
│  Pairs: [         ] │  [Live log — auto-scrolls]   │  Trades:  87           │
│  Wallet: [        ] │  [stdout/stderr streams here] │  Sharpe:  1.23         │
│  Max Trades: [    ] │                               │  Win Rate: 58%         │
│  ─────────────────  │  ─────────────────────────── │  ──────────────────── │
│  Trials: [50      ] │  # │Params│Profit%│DD%│Score│★│  Selected Trial        │
│  Score: [▼]         │  1 │rsi=14│  3.21%│ 8%│3.21 │ │  Profit:  3.21%        │
│  ─────────────────  │  2 │rsi=18│  5.44%│ 6%│5.44 │★│  DD:      8.0%         │
│  [Sync Backtest]    │  3 │rsi=22│  FAIL │ - │ -   │ │  Trades:  64           │
│  ─────────────────  │  ...                          │  ...                   │
│  Param Table:       │                               │  [Set as Best]         │
│  ☑ buy_rsi  14 5-30 │                               │  [Open Log]            │
│  ☑ sell_rsi 70 50-90│                               │  [Open Result File]    │
│  ☐ stoploss ...     │                               │  [Compare ▼]           │
│  ─────────────────  │                               │                        │
│  [Export Best]      │                               │                        │
│  [Rollback]         │                               │                        │
│  [History ▼]        │                               │                        │
└─────────────────────┴──────────────────────────────┴────────────────────────┘
```

### Visual Theme

The page follows the application's existing dark theme. Trial rows use semantic accent colors:
- **Accepted_Best row**: muted green tint (`#1E3A2F` background, `#4CAF50` star)
- **Failed trial row**: muted red tint (`#3A1E1E` background)
- **Running trial row**: soft blue tint (`#1E2A3A` background)
- **Default row**: standard dark background (`#1E1E1E`)

These colors are applied via `Qt.BackgroundRole` in `TrialTableModel.data()`, not via stylesheets, so they compose correctly with the existing theme.

### Thread Safety

The trial loop runs on a `QThread` (or `threading.Thread`). All UI updates are marshalled back to the Qt main thread via bridge signals, following the same pattern as `BacktestPage`:

```python
# Bridge signals (background thread → Qt main thread)
_sig_log_line      = Signal(str)
_sig_trial_done    = Signal(object)   # TrialRecord
_sig_session_done  = Signal(object)   # OptimizerSession
_sig_trial_start   = Signal(int, dict)
```

The `StrategyOptimizerService` accepts callbacks; the page wires those callbacks to emit the bridge signals.

### TrialTableModel

```python
class TrialTableModel(QAbstractTableModel):
    COLUMNS = ["#", "Params", "Profit %", "DD %", "Score", "★"]

    def append_trial(self, record: TrialRecord) -> None:
        row = len(self._records)
        self.beginInsertRows(QModelIndex(), row, row)
        self._records.append(record)
        self.endInsertRows()

    def update_best(self, old_best: int, new_best: int) -> None:
        # Emit dataChanged only for the two affected rows
        for trial_number in (old_best, new_best):
            idx = self._index_of(trial_number)
            if idx >= 0:
                tl = self.index(idx, self.COLUMNS.index("★"))
                self.dataChanged.emit(tl, tl, [Qt.DisplayRole])
```

### Batched UI Updates

At high trial counts (500–1000+), emitting a signal per log line would saturate the Qt event loop. The page uses a `QTimer` (500 ms interval) to batch-flush pending log lines and trial updates:

```python
# In OptimizerPage.__init__:
self._pending_log_lines: list[str] = []
self._pending_trials: list[TrialRecord] = []
self._flush_timer = QTimer(self)
self._flush_timer.setInterval(500)
self._flush_timer.timeout.connect(self._flush_pending_updates)
self._flush_timer.start()

def _flush_pending_updates(self) -> None:
    if self._pending_log_lines:
        self._log_view.appendPlainText("\n".join(self._pending_log_lines))
        self._pending_log_lines.clear()
    for record in self._pending_trials:
        self._trial_model.append_trial(record)
    self._pending_trials.clear()
```

The bridge signal handlers (`_on_log_line`, `_on_trial_done`) append to the pending lists rather than updating the UI directly. This keeps the GUI thread entirely unburdened during fast trial sequences.

---

## Settings Integration

`OptimizerPreferences` is added to `AppSettings` following the existing pattern:

```python
# In app/core/models/settings_models.py
class AppSettings(BaseModel):
    ...
    optimizer_preferences: OptimizerPreferences = Field(
        default_factory=OptimizerPreferences,
        description="Strategy Optimizer UI preferences",
    )
```

The `Strategy_Optimizer` page reads and writes `optimizer_preferences` via `SettingsService`, and also reads/writes `backtest_preferences` for the shared fields (pairs, timeframe, timerange, wallet, max open trades).

---

## Sidebar and Main Window Integration

`sidebar.py` — add one entry to `_NAV_ITEMS`:
```python
("optimizer", "⚡", "Optimizer"),
```

`main_window.py` — instantiate and register the page:
```python
from app.ui.pages.optimizer_page import OptimizerPage
...
self.optimizer_page = OptimizerPage(self.settings_state, self._process_manager)
self._pages["optimizer"] = self.optimizer_page
self.stack.addWidget(self.optimizer_page)
```

---

## Correctness Properties

### Property 1: Optimizer Score is Always Finite (Requirement 16.4)

For all combinations of score metric name and metrics dict (including empty dicts, dicts with `None` values, dicts with `NaN`/`Inf` values), `compute_optimizer_score()` returns a finite `float`.

**Type:** Property-based test (Hypothesis)
**Test location:** `tests/property/test_optimizer_properties.py`

```python
from hypothesis import given, strategies as st
import math

METRIC_NAMES = ["total_profit_pct", "total_profit_abs", "sharpe_ratio",
                "profit_factor", "win_rate", "unknown_metric"]

@given(
    metric=st.sampled_from(METRIC_NAMES),
    value=st.one_of(
        st.none(),
        st.floats(allow_nan=True, allow_infinity=True),
        st.integers(),
        st.text(max_size=5),
    ),
)
def test_score_always_finite(metric, value):
    metrics = {metric: value}
    score = compute_optimizer_score(metrics, metric)
    assert math.isfinite(score)
```

### Property 2: StrategyParams Round-Trip (Requirement 14.4)

For all valid `StrategyParams` objects, `StrategyParams.from_dict(params.to_dict()) == params`.

**Type:** Property-based test (Hypothesis)
**Test location:** `tests/property/test_optimizer_properties.py`

```python
@given(strategy_params_strategy())
def test_strategy_params_round_trip(params: StrategyParams):
    serialized = params.to_dict()
    restored = StrategyParams.from_dict(serialized)
    assert restored == params
```

### Property 3: Score Metric Consistency (Requirement 13.2–13.6)

For each named metric, when the metrics dict contains a finite float value for that key, `compute_optimizer_score()` returns exactly that value.

**Type:** Example-based test
**Test location:** `tests/core/test_optimizer_score.py`

### Property 4: Empty Metrics Dict Returns Zero (Requirement 13.7, 16.2)

`compute_optimizer_score({}, any_metric)` returns `0.0` for all metric names.

**Type:** Example-based test + property test
**Test location:** `tests/core/test_optimizer_score.py`

### Property 5: Best Pointer Monotonically Increases (Requirement 6.1)

After each trial, if the new trial's score is strictly greater than the current best score, the best pointer is updated; otherwise it is unchanged.

**Type:** Example-based test
**Test location:** `tests/core/test_optimizer_session_service.py`

### Property 6: Trial Records Are Idempotent on Re-Save (Requirement 11.1)

Saving a `TrialRecord` twice produces the same file content as saving it once.

**Type:** Example-based test
**Test location:** `tests/core/test_optimizer_session_service.py`
