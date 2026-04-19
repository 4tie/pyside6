# Implementation Plan: Strategy Auto-Optimizer

## Overview

Implements the Strategy Auto-Optimizer feature in two parts: an enhanced Improve tab (multi-round sessions, deeper diagnostics, rollback) and a new Strategy Lab tab (autonomous backtest-diagnose-mutate loop with multi-gate validation). The work is split into six phases ordered to minimise integration risk: pure models and helpers first, then UI upgrades, then the LoopService state machine, then LoopPage UI, then MainWindow wiring, and finally tests.

## Tasks

- [x] 1. Replace loop_models.py with full-spec dataclasses
  - Delete the existing `LoopConfig`, `LoopIteration`, and `LoopResult` definitions in `app/core/models/loop_models.py` and rewrite the file from scratch.
  - Add `RobustScoreInput` dataclass: fields `in_sample: BacktestSummary`, `fold_summaries: Optional[list[BacktestSummary]]`, `stress_summary: Optional[BacktestSummary]`, `pair_profit_distribution: Optional[dict[str, float]]`.
  - Add `RobustScore` dataclass: fields `total: float`, `profitability: float`, `consistency: float`, `stability: float`, `fragility: float`.
  - Add `HardFilterFailure` dataclass: fields `filter_name: str`, `reason: str`, `evidence: str`.
  - Add `GateResult` dataclass with exactly the fields from Requirement 17 criterion 1: `gate_name: str`, `passed: bool`, `metrics: Optional[BacktestSummary]`, `fold_summaries: Optional[list[BacktestSummary]]`, `failure_reason: Optional[str]`.
  - Rewrite `LoopConfig` with all new fields: existing targets plus `oos_split_pct: float = 20.0`, `walk_forward_folds: int = 5`, `stress_fee_multiplier: float = 2.0`, `stress_slippage_pct: float = 0.1`, `stress_profit_target_pct: float = 50.0`, `consistency_threshold_pct: float = 30.0`, `validation_mode: str = "full"`, `profit_concentration_threshold: float = 0.50`, `profit_factor_floor: float = 1.1`, `pair_dominance_threshold: float = 0.60`, `time_dominance_threshold: float = 0.40`, `validation_variance_ceiling: float = 1.0`.
  - Rewrite `LoopIteration` with exactly the fields from Requirement 17 criterion 5: `iteration_number: int`, `params_before: dict`, `params_after: dict`, `changes_summary: list[str]`, `summary: Optional[BacktestSummary]`, `score: Optional[RobustScore]`, `is_improvement: bool`, `status: str`, `error_message: Optional[str]`, `below_min_trades: bool`, `sandbox_path: Path`, `validation_gate_reached: str`, `validation_gate_passed: bool`, `gate_results: list[GateResult]`, `hard_filter_failures: list[HardFilterFailure]`.
  - Keep `LoopResult` with its existing fields; update `best_iteration` type to use the new `LoopIteration`.
  - _Requirements: 5.11–5.19, 8.3–8.4, 10.1, 17.1–17.10, 21.5_

- [x] 2. Add SessionRound and SessionBaseline to improve_models.py
  - Add `SessionBaseline` dataclass to `app/core/models/improve_models.py`: fields `params: dict`, `summary: BacktestSummary`.
  - Add `SessionRound` dataclass: fields `round_number: int`, `params_before: dict`, `params_after: dict`, `summary: BacktestSummary`, `timestamp: datetime`.
  - Import `datetime` and `BacktestSummary` at the top of the file.
  - _Requirements: 16.1_

- [x] 3. Create diagnosis_models.py with DiagnosisInput, DiagnosisBundle, StructuralDiagnosis
  - Create new file `app/core/models/diagnosis_models.py`.
  - Define `StructuralDiagnosis` dataclass: fields `failure_pattern: str`, `evidence: str`, `root_cause: str`, `mutation_direction: str`, `confidence: float`, `severity: str`.
  - Define `DiagnosisInput` dataclass: fields `in_sample: BacktestSummary`, `oos_summary: Optional[BacktestSummary]`, `fold_summaries: Optional[list[BacktestSummary]]`, `trade_profit_contributions: Optional[list[float]]`, `drawdown_periods: Optional[list[tuple[str, str, float]]]`, `atr_spike_periods: Optional[list[tuple[str, str]]]`.
  - Define `DiagnosisBundle` dataclass: fields `issues: list[DiagnosedIssue]`, `structural: list[StructuralDiagnosis]`.
  - Import `DiagnosedIssue` from `app.core.models.improve_models` and `BacktestSummary` from `app.core.backtests.results_models`.
  - _Requirements: 22.1, 22.3_

