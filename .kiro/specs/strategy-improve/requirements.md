# Requirements Document

## Introduction

The Strategy Improve feature adds an "Improve" tab to the Freqtrade GUI desktop application, positioned between the Backtest and Optimize tabs. It provides a result-driven improvement loop: the page reads a saved backtest run for a selected strategy, diagnoses performance issues using rule-based heuristics, generates concrete parameter-change suggestions, lets the user apply those suggestions as a candidate configuration, re-runs a backtest against the candidate, and then presents a side-by-side comparison so the user can accept, reject, or continue iterating. No AI or external services are involved in this slice — all diagnosis and suggestion logic is rule-based.

---

## Glossary

- **ImprovePage**: The PySide6 `QWidget` page that hosts the full improvement workflow UI.
- **ImproveService**: The service layer class that orchestrates loading runs, invoking diagnosis, and invoking suggestion generation.
- **ResultsDiagnosisService**: The stateless service that inspects a `BacktestSummary` and returns a list of `DiagnosedIssue` objects.
- **RuleSuggestionService**: The stateless service that maps a list of `DiagnosedIssue` objects to a list of `ParameterSuggestion` objects.
- **CandidateConfig**: An in-memory snapshot of strategy parameters (`stoploss`, `minimal_roi`, `max_open_trades`, `buy_params`, `sell_params`) that represents a proposed change set derived from applied suggestions.
- **BaselineRun**: The `BacktestResults` loaded from the `RunStore` that serves as the reference point for comparison.
- **CandidateRun**: The `BacktestResults` produced by running a backtest with the `CandidateConfig` applied.
- **DiagnosedIssue**: A typed data object describing a single detected performance problem (e.g. stoploss too wide, win rate too low).
- **ParameterSuggestion**: A typed data object describing a single rule-based parameter change, including the target parameter, proposed value, human-readable reason, and expected effect.
- **RunStore**: Existing service at `app/core/backtests/results_store.py` that persists and loads backtest run folders. `load_run()` reconstructs `BacktestResults` from `results.json` and `trades.json` only; `params.json` must be loaded separately.
- **BaselineParams**: A plain `dict` loaded from `params.json` in the selected run folder, containing `buy_params`, `sell_params`, `minimal_roi`, and `stoploss`. Loaded separately from `RunStore.load_run()` and used as the reference for candidate configuration diffs.
- **IndexStore**: Existing service at `app/core/backtests/results_index.py` that maintains per-strategy run indexes.
- **BacktestResults**: Existing dataclass at `app/core/backtests/results_models.py` containing `BacktestSummary` and a list of `BacktestTrade`.
- **BacktestSummary**: Existing dataclass with aggregate metrics: `strategy`, `timeframe`, `total_trades`, `wins`, `losses`, `draws`, `win_rate`, `avg_profit`, `total_profit`, `total_profit_abs`, `sharpe_ratio`, `sortino_ratio`, `calmar_ratio`, `max_drawdown`, `max_drawdown_abs`, `trade_duration_avg`, `starting_balance`, `final_balance`, `timerange`, `pairlist`, `backtest_start`, `backtest_end`, `expectancy`, `profit_factor`, `max_consecutive_wins`, `max_consecutive_losses`.
- **SettingsState**: Existing `QObject` subclass that holds `AppSettings` and emits `settings_changed`.
- **BacktestService**: Existing service at `app/core/services/backtest_service.py` used to build and execute backtest commands.
- **ProcessService**: Existing service at `app/core/services/process_service.py` that manages `QProcess` execution.

---

## Requirements

### Requirement 1: Improve Tab Integration

**User Story:** As a Freqtrade GUI user, I want an "Improve" tab between Backtest and Optimize, so that I can access the improvement workflow without disrupting my existing navigation.

#### Acceptance Criteria

1. THE `MainWindow` SHALL insert the Improve tab immediately after the existing Backtest tab and immediately before the existing Optimize tab, preserving the rest of the current tab order.
2. THE `ImprovePage` SHALL accept a `SettingsState` instance via its constructor and SHALL NOT instantiate `SettingsState` itself.
3. WHEN `SettingsState` emits `settings_changed`, THE `ImprovePage` SHALL refresh its strategy selector to reflect the updated `user_data_path`.

---

### Requirement 2: Strategy and Run Selection

**User Story:** As a user, I want to select a strategy and a specific saved run to analyze, so that I can target the improvement workflow at a particular backtest result.

#### Acceptance Criteria

