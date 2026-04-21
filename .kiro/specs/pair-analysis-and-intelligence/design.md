# Design Document — Pair Analysis and Intelligence

## Overview

This feature adds five layers of intelligence to the Freqtrade GUI:

1. **Pair Analysis** — `PairAnalysisService` + `PairAnalysis`/`PairMetrics` dataclasses + Pair Results tab
2. **Diagnosis Service** — `DiagnosisService` + `DiagnosisSuggestion` dataclass (rule-based, distinct from `ResultsDiagnosisService`)
3. **Comparison Engine** — `ComparisonService` + `RunComparison` dataclass + Comparison tab
4. **Improve Flow Hardening** — deterministic `sandbox/{version_id}/` paths in `ImproveService`
5. **GUI Layout Unification** — `BacktestPage` tab order, single `load_results()`, `LoopPage` step-gating

All new code follows the existing layered architecture: UI → State → Service → Model → Infra. Services never import UI code. New DTOs use `@dataclass`.

---

## Architecture

### Layer Placement

```
app/core/backtests/
    results_models.py          ← add PairMetrics, PairAnalysis, RunComparison (new dataclasses)

app/core/models/
    analysis_models.py         ← new: DiagnosisSuggestion dataclass

app/core/services/
    pair_analysis_service.py   ← new: PairAnalysisService (stateless)
    diagnosis_service.py       ← new: DiagnosisService (stateless, distinct from ResultsDiagnosisService)
    comparison_service.py      ← new: ComparisonService (stateless)
    improve_service.py         ← modify: prepare_sandbox() + build_candidate_command()

app/ui_v2/pages/
    backtest_page.py           ← modify: add Pair Results tab, Comparison tab, load_results()

app/ui/pages/
    loop_page.py               ← modify: step-gating on UI controls
```

### Data Flow

```
BacktestResults
    │
    ├─► PairAnalysisService.analyse(results)
    │       └─► PairAnalysis { pair_metrics, best_pairs, worst_pairs, dominance_flags }
    │               │
    │               ├─► PairResultsTab (display)
    │               └─► DiagnosisService.diagnose(pair_analysis, summary)
    │                       └─► List[DiagnosisSuggestion]
    │
    └─► ComparisonService.compare(summary_a, summary_b)
            └─► RunComparison { profit_diff, winrate_diff, drawdown_diff, verdict }
                    └─► ComparisonTab (display)
```

---

## New Dataclasses

### `app/core/backtests/results_models.py` — additions

```python
@dataclass
class PairMetrics:
    """Per-pair computed statistics for one backtest run."""
    pair: str
    total_profit_pct: float   # sum of BacktestTrade.profit for this pair
    win_rate: float           # wins / total_trades * 100
    trade_count: int
    max_drawdown_pct: float   # most negative single-trade profit; 0.0 if no losses
    profit_share: float       # total_profit_pct / abs_sum_all_pairs; 0.0 when total=0


@dataclass
class PairAnalysis:
    """Full output of PairAnalysisService for one run."""
    pair_metrics: List[PairMetrics]
    best_pairs: List[PairMetrics]       # up to 3, highest total_profit_pct desc
    worst_pairs: List[PairMetrics]      # up to 3, lowest total_profit_pct asc
    dominance_flags: List[str]          # e.g. ["profit_concentration"]


@dataclass
class RunComparison:
    """Diff between two backtest runs (run_b relative to run_a)."""
    profit_diff: float      # run_b.total_profit - run_a.total_profit
    winrate_diff: float     # run_b.win_rate - run_a.win_rate
    drawdown_diff: float    # run_b.max_drawdown - run_a.max_drawdown (positive = worse)
    verdict: str            # "improved" | "degraded" | "neutral"
```

### `app/core/models/analysis_models.py` — new file

```python
@dataclass
class DiagnosisSuggestion:
    """One actionable suggestion from DiagnosisService."""
    rule_id: str       # e.g. "entry_too_aggressive"
    message: str       # human-readable explanation
    severity: str      # "critical" | "warning"
```

---

## New Services

### `PairAnalysisService` — `app/core/services/pair_analysis_service.py`

Stateless. All methods are `@staticmethod`.

```python
class PairAnalysisService:

    @staticmethod
    def analyse(results: BacktestResults) -> PairAnalysis:
        """Derive PairAnalysis from a BacktestResults object.

        Args:
            results: BacktestResults containing trades list.

        Returns:
            PairAnalysis with per-pair metrics, best/worst pairs, and
            dominance flags.
        """
```

