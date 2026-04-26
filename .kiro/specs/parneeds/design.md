# Design Document: ParNeeds — Walk-Forward, Monte Carlo, and Parameter Sensitivity Workflows

## Overview

ParNeeds is the validation and robustness-testing workstation in the Freqtrade GUI desktop application. The existing page already delivers a Timerange workflow: it splits a date range into 2-week and 1-month windows, validates candle coverage, auto-downloads missing data, and runs sequential backtests.

This design extends ParNeeds with three new workflows:

- **Walk-Forward** — divides the timerange into in-sample / out-of-sample fold pairs, runs backtests on each, and computes a stability score.
- **Monte Carlo** — runs many backtest iterations with per-iteration random seeds and optional profit noise to estimate the distribution of outcomes.
- **Parameter Sensitivity** — sweeps one or more strategy parameters across a defined range (one-at-a-time or grid) and produces a sweep table plus chart.

All three workflows share the existing UI shell (workflow selector, config panel, terminal, results table), the existing `ProcessRunManager` / `BacktestService` / `ParNeedsService` infrastructure, and the new shared results table and export mechanism introduced by this design.

Key design goals (from `data/rules/product.md`, `data/rules/tech.md`, `data/rules/structure.md`):
- Business logic stays in `app/core/**`; UI orchestration stays in `app/ui/**`.
- Freqtrade runs as a subprocess via the existing `ProcessRunManager` / `BacktestService` wrappers — no ad-hoc process spawning.
- The app must remain useful without any live AI provider.
- Stability across more than one period matters; profit is treated as after-fee profit.

---

## Architecture

### Layer Boundaries

```
app/ui/pages/parneeds_page.py          ← UI orchestration only
    │  uses
    ▼
app/core/services/parneeds_service.py  ← planning, fold/sweep generation, statistics
app/core/services/backtest_service.py  ← command building, result parsing/saving
app/core/services/process_run_manager.py ← subprocess lifecycle
    │  uses
    ▼
app/core/models/parneeds_models.py     ← data models (Pydantic / dataclasses)
```

The page never calls `subprocess` directly. All subprocess work goes through `ProcessRunManager.start_run()` / `stop_run()`. All result parsing goes through `BacktestService.parse_and_save_latest_results()`.

### Thread Safety Pattern (from `optimizer_page.py`)

Background subprocess output arrives on daemon threads. The page uses bridge signals to marshal updates to the Qt main thread, and a `QTimer` (500 ms) to batch-flush pending log lines and result rows — identical to the pattern in `OptimizerPage`.

```
daemon thread (ProcessRunAdapter)
    │  emits bridge signal
    ▼
Qt main thread slot
    │  appends to pending buffer
    ▼
QTimer.timeout → _flush_pending_updates()
    │  writes to TerminalWidget / results table
```

### Workflow State Machine

Each workflow follows the same high-level state machine:

```
idle → coverage_check → [download →] running → done
                                              ↘ failed
                                              ↘ stopped
```

The `_phase` string attribute on `ParNeedsPage` tracks the current phase. The `_workflow` attribute tracks which workflow is active. The `_running` boolean gates the Start button.

---

## Components and Interfaces

### `ParNeedsService` — new methods

```python
# Walk-Forward
def generate_walk_forward_folds(
    self,
    config: WalkForwardConfig,
) -> list[WalkForwardFold]: ...

def compute_stability_score(
    self,
    oos_profits: list[float],
) -> float: ...

# Monte Carlo
def generate_mc_seed(self, base_seed: int, iteration_index: int) -> int: ...

def apply_profit_noise(
    self,
    profit: float,
    seed: int,
    noise_pct: float = 0.02,
) -> float: ...

def compute_mc_percentiles(
    self,
    values: list[float],
) -> MCPercentiles: ...

# Parameter Sensitivity
def discover_strategy_parameters(
    self,
    strategy_path: Path,
) -> list[SweepParameterDef]: ...

def generate_oat_sweep_points(
    self,
    params: list[SweepParameterDef],
    baseline: dict[str, Any],
) -> list[SweepPoint]: ...

def generate_grid_sweep_points(
    self,
    params: list[SweepParameterDef],
    baseline: dict[str, Any],
) -> list[SweepPoint]: ...

# Export
def export_results(
    self,
    results: list[ParNeedsRunResult],
    workflow: str,
    export_dir: Path,
) -> tuple[Path, Path]: ...
```

