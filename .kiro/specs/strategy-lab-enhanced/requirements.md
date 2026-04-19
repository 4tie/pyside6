# Requirements Document

## Introduction

The Enhanced Strategy Lab is a major upgrade to the existing "Strategy Lab" tab (currently `LoopPage`) in the Freqtrade GUI desktop application. The current tab runs an automated backtest → diagnose → suggest → apply loop, but it is limited to adjusting only three parameters (stoploss, max_open_trades, minimal_roi), uses a shallow rule-based diagnosis engine, and provides no visibility into why the loop is making decisions or how close it is to finding a profitable configuration.

This feature expands the Strategy Lab into a comprehensive, intelligent optimization workbench that:
- Exposes the full parameter surface of a strategy (buy/sell indicator params, ROI, stoploss, trailing, max_open_trades)
- Replaces the shallow rule engine with a multi-dimensional scoring and structural diagnosis system that is already partially built
- Adds an AI-assisted suggestion layer that can reason about parameter interactions
- Provides a rich, transparent UI showing every decision the loop makes and why
- Integrates a hyperopt-guided mode that uses Freqtrade's own hyperopt engine as a sub-step
- Adds walk-forward validation and out-of-sample gating to prevent overfitting
- Surfaces actionable, human-readable explanations for every parameter change

The goal is to give users the best possible chance of finding a genuinely profitable strategy configuration — not just one that looks good in-sample.

---

## Glossary

- **Strategy_Lab**: The enhanced Strategy Lab tab (replaces the current `LoopPage`).
- **Loop_Service**: The `LoopService` class in `app/core/services/loop_service.py` that orchestrates the iterative optimization cycle.
- **Improve_Service**: The `ImproveService` class in `app/core/services/improve_service.py` that manages sandboxes, command building, and result parsing.
- **Diagnosis_Service**: The `ResultsDiagnosisService` class that evaluates rule-based heuristics on backtest results.
- **Suggestion_Rotator**: The `SuggestionRotator` class inside `loop_service.py` that tracks tried configurations and generates varied suggestions.
- **Robust_Score**: The composite multi-dimensional score computed by `compute_score()` in `loop_service.py` (profitability + consistency + stability − fragility).
- **Parameter_Surface**: The complete set of optimizable parameters for a strategy: buy_params, sell_params, minimal_roi, stoploss, trailing_stop, trailing_stop_positive, trailing_stop_positive_offset, max_open_trades.
- **Sandbox**: An isolated directory under `user_data/strategies/_improve_sandbox/` used to run a candidate backtest without touching the live strategy file.
- **Candidate**: A proposed parameter configuration that has not yet been accepted as the live strategy.
- **Baseline**: The most recently accepted parameter configuration used as the comparison reference.
- **OOS_Gate**: The out-of-sample validation gate that runs a backtest on a held-out date range to detect overfitting.
- **Walk_Forward_Gate**: The walk-forward validation gate that splits the date range into K folds and checks consistency across folds.
- **Stress_Gate**: The stress-test gate that re-runs the backtest with elevated fees and slippage to check robustness.
- **Hyperopt_Mode**: An optional loop mode where each iteration uses Freqtrade's `hyperopt` subcommand instead of a fixed parameter mutation to explore the parameter space.
- **AI_Advisor**: An optional AI-powered suggestion layer that uses the configured LLM (via `AIService`) to reason about parameter interactions and propose changes beyond the rule engine's reach.
- **Session**: A single continuous run of the Strategy Lab loop from Start to Stop/Complete.

---

## Requirements

### Requirement 1: Full Parameter Surface Exposure

**User Story:** As a strategy developer, I want the Strategy Lab to mutate all optimizable parameters of my strategy — not just stoploss, ROI, and max_open_trades — so that the loop can explore the full configuration space and find better results.

#### Acceptance Criteria