- [x] 4. Implement compute_score, _normalize_summary, and targets_met in loop_service.py
  - Replace the old `compute_score(summary: BacktestSummary) -> float` function with `compute_score(input: RobustScoreInput) -> RobustScore` implementing the four-component formula from Requirement 8 criterion 1.
  - Implement `_normalize_summary(summary: BacktestSummary) -> BacktestSummary` as a pure helper that substitutes `None`/`NaN` fields with neutral values per Requirement 8 criteria 13–15: `sharpe_ratio` → `0.0`, `profit_factor` → `0.0`, `win_rate` → `0.0`, `max_drawdown` → `100.0`. Log a WARNING for any substitution.
  - Call `_normalize_summary()` inside `compute_score()` before accessing any summary fields.
  - Use fixed reference ranges for `norm()`: `net_profit` [−100, 200], `expectancy` [−1.0, 5.0], `profit_factor` [0, 3.0], `max_drawdown` [0, 100].
  - Update `targets_met(summary: BacktestSummary, config: LoopConfig) -> bool` to match the existing signature (already correct); verify it checks all four conditions simultaneously.
  - Update all call sites inside `loop_service.py` that previously called the old `compute_score`.
  - _Requirements: 8.1–8.5, 8.13–8.15_

  - [x] 4.1 Write property test for compute_score
    - **Property: score components sum to total** — for any valid `RobustScoreInput`, `abs(score.profitability + score.consistency + score.stability - score.fragility - score.total) < 1e-9`.
    - **Property: score is bounded** — `RobustScore.total` is always in `[-0.15, 1.0]` for any normalized input.
    - **Validates: Requirements 8.1, 8.2**

  - [x] 4.2 Write property test for _normalize_summary
    - **Property: no None or NaN fields after normalization** — for any `BacktestSummary` with arbitrary None/NaN fields, `_normalize_summary()` returns a summary with no None or NaN in the four guarded fields.
    - **Validates: Requirements 8.13–8.15**

  - [x] 4.3 Write unit tests for targets_met
    - Test all four conditions independently (each one failing while others pass).
    - Test all four conditions passing simultaneously.
    - _Requirements: 10.10_

- [x] 5. Create HardFilterService in hard_filter_service.py
  - Create new file `app/core/services/hard_filter_service.py`.
  - Implement `HardFilterService` class with two `@staticmethod` methods.
  - `evaluate_post_gate1(gate1_result: GateResult, config: LoopConfig) -> list[HardFilterFailure]`: evaluates filters 1–7 in order using `gate1_result.metrics` (the in-sample `BacktestSummary`). All filters are evaluated even after the first failure; rejection is logical. Filters: `min_trade_count`, `max_drawdown`, `profit_concentration` (top 3 trades vs `config.profit_concentration_threshold`), `profit_factor_floor`, `expectancy_floor`, `pair_dominance`, `time_dominance`.
  - `evaluate_post_gate(gate_name: str, gate_result: GateResult, config: LoopConfig) -> list[HardFilterFailure]`: evaluates filter 8 (`oos_negativity`) when `gate_name == "out_of_sample"` using `gate_result.metrics`; evaluates filter 9 (`validation_variance`) when `gate_name == "walk_forward"` using `gate_result.fold_summaries`.
  - Return empty list when all applicable filters pass.
  - Add module-level logger `_log = get_logger("services.hard_filter")`.
  - _Requirements: 21.1–21.6_

  - [x] 5.1 Write property test for HardFilterService.evaluate_post_gate1
    - **Property: empty list when all thresholds satisfied** — for any `GateResult` where all seven filter conditions are within bounds, `evaluate_post_gate1` returns `[]`.
    - **Property: all failures recorded even after first** — when multiple filters fail, all are present in the returned list.
    - **Validates: Requirements 21.1, 21.4**

  - [x] 5.2 Write unit tests for HardFilterService.evaluate_post_gate
    - Test filter 8 (`oos_negativity`): negative OOS profit → one failure; non-negative → empty list.
    - Test filter 9 (`validation_variance`): CV above ceiling → one failure; below ceiling → empty list; mean ≤ 0 → failure.
    - _Requirements: 21.1, 21.4_

