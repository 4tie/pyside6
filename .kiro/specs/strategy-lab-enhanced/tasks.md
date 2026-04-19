# Implementation Plan: Enhanced Strategy Lab

## Overview

Upgrade the existing `LoopPage` / `LoopService` stack into a full-featured optimization workbench.
The work is split into six epics that build on each other: data-model extensions → service-layer
enhancements → multi-gate pipeline → hyperopt mode → AI advisor → UI rebuild.
All code is Python / PySide6 following the project's layered architecture.

---

## Tasks

- [x] 1. Extend data models for the full parameter surface and new loop config fields
  - [x] 1.1 Add `StrategyLabPreferences` Pydantic model to `app/core/models/settings_models.py`
    - Fields: strategy, max_iterations, target_profit_pct, target_win_rate, target_max_drawdown,
      target_min_trades, stop_on_first_profitable, timerange, pairs (comma-sep), oos_split_pct,
      walk_forward_folds, stress_fee_multiplier, stress_slippage_pct, stress_profit_target_pct,
      consistency_threshold_pct, validation_mode ("full"/"quick"), iteration_mode
      ("rule_based"/"hyperopt"), hyperopt_epochs, hyperopt_spaces (list[str]),
      hyperopt_loss_function, ai_advisor_enabled
    - Add `strategy_lab: StrategyLabPreferences` field to `AppSettings`
    - _Requirements: 8.3_

  - [x] 1.2 Extend `LoopConfig` dataclass in `app/core/models/loop_models.py`
    - Add fields: `iteration_mode: str = "rule_based"`, `hyperopt_epochs: int = 200`,
      `hyperopt_spaces: List[str]`, `hyperopt_loss_function: str`, `pairs: List[str]`,
      `ai_advisor_enabled: bool = False`
    - _Requirements: 3.1, 3.4, 4.1, 8.1_

  - [x] 1.3 Extend `LoopIteration` dataclass in `app/core/models/loop_models.py`
    - Add fields: `ai_suggested: bool = False`, `ai_suggestion_reason: Optional[str] = None`,
      `diagnosed_structural: List = field(default_factory=list)`
    - _Requirements: 4.7, 7.2_

  - [x] 1.4 Write unit tests for new model fields
    - Verify `StrategyLabPreferences` round-trips through JSON via Pydantic
    - Verify `LoopConfig` and `LoopIteration` default values
    - _Requirements: 1.1, 8.3_

- [x] 2. Extend `SuggestionRotator` for the full parameter surface
  - [x] 2.1 Add `_vary_buy_sell_param()` helper to `SuggestionRotator` in `loop_service.py`
    - Numeric buy/sell params: apply step-scaled delta respecting observed range from strategy JSON
    - Boolean buy/sell params: propose toggle as discrete mutation step
    - Clamp all proposed values to valid range; log a warning when clamping occurs
    - _Requirements: 1.2, 1.3, 1.4, 1.7_

  - [x] 2.2 Add trailing-stop mutation to `SuggestionRotator._vary_suggestion()`
    - When `trailing_stop` is `False` and a high-drawdown structural pattern is present,
      propose enabling `trailing_stop` with a conservative `trailing_stop_positive` value
    - _Requirements: 1.5_

  - [x] 2.3 Extend `SuggestionRotator.generate_suggestions()` to handle all ten structural patterns
    - Map `exits_cutting_winners_early` → widen `minimal_roi` targets
    - Map `filter_stack_too_strict` → relax most-restrictive `buy_params` threshold
    - Map `losers_lasting_too_long` → tighten `stoploss`, optionally enable `trailing_stop`
    - Map remaining seven patterns to appropriate parameter mutations
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 2.4 Write unit tests for `SuggestionRotator` parameter surface coverage
    - Test numeric buy/sell param delta with clamping
    - Test boolean toggle mutation
    - Test trailing-stop proposal on high-drawdown pattern
    - Test all ten structural pattern mappings produce non-None suggestions
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 2.2–2.6_