1. THE `ImprovePage` SHALL display a strategy selector combo box populated from `BacktestService.get_available_strategies()` using the current `SettingsState`.
2. THE `ImprovePage` SHALL display a run selector combo box that lists all saved runs for the selected strategy, retrieved via `IndexStore.get_strategy_runs(backtest_results_dir, strategy)` where `backtest_results_dir` is `{user_data_path}/backtest_results/`, showing run ID, profit percentage, trade count, and saved timestamp for each entry.
3. WHEN the strategy selector value changes, THE `ImprovePage` SHALL repopulate the run selector with runs for the newly selected strategy.
4. THE `ImprovePage` SHALL display a "Load Latest" button that, when clicked, selects the most recently saved run for the current strategy in the run selector.
5. IF no saved runs exist for the selected strategy, THEN THE `ImprovePage` SHALL display the message "No saved runs found for this strategy" in the run selector and SHALL disable the "Analyze" button.

---

### Requirement 3: Load and Display Baseline Run Summary

**User Story:** As a user, I want to load a saved backtest run and see its key metrics summarized, so that I understand the baseline before applying improvements.

#### Acceptance Criteria

1. THE `ImprovePage` SHALL display an "Analyze" button that, when clicked, loads the selected run via `RunStore.load_run()` and stores it as the `BaselineRun`.
2. WHEN the `BaselineRun` is loaded, THE `ImprovePage` SHALL display the following summary metrics: strategy name, timeframe, total trades, win rate (%), total profit (%), max drawdown (%), Sharpe ratio, and backtest date range.
3. IF `RunStore.load_run()` raises `FileNotFoundError` or `ValueError`, THEN THE `ImprovePage` SHALL display an error message containing the exception text and SHALL NOT update the `BaselineRun`.
4. WHILE a run is being loaded, THE `ImprovePage` SHALL disable the "Analyze" button to prevent concurrent load operations.
5. WHEN the `BaselineRun` is loaded, THE `ImproveService` SHALL also read the `params.json` file from the same run folder as a separate `BaselineParams` snapshot (a plain dict containing `buy_params`, `sell_params`, `minimal_roi`, `stoploss`). This snapshot SHALL be stored independently of the `BacktestResults` object and SHALL serve as the reference for candidate diff computation.

---

### Requirement 4: Issue Diagnosis

**User Story:** As a user, I want the app to automatically detect performance issues in my backtest results, so that I know what problems need to be addressed.

#### Acceptance Criteria

1. WHEN the `BaselineRun` is loaded, THE `ResultsDiagnosisService` SHALL evaluate the `BacktestSummary` against all diagnostic rules and return a list of zero or more `DiagnosedIssue` objects.
2. THE `ResultsDiagnosisService` SHALL detect the issue "stoploss_too_wide" WHEN `BacktestSummary.max_drawdown` exceeds 20.0%.
3. THE `ResultsDiagnosisService` SHALL detect the issue "trades_too_low" WHEN `BacktestSummary.total_trades` is fewer than 30 trades over the backtest period.
4. THE `ResultsDiagnosisService` SHALL detect the issue "weak_win_rate" WHEN `BacktestSummary.win_rate` is below 45.0%.
5. THE `ResultsDiagnosisService` SHALL detect the issue "drawdown_high" WHEN `BacktestSummary.max_drawdown` exceeds 30.0%.
6. THE `ResultsDiagnosisService` SHALL detect the issue "poor_pair_concentration" WHEN fewer than 3 pairs are present in `BacktestSummary.pairlist`.
7. THE `ResultsDiagnosisService` SHALL detect the issue "negative_profit" WHEN `BacktestSummary.total_profit` is less than 0.0%.
8. THE `ImprovePage` SHALL display each `DiagnosedIssue` in the "Detected Issues" panel, showing the issue name and a human-readable description.
9. IF no issues are detected, THEN THE `ImprovePage` SHALL display the message "No issues detected — results look healthy" in the Detected Issues panel.

---

### Requirement 5: Rule-Based Suggestions

**User Story:** As a user, I want to see concrete parameter-change suggestions for each detected issue, so that I know what to try next.

#### Acceptance Criteria

