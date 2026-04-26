import asyncio

from app.core.parsing.json_parser import write_json_file_atomic
from app.core.services.settings_service import SettingsService
from app.web.api.route_utils import find_run_entry, iter_index_runs, run_response_from_entry
from app.web.api.routes.dashboard import dashboard_summary


def _settings(tmp_path):
    service = SettingsService(str(tmp_path / "settings.json"))
    settings = service.load_settings()
    settings.user_data_path = str(tmp_path / "user_data")
    service.save_settings(settings)
    return service


def _write_index(tmp_path):
    root = tmp_path / "user_data" / "backtest_results"
    root.mkdir(parents=True)
    write_json_file_atomic(
        root / "index.json",
        {
            "updated_at": "2026-04-26T00:00:00",
            "strategies": {
                "Alpha": {
                    "runs": [
                        {
                            "run_id": "run_old",
                            "strategy": "Alpha",
                            "timeframe": "5m",
                            "pairs": ["BTC/USDT"],
                            "timerange": "",
                            "saved_at": "2026-04-24T12:00:00",
                            "profit_total_pct": 4.2,
                            "profit_total_abs": 3.1,
                            "starting_balance": 80,
                            "final_balance": 83.1,
                            "max_drawdown_pct": 2.0,
                            "max_drawdown_abs": 1.5,
                            "trades_count": 12,
                            "wins": 8,
                            "losses": 4,
                            "win_rate_pct": 66.67,
                            "profit_factor": 1.4,
                            "expectancy": 0.2,
                            "run_dir": "Alpha/run_old",
                        }
                    ]
                },
                "Beta": {
                    "runs": [
                        {
                            "run_id": "run_new",
                            "strategy": "Beta",
                            "timeframe": "1h",
                            "pairs": ["ETH/USDT"],
                            "timerange": "",
                            "saved_at": "2026-04-25T12:00:00",
                            "profit_total_pct": 7.5,
                            "profit_total_abs": 4.0,
                            "starting_balance": 80,
                            "final_balance": 84.0,
                            "max_drawdown_pct": 1.0,
                            "max_drawdown_abs": 0.8,
                            "trades_count": 9,
                            "wins": 7,
                            "losses": 2,
                            "win_rate_pct": 77.78,
                            "profit_factor": 1.8,
                            "expectancy": 0.3,
                            "run_dir": "Beta/run_new",
                        }
                    ]
                },
            },
        },
    )


def test_dashboard_summary_aggregates_backend_metrics(tmp_path):
    service = _settings(tmp_path)
    _write_index(tmp_path)

    response = asyncio.run(dashboard_summary(service))

    assert response["metrics"]["total_runs"] == 2
    assert response["metrics"]["total_strategies"] == 2
    assert response["metrics"]["best_profit_pct"] == 7.5
    assert response["metrics"]["best_win_rate_pct"] == 77.78
    assert response["metrics"]["min_drawdown_pct"] == 1.0
    assert response["metrics"]["total_trades"] == 21
    assert response["recent_runs"][0]["run_id"] == "run_new"


def test_route_utils_find_and_shape_runs(tmp_path):
    service = _settings(tmp_path)
    _write_index(tmp_path)

    run = find_run_entry(service, "run_old", "Alpha")
    shaped = run_response_from_entry(run)

    assert len(list(iter_index_runs({"strategies": {"Alpha": {"runs": [run]}}}))) == 1
    assert shaped.run_id == "run_old"
    assert shaped.strategy == "Alpha"
