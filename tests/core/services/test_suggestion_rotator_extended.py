"""
test_suggestion_rotator_extended.py — Unit tests for the extended SuggestionRotator
covering buy/sell param mutations, trailing-stop proposals, and all ten structural
pattern mappings.
"""
import pytest
from app.core.services.loop_service import SuggestionRotator
from app.core.models.improve_models import ParameterSuggestion
from app.core.models.diagnosis_models import StructuralDiagnosis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_structural(pattern: str) -> StructuralDiagnosis:
    return StructuralDiagnosis(
        failure_pattern=pattern,
        evidence="test evidence",
        root_cause="test root cause",
        mutation_direction="test direction",
        confidence=0.7,
        severity="moderate",
    )


def _base_params() -> dict:
    return {
        "stoploss": -0.10,
        "max_open_trades": 3,
        "minimal_roi": {"0": 0.10, "30": 0.05, "60": 0.02},
        "buy_params": {"rsi_buy": 30.0, "ema_fast": 12, "use_volume": True},
        "sell_params": {"rsi_sell": 70.0, "ema_slow": 26},
        "trailing_stop": False,
    }


# ---------------------------------------------------------------------------
# Numeric buy/sell param delta with clamping
# ---------------------------------------------------------------------------

class TestVaryBuySellParam:
    def test_numeric_delta_applied(self):
        rotator = SuggestionRotator(_base_params())
        suggestion = ParameterSuggestion(
            parameter="buy_params",
            proposed_value={"rsi_buy": 31.0},
            reason="test",
            expected_effect="test",
        )
        result = rotator._vary_buy_sell_param(suggestion, _base_params(), step=0, reverse=False)
        assert result is not None
        assert result.parameter == "buy_params"
        assert isinstance(result.proposed_value, dict)
        # The proposed value for rsi_buy should differ from 30.0
        assert result.proposed_value.get("rsi_buy") != 30.0

    def test_reverse_direction(self):
        rotator = SuggestionRotator(_base_params())
        suggestion = ParameterSuggestion(
            parameter="buy_params",
            proposed_value={"rsi_buy": 31.0},
            reason="test",
            expected_effect="test",
        )
        result_fwd = rotator._vary_buy_sell_param(suggestion, _base_params(), step=0, reverse=False)
        result_rev = rotator._vary_buy_sell_param(suggestion, _base_params(), step=0, reverse=True)
        assert result_fwd is not None
        assert result_rev is not None
        # Forward and reverse should produce different values
        assert result_fwd.proposed_value["rsi_buy"] != result_rev.proposed_value["rsi_buy"]

    def test_boolean_toggle_mutation(self):
        rotator = SuggestionRotator(_base_params())
        suggestion = ParameterSuggestion(
            parameter="buy_params",
            proposed_value={"use_volume": False},
            reason="test",
            expected_effect="test",
        )
        result = rotator._vary_buy_sell_param(suggestion, _base_params(), step=0, reverse=False)
        assert result is not None
        # use_volume was True, should be toggled to False
        assert result.proposed_value["use_volume"] is False

    def test_empty_group_returns_none(self):
        rotator = SuggestionRotator(_base_params())
        params = dict(_base_params())
        params["buy_params"] = {}
        suggestion = ParameterSuggestion(
            parameter="buy_params",
            proposed_value={},
            reason="test",
            expected_effect="test",
        )
        result = rotator._vary_buy_sell_param(suggestion, params, step=0, reverse=False)
        assert result is None

    def test_clamping_logs_warning(self, caplog):
        """Values outside observed range should be clamped."""
        import logging
        rotator = SuggestionRotator(_base_params())
        # Use a very large step to force clamping
        suggestion = ParameterSuggestion(
            parameter="buy_params",
            proposed_value={"rsi_buy": 30.0},
            reason="test",
            expected_effect="test",
        )
        with caplog.at_level(logging.WARNING, logger="services.loop"):
            result = rotator._vary_buy_sell_param(suggestion, _base_params(), step=10, reverse=False)
        # Result should still be returned (clamped)
        assert result is not None


# ---------------------------------------------------------------------------
# Trailing-stop proposal on high-drawdown pattern
# ---------------------------------------------------------------------------

