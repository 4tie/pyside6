"""
Bug condition exploration tests for ImprovePage.

These tests encode the EXPECTED (correct) behavior and are designed to FAIL on
the unfixed code, confirming the two Qt object-lifetime bugs described in the
bugfix spec at .kiro/specs/improve-tab-gui-update-bug/.

Bug 1 — Terminal widget deleted on second call to _update_candidate_preview()
Bug 2 — Accept/Reject/Rollback buttons deleted on second call to _update_comparison_view()

After the fix is applied, both tests should PASS.

Documented failure output (unfixed code):
---------------------------------------------------------------------------
FAILED tests/test_improve_page_bug.py::test_bug_condition_terminal_deleted_on_second_preview_call
  AssertionError: Bug 1 confirmed: self._terminal is a deleted C++ object after the second call
  to _update_candidate_preview(). The clearing loop called deleteLater() on it.
  assert False
    where False = shiboken6.isValid(<[RuntimeError('libshiboken: Internal C++ object
    (TerminalWidget) already deleted.') raised in repr()] TerminalWidget object>)

FAILED tests/test_improve_page_bug.py::test_bug_condition_buttons_deleted_on_second_comparison_call
  AssertionError: Bug 2 confirmed: no valid, visible Accept button found in _comparison_layout
  after two calls to _update_comparison_view(). Total buttons found: 3, valid: 3.
  The pre-created accept_btn was destroyed when arb_widget.deleteLater() ran.
  assert 0 >= 1
---------------------------------------------------------------------------
"""
import pytest
import shiboken6
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtCore import QCoreApplication, QEvent

from app.ui.pages.improve_page import ImprovePage
from app.app_state.settings_state import SettingsState
from app.core.models.settings_models import AppSettings
from app.core.backtests.results_models import BacktestResults, BacktestSummary


# ---------------------------------------------------------------------------
# QApplication fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """Create or reuse a QApplication for the test session."""
    app = QApplication.instance() or QApplication([])
    yield app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings_state(tmp_path) -> SettingsState:
    """Return a real SettingsState whose settings_service returns a valid AppSettings."""
    state = SettingsState()
    settings = AppSettings(user_data_path=str(tmp_path / "user_data"))
    state.settings_service.load_settings = MagicMock(return_value=settings)
    return state


def _make_backtest_results() -> BacktestResults:
    """Return a minimal BacktestResults suitable for _update_comparison_view()."""
    summary = BacktestSummary(
        strategy="TestStrategy",
        timeframe="5m",
        total_trades=10,
        wins=6,
        losses=4,
        draws=0,
        win_rate=60.0,
        avg_profit=0.5,
        total_profit=5.0,
        total_profit_abs=50.0,
        sharpe_ratio=1.2,
        sortino_ratio=1.5,
        calmar_ratio=0.8,
        max_drawdown=10.0,
        max_drawdown_abs=100.0,
        trade_duration_avg=60,
    )
    return BacktestResults(summary=summary)


def _collect_buttons_from_layout(layout) -> list[QPushButton]:
    """Walk a QLayout recursively and collect all QPushButton children."""
    buttons = []
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            if isinstance(widget, QPushButton):
                buttons.append(widget)
            # Recurse into child layouts of the widget
            child_layout = widget.layout()
            if child_layout is not None:
                buttons.extend(_collect_buttons_from_layout(child_layout))
        sub_layout = item.layout()
        if sub_layout is not None:
            buttons.extend(_collect_buttons_from_layout(sub_layout))
    return buttons


# ---------------------------------------------------------------------------
# Bug condition exploration tests
# ---------------------------------------------------------------------------