1. WHEN the Strategy_Lab loads a strategy, THE Loop_Service SHALL read and expose all parameter groups from the strategy JSON: buy_params, sell_params, minimal_roi, stoploss, trailing_stop, trailing_stop_positive, trailing_stop_positive_offset, trailing_only_offset_is_reached, and max_open_trades.
2. WHEN the Suggestion_Rotator generates suggestions, THE Suggestion_Rotator SHALL be capable of proposing changes to buy_params and sell_params key-by-key, in addition to the existing stoploss, minimal_roi, and max_open_trades parameters.
3. WHEN a buy_params or sell_params key holds a numeric value, THE Suggestion_Rotator SHALL apply a step-scaled delta to that value, respecting the parameter's observed range from the loaded strategy JSON.
4. WHEN a buy_params or sell_params key holds a boolean value, THE Suggestion_Rotator SHALL propose toggling the value as a discrete mutation step.
5. WHEN trailing_stop is false and the Diagnosis_Service identifies a high-drawdown pattern, THE Suggestion_Rotator SHALL propose enabling trailing_stop with a conservative trailing_stop_positive value.
6. THE Loop_Service SHALL write all mutated parameter groups back to the sandbox strategy JSON via Improve_Service before each candidate backtest.
7. IF a parameter mutation would produce a value outside the parameter's valid range (e.g., stoploss > −0.001 or stoploss < −0.99), THEN THE Suggestion_Rotator SHALL clamp the proposed value to the nearest valid boundary.

---

### Requirement 2: Structural Diagnosis Integration

**User Story:** As a strategy developer, I want the loop to use the full structural diagnosis engine — not just the eight shallow rules — so that it can detect deeper failure patterns like choppy-market entries, late trend entries, and outlier trade dependency.

#### Acceptance Criteria

1. WHEN a candidate backtest completes, THE Loop_Service SHALL call `ResultsDiagnosisService.diagnose()` with a `DiagnosisInput` that includes the in-sample summary, and SHALL pass the resulting `DiagnosisBundle.structural` list to the Suggestion_Rotator.
2. THE Suggestion_Rotator SHALL handle all ten structural failure patterns defined in `ResultsDiagnosisService._run_structural_rules()`: entries_too_loose_in_chop, entries_too_late_in_trend, exits_cutting_winners_early, losers_lasting_too_long, single_regime_dependency, micro_loss_noise, filter_stack_too_strict, high_winrate_bad_payoff, outlier_trade_dependency, and drawdown_after_volatility.
3. WHEN a structural pattern maps to a buy_params or sell_params mutation, THE Suggestion_Rotator SHALL apply the mutation to the specific indicator parameter identified in the pattern's `mutation_direction` field.
4. WHEN the Diagnosis_Service detects `exits_cutting_winners_early`, THE Suggestion_Rotator SHALL propose widening the minimal_roi targets by a step-scaled amount.
5. WHEN the Diagnosis_Service detects `filter_stack_too_strict`, THE Suggestion_Rotator SHALL propose relaxing the most restrictive buy_params threshold by a step-scaled amount.
6. WHEN the Diagnosis_Service detects `losers_lasting_too_long`, THE Suggestion_Rotator SHALL propose tightening the stoploss and optionally enabling trailing_stop.
7. THE Strategy_Lab UI SHALL display each structural diagnosis pattern with its failure_pattern name, evidence string, root_cause, and mutation_direction in the iteration detail panel.

---

### Requirement 3: Hyperopt-Guided Iteration Mode

**User Story:** As a strategy developer, I want the option to use Freqtrade's hyperopt engine as the search mechanism for each loop iteration, so that the loop can explore a much larger parameter space than manual step-based mutations allow.

#### Acceptance Criteria

1. THE Strategy_Lab SHALL expose a "Iteration Mode" selector with two options: "Rule-Based Mutations" (default) and "Hyperopt-Guided".
2. WHEN Hyperopt-Guided mode is selected, THE Loop_Service SHALL run `freqtrade hyperopt` instead of a fixed-parameter backtest for each iteration, using the spaces and epochs configured in the loop settings.
3. WHEN Hyperopt-Guided mode is active, THE Loop_Service SHALL pass the hyperopt result's best parameter set to the validation gates (OOS_Gate, Walk_Forward_Gate, Stress_Gate) before accepting it as a candidate.
4. WHEN Hyperopt-Guided mode is active, THE Strategy_Lab UI SHALL expose a "Hyperopt Epochs per Iteration" spin box (range 50–2000, default 200) and a "Hyperopt Spaces" multi-select (buy, sell, roi, stoploss, trailing).
5. WHEN a hyperopt iteration completes with exit code 0, THE Loop_Service SHALL parse the best result from the `.fthypt` file and apply it as the candidate parameter set for validation.
6. IF a hyperopt iteration exits with a non-zero code, THEN THE Loop_Service SHALL record the iteration as status="error" and continue to the next iteration without stopping the loop.
7. WHEN Hyperopt-Guided mode is active, THE Strategy_Lab UI SHALL display the hyperopt terminal output in the live output panel during each iteration.

---

### Requirement 4: AI-Assisted Suggestion Layer

