# Implementation Plan: ParNeeds — Walk-Forward, Monte Carlo, and Parameter Sensitivity Workflows

## Overview

Extend the existing ParNeeds page with three new validation workflows (Walk-Forward, Monte Carlo, Parameter Sensitivity) by adding new data models, new service methods, a restructured three-pane UI, property-based tests, and an export mechanism. All subprocess work continues through the existing `ProcessRunManager` / `BacktestService` wrappers. Business logic stays in `app/core/**`; UI orchestration stays in `app/ui/**`.

## Tasks

- [x] 1. Extend data models in `app/core/models/parneeds_models.py`
  - Add `WalkForwardMode` enum (`ANCHORED`, `ROLLING`)
  - Add frozen dataclasses: `WalkForwardConfig`, `WalkForwardFold`, `WalkForwardFoldResult`
  - Add frozen dataclasses: `MonteCarloConfig`, `MCPercentiles`, `MCSummary`
  - Add `SweepParamType` enum and dataclasses: `SweepParameterDef`, `SweepPoint`, `SweepPointResult`
  - Replace the existing `ParNeedsRunResult` with the extended version that includes `run_trial`, `workflow`, `profit_pct`, `total_profit`, `win_rate`, `max_dd_pct`, `trades`, `profit_factor`, `sharpe_ratio`, `score`, `result_path`, `log_path` — keep backward compatibility with the Timerange workflow by mapping existing fields
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 3.1, 5.1, 6.1, 8.1, 9.1, 12.1_

- [x] 2. Implement Walk-Forward service methods in `app/core/services/parneeds_service.py`
  - [x] 2.1 Implement `generate_walk_forward_folds(config: WalkForwardConfig) -> list[WalkForwardFold]`
    - Parse timerange start/end using existing `parse_timerange`
    - Compute fold step as `total_days / n_folds`
    - Anchored mode: IS start is always global start; IS end advances by one step per fold; OOS window follows immediately
    - Rolling mode: both IS and OOS windows slide forward by one step per fold
    - Raise `ValueError` with a descriptive message when the timerange is too short to produce at least 2 folds
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 2.2 Write property test for `generate_walk_forward_folds` — fold count (Property 1)
    - **Property 1: Walk-Forward fold count**
    - **Validates: Requirements 1.1, 1.5**

  - [x] 2.3 Write property test for `generate_walk_forward_folds` — anchored start invariant (Property 2)
    - **Property 2: Anchored mode — start date invariant**
    - **Validates: Requirements 1.2**

  - [x] 2.4 Write property test for `generate_walk_forward_folds` — rolling step invariant (Property 3)
    - **Property 3: Rolling mode — fixed step invariant**
    - **Validates: Requirements 1.3**

  - [x] 2.5 Write property test for `generate_walk_forward_folds` — split ratio invariant (Property 4)
    - **Property 4: Split ratio invariant**
    - **Validates: Requirements 1.4**

  - [x] 2.6 Implement `compute_stability_score(oos_profits: list[float]) -> float`
    - Return 0.0 for empty list
    - Score = `(positive_fold_ratio * 70) + (consistency_bonus * 30)` clamped to `[0, 100]`
    - Consistency bonus derived from inverse coefficient of variation of OOS profits
    - _Requirements: 3.2_

  - [x] 2.7 Write property test for `compute_stability_score` — bounded output (Property 5)
    - **Property 5: Stability score is bounded**
    - **Validates: Requirements 3.2**