1. WHEN `ResultsDiagnosisService` returns a non-empty list of `DiagnosedIssue` objects, THE `RuleSuggestionService` SHALL map each issue to one or more `ParameterSuggestion` objects and return the combined list.
2. FOR the issue "stoploss_too_wide", THE `RuleSuggestionService` SHALL suggest tightening `stoploss` by reducing its absolute value by 0.02 (e.g. -0.10 → -0.08), with reason "Stoploss is too wide — tightening reduces per-trade loss exposure" and expected effect "Lower max drawdown, smaller individual losses".
3. FOR the issue "trades_too_low", THE `RuleSuggestionService` SHALL suggest increasing `max_open_trades` by 1 (capped at 10), with reason "Too few trades reduce statistical significance" and expected effect "More trades, better statistical confidence".
4. FOR the issue "weak_win_rate", THE `RuleSuggestionService` SHALL suggest adjusting the ROI tier with the smallest numeric key (e.g. key `"0"` after sorting keys as integers) to reduce the target profit by 0.005 (e.g. 0.02 → 0.015), with reason "Lowering ROI target increases the chance of hitting take-profit" and expected effect "Higher win rate, lower average profit per trade".
5. FOR the issue "drawdown_high", THE `RuleSuggestionService` SHALL suggest reducing `max_open_trades` by 1 (minimum 1), with reason "Reducing concurrent trades limits simultaneous drawdown exposure" and expected effect "Lower max drawdown".
6. FOR the issue "poor_pair_concentration", THE `RuleSuggestionService` SHALL produce a suggestion with reason "Too few pairs reduce diversification" and expected effect "More diversified exposure; add pairs via Backtest page" and no parameter value change (advisory only).
7. FOR the issue "negative_profit", THE `RuleSuggestionService` SHALL suggest tightening `stoploss` by reducing its absolute value by 0.03, with reason "Negative total profit — cutting losses earlier may recover profitability" and expected effect "Reduced losses per trade".
8. THE `ImprovePage` SHALL display each `ParameterSuggestion` in the "Suggested Actions" panel, showing: parameter name, proposed value (or "Advisory" for advisory-only suggestions), reason, expected effect, and an "Apply" button.
9. IF no suggestions are generated, THE `ImprovePage` SHALL display the message "No suggestions available" in the Suggested Actions panel.

---

### Requirement 6: Candidate Configuration

**User Story:** As a user, I want to apply one or more suggestions to create a candidate configuration, so that I can test proposed changes without permanently modifying my strategy.

#### Acceptance Criteria

1. WHEN the user clicks "Apply" on a `ParameterSuggestion`, THE `ImprovePage` SHALL merge the suggested parameter change into the in-memory `CandidateConfig`, overwriting any previous value for that parameter.
2. THE `ImprovePage` SHALL display the current `CandidateConfig` in the "Candidate Preview" panel as a key-value diff, showing only parameters that differ from the `BaselineParams` snapshot loaded for the `BaselineRun`.
3. WHEN the `CandidateConfig` contains at least one changed parameter, THE `ImprovePage` SHALL enable the "Run Backtest on Candidate" button.
4. THE `ImprovePage` SHALL display a "Reset Candidate" button that, when clicked, clears all applied suggestions and resets the `CandidateConfig` to the `BaselineParams` snapshot values.
5. IF a `ParameterSuggestion` is advisory-only (no parameter value change), THEN THE `ImprovePage` SHALL mark it as applied in the UI but SHALL NOT add any entry to the `CandidateConfig` diff.

---

### Requirement 7: Candidate Backtest Execution

**User Story:** As a user, I want to run a backtest using the candidate configuration, so that I can measure the effect of the suggested changes.

#### Acceptance Criteria

1. WHEN the user clicks "Run Backtest on Candidate", THE `ImproveService` SHALL create a per-candidate-run subdirectory under `{user_data_path}/strategies/_improve_sandbox/{strategy_name}_{timestamp}/`, copy the strategy's `.py` file into it, and write the `CandidateConfig` values as `{strategy_name}.json` in that same subdirectory. Each candidate run SHALL use its own isolated subdirectory to prevent collisions between successive runs.
2. WHEN the sandbox is prepared, THE `ImproveService` SHALL invoke `BacktestService.build_command()` with the same strategy name, timeframe, and pairs as the `BaselineRun`, passing `--strategy-path {sandbox_dir}` as an extra flag so Freqtrade loads the strategy and its params from the sandbox.
3. THE `ImprovePage` SHALL stream the candidate backtest subprocess output to a terminal widget within the Candidate Preview panel.
4. WHILE the candidate backtest is running, THE `ImprovePage` SHALL disable the "Run Backtest on Candidate" button and SHALL display a "Stop" button that, when clicked, terminates the subprocess via `ProcessService`.
5. WHEN the candidate backtest process exits with code 0, THE `ImproveService` SHALL parse the deterministic export file produced for that candidate run via `parse_backtest_zip()` and store the result as the `CandidateRun`. The export filename SHALL be derived from the command builder output path. If the command builder does not expose a deterministic export path, the fallback is to select the most recently modified `.zip` in `{user_data_path}/backtest_results/` with a modification time after the process start timestamp.
6. IF the candidate backtest process exits with a non-zero exit code, THEN THE `ImprovePage` SHALL display the message "Candidate backtest failed — see terminal output" and SHALL NOT update the `CandidateRun`.