### `ParNeedsPage` — structural changes

The existing two-pane layout (config panel | terminal + results table) is extended to a three-pane layout matching `OptimizerPage`:

```
┌─────────────────┬──────────────────────────────┬──────────────────┐
│  Left sidebar   │       Center pane            │  Right sidebar   │
│  (config panel) │  Terminal (top)              │  Summary stats   │
│  Workflow combo │  Results table (bottom)      │  Chart widget    │
│  Shared fields  │                              │  Export button   │
│  WF-specific    │                              │                  │
│  fields         │                              │                  │
└─────────────────┴──────────────────────────────┴──────────────────┘
```

The left sidebar hosts:
- Workflow combo (all four workflows)
- Shared config fields (strategy, timeframe, timerange, pairs, wallet, max trades, seed)
- A `QStackedWidget` of workflow-specific config panels (one per workflow, hidden when not active)

The center pane hosts:
- `TerminalWidget` (top, stretch 2)
- Shared results `QTableWidget` (bottom, stretch 1)

The right sidebar hosts:
- Workflow summary section (stability score for WF, percentile table for MC, best sweep point for PS)
- Chart widget (`QLabel` placeholder backed by `matplotlib` figure embedded via `FigureCanvasQTAgg`, or a simple `QTableWidget` for the percentile table)
- Export button

### Workflow-Specific Config Panels (QStackedWidget)

Each panel is a `QFrame` with a `QFormLayout`:

**Walk-Forward panel**
- `_wf_folds_spin`: QSpinBox, range 2–20, default 5
- `_wf_split_spin`: QSpinBox (%), range 50–95, default 80
- `_wf_mode_combo`: QComboBox ["anchored", "rolling"], default "anchored"

**Monte Carlo panel**
- `_mc_iterations_spin`: QSpinBox, range 10–5000, default 500
- `_mc_randomise_chk`: QCheckBox "Randomise trade order", default checked
- `_mc_noise_chk`: QCheckBox "Profit noise (±2%)", default checked
- `_mc_max_dd_spin`: QDoubleSpinBox (%), range 1–100, default 20

**Parameter Sensitivity panel**
- `_ps_mode_combo`: QComboBox ["One-at-a-time", "Grid"], default "One-at-a-time"
- `_ps_param_table`: QTableWidget — columns: Enabled, Name, Type, Min, Max, Step/Values
- `_ps_discover_btn`: QPushButton "Discover Parameters"

### Bridge Signals (new)

```python
_sig_stdout   = Signal(str)   # existing
_sig_stderr   = Signal(str)   # existing
_sig_finished = Signal(int)   # existing
_sig_result   = Signal(object)  # ParNeedsRunResult — new, for batched table updates
```

### `ProcessRunAdapter`

Unchanged. The page creates one adapter per subprocess run, connects its signals to the bridge signals, and discards it when the run finishes.

---

## Data Models

### New models in `parneeds_models.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional
from enum import Enum


class WalkForwardMode(str, Enum):
    ANCHORED = "anchored"
    ROLLING  = "rolling"


@dataclass(frozen=True)
class WalkForwardConfig:
    """Configuration for one Walk-Forward run."""
    strategy: str
    timeframe: str
    timerange: str          # normalised YYYYMMDD-YYYYMMDD
    pairs: list[str]
    dry_run_wallet: float
    max_open_trades: int
    n_folds: int = 5
    split_ratio: float = 0.80   # fraction of each fold that is in-sample
    mode: WalkForwardMode = WalkForwardMode.ANCHORED


@dataclass(frozen=True)
class WalkForwardFold:
    """One in-sample / out-of-sample fold pair."""
    fold_index: int          # 1-based
    is_timerange: str        # in-sample YYYYMMDD-YYYYMMDD
    oos_timerange: str       # out-of-sample YYYYMMDD-YYYYMMDD
    is_start: date
    is_end: date
    oos_start: date
    oos_end: date


