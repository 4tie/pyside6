"""Route tests for rollback endpoint and SSE process stream.

Tests:
- POST /api/runs/{strategy}/{run_id}/rollback → 200 with valid run
- POST /api/runs/{strategy}/{run_id}/rollback → 404 when run does not exist
- POST /api/runs/{strategy}/{run_id}/rollback → 500 on unexpected service error
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.models.settings_models import AppSettings
from app.core.services.rollback_service import RollbackResult, RollbackService
from app.web.dependencies import (
    get_rollback_service,
    get_settings_service,
)
from app.web.main import app


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeSettingsService:
    def load_settings(self) -> AppSettings:
        return AppSettings(
            venv_path="T:/venv",
            python_executable="T:/venv/Scripts/python.exe",
            freqtrade_executable="T:/venv/Scripts/freqtrade.exe",
            user_data_path="T:/user_data",
            use_module_execution=True,
        )


class _FakeRollbackServiceSuccess:
    def rollback(self, run_dir, user_data_path, strategy_name):
        return RollbackResult(
            success=True,
            rolled_back_to=run_dir.name,
            strategy_name=strategy_name,
            params_restored=True,
            config_restored=True,
        )


class _FakeRollbackServiceNotFound:
    def rollback(self, run_dir, user_data_path, strategy_name):
        raise FileNotFoundError(f"Run directory not found: {run_dir}")


class _FakeRollbackServiceError:
    def rollback(self, run_dir, user_data_path, strategy_name):
        raise RuntimeError("Unexpected disk error")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRollbackEndpoint:
    def _client(self, rollback_svc):
        app.dependency_overrides[get_settings_service] = lambda: _FakeSettingsService()
        app.dependency_overrides[get_rollback_service] = lambda: rollback_svc
        client = TestClient(app, raise_server_exceptions=False)
        return client

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_rollback_success_returns_200(self):
        client = self._client(_FakeRollbackServiceSuccess())
        resp = client.post("/api/runs/MyStrategy/run_2024-01-01_abc/rollback")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["strategy_name"] == "MyStrategy"
        assert "run_2024-01-01_abc" in data["rollback_to_run_id"]

    def test_rollback_not_found_returns_404(self):
        client = self._client(_FakeRollbackServiceNotFound())
        resp = client.post("/api/runs/MyStrategy/nonexistent_run/rollback")
        assert resp.status_code == 404

    def test_rollback_unexpected_error_returns_500(self):
        client = self._client(_FakeRollbackServiceError())
        resp = client.post("/api/runs/MyStrategy/run_2024-01-01_abc/rollback")
        assert resp.status_code == 500
