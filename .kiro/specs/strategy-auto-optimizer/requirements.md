# Requirements Document

## Introduction

This feature covers two related enhancements to the Freqtrade GUI desktop app (PySide6/Python):

1. **Enhanced Improve Tab** — upgrades the existing `ImprovePage` from a single-iteration suggestion tool into a multi-iteration, AI-assisted improvement workflow. The enhanced tab surfaces deeper diagnostics, supports multiple sequential improvement rounds, tracks a full improvement history within a session, and provides richer guidance so users can arrive at a genuinely profitable strategy rather than just applying surface-level parameter tweaks.

2. **Strategy Lab Tab (Auto-Loop)** — a new `LoopPage` tab that runs a fully autonomous backtest → diagnose → mutate → repeat cycle. The user picks a strategy and configures targets; the system runs backtests via the existing `QProcess`/`ProcessService` infrastructure, analyses results with `ResultsDiagnosisService` and `RuleSuggestionService`, applies parameter mutations via `SuggestionRotator`, and loops until targets are met or the iteration budget is exhausted. Every iteration is recorded in a scrollable history. At the end the user reviews all iterations and can apply the best result to the live strategy file.

Both features build on the existing service layer (`ImproveService`, `LoopService`, `BacktestService`, `ProcessService`) and follow the project's layered architecture: UI → State → Service → Model → Infra.

### Scope of Parameter Mutation

Both ImprovePage and LoopPage mutate **JSON-configurable parameters only** — values stored in the strategy's `.json` params file (ROI table, stoploss, trailing stop, buy/sell parameters). Neither feature rewrites or modifies the strategy's **Python source file** (`.py`). Code-level mutation (indicator logic, signal conditions, custom stoploss functions) is **explicitly out of scope** for this feature set.

---

## Glossary

- **ImprovePage**: The existing `app/ui/pages/improve_page.py` widget — the Improve tab.
- **LoopPage**: The new `app/ui/pages/loop_page.py` widget — the Strategy Lab / Auto-Loop tab.
- **LoopService**: `app/core/services/loop_service.py` — orchestrates the iterative backtest-improve cycle.
- **ImproveService**: `app/core/services/improve_service.py` — sandbox management, command building, result parsing, accept/reject.
- **BacktestService**: `app/core/services/backtest_service.py` — builds `BacktestRunCommand` objects and lists strategies.
- **ProcessService**: `app/core/services/process_service.py` — wraps `QProcess` for non-blocking subprocess execution.
- **ResultsDiagnosisService**: `app/core/services/results_diagnosis_service.py` — stateless rule-based issue detection.
- **RuleSuggestionService**: `app/core/services/rule_suggestion_service.py` — maps diagnosed issues to `ParameterSuggestion` objects.
- **SuggestionRotator**: Class inside `loop_service.py` — tracks tried configurations and generates varied suggestions across iterations.
- **LoopConfig**: `app/core/models/loop_models.LoopConfig` — user-supplied targets and iteration budget for a loop run.
- **LoopIteration**: `app/core/models/loop_models.LoopIteration` — record of one backtest-improve cycle, including all gate results.
- **LoopResult**: `app/core/models/loop_models.LoopResult` — final aggregate of all iterations.
- **GateResult**: `app/core/models/loop_models.GateResult` — record of a single validation gate execution within one iteration.
- **BacktestResults**: `app/core/backtests/results_models.BacktestResults` — parsed output of a single backtest run.
- **BacktestSummary**: `app/core/backtests/results_models.BacktestSummary` — aggregate metrics within `BacktestResults`.
- **Sandbox**: Isolated directory under `{user_data}/strategies/_improve_sandbox/{strategy_name}_{timestamp_ms}/` used for candidate backtests. One directory is created per run and is never reused.
- **SessionBaseline**: `@dataclass` holding `params: dict` and `summary: BacktestSummary` — the in-memory accepted-session baseline for ImprovePage. Captured at the moment the user accepts a candidate. Never re-read from disk after initial load.
- **SessionRound**: `@dataclass` — one entry in the ImprovePage session history stack (see Requirement 16 for full field definition).
- **Composite Score**: Deprecated term for the old weighted scoring formula. Replaced by `RobustScore` — see `RobustScoreInput` and `RobustScore` in the Glossary.
- **Candidate Config**: The mutated parameter dict proposed for a given iteration.
- **Live Strategy JSON**: `{user_data}/strategies/{StrategyName}.json` — the persisted parameter file read by Freqtrade.
- **TerminalWidget**: `app/ui/widgets/terminal_widget.py` — live subprocess output display widget.
- **AppSettings**: `app/core/models/settings_models.AppSettings` — Pydantic model holding all user-configured paths.
- **user_data_path**: The Freqtrade `user_data` directory configured in `AppSettings`.
- **IssueBadge**: `app/ui/widgets/issue_badge.py` — color-coded badge widget for a single `DiagnosedIssue`.
- **SuggestionRow**: `app/ui/widgets/suggestion_row.py` — styled row widget for a single `ParameterSuggestion`.
- **AnimatedMetricCard**: `app/ui/widgets/animated_metric_card.py` — animated metric card widget.
- **IterationHistoryRow**: `app/ui/widgets/iteration_history_row.py` — row widget for a single `LoopIteration` in the history list.
- **HardFilterFailure**: `app/core/models/loop_models.HardFilterFailure` — dataclass recording a single hard-filter rejection with `filter_name`, `reason`, and `evidence`.
- **HardFilterService**: `app/core/services/hard_filter_service.py` — stateless service with two static methods: `evaluate_post_gate1()` (filters 1–7, called after Gate 1 and before Gate 2) and `evaluate_post_gate()` (filters 8–9, called after Gate 2 and Gate 3 respectively).
- **RobustScoreInput**: `app/core/models/loop_models.RobustScoreInput` — dataclass bundling in-sample summary, optional fold summaries, optional stress summary, and optional pair profit distribution for multi-dimensional scoring.
- **RobustScore**: `app/core/models/loop_models.RobustScore` — dataclass holding the total score and its four component scores (profitability, consistency, stability, fragility).
- **StructuralDiagnosis**: `app/core/models/diagnosis_models.StructuralDiagnosis` — dataclass representing a pattern-based root-cause diagnosis with failure pattern label, evidence, root cause, mutation direction, confidence, and severity.
- **Training Range** — `[date_from, training_end_date)` — half-open interval (inclusive start, exclusive end) used for Gate 1, Gate 3, and Gate 4. Computed as the first `(1 - oos_split_pct/100)` fraction of the total configured date range. Does NOT include `training_end_date`.
- **OOS Range** — `[training_end_date, date_to]` — closed interval (inclusive start and end) used exclusively for Gate 2. Begins at `training_end_date`, the first date excluded from the Training Range. Never seen by Gate 1, Gate 3, or Gate 4.
- **DiagnosisInput** — `app/core/models/diagnosis_models.DiagnosisInput` — dataclass passed to `ResultsDiagnosisService.diagnose()` bundling the in-sample summary, optional OOS summary, optional fold summaries, optional per-trade profit contributions, and optional drawdown/ATR period data needed by structural diagnosis rules.
- **DiagnosisBundle** — `app/core/models/diagnosis_models.DiagnosisBundle` — dataclass returned by `ResultsDiagnosisService.diagnose()` containing two lists: `issues: list[DiagnosedIssue]` and `structural: list[StructuralDiagnosis]`.
- **ConfigurationGuard** — a stateless check (implemented as a pure function `check_prerequisites(settings: AppSettings) -> list[str]`) that returns a list of human-readable failure messages, or an empty list when all prerequisites are satisfied. Used by both ImprovePage and LoopPage.
- **export_dir** — a per-run directory passed to Freqtrade via `--backtest-directory`. Created inside the sandbox before the subprocess starts. Freqtrade writes a `.zip` result file into this directory. Path format: `{sandbox_dir}/backtest_output/` for ImprovePage runs, `{sandbox_dir}/gate_{gate_name}_{n}/` for LoopPage gate runs.

---

## Requirements

### Requirement 1: Enhanced Improve Tab — Multi-Iteration Improvement Workflow

**User Story:** As a strategy developer, I want the Improve tab to support multiple sequential improvement rounds within a single session, so that I can iteratively refine a strategy without manually restarting the workflow each time.

#### Acceptance Criteria

