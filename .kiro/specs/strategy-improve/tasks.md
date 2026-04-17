# Implementation Plan: Strategy Improve

## Overview

Implement the Strategy Improve tab as three vertical slices: (1) shell + baseline loading + diagnosis + suggestions, (2) candidate config + sandboxed backtest, (3) comparison view + accept/reject/rollback. Property-based tests cover all 8 correctness properties from the design.

## Tasks

- [x] 1. Data models and stateless services
  - [x] 1.1 Create `app/core/models/improve_models.py` with `DiagnosedIssue` and `ParameterSuggestion` dataclasses
    - `DiagnosedIssue(issue_id: str, description: str)`
    - `ParameterSuggestion(parameter: str, proposed_value: Any, reason: str, expected_effect: str, is_advisory: bool = False)`
    - Use `@dataclass`; import `Any` from `typing`
    - _Requirements: 4.1, 5.1, 10.1, 10.2_

  - [x] 1.2 Implement `ResultsDiagnosisService` in `app/core/services/results_diagnosis_service.py`
    - Module-level threshold constants: `STOPLOSS_TOO_WIDE = 20.0`, `TRADES_TOO_LOW = 30`, `WEAK_WIN_RATE = 45.0`, `DRAWDOWN_HIGH = 30.0`, `POOR_PAIR_CONCENTRATION = 3`
    - `@staticmethod diagnose(summary: BacktestSummary) -> List[DiagnosedIssue]` evaluating all 6 rules
    - No UI imports; logger `get_logger("services.results_diagnosis")`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 10.1_

  - [x] 1.3 Write property test for `ResultsDiagnosisService` (Property 1)
    - **Property 1: Diagnosis threshold rules are exhaustive and correct**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7**
    - Use `@given(st.builds(BacktestSummary, ...))` with `max_examples=200`
    - Assert each issue ID present iff its condition holds (both sides of every threshold)
    - File: `tests/core/services/test_results_diagnosis_service.py`

  - [x] 1.4 Implement `RuleSuggestionService` in `app/core/services/rule_suggestion_service.py`
    - `@staticmethod suggest(issues: List[DiagnosedIssue], params: dict) -> List[ParameterSuggestion]`
    - Handle all 6 issue types per design: stoploss delta −0.02, max_open_trades +1 capped at 10, ROI smallest-key −0.005, max_open_trades −1 min 1, advisory for poor_pair_concentration, stoploss delta −0.03 for negative_profit
    - No UI imports; logger `get_logger("services.rule_suggestion")`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 10.2_

  - [x] 1.5 Write property test for `RuleSuggestionService` (Property 2)
    - **Property 2: Suggestion rules produce correct parameter mutations**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.7**
    - Use `@given(params=st.fixed_dictionaries({...}), issues=st.lists(st.sampled_from([...]), min_size=1))`
    - Verify each suggestion's `proposed_value` matches the rule formula for its issue type
    - File: `tests/core/services/test_rule_suggestion_service.py`

- [x] 2. Checkpoint — run `pytest tests/core/services/test_results_diagnosis_service.py tests/core/services/test_rule_suggestion_service.py --tb=short` and confirm all tests pass

