"""
Tests for LoopService state machine and SuggestionRotator.

Covers:
  - SuggestionRotator: no duplicate configs (property test)
  - LoopService: happy path, stop, zero_trades, below_min_trades,
    gate short-circuit, hard filter rejection
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.backtests.results_models import BacktestSummary
from app.core.models.loop_models import (
    GateResult,
    HardFilterFailure,
    LoopConfig,
    LoopIteration,
    RobustScoreInput,
)
from app.core.services.loop_service import LoopService, SuggestionRotator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_summary(
    total_profit: float = 10.0,
    win_rate: float = 60.0,
    max_drawdown: float = 15.0,
    total_trades: int = 50,
    profit_factor: float = 1.5,
    expectancy: float = 0.5,
) -> BacktestSummary:
    return BacktestSummary(
        strategy="TestStrategy",
        timeframe="1h",
        total_trades=total_trades,
        wins=int(total_trades * win_rate / 100),
        losses=total_trades - int(total_trades * win_rate / 100),
        draws=0,
        win_rate=win_rate,
        avg_profit=total_profit / max(total_trades, 1),
        total_profit=total_profit,
        total_profit_abs=total_profit * 10,
        sharpe_ratio=1.0,
        sortino_ratio=None,
        calmar_ratio=None,
        max_drawdown=max_drawdown,
        max_drawdown_abs=max_drawdown * 10,
        trade_duration_avg=60,
        profit_factor=profit_factor,
        expectancy=expectancy,
    )


def _make_config(
    max_iterations: int = 5,
    target_profit_pct: float = 5.0,
    target_win_rate: float = 55.0,
    target_max_drawdown: float = 20.0,
    target_min_trades: int = 30,
    stop_on_first_profitable: bool = False,
) -> LoopConfig:
    return LoopConfig(
        strategy="TestStrategy",
        max_iterations=max_iterations,
        target_profit_pct=target_profit_pct,
        target_win_rate=target_win_rate,
        target_max_drawdown=target_max_drawdown,
        target_min_trades=target_min_trades,
        stop_on_first_profitable=stop_on_first_profitable,
    )


def _make_service() -> LoopService:
    improve_service = MagicMock()
    return LoopService(improve_service)


def _make_iteration(
    iteration_number: int = 1,
    params_before: Optional[dict] = None,
    params_after: Optional[dict] = None,
    validation_gate_passed: bool = True,
    status: str = "success",
) -> LoopIteration:
    return LoopIteration(
        iteration_number=iteration_number,
        params_before=params_before or {"stoploss": -0.10},
        params_after=params_after or {"stoploss": -0.08},
        changes_summary=["stoploss: -0.10 → -0.08"],
        sandbox_path=Path("."),
        validation_gate_passed=validation_gate_passed,
        status=status,
    )


# ---------------------------------------------------------------------------
# Property test: SuggestionRotator — no duplicate configs
# ---------------------------------------------------------------------------

class TestSuggestionRotatorNoDuplicates:
    """Property test: SuggestionRotator never submits the same config twice."""

    def test_mark_tried_prevents_duplicates(self) -> None:
        """already_tried returns True after mark_tried is called."""
        rotator = SuggestionRotator({"stoploss": -0.10})
        params = {"stoploss": -0.08}
        assert not rotator.already_tried(params)
        rotator.mark_tried(params)
        assert rotator.already_tried(params)

    def test_different_params_not_duplicate(self) -> None:
        """Different param values are not considered duplicates."""
        rotator = SuggestionRotator({"stoploss": -0.10})
        params1 = {"stoploss": -0.08}
        params2 = {"stoploss": -0.06}
        rotator.mark_tried(params1)
        assert not rotator.already_tried(params2)

    @given(
        st.lists(
            st.floats(min_value=-0.30, max_value=-0.01, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20,
            unique=True,
        )
    )
    @settings(max_examples=100)
    def test_no_duplicate_configs_submitted(self, stoploss_values: List[float]) -> None:
        """Property: no duplicate configs are submitted across multiple mark_tried calls."""
        rotator = SuggestionRotator({"stoploss": -0.10})
        seen_keys = set()

        for val in stoploss_values:
            params = {"stoploss": round(val, 4)}
            key = rotator._config_key(params)
            if key not in seen_keys:
                assert not rotator.already_tried(params), (
                    f"Config {params} was not marked tried but already_tried returned True"
                )
                rotator.mark_tried(params)
                seen_keys.add(key)
            else:
                assert rotator.already_tried(params), (
                    f"Config {params} was marked tried but already_tried returned False"
                )

    def test_exhausted_after_max_steps(self) -> None:
        """exhausted() returns True after _MAX_STEPS_PER_PARAM increments."""
        rotator = SuggestionRotator({})
        for _ in range(SuggestionRotator._MAX_STEPS_PER_PARAM):
            assert not rotator.exhausted("stoploss")
            rotator.increment_step("stoploss")
        assert rotator.exhausted("stoploss")


# ---------------------------------------------------------------------------
# Unit tests: LoopService state machine
# ---------------------------------------------------------------------------

class TestLoopServiceStateMachine:
    """Unit tests for LoopService state machine."""

    def test_start_sets_running(self) -> None:
        """start() sets is_running to True."""
        service = _make_service()
        config = _make_config()
        service.start(config, {"stoploss": -0.10})
        assert service.is_running is True

    def test_stop_causes_should_continue_false(self) -> None:
        """stop() causes should_continue() to return False."""
        service = _make_service()
        config = _make_config()
        service.start(config, {"stoploss": -0.10})
        assert service.should_continue() is True
        service.stop()
        assert service.should_continue() is False

    def test_should_continue_false_after_max_iterations(self) -> None:
        """should_continue() returns False when iteration count reaches max."""
        service = _make_service()
        config = _make_config(max_iterations=2)
        service.start(config, {"stoploss": -0.10})

        # Simulate 2 iterations
        service._current_iteration = 2
        assert service.should_continue() is False

    def test_record_iteration_result_happy_path(self) -> None:
        """record_iteration_result() marks improvement when score exceeds best."""
        service = _make_service()
        config = _make_config()
        service.start(config, {"stoploss": -0.10})

        iteration = _make_iteration(validation_gate_passed=True)
        summary = _make_summary(total_profit=20.0, win_rate=65.0)

        is_improvement = service.record_iteration_result(iteration, summary)

        assert is_improvement is True
        assert iteration.is_improvement is True
        assert service.current_result.best_iteration is iteration

    def test_record_iteration_result_zero_trades(self) -> None:
        """record_iteration_result() marks zero_trades status when trades == 0."""
        service = _make_service()
        config = _make_config()
        service.start(config, {"stoploss": -0.10})

        iteration = _make_iteration(validation_gate_passed=True)
        summary = _make_summary(total_trades=0)

        is_improvement = service.record_iteration_result(iteration, summary)

        assert is_improvement is False
        assert iteration.is_improvement is False
        assert iteration.status == "zero_trades"

    def test_record_iteration_result_below_min_trades(self) -> None:
        """record_iteration_result() sets below_min_trades and prevents best."""
        service = _make_service()
        config = _make_config(target_min_trades=30)
        service.start(config, {"stoploss": -0.10})

        iteration = _make_iteration(validation_gate_passed=True)
        summary = _make_summary(total_trades=10)  # below 30

        is_improvement = service.record_iteration_result(iteration, summary)

        assert is_improvement is False
        assert iteration.below_min_trades is True
        assert iteration.is_improvement is False

    def test_record_iteration_result_gate_not_passed(self) -> None:
        """record_iteration_result() does not set best when gate not passed."""
        service = _make_service()
        config = _make_config()
        service.start(config, {"stoploss": -0.10})

        iteration = _make_iteration(validation_gate_passed=False)
        summary = _make_summary(total_profit=50.0)  # great score but gate failed

        is_improvement = service.record_iteration_result(iteration, summary)

        assert is_improvement is False
        assert iteration.is_improvement is False
        assert service.current_result.best_iteration is None

    def test_record_iteration_result_hard_filter_rejected_not_best(self) -> None:
        service = _make_service()
        config = _make_config()
        service.start(config, {"stoploss": -0.10})

        iteration = _make_iteration(validation_gate_passed=True, status="hard_filter_rejected")
        summary = _make_summary(total_profit=50.0)

        is_improvement = service.record_iteration_result(iteration, summary)

        assert is_improvement is False
        assert service.current_result.best_iteration is None

    def test_finalize_excludes_gate_failed_iterations_from_best(self) -> None:
        service = _make_service()
        config = _make_config()
        service.start(config, {"stoploss": -0.10})

        good_iteration = _make_iteration(iteration_number=1, validation_gate_passed=True, status="success")
        failed_iteration = _make_iteration(iteration_number=2, validation_gate_passed=True, status="gate_failed")

        service.record_iteration_result(good_iteration, _make_summary(total_profit=10.0))
        service.record_iteration_result(failed_iteration, _make_summary(total_profit=60.0))

        result = service.finalize()
        assert result.best_iteration is good_iteration

    def test_record_iteration_error(self) -> None:
        """record_iteration_error() sets status=error and error_message."""
        service = _make_service()
        config = _make_config()
        service.start(config, {"stoploss": -0.10})

        iteration = _make_iteration()
        service.record_iteration_error(iteration, "Process exited with code 1")

        assert iteration.status == "error"
        assert iteration.error_message == "Process exited with code 1"
        assert len(service.current_result.iterations) == 1

    def test_finalize_returns_result(self) -> None:
        """finalize() returns the LoopResult with stop_reason set."""
        service = _make_service()
        config = _make_config()
        service.start(config, {"stoploss": -0.10})

        result = service.finalize("Max iterations reached")

        assert result.stop_reason == "Max iterations reached"
        assert service.is_running is False

    def test_finalize_picks_best_from_validated_iterations(self) -> None:
        """finalize() picks best_iteration from fully-validated iterations."""
        service = _make_service()
        config = _make_config()
        service.start(config, {"stoploss": -0.10})

        # Add two iterations: one validated, one not
        iter1 = _make_iteration(iteration_number=1, validation_gate_passed=True)
        iter2 = _make_iteration(iteration_number=2, validation_gate_passed=False)

        service.record_iteration_result(iter1, _make_summary(total_profit=10.0))
        service.record_iteration_result(iter2, _make_summary(total_profit=50.0))

        result = service.finalize()

        # best_iteration should be iter1 (only validated one)
        assert result.best_iteration is iter1

    def test_hard_filter_rejection_continues_loop(self) -> None:
        """Hard filter rejection sets status=hard_filter_rejected and loop continues."""
        service = _make_service()
        config = _make_config(max_iterations=5)
        service.start(config, {"stoploss": -0.10})

        iteration = _make_iteration(
            validation_gate_passed=False,
            status="hard_filter_rejected",
        )
        iteration.hard_filter_failures = [
            HardFilterFailure(
                filter_name="min_trade_count",
                reason="Only 5 trades",
                evidence="5",
            )
        ]
        service._result.iterations.append(iteration)

        # Loop should still continue (not stopped by hard filter)
        service._current_iteration = 1
        assert service.should_continue() is True

    def test_callbacks_fired_on_iteration_complete(self) -> None:
        """on_iteration_complete callback is fired when iteration is recorded."""
        service = _make_service()
        config = _make_config()
        service.start(config, {"stoploss": -0.10})

        fired_iterations = []
        service.set_callbacks(
            on_iteration_complete=lambda it: fired_iterations.append(it),
            on_loop_complete=lambda r: None,
            on_status=lambda s: None,
        )

        iteration = _make_iteration(validation_gate_passed=True)
        service.record_iteration_result(iteration, _make_summary())

        assert len(fired_iterations) == 1
        assert fired_iterations[0] is iteration

    def test_start_with_initial_results_seeds_best_score(self) -> None:
        """start() with initial_results seeds the best score from baseline."""
        service = _make_service()
        config = _make_config()

        class FakeResults:
            summary = _make_summary(total_profit=5.0)

        service.start(config, {"stoploss": -0.10}, initial_results=FakeResults())

        # Best score should be seeded (not -inf)
        assert service._best_score > float("-inf")