- [-] 3. Implement Monte Carlo service methods in `app/core/services/parneeds_service.py`
  - [x] 3.1 Implement `generate_mc_seed(base_seed: int, iteration_index: int) -> int`
    - Derive a unique, deterministic seed per iteration: `(base_seed * 1_000_003 + iteration_index) % (2**31 - 1)` or equivalent hash
    - Same call with same arguments must always return the same value
    - Different iteration indices must produce different seeds
    - _Requirements: 5.2_

  - [x] 3.2 Write property test for `generate_mc_seed` — determinism and uniqueness (Property 6)
    - **Property 6: Monte Carlo seed determinism and uniqueness**
    - **Validates: Requirements 5.2**

  - [x] 3.3 Implement `apply_profit_noise(profit: float, seed: int, noise_pct: float = 0.02) -> float`
    - Use `random.Random(seed)` to generate a multiplier in `[1 - noise_pct, 1 + noise_pct]`
    - Return `profit * multiplier`
    - Must not modify any backtest output files
    - _Requirements: 5.4_

  - [x] 3.4 Write property test for `apply_profit_noise` — noise within bounds (Property 7)
    - **Property 7: Profit noise stays within bounds**
    - **Validates: Requirements 5.4**

  - [x] 3.5 Implement `compute_mc_percentiles(values: list[float]) -> MCPercentiles`
    - Use `statistics.quantiles` or `sorted` index arithmetic to compute p5, p50, p95
    - Raise `ValueError` for empty list
    - _Requirements: 6.3_

  - [x] 3.6 Write property test for `compute_mc_percentiles` — ordering invariant (Property 8)
    - **Property 8: Percentile ordering invariant**
    - **Validates: Requirements 6.3**

- [x] 4. Implement Parameter Sensitivity service methods in `app/core/services/parneeds_service.py`
  - [x] 4.1 Implement `discover_strategy_parameters(strategy_path: Path) -> list[SweepParameterDef]`
    - Parse the strategy Python file with `ast` to find `IntParameter`, `DecimalParameter`, `CategoricalParameter`, `BooleanParameter` assignments
    - Also expose fixed backtest params: `stoploss`, `roi_table`, `trailing_stop`, `trailing_stop_positive`, `trailing_stop_positive_offset`, `max_open_trades` as `SweepParamType.FIXED`
    - Return empty list (not raise) when no parameters are found
    - _Requirements: 8.1, 8.2_

  - [x] 4.2 Implement `generate_oat_sweep_points(params: list[SweepParameterDef], baseline: dict[str, Any]) -> list[SweepPoint]`
    - For each enabled parameter, enumerate its range while holding all others at baseline
    - Return one `SweepPoint` per value per parameter
    - _Requirements: 9.1_

  - [x] 4.3 Write property test for `generate_oat_sweep_points` — point count (Property 9)
    - **Property 9: OAT sweep point count**
    - **Validates: Requirements 9.1**

  - [x] 4.4 Implement `generate_grid_sweep_points(params: list[SweepParameterDef], baseline: dict[str, Any]) -> list[SweepPoint]`
    - Compute the Cartesian product of all enabled parameter ranges using `itertools.product`
    - Return one `SweepPoint` per combination
    - _Requirements: 9.2_

  - [x] 4.5 Write property test for `generate_grid_sweep_points` — Cartesian product count (Property 10)
    - **Property 10: Grid sweep point count**
    - **Validates: Requirements 9.2**

- [x] 5. Implement export method in `app/core/services/parneeds_service.py`
  - [x] 5.1 Implement `export_results(results: list[ParNeedsRunResult], workflow: str, export_dir: Path) -> tuple[Path, Path]`
    - Generate timestamp string `YYYYMMDD_HHMMSS`
    - Write `parneeds_{workflow}_{timestamp}.json` (full field serialization via `dataclasses.asdict`)
    - Write `parneeds_{workflow}_{timestamp}.csv` (visible table columns only, using `csv.DictWriter`)
    - Return `(json_path, csv_path)`
    - Raise on write failure (caller logs and surfaces to terminal)
    - _Requirements: 13.2, 13.3, 13.4_

  - [x] 5.2 Write property test for `export_results` — filename pattern (Property 12)
    - **Property 12: Export filename pattern**
    - **Validates: Requirements 13.4**

- [x] 6. Checkpoint — core service layer complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Restructure `app/ui/pages/parneeds_page.py` — three-pane layout and workflow selector
  - Replace the existing two-pane splitter with a three-pane layout: left sidebar (config), center pane (terminal + results table), right sidebar (summary + chart + export)
  - Add "Walk-Forward workflow", "Monte Carlo workflow", "Parameter Sensitivity workflow" to `_workflow_combo` (keep "Timerange workflow" as first item)
  - Connect `_workflow_combo.currentIndexChanged` to a `_on_workflow_changed` slot that shows/hides the correct `QStackedWidget` panel and updates the plan label
  - Ignore workflow combo changes while `_running` is True
  - Add `_sig_result = Signal(object)` bridge signal for batched result row delivery
  - Add a `QTimer` (500 ms) that calls `_flush_pending_updates()` to batch-write pending log lines and result rows to the terminal and table (matching the `OptimizerPage` pattern)
  - _Requirements: 14.1, 14.2, 14.3_