- [x] 3. `ImproveService` — data loading and file I/O
  - [x] 3.1 Create `app/core/services/improve_service.py` skeleton with constructor and data-loading methods
    - `__init__(self, settings_service: SettingsService, backtest_service: BacktestService)`
    - `get_available_strategies() -> List[str]` — delegates to `backtest_service.get_available_strategies()`
    - `get_strategy_runs(strategy: str) -> List[dict]` — calls `IndexStore.get_strategy_runs(backtest_results_dir, strategy)`
    - `load_baseline(run_dir: Path) -> BacktestResults` — calls `RunStore.load_run(run_dir)`
    - `load_baseline_params(run_dir: Path) -> dict` — reads `params.json` directly; returns `{}` with warning if missing
    - Logger `get_logger("services.improve")`; no UI imports
    - _Requirements: 2.1, 2.2, 3.1, 3.5, 10.3, 10.5_

  - [x] 3.2 Write property test for `load_baseline_params` round-trip (Property 3)
    - **Property 3: BaselineParams round-trip from params.json**
    - **Validates: Requirements 3.5**
    - Use `@given(params=st.fixed_dictionaries({...}))` with `tmp_path` fixture
    - Write params to `tmp_path / "params.json"`, load via `ImproveService.load_baseline_params(tmp_path)`, assert equality
    - File: `tests/core/services/test_improve_service.py`

  - [x] 3.3 Add sandbox and command-building methods to `ImproveService`
    - `prepare_sandbox(strategy_name: str, candidate_config: dict) -> Path`
      - Creates `{user_data_path}/strategies/_improve_sandbox/{strategy_name}_{YYYYMMDD_HHMMSS}/`
      - Copies `{strategies_dir}/{strategy_name}.py` into sandbox dir
      - Writes `{strategy_name}.json` from `candidate_config` into sandbox dir
      - Raises `FileNotFoundError` if strategy `.py` not found
    - `build_candidate_command(strategy_name: str, baseline: BacktestResults, sandbox_dir: Path) -> tuple[BacktestRunCommand, Path]`
      - Derives `export_dir = {user_data_path}/backtest_results/_improve/{strategy_name}_{timestamp}/`
      - Calls `backtest_service.build_command()` with `extra_flags=["--strategy-path", str(sandbox_dir), "--backtest-directory", str(export_dir)]`
      - Returns `(command, export_dir)` so `ImprovePage` can store `_export_dir` alongside the command
    - `ImprovePage` stores both: `_sandbox_dir` from `prepare_sandbox()` and `_export_dir` from `build_candidate_command()`
    - _Requirements: 7.1, 7.2, 10.3_

  - [x] 3.4 Add zip resolution, accept, reject, and rollback methods to `ImproveService`
    - `resolve_candidate_zip(export_dir: Path) -> Optional[Path]` — returns single `.zip` from `export_dir`; falls back to mtime scan of `backtest_results/` if empty
    - `parse_candidate_run(export_dir: Path) -> BacktestResults` — calls `resolve_candidate_zip` then `parse_backtest_zip()`
    - `accept_candidate(strategy_name: str, candidate_config: dict) -> None` — atomic write (`.tmp` → `os.replace()`) of `{strategies_dir}/{strategy_name}.json`
    - `reject_candidate(sandbox_dir: Path) -> None` — deletes sandbox dir contents; does not touch main param file
    - `rollback(strategy_name: str, baseline_params: dict) -> None` — atomic write of `baseline_params` to `{strategies_dir}/{strategy_name}.json`
    - _Requirements: 7.5, 9.1, 9.3, 9.6, 10.3_

  - [x] 3.5 Write unit tests for `ImproveService` file I/O methods
    - `test_load_baseline_params`: verify dict matches file contents; verify `{}` returned with warning when `params.json` missing
    - `test_prepare_sandbox`: verify directory structure and file contents using `tmp_path`
    - `test_accept_candidate_atomic_write`: verify `.tmp` → `os.replace()` pattern; assert final file matches candidate config
    - `test_reject_candidate_cleanup`: verify sandbox files deleted; assert main param file untouched
    - `test_rollback`: verify correct snapshot written atomically
    - File: `tests/core/services/test_improve_service.py`

- [x] 4. Checkpoint — run `pytest tests/core/services/test_improve_service.py --tb=short` and confirm all tests pass

- [x] 5. Slice 1 — `ImprovePage` shell: strategy/run selector, baseline summary, diagnosis, suggestions
  - [x] 5.1 Create `app/ui/pages/improve_page.py` with `ImprovePage(QWidget)` shell
    - Constructor: `__init__(self, settings_state: SettingsState, parent=None)`
    - Instantiate `ImproveService`, `ResultsDiagnosisService`, `RuleSuggestionService` internally
    - Internal state: `_baseline_run`, `_baseline_params`, `_candidate_config`, `_candidate_run`, `_baseline_history`, `_sandbox_dir`, `_run_started_at`
    - Logger `get_logger("ui.improve_page")`
    - Connect `settings_state.settings_changed` → `_refresh_strategies()`
    - _Requirements: 1.1, 1.2, 1.3, 10.4, 10.5_

  - [x] 5.2 Implement strategy selector, run selector, and "Load Latest" button
    - Strategy combo populated from `ImproveService.get_available_strategies()`
    - Run combo populated from `ImproveService.get_strategy_runs(strategy)` showing run ID, profit %, trade count, saved timestamp
    - "Load Latest" button selects most recent run entry in combo
    - When strategy changes, repopulate run combo
    - If no runs: show "No saved runs found for this strategy" and disable "Analyze" button
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 5.3 Write property test for run selector label format (Property 8)
    - **Property 8: Run selector entries contain required display fields**
    - **Validates: Requirements 2.2**
    - Extract `_build_run_label(run: dict) -> str` as a pure function in `improve_page.py`
    - Use `@given(runs=st.lists(st.fixed_dictionaries({...}), min_size=0, max_size=20))`
    - Assert `len(labels) == len(runs)` and each label contains run_id, profit_total_pct, trades_count, saved_at substring
    - File: `tests/ui/pages/test_improve_page.py`

  - [x] 5.4 Implement "Analyze" button: load baseline, run diagnosis, display issues and suggestions
    - On click: call `ImproveService.load_baseline()` and `load_baseline_params()`; disable button during load
    - On success: display summary metrics (strategy, timeframe, total trades, win rate, total profit, max drawdown, Sharpe, date range)
    - Call `ResultsDiagnosisService.diagnose(summary)` → populate "Detected Issues" panel
    - Call `RuleSuggestionService.suggest(issues, baseline_params)` → populate "Suggested Actions" panel with parameter, proposed value (or "Advisory"), reason, expected effect, and "Apply" button per suggestion
    - If no issues: show "No issues detected — results look healthy"
    - If no suggestions: show "No suggestions available"
    - On `FileNotFoundError` or `ValueError`: display error message; do not update `_baseline_run`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.8, 4.9, 5.8, 5.9_

