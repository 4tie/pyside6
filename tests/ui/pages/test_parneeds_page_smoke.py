from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from app.core.models.parneeds_models import CandleCoverageReport
from app.core.models.settings_models import AppSettings
from app.core.services.process_run_manager import ProcessRunManager


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def _settings(tmp_path: Path) -> AppSettings:
    user_data = tmp_path / "user_data"
    (user_data / "strategies").mkdir(parents=True)
    (user_data / "config.json").write_text('{"exchange": {"name": "binance"}}', encoding="utf-8")
    return AppSettings(
        python_executable=sys.executable,
        user_data_path=str(user_data),
    )


def _state(settings: AppSettings):
    from app.app_state.settings_state import SettingsState

    state = SettingsState()
    state.current_settings = settings
    return state


def test_parneeds_page_instantiates_and_has_workflow(qt_app, tmp_path):
    from app.ui.pages.parneeds_page import ParNeedsPage

    with patch(
        "app.core.services.backtest_service.BacktestService.get_available_strategies",
        return_value=["DemoStrategy"],
    ):
        page = ParNeedsPage(_state(_settings(tmp_path)), ProcessRunManager())

    assert page is not None
    assert page._workflow_combo.currentText() == "Timerange workflow"
    assert hasattr(page, "_process_manager")


def test_sync_from_backtest_populates_editable_config(qt_app, tmp_path):
    from app.ui.pages.parneeds_page import ParNeedsPage

    with patch(
        "app.core.services.backtest_service.BacktestService.get_available_strategies",
        return_value=["DemoStrategy"],
    ):
        page = ParNeedsPage(_state(_settings(tmp_path)), ProcessRunManager())

    page.sync_from_backtest(
        {
            "strategy": "DemoStrategy",
            "timeframe": "1h",
            "timerange": "20240101-20240201",
            "pairs": ["BTC/USDT", "ETH/USDT"],
            "dry_run_wallet": 500.0,
            "max_open_trades": 4,
        }
    )
    config = page.build_config()

    assert config.strategy == "DemoStrategy"
    assert config.timeframe == "1h"
    assert config.timerange == "20240101-20240201"
    assert config.pairs == ["BTC/USDT", "ETH/USDT"]
    assert config.dry_run_wallet == 500.0
    assert config.max_open_trades == 4


def test_start_with_full_coverage_starts_first_backtest(qt_app, tmp_path):
    from app.ui.pages.parneeds_page import ParNeedsPage

    with patch(
        "app.core.services.backtest_service.BacktestService.get_available_strategies",
        return_value=["DemoStrategy"],
    ):
        page = ParNeedsPage(_state(_settings(tmp_path)), ProcessRunManager())

    page.sync_from_backtest(
        {
            "strategy": "DemoStrategy",
            "timeframe": "5m",
            "timerange": "20240101-20240115",
            "pairs": ["BTC/USDT"],
            "dry_run_wallet": 80.0,
            "max_open_trades": 2,
        }
    )
    page._parneeds_svc.validate_candle_coverage = MagicMock(
        return_value=[
            CandleCoverageReport(
                pair="BTC/USDT",
                timeframe="5m",
                timerange="20240101-20240115",
                first_candle="2024-01-01 00:00",
                last_candle="2024-01-14 23:55",
                expected_candles=4032,
                actual_candles=4032,
            )
        ]
    )
    page._backtest_svc.build_command = MagicMock(return_value=MagicMock(to_display_string=lambda: "freqtrade backtesting"))
    page._start_process = MagicMock()

    page.start_timerange_workflow()

    assert page._phase == "backtest"
    assert page._start_process.call_count == 1
    assert page._pending_windows


def test_start_with_missing_coverage_auto_downloads(qt_app, tmp_path):
    from app.ui.pages.parneeds_page import ParNeedsPage

    with patch(
        "app.core.services.backtest_service.BacktestService.get_available_strategies",
        return_value=["DemoStrategy"],
    ):
        page = ParNeedsPage(_state(_settings(tmp_path)), ProcessRunManager())

    page.sync_from_backtest(
        {
            "strategy": "DemoStrategy",
            "timeframe": "5m",
            "timerange": "20240101-20240115",
            "pairs": ["BTC/USDT"],
            "dry_run_wallet": 80.0,
            "max_open_trades": 2,
        }
    )
    page._parneeds_svc.validate_candle_coverage = MagicMock(
        return_value=[
            CandleCoverageReport(
                pair="BTC/USDT",
                timeframe="5m",
                timerange="20240101-20240115",
                expected_candles=4032,
                actual_candles=0,
                missing_reasons=["no candles found"],
            )
        ]
    )
    page._download_svc.build_command = MagicMock(return_value=MagicMock(to_display_string=lambda: "freqtrade download-data"))
    page._start_process = MagicMock()

    page.start_timerange_workflow()

    assert page._phase == "download"
    page._download_svc.build_command.assert_called_once()
    assert page._download_svc.build_command.call_args.kwargs["prepend"] is False
    assert page._start_process.call_count == 1


