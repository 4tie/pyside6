"""
Unit and integration tests for the Strategy Optimizer session service and store.
"""
import os
import sqlite3
import json

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.core.models.command_models import BacktestRunCommand
from app.core.models.optimizer_models import (
    BestPointer, OptimizerSession, ParamDef, ParamType, SessionConfig, SessionStatus,
    TrialMetrics, TrialRecord, TrialStatus,
)
from app.core.models.settings_models import AppSettings
from app.core.services.optimizer_session_service import StrategyOptimizerService
from app.core.services.optimizer_store import OptimizerStore
from app.core.services.settings_service import SettingsService


def make_settings_service(tmp_path: Path) -> SettingsService:
    """Create a SettingsService that uses tmp_path as user_data_path."""
    svc = MagicMock(spec=SettingsService)
    settings = AppSettings(user_data_path=str(tmp_path))
    svc.load_settings.return_value = settings
    return svc


def make_session_config() -> SessionConfig:
    return SessionConfig(
        strategy_name="TestStrategy",
        strategy_class="TestStrategy",
        pairs=["BTC/USDT"],
        timeframe="5m",
        total_trials=10,
        score_metric="total_profit_pct",
        score_mode="single_metric",
        param_defs=[
            ParamDef(name="buy_rsi", param_type=ParamType.INT, default=14, low=1, high=99, space="buy"),
            ParamDef(name="sell_rsi", param_type=ParamType.INT, default=80, low=1, high=99, space="sell"),
        ],
    )


def make_service(tmp_path: Path, *, export_dir: Path | None = None) -> StrategyOptimizerService:
    """Create a StrategyOptimizerService with isolated settings and fake backtest command."""
    settings_service = make_settings_service(tmp_path)
    export_path = export_dir or (tmp_path / "backtest_results")
    export_path.mkdir(parents=True, exist_ok=True)

    backtest_service = MagicMock()
    backtest_service.build_command.return_value = BacktestRunCommand(
        program="freqtrade",
        args=["backtesting"],
        cwd=str(tmp_path),
        export_dir=str(export_path),
        config_file=str(tmp_path / "config.json"),
        strategy_file=str(tmp_path / "strategies" / "TestStrategy.py"),
    )
    return StrategyOptimizerService(settings_service, backtest_service)


def run_optimizer_thread(service: StrategyOptimizerService, session: OptimizerSession) -> None:
    thread = service.run_session_async(session)
    thread.join(timeout=10)
    assert not thread.is_alive()


def make_session(session_id: str = "test-session-001") -> OptimizerSession:
    return OptimizerSession(
        session_id=session_id,
        status=SessionStatus.PENDING,
        config=make_session_config(),
        started_at="2026-01-01T00:00:00",
    )


def make_trial_record(session_id: str, trial_number: int, score: float = 1.0) -> TrialRecord:
    return TrialRecord(
        session_id=session_id,
        trial_number=trial_number,
        status=TrialStatus.SUCCESS,
        candidate_params={"buy_rsi": 14},
        metrics=TrialMetrics(total_profit_pct=score),
        score=score,
        score_metric="total_profit_pct",
    )


