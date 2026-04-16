"""Unit tests for VersioningService — full lifecycle, accept, reject, queries, diff."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.core.versioning.version_models import VersionStatus
from app.core.versioning.versioning_service import VersioningService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_settings_service(tmp_path):
    svc = MagicMock()
    svc.settings.user_data_path = str(tmp_path)
    return svc


def create_strategy_files(tmp_path, strategy="MyStrategy", py_content=None, json_content=None):
    """Create real strategy.py and params.json files."""
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir(parents=True, exist_ok=True)
    py_file = strategies_dir / f"{strategy}.py"
    json_file = strategies_dir / f"{strategy}.json"
    py_file.write_text(py_content or "class MyStrategy:\n    pass\n", encoding="utf-8")
    json_file.write_text(json_content or '{"buy_params": {}}', encoding="utf-8")
    return py_file, json_file


# ---------------------------------------------------------------------------
# create_candidate
# ---------------------------------------------------------------------------

def test_create_candidate_status_is_candidate(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    version = svc.create_candidate("MyStrategy", py_file, json_file)

    assert version.status == VersionStatus.CANDIDATE


def test_create_candidate_version_id_is_uuid(tmp_path):
    import uuid
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    version = svc.create_candidate("MyStrategy", py_file, json_file)

    # Should not raise
    uuid.UUID(version.version_id)


def test_create_candidate_snapshot_files_exist(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    version = svc.create_candidate("MyStrategy", py_file, json_file)

    assert Path(version.snapshot_strategy_path).exists()
    assert Path(version.snapshot_params_path).exists()


def test_create_candidate_with_notes(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    version = svc.create_candidate("MyStrategy", py_file, json_file, notes="test note")

    assert version.notes == "test note"


def test_create_candidate_unique_ids(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    v1 = svc.create_candidate("MyStrategy", py_file, json_file)
    v2 = svc.create_candidate("MyStrategy", py_file, json_file)

    assert v1.version_id != v2.version_id


# ---------------------------------------------------------------------------
# accept_version
# ---------------------------------------------------------------------------

def test_accept_version_status_becomes_active(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    candidate = svc.create_candidate("MyStrategy", py_file, json_file)
    active = svc.accept_version(candidate.version_id)

    assert active.status == VersionStatus.ACTIVE


def test_accept_version_copies_live_files(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path, py_content="class V1: pass\n")

    candidate = svc.create_candidate("MyStrategy", py_file, json_file)
    svc.accept_version(candidate.version_id)

    # Live file should match snapshot content
    assert py_file.read_text() == "class V1: pass\n"


def test_accept_version_demotes_previous_active(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    # First candidate → active
    c1 = svc.create_candidate("MyStrategy", py_file, json_file)
    svc.accept_version(c1.version_id)

    # Second candidate → active (should demote first)
    c2 = svc.create_candidate("MyStrategy", py_file, json_file)
    svc.accept_version(c2.version_id)

    v1_reloaded = svc.get_version(c1.version_id)
    v2_reloaded = svc.get_version(c2.version_id)

    assert v1_reloaded.status == VersionStatus.ACCEPTED
    assert v2_reloaded.status == VersionStatus.ACTIVE


def test_accept_version_sets_base_version_id(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    c1 = svc.create_candidate("MyStrategy", py_file, json_file)
    a1 = svc.accept_version(c1.version_id)

    c2 = svc.create_candidate("MyStrategy", py_file, json_file)
    a2 = svc.accept_version(c2.version_id)

    assert a2.base_version_id == a1.version_id


def test_accept_non_candidate_raises(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    candidate = svc.create_candidate("MyStrategy", py_file, json_file)
    svc.accept_version(candidate.version_id)  # now ACTIVE

    with pytest.raises(ValueError, match="expected 'candidate'"):
        svc.accept_version(candidate.version_id)


# ---------------------------------------------------------------------------
# reject_version
# ---------------------------------------------------------------------------

def test_reject_version_status_becomes_rejected(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    candidate = svc.create_candidate("MyStrategy", py_file, json_file)
    rejected = svc.reject_version(candidate.version_id)

    assert rejected.status == VersionStatus.REJECTED


def test_reject_non_candidate_raises(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    candidate = svc.create_candidate("MyStrategy", py_file, json_file)
    svc.accept_version(candidate.version_id)  # now ACTIVE

    with pytest.raises(ValueError, match="expected 'candidate'"):
        svc.reject_version(candidate.version_id)


# ---------------------------------------------------------------------------
# get_active_version
# ---------------------------------------------------------------------------

def test_get_active_version_returns_active(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    candidate = svc.create_candidate("MyStrategy", py_file, json_file)
    svc.accept_version(candidate.version_id)

    active = svc.get_active_version("MyStrategy")

    assert active is not None
    assert active.status == VersionStatus.ACTIVE
    assert active.version_id == candidate.version_id


def test_get_active_version_returns_none_when_no_active(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))

    result = svc.get_active_version("MyStrategy")

    assert result is None


def test_get_active_version_none_after_reject(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    candidate = svc.create_candidate("MyStrategy", py_file, json_file)
    svc.reject_version(candidate.version_id)

    assert svc.get_active_version("MyStrategy") is None


# ---------------------------------------------------------------------------
# get_version_for_run
# ---------------------------------------------------------------------------

def test_get_version_for_run_returns_version(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    candidate = svc.create_candidate("MyStrategy", py_file, json_file)

    result = svc.get_version_for_run({"version_id": candidate.version_id})

    assert result is not None
    assert result.version_id == candidate.version_id


def test_get_version_for_run_missing_key_returns_none(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))

    result = svc.get_version_for_run({})

    assert result is None


def test_get_version_for_run_unknown_id_returns_none(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))

    result = svc.get_version_for_run({"version_id": "nonexistent-uuid"})

    assert result is None


# ---------------------------------------------------------------------------
# build_diff_preview
# ---------------------------------------------------------------------------

def test_build_diff_preview_returns_dict_keys(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    candidate = svc.create_candidate("MyStrategy", py_file, json_file)
    result = svc.build_diff_preview(candidate.version_id)

    assert "strategy_diff" in result
    assert "params_diff" in result


def test_build_diff_preview_nonempty_when_files_differ(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))

    # Create candidate with original content
    py_file, json_file = create_strategy_files(tmp_path, py_content="class V1: pass\n")
    candidate = svc.create_candidate("MyStrategy", py_file, json_file)

    # Modify live file after snapshot
    py_file.write_text("class V2: pass\n", encoding="utf-8")

    result = svc.build_diff_preview(candidate.version_id)

    assert isinstance(result["strategy_diff"], str)
    assert len(result["strategy_diff"]) > 0


def test_build_diff_preview_empty_when_files_identical(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))
    py_file, json_file = create_strategy_files(tmp_path)

    candidate = svc.create_candidate("MyStrategy", py_file, json_file)
    # Don't modify live files — they match the snapshot
    result = svc.build_diff_preview(candidate.version_id)

    assert result["strategy_diff"] == ""
    assert result["params_diff"] == ""


def test_build_diff_preview_unknown_version_raises(tmp_path):
    svc = VersioningService(make_settings_service(tmp_path))

    with pytest.raises(ValueError):
        svc.build_diff_preview("nonexistent-uuid")
