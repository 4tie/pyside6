"""Core logic for ParNeeds validation workflows."""
from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from app.core.freqtrade.resolvers.runtime_resolver import find_run_paths
from app.core.models.parneeds_models import (
    CandleCoverageReport,
    ParNeedsConfig,
    ParNeedsWindow,
)
from app.core.models.settings_models import AppSettings
from app.core.parsing.json_parser import parse_json_file
from app.core.utils.app_logger import get_logger

_log = get_logger("services.parneeds")

_DEFAULT_START = date(2024, 1, 1)
_WINDOW_SPECS = ((14, "2w"), (30, "1m"))
_TF_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1d": 86400,
}


class ParNeedsService:
    """Planning and validation helpers for ParNeeds workflows."""

    def normalize_timerange(
        self,
        timerange: Optional[str],
        *,
        today: Optional[date] = None,
    ) -> str:
        """Return the user timerange or the ParNeeds default timerange."""
        if timerange and timerange.strip():
            self.parse_timerange(timerange.strip())
            return timerange.strip()

        current = today or date.today()
        end = current - timedelta(days=1)
        if end <= _DEFAULT_START:
            end = _DEFAULT_START + timedelta(days=1)
        return f"{_DEFAULT_START:%Y%m%d}-{end:%Y%m%d}"

    def parse_timerange(self, timerange: str) -> tuple[date, date]:
        """Parse ``YYYYMMDD-YYYYMMDD`` into start/end dates."""
        try:
            start_s, end_s = timerange.split("-", 1)
            start = datetime.strptime(start_s, "%Y%m%d").date()
            end = datetime.strptime(end_s, "%Y%m%d").date()
        except ValueError as exc:
            raise ValueError("timerange must use YYYYMMDD-YYYYMMDD") from exc

        if end <= start:
            raise ValueError("timerange end must be after start")
        return start, end

    def generate_timerange_windows(self, config: ParNeedsConfig) -> list[ParNeedsWindow]:
        """Generate reproducible shuffled 2-week and 1-month windows."""
        timerange = self.normalize_timerange(config.timerange)
        start, end = self.parse_timerange(timerange)

        windows: list[ParNeedsWindow] = []
        for span_days, label in _WINDOW_SPECS:
            cursor = start
            while cursor < end:
                window_end = min(cursor + timedelta(days=span_days), end)
                days = max(1, (window_end - cursor).days)
                windows.append(
                    ParNeedsWindow(
                        timerange=f"{cursor:%Y%m%d}-{window_end:%Y%m%d}",
                        start=cursor,
                        end=window_end,
                        days=days,
                        label=label,
                    )
                )
                cursor = window_end

        rng = random.Random(config.seed)
        rng.shuffle(windows)
        return windows

    def validate_candle_coverage(
        self,
        settings: AppSettings,
        config: ParNeedsConfig,
    ) -> list[CandleCoverageReport]:
        """Validate OHLCV coverage for all selected pairs in the run range."""
        timerange = self.normalize_timerange(config.timerange)
        start, end = self.parse_timerange(timerange)
        paths = find_run_paths(settings)
        data_dir = self.resolve_data_dir_from_paths(
            Path(paths.user_data_dir),
            Path(paths.config_file),
        )
        data_format = self._data_format_ohlcv(Path(paths.config_file))
        return [
            self.validate_pair_coverage(
                data_dir=data_dir,
                pair=pair,
                timeframe=config.timeframe,
                timerange=timerange,
                start=start,
                end=end,
                data_format=data_format,
            )
            for pair in config.pairs
        ]

    def validate_pair_coverage(
        self,
        *,
        data_dir: Path,
        pair: str,
        timeframe: str,
        timerange: str,
        start: date,
        end: date,
        data_format: Optional[str] = None,
    ) -> CandleCoverageReport:
        """Validate one pair/timeframe against local Freqtrade candle data."""
        step = self.timeframe_seconds(timeframe)
        expected = self.expected_candle_count(start, end, step)
        reasons: list[str] = []

        try:
            history = self._load_history(data_dir, pair, timeframe, timerange, data_format)
        except Exception as exc:
            _log.warning("Could not load candle history for %s %s: %s", pair, timeframe, exc)
            return CandleCoverageReport(
                pair=pair,
                timeframe=timeframe,
                timerange=timerange,
                expected_candles=expected,
                missing_reasons=[f"load failed: {exc}"],
            )

        timestamps = self._extract_timestamps(history)
        if not timestamps:
            return CandleCoverageReport(
                pair=pair,
                timeframe=timeframe,
                timerange=timerange,
                expected_candles=expected,
                missing_reasons=["no candles found"],
            )

        timestamps.sort()
        start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time.min, tzinfo=timezone.utc)
        tolerance = timedelta(seconds=step)

        if timestamps[0] > start_dt:
            reasons.append("missing start candles")
        if timestamps[-1] < end_dt - tolerance:
            reasons.append("missing end candles")

        gap_count = sum(
            1
            for left, right in zip(timestamps, timestamps[1:])
            if (right - left).total_seconds() > step * 1.5
        )
        if gap_count:
            reasons.append(f"{gap_count} internal gap(s)")
        if len(timestamps) < expected:
            reasons.append("candle count below expected")

        return CandleCoverageReport(
            pair=pair,
            timeframe=timeframe,
            timerange=timerange,
            first_candle=self._format_dt(timestamps[0]),
            last_candle=self._format_dt(timestamps[-1]),
            expected_candles=expected,
            actual_candles=len(timestamps),
            gap_count=gap_count,
            missing_reasons=reasons,
        )

    def resolve_data_dir(self, settings: AppSettings) -> Path:
        """Return the Freqtrade exchange data directory for OHLCV loading."""
        paths = find_run_paths(settings)
        return self.resolve_data_dir_from_paths(Path(paths.user_data_dir), Path(paths.config_file))

    def resolve_data_dir_from_paths(self, user_data: Path, config_path: Path) -> Path:
        """Return the exchange data directory from resolved run paths."""
        data_root = user_data / "data"
        exchange_name = self._exchange_name(config_path)
        if exchange_name:
            return data_root / exchange_name

        if data_root.exists():
            exchange_dirs = [p for p in data_root.iterdir() if p.is_dir()]
            if len(exchange_dirs) == 1:
                return exchange_dirs[0]
        return data_root

    def timeframe_seconds(self, timeframe: str) -> int:
        """Return the candle interval in seconds for a known Freqtrade timeframe."""
        if timeframe not in _TF_SECONDS:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return _TF_SECONDS[timeframe]

    def expected_candle_count(self, start: date, end: date, step_seconds: int) -> int:
        """Return expected candle count for the half-open date range."""
        seconds = (
            datetime.combine(end, time.min) - datetime.combine(start, time.min)
        ).total_seconds()
        return max(1, int(seconds // step_seconds))

    def _exchange_name(self, config_path: Path) -> str:
        try:
            config = parse_json_file(config_path)
        except Exception:
            return ""
        exchange = config.get("exchange", {})
        if not isinstance(exchange, dict):
            return ""
        return str(exchange.get("name") or "").strip()

    def _data_format_ohlcv(self, config_path: Path) -> Optional[str]:
        try:
            config = parse_json_file(config_path)
        except Exception:
            return None
        value = config.get("dataformat_ohlcv") or config.get("data_format_ohlcv")
        return str(value).strip() if value else None

    def _load_history(
        self,
        data_dir: Path,
        pair: str,
        timeframe: str,
        timerange: str,
        data_format: Optional[str] = None,
    ):
        from freqtrade.configuration.timerange import TimeRange
        from freqtrade.data.history import load_pair_history

        return load_pair_history(
            pair=pair,
            timeframe=timeframe,
            datadir=data_dir,
            timerange=TimeRange.parse_timerange(timerange),
            fill_up_missing=False,
            drop_incomplete=False,
            data_format=data_format,
        )

    def _extract_timestamps(self, history) -> list[datetime]:
        if history is None:
            return []

        raw_values: Iterable = []
        if hasattr(history, "empty") and history.empty:
            return []
        if hasattr(history, "columns") and "date" in history.columns:
            raw_values = history["date"].tolist()
        elif hasattr(history, "index"):
            raw_values = list(history.index)

        timestamps: list[datetime] = []
        for value in raw_values:
            dt = self._to_utc_datetime(value)
            if dt is not None:
                timestamps.append(dt)
        return timestamps

    def _to_utc_datetime(self, value) -> Optional[datetime]:
        if isinstance(value, datetime):
            dt = value
        elif hasattr(value, "to_pydatetime"):
            dt = value.to_pydatetime()
        else:
            return None

        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _format_dt(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
