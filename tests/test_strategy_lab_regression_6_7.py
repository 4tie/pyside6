"""Regression tests for Bugs 6 and 7 in the strategy-lab-bugfix spec.

Bug 6: _on_start() unconditionally wiped _latest_diagnosis_input, causing an
       infinite baseline loop when called as a baseline-completion restart.

       Root cause of the original regression: _on_baseline_backtest_finished()
       cleared _baseline_in_progress BEFORE scheduling the QTimer, so by the
       time _on_start() ran the flag was already False and the guard missed.

       Fix: _on_baseline_backtest_finished() keeps _baseline_in_progress=True
       until _on_start() runs; _on_start() clears it itself after the guard.

Bug 7: _update_state_machine() ignored _baseline_in_progress, leaving the Start
       button and config widgets enabled while the baseline subprocess was running.

**Validates: Requirements 2.5, 2.6, 2.7, 3.1**
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from PySide6.QtWidgets import QApplication

from app.app_state.settings_state import SettingsState
from app.core.models.settings_models import AppSettings
from app.core.models.loop_models import LoopConfig
from app.core.services.improve_service import ImproveService


# ---------------------------------------------------------------------------
# QApplication fixture (session-scoped to avoid multiple instances)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """Create or reuse a QApplication for the test session."""
    app = QApplication.instance() or QApplication([])
    yield app


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_app_settings(tmp_path: Path) -> AppSettings:
    """Return a minimal AppSettings pointing at tmp_path."""
    user_data = tmp_path / "user_data"
    user_data.mkdir(parents=True, exist_ok=True)
    (user_data / "strategies").mkdir(exist_ok=True)
    return AppSettings(
        user_data_path=str(user_data),
        python_executable="python",
        freqtrade_executable="freqtrade",
        venv_path=str(tmp_path / "venv"),
    )


def _make_settings_state(tmp_path: Path) -> SettingsState:
    """Return a SettingsState whose settings_service returns a valid AppSettings."""
    state = SettingsState()
    settings = _make_app_settings(tmp_path)
    state.settings_service.load_settings = MagicMock(return_value=settings)
    state.settings_service.save_settings = MagicMock()
    return state


def _make_loop_page(settings_state: SettingsState):
    """Instantiate LoopPage with mocked strategy list."""
    from app.ui.pages.loop_page import LoopPage
    with patch.object(ImproveService, "get_available_strategies", return_value=["TestStrategy"]):
        page = LoopPage(settings_state)
    return page


def _make_loop_config(
    strategy: str = "TestStrategy",
    timeframe: str = "5m",
    date_from: str = "20240101",
    date_to: str = "20240131",
) -> LoopConfig:
    """Return a minimal LoopConfig for testing."""
    return LoopConfig(
        strategy=strategy,
        timeframe=timeframe,
        max_iterations=5,
        date_from=date_from,
        date_to=date_to,
        oos_split_pct=20.0,
        validation_mode="full",
    )


# ===========================================================================
# Test 6a — Baseline-completion restart preserves _latest_diagnosis_input
# ===========================================================================

class TestBug6BaselineRestartPreservesInput:
    """Regression test for Bug 6: baseline-completion restart must NOT wipe
    _latest_diagnosis_input when _baseline_in_progress is True.

    The correct call path (after the fix) is:
      _on_baseline_backtest_finished():
        1. sets _latest_diagnosis_input = DiagnosisInput(...)
        2. keeps _baseline_in_progress = True   ← does NOT clear it
        3. schedules QTimer.singleShot(100, self._on_start)

      _on_start() (100ms later):
        1. guard: _baseline_in_progress is True → skip reset
        2. clears _baseline_in_progress = False
        3. needs_baseline = False (sentinel is not None) → proceeds to loop start

    **Validates: Requirements 2.6**
    """

    def test_baseline_restart_preserves_latest_diagnosis_input(self, qapp, tmp_path):
        """Assert _latest_diagnosis_input is NOT reset when _baseline_in_progress=True.

        **Validates: Requirements 2.6**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)
        page._ensure_loop_runtime_state()

        # Simulate the state just before the baseline-completion restart fires:
        # _baseline_in_progress is True (not yet cleared) and _latest_diagnosis_input
        # has been set to the freshly-parsed baseline result.
        sentinel = MagicMock(name="DiagnosisInput_sentinel")
        page._baseline_in_progress = True
        page._latest_diagnosis_input = sentinel

        # Mock out everything after the reset guard to prevent full loop execution.
        # We need to stop at the point where _loop_service.start() would be called,
        # because the sentinel MagicMock would cause TypeError in ResultsDiagnosisService.
        with patch.object(page, "_ensure_loop_runtime_state"):
            with patch.object(page, "_validate_loop_inputs", return_value=None):
                with patch.object(page, "_save_preferences"):
                    with patch.object(
                        page._improve_service,
                        "load_baseline_params",
                        return_value={"stoploss": -0.10},
                    ):
                        with patch.object(page, "_build_loop_config", return_value=_make_loop_config()):
                            with patch.object(page, "_clear_history_ui"):
                                with patch.object(page, "_reset_iteration_runtime"):
                                    with patch.object(page._loop_service, "start"):
                                        with patch.object(page._loop_service, "set_callbacks"):
                                            with patch.object(page, "_run_next_iteration"):
                                                page._on_start()

        # After _on_start() runs with _baseline_in_progress=True:
        # - the guard skips the reset
        # - _baseline_in_progress is cleared to False by _on_start itself
        # - _latest_diagnosis_input must still be the sentinel
        assert page._latest_diagnosis_input is sentinel, (
            "_latest_diagnosis_input must NOT be reset to None when _baseline_in_progress=True "
            "at the time _on_start() is called. "
            f"Got: {page._latest_diagnosis_input!r}. "
            "Bug 6 regression: the guard must protect the freshly-set baseline result."
        )
        # Also verify _baseline_in_progress was cleared by _on_start
        assert page._baseline_in_progress is False, (
            "_baseline_in_progress must be False after _on_start() completes."
        )


