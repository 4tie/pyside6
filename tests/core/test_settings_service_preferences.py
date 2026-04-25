import pytest

from app.core.models.settings_models import AppSettings
from app.core.services.settings_service import SettingsService


def test_update_preferences_persists_partial_section_update(tmp_path):
    settings_file = tmp_path / "settings.json"
    service = SettingsService(str(settings_file))
    service.save_settings(AppSettings())

    prefs = service.update_preferences(
        "backtest_preferences",
        default_timeframe="1h",
        default_pairs="BTC/USDT,ETH/USDT",
    )

    assert prefs.default_timeframe == "1h"
    assert prefs.default_pairs == "BTC/USDT,ETH/USDT"

    reloaded = SettingsService(str(settings_file)).load_settings()
    assert reloaded.backtest_preferences.default_timeframe == "1h"
    assert reloaded.backtest_preferences.default_pairs == "BTC/USDT,ETH/USDT"
    assert reloaded.backtest_preferences.max_open_trades == 2


def test_update_preferences_rejects_unknown_section(tmp_path):
    service = SettingsService(str(tmp_path / "settings.json"))

    with pytest.raises(ValueError, match="Unknown settings preference section"):
        service.update_preferences("missing_preferences", default_timeframe="1h")


def test_update_preferences_rejects_unknown_field(tmp_path):
    service = SettingsService(str(tmp_path / "settings.json"))

    with pytest.raises(ValueError, match="Unknown preference field"):
        service.update_preferences("download_preferences", not_a_field=True)
