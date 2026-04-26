# Requirements Document

## Introduction

The ParNeeds feature is a validation and robustness-testing workstation within the Freqtrade GUI desktop application. It currently provides a Timerange workflow that splits a date range into 2-week and 1-month windows, validates candle coverage, auto-downloads missing data, and runs sequential backtests.

This document specifies three new workflows to be added to the ParNeeds page:

1. **Walk-Forward Workflow** — validates that a strategy generalises across time by splitting the timerange into in-sample (training) and out-of-sample (test) folds, running backtests on each fold, and computing a stability score.
2. **Monte Carlo Workflow** — estimates the distribution of strategy outcomes by running many iterations with randomised trade order and/or price/profit noise, then reporting confidence percentiles and risk metrics.
3. **Parameter Sensitivity Workflow** — sweeps one or more strategy parameters across a defined range using direct backtest runs, producing a sweep table and heatmap to show how sensitive results are to each parameter.

All three workflows integrate with the existing ParNeeds UI shell (workflow selector, config panel, terminal, results table) and the existing `ProcessRunManager`, `BacktestService`, and `ParNeedsService` infrastructure.

---

## Glossary

- **ParNeeds_Page**: The PySide6 `QWidget` page at `app/ui/pages/parneeds_page.py` that hosts all ParNeeds workflows.
- **ParNeeds_Service**: The service at `app/core/services/parneeds_service.py` that provides planning and validation helpers.
- **Backtest_Service**: The service at `app/core/services/backtest_service.py` that builds and parses Freqtrade backtest commands.
- **Process_Run_Manager**: The service at `app/core/services/process_run_manager.py` that manages subprocess lifecycle.
- **Walk_Forward_Workflow**: A ParNeeds workflow that divides the timerange into sequential in-sample/out-of-sample fold pairs and runs backtests on each.
- **Monte_Carlo_Workflow**: A ParNeeds workflow that runs many backtest iterations with randomised trade order and/or profit noise to estimate outcome distributions.
- **Parameter_Sensitivity_Workflow**: A ParNeeds workflow that sweeps one or more strategy parameters across a defined range using direct backtest runs.
- **Fold**: One in-sample + out-of-sample pair in a Walk-Forward run.
- **In_Sample_Window**: The training portion of a Fold, used to represent the period the strategy was optimised on.
- **Out_Of_Sample_Window**: The test portion of a Fold, used to validate that the strategy generalises beyond the training period.
- **Anchored_Mode**: Walk-forward mode where the start date is fixed and the in-sample window expands with each fold.
- **Rolling_Mode**: Walk-forward mode where both the in-sample and out-of-sample windows slide forward by a fixed step.
- **Stability_Score**: A scalar metric (0–100) computed from the consistency of out-of-sample profit across folds; higher is more stable.
- **Iteration**: One Monte Carlo backtest run with a specific randomisation seed.
- **Percentile_Table**: A table showing the 5th, 50th, and 95th percentile values for key metrics across all Monte Carlo iterations.
- **Distribution_Chart**: A histogram or density plot of profit outcomes across all Monte Carlo iterations.
- **Sweep_Parameter**: A strategy parameter selected for variation in the Parameter Sensitivity workflow.
- **Sweep_Point**: One combination of parameter values tested in a Parameter Sensitivity run.
- **One_At_A_Time_Mode**: Parameter sensitivity mode where one parameter varies while all others are held at their baseline values.
- **Grid_Mode**: Parameter sensitivity mode where selected parameters are varied in combination.
- **Run_Result**: A single completed backtest result row stored in the shared results table.
- **Export**: A file written to disk containing run results in JSON or CSV format.
- **Terminal_Widget**: The `TerminalWidget` component that displays live subprocess output on the ParNeeds page.
- **AppSettings**: The Pydantic settings model at `app/core/models/settings_models.py` that provides paths and configuration.

---

## Requirements

### Requirement 1: Walk-Forward Workflow — Fold Generation