1. WHEN the user clicks **Accept & Save** on a candidate result, THE ImprovePage SHALL update its internal `SessionBaseline` (in-memory `params: dict` and `summary: BacktestSummary`) to the accepted candidate's values and immediately enable a new **Run Another Round** action without requiring a page reload.
2. THE ImprovePage SHALL maintain an in-session improvement history list showing every accepted round's key metrics (profit %, win rate, max drawdown, trade count) in chronological order.
3. WHEN the user has accepted at least one round, THE ImprovePage SHALL display a **Rollback** button that restores the strategy parameters to the state before the most recent accepted round.
4. WHEN the user clicks **Rollback**, THE ImprovePage SHALL call `ImproveService.rollback()` with the previous accepted parameters and update the displayed baseline metrics accordingly. Rollback SHALL restore the in-memory `SessionBaseline` to the previous entry in the session history stack — it SHALL NOT re-read parameters from the strategy JSON on disk.
5. THE ImprovePage SHALL display the current workflow step (1–5: Select, Analyze, Apply, Backtest, Decide) using the existing `StepIndicator` widget, updating it after each user action.
6. WHEN ImprovePage first loads a strategy (before any candidate has been accepted), THE ImprovePage SHALL populate the `SessionBaseline` by parsing the most recent backtest result for that strategy from the run store. IF no prior result exists in the run store, THE ImprovePage SHALL run a fresh baseline backtest to establish the initial `SessionBaseline`.
7. WHEN a candidate backtest is actively running in ImprovePage, THE ImprovePage SHALL disable the strategy combo box and SHALL NOT allow strategy selection changes until the subprocess completes.
8. THE ImprovePage SHALL re-enable the strategy combo box only when no subprocess is running and no candidate decision is pending.
9. WHEN the user clicks **Run Another Round**, THE ImprovePage SHALL use the current in-memory `SessionBaseline.params` as the starting point for the next suggestion cycle — it SHALL NOT re-read the strategy JSON from disk.

---

### Requirement 2: Enhanced Improve Tab — Deeper Diagnostics Display

**User Story:** As a strategy developer, I want the Improve tab to show me a richer explanation of why my strategy is underperforming, so that I can make informed decisions about which suggestions to apply.

#### Acceptance Criteria

1. WHEN `ResultsDiagnosisService.diagnose()` returns a `DiagnosisBundle` with one or more `DiagnosedIssue` objects in `bundle.issues`, THE ImprovePage SHALL render each as a color-coded `IssueBadge` widget with a severity indicator (red for critical, orange for moderate, yellow for advisory). THE ImprovePage SHALL construct a `DiagnosisInput` from the available data before calling `diagnose()`. When only the in-sample baseline is available (no OOS or fold data), `oos_summary`, `fold_summaries`, `drawdown_periods`, and `atr_spike_periods` SHALL be None — rules that require those fields will be suppressed automatically.
2. WHEN `RuleSuggestionService.suggest()` returns one or more `ParameterSuggestion` objects, THE ImprovePage SHALL render each suggestion as a `SuggestionRow` widget showing the parameter name, proposed value, reason, and expected effect.
3. WHEN a `ParameterSuggestion` has `is_advisory=True`, THE ImprovePage SHALL display it with an "Advisory" badge and SHALL NOT render an Apply button for it.
4. WHEN `bundle.structural` contains one or more `StructuralDiagnosis` objects, THE ImprovePage SHALL render each in the diagnostics panel showing: `failure_pattern` label, `evidence`, `root_cause`, `mutation_direction`, and a confidence bar. Severity determines badge color.
5. WHEN both `bundle.issues` and `bundle.structural` are empty, THE ImprovePage SHALL display the "No issues detected" message with a green indicator instead of an empty issues panel.
6. THE ImprovePage SHALL display animated metric cards (`AnimatedMetricCard`) for profit %, win rate, max drawdown, and trade count, updating them with animation when new backtest results are loaded.

---

### Requirement 3: Enhanced Improve Tab — Candidate Backtest Comparison

**User Story:** As a strategy developer, I want to see a side-by-side comparison of the baseline and candidate backtest results, so that I can clearly judge whether the suggested changes improved the strategy.

#### Acceptance Criteria

1. WHEN a candidate backtest completes successfully, THE ImprovePage SHALL display a comparison table with one row per metric (profit %, win rate, max drawdown, trade count, Sharpe ratio) showing the baseline value, candidate value, and delta.
2. WHEN a metric delta is positive and higher-is-better (profit, win rate, Sharpe), THE ImprovePage SHALL color the delta cell green.
3. WHEN a metric delta is negative and higher-is-better, THE ImprovePage SHALL color the delta cell red.
4. WHEN a metric delta is negative and lower-is-better (max drawdown), THE ImprovePage SHALL color the delta cell green.
5. WHEN a candidate backtest fails (non-zero exit code), THE ImprovePage SHALL display an error status message and SHALL NOT show the comparison table.
6. THE ImprovePage SHALL use the `compute_highlight()` pure function to determine cell color, ensuring the coloring logic is testable independently of the UI.
7. THE candidate backtest command SHALL pass `--backtest-directory {sandbox_dir}/backtest_output/` as specified by the artifact directory contract in Requirement 18 criterion 7.
8. `ImproveService.parse_candidate_run(export_dir: Path)` SHALL accept the export directory — it SHALL NOT accept a file path. See Requirement 18 criterion 7 for the full contract.
9. IF no `.zip` file is found in `export_dir` after subprocess completion, `ImproveService.parse_candidate_run()` SHALL raise `FileNotFoundError` with the `export_dir` path included in the exception message.

---

### Requirement 4: Enhanced Improve Tab — Configuration Guard

**User Story:** As a user who has not yet configured the app, I want the Improve tab to clearly tell me what is missing, so that I know exactly what to set up before I can use it.

#### Acceptance Criteria

1. THE ImprovePage SHALL evaluate a `ConfigurationGuard` check on load and whenever `SettingsState.settings_changed` is emitted. The guard checks ALL of the following prerequisites:
   - `AppSettings.user_data_path` is set and the directory exists on disk.
   - `AppSettings.python_executable` (or `AppSettings.freqtrade_executable` when `use_module_execution=False`) exists on disk and is executable.
   - At least one strategy file exists under `{user_data_path}/strategies/`.
2. WHEN ALL prerequisites pass, THE ImprovePage SHALL hide the warning banner and enable the strategy combo box and Analyze button.
3. WHEN ANY prerequisite fails, THE ImprovePage SHALL display a warning banner listing each failing prerequisite by name (e.g., "Python executable not found at {path}") and disable the strategy combo box and Analyze button.
4. WHEN `SettingsState.settings_changed` is emitted, THE ImprovePage SHALL re-run the `ConfigurationGuard` check and update the banner and control states accordingly.

---

### Requirement 5: Strategy Lab Tab — Loop Configuration

**User Story:** As a strategy developer, I want to configure the auto-optimization loop with my own profitability targets and iteration budget, so that the loop stops when my specific goals are met.

#### Acceptance Criteria

1. THE LoopPage SHALL provide a strategy selector combo box populated from `ImproveService.get_available_strategies()`.
2. THE LoopPage SHALL provide a **Max Iterations** spin box (range 1–50, default 10) that limits the total number of backtest-improve cycles.
3. THE LoopPage SHALL provide a **Target Profit (%)** spin box (range −100 to 10000, default 5.0) that sets the minimum total profit required to consider the loop successful.
4. THE LoopPage SHALL provide a **Target Win Rate (%)** spin box (range 0–100, default 55.0).
5. THE LoopPage SHALL provide a **Max Drawdown (%)** spin box (range 0–100, default 20.0) that sets the maximum acceptable drawdown.
6. THE LoopPage SHALL provide a **Min Trades** spin box (range 1–10000, default 30) that sets the minimum trade count required for a result to be considered valid.
7. THE LoopPage SHALL provide a **Stop as soon as all targets are met** checkbox (default checked) that, when checked, causes the loop to terminate immediately once all five validation gates pass for a single candidate.
8. WHEN the user clicks **Start Loop**, THE LoopPage SHALL construct a `LoopConfig` from the current spin box and checkbox values and pass it to `LoopService.start()`.
9. WHEN a loop is actively running in LoopPage, THE LoopPage SHALL disable the strategy combo box and all configuration spin boxes and SHALL NOT allow strategy selection changes until the loop finishes or is stopped.
10. THE LoopPage SHALL re-enable the strategy combo box and configuration spin boxes only when no loop is active and no subprocess is running.
11. THE LoopPage SHALL provide an **Out-of-Sample Split (%)** spin box (range 5–50, default 20) that sets the percentage of the total date range held out for the out-of-sample gate.
12. THE LoopPage SHALL provide a **Walk-Forward Folds (K)** spin box (range 2–10, default 5) that sets the number of folds used in the walk-forward validation gate.
13. THE LoopPage SHALL provide a **Stress Fee Multiplier** spin box (range 1.0–5.0, step 0.1, default 2.0) that sets the fee multiplier applied during the stress-test gate.
14. THE LoopPage SHALL provide a **Stress Slippage (%)** spin box (range 0.0–2.0, step 0.01, default 0.1) that sets the per-trade slippage added during the stress-test gate.
15. THE LoopPage SHALL provide a **Stress Profit Target (%)** spin box (range 0–100, default 50) that sets the minimum profit required during the stress-test gate as a percentage of the main profit target.
16. THE LoopPage SHALL provide a **Consistency Threshold (%)** spin box (range 0–100, default 30) that sets the maximum allowed standard deviation of per-fold profit as a percentage of mean fold profit.
17. THE LoopPage SHALL provide a **Validation Mode** selector with two options: "Full Ladder" (all five gates, default) and "Quick" (in-sample + out-of-sample only, gates 1–2). WHEN "Quick" is selected, THE LoopPage SHALL disable the walk-forward, stress-test, and consistency spin boxes.
18. THE LoopPage SHALL provide the following hard-filter threshold controls, grouped under a collapsible **Advanced Filters** section to avoid overwhelming the user:
    - **Max Profit Concentration (top 3 trades %)** spin box (range 0.10–0.90, step 0.05, default 0.50) — maps to `LoopConfig.profit_concentration_threshold`.
    - **Min Profit Factor** spin box (range 1.0–3.0, step 0.05, default 1.1) — maps to `LoopConfig.profit_factor_floor`.
    - **Max Single-Pair Profit Share (%)** spin box (range 0.10–1.0, step 0.05, default 0.60) — maps to `LoopConfig.pair_dominance_threshold`.
    - **Max Single-Period Profit Share (%)** spin box (range 0.10–1.0, step 0.05, default 0.40) — maps to `LoopConfig.time_dominance_threshold`.
    - **Max Walk-Forward Variance (CV)** spin box (range 0.1–3.0, step 0.1, default 1.0) — maps to `LoopConfig.validation_variance_ceiling`.
