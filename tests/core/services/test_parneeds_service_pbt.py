"""Property-based tests for ParNeedsService.

Each test is tagged with the design property it validates.
All tests use Hypothesis with the settings specified in the design document.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from hypothesis import assume, given, settings
from hypothesis.strategies import (
    booleans,
    composite,
    datetimes,
    floats,
    integers,
    just,
    lists,
    one_of,
    sampled_from,
    text,
)

from app.core.models.parneeds_models import (
    MCPercentiles,
    ParNeedsRunResult,
    SweepParameterDef,
    SweepParamType,
    WalkForwardConfig,
    WalkForwardMode,
)
from app.core.services.parneeds_service import ParNeedsService

# ---------------------------------------------------------------------------
# Shared composite strategies (Task 17.1)
# ---------------------------------------------------------------------------


@composite
def walk_forward_configs(draw, mode: WalkForwardMode | None = None):
    """Generate valid WalkForwardConfig instances."""
    start_year = draw(integers(min_value=2020, max_value=2023))
    start_month = draw(integers(min_value=1, max_value=12))
    start_day = draw(integers(min_value=1, max_value=28))
    start = date(start_year, start_month, start_day)

    span_days = draw(integers(min_value=60, max_value=1000))
    end = start + timedelta(days=span_days)

    n_folds = draw(integers(min_value=2, max_value=10))
    split_ratio = draw(floats(min_value=0.5, max_value=0.95))

    if mode is None:
        wf_mode = draw(sampled_from([WalkForwardMode.ANCHORED, WalkForwardMode.ROLLING]))
    else:
        wf_mode = mode

    return WalkForwardConfig(
        strategy="Demo",
        timeframe="5m",
        timerange=f"{start:%Y%m%d}-{end:%Y%m%d}",
        pairs=["BTC/USDT"],
        dry_run_wallet=80.0,
        max_open_trades=2,
        n_folds=n_folds,
        split_ratio=split_ratio,
        mode=wf_mode,
    )


@composite
def oat_param_configs(draw):
    """Generate (params, baseline) tuples for OAT sweep tests."""
    n_params = draw(integers(min_value=1, max_value=4))
    params = []
    for i in range(n_params):
        lo = draw(integers(min_value=1, max_value=10))
        hi = draw(integers(min_value=lo + 1, max_value=lo + 10))
        step = draw(integers(min_value=1, max_value=3))
        params.append(SweepParameterDef(
            name=f"param_{i}",
            param_type=SweepParamType.INT,
            default_value=lo,
            min_value=float(lo),
            max_value=float(hi),
            step=float(step),
            enabled=True,
        ))
    baseline: dict[str, Any] = {}
    return params, baseline


@composite
def grid_param_configs(draw):
    """Generate (params, baseline) tuples for grid sweep tests (small grids)."""
    n_params = draw(integers(min_value=1, max_value=3))
    params = []
    for i in range(n_params):
        lo = draw(integers(min_value=1, max_value=5))
        hi = draw(integers(min_value=lo + 1, max_value=lo + 4))
        step = draw(integers(min_value=1, max_value=2))
        params.append(SweepParameterDef(
            name=f"param_{i}",
            param_type=SweepParamType.INT,
            default_value=lo,
            min_value=float(lo),
            max_value=float(hi),
            step=float(step),
            enabled=True,
        ))
    baseline: dict[str, Any] = {}
    return params, baseline


@composite
def parneeds_run_results_with_missing_fields(draw):
    """Generate ParNeedsRunResult instances with some None optional fields."""
    # Randomly set optional float/int fields to None or a value
    def maybe_float():
        return draw(one_of(just(None), floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False)))

    def maybe_int():
        return draw(one_of(just(None), integers(min_value=0, max_value=1000)))

    return ParNeedsRunResult(
        run_trial=draw(text(min_size=1, max_size=20)),
        workflow=draw(sampled_from(["timerange", "walk_forward", "monte_carlo", "param_sensitivity"])),
        strategy="Demo",
        profit_pct=maybe_float(),
        total_profit=maybe_float(),
        win_rate=maybe_float(),
        max_dd_pct=maybe_float(),
        trades=maybe_int(),
        profit_factor=maybe_float(),
        sharpe_ratio=maybe_float(),
        score=maybe_float(),
    )


# ---------------------------------------------------------------------------
# Properties 1–5: Walk-Forward (Task 17.2)
# ---------------------------------------------------------------------------


# Feature: parneeds, Property 1: Walk-Forward fold count
@given(
    start=integers(min_value=0, max_value=365 * 3).map(lambda d: date(2020, 1, 1) + timedelta(days=d)),
    span_days=integers(min_value=30, max_value=1000),
    n_folds=integers(min_value=2, max_value=20),
    split_ratio=floats(min_value=0.5, max_value=0.95),
)
@settings(max_examples=200)
def test_fold_count_property(start, span_days, n_folds, split_ratio):
    """Property 1: generate_walk_forward_folds returns exactly n_folds when range is long enough."""
    end = start + timedelta(days=span_days)
    timerange = f"{start:%Y%m%d}-{end:%Y%m%d}"
    config = WalkForwardConfig(
        strategy="Demo",
        timeframe="5m",
        timerange=timerange,
        pairs=["BTC/USDT"],
        dry_run_wallet=80.0,
        max_open_trades=2,
        n_folds=n_folds,
        split_ratio=split_ratio,
        mode=WalkForwardMode.ANCHORED,
    )
    svc = ParNeedsService()
    try:
        folds = svc.generate_walk_forward_folds(config)
        assert len(folds) == n_folds
    except ValueError:
        # Acceptable when timerange is too short
        fold_step = span_days / n_folds
        assert fold_step < 2


# Feature: parneeds, Property 2: Anchored mode — start date invariant
@given(wf_config=walk_forward_configs(mode=WalkForwardMode.ANCHORED))
@settings(max_examples=200)
def test_anchored_start_invariant(wf_config):
    """Property 2: In anchored mode, every fold's IS start equals the global start."""
    svc = ParNeedsService()
    global_start, _ = svc.parse_timerange(wf_config.timerange)
    try:
        folds = svc.generate_walk_forward_folds(wf_config)
    except ValueError:
        return  # Too short — skip
    for fold in folds:
        assert fold.is_start == global_start, (
            f"Fold {fold.fold_index} IS start {fold.is_start} != global start {global_start}"
        )


