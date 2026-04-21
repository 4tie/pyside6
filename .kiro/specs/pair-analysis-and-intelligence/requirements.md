# Requirements Document

## Introduction

This feature adds deeper intelligence and analysis capabilities to the Freqtrade GUI
desktop application. The app currently shows backtest results as aggregate totals and a
flat trades list. This feature introduces five layers of improvement, in priority order:

1. **Pair Analysis** — per-pair breakdown of profit, win rate, trade count, and drawdown,
   surfaced in a new "Pair Results" tab on the Backtest page.
2. **Diagnosis Service** — logic-based rule engine that maps pair-level and run-level
   metrics to structured, actionable suggestions.
3. **Comparison Engine** — side-by-side diff of two backtest runs with green/red
   indicators.
4. **Improve Flow Hardening** — deterministic sandbox export paths keyed on `version_id`,
   eliminating directory scanning.
5. **GUI Refactor** — unified layout system, removal of duplicate styling, and a clear
   enforced user flow.

The implementation follows the existing layered architecture: UI → State → Service →
Model → Infra. Services never import UI code. All new models use `@dataclass` for
internal DTOs.

---

## Glossary

- **BacktestTrade**: Existing dataclass representing a single trade, including `pair`,
  `profit`, `profit_abs`, `duration`, and `exit_reason` fields.
- **BacktestSummary**: Existing dataclass with aggregate run-level metrics
  (`total_profit`, `win_rate`, `max_drawdown`, `total_trades`, etc.).
- **BacktestResults**: Existing dataclass bundling `BacktestSummary` and a list of
  `BacktestTrade` objects.
- **PairMetrics**: New dataclass holding per-pair computed statistics for one backtest
  run (profit, win rate, trade count, max drawdown, profit share).
- **PairAnalysis**: New dataclass holding the full output of `PairAnalysisService` for
  one run: a list of `PairMetrics`, `best_pairs`, `worst_pairs`, and `dominance_flags`.
- **PairAnalysisService**: New stateless service that derives `PairAnalysis` from a
  `BacktestResults` object.
- **DiagnosisService**: New stateless service that applies logic-based rules to a
  `PairAnalysis` and `BacktestSummary` to produce a list of `DiagnosisSuggestion`
  objects. Distinct from the existing `ResultsDiagnosisService` (which operates on
  `DiagnosisInput` bundles for the Strategy Lab loop).
- **DiagnosisSuggestion**: New dataclass representing one actionable suggestion produced
  by `DiagnosisService`, including a `rule_id`, human-readable `message`, and `severity`.
- **RunComparison**: New dataclass holding the diff between two backtest runs:
  `profit_diff`, `winrate_diff`, `drawdown_diff`, and a `verdict` string.
- **ComparisonService**: New stateless service that computes a `RunComparison` from two
  `BacktestSummary` objects.
- **version_id**: Opaque string identifier assigned to a candidate run by the versioning
  system. Used as the canonical key for sandbox directory naming and export file naming.
- **sandbox**: Temporary directory created by `ImproveService.prepare_sandbox()` for
  isolating a candidate strategy file during a backtest run.
- **RunStore**: Existing static service that saves and loads backtest run folders.
- **IndexStore**: Existing static service that maintains the global
  `backtest_results/index.json`.
- **Pair_Results_Tab**: New tab added to the Backtest page that displays `PairAnalysis`
  output for the currently loaded run.
- **Comparison_Tab**: New tab added to the Backtest page that displays a `RunComparison`
  between two selected runs.

---

## Requirements

### Requirement 1: Per-Pair Metrics Computation

**User Story:** As a strategy developer, I want to see how each trading pair contributed
to a backtest run, so that I can identify which pairs are profitable and which are
dragging down overall performance.

#### Acceptance Criteria

1. THE `PairAnalysisService` SHALL accept a `BacktestResults` object and return a
   `PairAnalysis` object.

2. WHEN `PairAnalysisService` processes a `BacktestResults` object, THE
   `PairAnalysisService` SHALL compute a `PairMetrics` entry for every distinct `pair`
   value present in `BacktestResults.trades`.

3. FOR EACH `PairMetrics` entry, THE `PairAnalysisService` SHALL compute:
   - `total_profit_pct`: sum of `BacktestTrade.profit` for all trades on that pair
   - `win_rate`: wins divided by total trades for that pair, expressed as a percentage
   - `trade_count`: total number of trades on that pair
   - `max_drawdown_pct`: maximum single-trade loss percentage (most negative
     `BacktestTrade.profit`) for that pair; 0.0 if no losing trades exist
   - `profit_share`: `total_profit_pct` for this pair divided by the absolute sum of
     all pairs' `total_profit_pct`; 0.0 when total absolute profit is zero

4. THE `PairAnalysisService` SHALL populate `PairAnalysis.best_pairs` with the up to
   three `PairMetrics` entries having the highest `total_profit_pct`, ordered
   descending.

