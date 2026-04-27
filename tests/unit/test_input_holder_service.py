"""Unit tests for InputHolderService.

Tests cover:
- read_config returns defaults when no settings file exists
- resolve_preset for all 7 known keys
- resolve_preset returns None for unknown key
- deduplicate_pairs with empty string
- deduplicate_pairs preserves insertion order
- write_config raises ValueError for dry_run_wallet <= 0
- write_config raises ValueError for max_open_trades < 1
- disk write failure propagates RuntimeError
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.core.models.optimizer_models import (
    OptimizerConfigUpdate,
    OptimizerPreferences,
)
from app.core.services.input_holder_service import (
    KNOWN_PRESETS,
    InputHolderService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(prefs: OptimizerPreferences | None = None) -> InputHolderService:
    """Return an InputHolderService backed by a mock SettingsService."""
    mock_settings = MagicMock()
    if prefs is None:
        prefs = OptimizerPreferences()
    app_settings = MagicMock()
    app_settings.optimizer_preferences = prefs
    mock_settings.load_settings.return_value = app_settings
    mock_settings.update_preferences.return_value = prefs
    return InputHolderService(mock_settings)


# ---------------------------------------------------------------------------
# read_config
# ---------------------------------------------------------------------------

def test_read_config_returns_defaults():
    svc = _make_service()
    resp = svc.read_config()
    assert resp.dry_run_wallet == 80.0
    assert resp.max_open_trades == 2
    assert resp.default_timeframe == "5m"
    assert resp.last_strategy == ""
    assert resp.pairs_list == []


# ---------------------------------------------------------------------------
# resolve_preset
# ---------------------------------------------------------------------------

def test_resolve_preset_all_known_keys():
    ref = date(2025, 1, 1)
    for key in KNOWN_PRESETS:
        result = InputHolderService.resolve_preset(key, today=ref)
        assert result is not None, f"Expected result for key {key!r}"
        parts = result.split("-")
        assert len(parts) == 2, f"Expected YYYYMMDD-YYYYMMDD, got {result!r}"
        start_str, end_str = parts
        assert len(start_str) == 8
        assert len(end_str) == 8
        assert end_str == ref.strftime("%Y%m%d")


def test_resolve_preset_unknown_key_returns_none():
    assert InputHolderService.resolve_preset("unknown_key") is None
    assert InputHolderService.resolve_preset("") is None
    assert InputHolderService.resolve_preset("999d") is None


# ---------------------------------------------------------------------------
# deduplicate_pairs
# ---------------------------------------------------------------------------

def test_deduplicate_pairs_empty_string():
    assert InputHolderService.deduplicate_pairs("") == ""


def test_deduplicate_pairs_preserves_order():
    result = InputHolderService.deduplicate_pairs("BTC/USDT,ETH/USDT,BTC/USDT,ADA/USDT,ETH/USDT")
    assert result == "BTC/USDT,ETH/USDT,ADA/USDT"


def test_deduplicate_pairs_no_duplicates_unchanged():
    result = InputHolderService.deduplicate_pairs("BTC/USDT,ETH/USDT")
    assert result == "BTC/USDT,ETH/USDT"


# ---------------------------------------------------------------------------
# write_config validation
# ---------------------------------------------------------------------------

def test_write_config_invalid_wallet_raises():
    svc = _make_service()
    with pytest.raises(ValueError, match="dry_run_wallet"):
        svc.write_config(OptimizerConfigUpdate(dry_run_wallet=0.0))

    with pytest.raises(ValueError, match="dry_run_wallet"):
        svc.write_config(OptimizerConfigUpdate(dry_run_wallet=-10.0))


def test_write_config_invalid_trades_raises():
    svc = _make_service()
    with pytest.raises(ValueError, match="max_open_trades"):
        svc.write_config(OptimizerConfigUpdate(max_open_trades=0))

    with pytest.raises(ValueError, match="max_open_trades"):
        svc.write_config(OptimizerConfigUpdate(max_open_trades=-1))


def test_disk_write_failure_propagates_runtime_error():
    mock_settings = MagicMock()
    prefs = OptimizerPreferences()
    app_settings = MagicMock()
    app_settings.optimizer_preferences = prefs
    mock_settings.load_settings.return_value = app_settings
    mock_settings.update_preferences.side_effect = RuntimeError("disk full")

    svc = InputHolderService(mock_settings)
    with pytest.raises(RuntimeError, match="disk full"):
        svc.write_config(OptimizerConfigUpdate(last_strategy="MyStrategy"))