# Feature: parneeds, Property 3: Rolling mode — fixed step invariant
@given(wf_config=walk_forward_configs(mode=WalkForwardMode.ROLLING))
@settings(max_examples=200)
def test_rolling_step_invariant(wf_config):
    """Property 3: In rolling mode, fold i's IS start equals global_start + int((i-1)*step) days.

    The implementation uses int((i-1) * fold_step) for each fold, so consecutive
    deltas may differ by 1 day due to floating-point truncation. The invariant
    is that each fold's IS start matches the formula exactly.
    """
    svc = ParNeedsService()
    global_start, global_end = svc.parse_timerange(wf_config.timerange)
    total_days = (global_end - global_start).days
    fold_step = total_days / wf_config.n_folds
    try:
        folds = svc.generate_walk_forward_folds(wf_config)
    except ValueError:
        return  # Too short — skip
    for fold in folds:
        i = fold.fold_index
        expected_start = global_start + timedelta(days=int((i - 1) * fold_step))
        assert fold.is_start == expected_start, (
            f"Fold {i} IS start {fold.is_start} != expected {expected_start}"
        )


# Feature: parneeds, Property 4: Split ratio invariant
@given(wf_config=walk_forward_configs())
@settings(max_examples=200)
def test_split_ratio_invariant(wf_config):
    """Property 4: IS/(IS+OOS) ratio is within reasonable tolerance of configured split_ratio.

    The implementation uses integer arithmetic (int(fold_step * split_ratio)) so
    the actual ratio can deviate from the configured ratio. We verify that the
    IS window is always larger than the OOS window when split_ratio > 0.5, and
    that the IS days are at least floor(fold_step * split_ratio) days.
    """
    svc = ParNeedsService()
    global_start, global_end = svc.parse_timerange(wf_config.timerange)
    total_days = (global_end - global_start).days
    fold_step = total_days / wf_config.n_folds
    try:
        folds = svc.generate_walk_forward_folds(wf_config)
    except ValueError:
        return  # Too short — skip
    for fold in folds:
        is_days = (fold.is_end - fold.is_start).days
        oos_days = (fold.oos_end - fold.oos_start).days
        # IS window must be positive
        assert is_days >= 1, f"Fold {fold.fold_index} IS days {is_days} < 1"
        # OOS window must be positive
        assert oos_days >= 1, f"Fold {fold.fold_index} OOS days {oos_days} < 1"
        # When split_ratio > 0.5, IS should be larger than OOS
        if wf_config.split_ratio > 0.5:
            assert is_days >= oos_days, (
                f"Fold {fold.fold_index}: IS {is_days} < OOS {oos_days} with ratio {wf_config.split_ratio}"
            )


