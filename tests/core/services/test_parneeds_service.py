from __future__ import annotations

import csv
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from app.core.models.parneeds_models import ParNeedsConfig
from app.core.services.parneeds_service import ParNeedsService

from app.core.models.parneeds_models import (
    WalkForwardConfig,
    WalkForwardFold,
    WalkForwardMode,
    MCPercentiles,
    SweepParameterDef,
    SweepParamType,
    ParNeedsRunResult,
)


def _dates(start: str, count: int, step_minutes: int = 5):
    current = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return [current + timedelta(minutes=step_minutes * i) for i in range(count)]


def test_default_timerange_ends_yesterday() -> None:
    svc = ParNeedsService()

    assert svc.normalize_timerange(None, today=date(2026, 4, 25)) == "20240101-20260424"


def test_timerange_windows_are_seeded_and_cover_range() -> None:
    svc = ParNeedsService()
    cfg = ParNeedsConfig(
        strategy="Demo",
        timeframe="5m",
        timerange="20240101-20240201",
        pairs=["BTC/USDT"],
        seed=123,
    )

    first = svc.generate_timerange_windows(cfg)
    second = svc.generate_timerange_windows(cfg)

    assert [w.timerange for w in first] == [w.timerange for w in second]
    assert {w.label for w in first} == {"2w", "1m"}

    for label in ("2w", "1m"):
        ordered = sorted((w for w in first if w.label == label), key=lambda w: w.start)
        assert ordered[0].start == date(2024, 1, 1)
        assert ordered[-1].end == date(2024, 2, 1)
        assert all(left.end == right.start for left, right in zip(ordered, ordered[1:]))


def test_validate_pair_coverage_complete() -> None:
    svc = ParNeedsService()
    frame = pd.DataFrame({"date": _dates("2024-01-01", 288)})
    svc._load_history = lambda *args, **kwargs: frame

    report = svc.validate_pair_coverage(
        data_dir=Path("/tmp/data/binance"),
        pair="BTC/USDT",
        timeframe="5m",
        timerange="20240101-20240102",
        start=date(2024, 1, 1),
        end=date(2024, 1, 2),
    )

    assert report.is_complete
    assert report.actual_candles == 288
    assert report.expected_candles == 288


def test_validate_pair_coverage_reports_start_end_and_gap() -> None:
    svc = ParNeedsService()
    candles = _dates("2024-01-01", 288)
    sparse = candles[3:100] + candles[130:250]
    frame = pd.DataFrame({"date": sparse})
    svc._load_history = lambda *args, **kwargs: frame

    report = svc.validate_pair_coverage(
        data_dir=Path("/tmp/data/binance"),
        pair="ETH/USDT",
        timeframe="5m",
        timerange="20240101-20240102",
        start=date(2024, 1, 1),
        end=date(2024, 1, 2),
    )

    assert not report.is_complete
    assert "missing start candles" in report.missing_reasons
    assert "missing end candles" in report.missing_reasons
    assert any("internal gap" in reason for reason in report.missing_reasons)


def test_validate_pair_coverage_reports_load_failure() -> None:
    svc = ParNeedsService()

    def _raise(*args, **kwargs):
        raise RuntimeError("bad data")

    svc._load_history = _raise

    report = svc.validate_pair_coverage(
        data_dir=Path("/tmp/data/binance"),
        pair="ADA/USDT",
        timeframe="5m",
        timerange="20240101-20240102",
        start=date(2024, 1, 1),
        end=date(2024, 1, 2),
    )

    assert not report.is_complete
    assert report.missing_reasons == ["load failed: bad data"]


def test_invalid_timerange_rejected() -> None:
    svc = ParNeedsService()

    with pytest.raises(ValueError):
        svc.normalize_timerange("20240201-20240101")


# ---------------------------------------------------------------------------
# Walk-Forward tests (Task 16.1)
# ---------------------------------------------------------------------------

def _wf_config(
    timerange: str = "20240101-20241231",
    n_folds: int = 5,
    split_ratio: float = 0.80,
    mode: WalkForwardMode = WalkForwardMode.ANCHORED,
) -> WalkForwardConfig:
    return WalkForwardConfig(
        strategy="Demo",
        timeframe="5m",
        timerange=timerange,
        pairs=["BTC/USDT"],
        dry_run_wallet=80.0,
        max_open_trades=2,
        n_folds=n_folds,
        split_ratio=split_ratio,
        mode=mode,
    )


def test_wf_fold_count_anchored() -> None:
    svc = ParNeedsService()
    folds = svc.generate_walk_forward_folds(_wf_config(n_folds=5))
    assert len(folds) == 5