- [-] 8. Build workflow-specific config panels in `app/ui/pages/parneeds_page.py`
  - [x] 8.1 Build Walk-Forward config panel (`QFrame` + `QFormLayout`)
    - `_wf_folds_spin`: QSpinBox, range 2–20, default 5
    - `_wf_split_spin`: QSpinBox (%), range 50–95, default 80
    - `_wf_mode_combo`: QComboBox ["anchored", "rolling"], default "anchored"
    - Connect value-change signals to `_update_plan_label`
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 8.2 Build Monte Carlo config panel (`QFrame` + `QFormLayout`)
    - `_mc_iterations_spin`: QSpinBox, range 10–5000, default 500
    - `_mc_randomise_chk`: QCheckBox "Randomise trade order", default checked
    - `_mc_noise_chk`: QCheckBox "Profit noise (±2%)", default checked
    - `_mc_max_dd_spin`: QDoubleSpinBox (%), range 1–100, default 20
    - Connect value-change signals to `_update_plan_label`
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 8.3 Build Parameter Sensitivity config panel (`QFrame` + `QFormLayout`)
    - `_ps_mode_combo`: QComboBox ["One-at-a-time", "Grid"], default "One-at-a-time"
    - `_ps_param_table`: QTableWidget — columns: Enabled, Name, Type, Min, Max, Step/Values
    - `_ps_discover_btn`: QPushButton "Discover Parameters" — calls `_discover_ps_parameters()`
    - Connect value-change signals to `_update_plan_label`
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 8.4 Wire `QStackedWidget` to show the correct panel when workflow changes
    - Index 0 → no extra panel (Timerange)
    - Index 1 → Walk-Forward panel
    - Index 2 → Monte Carlo panel
    - Index 3 → Parameter Sensitivity panel
    - _Requirements: 14.2_

- [-] 9. Rebuild shared results table and right sidebar in `app/ui/pages/parneeds_page.py`
  - Replace the existing 7-column results table with the 17-column shared table: Run/Trial, Workflow, Strategy, Pair(s), Timeframe, Timerange, Profit %, Total Profit, Win Rate, Max DD %, Trades, Profit Factor, Sharpe Ratio, Score, Status, Result Path, Log Path
  - Display "-" for any `None` field (reuse `_fmt_float` / `_fmt_int` helpers)
  - Preserve existing Timerange workflow rows when a new workflow run starts (do not call `setRowCount(0)` on workflow switch)
  - Build right sidebar: summary `QLabel` block, chart placeholder `QLabel` (backed by `matplotlib` `FigureCanvasQTAgg` when available, graceful fallback to `QLabel`), Export `QPushButton`
  - Export button disabled when table is empty; enabled when table has ≥ 1 row
  - Connect Export button to `_export_results()`
  - _Requirements: 12.1, 12.2, 12.3, 13.1_

  - [~] 9.1 Write property test for results table formatter — missing field displays "-" (Property 11)
    - **Property 11: Missing field formatting**
    - **Validates: Requirements 12.2**

