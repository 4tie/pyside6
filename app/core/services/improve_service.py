"""
improve_service.py — Service for the strategy improvement pipeline.

Provides data-loading helpers used by the improve workflow:
listing strategies, fetching run history, and loading baseline results.
"""
import json
import os
import shutil
from datetime import datetime
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

        Args:
            strategy_name: Strategy class name (must exist as a ``.py`` file).
            candidate_config: Candidate parameter dict to write as JSON.

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

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sandbox_dir = user_data_path / "strategies" / "_improve_sandbox" / f"{strategy_name}_{timestamp}"
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(strategy_py, sandbox_dir / f"{strategy_name}.py")

        config_file = sandbox_dir / f"{strategy_name}.json"
        config_file.write_text(json.dumps(candidate_config, indent=2), encoding="utf-8")

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

        command = self.backtest_service.build_command(
            strategy_name=strategy_name,
            timeframe=baseline.summary.timeframe,
            pairs=baseline.summary.pairlist,
            extra_flags=extra_flags,
        )

        _log.info("Candidate command built; export_dir=%s", export_dir)
        return (command, export_dir)

    def load_baseline_params(self, run_dir: Path) -> Dict:
        """Load strategy parameters from a saved run folder.

        Reads params.json from the run directory. If the file is absent,
        logs a warning and returns an empty dict rather than raising.

        Args:
            run_dir: Path to the run folder.

        Returns:
            Dict of strategy parameters, or {} if params.json is missing.

        Raises:
            ValueError: If params.json exists but cannot be parsed.
        """
        params_file = run_dir / "params.json"
        if not params_file.exists():
            _log.warning("params.json not found in %s — returning empty params", run_dir)
            return {}
        try:
            return json.loads(params_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            _log.error("Failed to parse params.json in %s: %s", run_dir, e)
            raise ValueError(f"Failed to parse params.json: {e}")

    def resolve_candidate_zip(self, export_dir: Path) -> Optional[Path]:
        """Return the single .zip from export_dir, or fall back to mtime scan.

        Args:
            export_dir: Directory where the candidate backtest wrote its zip.

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
        all_zips = list(scan_root.rglob("*.zip"))
        if not all_zips:
            return None
        return max(all_zips, key=lambda p: p.stat().st_mtime)

    def parse_candidate_run(self, export_dir: Path) -> BacktestResults:
        """Parse the candidate backtest zip from export_dir.

        Args:
            export_dir: Directory where the candidate backtest wrote its zip.

        Returns:
            BacktestResults parsed from the zip.

        Raises:
            FileNotFoundError: If no candidate zip is found.
        """
        zip_path = self.resolve_candidate_zip(export_dir)
        if zip_path is None:
            raise FileNotFoundError("No candidate zip found in export_dir")
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

        tmp_path.write_text(json.dumps(candidate_config, indent=2), encoding="utf-8")
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

        tmp_path.write_text(json.dumps(baseline_params, indent=2), encoding="utf-8")
        os.replace(tmp_path, final_path)
        _log.info("Rollback complete; restored %s", final_path)
