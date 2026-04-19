# Improve Bugfix Design

## Overview

This document describes the fix for two bugs in the Improve feature:

1. **Bug 1**: `RuleSuggestionService` only processes the legacy `issues` list and ignores the `structural` list from `DiagnosisBundle`, so structural diagnosis patterns don't drive suggestions.

2. **Bug 2**: Rollback in `ImprovePage._on_rollback()` restores `params_before` and updates `_session_baseline`, but doesn't restore `_baseline_run` to the correct summary from the accepted run, leaving state inconsistent.

The fix ensures both legacy issues and structural patterns drive suggestions, and that rollback restores all three state variables atomically: `_baseline_params`, `_baseline_run`, and `_session_baseline`.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug:
  - Bug 1: `structural` list in `DiagnosisBundle` is non-empty and `RuleSuggestionService.suggest()` is called with only `issues`
  - Bug 2: Rollback occurs and `_baseline_run` is not restored from the popped `SessionRound.summary`
- **Property (P)**: The desired behavior when bug condition holds:
  - Bug 1: `RuleSuggestionService.suggest()` must generate suggestions for both `issues` and `structural` patterns
  - Bug 2: After rollback, `_baseline_run.summary` must match the summary stored in the rollback target `SessionRound`
- **Preservation**: Existing behavior that must remain unchanged:
  - Legacy issue suggestions continue to work
  - Mouse clicks and UI interactions continue to work
  - Session history rollback functionality is preserved
- **DiagnosisBundle**: Output bundle from `ResultsDiagnosisService.diagnose()` containing both `issues` (legacy) and `structural` (pattern-based) lists
- **StructuralDiagnosis**: Pattern-based root-cause diagnosis with fields: `failure_pattern`, `evidence`, `root_cause`, `mutation_direction`, `confidence`, `severity`
- **SessionRound**: One entry in the session history stack containing `params_before`, `params_after`, `summary`, and `round_number`

## Bug Details

### Bug Condition

**Bug 1**: `RuleSuggestionService.suggest()` only accepts `issues` parameter and ignores `structural` list from `DiagnosisBundle`.

**Formal Specification:**
```
FUNCTION isBugCondition1(input)
  INPUT: input of type Tuple[List[DiagnosedIssue], List[StructuralDiagnosis]]
  OUTPUT: boolean
  
  issues, structural := input
  RETURN len(structural) > 0
         AND RuleSuggestionService.suggest(issues, params) does NOT process structural patterns
END FUNCTION
```

**Bug 2**: Rollback doesn't restore `_baseline_run` from the popped `SessionRound.summary`.

**Formal Specification:**
```
FUNCTION isBugCondition2(input)
  INPUT: input of type SessionRound (the popped round)
  OUTPUT: boolean
  
  popped_round := input
  RETURN _baseline_run.summary != popped_round.summary
         OR _baseline_run is not restored after rollback
END FUNCTION
```

### Examples

**Bug 1 Example:**
- Input: `DiagnosisBundle` with `issues=[]` and `structural=[StructuralDiagnosis(failure_pattern="entries_too_loose_in_chop", ...)]`
- Current behavior: `RuleSuggestionService.suggest(issues, params)` returns no suggestions because `issues` is empty
- Expected behavior: Should generate suggestions for structural patterns like "entries_too_loose_in_chop"

**Bug 2 Example:**
- Input: Rollback from round 3 to round 2, where round 2 has `summary=BacktestSummary(...)`
- Current behavior: `_baseline_run` is cleared (`None`) after rollback
- Expected behavior: `_baseline_run.summary` should match round 2's summary

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Legacy issue suggestions (e.g., "stoploss_too_wide", "trades_too_low") must continue to work exactly as before
- Mouse clicks on suggestion rows must continue to work
- UI display of issues and suggestions must remain unchanged
- Session history rollback functionality must continue to work
- All existing state variables (`_baseline_params`, `_session_baseline`) must be preserved

**Scope:**
All inputs that do NOT involve structural diagnosis or rollback must be completely unaffected by this fix. This includes:
- Calls to `RuleSuggestionService.suggest()` with empty `structural` list
- All UI interactions except rollback
- All other state management operations

## Hypothesized Root Cause

Based on the bug description, the most likely issues are:

