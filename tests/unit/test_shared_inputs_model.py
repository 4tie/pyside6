"""Unit tests for SharedInputsPreferences model and AppSettings migration.

Covers:
  - test_shared_inputs_defaults         (Req 1.1)
  - test_shared_inputs_fields_only      (Req 1.2)
  - test_legacy_fields_retained         (Req 1.4)
"""

from app.core.models.settings_models import (
    AppSettings,
    BacktestPreferences,
    DownloadPreferences,
    SharedInputsPreferences,
)
from app.core.models.optimizer_models import OptimizerPreferences


# ---------------------------------------------------------------------------
# test_shared_inputs_defaults — Req 1.1
# ---------------------------------------------------------------------------

def test_shared_inputs_defaults():
    """AppSettings() has correct default values for all six shared fields."""
    settings = AppSettings()
    si = settings.shared_inputs
    assert si.default_timeframe == "5m"
    assert si.default_timerange == ""
    assert si.last_timerange_preset == "30d"
    assert si.default_pairs == ""
    assert si.dry_run_wallet == 80.0
    assert si.max_open_trades == 2


# ---------------------------------------------------------------------------
# test_shared_inputs_fields_only — Req 1.2
# ---------------------------------------------------------------------------

def test_shared_inputs_fields_only():
    """SharedInputsPreferences has exactly six fields and no others."""
    fields = set(SharedInputsPreferences.model_fields.keys())
    expected = {
        "default_timeframe",
        "default_timerange",
        "last_timerange_preset",
        "default_pairs",
        "dry_run_wallet",
        "max_open_trades",
    }
    assert fields == expected


# ---------------------------------------------------------------------------
# test_legacy_fields_retained — Req 1.4
# ---------------------------------------------------------------------------

def test_legacy_fields_retained():
    """BacktestPreferences, DownloadPreferences, and OptimizerPreferences still carry the shared fields."""
    shared_fields = {
        "default_timeframe",
        "default_timerange",
        "last_timerange_preset",
        "default_pairs",
        "dry_run_wallet",
        "max_open_trades",
    }
    backtest_fields = set(BacktestPreferences.model_fields.keys())
    download_fields = set(DownloadPreferences.model_fields.keys())
    optimizer_fields = set(OptimizerPreferences.model_fields.keys())

    # DownloadPreferences doesn't have dry_run_wallet / max_open_trades
    download_shared = {"default_timeframe", "default_timerange", "last_timerange_preset", "default_pairs"}
    assert download_shared.issubset(download_fields)
    assert shared_fields.issubset(backtest_fields)
    assert shared_fields.issubset(optimizer_fields)


# ---------------------------------------------------------------------------
# Migration tests — Req 1.3
# ---------------------------------------------------------------------------

def test_migration_uses_optimizer_over_backtest():
    """optimizer_preferences values win over backtest_preferences during migration."""
    data = {
        "backtest_preferences": {"default_timeframe": "15m"},
        "optimizer_preferences": {"default_timeframe": "1h"},
    }
    settings = AppSettings(**data)
    assert settings.shared_inputs.default_timeframe == "1h"


def test_migration_uses_backtest_over_download():
    """backtest_preferences values win over download_preferences during migration."""
    data = {
        "download_preferences": {"default_timeframe": "1m"},
        "backtest_preferences": {"default_timeframe": "4h"},
    }
    settings = AppSettings(**data)
    assert settings.shared_inputs.default_timeframe == "4h"


def test_migration_skipped_when_shared_inputs_present():
    """When shared_inputs key is present, migration does not overwrite it."""
    data = {
        "shared_inputs": {"default_timeframe": "1d"},
        "backtest_preferences": {"default_timeframe": "5m"},
        "optimizer_preferences": {"default_timeframe": "15m"},
    }
    settings = AppSettings(**data)
    assert settings.shared_inputs.default_timeframe == "1d"


def test_migration_partial_sources():
    """Migration works when only some source sections have shared fields."""
    data = {
        "download_preferences": {"default_pairs": "BTC/USDT"},
        "optimizer_preferences": {"default_timeframe": "1h"},
    }
    settings = AppSettings(**data)
    assert settings.shared_inputs.default_timeframe == "1h"
    assert settings.shared_inputs.default_pairs == "BTC/USDT"
