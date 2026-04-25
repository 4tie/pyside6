import asyncio

import pytest
from fastapi import HTTPException

from app.core.services.settings_service import SettingsService
from app.web.api.routes.settings import update_settings
from app.web.models import SettingsUpdate


def test_settings_api_accepts_partial_preference_updates(tmp_path):
    service = SettingsService(str(tmp_path / "settings.json"))

    response = asyncio.run(
        update_settings(
            SettingsUpdate(
                backtest_preferences={
                    "default_timeframe": "1h",
                    "default_pairs": "BTC/USDT",
                },
                optimizer_preferences={
                    "default_timeframe": "15m",
                    "default_pairs": "ETH/USDT",
                    "total_trials": 12,
                },
            ),
            service,
        )
    )

    body = response.model_dump()
    assert body["backtest_preferences"]["default_timeframe"] == "1h"
    assert body["backtest_preferences"]["default_pairs"] == "BTC/USDT"
    assert body["backtest_preferences"]["max_open_trades"] == 2
    assert body["optimizer_preferences"]["default_timeframe"] == "15m"
    assert body["optimizer_preferences"]["default_pairs"] == "ETH/USDT"
    assert body["optimizer_preferences"]["total_trials"] == 12

    reloaded = service.load_settings()
    assert reloaded.backtest_preferences.default_timeframe == "1h"
    assert reloaded.optimizer_preferences.total_trials == 12


def test_settings_api_rejects_unknown_preference_fields(tmp_path):
    service = SettingsService(str(tmp_path / "settings.json"))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            update_settings(
                SettingsUpdate(backtest_preferences={"missing_field": "value"}),
                service,
            )
        )

    assert exc_info.value.status_code == 422
