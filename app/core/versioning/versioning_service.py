"""VersioningService — orchestrates strategy version lifecycle.

Coordinates VersionStore and VersionIndex to implement the full
create → accept/reject lifecycle for strategy versions.
"""

from __future__ import annotations

import difflib
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger
from app.core.versioning.version_index import VersionIndex
from app.core.versioning.version_models import (
    StrategyVersion,
    VersionSource,
    VersionStatus,
    version_to_dict,
)
from app.core.versioning.version_store import VersionStore

_log = get_logger("services.versioning")


class VersioningService:
    """Orchestrates strategy version lifecycle operations.

    Coordinates VersionStore (disk persistence) and VersionIndex (fast lookup)
    to implement create_candidate, accept_version, reject_version, and query
    operations.

    Args:
        settings_service: Application settings service providing user_data_path.
    """

    def __init__(self, settings_service: SettingsService) -> None:
        self._settings_service = settings_service

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _versions_root(self) -> Path:
        """Return the root directory for all strategy versions.

        Returns:
            Path to ``{user_data_path}/strategy_versions/``.

        Raises:
            ValueError: If settings or user_data_path is not configured.
        """
        settings = self._settings_service.load_settings()
        if not settings.user_data_path:
            raise ValueError(
                "user_data_path is not configured in settings. "
                "Please set it in the application settings."
            )
        return Path(settings.user_data_path) / "strategy_versions"

    def _strategy_versions_dir(self, strategy_name: str) -> Path:
        """Return the directory for a specific strategy's versions.

        Args:
            strategy_name: Name of the strategy.

        Returns:
            Path to ``{versions_root}/{strategy_name}/``.
        """
        return self._versions_root() / strategy_name

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_candidate(
        self,
        strategy_name: str,
        strategy_py_path: Path,
        strategy_params_path: Path,
        source_type: str = "manual_edit",
        notes: Optional[str] = None,
    ) -> StrategyVersion:
        """Create a new candidate version by snapshotting the given strategy files.

        Args:
            strategy_name: Name of the strategy (e.g. ``"MyStrategy"``).
            strategy_py_path: Path to the live strategy ``.py`` file to snapshot.
            strategy_params_path: Path to the live strategy params ``.json`` file to snapshot.
            source_type: Origin of this version (default: ``"manual_edit"``).
            notes: Optional free-text notes for this version.

        Returns:
            The newly created ``StrategyVersion`` with status ``candidate``.

        Raises:
            FileNotFoundError: If either source file does not exist.
            ValueError: If settings are not configured or version dir already exists.
        """
        versions_root = self._versions_root()
        version_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        version_dir = versions_root / strategy_name / version_id
        snapshot_strategy_path = str(version_dir / "strategy.py")
        snapshot_params_path = str(version_dir / "strategy_params.json")

        version = StrategyVersion(
            version_id=version_id,
            strategy_name=strategy_name,
            base_version_id=None,
            status=VersionStatus.CANDIDATE,
            source_type=VersionSource(source_type),
            strategy_file_path=str(strategy_py_path),
            live_params_path=str(strategy_params_path),
            snapshot_strategy_path=snapshot_strategy_path,
            snapshot_params_path=snapshot_params_path,
            created_at=now,
            updated_at=now,
            notes=notes,
        )

        VersionStore.save_version(
            version,
            strategy_py_path,
            strategy_params_path,
            versions_root,
        )

        strategy_versions_dir = self._strategy_versions_dir(strategy_name)
        VersionIndex.update(strategy_versions_dir, version)

        _log.info(
            "Created candidate version %s for strategy '%s'",
            version_id,
            strategy_name,
        )
        return version

    # ------------------------------------------------------------------
    # Accept
    # ------------------------------------------------------------------

    def accept_version(self, version_id: str) -> StrategyVersion:
        """Accept a candidate version, making it the active version.

        Safe ordering:
        1. Copy snapshot files → live paths atomically (FIRST — before any state change).
        2. Move previous active → accepted (only after copy succeeds).
        3. Convert candidate → active, set base_version_id.
        4. Update index for both versions.

        Args:
            version_id: The ``version_id`` of the candidate to accept.

        Returns:
            The updated ``StrategyVersion`` now with status ``active``.

        Raises:
            ValueError: If the version is not found or its status is not ``candidate``.
        """
        version = self.get_version(version_id)
        if version is None:
            raise ValueError(f"Version {version_id} not found.")

        if version.status != VersionStatus.CANDIDATE:
            raise ValueError(
                f"Version {version_id} has status '{version.status.value}', "
                f"expected 'candidate'"
            )

        strategy_name = version.strategy_name
        versions_root = self._versions_root()
        version_dir = versions_root / strategy_name / version_id
        strategy_versions_dir = self._strategy_versions_dir(strategy_name)

        # Step 1 & 2: Copy snapshot files → live paths atomically (BEFORE state changes)
        _log.debug(
            "Copying snapshot files to live paths for version %s", version_id
        )
        self._atomic_copy(
            Path(version.snapshot_strategy_path),
            Path(version.strategy_file_path),
        )
        self._atomic_copy(
            Path(version.snapshot_params_path),
            Path(version.live_params_path),
        )
        _log.info(
            "Live files updated for version %s (strategy '%s')",
            version_id,
            strategy_name,
        )

        # Step 3: Move previous active → accepted (only after copy succeeded)
        previous_active = self.get_active_version(strategy_name)
        if previous_active is not None:
            prev_version_dir = versions_root / strategy_name / previous_active.version_id
            VersionStore.update_status(prev_version_dir, VersionStatus.ACCEPTED.value)
            previous_active.status = VersionStatus.ACCEPTED
            VersionIndex.update(strategy_versions_dir, previous_active)
            _log.info(
                "Moved previous active version %s → accepted",
                previous_active.version_id,
            )

        # Step 4: Convert candidate → active, set base_version_id
        VersionStore.update_status(version_dir, VersionStatus.ACTIVE.value)

        # Reload from disk to get updated timestamps, then set base_version_id
        new_active = VersionStore.load_version(version_dir)
        new_active.base_version_id = (
            previous_active.version_id if previous_active is not None else None
        )
        # Write back with base_version_id set (atomic)
        import json as _json
        version_json_path = version_dir / "version.json"
        data = _json.loads(version_json_path.read_text(encoding="utf-8"))
        data["base_version_id"] = new_active.base_version_id
        tmp = version_json_path.with_suffix(".tmp")
        tmp.write_text(_json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(version_json_path)

        # Reload final state
        new_active = VersionStore.load_version(version_dir)

        # Step 5: Update index for the new active version
        VersionIndex.update(strategy_versions_dir, new_active)

        _log.info(
            "Accepted version %s as active for strategy '%s'",
            version_id,
            strategy_name,
        )
        return new_active

    # ------------------------------------------------------------------
    # Reject
    # ------------------------------------------------------------------

    def reject_version(self, version_id: str) -> StrategyVersion:
        """Reject a candidate version.

        Args:
            version_id: The ``version_id`` of the candidate to reject.

        Returns:
            The updated ``StrategyVersion`` with status ``rejected``.

        Raises:
            ValueError: If the version is not found or its status is not ``candidate``.
        """
        version = self.get_version(version_id)
        if version is None:
            raise ValueError(f"Version {version_id} not found.")

        if version.status != VersionStatus.CANDIDATE:
            raise ValueError(
                f"Version {version_id} has status '{version.status.value}', "
                f"expected 'candidate'"
            )

        strategy_name = version.strategy_name
        versions_root = self._versions_root()
        version_dir = versions_root / strategy_name / version_id
        strategy_versions_dir = self._strategy_versions_dir(strategy_name)

        VersionStore.update_status(version_dir, VersionStatus.REJECTED.value)
        updated = VersionStore.load_version(version_dir)
        VersionIndex.update(strategy_versions_dir, updated)

        _log.info(
            "Rejected version %s for strategy '%s'", version_id, strategy_name
        )
        return updated

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_active_version(self, strategy_name: str) -> Optional[StrategyVersion]:
        """Return the currently active version for a strategy, or None.

        Uses the index as a fast lookup, then loads the full version from disk.

        Args:
            strategy_name: Name of the strategy.

        Returns:
            The active ``StrategyVersion``, or ``None`` if no active version exists.
        """
        strategy_versions_dir = self._strategy_versions_dir(strategy_name)
        versions = VersionIndex.load(strategy_versions_dir)
        for v in versions:
            if v.status == VersionStatus.ACTIVE:
                return v
        return None

    def list_versions(self, strategy_name: str) -> List[StrategyVersion]:
        """Return all versions for a strategy, sorted by created_at descending.

        Args:
            strategy_name: Name of the strategy.

        Returns:
            List of ``StrategyVersion`` objects, newest first.
        """
        strategy_versions_dir = self._strategy_versions_dir(strategy_name)
        return VersionIndex.load(strategy_versions_dir)

    def get_version(self, version_id: str) -> Optional[StrategyVersion]:
        """Find and return a version by its ID, scanning all strategy directories.

        The index is not used here — this reads directly from disk (version.json).

        Args:
            version_id: The UUID string of the version to find.

        Returns:
            The matching ``StrategyVersion``, or ``None`` if not found.
        """
        try:
            versions_root = self._versions_root()
        except ValueError:
            return None

        if not versions_root.exists():
            return None

        for strategy_dir in versions_root.iterdir():
            if not strategy_dir.is_dir():
                continue
            version_dir = strategy_dir / version_id
            if not version_dir.is_dir():
                continue
            try:
                sv = VersionStore.load_version(version_dir)
                if sv.version_id == version_id:
                    return sv
            except (FileNotFoundError, Exception):  # noqa: BLE001
                continue

        return None

    def get_version_for_run(self, run_meta: dict) -> Optional[StrategyVersion]:
        """Retrieve the version associated with a backtest run.

        The source of truth is ``run_meta["version_id"]`` from ``meta.json``.
        The index is cache only — this loads from disk via ``get_version``.

        Args:
            run_meta: Dict loaded from a run's ``meta.json``.

        Returns:
            The associated ``StrategyVersion``, or ``None`` if not found or
            ``version_id`` is absent/unknown.
        """
        version_id = run_meta.get("version_id")
        if not version_id:
            return None
        return self.get_version(version_id)

    # ------------------------------------------------------------------
    # Diff preview
    # ------------------------------------------------------------------

    def build_diff_preview(self, candidate_version_id: str) -> Dict[str, str]:
        """Build a unified diff between live files and a candidate's snapshots.

        Compares:
        - Live ``strategy_file_path`` vs ``snapshot_strategy_path``
        - Live ``live_params_path`` vs ``snapshot_params_path``

        Args:
            candidate_version_id: The ``version_id`` of the candidate version.

        Returns:
            Dict with keys ``"strategy_diff"`` and ``"params_diff"``, each
            containing a unified diff string (empty string if files are identical
            or a file is missing).

        Raises:
            ValueError: If the version is not found.
        """
        version = self.get_version(candidate_version_id)
        if version is None:
            raise ValueError(f"Version {candidate_version_id} not found.")

        strategy_diff = self._unified_diff(
            Path(version.strategy_file_path),
            Path(version.snapshot_strategy_path),
            fromfile="live/strategy.py",
            tofile=f"candidate/{candidate_version_id}/strategy.py",
        )

        params_diff = self._unified_diff(
            Path(version.live_params_path),
            Path(version.snapshot_params_path),
            fromfile="live/strategy_params.json",
            tofile=f"candidate/{candidate_version_id}/strategy_params.json",
        )

        return {"strategy_diff": strategy_diff, "params_diff": params_diff}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _atomic_copy(source: Path, target: Path) -> None:
        """Copy source → target atomically via a temp file + Path.replace().

        Args:
            source: Source file path.
            target: Destination file path.
        """
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        shutil.copy2(source, tmp)
        tmp.replace(target)

    @staticmethod
    def _unified_diff(
        live_path: Path,
        snapshot_path: Path,
        fromfile: str,
        tofile: str,
    ) -> str:
        """Generate a unified diff between two files.

        Args:
            live_path: Path to the live (current) file.
            snapshot_path: Path to the snapshot (candidate) file.
            fromfile: Label for the live file in the diff header.
            tofile: Label for the snapshot file in the diff header.

        Returns:
            Unified diff string, or empty string if either file is missing.
        """
        try:
            live_lines = live_path.read_text(encoding="utf-8").splitlines(keepends=True)
        except (FileNotFoundError, OSError):
            _log.warning("Live file not found for diff: %s", live_path)
            live_lines = []

        try:
            snapshot_lines = snapshot_path.read_text(encoding="utf-8").splitlines(
                keepends=True
            )
        except (FileNotFoundError, OSError):
            _log.warning("Snapshot file not found for diff: %s", snapshot_path)
            snapshot_lines = []

        diff = difflib.unified_diff(
            live_lines,
            snapshot_lines,
            fromfile=fromfile,
            tofile=tofile,
        )
        return "".join(diff)