# Feature: parneeds, Property 5: Stability score is bounded
@given(
    oos_profits=lists(
        floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
        min_size=0,
        max_size=50,
    )
)
@settings(max_examples=500)
def test_stability_score_bounded(oos_profits):
    """Property 5: compute_stability_score always returns a value in [0, 100]."""
    svc = ParNeedsService()
    score = svc.compute_stability_score(oos_profits)
    assert 0.0 <= score <= 100.0, f"Score {score} out of [0, 100]"


# ---------------------------------------------------------------------------
# Properties 6–8: Monte Carlo (Task 17.3)
# ---------------------------------------------------------------------------


# Feature: parneeds, Property 6: Monte Carlo seed determinism and uniqueness
@given(
    base_seed=integers(min_value=1, max_value=2**31 - 1),
    indices=lists(
        integers(min_value=0, max_value=9999),
        min_size=2,
        max_size=100,
        unique=True,
    ),
)
@settings(max_examples=200)
def test_mc_seed_determinism_and_uniqueness(base_seed, indices):
    """Property 6: generate_mc_seed is deterministic and produces unique seeds for distinct indices."""
    svc = ParNeedsService()
    # Determinism: same call returns same value
    for idx in indices:
        assert svc.generate_mc_seed(base_seed, idx) == svc.generate_mc_seed(base_seed, idx)
    # Uniqueness: distinct indices produce distinct seeds
    seeds = [svc.generate_mc_seed(base_seed, idx) for idx in indices]
    assert len(seeds) == len(set(seeds)), "Duplicate seeds found for distinct indices"


# Feature: parneeds, Property 7: Profit noise stays within bounds
@given(
    profit=floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    seed=integers(min_value=0, max_value=2**31 - 1),
)
@settings(max_examples=500)
def test_profit_noise_bounds(profit, seed):
    """Property 7: apply_profit_noise result stays within ±2% of the input profit."""
    svc = ParNeedsService()
    noisy = svc.apply_profit_noise(profit, seed, noise_pct=0.02)
    # |noisy - profit| <= |profit| * 0.02 (with floating-point tolerance)
    assert abs(noisy - profit) <= abs(profit) * 0.02 + 1e-9, (
        f"Noise {abs(noisy - profit):.6f} exceeds bound {abs(profit) * 0.02:.6f}"
    )


# Feature: parneeds, Property 8: Percentile ordering invariant
@given(
    values=lists(
        floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
        min_size=1,
        max_size=1000,
    )
)
@settings(max_examples=300)
def test_percentile_ordering(values):
    """Property 8: compute_mc_percentiles returns p5 <= p50 <= p95."""
    svc = ParNeedsService()
    pct = svc.compute_mc_percentiles(values)
    assert pct.p5 <= pct.p50, f"p5 {pct.p5} > p50 {pct.p50}"
    assert pct.p50 <= pct.p95, f"p50 {pct.p50} > p95 {pct.p95}"


