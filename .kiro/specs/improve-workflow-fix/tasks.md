# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Flat Format Written by ImproveService
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior — it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate that `prepare_sandbox`, `accept_candidate`, and `rollback` write the flat `params.json` format instead of the freqtrade nested format
  - **Scoped PBT Approach**: Scope the property to the concrete failing cases — a flat params dict with `stoploss`, `minimal_roi`, `buy_params`, `sell_params`, `max_open_trades` — and assert the written JSON contains `strategy_name`, `ft_stratparam_v`, and nested `params` keys
  - Write a property-based test using Hypothesis that generates arbitrary flat params dicts (varying `stoploss` scalar, `max_open_trades` scalar, `minimal_roi` dict, `buy_params` dict, `sell_params` dict) and for each:
    - Calls `prepare_sandbox(strategy_name, flat_params)`, reads the written JSON, asserts `"strategy_name" in result` — FAILS on unfixed code
    - Calls `accept_candidate(strategy_name, flat_params)`, reads the written JSON, asserts `result["params"]["stoploss"]["stoploss"] == flat_params["stoploss"]` — FAILS on unfixed code
    - Calls `rollback(strategy_name, flat_params)`, reads the written JSON, asserts `"ft_stratparam_v" in result` — FAILS on unfixed code
  - Also test `load_baseline_params(run_dir_without_params, "MultiMeee")` returns non-empty — FAILS on unfixed code (no fallback exists)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct — it proves the bug exists)
  - Document counterexamples found (e.g. written JSON contains `{"stoploss": -0.245, "minimal_roi": {...}}` instead of `{"strategy_name": "MultiMeee", "params": {...}, "ft_stratparam_v": 1}`)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.6_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Behaviors Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs (cases where the bug condition does NOT hold):
    - Observe: `load_baseline_params(run_dir_with_params_json)` returns the parsed flat dict from `params.json` unchanged
    - Observe: `prepare_sandbox` creates a timestamped directory under `_improve_sandbox/` and copies the `.py` file
    - Observe: `accept_candidate` and `rollback` use the `.tmp` → `os.replace()` atomic write pattern
    - Observe: `ResultsDiagnosisService.diagnose()` fires all six existing rules for their threshold conditions
    - Observe: `RuleSuggestionService.suggest()` returns the same suggestions for all six existing issue types
  - Write property-based tests using Hypothesis capturing these observed behaviors:
    - **Trailing preservation**: Generate random `trailing` dicts embedded in a live strategy JSON; assert `_build_freqtrade_params_file(strategy_name, flat_params)` preserves `result["params"]["trailing"]` unchanged for all generated inputs (from Preservation Requirements in design)
    - **`load_baseline_params` primary path**: For any valid `params.json` content, assert the returned dict equals the parsed file content without consulting the live strategy JSON
    - **Diagnosis rules unchanged**: For any `BacktestSummary` where existing thresholds are met, assert all six existing rules still fire with the same `issue_id` and description format
    - **Suggestion handlers unchanged**: For any of the six existing `issue_id` values, assert `suggest()` returns a `ParameterSuggestion` with the same `parameter`, `proposed_value`, and `is_advisory` as before
  - Verify all tests PASS on UNFIXED code (confirms baseline behavior to preserve)
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

