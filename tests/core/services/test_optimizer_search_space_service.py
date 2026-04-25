"""Tests for core optimizer search-space generation."""

from pathlib import Path

import pytest

from app.core.models.optimizer_models import ParamDef, ParamType, StrategyParams
from app.core.services.optimizer_search_space_service import OptimizerSearchSpaceService
from app.core.services.optimizer_session_service import (
    _build_freqtrade_params_file,
    _group_candidate_params,
)


def _strategy_params() -> StrategyParams:
    return StrategyParams(
        strategy_class="TestStrategy",
        timeframe="5m",
        minimal_roi={"0": 0.10, "30": 0.03},
        stoploss=-0.12,
        trailing_stop=True,
        trailing_stop_positive=0.02,
        trailing_stop_positive_offset=0.04,
        buy_params={
            "buy_rsi": ParamDef(
                name="buy_rsi",
                param_type=ParamType.INT,
                default=30,
                low=10,
                high=50,
                space="buy",
            ),
        },
        sell_params={
            "sell_rsi": ParamDef(
                name="sell_rsi",
                param_type=ParamType.INT,
                default=70,
                low=50,
                high=90,
                space="sell",
            ),
        },
    )


def _by_name(defs: list[ParamDef]) -> dict[str, ParamDef]:
    return {param.name: param for param in defs}


def test_builds_buy_sell_roi_stoploss_and_trailing_from_core_inputs() -> None:
    live_json = {
        "params": {
            "roi": {"0": 0.12, "45": 0.04},
            "stoploss": {"stoploss": -0.08},
            "trailing": {
                "trailing_stop": True,
                "trailing_stop_positive": 0.015,
                "trailing_stop_positive_offset": 0.03,
                "trailing_only_offset_is_reached": True,
            },
        }
    }

    defs = OptimizerSearchSpaceService.build_search_space(_strategy_params(), live_json)
    names = [param.name for param in defs]
    spaces = [param.space for param in defs]

    assert names == [
        "buy_rsi",
        "sell_rsi",
        "0",
        "45",
        "stoploss",
        "trailing_stop",
        "trailing_stop_positive",
        "trailing_stop_positive_offset",
        "trailing_only_offset_is_reached",
    ]
    assert spaces == [
        "buy",
        "sell",
        "roi",
        "roi",
        "stoploss",
        "trailing",
        "trailing",
        "trailing",
        "trailing",
    ]
    assert _by_name(defs)["0"].default == pytest.approx(0.12)
    assert _by_name(defs)["45"].name == "45"
    assert _by_name(defs)["stoploss"].default == pytest.approx(-0.08)
    assert _by_name(defs)["trailing_only_offset_is_reached"].param_type == ParamType.BOOLEAN


def test_skips_unavailable_trailing_fields_safely() -> None:
    params = StrategyParams(
        strategy_class="NoTrailing",
        minimal_roi={"0": 0.05},
        stoploss=-0.10,
    )

    defs = OptimizerSearchSpaceService.build_search_space(params, {})

    assert "trailing_stop" not in _by_name(defs)
    assert "trailing_stop_positive" not in _by_name(defs)
    assert "stoploss" in _by_name(defs)


def test_validate_invalid_numeric_bounds_and_stoploss_ranges() -> None:
    defs = [
        ParamDef(
            name="buy_rsi",
            param_type=ParamType.INT,
            default=20,
            low=30,
            high=10,
            space="buy",
        ),
        ParamDef(
            name="stoploss",
            param_type=ParamType.DECIMAL,
            default=-0.1,
            low=-0.2,
            high=0.1,
            space="stoploss",
        ),
        ParamDef(
            name="roi_missing",
            param_type=ParamType.DECIMAL,
            default=0.05,
            low=None,
            high=0.1,
            space="roi",
        ),
    ]

    errors = OptimizerSearchSpaceService.validate_param_defs(defs)

    assert any("buy.buy_rsi" in error and "minimum" in error for error in errors)
    assert any("stoploss.stoploss" in error and "negative" in error for error in errors)
    assert any("roi.roi_missing" in error and "numeric bounds" in error for error in errors)


def test_trailing_default_offset_constraint_is_validated() -> None:
    defs = [
        ParamDef(
            name="trailing_stop_positive",
            param_type=ParamType.DECIMAL,
            default=0.05,
            low=0.001,
            high=0.50,
            space="trailing",
        ),
        ParamDef(
            name="trailing_stop_positive_offset",
            param_type=ParamType.DECIMAL,
            default=0.02,
            low=0.001,
            high=0.75,
            space="trailing",
        ),
    ]

    errors = OptimizerSearchSpaceService.validate_param_defs(defs)

    assert any("trailing_stop_positive_offset" in error for error in errors)


def test_all_spaces_convert_to_valid_freqtrade_json(tmp_path: Path) -> None:
    defs = OptimizerSearchSpaceService.build_search_space(
        _strategy_params(),
        {
            "params": {
                "roi": {"0": 0.10},
                "stoploss": {"stoploss": -0.10},
                "trailing": {
                    "trailing_stop": True,
                    "trailing_stop_positive": 0.02,
                    "trailing_stop_positive_offset": 0.04,
                },
            }
        },
    )
    candidate = {
        "buy_rsi": 22,
        "sell_rsi": 74,
        "0": 0.08,
        "stoploss": -0.06,
        "trailing_stop": True,
        "trailing_stop_positive": 0.025,
        "trailing_stop_positive_offset": 0.05,
    }

    grouped = _group_candidate_params(candidate, defs)
    params_file = _build_freqtrade_params_file(
        "TestStrategy",
        grouped,
        tmp_path / "missing.json",
    )

    assert params_file["strategy_name"] == "TestStrategy"
    assert params_file["params"]["buy"]["buy_rsi"] == 22
    assert params_file["params"]["sell"]["sell_rsi"] == 74
    assert params_file["params"]["roi"] == {"0": 0.08}
    assert params_file["params"]["stoploss"]["stoploss"] == pytest.approx(-0.06)
    assert params_file["params"]["trailing"]["trailing_stop"] is True
    assert params_file["params"]["trailing"]["trailing_stop_positive"] == pytest.approx(0.025)