5. THE `PairAnalysisService` SHALL populate `PairAnalysis.worst_pairs` with the up to
   three `PairMetrics` entries having the lowest `total_profit_pct`, ordered ascending.

6. WHEN a single pair's `profit_share` exceeds 0.60, THE `PairAnalysisService` SHALL
   add the string `"profit_concentration"` to `PairAnalysis.dominance_flags`.

7. WHEN `BacktestResults.trades` is empty, THE `PairAnalysisService` SHALL return a
   `PairAnalysis` with an empty `pair_metrics` list, empty `best_pairs`, empty
   `worst_pairs`, and empty `dominance_flags`.

8. FOR ALL valid `BacktestResults` inputs, THE `PairAnalysisService` SHALL produce a
   `PairAnalysis` where the sum of all `PairMetrics.trade_count` values equals
   `len(BacktestResults.trades)` (trade count invariant).

---

### Requirement 2: Pair Results Tab

**User Story:** As a strategy developer, I want a dedicated tab in the Backtest page
that shows per-pair statistics for the currently loaded run, so that I can quickly
identify outlier pairs without manually filtering the trades table.

#### Acceptance Criteria

1. WHEN a backtest run is loaded in the Backtest page, THE `Pair_Results_Tab` SHALL
   display a table with one row per pair, showing: pair name, total profit (%),
   win rate (%), trade count, and max drawdown (%).

2. WHEN `PairAnalysis.dominance_flags` contains `"profit_concentration"`, THE
   `Pair_Results_Tab` SHALL display a visible warning label indicating profit
   concentration risk.

3. WHEN `PairAnalysis.best_pairs` is non-empty, THE `Pair_Results_Tab` SHALL highlight
   the rows corresponding to `best_pairs` entries with a distinct visual style (e.g.
   green background or bold text).

4. WHEN `PairAnalysis.worst_pairs` is non-empty, THE `Pair_Results_Tab` SHALL highlight
   the rows corresponding to `worst_pairs` entries with a distinct visual style (e.g.
   red background or italic text).

5. WHEN no run is loaded, THE `Pair_Results_Tab` SHALL display an empty state message
   indicating that no data is available.

6. THE `Pair_Results_Tab` SHALL be implemented without importing any service or model
   from the service layer into the UI layer directly — all data SHALL be passed as
   `PairAnalysis` objects from the page controller.

---

### Requirement 3: Logic-Based Diagnosis Service

**User Story:** As a strategy developer, I want the app to automatically flag common
strategy problems based on pair-level and run-level metrics, so that I receive
actionable suggestions without manually interpreting the numbers.

#### Acceptance Criteria

1. THE `DiagnosisService` SHALL accept a `PairAnalysis` object and a `BacktestSummary`
   object and return a list of `DiagnosisSuggestion` objects.

2. WHEN `BacktestSummary.win_rate` is less than 30.0, THE `DiagnosisService` SHALL
   include a `DiagnosisSuggestion` with `rule_id = "entry_too_aggressive"` and
   `severity = "critical"`.

3. WHEN `BacktestSummary.max_drawdown` is greater than 40.0, THE `DiagnosisService`
   SHALL include a `DiagnosisSuggestion` with `rule_id = "stoploss_too_loose"` and
   `severity = "critical"`.

4. WHEN `PairAnalysis.dominance_flags` contains `"profit_concentration"`, THE
   `DiagnosisService` SHALL include a `DiagnosisSuggestion` with
   `rule_id = "overfitting_risk"` and `severity = "warning"`.

5. WHEN `BacktestSummary.total_trades` is less than 30, THE `DiagnosisService` SHALL
   include a `DiagnosisSuggestion` with `rule_id = "insufficient_trades"` and
   `severity = "warning"`.

6. WHEN `BacktestSummary.profit_factor` is greater than 0.0 and less than 1.0, THE
   `DiagnosisService` SHALL include a `DiagnosisSuggestion` with
   `rule_id = "negative_expectancy"` and `severity = "critical"`.

7. WHEN none of the rule conditions are met, THE `DiagnosisService` SHALL return an
   empty list.

8. THE `DiagnosisService` SHALL be stateless — all methods SHALL be `@staticmethod`.

9. THE `DiagnosisService` SHALL NOT import any UI code.

---

### Requirement 4: Run Comparison Engine

**User Story:** As a strategy developer, I want to compare two backtest runs
side-by-side, so that I can objectively evaluate whether a parameter change improved
or degraded strategy performance.

#### Acceptance Criteria

1. THE `ComparisonService` SHALL accept two `BacktestSummary` objects (labelled `run_a`
   and `run_b`) and return a `RunComparison` object.

2. THE `ComparisonService` SHALL compute `RunComparison.profit_diff` as
   `run_b.total_profit - run_a.total_profit`.