**User Story:** As a strategy developer, I want the loop to optionally use the configured AI model to reason about parameter interactions and suggest changes that the rule engine cannot derive, so that I can benefit from AI-level analysis without leaving the app.

#### Acceptance Criteria

1. THE Strategy_Lab SHALL expose an "AI Advisor" toggle that is disabled when no AI model is configured in Settings and enabled when a model is available.
2. WHEN the AI Advisor toggle is enabled and a candidate backtest completes, THE Strategy_Lab SHALL send the current backtest summary, the diagnosed issues, and the current parameter set to the AI model via `AIService` and request a parameter suggestion.
3. THE AI_Advisor prompt SHALL include: strategy name, current parameter values, backtest metrics (profit, win_rate, max_drawdown, sharpe_ratio, total_trades, expectancy, profit_factor), and the list of diagnosed issues with their descriptions.
4. WHEN the AI model returns a valid parameter suggestion, THE Loop_Service SHALL apply it as an additional candidate mutation alongside the rule-based suggestions for the next iteration.
5. WHEN the AI model returns a suggestion that would produce an invalid parameter value, THE Loop_Service SHALL clamp the value to the valid range and log a warning.
6. IF the AI model request fails or times out, THEN THE Loop_Service SHALL fall back to rule-based suggestions only and log the failure without stopping the loop.
7. THE Strategy_Lab UI SHALL display a "AI suggested:" label next to any parameter change that originated from the AI Advisor, distinguishing it from rule-based changes.
8. WHILE the AI Advisor is making a request, THE Strategy_Lab UI SHALL display a loading indicator in the iteration detail panel.

---

### Requirement 5: Multi-Gate Validation Pipeline

**User Story:** As a strategy developer, I want every candidate configuration to pass a series of validation gates before being accepted, so that I can be confident the improvements are real and not just in-sample overfitting.

#### Acceptance Criteria

1. THE Loop_Service SHALL run candidates through the following gate sequence in order: Gate 1 (In-Sample Backtest), Gate 2 (Out-of-Sample Backtest), Gate 3 (Walk-Forward Validation), Gate 4 (Stress Test), Gate 5 (Consistency Check).
2. WHEN a candidate fails any gate, THE Loop_Service SHALL record the gate failure in the iteration's `gate_results` list and SHALL NOT advance to subsequent gates.
3. WHEN Gate 2 (OOS_Gate) runs, THE Loop_Service SHALL run a backtest on the held-out date range (configured by `oos_split_pct`) and SHALL reject the candidate if OOS profit is less than 50% of in-sample profit.
4. WHEN Gate 3 (Walk_Forward_Gate) runs, THE Loop_Service SHALL split the full date range into `walk_forward_folds` equal folds, run a backtest on each fold, and SHALL reject the candidate if fewer than 60% of folds are profitable.
5. WHEN Gate 4 (Stress_Gate) runs, THE Loop_Service SHALL re-run the in-sample backtest with fees multiplied by `stress_fee_multiplier` and per-trade slippage of `stress_slippage_pct`, and SHALL reject the candidate if stress profit is below `stress_profit_target_pct` percent of the main profit target.
6. WHEN Gate 5 (Consistency Check) runs, THE Loop_Service SHALL compute the coefficient of variation of per-fold profits from Gate 3 and SHALL reject the candidate if it exceeds `consistency_threshold_pct`.
7. WHEN "Quick" validation mode is selected, THE Loop_Service SHALL run only Gates 1 and 2, skipping Gates 3–5.
8. THE Strategy_Lab UI SHALL display a gate progress indicator for the current iteration showing which gates have passed (✓), failed (✗), or are pending (○).
9. THE Strategy_Lab UI SHALL display the specific failure reason for each failed gate in the iteration history row.

---

### Requirement 6: Robust Scoring and Best-Result Tracking

**User Story:** As a strategy developer, I want the loop to track the best result found using a multi-dimensional score — not just profit — so that the "best" configuration is genuinely robust and not just the most profitable in-sample.

#### Acceptance Criteria

1. THE Loop_Service SHALL compute a Robust_Score for every iteration that passes all validation gates, using the existing `compute_score()` function with `RobustScoreInput` populated from Gate 1 (in_sample), Gate 3 fold summaries (fold_summaries), and Gate 4 (stress_summary).
2. THE Loop_Service SHALL update `LoopResult.best_iteration` only when the new iteration's Robust_Score.total exceeds the current best score AND the iteration has passed all configured validation gates.
3. THE Strategy_Lab UI SHALL display the Robust_Score breakdown (profitability, consistency, stability, fragility components) for the best iteration found.
4. THE Strategy_Lab UI SHALL display a live "Best Score" stat card that updates after each iteration completes.
5. WHEN the loop completes, THE Strategy_Lab UI SHALL highlight the best iteration in the history list with a distinct visual indicator.
6. THE Strategy_Lab UI SHALL display the delta between the best iteration's metrics and the baseline metrics (profit Δ, win_rate Δ, drawdown Δ, sharpe Δ) in the best result panel.

