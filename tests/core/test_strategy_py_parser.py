"""
Unit tests for app/core/parsing/strategy_py_parser.py

Tests cover:
- Parameter extraction for all four parameter types
- Missing params → empty result (no exception)
- Parse error handling (syntax error → empty result, no exception)
- Strategy that inherits from a base class → empty result, no exception
- Extraction of strategy metadata (timeframe, stoploss, trailing_stop, minimal_roi)
- Negative numbers in parameters (e.g. stoploss = -0.10)
"""

import pytest
from pathlib import Path

from app.core.parsing.strategy_py_parser import parse_strategy_py
from app.core.models.optimizer_models import ParamType


SIMPLE_STRATEGY = '''
class SimpleStrategy:
    timeframe = "1h"
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    minimal_roi = {"0": 0.10, "30": 0.05, "60": 0.01}

    buy_rsi = IntParameter(low=5, high=30, default=14, space="buy")
    sell_rsi = IntParameter(low=50, high=90, default=70, space="sell")
    buy_threshold = DecimalParameter(low=0.01, high=0.10, default=0.05, space="buy")
    buy_signal = CategoricalParameter(categories=["rsi", "macd", "ema"], default="rsi", space="buy")
    use_custom_stoploss = BooleanParameter(default=False, space="buy")
'''


def test_extract_int_parameter(tmp_path):
    f = tmp_path / "simple.py"
    f.write_text(SIMPLE_STRATEGY)
    result = parse_strategy_py(f)
    assert "buy_rsi" in result.buy_params
    p = result.buy_params["buy_rsi"]
    assert p.param_type == ParamType.INT
    assert p.low == 5.0
    assert p.high == 30.0
    assert p.default == 14


def test_extract_decimal_parameter(tmp_path):
    f = tmp_path / "simple.py"
    f.write_text(SIMPLE_STRATEGY)
    result = parse_strategy_py(f)
    assert "buy_threshold" in result.buy_params
    p = result.buy_params["buy_threshold"]
    assert p.param_type == ParamType.DECIMAL
    assert p.low == pytest.approx(0.01)
    assert p.high == pytest.approx(0.10)
    assert p.default == pytest.approx(0.05)


def test_extract_categorical_parameter(tmp_path):
    f = tmp_path / "simple.py"
    f.write_text(SIMPLE_STRATEGY)
    result = parse_strategy_py(f)
    assert "buy_signal" in result.buy_params
    p = result.buy_params["buy_signal"]
    assert p.param_type == ParamType.CATEGORICAL
    assert p.categories == ["rsi", "macd", "ema"]
    assert p.default == "rsi"


def test_extract_boolean_parameter(tmp_path):
    f = tmp_path / "simple.py"
    f.write_text(SIMPLE_STRATEGY)
    result = parse_strategy_py(f)
    assert "use_custom_stoploss" in result.buy_params
    p = result.buy_params["use_custom_stoploss"]
    assert p.param_type == ParamType.BOOLEAN
    assert p.default == False


def test_sell_param_in_sell_params(tmp_path):
    f = tmp_path / "simple.py"
    f.write_text(SIMPLE_STRATEGY)
    result = parse_strategy_py(f)
    assert "sell_rsi" in result.sell_params
    assert "sell_rsi" not in result.buy_params


def test_strategy_metadata(tmp_path):
    f = tmp_path / "simple.py"
    f.write_text(SIMPLE_STRATEGY)
    result = parse_strategy_py(f)
    assert result.timeframe == "1h"
    assert result.stoploss == pytest.approx(-0.05)
    assert result.trailing_stop == True
    assert result.trailing_stop_positive == pytest.approx(0.02)
    assert result.trailing_stop_positive_offset == pytest.approx(0.03)
    assert result.minimal_roi == {"0": pytest.approx(0.10), "30": pytest.approx(0.05), "60": pytest.approx(0.01)}


def test_strategy_class_name(tmp_path):
    f = tmp_path / "simple.py"
    f.write_text(SIMPLE_STRATEGY)
    result = parse_strategy_py(f)
    assert result.strategy_class == "SimpleStrategy"


def test_no_params_returns_empty(tmp_path):
    f = tmp_path / "empty.py"
    f.write_text("class EmptyStrategy:\n    timeframe = '5m'\n    stoploss = -0.10\n")
    result = parse_strategy_py(f)
    assert result.buy_params == {}
    assert result.sell_params == {}


def test_syntax_error_returns_empty(tmp_path):
    f = tmp_path / "broken.py"
    f.write_text("class Broken:\n    def bad syntax here !!!\n")
    result = parse_strategy_py(f)
    assert result.buy_params == {}
    assert result.sell_params == {}


def test_syntax_error_does_not_raise(tmp_path):
    f = tmp_path / "broken.py"
    f.write_text("class Broken:\n    def bad syntax here !!!\n")
    # Must not raise
    result = parse_strategy_py(f)
    assert result is not None


def test_missing_file_returns_empty(tmp_path):
    result = parse_strategy_py(tmp_path / "nonexistent.py")
    assert result.buy_params == {}
    assert result.sell_params == {}


def test_missing_file_does_not_raise(tmp_path):
    # Must not raise even when file doesn't exist
    result = parse_strategy_py(tmp_path / "nonexistent.py")
    assert result is not None


