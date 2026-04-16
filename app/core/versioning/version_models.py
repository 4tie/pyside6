"""Data models for the strategy versioning system.

Defines StrategyVersion DTO, VersionStatus and VersionSource enums,
and serialization helpers version_to_dict / version_from_dict.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from app.core.utils.app_logger import get_logger

_log = get_logger("services.versioning")


class VersionStatus(str, Enum):
    """Lifecycle status of a strategy version.

    Uses str mixin so values serialize directly to JSON without extra conversion.
    """

    ACTIVE = "active"
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class VersionSource(str, Enum):
    """Source / origin of a strategy version.

    Uses str mixin so values serialize directly to JSON without extra conversion.
    """

    MANUAL_EDIT = "manual_edit"
    OPTIMIZE = "optimize"
    AI_CANDIDATE = "ai_candidate_future"
    RULE_BASED = "rule_based_future"


@dataclass
class StrategyVersion:
    """Internal DTO representing a single strategy version.

    Attributes:
        version_id: UUID string uniquely identifying this version.
        strategy_name: Name of the strategy (e.g. "MyStrategy").
        base_version_id: version_id of the parent version, or None for the first version.
        status: Current lifecycle status of this version.
        source_type: How this version was created.
        strategy_file_path: Absolute path to the live strategy .py file.
        live_params_path: Absolute path to the live strategy params .json file.
        snapshot_strategy_path: Path to the snapshotted strategy.py inside the version dir.
        snapshot_params_path: Path to the snapshotted params json inside the version dir.
        created_at: ISO-8601 datetime string when the version was created.
        updated_at: ISO-8601 datetime string of the last status change.
        notes: Optional free-text notes attached to this version.
        last_run_id: run_id of the most recent backtest run using this version.
        diff_summary: Human-readable summary of changes vs base_version (for UI display).
    """

    # --- Identity ---
    version_id: str
    strategy_name: str
    base_version_id: Optional[str]

    # --- State ---
    status: VersionStatus
    source_type: VersionSource

    # --- Live file paths ---
    strategy_file_path: str
    live_params_path: str

    # --- Snapshot paths ---
    snapshot_strategy_path: str
    snapshot_params_path: str

    # --- Timestamps ---
    created_at: str
    updated_at: str

    # --- Optional / future ---
    notes: Optional[str] = None
    last_run_id: Optional[str] = None
    diff_summary: Optional[str] = None


def version_to_dict(v: StrategyVersion) -> Dict:
    """Serialize a StrategyVersion to a plain dict suitable for JSON storage.

    Enum values are converted to their string representations.

    Args:
        v: The StrategyVersion instance to serialize.

    Returns:
        A dict with all fields serialized to JSON-compatible types.
    """
    return {
        "version_id": v.version_id,
        "strategy_name": v.strategy_name,
        "base_version_id": v.base_version_id,
        "status": v.status.value,
        "source_type": v.source_type.value,
        "strategy_file_path": v.strategy_file_path,
        "live_params_path": v.live_params_path,
        "snapshot_strategy_path": v.snapshot_strategy_path,
        "snapshot_params_path": v.snapshot_params_path,
        "created_at": v.created_at,
        "updated_at": v.updated_at,
        "notes": v.notes,
        "last_run_id": v.last_run_id,
        "diff_summary": v.diff_summary,
    }


def version_from_dict(d: Dict) -> StrategyVersion:
    """Deserialize a StrategyVersion from a plain dict (e.g. loaded from JSON).

    Args:
        d: Dict containing all StrategyVersion fields.

    Returns:
        A fully reconstructed StrategyVersion instance.

    Raises:
        KeyError: If a required field is missing from the dict.
        ValueError: If an enum value is unrecognized.
    """
    return StrategyVersion(
        version_id=d["version_id"],
        strategy_name=d["strategy_name"],
        base_version_id=d.get("base_version_id"),
        status=VersionStatus(d["status"]),
        source_type=VersionSource(d["source_type"]),
        strategy_file_path=d["strategy_file_path"],
        live_params_path=d["live_params_path"],
        snapshot_strategy_path=d["snapshot_strategy_path"],
        snapshot_params_path=d["snapshot_params_path"],
        created_at=d["created_at"],
        updated_at=d["updated_at"],
        notes=d.get("notes"),
        last_run_id=d.get("last_run_id"),
        diff_summary=d.get("diff_summary"),
    )