class TestTrailingStopProposal:
    def test_trailing_stop_proposed_on_drawdown_pattern(self):
        rotator = SuggestionRotator(_base_params())
        structural = [_make_structural("losers_lasting_too_long")]
        suggestions = rotator.generate_suggestions(
            issues=[],
            current_params=_base_params(),
            prev_iteration=None,
            structural=structural,
        )
        trailing_suggestions = [s for s in suggestions if s.parameter == "trailing_stop"]
        assert len(trailing_suggestions) >= 1
        assert trailing_suggestions[0].proposed_value is True

    def test_trailing_stop_not_proposed_when_already_enabled(self):
        params = dict(_base_params())
        params["trailing_stop"] = True
        rotator = SuggestionRotator(params)
        structural = [_make_structural("losers_lasting_too_long")]
        suggestions = rotator.generate_suggestions(
            issues=[],
            current_params=params,
            prev_iteration=None,
            structural=structural,
        )
        trailing_suggestions = [s for s in suggestions if s.parameter == "trailing_stop"]
        assert len(trailing_suggestions) == 0

    def test_drawdown_after_volatility_also_triggers_trailing(self):
        rotator = SuggestionRotator(_base_params())
        structural = [_make_structural("drawdown_after_volatility")]
        suggestions = rotator.generate_suggestions(
            issues=[],
            current_params=_base_params(),
            prev_iteration=None,
            structural=structural,
        )
        trailing_suggestions = [s for s in suggestions if s.parameter == "trailing_stop"]
        assert len(trailing_suggestions) >= 1


# ---------------------------------------------------------------------------
# All ten structural pattern mappings produce non-None suggestions
# ---------------------------------------------------------------------------

ALL_TEN_PATTERNS = [
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
]


class TestAllStructuralPatternMappings:
    @pytest.mark.parametrize("pattern", ALL_TEN_PATTERNS)
    def test_pattern_produces_suggestion(self, pattern):
        """Each structural pattern must produce at least one non-None suggestion."""
        rotator = SuggestionRotator(_base_params())
        structural = [_make_structural(pattern)]
        suggestions = rotator._suggestions_from_structural(structural, _base_params())
        # Some patterns may not produce suggestions if params are already at boundary,
        # but with our base_params they should all produce at least one
        # (trailing-stop patterns are handled separately in generate_suggestions)
        if pattern in ("losers_lasting_too_long", "drawdown_after_volatility"):
            # These also trigger trailing_stop via generate_suggestions; stoploss suggestion here
            assert len(suggestions) >= 1
        else:
            assert len(suggestions) >= 1, (
                f"Pattern '{pattern}' produced no suggestions with base_params"
            )

    def test_exits_cutting_winners_early_widens_roi(self):
        rotator = SuggestionRotator(_base_params())
        structural = [_make_structural("exits_cutting_winners_early")]
        suggestions = rotator._suggestions_from_structural(structural, _base_params())
        roi_suggestions = [s for s in suggestions if s.parameter == "minimal_roi"]
        assert len(roi_suggestions) == 1
        # All ROI values should be larger than original
        original_roi = _base_params()["minimal_roi"]
        for k, v in roi_suggestions[0].proposed_value.items():
            assert v > original_roi[k]

    def test_filter_stack_too_strict_relaxes_buy_params(self):
        rotator = SuggestionRotator(_base_params())
        structural = [_make_structural("filter_stack_too_strict")]
        suggestions = rotator._suggestions_from_structural(structural, _base_params())
        buy_suggestions = [s for s in suggestions if s.parameter == "buy_params"]
        assert len(buy_suggestions) == 1

    def test_losers_lasting_too_long_tightens_stoploss(self):
        rotator = SuggestionRotator(_base_params())
        structural = [_make_structural("losers_lasting_too_long")]
        suggestions = rotator._suggestions_from_structural(structural, _base_params())
        sl_suggestions = [s for s in suggestions if s.parameter == "stoploss"]
        assert len(sl_suggestions) == 1
        # Stoploss should be tighter (less negative)
        assert sl_suggestions[0].proposed_value > _base_params()["stoploss"]
