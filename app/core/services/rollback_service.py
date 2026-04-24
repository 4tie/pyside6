"""Service for rolling back strategy params and config from a saved backtest run.

Restores params.json and config.snapshot.json from a run directory back to
the active strategy locations in user_data.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.core.parsing.json_parser import parse_json_file, write_json_file_atomic
from app.core.utils.app_logger import get_logger

_log = get_logger("services.rollback")


@dataclass
class RollbackResult:
    """Result of a rollback operation."""

    success: bool
    rolled_back_to: str
    strategy_name: str
    params_restored: bool
    config_restored: bool
    error: Optional[str] = None


class RollbackService:
    """Restores strategy params and config from a saved backtest run.

    Copies params.json and config.snapshot.json from a run directory back
    to the active strategy locations in user_data.
    """

    def rollback(
        self,
        run_dir: Path,
        user_data_path: Path,
        strategy_name: str,
    ) -> RollbackResult:
        """Restore strategy params and config from a saved run directory.

        Args:
            run_dir: Absolute path to the run folder (contains params.json,
                     config.snapshot.json).
            user_data_path: Absolute path to the freqtrade user_data directory.
            strategy_name: Name of the strategy (without .py extension).

        Returns:
            RollbackResult with success flag and details.

        Raises:
            FileNotFoundError: If run_dir does not exist.
            ValueError: If neither params.json nor config.snapshot.json exists
                        in the run directory.
        """
        run_dir = Path(run_dir)
        user_data_path = Path(user_data_path)

        # Step 1: Validate run_dir exists
        if not run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {run_dir}")

        run_id = run_dir.name
        params_restored = False
        config_restored = False

        # Step 2: Restore params.json → {user_data}/strategies/{strategy_name}.json
        params_src = run_dir / "params.json"
        if params_src.exists():
            params_dest = user_data_path / "strategies" / f"{strategy_name}.json"
            params_dest.parent.mkdir(parents=True, exist_ok=True)
            data = parse_json_file(params_src)
            write_json_file_atomic(params_dest, data)
            params_restored = True
            _log.info("Restored params: %s → %s", params_src, params_dest)
        else:
            _log.warning("params.json not found in run directory: %s", run_dir)

        # Step 3: Restore config.snapshot.json → {user_data}/config.json
        config_src = run_dir / "config.snapshot.json"
        if config_src.exists():
            config_dest = user_data_path / "config.json"
            config_dest.parent.mkdir(parents=True, exist_ok=True)
            data = parse_json_file(config_src)
            write_json_file_atomic(config_dest, data)
            config_restored = True
            _log.info("Restored config: %s → %s", config_src, config_dest)
        else:
            _log.warning("config.snapshot.json not found in run directory: %s", run_dir)

        # Step 4: If neither file was restored, raise ValueError
        if not params_restored and not config_restored:
            raise ValueError(f"No restorable files found in run directory: {run_dir}")

        # Step 5: Return success result
        return RollbackResult(
            success=True,
            rolled_back_to=run_id,
            strategy_name=strategy_name,
            params_restored=params_restored,
            config_restored=config_restored,
        )