- [x] 6. Upgrade ResultsDiagnosisService to new DiagnosisInput/DiagnosisBundle signature
  - Change `ResultsDiagnosisService.diagnose()` signature from `diagnose(summary: BacktestSummary) -> List[DiagnosedIssue]` to `diagnose(input: DiagnosisInput) -> DiagnosisBundle` in `app/core/services/results_diagnosis_service.py`.
  - Move existing eight shallow-issue rules to use `input.in_sample` instead of `summary`.
  - Add the ten structural diagnosis rules from Requirement 22 criterion 2, each producing a `StructuralDiagnosis` with the specified `failure_pattern`, `evidence`, `root_cause`, `mutation_direction`, `confidence`, and `severity`.
  - Suppress rules that require optional fields (`single_regime_dependency`, `outlier_trade_dependency`, `drawdown_after_volatility`) when those fields are None.
  - Apply `min_confidence` thresholds: critical 0.6, moderate 0.5, advisory 0.4.
  - Return `DiagnosisBundle(issues=[...], structural=[...])`.
  - Update the call site in `app/ui/pages/improve_page.py` to construct a `DiagnosisInput` and unpack the returned `DiagnosisBundle`.
  - Update the call site in `app/core/services/loop_service.py` similarly.
  - _Requirements: 2.1, 2.4, 22.2–22.3_

  - [x] 6.1 Write unit tests for ResultsDiagnosisService.diagnose with DiagnosisInput
    - Test that each of the ten structural patterns fires when its detection criteria are met.
    - Test that rules requiring optional fields are suppressed when those fields are None.
    - Test that `bundle.issues` still contains legacy `DiagnosedIssue` objects for the eight shallow rules.
    - _Requirements: 22.2, 22.3_

- [x] 7. Checkpoint — pure layer complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Extract widget files from improve_page.py
  - Create `app/ui/widgets/issue_badge.py` and move the `IssueBadge` class out of `improve_page.py` into it. Update the import in `improve_page.py`.
  - Create `app/ui/widgets/suggestion_row.py` and move the `SuggestionRow` class out of `improve_page.py` into it. Update the import in `improve_page.py`.
  - Create `app/ui/widgets/animated_metric_card.py` and move the `AnimatedMetricCard` class out of `improve_page.py` into it. Update the import in `improve_page.py`.
  - Create `app/ui/widgets/iteration_history_row.py` with a new `IterationHistoryRow` class (stub for now — full implementation in task 14).
  - Verify `improve_page.py` still imports and uses all three widgets correctly after extraction.
  - _Requirements: 2.2, 2.6, 7.1_

- [x] 9. Upgrade ImprovePage — SessionBaseline, session history, and rollback
  - Add `_session_baseline: Optional[SessionBaseline]` and `_session_history: List[SessionRound]` instance fields to `ImprovePage.__init__`.
  - Implement baseline population on strategy load: call `ImproveService.get_strategy_runs()` and load the most recent run via `ImproveService.load_baseline()`; if no run exists, set `_session_baseline` to None and trigger a fresh baseline backtest.
  - WHEN the user accepts a candidate: construct a `SessionRound` from `_session_baseline.params`, accepted params, candidate `BacktestSummary`, and `datetime.now(timezone.utc)`; append to `_session_history`; update `_session_baseline` to the accepted candidate values.
  - Add a **Rollback** button (hidden until at least one round is accepted): clicking it pops the last `SessionRound` from `_session_history`, calls `ImproveService.rollback()` with `round.params_before`, and restores `_session_baseline.params` to `round.params_before` — no disk read.
  - Add a **Run Another Round** button (hidden until at least one round is accepted): clicking it uses `_session_baseline.params` as the starting point for the next suggestion cycle without re-reading the strategy JSON.
  - WHEN the strategy combo box changes, clear `_session_history` and reset `_session_baseline`.
  - Display the session history list in a scrollable panel showing round number, profit %, win rate, max drawdown, trade count per entry.
  - _Requirements: 1.1–1.9, 15.1–15.5, 16.1–16.5_