**User Story:** As a strategy developer, I want the Walk-Forward workflow to automatically divide my timerange into in-sample and out-of-sample folds, so that I can validate whether my strategy generalises across time periods.

#### Acceptance Criteria

1. WHEN the user selects "Walk-Forward workflow" and starts a run, THE ParNeeds_Service SHALL divide the configured timerange into the configured number of folds (default: 5).
2. WHEN the fold mode is set to "anchored", THE ParNeeds_Service SHALL fix the start date and expand the In_Sample_Window by one fold step with each successive Fold.
3. WHEN the fold mode is set to "rolling", THE ParNeeds_Service SHALL slide both the In_Sample_Window and Out_Of_Sample_Window forward by one fold step with each successive Fold.
4. THE ParNeeds_Service SHALL compute the In_Sample_Window and Out_Of_Sample_Window for each Fold using the configured split ratio (default: 80/20).
5. IF the configured timerange is too short to produce at least 2 folds with the configured split ratio, THEN THE ParNeeds_Service SHALL return a descriptive error before any backtest is started.
6. THE ParNeeds_Page SHALL display the planned fold schedule (fold number, in-sample timerange, out-of-sample timerange) in the Terminal_Widget before any backtest is started.

---

### Requirement 2: Walk-Forward Workflow — Backtest Execution

**User Story:** As a strategy developer, I want the Walk-Forward workflow to run backtests on each fold's in-sample and out-of-sample windows sequentially, so that I get a complete picture of in-sample vs. out-of-sample performance.

#### Acceptance Criteria

1. WHEN fold generation succeeds, THE ParNeeds_Page SHALL run one backtest per window (in-sample then out-of-sample) for each Fold, sequentially, using the Backtest_Service and Process_Run_Manager.
2. WHEN a fold backtest completes with exit code 0, THE ParNeeds_Page SHALL parse and save the result using the Backtest_Service and store it as a Run_Result linked to that Fold.
3. WHEN a fold backtest fails with a non-zero exit code, THE ParNeeds_Page SHALL record the Fold as failed, log the exit code to the Terminal_Widget, and continue with the next Fold.
4. WHILE a Walk-Forward run is in progress, THE ParNeeds_Page SHALL display the current fold number and window label in the plan label and Terminal_Widget.
5. WHEN the user clicks Stop during a Walk-Forward run, THE ParNeeds_Page SHALL cancel the active subprocess via Process_Run_Manager and halt further fold execution.

---

### Requirement 3: Walk-Forward Workflow — Results and Stability Score

**User Story:** As a strategy developer, I want to see a fold-by-fold results table and a stability score after a Walk-Forward run, so that I can assess whether my strategy is robust across time.

#### Acceptance Criteria

1. WHEN all folds complete, THE ParNeeds_Page SHALL display a fold results table with columns: Fold, IS Timerange, OOS Timerange, IS Profit %, OOS Profit %, Win %, DD %, Trades, Status.
2. THE ParNeeds_Service SHALL compute the Stability_Score as a value between 0 and 100 derived from the ratio of folds where OOS Profit % is positive and the variance of OOS Profit % across folds.
3. WHEN all folds complete, THE ParNeeds_Page SHALL display the Stability_Score, average OOS Profit %, average OOS DD %, and a pass/fail count in a summary section below the fold table.
4. THE ParNeeds_Page SHALL colour-code each fold row: green when OOS Profit % is positive, red when OOS Profit % is negative or the fold failed.
5. WHEN the Walk-Forward run completes, THE ParNeeds_Page SHALL emit the `run_completed` signal for each fold Run_Result that has a valid run ID, consistent with the existing Timerange workflow behaviour.

---

### Requirement 4: Walk-Forward Workflow — Configuration

**User Story:** As a strategy developer, I want to configure the Walk-Forward workflow parameters in the config panel, so that I can control how folds are generated.

#### Acceptance Criteria