---

### Requirement 7: Transparent Iteration History

**User Story:** As a strategy developer, I want to see a detailed, human-readable record of every iteration the loop ran — including what changed, why, and what the result was — so that I can understand the optimization process and learn from it.

#### Acceptance Criteria

1. THE Strategy_Lab UI SHALL display an iteration history list where each row shows: iteration number, parameter changes applied, gate results summary, Robust_Score, profit %, win rate %, max drawdown %, and improvement indicator.
2. WHEN a user clicks an iteration history row, THE Strategy_Lab UI SHALL expand it to show: the full list of parameter changes with before/after values, the diagnosed issues that triggered each change, the AI Advisor suggestion (if any), and the per-gate pass/fail results with failure reasons.
3. THE Strategy_Lab UI SHALL color-code iteration rows: green for improvements, amber for no-improvement passes, red for gate failures or errors.
4. THE Strategy_Lab UI SHALL display a "Changes" column in each row listing the parameter names that were mutated, formatted as "param: old → new".
5. WHEN the loop is running, THE Strategy_Lab UI SHALL auto-scroll the history list to the most recently added row.
6. THE Strategy_Lab UI SHALL display a "Why this change?" tooltip on each parameter change that shows the diagnosed issue and structural pattern that triggered it.

---

### Requirement 8: Configurable Loop Parameters

**User Story:** As a strategy developer, I want to configure all aspects of the optimization loop — targets, iteration limits, validation thresholds, and search strategy — from a single panel, so that I can tune the loop to my specific strategy and risk tolerance.

#### Acceptance Criteria

1. THE Strategy_Lab UI SHALL expose the following configuration fields: Strategy selector, Max Iterations (1–100), Target Profit % (−100 to 10000), Target Win Rate % (0–100), Max Drawdown % (0–100), Min Trades (1–10000), Stop on First Profitable (checkbox), OOS Split % (5–50), Walk-Forward Folds K (2–10), Stress Fee Multiplier (1.0–5.0), Stress Slippage % (0–2.0), Stress Profit Target % (0–100), Consistency Threshold % (0–100), Validation Mode (Full / Quick), Iteration Mode (Rule-Based / Hyperopt-Guided).
2. WHEN Hyperopt-Guided mode is selected, THE Strategy_Lab UI SHALL additionally show: Hyperopt Epochs per Iteration (50–2000), Hyperopt Spaces (multi-select: buy, sell, roi, stoploss, trailing), Hyperopt Loss Function (dropdown matching the existing OptimizePage loss options).
3. THE Strategy_Lab SHALL persist all loop configuration fields to `AppSettings` under a new `StrategyLabPreferences` Pydantic model and restore them on next launch.
4. WHEN the loop is running, THE Strategy_Lab UI SHALL disable all configuration fields to prevent mid-run changes.
5. WHEN the user changes Validation Mode to "Quick", THE Strategy_Lab UI SHALL display a warning label: "Quick mode skips walk-forward and stress gates — results may overfit."
6. THE Strategy_Lab UI SHALL display a "Timerange" field (with preset buttons matching the existing Backtest and Optimize pages) that sets the date range used for all backtests within the loop.
7. THE Strategy_Lab UI SHALL display a "Pairs" selector (reusing the existing PairsSelectorDialog) that sets the pair list used for all backtests within the loop.

---

### Requirement 9: Accept, Reject, and Rollback

**User Story:** As a strategy developer, I want to accept the best result found by the loop, reject it, or roll back to a previous accepted state, so that I always remain in control of what gets written to my live strategy file.

#### Acceptance Criteria