class TestOptimizerStore:
    def test_sessions_root_resolves_under_user_data(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        root = store.sessions_root()
        assert str(root).startswith(str(tmp_path))
        assert root.name == "sessions"

    def test_session_dir_is_under_sessions_root(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        d = store.session_dir("abc-123")
        assert d.parent == store.sessions_root()
        assert d.name == "abc-123"

    def test_trial_dir_is_under_session_dir(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        d = store.trial_dir("abc-123", 5)
        assert d.parent == store.session_dir("abc-123")
        assert d.name == "trial_005"

    def test_save_and_load_session(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        session = make_session()
        store.save_session(session)
        loaded = store.load_session(session.session_id)
        assert loaded is not None
        assert loaded.session_id == session.session_id
        assert loaded.status == SessionStatus.PENDING

    def test_load_session_missing_returns_none(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        result = store.load_session("nonexistent-session")
        assert result is None

    def test_list_sessions_empty_when_no_sessions(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        assert store.list_sessions() == []

    def test_list_sessions_returns_all_sessions(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        s1 = make_session("session-001")
        s1 = s1.model_copy(update={"started_at": "2026-01-01T00:00:00"})
        s2 = make_session("session-002")
        s2 = s2.model_copy(update={"started_at": "2026-01-02T00:00:00"})
        store.save_session(s1)
        store.save_session(s2)
        sessions = store.list_sessions()
        assert len(sessions) == 2

    def test_list_sessions_sorted_newest_first(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        s1 = make_session("session-001")
        s1 = s1.model_copy(update={"started_at": "2026-01-01T00:00:00"})
        s2 = make_session("session-002")
        s2 = s2.model_copy(update={"started_at": "2026-01-03T00:00:00"})
        store.save_session(s1)
        store.save_session(s2)
        sessions = store.list_sessions()
        assert sessions[0].session_id == "session-002"
        assert sessions[1].session_id == "session-001"

    def test_delete_session_removes_directory(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        session = make_session()
        store.save_session(session)
        assert store.session_dir(session.session_id).exists()
        store.delete_session(session.session_id)
        assert not store.session_dir(session.session_id).exists()

    def test_delete_session_nonexistent_does_not_raise(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        store.delete_session("nonexistent-session")  # should not raise

    def test_save_and_load_trial_record(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        record = make_trial_record("session-001", 1, score=3.5)
        store.save_trial_record("session-001", record)
        loaded = store.load_trial_record("session-001", 1)
        assert loaded is not None
        assert loaded.trial_number == 1
        assert loaded.score == pytest.approx(3.5)

    def test_load_trial_record_missing_returns_none(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        result = store.load_trial_record("session-001", 99)
        assert result is None

    def test_load_all_trial_records_sorted_by_number(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        for i in [3, 1, 2]:
            store.save_trial_record("session-001", make_trial_record("session-001", i))
        records = store.load_all_trial_records("session-001")
        assert [r.trial_number for r in records] == [1, 2, 3]

    def test_load_all_trial_records_empty_session(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        result = store.load_all_trial_records("nonexistent-session")
        assert result == []

    def test_save_and_load_best_pointer(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        # Need session dir to exist
        store.save_session(make_session("session-001"))
        pointer = BestPointer(session_id="session-001", trial_number=3, score=5.44)
        store.save_best_pointer("session-001", pointer)
        loaded = store.load_best_pointer("session-001")
        assert loaded is not None
        assert loaded.trial_number == 3
        assert loaded.score == pytest.approx(5.44)

    def test_load_best_pointer_missing_returns_none(self, tmp_path):
        store = OptimizerStore(make_settings_service(tmp_path))
        result = store.load_best_pointer("nonexistent-session")
        assert result is None

    def test_trial_record_is_idempotent_on_resave(self, tmp_path):
        """Saving a TrialRecord twice produces the same file content."""
        store = OptimizerStore(make_settings_service(tmp_path))
        record = make_trial_record("session-001", 1, score=2.0)
        store.save_trial_record("session-001", record)
        path = store.trial_dir("session-001", 1) / "trial_record.json"
        content1 = path.read_text()
        store.save_trial_record("session-001", record)
        content2 = path.read_text()
        assert content1 == content2


class TestStrategyOptimizerServiceIntegration:
    def test_disabled_param_is_held_at_default_and_not_sampled(self, tmp_path):
        service = make_service(tmp_path)
        optuna_trial = MagicMock()
        optuna_trial.suggest_int.return_value = 33
        defs = [
            ParamDef(
                name="buy_disabled",
                param_type=ParamType.INT,
                default=14,
                low=1,
                high=99,
                space="buy",
                enabled=False,
            ),
            ParamDef(
                name="sell_enabled",
                param_type=ParamType.INT,
                default=80,
                low=1,
                high=99,
                space="sell",
                enabled=True,
            ),
        ]

        params = service._sample_params(optuna_trial, defs)

        assert params["buy_disabled"] == 14
        assert params["sell_enabled"] == 33
        optuna_trial.suggest_int.assert_called_once_with("sell_enabled", 1, 99)

    def test_run_one_mock_trial_persists_record_and_best_pointer(self, tmp_path, monkeypatch):
        service = make_service(tmp_path)
        session = service.create_session(make_session_config().model_copy(update={"total_trials": 1}))

        monkeypatch.setattr(service, "_run_subprocess", lambda *args, **kwargs: 0)
        monkeypatch.setattr(
            service,
            "_parse_trial_result",
            lambda *args, **kwargs: TrialMetrics(
                total_profit_pct=6.25,
                total_profit_abs=12.5,
                win_rate=0.75,
                total_trades=4,
                profit_factor=1.8,
            ),
        )

        run_optimizer_thread(service, session)

        record = service._store.load_trial_record(session.session_id, 1)
        best = service._store.load_best_pointer(session.session_id)
        saved_session = service._store.load_session(session.session_id)

        assert record is not None
        assert record.status == TrialStatus.SUCCESS
        assert record.score == pytest.approx(6.25)
        assert best is not None
        assert best.trial_number == 1
        assert best.score == pytest.approx(6.25)
        assert saved_session is not None
        assert saved_session.status == SessionStatus.COMPLETED

    def test_composite_trial_persists_score_breakdown_and_best_pointer(self, tmp_path, monkeypatch):
        service = make_service(tmp_path)
        config = make_session_config().model_copy(
            update={
                "total_trials": 1,
                "score_metric": "composite",
                "score_mode": "composite",
                "target_min_trades": 100,
                "target_profit_pct": 50.0,
                "max_drawdown_limit": 25.0,
                "target_romad": 2.0,
            }
        )
        session = service.create_session(config)

        monkeypatch.setattr(service, "_run_subprocess", lambda *args, **kwargs: 0)
        monkeypatch.setattr(
            service,
            "_parse_trial_result",
            lambda *args, **kwargs: TrialMetrics(
                total_profit_pct=50.0,
                total_profit_abs=50.0,
                win_rate=0.60,
                total_trades=100,
                max_drawdown_pct=10.0,
                profit_factor=2.0,
                sharpe_ratio=1.5,
            ),
        )

        run_optimizer_thread(service, session)

        record = service._store.load_trial_record(session.session_id, 1)
        best = service._store.load_best_pointer(session.session_id)
        score_data = json.loads((service._store.trial_dir(session.session_id, 1) / "score.json").read_text())

        assert record is not None
        assert record.status == TrialStatus.SUCCESS
        assert record.score_mode == "composite"
        assert record.score_metric == "composite"
        assert record.score_breakdown["final_score"] == pytest.approx(round(record.score, 4))
        assert "romad_score" in record.score_breakdown
        assert best is not None
        assert best.score == pytest.approx(record.score)
        assert score_data["score_mode"] == "composite"
        assert score_data["score_breakdown"] == record.score_breakdown

    def test_failed_trial_is_recorded_and_does_not_stop_session(self, tmp_path, monkeypatch):
        service = make_service(tmp_path)
        session = service.create_session(make_session_config().model_copy(update={"total_trials": 2}))

        monkeypatch.setattr(service, "_run_subprocess", lambda *args, **kwargs: 1)

        run_optimizer_thread(service, session)

        records = service._store.load_all_trial_records(session.session_id)
        saved_session = service._store.load_session(session.session_id)

        assert [record.status for record in records] == [TrialStatus.FAILED, TrialStatus.FAILED]
        assert saved_session is not None
        assert saved_session.trials_completed == 2
        assert saved_session.status == SessionStatus.COMPLETED
        assert service._store.load_best_pointer(session.session_id) is None

    def test_stop_session_terminates_active_subprocess_and_marks_session_stopped(self, tmp_path, monkeypatch):
        service = make_service(tmp_path)
        config = make_session_config().model_copy(
            update={
                "total_trials": 5,
                "param_defs": [
                    ParamDef(
                        name="buy_rsi",
                        param_type=ParamType.INT,
                        default=14,
                        low=10,
                        high=20,
                    )
                ],
            }
        )
        session = service.create_session(config)

        class FakeProcess:
            terminated = False
            killed = False

            def poll(self):
                return None

            def terminate(self):
                self.terminated = True

            def wait(self, timeout=None):
                return 0

            def kill(self):
                self.killed = True

        fake_process = FakeProcess()

        def execute_and_stop(session_arg, trial_number, candidate, trial_dir, on_log_line):
            service._active_subprocess = fake_process
            service.stop_session()
            return make_trial_record(session_arg.session_id, trial_number, score=1.0)

        monkeypatch.setattr(service, "_execute_trial", execute_and_stop)

        run_optimizer_thread(service, session)

        saved_session = service._store.load_session(session.session_id)
        records = service._store.load_all_trial_records(session.session_id)

        assert fake_process.terminated is True
        assert fake_process.killed is False
        assert len(records) == 1
        assert saved_session is not None
        assert saved_session.status == SessionStatus.STOPPED

    def test_execute_trial_writes_freqtrade_strategy_params_file(self, tmp_path, monkeypatch):
        service = make_service(tmp_path)
        session = service.create_session(make_session_config().model_copy(update={"total_trials": 1}))

        strategy_file = tmp_path / "strategies" / "TestStrategy.py"
        strategy_file.parent.mkdir(parents=True, exist_ok=True)
        strategy_file.write_text("class TestStrategy:\n    pass\n", encoding="utf-8")
        live_json = tmp_path / "strategies" / "TestStrategy.json"
        live_json.write_text(
            json.dumps({
                "strategy_name": "TestStrategy",
                "params": {
                    "buy": {"buy_rsi": 14},
                    "sell": {"sell_rsi": 80},
                    "roi": {"0": 0.1},
                    "stoploss": {"stoploss": -0.1},
                },
            }),
            encoding="utf-8",
        )

        monkeypatch.setattr(service, "_run_subprocess", lambda *args, **kwargs: 1)

        trial_dir = service._store.trial_dir(session.session_id, 1)
        record = service._execute_trial(
            session,
            1,
            {"buy_rsi": 21, "sell_rsi": 70},
            trial_dir,
            None,
        )

        strategy_json = trial_dir / "strategy_dir" / "TestStrategy.json"
        trial_params = trial_dir / "params.json"
        data = json.loads(strategy_json.read_text(encoding="utf-8"))
        grouped = json.loads(trial_params.read_text(encoding="utf-8"))

        assert record.status == TrialStatus.FAILED
        assert data["strategy_name"] == "TestStrategy"
        assert data["ft_stratparam_v"] == 1
        assert data["params"]["buy"] == {"buy_rsi": 21}
        assert data["params"]["sell"] == {"sell_rsi": 70}
        assert data["params"]["roi"] == {"0": 0.1}
        assert grouped == {
            "buy_params": {"buy_rsi": 21},
            "sell_params": {"sell_rsi": 70},
        }

    def test_export_best_writes_live_json_atomically_and_creates_backup(self, tmp_path, monkeypatch):
        service = make_service(tmp_path)
        session = service.create_session(make_session_config().model_copy(update={"total_trials": 1}))
        record = make_trial_record(session.session_id, 1, score=3.0)
        record.candidate_params = {"buy_rsi": 21, "sell_rsi": 80}
        service._store.save_trial_record(session.session_id, record)
        service._store.save_best_pointer(
            session.session_id,
            BestPointer(session_id=session.session_id, trial_number=1, score=3.0),
        )

        live_json = tmp_path / "strategies" / "TestStrategy.json"
        live_json.parent.mkdir(parents=True, exist_ok=True)
        live_json.write_text(
            '{"strategy_name":"TestStrategy","params":{"buy":{"buy_rsi":14},"sell":{"sell_rsi":75}}}',
            encoding="utf-8",
        )
        backup_json = tmp_path / "strategies" / "TestStrategy.json.bak"

        rollback = MagicMock()
        rollback._backup_file.return_value = backup_json
        service._rollback = rollback

        replacements: list[tuple[Path, Path]] = []
        real_replace = os.replace

        def capture_replace(src, dst):
            replacements.append((Path(src), Path(dst)))
            real_replace(src, dst)

        monkeypatch.setattr("app.core.parsing.json_parser.os.replace", capture_replace)

        result = service.export_best(session.session_id)

        assert result.success is True
        assert result.live_json_path == str(live_json)
        assert result.backup_path == str(backup_json)
        assert rollback._backup_file.call_args.args[0] == live_json
        assert rollback._prune_backups.call_args.args[0] == live_json
        assert any(src.parent == live_json.parent and dst == live_json for src, dst in replacements)
        exported = json.loads(live_json.read_text(encoding="utf-8"))
        assert exported["strategy_name"] == "TestStrategy"
        assert exported["ft_stratparam_v"] == 1
        assert exported["params"]["buy"] == {"buy_rsi": 21}
        assert exported["params"]["sell"] == {"sell_rsi": 80}

    def test_build_trial_diff_reports_param_and_code_changes(self, tmp_path):
        service = make_service(tmp_path)
        session = service.create_session(make_session_config().model_copy(update={"total_trials": 1}))
        record = make_trial_record(session.session_id, 1, score=3.0)
        record.candidate_params = {"buy_rsi": 21, "sell_rsi": 80}
        service._store.save_trial_record(session.session_id, record)

        strategies_dir = tmp_path / "strategies"
        strategies_dir.mkdir(parents=True)
        (strategies_dir / "TestStrategy.py").write_text(
            "class TestStrategy:\n    value = 1\n",
            encoding="utf-8",
        )
        (strategies_dir / "TestStrategy.json").write_text(
            json.dumps({
                "strategy_name": "TestStrategy",
                "params": {"buy": {"buy_rsi": 14}, "sell": {"sell_rsi": 75}},
            }),
            encoding="utf-8",
        )

        trial_strategy_dir = service._store.trial_dir(session.session_id, 1) / "strategy_dir"
        trial_strategy_dir.mkdir(parents=True)
        (trial_strategy_dir / "TestStrategy.py").write_text(
            "class TestStrategy:\n    value = 2\n",
            encoding="utf-8",
        )
        (trial_strategy_dir / "TestStrategy.json").write_text(
            json.dumps({
                "strategy_name": "TestStrategy",
                "params": {"buy": {"buy_rsi": 21}, "sell": {"sell_rsi": 80}},
            }),
            encoding="utf-8",
        )

        diff = service.build_trial_diff(session.session_id, 1)

        assert diff.success is True
        changes = {change.key: change for change in diff.param_changes}
        assert changes["buy.buy_rsi"].current_value == 14
        assert changes["buy.buy_rsi"].trial_value == 21
        assert changes["sell.sell_rsi"].current_value == 75
        assert changes["sell.sell_rsi"].trial_value == 80
        assert "-    value = 1" in diff.strategy_diff
        assert "+    value = 2" in diff.strategy_diff

    def test_apply_trial_to_strategy_backs_up_and_writes_py_and_json(self, tmp_path):
        service = make_service(tmp_path)
        session = service.create_session(make_session_config().model_copy(update={"total_trials": 1}))
        record = make_trial_record(session.session_id, 1, score=3.0)
        service._store.save_trial_record(session.session_id, record)

        strategies_dir = tmp_path / "strategies"
        strategies_dir.mkdir(parents=True)
        live_py = strategies_dir / "TestStrategy.py"
        live_json = strategies_dir / "TestStrategy.json"
        live_py.write_text("class TestStrategy:\n    value = 1\n", encoding="utf-8")
        live_json.write_text(
            json.dumps({"strategy_name": "TestStrategy", "params": {"buy": {"buy_rsi": 14}}}),
            encoding="utf-8",
        )

        trial_strategy_dir = service._store.trial_dir(session.session_id, 1) / "strategy_dir"
        trial_strategy_dir.mkdir(parents=True)
        (trial_strategy_dir / "TestStrategy.py").write_text(
            "class TestStrategy:\n    value = 9\n",
            encoding="utf-8",
        )
        (trial_strategy_dir / "TestStrategy.json").write_text(
            json.dumps({"strategy_name": "TestStrategy", "params": {"buy": {"buy_rsi": 21}}}),
            encoding="utf-8",
        )

        result = service.apply_trial_to_strategy(session.session_id, 1)

        assert result.success is True
        assert live_py.read_text(encoding="utf-8") == "class TestStrategy:\n    value = 9\n"
        exported = json.loads(live_json.read_text(encoding="utf-8"))
        assert exported["strategy_name"] == "TestStrategy"
        assert exported["params"]["buy"] == {"buy_rsi": 21}
        assert len(result.backup_paths) == 2
        assert any(Path(path).name.startswith("TestStrategy.py.bak_") for path in result.backup_paths)
        assert any(Path(path).name.startswith("TestStrategy.json.bak_") for path in result.backup_paths)

    def test_apply_trial_as_new_strategy_writes_renamed_py_and_json(self, tmp_path):
        service = make_service(tmp_path)
        session = service.create_session(make_session_config().model_copy(update={"total_trials": 1}))
        record = make_trial_record(session.session_id, 1, score=3.0)
        service._store.save_trial_record(session.session_id, record)

        (tmp_path / "strategies").mkdir(parents=True)
        trial_strategy_dir = service._store.trial_dir(session.session_id, 1) / "strategy_dir"
        trial_strategy_dir.mkdir(parents=True)
        (trial_strategy_dir / "TestStrategy.py").write_text(
            "class TestStrategy:\n    value = 9\n",
            encoding="utf-8",
        )
        (trial_strategy_dir / "TestStrategy.json").write_text(
            json.dumps({"strategy_name": "TestStrategy", "params": {"buy": {"buy_rsi": 21}}}),
            encoding="utf-8",
        )

        result = service.apply_trial_as_new_strategy(session.session_id, 1, "Strategy1.py")

        assert result.success is True
        new_py = tmp_path / "strategies" / "Strategy1.py"
        new_json = tmp_path / "strategies" / "Strategy1.json"
        assert "class Strategy1:" in new_py.read_text(encoding="utf-8")
        exported = json.loads(new_json.read_text(encoding="utf-8"))
        assert exported["strategy_name"] == "Strategy1"
        assert exported["params"]["buy"] == {"buy_rsi": 21}

    def test_apply_trial_as_new_strategy_blocks_existing_names(self, tmp_path):
        service = make_service(tmp_path)
        session = service.create_session(make_session_config().model_copy(update={"total_trials": 1}))
        service._store.save_trial_record(session.session_id, make_trial_record(session.session_id, 1))

        strategies_dir = tmp_path / "strategies"
        strategies_dir.mkdir(parents=True)
        (strategies_dir / "Strategy1.py").write_text("class Strategy1:\n    pass\n", encoding="utf-8")
        trial_strategy_dir = service._store.trial_dir(session.session_id, 1) / "strategy_dir"
        trial_strategy_dir.mkdir(parents=True)
        (trial_strategy_dir / "TestStrategy.py").write_text("class TestStrategy:\n    pass\n", encoding="utf-8")
        (trial_strategy_dir / "TestStrategy.json").write_text(
            json.dumps({"strategy_name": "TestStrategy", "params": {}}),
            encoding="utf-8",
        )

        result = service.apply_trial_as_new_strategy(session.session_id, 1, "Strategy1")

        assert result.success is False
        assert "already exists" in result.error_message
        assert "class Strategy1" in (strategies_dir / "Strategy1.py").read_text(encoding="utf-8")

    def test_apply_trial_as_new_strategy_rejects_invalid_name(self, tmp_path):
        service = make_service(tmp_path)
        session = service.create_session(make_session_config().model_copy(update={"total_trials": 1}))
        service._store.save_trial_record(session.session_id, make_trial_record(session.session_id, 1))

        result = service.apply_trial_as_new_strategy(session.session_id, 1, "bad-name.py")

        assert result.success is False
        assert "valid Python identifier" in result.error_message

    def test_set_best_updates_best_pointer_to_manual_trial(self, tmp_path):
        service = make_service(tmp_path)
        session = service.create_session(make_session_config().model_copy(update={"total_trials": 2}))
        service._store.save_trial_record(session.session_id, make_trial_record(session.session_id, 1, score=1.0))
        service._store.save_trial_record(session.session_id, make_trial_record(session.session_id, 2, score=4.0))
        service._store.save_best_pointer(
            session.session_id,
            BestPointer(session_id=session.session_id, trial_number=1, score=1.0),
        )

        service.set_best(session.session_id, 2)

        best = service._store.load_best_pointer(session.session_id)
        assert best is not None
        assert best.trial_number == 2
        assert best.score == pytest.approx(4.0)

    def test_create_session_uses_sqlite_wal_mode_for_optuna_study(self, tmp_path):
        service = make_service(tmp_path)
        session = service.create_session(make_session_config())
        study_db = service._store.session_dir(session.session_id) / "study.db"

        with sqlite3.connect(study_db) as conn:
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]

        assert journal_mode == "wal"
