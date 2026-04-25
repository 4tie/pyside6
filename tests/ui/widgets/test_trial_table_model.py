import os
import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.models.optimizer_models import TrialRecord, TrialStatus
from app.ui.widgets.trial_table_model import TRIAL_RATING_COLUMN, TrialTableModel


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def _record(trial_number: int, score: float | None, *, is_best: bool = False) -> TrialRecord:
    return TrialRecord(
        session_id="session",
        trial_number=trial_number,
        status=TrialStatus.SUCCESS if score is not None else TrialStatus.RUNNING,
        score=score,
        is_best=is_best,
    )


def _rating_text(model: TrialTableModel, row: int) -> str:
    index = model.index(row, TRIAL_RATING_COLUMN)
    return model.data(index, Qt.DisplayRole)


def _rating_color(model: TrialTableModel, row: int) -> str:
    index = model.index(row, TRIAL_RATING_COLUMN)
    return model.data(index, Qt.ForegroundRole).name().upper()


def test_trial_ratings_scale_from_one_red_to_seven_green(qapp):
    model = TrialTableModel()
    model.append_trial(_record(1, 0.0))
    model.append_trial(_record(2, 5.0))
    model.append_trial(_record(3, 10.0, is_best=True))

    assert _rating_text(model, 0) == "★"
    assert _rating_text(model, 1) == "★★★★"
    assert _rating_text(model, 2) == "★★★★★★★"
    assert _rating_color(model, 0) == "#FF3B30"
    assert _rating_color(model, 2) == "#31FF72"


def test_best_trial_is_forced_to_seven_stars(qapp):
    model = TrialTableModel()
    model.append_trial(_record(1, 10.0))
    model.append_trial(_record(2, 1.0, is_best=True))

    assert _rating_text(model, 0) == "★★★★★★★"
    assert _rating_text(model, 1) == "★★★★★★★"


def test_unscored_trials_do_not_show_rating(qapp):
    model = TrialTableModel()
    model.append_trial(_record(1, None))

    assert _rating_text(model, 0) == ""
    assert model.data(model.index(0, TRIAL_RATING_COLUMN), Qt.ForegroundRole) is None