@pytest.mark.bug_condition
def test_bug_condition_terminal_deleted_on_second_preview_call(qapp, tmp_path):
    """
    Bug 1 — Terminal widget is deleted on the second call to _update_candidate_preview().

    The clearing loop in _update_candidate_preview() iterates over every widget at
    index > 0 in _candidate_layout and calls deleteLater() on each. On the first call
    the terminal is not yet in the layout, so it survives. On the second call the
    terminal (added at the end of the first call) is encountered and scheduled for
    deletion. self._terminal becomes a dangling reference.

    Bug condition: isBugCondition_Terminal(callCount) where callCount >= 2

    EXPECTED OUTCOME on unfixed code: FAIL
      shiboken6.isValid(page._terminal) returns False after the second call.

    EXPECTED OUTCOME after fix: PASS
      The terminal is detached before the clearing loop and remains valid.

    Validates: Requirements 2.1, 2.2
    """
    settings_state = _make_settings_state(tmp_path)

    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=[]):
        page = ImprovePage(settings_state)

    # Set minimal state so _update_candidate_preview() can run without errors
    page._baseline_params = {}
    page._candidate_config = {}

    # Call twice — this is the bug condition (callCount >= 2)
    page._update_candidate_preview()
    page._update_candidate_preview()

    # Process deferred deletions so any deleteLater() calls are actually executed
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    # Assert: terminal must still be a valid Qt object
    assert shiboken6.isValid(page._terminal), (
        "Bug 1 confirmed: self._terminal is a deleted C++ object after the second call "
        "to _update_candidate_preview(). The clearing loop called deleteLater() on it."
    )

    # Assert: append_output must execute without error
    page._terminal.append_output("x")


@pytest.mark.bug_condition
def test_bug_condition_buttons_deleted_on_second_comparison_call(qapp, tmp_path):
    """
    Bug 2 — Accept/Reject/Rollback buttons are deleted on the second call to
    _update_comparison_view().

    The three buttons are pre-created in __init__ and added as children of a transient
    arb_widget inside _update_comparison_view(). When _update_comparison_view() is called
    again, the clearing loop calls arb_widget.deleteLater(), which also destroys all its
    children — including the three pre-created buttons. Subsequent .setVisible() calls
    silently fail and the buttons never appear.

    Bug condition: isBugCondition_Buttons(comparisonViewCallCount) where
    comparisonViewCallCount >= 2

    EXPECTED OUTCOME on unfixed code: FAIL
      The Accept and Reject buttons are deleted C++ objects after the second call.
      No valid, visible Accept/Reject buttons are found in _comparison_layout.

    EXPECTED OUTCOME after fix: PASS
      Fresh button instances are created on every call and remain valid.

    Validates: Requirements 2.3, 2.4
    """
    settings_state = _make_settings_state(tmp_path)

    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=[]):
        page = ImprovePage(settings_state)

    # Set both runs so the comparison view renders the full table + buttons
    results = _make_backtest_results()
    page._baseline_run = results
    page._candidate_run = results

    # Call twice — this is the bug condition (comparisonViewCallCount >= 2)
    page._update_comparison_view()
    page._update_comparison_view()

    # Process deferred deletions so any deleteLater() calls are actually executed
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    # Walk _comparison_layout to find all QPushButton children
    buttons = _collect_buttons_from_layout(page._comparison_layout)

    # Filter to valid Qt objects only
    valid_buttons = [b for b in buttons if shiboken6.isValid(b)]

    # Find Accept and Reject buttons among valid ones
    accept_buttons = [
        b for b in valid_buttons
        if "Accept" in b.text() and not b.isHidden()
    ]
    reject_buttons = [
        b for b in valid_buttons
        if "Reject" in b.text() and not b.isHidden()
    ]

    assert len(accept_buttons) >= 1, (
        f"Bug 2 confirmed: no valid, non-hidden Accept button found in _comparison_layout "
        f"after two calls to _update_comparison_view(). "
        f"Total buttons found: {len(buttons)}, valid: {len(valid_buttons)}. "
        f"The pre-created accept_btn was destroyed when arb_widget.deleteLater() ran."
    )
    assert len(reject_buttons) >= 1, (
        f"Bug 2 confirmed: no valid, non-hidden Reject button found in _comparison_layout "
        f"after two calls to _update_comparison_view(). "
        f"Total buttons found: {len(buttons)}, valid: {len(valid_buttons)}. "
        f"The pre-created reject_btn was destroyed when arb_widget.deleteLater() ran."
    )


