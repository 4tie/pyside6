# Bugfix Requirements Document

## Introduction

This bugfix addresses two critical issues in the Improve feature of the Freqtrade GUI application:

1. **RuleSuggestionService not using structural diagnosis**: The `ResultsDiagnosisService` returns a `DiagnosisBundle` containing both `issues` (legacy DiagnosedIssue objects) and `structural` (pattern-based StructuralDiagnosis objects), but `RuleSuggestionService` only processes the legacy `issues` list. The structural diagnosis data is displayed in the UI but not used to generate parameter suggestions, defeating the purpose of the structural analysis.

2. **Rollback doesn't restore baseline run state consistently**: When rollback occurs, it restores `params_before` and updates `_session_baseline`, but fails to rebuild the baseline run state coherently. The code updates `_baseline_params` and clears `_candidate_run`, but doesn't restore `_baseline_run` to the correct summary for the state before the last accept, leaving the UI with params reverted but summary/analysis potentially mismatched.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `ResultsDiagnosisService.diagnose()` returns a `DiagnosisBundle` with both `issues` and `structural` lists THEN `RuleSuggestionService.suggest()` only processes the `issues` list and ignores the `structural` list entirely

1.2 WHEN `ImprovePage.rollback()` is called to restore previous parameters THEN `_baseline_run` is not restored to the correct summary from the accepted run, leaving the UI in an inconsistent state where params are reverted but summary data may be stale or mismatched

1.3 WHEN structural diagnosis identifies a pattern-based issue (e.g., "entries_too_loose_in_chop", "single_regime_dependency") THEN no parameter suggestions are generated for that issue because `RuleSuggestionService` only handles legacy `DiagnosedIssue` objects, not `StructuralDiagnosis` objects

### Expected Behavior (Correct)

2.1 WHEN `ResultsDiagnosisService.diagnose()` returns a `DiagnosisBundle` with both `issues` and `structural` lists THEN `RuleSuggestionService.suggest()` processes both lists and generates parameter suggestions for structural diagnosis patterns

2.2 WHEN `ImprovePage.rollback()` is called to restore previous parameters THEN `_baseline_run` is restored to the correct summary from the accepted run, ensuring params and summary data are consistent

2.3 WHEN structural diagnosis identifies a pattern-based issue THEN `RuleSuggestionService` generates appropriate parameter suggestions based on the structural diagnosis pattern and mutation direction

### Unchanged Behavior (Regression Prevention)

3.1 WHEN `ResultsDiagnosisService.diagnose()` is called with a `DiagnosisInput` THEN it continues to return a `DiagnosisBundle` with both `issues` and `structural` lists populated according to the existing rule logic

3.2 WHEN `RuleSuggestionService.suggest()` is called with legacy `DiagnosedIssue` objects THEN it continues to generate parameter suggestions using the existing rule-based handlers

3.3 WHEN rollback is NOT performed (normal workflow) THEN `_baseline_run` and `_baseline_params` remain unchanged and continue to reflect the current accepted state

3.4 WHEN a new run is selected and analyzed THEN `_baseline_run` is updated to the new run's summary and `_baseline_params` is updated to the new run's parameters, regardless of whether rollback occurred previously

## Bug Condition

**Bug Condition C(X)**: The bug is triggered when:
- A `DiagnosisBundle` is returned from `ResultsDiagnosisService.diagnose()` containing non-empty `structural` list, AND
- `RuleSuggestionService.suggest()` is called with only the `issues` list (ignoring `structural`), OR
- `ImprovePage.rollback()` is called without restoring `_baseline_run` to the correct summary

**Property P(result)**: After the fix:
- `RuleSuggestionService.suggest()` must process both `issues` and `structural` from the `DiagnosisBundle`
- `ImprovePage.rollback()` must restore `_baseline_run` to the summary from the accepted run stored in session history

**Preservation Goal**: For all non-buggy inputs (no structural diagnosis, or normal workflow without rollback), the behavior must remain unchanged.