19. WHEN the user clicks **Start Loop**, THE LoopPage SHALL include all five hard-filter threshold values in the `LoopConfig` passed to `LoopService.start()`.

---

### Requirement 6: Strategy Lab Tab — Autonomous Loop Execution

**User Story:** As a strategy developer, I want the Strategy Lab to automatically run backtests, diagnose results, apply parameter changes, and repeat — without me having to intervene between iterations — so that I can let it run and come back to a set of results.

#### Acceptance Criteria

1. WHEN the loop starts, THE LoopPage SHALL first run an initial backtest on the **Training Range** only (using `[date_from, training_end_date)` as defined in Requirement 10 criterion 1) with the strategy's current parameters and no mutations. This produces the initial `BacktestSummary` used to establish the baseline `RobustScore`. The baseline score is computed by calling `compute_score()` with a `RobustScoreInput` where only `in_sample` is populated (all other fields are None). This baseline is used as the reference point for `is_improvement` comparisons throughout the loop session.
2. THE initial baseline backtest SHALL use the same Training Range that all subsequent Gate 1 backtests use. The baseline SHALL NOT be computed from the full configured date range or the OOS Range. This ensures that all `RobustScore.total` comparisons (baseline vs. candidate) are made on the same data domain.
3. WHEN the initial backtest completes successfully, THE LoopPage SHALL call `LoopService.prepare_next_iteration()` with the initial results to obtain the first candidate parameter set.
4. WHEN `LoopService.prepare_next_iteration()` returns a `LoopIteration`, THE LoopPage SHALL call `ImproveService.prepare_sandbox()` to create an isolated sandbox directory, then call `ImproveService.build_candidate_command()` to build the backtest command, then execute it via `ProcessService.execute_command()`.
5. WHEN a candidate backtest completes successfully, THE LoopPage SHALL call `ImproveService.parse_candidate_run()` to parse the result artifact, then call `LoopService.record_iteration_result()` to update the best-score tracking.
6. WHEN a candidate backtest exits with a non-zero exit code, THE LoopPage SHALL call `LoopService.record_iteration_error()` and continue to the next iteration if `LoopService.should_continue()` returns True.
7. AFTER recording each iteration result, THE LoopPage SHALL call `LoopService.should_continue()` and, if True, schedule the next iteration via `QTimer.singleShot()` to keep the Qt event loop responsive.
8. WHEN `LoopService.should_continue()` returns False, THE LoopPage SHALL call `LoopService.finalize()` and transition to the results review state.
9. WHEN the user clicks **Stop**, THE LoopPage SHALL call `LoopService.stop()` and `ProcessService.stop_process()`, then wait for the current backtest to finish before finalizing.
10. Each iteration's gate backtest command SHALL pass `--backtest-directory {sandbox_dir}/gate_{gate_name}_{n}/` as specified by the artifact directory contract in Requirement 18 criterion 7.
11. `ImproveService.parse_candidate_run(export_dir: Path)` SHALL accept the export directory — it SHALL NOT accept a file path. See Requirement 18 criterion 7 for the full contract.
12. IF no `.zip` file is found in `export_dir` after subprocess completion, `ImproveService.parse_candidate_run()` SHALL raise `FileNotFoundError` with the `export_dir` path included in the exception message.
13. WHEN `parse_candidate_run()` raises `FileNotFoundError` or `json.JSONDecodeError`, THE LoopPage SHALL treat the failure identically to a non-zero subprocess exit — calling `LoopService.record_iteration_error()` and continuing if budget allows.
14. WHEN `ImproveService` raises `ValueError` during settings validation before a loop starts, THE LoopPage SHALL display the error in a banner and SHALL NOT start the loop.
15. WHEN an `OSError` occurs during sandbox directory creation, THE LoopPage SHALL display the error in the terminal, stop the loop entirely (the error is not recoverable mid-run), and transition to the finalized state.
16. WHEN executing a validation gate that requires a backtest (in-sample, out-of-sample, each walk-forward fold, stress test), THE LoopService SHALL issue a separate backtest command per gate — each iteration therefore runs between 2 and (K + 3) backtests depending on how far the candidate progresses through the ladder.
17. WHEN a gate fails for a candidate, THE LoopService SHALL skip all remaining gates for that iteration, record the gate name and failure reason in the `LoopIteration`, and proceed to the next iteration.
18. WHEN `LoopConfig.validation_mode` is `"quick"`, THE LoopService SHALL execute only gates 1 (in-sample) and 2 (out-of-sample) per iteration and SHALL skip gates 3–5 entirely.

---

### Requirement 7: Strategy Lab Tab — Iteration History Display

**User Story:** As a strategy developer, I want to see a full history of every iteration the loop ran — what changed, what the results were, and whether it was an improvement — so that I can understand the optimization trajectory.

#### Acceptance Criteria

1. WHEN a `LoopIteration` is completed, THE LoopPage SHALL append a row to the iteration history list showing: iteration number, status icon (✅ improvement / ➡ no improvement / ❌ error), parameter changes summary, profit %, win rate, max drawdown, trade count, Sharpe ratio, the name of the last validation gate attempted, and whether the candidate passed or failed that gate.
2. WHEN a `LoopIteration` is an improvement (`is_improvement=True`), THE LoopPage SHALL render its history row with a green left border and a "BEST" badge.
3. WHEN a `LoopIteration` has an error, THE LoopPage SHALL render its history row with a red left border and display the error message (truncated to 60 characters).
4. THE LoopPage SHALL auto-scroll the history list to the most recently added row after each iteration completes.
5. WHEN no iterations have been run yet, THE LoopPage SHALL display an empty-state message ("No iterations yet — start the loop to begin.") in the history area.
6. THE LoopPage SHALL display live stat cards for current iteration number, best profit %, best win rate, best max drawdown, and best Sharpe ratio, updating them after each iteration that sets a new best score.
7. THE LoopPage SHALL display a progress bar showing the percentage of the iteration budget consumed (current iteration / max iterations × 100).
8. WHEN a `LoopIteration` is partially validated (passed gate 1 but failed a later gate), THE LoopPage SHALL render its history row with an amber left border and a "PARTIAL" badge indicating the candidate was not fully validated.
9. THE LoopPage SHALL display a gate progress indicator in each history row showing how many gates the candidate passed out of the total gates in the configured validation mode (e.g., "3/5 gates" for Full Ladder or "1/2 gates" for Quick mode).

---

### Requirement 8: Strategy Lab Tab — Loop Scoring and Best-Result Tracking

**User Story:** As a strategy developer, I want the loop to automatically identify the best result across all iterations using a principled, multi-dimensional scoring formula, so that I don't have to manually compare every run.

#### Acceptance Criteria

1. THE LoopService SHALL compute a `RobustScore` for each iteration using the `compute_score()` function, which accepts a `RobustScoreInput` dataclass. The formula is:

   ```
   robust_score = profitability_score + consistency_score + stability_score - fragility_score
   ```

   Each component is a normalized value in [0, 1] (fragility is subtracted):

   - **profitability_score** (weight 0.35): `0.35 * mean([norm(net_profit), norm(expectancy), norm(min(profit_factor, 3.0))])`
   - **consistency_score** (weight 0.30): `0.30 * mean([pct_profitable_folds, equity_r2])` where `pct_profitable_folds` is the fraction of walk-forward folds that are profitable and `equity_r2` is the R² of the equity curve vs a linear trend (range 0–1). WHEN walk-forward data is not available (Quick mode), use only `equity_r2` with full weight.
   - **stability_score** (weight 0.20): `0.20 * mean([1 - cv_fold_profits, 1 - pair_dominance_ratio])` where `cv_fold_profits` is the coefficient of variation of per-fold profits (clamped to [0, 1]) and `pair_dominance_ratio` is the profit share of the single most dominant pair (clamped to [0, 1]). WHEN walk-forward data is not available, use only pair stability with full weight.
   - **fragility_score** (weight 0.15, subtracted): `0.15 * mean([norm(max_drawdown), slippage_sensitivity, pair_dominance_ratio])` where `slippage_sensitivity` is the ratio of stress-test profit drop to baseline profit (range 0–1). WHEN stress-test data is not available (Quick mode), use only drawdown and pair dependence.