- [x] 6. Slice 2 — candidate config, diff preview, and candidate backtest execution
  - [x] 6.1 Implement "Apply" button logic and `CandidateConfig` diff preview
    - On "Apply": merge suggestion into `_candidate_config`; skip diff entry for advisory suggestions but mark as applied in UI
    - `compute_diff(baseline, candidate)` is top-level-keys only in this version — nested dicts (e.g. `buy_params`, `sell_params`) are compared as whole values, not field-by-field
    - "Candidate Preview" panel shows key-value diff: only top-level keys where `_candidate_config[k] != _baseline_params[k]`
    - Enable "Run Backtest on Candidate" when diff is non-empty
    - "Reset Candidate" button deep-copies `_baseline_params` back into `_candidate_config` and clears diff panel
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 6.2 Write property test for candidate diff exactness (Property 4)
    - **Property 4: CandidateConfig diff contains exactly the changed keys**
    - **Validates: Requirements 6.1, 6.2**
    - Extract `compute_diff(baseline: dict, candidate: dict) -> dict` as a pure module-level function in `improve_page.py`
    - Use `@given(baseline=..., suggestions=st.lists(...))` with `max_examples=200`
    - Assert `set(diff.keys()) == {s.parameter for s in suggestions if not s.is_advisory}`
    - File: `tests/ui/pages/test_improve_page.py`

  - [x] 6.3 Write property test for reset candidate (Property 5)
    - **Property 5: Reset candidate restores to baseline**
    - **Validates: Requirements 6.4**
    - Use `@given(baseline=..., suggestions=st.lists(...))` with `max_examples=100`
    - Apply suggestions to a copy of baseline, then reset; assert result equals original baseline
    - File: `tests/ui/pages/test_improve_page.py`

  - [x] 6.4 Implement "Run Backtest on Candidate" button and subprocess lifecycle
    - On click: call `ImproveService.prepare_sandbox(strategy_name, _candidate_config)` → store `_sandbox_dir`
    - Call `ImproveService.build_candidate_command(strategy_name, _baseline_run, _sandbox_dir)` → unpack `(command, export_dir)`; store `_export_dir = export_dir`
    - Record `_run_started_at = time.time()`; disable "Run Backtest on Candidate"; show "Stop" button
    - Call `ProcessService.execute_command()` streaming stdout/stderr to `TerminalWidget` inside Candidate Preview panel
    - On `FileNotFoundError` from `prepare_sandbox`: display error in UI; do not start process
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 6.5 Implement `on_finished` handler for candidate backtest
    - On exit code 0: call `ImproveService.parse_candidate_run(self._export_dir)` → store as `_candidate_run`; trigger comparison view update
    - `ImprovePage` SHALL NOT call `parse_backtest_zip()` directly — all candidate parsing is delegated to `ImproveService.parse_candidate_run()`
    - On non-zero exit: display "Candidate backtest failed — see terminal output"; do not update `_candidate_run`
    - Re-enable "Run Backtest on Candidate"; hide "Stop" button
    - _Requirements: 7.5, 7.6_

- [x] 7. Checkpoint — run `pytest tests/ --tb=short` and confirm all tests pass

