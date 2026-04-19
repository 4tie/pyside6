"""
test_loop_service_gates.py — Unit tests for the multi-gate validation pipeline
in LoopService: OOS gate, walk-forward gate, stress gate, consistency gate,
quick mode, and the full gate sequence.
"""
import pytest
from unittest.mock import MagicMock
from pathlib import Path

from app.core.backtests.results_models import BacktestSummary
from app.core.models.loop_models import LoopConfig, LoopIteration
from app.core.services.loop_service import LoopService
from app.core.services.improve_service import ImproveService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service() -> LoopService:
    improve_mock = MagicMock(spec=ImproveService)
    return LoopService(improve_mock)


def _summary(profit: float, trades: int = 50, win_rate: float = 55.0) -> BacktestSummary:
    return BacktestSummary(
        strategy="TestStrategy",
        timeframe="5m",
        total_trades=trades,
        wins=int(trades * win_rate / 100),
        losses=int(trades * (1 - win_rate / 100)),
        draws=0,
        win_rate=win_rate,
        avg_profit=profit / max(trades, 1),
        total_profit=profit,
        total_profit_abs=profit * 100,
        sharpe_ratio=1.0,
        sortino_ratio=1.0,
        calmar_ratio=1.0,
        max_drawdown=10.0,
        max_drawdown_abs=10.0,
        trade_duration_avg=60,
    )


def _config(**kwargs) -> LoopConfig:
    defaults = dict(
        strategy="TestStrategy",
        date_from="20240101",
        date_to="20241231",
        oos_split_pct=20.0,
        walk_forward_folds=4,
        stress_fee_multiplier=2.0,
        stress_slippage_pct=0.1,
        stress_profit_target_pct=50.0,
        consistency_threshold_pct=30.0,
        target_profit_pct=5.0,
        validation_mode="full",
    )
    defaults.update(kwargs)
    return LoopConfig(**defaults)


def _iteration() -> LoopIteration:
    return LoopIteration(
        iteration_number=1,
        params_before={},
        params_after={},
        changes_summary=[],
        sandbox_path=Path("."),
    )


# ---------------------------------------------------------------------------
# OOS gate
# ---------------------------------------------------------------------------

class TestOOSGate:
    def test_passes_when_oos_profit_above_50pct_of_insample(self):
        svc = _make_service()
        config = _config()

        call_count = [0]
        def run_bt(timerange, sandbox_dir, fee_multiplier=1.0, slippage_pct=0.0):
            call_count[0] += 1
            # First call = in-sample (10%), second = OOS (6% > 50% of 10%)
            return _summary(10.0) if call_count[0] == 1 else _summary(6.0)

        result = svc._run_oos_gate(config, Path("."), run_bt)
        assert result.passed is True
        assert result.gate_name == "out_of_sample"

    def test_rejects_when_oos_profit_below_50pct_of_insample(self):
        svc = _make_service()
        config = _config()

        call_count = [0]
        def run_bt(timerange, sandbox_dir, fee_multiplier=1.0, slippage_pct=0.0):
            call_count[0] += 1
            return _summary(10.0) if call_count[0] == 1 else _summary(3.0)

        result = svc._run_oos_gate(config, Path("."), run_bt)
        assert result.passed is False
        assert result.failure_reason is not None

    def test_rejects_when_oos_backtest_fails(self):
        svc = _make_service()
        config = _config()

        call_count = [0]
        def run_bt(timerange, sandbox_dir, fee_multiplier=1.0, slippage_pct=0.0):
            call_count[0] += 1
            return _summary(10.0) if call_count[0] == 1 else None

        result = svc._run_oos_gate(config, Path("."), run_bt)
        assert result.passed is False

    def test_rejects_when_no_date_range(self):
        svc = _make_service()
        config = _config(date_from="", date_to="")
        result = svc._run_oos_gate(config, Path("."), lambda *a, **kw: _summary(5.0))
        assert result.passed is False


# ---------------------------------------------------------------------------
# Walk-forward gate
# ---------------------------------------------------------------------------

class TestWalkForwardGate:
    def test_passes_when_60pct_folds_profitable(self):
        svc = _make_service()
        config = _config(walk_forward_folds=4)

        call_count = [0]
        def run_bt(timerange, sandbox_dir, fee_multiplier=1.0, slippage_pct=0.0):
            call_count[0] += 1
            # 3 of 4 folds profitable = 75% >= 60%
            return _summary(5.0) if call_count[0] <= 3 else _summary(-1.0)

        result = svc._run_walk_forward_gate(config, Path("."), run_bt)
        assert result.passed is True
        assert result.fold_summaries is not None
        assert len(result.fold_summaries) == 4

    def test_rejects_when_fewer_than_60pct_folds_profitable(self):
        svc = _make_service()
        config = _config(walk_forward_folds=4)

        call_count = [0]
        def run_bt(timerange, sandbox_dir, fee_multiplier=1.0, slippage_pct=0.0):
            call_count[0] += 1
            # Only 1 of 4 folds profitable = 25% < 60%
            return _summary(5.0) if call_count[0] == 1 else _summary(-2.0)

        result = svc._run_walk_forward_gate(config, Path("."), run_bt)
        assert result.passed is False
        assert "60%" in result.failure_reason

    def test_rejects_when_no_date_range(self):
        svc = _make_service()
        config = _config(date_from="", date_to="")
        result = svc._run_walk_forward_gate(config, Path("."), lambda *a, **kw: _summary(5.0))
        assert result.passed is False


