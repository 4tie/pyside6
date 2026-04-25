"""Smoke tests for selected-trial diff and apply controls on OptimizerPage."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from app.core.models.optimizer_models import (
    ApplyTrialResult,
    OptimizerSession,
    SessionConfig,
    TrialDiff,
    TrialMetrics,
    TrialParamChange,
    TrialRecord,
    TrialStatus,
)
from app.core.models.settings_models import AppSettings
from app.core.services.process_run_manager import ProcessRunManager
from app.ui.pages.optimizer_page import OptimizerPage


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def _page(tmp_path: Path) -> OptimizerPage:
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir(parents=True, exist_ok=True)
    (strategies_dir / "TestStrategy.py").write_text(
        "class TestStrategy:\n    pass\n",
        encoding="utf-8",
    )

    settings_service = MagicMock()
    settings_service.load_settings.return_value = AppSettings(user_data_path=str(tmp_path))
    settings_state = MagicMock()
    settings_state.settings_service = settings_service
    return OptimizerPage(settings_state, ProcessRunManager())


def _session() -> OptimizerSession:
    return OptimizerSession(
        session_id="session-1",
        config=SessionConfig(
            strategy_name="TestStrategy",
            strategy_class="TestStrategy",
            total_trials=1,
        ),
    )


def _record() -> TrialRecord:
    return TrialRecord(
        session_id="session-1",
        trial_number=1,
        status=TrialStatus.SUCCESS,
        candidate_params={"buy_rsi": 21},
        metrics=TrialMetrics(total_profit_pct=3.0),
        score=3.0,
    )


def test_selecting_trial_refreshes_diff_area(qt_app, tmp_path):
    page = _page(tmp_path)
    page._active_session = _session()
    record = _record()
    page._trial_model.append_trial(record)
    page._service = MagicMock()
    page._service.build_trial_diff.return_value = TrialDiff(
        success=True,
        param_changes=[
            TrialParamChange(key="buy.buy_rsi", current_value=14, trial_value=21),
        ],
        strategy_diff="-    value = 1\n+    value = 2\n",
    )

    page._on_trial_clicked(page._trial_proxy.index(0, 0))

    assert page._selected_trial == record
    assert page._param_diff_table.rowCount() == 1
    assert page._param_diff_table.item(0, 0).text() == "buy.buy_rsi"
    assert "value = 2" in page._strategy_diff_view.toPlainText()
    page._service.build_trial_diff.assert_called_once_with("session-1", 1)


def test_build_config_reads_composite_score_controls_on_start(qt_app, tmp_path):
    page = _page(tmp_path)
    page._strategy_combo.setCurrentText("TestStrategy")
    page._score_combo.setCurrentIndex(page._score_combo.findData("composite"))
    page._target_trades_spin.setValue(150)
    page._target_profit_spin.setValue(75.0)
    page._max_drawdown_spin.setValue(18.5)
    page._target_romad_spin.setValue(3.0)

    config = page._build_config()

    assert config.score_mode == "composite"
    assert config.score_metric == "composite"
    assert config.target_min_trades == 150
    assert config.target_profit_pct == pytest.approx(75.0)
    assert config.max_drawdown_limit == pytest.approx(18.5)
    assert config.target_romad == pytest.approx(3.0)


def test_apply_to_strategy_action_calls_service(qt_app, tmp_path, monkeypatch):
    page = _page(tmp_path)
    page._active_session = _session()
    page._selected_trial = _record()
    page._service = MagicMock()
    page._service.apply_trial_to_strategy.return_value = ApplyTrialResult(
        success=True,
        strategy_py_path="/tmp/TestStrategy.py",
        strategy_json_path="/tmp/TestStrategy.json",
    )
    page._service.build_trial_diff.return_value = TrialDiff(success=True)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    page._apply_selected_to_strategy()

    page._service.apply_trial_to_strategy.assert_called_once_with("session-1", 1)


def test_apply_new_strategy_normalizes_py_suffix(qt_app, tmp_path, monkeypatch):
    page = _page(tmp_path)
    page._active_session = _session()
    page._selected_trial = _record()
    page._service = MagicMock()
    page._service.apply_trial_as_new_strategy.return_value = ApplyTrialResult(
        success=True,
        strategy_py_path="/tmp/Strategy1.py",
        strategy_json_path="/tmp/Strategy1.json",
    )
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("Strategy1.py", True))
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    page._apply_selected_as_new_strategy()

    page._service.apply_trial_as_new_strategy.assert_called_once_with("session-1", 1, "Strategy1")