- [x] 3. Extend `ImproveService` to write the full parameter surface to sandbox JSON
  - [x] 3.1 Update `ImproveService._build_freqtrade_params_file()` to include trailing params
    - Write `trailing_stop`, `trailing_stop_positive`, `trailing_stop_positive_offset`,
      `trailing_only_offset_is_reached` from `flat_params` into the nested freqtrade JSON
    - _Requirements: 1.1, 1.6_

  - [x] 3.2 Update `ImproveService.prepare_sandbox()` to accept and write full parameter surface
    - Accept `candidate_config` dict that may contain all parameter groups
    - Ensure `buy_params` and `sell_params` are written under the correct nested keys
    - _Requirements: 1.6_

  - [x] 3.3 Add `ImproveService.cleanup_stale_sandboxes()` method
    - Scan `{user_data}/strategies/_improve_sandbox/` for directories older than 24 hours
    - Skip directories less than 5 minutes old
    - Delete stale directories; log WARNING on `OSError` and continue
    - _Requirements: 11.1, 11.4, 11.5_

  - [x] 3.4 Write unit tests for `ImproveService` sandbox and cleanup
    - Test `_build_freqtrade_params_file()` round-trips trailing params correctly
    - Test `cleanup_stale_sandboxes()` skips young directories and deletes old ones
    - _Requirements: 1.6, 11.1, 11.4, 11.5_

- [x] 4. Implement the multi-gate validation pipeline in `LoopService`
  - [x] 4.1 Add `_run_oos_gate()` method to `LoopService`
    - Compute OOS date range from `config.oos_split_pct` and the full timerange
    - Build and execute a backtest command via `ImproveService` for the OOS range
    - Reject candidate if OOS profit < 50% of in-sample profit; record `GateResult`
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 4.2 Add `_run_walk_forward_gate()` method to `LoopService`
    - Split full date range into `config.walk_forward_folds` equal folds
    - Run a backtest for each fold; collect `BacktestSummary` per fold
    - Reject candidate if fewer than 60% of folds are profitable; record `GateResult`
    - _Requirements: 5.1, 5.2, 5.4_

  - [x] 4.3 Add `_run_stress_gate()` method to `LoopService`
    - Re-run in-sample backtest with fees × `config.stress_fee_multiplier` and
      per-trade slippage of `config.stress_slippage_pct`
    - Reject candidate if stress profit < `config.stress_profit_target_pct`% of main target
    - Record `GateResult` with stress `BacktestSummary`
    - _Requirements: 5.1, 5.2, 5.5_

  - [x] 4.4 Add `_run_consistency_gate()` method to `LoopService`
    - Compute coefficient of variation of per-fold profits from walk-forward gate
    - Reject candidate if CV exceeds `config.consistency_threshold_pct`
    - Record `GateResult`
    - _Requirements: 5.1, 5.2, 5.6_

  - [x] 4.5 Wire gate sequence into `LoopService.record_iteration_result()`
    - Run gates in order: Gate 1 (in-sample) → Gate 2 (OOS) → Gate 3 (walk-forward) →
      Gate 4 (stress) → Gate 5 (consistency)
    - Stop gate sequence on first failure; set `iteration.validation_gate_reached` and
      `iteration.validation_gate_passed` accordingly
    - Skip Gates 3–5 when `config.validation_mode == "quick"`
    - _Requirements: 5.1, 5.2, 5.7_

  - [x] 4.6 Write unit tests for gate logic
    - Test OOS gate rejects when OOS profit < 50% of in-sample
    - Test walk-forward gate rejects when < 60% folds profitable
    - Test stress gate rejects when stress profit below threshold
    - Test consistency gate rejects when CV exceeds threshold
    - Test quick mode skips gates 3–5
    - _Requirements: 5.3, 5.4, 5.5, 5.6, 5.7_

- [x] 5. Implement Hyperopt-Guided iteration mode in `LoopService`
  - [x] 5.1 Add `_build_hyperopt_command()` helper to `LoopService`
    - Build `freqtrade hyperopt` command using `config.hyperopt_spaces`,
      `config.hyperopt_epochs`, and `config.hyperopt_loss_function`
    - Use `ImproveService` sandbox directory and `ProcessService` for execution
    - _Requirements: 3.2, 3.4_

  - [x] 5.2 Add `_parse_hyperopt_result()` helper to `LoopService`
    - Locate the `.fthypt` file written by freqtrade in the hyperopt results directory
    - Parse the best parameter set from the JSON-lines file
    - Return the best params dict; raise `ValueError` on parse failure
    - _Requirements: 3.5_

  - [x] 5.3 Integrate hyperopt mode into `LoopService.prepare_next_iteration()`
    - When `config.iteration_mode == "hyperopt"`, call `_build_hyperopt_command()` instead
      of the rule-based mutation path
    - On exit code 0, call `_parse_hyperopt_result()` and use result as candidate params
    - On non-zero exit code, record iteration as `status="error"` and continue
    - Pass hyperopt candidate through the full gate sequence (tasks 4.1–4.5)
    - _Requirements: 3.2, 3.3, 3.6_

  - [x] 5.4 Write unit tests for hyperopt mode
    - Test `_parse_hyperopt_result()` correctly extracts best params from a sample `.fthypt` file
    - Test non-zero exit code records error and does not stop the loop
    - _Requirements: 3.5, 3.6_

