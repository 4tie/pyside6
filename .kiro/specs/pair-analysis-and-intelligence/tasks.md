# Implementation Tasks — Pair Analysis and Intelligence

## Tasks

- [x] 1. Add PairMetrics, PairAnalysis, and RunComparison dataclasses to results_models.py
  - [x] 1.1 Add `PairMetrics` dataclass with fields: `pair`, `total_profit_pct`, `win_rate`, `trade_count`, `max_drawdown_pct`, `profit_share`
  - [x] 1.2 Add `PairAnalysis` dataclass with fields: `pair_metrics`, `best_pairs`, `worst_pairs`, `dominance_flags`
  - [x] 1.3 Add `RunComparison` dataclass with fields: `profit_diff`, `winrate_diff`, `drawdown_diff`, `verdict`
  - [x] 1.4 Verify existing imports of `results_models` are unaffected (no regressions)

- [x] 2. Create DiagnosisSuggestion dataclass in analysis_models.py
  - [x] 2.1 Create `app/core/models/analysis_models.py` with `DiagnosisSuggestion` dataclass (`rule_id`, `message`, `severity`)
  - [x] 2.2 Add module-level logger and Google-style docstring

- [x] 3. Implement PairAnalysisService
  - [x] 3.1 Create `app/core/services/pair_analysis_service.py` with stateless `PairAnalysisService` class
  - [x] 3.2 Implement `analyse(results: BacktestResults) -> PairAnalysis` as `@staticmethod` following the 8-step algorithm in the design
  - [x] 3.3 Handle empty trades case: return `PairAnalysis([], [], [], [])`
  - [x] 3.4 Compute `profit_share` correctly (0.0 when `abs_total == 0`)
  - [x] 3.5 Populate `best_pairs` (top 3 desc) and `worst_pairs` (bottom 3 asc)
  - [x] 3.6 Set `dominance_flags = ["profit_concentration"]` when any single `profit_share > 0.60`

- [x] 4. Write property-based tests for PairAnalysisService
  - [x] 4.1 Create `tests/test_pair_analysis_properties.py` with Hypothesis strategies for `BacktestTrade` and `BacktestResults`
  - [x] 4.2 Implement `test_trade_count_invariant`: `sum(pm.trade_count) == len(trades)` for all non-empty inputs
  - [x] 4.3 Implement `test_empty_trades_returns_empty_analysis`: all lists empty, no flags
  - [x] 4.4 Run tests and confirm they pass

- [x] 5. Implement DiagnosisService
  - [x] 5.1 Create `app/core/services/diagnosis_service.py` with stateless `DiagnosisService` class
  - [x] 5.2 Implement `diagnose(pair_analysis, summary) -> List[DiagnosisSuggestion]` as `@staticmethod`
  - [x] 5.3 Implement all 5 rules: `entry_too_aggressive`, `stoploss_too_loose`, `overfitting_risk`, `insufficient_trades`, `negative_expectancy`
  - [x] 5.4 Ensure all matching rules are included (rules are independent, not mutually exclusive)
  - [x] 5.5 Return empty list when no rules fire

- [x] 6. Write unit tests for DiagnosisService
  - [x] 6.1 Create `tests/test_diagnosis_service.py`
  - [x] 6.2 Test each of the 5 rules fires when its condition is met
  - [x] 6.3 Test each rule does NOT fire when its condition is not met
  - [x] 6.4 Test empty list returned when no conditions met
  - [x] 6.5 Test multiple rules fire simultaneously when multiple conditions met
  - [x] 6.6 Run tests and confirm they pass

- [x] 7. Implement ComparisonService
  - [x] 7.1 Create `app/core/services/comparison_service.py` with stateless `ComparisonService` class
  - [x] 7.2 Implement `compare(run_a, run_b) -> RunComparison` as `@staticmethod`
  - [x] 7.3 Compute `profit_diff`, `winrate_diff`, `drawdown_diff` as `run_b - run_a`
  - [x] 7.4 Implement verdict logic in order: `"improved"` → `"degraded"` → `"neutral"`

- [x] 8. Write property-based tests for ComparisonService
  - [x] 8.1 Create `tests/test_comparison_properties.py` with Hypothesis strategy for `BacktestSummary`
  - [x] 8.2 Implement `test_profit_diff_antisymmetry`: `compare(a,b).profit_diff == -compare(b,a).profit_diff`
  - [x] 8.3 Run tests and confirm they pass