1. THE ParNeeds_Page SHALL expose the following Walk-Forward configuration fields when "Walk-Forward workflow" is selected: number of folds (integer, default 5, range 2–20), split ratio (percentage, default 80, range 50–95), and fold mode (anchored or rolling, default anchored).
2. WHEN the user changes the number of folds or split ratio, THE ParNeeds_Page SHALL update the plan label to show the recalculated fold schedule.
3. THE ParNeeds_Page SHALL hide Walk-Forward configuration fields when a different workflow is selected.

---

### Requirement 5: Monte Carlo Workflow — Iteration Execution

**User Story:** As a strategy developer, I want the Monte Carlo workflow to run many backtest iterations with randomised inputs, so that I can estimate the distribution of possible outcomes for my strategy.

#### Acceptance Criteria

1. WHEN the user selects "Monte Carlo workflow" and starts a run, THE ParNeeds_Page SHALL execute the configured number of iterations (default: 500) sequentially using the Backtest_Service and Process_Run_Manager.
2. THE ParNeeds_Service SHALL generate a unique random seed for each Iteration derived from the base seed and the iteration index, ensuring reproducibility when the same base seed is used.
3. WHEN randomise trade order is enabled (default: enabled), THE ParNeeds_Service SHALL pass a different seed to each backtest run so that Freqtrade's internal trade ordering varies across iterations.
4. WHEN profit noise is enabled (default: enabled), THE ParNeeds_Service SHALL apply a conservative random perturbation (±2% of profit per trade) to the parsed profit values before storing the Iteration result, without modifying the underlying backtest output files.
5. WHEN an Iteration fails with a non-zero exit code, THE ParNeeds_Page SHALL record the Iteration as failed and continue with the next Iteration without halting the workflow.
6. WHILE a Monte Carlo run is in progress, THE ParNeeds_Page SHALL display a progress indicator showing completed iterations out of total (e.g. "Iteration 47 / 500") in the plan label.
7. WHEN the user clicks Stop during a Monte Carlo run, THE ParNeeds_Page SHALL cancel the active subprocess and halt further iteration execution.

---

### Requirement 6: Monte Carlo Workflow — Results and Distribution

**User Story:** As a strategy developer, I want to see a percentile table, distribution chart, and summary statistics after a Monte Carlo run, so that I can understand the risk and upside of my strategy.

#### Acceptance Criteria

1. WHEN all iterations complete, THE ParNeeds_Page SHALL display a Percentile_Table with the 5th, 50th, and 95th percentile values for: Profit %, Max Drawdown %, Win Rate %, and Trades.
2. WHEN all iterations complete, THE ParNeeds_Page SHALL display a Distribution_Chart (histogram) of Profit % outcomes across all completed iterations.
3. WHEN all iterations complete, THE ParNeeds_Page SHALL display the following summary statistics: 5th percentile profit, median profit, 95th percentile profit, worst-case drawdown, probability of ending profitable (fraction of iterations with Profit % > 0), and probability of exceeding the configured max drawdown threshold.
4. THE ParNeeds_Page SHALL add one row per completed Iteration to the shared results table with columns: Iteration, Profit %, Win %, DD %, Trades, Status, Run ID.
5. WHEN the Monte Carlo run completes, THE ParNeeds_Page SHALL emit the `run_completed` signal for each Iteration Run_Result that has a valid run ID.

---

### Requirement 7: Monte Carlo Workflow — Configuration

**User Story:** As a strategy developer, I want to configure the Monte Carlo workflow parameters in the config panel, so that I can control the number of iterations and the type of randomisation applied.

#### Acceptance Criteria

1. THE ParNeeds_Page SHALL expose the following Monte Carlo configuration fields when "Monte Carlo workflow" is selected: number of iterations (integer, default 500, range 10–5000), randomise trade order toggle (default: enabled), profit noise toggle (default: enabled), and max drawdown threshold for probability calculation (percentage, default 20).
2. WHEN the user changes the number of iterations, THE ParNeeds_Page SHALL update the plan label to reflect the new iteration count.
3. THE ParNeeds_Page SHALL hide Monte Carlo configuration fields when a different workflow is selected.

---

