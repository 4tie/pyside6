"""Index management for strategy versions.

Maintains a lightweight index.json per strategy that tracks all versions
without requiring a full scan of version directories on every listing.
All methods are static — no instance state required.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.core.utils.app_logger import get_logger
from app.core.parsing.json_parser import parse_json_with_default, write_json_file_atomic
from app.core.versioning.version_models import (
    StrategyVersion,
    VersionStatus,
    version_from_dict,
)
from app.core.versioning.version_store import VersionStore

_log = get_logger("services.versioning")

# Lightweight fields stored in index entries
_INDEX_FIELDS = ("version_id", "status", "source_type", "created_at", "base_version_id", "notes")


class VersionIndex:
    """Static methods for managing the per-strategy version index (index.json).

    The index is a lightweight cache — it stores only a subset of fields for
    fast listing. Full ``StrategyVersion`` objects are loaded from ``version.json``
    on disk when needed.

    Index file location::

        {strategy_versions_dir}/index.json

    where ``strategy_versions_dir`` = ``{versions_root}/{strategy_name}/``.
    """

    @staticmethod
    def update(strategy_versions_dir: Path, version: StrategyVersion) -> None:
        """Upsert a version entry in index.json.

        If a version with the same ``version_id`` already exists in the index,
        it is replaced. Otherwise the entry is appended. The ``updated_at``
        field at the index root is refreshed on every call.

        The write is atomic: data is written to a ``.tmp`` file first, then
        renamed to the final path.

        Args:
            strategy_versions_dir: Path to the strategy-specific versions directory
                (i.e. ``{versions_root}/{strategy_name}/``).
            version: The ``StrategyVersion`` whose entry should be upserted.
        """
        index_path = strategy_versions_dir / "index.json"
        index_data = VersionIndex._read_raw(index_path)

        # Build the lightweight entry
        entry = VersionIndex._to_entry(version)

        # Upsert: replace existing entry or append
        versions_list: List[Dict] = index_data.get("versions", [])
        replaced = False
        for i, v in enumerate(versions_list):
            if v.get("version_id") == version.version_id:
                versions_list[i] = entry
                replaced = True
                break
        if not replaced:
            versions_list.append(entry)

        index_data["strategy"] = version.strategy_name
        index_data["updated_at"] = datetime.now().isoformat()
        index_data["versions"] = versions_list

        strategy_versions_dir.mkdir(parents=True, exist_ok=True)
        VersionIndex._write_atomic(index_path, index_data)
        _log.debug(
            "Index updated for version %s (strategy '%s')",
            version.version_id,
            version.strategy_name,
        )

    @staticmethod
    def load(strategy_versions_dir: Path) -> List[StrategyVersion]:
        """Load all versions for a strategy, sorted by ``created_at`` descending.

        For each entry in the index, the full ``StrategyVersion`` is loaded from
        the corresponding ``version.json`` on disk. Entries whose ``version.json``
        is missing or malformed are skipped with a warning.

        Args:
            strategy_versions_dir: Path to the strategy-specific versions directory.

        Returns:
            List of ``StrategyVersion`` objects sorted by ``created_at`` descending
            (newest first). Returns an empty list if ``index.json`` does not exist.
        """
        index_path = strategy_versions_dir / "index.json"

        if not index_path.exists():
            _log.debug("index.json not found at %s — returning []", index_path)
            return []

        index_data = VersionIndex._read_raw(index_path)
        versions_list: List[Dict] = index_data.get("versions", [])

        loaded: List[StrategyVersion] = []
        for entry in versions_list:
            version_id = entry.get("version_id", "<unknown>")
            version_dir = strategy_versions_dir / version_id
            try:
                sv = VersionStore.load_version(version_dir)
                loaded.append(sv)
            except FileNotFoundError:
                _log.warning(
                    "version.json missing for version %s — skipping index entry",
                    version_id,
                )
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "Failed to load version %s from disk: %s — skipping",
                    version_id,
                    exc,
                )

        loaded.sort(key=lambda v: v.created_at, reverse=True)
        return loaded

    @staticmethod
    def rebuild(strategy_versions_dir: Path, strategy_name: str) -> List[StrategyVersion]:
        """Scan version directories and reconstruct index.json from scratch.

        Iterates over all subdirectories of ``strategy_versions_dir``, treating
        each as a potential version directory. Attempts to load ``version.json``
        from each. Malformed or missing files are skipped with a warning.

        Enforces the at-most-one-active invariant: if multiple versions carry
        ``active`` status, the one with the latest ``created_at`` is kept as
        ``active``; all others are demoted to ``accepted`` (their ``version.json``
        files are updated via ``VersionStore.update_status``).

        The rebuilt index is written atomically.

        Args:
            strategy_versions_dir: Path to the strategy-specific versions directory.
            strategy_name: Name of the strategy (used to populate the index root).

        Returns:
            List of ``StrategyVersion`` objects sorted by ``created_at`` descending.
        """
        if not strategy_versions_dir.exists():
            _log.debug(
                "strategy_versions_dir does not exist: %s — returning []",
                strategy_versions_dir,
            )
            return []

        loaded: List[StrategyVersion] = []

        for subdir in sorted(strategy_versions_dir.iterdir()):
            if not subdir.is_dir():
                continue  # skip index.json and any stray files
            try:
                sv = VersionStore.load_version(subdir)
                loaded.append(sv)
            except FileNotFoundError:
                _log.warning(
                    "version.json missing in directory %s — skipping during rebuild",
                    subdir,
                )
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "Corrupt version.json in %s: %s — skipping during rebuild",
                    subdir,
                    exc,
                )

        # Enforce at-most-one-active invariant
        active_versions = [v for v in loaded if v.status == VersionStatus.ACTIVE]
        if len(active_versions) > 1:
            # Keep the one with the latest created_at as active
            active_versions.sort(key=lambda v: v.created_at, reverse=True)
            keep_active = active_versions[0]
            to_demote = active_versions[1:]

            for demoted in to_demote:
                _log.warning(
                    "Multiple active versions detected for strategy '%s'. "
                    "Demoting version %s (created_at=%s) from 'active' to 'accepted'.",
                    strategy_name,
                    demoted.version_id,
                    demoted.created_at,
                )
                version_dir = strategy_versions_dir / demoted.version_id
                try:
                    VersionStore.update_status(version_dir, VersionStatus.ACCEPTED.value)
                    # Reflect the change in our in-memory list
                    demoted.status = VersionStatus.ACCEPTED
                except Exception as exc:  # noqa: BLE001
                    _log.error(
                        "Failed to demote version %s: %s",
                        demoted.version_id,
                        exc,
                    )

            _log.info(
                "Kept version %s as the sole active version for strategy '%s'.",
                keep_active.version_id,
                strategy_name,
            )

        # Sort newest first
        loaded.sort(key=lambda v: v.created_at, reverse=True)

        # Rewrite index.json atomically
        index_path = strategy_versions_dir / "index.json"
        index_data: Dict = {
            "strategy": strategy_name,
            "updated_at": datetime.now().isoformat(),
            "versions": [VersionIndex._to_entry(v) for v in loaded],
        }
        strategy_versions_dir.mkdir(parents=True, exist_ok=True)
        VersionIndex._write_atomic(index_path, index_data)
        _log.info(
            "Rebuilt index for strategy '%s' with %d version(s).",
            strategy_name,
            len(loaded),
        )

        return loaded

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_entry(version: StrategyVersion) -> Dict:
        """Build a lightweight index entry dict from a StrategyVersion.

        Args:
            version: The source ``StrategyVersion``.

        Returns:
            Dict containing only the lightweight index fields.
        """
        return {
            "version_id": version.version_id,
            "status": version.status.value if hasattr(version.status, "value") else version.status,
            "source_type": version.source_type.value if hasattr(version.source_type, "value") else version.source_type,
            "created_at": version.created_at,
            "base_version_id": version.base_version_id,
            "notes": version.notes,
        }

    @staticmethod
    def _read_raw(index_path: Path) -> Dict:
        """Read and parse index.json, returning an empty structure if missing.

        Args:
            index_path: Path to the index.json file.

        Returns:
            Parsed dict, or ``{"versions": []}`` if the file does not exist.
        """
        return parse_json_with_default(index_path, {"versions": []})

    @staticmethod
    def _write_atomic(path: Path, data: Dict) -> None:
        """Write a dict as JSON to ``path`` atomically via a temp file + rename.

        Args:
            path: Target file path.
            data: Dict to serialize as JSON.
        """
        write_json_file_atomic(path, data)
