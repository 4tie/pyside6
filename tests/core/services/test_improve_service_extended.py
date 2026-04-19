"""
test_improve_service_extended.py — Unit tests for ImproveService extensions:
- _build_freqtrade_params_file() trailing params round-trip
- cleanup_stale_sandboxes() skips young directories and deletes old ones
"""
import json
import time
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.services.improve_service import ImproveService


def _make_service(user_data_path: str) -> ImproveService:
    """Create an ImproveService with a mocked settings_service."""
    settings_mock = MagicMock()
    settings_mock.load_settings.return_value = MagicMock(
        user_data_path=user_data_path,
    )
    return ImproveService(settings_mock, MagicMock())


# ---------------------------------------------------------------------------
# _build_freqtrade_params_file — trailing params round-trip
# ---------------------------------------------------------------------------

class TestBuildFreqtradeParamsFileTrailing:
    def test_trailing_stop_written_to_nested_block(self, tmp_path):
        """trailing_stop=True must appear in ft_params['trailing']['trailing_stop']."""
        service = _make_service(str(tmp_path))
        flat_params = {
            "stoploss": -0.10,
            "trailing_stop": True,
            "trailing_stop_positive": 0.02,
            "trailing_stop_positive_offset": 0.04,
            "trailing_only_offset_is_reached": True,
        }
        result = service._build_freqtrade_params_file("TestStrategy", flat_params)
        trailing = result["params"]["trailing"]
        assert trailing["trailing_stop"] is True
        assert trailing["trailing_stop_positive"] == 0.02
        assert trailing["trailing_stop_positive_offset"] == 0.04
        assert trailing["trailing_only_offset_is_reached"] is True

    def test_trailing_stop_false_written(self, tmp_path):
        service = _make_service(str(tmp_path))
        flat_params = {"trailing_stop": False}
        result = service._build_freqtrade_params_file("TestStrategy", flat_params)
        assert result["params"]["trailing"]["trailing_stop"] is False

    def test_trailing_params_absent_when_not_in_flat(self, tmp_path):
        """When trailing_stop is not in flat_params, no trailing block is added."""
        service = _make_service(str(tmp_path))
        flat_params = {"stoploss": -0.10}
        result = service._build_freqtrade_params_file("TestStrategy", flat_params)
        # trailing block should not be present (or should be empty from base)
        trailing = result["params"].get("trailing", {})
        assert "trailing_stop" not in trailing

    def test_buy_sell_params_written_under_correct_keys(self, tmp_path):
        service = _make_service(str(tmp_path))
        flat_params = {
            "buy_params": {"rsi_buy": 30},
            "sell_params": {"rsi_sell": 70},
        }
        result = service._build_freqtrade_params_file("TestStrategy", flat_params)
        assert result["params"]["buy"] == {"rsi_buy": 30}
        assert result["params"]["sell"] == {"rsi_sell": 70}

    def test_round_trip_json_serialisable(self, tmp_path):
        """The output of _build_freqtrade_params_file must be JSON-serialisable."""
        service = _make_service(str(tmp_path))
        flat_params = {
            "stoploss": -0.08,
            "max_open_trades": 3,
            "minimal_roi": {"0": 0.10, "30": 0.05},
            "buy_params": {"rsi_buy": 30},
            "sell_params": {"rsi_sell": 70},
            "trailing_stop": True,
            "trailing_stop_positive": 0.02,
            "trailing_stop_positive_offset": 0.04,
            "trailing_only_offset_is_reached": False,
        }
        result = service._build_freqtrade_params_file("TestStrategy", flat_params)
        # Must not raise
        serialised = json.dumps(result)
        restored = json.loads(serialised)
        assert restored["params"]["trailing"]["trailing_stop"] is True
        assert restored["params"]["buy"]["rsi_buy"] == 30


# ---------------------------------------------------------------------------
# cleanup_stale_sandboxes
# ---------------------------------------------------------------------------

class TestCleanupStaleSandboxes:
    def test_skips_young_directories(self, tmp_path):
        """Directories less than 5 minutes old must NOT be deleted."""
        sandbox_root = tmp_path / "strategies" / "_improve_sandbox"
        sandbox_root.mkdir(parents=True)
        young_dir = sandbox_root / "MyStrategy_young"
        young_dir.mkdir()
        # mtime is current — well within 5 minutes

        service = _make_service(str(tmp_path))
        service.cleanup_stale_sandboxes()

        assert young_dir.exists(), "Young sandbox should not be deleted"

    def test_deletes_old_directories(self, tmp_path):
        """Directories older than 24 hours must be deleted."""
        sandbox_root = tmp_path / "strategies" / "_improve_sandbox"
        sandbox_root.mkdir(parents=True)
        old_dir = sandbox_root / "MyStrategy_old"
        old_dir.mkdir()

        # Set mtime to 25 hours ago
        old_time = time.time() - (25 * 3600)
        import os
        os.utime(old_dir, (old_time, old_time))

        service = _make_service(str(tmp_path))
        service.cleanup_stale_sandboxes()

        assert not old_dir.exists(), "Old sandbox should be deleted"

    def test_does_not_delete_between_5min_and_24h(self, tmp_path):
        """Directories between 5 minutes and 24 hours old must NOT be deleted."""
        sandbox_root = tmp_path / "strategies" / "_improve_sandbox"
        sandbox_root.mkdir(parents=True)
        mid_dir = sandbox_root / "MyStrategy_mid"
        mid_dir.mkdir()

        # Set mtime to 12 hours ago
        mid_time = time.time() - (12 * 3600)
        import os
        os.utime(mid_dir, (mid_time, mid_time))

        service = _make_service(str(tmp_path))
        service.cleanup_stale_sandboxes()

        assert mid_dir.exists(), "Mid-age sandbox should not be deleted"

    def test_continues_on_oserror(self, tmp_path):
        """OSError during deletion must not propagate — function must complete silently."""
        sandbox_root = tmp_path / "strategies" / "_improve_sandbox"
        sandbox_root.mkdir(parents=True)
        old_dir = sandbox_root / "MyStrategy_old"
        old_dir.mkdir()

        old_time = time.time() - (25 * 3600)
        import os
        os.utime(old_dir, (old_time, old_time))

        service = _make_service(str(tmp_path))

        import unittest.mock as mock
        def _raise_oserror(path, **kwargs):
            raise OSError("Permission denied")

        # Must not raise even when rmtree fails
        with mock.patch("app.core.services.improve_service.shutil.rmtree", side_effect=_raise_oserror):
            service.cleanup_stale_sandboxes()  # should complete without raising

    def test_no_sandbox_root_is_noop(self, tmp_path):
        """If sandbox root does not exist, cleanup must be a no-op."""
        service = _make_service(str(tmp_path))
        # sandbox root does not exist — should not raise
        service.cleanup_stale_sandboxes()