- [x] 3. Fix flat-format write bug and related workflow gaps

  - [x] 3.1 Add `_build_freqtrade_params_file` helper to `ImproveService`
    - Add `from datetime import datetime, timezone` import (update existing `from datetime import datetime` import)
    - Add private method `_build_freqtrade_params_file(self, strategy_name: str, flat_params: dict) -> dict` to `app/core/services/improve_service.py`
    - Read live strategy JSON at `{user_data_path}/strategies/{strategy_name}.json` as base; fall back to `{"strategy_name": strategy_name, "params": {}, "ft_stratparam_v": 1}` on missing file or `JSONDecodeError`
    - Copy `base.get("params", {})` into `ft_params`
    - Map flat keys to nested keys: `stoploss` → `ft_params["stoploss"]["stoploss"]`, `max_open_trades` → `ft_params["max_open_trades"]["max_open_trades"]`, `minimal_roi` → `ft_params["roi"]`, `buy_params` → `ft_params["buy"]`, `sell_params` → `ft_params["sell"]` — only when the key is present and not `None`/empty
    - Set `base["params"] = ft_params`, `base["strategy_name"] = strategy_name`, `base["ft_stratparam_v"] = 1`, `base["export_time"] = datetime.now(timezone.utc).isoformat()`
    - Return `base`
    - _Bug_Condition: isBugCondition(written_file_content) where "strategy_name" NOT IN written_file_content OR "params" NOT IN written_file_content OR "ft_stratparam_v" NOT IN written_file_content_
    - _Expected_Behavior: result["strategy_name"] == strategy_name AND result["ft_stratparam_v"] == 1 AND result["params"]["stoploss"]["stoploss"] == flat_params["stoploss"] AND result["params"]["roi"] == flat_params["minimal_roi"]_
    - _Preservation: trailing block in live JSON preserved in result["params"]["trailing"]; atomic write pattern unchanged in callers_
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.2 Update `prepare_sandbox`, `accept_candidate`, and `rollback` to use the helper
    - In `prepare_sandbox`: replace `json.dumps(candidate_config, indent=2)` with `json.dumps(self._build_freqtrade_params_file(strategy_name, candidate_config), indent=2)`
    - In `accept_candidate`: replace `json.dumps(candidate_config, indent=2)` with `json.dumps(self._build_freqtrade_params_file(strategy_name, candidate_config), indent=2)`
    - In `rollback`: replace `json.dumps(baseline_params, indent=2)` with `json.dumps(self._build_freqtrade_params_file(strategy_name, baseline_params), indent=2)`
    - Verify `prepare_sandbox` still creates the timestamped sandbox directory and copies the `.py` file (no structural change)
    - Verify `accept_candidate` and `rollback` still use the `.tmp` → `os.replace()` atomic write pattern (no structural change)
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3_

  - [x] 3.3 Update `load_baseline_params` to add `strategy_name` fallback
    - Add `strategy_name: str = ""` parameter to `load_baseline_params` signature in `app/core/services/improve_service.py`
    - After the existing early-return for missing `params.json`, add a fallback block: if `strategy_name` is provided, read `{user_data_path}/strategies/{strategy_name}.json`; extract flat params using reverse key mapping (`params["stoploss"]["stoploss"]` → `stoploss`, `params["max_open_trades"]["max_open_trades"]` → `max_open_trades`, `params["roi"]` → `minimal_roi`, `params["buy"]` → `buy_params`, `params["sell"]` → `sell_params`); return the flat dict; if live JSON also missing, return `{}`
    - Ensure the primary path (valid `params.json` present) is completely unchanged
    - _Requirements: 2.6, 3.4_

  - [x] 3.4 Update `improve_page.py` call sites for `load_baseline_params`
    - Find all calls to `self._improve_service.load_baseline_params(...)` in `app/ui/pages/improve_page.py`
    - Pass `strategy_name` as the second argument at each call site
    - _Requirements: 2.6_

  - [x] 3.5 Improve error message specificity in `_on_candidate_finished`
    - In the `else` branch (non-zero exit code) of `_on_candidate_finished` in `app/ui/pages/improve_page.py`, call `self._terminal.get_output()` to retrieve terminal text
    - Scan for known freqtrade error phrases: `"Invalid parameter file"`, `"Strategy not found"`, `"No data found"`, `"Configuration error"`, `"No pairs defined"`
    - If a phrase is matched, append it in parentheses to the status message (e.g. `"❌  Candidate backtest failed (Invalid parameter file)"`)
    - Fall back to the existing generic message if no phrase matches
    - _Requirements: 2.4, 3.8_

  - [x] 3.6 Add sandbox cleanup after successful accept in `_on_accept`
    - In `_on_accept` in `app/ui/pages/improve_page.py`, after the successful `accept_candidate` call and before updating state, add:
      ```python
      if self._sandbox_dir is not None:
          self._improve_service.reject_candidate(self._sandbox_dir)
          self._sandbox_dir = None
      ```
    - _Requirements: 2.5_

  - [x] 3.7 Add `profit_factor_low` and `expectancy_negative` diagnosis rules
    - Add threshold constants to `app/core/services/results_diagnosis_service.py`: `PROFIT_FACTOR_LOW: float = 1.0` and `EXPECTANCY_NEGATIVE: float = 0.0`
    - Add two rules at the end of `diagnose()` (after existing rules):
      - If `0.0 < summary.profit_factor < PROFIT_FACTOR_LOW`: append `DiagnosedIssue(issue_id="profit_factor_low", description=f"Profit factor {summary.profit_factor:.2f} is below 1.0 — losses exceed gains over the backtest period.")`
      - If `summary.expectancy < EXPECTANCY_NEGATIVE`: append `DiagnosedIssue(issue_id="expectancy_negative", description=f"Expectancy {summary.expectancy:.4f} is negative — the average trade loses money.")`
    - Verify all six existing rules are structurally unchanged
    - _Requirements: 2.7, 2.8, 3.5_

  - [x] 3.8 Add `profit_factor_low` and `expectancy_negative` suggestion handlers
    - Add two entries to the `handlers` dict in `_handle_issue` in `app/core/services/rule_suggestion_service.py`: `"profit_factor_low": RuleSuggestionService._suggest_profit_factor_low` and `"expectancy_negative": RuleSuggestionService._suggest_expectancy_negative`
    - Add static method `_suggest_profit_factor_low(_params: dict) -> ParameterSuggestion` returning `ParameterSuggestion(parameter="entry_conditions", proposed_value=None, reason="Profit factor below 1.0 — losses exceed gains", expected_effect="Review entry/exit conditions to improve trade quality", is_advisory=True)`
    - Add static method `_suggest_expectancy_negative(_params: dict) -> ParameterSuggestion` returning `ParameterSuggestion(parameter="entry_filters", proposed_value=None, reason="Negative expectancy — average trade loses money", expected_effect="Consider tightening entry filters to improve trade selectivity", is_advisory=True)`
    - Verify all six existing handlers are structurally unchanged
    - _Requirements: 2.9, 2.10, 3.6_

  - [x] 3.9 Add `profit_factor_low` and `expectancy_negative` severity colors to `IssueBadge`
    - Add two entries to `IssueBadge.SEVERITY_COLORS` in `app/ui/pages/improve_page.py`: `"profit_factor_low": (_C_ORANGE, "🟠")` and `"expectancy_negative": (_C_ORANGE, "🟠")`
    - Verify all existing entries in `SEVERITY_COLORS` are unchanged
    - _Requirements: 2.11, 2.12, 3.7_

  - [x] 3.10 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Freqtrade Format Round-Trip
    - **IMPORTANT**: Re-run the SAME test from task 1 — do NOT write a new test
    - The test from task 1 encodes the expected behavior (nested format with `strategy_name`, `ft_stratparam_v`, `params` sub-object)
    - When this test passes, it confirms the expected behavior is satisfied for all generated flat params inputs
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.6_

  - [x] 3.11 Verify preservation tests still pass
    - **Property 2: Preservation** - Existing Behaviors Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm trailing block preservation, `load_baseline_params` primary path, existing diagnosis rules, and existing suggestion handlers all behave identically to the unfixed baseline

- [x] 4. Checkpoint — Ensure all tests pass
  - Run the full test suite: `pytest --tb=short`
  - Ensure all tests pass; ask the user if questions arise
  - Verify no ruff lint errors: `ruff check app/core/services/improve_service.py app/core/services/results_diagnosis_service.py app/core/services/rule_suggestion_service.py app/ui/pages/improve_page.py`