@dataclass
class WalkForwardFoldResult:
    """Mutable result for one fold (populated as backtests complete)."""
    fold: WalkForwardFold
    is_run_id: str = ""
    oos_run_id: str = ""
    is_profit_pct: Optional[float] = None
    oos_profit_pct: Optional[float] = None
    win_rate_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    trades_count: Optional[int] = None
    status: str = "pending"   # pending | running | completed | failed


@dataclass(frozen=True)
class MonteCarloConfig:
    """Configuration for one Monte Carlo run."""
    strategy: str
    timeframe: str
    timerange: str
    pairs: list[str]
    dry_run_wallet: float
    max_open_trades: int
    n_iterations: int = 500
    randomise_trade_order: bool = True
    profit_noise: bool = True
    max_drawdown_threshold_pct: float = 20.0
    base_seed: int = 20240101


@dataclass(frozen=True)
class MCPercentiles:
    """Percentile summary for one metric across Monte Carlo iterations."""
    p5: float
    p50: float
    p95: float


@dataclass(frozen=True)
class MCSummary:
    """Aggregate statistics for a completed Monte Carlo run."""
    profit_percentiles: MCPercentiles
    drawdown_percentiles: MCPercentiles
    win_rate_percentiles: MCPercentiles
    trades_percentiles: MCPercentiles
    probability_of_profit: float        # fraction of iterations with profit > 0
    probability_exceed_max_dd: float    # fraction of iterations exceeding threshold


class SweepParamType(str, Enum):
    INT         = "int"
    DECIMAL     = "decimal"
    CATEGORICAL = "categorical"
    BOOLEAN     = "boolean"
    FIXED       = "fixed"   # built-in backtest params (stoploss, roi, etc.)


@dataclass
class SweepParameterDef:
    """Definition of one sweepable parameter."""
    name: str
    param_type: SweepParamType
    default_value: Any
    # For numeric params
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    # For categorical/boolean params
    values: list[Any] = field(default_factory=list)
    enabled: bool = False   # user must opt-in


@dataclass(frozen=True)
class SweepPoint:
    """One combination of parameter values to test."""
    index: int
    param_overrides: dict[str, Any]   # param_name → value
    label: str                         # human-readable summary


@dataclass
class SweepPointResult:
    """Mutable result for one sweep point."""
    point: SweepPoint
    run_id: str = ""
    profit_pct: Optional[float] = None
    win_rate_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    trades_count: Optional[int] = None
    status: str = "pending"


# Extended shared result row (replaces the existing ParNeedsRunResult)
@dataclass(frozen=True)
class ParNeedsRunResult:
    """Displayable result row for the shared results table."""
    run_trial: str                      # e.g. "Fold 1 OOS", "Iter 42", "Sweep 7"
    workflow: str                       # "timerange" | "walk_forward" | "monte_carlo" | "param_sensitivity"
    strategy: str = ""
    pairs: str = ""                     # comma-joined
    timeframe: str = ""
    timerange: str = ""
    profit_pct: Optional[float] = None
    total_profit: Optional[float] = None
    win_rate: Optional[float] = None
    max_dd_pct: Optional[float] = None
    trades: Optional[int] = None
    profit_factor: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    score: Optional[float] = None       # stability score (WF) or None
    status: str = ""
    result_path: str = ""
    log_path: str = ""
```

### Updated `ParNeedsConfig`

`ParNeedsConfig` is unchanged — it continues to serve the Timerange workflow. The new workflows use their own typed config dataclasses (`WalkForwardConfig`, `MonteCarloConfig`, and a `ParameterSensitivityConfig` that wraps `SweepParameterDef` list).

---

## Data Flow

### Walk-Forward Workflow

```
User clicks Start
    │
    ▼
build_wf_config()
    │
    ▼
ParNeedsService.generate_walk_forward_folds(config)
    │  → list[WalkForwardFold]  (or ValueError if too short)
    │
    ▼
Display fold schedule in TerminalWidget
    │
    ▼
validate_candle_coverage() [full timerange]
    │  gaps? → queue_downloads() → start_next_download()
    │  ok?   → start_next_fold_backtest()
    │
    ▼
For each fold (IS then OOS):
    BacktestService.build_command(timerange=fold.is_timerange / fold.oos_timerange)
    ProcessRunManager.start_run(cmd)
    ProcessRunAdapter → bridge signals → TerminalWidget
    _handle_finished(exit_code)
        exit_code == 0 → BacktestService.parse_and_save_latest_results()
                       → WalkForwardFoldResult updated
                       → _append_result_row()
                       → run_completed.emit(run_id)
        exit_code != 0 → fold marked failed, continue
    │
    ▼