1. **Missing structural parameter in RuleSuggestionService.suggest()**: The method signature only accepts `issues` and doesn't have a `structural` parameter, so structural diagnoses are never processed.

2. **Missing pattern handlers for structural diagnoses**: Even if `structural` were passed, there are no handlers for structural pattern types like "entries_too_loose_in_chop", "single_regime_dependency", etc.

3. **Incomplete rollback state restoration**: The `_on_rollback()` method updates `_baseline_params` and `_session_baseline` but doesn't restore `_baseline_run.summary` from the popped `SessionRound.summary`.

4. **Missing `_baseline_run` field**: The `ImprovePage` class may not have a `_baseline_run` field that stores the summary separately from `_session_baseline`.

## Correctness Properties

Property 1: Bug Condition - Structural Diagnosis Generates Suggestions

_For any_ `DiagnosisBundle` where `structural` list is non-empty, the fixed `RuleSuggestionService.suggest()` method SHALL generate at least one `ParameterSuggestion` for each structural pattern that has a corresponding handler.

**Validates: Requirements 2.1, 2.2**

Property 2: Bug Condition - Rollback Restores Baseline Run

_For any_ rollback operation where a `SessionRound` is popped from history, the fixed `_on_rollback()` method SHALL ensure `_baseline_run.summary` matches the `summary` field of the popped `SessionRound`.

**Validates: Requirements 2.3, 2.4**

Property 3: Preservation - Legacy Issue Suggestions

_For any_ `DiagnosisBundle` where `structural` list is empty, the fixed `RuleSuggestionService.suggest()` method SHALL produce exactly the same suggestions as the original implementation, preserving all legacy issue handling.

**Validates: Requirements 3.1, 3.2**

Property 4: Preservation - Rollback State Consistency

_For any_ rollback operation, the fixed `_on_rollback()` method SHALL restore all three state variables atomically: `_baseline_params`, `_baseline_run`, and `_session_baseline`, preserving the exact state from the rollback target round.

**Validates: Requirements 3.3, 3.4**

## Fix Implementation

### Changes Required

**File**: `app/core/services/rule_suggestion_service.py`

**Function**: `RuleSuggestionService.suggest()`

**Specific Changes**:

1. **Add structural parameter to suggest() method**:
   - Update method signature to accept `structural: List[StructuralDiagnosis] = None` as optional parameter
   - Process both `issues` and `structural` lists in the same loop or sequentially

2. **Add handlers for structural diagnosis patterns**:
   - Create handler methods for common structural patterns:
     - `_suggest_entries_too_loose_in_chop()` - adjust entry thresholds
     - `_suggest_single_regime_dependency()` - add regime filters
     - `_suggest_outlier_trade_dependency()` - adjust position sizing
     - `_suggest_drawdown_cluster_dependency()` - adjust stoploss or max_open_trades
   - Map pattern names to handlers in the dispatch dictionary

3. **Preserve backward compatibility**:
   - Make `structural` parameter optional with default `None`
   - If `structural` is `None` or empty, behavior is identical to original

**File**: `app/ui/pages/improve_page.py`

**Functions**: `_display_issues_and_suggestions()`, `_on_rollback()`

**Specific Changes**:

1. **Update _display_issues_and_suggestions()**:
   - Pass both `bundle.issues` and `bundle.structural` to `RuleSuggestionService.suggest()`
   - Update call: `RuleSuggestionService.suggest(issues, params, structural)`

2. **Update _on_rollback()**:
   - Add `_baseline_run` field to `ImprovePage.__init__()` if not already present
   - In rollback, restore `_baseline_run.summary` from `last_round.summary`
   - Ensure all three state variables are restored atomically:
     ```python
     self._baseline_params = copy.deepcopy(last_round.params_before)
     self._baseline_run = BacktestRun(summary=last_round.summary)  # or appropriate structure
     self._session_baseline = SessionBaseline(
         params=last_round.params_before,
         summary=last_round.summary,
     )
     ```

3. **Add BacktestRun wrapper if needed**:
   - If `_baseline_run` doesn't exist, create a simple wrapper class or use existing `BacktestSummary` directly
   - Determine from codebase whether `BacktestRun` exists or if we store just the summary

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bugs on unfixed code, then verify the fixes work correctly and preserve existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bugs BEFORE implementing the fix. Confirm or refute the root cause analysis.

