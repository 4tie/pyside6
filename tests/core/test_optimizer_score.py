"""Unit tests for compute_optimizer_score."""
import math
import pytest
from app.core.services.optimizer_session_service import compute_optimizer_score


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
