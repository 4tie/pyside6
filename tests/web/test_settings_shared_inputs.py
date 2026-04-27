"""Unit test for GET /api/settings including shared_inputs in the response."""

from contextlib import contextmanager

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


def test_settings_response_includes_shared_inputs(tmp_path):
    """GET /api/settings response JSON contains a shared_inputs key with all six fields."""
    service = SettingsService(str(tmp_path / "settings.json"))

    with _client_with_settings(service) as client:
        response = client.get("/api/settings")

    assert response.status_code == 200
    body = response.json()

    assert "shared_inputs" in body

    shared = body["shared_inputs"]
    expected_keys = {
        "default_timeframe",
        "default_timerange",
        "last_timerange_preset",
        "default_pairs",
        "dry_run_wallet",
        "max_open_trades",
    }
    assert set(shared.keys()) == expected_keys

    # Verify default values
    assert shared["default_timeframe"] == "5m"
    assert shared["default_timerange"] == ""
    assert shared["last_timerange_preset"] == "30d"
    assert shared["default_pairs"] == ""
    assert shared["dry_run_wallet"] == 80.0
    assert shared["max_open_trades"] == 2