**Algorithm:**

1. If `results.trades` is empty → return `PairAnalysis([], [], [], [])`.
2. Group trades by `trade.pair`.
3. For each group compute `PairMetrics`:
   - `total_profit_pct` = `sum(t.profit for t in group)`
   - `win_rate` = `len([t for t in group if t.profit > 0]) / len(group) * 100`
   - `trade_count` = `len(group)`
   - `max_drawdown_pct` = `abs(min((t.profit for t in group if t.profit < 0), default=0.0))`
   - `profit_share` deferred until all pairs computed
4. Compute `abs_total = sum(abs(pm.total_profit_pct) for pm in all_metrics)`.
5. Set `profit_share = pm.total_profit_pct / abs_total` for each metric (0.0 when `abs_total == 0`).
6. `best_pairs` = top 3 by `total_profit_pct` descending.
7. `worst_pairs` = bottom 3 by `total_profit_pct` ascending.
8. `dominance_flags` = `["profit_concentration"]` if any single `profit_share > 0.60`, else `[]`.

**Correctness property (PBT):**
- `sum(pm.trade_count for pm in analysis.pair_metrics) == len(results.trades)` for all valid inputs.

---

### `DiagnosisService` — `app/core/services/diagnosis_service.py`

Stateless. All methods are `@staticmethod`. Distinct from `ResultsDiagnosisService` (which operates on `DiagnosisInput` bundles for the Strategy Lab loop).

```python
class DiagnosisService:

    @staticmethod
    def diagnose(
        pair_analysis: PairAnalysis,
        summary: BacktestSummary,
    ) -> List[DiagnosisSuggestion]:
        """Apply logic-based rules and return actionable suggestions.

        Args:
            pair_analysis: Output of PairAnalysisService.analyse().
            summary: Aggregate run-level metrics.

        Returns:
            List of DiagnosisSuggestion objects; empty list when no rules fire.
        """
```

**Rules (evaluated independently, all matching rules included):**

| Condition | `rule_id` | `severity` | `message` |
|---|---|---|---|
| `summary.win_rate < 30.0` | `entry_too_aggressive` | `critical` | "Win rate is {win_rate:.1f}% — entry conditions may be too aggressive." |
| `summary.max_drawdown > 40.0` | `stoploss_too_loose` | `critical` | "Max drawdown is {drawdown:.1f}% — stoploss may be too loose." |
| `"profit_concentration" in pair_analysis.dominance_flags` | `overfitting_risk` | `warning` | "One pair dominates profit — strategy may be overfit to a single asset." |
| `summary.total_trades < 30` | `insufficient_trades` | `warning` | "Only {trades} trades — results may not be statistically significant." |
| `0.0 < summary.profit_factor < 1.0` | `negative_expectancy` | `critical` | "Profit factor is {pf:.2f} — strategy has negative expectancy." |

---

### `ComparisonService` — `app/core/services/comparison_service.py`

Stateless. All methods are `@staticmethod`.

```python
class ComparisonService:

    @staticmethod
    def compare(run_a: BacktestSummary, run_b: BacktestSummary) -> RunComparison:
        """Compute a RunComparison between two backtest summaries.

        run_b is treated as the candidate; run_a as the baseline.

        Args:
            run_a: Baseline BacktestSummary.
            run_b: Candidate BacktestSummary.

        Returns:
            RunComparison with diffs and verdict.
        """
```

**Verdict logic (evaluated in order, first match wins):**

1. `profit_diff > 0.0 AND drawdown_diff <= 0.0` → `"improved"`
2. `profit_diff < 0.0 OR drawdown_diff > 5.0` → `"degraded"`
3. Otherwise → `"neutral"`

**Correctness property (PBT):**
- `compare(a, b).profit_diff == -compare(b, a).profit_diff` for all valid inputs.

---

## Modified Services

### `ImproveService.prepare_sandbox()` — deterministic paths

**Current behaviour:** uses `{strategy_name}_{timestamp_ms}` as the sandbox directory name. Export directory uses a separate timestamp in `build_candidate_command()`. No strict run↔version_id mapping.

**New behaviour:**

`prepare_sandbox()` gains a required `version_id: str` parameter:

```python
def prepare_sandbox(
    self,
    strategy_name: str,
    candidate_config: dict,
    version_id: str,
) -> Path:
    """Create an isolated sandbox directory keyed on version_id.

    Args:
        strategy_name: Strategy class name.
        candidate_config: Candidate parameter dict.
        version_id: Canonical identifier for this candidate (from versioning system).

    Returns:
        Path to sandbox/{version_id}/ directory.

    Raises:
        FileNotFoundError: If the strategy .py file does not exist.
        ValueError: If sandbox/{version_id}/ already exists (collision guard).
    """
```

- Sandbox path: `{user_data}/strategies/_improve_sandbox/{version_id}/`
- If the directory already exists → raise `ValueError(f"Sandbox collision: version_id '{version_id}' already exists at {sandbox_dir}")`
- Config file written as `{version_id}.json` inside the sandbox directory (not `{strategy_name}.json`)

`build_candidate_command()` gains a `version_id: str` parameter:

```python
def build_candidate_command(
    self,
    strategy_name: str,
    baseline: BacktestResults,
    sandbox_dir: Path,
    version_id: str,
) -> Tuple[BacktestRunCommand, Path]:
```

- Export directory: `{user_data}/backtest_results/_improve/{version_id}/`
- No directory scanning in `parse_candidate_run()` — path constructed as `export_dir / f"{version_id}.zip"` first; falls back to `resolve_candidate_artifact(export_dir)` only if the deterministic path does not exist.

**Callers to update:** `LoopPage` and `ImprovePage` (wherever `prepare_sandbox()` and `build_candidate_command()` are called) must pass a `version_id`. The versioning system already assigns a `version_id` per candidate; callers should use that value. If no versioning system is active, callers generate `version_id = f"{strategy_name}_{int(time.time() * 1000)}"` as a fallback.

---

## Modified UI

### `BacktestPage` — `app/ui_v2/pages/backtest_page.py`

#### Tab order

The right-panel `QTabWidget` (`_output_tabs`) gains two new tabs:

```
Index 0: Results    (existing BacktestResultsWidget)
Index 1: Pair Results  (new PairResultsWidget)
Index 2: Compare    (new CompareWidget)
Index 3: Terminal   (existing TerminalWidget)
```

#### Single `load_results()` entry point

A new public method replaces the scattered per-tab load calls:

```python
def load_results(self, results: BacktestResults) -> None:
    """Populate all result tabs from a single BacktestResults object.

    Calls:
        _results_widget.display_results(results)
        _pair_results_widget.display(PairAnalysisService.analyse(results))
        Navigates to Results tab (index 0).

    Args:
        results: BacktestResults from a completed or loaded run.
    """
```

All existing call sites (`_try_load_results`, `_on_load_run`) are updated to call `load_results()` instead of calling `_results_widget.display_results()` directly.

After a run completes successfully, `load_results()` is called and the page navigates to tab index 0 (Summary/Results).

#### `PairResultsWidget` — new widget

Location: `app/ui_v2/widgets/pair_results_widget.py`

```python
class PairResultsWidget(QWidget):
    """Displays PairAnalysis output in a table with best/worst highlighting."""

    def display(self, analysis: PairAnalysis) -> None:
        """Populate the table from a PairAnalysis object.

        Args:
            analysis: Output of PairAnalysisService.analyse().
        """

    def clear(self) -> None:
        """Reset to empty state with placeholder message."""
```

**Table columns:** Pair | Profit (%) | Win Rate (%) | Trades | Max Drawdown (%)

**Row styling (single shared stylesheet constant `_PAIR_TABLE_STYLES`):**
- Best pair rows: `background-color: rgba(0, 180, 0, 0.15)` + bold font
- Worst pair rows: `background-color: rgba(220, 0, 0, 0.15)` + italic font
- Normal rows: no override

**Concentration warning:** a `QLabel` above the table, hidden by default. Shown (with warning text) when `"profit_concentration" in analysis.dominance_flags`.

**Empty state:** when `analysis` is `None` or `analysis.pair_metrics` is empty, show a centred `QLabel("No pair data available.")`.

**No service imports in this widget** — receives `PairAnalysis` objects only.

#### `CompareWidget` — new widget

Location: `app/ui_v2/widgets/compare_widget.py`

```python
class CompareWidget(QWidget):
    """Side-by-side run comparison with colour-coded diffs."""

    def set_run_choices(self, runs: List[dict]) -> None:
        """Populate both run selector combos from a list of run metadata dicts."""

    def display(self, comparison: RunComparison) -> None:
        """Render the comparison result with green/red colouring."""
```