def test_wf_fold_count_rolling() -> None:
    svc = ParNeedsService()
    folds = svc.generate_walk_forward_folds(_wf_config(n_folds=4, mode=WalkForwardMode.ROLLING))
    assert len(folds) == 4


def test_wf_anchored_all_folds_share_is_start() -> None:
    svc = ParNeedsService()
    folds = svc.generate_walk_forward_folds(_wf_config(mode=WalkForwardMode.ANCHORED))
    global_start = date(2024, 1, 1)
    for fold in folds:
        assert fold.is_start == global_start, f"Fold {fold.fold_index} IS start mismatch"


def test_wf_rolling_is_start_advances_by_step() -> None:
    svc = ParNeedsService()
    folds = svc.generate_walk_forward_folds(
        _wf_config(timerange="20240101-20241231", n_folds=4, mode=WalkForwardMode.ROLLING)
    )
    total_days = (date(2024, 12, 31) - date(2024, 1, 1)).days
    step = total_days / 4
    for i in range(len(folds) - 1):
        delta = (folds[i + 1].is_start - folds[i].is_start).days
        assert delta == int(step), f"Step mismatch between fold {i+1} and {i+2}"


def test_wf_raises_value_error_when_too_short() -> None:
    svc = ParNeedsService()
    with pytest.raises(ValueError, match="too short"):
        svc.generate_walk_forward_folds(_wf_config(timerange="20240101-20240103", n_folds=10))


def test_wf_fold_indices_are_one_based() -> None:
    svc = ParNeedsService()
    folds = svc.generate_walk_forward_folds(_wf_config(n_folds=3))
    assert [f.fold_index for f in folds] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Stability score tests (Task 16.2)
# ---------------------------------------------------------------------------


def test_stability_score_empty_returns_zero() -> None:
    svc = ParNeedsService()
    assert svc.compute_stability_score([]) == 0.0


def test_stability_score_all_positive_above_50() -> None:
    svc = ParNeedsService()
    score = svc.compute_stability_score([1.0, 2.0, 3.0, 4.0, 5.0])
    assert score > 50.0


def test_stability_score_all_negative_below_50() -> None:
    svc = ParNeedsService()
    score = svc.compute_stability_score([-1.0, -2.0, -3.0])
    assert score < 50.0


def test_stability_score_bounded() -> None:
    svc = ParNeedsService()
    for profits in [[], [0.0], [1e9, -1e9], [0.1] * 100]:
        score = svc.compute_stability_score(profits)
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# MC seed, noise, percentile tests (Task 16.3)
# ---------------------------------------------------------------------------


def test_mc_seed_determinism() -> None:
    svc = ParNeedsService()
    assert svc.generate_mc_seed(12345, 0) == svc.generate_mc_seed(12345, 0)
    assert svc.generate_mc_seed(99999, 42) == svc.generate_mc_seed(99999, 42)


def test_mc_seed_different_indices_differ() -> None:
    svc = ParNeedsService()
    seeds = {svc.generate_mc_seed(1, i) for i in range(100)}
    assert len(seeds) == 100


def test_apply_profit_noise_within_bounds() -> None:
    svc = ParNeedsService()
    profit = 100.0
    for seed in range(50):
        noisy = svc.apply_profit_noise(profit, seed, noise_pct=0.02)
        assert abs(noisy - profit) <= profit * 0.02 + 1e-9


def test_apply_profit_noise_zero_profit() -> None:
    svc = ParNeedsService()
    assert svc.apply_profit_noise(0.0, 42) == 0.0


def test_compute_mc_percentiles_ordering() -> None:
    svc = ParNeedsService()
    pct = svc.compute_mc_percentiles([5.0, 1.0, 3.0, 2.0, 4.0])
    assert pct.p5 <= pct.p50 <= pct.p95


def test_compute_mc_percentiles_single_value() -> None:
    svc = ParNeedsService()
    pct = svc.compute_mc_percentiles([7.0])
    assert pct.p5 == pct.p50 == pct.p95 == 7.0


def test_compute_mc_percentiles_empty_raises() -> None:
    svc = ParNeedsService()
    with pytest.raises(ValueError):
        svc.compute_mc_percentiles([])


# ---------------------------------------------------------------------------
# Sweep point tests (Task 16.4)
# ---------------------------------------------------------------------------