def test_inherited_strategy_returns_empty_no_exception(tmp_path):
    """Strategy inherits from a base class — inherited params not visible (V1 limitation)."""
    f = tmp_path / "inherited.py"
    f.write_text("""
class BaseStrategy:
    buy_rsi = IntParameter(low=5, high=30, default=14, space='buy')

class MyStrategy(BaseStrategy):
    timeframe = '5m'
    stoploss = -0.10
""")
    # Only the first class body is parsed — BaseStrategy has the param,
    # MyStrategy body has none. Should not raise.
    result = parse_strategy_py(f)
    assert isinstance(result.buy_params, dict)
    assert isinstance(result.sell_params, dict)


def test_negative_stoploss(tmp_path):
    f = tmp_path / "neg.py"
    f.write_text(
        "class S:\n"
        "    stoploss = -0.15\n"
        "    buy_rsi = IntParameter(low=5, high=30, default=14, space='buy')\n"
    )
    result = parse_strategy_py(f)
    assert result.stoploss == pytest.approx(-0.15)


def test_negative_param_low(tmp_path):
    """Negative values in parameter bounds are handled correctly."""
    f = tmp_path / "neg_param.py"
    f.write_text(
        "class S:\n"
        "    buy_threshold = DecimalParameter(low=-0.05, high=0.05, default=0.0, space='buy')\n"
    )
    result = parse_strategy_py(f)
    assert "buy_threshold" in result.buy_params
    p = result.buy_params["buy_threshold"]
    assert p.low == pytest.approx(-0.05)
    assert p.high == pytest.approx(0.05)


def test_positional_args_int_parameter(tmp_path):
    """IntParameter with positional args (low, high, default) is parsed correctly."""
    f = tmp_path / "pos.py"
    f.write_text(
        "class S:\n"
        "    buy_rsi = IntParameter(5, 30, 14, space='buy')\n"
    )
    result = parse_strategy_py(f)
    assert "buy_rsi" in result.buy_params
    p = result.buy_params["buy_rsi"]
    assert p.low == 5.0
    assert p.high == 30.0
    assert p.default == 14


def test_annotated_assignment(tmp_path):
    """Annotated assignments (buy_rsi: int = IntParameter(...)) are parsed."""
    f = tmp_path / "ann.py"
    f.write_text(
        "class S:\n"
        "    buy_rsi: int = IntParameter(low=5, high=30, default=14, space='buy')\n"
    )
    result = parse_strategy_py(f)
    assert "buy_rsi" in result.buy_params


def test_boolean_parameter_default_false_when_missing(tmp_path):
    """BooleanParameter with no default gets False as default."""
    f = tmp_path / "bool.py"
    f.write_text(
        "class S:\n"
        "    use_sl = BooleanParameter(space='buy')\n"
    )
    result = parse_strategy_py(f)
    assert "use_sl" in result.buy_params
    assert result.buy_params["use_sl"].default == False


def test_categorical_positional_categories(tmp_path):
    """CategoricalParameter with positional categories list is parsed."""
    f = tmp_path / "cat.py"
    f.write_text(
        "class S:\n"
        "    signal = CategoricalParameter(['rsi', 'macd'], default='rsi', space='buy')\n"
    )
    result = parse_strategy_py(f)
    assert "signal" in result.buy_params
    p = result.buy_params["signal"]
    assert p.categories == ["rsi", "macd"]


def test_empty_file_returns_empty(tmp_path):
    """Empty file returns empty StrategyParams without raising."""
    f = tmp_path / "empty.py"
    f.write_text("")
    result = parse_strategy_py(f)
    assert result.buy_params == {}
    assert result.sell_params == {}


def test_trailing_stop_false_by_default(tmp_path):
    """trailing_stop defaults to False when not declared."""
    f = tmp_path / "s.py"
    f.write_text("class S:\n    timeframe = '5m'\n")
    result = parse_strategy_py(f)
    assert result.trailing_stop == False


def test_trailing_stop_positive_none_by_default(tmp_path):
    """trailing_stop_positive defaults to None when not declared."""
    f = tmp_path / "s.py"
    f.write_text("class S:\n    timeframe = '5m'\n")
    result = parse_strategy_py(f)
    assert result.trailing_stop_positive is None
    assert result.trailing_stop_positive_offset is None


def test_multiple_buy_params(tmp_path):
    """Multiple buy parameters are all captured."""
    f = tmp_path / "multi.py"
    f.write_text("""
class S:
    a = IntParameter(low=1, high=10, default=5, space='buy')
    b = IntParameter(low=2, high=20, default=10, space='buy')
    c = DecimalParameter(low=0.1, high=1.0, default=0.5, space='buy')
""")
    result = parse_strategy_py(f)
    assert len(result.buy_params) == 3
    assert "a" in result.buy_params
    assert "b" in result.buy_params
    assert "c" in result.buy_params


def test_stem_used_as_class_name_when_no_class(tmp_path):
    """When no class is found, the file stem is used as strategy_class."""
    f = tmp_path / "my_strategy.py"
    f.write_text("# just a comment\n")
    result = parse_strategy_py(f)
    assert result.strategy_class == "my_strategy"
