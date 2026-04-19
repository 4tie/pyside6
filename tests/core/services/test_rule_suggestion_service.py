"""
Tests for RuleSuggestionService concrete mutation mapping.
"""
from __future__ import annotations

import pytest

from app.core.models.diagnosis_models import StructuralDiagnosis
from app.core.models.improve_models import DiagnosedIssue
from app.core.services.rule_suggestion_service import RuleSuggestionService


def _base_params() -> dict:
    return {
        "stoploss": -0.10,
        "max_open_trades": 3,
        "minimal_roi": {"0": 0.10, "30": 0.05, "60": 0.02},
        "buy_params": {"rsi_buy": 30.0, "mfi_buy": 25.0, "ema_fast": 12},
        "sell_params": {"rsi_sell": 70.0, "ema_slow": 26},
    }


def _structural(pattern: str) -> StructuralDiagnosis:
    return StructuralDiagnosis(
        failure_pattern=pattern,
        evidence="test evidence",
        root_cause="test cause",
        mutation_direction="test direction",
        confidence=0.7,
        severity="moderate",
    )


def test_concrete_issue_suggestions_remain_json_mutations() -> None:
    params = _base_params()
    issues = [
        DiagnosedIssue("stoploss_too_wide", "desc"),
        DiagnosedIssue("trades_too_low", "desc"),
        DiagnosedIssue("weak_win_rate", "desc"),
        DiagnosedIssue("drawdown_high", "desc"),
        DiagnosedIssue("negative_profit", "desc"),
    ]

    suggestions = RuleSuggestionService.suggest(issues, params)
    by_param = {suggestion.parameter: suggestion for suggestion in suggestions}

    assert by_param["stoploss"].proposed_value == round(params["stoploss"] + 0.03, 10)
    assert by_param["max_open_trades"].proposed_value == max(params["max_open_trades"] - 1, 1)
    assert by_param["minimal_roi"].proposed_value["0"] == round(
        params["minimal_roi"]["0"] - 0.005,
        10,
    )


def test_advisory_issue_placeholders_are_omitted() -> None:
    params = _base_params()
    issues = [
        DiagnosedIssue("poor_pair_concentration", "desc"),
        DiagnosedIssue("profit_factor_low", "desc"),
        DiagnosedIssue("expectancy_negative", "desc"),
    ]

    suggestions = RuleSuggestionService.suggest(issues, params)
    assert suggestions == []


@pytest.mark.parametrize(
    "pattern",
    [
        "entries_too_loose_in_chop",
        "entries_too_late_in_trend",
        "exits_cutting_winners_early",
        "losers_lasting_too_long",
        "single_regime_dependency",
        "micro_loss_noise",
        "filter_stack_too_strict",
        "high_winrate_bad_payoff",
        "outlier_trade_dependency",
        "drawdown_after_volatility",
    ],
)
def test_all_current_structural_patterns_map_to_concrete_mutations(pattern: str) -> None:
    suggestions = RuleSuggestionService.suggest([], _base_params(), [_structural(pattern)])
    assert len(suggestions) == 1
    assert suggestions[0].proposed_value is not None
    assert suggestions[0].is_advisory is False
    assert suggestions[0].parameter not in {"entry_filters", "entry_conditions"}


def test_drawdown_after_volatility_maps_to_stoploss() -> None:
    params = _base_params()
    suggestion = RuleSuggestionService.suggest([], params, [_structural("drawdown_after_volatility")])[0]
    assert suggestion.parameter == "stoploss"
    assert suggestion.proposed_value > params["stoploss"]


def test_drawdown_cluster_dependency_alias_maps_to_same_stoploss() -> None:
    params = _base_params()
    direct = RuleSuggestionService._suggest_drawdown_cluster_dependency(
        _structural("drawdown_cluster_dependency"),
        params,
    )
    canonical = RuleSuggestionService.suggest(
        [],
        params,
        [_structural("drawdown_after_volatility")],
    )[0]
    assert direct is not None
    assert direct.parameter == canonical.parameter == "stoploss"
    assert direct.proposed_value == canonical.proposed_value


def test_entries_too_loose_in_chop_returns_none_when_no_real_change() -> None:
    params = _base_params()
    params["buy_params"] = {}
    suggestion = RuleSuggestionService._suggest_entries_too_loose_in_chop(
        _structural("entries_too_loose_in_chop"),
        params,
    )
    assert suggestion is None
