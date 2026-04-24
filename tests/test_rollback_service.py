"""Tests for RollbackService — unit tests and property-based tests.

Covers:
- Happy path: both files present → both restored
- Missing params.json → params_restored=False, config still restored
- Missing config.snapshot.json → config_restored=False, params still restored
- Neither file present → ValueError
- Non-existent run_dir → FileNotFoundError
- Property 5: Rollback file fidelity
"""
import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.core.services.rollback_service import RollbackService, RollbackResult
from app.core.parsing.json_parser import parse_json_file, write_json_file_atomic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run_dir(tmp_path: Path, with_params: bool = True, with_config: bool = True) -> Path:
    """Create a minimal run directory with optional source files."""
    run_dir = tmp_path / "run_2024-01-01_abc123"
    run_dir.mkdir()
    if with_params:
        write_json_file_atomic(run_dir / "params.json", {"buy_rsi": 30, "sell_rsi": 70})
    if with_config:
        write_json_file_atomic(run_dir / "config.snapshot.json", {"stake_currency": "USDT"})
    return run_dir


def _make_user_data(tmp_path: Path) -> Path:
    """Create a minimal user_data directory."""
    user_data = tmp_path / "user_data"
    (user_data / "strategies").mkdir(parents=True)
    return user_data


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestRollbackServiceHappyPath:
    def test_both_files_restored(self, tmp_path):
        run_dir = _make_run_dir(tmp_path, with_params=True, with_config=True)
        user_data = _make_user_data(tmp_path)
        svc = RollbackService()

        result = svc.rollback(run_dir, user_data, "MyStrategy")

        assert result.success is True
        assert result.params_restored is True
        assert result.config_restored is True
        assert result.strategy_name == "MyStrategy"
        assert result.rolled_back_to == run_dir.name
        assert result.error is None

        # Verify files were actually written
        assert (user_data / "strategies" / "MyStrategy.json").exists()
        assert (user_data / "config.json").exists()


class TestRollbackServicePartialFiles:
    def test_missing_params_config_still_restored(self, tmp_path):
        run_dir = _make_run_dir(tmp_path, with_params=False, with_config=True)
        user_data = _make_user_data(tmp_path)
        svc = RollbackService()

        result = svc.rollback(run_dir, user_data, "MyStrategy")

        assert result.success is True
        assert result.params_restored is False
        assert result.config_restored is True
        assert not (user_data / "strategies" / "MyStrategy.json").exists()
        assert (user_data / "config.json").exists()

    def test_missing_config_params_still_restored(self, tmp_path):
        run_dir = _make_run_dir(tmp_path, with_params=True, with_config=False)
        user_data = _make_user_data(tmp_path)
        svc = RollbackService()

        result = svc.rollback(run_dir, user_data, "MyStrategy")

        assert result.success is True
        assert result.params_restored is True
        assert result.config_restored is False
        assert (user_data / "strategies" / "MyStrategy.json").exists()
        assert not (user_data / "config.json").exists()


class TestRollbackServiceErrors:
    def test_neither_file_raises_value_error(self, tmp_path):
        run_dir = _make_run_dir(tmp_path, with_params=False, with_config=False)
        user_data = _make_user_data(tmp_path)
        svc = RollbackService()

        with pytest.raises(ValueError, match="No restorable files"):
            svc.rollback(run_dir, user_data, "MyStrategy")

    def test_nonexistent_run_dir_raises_file_not_found(self, tmp_path):
        run_dir = tmp_path / "nonexistent_run"
        user_data = _make_user_data(tmp_path)
        svc = RollbackService()

        with pytest.raises(FileNotFoundError):
            svc.rollback(run_dir, user_data, "MyStrategy")


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Feature: web-layer-architecture, Property 5: Rollback file fidelity
@given(
    params=st.dictionaries(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"))),
        st.integers(),
        max_size=10,
    ),
    config=st.dictionaries(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"))),
        st.text(max_size=50),
        max_size=10,
    ),
)
@h_settings(max_examples=100)
def test_rollback_file_fidelity(params, config):
    """Property 5: After rollback, restored files are byte-for-byte equal to source files."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir = tmp_path / "run_2024-01-01_abc123"
        run_dir.mkdir()
        write_json_file_atomic(run_dir / "params.json", params)
        write_json_file_atomic(run_dir / "config.snapshot.json", config)

        user_data = tmp_path / "user_data"
        (user_data / "strategies").mkdir(parents=True)

        svc = RollbackService()
        result = svc.rollback(run_dir, user_data, "MyStrategy")

        assert result.success is True

        restored_params = parse_json_file(user_data / "strategies" / "MyStrategy.json")
        restored_config = parse_json_file(user_data / "config.json")

        assert restored_params == params
        assert restored_config == config
