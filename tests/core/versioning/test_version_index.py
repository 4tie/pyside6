"""Unit tests for VersionIndex — load, update, rebuild, invariants."""
import json
import pytest

from app.core.versioning.version_index import VersionIndex
from app.core.versioning.version_models import (
    StrategyVersion,
    VersionSource,
    VersionStatus,
    version_to_dict,
)
from app.core.versioning.version_store import VersionStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_version(
    version_id: str,
    strategy: str = "MyStrategy",
    status: VersionStatus = VersionStatus.CANDIDATE,
    created_at: str = "2024-01-15T10:00:00.000000",
    base_version_id=None,
) -> StrategyVersion:
    return StrategyVersion(
        version_id=version_id,
        strategy_name=strategy,
        base_version_id=base_version_id,
        status=status,
        source_type=VersionSource.MANUAL_EDIT,
        strategy_file_path=f"/data/strategies/{strategy}.py",
        live_params_path=f"/data/strategies/{strategy}.json",
        snapshot_strategy_path=f"/data/versions/{strategy}/{version_id}/strategy.py",
        snapshot_params_path=f"/data/versions/{strategy}/{version_id}/strategy_params.json",
        created_at=created_at,
        updated_at=created_at,
    )


def write_version_to_disk(strategy_versions_dir, version: StrategyVersion):
    """Write a version.json to disk so VersionIndex.load can find it."""
    version_dir = strategy_versions_dir / version.version_id
    version_dir.mkdir(parents=True, exist_ok=True)
    version_json = version_dir / "version.json"
    version_json.write_text(json.dumps(version_to_dict(version), indent=2), encoding="utf-8")
    return version_dir


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

def test_load_returns_empty_when_missing(tmp_path):
    result = VersionIndex.load(tmp_path / "nonexistent_strategy")
    assert result == []


def test_load_returns_empty_when_index_missing_but_dir_exists(tmp_path):
    strategy_dir = tmp_path / "MyStrategy"
    strategy_dir.mkdir()
    result = VersionIndex.load(strategy_dir)
    assert result == []


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

def test_update_creates_index_json(tmp_path):
    strategy_dir = tmp_path / "MyStrategy"
    version = make_version("v-001")
    write_version_to_disk(strategy_dir, version)

    VersionIndex.update(strategy_dir, version)

    assert (strategy_dir / "index.json").exists()


def test_update_then_load_returns_version(tmp_path):
    strategy_dir = tmp_path / "MyStrategy"
    version = make_version("v-001")
    write_version_to_disk(strategy_dir, version)

    VersionIndex.update(strategy_dir, version)
    loaded = VersionIndex.load(strategy_dir)

    assert len(loaded) == 1
    assert loaded[0].version_id == "v-001"


def test_update_upserts_existing_entry(tmp_path):
    strategy_dir = tmp_path / "MyStrategy"
    version = make_version("v-001", status=VersionStatus.CANDIDATE)
    write_version_to_disk(strategy_dir, version)
    VersionIndex.update(strategy_dir, version)

    # Update status on disk and in index
    version_dir = strategy_dir / "v-001"
    VersionStore.update_status(version_dir, "active")
    updated_version = VersionStore.load_version(version_dir)
    VersionIndex.update(strategy_dir, updated_version)

    loaded = VersionIndex.load(strategy_dir)
    assert len(loaded) == 1
    assert loaded[0].status == VersionStatus.ACTIVE


def test_update_multiple_versions(tmp_path):
    strategy_dir = tmp_path / "MyStrategy"
    v1 = make_version("v-001", created_at="2024-01-15T10:00:00.000000")
    v2 = make_version("v-002", created_at="2024-01-15T11:00:00.000000")

    write_version_to_disk(strategy_dir, v1)
    write_version_to_disk(strategy_dir, v2)
    VersionIndex.update(strategy_dir, v1)
    VersionIndex.update(strategy_dir, v2)

    loaded = VersionIndex.load(strategy_dir)
    assert len(loaded) == 2


# ---------------------------------------------------------------------------
# rebuild
# ---------------------------------------------------------------------------

def test_rebuild_skips_corrupt_file(tmp_path):
    strategy_dir = tmp_path / "MyStrategy"
    strategy_dir.mkdir(parents=True)

    # Valid version
    v1 = make_version("v-valid")
    write_version_to_disk(strategy_dir, v1)

    # Corrupt version dir
    corrupt_dir = strategy_dir / "v-corrupt"
    corrupt_dir.mkdir()
    (corrupt_dir / "version.json").write_text("{ not valid json !!!", encoding="utf-8")

    result = VersionIndex.rebuild(strategy_dir, "MyStrategy")

    assert len(result) == 1
    assert result[0].version_id == "v-valid"


def test_rebuild_at_most_one_active(tmp_path):
    strategy_dir = tmp_path / "MyStrategy"
    strategy_dir.mkdir(parents=True)

    # Create 3 versions all with status "active"
    v1 = make_version("v-001", status=VersionStatus.ACTIVE, created_at="2024-01-15T08:00:00.000000")
    v2 = make_version("v-002", status=VersionStatus.ACTIVE, created_at="2024-01-15T09:00:00.000000")
    v3 = make_version("v-003", status=VersionStatus.ACTIVE, created_at="2024-01-15T10:00:00.000000")

    write_version_to_disk(strategy_dir, v1)
    write_version_to_disk(strategy_dir, v2)
    write_version_to_disk(strategy_dir, v3)

    result = VersionIndex.rebuild(strategy_dir, "MyStrategy")

    active_versions = [v for v in result if v.status == VersionStatus.ACTIVE]
    accepted_versions = [v for v in result if v.status == VersionStatus.ACCEPTED]

    assert len(active_versions) == 1
    assert len(accepted_versions) == 2
    # Newest (v-003) should be kept as active
    assert active_versions[0].version_id == "v-003"


def test_rebuild_with_missing_version_json_skips(tmp_path):
    strategy_dir = tmp_path / "MyStrategy"
    strategy_dir.mkdir(parents=True)

    # Valid version
    v1 = make_version("v-valid")
    write_version_to_disk(strategy_dir, v1)

    # Dir without version.json
    empty_dir = strategy_dir / "v-empty"
    empty_dir.mkdir()

    result = VersionIndex.rebuild(strategy_dir, "MyStrategy")
    assert len(result) == 1


# ---------------------------------------------------------------------------
# load — sort order
# ---------------------------------------------------------------------------

def test_load_sorted_descending(tmp_path):
    strategy_dir = tmp_path / "MyStrategy"

    v1 = make_version("v-001", created_at="2024-01-15T08:00:00.000000")
    v2 = make_version("v-002", created_at="2024-01-15T10:00:00.000000")
    v3 = make_version("v-003", created_at="2024-01-15T09:00:00.000000")

    for v in (v1, v2, v3):
        write_version_to_disk(strategy_dir, v)
        VersionIndex.update(strategy_dir, v)

    loaded = VersionIndex.load(strategy_dir)

    assert len(loaded) == 3
    assert loaded[0].version_id == "v-002"  # newest
    assert loaded[1].version_id == "v-003"
    assert loaded[2].version_id == "v-001"  # oldest