# ---------------------------------------------------------------------------
# Stress gate
# ---------------------------------------------------------------------------

class TestStressGate:
    def test_passes_when_stress_profit_above_threshold(self):
        svc = _make_service()
        # target_profit_pct=10, stress_profit_target_pct=50 → threshold=5%
        config = _config(target_profit_pct=10.0, stress_profit_target_pct=50.0)

        def run_bt(timerange, sandbox_dir, fee_multiplier=1.0, slippage_pct=0.0):
            return _summary(6.0)  # 6% > 5% threshold

        result = svc._run_stress_gate(config, Path("."), run_bt, "20240101-20241001")
        assert result.passed is True

    def test_rejects_when_stress_profit_below_threshold(self):
        svc = _make_service()
        config = _config(target_profit_pct=10.0, stress_profit_target_pct=50.0)

        def run_bt(timerange, sandbox_dir, fee_multiplier=1.0, slippage_pct=0.0):
            return _summary(3.0)  # 3% < 5% threshold

        result = svc._run_stress_gate(config, Path("."), run_bt, "20240101-20241001")
        assert result.passed is False

    def test_rejects_when_stress_backtest_fails(self):
        svc = _make_service()
        config = _config()

        result = svc._run_stress_gate(config, Path("."), lambda *a, **kw: None, "20240101-20241001")
        assert result.passed is False


# ---------------------------------------------------------------------------
# Consistency gate
# ---------------------------------------------------------------------------

class TestConsistencyGate:
    def test_passes_when_cv_below_threshold(self):
        svc = _make_service()
        config = _config(consistency_threshold_pct=50.0)
        # Low variance folds: CV should be small
        folds = [_summary(10.0), _summary(11.0), _summary(9.0), _summary(10.5)]
        result = svc._run_consistency_gate(config, folds)
        assert result.passed is True

    def test_rejects_when_cv_exceeds_threshold(self):
        svc = _make_service()
        config = _config(consistency_threshold_pct=10.0)
        # High variance folds: CV will be large
        folds = [_summary(1.0), _summary(50.0), _summary(-5.0), _summary(30.0)]
        result = svc._run_consistency_gate(config, folds)
        assert result.passed is False

    def test_passes_with_fewer_than_2_folds(self):
        svc = _make_service()
        config = _config()
        result = svc._run_consistency_gate(config, [_summary(5.0)])
        assert result.passed is True  # Not enough data to reject


# ---------------------------------------------------------------------------
# Quick mode skips gates 3–5
# ---------------------------------------------------------------------------

class TestQuickMode:
    def test_quick_mode_skips_gates_3_to_5(self):
        svc = _make_service()
        config = _config(validation_mode="quick")
        iteration = _iteration()

        gate_calls = []
        def run_bt(timerange, sandbox_dir, fee_multiplier=1.0, slippage_pct=0.0):
            gate_calls.append(timerange)
            return _summary(10.0)

        passed = svc.run_gate_sequence(
            iteration, _summary(10.0), config, Path("."), run_bt
        )
        assert passed is True
        # Quick mode: only Gate 2 (OOS) runs additional backtests
        # Gates 3 (walk-forward), 4 (stress), 5 (consistency) are skipped
        gate_names = [g.gate_name for g in iteration.gate_results]
        assert "in_sample" in gate_names
        assert "out_of_sample" in gate_names
        assert "walk_forward" not in gate_names
        assert "stress_test" not in gate_names
        assert "consistency" not in gate_names

    def test_full_mode_runs_all_gates(self):
        svc = _make_service()
        config = _config(validation_mode="full", walk_forward_folds=2)
        iteration = _iteration()

        def run_bt(timerange, sandbox_dir, fee_multiplier=1.0, slippage_pct=0.0):
            return _summary(10.0)

        passed = svc.run_gate_sequence(
            iteration, _summary(10.0), config, Path("."), run_bt
        )
        assert passed is True
        gate_names = [g.gate_name for g in iteration.gate_results]
        assert "in_sample" in gate_names
        assert "out_of_sample" in gate_names
        assert "walk_forward" in gate_names
        assert "stress_test" in gate_names
        assert "consistency" in gate_names

    def test_gate_sequence_stops_on_first_failure(self):
        svc = _make_service()
        config = _config(validation_mode="full")
        iteration = _iteration()

        call_count = [0]
        def run_bt(timerange, sandbox_dir, fee_multiplier=1.0, slippage_pct=0.0):
            call_count[0] += 1
            # OOS gate: in-sample=10%, OOS=1% (fails 50% threshold)
            return _summary(10.0) if call_count[0] == 1 else _summary(1.0)

        passed = svc.run_gate_sequence(
            iteration, _summary(10.0), config, Path("."), run_bt
        )
        assert passed is False
        assert iteration.validation_gate_passed is False
        # Should stop after Gate 2 failure — Gate 3 should not be in results
        gate_names = [g.gate_name for g in iteration.gate_results]
        assert "walk_forward" not in gate_names