- [x] 10. Upgrade ImprovePage — strategy-switch lock and ConfigurationGuard
  - Implement `check_prerequisites(settings: AppSettings) -> list[str]` as a pure module-level function in `app/ui/pages/improve_page.py` (or extract to a shared module if LoopPage also needs it). Checks: `user_data_path` set and exists, Python/Freqtrade executable exists and is executable, at least one `.py` strategy file under `{user_data_path}/strategies/`.
  - Call `check_prerequisites()` on page load and whenever `SettingsState.settings_changed` is emitted; show/hide the warning banner and enable/disable controls accordingly.
  - Disable the strategy combo box while a subprocess is running; re-enable only when no subprocess is active and no candidate decision is pending.
  - _Requirements: 4.1–4.4, 1.7–1.8_

- [x] 11. Upgrade ImprovePage — deeper diagnostics display and comparison table
  - Update the diagnostics panel to construct a `DiagnosisInput` from available data before calling `ResultsDiagnosisService.diagnose()`. When only in-sample data is available, set all optional fields to None.
  - Render `bundle.structural` entries in the diagnostics panel using the extracted `IssueBadge` widget (or a new `StructuralDiagnosisBadge` sub-widget): show `failure_pattern`, `evidence`, `root_cause`, `mutation_direction`, and a `QProgressBar` confidence bar. Badge color: critical → red, moderate → orange, advisory → yellow.
  - Render `bundle.issues` entries using the extracted `IssueBadge` widget.
  - Update the candidate comparison table to use `compute_highlight()` for cell coloring.
  - Update `ImproveService.build_candidate_command()` call to pass `--backtest-directory {sandbox_dir}/backtest_output/` as the export directory.
  - Update `ImproveService.parse_candidate_run()` call to pass the `export_dir` directory (not a file path).
  - _Requirements: 2.1–2.6, 3.1–3.9_

- [x] 12. Add resolve_candidate_artifact to ImproveService and update sandbox path format
  - Add `resolve_candidate_artifact(export_dir: Path) -> Path` method to `ImproveService` in `app/core/services/improve_service.py`. Locates the single `.zip` in `export_dir`; raises `FileNotFoundError` with `export_dir` in the message if zero zips found. Remove the old `resolve_candidate_zip` mtime-scan fallback.
  - Update `parse_candidate_run(export_dir: Path)` to call `resolve_candidate_artifact(export_dir)` internally.
  - Update `prepare_sandbox()` to use `timestamp_ms` (Unix timestamp in milliseconds) in the directory name: `{user_data}/strategies/_improve_sandbox/{strategy_name}_{timestamp_ms}/`.
  - _Requirements: 3.8–3.9, 6.11–6.12, 18.1, 18.7_

  - [x] 12.1 Write unit tests for ImproveService.resolve_candidate_artifact
    - Test: exactly one zip → returns its path.
    - Test: zero zips → raises `FileNotFoundError` with `export_dir` in message.
    - _Requirements: 3.9, 18.7_

- [x] 13. Checkpoint — ImprovePage upgrade complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Upgrade LoopService state machine — new scoring, gate ladder, hard filters
  - Rewrite `LoopService.start()` to accept the new `LoopConfig` fields; compute `training_end_date` and `oos_end_date` from `date_from`, `date_to`, and `oos_split_pct`; assert `training_end_date < date_to`.
  - Rewrite `LoopService.prepare_next_iteration()` to return a `LoopIteration` (new field set) instead of a tuple; populate `sandbox_path`, `changes_summary` (list of strings), `iteration_number`.
  - Implement the five-gate validation ladder inside `LoopService` (or a private `_run_gate()` helper): Gate 1 in-sample, Gate 2 OOS, Gate 3 walk-forward (K folds), Gate 4 stress test, Gate 5 consistency check. Each gate appends a `GateResult` to `iteration.gate_results`. Short-circuit on first gate failure.
  - After Gate 1, call `HardFilterService.evaluate_post_gate1(gate1_result, config)`; if failures returned, set `iteration.status = "hard_filter_rejected"`, populate `iteration.hard_filter_failures`, skip remaining gates.
  - After Gate 2, call `HardFilterService.evaluate_post_gate("out_of_sample", gate2_result, config)`; reject if failures.
  - After Gate 3, call `HardFilterService.evaluate_post_gate("walk_forward", gate3_result, config)`; reject if failures.
  - Implement Gate 5 as a pure computation over Gate 3 fold profits (no backtest): `std_dev(fold_profits) <= (consistency_threshold_pct / 100) * mean(fold_profits)`; fail unconditionally if mean ≤ 0.
  - Update `record_iteration_result()` to accept the new `LoopIteration`; compute `RobustScore` via `compute_score(RobustScoreInput(...))`; set `is_improvement` only when `validation_gate_passed=True` and score exceeds best; handle `zero_trades` and `below_min_trades` guards.
  - When `validation_mode == "quick"`, skip Gates 3–5.
  - Update `finalize()` to set `best_iteration` from fully-validated iterations only.
  - _Requirements: 6.16–6.18, 8.6–8.12, 9.1–9.6, 10.1–10.10, 21.1–21.6_

  - [x] 14.1 Write property test for SuggestionRotator variation logic
    - **Property: no duplicate configs submitted** — for any sequence of `generate_suggestions()` calls, the set of returned candidate configs never contains a duplicate.
    - **Validates: Requirements 9.1**

  - [x] 14.2 Write unit tests for LoopService state machine
    - Test `start()` → `prepare_next_iteration()` → `record_iteration_result()` → `should_continue()` → `finalize()` happy path.
    - Test `stop()` causes `should_continue()` to return False.
    - Test `zero_trades` guard: iteration not eligible for best.
    - Test `below_min_trades` guard: `is_improvement` always False.
    - Test gate short-circuit: Gate 1 failure skips Gates 2–5.
    - Test hard filter rejection: `status="hard_filter_rejected"`, loop continues.
    - _Requirements: 8.7–8.12, 10.2–10.4, 21.2–21.3_

