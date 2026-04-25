"""
Unit and integration tests for the Strategy Optimizer session service and store.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.core.models.optimizer_models import (
    BestPointer, OptimizerSession, SessionConfig, SessionStatus,
    TrialMetrics, TrialRecord, TrialStatus,
)
from app.core.models.settings_models import AppSettings
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
    )


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
