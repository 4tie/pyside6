"""Unit tests for GET /api/shared-inputs and PUT /api/shared-inputs endpoints."""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.services.settings_service import SettingsService
from leave.web.dependencies import get_settings_service
from leave.web.main import app


@contextmanager
def _client_with_settings(settings_service: SettingsService):
    """Build a TestClient with the given SettingsService injected."""
    app.dependency_overrides[get_settings_service] = lambda: settings_service
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_settings_service, None)


@pytest.fixture()
def settings_service(tmp_path):
    return SettingsService(str(tmp_path / "settings.json"))


def test_get_shared_inputs_endpoint(settings_service):
    with _client_with_settings(settings_service) as client:
        response = client.get("/api/shared-inputs")

    assert response.status_code == 200
    body = response.json()
    # Must have exactly the six shared fields
    expected_keys = {
        "default_timeframe",
        "default_timerange",
        "last_timerange_preset",
        "default_pairs",
        "dry_run_wallet",
        "max_open_trades",
    }
    assert set(body.keys()) == expected_keys
    # Check defaults
    assert body["default_timeframe"] == "5m"
    assert body["dry_run_wallet"] == 80.0
    assert body["max_open_trades"] == 2


def test_put_shared_inputs_endpoint(settings_service):
    with _client_with_settings(settings_service) as client:
        response = client.put(
            "/api/shared-inputs",
            json={"default_timeframe": "1h", "max_open_trades": 5},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["default_timeframe"] == "1h"
    assert body["max_open_trades"] == 5
    # Unset fields retain defaults
    assert body["dry_run_wallet"] == 80.0

    # Verify persistence
    reloaded = settings_service.load_settings()
    assert reloaded.shared_inputs.default_timeframe == "1h"
    assert reloaded.shared_inputs.max_open_trades == 5


def test_api_422_on_invalid_wallet(settings_service):
    with _client_with_settings(settings_service) as client:
        response = client.put("/api/shared-inputs", json={"dry_run_wallet": 0})

    assert response.status_code == 422


def test_api_422_on_invalid_trades(settings_service):
    with _client_with_settings(settings_service) as client:
        response = client.put("/api/shared-inputs", json={"max_open_trades": 0})

    assert response.status_code == 422


def test_disk_write_failure_returns_500(settings_service):
    with _client_with_settings(settings_service) as client:
        with patch(
            "app.core.services.shared_inputs_service.SharedInputsService.write_config",
            side_effect=RuntimeError("disk full"),
        ):
            response = client.put(
                "/api/shared-inputs",
                json={"default_timeframe": "15m"},
            )

    assert response.status_code == 500
    assert "disk full" in response.json()["detail"]