- [x] 15. Upgrade SuggestionRotator in loop_service.py
  - Verify `already_tried()` and `mark_tried()` use the existing `_config_key()` frozenset approach (already implemented).
  - Verify `_MAX_STEPS_PER_PARAM = 5` and `exhausted()` logic (already implemented).
  - Verify step-based multiplier: step 0 → 1×, step 1 → 1.5×, step 2 → 2× (already implemented).
  - Verify direction reversal when `prev_was_worse` (already implemented).
  - Update `generate_suggestions()` to accept the new `LoopIteration` type (field `iteration_number` instead of `iteration_num`).
  - _Requirements: 9.1–9.6_

- [x] 16. Checkpoint — LoopService upgrade complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Implement IterationHistoryRow widget
  - Implement `IterationHistoryRow` in `app/ui/widgets/iteration_history_row.py`.
  - Show: iteration number badge, status icon (✅ / ➡ / ❌), `changes_summary` joined string, profit %, win rate, max drawdown, trade count, Sharpe ratio, last gate name (`validation_gate_reached`), gate pass/fail.
  - Gate progress indicator: e.g. "3/5 gates" for Full Ladder, "1/2 gates" for Quick mode.
  - Border and badge logic: green + "BEST" for `is_improvement=True`; red for `status="error"`; amber + "PARTIAL" for passed Gate 1 but `validation_gate_passed=False` and `status != "hard_filter_rejected"`; orange + "FILTERED" + filter names for `status="hard_filter_rejected"`; default border otherwise.
  - _Requirements: 7.1–7.9, 21.8–21.9_

- [x] 18. Upgrade LoopPage UI — config controls and validation mode
  - Add the following spin boxes to the Loop Configuration panel in `app/ui/pages/loop_page.py`:
    - **Out-of-Sample Split (%)**: range 5–50, default 20, maps to `LoopConfig.oos_split_pct`.
    - **Walk-Forward Folds (K)**: range 2–10, default 5, maps to `LoopConfig.walk_forward_folds`.
    - **Stress Fee Multiplier**: range 1.0–5.0, step 0.1, default 2.0, maps to `LoopConfig.stress_fee_multiplier`.
    - **Stress Slippage (%)**: range 0.0–2.0, step 0.01, default 0.1, maps to `LoopConfig.stress_slippage_pct`.
    - **Stress Profit Target (%)**: range 0–100, default 50, maps to `LoopConfig.stress_profit_target_pct`.
    - **Consistency Threshold (%)**: range 0–100, default 30, maps to `LoopConfig.consistency_threshold_pct`.
  - Add a **Validation Mode** `QComboBox` with options "Full Ladder" (default) and "Quick". When "Quick" is selected, disable the walk-forward, stress-test, and consistency spin boxes.
  - Add a collapsible **Advanced Filters** `QGroupBox` containing five spin boxes: Max Profit Concentration (0.10–0.90, step 0.05, default 0.50), Min Profit Factor (1.0–3.0, step 0.05, default 1.1), Max Single-Pair Profit Share (0.10–1.0, step 0.05, default 0.60), Max Single-Period Profit Share (0.10–1.0, step 0.05, default 0.40), Max Walk-Forward Variance CV (0.1–3.0, step 0.1, default 1.0).
  - Update `_on_start()` to include all new fields when constructing `LoopConfig`.
  - _Requirements: 5.11–5.19_