2. All `norm()` calls SHALL use **fixed reference ranges** that are set once at loop start and never change during the session. The fixed ranges are: `net_profit` [−100%, +200%], `expectancy` [−1.0, +5.0], `profit_factor` [0, 3.0], `max_drawdown` [0%, 100%]. These ranges are hard-coded constants in `loop_service.py` and are not configurable. This guarantees that `RobustScore.total` values are directly comparable across all iterations in a session regardless of the order they were computed.

3. THE `compute_score()` function SHALL accept a `RobustScoreInput` dataclass:

   ```python
   @dataclass
   class RobustScoreInput:
       in_sample: BacktestSummary
       fold_summaries: Optional[list[BacktestSummary]]   # from walk-forward gate; None in Quick mode
       stress_summary: Optional[BacktestSummary]          # from stress-test gate; None in Quick mode
       pair_profit_distribution: Optional[dict[str, float]]  # pair → profit contribution ratio
   ```

4. THE `compute_score()` function SHALL return a `RobustScore` dataclass:

   ```python
   @dataclass
   class RobustScore:
       total: float
       profitability: float
       consistency: float
       stability: float
       fragility: float
   ```

5. THE `compute_score()` function SHALL remain a pure module-level function in `loop_service.py`, so that it can be tested independently of the loop state machine.

6. THE `LoopIteration.score` field SHALL store `Optional[RobustScore]` instead of `Optional[float]`. Best-iteration comparison SHALL use `RobustScore.total`.

7. WHEN a new iteration's `RobustScore.total` exceeds the current best score AND the iteration is fully validated (`validation_gate_passed=True`), THE LoopService SHALL update `LoopResult.best_iteration` to point to that iteration and set `LoopIteration.is_improvement = True`. The initial best score is set from the baseline backtest run at loop start (Training Range only, no mutations) — it is not loaded from a prior session or disk state.

8. WHEN a new iteration's score does not exceed the current best score, or the iteration is not fully validated, THE LoopService SHALL set `LoopIteration.is_improvement = False` and leave `LoopResult.best_iteration` unchanged.

9. WHEN the loop finalizes with no fully validated iterations, THE LoopService SHALL leave `LoopResult.best_iteration` as None.

10. WHEN the loop finalizes with at least one fully validated iteration but `best_iteration` was never set during the run, THE LoopService SHALL set `best_iteration` to the fully validated iteration with the highest `RobustScore.total`.

11. WHEN a backtest completes successfully but produces 0 trades, `LoopService.record_iteration_result()` SHALL mark the iteration as `status="zero_trades"` and SHALL NOT compute a score for it.

12. WHEN a backtest produces fewer than `LoopConfig.min_trades` trades, THE LoopService SHALL score the iteration but set `LoopIteration.below_min_trades = True` and SHALL NOT allow that iteration to become `LoopResult.best_iteration`.

13. WHEN `BacktestSummary.sharpe_ratio` is None or NaN, `compute_score()` SHALL substitute `0.0` for the Sharpe component rather than raising an error.

14. WHEN `BacktestSummary.profit_factor`, `win_rate`, or `max_drawdown` is None or NaN, `compute_score()` SHALL substitute neutral values (`0.0` for profit_factor and win_rate, `100.0` for max_drawdown) and log a WARNING via `_log.warning`.

15. THE normalization rules in criteria 13 and 14 SHALL be implemented in a `_normalize_summary()` pure helper function called inside `compute_score()`, so that the normalization logic is independently testable.

16. WHEN a candidate passes gate 1 (in-sample) but fails a later gate, THE LoopService SHALL still compute and record a `RobustScore` for that iteration (using the in-sample `BacktestSummary`) and mark it as "partially validated" — but it SHALL NOT be eligible to become `LoopResult.best_iteration`.

---

### Requirement 9: Strategy Lab Tab — Parameter Mutation and Variation

**User Story:** As a strategy developer, I want the loop to try progressively different parameter combinations across iterations rather than repeating the same change, so that it explores the parameter space effectively.

#### Acceptance Criteria

1. THE SuggestionRotator SHALL track which parameter configurations have already been tried using a set of hashable config keys, and SHALL NOT submit the same configuration twice.
2. WHEN a parameter has been adjusted `_MAX_STEPS_PER_PARAM` (5) times, THE SuggestionRotator SHALL skip that parameter in subsequent iterations.
3. WHEN the previous iteration did not improve the score and a parameter was changed in that iteration, THE SuggestionRotator SHALL reverse the direction of the next change for that parameter.
4. THE SuggestionRotator SHALL apply a step-based multiplier to the magnitude of each change: step 0 → 1×, step 1 → 1.5×, step 2 → 2×, and so on.
5. WHEN no actionable (non-advisory) suggestions remain after rotation, THE LoopService SHALL set `LoopResult.stop_reason` to "No more actionable suggestions to try" and terminate the loop.
6. WHEN all reachable parameter combinations are exhausted (every candidate config has been tried), THE LoopService SHALL set `LoopResult.stop_reason` to "All reachable parameter combinations exhausted" and terminate the loop.

---

### Requirement 10: Strategy Lab Tab — Multi-Gate Validation Ladder

**User Story:** As a strategy developer, I want a candidate strategy to be considered "validated" only after it passes a sequential series of robustness checks — not just a single backtest — so that the loop does not declare success on a result that is overfit or fragile.

#### Acceptance Criteria

**Gate definitions:**

1. THE LoopService SHALL evaluate each candidate through the following five gates in strict order. A candidate is fully validated only when it passes ALL five gates. Failing any gate immediately rejects the candidate for that iteration — remaining gates are skipped.

   At loop start, `LoopService` SHALL compute two non-overlapping sub-ranges from the total configured date range (`date_from` / `date_to`) using `oos_split_pct` (default 20%, configurable via `LoopConfig.oos_split_pct`, range 5–50):
   - **Training Range**: the half-open interval `[date_from, training_end_date)` — inclusive start, exclusive end. `training_end_date` is computed as `date_from + (1 - oos_split_pct/100) * total_duration`.
   - **OOS Range**: the closed interval `[training_end_date, date_to]` — inclusive start, inclusive end. The OOS range begins exactly at `training_end_date`, which is the first date NOT included in the Training Range.

   By this definition the two ranges share no data points: the Training Range excludes `training_end_date`, and the OOS Range begins at `training_end_date`. `LoopService` SHALL assert `training_end_date < date_to` before starting any iteration.

   - **Gate 1 — In-sample backtest**: Run a backtest on the **Training Range** only. The gate passes when ALL of the following hold simultaneously: `total_profit >= target_profit_pct`, `win_rate >= target_win_rate`, `max_drawdown <= target_max_drawdown`, `total_trades >= min_trades`.
   - **Gate 2 — Out-of-sample backtest**: Run a backtest on the **OOS Range** only (the last `oos_split_pct%` of the total date range). The gate passes when the same four targets from Gate 1 are independently satisfied on this held-out period.
   - **Gate 3 — Walk-forward validation**: Split the **Training Range** into `walk_forward_folds` equal folds (default 5, configurable via `LoopConfig.walk_forward_folds`, range 2–10). Run a separate backtest on each fold. Gate 3 does NOT touch the OOS Range. The gate passes when at least `(walk_forward_folds − 1)` folds satisfy `total_profit >= target_profit_pct` AND `total_trades >= min_trades` (exactly one fold is permitted to fail).
   - **Gate 4 — Stress test**: Re-run the backtest on the **Training Range** with fees multiplied by `stress_fee_multiplier` (default 2.0, configurable via `LoopConfig.stress_fee_multiplier`, range 1.0–5.0) and per-trade slippage of `stress_slippage_pct` percent (default 0.1, configurable via `LoopConfig.stress_slippage_pct`, range 0.0–2.0). The gate passes when `total_profit >= (target_profit_pct * stress_profit_target_pct / 100)` AND `max_drawdown <= target_max_drawdown`, where `stress_profit_target_pct` defaults to 50 (configurable via `LoopConfig.stress_profit_target_pct`, range 0–100).
   - **Gate 5 — Consistency check**: Using the per-fold profit values from Gate 3, compute the standard deviation of fold profits. This is a pure computation over Gate 3 fold results — no additional backtest is run. The gate passes when `std_dev(fold_profits) <= (consistency_threshold_pct / 100) * mean(fold_profits)`, where `consistency_threshold_pct` defaults to 30 (configurable via `LoopConfig.consistency_threshold_pct`, range 0–100). IF `mean(fold_profits)` is zero or negative, the gate SHALL fail unconditionally.