All folds done:
    ParNeedsService.compute_stability_score(oos_profits)
    Display summary in right sidebar
```

### Monte Carlo Workflow

```
User clicks Start
    │
    ▼
build_mc_config()
    │
    ▼
validate_candle_coverage() [once, full timerange]
    │  gaps? → queue_downloads()
    │  ok?   → start_next_mc_iteration()
    │
    ▼
For each iteration i in range(n_iterations):
    seed_i = ParNeedsService.generate_mc_seed(base_seed, i)
    BacktestService.build_command(timerange=config.timerange, extra_flags=["--random-state", str(seed_i)])
    ProcessRunManager.start_run(cmd)
    _handle_finished(exit_code)
        exit_code == 0 → parse result
                       → if profit_noise: apply_profit_noise(profit, seed_i)
                       → _append_result_row()
                       → run_completed.emit(run_id)
        exit_code != 0 → iteration marked failed, continue
    │
    ▼
All iterations done:
    ParNeedsService.compute_mc_percentiles(profits)
    Display MCSummary in right sidebar
    Show distribution histogram
```

### Parameter Sensitivity Workflow

```
User selects strategy → ParNeedsService.discover_strategy_parameters(strategy_path)
    │  → list[SweepParameterDef]
    │
User enables parameters, sets ranges
    │
User clicks Start
    │
    ▼
build_ps_config()
    │
    ▼
validate_candle_coverage() [full timerange]
    │  gaps? → queue_downloads()
    │  ok?   → generate sweep points
    │
    ▼
mode == OAT → ParNeedsService.generate_oat_sweep_points(params, baseline)
mode == Grid → ParNeedsService.generate_grid_sweep_points(params, baseline)
    │  → list[SweepPoint]
    │  Grid > 200 points? → confirmation dialog
    │
    ▼
For each sweep point:
    BacktestService.build_command(..., extra_flags=point.to_freqtrade_flags())
    ProcessRunManager.start_run(cmd)
    _handle_finished(exit_code)
        exit_code == 0 → parse result → _append_result_row() → run_completed.emit()
        exit_code != 0 → point marked failed, continue
    │
    ▼
All points done:
    Highlight best row
    Display chart (line for 1 param, heatmap for 2+ params)
```

### Export Flow

```
User clicks Export (enabled when results table has ≥ 1 row)
    │
    ▼
ParNeedsService.export_results(results, workflow, export_dir)
    │  → writes parneeds_{workflow}_{timestamp}.json
    │  → writes parneeds_{workflow}_{timestamp}.csv
    │  → returns (json_path, csv_path)
    │
    ▼
TerminalWidget.append_info(f"Exported to {json_path} and {csv_path}")
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Walk-Forward fold count

*For any* valid timerange and fold count `n` (2–20), `generate_walk_forward_folds` SHALL return exactly `n` folds when the timerange is long enough, and SHALL raise a `ValueError` when the timerange is too short to produce `n` folds with the configured split ratio.

**Validates: Requirements 1.1, 1.5**

---

### Property 2: Anchored mode — start date invariant

*For any* walk-forward config in anchored mode, every fold's in-sample start date SHALL equal the global timerange start date.

**Validates: Requirements 1.2**

---

### Property 3: Rolling mode — fixed step invariant

*For any* walk-forward config in rolling mode with `n` folds, the in-sample start date of fold `i+1` SHALL equal the in-sample start date of fold `i` plus the fold step duration, for all `i` in `[1, n-1]`.

**Validates: Requirements 1.3**

---

### Property 4: Split ratio invariant

*For any* walk-forward fold, the ratio `is_days / (is_days + oos_days)` SHALL be within 1 day's tolerance of the configured split ratio.

**Validates: Requirements 1.4**

---

### Property 5: Stability score is bounded

*For any* list of OOS profit values (including empty lists, all-positive, all-negative, and mixed), `compute_stability_score` SHALL return a value in the closed interval `[0, 100]`.

**Validates: Requirements 3.2**

---

### Property 6: Monte Carlo seed determinism and uniqueness

