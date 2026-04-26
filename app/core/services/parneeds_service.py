"""Core logic for ParNeeds validation workflows."""
from __future__ import annotations

import ast
import csv
import dataclasses
import itertools
import json
import random
import statistics
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from app.core.freqtrade.resolvers.runtime_resolver import find_run_paths
from app.core.models.parneeds_models import (
    CandleCoverageReport,
    MCPercentiles,
    MCSummary,
    MonteCarloConfig,
    ParNeedsConfig,
    ParNeedsRunResult,
    ParNeedsWindow,
    SweepParameterDef,
    SweepParamType,
    SweepPoint,
    SweepPointResult,
    WalkForwardConfig,
    WalkForwardFold,
    WalkForwardMode,
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

    # ------------------------------------------------------------------
    # Walk-Forward methods
    # ------------------------------------------------------------------

    def generate_walk_forward_folds(
        self,
        config: WalkForwardConfig,
    ) -> list[WalkForwardFold]:
        """Generate in-sample / out-of-sample fold pairs for walk-forward validation.

        Raises ValueError when the timerange is too short to produce the
        requested number of folds.
        """
        global_start, global_end = self.parse_timerange(config.timerange)
        total_days = (global_end - global_start).days

        fold_step = total_days / config.n_folds
        if fold_step < 2:
            raise ValueError(
                f"Timerange is too short ({total_days} days) to produce "
                f"{config.n_folds} folds — each fold would be less than 2 days. "
                "Use a longer timerange or fewer folds."
            )

        folds: list[WalkForwardFold] = []
        for i in range(1, config.n_folds + 1):
            if config.mode == WalkForwardMode.ANCHORED:
                is_start = global_start
                is_end = global_start + timedelta(
                    days=int(fold_step * i * config.split_ratio)
                )
            else:  # ROLLING
                is_start = global_start + timedelta(days=int((i - 1) * fold_step))
                is_end = is_start + timedelta(days=int(fold_step * config.split_ratio))

            oos_start = is_end
            oos_days = max(1, int(fold_step * (1 - config.split_ratio)))
            oos_end = oos_start + timedelta(days=oos_days)

            folds.append(
                WalkForwardFold(
                    fold_index=i,
                    is_timerange=f"{is_start:%Y%m%d}-{is_end:%Y%m%d}",
                    oos_timerange=f"{oos_start:%Y%m%d}-{oos_end:%Y%m%d}",
                    is_start=is_start,
                    is_end=is_end,
                    oos_start=oos_start,
                    oos_end=oos_end,
                )
            )

        return folds

    def compute_stability_score(self, oos_profits: list[float]) -> float:
        """Compute a stability score in [0, 100] from a list of OOS profits.

        Score = (positive_fold_ratio * 70) + (consistency_bonus * 30)
        """
        if not oos_profits:
            return 0.0

        n = len(oos_profits)
        positive_count = sum(1 for p in oos_profits if p > 0)
        positive_fold_ratio = positive_count / n

        mean = statistics.mean(oos_profits)
        if n < 2:
            std_dev = 0.0
        else:
            std_dev = statistics.stdev(oos_profits)

        if std_dev == 0.0:
            # Perfectly consistent (all values identical)
            consistency_bonus = 1.0
        elif mean == 0.0:
            consistency_bonus = 0.0
        else:
            cv = abs(std_dev / mean)
            consistency_bonus = max(0.0, 1.0 - min(cv, 1.0))

        score = (positive_fold_ratio * 70.0) + (consistency_bonus * 30.0)
        return max(0.0, min(100.0, score))

    # ------------------------------------------------------------------
    # Monte Carlo methods
    # ------------------------------------------------------------------

    def generate_mc_seed(self, base_seed: int, iteration_index: int) -> int:
        """Derive a unique, deterministic seed for a Monte Carlo iteration.

        Uses: (base_seed * 1_000_003 + iteration_index) % (2**31 - 1)
        """
        return (base_seed * 1_000_003 + iteration_index) % (2**31 - 1)

    def apply_profit_noise(
        self,
        profit: float,
        seed: int,
        noise_pct: float = 0.02,
    ) -> float:
        """Apply a small random multiplier to a profit value.

        The multiplier is drawn uniformly from [1 - noise_pct, 1 + noise_pct]
        using a seeded RNG so results are reproducible.
        """
        rng = random.Random(seed)
        multiplier = rng.uniform(1.0 - noise_pct, 1.0 + noise_pct)
        return profit * multiplier

    def compute_mc_percentiles(self, values: list[float]) -> MCPercentiles:
        """Compute p5, p50, p95 percentiles from a list of float values.

        Raises ValueError for an empty list.
        """
        if not values:
            raise ValueError("Cannot compute percentiles of an empty list")

        sorted_vals = sorted(values)
        n = len(sorted_vals)

        def _percentile(p: float) -> float:
            # Linear interpolation (same as numpy's default)
            idx = p * (n - 1)
            lo = int(idx)
            hi = lo + 1
            if hi >= n:
                return sorted_vals[-1]
            frac = idx - lo
            return sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo])

        return MCPercentiles(
            p5=_percentile(0.05),
            p50=_percentile(0.50),
            p95=_percentile(0.95),
        )

    # ------------------------------------------------------------------
    # Parameter Sensitivity methods
    # ------------------------------------------------------------------

    _FIXED_BACKTEST_PARAMS = (
        "stoploss",
        "roi_table",
        "trailing_stop",
        "trailing_stop_positive",
        "trailing_stop_positive_offset",
        "max_open_trades",
    )

    _PARAM_CLASS_TO_TYPE: dict[str, SweepParamType] = {
        "IntParameter": SweepParamType.INT,
        "DecimalParameter": SweepParamType.DECIMAL,
        "CategoricalParameter": SweepParamType.CATEGORICAL,
        "BooleanParameter": SweepParamType.BOOLEAN,
    }

    def discover_strategy_parameters(
        self,
        strategy_path: Path,
    ) -> list[SweepParameterDef]:
        """Parse a Freqtrade strategy file and return sweepable parameter definitions.

        Returns an empty list when the file does not exist or contains no
        recognised parameters — never raises.
        """
        if not strategy_path.exists():
            return []

        try:
            source = strategy_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(strategy_path))
        except Exception:
            _log.warning("Could not parse strategy file: %s", strategy_path)
            return []

        params: list[SweepParameterDef] = []
        seen_names: set[str] = set()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue

            # Resolve the target name
            if isinstance(node, ast.Assign):
                targets = node.targets
                value_node = node.value
            else:  # AnnAssign
                targets = [node.target] if node.value is not None else []
                value_node = node.value

            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                var_name = target.id

                # Fixed backtest params (simple attribute assignments)
                if var_name in self._FIXED_BACKTEST_PARAMS and var_name not in seen_names:
                    params.append(
                        SweepParameterDef(
                            name=var_name,
                            param_type=SweepParamType.FIXED,
                            default_value=None,
                            enabled=False,
                        )
                    )
                    seen_names.add(var_name)
                    continue

                # Freqtrade hyperopt parameter classes
                if not isinstance(value_node, ast.Call):
                    continue
                func = value_node.func
                class_name = (
                    func.id
                    if isinstance(func, ast.Name)
                    else (func.attr if isinstance(func, ast.Attribute) else None)
                )
                if class_name not in self._PARAM_CLASS_TO_TYPE:
                    continue
                if var_name in seen_names:
                    continue

                params.append(
                    SweepParameterDef(
                        name=var_name,
                        param_type=self._PARAM_CLASS_TO_TYPE[class_name],
                        default_value=None,
                        enabled=False,
                    )
                )
                seen_names.add(var_name)

        return params

    def generate_oat_sweep_points(
        self,
        params: list[SweepParameterDef],
        baseline: dict[str, Any],
    ) -> list[SweepPoint]:
        """Generate One-At-a-Time sweep points.

        For each enabled parameter, enumerate its range while holding all
        other parameters at their baseline values.
        """
        points: list[SweepPoint] = []
        idx = 0

        for param in params:
            if not param.enabled:
                continue

            values = self._param_values(param)
            for val in values:
                overrides = {**baseline, param.name: val}
                points.append(
                    SweepPoint(
                        index=idx,
                        param_overrides=overrides,
                        label=f"{param.name}={val}",
                    )
                )
                idx += 1

        return points

    def generate_grid_sweep_points(
        self,
        params: list[SweepParameterDef],
        baseline: dict[str, Any],
    ) -> list[SweepPoint]:
        """Generate grid (Cartesian product) sweep points.

        Computes the full Cartesian product of all enabled parameter ranges.
        """
        enabled = [p for p in params if p.enabled]
        if not enabled:
            return []

        param_names = [p.name for p in enabled]
        param_ranges = [self._param_values(p) for p in enabled]

        points: list[SweepPoint] = []
        for idx, combo in enumerate(itertools.product(*param_ranges)):
            overrides = {**baseline, **dict(zip(param_names, combo))}
            label = ", ".join(f"{name}={val}" for name, val in zip(param_names, combo))
            points.append(
                SweepPoint(
                    index=idx,
                    param_overrides=overrides,
                    label=label,
                )
            )

        return points

    def _param_values(self, param: SweepParameterDef) -> list[Any]:
        """Enumerate the discrete values for a sweep parameter."""
        if param.param_type in (SweepParamType.CATEGORICAL, SweepParamType.BOOLEAN):
            return list(param.values)

        if param.param_type in (SweepParamType.INT, SweepParamType.DECIMAL):
            if param.min_value is None or param.max_value is None or param.step is None:
                return []
            values: list[Any] = []
            current = param.min_value
            while current <= param.max_value + 1e-9:
                if param.param_type == SweepParamType.INT:
                    values.append(int(round(current)))
                else:
                    values.append(round(current, 10))
                current += param.step
            return values

        # FIXED params have no enumerable range
        return []

    # ------------------------------------------------------------------
    # Export method
    # ------------------------------------------------------------------

    _CSV_COLUMNS = (
        "run_trial",
        "workflow",
        "strategy",
        "pairs",
        "timeframe",
        "timerange",
        "profit_pct",
        "total_profit",
        "win_rate",
        "max_dd_pct",
        "trades",
        "profit_factor",
        "sharpe_ratio",
        "score",
        "status",
        "result_path",
        "log_path",
    )

    def export_results(
        self,
        results: list[ParNeedsRunResult],
        workflow: str,
        export_dir: Path,
    ) -> tuple[Path, Path]:
        """Write results to JSON and CSV files in *export_dir*.

        Returns ``(json_path, csv_path)``.  Raises on write failure so the
        caller can log and surface the error to the terminal.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = f"parneeds_{workflow}_{timestamp}"

        export_dir.mkdir(parents=True, exist_ok=True)

        json_path = export_dir / f"{stem}.json"
        csv_path = export_dir / f"{stem}.csv"

        # JSON — full serialisation
        json_data = [dataclasses.asdict(r) for r in results]
        json_path.write_text(
            json.dumps(json_data, indent=2, default=str),
            encoding="utf-8",
        )

        # CSV — visible table columns only
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(self._CSV_COLUMNS))
            writer.writeheader()
            for row in json_data:
                writer.writerow({col: row.get(col, "") for col in self._CSV_COLUMNS})

        return json_path, csv_path
