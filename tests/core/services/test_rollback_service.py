"""Unit tests for the new RollbackService implementation.

Covers backup, prune, atomic-restore, and rollback scope logic.
"""
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.parsing.json_parser import ParseError, write_json_file_atomic
from app.core.services.rollback_service import RollbackResult, RollbackService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_dir(
    tmp_path: Path,
    with_params: bool = True,
    with_config: bool = True,
) -> Path:
    """Create a minimal run directory with optional source files."""
    run_dir = tmp_path / "run_20240101_abc123"
    run_dir.mkdir()
    if with_params:
        write_json_file_atomic(run_dir / "params.json", {"buy_rsi": 30, "sell_rsi": 70})
    if with_config:
        write_json_file_atomic(
            run_dir / "config.snapshot.json", {"stake_currency": "USDT"}
        )
    return run_dir


def _make_user_data(tmp_path: Path) -> Path:
    """Create a minimal user_data directory."""
    user_data = tmp_path / "user_data"
    (user_data / "strategies").mkdir(parents=True)
    return user_data


# ---------------------------------------------------------------------------
# rollback() — happy paths
# ---------------------------------------------------------------------------


class TestRollbackBothFiles:
    def test_both_files_present_both_flags_true(self, tmp_path):
        """rollback() with both files present and both flags True restores both."""
        run_dir = _make_run_dir(tmp_path, with_params=True, with_config=True)
        user_data = _make_user_data(tmp_path)
        svc = RollbackService()

        result = svc.rollback(
            run_dir, user_data, "MyStrategy",
            restore_params=True, restore_config=True,
        )

        assert isinstance(result, RollbackResult)
        assert result.params_restored is True
        assert result.config_restored is True
        assert result.strategy_name == "MyStrategy"
        assert result.rolled_back_to == run_dir.name
        assert result.params_path == user_data / "strategies" / "MyStrategy.json"
        assert result.config_path == user_data / "config.json"
        assert (user_data / "strategies" / "MyStrategy.json").exists()
        assert (user_data / "config.json").exists()


class TestRollbackParamsOnly:
    def test_only_params_present_restore_params_true(self, tmp_path):
        """rollback() with only params.json present and restore_params=True."""
        run_dir = _make_run_dir(tmp_path, with_params=True, with_config=False)
        user_data = _make_user_data(tmp_path)
        svc = RollbackService()

        result = svc.rollback(
            run_dir, user_data, "MyStrategy",
            restore_params=True, restore_config=False,
        )

        assert result.params_restored is True
        assert result.config_restored is False
        assert result.params_path == user_data / "strategies" / "MyStrategy.json"
        assert result.config_path is None
        assert (user_data / "strategies" / "MyStrategy.json").exists()
        assert not (user_data / "config.json").exists()


class TestRollbackConfigOnly:
    def test_only_config_present_restore_config_true(self, tmp_path):
        """rollback() with only config.snapshot.json present and restore_config=True."""
        run_dir = _make_run_dir(tmp_path, with_params=False, with_config=True)
        user_data = _make_user_data(tmp_path)
        svc = RollbackService()

        result = svc.rollback(
            run_dir, user_data, "MyStrategy",
            restore_params=False, restore_config=True,
        )

        assert result.params_restored is False
        assert result.config_restored is True
        assert result.params_path is None
        assert result.config_path == user_data / "config.json"
        assert not (user_data / "strategies" / "MyStrategy.json").exists()
        assert (user_data / "config.json").exists()


# ---------------------------------------------------------------------------
# rollback() — error cases
# ---------------------------------------------------------------------------


class TestRollbackErrors:
    def test_raises_file_not_found_for_missing_run_dir(self, tmp_path):
        """rollback() raises FileNotFoundError when run_dir does not exist."""
        run_dir = tmp_path / "nonexistent_run"
        user_data = _make_user_data(tmp_path)
        svc = RollbackService()

        with pytest.raises(FileNotFoundError, match="Run directory not found"):
            svc.rollback(run_dir, user_data, "MyStrategy")

    def test_raises_value_error_when_neither_source_file_present(self, tmp_path):
        """rollback() raises ValueError when neither params.json nor config.snapshot.json exists."""
        run_dir = _make_run_dir(tmp_path, with_params=False, with_config=False)
        user_data = _make_user_data(tmp_path)
        svc = RollbackService()

        with pytest.raises(ValueError, match="No restorable files found in run directory"):
            svc.rollback(run_dir, user_data, "MyStrategy")