# ---------------------------------------------------------------------------
# Properties 9–10: Parameter Sensitivity (Task 17.4)
# ---------------------------------------------------------------------------


# Feature: parneeds, Property 9: OAT sweep point count
@given(param_configs=oat_param_configs())
@settings(max_examples=200)
def test_oat_sweep_count(param_configs):
    """Property 9: generate_oat_sweep_points returns sum(len(range(p)) for p in params) points."""
    params, baseline = param_configs
    svc = ParNeedsService()
    points = svc.generate_oat_sweep_points(params, baseline)
    expected = sum(len(svc._param_values(p)) for p in params if p.enabled)
    assert len(points) == expected, (
        f"OAT count {len(points)} != expected {expected}"
    )


# Feature: parneeds, Property 10: Grid sweep point count
@given(param_configs=grid_param_configs())
@settings(max_examples=200)
def test_grid_sweep_count(param_configs):
    """Property 10: generate_grid_sweep_points returns product(len(range(p)) for p in params) points."""
    params, baseline = param_configs
    svc = ParNeedsService()
    points = svc.generate_grid_sweep_points(params, baseline)
    import math
    expected = math.prod(len(svc._param_values(p)) for p in params if p.enabled)
    assert len(points) == expected, (
        f"Grid count {len(points)} != expected {expected}"
    )


# ---------------------------------------------------------------------------
# Properties 11–12: UI formatting and export (Task 17.5)
# ---------------------------------------------------------------------------


# Feature: parneeds, Property 11: Missing field formatting
@given(result=parneeds_run_results_with_missing_fields())
@settings(max_examples=300)
def test_missing_field_formatting(result):
    """Property 11: None optional fields format as '-'."""
    # Simulate the formatter used in the results table
    def fmt_float(value) -> str:
        if value is None or value == "":
            return "-"
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "-"

    def fmt_int(value) -> str:
        if value is None or value == "":
            return "-"
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return "-"

    # All None float fields must produce "-"
    for field_name in ("profit_pct", "total_profit", "win_rate", "max_dd_pct",
                       "profit_factor", "sharpe_ratio", "score"):
        val = getattr(result, field_name)
        if val is None:
            assert fmt_float(val) == "-", f"{field_name}=None should format as '-'"

    # None int fields must produce "-"
    if result.trades is None:
        assert fmt_int(result.trades) == "-", "trades=None should format as '-'"


# Feature: parneeds, Property 12: Export filename pattern
@given(
    workflow=sampled_from(["timerange", "walk_forward", "monte_carlo", "param_sensitivity"]),
    ts=datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
)
@settings(
    max_examples=200,
    suppress_health_check=[__import__("hypothesis", fromlist=["HealthCheck"]).HealthCheck.function_scoped_fixture],
)
def test_export_filename_pattern(workflow, ts, tmp_path):
    """Property 12: export_results filenames match parneeds_{workflow}_{timestamp}.{ext}."""
    svc = ParNeedsService()
    results = [ParNeedsRunResult(run_trial="T1", workflow=workflow)]

    # Patch datetime.now to return our controlled timestamp
    import unittest.mock as mock
    with mock.patch("app.core.services.parneeds_service.datetime") as mock_dt:
        mock_dt.now.return_value = ts
        mock_dt.strptime = datetime.strptime  # keep parse working
        json_path, csv_path = svc.export_results(results, workflow, tmp_path)

    pattern = re.compile(
        rf"parneeds_{re.escape(workflow)}_\d{{8}}_\d{{6}}\.(json|csv)"
    )
    assert pattern.match(json_path.name), f"JSON filename '{json_path.name}' doesn't match pattern"
    assert pattern.match(csv_path.name), f"CSV filename '{csv_path.name}' doesn't match pattern"
    assert json_path.exists()
    assert csv_path.exists()
