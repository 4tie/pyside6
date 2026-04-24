"""VersioningService — manages strategy version lifecycle."""
from __future__ import annotations

import difflib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.versioning.version_models import (
    StrategyVersion,
    VersionSource,
    VersionStatus,
    version_from_dict,
    version_to_dict,
)
from app.core.versioning.version_store import VersionStore
from app.core.versioning.version_index import VersionIndex
from app.core.utils.app_logger import get_logger

_log = get_logger("services.versioning")


class VersioningService:
    """Manages the full lifecycle of strategy versions.

    Args:
        settings_service: Provides user_data_path via load_settings().
    """

    def __init__(self, settings_service) -> None:
        self._settings_service = settings_service

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _versions_root(self) -> Path:
        settings = self._settings_service.load_settings()
        return Path(settings.user_data_path) / "strategy_versions"

    def _strategy_versions_dir(self, strategy_name: str) -> Path:
        return self._versions_root() / strategy_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_candidate(
        self,
        strategy_name: str,
        strategy_py_path: Path,
        strategy_params_path: Path,
        notes: Optional[str] = None,
        source_type: VersionSource = VersionSource.MANUAL_EDIT,
        base_version_id: Optional[str] = None,
    ) -> StrategyVersion:
        """Snapshot the current strategy files as a new candidate version.

        Args:
            strategy_name: Name of the strategy.
            strategy_py_path: Path to the live .py file.
            strategy_params_path: Path to the live .json params file.
            notes: Optional human-readable notes.
            source_type: How this candidate was created.
            base_version_id: ID of the version this is based on.

        Returns:
            The newly created StrategyVersion with CANDIDATE status.
        """
        versions_root = self._versions_root()
        version_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        version_dir = versions_root / strategy_name / version_id
        snapshot_py = str(version_dir / "strategy.py")
        snapshot_params = str(version_dir / "strategy_params.json")

        version = StrategyVersion(
            version_id=version_id,
            strategy_name=strategy_name,
            base_version_id=base_version_id,
            status=VersionStatus.CANDIDATE,
            source_type=source_type,
            strategy_file_path=str(strategy_py_path),
            live_params_path=str(strategy_params_path),
            snapshot_strategy_path=snapshot_py,
            snapshot_params_path=snapshot_params,
            created_at=now,
            updated_at=now,
            notes=notes,
        )

        VersionStore.save_version(version, strategy_py_path, strategy_params_path, versions_root)
        VersionIndex.update(self._strategy_versions_dir(strategy_name), version)
        _log.info("Created candidate version %s for strategy '%s'", version_id, strategy_name)
        return version

    def accept_version(self, version_id: str) -> StrategyVersion:
        """Promote a candidate to ACTIVE, demoting any existing active version.

        Args:
            version_id: ID of the candidate to accept.

        Returns:
            The updated StrategyVersion with ACTIVE status.

        Raises:
            ValueError: If the version is not found or not in CANDIDATE status.
        """
        version = self.get_version(version_id)
        if version is None:
            raise ValueError(f"Version not found: {version_id}")
        if version.status != VersionStatus.CANDIDATE:
            raise ValueError(
                f"Cannot accept version {version_id}: expected 'candidate', got '{version.status.value}'"
            )

        strategy_dir = self._strategy_versions_dir(version.strategy_name)

        # Demote any existing active version
        existing_active = self.get_active_version(version.strategy_name)
        if existing_active is not None:
            active_dir = strategy_dir / existing_active.version_id
            VersionStore.update_status(active_dir, VersionStatus.ACCEPTED.value)
            VersionIndex.update(strategy_dir, VersionStore.load_version(active_dir))

        # Promote this candidate
        version_dir = strategy_dir / version_id
        VersionStore.update_status(version_dir, VersionStatus.ACTIVE.value)
        updated = VersionStore.load_version(version_dir)

        # Set base_version_id to the previously active version
        if existing_active is not None and updated.base_version_id is None:
            from app.core.parsing.json_parser import parse_json_file, write_json_file_atomic
            version_json = version_dir / "version.json"
            data = parse_json_file(version_json)
            data["base_version_id"] = existing_active.version_id
            write_json_file_atomic(version_json, data)
            updated = VersionStore.load_version(version_dir)

        # Copy snapshot files back to live paths
        snapshot_py = Path(updated.snapshot_strategy_path)
        snapshot_params = Path(updated.snapshot_params_path)
        live_py = Path(updated.strategy_file_path)
        live_params = Path(updated.live_params_path)

        if snapshot_py.exists():
            live_py.write_bytes(snapshot_py.read_bytes())
        if snapshot_params.exists():
            live_params.write_bytes(snapshot_params.read_bytes())

        VersionIndex.update(strategy_dir, updated)
        _log.info("Accepted version %s for strategy '%s'", version_id, version.strategy_name)
        return updated

    def reject_version(self, version_id: str) -> StrategyVersion:
        """Mark a candidate as REJECTED.

        Args:
            version_id: ID of the candidate to reject.

        Returns:
            The updated StrategyVersion with REJECTED status.

        Raises:
            ValueError: If the version is not found or not in CANDIDATE status.
        """
        version = self.get_version(version_id)
        if version is None:
            raise ValueError(f"Version not found: {version_id}")
        if version.status != VersionStatus.CANDIDATE:
            raise ValueError(
                f"Cannot reject version {version_id}: expected 'candidate', got '{version.status.value}'"
            )

        strategy_dir = self._strategy_versions_dir(version.strategy_name)
        version_dir = strategy_dir / version_id
        VersionStore.update_status(version_dir, VersionStatus.REJECTED.value)
        updated = VersionStore.load_version(version_dir)
        VersionIndex.update(strategy_dir, updated)
        _log.info("Rejected version %s", version_id)
        return updated

    def get_version(self, version_id: str) -> Optional[StrategyVersion]:
        """Load a specific version by ID, searching all strategy directories.

        Args:
            version_id: The version UUID to look up.

        Returns:
            StrategyVersion if found, None otherwise.
        """
        versions_root = self._versions_root()
        if not versions_root.exists():
            return None
        for strategy_dir in versions_root.iterdir():
            if not strategy_dir.is_dir():
                continue
            version_dir = strategy_dir / version_id
            if version_dir.is_dir():
                try:
                    return VersionStore.load_version(version_dir)
                except FileNotFoundError:
                    pass
        return None

    def get_active_version(self, strategy_name: str) -> Optional[StrategyVersion]:
        """Return the currently ACTIVE version for a strategy, or None.

        Args:
            strategy_name: Name of the strategy.

        Returns:
            The active StrategyVersion, or None if no active version exists.
        """
        strategy_dir = self._strategy_versions_dir(strategy_name)
        versions = VersionIndex.load(strategy_dir)
        for v in versions:
            if v.status == VersionStatus.ACTIVE:
                return v
        return None

    def get_version_for_run(self, run_meta: dict) -> Optional[StrategyVersion]:
        """Look up the version associated with a backtest run.

        Args:
            run_meta: Dict that may contain a 'version_id' key.

        Returns:
            StrategyVersion if found, None otherwise.
        """
        version_id = run_meta.get("version_id")
        if not version_id:
            return None
        return self.get_version(version_id)

    def build_diff_preview(self, version_id: str) -> dict:
        """Build a unified diff between the snapshot and the current live files.

        Args:
            version_id: ID of the version to diff.

        Returns:
            Dict with 'strategy_diff' and 'params_diff' keys (unified diff strings).

        Raises:
            ValueError: If the version is not found.
        """
        version = self.get_version(version_id)
        if version is None:
            raise ValueError(f"Version not found: {version_id}")

        def _diff(snapshot_path: str, live_path: str) -> str:
            snap = Path(snapshot_path)
            live = Path(live_path)
            snap_lines = snap.read_text(encoding="utf-8").splitlines(keepends=True) if snap.exists() else []
            live_lines = live.read_text(encoding="utf-8").splitlines(keepends=True) if live.exists() else []
            return "".join(difflib.unified_diff(
                snap_lines, live_lines,
                fromfile=f"snapshot/{snap.name}",
                tofile=f"live/{live.name}",
            ))

        return {
            "strategy_diff": _diff(version.snapshot_strategy_path, version.strategy_file_path),
            "params_diff": _diff(version.snapshot_params_path, version.live_params_path),
        }