---

### Requirement 8: Comparison View

**User Story:** As a user, I want to see a side-by-side comparison of the baseline and candidate backtest results, so that I can make an informed decision about whether to accept the changes.

#### Acceptance Criteria

1. WHEN both `BaselineRun` and `CandidateRun` are available, THE `ImprovePage` SHALL display a comparison table with one row per metric and two columns: "Baseline" and "Candidate".
2. THE comparison table SHALL include the following metrics: total trades, win rate (%), total profit (%), max drawdown (%), Sharpe ratio, profit factor, and expectancy.
3. WHEN a `CandidateRun` metric value is strictly better than the corresponding `BaselineRun` metric value, THE `ImprovePage` SHALL render that candidate cell with a green highlight.
4. WHEN a `CandidateRun` metric value is strictly worse than the corresponding `BaselineRun` metric value, THE `ImprovePage` SHALL render that candidate cell with a red highlight.
5. THE `ImprovePage` SHALL display an "Accept" button and a "Reject" button below the comparison table WHEN both runs are available.

---

### Requirement 9: Accept / Reject / Rollback

**User Story:** As a user, I want to accept or reject the candidate changes, so that I can commit improvements or safely discard them.

#### Acceptance Criteria

1. WHEN the user clicks "Accept", THE `ImproveService` SHALL overwrite the strategy's `{strategy_name}.json` parameter file with the `CandidateConfig` values, using an atomic write (write to `.tmp` then `os.replace()`).
2. WHEN the user clicks "Accept", THE `ImprovePage` SHALL display the message "Candidate accepted — strategy parameters updated" and SHALL promote the `CandidateRun` to become the new `BaselineRun`.
3. WHEN the user clicks "Reject", THE `ImproveService` SHALL delete the `{strategy_name}.json` candidate file and the copied strategy `.py` file from the `_improve_sandbox/` directory if they exist, and SHALL NOT modify the strategy's main parameter file.
4. WHEN the user clicks "Reject", THE `ImprovePage` SHALL reset the `CandidateConfig` to the `BaselineParams` snapshot values and SHALL clear the comparison view.
5. THE `ImprovePage` SHALL display a "Rollback" button WHEN `_baseline_history` is non-empty (i.e. at least one "Accept" has been performed in the current session).
6. WHEN the user clicks "Rollback", THE `ImproveService` SHALL restore the strategy's `{strategy_name}.json` to the parameter values from the most recent `BaselineParams` snapshot in `_baseline_history`, using an atomic write (write to `.tmp` then `os.replace()`).
7. WHEN the user clicks "Rollback", THE `ImprovePage` SHALL display the message "Rolled back to previous baseline parameters" and SHALL restore the popped `BaselineParams` snapshot as the active `BaselineParams`. The `BaselineRun` metrics display is not automatically updated — the user may re-analyze if needed.
8. THE `ImprovePage` SHALL maintain an in-memory `_baseline_history` list that stores each previous `BaselineParams` snapshot whenever the user clicks "Accept". WHEN the user clicks "Rollback", THE `ImprovePage` SHALL pop the most recent entry from `_baseline_history` and restore it as the active `BaselineParams`.

---

### Requirement 10: Service Layer Architecture

**User Story:** As a developer, I want the improvement logic separated into dedicated service classes, so that the UI layer remains thin and the business logic is independently testable.

#### Acceptance Criteria

1. THE `ResultsDiagnosisService` SHALL be implemented as a stateless class with a `@staticmethod` method `diagnose(summary: BacktestSummary) -> List[DiagnosedIssue]` that accepts no UI dependencies.
2. THE `RuleSuggestionService` SHALL be implemented as a stateless class with a `@staticmethod` method `suggest(issues: List[DiagnosedIssue], params: dict) -> List[ParameterSuggestion]` that accepts no UI dependencies.
3. THE `ImproveService` SHALL accept `SettingsService` and `BacktestService` via its constructor and SHALL NOT import any PySide6 UI classes. THE `ImprovePage` SHALL hold the `SettingsState` reference and SHALL pass `settings_state.settings_service` when constructing `ImproveService`.
4. THE `ImprovePage` SHALL instantiate `ImproveService`, `ResultsDiagnosisService`, and `RuleSuggestionService` internally and SHALL NOT expose them as public attributes.
5. THE `ImproveService` SHALL use `get_logger("services.improve")` for all log output, and THE `ImprovePage` SHALL use `get_logger("ui.improve_page")` for all log output.
