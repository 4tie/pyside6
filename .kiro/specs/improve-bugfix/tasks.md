# Implementation Plan

- [x] 1. Write bug condition exploration property tests
  - **Property 1: Bug Condition** - Structural Diagnosis Generates Suggestions
  - **Property 2: Bug Condition** - Rollback Restores Baseline Run Summary
  - **IMPORTANT**: Write these tests BEFORE implementing the fix
  - **GOAL**: Surface counterexamples that demonstrate the bugs exist
  - **Test 1.1**: Create DiagnosisBundle with non-empty structural list and empty issues, call suggest() on unfixed code
    - Expected: suggest() returns empty list (bug confirmed)
    - _Requirements: 1.1, 1.2_
  - **Test 1.2**: Create DiagnosisBundle with both issues and structural non-empty, verify only issues generate suggestions on unfixed code
    - Expected: structural patterns ignored (bug confirmed)
    - _Requirements: 1.1, 1.2_
  - **Test 1.3**: Create StructuralDiagnosis with failure_pattern="entries_too_loose_in_chop", verify no handler exists on unfixed code
    - Expected: no handler found (bug confirmed)
    - _Requirements: 1.3_
  - **Test 1.4**: Perform rollback on unfixed code, assert _baseline_run.summary doesn't match the popped round's summary
    - Expected: _baseline_run.summary is None or wrong (bug confirmed)
    - _Requirements: 1.2, 1.3_
  - **Test 1.5**: Perform rollback, assert _baseline_params, _baseline_run, and _session_baseline are not consistent
    - Expected: state inconsistency (bug confirmed)
    - _Requirements: 1.2, 1.3_

- [x] 2. Implement RuleSuggestionService fix
  - Add structural parameter to suggest() method
  - Add handlers for structural diagnosis patterns
  - Preserve backward compatibility
  - _Bug_Condition: isBugCondition1(input) where input.structural is non-empty and suggest() only processes issues_
  - _Expected_Behavior: suggest() generates at least one suggestion per structural pattern with a handler_
  - _Preservation: Legacy issue suggestions continue to work identically when structural is empty or None_
  - _Requirements: 2.1, 2.2, 3.1, 3.2_

  - [x] 2.1 Update suggest() method signature
    - Add `structural: List[StructuralDiagnosis] = None` as optional parameter
    - Process both issues and structural lists in the same loop or sequentially
    - _Bug_Condition: structural parameter missing from method signature_
    - _Expected_Behavior: method accepts structural parameter and processes it_
    - _Preservation: If structural is None or empty, behavior identical to original_
    - _Requirements: 2.1_

  - [x] 2.2 Add handlers for structural diagnosis patterns
    - Create `_suggest_entries_too_loose_in_chop()` - adjust entry thresholds
    - Create `_suggest_single_regime_dependency()` - add regime filters
    - Create `_suggest_outlier_trade_dependency()` - adjust position sizing
    - Create `_suggest_drawdown_cluster_dependency()` - adjust stoploss or max_open_trades
    - Map pattern names to handlers in the dispatch dictionary
    - _Bug_Condition: No handlers exist for structural pattern types_
    - _Expected_Behavior: Each structural pattern has a corresponding handler that generates appropriate suggestions_
    - _Preservation: Existing issue handlers continue to work unchanged_
    - _Requirements: 2.2_

  - [x] 2.3 Update suggest() to process structural list
    - Iterate through structural list and dispatch to appropriate handlers
    - Combine suggestions from both issues and structural lists
    - _Bug_Condition: structural list is ignored in suggest()_
    - _Expected_Behavior: Both issues and structural lists are processed_
    - _Preservation: If structural is empty, only issues are processed (original behavior)_
    - _Requirements: 2.1, 2.2_

- [x] 3. Implement ImprovePage fix
  - Update _display_issues_and_suggestions() to pass both issues and structural
  - Update _on_rollback() to restore _baseline_run.summary from popped round
  - _Bug_Condition: isBugCondition2(input) where rollback doesn't restore _baseline_run.summary from popped round_
  - _Expected_Behavior: _on_rollback() restores all three state variables atomically: _baseline_params, _baseline_run, and _session_baseline_
  - _Preservation: Normal workflow without rollback continues to work unchanged_
  - _Requirements: 2.3, 2.4, 3.3, 3.4_

  - [x] 3.1 Update _display_issues_and_suggestions() to pass structural
    - Pass both bundle.issues and bundle.structural to RuleSuggestionService.suggest()
    - Update call: `RuleSuggestionService.suggest(issues, params, structural)`
    - _Bug_Condition: Only issues is passed to suggest()_
    - _Expected_Behavior: Both issues and structural are passed to suggest()_
    - _Preservation: If bundle.structural is empty, behavior identical to original_
    - _Requirements: 2.1_

  - [x] 3.2 Add _baseline_run field to ImprovePage.__init__()
    - Initialize `_baseline_run: Optional[BacktestRun] = None` in __init__
    - Determine from codebase whether BacktestRun exists or if we store just the summary
    - _Bug_Condition: _baseline_run field doesn't exist in ImprovePage_
    - _Expected_Behavior: _baseline_run field exists and stores the current baseline run_
    - _Preservation: Existing state variables unchanged_
    - _Requirements: 2.3_

  - [x] 3.3 Update _on_rollback() to restore _baseline_run
    - Restore `_baseline_run.summary` from `last_round.summary`
    - Ensure all three state variables are restored atomically:
      ```python
      self._baseline_params = copy.deepcopy(last_round.params_before)
      self._baseline_run = BacktestRun(summary=last_round.summary)  # or appropriate structure
      self._session_baseline = SessionBaseline(
          params=last_round.params_before,
          summary=last_round.summary,
      )
      ```
    - _Bug_Condition: _baseline_run.summary not restored from popped round_
    - _Expected_Behavior: _baseline_run.summary matches last_round.summary after rollback_
    - _Preservation: Non-rollback operations unchanged_
    - _Requirements: 2.4_