### Requirement 8: Parameter Sensitivity Workflow — Parameter Discovery

**User Story:** As a strategy developer, I want the Parameter Sensitivity workflow to automatically discover sweepable parameters from my strategy, so that I do not have to manually specify every parameter.

#### Acceptance Criteria

1. WHEN the user selects "Parameter Sensitivity workflow" and a strategy is chosen, THE ParNeeds_Service SHALL inspect the strategy file and detect all parameters of type IntParameter, DecimalParameter, CategoricalParameter, and BooleanParameter.
2. THE ParNeeds_Service SHALL also expose the following fixed backtest parameters as sweepable: ROI (roi_table), stoploss, trailing_stop, trailing_stop_positive, trailing_stop_positive_offset, and max_open_trades.
3. WHEN parameter discovery completes, THE ParNeeds_Page SHALL display the discovered parameters in a selectable list so the user can choose which parameters to sweep.
4. IF no sweepable parameters are found for the selected strategy, THEN THE ParNeeds_Page SHALL display an informational message and disable the Start button.

---

### Requirement 9: Parameter Sensitivity Workflow — Sweep Execution

**User Story:** As a strategy developer, I want the Parameter Sensitivity workflow to run backtests across a defined range of parameter values, so that I can see how sensitive my strategy's results are to each parameter.

#### Acceptance Criteria

1. WHEN the user starts a Parameter Sensitivity run in One_At_A_Time_Mode, THE ParNeeds_Service SHALL generate one Sweep_Point per value in each selected parameter's range while holding all other parameters at their baseline values.
2. WHEN the user starts a Parameter Sensitivity run in Grid_Mode, THE ParNeeds_Service SHALL generate the Cartesian product of all selected parameter ranges as Sweep_Points.
3. THE ParNeeds_Page SHALL run one backtest per Sweep_Point sequentially using the Backtest_Service and Process_Run_Manager.
4. WHEN a Sweep_Point backtest completes with exit code 0, THE ParNeeds_Page SHALL parse and save the result and store it as a Run_Result linked to that Sweep_Point.
5. WHEN a Sweep_Point backtest fails with a non-zero exit code, THE ParNeeds_Page SHALL record the Sweep_Point as failed and continue with the next Sweep_Point.
6. WHILE a Parameter Sensitivity run is in progress, THE ParNeeds_Page SHALL display the current sweep point index and total count in the plan label (e.g. "Sweep point 12 / 48").
7. WHEN the user clicks Stop during a Parameter Sensitivity run, THE ParNeeds_Page SHALL cancel the active subprocess and halt further sweep execution.

---

### Requirement 10: Parameter Sensitivity Workflow — Results Display

**User Story:** As a strategy developer, I want to see a sweep results table and a sensitivity heatmap after a Parameter Sensitivity run, so that I can identify which parameters have the most impact on performance.

#### Acceptance Criteria

1. WHEN all sweep points complete, THE ParNeeds_Page SHALL display a sweep results table with columns: Sweep Point, Parameter, Value, Profit %, Win %, DD %, Trades, Status, Run ID.
2. WHEN all sweep points complete and more than one parameter was swept, THE ParNeeds_Page SHALL display a sensitivity heatmap showing Profit % as a function of parameter values.
3. WHEN all sweep points complete and only one parameter was swept, THE ParNeeds_Page SHALL display a line chart showing Profit % as a function of that parameter's values.
4. THE ParNeeds_Page SHALL highlight the Sweep_Point row with the highest Profit % in the results table.
5. WHEN the Parameter Sensitivity run completes, THE ParNeeds_Page SHALL emit the `run_completed` signal for each Sweep_Point Run_Result that has a valid run ID.

---

### Requirement 11: Parameter Sensitivity Workflow — Configuration

**User Story:** As a strategy developer, I want to configure the Parameter Sensitivity workflow in the config panel, so that I can choose which parameters to sweep and how.

#### Acceptance Criteria