*For any* base seed and two distinct iteration indices `i ≠ j`, `generate_mc_seed(base_seed, i) == generate_mc_seed(base_seed, i)` (same call always returns the same value), and `generate_mc_seed(base_seed, i) != generate_mc_seed(base_seed, j)` (different indices produce different seeds).

**Validates: Requirements 5.2**

---

### Property 7: Profit noise stays within bounds

*For any* profit value `p` and any seed, `apply_profit_noise(p, seed, noise_pct=0.02)` SHALL return a value `p_noisy` such that `|p_noisy - p| <= |p| * 0.02`.

**Validates: Requirements 5.4**

---

### Property 8: Percentile ordering invariant

*For any* non-empty list of float values, `compute_mc_percentiles` SHALL return `MCPercentiles` where `p5 <= p50 <= p95`, and the `probability_of_profit` computed from the same list SHALL be in `[0.0, 1.0]`.

**Validates: Requirements 6.3**

---

### Property 9: OAT sweep point count

*For any* set of enabled sweep parameters with defined ranges in One-At-A-Time mode, `generate_oat_sweep_points` SHALL return exactly `sum(len(range(p)) for p in params)` sweep points.

**Validates: Requirements 9.1**

---

### Property 10: Grid sweep point count

*For any* set of enabled sweep parameters with defined ranges in Grid mode, `generate_grid_sweep_points` SHALL return exactly `product(len(range(p)) for p in params)` sweep points (the Cartesian product).

**Validates: Requirements 9.2**

---

### Property 11: Missing field formatting

*For any* `ParNeedsRunResult` where an optional numeric field is `None`, the formatted cell value produced by the results table formatter SHALL be `"-"`.

**Validates: Requirements 12.2**

---

### Property 12: Export filename pattern

*For any* workflow name string and timestamp, the filenames generated by `export_results` SHALL match the patterns `parneeds_{workflow}_{timestamp}.json` and `parneeds_{workflow}_{timestamp}.csv`.

**Validates: Requirements 13.4**

---

## Error Handling

### Validation errors (before run starts)

| Condition | Handling |
|---|---|
| Strategy not selected | `ValueError` surfaced to `TerminalWidget` via `append_info(..., RED)` |
| Timerange too short for requested folds | `ValueError` from `generate_walk_forward_folds`; displayed in terminal; run does not start |
| No pairs configured | `ValueError`; displayed in terminal |
| Grid sweep > 200 points | `QMessageBox` confirmation dialog; run blocked until confirmed |
| No sweepable parameters found | Informational message in terminal; Start button disabled |

### Runtime errors (during run)

| Condition | Handling |
|---|---|
| Subprocess non-zero exit | Record as failed; log exit code to terminal; continue with next window/fold/iteration/point |
| Coverage check exception | Log to terminal; set status "failed"; stop run |
| Result parse failure | Log warning; record row with status "parse failed"; continue |
| Export write failure | Log descriptive error to terminal; do not crash |
| Settings not configured | `ValueError` surfaced to terminal before any subprocess is started |

All error paths use `_terminal.append_info(msg, theme.RED)` and `_terminal.set_status("failed", theme.RED)`. No bare `except Exception: pass` blocks — all exceptions are caught, logged via `_log.warning` / `_log.error`, and surfaced to the user.

---

## Testing Strategy

### Unit tests (`tests/core/services/test_parneeds_service.py`)

Focus on pure functions in `ParNeedsService`:

- `generate_walk_forward_folds` — fold count, anchored invariant, rolling step invariant, split ratio, error on short range
- `compute_stability_score` — bounded output, monotonicity
- `generate_mc_seed` — determinism, uniqueness
- `apply_profit_noise` — bounds
- `compute_mc_percentiles` — ordering, probability bounds
- `generate_oat_sweep_points` — count
- `generate_grid_sweep_points` — count (Cartesian product)
- `export_results` — filename pattern (with `tmp_path` fixture)

### Property-based tests (`tests/core/services/test_parneeds_service_pbt.py`)

Using **Hypothesis** (already present in the project, see `.hypothesis/` directory).

Each property test runs a minimum of 100 iterations. Tests are tagged with a comment referencing the design property.