**Layout:**
- Two `QComboBox` selectors (Run A, Run B) + "Compare" button
- Three metric rows: Profit diff | Win Rate diff | Drawdown diff
  - Positive profit diff → green; negative → red
  - Negative drawdown diff (improvement) → green; positive → red
  - Positive winrate diff → green; negative → red
- Verdict label: green for `"improved"`, red for `"degraded"`, neutral (`#aaa`) for `"neutral"`
- When fewer than two runs selected: centred prompt label

**Colour constants (shared, defined once at module level):**
```python
_GREEN = "color: #4caf50;"
_RED   = "color: #f44336;"
_NEUTRAL = "color: #aaa;"
```

**Wiring in `BacktestPage`:** after `_refresh_run_picker()`, call `_compare_widget.set_run_choices(runs)`. The "Compare" button calls `ComparisonService.compare(summary_a, summary_b)` and passes the result to `_compare_widget.display()`.

---

### `LoopPage` — `app/ui/pages/loop_page.py`

#### Step-gating

The Strategy Lab enforces a linear flow. Controls for later steps are disabled until the preceding step completes.

**Steps and their gate conditions:**

| Step | Controls enabled when |
|---|---|
| 1. Run | Always enabled |
| 2. Results | After baseline run completes (`_baseline_results` is not None) |
| 3. Problems | After results loaded (same gate as step 2) |
| 4. Improve | After diagnosis shown (user has seen suggestions) |
| 5. Preview | After candidate config generated |
| 6. Run Candidate | After preview shown |
| 7. Compare | After candidate run completes |
| 8. Accept / Reject | After comparison shown |

**Implementation:** a private `_update_step_gates()` method checks the current state and calls `setEnabled(True/False)` on each control group. Called after every state transition (run complete, diagnosis shown, candidate generated, etc.).

---

## Property-Based Tests

### `test_pair_analysis_properties.py`

```python
@given(st.lists(backtest_trade_strategy(), min_size=1))
def test_trade_count_invariant(trades):
    """sum(pm.trade_count) == len(trades) for all valid inputs."""
    results = BacktestResults(summary=..., trades=trades)
    analysis = PairAnalysisService.analyse(results)
    assert sum(pm.trade_count for pm in analysis.pair_metrics) == len(trades)

@given(st.lists(backtest_trade_strategy(), min_size=0, max_size=0))
def test_empty_trades_returns_empty_analysis(trades):
    """Empty trades → all lists empty, no flags."""
    results = BacktestResults(summary=..., trades=trades)
    analysis = PairAnalysisService.analyse(results)
    assert analysis.pair_metrics == []
    assert analysis.best_pairs == []
    assert analysis.worst_pairs == []
    assert analysis.dominance_flags == []
```

### `test_comparison_properties.py`

```python
@given(backtest_summary_strategy(), backtest_summary_strategy())
def test_profit_diff_antisymmetry(summary_a, summary_b):
    """compare(a, b).profit_diff == -compare(b, a).profit_diff."""
    ab = ComparisonService.compare(summary_a, summary_b)
    ba = ComparisonService.compare(summary_b, summary_a)
    assert abs(ab.profit_diff + ba.profit_diff) < 1e-9
```

---

## File Checklist

| File | Action |
|---|---|
| `app/core/backtests/results_models.py` | Add `PairMetrics`, `PairAnalysis`, `RunComparison` |
| `app/core/models/analysis_models.py` | New — `DiagnosisSuggestion` |
| `app/core/services/pair_analysis_service.py` | New — `PairAnalysisService` |
| `app/core/services/diagnosis_service.py` | New — `DiagnosisService` |
| `app/core/services/comparison_service.py` | New — `ComparisonService` |
| `app/core/services/improve_service.py` | Modify — `prepare_sandbox()`, `build_candidate_command()` |
| `app/ui_v2/widgets/pair_results_widget.py` | New — `PairResultsWidget` |
| `app/ui_v2/widgets/compare_widget.py` | New — `CompareWidget` |
| `app/ui_v2/pages/backtest_page.py` | Modify — tabs, `load_results()`, wiring |
| `app/ui/pages/loop_page.py` | Modify — `_update_step_gates()` |
| `tests/test_pair_analysis_properties.py` | New — PBT for trade count invariant |
| `tests/test_comparison_properties.py` | New — PBT for antisymmetry |
| `tests/test_diagnosis_service.py` | New — unit tests for all 5 rules |