- [x] 8. Slice 3 — comparison view, accept/reject/rollback
  - [x] 8.1 Implement comparison table widget inline in `ImprovePage`
    - Shown only when both `_baseline_run` and `_candidate_run` are available
    - One row per metric: total trades, win rate (%), total profit (%), max drawdown (%), Sharpe ratio, profit factor, expectancy
    - Two columns: "Baseline" and "Candidate"
    - Green cell when candidate is strictly better; red when strictly worse; uncolored when equal
    - "Better" direction: higher for win_rate, total_profit, sharpe_ratio, profit_factor, expectancy, total_trades; lower for max_drawdown
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 8.2 Write property test for comparison highlight logic (Property 6)
    - **Property 6: Comparison metric direction determines highlight color**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4**
    - Extract `compute_highlight(metric: str, baseline_val: float, candidate_val: float) -> Optional[str]` as a pure function returning `"green"`, `"red"`, or `None`
    - Use `@given(baseline_val=st.floats(...), candidate_val=st.floats(...), metric=st.sampled_from(METRICS))` with `max_examples=200`
    - Assert green iff strictly better, red iff strictly worse, None iff equal
    - File: `tests/ui/pages/test_improve_page.py`

  - [x] 8.3 Implement "Accept" and "Reject" buttons
    - "Accept":
      - Call `ImproveService.accept_candidate(strategy_name, _candidate_config)`
      - Update all state atomically before any UI refresh: push `deepcopy(_baseline_params)` onto `_baseline_history`, set `_baseline_params = deepcopy(_candidate_config)`, set `_baseline_run = _candidate_run`, set `_candidate_run = None`, reset `_candidate_config = deepcopy(_baseline_params)`
      - Trigger a single UI refresh after all state is updated to avoid partial renders
      - Clear comparison view; display "Candidate accepted — strategy parameters updated"
      - On `OSError`: display error dialog; do not update any state
    - "Reject":
      - Call `ImproveService.reject_candidate(_sandbox_dir)`
      - Set `_candidate_run = None`; clear comparison view
      - Reset `_candidate_config = deepcopy(_baseline_params)`
      - `_baseline_params` and `_baseline_run` remain unchanged
    - Show "Accept" and "Reject" only when both `_baseline_run` and `_candidate_run` are available
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 8.4 Implement "Rollback" button and `_baseline_history` stack
    - Show "Rollback" button only when `_baseline_history` is non-empty
    - On click:
      - Call `ImproveService.rollback(strategy_name, _baseline_history[-1])`
      - Pop snapshot from `_baseline_history`; set `_baseline_params = popped_snapshot`
      - Set `_candidate_run = None`; clear comparison view
      - Reset `_candidate_config = deepcopy(_baseline_params)`
      - Display "Rolled back to previous baseline parameters"
      - On `OSError`: display error dialog; do not modify state
    - `_baseline_history` grows by 1 on each Accept, shrinks by 1 on each Rollback
    - _Requirements: 9.5, 9.6, 9.7, 9.8_

  - [x] 8.5 Write property test for baseline history stack invariant (Property 7)
    - **Property 7: Baseline history stack invariant**
    - **Validates: Requirements 9.8**
    - Extract `simulate_history(ops: List[str]) -> Tuple[List[dict], dict]` as a pure function
    - Use `@given(ops=st.lists(st.sampled_from(["accept", "rollback"]), min_size=1, max_size=20))` with `max_examples=100`
    - Assert history length increases by 1 on accept, decreases by 1 on rollback (when non-empty), and restored value equals most recently pushed snapshot
    - File: `tests/ui/pages/test_improve_page.py`

- [x] 9. Wire `ImprovePage` into `MainWindow`
  - Modify `app/ui/main_window.py`: import `ImprovePage`; instantiate `self.improve_page = ImprovePage(self.settings_state)`; insert tab after Backtest and before Optimize using `self.tabs.insertTab()`
  - Add `self.improve_page.terminal` (the candidate terminal widget) to `_all_terminals` so terminal preferences apply
  - _Requirements: 1.1, 1.2_

- [x] 10. Final checkpoint — run `pytest --tb=short` and confirm all tests pass; verify that Improve tab appears immediately after Backtest and immediately before Optimize, preserving the rest of the current tab order

## Notes

- Tasks marked with `*` are optional property-based tests — they validate universal correctness properties and are recommended but can be deferred for a faster MVP. Unit tests in Task 3.5 are mandatory.
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation before moving to the next slice
- Property tests validate universal correctness properties; unit tests validate specific examples and edge cases
- Pure helper functions (`_build_run_label`, `compute_diff`, `compute_highlight`, `simulate_history`) should be extracted at module level to make them directly testable without instantiating the full `ImprovePage`
- `compute_diff` is top-level keys only — nested dicts (`buy_params`, `sell_params`) are compared as whole values; nested field diffing is deferred to a future slice
- `ImprovePage` stores `_export_dir: Optional[Path]` set from the return value of `build_candidate_command()` and used in `on_finished` to call `ImproveService.parse_candidate_run(_export_dir)`