- [x] 6. Implement AI Advisor suggestion layer
  - [x] 6.1 Add `AIAdvisorService` class in `app/core/services/ai_advisor_service.py`
    - Method `build_prompt(strategy_name, params, summary, issues) -> str`
      including strategy name, current parameter values, backtest metrics, and diagnosed issues
    - Method `request_suggestion(prompt) -> Optional[dict]` calling `AIService` asynchronously
    - Clamp any out-of-range values in the returned suggestion; log WARNING on clamping
    - Return `None` on timeout or API failure; log the failure
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x] 6.2 Integrate `AIAdvisorService` into `LoopService.prepare_next_iteration()`
    - When `config.ai_advisor_enabled` is True and an `AIService` instance is available,
      call `AIAdvisorService.request_suggestion()` after rule-based suggestions are generated
    - Merge AI suggestion as an additional candidate mutation; set `iteration.ai_suggested = True`
    - Fall back to rule-based suggestions only on failure; do not stop the loop
    - _Requirements: 4.4, 4.6_

  - [x] 6.3 Write unit tests for `AIAdvisorService`
    - Test `build_prompt()` includes all required fields
    - Test out-of-range values are clamped and warning is logged
    - Test `None` is returned on simulated API failure
    - _Requirements: 4.3, 4.5, 4.6_