- [x] 10. Implement Walk-Forward workflow execution in `app/ui/pages/parneeds_page.py`
  - [x] 10.1 Implement `_build_wf_config() -> WalkForwardConfig` from current form values
    - _Requirements: 4.1_

  - [x] 10.2 Implement `start_walk_forward_workflow()` — entry point wired to Start button when WF workflow is active
    - Call `_build_wf_config()`, then `_parneeds_svc.generate_walk_forward_folds(config)`
    - On `ValueError` from fold generation: display error in terminal, do not start
    - Display fold schedule in terminal before any backtest starts
    - Invoke candle coverage validation for the full timerange; queue downloads if gaps found
    - On coverage OK: call `_start_next_wf_backtest()`
    - _Requirements: 1.6, 2.1, 15.1, 15.2_

  - [x] 10.3 Implement `_start_next_wf_backtest()` — sequential IS-then-OOS execution per fold
    - Pop the next `(fold, window_type)` tuple from `_pending_wf_items`
    - Build command via `_backtest_svc.build_command(timerange=fold.is_timerange / fold.oos_timerange)`
    - Update plan label: "Fold N / total — IS/OOS"
    - Call `_start_process(cmd)`
    - _Requirements: 2.1, 2.4_

  - [x] 10.4 Implement `_handle_wf_backtest_finished(exit_code)` — result parsing and fold result update
    - On exit 0: parse and save result via `_backtest_svc.parse_and_save_latest_results()`; update `WalkForwardFoldResult`; call `_append_result_row()`; emit `run_completed`
    - On non-zero exit: mark fold as failed; log exit code; continue
    - When all folds done: call `_finish_walk_forward()`
    - _Requirements: 2.2, 2.3, 3.5_

  - [x] 10.5 Implement `_finish_walk_forward()` — stability score and summary display
    - Collect OOS profits from completed folds
    - Call `_parneeds_svc.compute_stability_score(oos_profits)`
    - Display stability score, average OOS profit %, average OOS DD %, pass/fail count in right sidebar summary
    - Colour-code fold rows: green for positive OOS profit, red for negative or failed
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 11. Implement Monte Carlo workflow execution in `app/ui/pages/parneeds_page.py`
  - [x] 11.1 Implement `_build_mc_config() -> MonteCarloConfig` from current form values
    - _Requirements: 7.1_

  - [x] 11.2 Implement `start_monte_carlo_workflow()` — entry point wired to Start button when MC workflow is active
    - Call `_build_mc_config()`
    - Validate candle coverage once for the full timerange; queue downloads if gaps found
    - On coverage OK: call `_start_next_mc_iteration()`
    - _Requirements: 5.1, 15.3_

  - [x] 11.3 Implement `_start_next_mc_iteration()` — sequential iteration execution
    - Generate seed via `_parneeds_svc.generate_mc_seed(base_seed, i)`
    - Build command with `extra_flags=["--random-state", str(seed_i)]` when randomise is enabled
    - Update plan label: "Iteration N / total"
    - Call `_start_process(cmd)`
    - _Requirements: 5.2, 5.3, 5.6_

  - [x] 11.4 Implement `_handle_mc_iteration_finished(exit_code)` — result parsing and noise application
    - On exit 0: parse result; if profit noise enabled call `_parneeds_svc.apply_profit_noise(profit, seed_i)`; call `_append_result_row()`; emit `run_completed`
    - On non-zero exit: record iteration as failed; continue
    - When all iterations done: call `_finish_monte_carlo()`
    - _Requirements: 5.4, 5.5, 6.4, 6.5_

  - [x] 11.5 Implement `_finish_monte_carlo()` — percentile table and distribution chart
    - Call `_parneeds_svc.compute_mc_percentiles(profits)` for each metric
    - Display `MCSummary` (p5/p50/p95 profit, worst DD, probability of profit, probability exceeding max DD threshold) in right sidebar
    - Render profit distribution histogram via `matplotlib` embedded in right sidebar (graceful fallback to `QLabel` if matplotlib unavailable)
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 12. Implement Parameter Sensitivity workflow execution in `app/ui/pages/parneeds_page.py`
  - [x] 12.1 Implement `_discover_ps_parameters()` — triggered by "Discover Parameters" button
    - Call `_parneeds_svc.discover_strategy_parameters(strategy_path)`
    - Populate `_ps_param_table` with discovered parameters (all disabled by default)
    - If no parameters found: display informational message in terminal; disable Start button
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 12.2 Implement `start_param_sensitivity_workflow()` — entry point wired to Start button when PS workflow is active
    - Read enabled parameters and ranges from `_ps_param_table`
    - Validate candle coverage for the full timerange; queue downloads if gaps found
    - Generate sweep points via `generate_oat_sweep_points` or `generate_grid_sweep_points` based on `_ps_mode_combo`
    - If Grid mode and total points > 200: show `QMessageBox` confirmation; block until confirmed
    - Update plan label: "Sweep point 0 / total"
    - Call `_start_next_sweep_point()`
    - _Requirements: 9.1, 9.2, 9.3, 11.1, 11.2, 11.4, 15.1, 15.2_

  - [x] 12.3 Implement `_start_next_sweep_point()` — sequential sweep execution
    - Pop next `SweepPoint` from `_pending_sweep_points`
    - Build command with parameter override flags
    - Update plan label: "Sweep point N / total"
    - Call `_start_process(cmd)`
    - _Requirements: 9.3, 9.6_

  - [x] 12.4 Implement `_handle_sweep_point_finished(exit_code)` — result parsing and sweep result update
    - On exit 0: parse result; update `SweepPointResult`; call `_append_result_row()`; emit `run_completed`
    - On non-zero exit: record sweep point as failed; continue
    - When all sweep points done: call `_finish_param_sensitivity()`
    - _Requirements: 9.4, 9.5, 10.5_

  - [x] 12.5 Implement `_finish_param_sensitivity()` — chart and best-row highlight
    - Highlight the row with the highest Profit % in the results table
    - Render line chart (1 param) or heatmap (2+ params) in right sidebar via `matplotlib`
    - Display best sweep point summary in right sidebar
    - _Requirements: 10.2, 10.3, 10.4_

