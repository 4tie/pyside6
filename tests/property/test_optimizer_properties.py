"""
Hypothesis property-based tests for the Strategy Optimizer.

Property 1: compute_optimizer_score always returns a finite float.
Property 2: StrategyParams round-trip serialization (added in task 5.1).
"""
import math
import pytest
from hypothesis import given, settings, strategies as st

from app.core.services.optimizer_session_service import (
    SCORE_METRICS,
    compute_enhanced_composite_score,
    compute_optimizer_score,
)

# All metric names including an unknown one
_ALL_METRIC_NAMES = list(SCORE_METRICS) + ["unknown_metric", ""]


@given(
    metric=st.sampled_from(_ALL_METRIC_NAMES),
    value=st.one_of(
        st.none(),
        st.floats(allow_nan=True, allow_infinity=True),
        st.integers(),
        st.text(max_size=5),
    ),
)
@settings(max_examples=500)
def test_score_always_finite(metric, value):
    """For all metric names and all value types, score is always a finite float."""
    metrics = {metric: value}
    score = compute_optimizer_score(metrics, metric)
    assert isinstance(score, float)
    assert math.isfinite(score)


@given(
    metric=st.sampled_from(list(SCORE_METRICS)),
    value=st.floats(allow_nan=True, allow_infinity=True),
)
def test_score_finite_for_all_float_values(metric, value):
    """For all named metrics and all float values (including NaN/Inf), score is finite."""
    score = compute_optimizer_score({metric: value}, metric)
    assert math.isfinite(score)


@given(metric=st.sampled_from(list(SCORE_METRICS)))
def test_score_empty_dict_is_zero(metric):
    """Empty metrics dict always returns 0.0."""
    assert compute_optimizer_score({}, metric) == 0.0


@given(
    metric=st.sampled_from(list(SCORE_METRICS)),
    value=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
)
def test_score_finite_input_returns_same_value(metric, value):
    """For finite float inputs, score equals the input value."""
    result = compute_optimizer_score({metric: value}, metric)
    assert result == pytest.approx(value)


@given(
    metrics=st.dictionaries(
        keys=st.sampled_from([
            "total_trades",
            "total_profit_pct",
            "max_drawdown_pct",
            "profit_factor",
            "sharpe_ratio",
            "win_rate",
        ]),
        values=st.one_of(
            st.none(),
            st.floats(allow_nan=True, allow_infinity=True),
            st.integers(),
            st.text(max_size=5),
        ),
        max_size=6,
    ),
    target_min_trades=st.one_of(st.floats(allow_nan=True, allow_infinity=True), st.integers(), st.text(max_size=5)),
    target_profit_pct=st.one_of(st.floats(allow_nan=True, allow_infinity=True), st.integers(), st.text(max_size=5)),
    max_drawdown_limit=st.one_of(st.floats(allow_nan=True, allow_infinity=True), st.integers(), st.text(max_size=5)),
    target_romad=st.one_of(st.floats(allow_nan=True, allow_infinity=True), st.integers(), st.text(max_size=5)),
)
@settings(max_examples=300)
def test_enhanced_composite_score_always_finite(
    metrics,
    target_min_trades,
    target_profit_pct,
    max_drawdown_limit,
    target_romad,
):
    """Enhanced composite score and breakdown are finite for arbitrary inputs."""
    config = type(
        "Config",
        (),
        {
            "target_min_trades": target_min_trades,
            "target_profit_pct": target_profit_pct,
            "max_drawdown_limit": max_drawdown_limit,
            "target_romad": target_romad,
        },
    )()

    score, breakdown = compute_enhanced_composite_score(metrics, config)

    assert isinstance(score, float)
    assert math.isfinite(score)
    assert all(math.isfinite(value) for value in breakdown.values())


# -----------------------------------------------------------------------
# Property 2: StrategyParams round-trip (Requirement 14.4)
# -----------------------------------------------------------------------
from app.core.models.optimizer_models import (
    ParamDef, ParamType, StrategyParams,
)

# Hypothesis strategies for building valid model instances

_param_types = list(ParamType)

_param_def_strategy = st.builds(
    ParamDef,
    name=st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_"), min_size=1, max_size=20),
    param_type=st.sampled_from(_param_types),
    default=st.one_of(st.none(), st.integers(-100, 100), st.floats(-100.0, 100.0, allow_nan=False, allow_infinity=False), st.booleans(), st.text(max_size=10)),
    low=st.one_of(st.none(), st.floats(-100.0, 0.0, allow_nan=False, allow_infinity=False)),
    high=st.one_of(st.none(), st.floats(0.0, 100.0, allow_nan=False, allow_infinity=False)),
    categories=st.one_of(st.none(), st.lists(st.text(max_size=10), min_size=1, max_size=5)),
    space=st.sampled_from(["buy", "sell", "roi", "stoploss", "trailing"]),
    enabled=st.booleans(),
)

_strategy_params_strategy = st.builds(
    StrategyParams,
    strategy_class=st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_"), min_size=1, max_size=30),
    timeframe=st.sampled_from(["1m", "5m", "15m", "1h", "4h", "1d"]),
    minimal_roi=st.dictionaries(
        keys=st.text(alphabet="0123456789", min_size=1, max_size=4),
        values=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        max_size=5,
    ),
    stoploss=st.floats(min_value=-1.0, max_value=-0.001, allow_nan=False, allow_infinity=False),
    trailing_stop=st.booleans(),
    trailing_stop_positive=st.one_of(st.none(), st.floats(0.001, 0.5, allow_nan=False, allow_infinity=False)),
    trailing_stop_positive_offset=st.one_of(st.none(), st.floats(0.001, 0.5, allow_nan=False, allow_infinity=False)),
    buy_params=st.dictionaries(
        keys=st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_"), min_size=1, max_size=20),
        values=_param_def_strategy,
        max_size=5,
    ),
    sell_params=st.dictionaries(
        keys=st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_"), min_size=1, max_size=20),
        values=_param_def_strategy,
        max_size=5,
    ),
)


@given(_strategy_params_strategy)
@settings(max_examples=200)
def test_strategy_params_round_trip(params: StrategyParams):
    """For all valid StrategyParams, serializing then deserializing produces an equal object.

    **Validates: Requirement 14.4**
    """
    serialized = params.to_dict()
    restored = StrategyParams.from_dict(serialized)
    assert restored == params
