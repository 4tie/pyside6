from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from app.core.models.parneeds_models import ParNeedsConfig
from app.core.services.parneeds_service import ParNeedsService


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
