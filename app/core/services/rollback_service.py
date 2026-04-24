"""Service for rolling back strategy params and config from a saved backtest run.

Restores params.json and config.snapshot.json from a run directory back to
the active strategy locations in user_data, with automatic backup and pruning.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.parsing.json_parser import ParseError, parse_json_file, write_json_file_atomic
from app.core.utils.app_logger import get_logger

_log = get_logger("services.rollback")


@dataclass
class RollbackResult:
    """Result of a rollback operation."""

    params_restored: bool
    config_restored: bool
    rolled_back_to: str
    strategy_name: str
    params_path: Optional[Path] = None
    config_path: Optional[Path] = None


class RollbackService:
    """Restores strategy params and config from a saved backtest run.

    Copies params.json and config.snapshot.json from a run directory back
    to the active strategy locations in user_data, creating timestamped
    backups of the active files before overwriting and pruning old backups.
    """

    MAX_BACKUPS: int = 5

    def _backup_file(self, active_path: Path) -> Path:
        """Create a timestamped backup of an active file.

        Reads the active file, writes a backup with an ISO-8601 UTC timestamp
        suffix, then prunes old backups to keep at most MAX_BACKUPS.

        Args:
            active_path: Path to the active file to back up.

        Returns:
            Path to the newly created backup file.

        Raises:
            ValueError: If the backup write fails.
        """
        if not active_path.exists():
            # Nothing to back up — return a sentinel path (caller won't use it)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            return active_path.parent / f"{active_path.name}.bak_{timestamp}"

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        backup_path = active_path.parent / f"{active_path.name}.bak_{timestamp}"

        try:
            data = parse_json_file(active_path)
            write_json_file_atomic(backup_path, data)
        except (ParseError, Exception) as exc:
            raise ValueError(
                f"Failed to write backup {backup_path}: {exc}"
            ) from exc

        _log.debug("Backup written: %s → %s", active_path, backup_path)
        self._prune_backups(active_path)
        return backup_path

    def _prune_backups(self, active_path: Path) -> None:
        """Delete old backup files beyond MAX_BACKUPS for a given active file.

        Sorts existing .bak_* files in descending order (newest first) and
        deletes all beyond index MAX_BACKUPS - 1.

        Args:
            active_path: Path to the active file whose backups should be pruned.
        """
        pattern = f"{active_path.name}.bak_*"
        backups = sorted(
            active_path.parent.glob(pattern),
            key=lambda p: p.name,
            reverse=True,
        )

        excess = backups[self.MAX_BACKUPS :]
        for old_backup in excess:
            try:
                old_backup.unlink()
            except Exception as exc:
                _log.warning("Failed to delete old backup %s: %s", old_backup, exc)

    def _atomic_restore(self, src: Path, dest: Path) -> None:
        """Atomically restore a file from src to dest.

        Reads the source JSON and writes it atomically to the destination.

        Args:
            src: Source file path (inside a run directory).
            dest: Destination file path (active location in user_data).

        Raises:
            ValueError: If reading the source or writing the destination fails.
        """
        try:
            data = parse_json_file(src)
        except ParseError as exc:
            raise ValueError(f"Failed to read source file {src}: {exc}") from exc

        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            write_json_file_atomic(dest, data)
        except ParseError as exc:
            raise ValueError(f"Failed to write destination file {dest}: {exc}") from exc

        _log.info("Restored: %s → %s", src, dest)

    def rollback(
        self,
        run_dir: Path,
        user_data_path: Path,
        strategy_name: str,
        restore_params: bool = True,
        restore_config: bool = False,
    ) -> RollbackResult:
        """Restore strategy params and/or config from a saved run directory.

        Creates backups of the active files before overwriting them, then
        atomically restores the selected files from the run directory.

        Args:
            run_dir: Absolute path to the run folder (contains params.json,
                     config.snapshot.json).
            user_data_path: Absolute path to the freqtrade user_data directory.
            strategy_name: Name of the strategy (without .py extension).
            restore_params: Whether to restore params.json (default: True).
            restore_config: Whether to restore config.snapshot.json (default: False).

        Returns:
            RollbackResult with details of what was restored.

        Raises:
            FileNotFoundError: If run_dir does not exist.
            ValueError: If neither source file is present, or if a backup or
                        restore operation fails.
        """
        run_dir = Path(run_dir)
        user_data_path = Path(user_data_path)

        if not run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {run_dir}")

        run_id = run_dir.name
        params_src = run_dir / "params.json"
        config_src = run_dir / "config.snapshot.json"

        params_dest = user_data_path / "strategies" / f"{strategy_name}.json"
        config_dest = user_data_path / "config.json"

        # Validate that at least one restorable file exists
        params_available = restore_params and params_src.exists()
        config_available = restore_config and config_src.exists()

        if not params_src.exists() and not config_src.exists():
            raise ValueError(
                f"No restorable files found in run directory: {run_dir}"
            )

        _log.info(
            "Starting rollback: strategy=%s run_id=%s", strategy_name, run_id
        )

        params_restored = False
        config_restored = False
        result_params_path: Optional[Path] = None
        result_config_path: Optional[Path] = None

        # Restore params
        if params_available:
            # Backup first — raises ValueError on failure (aborts before touching active)
            self._backup_file(params_dest)
            self._atomic_restore(params_src, params_dest)
            params_restored = True
            result_params_path = params_dest

        # Restore config
        if config_available:
            # Backup first — raises ValueError on failure (aborts before touching active)
            self._backup_file(config_dest)
            self._atomic_restore(config_src, config_dest)
            config_restored = True
            result_config_path = config_dest

        return RollbackResult(
            params_restored=params_restored,
            config_restored=config_restored,
            rolled_back_to=run_id,
            strategy_name=strategy_name,
            params_path=result_params_path,
            config_path=result_config_path,
        )