- [x] 13. Implement export in `app/ui/pages/parneeds_page.py`
  - Implement `_export_results()` slot connected to Export button
  - Collect all current `ParNeedsRunResult` rows from the table
  - Determine `workflow` label from the active workflow combo selection
  - Call `_parneeds_svc.export_results(results, workflow, export_dir)`
  - On success: display both file paths in terminal via `_terminal.append_info`
  - On failure: display descriptive error in terminal; do not crash
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

- [x] 14. Wire Start button to the active workflow and implement Stop for all new workflows
  - Route `_start_btn.clicked` to the correct `start_*_workflow()` method based on `_workflow_combo.currentIndex()`
  - Implement `_stop()` to cancel the active subprocess via `_process_manager.stop_run()`, clear all pending queues (`_pending_wf_items`, `_pending_mc_iterations`, `_pending_sweep_points`, `_download_queue`), and reset `_phase` and `_running`
  - _Requirements: 2.5, 5.7, 9.7_

- [x] 15. Checkpoint — UI layer complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Write unit tests in `tests/core/services/test_parneeds_service.py`
  - [x] 16.1 Write unit tests for `generate_walk_forward_folds`
    - Test exact fold count for valid configs
    - Test anchored mode: all folds share the same IS start date
    - Test rolling mode: IS start advances by one step per fold
    - Test `ValueError` raised when timerange is too short
    - _Requirements: 1.1, 1.2, 1.3, 1.5_

  - [x] 16.2 Write unit tests for `compute_stability_score`
    - Test empty list returns 0.0
    - Test all-positive profits returns score > 50
    - Test all-negative profits returns score < 50
    - _Requirements: 3.2_

  - [x] 16.3 Write unit tests for `generate_mc_seed`, `apply_profit_noise`, `compute_mc_percentiles`
    - Test seed determinism: same call returns same value
    - Test noise: result within ±2% of input
    - Test percentile ordering: p5 ≤ p50 ≤ p95
    - _Requirements: 5.2, 5.4, 6.3_

  - [x] 16.4 Write unit tests for `generate_oat_sweep_points` and `generate_grid_sweep_points`
    - Test OAT count equals sum of range lengths
    - Test Grid count equals product of range lengths
    - _Requirements: 9.1, 9.2_

  - [x] 16.5 Write unit tests for `export_results` using `tmp_path` fixture
    - Test JSON and CSV files are created
    - Test filenames match `parneeds_{workflow}_{timestamp}` pattern
    - _Requirements: 13.4_