# ---------------------------------------------------------------------------
# _backup_file()
# ---------------------------------------------------------------------------


class TestBackupFile:
    def test_backup_creates_file_with_correct_name_format(self, tmp_path):
        """_backup_file() creates a backup with .bak_YYYYMMDDTHHMMSS suffix."""
        active = tmp_path / "MyStrategy.json"
        write_json_file_atomic(active, {"key": "value"})
        svc = RollbackService()

        backup_path = svc._backup_file(active)

        assert backup_path.exists()
        # Verify the name matches the expected pattern
        pattern = re.compile(r"MyStrategy\.json\.bak_\d{8}T\d{6}$")
        assert pattern.match(backup_path.name), (
            f"Backup name '{backup_path.name}' does not match expected pattern"
        )

    def test_backup_skips_silently_when_active_file_missing(self, tmp_path):
        """_backup_file() returns a path without error when active file doesn't exist."""
        active = tmp_path / "nonexistent.json"
        svc = RollbackService()

        # Should not raise
        result = svc._backup_file(active)
        assert result is not None


# ---------------------------------------------------------------------------
# _prune_backups()
# ---------------------------------------------------------------------------


class TestPruneBackups:
    def test_exactly_5_backups_no_deletion(self, tmp_path):
        """_prune_backups() with exactly 5 existing backups — no deletion occurs."""
        active = tmp_path / "MyStrategy.json"
        write_json_file_atomic(active, {"key": "value"})

        # Create exactly 5 backup files
        for i in range(5):
            bak = tmp_path / f"MyStrategy.json.bak_2024010{i + 1}T120000"
            write_json_file_atomic(bak, {"key": f"v{i}"})

        svc = RollbackService()
        svc._prune_backups(active)

        remaining = list(tmp_path.glob("MyStrategy.json.bak_*"))
        assert len(remaining) == 5

    def test_zero_backups_no_deletion_no_warning(self, tmp_path, caplog):
        """_prune_backups() with 0 existing backups — no deletion, no warning logged."""
        import logging

        active = tmp_path / "MyStrategy.json"
        write_json_file_atomic(active, {"key": "value"})

        svc = RollbackService()
        with caplog.at_level(logging.WARNING):
            svc._prune_backups(active)

        remaining = list(tmp_path.glob("MyStrategy.json.bak_*"))
        assert len(remaining) == 0
        # No warning should have been logged
        assert not any("warning" in r.levelname.lower() for r in caplog.records)

    def test_6_backups_oldest_deleted(self, tmp_path):
        """_prune_backups() with 6 backups deletes the oldest one."""
        active = tmp_path / "MyStrategy.json"
        write_json_file_atomic(active, {"key": "value"})

        # Create 6 backup files with ascending timestamps (oldest = 01, newest = 06)
        for i in range(6):
            bak = tmp_path / f"MyStrategy.json.bak_2024010{i + 1}T120000"
            write_json_file_atomic(bak, {"key": f"v{i}"})

        svc = RollbackService()
        svc._prune_backups(active)

        remaining = sorted(tmp_path.glob("MyStrategy.json.bak_*"))
        assert len(remaining) == 5
        # The oldest (01) should be gone; 02–06 should remain
        names = [p.name for p in remaining]
        assert "MyStrategy.json.bak_20240101T120000" not in names


# ---------------------------------------------------------------------------
# Backup failure aborts rollback
# ---------------------------------------------------------------------------


class TestBackupFailureAbortsRollback:
    def test_backup_write_failure_aborts_without_touching_active(self, tmp_path):
        """If backup write fails, rollback raises ValueError and active file is untouched."""
        run_dir = _make_run_dir(tmp_path, with_params=True, with_config=False)
        user_data = _make_user_data(tmp_path)

        # Pre-create the active params file with known content
        active_params = user_data / "strategies" / "MyStrategy.json"
        write_json_file_atomic(active_params, {"original": True})
        original_content = active_params.read_text(encoding="utf-8")

        svc = RollbackService()

        # Patch _backup_file to simulate a write failure
        with patch.object(svc, "_backup_file", side_effect=ValueError("disk full")):
            with pytest.raises(ValueError, match="disk full"):
                svc.rollback(
                    run_dir, user_data, "MyStrategy",
                    restore_params=True, restore_config=False,
                )

        # Active file must be unchanged
        assert active_params.read_text(encoding="utf-8") == original_content