- [x] 9. Harden ImproveService with deterministic version_id paths
  - [x] 9.1 Add `version_id: str` parameter to `prepare_sandbox()`
  - [x] 9.2 Change sandbox path to `{user_data}/strategies/_improve_sandbox/{version_id}/`
  - [x] 9.3 Write config file as `{version_id}.json` (not `{strategy_name}.json`)
  - [x] 9.4 Add collision guard: raise `ValueError` if sandbox directory already exists
  - [x] 9.5 Add `version_id: str` parameter to `build_candidate_command()`
  - [x] 9.6 Change export directory to `{user_data}/backtest_results/_improve/{version_id}/`
  - [x] 9.7 Update `parse_candidate_run()` to try deterministic path `export_dir / f"{version_id}.zip"` first before falling back to `resolve_candidate_artifact()`
  - [x] 9.8 Update all callers of `prepare_sandbox()` and `build_candidate_command()` in `LoopPage` and `ImprovePage` to pass a `version_id`

- [x] 10. Create PairResultsWidget
  - [x] 10.1 Create `app/ui_v2/widgets/pair_results_widget.py` with `PairResultsWidget(QWidget)`
  - [x] 10.2 Build table with columns: Pair | Profit (%) | Win Rate (%) | Trades | Max Drawdown (%)
  - [x] 10.3 Define `_PAIR_TABLE_STYLES` constant with best/worst row styles (single definition, no duplication)
  - [x] 10.4 Apply green background + bold to best pair rows; red background + italic to worst pair rows
  - [x] 10.5 Add concentration warning `QLabel` (hidden by default, shown when `"profit_concentration"` in flags)
  - [x] 10.6 Implement `display(analysis: PairAnalysis)` method
  - [x] 10.7 Implement `clear()` method showing empty state message
  - [x] 10.8 Ensure no service or model imports — widget receives `PairAnalysis` objects only

- [x] 11. Create CompareWidget
  - [x] 11.1 Create `app/ui_v2/widgets/compare_widget.py` with `CompareWidget(QWidget)`
  - [x] 11.2 Add two `QComboBox` selectors (Run A, Run B) and a "Compare" button
  - [x] 11.3 Define `_GREEN`, `_RED`, `_NEUTRAL` colour constants at module level (single definition)
  - [x] 11.4 Implement three metric diff rows with green/red colouring per sign
  - [x] 11.5 Implement verdict label with green/red/neutral colouring
  - [x] 11.6 Show prompt label when fewer than two runs are selected
  - [x] 11.7 Implement `set_run_choices(runs: List[dict])` method
  - [x] 11.8 Implement `display(comparison: RunComparison)` method

- [~] 12. Update BacktestPage with new tabs and load_results()
  - [ ] 12.1 Import `PairResultsWidget`, `CompareWidget`, `PairAnalysisService`, `ComparisonService` in `backtest_page.py`
  - [~] 12.2 Add `_pair_results_widget` and `_compare_widget` instances in `_build_right_panel()`
  - [~] 12.3 Set tab order: Results (0) → Pair Results (1) → Compare (2) → Terminal (3)
  - [~] 12.4 Implement `load_results(results: BacktestResults)` method that calls `_results_widget.display_results()`, `_pair_results_widget.display()`, and navigates to tab 0
  - [~] 12.5 Replace all direct `_results_widget.display_results()` calls in `_try_load_results()` and `_on_load_run()` with `load_results()`
  - [~] 12.6 Wire `_refresh_run_picker()` to also call `_compare_widget.set_run_choices(runs)`
  - [~] 12.7 Wire the Compare button to call `ComparisonService.compare()` and `_compare_widget.display()`

- [~] 13. Add step-gating to LoopPage
  - [~] 13.1 Identify all step-gated control groups in `LoopPage` (Run, Results/Problems, Improve, Preview, Run Candidate, Compare, Accept/Reject)
  - [~] 13.2 Implement `_update_step_gates()` private method that enables/disables controls based on current state flags
  - [~] 13.3 Call `_update_step_gates()` after every state transition: baseline run complete, diagnosis shown, candidate generated, preview shown, candidate run complete, comparison shown
  - [~] 13.4 Ensure Run controls are always enabled (step 1 gate)
  - [~] 13.5 Verify step-gating does not break existing LoopPage functionality
