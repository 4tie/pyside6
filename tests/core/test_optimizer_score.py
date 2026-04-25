"""Unit tests for compute_optimizer_score."""
import math
from types import SimpleNamespace

import pytest
from app.core.services.optimizer_session_service import (
    compute_enhanced_composite_score,
    compute_optimizer_score,
)


class TestComputeOptimizerScore:
    def test_total_profit_pct(self):
        assert compute_optimizer_score({"total_profit_pct": 5.44}, "total_profit_pct") == pytest.approx(5.44)

    def test_total_profit_abs(self):
        assert compute_optimizer_score({"total_profit_abs": 123.45}, "total_profit_abs") == pytest.approx(123.45)

    def test_sharpe_ratio(self):
        assert compute_optimizer_score({"sharpe_ratio": 1.23}, "sharpe_ratio") == pytest.approx(1.23)

    def test_profit_factor(self):
        assert compute_optimizer_score({"profit_factor": 2.5}, "profit_factor") == pytest.approx(2.5)

    def test_win_rate(self):
        assert compute_optimizer_score({"win_rate": 0.58}, "win_rate") == pytest.approx(0.58)

    def test_missing_key_returns_zero(self):
        assert compute_optimizer_score({}, "total_profit_pct") == 0.0

    def test_unknown_metric_returns_zero(self):
        assert compute_optimizer_score({"unknown": 99.9}, "unknown") == 0.0

    def test_zero_trades_returns_zero(self):
        metrics = {
            "total_profit_pct": 0.0,
            "total_profit_abs": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
        }
        assert compute_optimizer_score(metrics, "total_profit_pct") == 0.0

    def test_none_value_returns_zero(self):
        assert compute_optimizer_score({"sharpe_ratio": None}, "sharpe_ratio") == 0.0

    def test_nan_value_returns_zero(self):
        assert compute_optimizer_score({"sharpe_ratio": float("nan")}, "sharpe_ratio") == 0.0

    def test_positive_inf_returns_zero(self):
        assert compute_optimizer_score({"profit_factor": float("inf")}, "profit_factor") == 0.0

    def test_negative_inf_returns_zero(self):
        assert compute_optimizer_score({"total_profit_pct": float("-inf")}, "total_profit_pct") == 0.0

    def test_string_value_returns_zero(self):
        assert compute_optimizer_score({"total_profit_pct": "not_a_number"}, "total_profit_pct") == 0.0

    def test_empty_dict_returns_zero(self):
        assert compute_optimizer_score({}, "win_rate") == 0.0

    def test_negative_profit_is_returned(self):
        """Negative but finite values are valid scores."""
        assert compute_optimizer_score({"total_profit_pct": -3.5}, "total_profit_pct") == pytest.approx(-3.5)

    def test_integer_value_is_accepted(self):
        assert compute_optimizer_score({"total_profit_pct": 5}, "total_profit_pct") == pytest.approx(5.0)

    def test_result_is_always_finite(self):
        """Sanity check: result is always finite."""
        result = compute_optimizer_score({"total_profit_pct": 3.14}, "total_profit_pct")
        assert math.isfinite(result)


class TestComputeEnhancedCompositeScore:
    def _config(self, **overrides):
        values = {
            "target_min_trades": 100,
            "target_profit_pct": 50.0,
            "max_drawdown_limit": 25.0,
            "target_romad": 2.0,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def _metrics(self, **overrides):
        values = {
            "total_trades": 100,
            "total_profit_pct": 50.0,
            "max_drawdown_pct": 10.0,
            "profit_factor": 2.0,
            "sharpe_ratio": 1.5,
            "win_rate": 0.60,
        }
        values.update(overrides)
        return values

    def test_breakdown_contains_expected_rounded_keys(self):
        score, breakdown = compute_enhanced_composite_score(self._metrics(), self._config())

        assert math.isfinite(score)
        assert set(breakdown) == {
            "trade_count_score",
            "profit_score",
            "drawdown_score",
            "romad_score",
            "profit_factor_score",
            "sharpe_score",
            "win_rate_score",
            "base_score",
            "final_score",
        }
        assert all(isinstance(value, float) for value in breakdown.values())
        assert breakdown["final_score"] == round(score, 4)

    def test_trade_count_logarithmic_saturation(self):
        _, target = compute_enhanced_composite_score(
            self._metrics(total_trades=100),
            self._config(target_min_trades=100),
        )
        _, excessive = compute_enhanced_composite_score(
            self._metrics(total_trades=1000),
            self._config(target_min_trades=100),
        )

        assert target["trade_count_score"] == pytest.approx(1.0)
        assert excessive["trade_count_score"] == pytest.approx(1.0)

    def test_low_trade_count_gets_multiplicative_penalty(self):
        score, breakdown = compute_enhanced_composite_score(
            self._metrics(total_trades=25),
            self._config(target_min_trades=100),
        )

        assert breakdown["trade_count_score"] < 1.0
        assert score == pytest.approx(breakdown["base_score"] * 0.25, abs=1e-4)

    def test_quadratic_drawdown_penalty(self):
        _, low_dd = compute_enhanced_composite_score(
            self._metrics(max_drawdown_pct=5.0),
            self._config(max_drawdown_limit=25.0),
        )
        _, high_dd = compute_enhanced_composite_score(
            self._metrics(max_drawdown_pct=20.0),
            self._config(max_drawdown_limit=25.0),
        )

        assert low_dd["drawdown_score"] == pytest.approx(0.96)
        assert high_dd["drawdown_score"] == pytest.approx(0.36)

    def test_drawdown_limit_violation_penalty(self):
        score, breakdown = compute_enhanced_composite_score(
            self._metrics(max_drawdown_pct=30.0),
            self._config(max_drawdown_limit=25.0),
        )

        assert breakdown["drawdown_score"] == pytest.approx(0.0)
        assert score == pytest.approx(breakdown["base_score"] - 0.50, abs=1e-4)

    def test_non_positive_profit_penalty(self):
        score, breakdown = compute_enhanced_composite_score(
            self._metrics(total_profit_pct=0.0),
            self._config(),
        )

        assert breakdown["profit_score"] == pytest.approx(0.0)
        assert breakdown["romad_score"] == pytest.approx(0.0)
        assert score == pytest.approx(breakdown["base_score"] - 1.0, abs=1e-4)

    def test_romad_favors_efficient_profit_over_raw_profit(self):
        efficient_score, efficient = compute_enhanced_composite_score(
            self._metrics(total_profit_pct=40.0, max_drawdown_pct=5.0),
            self._config(target_romad=5.0),
        )
        inefficient_score, inefficient = compute_enhanced_composite_score(
            self._metrics(total_profit_pct=60.0, max_drawdown_pct=25.0),
            self._config(target_romad=5.0),
        )

        assert efficient["romad_score"] > inefficient["romad_score"]
        assert efficient_score > inefficient_score

    def test_nan_inf_and_non_numeric_inputs_return_finite_fallback(self):
        score, breakdown = compute_enhanced_composite_score(
            {
                "total_trades": "bad",
                "total_profit_pct": float("nan"),
                "max_drawdown_pct": float("inf"),
                "profit_factor": "bad",
                "sharpe_ratio": None,
                "win_rate": "bad",
            },
            self._config(
                target_min_trades=float("nan"),
                target_profit_pct=0.0,
                max_drawdown_limit=float("inf"),
                target_romad="bad",
            ),
        )

        assert math.isfinite(score)
        assert math.isfinite(breakdown["final_score"])