3. THE `ComparisonService` SHALL compute `RunComparison.winrate_diff` as
   `run_b.win_rate - run_a.win_rate`.

4. THE `ComparisonService` SHALL compute `RunComparison.drawdown_diff` as
   `run_b.max_drawdown - run_a.max_drawdown` (positive means run_b has higher
   drawdown, i.e. worse).

5. WHEN `RunComparison.profit_diff` is greater than 0.0 AND
   `RunComparison.drawdown_diff` is less than or equal to 0.0, THE
   `ComparisonService` SHALL set `RunComparison.verdict` to `"improved"`.

6. WHEN `RunComparison.profit_diff` is less than 0.0 OR
   `RunComparison.drawdown_diff` is greater than 5.0, THE `ComparisonService` SHALL
   set `RunComparison.verdict` to `"degraded"`.

7. WHEN neither the `"improved"` nor `"degraded"` conditions are met, THE
   `ComparisonService` SHALL set `RunComparison.verdict` to `"neutral"`.

8. FOR ALL pairs of `BacktestSummary` inputs, THE `ComparisonService` SHALL produce a
   `RunComparison` where `compare(a, b).profit_diff == -compare(b, a).profit_diff`
   (antisymmetry property).

---

### Requirement 5: Comparison Tab

**User Story:** As a strategy developer, I want a tab in the Backtest page where I can
select two runs and see a colour-coded diff, so that I can quickly judge whether a
change was beneficial.

#### Acceptance Criteria

1. THE `Comparison_Tab` SHALL allow the user to select two backtest runs from the
   currently loaded strategy's run history.

2. WHEN both runs are selected, THE `Comparison_Tab` SHALL display `profit_diff`,
   `winrate_diff`, and `drawdown_diff` values with green colouring when the diff
   indicates improvement and red colouring when it indicates degradation.

3. WHEN `RunComparison.verdict` is `"improved"`, THE `Comparison_Tab` SHALL display
   the verdict label in green.

4. WHEN `RunComparison.verdict` is `"degraded"`, THE `Comparison_Tab` SHALL display
   the verdict label in red.

5. WHEN `RunComparison.verdict` is `"neutral"`, THE `Comparison_Tab` SHALL display
   the verdict label in a neutral colour (neither green nor red).

6. WHEN fewer than two runs are selected, THE `Comparison_Tab` SHALL display a prompt
   instructing the user to select two runs.

---

### Requirement 6: Deterministic Improve Flow Export Paths

**User Story:** As a strategy developer, I want the improve flow to use deterministic,
version-keyed export paths, so that run results are always traceable to a specific
candidate version without relying on directory scanning.

#### Acceptance Criteria

1. WHEN `ImproveService.prepare_sandbox()` creates a sandbox directory for a candidate
   run, THE `ImproveService` SHALL use the path `sandbox/{version_id}/` where
   `version_id` is the canonical identifier for that candidate.

2. WHEN `ImproveService` exports a backtest result for a candidate run, THE
   `ImproveService` SHALL write the result file as `{version_id}.json` inside the
   sandbox directory.

3. THE `ImproveService` SHALL maintain a strict one-to-one mapping between a candidate
   run, its `version_id`, and its sandbox directory — no two candidates SHALL share
   the same `version_id` path within a session.

4. IF a sandbox directory for the given `version_id` already exists when
   `prepare_sandbox()` is called, THEN THE `ImproveService` SHALL raise a `ValueError`
   with a message identifying the conflicting `version_id`.

5. THE `ImproveService` SHALL NOT use directory scanning or glob patterns to locate
   export results — all result file paths SHALL be constructed deterministically from
   `version_id`.

---

### Requirement 7: GUI Layout Unification

**User Story:** As a developer maintaining the codebase, I want the UI layout system
to be unified and free of duplicate styling logic, so that visual changes can be made
in one place and the user flow is predictable.

#### Acceptance Criteria

1. THE `BacktestPage` SHALL enforce the following tab order: Summary → Trades →
   Pair Results → Compare.

2. THE `BacktestPage` SHALL apply a single shared stylesheet or style helper for
   result table colouring — duplicate inline style strings for the same visual element
   SHALL NOT exist across more than one method.

3. THE `BacktestPage` SHALL expose a single `load_results(results: BacktestResults)`
   method that populates all tabs (Summary, Trades, Pair Results) in one call, rather
   than separate per-tab load methods called from multiple locations.

4. WHEN the user completes a backtest run, THE `BacktestPage` SHALL automatically
   navigate to the Summary tab.

5. THE `LoopPage` (Strategy Lab) SHALL enforce the following user flow in its UI
   controls: Run → Results → Problems → Improve → Preview → Run Candidate → Compare →
   Accept/Reject — controls for later steps SHALL be disabled until the preceding step
   is complete.