# ===========================================================================
# Test 6b — Fresh user start resets _latest_diagnosis_input
# ===========================================================================

class TestBug6FreshStartResetsInput:
    """Regression test for Bug 6 preservation: a fresh user-initiated start
    (where _baseline_in_progress=False) must still reset _latest_diagnosis_input.

    **Validates: Requirements 2.5, 3.1**
    """

    def test_fresh_user_start_resets_latest_diagnosis_input(self, qapp, tmp_path):
        """Assert _latest_diagnosis_input IS reset to None when _baseline_in_progress=False.

        **Validates: Requirements 2.5, 3.1**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)
        page._ensure_loop_runtime_state()

        # Simulate stale data from a prior session.
        sentinel = MagicMock(name="stale_DiagnosisInput")
        page._baseline_in_progress = False
        page._latest_diagnosis_input = sentinel

        # Track the value of _latest_diagnosis_input when _run_baseline_backtest is called.
        captured_value_at_baseline = []

        def tracking_run_baseline(config, strategy, settings):
            captured_value_at_baseline.append(page._latest_diagnosis_input)

        with patch.object(page, "_validate_loop_inputs", return_value=None):
            with patch.object(page, "_save_preferences"):
                with patch.object(
                    page._improve_service,
                    "load_baseline_params",
                    return_value={"stoploss": -0.10},
                ):
                    with patch.object(page, "_build_loop_config", return_value=_make_loop_config()):
                        with patch.object(page, "_run_baseline_backtest", side_effect=tracking_run_baseline):
                            page._on_start()

        assert len(captured_value_at_baseline) == 1, (
            "_run_baseline_backtest should be called once (needs_baseline=True after reset). "
            f"Called {len(captured_value_at_baseline)} time(s)."
        )
        assert captured_value_at_baseline[0] is None, (
            "_latest_diagnosis_input must be None when _run_baseline_backtest is called "
            "(i.e., the guard reset it because _baseline_in_progress=False). "
            f"Got: {captured_value_at_baseline[0]!r}."
        )


# ===========================================================================
# Test 7a — UI busy during baseline phase
# ===========================================================================

class TestBug7UIBusyDuringBaseline:
    """Regression test for Bug 7: _update_state_machine() must treat the page
    as busy when _baseline_in_progress=True, even if _loop_service.is_running=False.

    **Validates: Requirements 2.7**
    """

    def test_start_btn_disabled_during_baseline(self, qapp, tmp_path):
        """Assert _start_btn.isEnabled() is False when _baseline_in_progress=True.

        **Validates: Requirements 2.7**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)
        page._ensure_loop_runtime_state()

        # Simulate the baseline subprocess running:
        # LoopService has NOT been started yet, so is_running=False.
        page._baseline_in_progress = True

        from app.core.services.loop_service import LoopService
        with patch.object(LoopService, "is_running", new_callable=PropertyMock, return_value=False):
            page._update_state_machine()

        assert not page._start_btn.isEnabled(), (
            "_start_btn must be DISABLED while _baseline_in_progress=True. "
            "Bug 7 regression: _update_state_machine only checked is_running, "
            "which is False during the baseline phase."
        )

    def test_stop_btn_visible_and_enabled_during_baseline(self, qapp, tmp_path):
        """Assert _stop_btn is not hidden and is enabled during baseline.

        **Validates: Requirements 2.7**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)
        page._ensure_loop_runtime_state()

        page._baseline_in_progress = True

        from app.core.services.loop_service import LoopService
        with patch.object(LoopService, "is_running", new_callable=PropertyMock, return_value=False):
            page._update_state_machine()

        # isHidden() checks only the widget's own visibility flag (no parent chain needed).
        assert not page._stop_btn.isHidden(), (
            "_stop_btn must not be hidden while _baseline_in_progress=True."
        )
        assert page._stop_btn.isEnabled(), (
            "_stop_btn must be ENABLED while _baseline_in_progress=True."
        )


# ===========================================================================
# Test 7b — UI not busy after baseline clears
# ===========================================================================

class TestBug7UIIdleAfterBaselineClears:
    """Regression test for Bug 7 preservation: once _baseline_in_progress=False
    and is_running=False, the Start button must be re-enabled (given valid config).

    **Validates: Requirements 2.7**
    """

    def test_start_btn_enabled_after_baseline_clears(self, qapp, tmp_path):
        """Assert _start_btn.isEnabled() is True when baseline is done and loop is idle.

        **Validates: Requirements 2.7**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)
        page._ensure_loop_runtime_state()

        # Baseline is done, loop service not running.
        page._baseline_in_progress = False

        # Select a valid strategy in the combo so has_strategy=True.
        idx = page._strategy_combo.findText("TestStrategy")
        if idx >= 0:
            page._strategy_combo.setCurrentIndex(idx)
        else:
            page._strategy_combo.setCurrentText("TestStrategy")

        from app.core.services.loop_service import LoopService
        with patch.object(LoopService, "is_running", new_callable=PropertyMock, return_value=False):
            page._update_state_machine()

        assert page._start_btn.isEnabled(), (
            "_start_btn must be ENABLED when _baseline_in_progress=False, "
            "is_running=False, and a valid strategy is selected."
        )
