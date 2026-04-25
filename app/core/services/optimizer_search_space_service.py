"""Core search-space generation for strategy optimizer parameters.

This service converts parsed strategy metadata plus optional live Freqtrade
strategy JSON into a unified ``ParamDef`` list.  It intentionally lives in
core so desktop and future web surfaces share the same parameter schema,
validation rules, and downstream optimizer conversion path.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.core.models.optimizer_models import ParamDef, ParamType, StrategyParams
from app.core.parsing.json_parser import parse_json_file
from app.core.parsing.strategy_py_parser import parse_strategy_py
from app.core.utils.app_logger import get_logger

_log = get_logger("services.optimizer_search_space")

SPACE_ORDER = {
    "buy": 0,
    "sell": 1,
    "roi": 2,
    "stoploss": 3,
    "trailing": 4,
}

SPACE_PARAM_ORDER = {
    "trailing_stop": 0,
    "trailing_stop_positive": 1,
    "trailing_stop_positive_offset": 2,
    "trailing_only_offset_is_reached": 3,
}


class OptimizerSearchSpaceService:
    """Build and validate optimizer ``ParamDef`` search spaces."""

    @staticmethod
    def build_search_space(
        strategy_params: StrategyParams,
        live_strategy_json: Optional[Dict[str, Any]] = None,
    ) -> List[ParamDef]:
        """Return all optimizer spaces as a flat, predictably sorted list."""
        params_block = _params_block(live_strategy_json or {})
        defs: List[ParamDef] = []

        defs.extend(_copy_params(strategy_params.buy_params.values(), "buy"))
        defs.extend(_copy_params(strategy_params.sell_params.values(), "sell"))
        defs.extend(_build_roi_defs(strategy_params, params_block))
        defs.extend(_build_stoploss_defs(strategy_params, params_block))
        defs.extend(_build_trailing_defs(strategy_params, params_block))

        return sorted(defs, key=_sort_key)

    @staticmethod
    def build_search_space_from_files(
        strategy_py_path: Path,
        strategy_json_path: Optional[Path] = None,
    ) -> tuple[StrategyParams, List[ParamDef]]:
        """Parse strategy files and return strategy metadata plus ParamDefs."""
        strategy_params = parse_strategy_py(strategy_py_path)
        live_json: Dict[str, Any] = {}
        if strategy_json_path and strategy_json_path.exists():
            try:
                live_json = parse_json_file(strategy_json_path)
            except Exception as exc:  # noqa: BLE001
                _log.warning("Could not parse strategy params JSON %s: %s", strategy_json_path, exc)
        return strategy_params, OptimizerSearchSpaceService.build_search_space(strategy_params, live_json)

    @staticmethod
    def validate_param_defs(param_defs: Sequence[ParamDef]) -> List[str]:
        """Return human-readable validation errors for enabled ParamDefs."""
        errors: List[str] = []
        by_name = {param.name: param for param in param_defs}

        for param in param_defs:
            if not param.enabled:
                continue
            if param.param_type not in (ParamType.INT, ParamType.DECIMAL):
                continue

            if param.low is None or param.high is None:
                errors.append(f"{param.space}.{param.name}: numeric bounds are required.")
                continue
            if not (_is_finite_number(param.low) and _is_finite_number(param.high)):
                errors.append(f"{param.space}.{param.name}: bounds must be finite numbers.")
                continue
            if float(param.low) >= float(param.high):
                errors.append(f"{param.space}.{param.name}: minimum must be less than maximum.")
            if param.space == "stoploss" and (float(param.low) >= 0 or float(param.high) >= 0):
                errors.append(f"{param.space}.{param.name}: stoploss bounds must be negative.")

        trailing_positive = by_name.get("trailing_stop_positive")
        trailing_offset = by_name.get("trailing_stop_positive_offset")
        if trailing_positive and trailing_offset and trailing_positive.enabled and trailing_offset.enabled:
            positive_default = _to_float(trailing_positive.default)
            offset_default = _to_float(trailing_offset.default)
            if (
                positive_default is not None
                and offset_default is not None
                and offset_default < positive_default
            ):
                errors.append(
                    "trailing.trailing_stop_positive_offset: default must be greater than "
                    "or equal to trailing_stop_positive."
                )

        return errors


def _params_block(data: Dict[str, Any]) -> Dict[str, Any]:
    params = data.get("params", data)
    return params if isinstance(params, dict) else {}


def _copy_params(params: Iterable[ParamDef], space: str) -> List[ParamDef]:
    return [param.model_copy(update={"space": space}) for param in params]


def _build_roi_defs(strategy_params: StrategyParams, params_block: Dict[str, Any]) -> List[ParamDef]:
    roi = params_block.get("roi")
    if roi is None:
        roi = params_block.get("minimal_roi", strategy_params.minimal_roi)
    if not isinstance(roi, dict):
        return []

    defs: List[ParamDef] = []
    for key in sorted(roi.keys(), key=_roi_key_sort):
        value = _to_float(roi.get(key))
        if value is None:
            continue
        high = max(1.0, round(value * 3.0, 6))
        defs.append(
            ParamDef(
                name=str(key),
                param_type=ParamType.DECIMAL,
                default=value,
                low=0.0,
                high=high,
                space="roi",
            )
        )
    return defs


def _build_stoploss_defs(strategy_params: StrategyParams, params_block: Dict[str, Any]) -> List[ParamDef]:
    raw = params_block.get("stoploss")
    if isinstance(raw, dict):
        raw = raw.get("stoploss")
    value = _to_float(raw)
    if value is None:
        value = float(strategy_params.stoploss)
    high = min(-0.001, round(value / 2.0, 6)) if value < 0 else -0.01
    low = max(-0.99, round(value * 3.0, 6)) if value < 0 else -0.50
    if low >= high:
        low, high = -0.50, -0.01
    return [
        ParamDef(
            name="stoploss",
            param_type=ParamType.DECIMAL,
            default=value,
            low=low,
            high=high,
            space="stoploss",
        )
    ]


def _build_trailing_defs(strategy_params: StrategyParams, params_block: Dict[str, Any]) -> List[ParamDef]:
    trailing = params_block.get("trailing")
    if not isinstance(trailing, dict):
        trailing = {
            key: params_block[key]
            for key in (
                "trailing_stop",
                "trailing_stop_positive",
                "trailing_stop_positive_offset",
                "trailing_only_offset_is_reached",
            )
            if key in params_block
        }

    has_strategy_trailing = (
        strategy_params.trailing_stop
        or strategy_params.trailing_stop_positive is not None
        or strategy_params.trailing_stop_positive_offset is not None
    )
    if not trailing and not has_strategy_trailing:
        return []

    defs: List[ParamDef] = []

    if "trailing_stop" in trailing or strategy_params.trailing_stop:
        defs.append(
            ParamDef(
                name="trailing_stop",
                param_type=ParamType.BOOLEAN,
                default=bool(trailing.get("trailing_stop", strategy_params.trailing_stop)),
                space="trailing",
            )
        )

    positive = _to_float(trailing.get("trailing_stop_positive"))
    if positive is None:
        positive = strategy_params.trailing_stop_positive
    if positive is not None:
        defs.append(
            ParamDef(
                name="trailing_stop_positive",
                param_type=ParamType.DECIMAL,
                default=float(positive),
                low=0.001,
                high=max(0.50, round(float(positive) * 3.0, 6)),
                space="trailing",
            )
        )

    offset = _to_float(trailing.get("trailing_stop_positive_offset"))
    if offset is None:
        offset = strategy_params.trailing_stop_positive_offset
    if offset is not None:
        defs.append(
            ParamDef(
                name="trailing_stop_positive_offset",
                param_type=ParamType.DECIMAL,
                default=float(offset),
                low=0.001,
                high=max(0.75, round(float(offset) * 3.0, 6)),
                space="trailing",
            )
        )

    if "trailing_only_offset_is_reached" in trailing:
        defs.append(
            ParamDef(
                name="trailing_only_offset_is_reached",
                param_type=ParamType.BOOLEAN,
                default=bool(trailing.get("trailing_only_offset_is_reached")),
                space="trailing",
            )
        )

    return defs


def _sort_key(param: ParamDef) -> tuple[int, int, str]:
    param_order = _roi_key_sort(param.name) if param.space == "roi" else SPACE_PARAM_ORDER.get(param.name, 99)
    return (SPACE_ORDER.get(param.space, 99), param_order, param.name)


def _roi_key_sort(key: Any) -> int:
    try:
        return int(str(key))
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _is_finite_number(value: Any) -> bool:
    return _to_float(value) is not None