1. WHEN the loop completes or is stopped, THE Strategy_Lab UI SHALL enable an "Apply Best Result" button that writes the best iteration's parameters to the live strategy JSON via `Improve_Service.accept_candidate()`.
2. WHEN the loop completes or is stopped, THE Strategy_Lab UI SHALL enable a "Discard" button that removes the sandbox directory and leaves the live strategy file unchanged.
3. WHEN the user clicks "Apply Best Result", THE Strategy_Lab UI SHALL display a confirmation dialog showing the parameter changes that will be written before proceeding.
4. WHEN the user accepts the confirmation, THE Improve_Service SHALL atomically write the candidate parameters to the live strategy JSON using a `.tmp` file and `os.replace()`.
5. THE Strategy_Lab UI SHALL maintain a session history stack of all accepted parameter sets, enabling rollback to any previously accepted state within the current session.
6. WHEN the user clicks "Rollback", THE Strategy_Lab UI SHALL display a list of previous accepted states with their metrics and allow the user to select one to restore.
7. WHEN a rollback is performed, THE Improve_Service SHALL atomically write the selected historical parameters to the live strategy JSON.
8. IF the Strategy_Lab is closed while a subprocess is running, THEN THE Strategy_Lab SHALL stop the subprocess and clean up the sandbox directory before closing.

---

### Requirement 10: Live Progress and Status Feedback

**User Story:** As a strategy developer, I want real-time feedback on what the loop is doing at every moment — including subprocess output, gate progress, and scoring — so that I am never left wondering whether the loop is working or stuck.

#### Acceptance Criteria

1. WHILE the loop is running, THE Strategy_Lab UI SHALL display a progress bar showing current iteration / max iterations.
2. WHILE a subprocess (backtest or hyperopt) is running, THE Strategy_Lab UI SHALL stream its stdout and stderr to the live output terminal widget in real time.
3. WHEN a gate starts, THE Strategy_Lab UI SHALL update the gate progress indicator for the current iteration to show the gate as "running" (spinner or animated indicator).
4. WHEN a gate completes, THE Strategy_Lab UI SHALL update the gate progress indicator to show pass (✓) or fail (✗) immediately.
5. THE Strategy_Lab UI SHALL display a status label that shows the current loop phase: "Idle", "Running backtest (iteration N/M)", "Running OOS gate", "Running walk-forward fold K/N", "Running stress test", "Scoring", "Waiting for AI Advisor", or "Complete".
6. THE Strategy_Lab UI SHALL display live stat cards for: current iteration number, best profit % found, best win rate % found, best drawdown % found, and best Sharpe ratio found — updating after each iteration.
7. WHEN the loop stops for any reason, THE Strategy_Lab UI SHALL display the stop reason in the status label: "Targets met", "Max iterations reached", "No more suggestions", "Stopped by user", or the specific error message.

---

### Requirement 11: Stale Sandbox Cleanup

**User Story:** As a strategy developer, I want the Strategy Lab to automatically clean up leftover sandbox directories from previous sessions, so that my strategies directory does not accumulate stale files over time.

#### Acceptance Criteria

1. WHEN the Strategy_Lab initializes, THE Strategy_Lab SHALL scan `user_data/strategies/_improve_sandbox/` for sandbox directories older than 24 hours and delete them.
2. WHEN a candidate is rejected via the "Discard" button, THE Improve_Service SHALL immediately delete the associated sandbox directory.
3. WHEN the loop is stopped by the user mid-run, THE Strategy_Lab SHALL delete the current iteration's sandbox directory after the subprocess terminates.
4. IF sandbox cleanup fails due to a file system error, THEN THE Strategy_Lab SHALL log the error at WARNING level and continue without surfacing the error to the user.
5. THE Strategy_Lab SHALL NOT delete sandbox directories that are less than 5 minutes old, to avoid deleting sandboxes from a concurrently running loop instance.

---

### Requirement 12: Integration with Existing Pages

**User Story:** As a strategy developer, I want the Strategy Lab to integrate seamlessly with the existing Backtest, Optimize, and Strategy Config pages, so that I can move between them without losing context.

#### Acceptance Criteria

1. WHEN the user accepts a result in the Strategy_Lab, THE Strategy_Config_Page SHALL reflect the updated parameters the next time it is opened or refreshed.
2. WHEN the Strategy_Lab completes a loop, THE Strategy_Lab SHALL emit a Qt signal `loop_completed` that the MainWindow can use to refresh other pages.
3. THE Strategy_Lab SHALL reuse the existing `PairsSelectorDialog` for pair selection, passing the current `SettingsState` and `favorite_pairs`.
4. THE Strategy_Lab SHALL reuse the existing `TerminalWidget` for subprocess output display, applying the user's terminal preferences from `AppSettings.terminal_preferences`.
5. WHEN the user navigates away from the Strategy_Lab tab while a loop is running, THE Strategy_Lab SHALL continue running in the background and SHALL NOT stop the subprocess.
6. THE Strategy_Lab SHALL reuse the existing `ProcessService` for all subprocess execution, ensuring consistent process lifecycle management across the app.
