"""Unit tests for InputHolderRouter (GET/PUT /api/optimizer/config).

Uses FastAPI TestClient with dependency overrides to isolate the router
from the real SettingsService and file system.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.models.optimizer_models import OptimizerConfigResponse, OptimizerPreferences
from app.core.services.input_holder_service import InputHolderService
from app.web.dependencies import get_settings_service
from app.web.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_response() -> OptimizerConfigResponse:
    prefs = OptimizerPreferences()
    return OptimizerConfigResponse(
        last_strategy=prefs.last_strategy,
        default_timeframe=prefs.default_timeframe,
        last_timerange_preset=prefs.last_timerange_preset,
        default_timerange=prefs.default_timerange,
        default_pairs=prefs.default_pairs,
        pairs_list=[],
        dry_run_wallet=prefs.dry_run_wallet,
        max_open_trades=prefs.max_open_trades,
    )


def _make_mock_settings(prefs: OptimizerPreferences | None = None) -> MagicMock:
    if prefs is None:
        prefs = OptimizerPreferences()
    mock = MagicMock()
    app_settings = MagicMock()
    app_settings.optimizer_preferences = prefs
    mock.load_settings.return_value = app_settings
    mock.update_preferences.return_value = prefs
    return mock


def _client_with_mock(mock_settings) -> TestClient:
    app.dependency_overrides[get_settings_service] = lambda: mock_settings
    client = TestClient(app, raise_server_exceptions=False)
    return client


# ---------------------------------------------------------------------------
# GET /api/optimizer/config
# ---------------------------------------------------------------------------

def test_get_returns_200_with_defaults():
    mock = _make_mock_settings()
    client = _client_with_mock(mock)
    try:
        resp = client.get("/api/optimizer/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "dry_run_wallet" in data
        assert "max_open_trades" in data
        assert "pairs_list" in data
        assert isinstance(data["pairs_list"], list)
    finally:
        app.dependency_overrides.clear()


def test_get_runtime_error_returns_500():
    mock = _make_mock_settings()
    mock.load_settings.side_effect = RuntimeError("disk error")
    client = _client_with_mock(mock)
    try:
        resp = client.get("/api/optimizer/config")
        assert resp.status_code == 500
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# PUT /api/optimizer/config
# ---------------------------------------------------------------------------

def test_put_valid_payload_returns_200():
    prefs = OptimizerPreferences(last_strategy="MyStrat", dry_run_wallet=100.0)
    mock = _make_mock_settings(prefs)
    client = _client_with_mock(mock)
    try:
        resp = client.put("/api/optimizer/config", json={"last_strategy": "MyStrat"})
        assert resp.status_code == 200
        data = resp.json()
        assert "last_strategy" in data
    finally:
        app.dependency_overrides.clear()


def test_put_unknown_field_returns_422():
    mock = _make_mock_settings()
    client = _client_with_mock(mock)
    try:
        resp = client.put("/api/optimizer/config", json={"unknown_field_xyz": "value"})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_put_invalid_wallet_returns_422():
    mock = _make_mock_settings()
    client = _client_with_mock(mock)
    try:
        resp = client.put("/api/optimizer/config", json={"dry_run_wallet": 0.0})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_put_invalid_trades_returns_422():
    mock = _make_mock_settings()
    client = _client_with_mock(mock)
    try:
        resp = client.put("/api/optimizer/config", json={"max_open_trades": 0})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_disk_write_failure_returns_500():
    mock = _make_mock_settings()
    mock.update_preferences.side_effect = RuntimeError("disk full")
    client = _client_with_mock(mock)
    try:
        resp = client.put("/api/optimizer/config", json={"last_strategy": "AnyStrat"})
        assert resp.status_code == 500
    finally:
        app.dependency_overrides.clear()


def test_last_strategy_empty_string_not_null():
    prefs = OptimizerPreferences(last_strategy="")
    mock = _make_mock_settings(prefs)
    client = _client_with_mock(mock)
    try:
        resp = client.get("/api/optimizer/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["last_strategy"] == ""
        assert data["last_strategy"] is not None
    finally:
        app.dependency_overrides.clear()