11. **Criterion 11 — Range boundary invariant**: The Training Range is `[date_from, training_end_date)` (exclusive end). The OOS Range is `[training_end_date, date_to]` (inclusive start and end). These two ranges are non-overlapping by construction. Gate 1, Gate 3, and Gate 4 SHALL use the Training Range. Gate 2 SHALL use the OOS Range. Gate 5 is a pure computation over Gate 3 fold results and requires no date range. See criterion 1 for the `training_end_date` computation.

**Termination:**

2. WHEN `LoopConfig.stop_on_first_profitable` is True and a candidate passes ALL five gates (or all two gates in "Quick" mode), THE LoopService SHALL set `LoopResult.target_reached = True`, set `LoopResult.stop_reason` to "All validation gates passed", and terminate the loop.
3. WHEN the iteration count reaches `LoopConfig.max_iterations`, THE LoopService SHALL set `LoopResult.stop_reason` to a message indicating the iteration limit was reached and terminate the loop.
4. WHEN `LoopService.stop()` is called externally, THE LoopService SHALL set its internal running flag to False so that `should_continue()` returns False on the next check.

**Validation mode:**

5. WHEN `LoopConfig.validation_mode` is `"quick"`, THE LoopService SHALL execute only Gate 1 and Gate 2 per iteration. A candidate is considered fully validated in Quick mode when it passes both of those gates.
6. WHEN `LoopConfig.validation_mode` is `"full"` (default), THE LoopService SHALL execute all five gates per iteration.

**Iteration recording:**

7. WHEN a gate fails for a candidate, THE LoopService SHALL record the gate failure as a `GateResult` with `passed=False` and a human-readable `failure_reason`, append it to `LoopIteration.gate_results`, set `LoopIteration.validation_gate_reached` to the name of that gate, set `LoopIteration.validation_gate_passed` to False, and skip all remaining gates for that iteration.
8. WHEN all required gates pass for a candidate, THE LoopService SHALL set `LoopIteration.validation_gate_reached` to the name of the last gate executed and set `LoopIteration.validation_gate_passed` to True.
9. A gate failure SHALL be treated as a "validation failure" for that iteration — it SHALL NOT increment the error counter or call `record_iteration_error()`. The loop SHALL continue to the next iteration normally.

**Pure helper:**

10. THE `targets_met()` function SHALL be a pure module-level function in `loop_service.py`, accepting a `BacktestSummary` and a `LoopConfig`, so that it can be tested independently. It SHALL return True only when ALL four conditions are simultaneously satisfied: `total_profit >= target_profit_pct`, `win_rate >= target_win_rate`, `max_drawdown <= target_max_drawdown`, `total_trades >= min_trades`.

---

### Requirement 11: Strategy Lab Tab — Best Result Review and Apply

**User Story:** As a strategy developer, I want to review the best result found by the loop and choose whether to apply it to my strategy, so that I remain in control of what gets written to my strategy file.

#### Acceptance Criteria

1. WHEN the loop finishes and `LoopResult.best_iteration` is not None, THE LoopPage SHALL display a **Best Result Found** panel showing: the iteration number, profit %, win rate, max drawdown, trade count, Sharpe ratio, and a human-readable summary of parameter changes from the original.
2. THE LoopPage SHALL display an **Apply Best Result to Strategy** button in the Best Result Found panel.
3. WHEN the user clicks **Apply Best Result to Strategy**, THE LoopPage SHALL display a confirmation dialog listing the parameter changes before proceeding.
4. WHEN the user confirms the apply action, THE LoopPage SHALL call `ImproveService.accept_candidate()` with the strategy name and best iteration's `params_after` dict.
5. WHEN `ImproveService.accept_candidate()` succeeds, THE LoopPage SHALL display a success message and hide the Best Result Found panel.
6. WHEN `ImproveService.accept_candidate()` raises an `OSError`, THE LoopPage SHALL display an error dialog with the exception message.
7. THE LoopPage SHALL display a **Discard** button in the Best Result Found panel that hides the panel without modifying any files.

---

### Requirement 12: Strategy Lab Tab — Live Terminal Output

**User Story:** As a strategy developer, I want to see the live stdout/stderr output of each backtest subprocess as it runs, so that I can monitor progress and diagnose failures.

#### Acceptance Criteria

1. THE LoopPage SHALL embed a `TerminalWidget` that displays live stdout and stderr from each backtest subprocess.
2. WHEN a new iteration starts, THE LoopPage SHALL append a separator line to the terminal output (e.g., `--- Iteration N/M ---`) before the subprocess output begins.
3. WHEN the initial backtest starts, THE LoopPage SHALL append a header line to the terminal output showing the strategy name and configured targets.
4. WHEN a backtest subprocess completes, THE LoopPage SHALL append a summary line to the terminal output showing the exit code and key result metrics.
5. THE LoopPage SHALL expose a `terminal` property returning the embedded `TerminalWidget`, so that `MainWindow._all_terminals` can include it for preference propagation.

---

### Requirement 13: Strategy Lab Tab — Configuration Guard

**User Story:** As a user who has not yet configured the app, I want the Strategy Lab tab to clearly tell me what is missing, so that I cannot accidentally start a loop with an invalid configuration.

#### Acceptance Criteria

1. THE LoopPage SHALL evaluate a `ConfigurationGuard` check on load and whenever `SettingsState.settings_changed` is emitted. The guard checks ALL of the following prerequisites:
   - `AppSettings.user_data_path` is set and the directory exists on disk.
   - `AppSettings.python_executable` (or `AppSettings.freqtrade_executable` when `use_module_execution=False`) exists on disk and is executable.
   - At least one strategy file exists under `{user_data_path}/strategies/`.
2. WHEN ALL prerequisites pass, THE LoopPage SHALL hide the warning banner and enable the strategy combo box and Start Loop button.
3. WHEN ANY prerequisite fails, THE LoopPage SHALL display a warning banner listing each failing prerequisite by name (e.g., "Python executable not found at {path}") and disable the strategy combo box and Start Loop button.
4. WHEN `SettingsState.settings_changed` is emitted, THE LoopPage SHALL re-run the `ConfigurationGuard` check and update the banner and control states accordingly.
5. WHEN the loop is actively running, THE LoopPage SHALL disable the Start Loop button and enable the Stop button regardless of settings state.

---

### Requirement 14: Strategy Lab Tab — Tab Registration in MainWindow

**User Story:** As a user, I want the Strategy Lab tab to appear in the main window alongside the other tabs, so that I can access it without any additional setup.

#### Acceptance Criteria

1. THE MainWindow SHALL instantiate `LoopPage` with `settings_state` and add it to the `QTabWidget` with the label "Strategy Lab".
2. THE MainWindow SHALL include the `LoopPage.terminal` widget in `_all_terminals` so that terminal preferences (font size, color scheme) are applied consistently.
3. WHEN the Strategy Lab tab is added, THE MainWindow SHALL position it after the Improve tab and before the Optimize tab in the tab order.

---

### Requirement 15: Improve Tab — Session History Persistence Within Run

**User Story:** As a strategy developer, I want the Improve tab to remember all the rounds I've run in the current session, so that I can compare my progress across multiple improvement iterations.

#### Acceptance Criteria

1. THE ImprovePage SHALL maintain an ordered list of accepted improvement rounds for the current session, where each entry records: round number, accepted parameters, and the key metrics (profit %, win rate, max drawdown, trade count) of the accepted candidate backtest.
2. WHEN the user accepts a candidate, THE ImprovePage SHALL append a new entry to the session history list.
3. WHEN the session history list contains at least one entry, THE ImprovePage SHALL display it in a scrollable panel within the page.
4. WHEN the user navigates away from the Improve tab and returns within the same application session, THE ImprovePage SHALL retain the session history list (in-memory only; no disk persistence required).
5. WHEN the user selects a different strategy from the strategy combo box, THE ImprovePage SHALL clear the session history list.

---

### Requirement 16: Improve Tab — Session History Data Model

**User Story:** As a strategy developer, I want the session history to capture a precise snapshot of each accepted round, so that rollback and comparison are always based on consistent, unambiguous data.

#### Acceptance Criteria

1. THE ImprovePage SHALL represent each accepted round using a `SessionRound` dataclass with the following fields:

   ```python
   @dataclass
   class SessionRound:
       round_number: int
       params_before: dict  # snapshot of SessionBaseline.params before this round's suggestions were applied
       params_after: dict   # accepted candidate params
       summary: BacktestSummary  # metrics of the accepted candidate backtest
       timestamp: datetime
   ```

2. WHEN the user accepts a candidate, THE ImprovePage SHALL construct a `SessionRound` from the current `SessionBaseline.params` (as `params_before`), the accepted candidate params (as `params_after`), the candidate `BacktestSummary`, and the current UTC timestamp.
3. THE ImprovePage SHALL append the new `SessionRound` to an ordered in-memory list (`_session_history: List[SessionRound]`).
4. WHEN the user clicks **Rollback**, THE ImprovePage SHALL pop the last `SessionRound` from `_session_history` and restore `SessionBaseline.params` to that round's `params_before` — it SHALL NOT re-read from disk.
5. WHEN the user selects a different strategy, THE ImprovePage SHALL clear `_session_history` and reset `SessionBaseline`.