def _int_param(name: str, lo: float, hi: float, step: float) -> SweepParameterDef:
    return SweepParameterDef(
        name=name,
        param_type=SweepParamType.INT,
        default_value=None,
        min_value=lo,
        max_value=hi,
        step=step,
        enabled=True,
    )


def _cat_param(name: str, values: list) -> SweepParameterDef:
    return SweepParameterDef(
        name=name,
        param_type=SweepParamType.CATEGORICAL,
        default_value=None,
        values=values,
        enabled=True,
    )


def test_oat_sweep_count_single_param() -> None:
    svc = ParNeedsService()
    param = _int_param("rsi_period", 10, 20, 2)  # 10,12,14,16,18,20 → 6 values
    points = svc.generate_oat_sweep_points([param], baseline={})
    assert len(points) == 6


def test_oat_sweep_count_two_params() -> None:
    svc = ParNeedsService()
    p1 = _int_param("a", 1, 3, 1)   # 3 values
    p2 = _cat_param("b", ["x", "y"])  # 2 values
    points = svc.generate_oat_sweep_points([p1, p2], baseline={})
    assert len(points) == 5  # 3 + 2


def test_oat_sweep_disabled_param_excluded() -> None:
    svc = ParNeedsService()
    p1 = _int_param("a", 1, 3, 1)
    p2 = SweepParameterDef(
        name="b", param_type=SweepParamType.INT, default_value=None,
        min_value=1, max_value=5, step=1, enabled=False,
    )
    points = svc.generate_oat_sweep_points([p1, p2], baseline={})
    assert len(points) == 3


def test_oat_sweep_indices_sequential() -> None:
    svc = ParNeedsService()
    param = _int_param("x", 0, 4, 1)
    points = svc.generate_oat_sweep_points([param], baseline={})
    assert [p.index for p in points] == list(range(5))


def test_grid_sweep_count_cartesian_product() -> None:
    svc = ParNeedsService()
    p1 = _int_param("a", 1, 3, 1)   # 3 values
    p2 = _int_param("b", 1, 2, 1)   # 2 values
    points = svc.generate_grid_sweep_points([p1, p2], baseline={})
    assert len(points) == 6  # 3 × 2


def test_grid_sweep_empty_when_no_enabled() -> None:
    svc = ParNeedsService()
    p = SweepParameterDef(
        name="x", param_type=SweepParamType.INT, default_value=None,
        min_value=1, max_value=5, step=1, enabled=False,
    )
    assert svc.generate_grid_sweep_points([p], baseline={}) == []


# ---------------------------------------------------------------------------
# Export tests (Task 16.5)
# ---------------------------------------------------------------------------


def test_export_creates_json_and_csv(tmp_path: Path) -> None:
    svc = ParNeedsService()
    results = [
        ParNeedsRunResult(run_trial="Fold 1 OOS", workflow="walk_forward", strategy="Demo"),
    ]
    json_path, csv_path = svc.export_results(results, "walk_forward", tmp_path)
    assert json_path.exists()
    assert csv_path.exists()


def test_export_filename_pattern(tmp_path: Path) -> None:
    svc = ParNeedsService()
    results = [ParNeedsRunResult(run_trial="Iter 1", workflow="monte_carlo")]
    json_path, csv_path = svc.export_results(results, "monte_carlo", tmp_path)
    pattern = re.compile(r"parneeds_monte_carlo_\d{8}_\d{6}\.(json|csv)")
    assert pattern.match(json_path.name)
    assert pattern.match(csv_path.name)


def test_export_json_content(tmp_path: Path) -> None:
    svc = ParNeedsService()
    results = [
        ParNeedsRunResult(
            run_trial="Sweep 1",
            workflow="param_sensitivity",
            strategy="MyStrat",
            profit_pct=5.5,
        )
    ]
    json_path, _ = svc.export_results(results, "param_sensitivity", tmp_path)
    data = json.loads(json_path.read_text())
    assert len(data) == 1
    assert data[0]["strategy"] == "MyStrat"
    assert data[0]["profit_pct"] == 5.5


def test_export_csv_has_correct_columns(tmp_path: Path) -> None:
    svc = ParNeedsService()
    results = [ParNeedsRunResult(run_trial="T1", workflow="timerange")]
    _, csv_path = svc.export_results(results, "timerange", tmp_path)
    with csv_path.open() as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
    expected = [
        "run_trial", "workflow", "strategy", "pairs", "timeframe", "timerange",
        "profit_pct", "total_profit", "win_rate", "max_dd_pct", "trades",
        "profit_factor", "sharpe_ratio", "score", "status", "result_path", "log_path",
    ]
    assert headers == expected
