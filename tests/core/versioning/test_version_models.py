"""Unit tests for version_models.py — StrategyVersion, enums, serialization."""
import pytest

from app.core.versioning.version_models import (
    StrategyVersion,
    VersionSource,
    VersionStatus,
    version_from_dict,
    version_to_dict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_version(**kwargs) -> StrategyVersion:
    defaults = dict(
        version_id="test-uuid-1234",
        strategy_name="MyStrategy",
        base_version_id=None,
        status=VersionStatus.CANDIDATE,
        source_type=VersionSource.MANUAL_EDIT,
        strategy_file_path="/data/strategies/MyStrategy.py",
        live_params_path="/data/strategies/MyStrategy.json",
        snapshot_strategy_path="/data/versions/MyStrategy/test-uuid-1234/strategy.py",
        snapshot_params_path="/data/versions/MyStrategy/test-uuid-1234/strategy_params.json",
        created_at="2024-01-15T10:30:00.000000",
        updated_at="2024-01-15T10:30:00.000000",
    )
    defaults.update(kwargs)
    return StrategyVersion(**defaults)


def make_minimal_dict() -> dict:
    """Dict with only required fields — no optional ones."""
    return {
        "version_id": "min-uuid-5678",
        "strategy_name": "MinStrategy",
        "base_version_id": None,
        "status": "candidate",
        "source_type": "manual_edit",
        "strategy_file_path": "/data/strategies/MinStrategy.py",
        "live_params_path": "/data/strategies/MinStrategy.json",
        "snapshot_strategy_path": "/data/versions/MinStrategy/min-uuid-5678/strategy.py",
        "snapshot_params_path": "/data/versions/MinStrategy/min-uuid-5678/strategy_params.json",
        "created_at": "2024-01-15T10:00:00.000000",
        "updated_at": "2024-01-15T10:00:00.000000",
        # notes, last_run_id, diff_summary intentionally omitted
    }


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

def test_version_status_values():
    assert VersionStatus.ACTIVE == "active"
    assert VersionStatus.CANDIDATE == "candidate"
    assert VersionStatus.ACCEPTED == "accepted"
    assert VersionStatus.REJECTED == "rejected"


def test_version_source_values():
    assert VersionSource.MANUAL_EDIT == "manual_edit"
    assert VersionSource.OPTIMIZE == "optimize"


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------

def test_version_to_dict_keys():
    v = make_version()
    d = version_to_dict(v)
    for key in (
        "version_id", "strategy_name", "base_version_id", "status", "source_type",
        "strategy_file_path", "live_params_path", "snapshot_strategy_path",
        "snapshot_params_path", "created_at", "updated_at", "notes",
        "last_run_id", "diff_summary",
    ):
        assert key in d, f"Missing key: {key}"


def test_version_to_dict_status_is_string():
    v = make_version()
    d = version_to_dict(v)
    assert d["status"] == "candidate"
    assert isinstance(d["status"], str)


def test_version_to_dict_source_type_is_string():
    v = make_version()
    d = version_to_dict(v)
    assert d["source_type"] == "manual_edit"
    assert isinstance(d["source_type"], str)


def test_round_trip():
    v = make_version()
    assert version_from_dict(version_to_dict(v)) == v


def test_round_trip_with_optional_fields():
    v = make_version(notes="some notes", last_run_id="run_abc", diff_summary="+ line added")
    assert version_from_dict(version_to_dict(v)) == v


def test_round_trip_with_base_version_id():
    v = make_version(base_version_id="parent-uuid-0000")
    assert version_from_dict(version_to_dict(v)) == v


# ---------------------------------------------------------------------------
# Deserialization — missing optional fields
# ---------------------------------------------------------------------------

def test_from_dict_missing_optional_fields():
    d = make_minimal_dict()
    v = version_from_dict(d)
    assert v.notes is None
    assert v.last_run_id is None
    assert v.diff_summary is None


def test_from_dict_sets_required_fields():
    d = make_minimal_dict()
    v = version_from_dict(d)
    assert v.version_id == "min-uuid-5678"
    assert v.strategy_name == "MinStrategy"
    assert v.status == VersionStatus.CANDIDATE


# ---------------------------------------------------------------------------
# Deserialization — error cases
# ---------------------------------------------------------------------------

def test_from_dict_missing_required_field():
    d = version_to_dict(make_version())
    del d["version_id"]
    with pytest.raises(KeyError):
        version_from_dict(d)


def test_from_dict_missing_strategy_name():
    d = version_to_dict(make_version())
    del d["strategy_name"]
    with pytest.raises(KeyError):
        version_from_dict(d)


def test_from_dict_invalid_status():
    d = version_to_dict(make_version())
    d["status"] = "invalid_status"
    with pytest.raises(ValueError):
        version_from_dict(d)


def test_from_dict_invalid_source_type():
    d = version_to_dict(make_version())
    d["source_type"] = "not_a_source"
    with pytest.raises(ValueError):
        version_from_dict(d)


def test_from_dict_all_statuses():
    for status in VersionStatus:
        d = version_to_dict(make_version())
        d["status"] = status.value
        v = version_from_dict(d)
        assert v.status == status
