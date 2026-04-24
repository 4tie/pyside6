"""
version_manager_service.py — Service for managing strategy versions.

Provides version creation, storage, retrieval, and rollback capabilities.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import List, Optional

from app.core.models.version_models import StrategyVersion, VersionLineage
from app.core.utils.app_logger import get_logger

_log = get_logger("services.version_manager")


class VersionManagerService:
    """Service for managing strategy versions and lineage.

    Stores versions in user_data/strategy_versions/{strategy_name}/
    with JSON files named {version_id}.json
    """

    _VERSIONS_DIR_NAME = "strategy_versions"

    def __init__(self, user_data_path: str) -> None:
        """Initialize with user data path.

        Args:
            user_data_path: Path to user_data directory.
        """
        self._user_data_path = Path(user_data_path)
        self._versions_root = self._user_data_path / self._VERSIONS_DIR_NAME
        self._versions_root.mkdir(parents=True, exist_ok=True)
        _log.debug("VersionManager initialized with root: %s", self._versions_root)

    def _get_strategy_dir(self, strategy_name: str) -> Path:
        """Get the versions directory for a specific strategy."""
        return self._versions_root / strategy_name

    def create_version(
        self,
        strategy_name: str,
        params: dict,
        summary: any,
        iteration_number: int,
        changes_summary: List[str],
        parent_version_id: Optional[str] = None,
        score: float = 0.0,
        exit_reason_analysis: Optional[dict] = None,
    ) -> StrategyVersion:
        """Create and save a new version.

        Args:
            strategy_name: Name of the strategy.
            params: Strategy parameters.
            summary: BacktestSummary or dict.
            iteration_number: Iteration number.
            changes_summary: List of change descriptions.
            parent_version_id: ID of parent version.
            score: RobustScore total.
            exit_reason_analysis: Optional exit reason stats.

        Returns:
            The created StrategyVersion.
        """
        version = StrategyVersion.from_iteration(
            strategy_name=strategy_name,
            params=params.copy(),
            summary=summary,
            iteration_number=iteration_number,
            changes_summary=changes_summary.copy(),
            parent_version_id=parent_version_id,
            score=score,
            exit_reason_analysis=exit_reason_analysis,
        )

        strategy_dir = self._get_strategy_dir(strategy_name)
        strategy_dir.mkdir(parents=True, exist_ok=True)

        version.save(self._versions_root)

        _log.info(
            "Created version %s for %s (iter #%d)",
            version.version_id,
            strategy_name,
            iteration_number,
        )

        return version

    def load_version(self, strategy_name: str, version_id: str) -> Optional[StrategyVersion]:
        """Load a specific version.

        Args:
            strategy_name: Name of the strategy.
            version_id: Version ID to load.

        Returns:
            StrategyVersion or None if not found.
        """
        version_file = self._get_strategy_dir(strategy_name) / f"{version_id}.json"

        if not version_file.exists():
            _log.warning("Version %s not found for %s", version_id, strategy_name)
            return None

        try:
            return StrategyVersion.load(version_file)
        except Exception as e:
            _log.error("Failed to load version %s: %s", version_id, e)
            return None

    def load_all_versions(self, strategy_name: str) -> List[StrategyVersion]:
        """Load all versions for a strategy.

        Args:
            strategy_name: Name of the strategy.

        Returns:
            List of StrategyVersion objects, sorted by creation time.
        """
        strategy_dir = self._get_strategy_dir(strategy_name)

        if not strategy_dir.exists():
            return []

        versions = []
        for version_file in sorted(strategy_dir.glob("v*.json")):
            try:
                version = StrategyVersion.load(version_file)
                versions.append(version)
            except Exception as e:
                _log.warning("Failed to load version from %s: %s", version_file, e)

        return sorted(versions, key=lambda v: v.created_at)

    def load_lineage(self, strategy_name: str) -> VersionLineage:
        """Load complete version lineage for a strategy.

        Args:
            strategy_name: Name of the strategy.

        Returns:
            VersionLineage with all versions.
        """
        versions = self.load_all_versions(strategy_name)

        lineage = VersionLineage(strategy_name=strategy_name)

        # Find best version
        best_version = None
        best_score = float("-inf")

        for version in versions:
            lineage.add_version(version)
            if version.score > best_score:
                best_score = version.score
                best_version = version.version_id

        if best_version:
            lineage.update_best_version(best_version)

        _log.debug(
            "Loaded lineage for %s: %d versions, best=%s",
            strategy_name,
            len(versions),
            best_version,
        )

        return lineage

    def update_best_version(
        self,
        strategy_name: str,
        version_id: str,
    ) -> bool:
        """Mark a version as the best version.

        Args:
            strategy_name: Name of the strategy.
            version_id: ID of the best version.

        Returns:
            True if successful, False otherwise.
        """
        version = self.load_version(strategy_name, version_id)
        if not version:
            return False

        version.is_best = True

        # Unmark other versions
        for v in self.load_all_versions(strategy_name):
            if v.version_id != version_id and v.is_best:
                v.is_best = False
                v.save(self._versions_root)

        version.save(self._versions_root)

        _log.info("Marked %s as best version for %s", version_id, strategy_name)
        return True

    def rollback_to_version(
        self,
        strategy_name: str,
        version_id: str,
    ) -> Optional[dict]:
        """Get parameters for rolling back to a specific version.

        Args:
            strategy_name: Name of the strategy.
            version_id: Version ID to rollback to.

        Returns:
            Dict of parameters from that version, or None if not found.
        """
        version = self.load_version(strategy_name, version_id)
        if not version:
            _log.error("Cannot rollback: version %s not found", version_id)
            return None

        _log.info(
            "Rollback to version %s for %s (iter #%d)",
            version_id,
            strategy_name,
            version.iteration_number,
        )

        return version.params.copy()

    def get_version_comparison(
        self,
        strategy_name: str,
        version_id_a: str,
        version_id_b: str,
    ) -> Optional[dict]:
        """Compare two versions side-by-side.

        Args:
            strategy_name: Name of the strategy.
            version_id_a: First version ID.
            version_id_b: Second version ID.

        Returns:
            Comparison dict with both versions' metrics, or None if not found.
        """
        v_a = self.load_version(strategy_name, version_id_a)
        v_b = self.load_version(strategy_name, version_id_b)

        if not v_a or not v_b:
            return None

        return {
            "version_a": {
                "id": v_a.version_id,
                "iteration": v_a.iteration_number,
                "changes": v_a.changes_summary,
                "profit": v_a.summary.get("total_profit", 0),
                "win_rate": v_a.summary.get("win_rate", 0),
                "drawdown": v_a.summary.get("max_drawdown", 0),
                "trades": v_a.summary.get("total_trades", 0),
                "score": v_a.score,
                "is_best": v_a.is_best,
            },
            "version_b": {
                "id": v_b.version_id,
                "iteration": v_b.iteration_number,
                "changes": v_b.changes_summary,
                "profit": v_b.summary.get("total_profit", 0),
                "win_rate": v_b.summary.get("win_rate", 0),
                "drawdown": v_b.summary.get("max_drawdown", 0),
                "trades": v_b.summary.get("total_trades", 0),
                "score": v_b.score,
                "is_best": v_b.is_best,
            },
            "profit_diff": v_b.summary.get("total_profit", 0) - v_a.summary.get("total_profit", 0),
            "winrate_diff": v_b.summary.get("win_rate", 0) - v_a.summary.get("win_rate", 0),
            "drawdown_diff": v_b.summary.get("max_drawdown", 0) - v_a.summary.get("max_drawdown", 0),
            "score_diff": v_b.score - v_a.score,
        }

    def delete_version(self, strategy_name: str, version_id: str) -> bool:
        """Delete a specific version.

        Args:
            strategy_name: Name of the strategy.
            version_id: Version ID to delete.

        Returns:
            True if deleted, False otherwise.
        """
        version_file = self._get_strategy_dir(strategy_name) / f"{version_id}.json"

        if not version_file.exists():
            return False

        try:
            version_file.unlink()
            _log.info("Deleted version %s for %s", version_id, strategy_name)
            return True
        except Exception as e:
            _log.error("Failed to delete version %s: %s", version_id, e)
            return False

    def cleanup_old_versions(
        self,
        strategy_name: str,
        keep_count: int = 50,
        keep_best: bool = True,
    ) -> int:
        """Remove old versions, keeping the most recent and best.

        Args:
            strategy_name: Name of the strategy.
            keep_count: Number of recent versions to keep.
            keep_best: Whether to always keep the best version.

        Returns:
            Number of versions deleted.
        """
        versions = self.load_all_versions(strategy_name)

        if len(versions) <= keep_count:
            return 0

        # Sort by creation date (newest first)
        versions = sorted(versions, key=lambda v: v.created_at, reverse=True)

        # Keep the most recent and optionally the best
        best_id = None
        if keep_best:
            best = max(versions, key=lambda v: v.score, default=None)
            if best:
                best_id = best.version_id

        to_keep = set(v.version_id for v in versions[:keep_count])
        if best_id:
            to_keep.add(best_id)

        deleted_count = 0
        for version in versions:
            if version.version_id not in to_keep:
                if self.delete_version(strategy_name, version.version_id):
                    deleted_count += 1

        _log.info(
            "Cleaned up %d old versions for %s, kept %d",
            deleted_count,
            strategy_name,
            len(to_keep),
        )

        return deleted_count

    def export_version_to_strategy(
        self,
        strategy_name: str,
        version_id: str,
        strategies_dir: Path,
    ) -> bool:
        """Export a version's parameters to the live strategy JSON file.

        Args:
            strategy_name: Name of the strategy.
            version_id: Version ID to export.
            strategies_dir: Path to strategies directory.

        Returns:
            True if exported successfully, False otherwise.
        """
        version = self.load_version(strategy_name, version_id)
        if not version:
            return False

        strategy_json = strategies_dir / f"{strategy_name}.json"

        try:
            # Load existing strategy JSON if present
            if strategy_json.exists():
                data = parse_json_file(strategy_json)
            else:
                data = {
                    "strategy_name": strategy_name,
                    "params": {},
                    "ft_stratparam_v": 1,
                }

            # Update params with version params
            data["params"] = version.params.copy()
            data["export_time"] = version.created_at
            data["version_id"] = version.version_id

            # Write back
            strategy_json.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )

            _log.info(
                "Exported version %s to %s",
                version_id,
                strategy_json,
            )
            return True

        except Exception as e:
            _log.error("Failed to export version %s: %s", version_id, e)
            return False
