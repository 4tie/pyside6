"""Property-based tests for the strategy versioning system.

Uses Hypothesis to verify correctness properties across arbitrary inputs.
"""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.versioning.version_models import (
    StrategyVersion,
    VersionSource,
    VersionStatus,
    version_from_dict,
    version_to_dict,
)
from app.core.versioning.versioning_service import VersioningService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings_service(tmp_path_str: str) -> MagicMock:
    svc = MagicMock()
    svc.settings.user_data_path = tmp_path_str
    return svc


def _create_strategy_files(base_dir: Path, strategy: str = "MyStrategy"):
    strategies_dir = base_dir / "strategies"
    strategies_dir.mkdir(parents=True, exist_ok=True)
    py_file = strategies_dir / f"{strategy}.py"
    json_file = strategies_dir / f"{strategy}.json"
    py_file.write_text("class MyStrategy: pass\n", encoding="utf-8")
    json_file.write_text('{"buy_params": {}}', encoding="utf-8")
    return py_file, json_file


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_strategy_name_st = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
)
_path_st = st.text(min_size=1, max_size=80)
_datetime_st = st.datetimes().map(lambda d: d.isoformat())
_optional_text_st = st.one_of(st.none(), st.text(max_size=100))


# ---------------------------------------------------------------------------
# Property 1: Serialization Round-Trip
# Feature: strategy-versioning, Property 1: serialization round-trip
# Validates: Requirements 1.3, 1.4, 1.5
# ---------------------------------------------------------------------------

@given(
    st.builds(
        StrategyVersion,
        version_id=st.uuids().map(str),
        strategy_name=_strategy_name_st,
        base_version_id=st.one_of(st.none(), st.uuids().map(str)),
        status=st.sampled_from(VersionStatus),
        source_type=st.sampled_from(VersionSource),
        strategy_file_path=_path_st,
        live_params_path=_path_st,
        snapshot_strategy_path=_path_st,
        snapshot_params_path=_path_st,
        created_at=_datetime_st,
        updated_at=_datetime_st,
        notes=_optional_text_st,
        last_run_id=_optional_text_st,
        diff_summary=_optional_text_st,
    )
)
@settings(max_examples=100)
def test_property_1_serialization_round_trip(version: StrategyVersion):
    # Feature: strategy-versioning, Property 1: serialization round-trip
    assert version_from_dict(version_to_dict(version)) == version


# ---------------------------------------------------------------------------
# Property 2: Index Consistency After Operations
# Feature: strategy-versioning, Property 2: index consistency after random operations
# Validates: Requirements 4.2, 4.6
# ---------------------------------------------------------------------------

@given(
    st.lists(
        st.sampled_from(["create", "accept", "reject"]),
        min_size=1,
        max_size=10,
    )
)
@settings(max_examples=100)
def test_property_2_index_consistency(operations):
    # Feature: strategy-versioning, Property 2: index consistency after random operations
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        svc = VersioningService(_make_settings_service(tmp_dir))
        py_file, json_file = _create_strategy_files(tmp_path)

        candidates = []

        for op in operations:
            if op == "create":
                try:
                    v = svc.create_candidate("MyStrategy", py_file, json_file)
                    candidates.append(v.version_id)
                except Exception:
                    pass
            elif op == "accept" and candidates:
                try:
                    vid = candidates[0]
                    svc.accept_version(vid)
                    candidates.remove(vid)
                except Exception:
                    pass
            elif op == "reject" and candidates:
                try:
                    vid = candidates[0]
                    svc.reject_version(vid)
                    candidates.remove(vid)
                except Exception:
                    pass

        versions = svc.list_versions("MyStrategy")
        valid_statuses = set(VersionStatus)

        # Every version has a valid status
        for v in versions:
            assert v.status in valid_statuses

        # No duplicate version_ids in the index
        ids = [v.version_id for v in versions]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Property 3: At Most One Active Version Per Strategy
# Feature: strategy-versioning, Property 3: at-most-one-active invariant
# Validates: Requirements 3.4
# ---------------------------------------------------------------------------

@given(st.integers(min_value=1, max_value=20))
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_property_3_at_most_one_active(n: int):
    # Feature: strategy-versioning, Property 3: at-most-one-active invariant
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        svc = VersioningService(_make_settings_service(tmp_dir))
        py_file, json_file = _create_strategy_files(tmp_path)

        for _ in range(n):
            candidate = svc.create_candidate("MyStrategy", py_file, json_file)
            svc.accept_version(candidate.version_id)

        versions = svc.list_versions("MyStrategy")
        active_count = sum(1 for v in versions if v.status == VersionStatus.ACTIVE)

        assert active_count <= 1


# ---------------------------------------------------------------------------
# Property 4: Unique Version IDs
# Feature: strategy-versioning, Property 4: unique version IDs
# Validates: Requirements 6.3, 6.4
# ---------------------------------------------------------------------------

@given(st.integers(min_value=2, max_value=50))
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_property_4_unique_version_ids(n: int):
    # Feature: strategy-versioning, Property 4: unique version IDs
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        svc = VersioningService(_make_settings_service(tmp_dir))
        py_file, json_file = _create_strategy_files(tmp_path)

        version_ids = []
        for _ in range(n):
            v = svc.create_candidate("MyStrategy", py_file, json_file)
            version_ids.append(v.version_id)

        assert len(version_ids) == len(set(version_ids))