**Test Plan**: Write tests that simulate the buggy conditions and assert failures on unfixed code.

**Test Cases**:

**Bug 1 Tests**:
1. **Structural Diagnosis Test**: Create `DiagnosisBundle` with non-empty `structural` list and empty `issues`, call `suggest()` on unfixed code (will fail - no suggestions generated)
2. **Mixed Issues Test**: Create `DiagnosisBundle` with both `issues` and `structural` non-empty, verify only `issues` generate suggestions on unfixed code
3. **Pattern Handler Test**: Create `StructuralDiagnosis` with `failure_pattern="entries_too_loose_in_chop"`, verify no handler exists on unfixed code

**Bug 2 Tests**:
4. **Rollback State Test**: Perform rollback on unfixed code, assert `_baseline_run.summary` doesn't match the popped round's summary
5. **State Consistency Test**: Perform rollback, assert `_baseline_params`, `_baseline_run`, and `_session_baseline` are not consistent

**Expected Counterexamples**:
- Bug 1: `RuleSuggestionService.suggest()` returns empty list when only `structural` is provided
- Bug 2: `_baseline_run` is `None` or has wrong summary after rollback

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed functions produce the expected behavior.

**Pseudocode for Bug 1:**
```
FOR ALL bundle WHERE len(bundle.structural) > 0 DO
  suggestions := RuleSuggestionService_fixed.suggest(bundle.issues, params, bundle.structural)
  ASSERT len(suggestions) >= len(bundle.structural)  # at least one per structural
  ASSERT all s in suggestions have valid parameter and proposed_value
END FOR
```

**Pseudocode for Bug 2:**
```
FOR ALL rollback operation DO
  popped_round := session_history.pop()
  _on_rollback_fixed()
  ASSERT _baseline_run.summary == popped_round.summary
  ASSERT _baseline_params == popped_round.params_before
  ASSERT _session_baseline.params == popped_round.params_before
  ASSERT _session_baseline.summary == popped_round.summary
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed functions produce the same result as the original functions.

**Pseudocode for Bug 1 Preservation:**
```
FOR ALL bundle WHERE len(bundle.structural) == 0 DO
  suggestions_original := RuleSuggestionService_original.suggest(bundle.issues, params)
  suggestions_fixed := RuleSuggestionService_fixed.suggest(bundle.issues, params, [])
  ASSERT suggestions_original == suggestions_fixed
END FOR
```

**Pseudocode for Bug 2 Preservation:**
```
FOR ALL operations that do NOT involve rollback DO
  state_original := capture_state()
  perform_operation()
  state_fixed := capture_state()
  ASSERT state_original == state_fixed
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for legacy issues and normal operations, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Legacy Issue Preservation**: Verify legacy issue suggestions work identically before and after fix
2. **UI Interaction Preservation**: Verify mouse clicks on suggestions work identically
3. **Normal Operation Preservation**: Verify non-rollback operations don't change behavior

### Unit Tests

- Test `RuleSuggestionService.suggest()` with empty `structural` list (backward compatibility)
- Test `RuleSuggestionService.suggest()` with non-empty `structural` list (new functionality)
- Test `RuleSuggestionService.suggest()` with both `issues` and `structural` lists
- Test each structural pattern handler generates appropriate suggestions
- Test rollback restores `_baseline_run.summary` from popped round
- Test rollback restores all three state variables consistently
- Test rollback with empty session history (no-op)
- Test rollback with single round (restores initial state)

### Property-Based Tests

- Generate random `DiagnosisBundle` with varying `issues` and `structural` combinations, verify suggestions are generated correctly
- Generate random structural patterns and verify handlers exist and generate valid suggestions
- Generate random rollback scenarios with multiple rounds, verify state consistency after each rollback
- Generate random session histories and verify rollback can traverse entire history correctly

### Integration Tests

- Test full Improve workflow with structural diagnosis patterns driving suggestions
- Test rollback in multi-round session, verify state consistency at each step
- Test rollback then run candidate, verify candidate starts from correct baseline
- Test rollback then accept, verify new round captures correct state
- Test UI display shows both legacy issues and structural patterns correctly
