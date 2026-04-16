"""Unit tests for VersionStore — save, load, update_status."""
import json
import time

import pytest

from app.core.versioning.version_models import (
    StrategyVersion,
    VersionSource,
    VersionStatus,
)
from app.core.versioning.version_store import VersionStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_version(tmp_path, version_id="v-001", strategy="MyStrategy") -> StrategyVersion:
    version_dir = tmp_path / "strategy_versions" / strategy / version_id
    return StrategyVersion(
        version_id=version_id,
        strategy_name=strategy,
        base_version_id=None,
        status=VersionStatus.CANDIDATE,
        source_type=VersionSource.MANUAL_EDIT,
        strategy_file_path=str(tmp_path / "strategies" / f"{strategy}.py"),
        live_params_path=str(tmp_path / "strategies" / f"{strategy}.json"),
        snapshot_strategy_path=str(version_dir / "strategy.py"),
        snapshot_params_path=str(version_dir / "strategy_params.json"),
        created_at="2024-01-15T10:00:00.000000",
        updated_at="2024-01-15T10:00:00.000000",
    )


def create_source_files(tmp_path, strategy="MyStrategy"):
    """Create real strategy.py and params.json files in tmp_path."""
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir(parents=True, exist_ok=True)
    py_file = strategies_dir / f"{strategy}.py"
    json_file = strategies_dir / f"{strategy}.json"
    py_file.write_text("class MyStrategy: pass\n", encoding="utf-8")
    json_file.write_text('{"buy_params": {}}', encoding="utf-8")
    return py_file, json_file


# ---------------------------------------------------------------------------
# save_version
# ---------------------------------------------------------------------------

def test_save_version_creates_files(tmp_path):
    py_file, json_file = create_source_files(tmp_path)
    version = make_version(tmp_path)
    versions_root = tmp_path / "strategy_versions"

    version_dir = VersionStore.save_version(version, py_file, json_file, versions_root)

    assert (version_dir / "strategy.py").exists()
    assert (version_dir / "strategy_params.json").exists()
    assert (version_dir / "version.json").exists()


def test_save_version_snapshot_content_matches(tmp_path):
    py_file, json_file = create_source_files(tmp_path)
    version = make_version(tmp_path)
    versions_root = tmp_path / "strategy_versions"

    version_dir = VersionStore.save_version(version, py_file, json_file, versions_root)

    assert (version_dir / "strategy.py").read_text() == py_file.read_text()
    assert (version_dir / "strategy_params.json").read_text() == json_file.read_text()


def test_save_version_returns_correct_path(tmp_path):
    py_file, json_file = create_source_files(tmp_path)
    version = make_version(tmp_path)
    versions_root = tmp_path / "strategy_versions"

    version_dir = VersionStore.save_version(version, py_file, json_file, versions_root)

    assert version_dir == versions_root / "MyStrategy" / "v-001"


def test_save_version_missing_strategy_py(tmp_path):
    _, json_file = create_source_files(tmp_path)
    missing_py = tmp_path / "strategies" / "Missing.py"
    version = make_version(tmp_path)
    versions_root = tmp_path / "strategy_versions"

    with pytest.raises(FileNotFoundError, match="Strategy .py file not found"):
        VersionStore.save_version(version, missing_py, json_file, versions_root)


def test_save_version_missing_params_json(tmp_path):
    py_file, _ = create_source_files(tmp_path)
    missing_json = tmp_path / "strategies" / "Missing.json"
    version = make_version(tmp_path)
    versions_root = tmp_path / "strategy_versions"

    with pytest.raises(FileNotFoundError, match="Strategy params .json file not found"):
        VersionStore.save_version(version, py_file, missing_json, versions_root)


def test_save_version_duplicate_raises(tmp_path):
    py_file, json_file = create_source_files(tmp_path)
    version = make_version(tmp_path)
    versions_root = tmp_path / "strategy_versions"

    VersionStore.save_version(version, py_file, json_file, versions_root)

    with pytest.raises(ValueError, match="Version directory already exists"):
        VersionStore.save_version(version, py_file, json_file, versions_root)


# ---------------------------------------------------------------------------
# load_version
# ---------------------------------------------------------------------------

def test_load_version_round_trip(tmp_path):
    py_file, json_file = create_source_files(tmp_path)
    version = make_version(tmp_path)
    versions_root = tmp_path / "strategy_versions"

    version_dir = VersionStore.save_version(version, py_file, json_file, versions_root)
    loaded = VersionStore.load_version(version_dir)

    assert loaded.version_id == version.version_id
    assert loaded.strategy_name == version.strategy_name
    assert loaded.status == version.status
    assert loaded.source_type == version.source_type


def test_load_version_missing_file(tmp_path):
    nonexistent = tmp_path / "nonexistent_version"
    with pytest.raises(FileNotFoundError):
        VersionStore.load_version(nonexistent)


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------

def test_update_status_changes_status(tmp_path):
    py_file, json_file = create_source_files(tmp_path)
    version = make_version(tmp_path)
    versions_root = tmp_path / "strategy_versions"

    version_dir = VersionStore.save_version(version, py_file, json_file, versions_root)
    VersionStore.update_status(version_dir, "active")

    loaded = VersionStore.load_version(version_dir)
    assert loaded.status == VersionStatus.ACTIVE


def test_update_status_updates_updated_at(tmp_path):
    py_file, json_file = create_source_files(tmp_path)
    version = make_version(tmp_path)
    versions_root = tmp_path / "strategy_versions"

    version_dir = VersionStore.save_version(version, py_file, json_file, versions_root)
    original_updated_at = version.updated_at

    time.sleep(0.01)
    VersionStore.update_status(version_dir, "active")

    loaded = VersionStore.load_version(version_dir)
    assert loaded.updated_at != original_updated_at


def test_update_status_invalid_status(tmp_path):
    py_file, json_file = create_source_files(tmp_path)
    version = make_version(tmp_path)
    versions_root = tmp_path / "strategy_versions"

    version_dir = VersionStore.save_version(version, py_file, json_file, versions_root)

    with pytest.raises(ValueError):
        VersionStore.update_status(version_dir, "not_a_valid_status")


def test_update_status_missing_version_json(tmp_path):
    nonexistent = tmp_path / "no_version_dir"
    with pytest.raises(FileNotFoundError):
        VersionStore.update_status(nonexistent, "active")