---

### Requirement 17: Loop Models — LoopIteration and GateResult Data Models

**User Story:** As a developer implementing LoopService, I want fully-specified `LoopIteration` and `GateResult` dataclasses so that every field is unambiguous and no implementation decisions are left open.

#### Acceptance Criteria

1. THE `GateResult` dataclass in `app/core/models/loop_models.py` SHALL have exactly the following fields:

   ```python
   @dataclass
   class GateResult:
       gate_name: str                              # "in_sample" | "out_of_sample" | "walk_forward" | "stress_test" | "consistency"
       passed: bool
       metrics: Optional[BacktestSummary]          # populated for in_sample, out_of_sample, stress_test; None for walk_forward and consistency
       fold_summaries: Optional[list[BacktestSummary]]  # populated for walk_forward; None for all other gates
       failure_reason: Optional[str]               # human-readable explanation when passed=False; None when passed=True
   ```

2. THE `gate_name` field of `GateResult` SHALL only ever contain one of the five string literals: `"in_sample"`, `"out_of_sample"`, `"walk_forward"`, `"stress_test"`, `"consistency"`.
3. WHEN `GateResult.passed` is True, `failure_reason` SHALL be None.
4. WHEN `GateResult.passed` is False, `failure_reason` SHALL be a non-empty string.

5. THE `LoopIteration` dataclass in `app/core/models/loop_models.py` SHALL have exactly the following fields:

   ```python
   @dataclass
   class LoopIteration:
       iteration_number: int
       params_before: dict          # params at start of this iteration
       params_after: dict           # mutated params used for this iteration's backtest
       changes_summary: list[str]   # human-readable list of what changed, e.g. ["stoploss: -0.10 → -0.08"]
       summary: Optional[BacktestSummary]   # in-sample BacktestSummary from gate 1; None if gate 1 backtest failed
       score: Optional[RobustScore]         # None if not scored
       is_improvement: bool
       status: str                  # "success" | "error" | "zero_trades" | "hard_filter_rejected"
       error_message: Optional[str]
       below_min_trades: bool
       sandbox_path: Path
       validation_gate_reached: str         # name of the last gate attempted ("in_sample", "out_of_sample", "walk_forward", "stress_test", "consistency")
       validation_gate_passed: bool         # True only when the candidate passed all required gates
       gate_results: list[GateResult]       # one entry per gate attempted, in execution order
       hard_filter_failures: list[HardFilterFailure]  # populated when status="hard_filter_rejected"; empty list otherwise
   ```

6. THE `status` field SHALL only ever contain one of the four string literals: `"success"`, `"error"`, `"zero_trades"`, or `"hard_filter_rejected"`.
7. WHEN `status` is `"error"`, `error_message` SHALL be a non-empty string describing the failure.
8. WHEN `status` is `"success"` or `"zero_trades"`, `error_message` SHALL be None.
9. WHEN `below_min_trades` is True, `is_improvement` SHALL always be False.
10. WHEN `validation_gate_passed` is False, `is_improvement` SHALL always be False.

---

### Requirement 18: Sandbox Lifecycle Management

**User Story:** As a developer, I want sandbox directories to follow a strict naming convention and be cleaned up deterministically, so that disk space is not wasted and debugging artifacts are preserved when needed.

#### Acceptance Criteria

1. THE sandbox path for every candidate run SHALL follow the format: `{user_data}/strategies/_improve_sandbox/{strategy_name}_{timestamp_ms}/` where `timestamp_ms` is the Unix timestamp in milliseconds at the moment `ImproveService.prepare_sandbox()` is called. Each directory is created once per run and is never reused.
2. Both ImprovePage and LoopPage SHALL use `ImproveService.prepare_sandbox()` to create sandbox directories — neither page SHALL construct sandbox paths directly.
3. WHEN the user accepts a candidate in ImprovePage, `ImproveService.accept_candidate()` SHALL delete the sandbox directory for that candidate after writing the accepted params to the live strategy JSON.
4. WHEN the user rejects or discards a candidate in ImprovePage, `ImproveService.reject_candidate()` SHALL delete the sandbox directory for that candidate.
5. WHEN a subprocess exits with a non-zero exit code (in either ImprovePage or LoopPage), the sandbox directory for that run SHALL be retained on disk for debugging and its path SHALL be logged at WARNING level via `_log.warning`.
6. WHEN LoopPage starts (before the first iteration begins), THE LoopPage SHALL delete any stale sandbox directories under `{user_data}/strategies/_improve_sandbox/` that are older than 24 hours. Deletion SHALL be silent (no user-visible message) and SHALL NOT block the UI thread.

7. **Artifact directory contract**: Every backtest command issued by either ImprovePage or LoopPage SHALL pass `--backtest-directory {export_dir}` to Freqtrade, where `export_dir` is a deterministic per-run directory created inside the sandbox before the subprocess starts. The `export_dir` path SHALL follow the format:
   - For ImprovePage candidate runs: `{sandbox_dir}/backtest_output/`
   - For LoopPage gate runs: `{sandbox_dir}/gate_{gate_name}_{n}/` where `gate_name` is one of `in_sample`, `out_of_sample`, `fold_{k}`, `stress_test` and `n` is the iteration number.

   Each `export_dir` is created once per run and is never reused. Freqtrade writes a `.zip` result file into this directory.

   After subprocess completion, `ImproveService.resolve_candidate_artifact(export_dir: Path) -> Path` SHALL locate the single `.zip` file written by Freqtrade into `export_dir` and return its path. If exactly one `.zip` is found, it is returned directly. If zero `.zip` files are found, `FileNotFoundError` SHALL be raised with `export_dir` in the message.

   `ImproveService.parse_candidate_run(export_dir: Path)` SHALL accept the export directory as its parameter — it SHALL NOT accept a file path. It calls `resolve_candidate_artifact(export_dir)` internally to locate the zip before parsing.

   The `--export-filename` flag SHALL NOT be used — it is deprecated in Freqtrade and not supported.

---

### Requirement 19: UI State Transitions — Explicit Button and Control Rules

**User Story:** As a developer implementing the UI, I want every button and control state to be fully specified for each workflow phase, so that there is no ambiguity about what is enabled or visible at any point.

#### Acceptance Criteria

**ImprovePage state machine:**

1. WHILE no strategy is selected (idle, no strategy): THE ImprovePage SHALL disable the Analyze button and enable the strategy combo box. Accept, Reject, Rollback, and Run Another Round buttons SHALL be hidden.
2. WHILE a strategy is selected but no run has been started (idle, strategy selected): THE ImprovePage SHALL enable the Analyze button and enable the strategy combo box. Accept, Reject, Rollback, and Run Another Round buttons SHALL be hidden.
3. WHILE a subprocess is actively running (running state): THE ImprovePage SHALL disable the Analyze button, disable the strategy combo box, and show the Stop button. Accept and Reject buttons SHALL be hidden.
4. WHEN a candidate backtest completes and is awaiting a user decision (awaiting decision state): THE ImprovePage SHALL show the Accept and Reject buttons, disable the Analyze button, and keep the strategy combo box disabled.
5. WHEN at least one round has been accepted (post-accept state): THE ImprovePage SHALL show the Rollback button and the Run Another Round button in addition to the controls appropriate for the current sub-state.

**LoopPage state machine:**

6. WHILE no strategy is selected (idle, no strategy): THE LoopPage SHALL disable the Start Loop button. Stop button SHALL be hidden.
7. WHILE a strategy is selected but no loop is running (idle, strategy selected): THE LoopPage SHALL enable the Start Loop button. Stop button SHALL be hidden. Strategy combo box and all config spin boxes SHALL be enabled.
8. WHILE a loop is actively running (running state): THE LoopPage SHALL disable the Start Loop button, show the Stop button, disable the strategy combo box, and disable all configuration spin boxes.
9. WHEN the loop finishes and a best result is available (finalizing state): THE LoopPage SHALL show the Apply Best Result button and the Discard button. Start Loop button SHALL be re-enabled.
10. WHEN the user applies or discards the best result (post-apply/discard state): THE LoopPage SHALL hide the Best Result panel, re-enable the Start Loop button, and re-enable all controls.

---

### Requirement 20: Error Taxonomy and Exception Handling

**User Story:** As a developer implementing LoopService and ImproveService, I want every error category to have a defined exception type and a specified handling strategy, so that error paths are consistent and predictable.

#### Acceptance Criteria