def test_start_with_start_and_end_gaps_queues_append_then_prepend(qt_app, tmp_path):
    from app.ui.pages.parneeds_page import ParNeedsPage

    with patch(
        "app.core.services.backtest_service.BacktestService.get_available_strategies",
        return_value=["DemoStrategy"],
    ):
        page = ParNeedsPage(_state(_settings(tmp_path)), ProcessRunManager())

    page.sync_from_backtest(
        {
            "strategy": "DemoStrategy",
            "timeframe": "4h",
            "timerange": "20250430-20260425",
            "pairs": ["HOME/USDT", "ETH/USDT"],
            "dry_run_wallet": 80.0,
            "max_open_trades": 2,
        }
    )
    page._parneeds_svc.validate_candle_coverage = MagicMock(
        return_value=[
            CandleCoverageReport(
                pair="HOME/USDT",
                timeframe="4h",
                timerange="20250430-20260425",
                first_candle="2025-06-12 12:00",
                last_candle="2026-04-24 20:00",
                expected_candles=2160,
                actual_candles=1900,
                missing_reasons=["missing start candles", "candle count below expected"],
            ),
            CandleCoverageReport(
                pair="ETH/USDT",
                timeframe="4h",
                timerange="20250430-20260425",
                first_candle="2025-04-30 00:00",
                last_candle="2026-04-21 00:00",
                expected_candles=2160,
                actual_candles=2137,
                missing_reasons=["missing end candles", "candle count below expected"],
            ),
        ]
    )
    page._download_svc.build_command = MagicMock(return_value=MagicMock(to_display_string=lambda: "freqtrade download-data"))
    page._start_process = MagicMock()

    page.start_timerange_workflow()

    assert page._download_svc.build_command.call_args.kwargs["prepend"] is False
    assert page._download_svc.build_command.call_args.kwargs["pairs"] == ["ETH/USDT"]
    assert page._download_queue == [(True, ["HOME/USDT"], "prepend missing start candles")]


def test_download_recheck_with_gaps_does_not_start_backtests(qt_app, tmp_path):
    from app.ui.pages.parneeds_page import ParNeedsPage

    with patch(
        "app.core.services.backtest_service.BacktestService.get_available_strategies",
        return_value=["DemoStrategy"],
    ):
        page = ParNeedsPage(_state(_settings(tmp_path)), ProcessRunManager())

    page.sync_from_backtest(
        {
            "strategy": "DemoStrategy",
            "timeframe": "5m",
            "timerange": "20240101-20240115",
            "pairs": ["BTC/USDT"],
            "dry_run_wallet": 80.0,
            "max_open_trades": 2,
        }
    )
    page._active_config = page.build_config()
    page._phase = "download"
    page._set_running(True)
    page._parneeds_svc.validate_candle_coverage = MagicMock(
        return_value=[
            CandleCoverageReport(
                pair="BTC/USDT",
                timeframe="5m",
                timerange="20240101-20240115",
                expected_candles=4032,
                actual_candles=0,
                missing_reasons=["no candles found"],
            )
        ]
    )
    page._start_next_backtest = MagicMock()

    page._handle_download_finished(0)

    page._start_next_backtest.assert_not_called()
    assert page._running is False


def test_download_recheck_allows_late_start_only(qt_app, tmp_path):
    from app.ui.pages.parneeds_page import ParNeedsPage

    with patch(
        "app.core.services.backtest_service.BacktestService.get_available_strategies",
        return_value=["DemoStrategy"],
    ):
        page = ParNeedsPage(_state(_settings(tmp_path)), ProcessRunManager())

    page.sync_from_backtest(
        {
            "strategy": "DemoStrategy",
            "timeframe": "4h",
            "timerange": "20250430-20260425",
            "pairs": ["HOME/USDT"],
            "dry_run_wallet": 80.0,
            "max_open_trades": 2,
        }
    )
    page._active_config = page.build_config()
    page._phase = "download"
    page._set_running(True)
    page._parneeds_svc.validate_candle_coverage = MagicMock(
        return_value=[
            CandleCoverageReport(
                pair="HOME/USDT",
                timeframe="4h",
                timerange="20250430-20260425",
                first_candle="2025-06-12 12:00",
                last_candle="2026-04-24 20:00",
                expected_candles=2160,
                actual_candles=1900,
                missing_reasons=["missing start candles", "candle count below expected"],
            )
        ]
    )
    page._start_next_backtest = MagicMock()

    page._handle_download_finished(0)

    page._start_next_backtest.assert_called_once()


def test_stop_clears_pending_windows(qt_app, tmp_path):
    from app.ui.pages.parneeds_page import ParNeedsPage

    with patch(
        "app.core.services.backtest_service.BacktestService.get_available_strategies",
        return_value=["DemoStrategy"],
    ):
        page = ParNeedsPage(_state(_settings(tmp_path)), ProcessRunManager())

    page._pending_windows = [MagicMock()]
    page._set_running(True)

    page._stop()

    assert page._pending_windows == []
    assert page._running is False


def test_main_window_registers_parneeds_page(qt_app, tmp_path):
    from app.ui.main_window import ModernMainWindow

    state = _state(_settings(tmp_path))
    with patch(
        "app.core.services.backtest_service.BacktestService.get_available_strategies",
        return_value=[],
    ), patch(
        "app.core.services.settings_service.SettingsService.load_settings",
        return_value=state.current_settings,
    ), patch(
        "app.ui.pages.optimizer_page.SettingsService.load_settings",
        return_value=state.current_settings,
    ):
        window = ModernMainWindow(settings_state=state)

    assert "parneeds" in window._pages
    assert "parneeds" in window.sidebar._buttons
    window.close()