- [x] 17. Write property-based tests in `tests/core/services/test_parneeds_service_pbt.py`
  - [x] 17.1 Implement Hypothesis strategies: `walk_forward_configs()`, `oat_param_configs()`, `grid_param_configs()`, `parneeds_run_results_with_missing_fields()`
    - These are shared `@composite` strategies used by all property tests below

  - [x] 17.2 Implement property tests for Properties 1–5 (Walk-Forward)
    - `test_fold_count_property` — Property 1
    - `test_anchored_start_invariant` — Property 2
    - `test_rolling_step_invariant` — Property 3
    - `test_split_ratio_invariant` — Property 4
    - `test_stability_score_bounded` — Property 5
    - Each test uses `@settings(max_examples=200)` (500 for Property 5)
    - Each test has a comment: `# Feature: parneeds, Property N: <title>`

  - [x] 17.3 Implement property tests for Properties 6–8 (Monte Carlo)
    - `test_mc_seed_determinism_and_uniqueness` — Property 6
    - `test_profit_noise_bounds` — Property 7
    - `test_percentile_ordering` — Property 8
    - Each test uses `@settings(max_examples=200)` (500 for Property 7, 300 for Property 8)

  - [x] 17.4 Implement property tests for Properties 9–10 (Parameter Sensitivity)
    - `test_oat_sweep_count` — Property 9
    - `test_grid_sweep_count` — Property 10
    - Each test uses `@settings(max_examples=200)`

  - [x] 17.5 Implement property tests for Properties 11–12 (UI formatting and export)
    - `test_missing_field_formatting` — Property 11, `@settings(max_examples=300)`
    - `test_export_filename_pattern` — Property 12, `@settings(max_examples=200)`

- [x] 18. Write integration tests in `tests/ui/pages/test_parneeds_page_integration.py`
  - [x] 18.1 Walk-Forward integration: verify subprocess call sequence (IS then OOS per fold) and `run_completed` signal count using mocked `ProcessRunManager` and `BacktestService`
    - _Requirements: 2.1, 3.5_

  - [x] 18.2 Monte Carlo integration: verify coverage check called exactly once and iteration count matches config
    - _Requirements: 5.1, 15.3_

  - [x] 18.3 Parameter Sensitivity integration: verify coverage check called before sweep and sweep point count matches generated list
    - _Requirements: 9.3, 15.1_

  - [x] 18.4 Export integration: verify JSON and CSV files written to `tmp_path` with correct filenames
    - _Requirements: 13.2, 13.3, 13.4_

  - [x] 18.5 Stop integration: verify `ProcessRunManager.stop_run` called when Stop button clicked during each workflow
    - _Requirements: 2.5, 5.7, 9.7_

- [x] 19. Write example-based unit tests in `tests/ui/pages/test_parneeds_page_unit.py`
  - [x] 19.1 Workflow selector shows/hides correct config panels for each workflow selection
    - _Requirements: 14.2_

  - [x] 19.2 Walk-Forward, Monte Carlo, and Parameter Sensitivity config panels have correct default values
    - _Requirements: 4.1, 7.1, 11.1_

  - [x] 19.3 Grid > 200 points shows confirmation dialog; no parameters found disables Start button
    - _Requirements: 8.4, 11.4_

  - [x] 19.4 Results table has correct 17-column headers; Export button disabled when empty, enabled when rows present
    - _Requirements: 12.1, 13.1_

  - [x] 19.5 Fold row colour-coding (green for positive OOS profit, red for negative); best sweep point row highlighted
    - _Requirements: 3.4, 10.4_

- [x] 20. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- The existing Timerange workflow must remain fully functional throughout — do not break `start_timerange_workflow()` or the existing `_append_result` path
- All subprocess work goes through `ProcessRunManager.start_run()` / `stop_run()` — no ad-hoc `subprocess` calls
- Business logic (fold generation, seed derivation, noise, percentiles, sweep generation, export) lives exclusively in `ParNeedsService`; the page only orchestrates
- Property tests use Hypothesis (already present in `.hypothesis/`) with `@settings(max_examples=...)` as specified in the design
- The `_sig_result` bridge signal and 500 ms `QTimer` flush pattern must match `OptimizerPage` for thread safety
- `matplotlib` embedding is optional — use `FigureCanvasQTAgg` when available, fall back to a `QLabel` placeholder