```python
# Feature: parneeds, Property 1: Walk-Forward fold count
@given(
    start=dates(min_value=date(2020, 1, 1), max_value=date(2024, 1, 1)),
    span_days=integers(min_value=30, max_value=1000),
    n_folds=integers(min_value=2, max_value=20),
    split_ratio=floats(min_value=0.5, max_value=0.95),
)
@settings(max_examples=200)
def test_fold_count_property(start, span_days, n_folds, split_ratio): ...

# Feature: parneeds, Property 2: Anchored mode start date invariant
@given(wf_config=walk_forward_configs(mode=WalkForwardMode.ANCHORED))
@settings(max_examples=200)
def test_anchored_start_invariant(wf_config): ...

# Feature: parneeds, Property 3: Rolling mode fixed step invariant
@given(wf_config=walk_forward_configs(mode=WalkForwardMode.ROLLING))
@settings(max_examples=200)
def test_rolling_step_invariant(wf_config): ...

# Feature: parneeds, Property 4: Split ratio invariant
@given(wf_config=walk_forward_configs())
@settings(max_examples=200)
def test_split_ratio_invariant(wf_config): ...

# Feature: parneeds, Property 5: Stability score bounded
@given(oos_profits=lists(floats(allow_nan=False, allow_infinity=False), min_size=0, max_size=50))
@settings(max_examples=500)
def test_stability_score_bounded(oos_profits): ...

# Feature: parneeds, Property 6: MC seed determinism and uniqueness
@given(
    base_seed=integers(min_value=1, max_value=2**31 - 1),
    indices=lists(integers(min_value=0, max_value=9999), min_size=2, max_size=100, unique=True),
)
@settings(max_examples=200)
def test_mc_seed_determinism_and_uniqueness(base_seed, indices): ...

# Feature: parneeds, Property 7: Profit noise within bounds
@given(
    profit=floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    seed=integers(min_value=0, max_value=2**31 - 1),
)
@settings(max_examples=500)
def test_profit_noise_bounds(profit, seed): ...

# Feature: parneeds, Property 8: Percentile ordering
@given(values=lists(floats(allow_nan=False, allow_infinity=False), min_size=1, max_size=1000))
@settings(max_examples=300)
def test_percentile_ordering(values): ...

# Feature: parneeds, Property 9: OAT sweep point count
@given(param_configs=oat_param_configs())
@settings(max_examples=200)
def test_oat_sweep_count(param_configs): ...

# Feature: parneeds, Property 10: Grid sweep point count
@given(param_configs=grid_param_configs())
@settings(max_examples=200)
def test_grid_sweep_count(param_configs): ...

# Feature: parneeds, Property 11: Missing field formatting
@given(result=parneeds_run_results_with_missing_fields())
@settings(max_examples=300)
def test_missing_field_formatting(result): ...

# Feature: parneeds, Property 12: Export filename pattern
@given(
    workflow=sampled_from(["timerange", "walk_forward", "monte_carlo", "param_sensitivity"]),
    timestamp=datetimes(min_value=datetime(2020, 1, 1)),
)
@settings(max_examples=200)
def test_export_filename_pattern(workflow, timestamp, tmp_path): ...
```

### Integration tests (`tests/ui/pages/test_parneeds_page_integration.py`)

Using `pytest-qt` with mocked `ProcessRunManager` and `BacktestService`:

- Walk-Forward: verify subprocess call sequence (IS then OOS per fold), verify `run_completed` signal count
- Monte Carlo: verify coverage check called exactly once, verify iteration count matches config
- Parameter Sensitivity: verify coverage check called before sweep, verify sweep point count matches generated list
- Export: verify JSON and CSV files written to `tmp_path` with correct filenames
- Stop: verify `ProcessRunManager.stop_run` called when Stop button clicked

### Example-based unit tests (`tests/ui/pages/test_parneeds_page_unit.py`)

- Workflow selector shows/hides correct config panels
- Walk-Forward config panel fields present and have correct defaults
- Monte Carlo config panel fields present and have correct defaults
- Parameter Sensitivity config panel fields present and have correct defaults
- Grid > 200 points shows confirmation dialog
- No parameters found disables Start button
- Results table has correct column headers
- Export button disabled when table is empty, enabled when table has rows
- Fold row colour-coding (green for positive OOS profit, red for negative)
- Best sweep point row highlighted