1. WHEN a subprocess exits with a non-zero exit code, `LoopService.record_iteration_error()` SHALL be called with the exit code and stderr content. The sandbox directory SHALL be retained. The loop SHALL continue to the next iteration if `LoopService.should_continue()` returns True.
2. WHEN `ImproveService.parse_candidate_run()` raises `FileNotFoundError` or `json.JSONDecodeError`, THE LoopPage SHALL treat the failure identically to a non-zero subprocess exit — calling `LoopService.record_iteration_error()` and continuing if budget allows. The sandbox directory SHALL be retained.
3. WHEN `ImproveService` raises `ValueError` during settings or configuration validation before a loop or candidate run starts, THE LoopPage or ImprovePage SHALL display the error message in a banner and SHALL NOT start the run.
4. WHEN an `OSError` occurs during sandbox directory creation inside `ImproveService.prepare_sandbox()`, THE LoopPage SHALL display the error in the terminal output, stop the loop entirely (the error is not recoverable mid-run), and transition to the finalized state. ImprovePage SHALL display the error in a status message and return to the idle state.
5. WHEN `ImproveService.accept_candidate()` raises `OSError` during the write to the live strategy JSON, THE ImprovePage or LoopPage SHALL display an error dialog with the exception message and SHALL NOT update the in-memory `SessionBaseline`.

---

### Requirement 21: Strategy Lab Tab — Layer 1 Hard Filters (Candidate Pre-Qualification)

**User Story:** As a strategy developer, I want candidates that are statistically meaningless or obviously unfit to be rejected immediately — before the validation ladder runs — so that the iteration budget is not wasted on hopeless candidates.

#### Acceptance Criteria

**Hard filter evaluation:**

1. THE LoopService SHALL evaluate hard filters at three specific points during each iteration, interleaved with the validation ladder:
   - **Filters 1–7** are evaluated AFTER Gate 1 completes and BEFORE Gate 2 starts, using the Gate 1 `BacktestSummary`. A candidate that fails any of filters 1–7 is immediately rejected — Gates 2, 3, 4, and 5 SHALL NOT be executed for that candidate.
   - **Filter 8 (`oos_negativity`)** is evaluated AFTER Gate 2 completes and BEFORE Gate 3 starts. A candidate that fails filter 8 is immediately rejected — Gates 3, 4, and 5 SHALL NOT be executed for that candidate.
   - **Filter 9 (`validation_variance`)** is evaluated AFTER Gate 3 completes and BEFORE Gate 4 starts. A candidate that fails filter 9 is immediately rejected — Gates 4 and 5 SHALL NOT be executed for that candidate.

   In all three cases, hard filter failures are recorded in `LoopIteration.hard_filter_failures`, `LoopIteration.status` is set to `"hard_filter_rejected"`, and the loop continues to the next iteration normally without incrementing the error counter.

   Note: A candidate is rejected as soon as any filter in a stage fails. However, all remaining filters in the same stage are still evaluated and recorded in `hard_filter_failures` to provide complete diagnostic evidence. Rejection is logical (no further gates run) but evidence collection within the same stage continues.

2. Hard filter failures SHALL be recorded in `LoopIteration.hard_filter_failures` and SHALL NOT increment the error counter or call `record_iteration_error()`. The loop SHALL continue to the next iteration normally.

3. WHEN a candidate is rejected by hard filters, `LoopIteration.status` SHALL be set to `"hard_filter_rejected"` and `LoopIteration.is_improvement` SHALL be False.

4. THE hard filters SHALL be evaluated in the following order. A candidate is rejected as soon as any filter fails (remaining filters are still evaluated and recorded):

   | # | Filter name | Rejection condition | Default threshold | Reason |
   |---|-------------|--------------------|--------------------|--------|
   | 1 | `min_trade_count` | `total_trades < min_trades` | `LoopConfig.min_trades` | "Insufficient trades for statistical significance." |
   | 2 | `max_drawdown` | `max_drawdown > target_max_drawdown` | `LoopConfig.target_max_drawdown` | "Max drawdown exceeds threshold." |
   | 3 | `profit_concentration` | top 3 trades > `profit_concentration_threshold` of total profit | 0.50 | "Profit concentrated in too few trades — result not reproducible." |
   | 4 | `profit_factor_floor` | `profit_factor < profit_factor_floor` | 1.1 | "Profit factor below minimum threshold." |
   | 5 | `expectancy_floor` | `expectancy <= 0.0` | — | "Non-positive expectancy — strategy loses money on average per trade." |
   | 6 | `pair_dominance` | single pair > `pair_dominance_threshold` of total profit | 0.60 | "Returns dominated by one pair — strategy not diversified." |
   | 7 | `time_dominance` | single calendar week or month > `time_dominance_threshold` of total profit | 0.40 | "Returns dominated by one time period — strategy not temporally stable." |
   | 8 | `oos_negativity` | out-of-sample total profit < 0 (evaluated immediately after gate 2 completes) | — | "Out-of-sample result is negative — strategy likely overfit." |
   | 9 | `validation_variance` | CV of per-fold profits from walk-forward > `validation_variance_ceiling` when mean > 0 | 1.0 | "Walk-forward variance too high — strategy is unstable across time periods." |

   Filters 1–7 are evaluated after Gate 1 completes and before Gate 2 starts. Filter 8 is evaluated immediately after Gate 2 completes. Filter 9 is evaluated immediately after Gate 3 completes.

**HardFilterFailure model:**

5. THE `HardFilterFailure` dataclass SHALL be defined in `app/core/models/loop_models.py`:

   ```python
   @dataclass
   class HardFilterFailure:
       filter_name: str   # e.g. "profit_concentration", "pair_dominance"
       reason: str        # human-readable rejection reason
       evidence: str      # e.g. "top 3 trades = 67% of profit"
   ```

**HardFilterService:**

6. THE hard filter evaluation SHALL be implemented in a `HardFilterService` class at `app/core/services/hard_filter_service.py` with two static methods:

   ```python
   @staticmethod
   def evaluate_post_gate1(
       gate1_result: GateResult,
       config: LoopConfig
   ) -> list[HardFilterFailure]:
       """Runs filters 1–7. Called after Gate 1 completes, before Gate 2 starts.
       gate1_result.metrics holds the in-sample BacktestSummary."""
       ...

   @staticmethod
   def evaluate_post_gate(
       gate_name: str,           # "out_of_sample" or "walk_forward"
       gate_result: GateResult,
       config: LoopConfig
   ) -> list[HardFilterFailure]:
       """Runs filter 8 after Gate 2, filter 9 after Gate 3.
       gate_result.metrics holds the OOS summary for filter 8.
       gate_result.fold_summaries holds the fold list for filter 9."""
       ...
   ```

   `evaluate_post_gate1` SHALL return an empty list when all filters 1–7 pass, or a list of one or more `HardFilterFailure` objects when one or more filters fail.

   `evaluate_post_gate` SHALL return an empty list when the applicable filter passes, or a list containing one `HardFilterFailure` when it fails. If `evaluate_post_gate` returns any failures, the iteration is immediately rejected (`status="hard_filter_rejected"`, remaining gates skipped, loop continues) — identical to a post-gate1 rejection.

   The execution order for hard filter evaluation is:
   - Filters 1–7: called via `evaluate_post_gate1(gate1_result, config)` AFTER Gate 1 completes and BEFORE Gate 2 starts.
   - Filter 8 (`oos_negativity`): called via `evaluate_post_gate("out_of_sample", gate2_result, config)` after Gate 2, before Gate 3.
   - Filter 9 (`validation_variance`): called via `evaluate_post_gate("walk_forward", gate3_result, config)` after Gate 3, before Gate 4.

**LoopConfig fields:**

7. THE `LoopConfig` dataclass SHALL include the following hard-filter threshold fields with the stated defaults:
   - `profit_concentration_threshold: float = 0.50`
   - `profit_factor_floor: float = 1.1`
   - `pair_dominance_threshold: float = 0.60`
   - `time_dominance_threshold: float = 0.40`
   - `validation_variance_ceiling: float = 1.0`

**UI display:**

8. THE LoopPage iteration history row SHALL display hard-filter-rejected iterations with an orange left border and a "FILTERED" badge.
9. THE LoopPage iteration history row for a hard-filter-rejected iteration SHALL list the `filter_name` values of all triggered filters.

---

### Requirement 22: Strategy Lab Tab — Structural Diagnosis Layer

**User Story:** As a strategy developer, I want the diagnosis system to identify the root cause of strategy failure using named structural patterns — not just surface-level parameter suggestions — so that I understand *why* the strategy is failing and what structural change is needed.

#### Acceptance Criteria

**StructuralDiagnosis model:**

1. THE `StructuralDiagnosis` dataclass SHALL be defined in `app/core/models/diagnosis_models.py`:

   ```python
   @dataclass
   class StructuralDiagnosis:
       failure_pattern: str      # short label, e.g. "high_trade_count_low_expectancy"
       evidence: str             # e.g. "avg win/loss ratio = 0.6, 73% of trades are losses < 0.3%"
       root_cause: str           # e.g. "entries too permissive in sideways conditions"
       mutation_direction: str   # e.g. "tighten entry confirmation or add regime filter"
       confidence: float         # 0.0–1.0
       severity: str             # "critical" | "moderate" | "advisory"
   ```

**Diagnosis rules:**

