"""Persistence layer for individual strategy versions.

Handles saving, loading, and updating a single StrategyVersion on disk.
All methods are static — no instance state required.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from app.core.utils.app_logger import get_logger
from app.core.versioning.version_models import (
    StrategyVersion,
    VersionStatus,
    version_from_dict,
    version_to_dict,
)

_log = get_logger("services.versioning")


class VersionStore:
    """Static methods for saving, loading, and updating strategy versions on disk.

    Directory layout for each version::

        {versions_root}/{strategy_name}/{version_id}/
            strategy.py           ← snapshot of the live .py file
            strategy_params.json  ← snapshot of the live params .json file
            version.json          ← serialized StrategyVersion metadata
    """

    @staticmethod
    def save_version(
        version: StrategyVersion,
        strategy_py_path: Path,
        strategy_params_path: Path,
        versions_root: Path,
    ) -> Path:
        """Copy snapshots and write version.json atomically.

        Args:
            version: The StrategyVersion metadata to persist.
            strategy_py_path: Path to the live strategy ``.py`` file to snapshot.
            strategy_params_path: Path to the live strategy params ``.json`` file to snapshot.
            versions_root: Root directory where all strategy versions are stored.

        Returns:
            The ``Path`` to the newly created version directory.

        Raises:
            FileNotFoundError: If ``strategy_py_path`` or ``strategy_params_path`` does not exist.
            ValueError: If the version directory already exists (duplicate version_id).
        """
        if not strategy_py_path.exists():
            raise FileNotFoundError(
                f"Strategy .py file not found: {strategy_py_path}"
            )
        if not strategy_params_path.exists():
            raise FileNotFoundError(
                f"Strategy params .json file not found: {strategy_params_path}"
            )

        version_dir = versions_root / version.strategy_name / version.version_id

        if version_dir.exists():
            raise ValueError(f"Version directory already exists: {version_dir}")

        version_dir.mkdir(parents=True, exist_ok=True)
        _log.debug("Created version directory: %s", version_dir)

        # Copy snapshots
        shutil.copy2(strategy_py_path, version_dir / "strategy.py")
        shutil.copy2(strategy_params_path, version_dir / "strategy_params.json")
        _log.debug(
            "Snapshotted strategy files for version %s", version.version_id
        )

        # Write version.json atomically
        version_json_path = version_dir / "version.json"
        VersionStore._write_atomic(version_json_path, version_to_dict(version))
        _log.info(
            "Saved version %s for strategy '%s'",
            version.version_id,
            version.strategy_name,
        )

        return version_dir

    @staticmethod
    def load_version(version_dir: Path) -> StrategyVersion:
        """Load a StrategyVersion from its version.json file.

        Args:
            version_dir: Path to the version directory containing ``version.json``.

        Returns:
            The reconstructed ``StrategyVersion`` instance.

        Raises:
            FileNotFoundError: If ``version.json`` does not exist in ``version_dir``.
        """
        version_json_path = version_dir / "version.json"

        if not version_json_path.exists():
            raise FileNotFoundError(
                f"version.json not found in version directory: {version_dir}"
            )

        data = json.loads(version_json_path.read_text(encoding="utf-8"))
        version = version_from_dict(data)
        _log.debug("Loaded version %s from %s", version.version_id, version_dir)
        return version

    @staticmethod
    def update_status(version_dir: Path, new_status: str) -> None:
        """Rewrite version.json with an updated status field (atomic).

        Also updates the ``updated_at`` timestamp to the current time.

        Args:
            version_dir: Path to the version directory containing ``version.json``.
            new_status: The new status string (must be a valid ``VersionStatus`` value).

        Raises:
            FileNotFoundError: If ``version.json`` does not exist in ``version_dir``.
            ValueError: If ``new_status`` is not a recognized ``VersionStatus`` value.
        """
        version_json_path = version_dir / "version.json"

        if not version_json_path.exists():
            raise FileNotFoundError(
                f"version.json not found in version directory: {version_dir}"
            )

        # Validate the new status value
        VersionStatus(new_status)

        data = json.loads(version_json_path.read_text(encoding="utf-8"))
        data["status"] = new_status
        data["updated_at"] = datetime.now().isoformat()

        VersionStore._write_atomic(version_json_path, data)
        _log.info(
            "Updated status to '%s' for version %s",
            new_status,
            data.get("version_id", "unknown"),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_atomic(path: Path, data: dict) -> None:
        """Write a dict as JSON to ``path`` atomically via a temp file + rename.

        Args:
            path: Target file path.
            data: Dict to serialize as JSON.
        """
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