- [x] 4. Write unit tests for fixes
  - Test RuleSuggestionService with structural diagnosis
  - Test rollback state restoration
  - Test backward compatibility
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4_

  - [x] 4.1 Test RuleSuggestionService.suggest() with empty structural list (backward compatibility)
    - Verify legacy issue suggestions work identically before and after fix
    - _Requirements: 3.1, 3.2_

  - [x] 4.2 Test RuleSuggestionService.suggest() with non-empty structural list (new functionality)
    - Verify structural patterns generate suggestions
    - _Requirements: 2.1, 2.2_

  - [x] 4.3 Test RuleSuggestionService.suggest() with both issues and structural lists
    - Verify both lists are processed correctly
    - _Requirements: 2.1, 2.2_

  - [x] 4.4 Test each structural pattern handler generates appropriate suggestions
    - Test entries_too_loose_in_chop, single_regime_dependency, outlier_trade_dependency, drawdown_cluster_dependency
    - _Requirements: 2.2_

  - [x] 4.5 Test rollback restores _baseline_run.summary from popped round
    - Verify _baseline_run.summary matches popped round's summary
    - _Requirements: 2.4_

  - [x] 4.6 Test rollback restores all three state variables consistently
    - Verify _baseline_params, _baseline_run, and _session_baseline are consistent
    - _Requirements: 2.4_

  - [x] 4.7 Test rollback with empty session history (no-op)
    - Verify no crash and state unchanged
    - _Requirements: 3.3_

  - [x] 4.8 Test rollback with single round (restores initial state)
    - Verify state restored to initial values
    - _Requirements: 2.4_

- [x] 5. Write property-based tests
  - Test random DiagnosisBundle combinations
  - Test random rollback scenarios
  - Verify preservation of existing behavior
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4_

  - [x] 5.1 Generate random DiagnosisBundle with varying issues and structural combinations, verify suggestions generated correctly
    - Property: For all bundles where len(structural) > 0, at least one suggestion per structural pattern
    - Property: For all bundles where len(structural) == 0, suggestions identical to original
    - _Requirements: 2.1, 2.2, 3.1, 3.2_

  - [x] 5.2 Generate random structural patterns and verify handlers exist and generate valid suggestions
    - Property: For all structural patterns, handler exists and generates valid ParameterSuggestion
    - _Requirements: 2.2_

  - [x] 5.3 Generate random rollback scenarios with multiple rounds, verify state consistency after each rollback
    - Property: For all rollback operations, _baseline_run.summary == popped_round.summary
    - Property: For all rollback operations, all three state variables are consistent
    - _Requirements: 2.4, 3.4_

  - [x] 5.4 Generate random session histories and verify rollback can traverse entire history correctly
    - Property: For all session histories, rollback can traverse entire history without state corruption
    - _Requirements: 3.4_

- [x] 6. Write integration tests
  - Test full workflow with structural diagnosis
  - Test rollback in multi-round session
  - Test rollback then run candidate
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4_

  - [x] 6.1 Test full Improve workflow with structural diagnosis patterns driving suggestions
    - End-to-end: diagnose() returns bundle with structural, suggest() generates suggestions, UI displays them
    - _Requirements: 2.1, 2.2_

  - [x] 6.2 Test rollback in multi-round session, verify state consistency at each step
    - Multiple rollbacks, verify state consistent after each
    - _Requirements: 2.4, 3.4_

  - [x] 6.3 Test rollback then run candidate, verify candidate starts from correct baseline
    - Rollback to previous state, run candidate, verify candidate uses correct baseline params
    - _Requirements: 2.4_

  - [x] 6.4 Test rollback then accept, verify new round captures correct state
    - Rollback, then accept, verify new round has correct params and summary
    - _Requirements: 2.4_

  - [x] 6.5 Test UI display shows both legacy issues and structural patterns correctly
    - Verify UI renders both issue types without confusion
    - _Requirements: 2.1, 2.2_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