- [x] 19. Upgrade LoopPage UI — iteration history, stat cards, progress bar
  - Replace the existing `_IterationRow` inner class with the extracted `IterationHistoryRow` widget from task 17.
  - Update `_on_iteration_complete()` to construct and append an `IterationHistoryRow` using the new `LoopIteration` field names (`iteration_number`, `changes_summary` list, `validation_gate_reached`, `validation_gate_passed`, `status`, `hard_filter_failures`).
  - Auto-scroll the history list to the most recently added row after each append.
  - Update the five `_StatCard` widgets to refresh after each iteration that sets a new best score.
  - Update the progress bar to show `current_iteration / max_iterations * 100`.
  - _Requirements: 7.1–7.9_

- [x] 20. Upgrade LoopPage UI — best result panel, apply/discard, stale sandbox cleanup
  - Update the Best Result Found panel to show: iteration number, profit %, win rate, max drawdown, trade count, Sharpe ratio, and a human-readable parameter changes summary.
  - Update `_on_apply_best()` to show a confirmation `QMessageBox` listing parameter changes before calling `ImproveService.accept_candidate()`. On `OSError`, show an error dialog.
  - Implement stale sandbox cleanup on startup: in `LoopPage.__init__` (or a `QTimer.singleShot(0, ...)` deferred call), scan `{user_data}/strategies/_improve_sandbox/` for directories older than 24 hours and delete them silently in a background thread or deferred call that does not block the UI.
  - _Requirements: 11.1–11.7, 18.6_

- [x] 21. Upgrade LoopPage UI — state machine and ConfigurationGuard
  - Implement `check_prerequisites()` (reuse or import from the shared implementation in task 10) and wire it to `SettingsState.settings_changed`.
  - Implement the full LoopPage state machine per Requirement 19 criteria 6–10: idle-no-strategy, idle-strategy-selected, running, finalizing, post-apply/discard. Show/hide Start Loop, Stop, Apply Best Result, and Discard buttons at each transition.
  - Disable strategy combo box and all config spin boxes while loop is running; re-enable on finalize.
  - _Requirements: 13.1–13.5, 19.6–19.10_

- [x] 22. Checkpoint — LoopPage upgrade complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 23. Register LoopPage in MainWindow
  - Import `LoopPage` in `app/ui/main_window.py`.
  - Instantiate `self.loop_page = LoopPage(self.settings_state)` in `MainWindow.__init__`.
  - Add it to `self.tabs` after the Improve tab and before the Optimize tab: `self.tabs.insertTab(self.tabs.indexOf(self.optimize_page), self.loop_page, "Strategy Lab")`.
  - Add `self.loop_page.terminal` to the `_all_terminals` property list.
  - _Requirements: 14.1–14.3_

- [x] 24. Write integration and property tests for compute_highlight and session history
  - [x] 24.1 Write unit tests for compute_highlight
    - Test all metric directions: higher-is-better metrics return "green" when candidate > baseline, "red" when candidate < baseline.
    - Test lower-is-better metrics return "green" when candidate < baseline.
    - Test equal values return None.
    - _Requirements: 3.6_

  - [x] 24.2 Write property test for ImprovePage session history and rollback
    - **Property: rollback restores previous state** — for any sequence of accept/rollback operations, the final `SessionBaseline.params` equals the params that were current before the last accepted round.
    - Use the existing `simulate_history()` pure function as the model.
    - **Validates: Requirements 1.3–1.4, 16.4**

- [x] 25. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP.
- Each task references specific requirements for traceability.
- Phases 1–3 (tasks 1–16) have no Qt dependencies and can be tested in isolation with `pytest`.
- The `LoopService` gate ladder (task 14) issues separate subprocess commands per gate; the UI layer (LoopPage) is responsible for wiring each gate's `on_finished` callback to the next gate dispatch.
- `compute_highlight()` already exists in `improve_page.py` as a module-level pure function — do not move it; import it from there in tests.
- `simulate_history()` already exists in `improve_page.py` as a module-level pure function — use it directly in property tests.
- The `--export-filename` flag SHALL NOT be used in any backtest command (deprecated in Freqtrade).
