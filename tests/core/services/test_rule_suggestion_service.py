"""
Property-based tests for RuleSuggestionService.

Property 2: Suggestion rules produce correct parameter mutations
Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.7
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.models.improve_models import DiagnosedIssue
from app.core.services.rule_suggestion_service import RuleSuggestionService

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
_params_st = st.fixed_dictionaries({
    "stoploss": st.floats(min_value=-0.99, max_value=-0.01, allow_nan=False, allow_infinity=False),
    "max_open_trades": st.integers(min_value=1, max_value=10),
    "minimal_roi": st.fixed_dictionaries({
        "0": st.floats(min_value=0.001, max_value=0.5, allow_nan=False, allow_infinity=False),
        "30": st.floats(min_value=0.001, max_value=0.3, allow_nan=False, allow_infinity=False),
        "60": st.floats(min_value=0.001, max_value=0.2, allow_nan=False, allow_infinity=False),
    }),
    "buy_params": st.just({}),
    "sell_params": st.just({}),
})

_issues_st = st.lists(
    st.sampled_from([
        DiagnosedIssue("stoploss_too_wide", "desc"),
        DiagnosedIssue("trades_too_low", "desc"),
        DiagnosedIssue("weak_win_rate", "desc"),
        DiagnosedIssue("drawdown_high", "desc"),
        DiagnosedIssue("poor_pair_concentration", "desc"),
        DiagnosedIssue("negative_profit", "desc"),
    ]),
    min_size=1,
    unique_by=lambda i: i.issue_id,
)


# ---------------------------------------------------------------------------
# Property 2 — Suggestion rules produce correct parameter mutations
# Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.7
# ---------------------------------------------------------------------------
@given(params=_params_st, issues=_issues_st)
@settings(max_examples=200)
def test_suggestion_rules_produce_correct_parameter_mutations(params, issues):
    """**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.7**

    For any BaselineParams dict and any DiagnosedIssue list, each suggestion's
    proposed_value must match the rule formula for its issue type.
    """
    suggestions = RuleSuggestionService.suggest(issues, params)

    # Build a lookup: issue_id -> suggestion (by matching suggestion.parameter to issue)
    # The service returns one suggestion per issue in order, so we can zip them.
    # Use a dict keyed by issue_id for direct lookup.
    issue_id_set = {issue.issue_id for issue in issues}
    suggestion_by_issue: dict = {}

    # Map each suggestion back to its originating issue_id via parameter name
    _param_to_issue = {
        "stoploss": None,   # could be stoploss_too_wide or negative_profit
        "max_open_trades": None,  # could be trades_too_low or drawdown_high
        "minimal_roi": "weak_win_rate",
        "pairlist": "poor_pair_concentration",
    }

    # Build suggestion_by_issue by iterating suggestions alongside issues (same order)
    for issue, suggestion in zip(issues, suggestions):
        suggestion_by_issue[issue.issue_id] = suggestion

    # Req 5.1 — stoploss_too_wide: proposed_stoploss == round(stoploss + 0.02, 10)
    if "stoploss_too_wide" in issue_id_set:
        s = suggestion_by_issue["stoploss_too_wide"]
        expected = round(params["stoploss"] + 0.02, 10)
        assert s.proposed_value == expected, (
            f"stoploss_too_wide: expected {expected}, got {s.proposed_value}"
        )

    # Req 5.2 — trades_too_low: proposed_max_open_trades == min(max_open_trades + 1, 10)
    if "trades_too_low" in issue_id_set:
        s = suggestion_by_issue["trades_too_low"]
        expected = min(params["max_open_trades"] + 1, 10)
        assert s.proposed_value == expected, (
            f"trades_too_low: expected {expected}, got {s.proposed_value}"
        )

    # Req 5.3 — weak_win_rate: proposed minimal_roi at smallest int key == round(original - 0.005, 10)
    if "weak_win_rate" in issue_id_set:
        s = suggestion_by_issue["weak_win_rate"]
        minimal_roi = params["minimal_roi"]
        smallest_key = min(minimal_roi.keys(), key=lambda k: int(k))
        original_val = minimal_roi[smallest_key]
        expected_val = round(original_val - 0.005, 10)
        assert isinstance(s.proposed_value, dict), (
            f"weak_win_rate: proposed_value should be a dict, got {type(s.proposed_value)}"
        )
        assert s.proposed_value[smallest_key] == expected_val, (
            f"weak_win_rate: expected roi[{smallest_key}]={expected_val}, "
            f"got {s.proposed_value[smallest_key]}"
        )

    # Req 5.4 — drawdown_high: proposed_max_open_trades == max(max_open_trades - 1, 1)
    if "drawdown_high" in issue_id_set:
        s = suggestion_by_issue["drawdown_high"]
        expected = max(params["max_open_trades"] - 1, 1)
        assert s.proposed_value == expected, (
            f"drawdown_high: expected {expected}, got {s.proposed_value}"
        )

    # Req 5.5 — poor_pair_concentration: is_advisory=True, proposed_value=None
    if "poor_pair_concentration" in issue_id_set:
        s = suggestion_by_issue["poor_pair_concentration"]
        assert s.is_advisory is True, (
            f"poor_pair_concentration: expected is_advisory=True, got {s.is_advisory}"
        )
        assert s.proposed_value is None, (
            f"poor_pair_concentration: expected proposed_value=None, got {s.proposed_value}"
        )

    # Req 5.7 — negative_profit: proposed_stoploss == round(stoploss + 0.03, 10)
    if "negative_profit" in issue_id_set:
        s = suggestion_by_issue["negative_profit"]
        expected = round(params["stoploss"] + 0.03, 10)
        assert s.proposed_value == expected, (
            f"negative_profit: expected {expected}, got {s.proposed_value}"
        )