# ---------------------------------------------------------------------------
# Imports for preservation tests
# ---------------------------------------------------------------------------

import tempfile
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st
from PySide6.QtWidgets import QFrame, QTableWidget


# ---------------------------------------------------------------------------
# Preservation test helpers
# ---------------------------------------------------------------------------

def _find_widgets_in_layout(layout, widget_type):
    """Recursively find all widgets of a given type in a layout."""
    found = []
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            if isinstance(widget, widget_type):
                found.append(widget)
            child_layout = widget.layout()
            if child_layout is not None:
                found.extend(_find_widgets_in_layout(child_layout, widget_type))
        sub_layout = item.layout()
        if sub_layout is not None:
            found.extend(_find_widgets_in_layout(sub_layout, widget_type))
    return found


# ---------------------------------------------------------------------------
# Preservation tests
# ---------------------------------------------------------------------------

@pytest.mark.preservation
@given(st.just(1))
@h_settings(max_examples=10)
def test_preservation_first_call_candidate_preview(qapp, call_count):
    """
    Test 3 — First-call candidate preview preservation.

    Verifies that a single call to _update_candidate_preview() with a non-empty
    diff correctly renders a QFrame (diff table) and a QPushButton containing
    "Run Candidate Backtest" in _candidate_layout.

    This behavior must be UNCHANGED by the fix.

    Validates: Requirements 3.1, 3.2
    """
    tmp_dir = tempfile.mkdtemp()

    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=[]):
        settings_state = _make_settings_state(MagicMock())
        settings_state.settings_service.load_settings = MagicMock(
            return_value=AppSettings(user_data_path=tmp_dir)
        )
        page = ImprovePage(settings_state)

    # Set a non-empty diff: baseline and candidate differ on stoploss
    page._baseline_params = {"stoploss": -0.10}
    page._candidate_config = {"stoploss": -0.05}

    # Single call — non-buggy input
    page._update_candidate_preview()

    # Assert: _candidate_layout contains a QFrame (the diff table)
    frames = _find_widgets_in_layout(page._candidate_layout, QFrame)
    assert len(frames) >= 1, (
        "Preservation failure: no QFrame found in _candidate_layout after first call "
        "to _update_candidate_preview() with a non-empty diff."
    )

    # Assert: _candidate_layout contains a QPushButton with "Run Candidate Backtest"
    buttons = _find_widgets_in_layout(page._candidate_layout, QPushButton)
    run_buttons = [b for b in buttons if "Run Candidate Backtest" in b.text()]
    assert len(run_buttons) >= 1, (
        f"Preservation failure: no QPushButton with 'Run Candidate Backtest' found in "
        f"_candidate_layout after first call. Buttons found: {[b.text() for b in buttons]}"
    )


@pytest.mark.preservation
@given(st.text(alphabet=st.characters(whitelist_categories=("L", "N", "P", "S"), whitelist_characters=" "), min_size=1, max_size=200))
@h_settings(max_examples=10)
def test_preservation_terminal_streaming(qapp, text):
    """
    Test 4 — Terminal streaming preservation (property-based).

    Verifies that after a single call to _update_candidate_preview(), the terminal
    widget correctly appends and retains arbitrary text via append_output().

    This behavior must be UNCHANGED by the fix.

    Validates: Requirements 3.3, 3.7
    """
    tmp_dir = tempfile.mkdtemp()

    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=[]):
        settings_state = _make_settings_state(MagicMock())
        settings_state.settings_service.load_settings = MagicMock(
            return_value=AppSettings(user_data_path=tmp_dir)
        )
        page = ImprovePage(settings_state)

    # Single call (empty diff is fine for this test)
    page._baseline_params = {}
    page._candidate_config = {}
    page._update_candidate_preview()

    # Append arbitrary text to the terminal
    page._terminal.append_output(text)

    # Assert: terminal output contains the appended text
    output = page._terminal.get_output()
    assert text in output, (
        f"Preservation failure: terminal output does not contain the appended text.\n"
        f"Expected to find: {text!r}\n"
        f"Actual output: {output!r}"
    )


