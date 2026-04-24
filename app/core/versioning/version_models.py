"""version_models.py — StrategyVersion dataclass and enums for the versioning layer."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class VersionStatus(str, Enum):
    ACTIVE = "active"
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class VersionSource(str, Enum):
    MANUAL_EDIT = "manual_edit"
    OPTIMIZE = "optimize"
    AI = "ai"
    RULE_BASED = "rule_based"
    HYPEROPT = "hyperopt"


@dataclass
class StrategyVersion:
    """A single version snapshot of a strategy."""

    version_id: str
    strategy_name: str
    base_version_id: Optional[str]
    status: VersionStatus
    source_type: VersionSource
    strategy_file_path: str
    live_params_path: str
    snapshot_strategy_path: str
    snapshot_params_path: str
    created_at: str
    updated_at: str
    notes: Optional[str] = None
    last_run_id: Optional[str] = None
    diff_summary: Optional[str] = None


def version_to_dict(v: StrategyVersion) -> dict:
    """Serialize a StrategyVersion to a JSON-safe dict."""
    return {
        "version_id": v.version_id,
        "strategy_name": v.strategy_name,
        "base_version_id": v.base_version_id,
        "status": v.status.value if isinstance(v.status, VersionStatus) else v.status,
        "source_type": v.source_type.value if isinstance(v.source_type, VersionSource) else v.source_type,
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


def version_from_dict(d: dict) -> StrategyVersion:
    """Deserialize a StrategyVersion from a dict.

    Raises:
        KeyError: If a required field is missing.
        ValueError: If status or source_type is not a valid enum value.
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