2. THE `ResultsDiagnosisService.diagnose()` method SHALL detect the following named failure patterns. Each rule has a `min_confidence` threshold below which it is suppressed (not returned). Default thresholds: critical rules 0.6, moderate rules 0.5, advisory rules 0.4.

   | Pattern label | Severity | Detection criteria | Root cause | Mutation direction |
   |---------------|----------|--------------------|------------|--------------------|
   | `entries_too_loose_in_chop` | critical | high trade count, win_rate < 45%, avg_loss < 0.5%, avg_trade_duration short | entries fire in sideways/choppy conditions | tighten entry confirmation, add trend filter or volatility regime filter |
   | `entries_too_late_in_trend` | moderate | low trade count, high win rate but low total profit, avg_trade_duration long, few trades per month | entries trigger after most of the move has occurred | use earlier signal (lower timeframe confirmation, reduce lag on indicator) |
   | `exits_cutting_winners_early` | moderate | win_rate > 60% but profit_factor < 1.3, avg_win < avg_loss | ROI table or trailing stop exits too early | widen ROI targets or increase trailing stop distance |
   | `losers_lasting_too_long` | moderate | low win rate, avg losing trade duration significantly longer than avg winning trade duration | stoploss too wide or not triggered | tighten stoploss or add time-based exit |
   | `single_regime_dependency` | critical | in-sample profit > target, OOS profit < 0 or < 50% of in-sample | strategy tuned to one market regime | add regime detection, reduce lookback, or test on more diverse data |
   | `micro_loss_noise` | moderate | > 60% of trades have loss < 0.2%, high trade count | strategy enters on noise signals | add minimum move filter or increase minimum signal strength |
   | `filter_stack_too_strict` | advisory | < 0.5 trades per day on a 6-month+ backtest | too many entry conditions stacked | relax threshold parameters (e.g., widen RSI range, reduce confirmation multiplier, increase lookback tolerance) |
   | `high_winrate_bad_payoff` | moderate | win_rate > 65% but profit_factor < 1.2, avg_win much smaller than avg_loss | asymmetric risk/reward — taking small wins and large losses | widen profit targets, tighten stoploss, or invert risk/reward ratio |
   | `outlier_trade_dependency` | moderate | top 3 trades > 40% of total profit | strategy relies on rare large moves | reduce position sizing on outlier conditions or add diversification |
   | `drawdown_after_volatility` | advisory | largest drawdown periods overlap with ATR spikes | strategy not adapted to volatility expansion | add volatility filter or reduce position size during high-ATR periods |

3. THE `ResultsDiagnosisService.diagnose()` method SHALL always return a `DiagnosisBundle`. The `bundle.issues` list contains legacy `DiagnosedIssue` objects for backward compatibility. The `bundle.structural` list contains `StructuralDiagnosis` objects from the pattern-based rules. Both lists may be empty. Neither list is ever None.

   The `DiagnosisBundle` dataclass SHALL be defined in `app/core/models/diagnosis_models.py`:

   ```python
   @dataclass
   class DiagnosisBundle:
       issues: list[DiagnosedIssue]              # legacy shallow issues (may be empty)
       structural: list[StructuralDiagnosis]     # pattern-based root-cause diagnoses (may be empty)
   ```

   The `DiagnosisInput` dataclass SHALL be defined in `app/core/models/diagnosis_models.py`:

   ```python
   @dataclass
   class DiagnosisInput:
       in_sample: BacktestSummary                          # always present
       oos_summary: Optional[BacktestSummary]              # from Gate 2; None if not yet run or Quick mode
       fold_summaries: Optional[list[BacktestSummary]]     # from Gate 3 walk-forward; None if not yet run or Quick mode
       trade_profit_contributions: Optional[list[float]]   # per-trade profit as fraction of total profit, sorted descending; None if not available
       drawdown_periods: Optional[list[tuple[str, str, float]]]  # list of (start_date, end_date, drawdown_pct) for each drawdown episode
       atr_spike_periods: Optional[list[tuple[str, str]]]  # list of (start_date, end_date) for high-ATR periods; None if not available
   ```

   The `ResultsDiagnosisService.diagnose()` signature SHALL be:

   ```python
   @staticmethod
   def diagnose(input: DiagnosisInput) -> DiagnosisBundle:
       ...
   ```

   The detection criteria for the three rules that require additional data beyond `in_sample` are:
   - `single_regime_dependency`: uses `input.in_sample` and `input.oos_summary`. IF `oos_summary` is None, this rule is suppressed (not returned).
   - `outlier_trade_dependency`: uses `input.trade_profit_contributions`. IF None, this rule is suppressed.
   - `drawdown_after_volatility`: uses `input.drawdown_periods` and `input.atr_spike_periods`. IF either is None, this rule is suppressed.

   All other rules use only `input.in_sample` and are unaffected by the presence or absence of the optional fields.

**Suggestion mapping:**

4. THE `RuleSuggestionService.suggest()` method SHALL consume `StructuralDiagnosis` objects and map each `mutation_direction` to one or more concrete `ParameterSuggestion` objects using rule-specific (not generic) mappings. Examples:
   - `exits_cutting_winners_early` → suggest increasing ROI table values by 20–50%, or increasing trailing stop distance.
   - `losers_lasting_too_long` → suggest reducing stoploss by 10–30%.
   - `filter_stack_too_strict` → suggest widening the most restrictive threshold parameter (e.g., increase RSI upper bound, reduce minimum volume multiplier, widen ATR filter range).

   All `ParameterSuggestion` objects produced by `RuleSuggestionService.suggest()` SHALL target JSON-configurable parameters only (ROI table, stoploss, trailing stop, buy/sell threshold values). No suggestion SHALL instruct the user to add, remove, or modify Python source code logic. This constraint applies to all 10 structural diagnosis rules without exception.

**UI display:**

5. THE ImprovePage SHALL display `StructuralDiagnosis` objects from `bundle.structural` in the diagnostics panel, showing: `failure_pattern` label, `evidence` text, `root_cause`, `mutation_direction`, and a confidence bar.
6. THE severity SHALL determine the badge color: `"critical"` → red, `"moderate"` → orange, `"advisory"` → yellow.

---

## Implementation Order (Non-Normative)

The following phase order is recommended to minimize integration risk and allow incremental testing. It is not a normative requirement — teams may deviate if justified.

- **Phase 1 — Pure helpers and models**: Implement `compute_highlight`, `compute_score` (accepting `RobustScoreInput`, returning `RobustScore`), `targets_met`, `_normalize_summary`, `GateResult` dataclass, `LoopIteration` dataclass (full field set including `validation_gate_reached`, `validation_gate_passed`, `gate_results`, `hard_filter_failures`), `SessionRound` dataclass, `SessionBaseline` dataclass, `HardFilterFailure` dataclass, `RobustScoreInput` dataclass, `RobustScore` dataclass, `StructuralDiagnosis` dataclass. These are pure functions and data structures with no UI or Qt dependencies and can be fully unit-tested in isolation.

- **Phase 2 — ImprovePage upgrade**: Add `SessionBaseline` tracking, `_session_history` stack, rollback logic, baseline population from run store (or fresh backtest), strategy-switch lock during subprocess, deeper diagnostics display (including `StructuralDiagnosis` objects in the diagnostics panel with confidence bar and severity badge), candidate comparison table, and `--backtest-directory {export_dir}` deterministic artifact resolution.

- **Phase 3 — LoopService state machine**: Implement `start`, `prepare_next_iteration`, `record_iteration_result`, `record_iteration_error`, `should_continue`, `stop`, `finalize`, and best-result tracking. Include `zero_trades` and `below_min_trades` guards. Implement `SuggestionRotator` variation logic. Implement `HardFilterService.evaluate_post_gate1()` (filters 1–7, called after Gate 1 and before Gate 2) and `HardFilterService.evaluate_post_gate()` (filter 8 called after Gate 2, filter 9 called after Gate 3). Set `status="hard_filter_rejected"` and populate `hard_filter_failures` when any filter fails. Implement the multi-gate validation ladder: LoopService must orchestrate sequential gate execution per iteration — issuing separate backtest commands for in-sample, out-of-sample, each walk-forward fold, and stress-test gates — short-circuiting on the first gate failure and populating `gate_results` on the `LoopIteration`. Apply out-of-sample negativity filter (filter 8) immediately after gate 2 and validation variance filter (filter 9) immediately after gate 3. Implement `consistency_check` as a pure computation over fold summaries (no additional backtest required). Replace old `compute_score(BacktestSummary)` with new `compute_score(RobustScoreInput) -> RobustScore`.

- **Phase 4 — LoopPage UI**: Config controls (spin boxes including the six new validation parameters and five new hard-filter threshold controls under a collapsible "Advanced Filters" section, Validation Mode selector, checkbox, strategy combo), terminal widget, iteration history list with `IterationHistoryRow` widgets (including gate progress indicator, partial-validation badge, and orange "FILTERED" badge with filter names for hard-filter-rejected iterations), progress bar, live stat cards, best result review panel (Apply / Discard), stale sandbox cleanup on startup, and strategy-switch lock during loop.

- **Phase 5 — MainWindow tab registration and terminal preference propagation**: Instantiate `LoopPage`, add it to `QTabWidget` after the Improve tab, include `LoopPage.terminal` in `_all_terminals`.