@pytest.mark.preservation
@given(st.just(1))
@h_settings(max_examples=10)
def test_preservation_comparison_table(qapp, call_count):
    """
    Test 5 — Comparison table preservation.

    Verifies that a single call to _update_comparison_view() with both
    _baseline_run and _candidate_run set correctly renders a QTableWidget
    and at least one delta card QFrame in _comparison_layout.

    This behavior must be UNCHANGED by the fix.

    Validates: Requirements 3.3, 3.6
    """
    tmp_dir = tempfile.mkdtemp()

    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=[]):
        settings_state = _make_settings_state(MagicMock())
        settings_state.settings_service.load_settings = MagicMock(
            return_value=AppSettings(user_data_path=tmp_dir)
        )
        page = ImprovePage(settings_state)

    results = _make_backtest_results()
    page._baseline_run = results
    page._candidate_run = results

    # Single call — non-buggy input
    page._update_comparison_view()

    # Assert: _comparison_layout contains a QTableWidget
    tables = _find_widgets_in_layout(page._comparison_layout, QTableWidget)
    assert len(tables) >= 1, (
        "Preservation failure: no QTableWidget found in _comparison_layout after "
        "first call to _update_comparison_view() with both runs set."
    )

    # Assert: _comparison_layout contains at least one delta card QFrame
    frames = _find_widgets_in_layout(page._comparison_layout, QFrame)
    assert len(frames) >= 1, (
        "Preservation failure: no QFrame (delta card) found in _comparison_layout "
        "after first call to _update_comparison_view() with both runs set."
    )


@pytest.mark.preservation
@given(st.lists(st.just({"stoploss": -0.10}), min_size=0, max_size=5))
@h_settings(max_examples=10)
def test_preservation_rollback_button_visibility(qapp, history):
    """
    Test 6 — Rollback button visibility preservation (property-based).

    Verifies that after a single call to _update_comparison_view(), the rollback
    button is visible when _baseline_history is non-empty and hidden when empty.

    This behavior must be UNCHANGED by the fix.

    Validates: Requirements 3.6
    """
    tmp_dir = tempfile.mkdtemp()

    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=[]):
        settings_state = _make_settings_state(MagicMock())
        settings_state.settings_service.load_settings = MagicMock(
            return_value=AppSettings(user_data_path=tmp_dir)
        )
        page = ImprovePage(settings_state)

    results = _make_backtest_results()
    page._baseline_run = results
    page._candidate_run = results
    page._baseline_history = list(history)

    # Single call — non-buggy input
    page._update_comparison_view()

    # Walk _comparison_layout to find the Rollback button
    buttons = _collect_buttons_from_layout(page._comparison_layout)
    rollback_buttons = [b for b in buttons if "Rollback" in b.text()]

    assert len(rollback_buttons) >= 1, (
        "Preservation failure: no Rollback button found in _comparison_layout "
        "after call to _update_comparison_view()."
    )

    rollback_btn = rollback_buttons[0]
    expected_visible = len(history) > 0
    # Use `not isHidden()` rather than `isVisible()` because isVisible() checks
    # the full parent chain — the widget is not shown in tests, so isVisible()
    # always returns False regardless of the explicit setVisible() call.
    actual_visible = not rollback_btn.isHidden()
    assert actual_visible == expected_visible, (
        f"Preservation failure: rollback button visibility mismatch.\n"
        f"history length: {len(history)}, expected visible: {expected_visible}, "
        f"actual visible (not isHidden): {actual_visible}"
    )
