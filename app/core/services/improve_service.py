"""
improve_service.py — Service for the strategy improvement pipeline.

Provides data-loading helpers used by the improve workflow:
listing strategies, fetching run history, and loading baseline results.
"""
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.backtests.results_index import IndexStore
from app.core.backtests.results_models import BacktestResults
from app.core.backtests.results_parser import parse_backtest_zip
from app.core.backtests.results_store import RunStore
from app.core.freqtrade.runners.backtest_runner import BacktestRunCommand
from app.core.services.backtest_service import BacktestService
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger

_log = get_logger("services.improve")


class ImproveService:
    """Service for the strategy improvement pipeline.

    Coordinates strategy selection, run history retrieval, and baseline
    loading for the improve workflow. No UI imports.

    Args:
        settings_service: Provides access to persisted application settings.
        backtest_service: Provides strategy discovery and backtest utilities.
    """

    def __init__(self, settings_service: SettingsService, backtest_service: BacktestService) -> None:
        self.settings_service = settings_service
        self.backtest_service = backtest_service

    def get_available_strategies(self) -> List[str]:
        """Return all strategy names discoverable from user_data/strategies/.

        Delegates to BacktestService which reads the strategies directory
        configured in AppSettings.

        Returns:
            Sorted list of strategy class names, or empty list if none found.
        """
        return self.backtest_service.get_available_strategies()

    def get_strategy_runs(self, strategy: str) -> List[Dict]:
        """Return all saved backtest runs for a strategy, newest first.

        Args:
            strategy: Strategy class name to look up.

        Returns:
            List of run metadata dicts from the global index, newest first.
            Returns empty list if no runs exist or index is missing.
        """
        settings = self.settings_service.load_settings()
        backtest_results_dir = str(Path(settings.user_data_path) / "backtest_results")
        return IndexStore.get_strategy_runs(backtest_results_dir, strategy)

    def load_baseline(self, run_dir: Path) -> BacktestResults:
        """Load a saved backtest run as BacktestResults.

        Args:
            run_dir: Path to the run folder containing results.json and trades.json.

        Returns:
            BacktestResults reconstructed from the run folder.

        Raises:
            FileNotFoundError: If required files are missing from run_dir.
            ValueError: If run files are malformed.
        """
        return RunStore.load_run(run_dir)

    def prepare_sandbox(self, strategy_name: str, candidate_config: dict) -> Path:
        """Create an isolated sandbox directory for a candidate backtest run.

        Creates a timestamped sandbox directory under
        ``{user_data_path}/strategies/_improve_sandbox/``, copies the strategy
        ``.py`` file into it, and writes the candidate config as
        ``{strategy_name}.json``.

        The directory name uses Unix timestamp in milliseconds (timestamp_ms)
        to ensure uniqueness and determinism.

        Args:
            strategy_name: Strategy class name (must exist as a ``.py`` file).
            candidate_config: Candidate parameter dict to write as JSON. May contain
                all parameter groups: stoploss, max_open_trades, minimal_roi,
                buy_params, sell_params, trailing_stop, trailing_stop_positive,
                trailing_stop_positive_offset, trailing_only_offset_is_reached.

        Returns:
            Path to the created sandbox directory.

        Raises:
            FileNotFoundError: If the strategy ``.py`` file does not exist.
        """
        settings = self.settings_service.load_settings()
        user_data_path = Path(settings.user_data_path)
        strategies_dir = user_data_path / "strategies"
        strategy_py = strategies_dir / f"{strategy_name}.py"

        if not strategy_py.exists():
            raise FileNotFoundError(f"Strategy file not found: {strategy_py}")

        # Use Unix timestamp in milliseconds for uniqueness (task 12)
        import time as _time
        timestamp_ms = int(_time.time() * 1000)
        sandbox_dir = (
            user_data_path / "strategies" / "_improve_sandbox"
            / f"{strategy_name}_{timestamp_ms}"
        )
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(strategy_py, sandbox_dir / f"{strategy_name}.py")

        config_file = sandbox_dir / f"{strategy_name}.json"
        config_file.write_text(
            json.dumps(
                self._build_freqtrade_params_file(strategy_name, candidate_config),
                indent=2,
            ),
            encoding="utf-8",
        )

        _log.info("Sandbox prepared at %s", sandbox_dir)
        return sandbox_dir

    def build_candidate_command(
        self,
        strategy_name: str,
        baseline: BacktestResults,
        sandbox_dir: Path,
    ) -> Tuple[BacktestRunCommand, Path]:
        """Build a backtest command targeting the sandbox candidate.

        Derives a deterministic export directory for the candidate run and
        delegates command construction to ``BacktestService.build_command()``.

        Args:
            strategy_name: Strategy class name.
            baseline: Baseline ``BacktestResults`` supplying timeframe and pairs.
            sandbox_dir: Path to the sandbox directory created by
                ``prepare_sandbox()``.

        Returns:
            A tuple of ``(BacktestRunCommand, export_dir)`` where ``export_dir``
            is the directory Freqtrade will write the result zip into.
        """
        settings = self.settings_service.load_settings()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = (
            Path(settings.user_data_path)
            / "backtest_results"
            / "_improve"
            / f"{strategy_name}_{timestamp}"
        )
        export_dir.mkdir(parents=True, exist_ok=True)

        extra_flags = [
            "--strategy-path", str(sandbox_dir),
            "--backtest-directory", str(export_dir),
        ]

        # Guard: use a sensible default timeframe if the baseline has none
        timeframe = baseline.summary.timeframe or "5m"
        # Guard: only pass pairs if the baseline has a non-empty pairlist
        pairs = baseline.summary.pairlist if baseline.summary.pairlist else []

        command = self.backtest_service.build_command(
            strategy_name=strategy_name,
            timeframe=timeframe,
            pairs=pairs,
            extra_flags=extra_flags,
        )

        _log.info("Candidate command built; export_dir=%s", export_dir)
        return (command, export_dir)

    def load_baseline_params(self, run_dir: Path, strategy_name: str = "") -> Dict:
        """Load strategy parameters from a saved run folder.

        Reads params.json from the run directory. If the file is absent and
        ``strategy_name`` is provided, falls back to reading the live strategy
        JSON at ``{user_data_path}/strategies/{strategy_name}.json`` and
        converting it to the flat params format.

        Args:
            run_dir: Path to the run folder.
            strategy_name: Optional strategy class name used for the fallback
                when params.json is missing.

        Returns:
            Dict of strategy parameters, or {} if params.json is missing and
            no fallback is available.

        Raises:
            ValueError: If params.json exists but cannot be parsed.
        """
        params_file = run_dir / "params.json"
        if not params_file.exists():
            _log.warning("params.json not found in %s — returning empty params", run_dir)
            if strategy_name:
                return self._load_params_from_live_strategy(strategy_name)
            return {}
        try:
            return json.loads(params_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            _log.error("Failed to parse params.json in %s: %s", run_dir, e)
            raise ValueError(f"Failed to parse params.json: {e}")

    def _load_params_from_live_strategy(self, strategy_name: str) -> Dict:
        """Load flat params from the live strategy JSON as a fallback.

        Reads the live strategy JSON at
        ``{user_data_path}/strategies/{strategy_name}.json`` and converts the
        nested ``params`` sub-object to the flat params format.

        Args:
            strategy_name: Strategy class name.

        Returns:
            Flat params dict, or {} if the live strategy JSON is missing or
            cannot be parsed.
        """
        settings = self.settings_service.load_settings()
        live_json_path = Path(settings.user_data_path) / "strategies" / f"{strategy_name}.json"

        if not live_json_path.exists():
            _log.warning(
                "Live strategy JSON not found at %s — returning empty params", live_json_path
            )
            return {}

        try:
            live_data = json.loads(live_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            _log.error("Failed to parse live strategy JSON at %s: %s", live_json_path, e)
            return {}

        nested_params = live_data.get("params", {})
        flat: Dict = {}

        stoploss_block = nested_params.get("stoploss")
        if isinstance(stoploss_block, dict) and "stoploss" in stoploss_block:
            flat["stoploss"] = stoploss_block["stoploss"]

        mot_block = nested_params.get("max_open_trades")
        if isinstance(mot_block, dict) and "max_open_trades" in mot_block:
            flat["max_open_trades"] = mot_block["max_open_trades"]

        roi_block = nested_params.get("roi")
        if roi_block is not None:
            flat["minimal_roi"] = roi_block

        buy_block = nested_params.get("buy")
        if buy_block is not None:
            flat["buy_params"] = buy_block

        sell_block = nested_params.get("sell")
        if sell_block is not None:
            flat["sell_params"] = sell_block

        _log.info(
            "Loaded baseline params from live strategy JSON for '%s': %d keys",
            strategy_name,
            len(flat),
        )
        return flat

    def _build_freqtrade_params_file(self, strategy_name: str, flat_params: dict) -> dict:
        """Convert a flat params dict to the freqtrade nested strategy JSON format.

        Reads the live strategy JSON as a base (preserving fields like ``trailing``
        that are not tracked in ``params.json``), merges the flat candidate config
        into the nested ``params`` sub-object using the defined key mapping, and
        updates ``export_time``.

        Args:
            strategy_name: Strategy class name.
            flat_params: Flat params dict with keys: stoploss, max_open_trades,
                minimal_roi, buy_params, sell_params.

        Returns:
            Dict in freqtrade nested format with strategy_name, params, ft_stratparam_v,
            export_time.
        """
        settings = self.settings_service.load_settings()
        live_json_path = Path(settings.user_data_path) / "strategies" / f"{strategy_name}.json"

        if live_json_path.exists():
            try:
                base = json.loads(live_json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                base = {"strategy_name": strategy_name, "params": {}, "ft_stratparam_v": 1}
        else:
            base = {"strategy_name": strategy_name, "params": {}, "ft_stratparam_v": 1}

        ft_params = dict(base.get("params", {}))

        if "stoploss" in flat_params and flat_params["stoploss"] is not None:
            ft_params["stoploss"] = {"stoploss": flat_params["stoploss"]}
        if "max_open_trades" in flat_params and flat_params["max_open_trades"] is not None:
            ft_params["max_open_trades"] = {"max_open_trades": flat_params["max_open_trades"]}
        if "minimal_roi" in flat_params and flat_params["minimal_roi"]:
            ft_params["roi"] = flat_params["minimal_roi"]
        if "buy_params" in flat_params and flat_params["buy_params"]:
            ft_params["buy"] = flat_params["buy_params"]
        if "sell_params" in flat_params and flat_params["sell_params"]:
            ft_params["sell"] = flat_params["sell_params"]

        # Trailing stop parameters
        if "trailing_stop" in flat_params and flat_params["trailing_stop"] is not None:
            trailing_block = ft_params.get("trailing", {})
            trailing_block["trailing_stop"] = flat_params["trailing_stop"]
            if "trailing_stop_positive" in flat_params and flat_params["trailing_stop_positive"] is not None:
                trailing_block["trailing_stop_positive"] = flat_params["trailing_stop_positive"]
            if "trailing_stop_positive_offset" in flat_params and flat_params["trailing_stop_positive_offset"] is not None:
                trailing_block["trailing_stop_positive_offset"] = flat_params["trailing_stop_positive_offset"]
            if "trailing_only_offset_is_reached" in flat_params and flat_params["trailing_only_offset_is_reached"] is not None:
                trailing_block["trailing_only_offset_is_reached"] = flat_params["trailing_only_offset_is_reached"]
            ft_params["trailing"] = trailing_block

        base["params"] = ft_params
        base["strategy_name"] = strategy_name
        base["ft_stratparam_v"] = 1
        base["export_time"] = datetime.now(timezone.utc).isoformat()

        return base

    def resolve_candidate_artifact(self, export_dir: Path) -> Path:
        """Locate the single .zip file written by Freqtrade into export_dir.

        Args:
            export_dir: Directory where the candidate backtest wrote its zip.

        Returns:
            Path to the single .zip file found in export_dir.

        Raises:
            FileNotFoundError: If zero .zip files are found in export_dir.
        """
        zips = list(export_dir.glob("*.zip"))
        if len(zips) == 1:
            return zips[0]
        if len(zips) == 0:
            raise FileNotFoundError(
                f"No .zip result file found in export_dir: {export_dir}"
            )
        # Multiple zips — return the most recently modified one
        _log.warning(
            "resolve_candidate_artifact: expected 1 zip in %s, found %d — "
            "returning most recent",
            export_dir,
            len(zips),
        )
        return max(zips, key=lambda p: p.stat().st_mtime)

    def resolve_candidate_zip(self, export_dir: Path, started_at: float = 0.0) -> Optional[Path]:
        """Return the single .zip from export_dir, or fall back to mtime scan.

        Deprecated: use resolve_candidate_artifact() instead.

        Args:
            export_dir: Directory where the candidate backtest wrote its zip.
            started_at: Unix timestamp of when the candidate process started.
                Used to filter the fallback mtime scan so only zips written
                after the run started are considered.

        Returns:
            Path to the zip file, or None if no zip is found anywhere.
        """
        zips = list(export_dir.glob("*.zip"))
        if len(zips) == 1:
            return zips[0]

        _log.warning(
            "resolve_candidate_zip: expected 1 zip in %s, found %d — falling back to mtime scan",
            export_dir,
            len(zips),
        )
        settings = self.settings_service.load_settings()
        scan_root = Path(settings.user_data_path) / "backtest_results"
        all_zips = [
            p for p in scan_root.rglob("*.zip")
            if p.stat().st_mtime >= started_at
        ]
        if not all_zips:
            return None
        return max(all_zips, key=lambda p: p.stat().st_mtime)

    def parse_candidate_run(self, export_dir: Path, started_at: float = 0.0) -> BacktestResults:
        """Parse the candidate backtest zip from export_dir.

        Calls resolve_candidate_artifact(export_dir) internally to locate the
        zip before parsing. Falls back to the legacy mtime scan when
        resolve_candidate_artifact raises FileNotFoundError.

        Args:
            export_dir: Directory where the candidate backtest wrote its zip.
            started_at: Unix timestamp of when the candidate process started.
                Used for the legacy fallback mtime filter.

        Returns:
            BacktestResults parsed from the zip.

        Raises:
            FileNotFoundError: If no candidate zip is found.
        """
        try:
            zip_path = self.resolve_candidate_artifact(export_dir)
        except FileNotFoundError:
            # Legacy fallback: mtime scan
            zip_path = self.resolve_candidate_zip(export_dir, started_at)
            if zip_path is None:
                raise FileNotFoundError(
                    f"No candidate zip found in export_dir: {export_dir}"
                )
        return parse_backtest_zip(str(zip_path))

    def accept_candidate(self, strategy_name: str, candidate_config: dict) -> None:
        """Atomically write candidate_config as the live strategy parameter file.

        Args:
            strategy_name: Strategy class name (file written as ``{strategy_name}.json``).
            candidate_config: Parameter dict to persist.
        """
        settings = self.settings_service.load_settings()
        strategies_dir = Path(settings.user_data_path) / "strategies"
        final_path = strategies_dir / f"{strategy_name}.json"
        tmp_path = strategies_dir / f"{strategy_name}.json.tmp"

        tmp_path.write_text(json.dumps(self._build_freqtrade_params_file(strategy_name, candidate_config), indent=2), encoding="utf-8")
        os.replace(tmp_path, final_path)
        _log.info("Candidate accepted; written to %s", final_path)

    def reject_candidate(self, sandbox_dir: Path) -> None:
        """Delete the sandbox directory, leaving the main strategy file untouched.

        Args:
            sandbox_dir: Path to the sandbox directory to remove.
        """
        shutil.rmtree(sandbox_dir, ignore_errors=True)
        _log.info("Candidate rejected; sandbox removed: %s", sandbox_dir)

    def rollback(self, strategy_name: str, baseline_params: dict) -> None:
        """Atomically restore baseline_params as the live strategy parameter file.

        Args:
            strategy_name: Strategy class name.
            baseline_params: Original parameter dict to restore.
        """
        settings = self.settings_service.load_settings()
        strategies_dir = Path(settings.user_data_path) / "strategies"
        final_path = strategies_dir / f"{strategy_name}.json"
        tmp_path = strategies_dir / f"{strategy_name}.json.tmp"

        tmp_path.write_text(json.dumps(self._build_freqtrade_params_file(strategy_name, baseline_params), indent=2), encoding="utf-8")
        os.replace(tmp_path, final_path)
        _log.info("Rollback complete; restored %s", final_path)

    def cleanup_stale_sandboxes(self) -> None:
        """Delete sandbox directories older than 24 hours from the improve sandbox root.

        Scans ``{user_data}/strategies/_improve_sandbox/`` for subdirectories.
        Skips directories less than 5 minutes old (to avoid deleting sandboxes
        from a concurrently running loop instance). Logs a WARNING on OSError
        and continues without surfacing the error to the caller.
        """
        import time as _time

        settings = self.settings_service.load_settings()
        if not settings.user_data_path:
            return

        sandbox_root = Path(settings.user_data_path) / "strategies" / "_improve_sandbox"
        if not sandbox_root.exists():
            return

        now = _time.time()
        stale_threshold = 24 * 3600  # 24 hours in seconds
        young_threshold = 5 * 60     # 5 minutes in seconds

        for entry in sandbox_root.iterdir():
            if not entry.is_dir():
                continue
            try:
                age = now - entry.stat().st_mtime
                if age < young_threshold:
                    _log.debug(
                        "cleanup_stale_sandboxes: skipping young sandbox %s (age=%.0fs)",
                        entry.name, age,
                    )
                    continue
                if age >= stale_threshold:
                    shutil.rmtree(entry)
                    _log.info(
                        "cleanup_stale_sandboxes: deleted stale sandbox %s (age=%.0fh)",
                        entry.name, age / 3600,
                    )
            except OSError as exc:
                _log.warning(
                    "cleanup_stale_sandboxes: failed to remove %s: %s", entry, exc
                )