- [x] 7. Checkpoint — Ensure all service-layer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Rebuild the Strategy Lab UI page (`app/ui/pages/loop_page.py`)
  - [x] 8.1 Add Timerange field and preset buttons to the config panel
    - Reuse the preset button pattern from `BacktestPage` ("7d", "14d", "30d", "90d", "120d", "360d")
    - Add a custom timerange `QLineEdit` (format YYYYMMDD-YYYYMMDD)
    - _Requirements: 8.6_

  - [x] 8.2 Add Pairs selector to the config panel
    - Reuse `PairsSelectorDialog` passing `SettingsState` and `favorite_pairs`
    - Display selected pairs count on the button label
    - _Requirements: 8.7, 12.3_

  - [x] 8.3 Add Iteration Mode selector and Hyperopt sub-fields to the config panel
    - `QComboBox` with "Rule-Based Mutations" / "Hyperopt-Guided"
    - Show/hide hyperopt sub-fields (epochs `QSpinBox` 50–2000, spaces multi-select,
      loss function `QComboBox`) based on selection
    - _Requirements: 3.1, 3.4, 8.2_

  - [x] 8.4 Add AI Advisor toggle to the config panel
    - `QCheckBox` "AI Advisor"; disable when no AI model is configured in `AppSettings.ai`
    - Show loading indicator in iteration detail panel while AI request is in flight
    - _Requirements: 4.1, 4.8_

  - [x] 8.5 Add Validation Mode selector with Quick-mode warning label
    - `QComboBox` "Full" / "Quick"
    - Show amber warning label "Quick mode skips walk-forward and stress gates — results may overfit."
      when Quick is selected
    - _Requirements: 8.5_

  - [x] 8.6 Implement gate progress indicator widget
    - Small inline widget showing five gate slots: ○ pending / ⟳ running / ✓ pass / ✗ fail
    - Update each slot in real time as gates complete
    - Display failure reason as tooltip on failed gate slot
    - _Requirements: 5.8, 5.9, 10.3, 10.4_

  - [x] 8.7 Implement live stat cards row
    - Six `_StatCard` widgets: Iteration, Best Profit %, Best Win Rate %, Best Drawdown %,
      Best Sharpe, Best Score
    - Update after each iteration completes
    - _Requirements: 6.4, 10.6_

  - [x] 8.8 Implement iteration history list with expandable rows
    - Each row shows: iteration number, changes ("param: old → new"), gate summary,
      RobustScore, profit %, win rate %, max drawdown %, improvement indicator
    - Color-code rows: green (improvement), amber (no-improvement pass), red (gate fail/error)
    - Clicking a row expands it to show full parameter changes with before/after values,
      diagnosed issues, AI suggestion label (if applicable), and per-gate pass/fail with reasons
    - "Why this change?" tooltip on each parameter change showing the structural pattern
    - Auto-scroll to most recently added row while loop is running
    - Highlight best iteration with a distinct visual indicator when loop completes
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 8.9 Implement best result panel with RobustScore breakdown and delta metrics
    - Show RobustScore component breakdown (profitability, consistency, stability, fragility)
    - Show delta metrics vs baseline: profit Δ, win_rate Δ, drawdown Δ, sharpe Δ
    - _Requirements: 6.3, 6.6_

  - [x] 8.10 Implement Accept / Discard / Rollback controls
    - "Apply Best Result" button: show confirmation dialog with parameter diff before writing
    - "Discard" button: remove sandbox directory, leave live strategy unchanged
    - "Rollback" button: show list of previously accepted states with metrics; restore selected
    - Maintain in-memory session history stack of accepted parameter sets
    - Use `ImproveService.accept_candidate()` / `ImproveService.rollback()` for atomic writes
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

  - [x] 8.11 Implement live status label with all defined phase strings
    - Display: "Idle", "Running backtest (iteration N/M)", "Running OOS gate",
      "Running walk-forward fold K/N", "Running stress test", "Scoring",
      "Waiting for AI Advisor", "Complete"
    - On loop stop, display stop reason: "Targets met", "Max iterations reached",
      "No more suggestions", "Stopped by user", or specific error message
    - _Requirements: 10.5, 10.7_

  - [x] 8.12 Wire subprocess output to `TerminalWidget` for all gate backtests and hyperopt
    - Stream stdout/stderr from every `ProcessService` call to the live output terminal
    - During hyperopt mode, stream hyperopt terminal output in real time
    - _Requirements: 3.7, 10.2_

  - [x] 8.13 Persist and restore all config fields via `StrategyLabPreferences`
    - On start, save current UI values to `AppSettings.strategy_lab` via `SettingsState`
    - On init, restore saved values from `AppSettings.strategy_lab`
    - Disable all config fields while loop is running
    - _Requirements: 8.3, 8.4_

  - [x] 8.14 Handle background running when user navigates away from the tab
    - Do NOT stop the subprocess when the tab loses focus
    - Continue updating internal state; refresh UI when tab regains focus
    - _Requirements: 12.5_

  - [x] 8.15 Implement stale sandbox cleanup on page init
    - Call `ImproveService.cleanup_stale_sandboxes()` via `QTimer.singleShot(0, ...)` on init
    - Delete current iteration sandbox after subprocess terminates when user stops mid-run
    - Clean up sandbox on page close if subprocess is running
    - _Requirements: 11.1, 11.2, 11.3_

- [x] 9. Emit `loop_completed` signal and wire MainWindow integration
  - [x] 9.1 Add `loop_completed = Signal(LoopResult)` to `LoopPage`
    - Emit after loop finishes for any reason
    - _Requirements: 12.2_

  - [x] 9.2 Wire `loop_completed` in `MainWindow.__init__()`
    - Connect `loop_page.loop_completed` to a slot that calls
      `strategy_config_page.refresh()` (or equivalent) so updated params are reflected
    - _Requirements: 12.1, 12.2_

  - [x] 9.3 Update `MainWindow._all_terminals` to include the new loop page terminal
    - Ensure terminal preferences are applied to the Strategy Lab terminal on settings save
    - _Requirements: 12.4_

- [x] 10. Checkpoint — Ensure all tests pass and UI is wired end-to-end
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Gate backtests (OOS, walk-forward folds, stress) reuse `ImproveService.build_candidate_command()`
  with modified timerange/fee flags — no new subprocess infrastructure needed
- The `AIAdvisorService` calls the existing `AIService` already wired in `MainWindow`; pass it
  into `LoopService` via constructor or callback, keeping the service layer free of UI imports
- `StrategyLabPreferences` follows the same Pydantic pattern as `BacktestPreferences`
- All new service methods must be `@staticmethod` where stateless, instance methods where stateful