1. THE ParNeeds_Page SHALL expose the following Parameter Sensitivity configuration fields when "Parameter Sensitivity workflow" is selected: sweep mode (One_At_A_Time_Mode or Grid_Mode, default One_At_A_Time_Mode), and a parameter list with per-parameter range controls (min, max, step for numeric; value list for categorical/boolean).
2. WHEN the user changes the sweep mode or parameter ranges, THE ParNeeds_Page SHALL update the plan label to show the recalculated total number of Sweep_Points.
3. THE ParNeeds_Page SHALL hide Parameter Sensitivity configuration fields when a different workflow is selected.
4. IF Grid_Mode is selected and the total number of Sweep_Points exceeds 200, THEN THE ParNeeds_Page SHALL display a warning and require explicit confirmation before starting the run.

---

### Requirement 12: Shared Results Table

**User Story:** As a strategy developer, I want all three new workflows to populate the same shared results table format, so that I can compare runs across workflow types in a consistent view.

#### Acceptance Criteria

1. THE ParNeeds_Page SHALL display a shared results table with the following columns for all workflow types: Run/Trial, Workflow, Strategy, Pair(s), Timeframe, Timerange, Profit %, Total Profit, Win Rate, Max DD %, Trades, Profit Factor, Sharpe Ratio, Score, Status, Result Path, Log Path.
2. WHEN a workflow produces a result that does not have a value for a column, THE ParNeeds_Page SHALL display "-" in that cell.
3. THE ParNeeds_Page SHALL preserve existing Timerange workflow result rows in the table when a new workflow run is started, unless the user explicitly clears the table.

---

### Requirement 13: Result Export

**User Story:** As a strategy developer, I want to export ParNeeds results to JSON and CSV, so that I can archive runs and analyse them outside the application.

#### Acceptance Criteria

1. THE ParNeeds_Page SHALL provide an "Export" button that is enabled when the results table contains at least one row.
2. WHEN the user clicks Export, THE ParNeeds_Page SHALL write a JSON file containing all current result rows with all available fields to the configured export directory.
3. WHEN the user clicks Export, THE ParNeeds_Page SHALL write a CSV file containing the visible results table columns to the configured export directory.
4. THE ParNeeds_Page SHALL name export files using the pattern `parneeds_{workflow}_{timestamp}.json` and `parneeds_{workflow}_{timestamp}.csv`.
5. WHEN an export file is written successfully, THE ParNeeds_Page SHALL display the file path in the Terminal_Widget.
6. IF an export write fails, THEN THE ParNeeds_Page SHALL display a descriptive error message in the Terminal_Widget without crashing.

---

### Requirement 14: Workflow Selector Integration

**User Story:** As a strategy developer, I want the workflow selector dropdown to include all four workflows, so that I can switch between them without leaving the ParNeeds page.

#### Acceptance Criteria

1. THE ParNeeds_Page SHALL include "Walk-Forward workflow", "Monte Carlo workflow", and "Parameter Sensitivity workflow" as selectable options in the workflow combo box, in addition to the existing "Timerange workflow".
2. WHEN the user selects a workflow, THE ParNeeds_Page SHALL show only the configuration fields relevant to that workflow and hide all others.
3. WHEN the user selects a workflow while a run is in progress, THE ParNeeds_Page SHALL ignore the selection change and keep the current workflow active.

---

### Requirement 15: Candle Coverage Validation for New Workflows

**User Story:** As a strategy developer, I want the Walk-Forward and Parameter Sensitivity workflows to validate candle coverage before running backtests, so that I am not surprised by missing data mid-run.

#### Acceptance Criteria

1. WHEN a Walk-Forward or Parameter Sensitivity run is started, THE ParNeeds_Page SHALL invoke the ParNeeds_Service candle coverage validation for the full configured timerange before generating folds or sweep points.
2. IF candle coverage has blocking gaps, THEN THE ParNeeds_Page SHALL attempt auto-download using the existing download queue mechanism before proceeding.
3. THE Monte_Carlo_Workflow SHALL reuse the same candle data for all iterations and SHALL NOT re-validate coverage per iteration.
