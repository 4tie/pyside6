from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.core.freqtrade.runners.backtest_runner import BacktestRunCommand
from app.core.freqtrade.runners.base_runner import RunCommand
from app.core.models.settings_models import AppSettings
from app.web.api.routes import backtest as backtest_routes
from app.web.dependencies import (
    get_backtest_service,
    get_process_service,
    get_settings_service,
)
from app.web.main import app


class _FakeSettingsService:
    def load_settings(self) -> AppSettings:
        return AppSettings(
            venv_path="T:/venv",
            python_executable="T:/venv/Scripts/python.exe",
            freqtrade_executable="T:/venv/Scripts/freqtrade.exe",
            user_data_path="T:/user_data",
            use_module_execution=True,
        )


class _FakeBacktestService:
    def __init__(self, command: BacktestRunCommand):
        self.command = command
        self.calls = []

    def build_command(self, **kwargs) -> BacktestRunCommand:
        self.calls.append(kwargs)
        return self.command


class _FakeProcessService:
    def __init__(self):
        self.calls = []

    def execute_command(
        self,
        command,
        on_output=None,
        on_error=None,
        on_finished=None,
        working_directory=None,
        env=None,
    ):
        self.calls.append(
            {
                "command": list(command),
                "working_directory": working_directory,
                "env": env,
            }
        )
        return object()


@contextmanager
def _build_client(
    *,
    settings_service: _FakeSettingsService,
    process_service: _FakeProcessService,
    backtest_service: _FakeBacktestService | None = None,
) -> TestClient:
    app.dependency_overrides.clear()
    app.dependency_overrides[get_settings_service] = lambda: settings_service
    app.dependency_overrides[get_process_service] = lambda: process_service
    if backtest_service is not None:
        app.dependency_overrides[get_backtest_service] = lambda: backtest_service
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_execute_backtest_runs_full_command():
    command = BacktestRunCommand(
        program="T:/venv/Scripts/python.exe",
        args=["-m", "freqtrade", "backtesting", "--strategy", "MultiMeee"],
        cwd="T:/project",
        export_dir="T:/user_data/backtest_results",
        config_file="T:/user_data/config.json",
        strategy_file="T:/user_data/strategies/MultiMeee.py",
    )
    settings_service = _FakeSettingsService()
    process_service = _FakeProcessService()
    backtest_service = _FakeBacktestService(command)

    with _build_client(
        settings_service=settings_service,
        process_service=process_service,
        backtest_service=backtest_service,
    ) as client:
        response = client.post(
            "/api/backtest/execute",
            json={
                "strategy": "MultiMeee",
                "timeframe": "5m",
                "timerange": "20240101-20241231",
                "pairs": ["BTC/USDT"],
                "max_open_trades": 2,
                "dry_run_wallet": 1000.0,
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "started"
    assert len(process_service.calls) == 1
    assert process_service.calls[0]["command"] == command.as_list()
    assert process_service.calls[0]["working_directory"] == command.cwd


def test_download_data_runs_full_command(monkeypatch):
    command = RunCommand(
        program="T:/venv/Scripts/python.exe",
        args=["-m", "freqtrade", "download-data", "--timeframe", "5m"],
        cwd="T:/project",
    )
    settings_service = _FakeSettingsService()
    process_service = _FakeProcessService()

    def _fake_build_command(self, timeframe, timerange=None, pairs=None):
        return command

    monkeypatch.setattr(
        backtest_routes.DownloadDataService,
        "build_command",
        _fake_build_command,
    )

    with _build_client(
        settings_service=settings_service,
        process_service=process_service,
    ) as client:
        response = client.post(
            "/api/download-data",
            json={
                "timeframe": "5m",
                "timerange": "20240101-20241231",
                "pairs": ["BTC/USDT"],
            },
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert len(process_service.calls) == 1
    assert process_service.calls[0]["command"] == command.as_list()
    assert process_service.calls[0]["working_directory"] == command.cwd
